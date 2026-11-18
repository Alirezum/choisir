# Tasks: Snooze the Selected Pick

**Input**: Design documents from `/specs/009-snooze-selected-pick/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/snooze-selected-pick.md, quickstart.md

**Tests**: Included. The specification does not request TDD, but plan.md and
constitution principle V require automated coverage for the TUI and frontend.
Write each test with its implementation; where practical, confirm the new test
fails before the implementation lands.

**Organization**: Tasks are grouped by user story. US1 is the MVP; US2 proves
Undo stays separate and trustworthy; US3 proves existence checks, conflicts,
accessibility, parity, and unchanged public boundaries. US2 and US3 build on
US1 without changing its successful behavior.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependency)
- **[Story]**: US1, US2, or US3; setup, foundational, and polish tasks omit it
- Every task names the exact file it changes

## Path Conventions

- Python package and tests: `choosier/`, `tests/`
- Frontend source and tests: `frontend/src/`, `frontend/tests/ui/`
- API contract: `specs/001-standardize-api-responses/contracts/api-contract.json`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the baseline and the frozen boundaries before adding the
interface-only composition.

- [X] T001 Run the existing quality gate on a clean tree and record the result: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy choosier main.py tests`, and in `frontend/` `npm run check:api && npm run test:api && npm run check:ui && npm run test:ui && npm run build`; confirm `specs/001-standardize-api-responses/contracts/api-contract.json` still lists exactly 17 routes and no `.specify/extensions.yml` hook file exists. Do not change files; stop and report any pre-existing failure.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the two reusable web seams that Snooze composes. The terminal
UI chain does not depend on this phase.

**⚠️ CRITICAL**: The web chain cannot begin until this phase is complete; TUI
work can start after T001.

- [X] T002 [P] In `frontend/src/state/use-undo.ts`, export `UndoOutcome = { kind: 'unavailable' } | { kind: 'failed'; error: unknown } | { kind: 'undone' | 'changed' | 'nothing_to_undo'; item: string }`, extract `performUndo(): Promise<UndoOutcome>` from `undo()`, and add it to `UndoBinding`; `performUndo` captures the receipt once, returns `unavailable` when it is absent or `undoing` is true, sets `undoing` while `api.undoHistory` runs, and on `undone`/`changed`/`nothing_to_undo` clears the receipt only if it is still the captured receipt, and invalidates the choice only when the receipt is still the captured receipt and `choice.choice.value?.item === captured.item`; it returns `failed` with the caught error and keeps the receipt, and it must set no status text and perform no refresh. Then make `undo()` a thin wrapper that calls `performUndo`, returns without refreshing on `unavailable`, otherwise sets the existing `Undid pick of ...`, `Could not undo ...: history changed.`, or `Could not undo ...: history is empty.` message, reports `failed` through `status.reportError`, and refreshes once after the attempt.
- [X] T003 [P] In `frontend/src/state/use-skip.ts`, add `add(name: string): void` to `SkipBinding` and the returned binding; it sets `clock.value` from `now()` once, prunes expired records, removes any existing record with the exact name, and appends `{ name, expiresAt: current + SKIP_COOLDOWN_MS }`; it must not set status text, call `refresh`, toggle `skipping`, consult `isRemaining`, or touch storage or cookies. Keep `skip()`, `restore()`, `restoreAll()`, `reconcile()`, `reset()`, and the one-second tick unchanged.
- [X] T004 [P] Extend `frontend/tests/ui/state/use-undo.test.ts` for `performUndo`: no receipt and a pending first call return `unavailable`; `undone`, `changed`, and `nothing_to_undo` return the item and clear the receipt; a matching choice is invalidated while a different choice is untouched; `performUndo` calls neither `setStatus` nor `refresh`; a thrown API error returns `failed`, keeps the receipt, and does not report through the status dependency; a new receipt and choice installed while the request is pending must survive. Keep every existing `undo()` message and refresh assertion green.
- [X] T005 [P] Extend `frontend/tests/ui/state/use-skip.test.ts` for `add`: it stamps `now + 600_000`, replaces an existing same-name record and restarts its expiry instead of duplicating it, prunes expired records first, accepts folder, video, `.png` image, spaced, and Unicode names, and does not set status, refresh, toggle `skipping`, or touch storage or cookies; keep the existing one-second expiry tick and refresh test green.

