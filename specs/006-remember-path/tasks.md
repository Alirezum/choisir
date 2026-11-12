# Tasks: Remembered Folder Paths

**Input**: Design documents from `/specs/006-remember-path/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/path-memory.md`, `contracts/web-paths.md`, `quickstart.md`

**Tests**: Included because Constitution Principle V requires tests for every
behavior change and the API contract/drift tests are mandatory. Every task must
leave the full suite green before it is committed.

**Organization**: Tasks are grouped by user story so each story can be
implemented, tested, and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `US1`, `US2`, or `US3`; omitted for setup, foundational, and polish
- Every task names the exact file(s) it changes

## Path Conventions

- Python package and tests: `choosier/`, `tests/`
- Frontend: `frontend/src/`, `frontend/tests/`
- Authoritative API contract: `specs/001-standardize-api-responses/contracts/`
- Feature docs: `specs/006-remember-path/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Governance prerequisite and baseline verification.

- [x] T001 Amend `.specify/memory/constitution.md` to v1.3.0 (MINOR, Last Amended 2026-11-11): extend Principle III to permit a user-scoped path-memory record limited to local folder paths and ordering, atomic writes, and clearability, and note the versioned JSON record in Technical Constraints; include the rationale and remove any temporary impact report before committing. **Completed 2026-11-11.**
- [x] T002 Run the baseline commands in Section 1 of `specs/006-remember-path/quickstart.md` (`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy choosier`, `cd frontend && npm run check:api && npm run check:ui && npm run test:api && npm run test:ui && npm run build`) and record the passing state before feature changes.

**Checkpoint**: Constitution permits the feature and the repository is green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared, standard-library-only path-memory core used by every
story. No adapter work may start until this phase is complete.

**⚠️ CRITICAL**: US1, US2, and US3 all depend on this phase.

- [x] T003 [P] Create `choosier/path_memory.py` with `MAX_RECENT = 10`, `DEFAULT_FILENAME = "path-memory.json"`, `ENV_OVERRIDE = "CHOOSIER_PATH_MEMORY_FILE"`, `default_memory_path()` (Windows `%APPDATA%\choosier\path-memory.json`, macOS `~/Library/Application Support/choosier/path-memory.json`, otherwise `$XDG_CONFIG_HOME/choosier/path-memory.json` or `~/.config/choosier/path-memory.json`), `canonical_path()` returning `Path(value).expanduser().resolve()`, and `is_usable_directory()` requiring `path.is_dir()` plus an openable `os.scandir`.
- [x] T004 Implement versioned JSON reading and atomic writing plus the exclusive sibling lock in `choosier/path_memory.py`: accept only `{"version": 1, "recent": [string, ...]}` with `recent` newest first, maximum 10, no duplicates after `os.path.normcase` canonicalization; treat malformed JSON/shape/version as empty with a warning; create parent directories with best-effort `0o700`; write UTF-8 with trailing newline via temp file, `flush`, `fsync`, best-effort `0o600`, and `os.replace`; use `fcntl.flock(LOCK_EX)` on POSIX and `msvcrt.locking(LK_LOCK, 1)` on Windows.
- [x] T005 Implement `MemorySnapshot` and `PathMemory.snapshot()` plus `StartupResolution` and `PathMemory.startup(default)` in `choosier/path_memory.py`: validate, deduplicate, and truncate to 10; drop unavailable directories; atomically rewrite only when pruning changed the list; return valid paths newest first with a non-blocking warning; `startup()` returns the first valid recent with `source="recent"` or the caller's default with `source="default"`.
- [x] T006 Implement `MutationResult`, `PathMemory.record()`, `PathMemory.remove()`, and `PathMemory.clear()` in `choosier/path_memory.py`: `record()` canonicalizes, verifies availability, moves an existing identity to index 0, truncates to 10, and persists; `remove()` deletes only a matching identity and reports `changed`; `clear()` persists an empty `recent` list; I/O or lock failures return `ok=False` with a notice and never raise.
- [x] T007 [P] Add core tests in `tests/test_path_memory.py` for `default_memory_path()` on each platform branch and the `CHOOSIER_PATH_MEMORY_FILE` override, canonicalization of trailing separators, relative segments, symlinks, spaces/Unicode, and `is_usable_directory()` for missing paths, files, unreadable directories, and valid folders.
- [x] T008 Extend `tests/test_path_memory.py` for format and ordering guarantees: malformed JSON and wrong shapes, unknown version, invalid/blank/relative elements, duplicate collapse, newest-first order, the 10-entry cap and oldest eviction, reuse moving an entry to the top, prune-on-`snapshot()` and startup fallback to the next valid recent, fallback to the default, empty-list behavior, and persistence across new `PathMemory` instances.
- [x] T009 Extend `tests/test_path_memory.py` for failure and concurrency behavior: unwritable directory/file, read-only file, corrupt record left untouched until the next successful write, `record`/`remove`/`clear` notices without exceptions, atomic temp-file cleanup, file mode `0o600` on POSIX, and a multi-process test that performs concurrent `record()` calls and asserts valid JSON, unique entries, the cap, and no lost successful writes; skip permission-denied cases when running as root (`os.geteuid() == 0`) or simulate failure with a directory path; add `tests/conftest.py` with an autouse fixture that points `CHOOSIER_PATH_MEMORY_FILE` at a unique temporary file per test so no test reads or writes the developer's real memory.

**Checkpoint**: The core module is complete, tested, and independent of any UI.

---

## Phase 3: User Story 1 - Resume in the last used folder (Priority: P1) 🎯 MVP

**Goal**: After a successful pick, the TUI and web UI remember the folder; a
later launch without an explicit path restores the most recent valid folder,
skips stale entries, and preserves today's default when nothing is valid.

**Independent Test**: Make a successful pick in a folder, close, and reopen each
interactive interface without a path. Verify the folder is restored, explicit
paths still win, and a deleted remembered folder falls back without blocking.

### Implementation for User Story 1

- [x] T010 [US1] In one atomic change, update `choosier/web.py`, `specs/001-standardize-api-responses/contracts/api-contract.json`, `tests/test_api_contract.py`, `frontend/src/api-contract.generated.ts`, `frontend/tests/ui/test-helpers.ts`, and `frontend/src/types.ts`: add nullable `path_warning` to `DefaultsResponse` and nullable `path_memory_notice` to `PickResponse`; resolve startup in `create_app()` (non-empty `initial_path` verbatim, otherwise `PathMemory().startup(Path.cwd())` and its warning); record the canonical target in `POST /api/pick` only when `outcome.status == "picked"` (including dry run), mapping a failed record to the nullable notice without changing pick status or HTTP code; update the contract fields, the contract tests, the shared fixtures, and regenerate the frontend contract with `npm run generate:api` so route/schema parity and the production build stay green.
- [x] T011 [US1] Add startup resolution and the record hook in `choosier/tui.py`: an empty `initial_path` resolves through `PathMemory().startup(...)` on mount and fills `#path-input` or leaves it empty when no memory exists; a successful pick (including dry-run) records the target in `do_pick()`; surface `path_warning`/record notices in `#status` without blocking.
- [x] T012 [US1] Change the `--web` branch in `choosier/cli.py` to pass `args.path or ""` instead of eagerly substituting `str(Path.cwd())`, leaving the one-shot CLI branch, flags, output, and exit codes untouched.
- [x] T013 [US1] Apply the startup warning in `frontend/src/state/use-bootstrap.ts`: after loading defaults, show `defaults.path_warning` through `status.setStatus` without overwriting a later refresh failure.
- [x] T014 [US1] Show the recording notice in `frontend/src/state/use-picker.ts`: append `result.path_memory_notice` to the successful pick status when present, leaving the picked item, preview, and refresh behavior unchanged.

