# Tasks: Undo Last Pick

**Feature**: `007-undo-last-pick` | **Date**: 2026-11-17

**Input**: Design documents from `/workspace/choosier/specs/007-undo-last-pick/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/undo-history.md`, `quickstart.md`

**Tests**: Required by Constitution V ("Every behavior change MUST include
tests"). Every user story includes test tasks, and tests MUST fail before the
matching implementation task.

**Organization**: Tasks are grouped by user story so each story is an
independently testable increment. Setup and Foundational phases contain no
story label; Polish contains no story label.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete
  task)
- **[Story]**: `[US1]`, `[US2]`, `[US3]` for user-story phases only
- Every description names the exact repository file or files to change

## Path Conventions

Single Python package at `choosier/` with tests at `tests/`; Vue frontend at
`frontend/src/` with tests at `frontend/tests/`; authoritative API contract at
`specs/001-standardize-api-responses/contracts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extract the reusable lock and keep the new lock file out of the
candidate pool. No user-visible behavior changes in this phase.

- [X] T001 Create `choosier/locking.py` with a `@contextmanager def
  exclusive_lock(file: Path) -> Iterator[None]` that opens
  `<file.name>.lock` in `a+b`, takes an exclusive OS lock
  (`fcntl.flock(..., LOCK_EX)` on POSIX; on Windows write a single NUL byte
  when the file is empty, then `msvcrt.locking(..., LK_LOCK, 1)` at offset 0),
  yields, and always unlocks and closes in `finally`. The helper MUST NOT
  create the parent directory. Document that the lock file is coordination
  metadata containing no user data.
- [X] T002 Refactor `choosier/path_memory.py` so `_exclusive_lock(file)` first
  calls `file.parent.mkdir(parents=True, exist_ok=True)` and then delegates to
  `choosier.locking.exclusive_lock(file)`. Delete the duplicated POSIX/Windows
  locking body and the now-unused `fcntl`/`msvcrt` imports; keep `sys` for
  `default_memory_path`. Run `tests/test_path_memory.py` to prove path-memory
  behavior is unchanged.
- [X] T003 Update `choosier/chooser.py::_is_managed_file` to return `True` for
  `name == f"{log_path.name}.lock"` in addition to the history log and
  `*.old` archives, so `--include-hidden` / `include_hidden=True` never offers
  the lock file as a candidate.
- [X] T004 Add a regression test in `tests/test_chooser.py` that creates
  `<log>.lock` beside the target log and asserts it is absent from
  `scan_candidates` and `list_candidates` with `include_hidden=True`, while an
  ordinary dotfile such as `.hidden.txt` is still listed. This test depends on
  T003.

**Checkpoint**: The lock helper is shared, path memory still works, and the
lock file cannot be picked.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the receipt and the verified, byte-preserving removal in the
shared core. Both interfaces consume these results; no UI work starts until
this phase is green.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Cover existing history mutations in `choosier/storage.py` with the
  shared lock: acquire `exclusive_lock(log_path)` around the read/rewrite in
  `remove_log_items`, the rename in `archive_log`, and the unlink in
  `reset_log`. Keep missing-log early returns before the lock so a missing log
  never creates a lock file or parent directory, and preserve every existing
  return value and atomic temp-file + `os.replace` behavior.
- [X] T006 Add to `choosier/storage.py`: a frozen `UndoReceipt` dataclass with
  exactly `item: str`, `entry: str`, and `digest: str`;
  `UndoStatus = Literal["undone", "nothing_to_undo", "changed"]`; and
  `append_log_entry(item: str, log_file: str | Path = DEFAULT_LOG_FILENAME) ->
  UndoReceipt | None`. Under `exclusive_lock`, append the existing
  `{"ts": <ISO-8601 UTC>, "item": <item>}` line, compute `hashlib.sha256` of
  the complete file bytes after the append, then call the existing rotation
  logic. Make `_maybe_rotate_log` return the backup `Path` when it renamed the
  file and `None` otherwise (existing callers ignore the value). Return `None`
  when rotation moved the file; otherwise return
  `UndoReceipt(item=item, entry=<JSON text without line terminator>,
  digest=<64 lowercase hex>)`. Keep `log_selection` as a void wrapper that
  delegates to `append_log_entry`.
- [X] T007 Add `undo_log_entry(receipt: UndoReceipt, log_file: str | Path =
  DEFAULT_LOG_FILENAME) -> UndoStatus` to `choosier/storage.py`. Under
  `exclusive_lock`: return `nothing_to_undo` when the log is missing or zero
  bytes; return `changed` unless the file's SHA-256 equals `receipt.digest`
  (exactly 64 lowercase hexadecimal characters), the file ends with a line
  terminator, the final line equals `receipt.entry` exactly (no raw CR/LF),
  and `parse_log_line(final_line)[1] == receipt.item`; otherwise rewrite
  atomically with every byte before that final line and return `undone`. Add a
  private bytes-based atomic writer and make `_rewrite_log` delegate to it so
  unrelated bytes are preserved. Every non-match writes nothing. Catch a
  concurrent `FileNotFoundError` as `nothing_to_undo`.
- [X] T008 Update `choosier/services/models.py` and
  `choosier/services/__init__.py`: add frozen `UndoOutcome` with `status:
  UndoStatus`, `item: str`, `log_file: Path`, and `removed: bool`; add
  `undo: UndoReceipt | None = None` to `PickOutcome`; re-export `UndoReceipt`
  and `UndoStatus` from the storage definitions and export `UndoOutcome`.
- [X] T009 Change `HistoryService.append(item)` in
  `choosier/services/history.py` to return the `UndoReceipt | None` produced by
  `storage.append_log_entry`, keeping the existing
  `ServiceError(FailureKind.IO_ERROR, f"Error writing log: {e}")` mapping. Add
  `HistoryService.undo(receipt: UndoReceipt) -> UndoOutcome` that calls
  `storage.undo_log_entry`, maps `OSError` to
  `ServiceError(FailureKind.IO_ERROR, f"Error undoing pick: {e}")`, and returns
  `UndoOutcome(status=..., item=receipt.item, log_file=self._log_file,
  removed=(status == "undone"))`.
- [X] T010 In `choosier/services/pick.py`, capture the return value of
  `HistoryService(log_path).append(item)` and set `PickOutcome.undo` to it only
  when `commit` is true and the pick is not a dry run. Every other outcome
  (invalid path, empty, exhausted, filtered, dry run, `commit=False`) and a
  pick that triggered rotation MUST leave `undo` as `None`.
- [X] T011 [P] Extend `tests/test_storage.py` with focused coverage: receipt
  `entry` has no CR/LF and `parse_log_line(entry)[1] == item`; `digest` is 64
  lowercase hex over the full file bytes; two picks of the same item produce
  distinct receipts and undo removes only the newest line; a later external
  append, removal, or full rewrite returns `changed` with byte-identical
  content; a missing or empty log returns `nothing_to_undo` and creates no
  file; rotation returns `None`; `OSError` propagates; concurrent append and
  undo are serialized by the lock; undo on a missing parent directory does not
  create the directory or a lock file.
- [X] T012 [P] Extend `tests/test_services_history.py` and
  `tests/test_services_pick.py`: `HistoryService.append` returns a receipt and
  maps write `OSError` to `FailureKind.IO_ERROR` with the exact prefix
  `"Error writing log: "`; `HistoryService.undo` maps all three statuses and
  maps `OSError` to `"Error undoing pick: "`; logged picks carry a receipt,
  while dry-run, `commit=False`, invalid-path, empty, exhausted, filtered, and
  rotated picks carry `None`. Update the existing
  `choosier.storage.log_selection` patch seams in
  `tests/test_services_history.py`, `tests/test_services_pick.py`, and
  `tests/test_api_errors.py` to patch `choosier.storage.append_log_entry` where
  the service now calls it.

**Checkpoint**: The core can append with a receipt, verify a receipt, and
remove exactly the receipt's line or nothing. All existing backend tests are
green.

---

## Phase 3: User Story 1 — Reverse an unwanted pick (Priority: P1) 🎯 MVP

**Goal**: A logged pick in either interactive interface can be undone with one
action; exactly that history entry disappears, the item becomes eligible again,
and the current choice/preview clears.

**Independent Test**: In a folder with three known entries, make a logged pick
in the TUI and in the web UI, activate Undo in each, and verify exactly one
history line is removed, the item returns to Remaining, the board/preview
clears, and a subsequent pick can select the item.

### Tests for User Story 1 (write first; they MUST fail before implementation)

- [X] T013 [P] [US1] Add TUI tests in `tests/test_tui.py`: after a logged pick,
  `#undo` is enabled with label `Undo <item>`; activating it removes exactly
  one log line, restores the item to `#remaining`, clears `#choice`, resets
  `#preview`, disables `#open`, and sets status `Undid pick of <item>.`; a
  second activation removes nothing and leaves the control disabled.
