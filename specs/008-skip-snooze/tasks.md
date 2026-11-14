# Tasks: Skip and Snooze

**Input**: Design documents from `/specs/008-skip-snooze/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/skip-snooze.md, quickstart.md

**Tests**: Included. The specification does not request TDD, but plan.md and
constitution principle V require automated coverage for the core, services,
API contract, TUI, and frontend. Write each test with its implementation; where
practical, confirm the new test fails before the implementation lands.

**Organization**: Tasks are grouped by user story. US1 is the MVP; US2 and US3
build on it without changing its behavior.

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

**Purpose**: Confirm the baseline and prepare one reusable validator that both
filters and skips will use.

- [X] T001 Run the existing quality gate on a clean tree and record the result: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy choosier main.py tests`, and in `frontend/` `npm run check:api && npm run test:api && npm run check:ui && npm run test:ui && npm run build`. Do not change files; stop and report if anything already fails.
- [X] T002 In `choosier/filters.py`, extend the private `_validate_entry_name` into a reusable module-level `validate_entry_name(value: object, field: str) -> str` that keeps the exact existing rules — strings only, at most `MAX_VALUE_LENGTH` (1,024) characters, non-empty, not `.` or `..`, and no `/` or NUL — and reports `field` in each message; keep `_validate_entry_name` as a thin wrapper with `field="excluded_entries"` so `normalize_exclusions` behavior and messages are unchanged, then run `uv run pytest tests/test_filters.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared skip input, selection effects, and additive API surface.
No story can work until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create `choosier/skip.py` with `SKIP_COOLDOWN_SECONDS = 600`, `MAX_SKIPPED_ENTRIES = 20000`, a frozen `SkipSelection` dataclass holding `names: frozenset[str] = frozenset()`, a `SkipValidationError(ValueError)`, and `normalize_skips(values: Iterable[object]) -> SkipSelection` that validates, deduplicates, and bounds names using `filters.validate_entry_name(value, "skipped_entries")` and enforces the verbatim rule "at most 20,000 names; each non-empty, not `.` or `..`, at most 1,024 characters, no `/` or NUL"; it uses only the standard library.
- [X] T004 [P] Create `tests/test_skip.py` covering `normalize_skips` for valid names, duplicates collapsing, Unicode/space/punctuation names, `SKIP_COOLDOWN_SECONDS == 600`, `MAX_SKIPPED_ENTRIES == 20000`, and rejection of a non-string, an empty name, `.`, `..`, a 1,025-character name, a name containing `/` or NUL, and 20,001 names.
- [X] T005 Extend `choosier/services/models.py` so `StateSnapshot` gains `skipped: tuple[str, ...] = ()`, `skipped_total: int = 0`, `skipped_present: tuple[str, ...] = ()`, and `all_skipped: bool = False`, and `PickStatus` gains `"all_skipped"` while keeping the existing six values and their meanings.
- [X] T006 Extend `choosier/services/state.py`: `build_state` and `_empty_snapshot` accept `skips: SkipSelection | None = None`; build the filtered, unlogged eligible pool exactly as now, then compute `skipped_present` from names present in a full `os.scandir(target)` listing (so hidden/mode options never prune a skip), `skipped` as those names that are not currently logged (sorted, untruncated), `remaining` excluding every skipped name that exists, `skipped_total = len(skipped)`, and `all_skipped` true exactly when at least one filtered, unlogged entry exists and every one is in `skips.names`; invalid paths return empty skip fields and existing fields keep their meanings.
- [X] T007 Extend `choosier/services/pick.py`: `pick` accepts `skips: SkipSelection | None = None`; after building the filtered, unlogged pool, keep the existing empty/exhausted/filtered statuses when that pool is empty, otherwise exclude skipped names and return `PickOutcome(status="all_skipped")` when the resulting pool is empty, and never return a skipped name as `item`.
- [X] T008 [P] Extend `tests/test_services_state.py` with cases for: a skipped entry leaving `remaining` and `remaining_total`; `skipped`/`skipped_total` excluding logged names while `skipped_present` still includes them; deleted/renamed names absent from both skip fields; a logged entry whose history is removed becoming displayable again; filters and folder options not pruning skips; `all_skipped` true only when every eligible entry is skipped; `filtered_exhausted` still returned when matching entries are all picked; and `skipped` untruncated by `max_lines=1`.
- [X] T009 [P] Extend `tests/test_services_pick.py` with cases for: a pick never returning a skipped name across repeated seeded picks; `all_skipped` with no item, no log write, and byte-identical history; `empty`, `exhausted`, `filtered_empty`, and `filtered_exhausted` unchanged when skips are empty; a skipped name that is filtered out still producing the existing filtered status; and determinism preserved for a fixed target, filters, seed, history, and skip set.
- [X] T010 Extend `choosier/web.py`: add `skipped_entries: list[str] = Field(default_factory=list)` with a validator raising `ValueError` for malformed values and a `skip_selection` property on `FilterExclusionsRequest`; extend `StateResponse` with `skipped: list[str] = []`, `skipped_total: int = 0`, `skipped_present: list[str] = []`, `all_skipped: bool = False`; add the four fields to `FilteredStateResponse`; extend `PickResponse.status` with `"all_skipped"`; pass `skips=request.skip_selection` through `POST /api/state` and `POST /api/pick`; leave `GET /api/state` behavior unchanged apart from serializing the empty skip fields.
- [X] T011 [P] Extend `tests/test_web.py` with cases for: `POST /api/state` echoing `skipped`/`skipped_total`/`skipped_present`/`all_skipped`; `GET /api/state` returning the four empty fields; `POST /api/pick` accepting `skipped_entries`, never returning a skipped item, and returning `200` with `all_skipped`, `item: null`, `logged: false`, `preview: null`, `undo: null`, and unchanged log bytes when everything is skipped; and stale names being ignored rather than rejected.
- [X] T012 Update `specs/001-standardize-api-responses/contracts/api-contract.json`: add the four additive response fields to both `/api/state` entries and the `all_skipped` enum value to `POST /api/pick`, without adding, removing, or renaming any route; then run `cd frontend && npm run generate:api` so `frontend/src/api-contract.generated.ts` is regenerated rather than hand-edited, and confirm `npm run check:api` passes.
- [X] T013 [P] Extend `tests/test_api_contract.py` to assert the route inventory is still exactly 17 with no skip route, `POST /api/state` and `GET /api/state` expose exactly the existing fields plus `skipped`, `skipped_total`, `skipped_present`, and `all_skipped` with the documented types, and the `POST /api/pick` enum contains exactly the existing six values plus `all_skipped`.
- [X] T014 [P] Extend `tests/test_api_errors.py` with malformed `skipped_entries` payloads — a non-array, a non-string element, an empty name, `.`, `..`, a 1,025-character name, a name containing `/` or NUL, and 20,001 names — each returning the existing `validation_error` 422 envelope, and confirm a stale but well-formed name is accepted.
- [X] T015 Extend `frontend/src/types.ts`: add `skipped_entries?: string[]` to `FilteredStateRequest` and `PickRequest`, add `skipped: string[]`, `skipped_total: number`, `skipped_present: string[]`, and `all_skipped: boolean` to `FilteredStateResponse`, and add `'all_skipped'` to the pick status union; keep all existing fields and optionality unchanged.

**Checkpoint**: Core, services, HTTP contract, generated client types, and all
backend tests are ready. User stories can now proceed.

---

## Phase 3: User Story 1 - Defer an item without picking it (Priority: P1) 🎯 MVP

**Goal**: A person marks one eligible remaining entry **Not now**; it leaves the
remaining pool, cannot be picked, writes no history, and returns after ten
minutes or in the next session.

**Independent Test**: In a folder with known entries and no history, skip one
entry, confirm it disappears from remaining and is never chosen by repeated
picks, confirm the history log is unchanged, advance the injected clock past the
cooldown and confirm it returns, then reload/restart and confirm it is eligible.

### Frontend for User Story 1

- [X] T016 [P] [US1] Create `frontend/src/state/use-skip.ts` with `SKIP_COOLDOWN_MS = 600_000`, a `SkipRecord { name: string; expiresAt: number }`, and `useSkip(deps)` where `deps` supplies `now` (default `() => performance.now()`), `status`, `refresh`, and `isRemaining: (name: string) => boolean`; expose `records`, `names` (a computed `readonly string[]`), `skipping`, `skip(name)`, `reconcile(sent, present)`, and `reset()`; `skip` refuses when a skip is in flight or the name is not remaining (message `Could not skip <item>: it is no longer available.`), prunes an expired record before adding a fresh `expiresAt = now() + SKIP_COOLDOWN_MS`, refreshes, and sets `Skipped <item>. It returns in ten minutes or when this session ends.`; run a one-second `window.setInterval` tick that drops expired records, calls `reset` on unmount, and never writes storage.
- [ ] T017 [P] [US1] Create `frontend/tests/ui/state/use-skip.test.ts` using a fake `now` and Vitest fake timers to cover: skip records one name and exposes it in `names`; a duplicate skip replaces the expiry instead of duplicating; expiry removes the name and triggers a refresh; `reconcile` removes only names included in the `sent` snapshot and present in `present`; a name absent from `present` is pruned; a name present but logged stays in the internal map; `reset` clears everything; skip is refused for a non-remaining name and while one is in flight; and no storage or cookie API is touched.
- [ ] T018 [US1] Extend `frontend/src/state/use-workspace-state.ts`: accept `skippedEntries: ComputedRef<readonly string[]>` and send `skipped_entries: [...skippedEntries.value]` in `api.stateFiltered`; capture that array per request and change `onState` to `(response, sentSkips) => void`, invoking it with `[]` for the blank-path case so the composition root can reconcile only what was sent.
- [ ] T019 [US1] Extend `frontend/src/state/use-picker.ts`: accept `skips` (`names`, `remove`, `skipping`) and send `skipped_entries: [...skips.names.value]`; expose `picking: Ref<boolean>` and refuse a pick while a skip is in flight with `Wait for the skip action to finish.`; add `result.status === 'all_skipped'` → `Every available item is skipped. Restore skipped items to pick again.`; and after a `picked` result defensively call `skips.remove(item)` when that item was skipped.
- [ ] T020 [US1] Wire `frontend/src/state/use-workspace.ts`: declare `let skip!: SkipBinding` before `useWorkspaceState`, pass `skippedEntries: skip.names` and an `onState` that calls `skip.reconcile(sentSkips, response?.skipped_present ?? [])`, then assign `skip = useSkip({ ... isRemaining: (name) => (workspaceState.state.value?.remaining ?? []).includes(name), refresh: workspaceState.refresh })`; call `skip.reset()` in `resetOnPathChange` and `resetOnLogChange`, pass `skips` to `usePicker`, and add `skip` to the returned binding.
- [ ] T021 [P] [US1] Extend `frontend/tests/ui/state/use-workspace-state.test.ts` to assert `skipped_entries` is sent on every state request, that the skip snapshot is captured per request, and that `onState` receives the snapshot used for that response.
- [ ] T022 [P] [US1] Extend `frontend/tests/ui/state/use-picker.test.ts` to assert the pick body carries `skipped_entries`, the all-skipped message, a refused pick while `skipping` is true, a picked item removing a stale skip, and existing outcomes unchanged with no skips.
- [ ] T023 [P] [US1] Extend `frontend/tests/ui/state/use-workspace.test.ts` to assert path and log changes call `skip.reset()`, the binding exposes `skip`, and a state response reconciles skips only from its own request snapshot.
- [ ] T024 [US1] Update `frontend/src/views/RemainingPanel.vue`: add an emitted `skip` event and a visible `Not now` button per remaining row with `:aria-label="'Skip ' + name"`, keeping the existing header, list, and empty state; the button is a native focusable `<button>` and is rendered only for rows in `items`.
- [ ] T025 [US1] Update `frontend/src/App.vue`: bind `skip` from the workspace binding to the panel's `@skip` event and keep the existing remaining props unchanged.
- [ ] T026 [P] [US1] Extend `frontend/tests/ui/views/RemainingPanel.test.ts` to assert one `Not now` button per row, the exact `Skip <name>` accessible name, the emitted `skip` name on click and Enter, and no buttons when the list is empty.

### TUI for User Story 1

- [ ] T027 [US1] Update `choosier/tui.py`: add `self._skips: dict[str, float]` and an injectable `self._skip_clock: Callable[[], float] = time.monotonic`; clear `_skips` inside `_sync_filter_scope` alongside filters so folder/log changes reset them; start `self.set_interval(1, self._expire_skips)` in `on_mount`; replace the `#remaining` body with a `#remaining-summary` Static and a `#remaining-list` OptionList plus a `#skip` Button labelled `Not now: <item>` for the highlighted row and disabled when none; add `_selected_remaining_name()`, `_skip_selection()`, and `_skip_now()` that re-build shared state with no skips to confirm the name is still eligible before adding `expiresAt = clock() + SKIP_COOLDOWN_SECONDS`; pass `skips=` to every `build_state` call in `_refresh_panels` and to `pick` in `do_pick`; show `Every available item is skipped. Restore skipped items to pick again.` for `all_skipped`; show `Skipped <item>. It returns in ten minutes or when this session ends.`; `_expire_skips` removes records at or past expiry and refreshes the panels.
- [ ] T028 [P] [US1] Extend `tests/test_tui.py` for US1: skip via the button removes the entry from `#remaining-list`/summary and decreases the remaining count; repeated picks never choose it; the history log bytes are unchanged by skipping; an injected `_skip_clock` advanced past 600 seconds returns the entry without another action; `_sync_filter_scope` clears skips on a path change; the `all_skipped` pick message appears; and the pick still logs normally for a non-skipped entry.