### Tests for User Story 1

- [x] T015 [P] [US1] Add TUI tests in `tests/test_tui.py`: empty initial path restores the remembered folder, an explicit path wins even when invalid, stale most-recent falls back to the next valid recent and prunes it, first run stays empty, and successful/dry-run picks record while empty/exhausted/invalid outcomes do not; assert the fallback/record notices appear in `#status`, filters and the current choice are not restored, and history is unchanged; use the isolated memory fixture from T009.
- [x] T016 [P] [US1] Add web tests in `tests/test_web.py`: `/api/defaults` resolves memory vs. explicit path vs. cwd fallback with `path_warning`, `POST /api/pick` records on success and dry-run, does not record on failure/invalid path, and returns `path_memory_notice` when the memory file is unwritable without failing the pick; assert filters, the current choice, previews, and history are unchanged by startup/recording; use the isolated memory fixture from T009.
- [x] T017 [P] [US1] Add CLI tests in `tests/test_cli.py`: `--web` without a path forwards an empty initial path to `run_web`, `--web` with a path forwards it unchanged, and one-shot CLI invocations never create or modify the path-memory file.
- [x] T018 [P] [US1] Add a bootstrap test in `frontend/tests/ui/state/use-bootstrap.test.ts` for applying `path_warning` to the status while still refreshing and preserving the existing failure path.
- [x] T019 [P] [US1] Add a picker test in `frontend/tests/ui/state/use-picker.test.ts` for appending `path_memory_notice` to the success status and leaving normal success/failure messages unchanged when it is null.

