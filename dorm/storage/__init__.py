"""
Pluggable storage for DORM state (command history, saved commands, settings).

Configure with:

    DORM_STORAGE = {
        "BACKEND": "json",                 # memory | json | redis | sql | dotted.path.Class
        "OPTIONS": {"path": "dorm.json"},  # passed to the backend constructor
        "HISTORY_LIMIT": 100,
    }
"""
import threading

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.signals import setting_changed
from django.utils.module_loading import import_string

from .base import COMMANDS, HISTORY, SETTINGS, BaseStorage

__all__ = ["BACKENDS", "BaseStorage", "get_storage", "reset_storage",
           "HISTORY", "COMMANDS", "SETTINGS"]

BACKENDS = {
    "memory": "dorm.storage.memory.MemoryStorage",
    "json":   "dorm.storage.json_file.JSONFileStorage",
    "redis":  "dorm.storage.redis.RedisStorage",
    "sql":    "dorm.storage.sql.SQLStorage",
}

_storage = None
_lock    = threading.Lock()


def _build() -> BaseStorage:
    config  = getattr(settings, "DORM_STORAGE", None) or {}
    backend = config.get("BACKEND", "memory")
    options = config.get("OPTIONS", {}) or {}
    path    = BACKENDS.get(backend, backend)

    if "." not in path:
        raise ImproperlyConfigured(
            f"DORM_STORAGE: unknown backend {backend!r}. "
            f"Use one of {sorted(BACKENDS)} or a dotted path to a BaseStorage subclass."
        )
    try:
        cls = import_string(path)
    except ImportError as exc:
        raise ImproperlyConfigured(f"DORM_STORAGE: cannot import backend {path!r}: {exc}") from exc
    if not (isinstance(cls, type) and issubclass(cls, BaseStorage)):
        raise ImproperlyConfigured(f"DORM_STORAGE: {path!r} is not a BaseStorage subclass.")

    try:
        storage = cls(**options)
    except TypeError as exc:
        raise ImproperlyConfigured(f"DORM_STORAGE: invalid OPTIONS for {path!r}: {exc}") from exc

    if "HISTORY_LIMIT" in config:
        storage.history_limit = config["HISTORY_LIMIT"]
    return storage


def get_storage() -> BaseStorage:
    """Return the configured storage backend (built once, then cached)."""
    global _storage
    if _storage is None:
        with _lock:
            if _storage is None:
                _storage = _build()
    return _storage


def reset_storage() -> None:
    """Drop the cached backend; the next get_storage() rebuilds it from settings."""
    global _storage
    with _lock:
        _storage = None


def _on_setting_changed(setting, **kwargs):
    if setting == "DORM_STORAGE":
        reset_storage()


setting_changed.connect(_on_setting_changed)
