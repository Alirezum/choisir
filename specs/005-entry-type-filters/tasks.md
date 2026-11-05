# Tasks: File-Type and Entry Filters

**Input**: Design documents from `/specs/005-entry-type-filters/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/filter-api.md`, `contracts/filter-ui.md`, `quickstart.md`

**Tests**: Included. The project constitution requires tests for every behavior
change, so test tasks are part of each phase even though the generic template
marks them optional.

**Organization**: Tasks are grouped by user story. Setup and foundational work
build the shared filter core, API, and frontend state units. User Story 1 then
delivers the type-filter MVP, User Story 2 adds per-entry control, and User
Story 3 completes the summary, reset, truncation, and accessibility layer.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete
  tasks).
- **[Story]**: Maps to `spec.md` stories: `US1` (type filters), `US2` (entry
  filters), `US3` (understand/reset/trust).
- Every task names an exact file path or an existing repository path.

## Path Conventions

- Python package: `choosier/`
- Python tests: `tests/`
- Frontend source: `frontend/src/`
- Frontend tests: `frontend/tests/`
- Feature artifacts: `specs/005-entry-type-filters/`
- API contract: `specs/001-standardize-api-responses/contracts/`

## Naming Contract

Use these names consistently; they are part of the tested contract.

- Existing folder options: `FolderFlags` type and `folderFlags` computed in
  `frontend/src/types.ts`, `frontend/src/view-models.ts`, and
  `frontend/src/state/use-folder-options.ts`. The old names `FilterSelection`
  and `filters` for these flags must be removed.
- New exclusions: `FilterExclusions` with `excluded_types` and
  `excluded_entries` arrays.
- New frontend state unit: `useFilters` / `FilterBinding` in
  `frontend/src/state/use-filters.ts`.
- Exposed view model: `filterPanel: ComputedRef<FilterPanelModel>`, never
  `filters`.
- State binding: `Ref<FilteredStateResponse | null>`, never `StateResponse`.
- Pick body: `PickRequest` gains optional `excluded_types` and
  `excluded_entries`; existing fields stay required/optional exactly as they
  are today.
- Reconciliation: `known_entry_exclusions` is the server-reported sorted subset
  of requested entry names that still match current candidates, including
  entries outside the 1,000-entry checklist cap.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature branch and a green baseline before changing
code. This is an existing project, so there is no project scaffold to create.

- [x] T001 Confirm the active branch is `005-entry-type-filters` and install the
  development, UI, and web extras declared in `pyproject.toml` plus the
  frontend dependencies in `frontend/package.json`.

- [x] T002 Run the baseline Python and frontend checks using `tests/` and the
  scripts in `frontend/package.json` (`uv run pytest`, `npm run test:api`,
  `npm run test:ui`, `npm run check:ui`), and record the current pass counts
  before any feature change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared filter core, service outcomes, additive API, and frontend
state units. No user story can be completed until this phase is done.

**⚠️ CRITICAL**: User Story phases depend on this work. Tests in this phase
cover shared behavior used by all three stories.

### Core Filter Tests

- [x] T003 [P] Create `tests/test_filters.py` covering canonical type keys
  (`dir`, `file:<suffix>`, `file:`), case-insensitive final `Path.suffix`,
  suffixless files, folders as one type, labels (`Folders`, `<suffix> files`,
  `Files without an extension`), display order, counts, `FilterSelection`
  intersection, sorted entry options, and `FILTER_ENTRY_LIMIT = 1000` with
  `entries_total` / `entries_truncated`. Add a 200-distinct-type fixture that
  asserts the type list is complete and ordered. Cover
  `normalize_exclusions()` success and every rejection in
  `contracts/filter-api.md` §5: `dir`, `file:`, `file:` plus a lowercased
  suffix, duplicates, unknown-but-well-formed values, invalid prefixes,
  `file:jpg`, `file:.`, uppercase `DIR`, entry `.`/`..`/empty, `/`, NUL,
  1,024-character boundaries, 2,000-type and 20,000-entry limits, and a
  backslash entry name.

