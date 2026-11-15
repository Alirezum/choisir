# Phase 0 Research: Undo Last Pick

**Feature**: `007-undo-last-pick` | **Date**: 2026-11-17

All unknown technical choices are resolved below. No `NEEDS CLARIFICATION`
markers remain.

## R1. How is the exact history entry identified?

**Decision**: A successful logged pick returns an `UndoReceipt` containing:

- `item`: the picked name, for messages.
- `entry`: the exact JSON line text appended (without the line terminator).
- `digest`: the SHA-256 hex digest of the complete history file immediately
  after that append.

Undo succeeds only when the current file's SHA-256 digest equals the receipt's
digest, and the final line still parses to the receipt's entry and item. It then
rewrites the file without that final line.

**Rationale**: Timestamp-only or item-only receipts cannot distinguish duplicate
entries, and a "newest line" check alone lets an earlier rewrite slip through.
The digest is a byte-exact compare-and-swap guard: any append, removal, clear,
or rewrite between pick and undo changes it, so the operation refuses instead of
removing a substitute entry (FR-008, SC-004). Reading and hashing a log bounded
by the 1,000,000-byte rotation limit is a few milliseconds.

**Alternatives considered**:

- *Item plus timestamp*: two rapid picks of the same item can share a timestamp
  prefix, and an external rewrite can move or duplicate the entry.
- *Byte offset plus file size*: catches most changes but not a same-size rewrite
  before the entry, and offsets are invalidated by line-ending or encoding
  normalization.
- *Server-issued opaque token with an in-memory map*: makes undo state
  process-global, so a pick in one browser tab or session could be undone from
  another; also cannot be shared with the TUI without a second state store.
- *Re-read the last history line and remove it*: removes an entry this session
  did not create, directly violating FR-009.

## R2. How are concurrent picks, undos, and history edits serialized?

**Decision**: Extract the existing platform-specific lock from
`choosier/path_memory.py` into a shared `choosier/locking.py` helper and use an
exclusive advisory lock for every history mutation: append, single removal,
batch removal, archive, clear, and undo. The lock file is
`<resolved-log-path>.lock`, created beside the log with the same open/lock
pattern already used for path memory (`fcntl.flock` on POSIX,
`msvcrt.locking` on Windows). History locking does **not** create a missing
parent directory; a missing target folder is already an invalid pick target.

**Rationale**: The digest check and the atomic rewrite are only safe together if
no other process can append between them. A sibling lock is stable across the
`os.replace` that swaps the log inode. The extracted helper keeps the core
standard-library-only and avoids two copies of platform locking code.

**Alternatives considered**:

- *Lock the log file itself*: the atomic rewrite replaces the inode, so a waiter
  holding the old file descriptor would no longer exclude a new opener.
- *In-process lock only*: does not protect against a CLI or a second TUI/web
  process editing the same log.
- *No lock, re-check immediately before rename*: still leaves a check-then-write
  window that can lose a concurrent append.
- *Lock in the OS temp directory*: no file appears beside the log, but the OS may
  clear temp files and the lock becomes hard to discover and reason about.

The lock file carries no user data (zero bytes on POSIX and a single NUL byte
on Windows where `msvcrt` needs a lockable byte), is recreated on demand, and is
never read as application state. It is excluded from candidate scans (R8).

## R3. What happens when the log rotates because of the pick?

**Decision**: If appending the pick triggers the existing rotation
(`> 1,000,000` bytes after the append and the rename succeeds), the pick is
still logged and successful, but it returns no receipt. Undo is unavailable for
that pick.

**Rationale**: After rotation the entry lives in an archive, and the active log
is empty, so the item is already eligible. Removing a line from the archive would
violate the archive-preservation rule and confuse the user. The performance
requirement still holds: the undo path never handles more than the active log.

**Alternatives considered**: Targeting the backup file (breaks archive safety);
preventing rotation on the pick (changes existing history behavior); treating
the rotation as a failed pick (breaks the pick contract and the CLI parity).

## R4. What is the HTTP contract?

**Decision**:

- `POST /api/pick` gains one additive nullable field, `undo`, holding the
  receipt or `null`.
- New `POST /api/history/undo` route with body
  `{path, log_file, receipt: {item, entry, digest}}`.
- Success is `200` with
  `{log_file, status, item, removed}` where `status` is
  `"undone" | "nothing_to_undo" | "changed"`.
- Missing/empty log returns `nothing_to_undo`; any digest or identity mismatch
  returns `changed`; an unreadable or unwritable log returns the existing
  `internal_error` 500 envelope. A malformed body returns `validation_error`
  422; a non-POST method returns `method_not_allowed` 405.

**Rationale**: The project keeps expected domain outcomes at 200 with stable
fields, as `/api/pick`, `/api/history`, and `/api/history/item` already do. The
client needs to distinguish "nothing left to undo" from "another session changed
the log" without parsing messages. No new error code or status is needed, so the
error taxonomy stays frozen.