- [X] T014 [P] [US1] Add web tests in `tests/test_web.py`: `POST /api/pick`
  returns `undo` with `item`, `entry`, and a 64-character lowercase hex
  `digest`; `POST /api/history/undo` with that receipt returns 200 with
  `status: "undone"`, `removed: true`, and echoes `item`; only the final log
  line is removed; a following `/api/state` or `/api/pick` shows the item
  eligible; missing/empty logs return `nothing_to_undo`; an externally
  appended line returns `changed`.
- [X] T015 [P] [US1] Update `tests/test_api_contract.py`: the route inventory
  is 17, `PickResponse` has exactly the six existing properties plus nullable
  `undo` referencing `UndoReceipt`/`UndoReceiptModel`, `UndoReceipt` has
  exactly `item`/`entry`/`digest` as non-nullable strings, and
  `UndoHistoryResponse` has exactly `log_file`/`status`/`item`/`removed` with
  the enum `["undone", "nothing_to_undo", "changed"]`. Add 422 cases for a
  non-hex or 63-character digest and for a missing receipt field.
- [X] T016 [P] [US1] Add frontend tests: create
  `frontend/tests/ui/state/use-undo.test.ts` covering `undone`, `changed`,
  `nothing_to_undo`, an API error that retains the receipt, and choice
  clearing only when `choice.item === item`; extend
  `frontend/tests/ui/state/use-picker.test.ts` for storing and clearing the
  receipt; extend `frontend/tests/ui/views/ChoiceBoard.test.ts` for the Undo
  button emitting; extend `frontend/tests/ui/state/use-workspace.test.ts` for
  the composed binding.

