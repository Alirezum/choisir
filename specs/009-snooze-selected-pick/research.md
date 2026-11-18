# Phase 0 Research: Snooze the Selected Pick

**Feature**: `009-snooze-selected-pick` | **Date**: 2026-11-18

No unresolved clarification markers remain in the plan. The spec, the shipped
Undo feature (007), and the shipped skip feature (008) already define every
externally visible rule. This document records the technical decisions needed
to compose them.

## Decision 1: Compose the existing Undo and skip behavior

**Decision**: Implement Snooze as two existing operations in order — remove the
exact history line through the current single-level undo receipt, then add the
same item name to the interface's existing session skip map with
`SKIP_COOLDOWN_SECONDS`. Do not add a shared `snooze` service, history marker,
or new persisted concept.

**Rationale**: Undo already owns the only safe way to remove the latest history
line (receipt plus whole-file digest and lock), and skip already owns the
cooldown, restore, restore-all, all-skipped, target-reset, and session-end
rules. Reusing both keeps one implementation of each rule and makes the
combined action trivially consistent across interfaces.

**Alternatives considered**:

- A shared `SnoozeService` that calls `HistoryService.undo` then returns a skip
  record — rejected because the skip record is interface-owned session state;
  the core has no session and no storage for it. It would also create a new
  service contract for a two-call composition.
- A new HTTP route or a new `snooze` command — rejected by FR-016, FR-017, and
  the user's constraint to keep the route inventory and CLI unchanged.
- Writing a "snoozed" marker to history — rejected because it would change the
  history format and make a deferral look like a pick.

## Decision 2: Eligibility follows the Undo receipt plus the current choice

**Decision**: Snooze is available exactly when:

1. `useUndo.receipt` (web) or `ChooserApp._undo_receipt` (TUI) is non-null;
2. the current choice still names the receipt's item;
3. no conflicting action is in progress; and
4. the target and log-file scope still match the receipt.

The web predicate also excludes a running undo, snooze, or skip action. The TUI
button is disabled when the receipt is absent or the current choice does not
match it; the action repeats the check before doing anything.

**Rationale**: The spec ties Snooze to the latest successful logged pick and
the existing Undo opportunity (FR-001, FR-008, FR-019). The receipt is already
invalidated by every event that ends that opportunity: a dry run, an empty or
failed pick, a completed undo, a target or log-file change, and log
archive/clear. Matching the current choice prevents offering Snooze for an
older or unrelated item.

**Alternatives considered**:

- Deriving eligibility from the last history line on every render — rejected
  because it would lose the external-change proof and could offer Snooze for a
  line this session did not write.
- Allowing Snooze whenever any history exists — rejected by FR-019 and the
  single-level undo scope.
- Enabling Snooze without the current-choice match — rejected because the
  user's request is specifically for the currently selected item.

## Decision 3: Keep Undo visible and consume the same opportunity

**Decision**: Add Snooze as a separate control. Never remove, rename, or
repurpose Undo. On any domain answer from the undo call, clear the receipt
exactly as Undo does, so Undo remains visible and disabled until the next
successful logged pick. On a transport or I/O failure, keep the receipt so the
person may retry.

**Rationale**: FR-007 and SC-005 require Undo to remain visible after Snooze.
The existing `useUndo` contract already clears the receipt on every domain
outcome and preserves it on transport failure; reusing that rule gives the
same trust behavior for both controls. The spec explicitly says a successful
Snooze consumes the single-level opportunity and restoring the item does not
bring the line back (FR-012).

**Alternatives considered**:

- Keeping the receipt after a successful Snooze so Undo can reverse it —
  rejected because the history line is already gone and re-enabling Undo would
  imply it can be re-removed or restored.
- Hiding Undo when Snooze is available — rejected by FR-007 and the user's
  explicit requirement that Undo remain.
- Clearing the receipt on transport failure — rejected because the existing
  Undo behavior intentionally allows a retry and the history may be unchanged.

