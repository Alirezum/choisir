"""Picking one unselected entry for every interface."""

import random
from pathlib import Path
from typing import Literal

from choosier.chooser import get_unselected_item, resolve_log_path
from choosier.preview import preview_entry
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.history import HistoryService
from choosier.services.models import PickOutcome


def pick(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    seed: int | None = None,
    dry_run: bool = False,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
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
    rng = random.Random(seed) if seed is not None else None
    item = get_unselected_item(
        target,
        log_path,
        include_hidden=include_hidden,
        files_only=files_only,
        dirs_only=dirs_only,
        rng=rng,
    )
    if item is None:
        status: Literal["empty", "exhausted"] = (
            "exhausted" if any(target.iterdir()) else "empty"
        )
        return PickOutcome(status=status, log_file=log_path)
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
