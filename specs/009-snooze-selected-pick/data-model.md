# Phase 1 Data Model: Snooze the Selected Pick

**Feature**: `009-snooze-selected-pick` | **Date**: 2026-11-18

This feature adds no persistent entity and does not change the history format,
the path-memory record, the HTTP schema, or the target. It composes two
existing session-scoped entities — the single-level undo receipt and the
session skip record — inside each interactive interface.

## Entity: Latest Pick Receipt (existing `UndoReceipt`)

The proof that this session appended one exact history line and may remove it.

| Field | Type | Origin | Rules |
|-------|------|--------|-------|
| `item` | string | The successful logged pick | The exact direct-child name; must match the current choice for Snooze |
| `entry` | string | The serialized JSONL line that was appended | Must equal the last line on disk |
| `digest` | string | SHA-256 of the complete log after the append | Proves the line is still newest and no other line changed |

**Lifetime**: Session-only and target/log-file scoped. It is created only by a
successful non-dry-run pick. It is cleared by a completed Undo, a successful
Snooze, a domain refusal from either action, a new pick attempt, a target or
log-file change, a log archive, or a log clear. A transport or I/O failure keeps
it for retry; an item-missing preflight refusal also keeps it because the undo
never ran.

**Identity rule**: The receipt identifies one history line by content and
digest, not by item name alone. A same-named later pick elsewhere does not make
an old receipt valid.

## Entity: Snooze Eligibility (derived, interface-only)

The condition that enables the Snooze control. It is computed from existing
state and is never persisted or sent over HTTP.

| Condition | Source | Rule |
|-----------|--------|------|
| Receipt present | `useUndo.receipt` / `ChooserApp._undo_receipt` | Required |
| Current choice matches | `choice.choice.value.item` / `ChooserApp._current_choice.name` | Must equal `receipt.item` |
| No competing action | `undoing`, `snoozing`, `skipping` (web); the TUI event loop serializes actions | Required in the web UI |
| Same target and log scope | The scope that produced the receipt | Any scope change has already cleared the receipt |

Item existence is **not** part of the synchronous availability predicate. It is
checked at activation because it requires a filesystem or browse request and
because a missing item is a refusal outcome rather than a change to the undo
opportunity.

**Derived values**:

- `canSnooze` — the predicate above.
- `snoozeLabel` (web) — `Snooze last pick: <item>` when a receipt exists,
  otherwise `Snooze last pick (nothing to snooze)`. The label keeps naming the
  item while the control is temporarily disabled by an in-flight action.
- TUI label — `Snooze: <item>` when a receipt exists, otherwise `Snooze`.
- TUI tooltip — `Snooze <item> and undo its pick` when a receipt exists,
  otherwise `Nothing to snooze`.

## Entity: Snooze Action (interface-only)

One in-flight reversal-and-deferral attempt.

| Field | Type | Rules |
|-------|------|-------|
| `snoozing` | boolean | Web-only guard; true from activation until the final refresh completes |
| Captured receipt | `UndoReceipt` | Captured once at activation; the action never re-reads a newer receipt mid-flight |
| Captured item | string | `captured receipt.item` |

**Lifetime**: One action at a time per interface. The TUI serializes button
events; the web guard rejects a second activation and exposes the guard through
`canSnooze`.

## Entity: Snoozed Entry (existing session skip record)

One active deferral created by a successful Snooze. It is indistinguishable
from a skip created by **Not now**, except for how it entered the list.

| Field | Type | Origin | Rules |
|-------|------|--------|-------|
| `name` | string | The undo outcome's `item` | Same validation as any skipped name; exactly one record per name |
| `started_at` / clock reading | monotonic number | The interface clock (`performance.now()` / `time.monotonic`) | Used only for display and expiry |
| `expires_at` | monotonic number | `started_at + 600` seconds | The record expires at or after this value |

**Creation rule**: Only after the undo outcome is `undone`. The record is not
created from the receipt before the request, because a refused undo must leave
the skipped list unchanged.

**Storage rule**: TUI stores the record in `ChooserApp._skips`; web stores it in
`useSkip.records`. It is never written to the history log, path memory,
cookies, browser storage, or any file. It is discarded when the TUI exits or
the web page unloads/reloads.

**Display rule**: The existing 008 rules apply unchanged. The record is shown
only while active and present in the state response's `skipped` list; a record
whose item is currently logged is retained internally but hidden from the
skipped display and counted as picked.

## Entity: Snooze Outcome (interface-level)

The result of one activation. It is not persisted and is not sent over HTTP.

| Value | Meaning | Receipt after | History | Skip after | Message |
|-------|---------|---------------|---------|------------|---------|
| `snoozed` | The undo succeeded and one skip was recorded | Cleared | Exactly one line removed | One record added | `Snoozed <item>. Its pick was removed; it returns in ten minutes or when this session ends.` |
| `unavailable` | No receipt exists, or the current choice no longer matches the receipt | Unchanged (absent or retained) | Unchanged | Unchanged | `Nothing to snooze.` |
| `conflict` | Another action is running | Retained | Unchanged | Unchanged | `Wait for the current action to finish.` |
| `item_missing` | The exact item is no longer a direct child of the target | Retained | Unchanged | Unchanged | `Could not snooze <item>: it is no longer available.` |
| `history_changed` | The undo endpoint returned `changed`, the captured receipt was replaced before the undo call, or `performUndo` returned `unavailable` after the Snooze guard | Captured receipt cleared; a newer receipt is untouched | Unchanged | Unchanged | `Could not snooze <item>: history changed.` |
| `history_empty` | The undo endpoint returned `nothing_to_undo` | Cleared | Unchanged | Unchanged | `Could not snooze <item>: history is empty.` |
| `scope_changed` (before undo) | The web path or log-file value changed before the preflight completed | Already cleared by the scope reset | Unchanged | Unchanged | `Could not snooze <item>: the folder or log file changed.` |
| `scope_changed` (during undo) | The web scope changed while the undo request was in flight | Cleared by the undo outcome | The old scope's line was removed | No skip is added to the new scope | `Removed the pick of <item>. The folder or log file changed before it could be skipped.` |
| `failed` | The browse check or undo request raised a transport/I/O error | Retained | Unchanged | Unchanged | The interface's existing error message |

