from django.conf import settings
from django.db.models import QuerySet
from django.http import Http404
from django.shortcuts import render

from . import executor

_MAX_ROWS = 200


def _is_accessible(request) -> bool:
    """
    Returns True when the request should be allowed into the playground.

    Rules:
      - DEBUG=False              → always denied (404)
      - DORM_AUTH_ACCESS=True    → DEBUG=True AND user must be authenticated
      - default                  → DEBUG=True is sufficient (no auth required)
    """
    if not settings.DEBUG:
        return False
    if getattr(settings, "DORM_AUTH_ACCESS", False):
        return request.user.is_authenticated
    return True


def playground(request):
    if not _is_accessible(request):
        raise Http404
    return render(request, "dorm/playground.html")


def run_query(request):
    if not _is_accessible(request):
        raise Http404

    code = request.POST.get("code", "").strip()
    if not code:
        return render(request, "dorm/partials/result.html", {"result_type": "none"})

    outcome = executor.execute(code)

    if not outcome["success"]:
        return render(request, "dorm/partials/error.html", {
            "error_type": outcome["error_type"],
            "error_message": outcome["error"],
            "traceback": outcome["traceback"],
        })

    ctx = _serialize_result(outcome["result"])
    return render(request, "dorm/partials/result.html", ctx)


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


def _serialize_result(result) -> dict:
    if result is None:
        return {"result_type": "none"}

    if isinstance(result, QuerySet):
        return _serialize_queryset(result)

    # Single model instance
    if hasattr(result, "_meta"):
        labels, field_names = _meta_columns(result._meta.concrete_fields)
        return {
            "result_type": "table",
            "model_name": result.__class__.__name__.lower(),
            "columns_meta": list(zip(labels, field_names)),
            "rows": [[_fmt(getattr(result, fn)) for fn in field_names]],
            "row_count": 1,
            "truncated": False,
        }

    # List / tuple of model instances
    if isinstance(result, (list, tuple)) and result and hasattr(result[0], "_meta"):
        labels, field_names = _meta_columns(result[0]._meta.concrete_fields)
        rows = [[_fmt(getattr(row, fn)) for fn in field_names] for row in result[:_MAX_ROWS]]
        return {
            "result_type": "table",
            "model_name": result[0].__class__.__name__.lower(),
            "columns_meta": list(zip(labels, field_names)),
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(result) > _MAX_ROWS,
        }

    return {"result_type": "value", "value": repr(result)}


def _serialize_queryset(qs: QuerySet) -> dict:
    iterable = qs._iterable_class.__name__

    if iterable == "ValuesIterable":
        sample = list(qs[: _MAX_ROWS + 1])
        truncated = len(sample) > _MAX_ROWS
        sample = sample[:_MAX_ROWS]
        if not sample:
            return {"result_type": "empty"}
        raw_names = list(sample[0].keys())
        labels    = [_field_label(qs.model, k) for k in raw_names]
        rows      = [[_fmt(row[k]) for k in raw_names] for row in sample]

    elif iterable in ("ValuesListIterable", "FlatValuesListIterable", "NamedValuesListIterable"):
        sample = list(qs[: _MAX_ROWS + 1])
        truncated = len(sample) > _MAX_ROWS
        sample = sample[:_MAX_ROWS]
        if not sample:
            return {"result_type": "empty"}
        flat      = not isinstance(sample[0], (list, tuple))
        qs_fields = list(qs._fields) if qs._fields else None
        if flat:
            raw_names = qs_fields or ["value"]
            labels    = [_field_label(qs.model, qs_fields[0])] if qs_fields else ["value"]
            rows      = [[_fmt(v)] for v in sample]
        else:
            raw_names = qs_fields or [f"col_{i}" for i in range(len(sample[0]))]
            labels    = [_field_label(qs.model, fn) for fn in qs_fields] if qs_fields else list(raw_names)
            rows      = [[_fmt(v) for v in row] for row in sample]

    else:
        # ModelIterable (default queryset)
        sample = list(qs[: _MAX_ROWS + 1])
        truncated = len(sample) > _MAX_ROWS
        sample = sample[:_MAX_ROWS]
        if not sample:
            return {"result_type": "empty"}
        labels, raw_names = _meta_columns(qs.model._meta.concrete_fields)
        rows = [[_fmt(getattr(row, fn)) for fn in raw_names] for row in sample]

    return {
        "result_type": "table",
        "model_name": qs.model.__name__.lower(),
        "columns_meta": list(zip(labels, raw_names)),
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
