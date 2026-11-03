# Tasks: Modular UI Components

**Input**: Design documents from `/specs/004-modular-ui-components/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: REQUIRED. The specification makes isolated tests a functional requirement
(FR-016), a success criterion (SC-004), and an accepted clarification. Write the
failing test first for every unit, view, and shared block, then implement it.

**Organization**: Tasks are grouped by user story. US1 delivers the state/workflow
extraction; US2 delivers presentation-only views; US3 adds enforcement and
documentation. US2 and US3 depend on the units and wiring delivered by US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`, `[US2]`, `[US3]` for story phases only
- Every task includes the exact file path(s) it changes or verifies

## Path Conventions

- Frontend root: `frontend/`
- Source: `frontend/src/`
- Tests: `frontend/tests/ui/` for Vitest; `frontend/tests/*.mjs` remains the Node runner
- Feature artifacts: `specs/004-modular-ui-components/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the development-only test runner, shared type/test scaffolding, and
the parity baseline before any behavior moves.

- [x] T001 Add `vitest@^5.1.0`, `@vue/test-utils@^2.5.1`, and `happy-dom@^21.0.4` to `devDependencies` in `frontend/package.json`, run `npm install` in `frontend/`, and commit the updated `frontend/package-lock.json`; do not change the runtime `dependencies` block.
- [x] T002 [P] Create `frontend/vitest.config.ts` using the Vue plugin, `environment: 'happy-dom'`, `include: ['tests/ui/**/*.test.ts']`, and `restoreMocks: true`.
- [x] T003 Update `frontend/package.json` with `"check:ui": "node scripts/check-ui-boundaries.mjs"` and `"test:ui": "vitest run"`, and add `vitest.config.ts` to the `include` list in `frontend/tsconfig.node.json` (depends on T001).
- [x] T004 [P] Create `frontend/src/view-models.ts` with the view-model interfaces, intent payload types, and workspace binding interface described in `data-model.md`; keep it type-only with no runtime logic.
- [x] T005 [P] Create `frontend/tests/ui/test-helpers.ts` with a minimal host-component mount helper, a deferred-promise helper, `flushPromises`, and shared API mock factories for state-unit tests.
- [x] T006 [P] Create `specs/004-modular-ui-components/parity-checklist.md` with the header, three viewport sections, flow matrix, message-class rows, five violation-trial slots, and sign-off fields required by `contracts/verification-contracts.md §5`.
- [x] T007 Capture the pre-refactor baseline on `main@d25abef`: run every flow in `contracts/verification-contracts.md §5.2` at desktop >900px, tablet 561–900px, and phone ≤560px, fill the baseline columns in `specs/004-modular-ui-components/parity-checklist.md`, and keep screenshots local (do not commit images).

**Checkpoint**: Test runner, shared types, test helpers, and baseline evidence are ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared presentation blocks and shared state units used by more than one
story.

**⚠️ CRITICAL**: Complete this phase before starting US1 or US2.

- [x] T008 [P] Write the failing test `frontend/tests/ui/components/EmptyState.test.ts`, then implement `frontend/src/components/EmptyState.vue` to own the `.panel-empty` presentation with a default slot and optional class; keep rendered text/styles unchanged.
- [x] T009 [P] Write the failing test `frontend/tests/ui/components/PanelShell.test.ts`, then implement `frontend/src/components/PanelShell.vue` with `headerClass` prop and `header`, default, and `actions` slots; render `.panel`, `.panel-header`, and `.panel-actions`, omit the action wrapper when the slot is absent, and allow root class fallthrough.
- [x] T010 [P] Write the failing test `frontend/tests/ui/state/use-status.test.ts`, then implement `frontend/src/state/use-status.ts` with the initial message `"Choose a folder, then press Pick."`, `setStatus`, and `reportError` using `apiErrorMessage`; exact strings and failure behavior must match the baseline.
- [x] T011 [P] Write the failing test `frontend/tests/ui/state/use-folder-options.test.ts`, then implement `frontend/src/state/use-folder-options.ts` with `path`, `logFile`, `seed`, `dryRun`, `includeHidden`, `mode`, the `filters` mapping (`include_hidden`, `files_only`, `dirs_only`), and `entryPath(item)` with trailing separator removal.
- [x] T012 [P] Write the failing test `frontend/tests/ui/state/use-choice.test.ts`, then implement `frontend/src/state/use-choice.ts` with the current choice, `pickSerial`, the monotonic preview serial, stale-response rejection, and `invalidate()`.
- [x] T013 [P] Create `frontend/tests/ui/README.md` documenting the two runners (`.mjs` Node tests vs `.ts` Vitest tests), the one-test-file-per-module rule, and the expected test path mapping.

**Checkpoint**: Shared blocks and shared units pass their isolated tests; US1 can begin.

---

## Phase 3: User Story 1 - One Owner per Web Workflow (Priority: P1) 🎯 MVP

**Goal**: Extract every app-level workflow into one named state/behavior unit and
reduce `App.vue` to a composition root. Browser and preview internals are converted
in US2; everything else must work identically after this phase.

**Independent Test**: Run the app and replay options, pick, preview-from-history,
open, archive, clear, single removal, batch removal, tabs, and Ctrl+N. Compare
outcomes/text with the baseline. Inspect `App.vue` and confirm it contains no data
access, validation, timers, watchers, computed state, or status derivation. Run
`npm run test:ui`, `npm run test:api`, and `npm run build`.

### Tests and implementation for User Story 1

- [x] T014 [P] [US1] Write the failing test `frontend/tests/ui/state/use-workspace-state.test.ts`, then implement `frontend/src/state/use-workspace-state.ts`: blank trimmed path sets state to null; successful `api.state` replaces state; failure uses the shared status error path; 250ms debounce; path/log callbacks; timer cleanup.
- [x] T015 [US1] Write the failing test `frontend/tests/ui/state/use-picker.test.ts`, then implement `frontend/src/state/use-picker.ts`: blank path and non-integer seed validation, `api.pick` with nullable log file and seed, `invalid_path`/`empty`/`exhausted` messages, logged vs dry-run text, choice/preview serial updates, `openEntry`/`openCurrent`, and refresh after pick (depends on T014).
- [x] T016 [P] [US1] Write the failing test `frontend/tests/ui/state/use-history-selection.test.ts`, then implement `frontend/src/state/use-history-selection.ts` with checked items, toggle, add-range, toggle-all, clear, and prune-missing; keep the anchor/shift interaction for US2.
- [x] T017 [US1] Write the failing test `frontend/tests/ui/state/use-history-actions.test.ts`, then implement `frontend/src/state/use-history-actions.ts`: archive, clear confirmation lifecycle, single and batch removal, busy guards, 0/1/many count messages, pending-delete copy, preview/open history item with stale guard, refresh and selection cleanup (depends on T015, T016).
- [x] T018 [P] [US1] Write the failing test `frontend/tests/ui/state/use-tabs.test.ts`, then implement `frontend/src/state/use-tabs.ts` with active tab, Remaining/History counts, ArrowLeft/Right wrap, Home/End, and focus movement to `#tab-<id>`.
- [x] T019 [P] [US1] Write the failing test `frontend/tests/ui/state/use-shortcuts.test.ts`, then implement `frontend/src/state/use-shortcuts.ts` with window Ctrl+N registration, the exact `clearing || .viewer-overlay/.overlay` block condition, and cleanup on unmount.
- [x] T020 [P] [US1] Write the failing test `frontend/tests/ui/state/use-bootstrap.test.ts`, then implement `frontend/src/state/use-bootstrap.ts`: load `api.defaults()`, assign path/log file, run the immediate refresh, preserve the existing watcher-triggered debounced refresh, and report defaults failure through the shared status path.
- [x] T021 [US1] Write the failing test `frontend/tests/ui/state/use-workspace.test.ts`, then implement `frontend/src/state/use-workspace.ts` as composition-only wiring: instantiate all US1 units, connect path/log reset callbacks (invalidate preview, clear choice/selection/pending confirmation), and return the binding surface; do not add validation, messages, API calls, or workflow rules (depends on T014–T020).
- [x] T022 [US1] Rewrite the `<script setup>` block of `frontend/src/App.vue` to use only `useWorkspace(...)`, template refs, and bindings; remove all direct API calls, watchers, computed state, timers, validation, confirmation logic, and status construction while preserving the existing template classes, layout, and view props (depends on T021).
- [x] T023 [US1] Run `npm run test:ui`, `npm run test:api`, and `npm run build` in `frontend/`; fix any regressions without changing visible behavior or exact strings.
- [ ] T024 [US1] Replay the US1 flow set (options, pick variants, preview-from-history, open, archive, clear, single/batch removal, tabs, Ctrl+N) and record the results in `specs/004-modular-ui-components/parity-checklist.md`; fix regressions before moving on.