**Checkpoint**: `performUndo` and `add` are proven in isolation. The web
user-story chain can now proceed; the TUI chain can start after T001.

---

## Phase 3: User Story 1 - Snooze the latest pick and defer it (Priority: P1) 🎯 MVP

**Goal**: A person activates **Snooze** beside Undo; exactly the latest logged
history line disappears and the same item joins the session skipped list for
ten minutes or until the session ends, with no replacement pick.

**Independent Test**: In a folder with known entries, pick one item, activate
Snooze, and verify that exactly that history line disappears, the item appears
as skipped, it cannot be picked during the cooldown, Undo is no longer
available, and restoring or waiting makes it eligible again without any
further history change.

### Web UI for User Story 1

- [X] T006 [US1] Create `frontend/src/state/use-snooze.ts` with `SnoozeDeps` (`options: Pick<FolderOptionsBinding, 'path' | 'logFile'>`, `choice: Pick<ChoiceBinding, 'choice' | 'invalidate'>`, `status: Pick<StatusBinding, 'setStatus' | 'reportError'>`, `undo: Pick<UndoBinding, 'receipt' | 'performUndo'>`, `skips: Pick<SkipBinding, 'add'>`, `refresh: () => Promise<void>`) and `SnoozeBinding` (`canSnooze: ComputedRef<boolean>`, `snoozing: Ref<boolean>`, `snoozeLabel: ComputedRef<string>`, `snooze: () => Promise<void>`); `canSnooze` is true exactly when the receipt exists, the current choice's item equals `receipt.item`, and no Snooze is already running; `snoozeLabel` is `Snooze last pick: <item>` with a receipt and `Snooze last pick (nothing to snooze)` without one; implement `snooze()` with a `snoozing` guard that sets `Wait for the current action to finish.`, absent or mismatched eligibility that sets `Nothing to snooze.`, and otherwise `undo.performUndo()`; on `undone` call `skips.add(outcome.item)`, set `Snoozed <item>. Its pick was removed; it returns in ten minutes or when this session ends.`, and refresh once; on `changed` set `Could not snooze <item>: history changed.` and refresh; on `nothing_to_undo` set `Could not snooze <item>: history is empty.` and refresh; on `failed` call `status.reportError(error)` and refresh; on `unavailable` treat it as `history changed` for the captured item; add no skip unless the outcome is `undone`, never clear the receipt or choice directly because `performUndo` owns those transitions, and reset `snoozing` in `finally`.
- [X] T007 [US1] Extend `frontend/src/view-models.ts` `WorkspaceBinding` beside the Undo fields with `canSnooze: ComputedRef<boolean>`, `snoozing: Ref<boolean>`, `snoozeLabel: ComputedRef<string>`, and `snooze: () => Promise<void>`; keep this type-only module free of runtime logic.
- [X] T008 [US1] Wire `frontend/src/state/use-workspace.ts`: import `useSnooze`, construct it after `useUndo` with `{ options, choice, status, undo, skips: skip, refresh: workspaceState.refresh }`, and expose `canSnooze`, `snoozing`, `snoozeLabel`, and `snooze` on the returned binding; do not add storage, timers, API calls, or workflow rules here, and keep the existing `undo.clear()` and `skip.reset()` calls on path and log changes as the scope reset.
- [X] T009 [US1] In `frontend/src/views/ChoiceBoard.vue`, add required props `canSnooze: boolean` and `snoozeLabel: string` and emit `snooze: []`; render a native `button.board-snooze` with visible text `Snooze`, `type="button"`, `:disabled="!canSnooze"`, `:aria-label="snoozeLabel"`, and `@click="canSnooze && emit('snooze')"` immediately after `.board-undo`, keeping Undo present and unchanged; update every existing ChoiceBoard mount in `frontend/tests/ui/views/ChoiceBoard.test.ts` with the two new props so the suite compiles.
- [X] T010 [US1] Update `frontend/src/App.vue`: destructure `canSnooze`, `snoozeLabel`, and `snooze` from `useWorkspace()`, pass `:can-snooze="canSnooze"` and `:snooze-label="snoozeLabel"` to `ChoiceBoard`, and bind `@snooze="snooze"`, leaving the existing Undo props and event unchanged.
- [X] T011 [P] [US1] Create `frontend/tests/ui/state/use-snooze.test.ts` covering the US1 path: the binding starts unavailable with the `(nothing to snooze)` label; a receipt plus matching choice exposes the item-bearing label and `canSnooze`; activation sends one `api.undoHistory` request with the receipt and exact path/log values, calls `skip.add` once with the returned item, sets the exact success message, refreshes once, and leaves `canSnooze` false after the receipt is consumed; no receipt or a different current choice sets `Nothing to snooze.` with no API call, no skip, and no refresh; `changed` and `nothing_to_undo` set their exact messages without a skip; a rejected request reports the error, adds no skip, and keeps the receipt; a second call while the first request is pending sets `Wait for the current action to finish.` and does not issue a second request; include a spaced or Unicode item name. Mock `api.browse` to return the picked item as a direct child so the suite stays valid once the US3 preflight lands.
- [X] T012 [P] [US1] Extend `frontend/tests/ui/state/use-workspace.test.ts` so a mocked `api.pick` with a receipt exposes `canSnooze` and the item-bearing `snoozeLabel`; calling `workspace.snooze()` with a mocked `api.undoHistory` `undone` response adds one session skip, refreshes state, clears `canSnooze`, clears the matching current choice, leaves a different choice untouched in a separate case, leaves Undo visible through `canUndo === false`, and exposes `snoozing`; assert the request uses the captured receipt, path, and log values and that `skippedTotal` becomes one; update the `api.browse` mock in the snooze case to list the picked item, and make the post-snooze state response include the picked item in both `skipped` and `skipped_present` so the record survives reconciliation; keep the existing path and log reset cases green.
- [X] T013 [P] [US1] Extend `frontend/tests/ui/views/ChoiceBoard.test.ts`: a disabled Snooze renders after Undo with text `Snooze`, `type="button"`, the `(nothing to snooze)` accessible name, and emits nothing on click; with a receipt the same button is enabled, carries `Snooze last pick: <item>`, and emits `snooze` on click; Undo still renders and emits `undo`; the DOM order is Open when present, then Undo, then Snooze.