- [x] T004 [P] Extend `tests/test_chooser.py` for one-scan candidate assembly,
  hidden/log-managed/files-only/dirs-only rules, filtered
  `list_available_items` and `get_unselected_item`, history subtraction,
  seeded reproducibility, and unchanged no-filter `empty`/`exhausted`
  behavior. Add the SC-001 100-pick type loop: with a mixed folder and two of
  at least five types checked, seeds `0..99` produce zero unchecked-type
  results.

### Core Implementation

- [x] T005 Implement `choosier/filters.py` with `FilterSelection`,
  `FilterValidationError`, `normalize_exclusions`, type-key and label helpers,
  `FilterTypeOption`, `FilterEntryOption`, `FilterOptions`,
  `build_filter_options`, and `filter_candidates`. Use the standard library
  only. Quote the validation constraints exactly as in
  `contracts/filter-api.md` §5: type keys `dir`, `file:`, or a dot-prefixed
  lowercased suffix; entry names non-empty, not `.`/`..`, no `/` or NUL;
  maximum 1,024 characters per value; maximum 2,000 type exclusions and 20,000
  entry exclusions, checked before deduplication. Types are complete, entries
  are sorted and capped at `FILTER_ENTRY_LIMIT = 1000`, and
  `types`/`entries_total` counts come from base candidates before filters and
  history.

- [x] T006 Update `choosier/chooser.py` with one `scan_candidates` pass that
  applies the existing hidden, log-managed, files-only, and dirs-only rules;
  expose whether the folder has children; make `list_candidates` delegate;
  and make `list_available_items` / `get_unselected_item` accept
  `FilterSelection` while preserving sorted seeded selection. The scan must
  expose the complete base-candidate names needed for
  `known_entry_exclusions` without adding a second directory scan.

### Service Tests

- [x] T007 [P] Extend `tests/test_services_state.py` for
  `StateSnapshot.filter_options`, filtered `remaining`/`remaining_total`,
  complete type counts before history subtraction, the 1,000-entry cap,
  invalid paths returning empty filter options and empty
  `known_entry_exclusions`, ignored stale exclusions,
  `known_entry_exclusions` matching an entry outside the visible cap, and
  unchanged existing state fields.

- [x] T008 [P] Extend `tests/test_services_pick.py` for the full outcome matrix:
  `empty`, `exhausted`, `filtered_empty`, `filtered_exhausted`, `picked`,
  `invalid_path`; no history writes for filtered outcomes; dry-run behavior;
  preserved hidden-only `exhausted` behavior; unchanged history on failure;
  and the SC-004 100-pick entry loop with unchecked entries.

### Service Implementation

- [x] T009 Update `choosier/services/models.py` to add
  `StateSnapshot.filter_options: FilterOptions` and
  `StateSnapshot.known_entry_exclusions: tuple[str, ...]`, and extend
  `PickStatus` with `"filtered_empty"` and `"filtered_exhausted"`; keep every
  existing field and default unchanged.

- [x] T010 Update `choosier/services/state.py` to accept a
  `FilterSelection`, use the shared scan once, return filtered remaining and
  totals, build complete filter options, compute `known_entry_exclusions`
  against all base candidates, and return empty options and empty known
  exclusions for an invalid path; keep `PANEL_MAX_LINES = 200`.

- [x] T011 Update `choosier/services/pick.py` to accept a `FilterSelection` and
  classify outcomes in the documented order: `invalid_path` → `empty` (no
  folder children) → `exhausted` (no base candidate) → `filtered_empty` (no
  filtered candidate) → `filtered_exhausted` (no remaining and filters removed
  at least one candidate) → `exhausted` (no remaining and filters removed
  nothing) → `picked`. Non-picked outcomes must not write history.

### API Contract and Boundary Tests

- [x] T012 [P] Update `tests/test_services_boundaries.py` to allow
  `choosier.filters` as a core module for services, add `state_filtered` →
  `services.build_state` to route delegation coverage, and keep the existing
  no-UI/no-web import assertions.