### Implementation for User Story 1

- [X] T017 [US1] Update the authoritative contract:
  `specs/001-standardize-api-responses/contracts/api-contract.json` gains an
  `UndoReceipt` schema (`item`, `entry`, `digest`, all non-nullable strings),
  `POST /api/pick` gains nullable `undo: {ref: UndoReceipt}`, and a new
  `POST /api/history/undo` route documents 200 `log_file`/`status`/`item`/
  `removed`, `validation_error` 422, `internal_error` 500, and
  `method_not_allowed` 405. Mirror both in
  `specs/001-standardize-api-responses/contracts/api-contract.md`. Add
  `RESPONSE_TYPE_NAMES['POST /api/history/undo'] = 'UndoHistoryResponse'` in
  `frontend/scripts/generate-api-contract.mjs`, then run
  `cd frontend && npm run generate:api`.
- [X] T018 [US1] Implement the web surface in `choosier/web.py`:
  `UndoReceiptModel` (`item` min length 1; `entry` min length 1 and no raw
  CR/LF; `digest` matching `^[0-9a-f]{64}$`), `UndoHistoryRequest` (`path`,
  nullable `log_file`, `receipt`), `UndoHistoryResponse`, and nullable
  `PickResponse.undo`. Add `@app.post("/api/history/undo")` named
  `undo_history`, convert the Pydantic receipt to `UndoReceipt`, call
  `services.HistoryService(log_path).undo(...)`, and return all four response
  fields. Set `undo` on the pick response only from `outcome.undo`. Add
  `"undo_history": ("services.HistoryService",)` to `ROUTE_DELEGATIONS` in
  `tests/test_services_boundaries.py`.