**Checkpoint**: US1 is fully functional and independently testable as the MVP.

---

## Phase 4: User Story 2 - Jump back to a recent folder (Priority: P2)

**Goal**: Both interactive interfaces show the shared recent list, newest first,
deduplicated, capped at ten, with stale entries omitted; choosing a row
activates that folder without typing.

**Independent Test**: Use folders A, B, then C; verify the list shows C, B, A,
reusing a folder moves it to the top, choosing a row activates it, and more
than ten folders keep only the newest ten.

### Implementation for User Story 2

- [x] T020 [US2] Extend the API mocks and recent-list fixtures in `frontend/tests/ui/test-helpers.ts` with `paths()` returning `{ recent: string[], warning: string | null }` and remove/clear mocks for US3.
- [x] T021 [US2] In one atomic change, add `GET /api/paths` and `PathMemoryResponse` to `choosier/web.py`, add the route and response schema to `specs/001-standardize-api-responses/contracts/api-contract.json`, update the route-count assertion in `tests/test_api_contract.py` to 14, add the response type name in `frontend/scripts/generate-api-contract.mjs`, and regenerate `frontend/src/api-contract.generated.ts`; the route returns `{ recent, warning }` from `PathMemory().snapshot()` so unavailable entries are pruned before the response.
- [x] T022 [US2] Add the `paths` operation name in `frontend/src/api-operations.ts` and the `api.paths()` facade method in `frontend/src/api.ts`.
- [x] T023 [US2] Create `frontend/src/state/use-path-memory.ts` exposing `recent`, `warning`, and `refresh()` backed by `api.paths()`, with non-blocking error reporting through the shared status binding.
- [x] T024 [US2] Compose the new state in `frontend/src/state/use-workspace.ts`, load it during bootstrap, expose its binding to `App.vue`, and refresh it after a successful pick through the picker dependency in `frontend/src/state/use-picker.ts`.
- [x] T025 [US2] Load and apply `.agents/skills/frontend-design/SKILL.md`, then add the recent-folder section to `frontend/src/views/OptionsPanel.vue` (full-path row buttons that activate a folder, visible focus, accessible names containing the full path, empty state) and wire its props/events in `frontend/src/App.vue`; no new runtime dependency.
- [x] T026 [US2] Add the recent-folder section to the Options tab in `choosier/tui.py`: a keyboard-focusable `OptionList` whose row labels are the full paths, a `Use` button that sets `#path-input`, refresh on mount/after a successful pick/after `Use`, and an empty-state label.

### Tests for User Story 2

- [x] T027 [P] [US2] Add `GET /api/paths` tests in `tests/test_web.py`: newest-first order, reuse moves to top without duplication, cap at ten, stale pruning, empty list, warning on corrupt/unreadable records, and standard `405` behavior.
- [x] T028 [P] [US2] Add TUI recent-list tests in `tests/test_tui.py`: the list shows valid full paths newest first, stale entries are absent, `Use` sets the path input and refreshes panels, keyboard focus reaches every row and control, and the list refreshes after a successful pick.
- [x] T029 [P] [US2] Add `frontend/tests/ui/state/use-path-memory.test.ts` covering initial load, refresh, empty state, and non-blocking load errors.
- [x] T030 [P] [US2] Add picker refresh assertions in `frontend/tests/ui/state/use-picker.test.ts`: the recent list refreshes after `picked` (including dry-run) and does not refresh after invalid/empty/exhausted outcomes.
- [x] T031 [P] [US2] Add recent-section tests in `frontend/tests/ui/views/OptionsPanel.test.ts` for full-path labels, activating a folder, keyboard operation, empty state, and accessible names containing the full path.

**Checkpoint**: US1 and US2 work independently; the recent list is usable from both interfaces.

---

## Phase 5: User Story 3 - Control remembered folders (Priority: P3)

**Goal**: Remove one remembered folder or clear all from either interface, with
changes persisted and no effect on history, filters, the current choice, or
target content.

