# DORM — Project Reference

## What it is
`dorm` is a pip-installable Django package that provides a browser-based ORM playground for Django developers. It lets devs run multi-line Python/ORM queries against their connected database with results rendered as a styled HTML table. Open in `DEBUG=True`; with `DEBUG=False` it needs a custom URL, login and a permission (see Access rules).

## Stack
- Python 3.10+ (dev: 3.12 via uv), Django ≥ 4.2, django-htmx, plain CSS (no Tailwind/npm)
- Virtual environment: `.venv/` managed by uv
- Tests: pytest + pytest-django

---

## Repository layout

```
dorm/               ← installable pip package
  __init__.py       ← __version__, get_url_prefix()
  apps.py           ← DormConfig; ready() registers checks + storage signal
  access.py         ← DEBUG / auth / permission access rules
  checks.py         ← dorm.W001: DEBUG=False without the required settings
  urls.py           ← "" (playground), "run/" (POST cells flow), "save/" (POST saved command), "export/" (POST full export), "history/" (GET modal body)
  views.py          ← _is_accessible(), playground(), run_query(), save_command(), export(), history(), _tabulate() serialisation
  exports.py        ← build_export(): CSV/JSON file, or .zip of ROWS_PER_FILE (1500) parts
  executor.py       ← AST-based execute() / execute_flow(cells); last expression auto-captured
  exceptions.py     ← DormNotDebugError, DormExecutionError (reserved), DormStorageError
  storage/          ← pluggable persistence (history, saved commands, settings)
    __init__.py     ← BACKENDS, get_storage() singleton, reset_storage() (on setting_changed)
    base.py         ← BaseStorage ABC: 7 primitives + high-level API
    memory.py / json_file.py / redis.py / sql.py
  templates/dorm/
    base.html       ← htmx + CodeMirror 5.65.16 (cdnjs) + static CSS/JS
    playground.html ← two-pane split layout, notebook cells container + <template id="dorm-cell-tpl">
    partials/
      result.html   ← table / empty / value output; export buttons
      error.html    ← traceback display
      history.html  ← history modal body: recents + saved tab panels
      history_actions.html ← copy / insert icon buttons
  static/dorm/
    css/dorm.css    ← black/white/gray theme; split-pane + resize CSS
    js/dorm.js      ← resize drag, layout toggle, verbose toggle, export, notebook cells

sandbox/            ← local dev Django project (NOT shipped in the package)
  manage.py
  sandbox/settings.py   ← DEBUG=True, includes dorm + django_htmx + library
  sandbox/urls.py       ← mounts dorm at get_url_prefix()
  library/              ← demo app: Author + Book models with verbose_name (French)
    models.py
    migrations/

tests/
  conftest.py
  test_views.py     ← basic DEBUG access tests
  test_access.py    ← full access matrix, permission, system check, no-models guard
  test_executor.py  ← AST exec + flow unit tests
  test_notebook.py  ← run (cells flow) / save / history endpoints
  test_export.py    ← truncation info, full export, zip splitting
  test_storage.py   ← backend contract tests (memory/json/sql/fakeredis) + factory
```

---

## Settings reference

| Setting | Type | Default | Effect |
|---|---|---|---|
| `DORM_AUTH_ACCESS` | `bool` | `False` | Require a logged-in user. Mandatory with `DEBUG=False` |
| `DORM_PERMISSION_ACCESS` | `bool` | `False` | Require the `DORM_PERMISSION_NAME` permission (superusers always pass). Mandatory with `DEBUG=False` |
| `DORM_PERMISSION_NAME` | `str` | `"can_access_dorm_plg"` | Permission checked, created by your project on one of its models. Bare codename = any app; `"app_label.codename"` = exact |
| `DORM_URL_NAME` | `str` | `"__dorm__"` | URL prefix used by `get_url_prefix()`. Must be a custom value with `DEBUG=False` |
| `DORM_STORAGE` | `dict` | memory backend | `{"BACKEND", "OPTIONS", "HISTORY_LIMIT"}` — see Storage below |

### Access rules

**`DEBUG=True`** (development)

| `DORM_AUTH_ACCESS` | `DORM_PERMISSION_ACCESS` | Who gets in |
|---|---|---|
| `False` / unset | `False` / unset | everyone |
| `True` | `False` / unset | logged-in users |
| any | `True` | users with the permission, and superusers |

