# Feature Specification: File-Type and Entry Filters

**Feature Branch**: `005-entry-type-filters`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Add filter to due-track. - option for select type of file you want to random select - i want user can on a menu of options select the type of file its want to select random in the dir (show list of dir file in there and user can checkbox them )"

## Clarifications

### Session 2026-11-05

- Q: Which checkboxes should the filter menu offer? → A: Types and individual entries.
- Q: Which interfaces should provide the new filter menu? → A: Terminal UI and web UI.
- Q: How should the type checklist group the folder's contents? → A: Exact file types.
- Q: When the filter menu first opens for a folder, which entries should be checked? → A: All entries checked.
- Q: Should filter choices be remembered after the application closes? → A: No, session only.
- Q: What happens to the current choice when the folder or log changes? → A: Filters reset in both cases. The current choice keeps each interface's existing behavior: the web UI clears it on a folder change and preserves it on a log change; the TUI preserves it on both.
- Q: What do the summary counts mean? → A: The type count is checked types out of all present types. The entry count is the server-reported eligible total after filters and history, out of all base candidates. Counts therefore describe the pool a pick can use, not just the visible checklist.
- Q: How are entry exclusions handled when an entry moves outside the visible list? → A: They are preserved. The state response reports which requested entry exclusions still match current candidates, including entries outside the visible cap, and the client prunes only names that no longer exist.
- Q: Is the type checklist bounded like the entry checklist? → A: No. It is complete and expected to contain at most 200 distinct types; a folder with more types remains scrollable but is outside the two-second performance target.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Narrow picks by file type (Priority: P1)

A person opens a folder that mixes images, documents, and subfolders, but only wants the random picker to draw from certain kinds of content. In the options menu they see every type present in that folder, each with a checkbox, and they select the types they want. Every later pick, the remaining list, and the remaining count stay inside those types until the filters are changed.

**Why this priority**: Type filtering is the core request and the smallest useful slice. It immediately turns a mixed folder into a focused pool without touching history or files.

**Independent Test**: Prepare a folder containing several file types, a suffixless file, and a subfolder. Select only two file types, make repeated seeded picks, and verify that no pick, remaining entry, or count comes from another type. Clear the filter and verify the full pool returns apart from already logged items.

**Acceptance Scenarios**:

1. **Given** a folder with several present file types, **When** the person opens the filter menu, **Then** every present type is listed with a checkbox, the entry count for that type, and its current checked state.
2. **Given** all types checked by default, **When** the person unchecks all but one file type, **Then** the remaining list, remaining total, and every subsequent pick contain only entries of that type.
3. **Given** only one file type is checked, **When** repeated picks exhaust that type, **Then** the interface reports exhaustion for the filtered pool without claiming the whole folder has been picked.
4. **Given** a type filter is active, **When** the person picks with a seed, **Then** the result is reproducible from the folder, filter selection, seed, and existing history.
5. **Given** type names differ only by letter case, **When** the types are listed, **Then** they are treated as one case-insensitive type and are not picked inconsistently.
6. **Given** the existing hidden-file or files/folders options, **When** either changes, **Then** the type list reflects the newly eligible contents and the filter result stays consistent with those options.

---

### User Story 2 - Choose exact eligible entries (Priority: P2)

The same options menu lists the folder's entries with individual checkboxes. The person can exclude one noisy file, keep a handful of favorites, or select and clear the whole list, and the random picker will only ever choose from the checked entries.

**Why this priority**: Type filtering cannot express "everything except this one file" or "only these three items." Per-entry control completes the filtering request and works independently of which types are available.

**Independent Test**: In a folder of at least five entries, uncheck two entries and make repeated picks; verify neither excluded entry is ever picked nor shown as remaining. Re-check one and verify it becomes eligible again unless it is already in history.

**Acceptance Scenarios**:

1. **Given** the filter menu is open for a folder, **When** it renders the entry list, **Then** every entry eligible under the existing hidden and files/folders options appears with a checkbox, its type, and its checked state, up to the documented visible bound; when the list is bounded, the total and a truncation notice are shown.
2. **Given** every entry is checked by default, **When** the person unchecks entries, **Then** those entries disappear from the remaining pool and are never picked while unchecked.
3. **Given** a type is checked but one entry of that type is unchecked, **When** the person picks, **Then** the unchecked entry remains excluded; type and entry filters combine by intersection.
4. **Given** an entry was previously picked and is in history, **When** the person checks it again, **Then** it stays excluded by history and its log remains untouched.
5. **Given** a long entry list, **When** the person uses Select all or Clear selection, **Then** every visible entry is affected and the total count is shown accurately.
6. **Given** the person changes the target folder, **When** the new folder loads, **Then** the entry list is rebuilt for that folder and all filters return to their default checked state.

---

### User Story 3 - Understand, reset, and trust the filter (Priority: P3)

A person can tell at a glance whether a filter is active, why a pick returned nothing, and how to get back to the full folder. An empty filtered result is never confused with an empty folder or a fully picked folder, and clearing filters never damages history or the current choice.

**Why this priority**: A filter that silently hides outcomes or traps the person in an empty pool is worse than no filter. Clear state and a one-step reset make the capability safe to rely on.

**Independent Test**: Apply a filter that matches nothing, attempt a pick, and verify a distinct explanation and reset action appear with no log write. Then clear the filter and verify the original remaining pool and history are intact.

**Acceptance Scenarios**:

1. **Given** any active filter, **When** the options area is collapsed or the person returns to it, **Then** a summary of active type and entry filters is visible and a single Clear filters action restores the default checked state.
2. **Given** checked types and entries match no candidate, **When** the person attempts a pick, **Then** the interface explains that the filters exclude every entry, offers Clear filters, writes nothing to history, and does not report an empty folder or an exhausted folder.
3. **Given** every entry matching the filters is already logged, **When** the person attempts a pick, **Then** the interface reports filtered exhaustion and offers history reset or filter changes without deleting history.
4. **Given** a filter is active, **When** the person changes folders or the history log, **Then** filters reset to all checked. The current choice follows each interface's existing behavior: the web UI clears it on a folder change and preserves it on a log change; the TUI preserves it on both.
5. **Given** a current choice and history exist, **When** filters are applied or cleared, **Then** no history entry is added, removed, or rewritten, and the displayed choice remains available.
6. **Given** the filter menu in either interactive interface, **When** the person uses only the keyboard, **Then** every checkbox, Select all, Clear selection, and Clear filters action is reachable with visible focus and announced labels.

---

### Edge Cases