- [X] T019 [US1] Implement the TUI surface in `choosier/tui.py`: add
  `self._undo_receipt: UndoReceipt | None = None`, yield
  `Button("Undo", id="undo", disabled=True)` after `Open` in `#actions`, route
  `event.button.id == "undo"` to `_undo_pick`, and implement `_undo_pick` to
  call `HistoryService(self._current_log_path()).undo(receipt)`, show
  `Undid pick of <item>.`, `Could not undo <item>: history changed.`, or
  `Could not undo <item>: history is empty.`, clear the choice/preview/Open
  only when `self._current_choice == self._target / item`, then refresh panels. Set the
  receipt in `do_pick` only from `outcome.undo` for a logged, non-rotated pick.
- [X] T020 [US1] Implement the frontend API surface: add
  `undoHistory: 'POST /api/history/undo'` to `frontend/src/api-operations.ts`;
  add `api.undoHistory(body)` using `postJson` in `frontend/src/api.ts`; add
  manual `UndoHistoryRequest` and re-export `UndoReceipt` /
  `UndoHistoryResponse` in `frontend/src/types.ts`; update
  `frontend/tests/api-contract.test.mjs` from 16 to 17 operations (including
  the test titles), append `undoHistory` in route order, and assert the facade
  and request shape. Run `cd frontend && npm run check:api && npm run test:api`.
- [X] T021 [US1] Create `frontend/src/state/use-undo.ts` with a `receipt` ref, a
  `canUndo` computed, an `undoing` guard ref, `setReceipt`, `clear`, and
  `undo()`. `undo()` returns immediately when no receipt or already undoing;
  calls `api.undoHistory({path, log_file: logFile || null, receipt})`; sets
  `Undid pick of <item>.`, `Could not undo <item>: history changed.`, or
  `Could not undo <item>: history is empty.`; clears the receipt for all three
  domain statuses; calls `choice.invalidate()` only when
  `choice.choice.value?.item === item`; reports errors without clearing the
  receipt; and awaits `refresh()` in `finally`. Add the binding to
  `frontend/src/view-models.ts` and declare it in
  `frontend/src/state/use-workspace.ts` after `workspaceState` (so `refresh` is
  available) and before `usePicker`; the earlier reset callbacks may reference
  it because they run only after setup, matching the existing pattern.
- [X] T022 [US1] Add the web control: in `frontend/src/views/ChoiceBoard.vue`
  add a `defineProps` entry for `canUndo`/`undoLabel`, an `undo` emit, and a
  `<button type="button" class="board-undo" :disabled="!canUndo"
  :aria-label="undoLabel">Undo</button>` beside Open; wire `:can-undo`,
  `:undo-label`, and `@undo="undo"` from `frontend/src/App.vue`; add quiet
  secondary styling in `frontend/src/styles.css` next to `.board-open` that
  reuses the existing amber focus ring and disabled treatment.

**Checkpoint**: A logged pick can be undone with one action in both
interfaces, and the item is eligible again.

---

## Phase 4: User Story 2 — Know when undo is available (Priority: P2)

**Goal**: Undo is visibly unavailable whenever the latest pick attempt was not
logged, the target changed, history was mutated, or undo already completed;
messages explain the state and name the item.