### Terminal UI for User Story 1

- [X] T014 [US1] In `choosier/tui.py`, add `Button("Snooze", id="snooze", disabled=True)` immediately after `#undo` in the actions row and add `_sync_snooze_control()` that disables the button unless `_undo_receipt` is set and `_current_choice.name` equals `receipt.item`, labels it `Snooze: <item>` whenever a receipt exists and `Snooze` otherwise, and sets the tooltip `Snooze <item> and undo its pick` or `Nothing to snooze`; call it from `_refresh_panels()` next to `_sync_undo_control()`, from the `on_input_changed` scope-reset branch, and wherever `_sync_undo_control()` is called directly after the receipt is cleared at the start of `do_pick()`; add the `snooze` branch in `on_button_pressed()` that calls `_snooze_pick()`.
- [X] T015 [US1] In `choosier/tui.py`, add `_snooze_pick()`: re-check the receipt and exact current-choice match, setting `Nothing to snooze.` and returning otherwise; on `undone` clear `_undo_receipt`, set `_skips[outcome.item] = self._skip_clock() + SKIP_COOLDOWN_SECONDS`, set `Snoozed <item>. Its pick was removed; it returns in ten minutes or when this session ends.`, clear the board and preview only when `_current_choice == self._target / outcome.item`, refresh the panels once so the skip and counts render, and call `_focus_control("#pick")`; on `changed` set `Could not snooze <item>: history changed.`, clear the receipt, clear the matching choice, and refresh; on the empty-history outcome set `Could not snooze <item>: history is empty.` with the same transitions; on `ServiceError` set its message, refresh, and retain the receipt and choice; add no skip unless the undo outcome is `undone`.
- [X] T016 [P] [US1] Extend `tests/test_tui.py` with a `TuiSnoozeScenarioTest` for US1: Snooze starts disabled; after a logged pick it is enabled with `Snooze: <item>`, Undo is enabled, and the exact status, log entries, remaining names, and skipped rows are recorded; pressing `#snooze` removes exactly the latest line, adds one skipped row with a countdown, keeps the item out of `#remaining-list`, leaves the remaining summary at its post-pick value while the skipped count rises by one and the picked count drops by one, clears the board and preview, sets the exact success message, and leaves Undo and Snooze visible but disabled; a later pick re-enables both for the new item; advance an injected `_skip_clock` past 600 seconds and assert `_expire_skips()` returns the item while history is unchanged; repeat the happy path for a directory, a `.mp4`, a `.png` image, and a spaced or Unicode name; assert filters, seed, dry-run mode, path memory, and every other history line are unchanged; and snooze the last remaining entry to assert the existing all-skipped or neutral no-items state offers restore and picks nothing automatically.