- [x] T013 [P] Extend `tests/test_api_contract.py` for the additive
  `POST /api/state` route, `FilterTypeOption` / `FilterEntryOption` /
  `FilterOptions` schemas, `known_entry_exclusions`, expanded pick
  request/status enum, the 13-route inventory, and an unchanged
  `GET /api/state` shape.

- [x] T014 [P] Extend `tests/test_api_errors.py` for every 422 case in
  `contracts/filter-api.md` §5: malformed type keys, malformed entry names,
  NUL, 1,024-character boundaries, 2,000/20,000 list limits, and duplicate
  handling; 400 conflicting folder options; and the existing error-envelope
  invariants. Assert the 422 message identifies `excluded_types` or
  `excluded_entries`.

### API Contract Artifacts and Web Service

- [x] T015 [P] Update `specs/001-standardize-api-responses/contracts/api-contract.json`
  with `POST /api/state`, the three filter schemas,
  `known_entry_exclusions`, pick request fields, and the expanded status enum.
  The route inventory becomes 13.

- [x] T016 [P] Update
  `specs/001-standardize-api-responses/contracts/api-contract.md` with the new
  route, fields including `known_entry_exclusions`, statuses, examples,
  validation ownership, compatibility rules, and migration note.

- [x] T017 Update `frontend/scripts/generate-api-contract.mjs` so
  `POST /api/state` maps to `FilteredStateResponse`, then run
  `npm run generate:api` to regenerate
  `frontend/src/api-contract.generated.ts` with the new schemas, route, and
  `known_entry_exclusions` field.

- [x] T018 [P] Extend `tests/test_web.py` for POST state with exclusions,
  `filter_options` and `known_entry_exclusions` in the response, unchanged GET
  state, filtered pick statuses without history writes, invalid-path filter
  state, and stale exclusions that match nothing.

- [x] T019 Update `choosier/web.py` with `FilterTypeOptionModel`,
  `FilterEntryOptionModel`, `FilterOptionsModel`, `StateRequest`, and
  `FilteredStateResponse`; add the POST `state_filtered` handler. Add
  `excluded_types` / `excluded_entries` to `PickRequest`, extend the pick
  status literal, and add Pydantic validators that call
  `choosier.filters.normalize_exclusions` and pass the normalized
  `FilterSelection` to services. Do not duplicate validation rules in the
  route or services.

### Frontend API Foundation

- [x] T020 [P] Update `frontend/tests/api-contract.test.mjs` from 12 to 13
  routes and operations, add a `stateFiltered` method/path/body test, and keep
  the existing `api.state` GET assertions unchanged.

- [x] T021 [P] Update `frontend/src/types.ts` with `FolderFlags` (moved from
  the old `FilterSelection`), `FilterExclusions`, `FilteredStateRequest`, and
  re-exports of `FilterTypeOption`, `FilterEntryOption`, `FilterOptions`, and
  `FilteredStateResponse`; add optional `excluded_types` /
  `excluded_entries` to `PickRequest` while keeping `StateQuery` and
  `StateResponse` for the unchanged GET. Do not create a type-only import
  cycle with `view-models.ts`.

- [x] T022 [P] Update `frontend/src/view-models.ts` with `FilterEntryRow` and
  `FilterPanelModel` (`ready`, `validPath`, `empty`, `eligibleEntries`,
  `types`, `entries`, `checkedTypeKeys`, `checkedEntryNames`, `active`,
  `summary`, `entriesTotal`, `entriesTruncated`); import `FolderFlags` from
  `types.ts`; change `WorkspaceBinding.state` to
  `Ref<FilteredStateResponse | null>`; and add `filterPanel` plus the seven
  filter actions.

- [x] T023 [P] Update `frontend/src/api-operations.ts` with
  `stateFiltered: 'POST /api/state'` and `frontend/src/api.ts` with a
  `stateFiltered(body: FilteredStateRequest)` method using the existing JSON
  POST helper; keep `state` as the GET operation.