**Checkpoint**: US1 is fully functional in both interfaces and independently
verifiable. The remaining and pick behavior is skip-aware, and skips expire or
reset correctly.

---

## Phase 4: User Story 2 - See and control deferred items (Priority: P2)

**Goal**: Deferred entries appear in a separate list with their return time,
each can be restored, all can be restored, and the all-skipped state is
explained distinctly with a restore path.

**Independent Test**: Skip two entries, confirm both appear in a separate
skipped list with countdowns, restore one and then the other, verify counts and
history stay correct, skip everything and confirm the distinct all-skipped
message plus restore-all.

### Session store and composition

- [ ] T029 [US2] Extend `frontend/src/state/use-skip.ts` with `restore(name)`, `restoreAll()`, `skippedRows` (name plus formatted remaining time sorted by expiry), and a `formatRemaining(ms)` helper that renders `m:ss`; restore removes only the named record and sets `Restored <item>.`; restore-all removes every record and sets `Restored N skipped items.` (singular `item` for one); both refuse with `Could not restore <item>: it is no longer available.` when nothing matches and never write history.
- [ ] T030 [P] [US2] Extend `frontend/tests/ui/state/use-skip.test.ts` with restore-one, restore-all (including the one-item message), restore of an unknown name, countdown formatting, and a restore that leaves other records and history untouched.
- [ ] T031 [US2] Extend `frontend/src/view-models.ts` `WorkspaceBinding` with `skipped: ComputedRef<readonly { name: string; returnsIn: string }[]>`, `skippedTotal: ComputedRef<number>`, `allSkipped: ComputedRef<boolean>`, `skipping: Ref<boolean>`, `skipEntry: (name: string) => Promise<void>`, `restoreSkipped: (name: string) => Promise<void>`, and `restoreAllSkipped: () => Promise<void>`.
- [ ] T032 [US2] Extend `frontend/src/state/use-workspace.ts` to expose the T031 surface, deriving `skipped`/`skippedTotal` from `skip.skippedRows` and `allSkipped` from `workspaceState.state.value?.all_skipped ?? false`.
- [ ] T033 [US2] Update `frontend/src/App.vue` to pass `:skipped`, `:skipped-total`, and `:all-skipped` to `RemainingPanel` and bind `@restore` and `@restore-all` to the workspace actions.