**Checkpoint**: US1 works end to end in both interfaces and is independently
verifiable. Snooze removes one line, creates one skip, and picks no replacement.

---

## Phase 4: User Story 2 - Keep Undo separate and trustworthy (Priority: P2)

**Goal**: Undo remains its own visible control; Snooze consumes the same
single-level opportunity, and every refusal changes neither history nor the
skipped list.

**Independent Test**: Pick an item and confirm both controls are available.
Snooze it and verify Undo remains visible but disabled. Pick again and verify
both become available for the new pick. Exercise dry-run, failed, empty, and
externally changed-history states and verify Snooze refuses without partial
changes.

- [X] T017 [US2] In `frontend/src/state/use-snooze.ts`, add conflict eligibility and trust handling: widen the dependency picks to include `undo.undoing` and `skips.skipping`, then make `canSnooze` additionally require `!undo.undoing` and `!skips.skipping`; `snooze()` checks `snoozing`, `undo.undoing`, and `skips.skipping` before anything else and sets `Wait for the current action to finish.` without an API call, skip, or refresh; after a successful undo the receipt stays consumed, Undo remains rendered but disabled, and only a later `undo.setReceipt` makes both available again; keep `changed` and `nothing_to_undo` receipt consumption and transport-failure retention exactly as the contract requires.
- [X] T018 [P] [US2] Extend `frontend/tests/ui/state/use-snooze.test.ts` for trust: refusal while `undoing`, `skipping`, or `snoozing` sets `Wait for the current action to finish.` and performs no API call, skip, or refresh; success leaves `canSnooze` false while the receipt is gone and `canUndo` false; a later receipt re-enables both labels; `changed` and `nothing_to_undo` clear the receipt and add no skip; a failed request retains the receipt and adds no skip; a successful Snooze clears the matching current choice while a separate run with a different choice leaves it untouched; restoring or expiring a skip never recreates the receipt or re-enables Undo; a history preview of a different item leaves Undo available for the receipt but sets `canSnooze` false, and activation sets `Nothing to snooze.` without an API call, skip, or refresh; mock `api.browse` to list the item, and use real `useUndo` and `useSkip` instances, or equivalent refs, so the assertion is about the bindings rather than a mock.
- [X] T019 [US2] Refactor `choosier/tui.py` to extract `_clear_choice_if(item: str)` from `_undo_pick()` and use it in both `_undo_pick()` and `_snooze_pick()` so both consume the receipt with identical board and preview clearing; keep `_undo_pick()` messages, availability, and visible control unchanged, and call `_sync_undo_control()` and `_sync_snooze_control()` after every receipt transition, including the start of `do_pick()`.
- [X] T020 [P] [US2] Extend `tests/test_tui.py` with `TuiSnoozeTrustTest` cases: a dry-run pick leaves Snooze disabled and `_snooze_pick()` changes nothing; a completed Undo and a cleared receipt leave it disabled; an externally appended history line makes Snooze report `Could not snooze <item>: history changed.`, remove no line, add no skip, and disable both controls; deleting the log makes it report `Could not snooze <item>: history is empty.`; a patched `HistoryService.undo` `ServiceError` reports the message, keeps the receipt, leaves Snooze enabled for retry, and adds no skip; pressing Snooze twice after success removes only one line and creates one skip; restoring the snoozed item returns it to remaining without restoring the history line or enabling Undo; after a successful Snooze, archiving a real log or clearing a real history disables both controls and retains the skip, an archive or clear that finds no log leaves the receipt and Snooze availability unchanged, and an external log rotation refuses with `Could not snooze <item>: history changed.`, removes no line, and adds no skip.
- [X] T021 [P] [US2] Extend `frontend/tests/ui/state/use-workspace.test.ts` for scope and receipt lifetime: a path or log-file change clears `canSnooze`, `canUndo`, and the skipped records; snoozing and then returning to the original path still leaves both unavailable until a new pick; a new successful pick re-enables both for the new item; restoring the snoozed item makes it remaining again but does not restore the receipt or `canUndo`; include the snoozed name in each post-snooze response's `skipped_present` so the record is not reconciled away before restore.
- [X] T022 [P] [US2] Extend `frontend/tests/ui/views/ChoiceBoard.test.ts` for Undo trust with explicit props: with `item=null`, `canUndo=false`, and `canSnooze=false`, both Undo and Snooze render disabled, Undo keeps its own label and accessible name, and Snooze carries `Snooze last pick (nothing to snooze)`; with a displayed item different from the receipt item (`canUndo=true`, `canSnooze=false`, `snoozeLabel` naming the receipt item), Undo renders enabled while Snooze renders disabled and names the receipt item rather than the displayed one; after a new pick both render enabled with `Undo last pick: <new>` and `Snooze last pick: <new>`, and Undo still emits `undo` independently; no Snooze state may hide, rename, or replace the Undo control.

