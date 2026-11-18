# Feature Specification: Snooze the Selected Pick

**Feature Branch**: `009-snooze-selected-pick`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "i want also can snooze the video that selected like undo a botton in there and when i snooze it its also undo it for example snooze do snooze and undo but also undo remain"

## Clarifications

### Session 2026-11-18

- Q: When Snooze succeeds, what should the remaining count show relative to the state immediately after the pick? → A: It stays at the post-pick value; the item moves from picked to skipped.
- Q: After Snooze refuses before the undo request because the picked item is missing or the folder cannot be read, should the Snooze opportunity remain available for a retry? → A: Keep it for those pre-undo refusals; consume it after a history-changed or empty-history refusal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Snooze the latest pick and defer it (Priority: P1)

A person has just picked an item and can see it on the board or in the preview. They decide it is not right for now. Next to Undo, they activate **Snooze**. The pick is removed from history exactly as Undo would remove it, and the same item immediately joins the existing skipped list for the usual cooldown or until the session ends. No replacement is picked automatically. After the cooldown, or after a restore, the item is available again as an unpicked entry.

**Why this priority**: Today the person must undo the pick, find the item again in the remaining pool, and skip it in a second action. Snooze makes that one reversal-and-deferral action without leaving a false pick in history.

**Independent Test**: In a folder with known entries, pick one item, activate Snooze, and verify that exactly that history line disappears, the item appears as skipped, it cannot be picked during the cooldown, Undo is no longer available, and restoring or waiting makes it eligible again without any further history change.

**Acceptance Scenarios**:

1. **Given** the current choice is the latest successful logged pick, **When** the person activates Snooze, **Then** exactly that pick's history line is removed, the item is skipped, the remaining count stays at its post-pick value (one lower than before the pick), and the status names the item and when it will return.
2. **Given** the latest pick is a file, folder, image, video, or any other entry kind, **When** the person activates Snooze, **Then** the action works the same way for that item.
3. **Given** a successful Snooze, **When** the action completes, **Then** no replacement item is picked, and the board and preview clear only when they still show the snoozed item.
4. **Given** a snoozed latest pick, **When** the ten-minute cooldown ends while the interface is open, **Then** the item leaves the skipped list and appears in the remaining list as an unpicked entry.
5. **Given** a snoozed latest pick, **When** the person restores it before the cooldown ends, **Then** it becomes eligible immediately, remains absent from history, and leaves the skipped list.
6. **Given** a snoozed latest pick, **When** the session ends before the cooldown, **Then** the next session shows the item as an unpicked and eligible entry, while the earlier pick remains removed from history.

---

### User Story 2 - Keep Undo separate and trustworthy (Priority: P2)

Undo remains its own visible control. Snooze does not replace it. Because Snooze removes the latest pick, it consumes the same single-level undo opportunity; Undo then stays visible but unavailable until the next successful logged pick. Whenever Undo cannot be used, Snooze cannot be used either, and a refused Snooze changes neither history nor the skipped list.

**Why this priority**: Reversing a logged pick is a trust-sensitive action. The person must be able to understand which control removed the line, why Undo is no longer available, and that a failed Snooze did not partially change anything.

**Independent Test**: Pick an item and confirm both Undo and Snooze are available. Snooze it and verify Undo remains visible but disabled. Pick again and verify both become available for the new pick. Then exercise dry-run, failed, and externally changed-history states and verify Snooze refuses without partial changes.

**Acceptance Scenarios**:

1. **Given** a latest successful pick that can be undone, **When** the person views the choice actions, **Then** both Undo and Snooze are present and usable.
2. **Given** the person activates Snooze successfully, **When** the action completes, **Then** the Undo control is still present but unavailable until the next successful logged pick.
3. **Given** a snoozed pick and a later successful logged pick, **When** that new pick exists, **Then** Undo and Snooze are available for the new pick and not for the older snoozed one.
4. **Given** a dry run, a failed or empty pick, a completed Undo, a target or log-file change, or a stale history state, **When** the person looks at the choice actions, **Then** Snooze is unavailable or refuses and changes nothing.
5. **Given** the person restores a snoozed item, **When** it returns to the remaining pool, **Then** its removed history line is not restored and Undo does not become available for it.
6. **Given** a Snooze attempt that cannot remove the pick, **When** it fails, **Then** the item is not added to the skipped list, history is unchanged, and the interface explains why.