### Web skipped view

- [ ] T034 [US2] Update `frontend/src/views/RemainingPanel.vue` with a separate `Skipped` section below the remaining list: each row shows the name and its countdown with a native `Restore` button whose `aria-label` is `Restore <item>, returns in <time>`, plus a `Restore all` button disabled when the list is empty; apply the empty-state precedence from `contracts/skip-snooze.md` — `all_skipped` shows `Every available item is skipped. Restore skipped items to pick again.` with restore-all visible, `total === 0 && skippedTotal > 0` shows `No items are available right now.` with the skipped section visible, and the existing invalid/empty/exhausted/filtered messages are unchanged; style the new controls with the existing secondary-action and panel classes in `frontend/src/styles.css` without a new palette, typeface, card, or animation.
- [ ] T035 [P] [US2] Extend `frontend/tests/ui/views/RemainingPanel.test.ts` for the skipped section: rows and countdowns render, `Restore` and `Restore all` emit with the right names, accessible names include the return time, restore-all is disabled when empty, and all three empty-state branches render the exact messages.

### TUI skipped view

- [ ] T036 [US2] Update `choosier/tui.py`: add a `#skipped-list` OptionList and `#restore` / `#restore-all` Buttons inside the Remaining tab, rendering `<name> — returns in <m:ss>` rows from the snapshot's `skipped` order; label the buttons `Restore: <item> (returns in <time>)` and `Restore all`, disable them when nothing is skipped, and add `on_button_pressed` branches plus `_restore_selected()` / `_restore_all()`; when `all_skipped` is true the remaining summary shows `Every available item is skipped. Restore skipped items to pick again.` and keeps restore-all enabled; when nothing remains but skips are displayed the summary says `No items are available right now.`; use the exact restore messages from `contracts/skip-snooze.md` and refresh panels after each action.
- [ ] T037 [P] [US2] Extend `tests/test_tui.py` for US2: skipped rows show names and countdowns, restore one returns only that entry, restore all clears the list, both messages match exactly, restore-all is disabled when empty, the all-skipped summary and restore-all availability appear when everything is skipped, and the neutral no-items message replaces the picked-out message.