**Checkpoint**: `App.vue` is a composition root for every workflow except the
browser and preview internals; US1 is independently functional.

---

## Phase 4: User Story 2 - Presentation Views Render, They Do Not Decide (Priority: P2)

**Goal**: Convert every visual area into a presentation-only view, add the two
view-local interaction units, introduce `PanelTabs`, and adopt the shared building
blocks without changing visuals or behavior.

**Independent Test**: Mount each view in isolation with fixed, empty, and boundary
data; confirm rendered text/classes/ARIA and emitted intents. Confirm by source
review that no view imports the API client or a domain state unit, and replay the
full interface at all three viewport ranges.

### Tests and implementation for User Story 2

- [ ] T025 [US2] Move `ChoiceBoard.vue`, `StatusBar.vue`, `OptionsPanel.vue`, `RemainingPanel.vue`, and `ConfirmDialog.vue` from `frontend/src/components/` to `frontend/src/views/`, update imports in `frontend/src/App.vue`, and add isolated tests `frontend/tests/ui/views/ChoiceBoard.test.ts`, `StatusBar.test.ts`, `OptionsPanel.test.ts`, `RemainingPanel.test.ts`, and `ConfirmDialog.test.ts`.
- [ ] T026 [P] [US2] Write the failing tests, then refactor `frontend/src/views/RemainingPanel.vue` to use `PanelShell` and `EmptyState` while preserving header, list, empty copy, and classes; update `frontend/tests/ui/views/RemainingPanel.test.ts`.
- [ ] T027 [P] [US2] Write the failing test, then refactor `frontend/src/views/OptionsPanel.vue` to use `PanelShell` with the existing `options-panel` class, labels, placeholders, and v-model fields; update `frontend/tests/ui/views/OptionsPanel.test.ts`.
- [ ] T028 [US2] Extend `frontend/src/state/use-history-selection.ts` with the anchor and shift-range behavior from `data-model.md`, update `frontend/tests/ui/state/use-history-selection.test.ts`, and expose the range intent through the workspace binding.
- [ ] T029 [US2] Refactor `frontend/src/views/HistoryPanel.vue` to presentation-only: receive entries/total/busy/selected/checked and derived labels, emit archive/clear/remove/open/select(item, shift)/toggleAll/removeSelected, remove local anchor/range logic, and use `PanelShell`/`EmptyState`; update `frontend/tests/ui/views/HistoryPanel.test.ts` (depends on T028).
- [ ] T030 [US2] Write the failing test `frontend/tests/ui/state/use-browser.test.ts`, implement `frontend/src/state/use-browser.ts` (immediate load, parent/child navigation, error, use-folder), convert `frontend/src/views/BrowserPanel.vue` to presentation-only with `PanelShell`, update `frontend/tests/ui/views/BrowserPanel.test.ts`, and wire the new bindings in `frontend/src/state/use-workspace.ts` and `frontend/src/App.vue`.
- [ ] T031 [US2] Write the failing test `frontend/tests/ui/state/use-preview.test.ts`, implement `frontend/src/state/use-preview.ts` with labels/meta/body/fallbacks, `src` (grid preview vs thumb) and `fullSrc` (viewer/original) media addresses, viewer index, and video error, then convert `frontend/src/views/PreviewPanel.vue`; update `frontend/tests/ui/views/PreviewPanel.test.ts`.
- [ ] T032 [US2] Write the failing test `frontend/tests/ui/state/use-image-viewer.test.ts`, implement `frontend/src/state/use-image-viewer.ts` with index wrap, zoom levels/limits, clamp, double-click, wheel/pointer/keyboard handling, preload, and body scroll lock, then convert `frontend/src/views/ImageViewer.vue` to use `fullSrc`; update `frontend/tests/ui/views/ImageViewer.test.ts`.
- [ ] T033 [US2] Create `frontend/src/views/PanelTabs.vue` + `frontend/tests/ui/views/PanelTabs.test.ts` with tab roles, ARIA selected/controls, roving tabindex, counts, and select/keydown intents; replace the inline tab strip in `frontend/src/App.vue` with this view.
- [ ] T034 [US2] Finalize `frontend/src/state/use-workspace.ts` and the `frontend/src/App.vue` template for all converted views: pass complete view models, bind intents, render dialogs from history state, and remove any stale props/imports; keep layout/classes unchanged.
- [ ] T035 [US2] Run `npm run test:ui` and `npm run build` in `frontend/`; fix view/unit regressions and confirm every view has a matching test file.
- [ ] T036 [US2] Replay the full interface at desktop >900px, tablet 561–900px, and phone ≤560px; update every flow/message/keyboard row in `specs/004-modular-ui-components/parity-checklist.md` and capture before/after screenshots locally.
- [ ] T037 [US2] Extend `frontend/tests/ui/state/use-workspace.test.ts` with integration coverage for path/log resets, defaults, debounce, stale previews, browser/preview bindings, and confirmation lifecycle.
- [ ] T038 [US2] Run a source audit with `rg` for `api`, `fetch`, `/api/`, `watch(`, `computed(`, `setTimeout`, and `panel-header|panel-empty|panel-actions` under `frontend/src/views/`; fix every violation before marking US2 complete.