- [x] T024 [P] Update `frontend/tests/ui/test-helpers.ts` so `ApiMock` includes
  `stateFiltered`, and add a `FilteredStateResponse` fixture with
  `filter_options` and `known_entry_exclusions`; keep the existing
  `StateResponse` fixture for GET tests.

- [x] T025 Rename the existing frontend folder-flag concept in
  `frontend/src/state/use-folder-options.ts`,
  `frontend/src/state/use-workspace-state.ts`,
  `frontend/src/state/use-picker.ts`, `frontend/src/state/use-workspace.ts`,
  `frontend/src/state/use-bootstrap.ts` consumers, and the corresponding
  `frontend/tests/ui/state/*.test.ts` files: `FilterSelection` → `FolderFlags`
  and the computed `filters` → `folderFlags`. Do not change the wire fields
  `include_hidden`, `files_only`, or `dirs_only`.

### Frontend Filter State Unit

- [x] T026 [P] Create `frontend/tests/ui/state/use-filters.test.ts` covering
  default all-checked state, type/entry toggles, select-all/clear actions,
  reset on path/log change, reconciliation that prunes vanished type keys and
  entry names using `known_entry_exclusions`, preservation of an exclusion for
  a name outside the visible entry list, newly appearing options checked by
  default, revision changes, invalid-path panel state, and the exact summary
  strings from `contracts/filter-ui.md`.

- [x] T027 Implement `frontend/src/state/use-filters.ts` with sorted exclusion
  arrays, `revision`, cached options, `reconcile(options,
  knownEntryExclusions)`, `reset`, all toggle and select-all/clear actions,
  `panel(options, eligibleEntries, validPath)`, the documented summary
  pluralization, and `FilterPanelModel`. It must not import API or view
  modules.

- [x] T028 [P] Update `frontend/tests/ui/state/use-workspace-state.test.ts` to
  mock `api.stateFiltered`, assert the POST body merges `folderFlags` and
  exclusions, use a `FilteredStateResponse` state binding, cover the 250 ms
  debounce, discard out-of-order responses, call `onState` with the response,
  and clear state for a blank path.

- [x] T029 Update `frontend/src/state/use-workspace-state.ts` to type `state`
  as `FilteredStateResponse | null`, call `api.stateFiltered`, watch
  `folderFlags` and `filterExclusions`, add a monotonic request number, ignore
  stale responses/errors, and invoke `onState(response)` / `onState(null)` for
  composition reconciliation.

- [x] T030 [P] Update `frontend/tests/ui/state/use-picker.test.ts` for the
  merged folder-flag plus exclusion pick body, `filtered_empty` /
  `filtered_exhausted` messages, no choice change on filtered outcomes, and
  stale pick results discarded when the filter revision or path changes.

- [x] T031 Update `frontend/src/state/use-picker.ts` to include
  `folderFlags` and exclusions, capture the filter revision and path before the
  request, discard stale results, and add the exact filtered status messages
  from `contracts/filter-ui.md`; leave existing statuses and text unchanged.

- [x] T032 [P] Update `frontend/tests/ui/state/use-workspace.test.ts` for the
  filter unit wiring, path/log resets, `filterPanel` composition, the seven
  filter actions, and current-choice behavior; keep existing
  history/browser/tab coverage.

- [x] T033 Update `frontend/src/state/use-workspace.ts` to create
  `useFilters` before `useWorkspaceState`, pass `folderFlags` and
  `filterExclusions` plus `onState` reconciliation with
  `known_entry_exclusions`, call `filterState.reset()` in path/log reset
  callbacks, expose the computed `filterPanel`, and return all filter actions.

- [x] T034 [P] Update `frontend/tests/ui/state/use-bootstrap.test.ts` to mock
  `api.stateFiltered` with a `FilteredStateResponse`, so the initial refresh
  path continues to work without the legacy GET call.

**Checkpoint**: Shared core, services, API, generated client, and frontend
state units are complete. User Story 1 can now be implemented independently.

---

