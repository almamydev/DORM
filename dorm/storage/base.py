from abc import ABC, abstractmethod

from django.utils import timezone

HISTORY  = "history"
COMMANDS = "commands"
SETTINGS = "settings"


class BaseStorage(ABC):
    """
    Base class for DORM storage backends.

    A backend implements seven primitives over two structures, both scoped
    by namespace. Values must be JSON-serialisable.

      - key/value : get, set, delete, all
      - list      : push, range, clear   (newest first)

    The high-level API (history, saved commands, settings) is built on top
    of these primitives, so every backend gets it for free.
    """

    history_limit = 100

    # --- key/value primitives ---

    @abstractmethod
    def get(self, ns: str, key: str, default=None):
        ...

    @abstractmethod
    def set(self, ns: str, key: str, value) -> None:
        ...

    @abstractmethod
    def delete(self, ns: str, key: str) -> None:
        ...

    @abstractmethod
    def all(self, ns: str) -> dict:
        ...

    # --- list primitives ---

    @abstractmethod
    def push(self, ns: str, value, max_len: int | None = None) -> None:
        """Prepend value; keep only the newest max_len items when given."""

    @abstractmethod
    def range(self, ns: str, limit: int | None = None) -> list:
        """Return items newest first, at most limit when given."""

    @abstractmethod
    def clear(self, ns: str) -> None:
        ...

    # --- command history ---

    def add_history(self, code: str) -> None:
        last = self.range(HISTORY, 1)
        if last and last[0].get("code") == code:
            return
        entry = {"code": code, "ts": timezone.now().isoformat()}
        self.push(HISTORY, entry, self.history_limit)

    def get_history(self, limit: int | None = None) -> list:
        return self.range(HISTORY, limit)

    def clear_history(self) -> None:
        self.clear(HISTORY)

    # --- saved commands ---

    def save_command(self, name: str, code: str) -> None:
        self.set(COMMANDS, name, code)

    def get_saved_commands(self) -> dict:
        return self.all(COMMANDS)

    def delete_saved_command(self, name: str) -> None:
        self.delete(COMMANDS, name)

    # --- settings ---

    def get_setting(self, key: str, default=None):
        return self.get(SETTINGS, key, default)

    def set_setting(self, key: str, value) -> None:
        self.set(SETTINGS, key, value)

    def get_settings(self) -> dict:
        return self.all(SETTINGS)