**Alternatives considered**: 409 Conflict (adds an error code and makes a normal
race look like a server fault); `removed` alone (cannot distinguish the two
non-removal reasons); an `undo` command on `POST /api/pick` (mixes two user
actions and makes the receipt optional in the pick body).

## R5. Where does session state live and when is it cleared?

**Decision**: The receipt is held only in memory by the interface that made the
pick: `ChooserApp._undo_receipt` in the TUI, and a `useUndo` ref in the browser.
It is replaced or cleared by every completed pick attempt (a non-logged outcome
clears it), cleared when the active folder or log setting changes, cleared after
a successful undo or a `changed`/`nothing_to_undo` result, cleared after a
successful archive/clear/removal that actually changed the log, and cleared by a
restart or page reload. An I/O error keeps the receipt so the user can retry.

**Rationale**: A client-held receipt is what makes "picks from other sessions are
not undoable" true by construction, without a server session store. Replacing it
on every attempt implements the spec's "most recent pick" rule: a dry run,
invalid path, empty folder, or exhausted pick leaves no target.

**Alternatives considered**: Server-side session state (shared across tabs and
restarts, violates FR-015); persisting the receipt in the history or path-memory
record (new persistent state); keeping an older receipt after a dry run (undo
would target a pick that is no longer the latest attempt, contradicting FR-002).

## R6. How do the interfaces present and label Undo?

**Decision**:

- **TUI**: a secondary `Button(id="undo")` in the existing `#actions` row after
  Pick and Open. Disabled with no receipt. When available, its label is
  `Undo <item>` and its tooltip repeats the target; Textual exposes the button
  label as the accessible name, so the item is part of it. Activation calls the
  shared service, then refreshes panels and the recent-folder list is untouched.
- **Web**: a secondary button beside Open in the board meta row, always present
  but disabled when unavailable. Visible text is `Undo`; `aria-label` is
  `Undo last pick: <item>` when available and `Undo last pick (nothing to undo)`
  otherwise. No new global keyboard shortcut is added; the button is a normal
  tab stop, so it cannot intercept a text field's own undo shortcut (FR-014).
- **Choice clearing**: after `undone`, clear the choice and preview only when the
  current choice's item equals the undone item. Leave an unrelated
  history-preview choice in place (FR-017).
- **Styling**: follow the loaded `frontend-design` skill and the existing
  graphite/amber split-flap language. The control is quiet and secondary, uses
  the established focus-visible ring and disabled treatment, and does not
  introduce a new palette, typeface, card, or animation.

**Rationale**: Both controls are reachable by keyboard and visibly unavailable
before any pick, matching P2 and FR-013. Avoiding a new shortcut removes the only
real conflict with browser text-field undo; the web requirement is conditional,
so no shortcut is required. The TUI has no ARIA layer, so its rendered label is
the available accessible name.

**Alternatives considered**: A global `Ctrl+Z` (would need careful target checks
and risks text-field undo); rendering the web control only when available (hides
why nothing can be undone); labeling the TUI button only "Undo" (drops the item
from its accessible name).

## R7. How does the shared core change while preserving compatibility?

**Decision**: Add `storage.append_log_entry(item, log_file) -> UndoReceipt | None`
as the primary append, and keep `storage.log_selection(...)` as a void wrapper so
the published helper and existing callers keep working. `HistoryService.append`
returns the receipt and still maps `OSError` to the exact existing
`"Error writing log: ..."` message. `services.pick` stores that result on
`PickOutcome.undo` only when `commit` is true and the pick is not a dry run. All
new dataclass fields default to `None`, so existing constructors and callers do
not change.

**Rationale**: The CLI, service tests, and TUI all share this path; a wrapper
keeps the public surface stable while the service gains the receipt. Service
errors stay interface-neutral and adapters keep their current messages.

**Alternatives considered**: A parallel receipt-only append path (two write
paths could diverge); returning a receipt from `log_selection` (changes a
published void signature); recomputing the receipt later from the log (cannot
prove the entry is this session's).

## R8. How is the lock file kept out of picks and counts?

**Decision**: Extend `chooser._is_managed_file` to treat
`name == f"{log_path.name}.lock"` as managed, alongside the log and its archived
`*.old` backups.

**Rationale**: With `--include-hidden`, the dot-prefixed lock file would
otherwise become a candidate and could be picked, violating the "no new visible
entries" expectation and the spirit of the managed-file rule.

**Alternatives considered**: Hide the lock in a temp directory (R2);
special-case it only in `scan_candidates` (the managed-file predicate is already
the shared place for this rule).

## R9. What remains explicitly unchanged?

**Decision**: The one-shot CLI keeps every flag, prompt, output line, and exit
code, and gains no undo option. The history JSONL format, legacy parsing,
rotation threshold, archive naming, and path-memory record are unchanged. Pick
selection, seed determinism, filters, ordering, and preview behavior are
unchanged. Undo never writes, moves, renames, or deletes a target entry.

**Rationale**: These are the feature's stated boundaries and the constitution's
public-contract constraints. The only visible additions are the TUI/web control,
the additive HTTP route/field, and the hidden lock file.
