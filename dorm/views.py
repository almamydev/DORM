import logging

from django.db.models import QuerySet
from django.http import FileResponse, Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import access, executor, exports
from .exceptions import DormStorageError
from .storage import get_storage

logger = logging.getLogger("dorm")

_MAX_ROWS = 200


def _is_accessible(request) -> bool:
    """See dorm/access.py for the full DEBUG / auth / permission rules."""
    return access.is_accessible(request)


def playground(request):
    if not _is_accessible(request):
        raise Http404
    return render(request, "dorm/playground.html")


def run_query(request):
    """
    Run a notebook flow. POST `cells` (repeated): every cell above the target
    plus the target itself, in order. A single `code` field is also accepted.

    Response headers tell the client how it went:
      X-Dorm-Status: ok | error
      X-Dorm-Cell:   0-based index of the failing cell (errors only)
    """
    if not _is_accessible(request):
        raise Http404
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    cells = request.POST.getlist("cells") or [request.POST.get("code", "")]
    if not cells[-1].strip():
        response = render(request, "dorm/partials/result.html", {"result_type": "none"})
        response["X-Dorm-Status"] = "ok"
        return response

    _record_history(cells[-1].strip())
    outcome = executor.execute_flow(cells)

    if not outcome["success"]:
        response = render(request, "dorm/partials/error.html", {
            "error_type": outcome["error_type"],
            "error_message": outcome["error"],
            "traceback": outcome["traceback"],
            "cell": outcome["cell"] + 1 if len(cells) > 1 else None,
        })
        response["X-Dorm-Status"] = "error"
        response["X-Dorm-Cell"] = str(outcome["cell"])
        return response

    response = render(request, "dorm/partials/result.html", _serialize_result(outcome["result"]))
    response["X-Dorm-Status"] = "ok"
    return response


def save_command(request):
    if not _is_accessible(request):
        raise Http404
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    name = request.POST.get("name", "").strip()
    code = request.POST.get("code", "").strip()
    if not name or not code:
        return JsonResponse({"ok": False, "error": "name and code are required"}, status=400)
    try:
        get_storage().save_command(name, code)
    except DormStorageError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
    return JsonResponse({"ok": True, "name": name})


def export(request):
    """
    Re-run a flow and download its full, untruncated result.
    POST: cells (repeated), format=csv|json, verbose=1|0
    """
    if not _is_accessible(request):
        raise Http404
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    fmt = request.POST.get("format")
    if fmt not in ("csv", "json"):
        return JsonResponse({"ok": False, "error": "format must be csv or json"}, status=400)

    cells = request.POST.getlist("cells")
    if not cells or not cells[-1].strip():
        return JsonResponse({"ok": False, "error": "nothing to export"}, status=400)

    outcome = executor.execute_flow(cells)
    if not outcome["success"]:
        return JsonResponse(
            {"ok": False, "error": f"{outcome['error_type']}: {outcome['error']}"}, status=400,
        )

    table = _tabulate(outcome["result"])
    if table is None or table["empty"]:
        return JsonResponse({"ok": False, "error": "the result has no rows to export"}, status=400)

    headers = table["labels"] if request.POST.get("verbose") == "1" else table["names"]
    fh, filename, content_type = exports.build_export(
        fmt, headers, table["rows"], f"{table['model_name']}_records",
    )
    return FileResponse(fh, as_attachment=True, filename=filename, content_type=content_type)


def history(request):
    """
    Modal body: recent runs + saved commands (both tabs rendered at once).
    ?format=json returns {"recents": [code, ...]} newest first, for Alt+Up/Down.
    """
    if not _is_accessible(request):
        raise Http404

    if request.GET.get("format") == "json":
        try:
            recents = [e.get("code", "") for e in get_storage().get_history()]
        except DormStorageError as exc:
            return JsonResponse({"recents": [], "error": str(exc)}, status=500)
        return JsonResponse({"recents": recents})

    error = None
    recents, saved = [], []
    try:
        storage = get_storage()
        for entry in storage.get_history():
            ts = parse_datetime(entry.get("ts") or "")
            recents.append({
                "code": entry.get("code", ""),
                "ts": timezone.localtime(ts) if ts and timezone.is_aware(ts) else ts,
            })
        saved = [{"name": n, "code": c} for n, c in sorted(storage.get_saved_commands().items())]
    except DormStorageError as exc:
        error = str(exc)

    return render(request, "dorm/partials/history.html", {
        "recents": recents, "saved": saved, "error": error,
    })