---

### User Story 3 - Trust Snooze across interfaces and conflicts (Priority: P3)

The terminal UI and the web UI offer the same Snooze behavior and the same outcomes. Snooze never removes a different history line, never creates a duplicate skip, never changes target content, filters, the active folder, the log-file setting, seed, dry-run mode, path memory, or the command-line interface. Concurrent or stale actions are refused clearly rather than applying half of the change.

**Why this priority**: The combined action touches the history record, which is the product's source of truth. It must remain consistent even when another session or an external edit changes the same log.

**Independent Test**: Record history and target hashes, then snooze in both interfaces and repeat with deleted items, external log edits, two sessions, quick repeated actions, reloads, and keyboard-only operation. Verify exactly one history line disappears per success, no other state changes, and every refusal leaves history and skips untouched.

**Acceptance Scenarios**:

1. **Given** the latest picked item is deleted or renamed before Snooze, **When** the person activates Snooze, **Then** the action refuses completely, history is unchanged, and no skip is created.
2. **Given** the history log changed externally after the pick, **When** the person activates Snooze, **Then** no line is removed, no skip is created, and the feedback says history changed.
3. **Given** two sessions or tabs hold the same latest pick, **When** both attempt Snooze or Undo, **Then** only one reversal succeeds, the other is refused, and history remains consistent.
4. **Given** a person using only the keyboard, **When** they reach and activate Snooze and the related restore controls, **Then** every control has visible focus and an accessible name that identifies the item.
5. **Given** a successful or refused Snooze, **When** feedback appears, **Then** it names the affected item and is announced in an accessible status region.
6. **Given** the one-shot command-line interface, **When** it runs, **Then** its flags, prompt behavior, output, and exit codes are unchanged and no snooze option is added.
7. **Given** a web reload or application restart, **When** the new session starts, **Then** the removed history line stays removed, while the skip and undo opportunity are gone and the item is eligible again.

---

### Edge Cases

