import json
import os
import tempfile
import threading
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from ..exceptions import DormStorageError
from .base import BaseStorage


class JSONFileStorage(BaseStorage):
    """
    Stores everything in a single JSON file:
        {"kv": {ns: {key: value}}, "lists": {ns: [newest, ...]}}

    The file is re-read on every operation so several processes stay in
    sync, and written atomically (temp file + os.replace).
    """

    def __init__(self, path=None):
        if not path:
            raise ImproperlyConfigured(
                "DORM_STORAGE: the 'json' backend requires OPTIONS['path']."
            )
        self.path  = Path(path)
        self._lock = threading.Lock()

    # --- file I/O ---

    def _load(self) -> dict:
        try:
            with self.path.open(encoding="utf-8") as fh:
                doc = json.load(fh)
        except FileNotFoundError:
            return {"kv": {}, "lists": {}}
        except (OSError, ValueError) as exc:
            raise DormStorageError(f"Cannot read DORM storage file {self.path}: {exc}") from exc
        doc.setdefault("kv", {})
        doc.setdefault("lists", {})
        return doc

    def _save(self, doc: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".dorm-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        except (OSError, TypeError, ValueError) as exc:
            raise DormStorageError(f"Cannot write DORM storage file {self.path}: {exc}") from exc

    # --- key/value ---

    def get(self, ns, key, default=None):
        with self._lock:
            return self._load()["kv"].get(ns, {}).get(key, default)

    def set(self, ns, key, value):
        with self._lock:
            doc = self._load()
            doc["kv"].setdefault(ns, {})[key] = value
            self._save(doc)

    def delete(self, ns, key):
        with self._lock:
            doc    = self._load()
            bucket = doc["kv"].get(ns, {})
            if key in bucket:
                del bucket[key]
                self._save(doc)

    def all(self, ns):
        with self._lock:
            return self._load()["kv"].get(ns, {})

    # --- lists ---

    def push(self, ns, value, max_len=None):
        with self._lock:
            doc   = self._load()
            items = doc["lists"].setdefault(ns, [])
            items.insert(0, value)
            if max_len is not None:
                del items[max_len:]
            self._save(doc)

    def range(self, ns, limit=None):
        with self._lock:
            items = self._load()["lists"].get(ns, [])
            return items if limit is None else items[:limit]

    def clear(self, ns):
        with self._lock:
            doc = self._load()
            if doc["lists"].pop(ns, None) is not None:
                self._save(doc)
