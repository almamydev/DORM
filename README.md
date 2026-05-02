# DORM

A Django ORM playground — a dev-only web UI to run ORM queries against your connected database.

## Install

```bash
pip install dorm
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

urlpatterns = [
    ...
    path("__dorm__/", include("dorm.urls", namespace="dorm")),
]
```

Open `/__dorm__/` in your browser and start writing ORM queries.

> **Warning**: DORM executes arbitrary Python code in your Django process. It is gated behind `DEBUG=True` and must never be used in production.

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
git clone https://github.com/yourname/dorm
cd dorm
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd sandbox && python manage.py migrate && python manage.py runserver
# Open: http://127.0.0.1:8000/__dorm__/
```
