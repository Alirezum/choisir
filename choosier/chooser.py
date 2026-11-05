"""Picking random unselected directory entries."""

import fnmatch
import random
from dataclasses import dataclass
from pathlib import Path

from choosier.filters import (
    CandidateEntry,
    FilterSelection,
    filter_candidates,
    type_key_for,
)
from choosier.storage import DEFAULT_LOG_FILENAME, get_logged_items


def resolve_default_log(directory: str | Path) -> Path:
    """Default history file colocated with the target directory.

    Colocating (instead of CWD-relative) keeps history stable when the
    tool is run from different working directories. The dot-prefix keeps
    it out of default listings.
    """
    return Path(directory).expanduser() / DEFAULT_LOG_FILENAME


def resolve_log_path(target: str | Path, override: str) -> Path:
    """Effective history log: explicit override or colocated default."""
    if override.strip():
        return Path(override).expanduser()
    return resolve_default_log(target)


def parse_seed(text: str) -> int | None:
    """Parse a seed input; blank means random. Raises ValueError if invalid."""
    stripped = text.strip()
    if not stripped:
        return None
    return int(stripped)


def _is_managed_file(name: str, log_path: Path) -> bool:
    if name == log_path.name:
        return True
    return fnmatch.fnmatch(name, f"{log_path.stem}-*{log_path.suffix}.old")


@dataclass(frozen=True)
class CandidateScan:
    """One directory read with its base candidates and child-presence flag."""

    valid_path: bool
    has_children: bool
    entries: tuple[CandidateEntry, ...]


def scan_candidates(
    directory: str | Path,
    log_path: str | Path,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
) -> CandidateScan:
    """Read a directory once and classify its base candidates.

    The base candidates apply the existing hidden, log-managed, files-only, and
    dirs-only rules. Type and entry exclusions and history are applied later so
    one scan can serve options, remaining totals, and picks.
    """
    if files_only and dirs_only:
        raise ValueError("files_only and dirs_only are mutually exclusive")
    dir_path = Path(directory).expanduser()
    if not dir_path.is_dir():
        return CandidateScan(valid_path=False, has_children=False, entries=())
    log_path = Path(log_path).expanduser()
    candidates: list[CandidateEntry] = []
    has_children = False
    try:
        for entry in dir_path.iterdir():
            has_children = True
            name = entry.name
            if not include_hidden and name.startswith("."):
                continue
            if _is_managed_file(name, log_path):
                continue
            is_dir = entry.is_dir()
            if files_only and not entry.is_file():
                continue
            if dirs_only and not is_dir:
                continue
            candidates.append(
                CandidateEntry(
                    name=name,
                    is_dir=is_dir,
                    type_key=type_key_for(name, is_dir=is_dir),
                )
            )
    except FileNotFoundError:
        return CandidateScan(valid_path=True, has_children=False, entries=())
    candidates.sort(key=lambda candidate: candidate.name)
    return CandidateScan(
        valid_path=True,
        has_children=has_children,
        entries=tuple(candidates),
    )


def list_candidates(
    directory: str | Path,
    log_path: str | Path,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
) -> set[str]:
    """Entries eligible for picking, before history filtering."""
    scan = scan_candidates(
        directory,
        log_path,
        include_hidden=include_hidden,
        files_only=files_only,
        dirs_only=dirs_only,
    )
    return {candidate.name for candidate in scan.entries}


def list_available_items(
    directory: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    selection: FilterSelection | None = None,
) -> list[str]:
    """Sorted remaining picks (filtered candidates minus logged history)."""
    dir_path = Path(directory).expanduser()
    log_path = (
        Path(log_file).expanduser()
        if log_file is not None
        else resolve_default_log(dir_path)
    )
    scan = scan_candidates(
        dir_path,
        log_path,
        include_hidden=include_hidden,
        files_only=files_only,
        dirs_only=dirs_only,
    )
    if not scan.valid_path:
        return []
    filtered = filter_candidates(scan.entries, selection or FilterSelection())
    if not filtered:
        return []
    logged = get_logged_items(log_path)
    return [candidate.name for candidate in filtered if candidate.name not in logged]


def get_unselected_item(
    directory: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    selection: FilterSelection | None = None,
    rng: random.Random | None = None,
) -> str | None:
    """Return a random unselected entry name, or None if none remains."""
    available = list_available_items(
        directory,
        log_file,
        include_hidden=include_hidden,
        files_only=files_only,
        dirs_only=dirs_only,
        selection=selection,
    )
    if not available:
        return None
    if rng is None:
        return random.choice(available)
    return rng.choice(available)
