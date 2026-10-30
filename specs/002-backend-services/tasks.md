---

description: "Task list for backend service extraction and unified data access"
---

# Tasks: Backend Service Extraction and Unified Data Access

**Input**: Design documents from `/specs/002-backend-services/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/service-boundaries.md](./contracts/service-boundaries.md),
[quickstart.md](./quickstart.md)

**Tests**: Tests are required by `FR-018` and `SC-004`. Existing behavior tests
keep their assertions; only imports and patch targets move. Direct service tests
are added in the user-story phases that require them.

**Organization**: Tasks are grouped by user story. User Story 1 is the P1
behavior-preserving extraction; the shared service package it depends on is
completed in the Foundational phase so every story can build on one foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (`US1`–`US4`)
- Every task includes an exact file path or an exact command with its target files

## Path Conventions

- Python package: `choosier/`
- Tests: `tests/`
- Packaging metadata: `pyproject.toml`
- Documentation: `README.md`, `CHANGELOG.md`
- Frozen reference: `specs/001-standardize-api-responses/contracts/api-contract.json`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package skeleton and make setuptools include it.

- [X] T001 [P] Create the `choosier/services/` package with a docstring-only `choosier/services/__init__.py`; exports are added in T012.
- [X] T002 [P] Update `pyproject.toml` under `[tool.setuptools]` to `packages = ["choosier", "choosier.services"]` so the wheel and sdist contain the new subpackage.

**Checkpoint**: The package exists and packaging metadata knows about it.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the interface-neutral service layer and the single structured
history read primitive. Every user story depends on this phase.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T003 [P] Create `choosier/services/errors.py` with `FailureKind(StrEnum)` values `INVALID_INPUT`, `FORBIDDEN`, `NOT_FOUND`, `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `RANGE_NOT_SATISFIABLE`, `IO_ERROR`, and `ServiceError(kind, message, details=None)` storing `kind`, `message`, and `details` with no HTTP status, framework type, or UI type.
- [X] T004 [P] Create `choosier/services/models.py` with the frozen dataclasses from `contracts/service-boundaries.md` §4: `BrowseEntry(name, is_dir)`, `BrowseListing(path, parent, entries)`, `HistorySnapshot(entries, logged, display)`, `StateSnapshot(valid_path, path, log_file, remaining, remaining_total, history, history_total)`, `PickStatus = Literal["picked", "empty", "exhausted", "invalid_path"]`, `PickOutcome(status, log_file, item=None, logged=False, preview=None)`, and `OpenOutcome(name)`; import `LogEntry` from `choosier.storage` and `Preview` from `choosier.preview`.
- [X] T005 [P] Refactor `choosier/storage.py` so `read_log_entries(log_file, *, ignore_errors: bool = True)` is the single structured reader: keep `parse_log_line` as the single line parser, return `[]` on `OSError` when tolerant, re-raise when `ignore_errors=False`, derive `load_log` and `get_logged_items` from it (keep `get_logged_items`'s `exists()` check followed by `read_log_entries(..., ignore_errors=False)`), keep `_parse_log_line` as a thin compatibility wrapper returning `parse_log_line(line)[1]`, and leave append, rotation, atomic rewrite, archive, and clear mechanics untouched.
- [X] T006 Create `choosier/services/history.py` with `HistoryService(log_file)`; expand `~` once; add `log_file` property, `snapshot(*, ignore_errors=True)`, `read_entries`, `logged_items`, `display_lines`, `append`, `remove`, `remove_many`, `archive`, and `clear` exactly as specified in `contracts/service-boundaries.md` §5.5; call `storage.<function>` through the module so the patch seams work; map `OSError` to `ServiceError(IO_ERROR, ...)` with the exact messages `"Error writing log: {e}"`, `"Error removing history item: {e}"`, `"Error removing history items: {e}"`, `"Error archiving log: {e}"`, and `"Error resetting log: {e}"`.
- [X] T007 [P] Create `choosier/services/browse.py` with `browse_directory(path)` per `contracts/service-boundaries.md` §5.1: expand `~`, return `ServiceError(NOT_FOUND, "Not a directory")` for a missing/non-directory target, map `iterdir()` `OSError` to `ServiceError(FORBIDDEN, f"Cannot list: {e}")`, sort with `(not p.is_dir(), p.name.lower())`, and set `parent=None` at a filesystem root; use `pathlib.Path` so class-level `Path.iterdir` patching remains effective.
- [X] T008 [P] Create `choosier/services/state.py` with `PANEL_MAX_LINES = 200` and `build_state(path, log_file=None, *, include_hidden=False, files_only=False, dirs_only=False, max_lines=PANEL_MAX_LINES)` per `contracts/service-boundaries.md` §5.2: resolve the log through `chooser.resolve_log_path` semantics including blank fallback and `~` expansion; return `valid_path=False` with empty remaining/history and zero totals for a non-directory target; let that invalid-path outcome take precedence over the filter conflict; raise `ServiceError(INVALID_INPUT, "files_only and dirs_only are mutually exclusive")` for conflicting filters; use `list_candidates`; treat `FileNotFoundError` as an empty candidate set; read history once through `HistoryService.snapshot()`; return `remaining[:max_lines]` and `history[-max_lines:]` when capped while `remaining_total` and `history_total` remain full counts; propagate unexpected listing errors unchanged.
- [X] T009 [P] Create `choosier/services/pick.py` with `pick(path, log_file=None, *, seed=None, dry_run=False, include_hidden=False, files_only=False, dirs_only=False, commit=True, include_preview=False)` per `contracts/service-boundaries.md` §5.3: resolve target/log path like `build_state`; return `invalid_path` for a non-directory target before any filter check; use `random.Random(seed)` when a seed is supplied; raise `ServiceError(INVALID_INPUT, "files_only and dirs_only are mutually exclusive")` on conflict; call `chooser.get_unselected_item`; classify no eligible item as `"exhausted"` when `any(target.iterdir())` is true and `"empty"` otherwise; append through `HistoryService.append` only when `commit` is true and `dry_run` is false, then set `logged=True`; map append `OSError` through `HistoryService` to `"Error writing log: {e}"`; keep `logged=False` for `dry_run` and `commit=False`; generate `preview_entry(target / item)` only when `include_preview` is true, after logging, and let history-read/listing errors propagate as today.
- [ ] T010 [P] Create `choosier/services/opening.py` with `open_entry(path)` per `contracts/service-boundaries.md` §5.4: expand `~`, raise `ServiceError(NOT_FOUND, "Entry is gone")` when the path does not exist, call `launcher.launch_path` through the module, map `OSError` to `ServiceError(IO_ERROR, f"Cannot open: {e}")`, and return `OpenOutcome(name=path.name)` on success.
- [ ] T011 [P] Create `choosier/web_media.py` with `THUMBNAIL_MAX_SIZE`, `THUMBNAIL_QUALITY`, `PREVIEW_MAX_SIZE`, `PREVIEW_QUALITY`, frozen `ImagePayload(data, media_type)` and `VideoFile(path, media_type, stat_result)`, plus `read_image(path, index=None)`, `make_thumbnail(data, max_size=THUMBNAIL_MAX_SIZE, quality=THUMBNAIL_QUALITY)`, and `read_video(path)`; port the existing `choosier/web.py` helper bodies verbatim, replace `ApiError` with `ServiceError`, move the first `is_file()` checks into `read_image`/`read_video`, preserve every message and limit listed in `contracts/service-boundaries.md` §6, and read `PREVIEW_MAX_IMAGE_BYTES` through the `choosier.preview` module at call time.
- [ ] T012 Update `choosier/services/__init__.py` to re-export exactly the adapter-facing surface from `contracts/service-boundaries.md` §2: `FailureKind`, `ServiceError`, `HistoryService`, `PANEL_MAX_LINES`, `BrowseEntry`, `BrowseListing`, `HistorySnapshot`, `StateSnapshot`, `PickOutcome`, `OpenOutcome`, `browse_directory`, `build_state`, `pick`, and `open_entry`.
- [ ] T013 Verify foundational imports and typing: run `uv run python -c "from choosier.services import FailureKind, ServiceError, HistoryService, PANEL_MAX_LINES, BrowseEntry, BrowseListing, HistorySnapshot, StateSnapshot, PickOutcome, OpenOutcome, browse_directory, build_state, pick, open_entry"` and `uv run mypy choosier/services choosier/web_media.py`; fix only issues in the new modules without changing behavior.

**Checkpoint**: The shared service package, unified read primitive, and web media
module are ready; user stories can now proceed.

---

## Phase 3: User Story 1 — Interface Behavior Unchanged After Extraction (Priority: P1) 🎯 MVP

**Goal**: Move every web-reachable business operation into the shared services
and migrate the web, CLI, and TUI adapters without changing any public behavior.

**Independent Test**: Replay the frozen API contract and full existing behavior
suite, plus representative CLI/TUI journeys, and compare statuses, headers,
bodies, output text, exit codes, ordering, and history outcomes with the
pre-refactor baseline.

### Implementation for User Story 1

- [ ] T014 [US1] Add the single `ServiceError` exception handler to `choosier/web.py`: import `FailureKind`/`ServiceError`, map `INVALID_INPUT→invalid_request/400`, `FORBIDDEN→forbidden/403`, `NOT_FOUND→not_found/404`, `PAYLOAD_TOO_LARGE→payload_too_large/413`, `UNSUPPORTED_MEDIA_TYPE→unsupported_media_type/415`, `RANGE_NOT_SATISFIABLE→range_not_satisfiable/416`, and `IO_ERROR→internal_error/500`, emitting the existing envelope with `detail == error.message` and `error.details`; keep `ApiError` only for byte-range work and leave the Starlette, validation, and catch-all handlers unchanged.
- [ ] T015 [US1] Migrate `GET /api/browse`, `GET /api/state`, `POST /api/pick`, and `POST /api/open` in `choosier/web.py` to one call each to `browse_directory`, `build_state`, `pick(..., include_preview=True)`, and `open_entry`; map `BrowseListing`, `StateSnapshot`, `PickOutcome`, and `OpenOutcome` onto the existing `BrowseResponse`, `StateResponse`, `PickResponse`, and `OpenResponse` fields; keep every Pydantic model, default, and validation constraint unchanged, keep `/api/defaults` transport-only, and remove the inline selection/filter/history logic and unused imports.
- [ ] T016 [US1] Migrate `POST /api/history/archive`, `DELETE /api/history`, `DELETE /api/history/item`, and `POST /api/history/remove` in `choosier/web.py` to `HistoryService.archive`, `clear`, `remove`, and `remove_many`; keep the small `_log_path` helper around `resolve_log_path`, preserve `ArchiveResponse.backup` as `backup.name` or `None`, and keep the response fields `log_file`, `item`, `items`, and `removed` unchanged; retain `RemoveHistoryItemsRequest.items = Field(min_length=1)`.
- [ ] T017 [US1] Migrate `GET /api/image` and `GET /api/video` in `choosier/web.py` to `choosier.web_media.read_image`, `make_thumbnail`, and `read_video`; keep `Range`/`If-Range` parsing, `MalformedRangeHeader`, `RangeNotSatisfiable`, `FileResponse`, `Content-Range`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and all status codes in the adapter; remove the old Pillow/zipfile/BytesIO imports, helper functions, and media constants from `web.py`, and remove the local `PANEL_MAX_LINES` definition because `build_state` owns the 200-line web default and `choosier/tui.py` imports the constant from `choosier.services.state`.
- [ ] T018 [P] [US1] Update only the patch targets in `tests/test_api_errors.py` per `contracts/service-boundaries.md` §11: `choosier.storage.read_log_entries`, `choosier.services.browse.Path.iterdir`, `choosier.storage.log_selection`, `choosier.preview.PREVIEW_MAX_IMAGE_BYTES`, `choosier.launcher.launch_path`, and `choosier.storage.archive_log`/`reset_log`/`remove_log_item`/`remove_log_items`; do not change assertions.
- [ ] T019 [P] [US1] Update only the media-limit and launcher patch targets in `tests/test_web.py` to `choosier.preview.PREVIEW_MAX_IMAGE_BYTES` and `choosier.launcher.launch_path`; do not change assertions.
- [ ] T020 [P] [US1] Update only the open-success patch target in `tests/test_api_compat.py` to `choosier.launcher.launch_path`; do not change assertions.
- [ ] T021 [P] [US1] Migrate `choosier/cli.py` to the shared path: resolve the log with `chooser.resolve_log_path(target, args.log_file or "")` (blank/whitespace falls back, `~` expands), use `HistoryService.clear()` for `--reset`, use `build_state(..., max_lines=None).remaining` for `--list` while keeping `_exhausted_exit`'s raw-directory check and exit codes 3/4, and use `pick(..., commit=False)` for the pick flow; print `"The choice: <item>"` before `HistoryService.append` on non-dry runs, and preserve `"Dry run: selection not logged."`, `"Added in <log_path> with timestamp.\n"`, error text, parser errors, and exit codes 0/1/3/4.
- [ ] T022 [P] [US1] Migrate `choosier/tui.py` to the shared path: refresh panels with `build_state(..., max_lines=None)` and feed `remaining` plus `entry.display` into `render_panel`'s last-200 rendering; import `PANEL_MAX_LINES` from `choosier.services.state` and delete the local constant; use `pick(..., seed=seed, dry_run=dry_run)` with the existing target-is-directory precheck before `parse_seed`; use `HistoryService` for archive and clear; use `open_entry` and map `NOT_FOUND` to `"Gone: <name>"` and `IO_ERROR` to the service message; keep `preview_entry`, widgets, shortcuts, focus behavior, and all status strings unchanged.
- [ ] T023 [US1] Verify the frozen behavior boundary: run `uv run pytest tests/test_api_contract.py tests/test_api_compat.py tests/test_api_errors.py tests/test_web.py tests/test_cli.py tests/test_tui.py tests/test_chooser.py tests/test_storage.py tests/test_preview.py tests/test_launcher.py -q`, confirm every existing assertion still passes, and run `git diff --exit-code 3ec1c7f -- specs/001-standardize-api-responses/contracts/api-contract.json specs/001-standardize-api-responses/contracts/api-contract.md` to prove the authoritative contract is untouched.

**Checkpoint**: User Story 1 is complete. All three interfaces run over the
shared services, and the frozen behavior suite passes with unchanged assertions.

---

## Phase 4: User Story 2 — Thin Handlers over Shared Services (Priority: P2)

**Goal**: Prove that each web-exposed operation has exactly one shared
implementation, handlers only translate, and maintainers can find the boundaries.

**Independent Test**: Invoke each shared operation directly without a web request,
review every route handler, and run the source-boundary checks; confirm no
competing selection, filter, history, or media logic remains in an adapter.

### Implementation for User Story 2

- [ ] T024 [P] [US2] Create `tests/test_services_boundaries.py` with source/import checks: `choosier/services` imports only the standard library and allowed core modules (`chooser`, `preview`, `launcher`, `storage`, `services.*`), never `fastapi`, `starlette`, `uvicorn`, `pydantic`, `textual`, `rich`, `PIL`, `choosier.web`, `choosier.tui`, `choosier.web_media`, or `choosier.cli`; `choosier.web_media` is imported only by `choosier/web.py`; `read_log_entries`, `parse_log_line`, and `HistoryService` each have exactly one production definition.
- [ ] T025 [US2] Add route-delegation assertions to `tests/test_services_boundaries.py`: each business route in `choosier/web.py` references its expected service entry point (`browse_directory`, `build_state`, `pick`, `open_entry`, `HistoryService`, or `web_media`), `/api/defaults` remains transport-only, and no adapter references `storage.log_selection`, `storage.remove_log_item`, `storage.remove_log_items`, `storage.archive_log`, `storage.reset_log`, `read_log_entries`, or `parse_log_line` directly.
- [ ] T026 [P] [US2] Update `README.md` with the service boundaries and history ownership: `choosier/services/` is the stdlib-only, UI-agnostic application layer; `choosier.storage` owns history file I/O and parsing; `HistoryService` owns application-layer history reads and mutations; CLI/TUI/web are thin adapters; `choosier/web_media.py` is web-only and may use Pillow; no new mandatory runtime dependency.
- [ ] T027 [US2] Run `uv run pytest tests/test_services_boundaries.py -q` and a direct-call smoke for `browse_directory`, `build_state`, and `pick(..., dry_run=True)` against a temporary directory without constructing a request; review `choosier/web.py` to confirm every nontrivial handler is input parsing, one service call, and outcome mapping only, and remove any remaining inline business logic found by the review.

**Checkpoint**: The thin-handler guarantee and documented service boundaries are
verifiable independently of any running interface.

---

## Phase 5: User Story 3 — One History Data-Access Path for Every Interface (Priority: P3)

**Goal**: Demonstrate that CLI, TUI, and web read and mutate history through the
same structured read primitive and `HistoryService`, with identical outcomes.

**Independent Test**: Create one fixture containing current JSONL, legacy, plain,
blank, malformed, and duplicate lines; read it, pick from it, remove items,
archive it, and clear it through each interface; compare entries, totals,
remaining candidates, removed counts, retained lines, and backup names.

### Implementation for User Story 3

- [ ] T028 [P] [US3] Create `tests/test_services_history.py` covering `HistoryService` snapshot derivation from one read, tolerant versus strict reads, append JSONL format, single removal of every duplicate, batch removal in one atomic rewrite with unrelated lines retained verbatim, archive naming and missing-file `None`, clear `True`/`False`, missing history, and each exact `ServiceError` message for `OSError`; patch `choosier.storage.*` to prove the module-level seam.
- [ ] T029 [P] [US3] Extend `tests/test_storage.py` with one fixture containing current JSONL, legacy timestamp-and-item, plain, blank, malformed, and duplicate lines; assert `read_log_entries`, `load_log`, and `get_logged_items` agree on entries/logged/display, and assert `ignore_errors=False` propagates a non-missing `OSError` while the default read stays tolerant; keep all existing test assertions unchanged.
- [ ] T030 [P] [US3] Create `tests/test_history_consistency.py` with a disposable target and separate log copies: exercise `choosier/cli.py` `main`, a FastAPI `TestClient` from `choosier/web.py`, and `HistoryService` against the same current/legacy/blank/malformed/duplicate scenario, then compare structured entries, totals, remaining candidates, removed counts, archive results, and final file contents; assert no partial write is ever observable.
- [ ] T031 [P] [US3] Extend `tests/test_tui.py` with a TUI history scenario that uses `build_state(..., max_lines=None)`, `render_panel`, and `HistoryService` on a history longer than 200 lines; assert the panels render the last 200 lines with the existing count header and that archive/clear outcomes match the shared service results; keep the existing `render_panel` assertions unchanged.
- [ ] T032 [US3] Run `uv run pytest tests/test_services_history.py tests/test_storage.py tests/test_history_consistency.py tests/test_tui.py -q` and confirm all three interface paths report identical history data and mutations.

**Checkpoint**: History has one read primitive and one application-layer command
facade, and the cross-interface scenario passes.

---

## Phase 6: User Story 4 — Service Rules Testable Without an Interface (Priority: P4)

**Goal**: Give every extracted operation direct success and failure coverage that
runs without a web server, TUI session, network, or browser.

**Independent Test**: Run `uv run pytest tests/test_services_*.py -q` with no
server or terminal running; confirm all service tests pass in under 10 seconds.

### Implementation for User Story 4

- [ ] T033 [P] [US4] Create `tests/test_services_browse.py` covering directories-first/case-insensitive ordering, parent reporting at a root and non-root, missing/non-directory target, and listing permission failure via `choosier.services.browse.Path.iterdir`.
- [ ] T034 [P] [US4] Create `tests/test_services_state.py` covering invalid-path outcome precedence, conflicting-filter `ServiceError`, hidden/type filters, managed history/archive exclusion, full totals, the default 200 cap (first remaining, last history), `max_lines=None` TUI shape, and empty/malformed history.
- [ ] T035 [P] [US4] Create `tests/test_services_pick.py` covering seeded repeatability, dry-run, `commit=False`, empty versus exhausted, invalid path, conflicting filters, write failure with the exact `"Error writing log:"` prefix by patching `choosier.storage.log_selection` with `OSError`, optional preview, and hidden/type filters.
- [ ] T036 [P] [US4] Create `tests/test_services_opening.py` covering success, missing entry, and launcher failure via `choosier.launcher.launch_path`, including the exact `"Entry is gone"` and `"Cannot open:"` messages.
- [ ] T037 [P] [US4] Create `tests/test_services_errors.py` covering every `FailureKind` value and `ServiceError` propagation of `kind`, `message`, and `details`, and assert the exception exposes no HTTP status or UI widget.
- [ ] T038 [US4] Run `time uv run pytest tests/test_services_*.py -q` with no web server or TUI session; confirm the subset passes in under 10 seconds (`SC-009`) and that no test opens a socket, browser, or interactive terminal.

**Checkpoint**: Every extracted operation is directly testable, and the fast
service subset passes within the required bound.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, packaging, full quality gates, and end-to-end
validation across all stories.

- [ ] T039 [P] Add a non-behavioral entry under `Unreleased` in `CHANGELOG.md` describing the service extraction, unified history access, and web-only media module; do not change version numbers, extras, entry points, or dependencies.
- [ ] T040 [P] Install the CI extras with `uv sync --group dev --extra ui --extra web`, then build the frontend with `npm ci && npm run build` in `frontend/` so static-serving tests have `choosier/web_static/`.
- [ ] T041 Run the full quality gate for `choosier/`, `main.py`, and `tests/` from the repository root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run mypy choosier main.py tests`, and `uv build`; fix every failure without changing frozen behavior.
- [ ] T042 Verify packaging and imports: run `uv run python -m zipfile -l dist/choosier-*.whl` and confirm entries for `choosier/services/__init__.py`, `browse.py`, `errors.py`, `history.py`, `models.py`, `opening.py`, `pick.py`, and `state.py`; then run `uv run python -c "from choosier.services import HistoryService, build_state, browse_directory, pick, open_entry; from choosier.web_media import read_image, read_video; print('service imports OK')"`.
- [ ] T043 Execute the validation scenarios in `specs/002-backend-services/quickstart.md` §3–§6: the cross-interface history fixture, CLI empty/exhausted exits, web state/browse/pick/error-envelope/media smoke checks, source-boundary commands, compatibility-export import check, and the frozen contract diff; record any mismatch as a regression.
- [ ] T044 Perform the final ownership review: run `git diff --exit-code 3ec1c7f -- specs/001-standardize-api-responses/contracts/api-contract.json specs/001-standardize-api-responses/contracts/api-contract.md`, review `git diff 3ec1c7f -- choosier/storage.py` for only the unified read primitive and derived wrappers, and confirm `choosier/cli.py`, `choosier/tui.py`, and `choosier/web.py` contain no direct history parsing or mutation calls.

**Checkpoint**: Documentation, packaging, source ownership, and all quality gates
are complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup; BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers the P1
  behavior-preserving extraction.
- **User Story 2 (Phase 4)**: Depends on Foundational and User Story 1; verifies
  the thin-handler and documentation guarantees.
- **User Story 3 (Phase 5)**: Depends on Foundational and User Story 1; verifies
  the unified history path across interfaces.
- **User Story 4 (Phase 6)**: Depends on Foundational and User Story 1; adds the
  direct service test coverage.
- **Polish (Phase 7)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories after Foundational; it is
  the MVP and the prerequisite for the verification layers.
- **US2 (P2)**: Integrates with US1's adapters; independently testable by direct
  service calls plus source-boundary checks.
- **US3 (P3)**: Integrates with US1's adapters and shared history service;
  independently testable with the cross-interface history fixture.
- **US4 (P4)**: Integrates with all extracted services; independently testable
  by the direct service subset.

### Within Each User Story

- Foundational models and errors before services.
- `HistoryService` and the unified read primitive before state, pick, and TUI panel work.
- Services before adapter migration.
- Adapter migration before patch-seam updates and behavior-suite verification.
- Boundary/history/direct tests after the production seams exist.
- Full gate and packaging checks last.

### Parallel Opportunities

- T001 and T002 are independent setup edits.
- T003, T004, and T005 touch different files and can start immediately after
  Setup; T007 and T010 can start once T003/T004 exist, and T011 can start once
  T003 exists.
- T006 depends on T003–T005; T008 and T009 depend on T006 (and T003/T004) and
  can then run in parallel with each other.
- T012 must wait for every service module; T013 waits for T012.
- T018, T019, and T020 are separate test files and can be updated in parallel
  after the adapter migration.
- T021 and T022 are separate adapter files and can be migrated in parallel.
- T024 and T026 are independent files; T025 extends T024's file.
- T028, T029, T030, and T031 are separate test files and can be written in parallel.
- T033–T037 are separate direct test files and can be written in parallel.
- T039 and T040 are independent documentation/environment tasks.

---

## Parallel Example: User Story 1

```bash
# After Foundational and the web adapter migration:
Task: "Update patch targets in tests/test_api_errors.py"
Task: "Update patch targets in tests/test_web.py"
Task: "Update patch targets in tests/test_api_compat.py"

# CLI and TUI adapter migrations are independent files:
Task: "Migrate choosier/cli.py to the shared services"
Task: "Migrate choosier/tui.py to the shared services"
```

## Parallel Example: User Story 2

```bash
Task: "Create tests/test_services_boundaries.py import/source checks"
Task: "Update README.md with service boundaries and history ownership"
```

## Parallel Example: User Story 3

```bash
Task: "Create tests/test_services_history.py"
Task: "Extend tests/test_storage.py with the cross-format fixture"
Task: "Create tests/test_history_consistency.py"
Task: "Extend tests/test_tui.py with the TUI history scenario"
```

## Parallel Example: User Story 4

```bash
Task: "Create tests/test_services_browse.py"
Task: "Create tests/test_services_state.py"
Task: "Create tests/test_services_pick.py"
Task: "Create tests/test_services_opening.py"
Task: "Create tests/test_services_errors.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational — the shared services and unified read
   primitive are hard prerequisites.
3. Complete Phase 3: User Story 1 — migrate the web, CLI, and TUI adapters.
4. **STOP and VALIDATE**: run the frozen behavior suite and the 001 contract
   diff from T023.
5. Demo the behavior-preserving extraction.

The MVP is the P1 user-visible guarantee. Do not declare the feature complete
until US3's cross-interface history checks and US4's direct service tests pass:
`FR-018` and `SC-004` require them.

### Incremental Delivery

1. Setup + Foundational → service package ready.
2. US1 → adapters migrated; all pre-existing behavior tests pass (MVP).
3. US2 → boundary tests and README prove thin handlers.
4. US3 → history consistency tests prove one data-access path.
5. US4 → direct service tests prove interface-free testability.
6. Polish → CHANGELOG, full gate, wheel, and quickstart validation.

### Parallel Team Strategy

With multiple contributors:

1. One contributor completes Setup + Foundational.
2. Then:
   - Contributor A: US1 web adapter (T014–T017).
   - Contributor B: US1 CLI/TUI adapters (T021–T022) after services exist.
   - Contributor C: US2 boundary tests/README (T024–T027).
   - Contributor D: US3 history tests (T028–T032).
   - Contributor E: US4 direct tests (T033–T038).
3. Integrate through T018–T023, then run the polish gate.

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task.
- `[USn]` labels map every story-phase task to `spec.md`.
- Existing behavior tests keep their assertions; only the patch seams and
  imports listed in `contracts/service-boundaries.md` §11 move.
- The 001 API contract JSON/Markdown files are frozen and must not be edited.
- No database, ORM, cache, migration, dependency, route, flag, shortcut, history
  format, archive naming, or frontend change is allowed.
- Commit each completed task separately using Conventional Commits
  (`refactor`, `test`, `docs`, or `chore` as appropriate), and never commit a
  task that fails the relevant tests or linters.