**Independent Test**: Remember several folders; remove one and clear the rest
from each interface. Verify the list updates immediately, survives a restart,
the next launch behaves like a first run after clearing, and history/targets are
byte-for-byte unchanged.

### Implementation for User Story 3

- [ ] T032 [US3] In one atomic change, add `DELETE /api/paths` and `DELETE /api/paths/item?path=` plus `ClearPathMemoryResponse` and `RemovePathMemoryResponse` to `choosier/web.py`, add both routes and schemas to `specs/001-standardize-api-responses/contracts/api-contract.json`, update the route-count assertion in `tests/test_api_contract.py` to 16, add both response type names in `frontend/scripts/generate-api-contract.mjs`, and regenerate `frontend/src/api-contract.generated.ts`; require a non-empty absolute `path` for the item route (`400 invalid_request` otherwise, `422 validation_error` when missing), return `{cleared}`/`{path, removed}`, and never change the running session's active path.
- [ ] T033 [US3] Add `clearPaths` and `removePath` operation names in `frontend/src/api-operations.ts` and facade methods in `frontend/src/api.ts`.
- [ ] T034 [US3] Add `remove(path)` and `clear()` actions to `frontend/src/state/use-path-memory.ts` that call the new endpoints, refresh the list, report warnings/errors through the status binding, and never mutate `options.path`.
- [ ] T035 [US3] Add per-row remove buttons and a clear-all button to the recent section in `frontend/src/views/OptionsPanel.vue`, wire the new events in `frontend/src/App.vue`, and keep keyboard/focus behavior, accessible names containing the full path, and the established visual language.
- [ ] T036 [US3] Add `Remove` and `Clear recent` controls to the TUI Options tab in `choosier/tui.py`, acting on the highlighted recent row, refreshing the list and status line, and leaving `#path-input` unchanged.

### Tests for User Story 3

- [ ] T037 [P] [US3] Add web tests in `tests/test_web.py`: remove present/absent, clear populated/empty, `422` for a missing `path`, `400` for a relative/empty `path`, persistence across app instances, two app instances sharing one memory file with the latest successful pick first, and no changes to history, filters, choice, previews, or other response state.
- [ ] T038 [P] [US3] Add TUI tests in `tests/test_tui.py`: remove one preserves the others' order, clear empties the list, persistence across restarts, the active path input, filters, choice, and history are unchanged, and status feedback is non-blocking.
- [ ] T039 [P] [US3] Extend `frontend/tests/ui/state/use-path-memory.test.ts` for remove/clear success, absent-entry no-op, refresh, error notices, and `options.path` remaining unchanged.
- [ ] T040 [P] [US3] Extend `frontend/tests/ui/views/OptionsPanel.test.ts` for row remove, clear-all, accessible labels, focus behavior, and action feedback.
- [ ] T041 [P] [US3] Add persistence and side-effect regression tests in `tests/test_path_memory.py`: remove the most recent entry and verify the next launch uses the next recent; clear and verify first-run behavior; confirm the record contains only `version` and `recent` and no history/file/filter data.

**Checkpoint**: All three user stories are independently complete and verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, full gates, and end-to-end validation.

- [ ] T042 [P] Update `README.md` for remembered startup, the recent list, remove/clear actions, privacy/storage location, the `CHOOSIER_PATH_MEMORY_FILE` test/portable override, and `--web` remembered-folder fallback; state that one-shot CLI flags and exit codes are unchanged.
- [ ] T043 [P] Update `CHANGELOG.md` under the next unreleased minor with the feature summary, privacy note, and the additive API routes/fields.
- [ ] T044 Run the full Python gates (`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy choosier`) and fix any failures in `choosier/` or `tests/`.
- [ ] T045 Run the full frontend gates (`cd frontend && npm run check:api && npm run check:ui && npm run test:api && npm run test:ui && npm run build`) and fix any failures in `frontend/src/` or `frontend/tests/`.
- [ ] T046 Execute all scenarios in `specs/006-remember-path/quickstart.md` on the reference machine, including TUI/web restore, recent ordering/cap, stale fallback/pruning, remove/clear side-effect checks, concurrent sessions, privacy inspection, and one-shot CLI regression; measure launch-to-usable time and confirm the path-memory overhead is at most one second (SC-009); record the results.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately. T001 is complete; T002 confirms the baseline.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational; no dependency on US2/US3.
- **US2 (Phase 4)**: Depends on Foundational and reuses US1's adapter fields; must remain independently testable.
- **US3 (Phase 5)**: Depends on Foundational; composes with US1/US2 but its remove/clear behavior is independently testable.
- **Polish (Phase 6)**: Depends on all desired stories.