## Phase 3: User Story 1 - Narrow picks by file type (Priority: P1) 🎯 MVP

**Goal**: A person can open the options area, see every exact type present,
uncheck types, and have picks, remaining entries, and counts stay inside the
checked types.

**Independent Test**: Prepare a folder with several file types, a suffixless
file, and a folder. Check only two types, make repeated seeded picks, and
verify no pick/remaining/count comes from another type. Exhaust the checked
types and verify filtered exhaustion; restore the full pool by re-checking the
types.

### Tests for User Story 1

- [x] T035 [P] [US1] Extend `tests/test_tui.py` with type-filter coverage:
  type option prompts/counts, unchecking a type changes the exclusions passed
  to `build_state`/`pick`, Remaining contains only checked types, filtered
  exhaustion is reported, hidden/mode changes reconcile options, path/log
  scope changes clear type exclusions, the `options-tab` activation rebuilds
  the lists, and `Input.Changed` resets the scope. Use `ChooserApp.run_test()`
  where widget behavior is asserted.

- [x] T036 [P] [US1] Extend `frontend/tests/ui/views/OptionsPanel.test.ts`
  with type-list rendering, checked states, `toggleType` emits, and
  `selectAllTypes` / `clearTypes` emits; keep the existing option-control
  tests passing.

- [x] T037 [P] [US1] Extend `frontend/tests/ui/state/use-workspace.test.ts`
  with type-filter model assertions: option types/counts, checked type keys,
  and the type actions reaching `useFilters`.

### Implementation for User Story 1

- [x] T038 [US1] Update `choosier/tui.py` with the type-filter state used by
  the Options tab: `_excluded_types`, `_filter_options`,
  `_known_entry_exclusions`, `_filter_scope`, `_sync_filter_scope`,
  reconciliation that preserves existing keys and uses
  `known_entry_exclusions`, and passing the type selection into
  `build_state` and `pick`. Add explicit event handlers for
  `Checkbox.Changed` on `#include-hidden`, `RadioSet.Changed` on `#mode`, and
  `Input.Changed` on `#path-input`/`#log-input`; include `options-tab` in
  `on_tabbed_content_tab_activated`. Keep entry exclusions empty until US2.

- [x] T039 [US1] Add the type control to `choosier/tui.py`: a bounded
  `SelectionList` (`id="type-filter"`) with `"{label} ({count})"` prompts,
  `types-all` / `types-none` buttons, guarded rebuilds that do not emit
  feedback events, and filtered status messages for
  `filtered_empty` / `filtered_exhausted`. Use `Text` or
  `rich.markup.escape` so bracket-containing names render literally. Keep the
  existing Options layout and keyboard focus behavior.

- [x] T040 [US1] Add the type section to `frontend/src/views/OptionsPanel.vue`
  and its bounded-list styles to `frontend/src/styles.css`: a `filterPanel`
  prop from `FilterPanelModel`, a native `fieldset`/`legend`, checkbox rows
  with labels and counts, `toggleType`, `selectAllTypes`, and `clearTypes`
  emits. Reuse the existing graphite/Archivo/amber visual language; do not add
  a new palette or font. Follow the `frontend-design` skill for the visual
  review.

- [x] T041 [US1] Wire type filtering in `frontend/src/App.vue`: destructure
  `filterPanel` plus the type actions from `useWorkspace`, pass the model to
  `OptionsPanel`, and forward the type events. Leave entry and summary markup
  for US2/US3.

**Checkpoint**: Type filtering works independently in the TUI and web UI. The
MVP is demonstrable without the entry checklist or the full summary/reset
layer.

---

## Phase 4: User Story 2 - Choose exact eligible entries (Priority: P2)

**Goal**: The same options area lists every visible eligible entry with a
checkbox so a person can exclude one noisy file, keep a handful of favorites,
or clear/select the visible list. Type and entry filters combine by
intersection.

**Independent Test**: In a folder of at least five entries, uncheck two
entries and make repeated picks; neither excluded entry is picked or shown as
remaining. Re-check one and verify it becomes eligible unless it is already in
history. Uncheck an entry whose type is checked and verify the type filter
still includes its siblings.