**Independent Test**: Exercise a fresh session, a dry-run pick, an empty or
exhausted pick, a successful undo, a second undo attempt, archive/clear, and a
folder/log change. Verify the control state and messages without any history
change beyond the intended undo.

### Tests for User Story 2

- [X] T023 [P] [US2] Extend `tests/test_tui.py`: `#undo` starts disabled;
  dry-run, invalid-path, empty, exhausted, and filtered outcomes leave it
  disabled; a successful undo disables it; folder-input and log-input changes
  clear availability; archive and clear disable it only when the log actually
  changed; `Undo`/`Undo <item>` labels match availability; the changed and
  nothing-to-undo messages name the item; a second undo attempt removes
  nothing.
- [X] T024 [P] [US2] Extend `tests/test_web.py` and the frontend tests
  (`frontend/tests/ui/state/use-picker.test.ts`,
  `frontend/tests/ui/state/use-history-actions.test.ts`): every non-logged
  pick returns `undo: null`; a second undo returns `nothing_to_undo`; archive,
  clear, single removal, and batch removal notify the client only when they
  changed the log; path/log changes clear the receipt without a request.

### Implementation for User Story 2

- [X] T025 [US2] Update `choosier/tui.py` availability: clear
  `self._undo_receipt` at the start of every `do_pick`, whenever
  `_sync_filter_scope` detects a path/log change (including from
  `on_input_changed`), and after `_archive_history` / `_do_clear` only when
  `backup is not None` / `removed` is true. Add `_sync_undo_control()` that sets
  `#undo.disabled` and label `Undo <item>` / `Undo`, and call it from
  `on_mount`, `_refresh_panels`, `on_input_changed` when the scope changed, and
  after undo.
- [X] T026 [US2] Update the frontend state: `frontend/src/state/use-picker.ts`
  clears the receipt before validation and every request, sets it from
  `result.undo` on a picked response, and leaves it cleared for every other
  outcome and error; `frontend/src/state/use-history-actions.ts` gains an
  `onHistoryChanged` callback invoked only after `result.backup !== null`,
  `result.removed === true`, or `result.removed > 0`;
  `frontend/src/state/use-workspace.ts` calls `undo.clear()` from
  `resetOnPathChange` and `resetOnLogChange` and passes `onHistoryChanged:
  undo.clear`. Expose `canUndo` and `undoLabel` from
  `frontend/src/state/use-undo.ts` for the control.

**Checkpoint**: Undo availability strictly tracks the latest completed pick
attempt and the current session target.

---

## Phase 5: User Story 3 — Keep undo safe and keyboard-accessible (Priority: P3)

**Goal**: Undo changes one history entry and nothing else, is fully keyboard
operable with visible focus and an item-bearing accessible name, never
intercepts text-field undo, and fails safely.

**Independent Test**: Use only the keyboard to undo a pick in each interface;
inspect the accessible name; externally append, rewrite, and delete the log
between pick and undo; hash the target tree and the log; and run the CLI
boundary checks.

### Tests for User Story 3

- [X] T027 [P] [US3] Add TUI accessibility tests in `tests/test_tui.py`: Tab
  reaches `#undo` after Open, the button receives focus, its rendered label
  includes the item, Enter activates the undo, and no new key binding is
  registered for undo.
- [X] T028 [P] [US3] Add frontend accessibility tests in
  `frontend/tests/ui/views/ChoiceBoard.test.ts` and
  `frontend/tests/ui/state/use-shortcuts.test.ts`: `aria-label` is
  `Undo last pick: <item>` when available and
  `Undo last pick (nothing to undo)` otherwise; the button is a normal tab
  stop and Enter/Space activate it; `Ctrl+Z` inside a text input is not
  intercepted and does not call the picker.
