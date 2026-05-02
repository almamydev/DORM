# DORM

A Django ORM playground — a dev-only web UI to run ORM queries against your connected database.

## Install

```bash
pip install dorm-plg
```

## Setup

```python
# settings.py
INSTALLED_APPS = [..., "django_htmx", "dorm"]
MIDDLEWARE = [..., "django_htmx.middleware.HtmxMiddleware"]
```

```python
# urls.py
from django.urls import path, include
from dorm import get_url_prefix

urlpatterns = [
    ...
    path(f"{get_url_prefix()}/", include("dorm.urls", namespace="dorm")),
]
```

Open `/__dorm__/` in your browser and start writing ORM queries.

> **Warning**: DORM executes arbitrary Python code in your Django process. It is gated behind `DEBUG=True` and must never be used in production.

## Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `DORM_AUTH_ACCESS` | `bool` | `False` | When `True`, requires the user to be authenticated even in DEBUG mode |
| `DORM_URL_NAME` | `str` | `"__dorm__"` | URL prefix where DORM is mounted (used by `get_url_prefix()`) |

### Access rules

| `DEBUG` | `DORM_AUTH_ACCESS` | Authenticated | Result |
|---|---|---|---|
| `False` | any | any | 404 |
| `True` | `False` / unset | any | 200 |
| `True` | `True` | yes | 200 |
| `True` | `True` | no | 404 |

Example with both settings:

```python
# settings.py
DORM_AUTH_ACCESS = True   # require login
DORM_URL_NAME = "dorm"    # mount at /dorm/
```

## Usage

In the playground editor, write any Django ORM expression. All models from your `INSTALLED_APPS` are available without importing them:

```python
# Get all users
User.objects.all()

# Filter with related fields
Book.objects.filter(author__name="Tolkien").select_related("author")

# Aggregations
from django.db.models import Count
Author.objects.annotate(book_count=Count("books")).order_by("-book_count")
```

Press **Ctrl+Enter** or click **Run** to execute. Results are rendered as a table.

## Development

```bash
git clone https://github.com/almamydev/DORM
cd DORM
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd sandbox && python manage.py migrate && python manage.py runserver
# Open: http://127.0.0.1:8000/__dorm__/
```
