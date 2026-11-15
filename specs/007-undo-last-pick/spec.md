# Feature Specification: Undo Last Pick

**Feature Branch**: `007-undo-last-pick`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "i want add a feature to Undo last pick that made random ..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reverse an unwanted pick (Priority: P1)

A person asks choosier for a random entry, sees the result, and immediately realizes it is not the one they wanted. Instead of clearing history or deleting every trace of that item, they activate **Undo last pick**. Only the selection just made is removed from history, the item becomes eligible to be picked again, and the current choice clears so the interface is ready for the next pick.

**Why this priority**: Random selection makes accidental picks common. A one-action reversal removes the main reason someone would avoid using the picker or would resort to destructive history editing.

**Independent Test**: In a folder with known entries, make a logged pick, activate Undo in the terminal UI and again in the web UI, and verify that exactly one history entry disappears, the item returns to the eligible pool, and the choice board clears while every other state remains unchanged.

**Acceptance Scenarios**:

1. **Given** a successful logged pick in the terminal UI, **When** the person activates Undo last pick, **Then** only that pick's history entry is removed, the item becomes eligible again, the current choice clears, and the status line confirms which item was undone.
2. **Given** a successful logged pick in the web UI, **When** the person activates Undo last pick, **Then** only that pick's history entry is removed, the item becomes eligible again, the board and preview clear, and the status region confirms which item was undone.
3. **Given** two logged picks were made in one session, **When** the person undoes the second pick, **Then** the first pick remains in history and only the second pick is removed.
4. **Given** the same item appears more than once in history, **When** the person undoes the latest pick of that item, **Then** only the exact latest entry is removed and the other occurrences remain.
5. **Given** a pick was undone, **When** the person picks again, **Then** the undone item is eligible and can be selected.
6. **Given** a pick was made in one session and a later pick was made in another session, **When** the first session tries to undo its pick, **Then** no history entry is removed and the person is told that history changed.

---

### User Story 2 - Know when undo is available (Priority: P2)

The person can tell at a glance whether there is a pick to undo and why the action is unavailable when there is not. Undo does not remove a dry-run result, a failed pick, a pick loaded from history, or a pick made in an earlier session.

**Why this priority**: An Undo control that is always enabled but sometimes does nothing, or that removes an older unexpected entry, would be less trustworthy than no Undo at all.

**Independent Test**: Exercise a fresh session, a dry-run pick, an empty or exhausted pick, a successful undo, a second undo attempt, and a folder change. Verify the control's availability and messages match the state without changing history.

**Acceptance Scenarios**:

1. **Given** a fresh session with no picks, **When** the interface loads, **Then** Undo last pick is visibly unavailable and no error is shown.
2. **Given** the most recent pick was a dry run, **When** the pick completes, **Then** Undo last pick is unavailable and history is unchanged.
3. **Given** a pick returned no item because the folder was empty, exhausted, or filtered to nothing, **When** the result appears, **Then** Undo last pick is unavailable.
4. **Given** a successful undo just completed, **When** the interface refreshes, **Then** Undo last pick is unavailable until another logged pick succeeds.
5. **Given** an undoable pick exists, **When** the person changes the active folder or history log, **Then** the undo becomes unavailable because the session has moved to a different target.
6. **Given** an undo succeeds or is refused, **When** feedback appears, **Then** it names the affected item and states whether the pick was undone or why it could not be.

---

### User Story 3 - Keep undo safe and keyboard-accessible (Priority: P3)

Undo changes one history entry and nothing else. It never touches target files or folders, filters, the active path, the log-file setting, the seed, the dry-run setting, or remembered folders. Keyboard users can reach and activate it in both interfaces with visible focus and an accessible name.

**Why this priority**: The feature is small, but it edits the same history file the rest of the product depends on. Its safety and accessibility need to be explicit so it does not become a destructive shortcut.

**Independent Test**: Use only the keyboard to undo a pick in each interface, then compare hashes of target files and the history log, and verify the active path, filters, seed, dry-run setting, and remembered folders are unchanged.

**Acceptance Scenarios**:

1. **Given** an undoable pick in either interface, **When** the person navigates by keyboard, **Then** the Undo control is reachable, shows visible focus, and has an accessible name that includes the item to be undone.
2. **Given** an undoable pick in the web UI, **When** focus is inside a text field and the person uses the field's normal undo shortcut, **Then** the field's text editing is not replaced by the picker's undo action.
3. **Given** an undo succeeds, **When** the action completes, **Then** no target file or folder, active path, log-file setting, filter selection, seed, dry-run setting, or remembered folder is added, removed, renamed, or rewritten.
4. **Given** history cannot be read or rewritten, **When** the person activates Undo, **Then** the application explains the failure without blocking further use and leaves history unchanged.
5. **Given** the one-shot command-line interface is used, **When** it runs, **Then** its flags, output, and exit codes are unchanged and no undo command is added.

---

### Edge Cases

- No history file exists, or the current target has never been picked from: Undo is unavailable and no file is created merely by viewing the interface.
- The history file is deleted, emptied, or archived between the pick and the undo: no entry is removed, the person is told there is nothing to undo, and history is left as found.
- The newest history line is malformed or cannot be read: undo refuses rather than guessing which line to remove.
- Another session appends a pick after this session's pick: this session's undo refuses because its entry is no longer the newest, and no history is removed.
- Another session removes or rewrites the picked entry: this session's undo refuses, refreshes the history view, and does not remove a different entry.
- The same item has several history entries, including one from this session: only the exact entry created by this session's latest pick is removed.
- The history log is at its existing rotation limit: undo still completes within the normal interactive feedback window and never leaves a partially rewritten log.
- A dry-run pick, an invalid-path result, an empty folder, an exhausted pick, or a filtered-to-nothing result occurs: Undo is unavailable because no history entry was written.
- A pick is loaded from the history panel rather than freshly picked: loading it does not make it undoable.
- The active folder or log file changes after a pick: undo availability clears and the previous session's pick is not removed from the new target's history.
- The application restarts: undo availability is not restored; a fresh pick is required.
- The person activates Undo twice quickly: at most one entry is removed and the second attempt reports that there is nothing left to undo.
- A filter currently hides the undone item: the item becomes eligible again, but the filter selection is unchanged, so it may remain outside the visible remaining list.
- The current choice board shows a different item when Undo is activated: only the undo target's history entry is removed, and the unrelated current choice is left in place.
- Two interactive sessions pick and undo at the same time: no entry is lost, duplicated, or partially rewritten, and a session never removes an entry it did not create.
- The pick was made before the feature was introduced or by a different tool: it is not undoable unless this session made it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both interactive interfaces MUST offer an Undo last pick action whenever the current session has an undoable pick.
- **FR-002**: The undo target MUST be the history entry written by the most recent successful pick in the current session, and that pick MUST have been logged; if the most recent pick was a dry run or wrote nothing, there is no undo target.
- **FR-003**: Undo MUST remove only the exact history entry created by that pick, leaving every other entry in the log unchanged, including other entries for the same item.
- **FR-004**: After a successful undo, the item MUST be eligible for future picks under the existing history rules, and the remaining, history, and current-choice views MUST refresh to reflect the removal.
- **FR-005**: Undo MUST be single-level: after a successful undo the action MUST be unavailable until another logged pick succeeds; no redo or multi-level undo is provided.
- **FR-006**: Only logged picks MUST be undoable; dry-run picks, invalid-path, empty, exhausted, filtered-empty, and filtered-exhausted outcomes, history-row loads, and picks from other sessions MUST NOT become undo targets.
- **FR-007**: Changing the active folder or history log MUST clear undo availability for the previous target.
- **FR-008**: If the history log has changed so that the session's entry is missing, no longer the newest entry, or no longer identifiable, undo MUST remove nothing, explain why, and refresh the history view rather than removing a substitute entry.
- **FR-009**: Concurrent picks, undos, and history edits MUST NOT lose, duplicate, or corrupt entries; undo MUST NOT remove an entry created by another session.
- **FR-010**: If history cannot be read or rewritten, undo MUST fail without changing history and MUST leave the application usable.
- **FR-011**: Undo MUST NOT change the active folder, history-log setting, filter selection, seed, dry-run setting, remembered folders, target files, target folders, or any history entry other than the target entry.
- **FR-012**: Success and failure feedback MUST identify the affected item when one exists and MUST be announced in an accessible status region in both interfaces.
- **FR-013**: The Undo control MUST be keyboard-operable in both interfaces, show visible focus, and have an accessible name that identifies the item to be undone.
- **FR-014**: If the web UI offers a keyboard shortcut for undo, it MUST NOT intercept the normal undo behavior of a focused text field.
- **FR-015**: Undo availability MUST be session-only and MUST NOT be persisted; restarting the application clears it.
- **FR-016**: The one-shot command-line interface MUST keep its existing flags, output, prompt behavior, and exit codes; this feature adds no command-line undo option.
- **FR-017**: If the current choice and preview show the undone item, undo MUST clear them; if they show an unrelated item, they MUST remain unchanged.
- **FR-018**: Undo MUST require one explicit user action and MUST NOT require a confirmation dialog, because it changes only the most recent history entry and never target content.