- The folder contains no entries at all: the existing empty-folder message appears, not the filtered-empty message.
- The folder has entries but no type or entry is checked: a filtered-empty outcome appears and no pick is logged.
- All entries of the checked types are already in history: the format reports filtered exhaustion, not an empty folder.
- A folder contains only folders, only suffixless files, or a mix of both: folders and suffixless files each get a stable, understandable type choice.
- Two files share a suffix with different case (`.JPG` and `.jpg`): they fall under one type.
- A file is added, removed, or renamed while the menu is open: the list refreshes; a removed name is pruned using the server-reported matched exclusions, a newly added entry is checked by default, and an exclusion for an entry outside the visible bound survives because the server still reports that name as present.
- A checked entry is deleted between filter selection and picking: the picker skips it and the state refreshes without logging a missing item.
- The folder is large (for example, thousands of entries, or up to 200 distinct types): the menu shows accurate totals and remains usable; the entry list is bounded at 1,000 with a stated notice, while the type list is complete and scrollable. Type filtering provides a way to narrow the entry list.
- The existing hidden-file, files-only, or folders-only option changes while filters are active: the available types and entries are recalculated against the new option.
- The history log is archived or cleared while filters are active: filters remain in effect, and newly re-eligible entries appear only if they are checked.
- The target folder and log file are handled independently: changing either one resets filters rather than carrying one folder's exclusions into another.
- A pick is in flight when filters change: the stale result does not replace the choice or the filtered pool.
- A filtered pick returns no item: no history write, no change to existing history, and no file or folder modification occurs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The filter menu MUST contain both a type checklist and an entry checklist, and MUST let a person restrict random selection to chosen types and chosen individual entries in the current folder, in addition to the existing hidden-file and files/folders options.
- **FR-002**: The type choices MUST be derived from the current folder after the existing hidden-file and files/folders options are applied, and MUST represent every distinct type present: each filename suffix compared case-insensitively, files without a suffix, and folders as one type-like choice when folders are currently eligible. These exact file types, not broad content categories, are the selectable units.
- **FR-003**: The type list MUST show, for each type, a checkbox, a human-readable label, and the number of current entries of that type.
- **FR-004**: Type choices MUST be multi-select, MUST start fully checked for a folder, and MUST treat unchecking a type as excluding every entry of that type from eligibility.
- **FR-005**: The entry list MUST show every current entry eligible under the existing hidden-file and files/folders options, up to the documented visible bound of 1,000 entries, with a checkbox, a type label, and its checked state; entries MUST start checked for a folder, and when the list is bounded the response MUST report the true total and a truncation flag.
- **FR-006**: The entry list MUST provide Select all and Clear selection for its visible entries, and the type list MUST provide equivalent select-all and clear actions plus one Clear filters action for both lists.
- **FR-007**: An entry MUST be eligible only when it passes the existing hidden-file and files/folders options, its type is checked, its own checkbox is checked, and it has not already been logged. The intersection MUST be authoritative; satisfying only some conditions is never enough.
- **FR-008**: A pick MUST choose only from eligible entries; excluded entries MUST never be returned, counted as remaining, or written to history.
- **FR-009**: The remaining list and remaining total MUST reflect the filtered pool and MUST update when a filter, folder option, or folder content changes.
- **FR-010**: Filters MUST NOT modify, move, rename, or delete user files or folders.
- **FR-011**: Filters MUST NOT add, remove, or rewrite history entries. Previously logged entries MUST remain in history and stay ineligible when re-included; excluding an entry MUST NOT delete its past log entries.
- **FR-012**: When filters leave no eligible entries while the folder contains entries, the interface MUST report a distinct filtered-empty outcome, MUST offer a way to clear the filters, and MUST NOT write history.
- **FR-013**: When every entry that matches the filters is already logged, the interface MUST report filtered exhaustion, distinct from an empty folder, and MUST NOT delete or alter history.
- **FR-014**: Filter state MUST be scoped to the current folder and the current session. Changing the target folder or history log MUST reset filters to fully checked, and filters MUST NOT persist across application restarts. The current choice keeps each interface's existing behavior: the web UI clears it on a folder change and preserves it on a log change; the TUI preserves it on both.
- **FR-015**: When folder contents or the existing folder options change, the type and entry lists MUST be recalculated. Selections for names that still exist MUST be preserved, including entries outside the visible entry bound; names that no longer exist MUST be pruned and have no effect; newly appearing entries and types MUST start checked. The state response MUST report the requested entry exclusions that still match current candidates so the client can reconcile without a complete unbounded listing.
- **FR-016**: Both interactive interfaces, the terminal UI and the web UI, MUST expose the filter menu in their existing options area, show an active-filter summary that reports checked types and server-eligible entries against base totals, and provide the Clear filters action.
- **FR-017**: The terminal UI and web UI MUST keep the remaining view, remaining total, pick outcome, and current choice consistent with the active filters. The one-shot CLI MUST continue to behave as it does today with its existing options; no new CLI filter flags are introduced in this feature.
- **FR-018**: Seeded picks MUST remain deterministic for the same folder contents, filter selection, history, and seed.
- **FR-019**: Dry-run behavior MUST remain unchanged: a filtered pick can be previewed without being logged, and the filter still applies.
- **FR-020**: Every filter control MUST be keyboard-operable with visible focus, an accessible label, and a checked state that assistive technology can announce.
- **FR-021**: Large folders MUST remain usable: accurate totals MUST be shown, the interface MUST state when the visible entry list is bounded at 1,000, and type filtering MUST remain available to narrow the list. The two-second opening target applies to folders with up to 5,000 entries and up to 200 distinct types; a folder with more types remains complete and scrollable but is outside that target.
- **FR-022**: Applying or clearing filters MUST preserve the current choice and preview. Changing the folder or log resets filters but MUST NOT introduce a new current-choice behavior: the web UI clears the choice on a folder change and preserves it on a log change; the TUI preserves it on both.
- **FR-023**: The implementation MUST NOT change the history format, file naming, archiving behavior, privacy guarantees, or existing public interface contracts beyond additive filter capability.

