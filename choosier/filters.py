"""Shared type and entry filtering for every chooser interface.

This module is standard-library-only and knows nothing about the CLI, TUI, or
web adapter. It classifies scanned candidate entries, builds the bounded option
lists rendered by the interfaces, and applies a normalized exclusion selection.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

DIR_TYPE_KEY = "dir"
SUFFIXLESS_TYPE_KEY = "file:"

FILTER_ENTRY_LIMIT = 1000
MAX_TYPE_EXCLUSIONS = 2000
MAX_ENTRY_EXCLUSIONS = 20000
MAX_VALUE_LENGTH = 1024


class FilterValidationError(ValueError):
    """A malformed exclusion value, tagged with the request field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class FilterSelection:
    """Immutable type and entry exclusions for one state or pick request."""

    excluded_types: frozenset[str] = frozenset()
    excluded_entries: frozenset[str] = frozenset()

    @property
    def is_active(self) -> bool:
        """Whether any type or entry has been excluded."""
        return bool(self.excluded_types or self.excluded_entries)


@dataclass(frozen=True)
class CandidateEntry:
    """One direct child after the existing hidden and mode options."""

    name: str
    is_dir: bool
    type_key: str


@dataclass(frozen=True)
class FilterTypeOption:
    """One selectable file type with its base-candidate count."""

    key: str
    label: str
    count: int


@dataclass(frozen=True)
class FilterEntryOption:
    """One selectable visible entry and its type key."""

    name: str
    type_key: str


@dataclass(frozen=True)
class FilterOptions:
    """The complete type list and bounded entry list for one folder."""

    types: tuple[FilterTypeOption, ...] = ()
    entries: tuple[FilterEntryOption, ...] = ()
    entries_total: int = 0
    entries_truncated: bool = False


def type_key_for(name: str, *, is_dir: bool) -> str:
    """Return the canonical type key for one direct child name."""
    if is_dir:
        return DIR_TYPE_KEY
    suffix = Path(name).suffix.lower()
    if suffix:
        return f"file:{suffix}"
    return SUFFIXLESS_TYPE_KEY


def type_label(key: str) -> str:
    """Return the stable human label for one canonical type key."""
    if key == DIR_TYPE_KEY:
        return "Folders"
    if key == SUFFIXLESS_TYPE_KEY:
        return "Files without an extension"
    return f"{key.removeprefix('file:')} files"


def _type_sort_key(key: str) -> tuple[int, str]:
    if key == DIR_TYPE_KEY:
        return (0, "")
    if key == SUFFIXLESS_TYPE_KEY:
        return (2, "")
    return (1, key.removeprefix("file:"))


def build_filter_options(entries: Iterable[CandidateEntry]) -> FilterOptions:
    """Build complete type counts and the bounded, name-sorted entry list."""
    base = list(entries)
    counts: dict[str, int] = {}
    for entry in base:
        counts[entry.type_key] = counts.get(entry.type_key, 0) + 1
    types = tuple(
        FilterTypeOption(key=key, label=type_label(key), count=counts[key])
        for key in sorted(counts, key=_type_sort_key)
    )
    ordered_entries = sorted(base, key=lambda entry: entry.name)
    visible = tuple(
        FilterEntryOption(name=entry.name, type_key=entry.type_key)
        for entry in ordered_entries[:FILTER_ENTRY_LIMIT]
    )
    total = len(ordered_entries)
    return FilterOptions(
        types=types,
        entries=visible,
        entries_total=total,
        entries_truncated=total > len(visible),
    )


def filter_candidates(
    entries: Iterable[CandidateEntry],
    selection: FilterSelection,
) -> list[CandidateEntry]:
    """Return the name-sorted candidates allowed by a filter selection."""
    return sorted(
        (
            entry
            for entry in entries
            if entry.type_key not in selection.excluded_types
            and entry.name not in selection.excluded_entries
        ),
        key=lambda entry: entry.name,
    )


def _validate_type_key(value: object) -> str:
    if not isinstance(value, str):
        raise FilterValidationError(
            "excluded_types", "excluded_types must contain strings"
        )
    if len(value) > MAX_VALUE_LENGTH:
        raise FilterValidationError(
            "excluded_types",
            f"type keys must be at most {MAX_VALUE_LENGTH} characters",
        )
    if "/" in value or "\x00" in value:
        raise FilterValidationError(
            "excluded_types", "type keys must not contain '/' or NUL"
        )
    if value == DIR_TYPE_KEY or value == SUFFIXLESS_TYPE_KEY:
        return value
    if value.startswith("file:") and len(value) > len("file:."):
        suffix = value[len("file:") :]
        if suffix.startswith(".") and len(suffix) > 1:
            return f"file:{suffix.lower()}"
    raise FilterValidationError(
        "excluded_types",
        "type keys must be 'dir', 'file:', or 'file:' plus a dot-prefixed suffix",
    )


def _validate_entry_name(value: object) -> str:
    if not isinstance(value, str):
        raise FilterValidationError(
            "excluded_entries", "excluded_entries must contain strings"
        )
    if len(value) > MAX_VALUE_LENGTH:
        raise FilterValidationError(
            "excluded_entries",
            f"entry names must be at most {MAX_VALUE_LENGTH} characters",
        )
    if value in ("", ".", ".."):
        raise FilterValidationError(
            "excluded_entries", "entry names must not be empty, '.' or '..'"
        )
    if "/" in value or "\x00" in value:
        raise FilterValidationError(
            "excluded_entries", "entry names must not contain '/' or NUL"
        )
    return value


def normalize_exclusions(
    excluded_types: Iterable[object],
    excluded_entries: Iterable[object],
) -> FilterSelection:
    """Validate, canonicalize, and deduplicate request exclusion values."""
    raw_types = list(excluded_types)
    raw_entries = list(excluded_entries)
    if len(raw_types) > MAX_TYPE_EXCLUSIONS:
        raise FilterValidationError(
            "excluded_types",
            f"at most {MAX_TYPE_EXCLUSIONS} type exclusions are allowed",
        )
    if len(raw_entries) > MAX_ENTRY_EXCLUSIONS:
        raise FilterValidationError(
            "excluded_entries",
            f"at most {MAX_ENTRY_EXCLUSIONS} entry exclusions are allowed",
        )
    types = frozenset(_validate_type_key(value) for value in raw_types)
    entries = frozenset(_validate_entry_name(value) for value in raw_entries)
    return FilterSelection(excluded_types=types, excluded_entries=entries)
