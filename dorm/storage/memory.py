import copy
import threading

from .base import BaseStorage


class MemoryStorage(BaseStorage):
    """Per-process storage. Everything is lost on restart."""

    def __init__(self):
        self._kv    = {}
        self._lists = {}
        self._lock  = threading.Lock()

    def get(self, ns, key, default=None):
        with self._lock:
            return copy.deepcopy(self._kv.get(ns, {}).get(key, default))

    def set(self, ns, key, value):
        with self._lock:
            self._kv.setdefault(ns, {})[key] = copy.deepcopy(value)

    def delete(self, ns, key):
        with self._lock:
            self._kv.get(ns, {}).pop(key, None)

    def all(self, ns):
        with self._lock:
            return copy.deepcopy(self._kv.get(ns, {}))

    def push(self, ns, value, max_len=None):
        with self._lock:
            items = self._lists.setdefault(ns, [])
            items.insert(0, copy.deepcopy(value))
            if max_len is not None:
                del items[max_len:]

    def range(self, ns, limit=None):
        with self._lock:
            items = self._lists.get(ns, [])
            return copy.deepcopy(items if limit is None else items[:limit])

    def clear(self, ns):
        with self._lock:
            self._lists.pop(ns, None)