**Domain-refusal rule**: `history_changed` and `history_empty` consume the
receipt exactly as Undo does, because the proof no longer matches the log.
`item_missing`, `conflict`, and `failed` keep the receipt because the undo call
did not produce a domain answer about the latest line.

## Entity: Board and Preview State (existing)

| State | Snooze success rule |
|-------|---------------------|
| Current choice is the snoozed item | Clear the item, preview, and Open control; Undo stays visible but disabled |
| Current choice is a different item | Leave it untouched; no replacement is picked |
| History count | Decreases by one through the existing state refresh |
| Remaining count | Stays at the post-pick count: the item does not return to the remaining view, so it is one lower than before the pick and does not increase as it would after a plain Undo |
| Skipped count | Increases by one because the state response reports the new skip |
| Picked count | Decreases by one because the history line is removed |
| All-skipped outcome | Recomputed by the existing state/pick rules; no automatic pick |

## State Transitions

| Event | Receipt | Skipped list | History | Board / preview | Snooze availability |
|-------|---------|--------------|---------|-----------------|---------------------|
| Fresh session | Absent | Empty | Unchanged | Empty | Unavailable |
| Successful logged pick | Set to the new line | Unchanged | One line appended | Shows the picked item | Available for that item |
| Dry run, empty, failed, or refused pick | Absent | Unchanged | Unchanged | Existing behavior | Unavailable |
| Snooze succeeds | Cleared | One record added for the item | Exactly one line removed | Clears only if it still shows the item | Unavailable until the next logged pick |
| Snooze finds the item missing | Retained | Unchanged | Unchanged | Unchanged | Still shown as available; retry refuses again |
| Snooze sees changed history | Cleared | Unchanged | Unchanged | Clears only if it still shows the item | Unavailable |
| Snooze sees an empty history | Cleared | Unchanged | Unchanged | Clears only if it still shows the item | Unavailable |
| Snooze transport/I/O failure | Retained | Unchanged | Unchanged | Unchanged | Still available for retry |
| Undo succeeds | Cleared | Unchanged | Exactly one line removed | Clears only if it still shows the item | Unavailable |
| Later successful logged pick | Replaced with the new line | Older snooze remains | One line appended | Shows the new item | Available for the new item |
| Restore the snoozed item | Unchanged (absent) | Record removed | Unchanged; removed line stays removed | Unchanged | Unavailable for the old item |
| Restore all | Unchanged (absent) | Empty | Unchanged | Unchanged | Unavailable |
| Cooldown expires | Unchanged (absent) | Record removed | Unchanged | Unchanged | Unavailable |
| Target or log-file change | Cleared | Empty | Unchanged | Existing reset behavior | Unavailable |
| Target or log-file change during the preflight | Cleared by the reset | Empty | Unchanged | Existing reset behavior | Unavailable |
| Target or log-file change during the undo request | Cleared by the undo outcome | Empty for the new scope | The old scope's line was removed | Existing reset behavior | Unavailable |
| Log archived or cleared | Cleared | Unchanged | Existing behavior | Existing behavior | Unavailable |
| Another session picks the snoozed item | Unchanged | Record retained but hidden and counted as picked | New line from the other session | Unchanged | Unavailable here |
| That other session's line is removed | Unchanged | Record becomes displayable again | One line removed | Unchanged | Unavailable here |

## Validation and Invariants

1. A successful Snooze removes exactly one history line: the line proven by the
   captured receipt. It never removes an older or unrelated line.
2. No skip record is created unless the undo outcome is `undone`. No history
   line is removed when the preflight or undo refuses.
3. Snooze adds no persistent state, history marker, schema field, route, or CLI
   option.
4. At most one skip record exists per exact item name in a session. A snooze of
   an already-skipped name (possible only if the name was restored, re-picked,
   and re-snoozed) replaces the record and restarts the cooldown rather than
   duplicating it.
5. A successful Snooze always clears the receipt; Undo remains visible and
   disabled until the next successful logged pick.
6. Restore, restore-all, cooldown expiry, target change, log change, and session
   end never restore the removed history line and never re-enable Undo.
7. The item is counted as skipped, not remaining and not picked, while the skip
   is active and the item is not otherwise logged.
8. Existing skip precedence, all-skipped classification, countdown display,
   and session-only lifetime are unchanged.
9. The current choice and preview are cleared on success only when they still
   show the snoozed item; no replacement item is selected.
10. The existence preflight compares the exact direct-child name; it does not
    require the item to pass the current type or entry filters.
11. A deletion that races with the undo after the preflight is outside the
    atomic boundary; the undo remains safe for history and the next state
    response reconciles the stale skip away.
12. Count semantics: relative to the state before the pick, the remaining count
    is one lower; relative to the state immediately after the pick, it is
    unchanged and the item moves from picked to skipped. The picked count drops
    by one and the skipped count rises by one.
