# Demo-only settings: isolated DB + storage next to this file, never touches sandbox data.
from pathlib import Path

from sandbox.settings import *  # noqa

HERE = Path(__file__).resolve().parent
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": HERE / "demo.sqlite3"}}
DORM_STORAGE = {"BACKEND": "json", "OPTIONS": {"path": HERE / "demo_dorm.json"}}