**`DEBUG=False`** (production): every condition is required, otherwise 404.

- `DORM_URL_NAME` set to a custom value (not `"__dorm__"`)
- `DORM_AUTH_ACCESS = True`
- `DORM_PERMISSION_ACCESS = True`
- the user is logged in and has the permission (superusers always pass)

When DEBUG is off and a setting is missing, `manage.py check` reports `dorm.W001` with what's missing.
DORM ships no models: the project creates the permission on its own model (usually the user model). A bare codename matches any app; `"app_label.codename"` is exact. README has the snippets.

Logic lives in `dorm/access.py` (`is_accessible`, `production_issues`, `permission_name`); every view calls it first, before the method check.

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

Managed with uv (Python 3.12, pinned in `.python-version`):

```bash
uv sync --extra dev

cd sandbox
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000   # → http://127.0.0.1:8000/__dorm__/
```

Sandbox data lives in `sandbox/db.sqlite3` and `sandbox/dorm_db.json` (both gitignored, user's live data — never delete).

## Tests

```bash
uv run pytest tests/      # from repo root
uv run pytest tests/ -v   # verbose
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

### Truncated results & full export
- `_tabulate(result, limit)` is the single table builder: preview uses `limit=MAX_ROWS+1`; export uses no limit and streams querysets with `.iterator(chunk_size=2000)`
- Truncated preview adds `total` (`qs.count()` / `len`) → `<table data-truncated data-total>`
- Export button on a truncated table opens a choice modal: loaded rows (client-side, as before) or full result → POST `export/` with the cells of the shown result (`lastFlow`), `format`, `verbose`; the flow is re-executed server-side
- ≤1500 rows → single file; more → `<model>_records.zip` with `<model>_records_partNNN.<ext>`; `ROWS_PER_FILE` duplicated in dorm.js for the modal text
- Server formats mirror the client ones below

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

### Notebook cells (input pane)
- Each cell = CodeMirror editor (python mode, closebrackets, matchbrackets, comment, placeholder); cells separated by a dashed top border, no boxes
- Running cell N POSTs `cells` (repeated) = cells 1..N; `execute_flow` runs them in order in one namespace, captures only cell N's last expression. Stateless: upstream cells re-execute on every run
- Response headers: `X-Dorm-Status: ok|error`, `X-Dorm-Cell: <0-based failing index>`
- Trailing cell is always an empty draft; running it commits it and appends a new draft. Remove on the draft only clears it
- Hover actions: run / save (prompt → `save/` → storage) / remove from flow
- Keys: Ctrl/Cmd/Shift+Enter run, Tab indents 4 spaces, Ctrl/Cmd+/ toggles comment
- Alt/Option+Up/Down: shell-style recents in the focused cell (Up = older). Recents from `history/?format=json`, cached until the next run; stepping back past the newest restores the typed text; any manual edit ends navigation
- `run_query` records the target cell in storage history (storage errors only logged)

### History modal
- Header "History" button → `dormOpenHistory()` fetches `history/` into a centered modal (semi-transparent backdrop; Esc / backdrop / × close)
- Tabs: Recents, Saved; selected tab kept in `sessionStorage["dorm.historyTab"]`
- Item actions (hover): copy (clipboard API, execCommand fallback on non-secure origins) and insert (replaces the last focused cell's content)
- Timestamps: server emits `<time datetime>`, JS re-formats in the viewer's local time

### Storage (`dorm/storage/`)
- Backends implement 7 primitives (`get/set/delete/all` per-namespace KV, `push/range/clear` newest-first lists); `BaseStorage` builds history / saved commands / settings on them
- Namespaces: `history`, `commands`, `settings`
- `BACKEND` short names map via `BACKENDS`; anything else is a dotted path (must subclass `BaseStorage`); `OPTIONS` → constructor kwargs
- Config errors → `ImproperlyConfigured`; runtime I/O → `DormStorageError`
- DORM has no models/migrations (enforced by tests). The `sql` backend's `Entry` model lives in a private `Apps()` registry in `sql.py`, invisible to makemigrations/contenttypes
- `sql` builds DDL via `SchemaEditorClass(conn).table_sql()` without entering the editor context, so it works inside atomic blocks on SQLite
- Used by `run_query` (history), `save_command` and `history` (modal)
- Sandbox uses the json backend → `sandbox/dorm_db.json` (gitignored)
