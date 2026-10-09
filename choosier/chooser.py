"""Picking random unselected directory entries."""

import fnmatch
import random
from pathlib import Path

from choosier.storage import DEFAULT_LOG_FILENAME, get_logged_items


def resolve_default_log(directory: str | Path) -> Path:
    """Default history file colocated with the target directory.

    Colocating (instead of CWD-relative) keeps history stable when the
    tool is run from different working directories. The dot-prefix keeps
    it out of default listings.
    """
    return Path(directory).expanduser() / DEFAULT_LOG_FILENAME


def _is_managed_file(name: str, log_path: Path) -> bool:
    if name == log_path.name:
        return True
    return fnmatch.fnmatch(name, f"{log_path.stem}-*{log_path.suffix}.old")


def list_candidates(
    directory: str | Path,
    log_path: str | Path,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
) -> set[str]:
    """Entries eligible for picking, before history filtering."""
    if files_only and dirs_only:
        raise ValueError("files_only and dirs_only are mutually exclusive")
    dir_path = Path(directory).expanduser()
    log_name = Path(log_path).expanduser()
    candidates: set[str] = set()
    for entry in dir_path.iterdir():
        name = entry.name
        if not include_hidden and name.startswith("."):
            continue
        if _is_managed_file(name, log_name):
            continue
        if files_only and not entry.is_file():
            continue
        if dirs_only and not entry.is_dir():
            continue
        candidates.add(name)
    return candidates


def list_available_items(
    directory: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
) -> list[str]:
    """Sorted remaining picks (candidates minus logged history)."""
    dir_path = Path(directory).expanduser()
    log_path = (
        Path(log_file).expanduser()
        if log_file is not None
        else resolve_default_log(dir_path)
    )
    try:
        candidates = list_candidates(
            dir_path,
            log_path,
            include_hidden=include_hidden,
            files_only=files_only,
            dirs_only=dirs_only,
        )
    except FileNotFoundError:
        return []
    if not candidates:
        return []
    return sorted(candidates - get_logged_items(log_path))


def get_unselected_item(
    directory: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    rng: random.Random | None = None,
) -> str | None:
    """Return a random unselected entry name, or None if none remains."""
    available = list_available_items(
        directory,
        log_file,
        include_hidden=include_hidden,
        files_only=files_only,
        dirs_only=dirs_only,
    )
    if not available:
        return None
    if rng is None:
        return random.choice(available)
    return rng.choice(available)