**Checkpoint**: Every visual area is presentation-only, each view has an isolated
test, and the full interface is visually and behaviorally unchanged at all three
ranges.

---

## Phase 5: User Story 3 - Modular Boundaries Stay Enforced (Priority: P3)

**Goal**: Add the automated boundary script, self-tests, CI gates, five violation
trials, and maintainer documentation so the monolith cannot return.

**Independent Test**: Add each of the five deliberate violations from
`contracts/verification-contracts.md §4`, confirm the expected rule fails, restore
the tree, and confirm all checks pass. Run the full frontend gate.

### Tests and implementation for User Story 3

- [ ] T039 [US3] Implement `frontend/scripts/check-ui-boundaries.mjs` with rules R-01 through R-07 from `contracts/verification-contracts.md`: view API isolation, view state allowlist, state isolation, composition-root thinness, acyclic graph, shared-scaffold tokens, and test-file mapping; export pure helpers and fail closed on unreadable/unresolved files.
- [ ] T040 [US3] Create `frontend/tests/ui/boundary-check.test.ts` with failing and passing fixtures for each of R-01–R-07, including the two allowlisted view→unit imports and the missing-test-file case (depends on T039).
- [ ] T041 [US3] Add `Check UI boundaries` (`npm run check:ui`) and `Test UI` (`npm run test:ui`) steps to `.github/workflows/ci.yml` after `Test API client` and before `Build frontend`.
- [ ] T042 [US3] Run the five violation trials from `contracts/verification-contracts.md §4` against `frontend/scripts/check-ui-boundaries.mjs`, restore the tree after each trial, and record the detected rule/file in `specs/004-modular-ui-components/parity-checklist.md`.
- [ ] T043 [P] [US3] Update `frontend/README.md` with the `state/` → `views/` → `components/` layer model, allowed dependency direction, view-local unit allowlist, `check:ui`/`test:ui` commands, and the one-test-file-per-module rule.
- [ ] T044 [P] [US3] Update the frontend structure/API-boundary section in `README.md` to state that the shared client remains the only network boundary, state units own data access, and views are presentation-only.
- [ ] T045 [P] [US3] Add an `Unreleased` entry to `CHANGELOG.md` describing the behavior-preserving modular UI refactor, the new state/view layers, and the development-only test/boundary tooling.
- [ ] T046 [US3] Run `npm run check:api`, `npm run test:api`, `npm run check:ui`, `npm run test:ui`, and `npm run build` in `frontend/`; fix every failure without weakening a rule.
- [ ] T047 [US3] Complete the final parity sign-off in `specs/004-modular-ui-components/parity-checklist.md`, including all viewports, message classes, keyboard/accessibility rows, and the five trial results.
- [ ] T048 [US3] Run a final coverage audit: `npm run check:ui` must report no missing test files, no forbidden view imports, no cycles, and no raw scaffold tokens; record the clean result in `specs/004-modular-ui-components/parity-checklist.md`.

