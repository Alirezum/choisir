# Feature Specification: Remembered Folder Paths

**Feature Branch**: `006-remember-path`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "i want to remember path"

## Clarifications

### Session 2026-11-11

- Q: When should a folder become remembered: only after a successful pick, or whenever it is successfully opened or selected? → A: Only after a successful pick from it, including a dry-run pick; opening or browsing a folder without a pick does not remember it.
- Q: When the most recently used remembered folder is unavailable, should the app try the next valid recent folder or fall back to today's default behavior? → A: Skip the unavailable folder, use the next valid recent folder, and fall back to today's default only when no remembered folder is valid.
- Q: When a remembered folder is unavailable, should the recent list remove it immediately or keep it visible as unavailable until the person removes it? → A: Remove and prune the unavailable folder automatically as soon as it is detected; never show it as a dead entry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume in the last used folder (Priority: P1)

A person uses choosier on the same folder repeatedly. Instead of typing or browsing to that folder every time, they open the app without naming a folder and it starts in the folder they most recently used. Explicitly naming a folder still overrides the remembered one.

**Why this priority**: Re-entering the same path is the most repeated action in every session. Restoring one remembered folder removes that friction with the smallest useful slice and no change to how picking works.

**Independent Test**: Make a successful pick in a folder, close the application, and reopen it without supplying a path in both interactive interfaces. Verify the same folder is active and ready to pick, with existing history and filter behavior unchanged.

**Acceptance Scenarios**:

1. **Given** a successful pick was made in a folder, **When** the person starts the terminal UI without naming a folder, **Then** that folder is the active target and the remaining view is ready for the next pick.
2. **Given** a successful pick was made in a folder, **When** the person starts the web UI without naming a folder, **Then** that folder is the active target and the current state is loaded for it.
3. **Given** the terminal UI and web UI share remembered locations, **When** the person picks in one interface and then opens the other without a path, **Then** the other interface starts in the same folder.
4. **Given** an explicit folder is named at launch, **When** the application starts, **Then** the explicit folder is used regardless of the remembered folder.
5. **Given** no folder has ever been used, **When** the application starts, **Then** it behaves exactly as it does today, with no error and no invented location.
6. **Given** the remembered folder is missing, is not a folder, or cannot be read, **When** the application starts, **Then** it skips that folder, uses the next valid recent folder, or today's default behavior when none are valid, explains the substitution without blocking startup, prunes the stale location, and continues to be usable.
7. **Given** a successful pick is made in a new folder, **When** the pick completes, **Then** that folder becomes the most recently used folder for the next launch.

---

### User Story 2 - Jump back to a recent folder (Priority: P2)

The person rotates among a handful of folders. The interface offers a short list of recently used folders so they can switch back with one action instead of typing a path.

**Why this priority**: One remembered folder covers the dominant case; a recent list covers changing projects without adding a full folder-management feature. It is independently useful once remembering exists.

**Independent Test**: Use three different folders in sequence, reopen the interface, and verify the recent list shows them newest first without duplicates. Choose the oldest from the list and verify it becomes active without typing.

**Acceptance Scenarios**:

1. **Given** successful picks in folders A, then B, then C, **When** the recent list is shown, **Then** it lists C, B, and A in that order.
2. **Given** a folder already appears in the recent list, **When** it is used again, **Then** it moves to the top and is not duplicated.
3. **Given** more than ten distinct folders have been used, **When** the recent list is shown, **Then** it contains at most ten folders and drops the oldest entries.
4. **Given** the recent list is visible in either interactive interface, **When** the person chooses a folder from it, **Then** that folder becomes active and its state loads without typing in the path field.
5. **Given** a remembered folder is unavailable, **When** the recent list is refreshed, **Then** the unavailable folder is omitted and pruned rather than shown as a dead entry or causing an error.
6. **Given** the person uses only the keyboard, **When** they open and navigate the recent list in either interface, **Then** every entry and its activation control are reachable with visible focus and an accessible name containing the full path.

---

### User Story 3 - Control remembered folders (Priority: P3)

The person can see what the application remembers, remove a single folder, or forget all remembered folders. Doing so never changes picks, history, filters, or files.

**Why this priority**: Remembering local paths is a privacy-sensitive convenience. A simple way to inspect and erase that memory makes the feature trustworthy, but the feature is usable without it.

