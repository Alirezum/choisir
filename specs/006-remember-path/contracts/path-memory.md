# Contract: Path Memory Core

**Module**: `choosier/path_memory.py` | **Feature**: 006-remember-path

The module is standard-library-only and UI-agnostic. It is the single owner of
the path-memory file, canonicalization, availability checks, locking, atomic
writes, and pruning. Adapters must not read or write the file directly.

## Public Surface

```python
MAX_RECENT = 10
DEFAULT_FILENAME = "path-memory.json"
ENV_OVERRIDE = "CHOOSIER_PATH_MEMORY_FILE"


def default_memory_path() -> Path: ...


def canonical_path(value: str | Path) -> Path: ...


def is_usable_directory(path: Path) -> bool: ...


@dataclass(frozen=True)
class MemorySnapshot:
    recent: tuple[str, ...]  # valid, ordered, unique, newest first
    warning: str | None  # pruning/read notice; None when clean


@dataclass(frozen=True)
class StartupResolution:
    path: Path
    source: Literal["recent", "default"]
    warning: str | None


@dataclass(frozen=True)
class MutationResult:
    ok: bool
    changed: bool
    notice: str | None


class PathMemory:
    def __init__(self, file: str | Path | None = None) -> None: ...

    @property
    def file(self) -> Path: ...

    def snapshot(self) -> MemorySnapshot: ...

    def startup(self, default: Path) -> StartupResolution: ...

    def record(self, folder: str | Path) -> MutationResult: ...

    def remove(self, folder: str | Path) -> MutationResult: ...

    def clear(self) -> MutationResult: ...
```

`PathMemory()` uses `default_memory_path()`; passing a file is an explicit
override used by tests and by adapters that want to inject a location.

## Location Resolution

`default_memory_path()`:

1. If `CHOOSIER_PATH_MEMORY_FILE` is set and non-empty, return
   `Path(value).expanduser()` unchanged (no existence requirement).
2. `sys.platform == "win32"`: `%APPDATA%\choosier\path-memory.json`; if
   `%APPDATA%` is missing, `~/.config/choosier/path-memory.json`.
3. `sys.platform == "darwin"`:
   `~/Library/Application Support/choosier/path-memory.json`.
4. Otherwise: `$XDG_CONFIG_HOME/choosier/path-memory.json` when
   `XDG_CONFIG_HOME` is absolute, else `~/.config/choosier/path-memory.json`.

The parent directory is created on first write with `parents=True` and
best-effort `0o700`. The file is written with best-effort `0o600`.

## File Format

```json
{
  "version": 1,
  "recent": ["/absolute/canonical/folder", "/another/folder"]
}
```

- UTF-8, trailing newline, no extra keys required or preserved.
- `recent` order is authoritative recency, newest first.
- Missing file → empty list, no warning.
- Malformed JSON, non-object root, non-list `recent`, or `version` other than
  `1` → empty list with a read warning; the file is not modified by the read.
- Invalid elements (non-string, blank, relative) are dropped. Identities are
  deduplicated keeping the first occurrence. The list is truncated to
  `MAX_RECENT`.

## Semantics

### `canonical_path(value)`

Returns `Path(value).expanduser().resolve()` (non-strict). Relative inputs are
resolved against the process working directory by `Path.resolve()`; callers
that require absolute input (the HTTP item route) validate before calling.

### `is_usable_directory(path)`

True only when the path exists, is a directory, and can be opened for listing
(`os.scandir`). All `OSError`s return False. No exception escapes.

### `snapshot()`

Acquires the exclusive lock, reads the record, validates/deduplicates/truncates,
drops unavailable directories, and atomically rewrites the file when pruning
changed the stored list. Returns valid paths in recency order. If the lock,
read, or prune write fails, returns the best-known valid list (possibly empty)
with a non-blocking warning.

### `startup(default)`

Calls `snapshot()`. If at least one valid recent path exists, returns it with
`source="recent"` and any warning. Otherwise returns `default` with
`source="default"` and the warning (if any). An explicitly supplied launch path
bypasses this function entirely.

### `record(folder)`

Under the exclusive lock:

1. Canonicalize the folder and verify it is a usable directory. If not, return
   `ok=False, changed=False` and a notice; do not write.
2. Read the current document (tolerant rules above).
3. Remove any entry with the same `os.path.normcase(identity)`.
4. Insert the canonical path at index 0.
5. Truncate to `MAX_RECENT`.
6. Atomically persist.
7. Return `ok=True, changed=True` and no notice.

Recording persists even if the list content is unchanged (re-recording the most
recent folder), because it refreshes the ordering. I/O/lock failures return
`ok=False, changed=False` with a notice and leave the previous file intact.

### `remove(folder)`

Canonicalizes, removes any matching identity under the lock, and persists only
when something was removed. Returns `ok=True, changed=<bool>`; absent paths are
not an error. Never touches any other state.

### `clear()`

Under the lock, persists an empty `recent` list. Returns `ok=True`,
`changed=True` when entries existed, otherwise `changed=False`. Never touches
any other state.

## Concurrency and Atomicity

- All operations take an exclusive lock on `<file>.lock`:
  `fcntl.flock(fd, LOCK_EX)` on POSIX, `msvcrt.locking(fd, LK_LOCK, 1)` on
  Windows. The descriptor is closed in `finally`, releasing the lock.
- Writes use a temporary file in the same directory, `flush`, `fsync`,
  best-effort `chmod`, then `os.replace`. Temporary files are unlinked on
  failure.
- A crash leaves either the old or the new complete document, never a partial
  one. Locks are released by the OS on process exit.
- Lock creation failure or lock acquisition failure is treated as an I/O
  failure: mutation returns `ok=False` with a notice; `snapshot` degrades.

## Failure Notices

Notices are short, single-line, user-facing strings. Suggested forms:

- Read: `"Remembered folders could not be read."`
- Prune: `"Skipped 1 unavailable remembered folder."`
- Record: `"Could not remember this folder: <reason>."`
- Remove/clear: `"Could not update remembered folders: <reason>."`

The module never raises for expected filesystem failure and never prints or
logs path contents.

## Guarantees

- Stores only local folder paths and ordering. No file names, history, filters,
  choices, previews, log paths, timestamps, or telemetry.
- Never modifies, moves, renames, or deletes user-selected files or folders.
- Never consults or alters the history log.
- Equivalent spellings of one folder map to one entry.
- At most ten entries, newest first, stale entries pruned on read.
- The one-shot CLI does not reference this module.
