"""
Server-side export of a full (untruncated) tabular result.

Formats match the client-side export in dorm.js:
  - CSV : ';' separator, every cell quoted, semicolons stripped from values
  - JSON: array of objects keyed by header text, 2-space indent

Up to ROWS_PER_FILE rows → a single file. More → a .zip of numbered parts.
"""
import csv
import io
import json
import tempfile
import zipfile
from itertools import islice

ROWS_PER_FILE = 1500

_CONTENT_TYPES = {
    "csv":  "text/csv; charset=utf-8",
    "json": "application/json",
    "zip":  "application/zip",
}


def _render(fmt: str, headers: list, rows: list) -> bytes:
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow([h.replace(";", "") for h in headers])
        writer.writerows([[v.replace(";", "") for v in row] for row in rows])
        return buf.getvalue().encode("utf-8")
    data = [dict(zip(headers, row)) for row in rows]
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def build_export(fmt: str, headers: list, rows, basename: str):
    """
    Return (file_obj, filename, content_type). `rows` is any iterable of
    string lists; it is consumed ROWS_PER_FILE at a time.
    """
    rows  = iter(rows)
    first = list(islice(rows, ROWS_PER_FILE))
    rest  = list(islice(rows, ROWS_PER_FILE))

    if not rest:
        return io.BytesIO(_render(fmt, headers, first)), f"{basename}.{fmt}", _CONTENT_TYPES[fmt]

    # Spill to disk past 20 MB so huge exports don't sit in memory.
    archive = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        part, chunk = 1, first
        while chunk:
            zf.writestr(f"{basename}_part{part:03d}.{fmt}", _render(fmt, headers, chunk))
            part, chunk = part + 1, rest
            rest = list(islice(rows, ROWS_PER_FILE))
    archive.seek(0)
    return archive, f"{basename}.zip", _CONTENT_TYPES["zip"]