**Independent Test**: Remember several folders, remove one, then clear the rest. Verify each action is reflected immediately and after a restart, the next launch uses today's default behavior, and history and target folders are untouched.

**Acceptance Scenarios**:

1. **Given** remembered folders exist, **When** the person clears remembered folders, **Then** all remembered locations are removed and the next launch behaves as a first run.
2. **Given** several remembered folders exist, **When** the person removes the most recent one, **Then** it disappears and the next most recent becomes the last used folder.
3. **Given** the person removes a folder that is not the most recent, **When** the list refreshes, **Then** only that folder is removed and the order of the others is preserved.
4. **Given** the person clears or removes remembered folders, **When** the action completes, **Then** no history entry, active filter, current choice, target file, or target folder is added, removed, or rewritten.
5. **Given** a remembered folder has become unavailable, **When** the application detects it, **Then** the pruning behavior in FR-010 applies and the stale location does not return on the next launch.
6. **Given** remembered locations cannot be read or written, **When** the person uses the application, **Then** picking still works, a non-blocking notice explains that the path could not be remembered, and no history or target content is affected.
7. **Given** another session is active, **When** the person clears remembered folders, **Then** the other session continues working and only future successful picks may re-add a folder.

---

### Edge Cases

- The first launch has no remembered state: today's default behavior applies and no empty or invalid location is shown.
- The remembered folder was deleted, renamed, unmounted, or moved between launches: startup skips it, uses the next valid recent folder when one exists, otherwise applies today's default behavior, and prunes the stale location without an error dialog.
- The remembered path is a file rather than a folder, or the person loses read permission: it is treated as unavailable.
- The explicit launch path is invalid while a valid remembered folder exists: the explicit path still wins and the existing invalid-path outcome is shown; the remembered folder is not silently substituted.
- The same folder is reached through different text forms (trailing separator, relative segments, symbolic link): it is treated as one remembered location and does not create duplicates in the recent list.
- A remembered path contains spaces, Unicode, unusual punctuation, or is very long: it is displayed and selected without corrupting the stored list or the path field.
- Two interfaces are open at once: a successful pick in either updates the shared recency without corrupting the remembered list; the most recent successful pick wins.
- The remembered list is full: adding a new folder evicts the oldest entry.
- Remembered locations are cleared while the app is running: the current session keeps working, and only a later successful pick can add a folder again.
- Picking is attempted from a remembered folder that becomes unavailable mid-session: the existing invalid-path or failure behavior applies; remembering does not mask it.
- The folder is valid but no pick is made: it is not recorded as used, so browsing or an abandoned session does not displace the last successfully used folder.
- A pick is dry-run: it still counts as a successful pick because the person selected from that folder, but no history is written.
- A remembered folder becomes unavailable while the recent list is open: it is removed from the list at the next refresh and is never selectable as a dead entry.
- Removing or clearing remembered folders does not change the folder currently active in a running session; only future launches use the updated memory.
- Remembered locations must not restore session-only filters, the previous choice, previews, or history.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the terminal UI or web UI starts without an explicit target folder, it MUST use the most recently used valid remembered folder as the active target, skipping unavailable folders and falling back to today's default behavior only when no remembered folder is valid.
- **FR-002**: An explicit target folder supplied at launch MUST always take precedence over a remembered folder, including when the explicit folder is invalid.
- **FR-003**: A folder MUST be recorded as used after a successful pick from that folder, including a dry-run pick, and MUST NOT be recorded merely from typing, browsing, or rejecting an invalid path.
- **FR-004**: Remembered locations MUST persist across application restarts and MUST be shared between the terminal UI and web UI.
- **FR-005**: The application MUST maintain an ordered list of at most ten unique recently used folders, most recent first, with reuse moving a folder to the top rather than duplicating it.
- **FR-006**: Both interactive interfaces MUST expose the recent folders as a selectable list that activates a chosen folder without requiring the person to type its path.
- **FR-007**: The recent-folder list MUST be keyboard-operable, identify each folder unambiguously with its full path available, provide visible focus, and give each entry an accessible name containing its full path.
- **FR-008**: The application MUST provide an action to remove one remembered folder and an action to clear all remembered folders; both actions MUST take effect for subsequent launches and MUST NOT change the active target of a running session.
- **FR-009**: Removing or clearing remembered folders MUST NOT modify history, filters, the current choice, target files, or target folders.
- **FR-010**: A remembered folder that is missing, is not a folder, or cannot be read MUST NOT block startup or picking; the application MUST skip it, use the next valid recent folder when one exists, otherwise fall back to today's default behavior, explain the outcome without an error dialog, and prune the stale location.
- **FR-011**: Failure to read or write remembered locations MUST NOT prevent a pick; the application MUST remain usable and show a non-blocking notice that the path could not be remembered.
- **FR-012**: Remembered state MUST contain only local folder paths and the information needed to order them; it MUST NOT contain file names, history entries, filter selections, telemetry, or any data sent over a network.
- **FR-013**: Remembering a folder MUST NOT restore session-only filters, the previous choice, previews, or history from an earlier session.
- **FR-014**: Equivalent path spellings for the same folder MUST be recognized as one remembered location and MUST NOT create duplicate recent entries.
- **FR-015**: Concurrent terminal UI and web UI sessions MUST update remembered locations without corrupting or losing the remembered list; the most recent successful pick determines the last used folder.
- **FR-016**: The one-shot command-line interface MUST keep its existing behavior, flags, and exit codes; this feature does not add a CLI path-memory flag or change non-interactive output.
- **FR-017**: A fresh installation or a cleared memory MUST behave exactly like today, with no remembered path and no additional startup friction.

