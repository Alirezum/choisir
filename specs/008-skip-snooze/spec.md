# Feature Specification: Skip and Snooze

**Feature Branch**: `008-skip-snooze`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "**Skip / snooze** — “not now” for an item without treating it as picked; it returns after a cooldown or next session. Complements Undo without rewriting history. *Medium.*"

## Clarifications

### Session 2026-11-17

- Q: When someone says "not now," which item should Skip act on? → A: A remaining entry before it is picked; the existing pick-and-log flow is unchanged.
- Q: How long should a skipped entry stay out of the pool before it returns? → A: A fixed ten-minute cooldown, capped by the end of the current session; no duration prompt or setting is introduced.
- Q: When the person switches folders or history logs and later returns, should skipped entries still be skipped? → A: No. All skips clear when the active folder or history-log setting changes, and returning starts with no skipped entries. Archiving, clearing, or editing the log's contents does not clear skips.
- Q: In the web UI, what should count as a new session that returns all skipped entries? → A: Every page load or reload starts a new session, and multiple tabs are independent.
- Q: What should happen when every eligible entry is currently skipped? → A: Show a distinct all-skipped message, write nothing to history, and offer restore-all; no automatic pick occurs.
- Q: When a skipped entry stops matching the current type or entry filters, or is hidden by the folder options, should it still appear in the skipped list? → A: Yes. It stays listed and counted as skipped until it expires or is restored, even though it is not shown as remaining.
- Q: When another session picks an entry that this session has skipped, should the skipped list keep showing that entry? → A: No. It is hidden from the skipped list and count and counted as picked, while its skip record is kept internally so it reappears if that history line is removed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Defer an item without picking it (Priority: P1)

A person reviews the remaining entries in the current folder. One entry is not right for now, but they do not want to exclude it permanently, record it as picked, or edit history to get it back. They mark that entry **Not now**. It leaves the remaining pool immediately without being recorded as picked, and the person continues picking from the other entries. The deferred entry returns after a short cooldown, or when the next session starts, whichever happens first.

**Why this priority**: Random selection is most useful when an item can be declined without consequences. The existing ways to keep an item out of the pool are a session-long filter or a history edit; neither expresses "not now" for one entry. Skip closes that gap.

**Independent Test**: In a folder with known entries and no history, mark one entry as skipped, then verify that it disappears from the remaining view and cannot be picked, that history is unchanged, and that it returns after the cooldown or at the start of a new session and can then be picked.

**Acceptance Scenarios**:

1. **Given** an eligible entry in the remaining view, **When** the person activates Not now, **Then** the entry leaves the remaining pool, the remaining count decreases, no history entry is written, and the status message names the entry and when it will return.
2. **Given** a skipped entry, **When** the person picks any number of times during the cooldown, **Then** the skipped entry is never selected, while every other eligible entry remains available.
3. **Given** a skipped entry whose cooldown ends while the interface is open, **When** the remaining view refreshes, **Then** the entry is eligible again and appears in the remaining list without a manual reload.
4. **Given** a skipped entry and a session that ends before its cooldown, **When** a new session loads the same folder, **Then** the entry is eligible again and no skip is restored.
5. **Given** a skipped entry, **When** the person restores it, **Then** it is eligible immediately, reappears in the remaining list, and leaves the skipped list.
6. **Given** several skipped entries, **When** the person restores all, **Then** every skipped entry becomes eligible immediately, the skipped list clears, and history is unchanged.
7. **Given** an entry was skipped, **When** the person picks it after it returns, **Then** that pick is logged exactly as any other pick and the earlier skip has no effect on history.

---

### User Story 2 - See and control deferred items (Priority: P2)

The person can always tell which entries are deferred, why they are unavailable, and when they will return. Deferred entries are shown separately from remaining entries and from picked history, and can be restored one at a time or all at once. A deferred entry never looks like a picked entry, a filtered-out entry, or a deleted entry.