**Checkpoint**: US1 and US2 both work independently. The person can always see
which control removed the line, and a refused Snooze leaves both stores alone.

---

## Phase 5: User Story 3 - Trust Snooze across interfaces and conflicts (Priority: P3)

**Goal**: Snooze refuses completely for deleted items, changed history, and
scope or concurrent changes; both interfaces are keyboard-operable with
item-bearing feedback; and no API, CLI, dependency, or persistent state
changes.

**Independent Test**: Record history and target hashes, then snooze in both
interfaces and repeat with deleted items, external log edits, two sessions,
quick repeated actions, reloads, and keyboard-only operation; verify exactly one
history line disappears per success, no other state changes, and every refusal
leaves history and skips untouched.

- [X] T023 [US3] In `frontend/src/state/use-snooze.ts`, capture `pathAtStart`, `logAtStart`, the receipt, and the item once at activation; before the undo call, call `api.browse(pathAtStart)` and wait for it to settle. Check the scope first: if the path or log value changed while the browse was pending, set `Could not snooze <item>: the folder or log file changed.` and stop; if the browse threw, report the error, keep the receipt, and stop; if the captured receipt is no longer current, set `Could not snooze <item>: history changed.` and stop; otherwise require `entries.some(entry => entry.name === item)` with an exact name match and no filter check, and if it is absent set `Could not snooze <item>: it is no longer available.` while keeping the receipt. In each refusal remove no history line, add no skip, and do not refresh. After `performUndo()` returns `undone`, re-check the path and log values before `skips.add`; when they changed, set `Removed the pick of <item>. The folder or log file changed before it could be skipped.`, add no skip, and refresh the new scope. Keep the existence preflight out of `canSnooze`.
- [X] T024 [P] [US3] Extend `frontend/tests/ui/state/use-snooze.test.ts` for preflight and scope: a deleted or renamed item calls `api.browse` but never `api.undoHistory`, sets the exact unavailable message, adds no skip, and retains the receipt; a browse failure reports the error and retains the receipt; a deferred browse with a path or log change before it resolves sets `Could not snooze <item>: the folder or log file changed.` and performs no undo or skip; a deferred undo with a path or log change before it resolves allows the existing history removal, sets `Removed the pick of <item>. The folder or log file changed before it could be skipped.`, adds no skip to the new scope, and refreshes; a newer receipt installed during the preflight refuses with the history-changed message and is left intact; two overlapping calls issue one undo request and one skip.
- [X] T025 [US3] In `choosier/tui.py`, add the existence preflight to `_snooze_pick()` before `HistoryService.undo`: import `os`, scan the active target with `os.scandir` and compare `entry.name == receipt.item` exactly (direct children, hidden included, no filter check); on absence set `Could not snooze <item>: it is no longer available.` with the receipt, history, and skips unchanged; on `OSError` set its message text via `_set_status` and refuse with the receipt, history, and skips unchanged; keep the preflight out of `_sync_snooze_control`; after a successful Snooze focus `#pick` and ensure `_sync_undo_control()` and `_sync_snooze_control()` run after every receipt change so Undo stays visible and disabled.
- [X] T026 [P] [US3] Extend `tests/test_tui.py` for existence, parity, and accessibility: after picking a file, delete or rename it outside the app and press `#snooze`; assert the exact unavailable message, unchanged log bytes, no skipped row, and both Undo and Snooze still enabled with the receipt retained; verify a target or log change clears the receipt and disables both controls; use Tab and Enter to reach `#snooze` from `#undo`, assert visible focus and the `Snooze: <item>` name and tooltip, and after success assert focus moved to `#pick`; instantiate a new `ChooserApp` and assert the removed line stays removed, no skip is present, the item is remaining, and both controls are disabled; assert the exact contract strings for success, nothing, missing, changed, and empty outcomes.
- [X] T027 [US3] Before editing `frontend/src/styles.css`, load `.agents/skills/frontend-design/SKILL.md` and apply its plan, review-against-the-brief, build, and critique process. Then add `.board-snooze` beside `.board-undo` using the same padding, border color, transparent background, text color, font size, and hover treatment; reuse the existing disabled and focus styles without a new palette, typeface, card, animation, or layout system, and keep the button a native tab stop immediately after Undo.
- [X] T028 [P] [US3] Extend `frontend/tests/ui/views/ChoiceBoard.test.ts` for accessibility: Snooze is a native `BUTTON` with `type="button"`, no `tabindex` or `aria-keyshortcuts`, has the item-bearing accessible name even when temporarily disabled, follows Undo in DOM order, is focusable, and emits `snooze` on click; the component adds no new keyboard shortcut or live region, so feedback stays in the existing status bar.
- [X] T029 [P] [US3] Extend `tests/test_cli.py` with a guard that `choosier --help` contains no `snooze` option or command and that the existing flags, prompt flow, output, and exit codes are unchanged; do not add any CLI branch, flag, or subcommand.
- [X] T030 [P] [US3] Extend `tests/test_api_contract.py` to assert the route inventory is exactly 17, no route or operation ID contains `snooze`, `POST /api/undoHistory` keeps its existing request fields and `undone`/`nothing_to_undo`/`changed` statuses, and `POST /api/pick` gains no field or status; confirm `frontend/src/api-contract.generated.ts` is unchanged and `cd frontend && npm run check:api` passes. Also extend `tests/test_web.py` with a two-session Snooze-shape check built on `test_two_sessions_share_only_the_latest_receipt`: session A picks, session B picks again so A's receipt reports `changed` while B's reports `undone`; after B removes its line, re-pick the item in one session with a seed that selects it and post `/api/state` with it in `skipped_entries`; assert it is absent from `skipped` and `remaining`, present in `skipped_present`, reflected in `history_total` with `skipped_total` 0, and that removing the new history line makes the same skip displayable with `skipped_total` 1. Add no route, field, or status.

