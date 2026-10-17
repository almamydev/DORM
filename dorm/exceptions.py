class DormNotDebugError(Exception):
    pass


class DormExecutionError(Exception):
    pass


class DormStorageError(Exception):
    """Raised when a storage backend fails at runtime (I/O, connection…)."""