**Checkpoint**: US1 and US2 work independently. Deferred entries are visible,
counted, restorable, and never mistaken for picked or filtered entries.

---

## Phase 5: User Story 3 - Trust that skip never rewrites history (Priority: P3)

**Goal**: Prove skip, restore, restore-all, expiry, and target/session changes
never touch history, target content, filters, choice, preview, seed, dry-run,
path memory, or the CLI; make every control keyboard-operable with clear
feedback, and explain refusals and stale actions.

**Independent Test**: Record history and target hashes, then skip, restore, let a
skip expire, restore all, change targets, and restart in both interfaces;
confirm history and target content never change, the CLI is unchanged, and a
keyboard-only pass reaches every named control.

- [ ] T038 [US3] Update `choosier/tui.py` so every skip/restore path reports a refusal with `Could not skip <item>: it is no longer available.` or the restore equivalent when the entry vanished or a pick is in progress, moves focus to a sensible control after each action, and keeps `#skip`, `#restore`, `#restore-all`, and the lists reachable in Tab order with the existing Textual focus styling; do not add a key binding that conflicts with inputs.
- [ ] T039 [P] [US3] Extend `tests/test_tui.py` with keyboard-only coverage using `run_test` and `pilot.press`/`pilot.click`: Tab reaches `#remaining-list`, `#skip`, `#skipped-list`, `#restore`, `#restore-all`; each button carries the entry name in its label; a stale skip/restore reports the exact refusal and leaves history and target bytes unchanged.
- [ ] T040 [US3] Update `frontend/src/views/RemainingPanel.vue` and `frontend/src/styles.css` for the accessibility contract: native buttons only, `aria-label` naming the entry (and return time for restore), the existing visible focus ring, a polite status announcement through the existing `role="status"` bar, and no new keyboard shortcut or text-field interception.
- [ ] T041 [P] [US3] Extend `frontend/tests/ui/views/RemainingPanel.test.ts` and `frontend/tests/ui/state/use-skip.test.ts` for accessibility and refusal: every control has an accessible name, Tab order is DOM order, refusal messages name the entry, and no skip or restore touches storage, history, or the current choice.
- [ ] T042 [P] [US3] Extend `tests/test_history_consistency.py`: capture `sha256` of the history log and a sorted target listing, then perform skip, restore, restore-all, expiry via an injected clock, folder change, log-setting change, all-skipped pick, restart/new session, and a concurrent second session; assert both hashes and the entry listing are identical (or the log is still absent), no `.lock`/skip/cooldown file appears, and no filter, seed, dry-run, choice, preview, or path-memory value changes.
- [ ] T043 [P] [US3] Extend `tests/test_cli.py` with a guard that `choosier --help` contains no skip/snooze option and that the existing flags, prompt flow, output, and exit codes are unchanged; do not add any CLI branch for skips.
- [ ] T044 [P] [US3] Extend `tests/test_web.py` with overlap and concurrency checks: a pick carrying a skip snapshot never returns a skipped name; a second independent client may pick a name skipped by the first; the first client's next state hides that name from `skipped` but keeps it in `skipped_present`; and a state response never prunes a skip added after its request was sent.