## Decision 4: Check that the item still exists before removing history

**Decision**: Before calling undo, verify that the exact item name still exists
as a direct child of the active target folder. The terminal UI scans the
target's direct children with `os.scandir` and compares the exact name. The web
UI calls the existing browse listing for the active path and compares exact
names. If the check fails, refuse with the item-unavailable message, remove no
history line, and add no skip. If the check itself fails because the folder is
unreadable, refuse and report the existing transport/error message.

**Rationale**: FR-010 and acceptance scenario 3.1 require a deletion or rename
before Snooze to refuse completely. The client cannot ask the shared undo
endpoint about target existence because the undo contract is history-only, and
the web client has no filesystem access. The browse capability is already
available to both interfaces and is local-only. Scanning the direct children
also matches the shared state scan's existence rule (exact name, direct child,
hidden entries included).

**Race boundary**: The check runs before the undo request. The undo endpoint's
lock and full-file digest remain the authoritative safety boundary for
history; if the item is deleted after the check but before the undo response,
the history removal still succeeds and the next state response reconciles the
skip away because the name is absent from `skipped_present`. Fully eliminating
that race would require a new atomic combined endpoint, which is explicitly out
of scope. The tested and specified behavior covers a deletion observed before
the action proceeds.

**Alternatives considered**:

- Checking after undo — rejected because the history line would already be gone
  and could not be restored safely.
- Adding an existence flag to the undo request — rejected because it changes
  the public HTTP contract and mixes target inspection into a history write.
- Relying on the skipped-list reconciliation alone — rejected because it would
  remove history for a missing item before the skip was pruned.

## Decision 5: Refactor `useUndo` into a reusable attempt plus the existing action

**Decision**: Extract `performUndo(): Promise<UndoOutcome>` from the existing
`undo()`. `performUndo` captures the receipt, guards concurrent attempts, calls
`api.undoHistory`, applies the existing domain transitions when the captured
receipt is still current (clear it and invalidate the matching choice), and
returns a typed outcome. It does not set status text and does not refresh.
`undo()` becomes a thin wrapper that sets the existing Undo messages and
refreshes, preserving today's user-visible behavior. `useSnooze` calls
`performUndo` directly so it can add the skip only after an `undone` outcome
and set Snooze-specific messages.

**Rationale**: The current `undo()` owns both the API call and Undo-specific
presentation. Calling it from Snooze would show `Undid pick of ...` before the
snooze message, and inspecting status text to infer the outcome would be
brittle. A typed outcome keeps the undo rule single-sourced. Identity-guarding
the clear prevents an in-flight action from consuming a newer pick's receipt;
normal single-action behavior is unchanged.

**Alternatives considered**:

- Duplicating the undo API call in `useSnooze` — rejected because it forks the
  receipt-clearing and choice-invalidation rules.
- Letting `useSnooze` call `undo()` and then always add a skip — rejected
  because a `changed`, `nothing_to_undo`, or failed undo must not create a skip.
- Adding a `silent` flag to `undo()` — rejected as a presentation flag leaking
  into the domain path; the typed return is clearer.

## Decision 6: Add a programmatic skip-record method

**Decision**: Add `add(name: string): void` to `useSkip`. It prunes expired
records, removes any existing record with the same name, and inserts one record
with `expiresAt = now + SKIP_COOLDOWN_MS`. It does not set status text, start a
refresh, or toggle the `skipping` flag by itself. `useSnooze` sets its own
`snoozing` guard, calls `add` only after a successful undo, then performs one
refresh with its own status message.

**Rationale**: Snooze is not "Not now": the item is no longer in the remaining
list, so the existing `skip(name)` method's `isRemaining` check would reject
it. A small record insertion reuses the cooldown and uniqueness rules without
duplicating them. One refresh after both halves avoids showing the item as
remaining between the undo and the skip.

**Alternatives considered**:

- Calling `skip(name)` — rejected because the item is logged at that moment and
  is not in `remaining`.