### Key Entities *(include if feature involves data)*

- **Filter selection**: The checked types and checked entries for the current folder, plus the session-scoped rule that determines whether each is eligible.
- **File type**: A stable, case-insensitive grouping of current folder entries by filename suffix, suffixless files, or folders.
- **Candidate entry**: One direct child of the target folder with a name, a type, and eligibility under the existing options, filters, and history.
- **Eligible pool**: The remaining unselected candidates after the hidden-file option, files/folders option, type filter, entry filter, and history are all applied; it drives picks, the remaining list, and counts.
- **Filtered outcome**: A pick result that distinguishes filtered-empty and filtered-exhausted states from an empty folder and ordinary exhaustion.
- **History**: The existing persistent record of picked items; filters never rewrite it, and its entries always remain ineligible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a mixed folder and a type filter selecting two of at least five types, 100 consecutive seeded picks return zero entries from any unchecked type.
- **SC-002**: After any filter, folder-option, or folder-content change, the remaining list and remaining total reflect the new eligible pool within one second in both interactive interfaces.
- **SC-003**: A person can narrow a folder to a single type in at most three interactions from the options area and can restore the full pool with one Clear filters action.
- **SC-004**: With individual entries unchecked, 100 consecutive seeded picks return zero unchecked entries, even when their types remain checked.
- **SC-005**: Applying and clearing filters changes zero history entries, zero user files, and zero folder structures in all tested flows.
- **SC-006**: A filtered-empty attempt and a filtered-exhausted attempt are each reported with their distinct explanation and next action in 100% of interactive-interface paths; neither writes history.
- **SC-007**: Every existing unfiltered flow, including seeded picks, dry runs, previews, openings, archive/clear, and history operations, continues to pass its current acceptance checks unchanged.
- **SC-008**: A folder with 5,000 entries and 200 distinct types opens the filter menu with accurate totals within two seconds and allows select-all, clear, and single-entry changes without freezing the interface.
- **SC-009**: A keyboard-only person can reach and operate every filter control, including reset, with visible focus and correct announced state in both interactive interfaces.
- **SC-010**: The same folder, filter selection, history, and seed always produce the same filtered pick sequence.

## Assumptions

- "due-track" refers to this chooser, and the request targets its interactive selection experience.
- A file type is the filename suffix compared case-insensitively; files without a suffix form one type. Content sniffing, MIME classification, and user-defined type groups are out of scope.
- Folders are represented as one type-like choice when folders are currently eligible, so type filtering does not silently exclude or include folders.
- Checked means eligible. Both lists start fully checked for a folder; unchecking is the way to restrict the pool.
- Existing hidden-file and files/folders options combine with the new filters rather than being replaced by them.
- The interactive terminal UI and web UI are both in scope because they already offer matching pick flows and an options area. The one-shot CLI remains on its current options in this feature; the selection rules stay interface-independent so it can adopt them later without behavior drift.
- Filters are session-scoped and folder-scoped; no saved presets, profiles, or cross-session persistence are introduced.
- Only direct children of the target folder are considered; recursive selection remains out of scope.
- The history log, its JSON Lines format, rotation, archiving, and clear behavior remain authoritative and unchanged.
- The exact wording and visual treatment of the filter menu are design decisions, but the filtered-empty and filtered-exhausted messages must remain distinct and actionable.
- The entry checklist is bounded at 1,000 entries. The cap and true total are stated, and the type checklist remains complete so type exclusions still remove all entries of that type, including entries outside the visible list. An entry exclusion that moves outside the visible list is preserved through the state response's matched-exclusion set; only names that no longer match any current candidate are pruned.
- The type checklist is complete and not separately capped. The design target is at most 200 distinct types per folder; a folder with more types still renders every type in a scrollable list, but it is outside the two-second performance target.
- Filtering changes only which existing candidates may be picked; it does not create, copy, move, or modify any file or folder.
- The current privacy guarantee remains: all filtering and selection happen locally, with no network requests, telemetry, or external service.