**Checkpoint**: All three stories pass independently, and the "never rewrites
history" promise is enforced by tests rather than inspection.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, end-to-end validation, and contract invariants.

- [ ] T045 Add a `Skip and snooze` section to `README.md` after the Undo section: the Not now action, the fixed ten-minute cooldown capped by session end, the separate skipped list with restore and restore-all, the all-skipped outcome, per-session/per-tab independence, and that no history, target, filter, seed, dry-run, choice, or path-memory state changes; state that the CLI is unchanged.
- [ ] T046 Add an entry under `CHANGELOG.md` `## Unreleased` describing the TUI and web skip behavior, the separate skipped list and restore actions, the all-skipped outcome, and the additive API fields without a new route or persistent state.
- [ ] T047 Run the complete quality gate from `specs/008-skip-snooze/quickstart.md` `## Automated checks`: all pytest suites, `ruff check`, `ruff format --check`, `mypy`, `npm run check:api`, `npm run test:api`, `npm run check:ui`, `npm run test:ui`, `npm run build`, and `uv build`; confirm the frontend build writes `choosier/web_static` and every command passes.
- [ ] T048 [P] Verify the frozen boundaries: `specs/001-standardize-api-responses/contracts/api-contract.json` still has exactly 17 routes and the same error codes, `git diff --stat pyproject.toml` is empty, no new dependency or route exists, and `frontend/src/api-contract.generated.ts` matches `npm run generate:api` output.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T002 blocks the skip validator reuse.
- **Foundational (Phase 2)**: depends on T002; blocks every user story.
  T003 → T005 → T006 → T007 → T010 → T012 → T015 in that order; the test
  tasks in the same phase run after their implementation task.
