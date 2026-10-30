"""Application-layer history reads and mutations."""

from collections.abc import Collection
from pathlib import Path

from choosier import storage
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.models import HistorySnapshot
from choosier.storage import LogEntry


class HistoryService:
    """The single application-layer owner of history reads and writes."""

    def __init__(self, log_file: str | Path) -> None:
        self._log_file = Path(log_file).expanduser()

    @property
    def log_file(self) -> Path:
        """The resolved history file path."""
        return self._log_file

    def snapshot(self, *, ignore_errors: bool = True) -> HistorySnapshot:
        """Read the history once and derive logged names and display lines."""
        entries = tuple(
            storage.read_log_entries(self._log_file, ignore_errors=ignore_errors)
        )
        return HistorySnapshot(
            entries=entries,
            logged=frozenset(entry.item for entry in entries),
            display=tuple(entry.display for entry in entries),
        )

    def read_entries(self, *, ignore_errors: bool = True) -> tuple[LogEntry, ...]:
        """Structured entries from one history read."""
        return self.snapshot(ignore_errors=ignore_errors).entries

    def logged_items(self, *, ignore_errors: bool = True) -> set[str]:
        """Item names derived from one history read."""
        return set(self.snapshot(ignore_errors=ignore_errors).logged)

    def display_lines(self, *, ignore_errors: bool = True) -> list[str]:
        """Display lines derived from one history read."""
        return list(self.snapshot(ignore_errors=ignore_errors).display)

    def append(self, item: str) -> None:
        """Append one selection using the existing append and rotation rules."""
        try:
            storage.log_selection(item, self._log_file)
        except OSError as e:
            raise ServiceError(
                FailureKind.IO_ERROR, f"Error writing log: {e}"
            ) from e

    def remove(self, item: str) -> int:
        """Remove every entry for one item; return the number removed."""
        try:
            return storage.remove_log_item(item, self._log_file)
        except OSError as e:
            raise ServiceError(
                FailureKind.IO_ERROR, f"Error removing history item: {e}"
            ) from e

    def remove_many(self, items: Collection[str]) -> int:
        """Remove every entry for all items in one atomic rewrite."""
        try:
            return storage.remove_log_items(items, self._log_file)
        except OSError as e:
            raise ServiceError(
                FailureKind.IO_ERROR, f"Error removing history items: {e}"
            ) from e

    def archive(self) -> Path | None:
        """Move the history to a timestamped backup, or return None."""
        try:
            return storage.archive_log(self._log_file)
        except OSError as e:
            raise ServiceError(FailureKind.IO_ERROR, f"Error archiving log: {e}") from e

    def clear(self) -> bool:
        """Delete the history file; return whether it existed."""
        try:
            return storage.reset_log(self._log_file)
        except OSError as e:
            raise ServiceError(
                FailureKind.IO_ERROR, f"Error resetting log: {e}"
            ) from e
