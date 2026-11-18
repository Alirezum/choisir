# Interface Contract: Snooze the Selected Pick

**Feature**: `009-snooze-selected-pick` | **Date**: 2026-11-18

This document defines the interactive contract for Snooze. It adds no HTTP or
CLI contract. The authoritative machine-readable API contract remains
[`specs/001-standardize-api-responses/contracts/api-contract.json`](../../001-standardize-api-responses/contracts/api-contract.json);
the shipped Undo contract is in
[`specs/007-undo-last-pick/contracts/`](../../007-undo-last-pick/contracts/),
and the shipped skip contract is in
[`specs/008-skip-snooze/contracts/skip-snooze.md`](../../008-skip-snooze/contracts/skip-snooze.md).

## Compatibility

- Existing routes, request fields, response fields, statuses, and error codes
  keep their types and meanings. The route inventory remains **17**.
- `POST /api/undoHistory` is reused unchanged: same request, same response,
  same `undone` / `nothing_to_undo` / `changed` statuses.
- The existing browse listing is reused unchanged for the web existence check.
- No new persisted state, history field, skip field, dependency, or CLI option
  is added.
- The history format remains JSON Lines. A Snooze removes one existing line; it
  writes no marker.
- The one-shot CLI flags, prompt behavior, output, and exit codes are unchanged.
- The existing skip cooldown, restore, restore-all, all-skipped, target-change,
  log-change, and session-end rules are unchanged.

## Control Contract

Snooze is a separate control beside Undo in both interactive interfaces. Undo
is never removed, hidden, renamed, or repurposed.

| Property | Terminal UI | Web UI |
|----------|-------------|--------|
| Control | `Button` with id `#snooze` | `button.board-snooze` |
| Placement | Actions row, immediately after `#undo` | Board meta row, immediately after `.board-undo` |
| Visible text | `Snooze: <item>` when a receipt exists; `Snooze` otherwise | `Snooze` always |
| Accessible name | The button label names the item; the tooltip adds the action | `Snooze last pick: <item>` when a receipt exists (even if temporarily disabled); `Snooze last pick (nothing to snooze)` otherwise |
| Tooltip | `Snooze <item> and undo its pick` when a receipt exists; `Nothing to snooze` otherwise | Native `title` is optional; the accessible name carries the meaning |
| Disabled state | Disabled when the predicate below is false | `disabled` when `canSnooze` is false |
| Activation | `Button.Pressed` for `#snooze` calls `_snooze_pick()` | `@click` emits `snooze` when `canSnooze` |
| Keyboard | Native focus, Enter/Space | Native focus, Enter/Space |

### Availability predicate

Snooze is available exactly when all of the following hold:

1. The latest-pick receipt exists.
2. The current choice still names `receipt.item`.
3. No Undo, Snooze, or skip action is in flight (web; the TUI event loop
   serializes actions).
4. The target and log-file scope is still the scope that produced the receipt
   (the existing reset rules clear the receipt on a scope change).

Item existence is checked when the control is activated, not by the synchronous
predicate. A missing item therefore leaves the control available for a retry
that refuses with the item-unavailable message, while history and skips remain
unchanged.

### Web binding additions

`WorkspaceBinding` gains:

```ts
canSnooze: ComputedRef<boolean>
snoozing: Ref<boolean>
snoozeLabel: ComputedRef<string>
snooze: () => Promise<void>
```

`ChoiceBoard.vue` gains the props `canSnooze: boolean` and
`snoozeLabel: string`, and the emit `snooze: []`. The Snooze event is wired in
`App.vue` to the workspace `snooze` action.

`useUndo` gains `performUndo(): Promise<UndoOutcome>` while keeping the public
`undo()` action, receipt, availability, and messages unchanged. `useSkip` gains
`add(name: string): void`, which inserts one session record with the existing
cooldown and no status text or refresh. `useSnooze` owns the composition and
the Snooze messages.

```ts
type UndoOutcome =
  | { kind: 'unavailable' }
  | { kind: 'failed'; error: unknown }
  | { kind: 'undone' | 'changed' | 'nothing_to_undo'; item: string }
```

`performUndo` applies the existing domain transitions when the captured receipt
is still current: clear it and invalidate the matching choice. It sets no
status text and performs no refresh. It returns `failed` on a transport or I/O
error and keeps the receipt available for retry. If an intervening pick
replaced the receipt, the newer receipt and its choice are left intact.

That identity guard is invisible in normal single-action use: Undo still
consumes the receipt it was invoked for, reports the same messages, and clears
the same matching choice. It only prevents an older in-flight attempt from
clearing a newer receipt or a different displayed choice; it does not change
Undo's visible behavior, availability, or message set.

## Activation Sequence

1. **Guard**: If the action is unavailable, set `Nothing to snooze.` and change
   nothing. If another action is in flight, set
   `Wait for the current action to finish.` and change nothing.
2. **Capture**: Read the receipt and item once, and capture the active path and
   log-file value. Do not re-read a newer receipt later in the same attempt.
3. **Existence preflight**: Verify the exact item name is still a direct child
   of the active target.
   - TUI: scan the target with `os.scandir` and compare `entry.name` exactly.
   - Web: call the existing browse listing for the active path and compare
     `entries[].name` exactly.
   - On a missing item: set
     `Could not snooze <item>: it is no longer available.`, keep the receipt,
     remove no history line, and add no skip.
   - If the web path or log-file value changed while the preflight was running:
     set `Could not snooze <item>: the folder or log file changed.`, remove no
     history line, and add no skip.
   - If the captured receipt is no longer the current receipt (a newer pick or
     another action replaced it): set
     `Could not snooze <item>: history changed.`, remove no history line, and
     add no skip.