- No successful logged pick exists, or the latest pick was a dry run: Snooze is unavailable and no history or skip change occurs.
- The latest pick was already undone, or its log was archived, cleared, or rotated: the undo opportunity is gone, so Snooze refuses and changes nothing.
- The history log changes externally after the pick: Snooze refuses, removes no line, and creates no skip.
- The picked item is deleted or renamed before Snooze: Snooze refuses completely rather than removing history for an item that can no longer be deferred.
- A missing-item or unreadable-folder refusal before the undo request leaves the undo opportunity available for retry; an external history change or empty history consumes it.
- The picked item no longer matches the current filters: Snooze still follows the undo opportunity, and the resulting skip is listed separately even though the item is hidden from the remaining view.
- The item is already logged again by another session after the latest line is removed: the existing skipped-entry rule applies, so the item is hidden from the skipped list and counted as picked until that history line is removed.
- Snooze is activated twice quickly: only the first attempt can consume the latest pick; the second refuses without removing another line or duplicating the skip.
- Snooze and Undo overlap: only one consumes the latest pick; the other refuses and reports that the state changed.
- Snoozing the last available entry leaves no remaining entries: the interface shows the existing all-skipped or neutral no-items state, offers restore, and picks nothing automatically.
- The item is snoozed and then another session picks it: history again prevents it from being picked here, and the existing skipped-entry visibility rule applies.
- The active folder or history-log setting changes after a Snooze: the history removal already happened, while the skip and undo state clear for the new target.
- The page is reloaded or the application restarts: the history removal persists, but the skip and undo opportunity do not.
- The system clock changes or the machine sleeps during the cooldown: the item returns no later than the next session and is never permanently unavailable.
- An item name contains spaces, Unicode, or unusual punctuation: it is displayed, snoozed, and restored without corrupting the list or the history view.
- The folder is larger than the visible remaining list: Snooze still reports the true skipped count and does not silently affect unseen entries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both interactive interfaces MUST offer a Snooze action for the current choice when that choice is the latest successful logged pick and the existing Undo action is available for it.
- **FR-002**: Snooze MUST work for every kind of picked entry — files, folders, images, videos, and any other selectable item — with no media-specific behavior.
- **FR-003**: Activating Snooze MUST remove exactly the history line written by that latest successful pick, no earlier or unrelated line, with the same safety guarantees as Undo.
- **FR-004**: A successful Snooze MUST add the same item to the existing skipped list with the fixed ten-minute cooldown capped by the end of the session, and MUST expose the same countdown, per-item restore, and restore-all actions.
- **FR-005**: Snooze MUST NOT pick a replacement item. The board and preview MUST clear only when they still show the snoozed item, and the remaining count MUST stay at its post-pick value (one lower than before the pick) while the item moves from picked to skipped.
- **FR-006**: Snooze MUST NOT modify target files or folders, filter selections, the active folder, the history-log setting, seed, dry-run mode, path memory, or any history line other than the one being removed.
- **FR-007**: The Undo control MUST remain visible and separate. A successful Snooze consumes the single-level undo opportunity, so Undo becomes unavailable until the next successful logged pick; Undo MUST NOT be removed or repurposed.
- **FR-008**: When Undo is unavailable — including no successful logged pick, a dry run, a failed or empty pick, a completed Undo, a target or log-file change, a log rotation, or an external history change — Snooze MUST be unavailable or MUST refuse without changing history or skips.
- **FR-009**: If the latest pick cannot be removed, Snooze MUST refuse completely: no history line may be removed, no skipped entry may be added, and the interface MUST explain why. A refusal because history changed or is empty MUST consume the opportunity exactly as Undo does; a missing-item or unreadable-target refusal before the undo request MUST leave it available for a retry (see FR-010). A target or log-file change clears the opportunity through the existing scope reset.
- **FR-010**: If the picked item no longer exists in the target under that name, or the target cannot be read, Snooze MUST refuse completely, leave history unchanged, and keep the undo opportunity available for a retry.
- **FR-011**: A snoozed item MUST be excluded from picks and from the remaining list while its skip is active, MUST follow the existing skipped-entry counting and visibility rules (counted as skipped while no history line exists; hidden and counted as picked while one does), and MUST follow the existing cooldown, expiry, target-change, session-end, and restore rules.
- **FR-012**: Restoring a snoozed item MUST make it eligible immediately and MUST NOT restore the removed history line, re-enable Undo for it, or re-pick it automatically.
- **FR-013**: Snooze success and failure feedback MUST identify the affected item, state that the pick was removed and the item was deferred when successful, state the return condition, and be announced in an accessible status region.
- **FR-014**: Snooze and its related restore controls MUST be keyboard-operable in both interactive interfaces, MUST show visible focus, and MUST have accessible names that identify the item.
- **FR-015**: Snooze behavior, availability, history outcome, and user-facing messages MUST be consistent across the terminal UI and the web UI.
- **FR-016**: The one-shot command-line interface MUST keep its existing flags, prompt behavior, output, and exit codes; no snooze option or command is added.
- **FR-017**: Snooze MUST NOT introduce a new persistent store, history format, dependency, or externally addressable operation. Existing undo and session-skip contracts MUST remain compatible.
- **FR-018**: Concurrent, repeated, or stale Snooze and Undo actions MUST NOT remove more than one history line, create duplicate skips, or make one item both freshly picked and skipped; refused actions MUST explain the conflict.
- **FR-019**: Snooze MUST NOT be offered for any item that does not satisfy the FR-001 eligibility rule, including an older history entry or an item selected from history that is not the latest successful pick.
- **FR-020**: Existing skip behavior for remaining, not-yet-picked entries MUST remain unchanged, including its separate skipped list, restore actions, all-skipped outcome, and session-only lifetime.

### Key Entities

- **Latest Pick**: The most recent successful logged selection in the current session and target, represented by the existing single-level undo opportunity. It identifies the exact history line that Snooze may remove.
- **Snooze Action**: A combined reversal-and-deferral of the latest pick. It succeeds only when the pick can be undone and the item can be deferred; it then removes one history line and creates one skipped entry.
- **Skipped Entry**: The existing session-only deferral of one item name with a cooldown and return condition. A snoozed item is indistinguishable from any other skipped entry except for how it entered the list.
- **Undo Opportunity**: The existing single-level, session-only ability to remove the latest logged pick. Snooze consumes it exactly as Undo would.
- **Snooze Outcome**: The result of the action: snoozed and undone, unavailable, or refused because history, the item, or the session state changed.

