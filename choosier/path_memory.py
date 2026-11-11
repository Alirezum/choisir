"""User-scoped memory of recently used target folders.

The module owns the path-memory file: location resolution, canonicalization,
availability checks, cross-process locking, atomic writes, and pruning. It is
standard-library-only and never touches target content or history.
"""

import json
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

MAX_RECENT = 10
DEFAULT_FILENAME = "path-memory.json"
ENV_OVERRIDE = "CHOOSIER_PATH_MEMORY_FILE"

READ_WARNING = "Remembered folders could not be read."
LOCK_WARNING = "Remembered folders could not be opened."
PRUNE_WARNING = "Could not update remembered folders."
RECORD_WARNING = "Could not remember this folder."
UPDATE_WARNING = "Could not update remembered folders."


@dataclass(frozen=True)
class MemorySnapshot:
    """Valid remembered folders, newest first, with a non-blocking notice."""

    recent: tuple[str, ...]
    warning: str | None


@dataclass(frozen=True)
class StartupResolution:
    """The folder chosen at launch and the reason for choosing it."""

    path: Path
    source: Literal["recent", "default"]
    warning: str | None


@dataclass(frozen=True)
class MutationResult:
    """The outcome of recording, removing, or clearing remembered folders."""

    ok: bool
    changed: bool
    notice: str | None


def default_memory_path() -> Path:
    """Return the OS-appropriate path-memory file, honoring the test override."""
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "choosier" / DEFAULT_FILENAME
        return Path.home() / ".config" / "choosier" / DEFAULT_FILENAME
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "choosier"
            / DEFAULT_FILENAME
        )
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config and Path(xdg_config).is_absolute():
        return Path(xdg_config) / "choosier" / DEFAULT_FILENAME
    return Path.home() / ".config" / "choosier" / DEFAULT_FILENAME


def canonical_path(value: str | Path) -> Path:
    """Expand and resolve a path without requiring it to exist."""
    return Path(value).expanduser().resolve()


def is_usable_directory(path: Path) -> bool:
    """True when `path` is a directory that can be listed."""
    try:
        with os.scandir(path):
            return True
    except (OSError, ValueError):
        return False


def _identity(value: str | Path) -> str:
    """Filesystem identity used only for comparison, never for storage."""
    return os.path.normcase(str(value))