### Tests for User Story 2

- [x] T042 [P] [US2] Extend `tests/test_tui.py` with entry-filter coverage:
  entry prompts include names and type labels, bracket-containing names render
  literally, unchecking an entry changes the exclusions passed to
  `build_state`/`pick`, type and entry exclusions intersect, re-checking
  restores eligibility unless logged, `entries-all` / `entries-none` affect
  visible entries, and an entry outside the visible cap keeps its exclusion
  through `known_entry_exclusions` even after a visible entry is toggled.

- [x] T043 [P] [US2] Extend `frontend/tests/ui/views/OptionsPanel.test.ts` with
  the entry list: checked states, `toggleEntry`, `selectAllEntries`,
  `clearEntries`, type labels, and long-name rendering. Keep the US1 type
  tests passing.

- [x] T044 [P] [US2] Extend `frontend/tests/ui/state/use-workspace.test.ts`
  with entry-filter model assertions: entry rows with joined type labels,
  checked entry names, and entry actions reaching `useFilters` without
  changing type exclusions.

### Implementation for User Story 2

- [x] T045 [US2] Update `choosier/tui.py` with entry exclusions and scope
  handling: `_excluded_entries`, reconciliation against
  `known_entry_exclusions` (not the visible list alone), entry selection in
  `build_state`/`pick`, an `entry-filter` `SelectionList`,
  `entries-all` / `entries-none` buttons, and `SelectedChanged` handling that
  updates only visible names while preserving exclusions for names outside the
  visible cap, without destroying the focused list.

- [x] T046 [US2] Add the entry section to
  `frontend/src/views/OptionsPanel.vue` and its styles to
  `frontend/src/styles.css`: a second `fieldset`/`legend`, checkbox rows with
  exact names and quiet type labels, `toggleEntry`, `selectAllEntries`, and
  `clearEntries` emits. Keep the type list independent from entry exclusions.
  Follow the `frontend-design` skill for the visual review.

- [x] T047 [US2] Wire entry filtering in `frontend/src/App.vue`: destructure
  and bind `toggleFilterEntry`, `selectAllFilterEntries`, and
  `clearFilterEntries` to `OptionsPanel`. Keep the US1 type bindings intact.

**Checkpoint**: Type and entry filters both work in both interactive
interfaces, and their intersection is authoritative. US1 remains functional
without US2.

---

## Phase 5: User Story 3 - Understand, reset, and trust the filter (Priority: P3)

**Goal**: The options area shows an active-filter summary, offers one Clear
filters action, states when the entry list is bounded, distinguishes
filtered-empty from filtered-exhausted, and is fully keyboard/assistive
operable.

**Independent Test**: Apply a filter that matches nothing, attempt a pick,
and verify a distinct explanation with no log write. Clear filters and verify
the full pool and history are intact. Change folders/logs and verify filters
reset while the current choice follows the documented per-interface behavior.
Navigate every control with only the keyboard.

### Tests for User Story 3

- [x] T048 [P] [US3] Extend `tests/test_tui.py` with summary/reset/truncation
  coverage: exact summary/states including invalid path and history-aware
  `remaining_total`, Clear filters clearing both sets, the bounded notice,
  folder/log scope reset, TUI current-choice preservation on path and log
  changes, and keyboard labels/focus for all controls.

- [x] T049 [P] [US3] Extend `frontend/tests/ui/views/OptionsPanel.test.ts` with
  the summary line, Clear filters enabled/disabled state, truncation notice,
  invalid-path state distinct from the empty state, `aria-describedby` wiring,
  keyboard semantics, and `clearFilters` emit.

- [x] T050 [P] [US3] Add frontend acceptance tests in
  `frontend/tests/ui/state/use-picker.test.ts` and
  `frontend/tests/ui/state/use-workspace.test.ts` for filtered-empty and
  filtered-exhausted wording, scope reset, and current-choice preservation
  when filters change.