**Why this priority**: An item that silently disappears is indistinguishable from data loss or a bug. Visibility and an immediate restore action make the temporary exclusion trustworthy.

**Independent Test**: Skip two entries, confirm both appear in a separate skipped list with their return condition, restore one and then the other, and verify the remaining and skipped counts update without changing history, filters, or target content.

**Acceptance Scenarios**:

1. **Given** one or more skipped entries, **When** the person views the remaining area, **Then** the skipped entries are listed separately with their names and when they will return: the remaining cooldown, with the next session as the latest return point.
2. **Given** a skipped entry with time left, **When** the cooldown passes, **Then** the entry leaves the skipped list and appears in the remaining list without any user action or page reload.
3. **Given** several skipped entries, **When** the person restores one, **Then** only that entry returns, the others remain skipped, and both counts are accurate.
4. **Given** skipped entries exist, **When** the person changes the active folder or history-log setting, **Then** the skipped list clears for the previous target and no skipped entry carries into the new target.
5. **Given** a skipped entry is renamed or deleted while the interface is open, **When** the view refreshes, **Then** the stale entry is removed from the skipped list without an error and no other entry is affected.
6. **Given** every eligible entry is skipped, **When** the person looks at the remaining area, **Then** the interface explains that items are skipped rather than picked or filtered out, shows zero available entries, and offers a restore action.
7. **Given** skipped entries exist, **When** the person uses only the keyboard, **Then** every skipped entry and every restore control is reachable with visible focus and an accessible name that identifies the entry.

---

### User Story 3 - Trust that skip never rewrites history (Priority: P3)

Skipping, restoring, restoring all, letting a cooldown expire, and a target or session change never add, remove, or rewrite a history entry. They also never change filters, the active folder, the log-file setting, the seed, dry-run mode, the current choice, the preview, remembered folders, or any target file or folder. Both interactive interfaces behave the same way, and the one-shot command line is unchanged.

**Why this priority**: History is the product's record of what was actually picked. A "not now" action is only trustworthy if it is clearly outside that record and cannot become a hidden history edit.

**Independent Test**: Record the history content and target hashes, then skip, restore, let a skip expire, restore all, change targets, and restart in both interactive interfaces. Verify that history and target content never change and that the command-line interface is unchanged.

**Acceptance Scenarios**:

1. **Given** any skip, restore, restore-all, expiry, or target-change action, **When** it completes, **Then** history contains exactly the same entries in the same order as before, with nothing added, removed, or rewritten.
2. **Given** any skip, restore, restore-all, expiry, or target-change action, **When** it completes, **Then** the active folder, history-log setting, filter selection, seed, dry-run setting, current choice, preview, remembered folders, target files, and target folders are unchanged.
3. **Given** a person using only the keyboard, **When** they skip and restore entries in either interactive interface, **Then** every control is reachable, shows visible focus, and has an accessible name that identifies the entry.
4. **Given** a skip or restore succeeds or is refused, **When** feedback appears, **Then** it names the affected entry and states whether it was skipped, restored, or could not be changed, and it is announced in an accessible status region.
5. **Given** the one-shot command-line interface is used, **When** it runs, **Then** its flags, prompt behavior, output, and exit codes are unchanged and no skip command or option is added.
6. **Given** a pick and a skip overlap in time, **When** both actions complete, **Then** the affected entry is never both skipped and recorded as picked, history remains consistent, and the interface explains any action that was refused because the state changed.

---

### Edge Cases