### Key Entities

- **Undoable Pick**: A session-only reference to the one history entry created by the most recent successful pick, when that pick was logged. It identifies the item and enough entry information to prove that the exact entry is still present and newest.
- **Undo State**: The current availability of undo and, when unavailable, the reason the person should understand. It is session-only and is cleared by a folder or log change, a restart, a dry-run result, a failed pick, or a successful undo.
- **History Entry**: An existing record of one selection. Undo removes exactly one entry and does not introduce a new persistent record or format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of scripted undo flows, exactly one history entry is removed and the undone item becomes eligible for the next pick in both interactive interfaces.
- **SC-002**: A person can undo the latest logged pick in one action without typing, navigating away from the current view, or confirming a dialog.
- **SC-003**: In 100% of scripted checks, undo leaves every other history entry, target file, target folder, active path, history-log setting, filter selection, seed, dry-run setting, and remembered-folder entry unchanged.
- **SC-004**: In 100% of conflict and failure checks — external append, external removal, rewrite, missing log, dry-run, and no-pick states — undo removes zero entries and leaves the history content unchanged.
- **SC-005**: Undo feedback appears within one second for a history log at the existing rotation limit on the reference machine.
- **SC-006**: A keyboard-only person can reach, identify, and activate undo in both interfaces with visible focus and an accessible name, verified in 100% of scripted keyboard checks.
- **SC-007**: Existing command-line tests continue to pass with no new flags, output changes, or exit-code changes.
- **SC-008**: After an undo, a scripted next pick can select the undone item, proving that eligibility was restored.
- **SC-009**: No new persistent state is created for undo; restarting the application makes undo unavailable until a new pick is made.

## Assumptions

- "Last pick" means the most recent successful pick that actually wrote a history entry in this running session. Dry runs and outcomes that wrote nothing are not picks for this purpose.
- The feature applies to the terminal UI and web UI. The one-shot CLI remains unchanged because it has no session in which a "last pick" can be undone, and its public flags, output, and exit codes are protected.
- Undo is intentionally single-level. Multi-level undo, redo, restoring the exact original log position, and undoing picks from earlier sessions are out of scope.
- No confirmation dialog is needed: undo is one explicit action, affects only the newest history entry, and never touches target content. Existing history deletion controls remain available for other cases.
- Undo removes the entry and restores eligibility; it does not automatically choose a replacement item. The person decides when to pick again.
- Undoing affects history eligibility only. It does not change filters, so an item still excluded by a filter may not appear in the visible remaining list even though it is no longer logged.
- Changing the active folder or history log ends the undo opportunity because the session's target and history have changed.
- Undo state is not persisted across restarts or shared between sessions; a session can only undo a pick it made itself.
- The existing history log format and rotation behavior stay unchanged. Undo removes an entry through the same history-writing rules already used for item deletion.
- No new network access, telemetry, dependency, or persistent store is introduced.
- The existing single-item history removal remains a separate action: it can remove every entry for a chosen item, while undo removes only the latest session pick.
- The feature must not make picking slower or block the interface while history is being read or rewritten.

## Dependencies

- The existing history log and its rotation behavior are the source of truth; this feature adds no parallel history store.
- Both interactive interfaces must present the same undo behavior and produce the same history result; undo must not differ by interface.
- After undo, both interfaces must refresh history, remaining items, the current choice, and the preview consistently.
- Existing command-line behavior and tests define the boundary that this feature must not change.
- The project constitution already permits explicit single-item history removal and requires history writes to leave existing history intact on failure; no amendment is needed for this feature.

## Out of Scope

- A command-line undo action or any change to one-shot command output, flags, prompts, or exit codes.
- Multi-level undo, redo, undo history across restarts, or restoring a previous log position or timestamp.
- Undoing picks made in another session, loaded from the history panel, or made before the current session began.
- Restoring cleared or archived history, changing target files or folders, or providing a general history audit or checkpoint system.
- Changing filters, the active folder, the log-file setting, seed, dry-run mode, or remembered folders as part of undo.