**Checkpoint**: The modular boundaries are enforced in CI, documented, and proven by
the five violation trials.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Remove leftovers, verify the whole quality gate, and merge only after
the complete validation.

- [ ] T049 [P] Remove dead code and stale imports from `frontend/src/`; verify `frontend/src/components/` contains only `PanelShell.vue` and `EmptyState.vue`, and `frontend/src/views/` contains every visual area.
- [ ] T050 [P] Verify `frontend/package.json` runtime `dependencies` are unchanged; only `vitest`, `@vue/test-utils`, and `happy-dom` appear in `devDependencies`; `frontend/package-lock.json` is intentional and committed.
- [ ] T051 [P] Run `npm run check:api` and `npm run test:api` in `frontend/`; confirm the frozen contract is unchanged and all 45 existing API-client tests pass.
- [ ] T052 [P] Run `npm run check:ui`, `npm run test:ui`, and `npm run build` in `frontend/`; confirm zero boundary violations, all UI tests pass, and the production build succeeds.
- [ ] T053 [P] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run mypy choosier main.py tests`, and `uv build` from the repository root; confirm `choosier/`, `main.py`, and `tests/` are untouched and green.
- [ ] T054 Run the full `specs/004-modular-ui-components/quickstart.md` validation, including the three viewport ranges and all targeted behavior checks; record any deviation and fix it before sign-off.
- [ ] T055 Review the final diff against `main@d25abef` across `frontend/src/`, `frontend/package.json`, `choosier/`, and `tests/`: confirm no backend, API-contract, history-format, visual-design, or runtime-dependency change; confirm every production module has a test; confirm `specs/004-modular-ui-components/parity-checklist.md` is complete.
- [ ] T056 Mark every completed task `[X]` in `specs/004-modular-ui-components/tasks.md`, run the full gate one final time, and make the final atomic commit with a Conventional Commit message.
- [ ] T057 After all gates and the sign-off recorded in `specs/004-modular-ui-components/parity-checklist.md` pass, fast-forward merge `004-modular-ui-components` into `main`, push `main` to `origin`, and delete the merged feature branch only if the user confirms; report the merge range and final commit.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: No dependencies; T001 must precede T003.
- **Foundational (Phase 2)**: Depends on Setup; blocks US1 and US2.
- **US1 (Phase 3)**: Depends on Foundational. T014 → T015 → T017; T016 → T017; T018–T020 can run in parallel; T021 depends on T014–T020; T022 depends on T021; T023–T024 depend on T022.
- **US2 (Phase 4)**: Depends on US1 (`use-workspace`, `App.vue`) for full wiring. T025 can start once T022 is complete; T026/T027 can run in parallel after T025; T028 → T029; T030/T031/T032 depend on T021/T022 and each updates shared app wiring sequentially; T033 depends on T022; T034 depends on T028–T033; T035–T038 depend on T034.
- **US3 (Phase 5)**: Depends on US1 and US2 because every production module must exist. T039 → T040 → T041 → T042; T043–T045 can run in parallel after T034; T046 depends on T042–T045; T047–T048 depend on T046.
- **Polish (Phase 6)**: Depends on all stories. T049–T053 can run in parallel; T054–T057 follow the gates and parity sign-off.

### User Story dependencies

- **US1 (P1)**: Independent after Foundational; it delivers the MVP.
- **US2 (P2)**: Needs US1's units and composition root; each view remains independently testable once wired.
- **US3 (P3)**: Needs the final module set from US1/US2; its rules are independently testable with fixtures.

### Within each user story

- Write the failing test before implementing the unit/view.
- Models/types before behavior; shared blocks before consumers.
- Keep every commit green: do not commit a failing test suite, build, or boundary check.
- Commit atomically after each task or logical group, following Conventional Commits.

### Parallel opportunities

- Setup: T002, T004, T005, T006.
- Foundational: T008–T013.
- US1: T014, T016, T018, T019, T020 (different files); T015 and T017 are sequential.
- US2: T026 and T027 (independent views/tests); test authoring for different views can proceed in parallel, but tasks that edit `App.vue`/`use-workspace.ts` must be sequenced.
- US3: T043, T044, T045 (different documentation files).
- Polish: T049–T053 (different verification areas).

---

## Parallel Example: User Story 1

```text
# Launch these independent unit tasks together after Foundational:
Task: "Write the failing test and implement use-workspace-state in frontend/src/state/use-workspace-state.ts"
Task: "Write the failing test and implement use-history-selection in frontend/src/state/use-history-selection.ts"
Task: "Write the failing test and implement use-tabs in frontend/src/state/use-tabs.ts"
Task: "Write the failing test and implement use-shortcuts in frontend/src/state/use-shortcuts.ts"
Task: "Write the failing test and implement use-bootstrap in frontend/src/state/use-bootstrap.ts"

