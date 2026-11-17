"""Remaining candidates and recent history for one target."""

import os
from pathlib import Path

from choosier.chooser import resolve_log_path, scan_candidates
from choosier.filters import (
    FilterOptions,
    FilterSelection,
    build_filter_options,
    filter_candidates,
)
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.history import HistoryService
from choosier.services.models import StateSnapshot
from choosier.skip import SkipSelection

PANEL_MAX_LINES = 200


def _empty_snapshot(
    target: Path,
    log_path: Path,
    *,
    valid_path: bool,
) -> StateSnapshot:
    return StateSnapshot(
        valid_path=valid_path,
        path=target,
        log_file=log_path,
        remaining=(),
        remaining_total=0,
        history=(),
        history_total=0,
        filter_options=FilterOptions(),
        known_entry_exclusions=(),
    )


def _present_names(target: Path) -> frozenset[str]:
    """Every direct child name, independent of the current option filters."""
    try:
        with os.scandir(target) as entries:
            return frozenset(entry.name for entry in entries)
    except OSError:
        return frozenset()


def build_state(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    selection: FilterSelection | None = None,
    skips: SkipSelection | None = None,
    max_lines: int | None = PANEL_MAX_LINES,
) -> StateSnapshot:
    """Remaining picks and recent history for the current target and filters."""
    target = Path(path).expanduser()
    log_path = resolve_log_path(target, str(log_file) if log_file is not None else "")
    if not target.is_dir():
        return _empty_snapshot(target, log_path, valid_path=False)
    if files_only and dirs_only:
        raise ServiceError(
            FailureKind.INVALID_INPUT,
            "files_only and dirs_only are mutually exclusive",
        )
    scan = scan_candidates(
        target,
        log_path,
        include_hidden=include_hidden,
        files_only=files_only,
        dirs_only=dirs_only,
    )
    if not scan.valid_path:
        return _empty_snapshot(target, log_path, valid_path=False)
    chosen = selection or FilterSelection()
    filtered = filter_candidates(scan.entries, chosen)
    snapshot = HistoryService(log_path).snapshot()
    skip_names = skips.names if skips is not None else frozenset()
    skipped_present = tuple(
        sorted(name for name in skip_names if name in _present_names(target))
    )
    skipped = tuple(name for name in skipped_present if name not in snapshot.logged)
    eligible = [
        candidate.name
        for candidate in filtered
        if candidate.name not in snapshot.logged
    ]
    remaining = [name for name in eligible if name not in skip_names]
    all_skipped = bool(eligible) and not remaining
    history = list(snapshot.entries)
    remaining_total = len(remaining)
    history_total = len(history)
    if max_lines is not None:
        remaining = remaining[:max_lines]
        history = history[-max_lines:]
    base_names = {candidate.name for candidate in scan.entries}
    known_entry_exclusions = tuple(
        sorted(name for name in chosen.excluded_entries if name in base_names)
    )
    return StateSnapshot(
        valid_path=True,
        path=target,
        log_file=log_path,
        remaining=tuple(remaining),
        remaining_total=remaining_total,
        history=tuple(history),
        history_total=history_total,
        filter_options=build_filter_options(scan.entries),
        known_entry_exclusions=known_entry_exclusions,
        skipped=skipped,
        skipped_total=len(skipped),
        skipped_present=skipped_present,
        all_skipped=all_skipped,
    )