- [X] T029 [P] [US3] Add conflict/failure tests in `tests/test_storage.py`,
  `tests/test_web.py`, and `tests/test_api_errors.py`: external append,
  external removal, full rewrite, malformed final line, and a 63-character or
  non-hex digest produce `changed`/422 with a byte-identical log; two sessions
  where the later pick makes the earlier session's undo refuse while the later
  session succeeds; a simulated `OSError` returns the existing 500 envelope
  and leaves bytes unchanged.
- [X] T030 [P] [US3] Add boundary tests in `tests/test_cli.py` and
  `tests/test_history_consistency.py`: `choosier --help` has no undo option;
  `--dry-run`, `--seed`, `--list`, prompt behavior, output lines, and exit
  codes `0`/`1`/`3`/`4` are unchanged; a CLI pick remains readable and
  undoable by the service; no undo state survives a restart.
- [X] T031 [P] [US3] Add side-effect tests in `tests/test_web.py` and
  `tests/test_history_consistency.py`: undo leaves the active path, log-file
  setting, filter selection, seed, dry-run setting, remembered folders, target
  files, and target folders unchanged; only the history log differs; no new
  persistent file exists other than the coordination lock.

### Implementation for User Story 3

- [X] T032 [US3] Finish TUI accessibility in `choosier/tui.py`: give `#undo`
  a tooltip that names the item when available, keep it enabled/disabled with
  `_sync_undo_control`, do not add a `Binding` or key handler for undo, and
  keep the label as the accessible name (`Undo <item>` / `Undo`).
- [X] T033 [US3] Finish web accessibility in `frontend/src/state/use-undo.ts`
  and `frontend/src/views/ChoiceBoard.vue`: compute
  `undoLabel` as `Undo last pick: <item>` / `Undo last pick (nothing to undo)`,
  keep visible text `Undo`, set `disabled` from `canUndo`, add no shortcut or
  `aria-keyshortcuts`, and rely on the existing `.board :focus-visible` amber
  ring.
- [X] T034 [US3] Harden adapter error handling in `choosier/tui.py` and
  `frontend/src/state/use-undo.ts`: on `ServiceError`/API error show the
  service message, retain the receipt for retry, and keep the interface
  usable; clear the receipt and refresh history after `changed`,
  `nothing_to_undo`, and `undone`; clear the choice/preview only when the
  current choice's item equals the undone item.

**Checkpoint**: Undo is safe under external edits, keyboard-only, and
side-effect free outside the one history line.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, manual validation, and the full repository gate.

- [X] T035 [P] Update `README.md` (TUI and web undo behavior, session-only
  availability, no CLI undo flag) and `CHANGELOG.md` (Unreleased bullet for Undo
  last pick, additive API route/field, hidden lock file).
- [X] T036 Run the manual scenarios in
  `specs/007-undo-last-pick/quickstart.md`: T1–T8 for the TUI, W1–W7 for the
  web UI, and the command-line boundary; record the observed results in the
  feature notes or PR body, including keyboard focus, accessible names, the
  one-second feedback check at the rotation limit, and the target-tree hash
  comparison.
- [X] T037 Run the full quality gate from the repository root across
  `choosier/`, `tests/`, and `frontend/`:
  `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy choosier main.py tests`, and
  `cd frontend && npm run check:api && npm run check:ui && npm run test:api &&
  npm run test:ui && npm run build`. Confirm 17 contract routes, 17 generated
  operations, no CLI diffs, no temp files left beside the log, and the lock
  file excluded from candidates.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No prerequisites. T002 depends on T001; T004 depends on
  T003.
- **Foundational (Phase 2)**: Depends on Setup. T005–T007 all edit
  `choosier/storage.py`, so run them in order; T008 waits for T006; T009 waits
  for T007 and T008; T010 waits for T009; T011/T012 wait for T005–T010.
  Every user story is blocked by this phase.
- **US1 (Phase 3)**: Depends on Foundational. Tests T013–T016 can be written
  first in parallel; T017–T022 then implement contract, web, TUI, and
  frontend. US1 is the MVP.