**Checkpoint**: All three stories pass independently, and the trust, existence,
accessibility, parity, and unchanged public-boundary promises are enforced by
tests rather than inspection.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, end-to-end validation, and frozen-boundary proof.

- [X] T031 [P] Extend the `Skip and snooze` section of `README.md` with the Snooze action: it removes the latest logged pick exactly as Undo does and adds the same item to the existing skipped list for the fixed ten-minute cooldown or session end, picks no replacement, clears the board only when it still shows the item, leaves Undo visible but disabled until the next logged pick, and refuses completely when the item is missing, history changed, history is empty, the folder or log-file scope changed, or another action is running; state that both interactive interfaces match, that restoring the item never restores the history line, and that the API, route inventory, persistent state, and one-shot CLI are unchanged.
- [X] T032 [P] Add an entry under `CHANGELOG.md` `## Unreleased` describing the TUI and web Snooze action beside Undo, the one-line removal plus session skip composition, the fixed cooldown or session end, Undo remaining visible and disabled, full refusals with no partial history or skip change, keyboard and accessible naming, and that no route, API field, CLI option, dependency, or persistent state was added.
- [X] T033 Run the complete quality gate from `specs/009-snooze-selected-pick/quickstart.md`: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy choosier main.py tests`, in `frontend/` `npm run check:api && npm run test:api && npm run check:ui && npm run test:ui && npm run build`, and `uv build`; confirm the frontend build writes `choosier/web_static`, the focused Snooze suites pass, and no existing suite regresses.
- [X] T034 Execute the manual TUI and web scenarios in `specs/009-snooze-selected-pick/quickstart.md` on a disposable folder: success, new pick, restore, restore-all, dry run, deleted item, external history change, target and log-file change, keyboard-only operation, folder/video/image/spaced names, last-remaining all-skipped, two tabs, archive and clear history, reload/restart, and cross-interface parity; record any mismatch, confirm Snooze feedback appears within one second without a manual reload, and do not wait ten minutes, because the cooldown is covered by the injected-clock automated tests.
- [X] T035 Verify the frozen boundaries: `specs/001-standardize-api-responses/contracts/api-contract.json` still has exactly 17 routes and the same error codes, `git diff --stat pyproject.toml` is empty, no new dependency, route, CLI option, or persistent store exists, `frontend/src/api-contract.generated.ts` matches `npm run generate:api`, and `git status --short` contains only the planned feature files.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on T001; T002 and T003 are parallel, then T004 follows T002 and T005 follows T003; this phase blocks only the web chain, so TUI tasks can start after T001.
- **US1 (Phase 3)**: the web tasks depend on Phase 2; the TUI tasks depend only on T001. T006 → T007 → T008; T009 → T010; T011 after T006; T012 after T008; T013 after T009; T014 → T015 → T016. The web chain and TUI chain can proceed in parallel.
- **US2 (Phase 4)**: depends on US1. T017 → T018; T019 → T020; T021 and T022 follow US1.
- **US3 (Phase 5)**: depends on US1 and US2. T023 → T024; T025 → T026; T027 → T028; T029 and T030 can run after US1 because they only guard existing boundaries.
- **Polish (Phase 6)**: depends on all three stories; T033 depends on T031 and T032 for a complete diff.

### User Story Dependencies

- **US1 (P1)**: no story dependency; MVP.
- **US2 (P2)**: depends on US1 because it verifies the receipt consumed by Snooze
  and the separation from Undo.
- **US3 (P3)**: depends on US1 and US2 because it verifies their combined
  refusal, existence, concurrency, accessibility, and parity rules.

### Within Each User Story

- Write each test with its implementation; where practical, confirm it fails
  first.
- State units before bindings, bindings before views, and views before tests.
- Python TUI work can proceed in parallel with the frontend chain.
- Finish a story's checkpoint before moving to the next priority.

### Parallel Opportunities

- T002 and T003 can run side by side; T004 and T005 are independent test files.
- The TUI chain (T014 → T015 → T016) can start after T001, while the web chain
  is still in Phase 2.
- Within US1: T011, T012, and T013 are independent test files once their units
  exist; T016 can run alongside the web chain once T014 and T015 land.
- Within US2: T018, T020, T021, and T022 are independent test files; T019 is the
  only TUI edit in that phase.
- Within US3: T024, T026, T028, T029, and T030 can run in parallel once their
  implementation units exist; T023, T025, and T027 touch three different
  source areas.
- Do not claim full cross-story parallelism: US2 and US3 extend
  `frontend/src/state/use-snooze.ts`, `choosier/tui.py`, and
  `frontend/src/views/ChoiceBoard.vue` after US1.

---

## Parallel Example: User Story 1

```text
Web state:  T006 use-snooze.ts → T007 view-models.ts → T008 use-workspace.ts
Web view:   T009 ChoiceBoard.vue → T010 App.vue
Web tests:  T011, T012, T013 (parallel after their units)
TUI:        T014 tui.py → T015 tui.py → T016 test_tui.py
```

## Parallel Example: User Story 2

```text
TUI trust:  T019 tui.py → T020 test_tui.py
Web tests:  T018 use-snooze.test.ts · T021 use-workspace.test.ts
            · T022 ChoiceBoard.test.ts
