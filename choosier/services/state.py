"""Remaining candidates and recent history for one target."""

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


def build_state(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    selection: FilterSelection | None = None,
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
    remaining = [
        candidate.name
        for candidate in filtered
        if candidate.name not in snapshot.logged
    ]
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
    )