## Success Criteria *(mandatory)*

- **SC-001**: In 100% of scripted Snooze flows, exactly the latest pick's history line is removed and no other history line, target file, or target folder changes.
- **SC-002**: In 100% of scripted checks, a snoozed item appears in the skipped list with a return condition, is never picked while skipped, and becomes eligible after the cooldown, after restore, or in a new session.
- **SC-003**: Snooze is never available when the existing Undo opportunity is gone, and whenever it is available it targets that same latest receipt; verified in 100% of dry-run, failed, empty, stale-history, changed-target, completed-undo, and history-preview checks.
- **SC-004**: Every refused Snooze leaves history and the skipped list unchanged and explains the reason in 100% of scripted checks.
- **SC-005**: The Undo control remains visible in 100% of checks; after a successful Snooze it is unavailable until the next successful logged pick, and it works normally for that new pick.
- **SC-006**: Restoring a snoozed item never re-adds its history line and never re-enables Undo for it, verified in 100% of restore checks.
- **SC-007**: A keyboard-only person can reach, identify, and activate Snooze and its restore controls in both interactive interfaces with visible focus and an accessible name in 100% of scripted keyboard checks.
- **SC-008**: The terminal UI and web UI produce the same availability, history, skip, and message outcome for the same state in 100% of paired checks.
- **SC-009**: No new externally addressable operation or persistent state is introduced; the existing public interface inventory and CLI behavior remain unchanged, and all existing command-line tests continue to pass. An additive test-only guard asserting that no snooze option is allowed is permitted.
- **SC-010**: Snooze feedback appears within one second after activation, and a cooldown expiry updates the remaining and skipped views without a manual reload while the interface is open.

## Assumptions

- "The video that selected" refers to the current picked item in general; the action is not limited to video files.
- Snooze is offered only for the latest successful logged pick in the current session and target, because it reuses the existing single-level Undo opportunity. Older history entries remain out of scope.
- Snooze is a composition of two existing behaviors: undo the latest pick, then skip that same item for the existing ten-minute cooldown. It is not a new persistent history operation.
- Snooze follows Undo availability rather than current filter eligibility. The item was eligible when picked, and the resulting skip remains listed even if a filter later hides it from the remaining view.
- Snooze consumes the single-level undo opportunity. Undo remains visible but unavailable until the next successful logged pick; restoring the snoozed item does not bring the removed history line back.
- No replacement item is picked after Snooze, matching both Undo and skip. The person decides when to pick again.
- A successful Snooze is permanent with respect to history: the removed line is not restored by a later session, reload, restore, or cooldown.
- The skip portion is session-only. A page reload or application restart clears the skip and the undo opportunity, while the history removal already performed remains.
- The existing skip list, cooldown, empty-state precedence, all-skipped outcome, restore-all, and session/target reset rules apply unchanged.
- The web interface performs the same combined action through its existing undo and session-skip capabilities; no new server capability, stored skip state, or history format is required.
- The one-shot command-line interface has no interactive session and gains no snooze option.
- Existing atomic history writes and external-change detection remain the safety boundary; a failed removal never leaves a partial history or skip change.

## Dependencies

- The existing single-level Undo behavior defines when a latest pick can be removed and how external history changes are detected.
- The existing skip/snooze feature defines the skipped list, ten-minute cooldown, restore and restore-all actions, all-skipped outcome, and session/target reset rules.
- The existing pick result identifies the current choice and the history line that was written.
- Both interactive interfaces must present the same combined action and the same outcome.
- The existing command-line behavior, history format, public interface inventory, and persistent-state rules remain binding.

## Out of Scope

- Snoozing an older history entry, an item selected from history that is not the latest pick, or an item that has not been picked.
- Re-adding the removed history line when a snoozed item is restored, or making Undo reverse a Snooze.
- Multi-level undo, redo, or a history browser for choosing which line to remove.
- Custom cooldowns, schedules, reminders, notifications, or calendar integration.
- Batch snooze, snoozing by type or pattern, or automatic snooze rules.
- A new persistent store, a new history format, a new externally addressable operation, or a new dependency.
- Changing the one-shot command-line interface, pure skip ("Not now"), filters, target content, path memory, or existing API contracts beyond compatible additive reuse.