4. **Undo**: Call the existing undo behavior with the captured receipt.
   - `undone`: proceed to step 5.
   - `changed`: set `Could not snooze <item>: history changed.`, clear the
     receipt exactly as Undo does, remove no additional history line, and add
     no skip.
   - `nothing_to_undo`: set
     `Could not snooze <item>: history is empty.`, clear the receipt exactly as
     Undo does, and add no skip.
   - `unavailable`: treat the captured receipt as no longer current; set
     `Could not snooze <item>: history changed.`, remove no additional history
     line, and add no skip.
   - Transport or I/O error: report the existing interface error, keep the
     receipt for retry, and add no skip.
5. **Scope re-check**: If the web path or log-file value changed while the undo
   request was in flight, do not add a skip to the new scope. The old scope's
   history removal stands; set
   `Removed the pick of <item>. The folder or log file changed before it could be skipped.`
   and refresh the new scope. The TUI serializes the action and skips this
   branch.
6. **Defer**: Add one session skip record for the outcome item with the existing
   ten-minute cooldown, set
   `Snoozed <item>. Its pick was removed; it returns in ten minutes or when this session ends.`,
   clear the receipt, clear the board/preview only if they still show the item,
   and refresh the state once.

The state refresh must happen after the skip record is added so the item is
already excluded from remaining and counted as skipped when the response is
rendered. No replacement item is picked.

## Outcome Contract

| Outcome | Receipt | History | Skipped list | Feedback |
|---------|---------|---------|--------------|----------|
| Snoozed | Cleared | Exactly one line removed | One record added | `Snoozed <item>. Its pick was removed; it returns in ten minutes or when this session ends.` |
| Unavailable | Unchanged | Unchanged | Unchanged | `Nothing to snooze.` |
| Competing action | Unchanged | Unchanged | Unchanged | `Wait for the current action to finish.` |
| Item missing | Retained | Unchanged | Unchanged | `Could not snooze <item>: it is no longer available.` |
| History changed | Cleared | Unchanged | Unchanged | `Could not snooze <item>: history changed.` |
| History empty | Cleared | Unchanged | Unchanged | `Could not snooze <item>: history is empty.` |
| Folder or log file changed before undo | Cleared by the scope reset | Unchanged | Unchanged | `Could not snooze <item>: the folder or log file changed.` |
| Folder or log file changed during undo | Cleared by the undo outcome | The old scope's line was removed | No skip in the new scope | `Removed the pick of <item>. The folder or log file changed before it could be skipped.` |
| Transport/I/O failure | Retained | Unchanged | Unchanged | Existing error message |

Every full refusal leaves history and the skipped list unchanged. A `changed`
or `nothing_to_undo` response consumes the undo opportunity because the receipt
no longer proves the latest line; a missing item, folder or log-file change
before the undo, or transport failure does not. A folder or log-file change
during the undo is the one partial case: the old scope's history removal
already happened and cannot be reversed, so the implementation must not leak
its skip into the new scope.

## Board, Preview, and Counts

- On success, clear the board and preview only when the displayed item is the
  snoozed item. Never clear a newer choice.
- A `changed` or `nothing_to_undo` domain refusal consumes the receipt and uses
  the shipped Undo board-clearing behavior for the matching item. A missing
  item, folder or log-file change, or transport failure leaves the board and
  preview untouched.
- Do not pick a replacement. The Pick control remains the person's next action.
- The existing state refresh drives the history/picked count down by one and
  the skipped count up by one. The remaining count does not increase: the item
  stays out of the remaining view, so it is one lower than before the pick and
  does not return as it would after a plain Undo.
- The existing all-skipped outcome is recomputed by the shared state and pick
  functions. If the snoozed item was the last available entry, the interface
  shows the existing all-skipped or neutral no-items state and offers restore.
- Undo stays visible. After a successful Snooze it is disabled until the next
  successful logged pick, then it names and reverses that new pick normally.

## Restore, Expiry, and Session Rules

These are unchanged from feature 008 and apply identically to a snoozed item:

- Per-item restore and restore-all remove the session record immediately.
- Cooldown expiry removes the record at or after ten minutes and the item
  returns to remaining if it still exists, is not logged, and matches the
  current options.
- Restoring or expiring a snoozed item never restores its removed history line
  and never re-enables Undo for it.
- A target or log-file change clears the receipt and every skip record for the
  previous scope.
- A page reload or application restart clears the receipt and skips; the
  history removal persists.
- If another session logs the snoozed item, the existing skipped-entry rule
  hides it from the skipped display and counts it as picked until that line is
  removed.

## Accessibility

- Both controls are native buttons with visible focus.
- The accessible name identifies the affected item whenever a receipt exists
  and explains that nothing is available otherwise.
- Success and refusal messages are written to the existing status line/status
  region. The web status region must remain the existing accessible live
  region; no new announcement mechanism is added.
- The control is reachable and operable with the keyboard alone in both
  interfaces.
- After a successful TUI Snooze, focus moves to the Pick button so a keyboard
  user is not left on a disabled control.

## Explicit Non-Changes

- No older history entry, history selection, or non-current item can be
  snoozed.
- No new route, API field, status value, error code, CLI flag, command,
  history marker, persistent store, or dependency.
- No change to pure skip (**Not now**), Undo's own behavior, filters, seed,
  dry-run mode, target content, active folder, log-file setting, path memory, or
  the one-shot CLI.