- Adding a special-case flag to `skip()` — rejected as a second behavior path
  inside the normal skip action.
- Adding a skip before undo and rolling it back on failure — rejected because
  rollback of session state is more complex and could briefly hide an item that
  should remain picked.

## Decision 7: Refusal semantics

**Decision**: Distinguish five refusal classes:

| Class | Examples | Receipt | History | Skip |
|-------|----------|---------|---------|------|
| Unavailable | No receipt, current choice no longer matches, dry run, failed/empty pick, completed undo, target/log change | Unchanged | Unchanged | Unchanged |
| Conflict while starting | Undo, Snooze, or skip already running | Retained | Unchanged | Unchanged |
| Domain refusal | Undo returns `changed` or `nothing_to_undo` | Cleared, matching Undo | Unchanged | Unchanged |
| Item missing | Preflight finds no exact direct child | Retained; the undo never ran | Unchanged | Unchanged |
| Transport/I/O failure | Undo request fails | Retained for retry | Unchanged | Unchanged |

**Clarification**: The missing-item refusal leaves the receipt intact for the
same reason a transport failure does: the undo call never ran, and history is
unchanged. The next pick, target/log change, or successful Undo clears it. The
button remains available until the receipt is consumed, but every retry
refuses at the same preflight until the item returns or the scope changes.
This matches the spec's requirement that a refused Snooze changes neither
history nor skips.

**Rationale**: The spec requires a failed Snooze to leave both stores
unchanged. Clearing the receipt on a preflight refusal would be an extra state
change and would make a temporary rename/symlink issue permanently consume the
opportunity. A domain refusal that proves history changed is different: the
receipt is already invalid, and keeping it would offer a control that can never
succeed, so it follows the shipped Undo behavior.

**Alternatives considered**:

- Clearing the receipt on every refusal — rejected because a missing item or a
  transient browse failure is not proof that history changed.
- Keeping the receipt after a `changed` undo response — rejected because the
  proof is gone and the shipped Undo behavior clears it.
- Offering a retry after `changed` — rejected because the original line can no
  longer be identified safely.

## Decision 8: Messages and cross-interface parity

**Decision**: Use the same item-bearing messages in both interfaces:

- Success: `Snoozed <item>. Its pick was removed; it returns in ten minutes or when this session ends.`
- No receipt: `Nothing to snooze.`
- Missing item: `Could not snooze <item>: it is no longer available.`
- History changed: `Could not snooze <item>: history changed.`
- History empty: `Could not snooze <item>: history is empty.`
- Folder or log file changed before undo: `Could not snooze <item>: the folder or log file changed.`
- Folder or log file changed during undo:
  `Removed the pick of <item>. The folder or log file changed before it could be skipped.`
- Transport/I/O failure: the existing interface error message.

The web status region and the TUI status line both announce the message; the
web Snooze button's accessible name is `Snooze last pick: <item>` while a
receipt exists (even if an in-flight action temporarily disabled the control)
and `Snooze last pick (nothing to snooze)` otherwise. The TUI label is
`Snooze: <item>` while a receipt exists and `Snooze` when there is none, with a
tooltip that names the item or says `Nothing to snooze`.

**Rationale**: FR-013 and FR-015 require item-bearing, accessible feedback and
consistent outcomes. Reusing the skip success sentence preserves the existing
return-condition vocabulary.

**Scope guard**: The web action captures the active path and log-file value at
activation. If either changes before the preflight completes, the action
refuses with `Could not snooze <item>: the folder or log file changed.` and
changes nothing. If the scope changes while the undo request is in flight, the
history removal already performed for the previous scope stands, but no skip is
added to the new scope; the status says
`Removed the pick of <item>. The folder or log file changed before it could be skipped.`
The TUI serializes the action and cannot hit this interleaving. This prevents a
stale skip from leaking into a newly selected folder.

**Alternatives considered**:

- Separate web/TUI wording — rejected by the parity requirement.
- Reusing `Undid pick of ...` — rejected because it would not say the item was
  deferred.
