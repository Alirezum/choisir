# Data Model: Backend Service Extraction and Unified Data Access

**Feature**: `specs/002-backend-services`
**Date**: 2026-10-30

## Overview

This feature does not change the history format, API schemas, or on-disk
layout. It introduces internal, interface-neutral service data structures and
makes the existing history entry the single representation for all readers.

## Persisted Data

### History entry (`LogEntry`)

One parsed line from the history file.

| Field | Type | Notes |
| --- | --- | --- |
| `timestamp` | `str \| None` | ISO timestamp for current JSONL lines; `None` for legacy and plain lines. |
| `item` | `str` | The selected entry name. This is the identity used for repeat prevention and removals. |
| `display` | `str` | `"<timestamp>  <item>"` for timestamped entries; the original stripped line otherwise. |

Rules:

- Current lines are JSON objects with `ts` and `item`.
- Legacy lines use `<timestamp> - <item>`; plain lines are accepted as items.
- Blank, malformed, or structurally invalid lines are ignored by readers.
- Duplicate entries for the same item are allowed; removal removes every
  matching line.
- The file remains `<target>/.choosier.jsonl` by default, or the explicit
  override. Logs over 1 MB rotate to timestamped `.old` backups.
- The history format and archive naming are frozen by the public contract.

### History archive

A timestamped copy of a prior history file, named
`<stem>-<UTC timestamp>[_counter]<suffix>.old`. Archiving moves the active log
to the backup and leaves no active log. Archives are never candidates for
picking.

## Service Data Structures

### `HistorySnapshot`

The result of one structured history read.

| Field | Type | Notes |
| --- | --- | --- |
| `entries` | `tuple[LogEntry, ...]` | Valid entries in file order. |
| `logged` | `frozenset[str]` | Item names derived from `entries`. |
| `display` | `tuple[str, ...]` | Display lines derived from `entries`. |

Invariant: `logged` and `display` are derived from the same `entries` tuple;
no second file read is required.

### `HistoryService`

Application-level owner of history reads and commands. It holds one resolved
`log_file: Path`.

| Operation | Result | Notes |
| --- | --- | --- |
| `snapshot(ignore_errors=True)` | `HistorySnapshot` | One structured read; tolerant by default. |
| `read_entries()` | `tuple[LogEntry, ...]` | Derived from `snapshot()`. |
| `logged_items()` | `set[str]` | Derived from `snapshot()`. |
| `display_lines()` | `list[str]` | Derived from `snapshot()`. |
| `append(item)` | `None` | Uses the existing append + rotation command. |
| `remove(item)` | `int` | Removes every matching entry; atomic rewrite. |
| `remove_many(items)` | `int` | One atomic rewrite for all items. |
| `archive()` | `Path \| None` | Moves the log to a backup; `None` if missing. |
| `clear()` | `bool` | Deletes the log; `False` if missing. |

Failure behavior:

- `append` maps `OSError` to `ServiceError(IO_ERROR, "Error writing log: ...")`.
- `archive` maps to `"Error archiving log: ..."`.
- `clear` maps to `"Error resetting log: ..."`.
- `remove` maps to `"Error removing history item: ..."`.
- `remove_many` maps to `"Error removing history items: ..."`.
- Reads keep the existing tolerant behavior by default;
  `ignore_errors=False` propagates `OSError`, and
  `storage.get_logged_items` retains its strict error behavior for selection.

### `BrowseEntry` and `BrowseListing`

| Entity | Fields | Notes |
| --- | --- | --- |
| `BrowseEntry` | `name: str`, `is_dir: bool` | One directory child. |
| `BrowseListing` | `path: Path`, `parent: Path \| None`, `entries: tuple[BrowseEntry, ...]` | Parent is `None` at a filesystem root. |

Rules:

- Entries are ordered directories-first, then case-insensitive by name.
- A missing or non-directory target produces `ServiceError(NOT_FOUND,
  "Not a directory")`.
- A listing permission failure produces `ServiceError(FORBIDDEN,
  "Cannot list: ...")`.

### `StateSnapshot`

The result of state assembly for one target, log, and filter combination.

| Field | Type | Notes |
| --- | --- | --- |
| `valid_path` | `bool` | `False` for a missing/non-directory target; this is a domain outcome, not an error. |
| `path` | `Path` | Expanded target path. |
| `log_file` | `Path` | Effective history path. |
| `remaining` | `tuple[str, ...]` | Sorted candidates minus logged items, capped by `max_lines` when supplied. |
| `remaining_total` | `int` | Full count before capping. |
| `history` | `tuple[LogEntry, ...]` | Recent entries, capped by `max_lines` when supplied. |
| `history_total` | `int` | Full history count before capping. |

Rules:

- A files-only/directories-only conflict raises
  `ServiceError(INVALID_INPUT, "files_only and dirs_only are mutually exclusive")`.
- Hidden and type filters match the existing `list_candidates` rules.
- The history file and its archives are never candidates.
- Web uses the default 200-line cap; TUI passes no cap and keeps its existing
  last-200 render behavior.

### `PickOutcome`

The result of one pick attempt.