- The folder is empty, or every entry has already been picked: Skip is unavailable because there is nothing eligible to defer, and the existing empty or exhausted message appears without a history write.
- Filters exclude every entry: the existing filtered-empty outcome appears, Skip is unavailable, and no skip is created.
- Filters leave entries but every one is already picked: the existing filtered-exhaustion outcome appears, not an all-skipped outcome.
- Every eligible entry is skipped: a pick attempt reports a distinct all-skipped outcome, writes nothing to history, does not claim the folder is empty or history is exhausted, and offers restore.
- An entry is skipped and then a different session picks it: history now prevents it from being picked again; the entry leaves the skipped list and is counted as picked, while its skip record stays active so that removing the history line makes it skipped again until expiry or restore.
- An entry is skipped and then its history entry is removed in another session: the skip remains active until it expires or is restored, after which the entry is eligible again under the current history.
- An entry is skipped and then deleted or renamed: the stale skip is pruned without an error and without blocking a different entry with the old or new name.
- An entry is skipped and then a filter stops matching it: it stays skipped and remains in the skipped list and count, though it is not shown as remaining; if the filter matches it again before expiry, it is still skipped until it returns.
- A skip expires at the same moment the person activates it again: the entry is treated as eligible and the new action starts a fresh cooldown rather than creating two overlapping skips.
- The person activates skip twice quickly: at most one skip exists for the entry, the second action does not duplicate the entry or change history, and feedback remains clear.
- A pick is already in progress when skip is activated: the entry is not both selected and skipped; the interface discards the stale result or refuses the skip, explains the outcome, and keeps history consistent.
- The active folder or history-log setting changes while skips are active: all skips for the previous target clear, the new target starts with no skipped entries, and returning to the old target in the same session does not restore them.
- The application restarts, or the web interface is reloaded: every previously skipped entry is eligible again because no skip state is persisted.
- Two sessions are open on the same folder: a skip in one session does not block a pick in the other, and neither session writes skip state to shared storage.
- The history log is archived, cleared, or modified externally while skips are active: skips keep their own cooldown and never change history; entries that become newly eligible still honor active skips.
- A folder has more entries than the visible remaining list shows: the skipped list reports its total and remains usable without blocking picking; entries outside the visible list are not silently skipped.
- An entry name contains spaces, Unicode, or unusual punctuation: it is displayed, skipped, and restored without corrupting the skipped list or the remaining view.
- The system clock changes or the machine sleeps during a cooldown: the entry returns no later than the next session, and the interface never leaves it permanently unavailable.
- A skip or restore is attempted for an entry that no longer exists or no longer passes the current options: the action explains that nothing changed, leaves history and target content untouched, and the interface remains usable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both interactive interfaces, the terminal UI and the web UI, MUST let the person mark a currently eligible remaining entry as skipped ("Not now") with one explicit action and no confirmation dialog. Skip MUST act before the entry is picked and MUST NOT make a pick result provisional or defer the logging of a picked entry.
- **FR-002**: Skipping MUST NOT treat the entry as picked: no history entry may be added, removed, or rewritten by skipping, restoring, restoring all, letting a skip expire, or a target or session change, and the picked count and history view MUST NOT change. If another session logs a skipped entry, this session MUST hide it from the skipped list and count it as picked while retaining its skip record, so it is skipped again only if that history line is later removed.
- **FR-003**: While a skip is active, the entry MUST be excluded from pick selection, MUST NOT appear in the remaining list, and MUST NOT be counted as available remaining.
- **FR-004**: A skip MUST last until the earlier of a fixed ten-minute cooldown or the end of the current session, and MUST NOT persist across sessions. No duration prompt or duration setting is introduced.
- **FR-005**: When a cooldown ends while the interface is open, the skipped entry MUST return to the remaining pool automatically and the remaining and skipped views MUST update without a manual reload.
- **FR-006**: Starting a new session MUST make every previously skipped entry eligible again; no skip state may be restored from a prior session. In the web UI, a page load or reload starts a new session, and multiple tabs are independent.
- **FR-007**: The interface MUST show active skipped entries separately from remaining entries and history, including each entry's name and when it will return (the remaining cooldown, with the next session as the latest point), and MUST provide per-entry restore and restore-all actions. A skipped entry that a filter or folder option hides from the remaining view MUST stay listed and counted as skipped until it expires or is restored.
- **FR-008**: Restoring a skipped entry MUST make it eligible immediately and MUST NOT change history, filters, the current choice, or target content.
- **FR-009**: When every currently eligible entry is skipped, a pick attempt MUST report a distinct all-skipped outcome, MUST write nothing to history, MUST NOT report an empty folder, exhausted history, or filtered-empty state, MUST NOT automatically restore or pick an entry, and MUST offer a restore action.
- **FR-010**: Only an entry that currently passes the existing folder options, filters, and history rules may be skipped; an entry that is already picked, excluded by filters, absent, or outside the current target MUST NOT receive a skip.
- **FR-011**: Skip state MUST be scoped to the current target folder and history-log setting and MUST clear when either changes, including when the person later returns to a previous target; skips from one target MUST NOT affect another target.
- **FR-012**: When folder contents change, skipped entries that no longer exist MUST be pruned, newly appearing entries MUST start unskipped, and valid skips MUST remain until they expire or are restored.
- **FR-013**: Skip, restore, restore-all, expiry, and target-change actions MUST NOT change the active folder, history-log setting, filter selection, seed, dry-run setting, current choice, preview, remembered folders, target files, or target folders.
- **FR-014**: Success and failure feedback MUST identify the affected entry when one exists, state the return condition for a skip, and be announced in an accessible status region in both interactive interfaces.
- **FR-015**: Skip and restore controls MUST be keyboard-operable in both interactive interfaces, MUST show visible focus, and MUST have accessible names that identify the entry and, for a skipped entry, when it will return.
- **FR-016**: Skip state MUST be session-only and independent per session; one session's skips MUST NOT block another session's picks, and no skip state may be written to shared history or remembered-folder storage.
- **FR-017**: If an action cannot be applied because the entry vanished, the target changed, the entry is no longer eligible, or a pick is already in progress, the interface MUST explain the outcome, change no history or target content, and remain usable.
- **FR-018**: A concurrent pick and skip MUST NOT make one entry both skipped and recorded as picked; history MUST remain consistent, and the interface MUST explain any refused or stale action.
- **FR-019**: The one-shot command-line interface MUST keep its existing flags, prompt behavior, output, and exit codes; this feature adds no command-line skip option.
- **FR-020**: In a folder larger than the visible remaining list, the interface MUST report the true number of skipped entries and MUST remain responsive; entries outside the visible list MUST NOT be skipped silently.
- **FR-021**: The skipped list MUST be cleared when the person restores all skipped entries, and restoring all MUST return every affected entry to the remaining pool without changing history, filters, or target content.
- **FR-022**: Skip behavior and messages MUST be consistent across the terminal UI and web UI; the same action against the same state MUST produce the same eligibility, count, and history result.