def _record_history(code: str) -> None:
    # Storage problems must never block running a query.
    try:
        get_storage().add_history(code)
    except DormStorageError as exc:
        logger.warning("DORM: could not record history: %s", exc)


# --- result serialisation ---

def _fmt(value) -> str:
    return "NULL" if value is None else str(value)


def _field_label(model, key: str) -> str:
    """Return verbose_name for a model field key, falling back to the key itself."""
    try:
        vn = str(model._meta.get_field(key).verbose_name)
        return vn if vn else key
    except Exception:
        return key


def _meta_columns(meta_fields) -> tuple[list, list]:
    """Return (verbose_labels, field_names) for a list of concrete meta fields."""
    labels = [str(f.verbose_name) or f.name for f in meta_fields]
    names  = [f.name for f in meta_fields]
    return labels, names


def _is_instance(obj) -> bool:
    return hasattr(obj, "_meta") and not isinstance(obj, type)


def _tabulate(result, limit: int | None = None) -> dict | None:
    """
    Describe a tabular result as
      {"model_name", "labels", "names", "rows", "empty"}
    where `rows` lazily yields formatted rows (at most `limit` when given;
    unbounded querysets are streamed with .iterator()).
    Returns None when the result is not tabular.
    """
    if isinstance(result, QuerySet):
        return _tabulate_queryset(result, limit)

    if _is_instance(result):
        result = [result]
    if isinstance(result, (list, tuple)) and result and _is_instance(result[0]):
        labels, names = _meta_columns(result[0]._meta.concrete_fields)
        items = result if limit is None else result[:limit]
        return {
            "model_name": result[0].__class__.__name__.lower(),
            "labels": labels,
            "names": names,
            "rows": ([_fmt(getattr(obj, fn)) for fn in names] for obj in items),
            "empty": False,
        }
    return None


def _tabulate_queryset(qs: QuerySet, limit: int | None) -> dict:
    source = iter(qs[:limit]) if limit is not None else qs.iterator(chunk_size=2000)
    first  = next(source, None)
    table  = {"model_name": qs.model.__name__.lower(), "labels": [], "names": [],
              "rows": iter(()), "empty": first is None}
    if first is None:
        return table

    def all_rows():
        yield first
        yield from source

    iterable = qs._iterable_class.__name__

    if iterable == "ValuesIterable":
        names  = list(first.keys())
        labels = [_field_label(qs.model, k) for k in names]
        rows   = ([_fmt(row[k]) for k in names] for row in all_rows())

    elif iterable in ("ValuesListIterable", "FlatValuesListIterable", "NamedValuesListIterable"):
        qs_fields = list(qs._fields) if qs._fields else None
        if not isinstance(first, (list, tuple)):
            names  = qs_fields or ["value"]
            labels = [_field_label(qs.model, qs_fields[0])] if qs_fields else ["value"]
            rows   = ([_fmt(v)] for v in all_rows())
        else:
            names  = qs_fields or [f"col_{i}" for i in range(len(first))]
            labels = [_field_label(qs.model, fn) for fn in qs_fields] if qs_fields else list(names)
            rows   = ([_fmt(v) for v in row] for row in all_rows())

    else:
        # ModelIterable (default queryset)
        labels, names = _meta_columns(qs.model._meta.concrete_fields)
        rows = ([_fmt(getattr(obj, fn)) for fn in names] for obj in all_rows())

    table.update(labels=labels, names=names, rows=rows)
    return table


def _total_rows(result) -> int | None:
    try:
        return result.count() if isinstance(result, QuerySet) else len(result)
    except Exception:
        return None


def _serialize_result(result) -> dict:
    if result is None:
        return {"result_type": "none"}

    table = _tabulate(result, _MAX_ROWS + 1)
    if table is None:
        return {"result_type": "value", "value": repr(result)}
    if table["empty"]:
        return {"result_type": "empty"}

    rows      = list(table["rows"])
    truncated = len(rows) > _MAX_ROWS
    rows      = rows[:_MAX_ROWS]
    return {
        "result_type": "table",
        "model_name": table["model_name"],
        "columns_meta": list(zip(table["labels"], table["names"])),
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "total": _total_rows(result) if truncated else len(rows),
    }
