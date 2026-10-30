"""Remaining candidates and recent history for one target."""

from pathlib import Path

from choosier.chooser import list_candidates, resolve_log_path
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.history import HistoryService
from choosier.services.models import StateSnapshot

PANEL_MAX_LINES = 200


def build_state(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    max_lines: int | None = PANEL_MAX_LINES,
) -> StateSnapshot:
    """Remaining picks and recent history for the current target and filters."""
    target = Path(path).expanduser()
    log_path = resolve_log_path(target, str(log_file) if log_file is not None else "")
    if not target.is_dir():
        return StateSnapshot(
            valid_path=False,
            path=target,
            log_file=log_path,
            remaining=(),
            remaining_total=0,
            history=(),
            history_total=0,
        )
    if files_only and dirs_only:
        raise ServiceError(
            FailureKind.INVALID_INPUT,
            "files_only and dirs_only are mutually exclusive",
        )
    try:
        candidates = list_candidates(
            target,
            log_path,
            include_hidden=include_hidden,
            files_only=files_only,
            dirs_only=dirs_only,
        )
    except FileNotFoundError:
        candidates = set()
    snapshot = HistoryService(log_path).snapshot()
    remaining = sorted(candidates - snapshot.logged)
    history = list(snapshot.entries)
    remaining_total = len(remaining)
    history_total = len(history)
    if max_lines is not None:
        remaining = remaining[:max_lines]
        history = history[-max_lines:]
    return StateSnapshot(
        valid_path=True,
        path=target,
        log_file=log_path,
        remaining=tuple(remaining),
        remaining_total=remaining_total,
        history=tuple(history),
        history_total=history_total,
    )