### Key Entities

- **Skipped Entry**: A session-only reference to one entry name in the current target and history-log setting, with when its skip started, when it returns, and whether it is active. It is not a history entry, is not counted as picked, and does not alter the history log.
- **Skip State**: The active skipped entries for the current target and session, together with their remaining cooldown, the restore and restore-all actions, and the distinct all-skipped condition. It is cleared by a target or history-log setting change, by a new session, and by restore or restore-all actions.
- **Eligible Remaining Pool**: The entries that pass the existing folder options, filters, and history rules, minus active skipped entries. Skip only removes entries from this pool temporarily; it never changes which entries history or filters allow.
- **Skip Outcome**: The result of a skip-related action: skipped, restored, restored all, expired, pruned, unavailable, or refused because the state changed. It identifies the entry and the return condition when one exists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of scripted skip, restore, restore-all, expiry, and target-change flows, history content is identical before and after, with zero entries added, removed, or rewritten, and no skipped entry is counted as picked.
- **SC-002**: A person can skip an eligible remaining entry in one action without typing, opening a menu, or confirming a dialog.
- **SC-003**: In 100% of scripted checks, a skipped entry is absent from picks while the skip is active and can be selected after the cooldown ends or after a new session starts.
- **SC-004**: In 100% of conflict and failure checks — all entries skipped, target or history-log setting change, vanished entry, filter change, history change, restart, concurrent session, and overlapping pick — zero history entries and zero target files or folders are added, removed, or rewritten.
- **SC-005**: Skip feedback appears within one second on the reference machine, and an expiring skip is reflected in the remaining and skipped views without a manual reload while the interface is open.
- **SC-006**: A keyboard-only person can reach, identify, and activate skip and restore in both interactive interfaces with visible focus and an accessible name, verified in 100% of scripted keyboard checks.
- **SC-007**: The all-skipped outcome is reported distinctly from empty, exhausted, and filtered-empty outcomes in 100% of scripted checks and never writes history.
- **SC-008**: Existing command-line tests continue to pass with no new flags, output changes, or exit-code changes.
- **SC-009**: No persistent skip state is created; restarting the application or loading a new web session makes every previously skipped entry eligible again in 100% of checks.
- **SC-010**: In 100% of scripted checks, skipped entries are shown separately from picked history and filtered entries, and at least one restore path is available whenever any entry is skipped.