- Announcing only the item name — rejected because the return condition is part
  of the skip contract.

## Decision 9: No replacement pick and selective board clearing

**Decision**: On success, clear the board/preview only when the displayed item
is still the snoozed item; never pick a replacement. Leave the counts driven by
the existing state refresh: the history/picked count drops by one and the
skipped count rises by one. The remaining count stays at the post-pick value
(the item never returns to the remaining view), which is one lower than before
the pick and does not increase as it would after a plain Undo. After a
successful action, move focus to the Pick control in the TUI so keyboard users
are not stranded on a disabled Snooze button. The web board's Snooze and Undo
buttons become disabled through their existing computed availability.

**Rationale**: FR-005 and the skip contract say no replacement is picked and
the board clears only when it still shows the affected item. The state refresh
already excludes the item as skipped, so it never returns to the remaining
view; the remaining count therefore keeps its post-pick value instead of rising
as it would after a plain Undo.

**Alternatives considered**:

- Picking the next item automatically — rejected by FR-005.
- Clearing the board unconditionally — rejected because a newer preview must
  not be erased by a stale action.

## Decision 10: No API, CLI, or persistent-state change

**Decision**: Keep the route inventory at 17, the `POST /api/undoHistory`
request/response shape unchanged, and the CLI unchanged. The web uses the
existing undo and browse routes plus its existing session skip state. The TUI
uses `HistoryService` and its existing `_skips` map. No skip or snooze is
written to the log, path memory, cookies, or browser storage.

**Rationale**: FR-016, FR-017, and the user's explicit constraint. The feature
is a composition, so the public contract does not need to grow.

**Alternatives considered**:

- A new `POST /api/snooze` — rejected as unnecessary public surface.
- Persisting skips so a reload retains them — rejected by FR-011 and the
  shipped session-only skip rule.
- Adding a CLI `--snooze` flag — rejected by FR-016.

## Decision 11: Validation strategy

**Decision**: Add focused automated coverage at the seams that can regress:

- TUI: Snooze starts disabled; becomes available after a logged pick; success
  removes exactly the latest line, adds one skip, clears the board, and leaves
  Undo visible but disabled; a second pick re-enables both; dry run, completed
  undo, target/log change, deleted item, and externally changed history refuse
  without a skip or extra history change; restore keeps the line removed; the
  control has an item-bearing accessible label.
- Web units: `useUndo.performUndo` outcomes and unchanged `undo()` messages;
  `useSkip.add` cooldown/uniqueness; `useSnooze` success, missing item, no
  receipt, changed history, transport failure, conflict guards, scope changes,
  and the exact messages; `useWorkspace` exposes the new binding; `ChoiceBoard`
  renders the Snooze control, disabled state, accessible name, and emits
  `snooze`.
- Cross-interface checks: paired assertions that the same starting state gives
  the same history/skip/message outcome; the existing skip and undo suites must
  remain green; the CLI suite and API contract check must remain unchanged.

**Rationale**: The feature has no new backend behavior, so the highest-risk
regressions are in the composition and the UI state. Testing at those seams
proves the spec without waiting for cooldowns or adding a browser harness.

**Alternatives considered**:

- Only manual checks — rejected by the constitution's test requirement.
- A new end-to-end browser runner — rejected as a new tool/dependency for a
  small local UI.
- Testing through a new API route — rejected because there is no new route.

## Summary of Resolved Unknowns

| Topic | Resolution |
|-------|------------|
| Where the combined behavior lives | Interface composition over existing undo + skip |
| Which item can be snoozed | The current choice tied to the latest undo receipt |
| How existence is checked | TUI direct child scan; web existing browse listing |
| What happens to Undo | Stays visible; disabled after success until the next logged pick |
| What happens on failure | No history change, no skip; receipt retention depends on the failure class |
| API/CLI impact | None; route inventory stays 17; CLI frozen |
| Persistence | None; skip is session-only, history removal is the existing undo write |
