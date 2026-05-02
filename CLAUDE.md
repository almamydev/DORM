# DORM — Project Reference

## What it is
`dorm` is a pip-installable Django package that provides a browser-based ORM playground for Django developers. It lets devs run multi-line Python/ORM queries against their connected database with results rendered as a styled HTML table. Dev-only tool — gated behind `DEBUG=True`.

## Stack
- Python 3.10+, Django ≥ 4.2, django-htmx, plain CSS (no Tailwind/npm)
- Virtual environment: `.venv/` (Python 3.10)
- Tests: pytest + pytest-django

---

## Repository layout

```
dorm/               ← installable pip package
  __init__.py       ← __version__, get_url_prefix()
  apps.py           ← DormConfig; logs warning if DEBUG=False (no crash)
  urls.py           ← 2 routes: "" (playground) + "run/" (htmx POST)
  views.py          ← _is_accessible(), playground(), run_query(), serialisation
  executor.py       ← AST-based exec(); last expression auto-captured as result
  exceptions.py     ← DormNotDebugError, DormExecutionError (reserved)
  templates/dorm/
    base.html       ← htmx CDN + static CSS/JS
    playground.html ← two-pane split layout + verbose-names checkbox
    partials/
      result.html   ← table / empty / value output; export buttons
      error.html    ← traceback display
  static/dorm/
    css/dorm.css    ← black/white/gray theme; split-pane + resize CSS
    js/dorm.js      ← resize drag, layout toggle, verbose toggle, export, Ctrl+Enter

sandbox/            ← local dev Django project (NOT shipped in the package)
  manage.py
  sandbox/settings.py   ← DEBUG=True, includes dorm + django_htmx + library
  sandbox/urls.py       ← mounts dorm at get_url_prefix()
  library/              ← demo app: Author + Book models with verbose_name (French)
    models.py
    migrations/

tests/
  conftest.py
  test_views.py     ← access control tests (DEBUG, DORM_AUTH_ACCESS, auth)
  test_executor.py  ← AST exec unit tests
```

---

## Settings reference

| Setting | Type | Default | Effect |
|---|---|---|---|
| `DORM_AUTH_ACCESS` | `bool` | `False` | When `True`, requires `request.user.is_authenticated` even in DEBUG |
| `DORM_URL_NAME` | `str` | `"__dorm__"` | URL prefix used by `get_url_prefix()` |

### Access rules

| `DEBUG` | `DORM_AUTH_ACCESS` | Authenticated | Result |
|---|---|---|---|
| `False` | any | any | 404 |
| `True` | `False` / unset | any | 200 |
| `True` | `True` | yes | 200 |
| `True` | `True` | no | 404 |

---

## Consumer setup (end-user project)

```python
# settings.py
INSTALLED_APPS = [..., "django_htmx", "dorm"]
MIDDLEWARE    = [..., "django_htmx.middleware.HtmxMiddleware"]

# Optional:
DORM_AUTH_ACCESS = True      # require login
DORM_URL_NAME    = "dorm"    # mount at /dorm/
```

```python
# urls.py
from dorm import get_url_prefix
urlpatterns = [
    path(f"{get_url_prefix()}/", include("dorm.urls", namespace="dorm")),
]
```

---

## Dev setup

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cd sandbox
python manage.py migrate
python manage.py runserver   # → http://127.0.0.1:8000/__dorm__/
```

Seed demo data (run once):
```bash
cd sandbox
python manage.py shell -c "
from library.models import Author, Book
# see sandbox/library/models.py for fields
"
```
Sandbox has 5 Authors + 14 Books already seeded in `sandbox/db.sqlite3` (gitignored).

## Tests

```bash
pytest tests/          # from repo root, venv active
pytest tests/ -v       # verbose
```

---

## Key implementation details

### Executor (`dorm/executor.py`)
- Uses Python `ast` module: parses code, splits at last `ast.Expr` node
- All preceding statements → `exec()`, last expression → `eval()` (captures the result)
- Namespace auto-populated with all installed models + common ORM helpers (Q, F, Count…)
- Returns `{"success": True, "result": ...}` or `{"success": False, "error_type": ..., "traceback": ...}`

### Result serialisation (`dorm/views.py`)
- `_serialize_queryset` detects queryset type via `qs._iterable_class.__name__`:
  - `ModelIterable` → model concrete fields
  - `ValuesIterable` → dict keys from first row
  - `ValuesListIterable` / `FlatValuesListIterable` → `qs._fields`
- Returns `columns_meta`: list of `(verbose_label, field_name)` tuples
- Template stores both on `<th data-verbose="..." data-field="...">` — JS toggles
- MAX_ROWS = 200 (constant in `views.py`)

### Verbose names toggle
- Server always sends both labels; checkbox in Result pane bar switches client-side
- `htmx:afterSwap` re-applies current checkbox state after each new query

### CSV export
- Separator: `;`
- Semicolons stripped from cell values before writing
- Filename: `<model_name>_records.csv`

### JSON export
- Array of objects, keys = current header text (respects verbose toggle)
- Filename: `<model_name>_records.json`

### Split-pane layout
- `#dorm-layout[data-dir="row|col"]` drives `flex-direction` via CSS attribute selector
- Drag resize: `mousedown` on `.dorm-divider` → track delta → update `paneA.style.flex`
- Toggle button resets to 50/50 on direction switch
