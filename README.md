# DORM

A browser playground for the Django ORM: run Python/ORM code against your database in notebook-style cells and see results as a table.

![DORM demo](https://raw.githubusercontent.com/almamydev/DORM/main/docs/demo.gif)

<sub>[Watch in full quality (MP4)](https://raw.githubusercontent.com/almamydev/DORM/main/docs/demo.mp4)</sub>

> DORM executes arbitrary Python in your Django process. Read [Access](#access) before enabling it anywhere but your laptop.

## Install

```bash
pip install dorm-plg            # add [redis] for the Redis storage backend
```

```python
# settings.py
INSTALLED_APPS = [..., "django_htmx", "dorm"]
MIDDLEWARE     = [..., "django_htmx.middleware.HtmxMiddleware"]

# urls.py
from dorm import get_url_prefix
urlpatterns = [..., path(f"{get_url_prefix()}/", include("dorm.urls", namespace="dorm"))]
```

Open `/__dorm__/`. DORM has no models and needs no migrations.

## Features

- **Cells**: each run commits a cell and opens a new one. Running a cell re-executes every cell above it first, so variables carry over. Hover a cell to run, save or remove it.
- **Editor**: Python highlighting, auto-closed quotes and brackets. `Ctrl/Cmd+Enter` runs, `Alt/Option+↑/↓` steps through recent executions, `Ctrl/Cmd+/` comments.
- **Auto-imports**: all models plus `Q`, `F`, `Count`, `Sum`, `Avg`, `Max`, `Min`, `Value`, `OuterRef` and `Subquery`.
- **History**: a modal with *Recents* and *Saved* tabs; copy an entry, or insert it into the focused cell.
- **Export**: CSV (`;`) or JSON. Previews show 200 rows; when a result is truncated, you choose between the loaded rows and the full result. The full result re-runs the query, and over 1,500 rows it arrives as a `.zip` of 1,500-row files.

## Access

| Setting | Default | |
|---|---|---|
| `DORM_URL_NAME` | `"__dorm__"` | URL prefix |
| `DORM_AUTH_ACCESS` | `False` | Require login |
| `DORM_PERMISSION_ACCESS` | `False` | Require a permission (superusers always pass) |
| `DORM_PERMISSION_NAME` | `"can_access_dorm_plg"` | Codename (any app) or `"app_label.codename"` |

- **`DEBUG=True`**: open to everyone, unless you turn on the auth or permission settings.
- **`DEBUG=False`**: every DORM URL returns 404 unless *all* of these hold:
  - `DORM_URL_NAME` is a custom value
  - `DORM_AUTH_ACCESS = True`
  - `DORM_PERMISSION_ACCESS = True`
  - the user is logged in and has the permission

  `manage.py check` reports `dorm.W001` when a setting is missing.

DORM defines no permission itself. Create it on one of your models, usually the user model:

```python
class User(AbstractUser):
    class Meta:
        permissions = [("can_access_dorm_plg", "Can access DORM")]
```

With the stock `auth.User`, create the same `Permission` in a data migration (`content_type` = User). Then grant it in the admin.

## Storage

History, saved commands and settings are stored in a pluggable backend. The default is in-memory.

```python
DORM_STORAGE = {
    "BACKEND": "json",                                # memory | json | redis | sql | dotted.path
    "OPTIONS": {"path": BASE_DIR / "dorm_db.json"},
    "HISTORY_LIMIT": 100,
}
```

| Backend | OPTIONS |
|---|---|
| `memory` | — |
| `json` | `path` |
| `redis` | `url="redis://localhost:6379/0"`, `prefix="dorm:"` |
| `sql` | `alias="default"`: any Django database (PostgreSQL, MySQL, SQLite). Its table is created on first use. |

To write a custom backend, subclass `dorm.storage.BaseStorage` and implement `get`, `set`, `delete`, `all`, `push`, `range` and `clear`.

## Development

```bash
git clone https://github.com/almamydev/DORM && cd DORM
uv sync --extra dev
uv run pytest
cd sandbox && uv run python manage.py migrate && uv run python manage.py runserver
```