```

## Parallel Example: User Story 3

```text
Web:    T023 use-snooze.ts → T024 use-snooze.test.ts
TUI:    T025 tui.py → T026 test_tui.py
View:   T027 styles.css → T028 ChoiceBoard.test.ts
Guards: T029 test_cli.py · T030 test_api_contract.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and the Phase 2 web seams; start the TUI chain after
   Phase 1 if the frontend work is still in progress.
2. Complete Phase 3 in both interfaces.
3. Stop and validate: pick one item, snooze it, verify exactly one line is
   removed and one skip is shown, advance the injected clock, restart the
   session, and confirm history stays removed with no duplicate skip.
4. Ship the MVP if Undo remaining visible but disabled after Snooze is
   acceptable; otherwise continue through US2 before release.

### Incremental Delivery

1. Foundation → `performUndo` and `add` with isolated tests.
2. US1 → Snooze removes the latest pick and defers the item in both interfaces
   (MVP).
3. US2 → Undo stays separate and trustworthy; refusals leave both stores
   untouched.
4. US3 → existence, scope, concurrency, accessibility, parity, and frozen
   boundaries.
5. Polish → README, changelog, full gate, manual validation, and boundary proof.

### Notes

- `[P]` marks different-file work with no incomplete dependency.
- No core, storage, HTTP, or CLI code is expected to change; Snooze is an
  interface composition over the existing Undo and skip behavior.
- Never write snooze or skip state to history, path memory, browser storage, or
  cookies.
- Do not add a replacement pick: after Snooze the Pick control remains the
  person's next action.
- Stop at each checkpoint and run that story's independent test.
