# Phase 1 Data Model: Undo Last Pick

**Feature**: `007-undo-last-pick` | **Date**: 2026-11-17

This feature adds no persistent entity and does not change the history format.
It adds one in-memory receipt, one session state, one service result, and one
additive API field.

## Entity: UndoReceipt

The proof that a specific session appended a specific history line.

| Field | Type | Origin | Rules |
|-------|------|--------|-------|
| `item` | string | The pick outcome | Non-empty; exactly the name written in the history entry |
| `entry` | string | The exact JSON text appended, without line terminator | Non-empty; contains no raw CR/LF; `parse_log_line(entry)` must yield `item` |
| `digest` | string | SHA-256 of the complete log bytes after the append | 64 lowercase hexadecimal characters |

**Lifecycle**: created only when a pick is `picked`, `logged: true`, and no
rotation occurred. Held in interface memory. Never persisted, never placed in
the history file, never added to path memory. Discarded on the clear events in
the session state below.

**Identity rule**: `(digest, entry, item)` is valid only while the current log's
SHA-256 digest equals `digest` and its final line is exactly `entry`. Because the
digest covers the whole file, a matching receipt proves the entry is present,
is the newest line, and that no other line changed since the append.

## Entity: UndoStatus

A closed value set for the domain result of an undo attempt.

| Value | Meaning | History effect |
|-------|---------|----------------|
| `undone` | The receipt matched and the final line was removed | One line removed via atomic rewrite |
| `nothing_to_undo` | No log exists, the log is empty, or the target folder no longer exists | No change |
| `changed` | The log is non-empty but the digest or trailing-line identity did not match | No change |

An unreadable or unwritable log is not a status: it raises the shared
`ServiceError(FailureKind.IO_ERROR, ...)` and becomes the existing 500 error
envelope in the web adapter.

## Entity: UndoOutcome

The service/API result returned to an adapter.

| Field | Type | Notes |
|-------|------|-------|
| `status` | `UndoStatus` | See above |
| `item` | string | Echo of the receipt's item, for feedback and the API response |
| `log_file` | path/string | The resolved active history file, matching existing route responses |
| `removed` | boolean | `true` only when `status == "undone"` |

## Entity: Session Undo State

Held by `ChooserApp` (TUI) or by `useUndo` (web). It owns at most one receipt.

| State | Meaning | Control |
|-------|---------|---------|
| `Unavailable` | No receipt in memory | Disabled; accessible label says nothing to undo |
| `Available(receipt)` | The latest completed pick attempt was logged | Enabled; label includes the item |

### Transitions

| Event | Current state | Next state | Side effects |
|-------|---------------|------------|--------------|
| App/page start or restart | any | `Unavailable` | No history read needed |
| A pick attempt starts | `Available` | `Unavailable` | Clears the previous target before the request |
| Pick result is logged, not rotated | `Unavailable` | `Available(new)` | Stores the returned receipt |
| Pick result is a dry run, invalid path, empty, exhausted, filtered, or unlogged | `Unavailable` | `Unavailable` | No receipt returned |
| Pick request fails with an I/O error | `Unavailable` | `Unavailable` | Error message only |
| Undo returns `undone` | `Available` | `Unavailable` | Choice/preview cleared only if they show the item; panels refresh |
| Undo returns `changed` or `nothing_to_undo` | `Available` | `Unavailable` | Message names the item; history view refreshes |
| Undo request fails with an I/O error | `Available` | `Available` | Message shown; receipt kept so the user may retry |
| Active folder or log setting changes | `Available` | `Unavailable` | Filters reset as they already do; history untouched |
| Archive/clear/removal actually changed the log | `Available` | `Unavailable` | Existing history action behavior unchanged |
| Same-item history row previewed or loaded | `Available` | `Available` | The receipt still targets the latest session pick |
| Unrelated history row previewed | `Available` | `Available` | Choice may differ from the target; undo leaves it in place |

## Existing Entity: HistoryEntry (unchanged)

The JSONL record remains `{"ts": <ISO-8601 string>, "item": <name>}`; legacy
timestamp-and-item and plain lines remain readable. Undo appends nothing and
introduces no marker, tombstone, or schema version. It removes one existing
line and preserves every other byte of the log, including blank and malformed
lines.

## Validation and Invariants

1. A receipt is issued only after the log write succeeds and rotation did not
   move the file.
2. `digest` is computed from the exact bytes after the append, not from parsed
   entries, so line endings and unrelated bytes are covered.
3. Undo acquires the history lock before reading, verifying, and rewriting.
4. Undo writes nothing unless the digest matches **and** the final line equals
   `entry` and parses to `item`.
5. On any verification failure, the log bytes are left unchanged.
6. On a successful undo, the rewrite contains every line except the final one;
   no other line is normalized, reordered, or re-serialized.
7. The log's parent directory is never created by undo, and no target file or
   folder is touched.
8. Undo never issues a new pick and never restores a previous seed or filter.
9. The receipt is not persisted; a restart or page reload makes undo
   unavailable until a new logged pick succeeds.
10. The lock file contains no user data (zero bytes on POSIX and a single NUL
    byte on Windows), and is excluded from candidate scans.
