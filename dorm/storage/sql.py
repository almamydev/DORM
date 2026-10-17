import json

from django.apps.registry import Apps
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, models

from ..exceptions import DormStorageError
from .base import BaseStorage

# DORM ships no models. The storage table is described by a model living in a
# private registry, so it never shows up in the project's apps, migrations,
# content types or permissions.
_registry = Apps()


class Entry(models.Model):
    KV   = "kv"
    LIST = "list"

    kind       = models.CharField(max_length=8)
    namespace  = models.CharField(max_length=64)
    key        = models.CharField(max_length=255, blank=True, default="")
    value      = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        apps      = _registry
        app_label = "dorm_storage"
        db_table  = "dorm_storage"


class SQLStorage(BaseStorage):
    """
    Stores entries in the `dorm_storage` table of any Django database alias
    (PostgreSQL, MySQL, SQLite…). The table is created on first use.
    """

    def __init__(self, alias="default"):
        if alias not in connections.databases:
            raise ImproperlyConfigured(
                f"DORM_STORAGE: database alias {alias!r} is not defined in DATABASES."
            )
        self.alias  = alias
        self._ready = False

    def _ensure_table(self) -> None:
        if self._ready:
            return
        conn = connections[self.alias]
        try:
            if Entry._meta.db_table not in conn.introspection.table_names():
                # Build the DDL without entering the schema editor context, so this
                # also works inside an atomic block (SQLite refuses that otherwise).
                editor = conn.SchemaEditorClass(conn)
                editor.deferred_sql = []
                sql, params = editor.table_sql(Entry)
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or None)
                    for stmt in editor.deferred_sql:
                        cursor.execute(str(stmt))
        except DatabaseError as exc:
            raise DormStorageError(f"Cannot create DORM storage table: {exc}") from exc
        self._ready = True

    def _qs(self, kind, ns):
        self._ensure_table()
        return Entry.objects.using(self.alias).filter(kind=kind, namespace=ns)

    def _run(self, fn):
        try:
            return fn()
        except DatabaseError as exc:
            raise DormStorageError(f"SQL storage error: {exc}") from exc

    # --- key/value ---

    def get(self, ns, key, default=None):
        def op():
            row = self._qs(Entry.KV, ns).filter(key=key).values_list("value", flat=True).first()
            return default if row is None else json.loads(row)
        return self._run(op)

    def set(self, ns, key, value):
        def op():
            self._qs(Entry.KV, ns).update_or_create(
                kind=Entry.KV, namespace=ns, key=key,
                defaults={"value": json.dumps(value)},
            )
        self._run(op)

    def delete(self, ns, key):
        self._run(lambda: self._qs(Entry.KV, ns).filter(key=key).delete())

    def all(self, ns):
        def op():
            rows = self._qs(Entry.KV, ns).order_by("id").values_list("key", "value")
            return {k: json.loads(v) for k, v in rows}
        return self._run(op)

    # --- lists ---

    def push(self, ns, value, max_len=None):
        def op():
            qs = self._qs(Entry.LIST, ns)
            qs.create(kind=Entry.LIST, namespace=ns, value=json.dumps(value))
            if max_len is not None:
                stale = list(qs.order_by("-id").values_list("id", flat=True)[max_len:])
                if stale:
                    qs.filter(id__in=stale).delete()
        self._run(op)

    def range(self, ns, limit=None):
        def op():
            qs = self._qs(Entry.LIST, ns).order_by("-id").values_list("value", flat=True)
            if limit is not None:
                qs = qs[:max(limit, 0)]
            return [json.loads(v) for v in qs]
        return self._run(op)

    def clear(self, ns):
        self._run(lambda: self._qs(Entry.LIST, ns).delete())