- **US1 (Phase 3)**: depends on Phase 2; T016 → T018 → T019 → T020 and
  T024 → T025; T027 is independent of the frontend chain.
- **US2 (Phase 4)**: depends on US1; T029 → T031 → T032 → T033 → T034 and
  T029 → T036.
- **US3 (Phase 5)**: depends on US1 and US2.
- **Polish (Phase 6)**: depends on all three stories; T047 depends on T045 and
  T046 for a complete diff.

### User Story Dependencies

- **US1 (P1)**: no story dependencies; MVP.
- **US2 (P2)**: depends on US1's session store and skip-aware state; no change
  to US1 behavior.
- **US3 (P3)**: depends on US1 and US2 because it verifies their combined
  invariants and accessibility.

### Within Each User Story

- Contract and service tests fail first, then implementation.
- Python core before adapters; adapters before panels.
- Backend before frontend where the wire shape is shared.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T003, T004, T008, T009, T011, T013, T014 can run side by side once their
  prerequisites exist; T005–T007 and T010 form the serial core chain.
- Within US1: T016+T017 with T021–T023 and T026 once their deps exist; T027
  (TUI) can proceed in parallel with the frontend chain.
- Within US2: T030, T035, and T037 in parallel; T034 and T036 are the two
  interface implementations.
- Within US3: T039, T041, T042, T043, and T044 in parallel; T038 and T040 are
  the two interface edits.

---

## Parallel Example: User Story 1

```text
Frontend chain:  T016 use-skip.ts → T018 use-workspace-state.ts
                 → T019 use-picker.ts → T020 use-workspace.ts
                 → T024 RemainingPanel.vue → T025 App.vue
Frontend tests:  T017, T021, T022, T023, T026 (parallel after their units)
TUI chain:       T027 tui.py → T028 test_tui.py (parallel with frontend chain)
```

## Parallel Example: User Story 2

```text
Web:  T029 use-skip.ts → T031 view-models.ts → T032 use-workspace.ts
      → T033 App.vue → T034 RemainingPanel.vue
TUI:  T036 tui.py
Tests: T030, T035, T037 (parallel once their units exist)
```

## Parallel Example: User Story 3

```text
T038 tui.py · T040 RemainingPanel.vue/styles.css
T039 test_tui.py · T041 frontend a11y tests · T042 history consistency
T043 test_cli.py · T044 test_web.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 in both interfaces.
3. Stop and validate: skip one entry, pick around it, advance the clock, restart
   the session, and confirm history is byte-identical.
4. Ship the MVP if the skipped list is acceptable as "entries return after the
   cooldown"; otherwise continue to US2 before release.

### Incremental Delivery

1. Foundation → skip-aware state, pick, and API contract.
2. US1 → defer without picking in TUI and web (MVP).
3. US2 → visible skipped list, per-entry restore, restore-all, all-skipped.
4. US3 → invariant, concurrency, CLI, and accessibility proof.
5. Polish → docs, changelog, full gate, contract check.

### Notes

- `[P]` marks different-file work with no incomplete dependency.
- The core stays time-free: only the TUI and web units own clocks.
- Never write skip state to history, path memory, browser storage, or cookies.
- Stop at each checkpoint and run the story's independent test.
