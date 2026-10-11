"""Persistent JSONL history of selected items."""

import json
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_LOG_FILENAME = ".choosier.jsonl"
LOG_ROTATE_BYTES = 1_000_000


def parse_log_line(line: str) -> tuple[str | None, str | None]:
    """Parse one history line into (timestamp, item).

    Returns (None, None) for blank or malformed lines. Legacy
    '<ts> - <item>' and plain lines yield a None timestamp.
    """
    stripped = line.strip()
    if not stripped:
        return None, None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(obj, dict) and isinstance(obj.get("item"), str):
            ts = obj.get("ts")
            return (ts if isinstance(ts, str) else None, obj["item"])
        return None, None
    if " - " in stripped:
        return None, stripped.split(" - ", 1)[1]
    return None, stripped


def _parse_log_line(line: str) -> str | None:
    return parse_log_line(line)[1]


def get_logged_items(log_file: str | Path = DEFAULT_LOG_FILENAME) -> set[str]:
    """Read previously selected item names from a JSONL log file."""
    log_path = Path(log_file).expanduser()
    if not log_path.exists():
        return set()
    with open(log_path, encoding="utf-8") as f:
        items = set()
        for line in f:
            item = _parse_log_line(line)
            if item is None:
                continue
            items.add(item)
        return items


def log_selection(item: str, log_file: str | Path = DEFAULT_LOG_FILENAME) -> None:
    """Append a selection to the log.

    Raises:
        OSError: If the log file cannot be written.
    """
    log_path = Path(log_file).expanduser()
    with open(log_path, "a", encoding="utf-8") as f:
        ts = datetime.now(UTC).isoformat()
        f.write(json.dumps({"ts": ts, "item": item}, ensure_ascii=False) + "\n")
    _maybe_rotate_log(log_path)


def _backup_path(log_path: Path) -> Path:
    """Timestamped backup name for a log file, with a counter on collision."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = log_path.with_name(f"{log_path.stem}-{stamp}{log_path.suffix}.old")
    counter = 1
    while backup.exists():
        counter += 1
        backup = log_path.with_name(
            f"{log_path.stem}-{stamp}_{counter}{log_path.suffix}.old"
        )
    return backup


def _maybe_rotate_log(log_file: str | Path = DEFAULT_LOG_FILENAME) -> None:
    log_path = Path(log_file).expanduser()
    try:
        if log_path.stat().st_size <= LOG_ROTATE_BYTES:
            return
    except OSError:
        return
    try:
        log_path.rename(_backup_path(log_path))
    except OSError:
        pass


def archive_log(log_file: str | Path = DEFAULT_LOG_FILENAME) -> Path | None:
    """Move the history log to a timestamped backup, starting fresh.

    Returns the backup path, or None if there was nothing to archive.
    Other OSErrors propagate to the caller.
    """
    log_path = Path(log_file).expanduser()
    if not log_path.exists():
        return None
    if log_path.is_dir():
        raise IsADirectoryError(f"Not a history file: {log_path}")
    backup = _backup_path(log_path)
    log_path.rename(backup)
    return backup


def reset_log(log_file: str | Path = DEFAULT_LOG_FILENAME) -> bool:
    """Delete a history log file.

    Returns True if a file was removed, False if there was nothing to delete.
    Other OSErrors propagate to the caller.
    """
    log_path = Path(log_file).expanduser()
    try:
        log_path.unlink()
    except FileNotFoundError:
        return False
    return True
