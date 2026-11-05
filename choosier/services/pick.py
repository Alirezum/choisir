"""Picking one unselected entry for every interface."""

import random
from pathlib import Path

from choosier.chooser import resolve_log_path, scan_candidates
from choosier.filters import FilterSelection, filter_candidates
from choosier.preview import preview_entry
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.history import HistoryService
from choosier.services.models import PickOutcome, PickStatus


def _empty_status(
    *,
    has_children: bool,
    base_count: int,
    filtered_count: int,
) -> PickStatus:
    if not has_children:
        return "empty"
    if base_count == 0:
        return "exhausted"
    if filtered_count == 0:
        return "filtered_empty"
    if filtered_count < base_count:
        return "filtered_exhausted"
    return "exhausted"


def pick(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    seed: int | None = None,
    dry_run: bool = False,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    selection: FilterSelection | None = None,
    commit: bool = True,
    include_preview: bool = False,
) -> PickOutcome:
    """Pick one unselected entry, optionally logging and previewing it."""
    target = Path(path).expanduser()
    log_path = resolve_log_path(target, str(log_file) if log_file is not None else "")
    if not target.is_dir():
        return PickOutcome(status="invalid_path", log_file=log_path)
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
        return PickOutcome(status="invalid_path", log_file=log_path)
    chosen = selection or FilterSelection()
    filtered = filter_candidates(scan.entries, chosen)
    snapshot = HistoryService(log_path).snapshot()
    remaining = [
        candidate.name
        for candidate in filtered
        if candidate.name not in snapshot.logged
    ]
    if not remaining:
        status = _empty_status(
            has_children=scan.has_children,
            base_count=len(scan.entries),
            filtered_count=len(filtered),
        )
        return PickOutcome(status=status, log_file=log_path)
    rng = random.Random(seed) if seed is not None else random.Random()
    item = rng.choice(remaining)
    logged = False
    if commit and not dry_run:
        HistoryService(log_path).append(item)
        logged = True
    preview = preview_entry(target / item) if include_preview else None
    return PickOutcome(
        status="picked",
        log_file=log_path,
        item=item,
        logged=logged,
        preview=preview,
    )
