"""Persistent JSONL history of selected items."""

import json
import os
import stat
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_LOG_FILENAME = ".choosier.jsonl"
LOG_ROTATE_BYTES = 1_000_000


@dataclass(frozen=True)
class LogEntry:
    """One valid history line: parsed timestamp, item, and display text."""

    timestamp: str | None
    item: str
    display: str


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


def read_log_entries(
    log_file: str | Path = DEFAULT_LOG_FILENAME,
) -> list[LogEntry]:
    """Read a history log into structured entries, one per valid line."""
    log_path = Path(log_file).expanduser()
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries: list[LogEntry] = []
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        ts, item = parse_log_line(stripped)
        if item is None:
            continue
        display = f"{ts}  {item}" if ts is not None else stripped
        entries.append(LogEntry(timestamp=ts, item=item, display=display))
    return entries


def load_log(
    log_file: str | Path = DEFAULT_LOG_FILENAME,
) -> tuple[set[str], list[str]]:
    """Read a history log once: (logged names, history display lines)."""
    entries = read_log_entries(log_file)
    return {entry.item for entry in entries}, [entry.display for entry in entries]


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


def _rewrite_log(log_path: Path, lines: list[str]) -> None:
    """Replace the log file with `lines` atomically (temp file + rename)."""
    content = "".join(lines)
    handle_fd, temp_name = tempfile.mkstemp(
        dir=log_path.parent, prefix=f".{log_path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp_path, stat.S_IMODE(log_path.stat().st_mode))
        except OSError:
            pass
        os.replace(temp_path, log_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def remove_log_items(
    items: Collection[str], log_file: str | Path = DEFAULT_LOG_FILENAME
) -> int:
    """Remove every log entry for each item in `items` in one rewrite.

    Returns the number of entries removed (0 if the log is missing or
    none of the items are logged). All other lines are kept verbatim.
    Rewrites the log atomically so a crash cannot leave a truncated file
    behind.
    """
    names = set(items)
    if not names:
        return 0
    log_path = Path(log_file).expanduser()
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        return 0
    kept: list[str] = []
    removed = 0
    for line in raw_lines:
        if parse_log_line(line)[1] in names:
            removed += 1
        else:
            kept.append(line)
    if removed == 0:
        return 0
    _rewrite_log(log_path, kept)
    return removed


def remove_log_item(item: str, log_file: str | Path = DEFAULT_LOG_FILENAME) -> int:
    """Remove every log entry for `item`, keeping all other lines verbatim."""
    return remove_log_items({item}, log_file)


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