def _normalize_entry(value: object) -> str | None:
    """Return a canonical absolute path string, or None when it is unusable."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        expanded = Path(value).expanduser()
        if not expanded.is_absolute():
            return None
        canonical = expanded.resolve()
    except (OSError, ValueError):
        return None
    if not canonical.is_absolute():
        return None
    return str(canonical)


def _combine(*warnings: str | None) -> str | None:
    parts = [warning for warning in warnings if warning]
    if not parts:
        return None
    return " ".join(dict.fromkeys(parts))


def _skip_warning(count: int) -> str | None:
    if count <= 0:
        return None
    noun = "folder" if count == 1 else "folders"
    return f"Skipped {count} unavailable remembered {noun}."


@contextmanager
def _exclusive_lock(file: Path) -> Iterator[None]:
    """Hold the exclusive sibling lock for the duration of the block."""
    file.parent.mkdir(parents=True, exist_ok=True)
    lock_path = file.with_name(f"{file.name}.lock")
    handle = open(lock_path, "a+b")
    try:
        if sys.platform == "win32":
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


class PathMemory:
    """Read and mutate the remembered-folder record for one user."""

    def __init__(self, file: str | Path | None = None) -> None:
        self._file = (
            Path(file).expanduser() if file is not None else default_memory_path()
        )

    @property
    def file(self) -> Path:
        """The record location; useful for diagnostics and tests."""
        return self._file

    def _read_locked(self) -> tuple[list[str], str | None, bool]:
        """Read and normalize the record.

        Returns the usable list, a warning when the document could not be
        interpreted, and whether the normalized list differs from the stored
        list (so the caller can rewrite it).
        """
        try:
            text = self._file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return [], None, False
        except (OSError, UnicodeError):
            return [], READ_WARNING, False
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, UnicodeError):
            return [], READ_WARNING, False
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("recent"), list)
        ):
            return [], READ_WARNING, False
        stored = data["recent"]
        normalized: list[str] = []
        seen: set[str] = set()
        for value in stored:
            entry = _normalize_entry(value)
            if entry is None:
                continue
            identity = _identity(entry)
            if identity in seen:
                continue
            seen.add(identity)
            normalized.append(entry)
            if len(normalized) == MAX_RECENT:
                break
        changed = normalized != stored
        return normalized, None, changed

    def _write_locked(self, recent: list[str]) -> None:
        """Atomically replace the record with `recent` while the lock is held."""
        parent = self._file.parent
        if not parent.exists():
            parent.mkdir(parents=True)
            try:
                os.chmod(parent, 0o700)
            except OSError:
                pass
        content = (
            json.dumps(
                {"version": 1, "recent": recent},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        handle_fd, temp_name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{self._file.name}.",
            suffix=".tmp",
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
            os.replace(temp_path, self._file)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    def snapshot(self) -> MemorySnapshot:
        """Return valid remembered folders, pruning unavailable entries."""
        try:
            self._file.stat()
        except FileNotFoundError:
            return MemorySnapshot((), None)
        except OSError:
            return MemorySnapshot((), READ_WARNING)
        try:
            with _exclusive_lock(self._file):
                entries, warning, changed = self._read_locked()
                valid: list[str] = []
                skipped = 0
                for entry in entries:
                    path = Path(entry)
                    if is_usable_directory(path):
                        valid.append(entry)
                    else:
                        skipped += 1
                prune_warning = _skip_warning(skipped)
                if changed or skipped:
                    try:
                        self._write_locked(valid)
                    except OSError:
                        return MemorySnapshot(
                            tuple(valid),
                            _combine(warning, prune_warning, PRUNE_WARNING),
                        )
                return MemorySnapshot(tuple(valid), _combine(warning, prune_warning))
        except OSError:
            return MemorySnapshot((), LOCK_WARNING)

    def startup(self, default: Path) -> StartupResolution:
        """Use the first valid recent folder, else the caller's default."""
        snapshot = self.snapshot()
        if snapshot.recent:
            return StartupResolution(
                Path(snapshot.recent[0]),
                "recent",
                snapshot.warning,
            )
        return StartupResolution(default, "default", snapshot.warning)

    def record(self, folder: str | Path) -> MutationResult:
        """Move a successfully used folder to the top of the recent list."""
        try:
            canonical = canonical_path(folder)
        except (OSError, ValueError):
            return MutationResult(False, False, RECORD_WARNING)
        if not is_usable_directory(canonical):
            return MutationResult(False, False, RECORD_WARNING)
        try:
            with _exclusive_lock(self._file):
                entries, _warning, _changed = self._read_locked()
                identity = _identity(canonical)
                kept = [entry for entry in entries if _identity(entry) != identity]
                recent = [str(canonical), *kept][:MAX_RECENT]
                self._write_locked(recent)
        except OSError:
            return MutationResult(False, False, RECORD_WARNING)
        return MutationResult(True, True, None)

    def remove(self, folder: str | Path) -> MutationResult:
        """Remove one remembered folder without touching anything else."""
        try:
            canonical = canonical_path(folder)
        except (OSError, ValueError):
            return MutationResult(False, False, UPDATE_WARNING)
        try:
            with _exclusive_lock(self._file):
                entries, _warning, _changed = self._read_locked()
                identity = _identity(canonical)
                recent = [entry for entry in entries if _identity(entry) != identity]
                changed = len(recent) != len(entries)
                if changed:
                    self._write_locked(recent)
        except OSError:
            return MutationResult(False, False, UPDATE_WARNING)
        return MutationResult(True, changed, None)

    def clear(self) -> MutationResult:
        """Persist an empty recent list without touching anything else."""
        try:
            with _exclusive_lock(self._file):
                entries, _warning, _changed = self._read_locked()
                self._write_locked([])
        except OSError:
            return MutationResult(False, False, UPDATE_WARNING)
        return MutationResult(True, bool(entries), None)
