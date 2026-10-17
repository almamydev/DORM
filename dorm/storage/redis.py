import json

from django.core.exceptions import ImproperlyConfigured

from ..exceptions import DormStorageError
from .base import BaseStorage


class RedisStorage(BaseStorage):
    """
    key/value → one hash per namespace   (<prefix>kv:<ns>)
    list      → one Redis list per ns     (<prefix>list:<ns>)
    """

    def __init__(self, url="redis://localhost:6379/0", prefix="dorm:", client=None):
        try:
            import redis
        except ImportError as exc:
            raise ImproperlyConfigured(
                "DORM_STORAGE: the 'redis' backend requires the redis package — "
                "pip install 'dorm-plg[redis]'."
            ) from exc
        self._errors = redis.exceptions.RedisError
        self.client  = client if client is not None else redis.Redis.from_url(url)
        self.prefix  = prefix

    def _kv_key(self, ns):
        return f"{self.prefix}kv:{ns}"

    def _list_key(self, ns):
        return f"{self.prefix}list:{ns}"

    def _call(self, fn, *args):
        try:
            return fn(*args)
        except self._errors as exc:
            raise DormStorageError(f"Redis storage error: {exc}") from exc

    # --- key/value ---

    def get(self, ns, key, default=None):
        raw = self._call(self.client.hget, self._kv_key(ns), key)
        return default if raw is None else json.loads(raw)

    def set(self, ns, key, value):
        self._call(self.client.hset, self._kv_key(ns), key, json.dumps(value))

    def delete(self, ns, key):
        self._call(self.client.hdel, self._kv_key(ns), key)

    def all(self, ns):
        raw = self._call(self.client.hgetall, self._kv_key(ns))
        return {
            (k.decode() if isinstance(k, bytes) else k): json.loads(v)
            for k, v in raw.items()
        }

    # --- lists ---

    def push(self, ns, value, max_len=None):
        key = self._list_key(ns)
        try:
            pipe = self.client.pipeline()
            pipe.lpush(key, json.dumps(value))
            if max_len is not None:
                pipe.ltrim(key, 0, max_len - 1)
            pipe.execute()
        except self._errors as exc:
            raise DormStorageError(f"Redis storage error: {exc}") from exc

    def range(self, ns, limit=None):
        if limit is not None and limit <= 0:
            return []
        end = -1 if limit is None else limit - 1
        raw = self._call(self.client.lrange, self._list_key(ns), 0, end)
        return [json.loads(v) for v in raw]

    def clear(self, ns):
        self._call(self.client.delete, self._list_key(ns))