## Assumptions

- "Skip" targets an entry in the **remaining pool before it is picked**, because that is the only way to defer an item without any history write. Skipping an already-picked result is out of scope: that result is already recorded, and Undo remains the way to reverse it.
- The cooldown is a fixed ten minutes. The end of the current session is always the latest a skip can survive. The duration is a product default and is not configurable in this feature; no duration prompt or duration setting is introduced.
- The feature applies to the terminal UI and web UI. The one-shot command line remains unchanged because it has no interactive session in which an item can be deferred, and its public flags, output, and exit codes are protected.
- A session begins when an interactive interface starts and ends when it closes; reloading the web interface starts a new session. Multiple windows or tabs are independent sessions.
- Skips are scoped to the current target folder and history-log setting and clear when either changes, matching the existing session-only filter reset. Returning to a previous target in the same session does not restore its skips. Archiving, clearing, or editing the log's contents does not clear skips.
- Skip is a temporary, entry-specific deferral, not a filter. Existing type and entry filters remain unchanged and continue to express session-long exclusions.
- No confirmation dialog is needed: skip is reversible through restore or the cooldown, and it never changes history or target content.
- Skipping does not automatically pick a replacement entry. The person decides when to pick again.
- The skipped list is display-only metadata; the remaining count and the picked count are adjusted so an entry is counted exactly once, either as available, skipped, filtered, or picked.
- If the interface closes before a cooldown ends, the entry returns in the next session because no skip state is persisted.
- Skipped entries are not written to the history log, remembered-folder record, or any other shared state; no new persistent store or history format is introduced.
- The cooldown is measured while the interface is open; a machine sleep or clock change may delay the visible refresh, but a skip never survives the next session.
- Existing single-item and batch history removal remain separate actions; skip does not remove history entries.

## Dependencies

- The existing history log and its rules are the source of truth for what has been picked; skip adds no parallel history.
- The existing folder options and filter behavior define which entries are eligible to be skipped; skip must not weaken or replace them.
- Both interactive interfaces must present the same skip behavior and produce the same eligibility and history result; skip must not differ by interface.
- The existing pick outcomes and command-line behavior define the boundary this feature must not change.
- The project constitution permits session-only state and forbids new persistent state outside history, its archives, and path memory; this feature therefore requires no constitutional amendment.
- The remaining view must be able to identify and act on individual entries; this feature does not change target content, filters, or history.

## Out of Scope

- Skipping, snoozing, or deferring a pick that has already been logged; Undo remains the way to reverse a logged pick.
- Persisting skips across sessions, sharing skip state between sessions, or restoring skips from a previous session.
- Custom cooldown durations, schedules, reminders, notifications, or calendar integration.
- Bulk skip by type, name pattern, or selection, and automatic skip rules.
- Treating skips as history entries, picked counts, statistics, or audit records.
- Changing history, filters, target files or folders, path memory, or the one-shot command-line interface.
- Redo, multi-level undo, or replacing Undo with skip.
- A new persistent store, a new history format, or any network or telemetry behavior.