### Implementation for User Story 3

- [x] T051 [US3] Add the TUI summary line, `clear-filters` button, and
  truncation notice to the Options tab in `choosier/tui.py`; use
  `snapshot.remaining_total` and `filter_options.entries_total` for the same
  counts as the web model, ensure Clear filters is always reachable when
  filters are active, and preserve existing focus order and visible focus.

- [x] T052 [US3] Add the summary line, global Clear filters button, truncation
  notice, invalid-path/empty/not-ready states, `aria-live`/`aria-describedby`,
  and disabled states to `frontend/src/views/OptionsPanel.vue` and
  `frontend/src/styles.css`; ensure the focus order from
  `contracts/filter-ui.md` and the existing `:focus-visible` treatment.
  Follow the `frontend-design` skill for the visual review.

- [x] T053 [US3] Verify the documented surface-specific filtered-outcome
  messages in `frontend/src/state/use-picker.ts` (web status bar) and
  `choosier/tui.py`; do not unify their wording. Confirm
  `frontend/src/views/OptionsPanel.vue` shows the summary, invalid-path/empty
  states, and Clear filters action rather than pick-outcome text. Verify no
  path suggests an empty folder or deletes history.

**Checkpoint**: All three stories work together. A keyboard-only person can
filter, understand, reset, and trust the result, and a filtered-empty attempt
writes nothing.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, full gates, and end-to-end validation.

- [x] T054 [P] Update `README.md` with the filter menu, session-scope rules,
  entry bound, type target, `known_entry_exclusions`, new API route, and the
  13-route inventory.

- [x] T055 [P] Update `CHANGELOG.md` with the type/entry filter capability,
  additive `POST /api/state`, new statuses, and the user-visible behavior.

- [x] T056 Run the frontend gate from `frontend/package.json`:
  `npm run check:api`, `npm run test:api`, `npm run check:ui`,
  `npm run test:ui`, and `npm run build`; fix any route inventory, boundary,
  type, or test regressions.

- [x] T057 Run the full Python gate from `pyproject.toml`:
  `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run mypy choosier main.py tests`. Confirm the existing CLI tests pass
  unchanged, so the one-shot CLI still has no filter flags. Re-run pytest after
  T056 because static-serving tests require the frontend build.

- [x] T058 Execute every validation scenario in `quickstart.md`, including the
  5,000-entry bounded-list check, the 200-type check, the 100-pick type and
  entry loops, `known_entry_exclusions` reconciliation, filtered-empty and
  filtered-exhausted flows, invalid-path state, and reset/current-choice
  behavior in both interfaces. Snapshot the fixture's files, folders, and
  history before and after filtering to confirm SC-005: zero user files or
  folder structures change and no history entry is added, removed, or
  rewritten by a filter action.

- [x] T059 Perform the final audit: confirm
  `specs/001-standardize-api-responses/contracts/api-contract.json` and
  `api-contract.md` are current, the generated client matches, no new runtime
  dependency was added, README/CHANGELOG are updated, the naming contract is
  followed, and the constitution gates still pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T002 depends on T001.
- **Foundational (Phase 2)**: Depends on Setup. Blocks all user stories.
- **User Stories (Phases 3–5)**: Depend on Foundational.
  - US1 has no dependency on US2/US3.
  - US2's core/API/state behavior is already foundational, but its UI
    increment builds on the filter section introduced by US1
    (`T038`–`T041`).
  - US3 builds on the controls from US1/US2.
- **Polish (Phase 6)**: Depends on all desired user stories.

### Within Each Story

- Tests are listed before implementation for the specific behavior.
- State/model changes precede service/endpoint changes.
- Core changes precede interface wiring.
- Each story ends with its checkpoint validation.

### Story Dependency Notes

- **US1 (P1)**: The MVP. It can be demonstrated after Phase 2 and
  T035–T041.
- **US2 (P2)**: Entry filtering is independently testable through the shared
  core/API/state units in Phase 2 even before its UI is added. The web/TUI
  entry controls extend the US1 filter section rather than replacing it.