- **US2 (Phase 4)**: Depends on US1 because it refines the same controls and
  receipt lifecycle. T023/T024 can run in parallel; T025 and T026 touch
  different codebases and can run in parallel after the tests.
- **US3 (Phase 5)**: Depends on US1 and US2. T027–T031 are independent test
  files and can run in parallel; T032–T034 harden the same files as US1/US2
  and run in order.
- **Polish (Phase 6)**: Depends on all desired stories. T035 can run while
  T036 is prepared; T037 is last.

### User Story Dependencies

- **US1 (P1)**: Fully independent increment after Foundational. Delivers the
  MVP.
- **US2 (P2)**: Adds availability and clearing rules on top of US1; it does
  not change the core undo result.
- **US3 (P3)**: Adds accessibility and safety guarantees on top of US1 and
  US2; it does not change selection or history format.

### Within Each User Story

- Write tests first and confirm they fail for the intended reason.
- Contract/schema changes before route/facade consumers.
- Storage/service/core before adapters.
- Adapter implementation before its behavior tests pass.
- Refresh behavior is part of the implementation, not a test-only concern.

### Parallel Opportunities

- Setup: T001→T002 and T003→T004 are independent chains.
- Foundational: T011 and T012 are different test files and can run in
  parallel once T005–T010 are complete.
- US1: T013–T016 are four different test files; T017 (contract) and T018
  (web) can run in parallel, but T020 depends on T017's generated types.
- US2: T023 (TUI tests) and T024 (web/frontend tests) are parallel; T025
  (`choosier/tui.py`) and T026 (`frontend/src/state/`) are parallel.
- US3: T027–T031 are five independent test files; run them in parallel.
- Polish: T035 (docs) can run alongside T036 (manual checklist).

### Parallel Example: User Story 1 Tests

```bash
# Four independent test files:
Task: "Add TUI undo tests in tests/test_tui.py"
Task: "Add web undo tests in tests/test_web.py"
Task: "Add API contract tests in tests/test_api_contract.py"
Task: "Add frontend undo tests in frontend/tests/ui/state/use-undo.test.ts"
```

### Parallel Example: User Story 3 Tests

```bash
# Five independent test surfaces:
Task: "TUI keyboard/accessibility tests in tests/test_tui.py"
Task: "Frontend accessibility tests in frontend/tests/ui/"
Task: "Conflict/failure tests in tests/test_storage.py, tests/test_web.py"
Task: "CLI boundary tests in tests/test_cli.py"
Task: "Side-effect tests in tests/test_web.py, tests/test_history_consistency.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocking).
3. Complete Phase 3: US1 — core undo reachable from both interfaces.
4. **STOP and VALIDATE**: run the US1 tests and quickstart T1/T3/T4 and
   W1/W6; confirm exactly one line is removed and eligibility returns.
5. Demo the MVP before adding availability polish.

### Incremental Delivery

1. Setup + Foundational → core receipt and verified removal, no UI.
2. US1 → both interfaces can undo one pick (MVP).
3. US2 → availability, labels, and clearing rules match the session.
4. US3 → keyboard accessibility, conflict safety, and boundary guarantees.
5. Polish → docs, quickstart, and the full gate.

### Commit Strategy

Constitution §5 requires each task to be committed separately after its tests
pass. Use Conventional Commits, one task per commit, for example
`feat(storage): add verified undo receipt`, `feat(web): expose history undo
route`, `feat(ui): add undo last pick`, `test(tui): cover undo availability`,
`docs: document undo last pick`.

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependency.
- The lock file is coordination metadata: zero bytes on POSIX and a single NUL
  byte on Windows; it is never read as application state and is excluded from
  candidates.
- The receipt is never persisted. A restart, page reload, folder change, log
  change, non-logged pick, successful undo, or real history mutation clears
  availability.
- The one-shot CLI is untouched: no flag, output, prompt, or exit-code change.
- Stop at each checkpoint to validate the story independently.