### Key Entities

- **Remembered Location**: One folder the person has successfully picked from, identified by its folder path and its recency relative to other remembered folders.
- **Recent Locations List**: An ordered, duplicate-free collection of at most ten remembered locations, newest first, shared by the interactive interfaces.
- **Path Memory Record**: The local, user-scoped record that holds the recent locations list and its ordering; it is separate from target folders and from history logs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of scripted launches without an explicit folder, the most recently used valid folder is restored as the active target in both interactive interfaces.
- **SC-002**: A returning person reaches a pick-ready state without typing a path, reducing the setup to at most one launch action per session.
- **SC-003**: The recent list contains at most ten unique folders and orders them by most recent use with 100% accuracy across scripted add, reuse, and eviction checks.
- **SC-004**: Clearing remembered folders removes 100% of stored locations, and the following launch behaves identically to a first run.
- **SC-005**: Remembering, selecting, or clearing a folder produces zero changes to target files, folder structures, history entries, or active filters.
- **SC-006**: An unavailable or unreadable remembered folder never produces a startup failure or blocked pick in scripted checks; the app skips it, uses the next valid recent folder when available, otherwise falls back and remains usable.
- **SC-007**: No remembered path data leaves the local machine, and the stored record contains no file names, history, or filter selections.
- **SC-008**: A person can remove one remembered folder or clear all of them in a single action from either interactive interface.
- **SC-009**: Remembering adds no more than one second to the time needed to reach a usable interface on the reference machine.

## Assumptions

- "Path" means the target folder being chosen from, not the history log path or an individual file. Log-file memory is out of scope.
- The feature applies to the terminal UI and web UI. The one-shot CLI remains unchanged so its public flags, prompt, output, and exit codes are preserved.
- A folder counts as used only after a successful pick. Merely browsing to a folder, loading its state, or attempting a pick that returns no item does not change the remembered folder.
- Dry-run picks count as successful use because the person did choose from that folder; they still write nothing to history.
- Ten recent folders is a reasonable default cap; it keeps the list scannable without becoming a general bookmark manager.
- The remembered record lives in a user-scoped location appropriate to the operating system, outside target folders, and is local-only.
- The record's storage location may be overridden through a local setting for portable setups and tests; this is not a CLI flag and does not change the one-shot CLI.
- Path data is shared across both interactive interfaces on the same machine and is not synchronized between machines or user accounts.
- Explicit paths always override memory, and the existing invalid-path outcome is preserved rather than replaced by a fallback.
- No new runtime service, network feature, or telemetry is introduced.
- Existing users keep today's behavior until their first successful pick after upgrading.

## Dependencies

- The project constitution currently limits persistent state to the history log and its archives. This feature introduces a small user-scoped path-memory record, so the constitution must be amended to permit that persistent state before implementation, or the feature must be deferred.