### Key Within-Story Dependencies

- Core module order: T003 → T004 → T005 → T006; tests T007 → T008 → T009.
- US1: T010 provides the generated fields; T011/T012 can proceed alongside it; T013/T014 depend on T010. Test tasks T015–T019 follow their implementation tasks.
- US2: T020 → T021 → T022 → T023 → T024 → T025/T026; test tasks T027–T031 follow implementation.
- US3: T032 → T033 → T034 → T035/T036; test tasks T037–T041 follow implementation.

### User Story Independence

- **US1 (P1)**: MVP. Delivers restore + record + fallback with no recent-list UI.
- **US2 (P2)**: Adds listing and one-action switching on top of the shared core; does not require US3.
- **US3 (P3)**: Adds remove/clear on top of the shared core; does not require US2 to be complete, though the UI placement is shared.

---

## Parallel Execution Examples

### Foundational

```bash
# Independent files:
Task: "T003 Create choosier/path_memory.py primitives"
Task: "T007 Add tests/test_path_memory.py primitive tests"
# The remaining core tasks are sequential because they edit the same module.
```

### User Story 1

```bash
# After T010–T014 implementation:
Task: "T015 Add TUI restore/record tests in tests/test_tui.py"
Task: "T016 Add web defaults/pick tests in tests/test_web.py"
Task: "T017 Add CLI --web wiring tests in tests/test_cli.py"
Task: "T018 Add bootstrap warning test in frontend/tests/ui/state/use-bootstrap.test.ts"
Task: "T019 Add picker notice test in frontend/tests/ui/state/use-picker.test.ts"
```

### User Story 2

```bash
# After T020–T026 implementation:
Task: "T027 Add GET /api/paths tests in tests/test_web.py"
Task: "T028 Add TUI recent-list tests in tests/test_tui.py"
Task: "T029 Add use-path-memory tests in frontend/tests/ui/state/use-path-memory.test.ts"
Task: "T030 Add picker refresh tests in frontend/tests/ui/state/use-picker.test.ts"
Task: "T031 Add OptionsPanel recent tests in frontend/tests/ui/views/OptionsPanel.test.ts"
```

### User Story 3

```bash
# After T032–T036 implementation:
Task: "T037 Add DELETE route tests in tests/test_web.py"
Task: "T038 Add TUI remove/clear tests in tests/test_tui.py"
Task: "T039 Add path-memory action tests in frontend/tests/ui/state/use-path-memory.test.ts"
Task: "T040 Add OptionsPanel action tests in frontend/tests/ui/views/OptionsPanel.test.ts"
Task: "T041 Add persistence/side-effect tests in tests/test_path_memory.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001 is already ratified; run the T002 baseline).
2. Complete Phase 2 (shared path-memory core).
3. Complete US1: startup resolution, recording, warnings, CLI `--web` wiring.
4. **STOP and VALIDATE**: run US1 tests and the TUI/web restore scenarios.
5. Commit each task atomically per the repository's Git policy.

### Incremental Delivery

1. Setup + Foundational → core ready.
2. US1 → restore/record MVP.
3. US2 → recent list and one-action switching.
4. US3 → remove/clear controls.
5. Polish → docs, full gates, quickstart.

### Parallel Team Strategy

- One developer owns Phase 2 (same module; sequential).
- After Phase 2, US1, US2, and US3 can be split across developers because they
  touch different adapter/state files; coordinate the shared `choosier/web.py`,
  `choosier/tui.py`, and generated-contract files at the story boundaries.
- Run the full gates at every checkpoint, not only at the end.

---

## Notes

- `[P]` means different files and no incomplete dependency; never run two tasks
  that edit `frontend/tests/ui/test-helpers.ts` or the same generated contract
  concurrently.
- Every behavior change includes tests; every task must leave the suite green
  before committing. Route/schema/contract/generated-client changes are kept in
  one task because the contract tests enforce exact parity.
- The path-memory record must never contain file names, history, filters,
  choices, previews, timestamps, telemetry, or network data.
- The one-shot CLI must remain byte-for-byte compatible in flags, prompt,
  output, and exit codes; only `--web` without a path gains remembered-folder
  resolution before the cwd fallback.
- Load the frontend-design skill before any aesthetic decision in T025/T035.
