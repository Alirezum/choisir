"""Immutable result objects shared by every interface."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from choosier.preview import Preview
from choosier.storage import LogEntry


@dataclass(frozen=True)
class BrowseEntry:
    """One child entry in a directory listing."""

    name: str
    is_dir: bool


@dataclass(frozen=True)
class BrowseListing:
    """An ordered directory listing and its parent."""

    path: Path
    parent: Path | None
    entries: tuple[BrowseEntry, ...]


@dataclass(frozen=True)
class HistorySnapshot:
    """One structured history read with derived views."""

    entries: tuple[LogEntry, ...]
    logged: frozenset[str]
    display: tuple[str, ...]


@dataclass(frozen=True)
class StateSnapshot:
    """Remaining candidates and recent history for one target."""

    valid_path: bool
    path: Path
    log_file: Path
    remaining: tuple[str, ...]
    remaining_total: int
    history: tuple[LogEntry, ...]
    history_total: int


PickStatus = Literal["picked", "empty", "exhausted", "invalid_path"]


@dataclass(frozen=True)
class PickOutcome:
    """The result of one pick attempt."""

    status: PickStatus
    log_file: Path
    item: str | None = None
    logged: bool = False
    preview: Preview | None = None


@dataclass(frozen=True)
class OpenOutcome:
    """The result of opening one entry."""

    name: str
