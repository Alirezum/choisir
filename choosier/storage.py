"""Persistent JSONL history of selected items."""

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from choosier.locking import exclusive_lock

DEFAULT_LOG_FILENAME = ".choosier.jsonl"
LOG_ROTATE_BYTES = 1_000_000


@dataclass(frozen=True)
class LogEntry:
    """One valid history line: parsed timestamp, item, and display text."""

    timestamp: str | None
    item: str
    display: str


@dataclass(frozen=True)
class UndoReceipt:
    """Proof that this session appended one exact history line.

    ``digest`` is the SHA-256 of the complete log file after the append, so a
    matching receipt proves the entry is still present, newest, and that no
    other line changed since.
    """

    item: str
    entry: str
    digest: str


UndoStatus = Literal["undone", "nothing_to_undo", "changed"]


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
    *,
    ignore_errors: bool = True,
) -> list[LogEntry]:
    """Read a history log into structured entries, one per valid line.

    Tolerant by default: unreadable files yield no entries. Callers that
    need strict I/O behavior pass ``ignore_errors=False``.
    """
    log_path = Path(log_file).expanduser()
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        if ignore_errors:
            return []
        raise
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
    """Read previously selected item names from a JSONL log file.

    Missing files are tolerated; other I/O errors propagate as before.
    """
    log_path = Path(log_file).expanduser()
    if not log_path.exists():
        return set()
    entries = read_log_entries(log_path, ignore_errors=False)
    return {entry.item for entry in entries}


def log_selection(item: str, log_file: str | Path = DEFAULT_LOG_FILENAME) -> None:
    """Append a selection to the log.

    Raises:
        OSError: If the log file cannot be written.
    """
    append_log_entry(item, log_file)


def append_log_entry(
    item: str, log_file: str | Path = DEFAULT_LOG_FILENAME
) -> UndoReceipt | None:
    """Append one selection and return the receipt that can undo it.

    The receipt is returned only when the append completed and rotation did
    not move the file. Raises OSError if the log cannot be written.
    """
    log_path = Path(log_file).expanduser()
    with exclusive_lock(log_path):
        with open(log_path, "a", encoding="utf-8") as handle:
            ts = datetime.now(UTC).isoformat()
            entry = json.dumps({"ts": ts, "item": item}, ensure_ascii=False)
            handle.write(entry + "\n")
        digest = hashlib.sha256(log_path.read_bytes()).hexdigest()
        if _maybe_rotate_log(log_path) is not None:
            return None
    return UndoReceipt(item=item, entry=entry, digest=digest)


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


def _maybe_rotate_log(log_file: str | Path = DEFAULT_LOG_FILENAME) -> Path | None:
    """Move an oversized log aside; return the backup path when it moved."""
    log_path = Path(log_file).expanduser()
    try:
        if log_path.stat().st_size <= LOG_ROTATE_BYTES:
            return None
    except OSError:
        return None
    backup = _backup_path(log_path)
    try:
        log_path.rename(backup)
    except OSError:
        return None
    return backup


def _rewrite_log_bytes(log_path: Path, content: bytes) -> None:
    """Replace the log file with `content` atomically (temp file + rename)."""
    handle_fd, temp_name = tempfile.mkstemp(
        dir=log_path.parent, prefix=f".{log_path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
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


def _rewrite_log(log_path: Path, lines: list[str]) -> None:
    """Replace the log file with `lines` atomically (temp file + rename)."""
    _rewrite_log_bytes(log_path, "".join(lines).encode("utf-8"))


def _is_digest(value: str) -> bool:
    """True for exactly 64 lowercase hexadecimal characters."""
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def undo_log_entry(
    receipt: UndoReceipt, log_file: str | Path = DEFAULT_LOG_FILENAME
) -> UndoStatus:
    """Remove the exact final line identified by `receipt`, or nothing.

    The digest and the trailing line must both still match; otherwise the log
    is left byte-identical. Raises OSError for read or write failures other
    than a concurrently removed log or parent directory.
    """
    log_path = Path(log_file).expanduser()
    if "\n" in receipt.entry or "\r" in receipt.entry:
        return "changed"
    try:
        with exclusive_lock(log_path):
            try:
                data = log_path.read_bytes()
            except FileNotFoundError:
                return "nothing_to_undo"
            if not data:
                return "nothing_to_undo"
            if not _is_digest(receipt.digest):
                return "changed"
            if hashlib.sha256(data).hexdigest() != receipt.digest:
                return "changed"
            if data.endswith(b"\r\n"):
                prefix = data[:-2]
            elif data.endswith(b"\n"):
                prefix = data[:-1]
            else:
                return "changed"
            final = prefix.rsplit(b"\n", 1)[-1]
            try:
                final_line = final.decode("utf-8")
            except UnicodeDecodeError:
                return "changed"
            if final_line != receipt.entry:
                return "changed"
            if parse_log_line(final_line)[1] != receipt.item:
                return "changed"
            _rewrite_log_bytes(log_path, prefix[: len(prefix) - len(final)])
            return "undone"
    except FileNotFoundError:
        return "nothing_to_undo"


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
    if not log_path.exists():
        return 0
    with exclusive_lock(log_path):
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
    with exclusive_lock(log_path):
        if not log_path.exists():
            return None
        backup = _backup_path(log_path)
        log_path.rename(backup)
        return backup


def reset_log(log_file: str | Path = DEFAULT_LOG_FILENAME) -> bool:
    """Delete a history log file.

    Returns True if a file was removed, False if there was nothing to delete.
    Other OSErrors propagate to the caller.
    """
    log_path = Path(log_file).expanduser()
    if not log_path.exists():
        return False
    with exclusive_lock(log_path):
        try:
            log_path.unlink()
        except FileNotFoundError:
            return False
        return True