# Then sequence:
Task: "use-picker" -> "use-history-actions" -> "use-workspace" -> "App.vue"
```

## Parallel Example: User Story 2

```text
# After the pure views are moved in T025, launch:
Task: "Convert RemainingPanel to PanelShell/EmptyState + test"
Task: "Convert OptionsPanel to PanelShell + test"

# Then sequence the shared-wiring work:
Task: "use-history-selection anchor/range" -> "HistoryPanel"
Task: "use-browser" -> "BrowserPanel"
Task: "use-preview" -> "PreviewPanel" -> "use-image-viewer" -> "ImageViewer"
Task: "PanelTabs" -> "use-workspace/App final wiring"
```

## Parallel Example: User Story 3

```text
# Documentation can proceed together after US2:
Task: "Update frontend/README.md layer model and commands"
Task: "Update root README.md frontend boundary section"
Task: "Update CHANGELOG.md Unreleased entry"
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Complete Setup + Foundational.
2. Complete US1: extract all app-level workflows, make `App.vue` a composition root.
3. **STOP and VALIDATE**: run unit tests, existing API tests, build, and the US1 flow
   replay. This delivers one owner per workflow and a testable state layer while the
   browser/preview internals still await US2.
4. This is the viable increment if the work must pause before the view conversion.

### Incremental delivery

1. Setup + Foundational → test runner, shared blocks, shared units, baseline.
2. US1 → state/workflow extraction and thin shell; validate independently.
3. US2 → presentation-only views, view-local units, shared shell adoption; validate
   visual/behavioral parity at all three viewport ranges.
4. US3 → boundary enforcement, CI gates, docs, five violation trials.
5. Polish → full gate, quickstart, diff audit, merge.

### Parallel team strategy

With multiple developers after Foundational:

- Developer A: US1 state units (sequential dependency chain).
- Developer B: shared presentation blocks and pure view moves (can start after T022).
- Developer C: document the layer model and prepare boundary fixtures.
- US2 wiring and US3 enforcement should converge before the final parity sign-off.

---

## Notes

- `[P]` means different files and no incomplete-task dependency; it does not override
  the need to keep each commit green.
- Every task must leave the UI at least as functional as before; behavior/visual
  parity is checked at the US1, US2, and final checkpoints.
- Exact user-visible strings, ordering, timing, focus, ARIA, and class names are
  part of the contract; do not "improve" them during extraction.
- The parity checklist is committed evidence; screenshots and browser tooling are not.
- Merge to `main` only after T057's prerequisites are all green.
