"""Session-only skip selections shared by every chooser interface.

A skip is a temporary deferral of one remaining entry. It is not a history
entry, not a filter, and never persisted: each interface holds its own skip
records and passes the active names to the shared core as an explicit input.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from choosier.filters import FilterValidationError, validate_entry_name

SKIP_COOLDOWN_SECONDS = 600
MAX_SKIPPED_ENTRIES = 20000


class SkipValidationError(FilterValidationError):
    """A malformed skipped-entry value, tagged as a request field error."""

    def __init__(self, message: str) -> None:
        super().__init__("skipped_entries", message)


@dataclass(frozen=True)
class SkipSelection:
    """Immutable set of entry names currently deferred for one request."""

    names: frozenset[str] = frozenset()

    @property
    def is_active(self) -> bool:
        """Whether any entry is currently deferred."""
        return bool(self.names)


def normalize_skips(values: Iterable[object]) -> SkipSelection:
    """Validate, canonicalize, and deduplicate request skip values."""
    raw = list(values)
    if len(raw) > MAX_SKIPPED_ENTRIES:
        raise SkipValidationError(
            f"at most {MAX_SKIPPED_ENTRIES} skipped entries are allowed"
        )
    try:
        names = frozenset(
            validate_entry_name(value, "skipped_entries") for value in raw
        )
    except FilterValidationError as exc:
        raise SkipValidationError(str(exc)) from exc
    return SkipSelection(names=names)