- **US3 (P3)**: Requires US1 and US2 controls to show the full summary/reset
  experience. Its shared scope/reset/outcome logic is already in Phase 2.

### Foundational Ordering Notes

- T003/T004, T007/T008, T012–T016, T020–T024, and T026/T028/T030/T032/T034
  are independent files and can run in parallel where marked.
- T005 follows T003; T006 follows T005.
- T009 follows T007/T008; T010/T011 follow T009.
- T017 follows T015; T018 follows T015/T016; T019 follows T018.
- T025 must precede T028, T030, and T033 because those files consume
  `folderFlags`.
- T027 follows T026; T029 follows T028; T031 follows T030 and T027; T033
  follows T027, T029, and T031; T034 follows T029/T033.

### Parallel Opportunities

- Foundational tests: T003/T004, T007/T008, T012/T013/T014, T015/T016,
  T020/T021/T022/T024, T026/T028/T030/T032/T034 are independent files.
- Foundational code: T023/T024 are independent after T021; T027/T029/T031
  follow their tests; T033 follows T027/T029/T031/T032.
- US1: T035/T036/T037 can run together; then T038→T039 and T040→T041.
- US2: T042/T043/T044 can run together; then T045→T047 and T046→T047.
- US3: T048/T049/T050 can run together; then T051/T052→T053.

---

## Parallel Example: User Story 1

```bash
# Write the three independent test surfaces together:
Task: "Add TUI type-filter tests in tests/test_tui.py"
Task: "Add OptionsPanel type tests in frontend/tests/ui/views/OptionsPanel.test.ts"
Task: "Add type-model assertions in frontend/tests/ui/state/use-workspace.test.ts"

# Then implement the TUI and web type surfaces in parallel:
Task: "Add TUI type state in choosier/tui.py"
Task: "Add OptionsPanel type section in frontend/src/views/OptionsPanel.vue"
```

## Parallel Example: User Story 2

```bash
Task: "Add TUI entry-filter tests in tests/test_tui.py"
Task: "Add OptionsPanel entry tests in frontend/tests/ui/views/OptionsPanel.test.ts"
Task: "Add entry-model assertions in frontend/tests/ui/state/use-workspace.test.ts"
```

## Parallel Example: User Story 3

```bash
Task: "Add TUI summary/reset tests in tests/test_tui.py"
Task: "Add OptionsPanel summary/a11y tests in frontend/tests/ui/views/OptionsPanel.test.ts"
Task: "Add frontend filtered-outcome/reset tests in frontend/tests/ui/state/use-picker.test.ts and use-workspace.test.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (critical; blocks every story).
3. Complete Phase 3: User Story 1 (type filters).
4. **STOP and VALIDATE**: Run T035–T041, then use the quickstart type-filter
   scenario in both interfaces.
5. Demo the type-only MVP if ready.

### Incremental Delivery

1. Setup + Foundational → shared core/API/state ready.
2. US1 → type filtering → validate independently → demo (MVP).
3. US2 → entry filtering → validate type/entry intersection → demo.
4. US3 → summary/reset/outcomes/accessibility → validate the full experience.
5. Polish → docs and full gates.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 TUI type surface.
   - Developer B: US1 web type surface.
   - Developer C: shared test/docs cleanup in a separate file.
3. After US1, split US2 TUI/web entry surfaces; US3 tests can start in
   parallel because their state behavior is already foundational.
4. Integrate at each checkpoint and run the focused gates before moving on.

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies.
- The exact summary strings, status messages, and focus order live in
  `contracts/filter-ui.md`; implement them literally so tests are stable.
- Do not add a new runtime dependency or change the CLI.
- History is read-only in this feature except for the existing pick append.
- A filtered outcome never writes history, never changes the current choice,
  and never reports the folder as empty.
- The summary's eligible-entry count is the server's `remaining_total`; never
  derive it from `type.count` or the visible entry list.
- Entry reconciliation uses `known_entry_exclusions`; never prune against the
  capped visible list alone.