| Field | Type | Notes |
| --- | --- | --- |
| `status` | `"picked" \| "empty" \| "exhausted" \| "invalid_path"` | Domain outcome. |
| `log_file` | `Path` | Effective history path. |
| `item` | `str \| None` | Selected name when picked. |
| `logged` | `bool` | Whether this pick wrote the history. |
| `preview` | `Preview \| None` | Present only when the caller requested preview work. |

Rules:

- A non-directory target returns `invalid_path`; it is not an error.
- No eligible entries returns `empty` when the target has no entries and
  `exhausted` when entries exist but are all logged. The distinction uses raw
  directory entries, as today.
- A seeded pick constructs a fresh RNG from the seed; the existing selection
  algorithm and sorted ordering are unchanged.
- `dry_run` prevents the append and leaves `logged` false.
- `commit=False` suppresses logging for adapters that need to interleave output
  with the write; the caller appends through `HistoryService` and `logged`
  remains false because this pick did not write history.
- A logging failure raises `ServiceError(IO_ERROR, "Error writing log: ...")`.
- The preview is generated only when requested, preserving CLI behavior.

### `OpenOutcome`

The result of opening one entry.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | `str` | The entry name returned to the caller after a successful launch. |

Rules:

- A missing entry raises `ServiceError(NOT_FOUND, "Entry is gone")`.
- A launcher `OSError` raises `ServiceError(IO_ERROR, "Cannot open: ...")`.
- Launching remains an explicit adapter action; the service never launches on
  its own.

### `Preview`, `PreviewImage`, `PreviewVideo`

These existing core structures remain unchanged:

- `Preview.kind`: text, directory, binary, empty, gone, unreadable, archive,
  image, or video.
- `Preview.text`, `truncated`, `entry_count`, `size`, `images`, `image_total`,
  `video`.
- `PreviewImage.index` is the archive member position; `None` for standalone
  images. Serving code reads by position, never by client-supplied name.
- `PreviewVideo` carries name, media type, and size.

The web adapter maps these structures to its existing Pydantic response models;
the models and their fields do not change.

### `ImagePayload` and `VideoFile` (web-only)

| Entity | Fields | Notes |
| --- | --- | --- |
| `ImagePayload` | `data: bytes`, `media_type: str` | Original or WebP-rendered image bytes. |
| `VideoFile` | `path: Path`, `media_type: str`, `stat_result: os.stat_result` | Validated video metadata for streaming. |

Rules:

- Standalone images validate extension, existence, size, read success, and
  content signature.
- Archive images validate the zip, member index, member type, encryption flag,
  and size; members are read by position.
- Thumbnails and preview renditions preserve current size limits, WebP output,
  and quality settings.
- Videos validate existence, extension, content signature, and stat success.
  HTTP byte-range parsing remains in the web adapter because it is transport
  behavior.

### `ServiceError` and `FailureKind`

`FailureKind` is an interface-neutral vocabulary:

- `INVALID_INPUT`
- `FORBIDDEN`
- `NOT_FOUND`
- `PAYLOAD_TOO_LARGE`
- `UNSUPPORTED_MEDIA_TYPE`
- `RANGE_NOT_SATISFIABLE`
- `IO_ERROR`

`ServiceError` carries `kind`, a human-readable `message`, and optional
`details`. It contains no HTTP status, framework type, or UI widget.

## Relationships

```text
HistoryService ──reads/writes──> history file and archives
HistoryService ──produces──────> HistorySnapshot
StateSnapshot  ──uses──────────> HistorySnapshot entries + logged names
PickOutcome    ──uses──────────> Preview (optional)
Web adapter    ──maps──────────> existing Pydantic response models
CLI/TUI        ──map───────────> existing exit codes, messages, panels
Web media      ──uses──────────> preview media constants and Pillow (web extra)
```

## State Transitions

### Pick

```text
target not a directory ──> invalid_path
target is empty         ──> empty
all entries logged      ──> exhausted
eligible entry found    ──> picked ──> append (unless dry_run or commit=False) ──> logged true
```

### History commands

```text
append(item)      : active log gains one JSONL line
remove(item)      : all matching lines removed in one atomic rewrite
remove_many(items): all matching lines for every item removed in one atomic rewrite
archive()         : active log moved to timestamped backup; active log absent
clear()           : active log deleted; absent
```

## Validation Rules

- `files_only` and `dirs_only` are mutually exclusive.
- Hidden entries are excluded unless requested; the active log and its backups
  are always excluded.
- History parsing accepts current JSONL, legacy timestamp-and-item lines, and
  plain lines; blank/malformed lines are skipped.
- Removals preserve all unrelated lines verbatim.
- History writes remain atomic where they already are; no new persistence
  format, locking, or database is introduced.
- Image/video validation preserves every existing limit and failure category.
- HTTP range validation remains in the web adapter and preserves malformed
  (400) and unsatisfiable (416) responses.

## What Does Not Change

- The JSONL history format, rotation threshold, and archive naming.
- The 12 existing `/api` routes, their success schemas, and the error envelope.
- CLI flags, output strings, and exit codes.
- TUI shortcuts, messages, and panel behavior.
- The public compatibility exports in `choosier/__init__.py` and `main.py`.
