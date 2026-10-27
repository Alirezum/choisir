# Tasks: Standardize API Responses and Error Schemas

**Input**: Design documents from `/specs/001-standardize-api-responses/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api-contract.json`, `contracts/api-contract.md`, `quickstart.md`

**Tests**: Required. The specification explicitly requires automated route-contract checks and drift protection (FR-012, FR-013, FR-016), and the constitution requires tests for every behavior change.

**Organization**: Tasks are grouped by user story so each story has an independent test and can be validated separately. Production changes are confined to `choosier/web.py`; the Vue source stays unchanged.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other `[P]` tasks in the same phase (different files, no incomplete dependency)
- **[Story]**: `[US1]`, `[US2]`, or `[US3]`; setup, foundational, and polish tasks have no story label
- Every task includes the exact file path or validation command paths

## Path Conventions

- Python package: `choosier/`
- Tests: `tests/`
- Frontend source: `frontend/src/` (must remain unchanged)
- Feature artifacts: `specs/001-standardize-api-responses/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing project and quality baseline before making changes.

- [X] T001 Confirm the baseline in `pyproject.toml`, `frontend/package.json`, and `tests/` is green: run `uv sync --group dev --extra ui --extra web`, `uv run pytest -q`, and `cd frontend && npm run build`; record the existing pass count and build result before edits.
  - Baseline recorded 2026-10-29: `147 passed, 5 subtests passed`; frontend production build succeeded with no source changes.

**Checkpoint**: The repository is known-green and the web/frontend extras are installed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared error vocabulary and test support that all stories use.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add the error vocabulary and envelope primitives in `choosier/web.py`: map exactly `invalid_request`→400, `forbidden`→403, `not_found`→404, `method_not_allowed`→405, `payload_too_large`→413, `unsupported_media_type`→415, `range_not_satisfiable`→416, `validation_error`→422, `internal_error`→500; define `ApiError(code, message, details=None, headers=None)`; add a serializer that emits exactly `{"error": {"code", "message", "details"}, "detail": message}` with `details` present and `null` for non-validation errors; narrow `PreviewModel.kind` to the existing `PreviewKind` Literal (`text`, `directory`, `binary`, `empty`, `gone`, `unreadable`, `archive`, `image`, `video`).
- [X] T003 [P] Create a fully type-annotated (strict mypy) `tests/api_contract_support.py` with contract loading from `specs/001-standardize-api-responses/contracts/api-contract.json`, `$ref`/`anyOf` normalization for contract and FastAPI OpenAPI schemas, an `api_routes(app)` collector, and `assert_error_envelope(testcase, response, expected_status, expected_code)` that enforces exact top-level keys `error`/`detail`, exact error keys `code`/`message`/`details`, `application/json`, `detail == error.message`, the code-to-status mapping, and `details.issues` with string `location`, `message`, and `type` for validation errors.

**Checkpoint**: The error vocabulary, envelope serializer, and shared test helpers exist. Existing behavior is still unchanged.

---

## Phase 3: User Story 1 - Existing Web Flows Keep Working (Priority: P1) 🎯 MVP

**Goal**: Freeze every success shape and domain outcome the current Vue client consumes, and prove no frontend changes are needed.

**Independent Test**: `uv run pytest tests/test_api_compat.py tests/test_web.py -v` passes and `cd frontend && npm run build` succeeds with no changes under `frontend/src/`.

### Tests for User Story 1

- [X] T004 [US1] Add `tests/test_api_compat.py` covering every existing success flow, using `specs/001-standardize-api-responses/contracts/api-contract.json` as the exact field/type/nullability/enum baseline: JSON routes return 200 `application/json` with the exact contract top-level fields; `/api/state` invalid path stays 200 with `valid_path: false`; `/api/pick` returns 200 for `invalid_path`, `empty`, and `exhausted`; archive/clear/remove no-ops stay 200; `/api/preview` gone/empty stays 200; image returns the original MIME/bytes and `image/webp` for thumb/preview; video returns 200 and 206 with `Accept-Ranges: bytes`.

### Implementation and Verification for User Story 1

- [X] T005 [US1] Run `uv run pytest tests/test_api_compat.py tests/test_web.py -v` and `npm run build` in `frontend/`; confirm all existing flows pass and no file under `frontend/src/` needs to change.

**Checkpoint**: User Story 1 is independently satisfied: the success surface is frozen and the current frontend contract is proven intact.

---

## Phase 4: User Story 2 - Consistent, Actionable Errors (Priority: P2)

**Goal**: Return the single documented JSON error envelope for route, framework, validation, server, and binary-range failures while preserving every existing message and status.

**Independent Test**: `uv run pytest tests/test_api_errors.py tests/test_web.py -v` passes, including framework 404/405/422/500, every route error condition, validation `details.issues`, and video 400/416 responses.

### Tests for User Story 2 (write first, expect failures)

- [X] T006 [US2] Add framework-error cases to `tests/test_api_errors.py`: `GET /api/nope` →404 `not_found`; `POST /api/defaults` →405 `method_not_allowed` with `Allow`; `GET /api/state` without `path` →422 `validation_error` with `details.issues`; malformed `POST /api/pick` JSON →422; and patch `choosier.web.read_log_entries` to raise `RuntimeError`, using `TestClient(create_app(), raise_server_exceptions=False)`, to assert 500 `internal_error` with `"Internal server error"`. Mark each new test `@unittest.expectedFailure` until T009/T010 implements the handlers, so this commit still passes the suite; remove the markers in T009/T010.
- [X] T007 [US2] Add route-error cases to `tests/test_api_errors.py`: browse missing→404 `not_found`, and patch `choosier.web.Path.iterdir` to raise `PermissionError` for 403 `forbidden`; state/pick conflicting filters→400 `invalid_request`; patch `choosier.web.log_selection` with `OSError`→500 `internal_error`; image missing→404, archive index out of range→404, non-zip/corrupt/encrypted archive→400 `invalid_request` (patch `ZipInfo.flag_bits` or corrupt a valid zip member for the encrypted/corrupt cases), patch `choosier.web.PREVIEW_MAX_IMAGE_BYTES` to 8 for 413 `payload_too_large`, unsupported/undecodable image→415 `unsupported_media_type`; video missing→404, unsupported→415; open missing→404, patch `choosier.web.launch_path` with `OSError`→500; patch `choosier.web.archive_log`, `reset_log`, `remove_log_item`, and `remove_log_items` with `OSError` for 500 `internal_error`; assert every failed request leaves the log bytes unchanged. Mark each new test `@unittest.expectedFailure` until the handlers land, then remove the markers in T009/T011.
- [X] T008 [US2] Add byte-range failure cases to `tests/test_api_errors.py`: malformed `Range`→400 `invalid_request`; unsatisfiable `Range`→416 `range_not_satisfiable` with `Content-Range: bytes */<size>`; confirm both are `application/json` and never `text/plain`. Mark both tests `@unittest.expectedFailure` until T012, then remove the markers.

### Implementation for User Story 2

- [X] T009 [US2] Register handlers in `create_app()` in `choosier/web.py` for `ApiError`, `StarletteHTTPException`, and `Exception`: return the exact envelope, map fallback 400/403/404/405/413/415/416/422/500 to the vocabulary, preserve the `Allow` header on 405, and emit `"Internal server error"` with 500 for unhandled exceptions. Remove the `expectedFailure` markers from the framework 404/405/500 tests added in T006 and from the route-error tests added in T007; the fallback handler already satisfies the latter.
- [X] T010 [US2] Register a `RequestValidationError` handler in `choosier/web.py` that returns 422 `validation_error`; set `details.issues` to one object per Pydantic error with `location` as strings, `message`, and `type`; summarize the first issue in the message; omit raw `input` and `ctx`. Remove the `expectedFailure` markers from the validation tests added in T006.
- [X] T011 [US2] Replace route-level `HTTPException` raises in `choosier/web.py` with `ApiError` using the 9-code vocabulary, preserving every existing message string and status: 400 conflicting filters/archive issues, 403 directory listing, 404 missing directory/entry/image/video/archive member, 413 oversized image, 415 unsupported image/video, 500 log/launch/read failures. Keep the route-error tests added in T007 green.
- [ ] T012 [US2] Add video `Range` pre-validation in `choosier/web.py` before returning `FileResponse`: use Starlette's range parser; raise `ApiError("invalid_request", ...)` for malformed headers and `ApiError("range_not_satisfiable", ..., headers={"Content-Range": f"bytes */{size}"})` for unsatisfiable starts; keep valid single, suffix, and multipart ranges delegated to `FileResponse` with 200/206 behavior. Remove the `expectedFailure` markers from the range tests added in T008.
- [ ] T013 [US2] Run `uv run pytest tests/test_api_errors.py tests/test_web.py -v` and fix any implementation gaps in `choosier/web.py` until every envelope, status, message, validation-detail, and binary-range assertion passes.

**Checkpoint**: User Stories 1 and 2 both pass independently; every tested failure uses the documented envelope and no success shape changed.

---

## Phase 5: User Story 3 - Auditable Contracts and Drift Protection (Priority: P3)

**Goal**: Make the contract inventory executable, reject undocumented routes/fields, and detect seeded breaking changes before they reach users.

**Independent Test**: `uv run pytest tests/test_api_contract.py -v` passes, including route parity, OpenAPI success-schema comparison, error taxonomy checks, and seeded drift assertions.

### Tests for User Story 3

- [ ] T014 [US3] Add route-inventory and taxonomy tests in `tests/test_api_contract.py`: load `specs/001-standardize-api-responses/contracts/api-contract.json`; compare the exact `(method, path)` set with `APIRoute` objects under `/api` in both directions; assert `ERROR_STATUS` from `choosier/web.py` exactly matches `errorCodes`; assert every route error code/status is documented, every `errorCodes` entry is referenced by a route or `globalErrors`, and every route lists `method_not_allowed` and `internal_error`.
- [ ] T015 [US3] Add OpenAPI success-schema tests in `tests/test_api_contract.py`: treat `specs/001-standardize-api-responses/contracts/api-contract.json` as the exact field/type/nullability/enum source; for each JSON route compare contract fields with FastAPI's OpenAPI schema for exact field names, JSON types, nullability, enums, arrays, and nested objects; reject both missing and undocumented extra fields; assert binary routes declare `body: "binary"`, statuses, and content-type rules from the contract.
- [ ] T016 [US3] Add seeded-drift tests in `tests/test_api_contract.py` using deep copies and `assertRaises`: removing a success field, renaming a field, changing a field type, changing nullability or an enum, adding/removing a contract route, and changing an error code's status must each be rejected by the comparison helpers.

### Documentation for User Story 3

- [ ] T017 [P] [US3] Document the error envelope, `detail` compatibility invariant, 9-code table, binary/range behavior, and the contract-test update workflow in `README.md`; link `specs/001-standardize-api-responses/contracts/api-contract.md`.
- [ ] T018 [P] [US3] Add an Unreleased `CHANGELOG.md` entry for standardized JSON errors, validation `details.issues`, preserved `detail` messages, binary/range error handling, and automated route-contract/drift checks.

**Checkpoint**: The inventory covers 100% of `/api` routes, and seeded field/type/route/error drift fails the suite.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Run the complete release gate, validate manually, review scope and history, and close the task list.

- [ ] T019 [P] Run the full quality gate from `pyproject.toml`, `tests/`, `choosier/`, and `frontend/package.json`: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy choosier main.py tests`, and `cd frontend && npm run build`.
- [ ] T020 [P] Execute the manual `specs/001-standardize-api-responses/quickstart.md` curl checks for success, framework errors, route errors, binary ranges, and domain outcomes; record any mismatch in `choosier/web.py` or the contract.
- [ ] T021 [P] Review `frontend/src/`, the route decorators in `choosier/web.py`, and the request models; confirm no frontend source, path, method, request field, auth, or loopback binding changed.
- [ ] T022 [P] Review `specs/001-standardize-api-responses/contracts/api-contract.json`, `contracts/api-contract.md`, `README.md`, and `CHANGELOG.md` for consistency with the implemented envelope and route errors; update only if implementation revealed a contract correction.
- [ ] T023 Review the commit history and working tree against this task list: confirm every completed task has one Conventional Commit, each commit passed its relevant test/lint gate, and `git status` is clean apart from intentionally untracked tooling files.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 starts immediately.
- **Foundational (Phase 2)**: Depends on T001; T002 and T003 block all stories.
- **User Story 1 (Phase 3)**: Depends on T002/T003; T005 depends on T004.
- **User Story 2 (Phase 4)**: Depends on T002/T003; T009–T012 depend on the failing tests in T006–T008; T013 depends on all US2 tasks.
- **User Story 3 (Phase 5)**: Depends on T002/T003; T014–T016 depend on T002 and the final `PreviewModel.kind`; T017–T018 depend on the US2 behavior they document.
- **Polish (Phase 6)**: Depends on all desired user stories; T023 depends on T019–T022.

### User Story Dependencies

- **US1 (P1)**: Independent of US2/US3 after foundational. It edits only `tests/test_api_compat.py` and runs the existing suite/build.
- **US2 (P2)**: Edits `choosier/web.py` and `tests/test_api_errors.py`. It can start after foundational; recommended after US1 so the baseline compatibility suite is already in place.
- **US3 (P3)**: Edits `tests/test_api_contract.py`, `README.md`, and `CHANGELOG.md`. It validates the final US2 behavior and should follow US2.

### Within Each User Story

- Tests are written first; US2's new tests use `@unittest.expectedFailure` until the matching handlers land.
- In US2, handlers precede route migration, then validation normalization, then range validation.
- In US3, route/taxonomy checks precede schema comparison and seeded drift.
- US1 has no production behavior change; its test is a regression guard.

### Parallel Opportunities

- T002 (production `choosier/web.py`) and T003 (test support `tests/api_contract_support.py`) can run in parallel.
- Once foundational is done, US1's `tests/test_api_compat.py` work can proceed alongside US2's `tests/test_api_errors.py` work (different files), though US2 implementation should wait for US1's baseline pass.
- T017 and T018 (different documentation files) can run in parallel.
- T019–T022 (independent commands/reviews) can run in parallel; T023 follows.

---

## Parallel Example: Foundational

```bash
# Production primitives and test support touch different files:
Task: "T002 Add error vocabulary and envelope primitives in choosier/web.py"
Task: "T003 Create contract/schema helpers in tests/api_contract_support.py"
```

## Parallel Example: User Story 2 test authoring and User Story 1 compatibility

```bash
# These touch different test files and can be prepared together:
Task: "T004 Add success compatibility tests in tests/test_api_compat.py"
Task: "T006 Add framework error tests in tests/test_api_errors.py"
```

## Parallel Example: Polish

```bash
# Independent release checks:
Task: "T019 Run the full quality gate"
Task: "T020 Execute the quickstart curl checks"
Task: "T021 Review frontend/route/request scope"
Task: "T022 Review contract and documentation consistency"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001).
2. Complete Phase 2 (T002–T003).
3. Complete Phase 3 (T004–T005).
4. **STOP and VALIDATE**: `tests/test_api_compat.py`, `tests/test_web.py`, and the frontend build pass with zero frontend source changes.

This MVP is a compatibility milestone. It proves the existing web flows are frozen, but the user-visible error standardization lands with US2. If the release must include the new error behavior, treat **US1 + US2** as the minimum shippable increment.

### Incremental Delivery

1. Setup + Foundational → shared envelope and test helpers.
2. US1 → compatibility baseline (no frontend changes).
3. US2 → standardized errors for every route/framework/binary failure.
4. US3 → executable contract inventory and drift protection.
5. Polish → full gate, manual validation, atomic commits.

### Parallel Team Strategy

1. One developer completes T001–T003.
2. After foundational:
   - Developer A: US1 compatibility tests (`tests/test_api_compat.py`).
   - Developer B: US2 error tests and implementation (`tests/test_api_errors.py`, `choosier/web.py`).
3. After US2, one developer completes US3 contract/drift tests; another handles README/CHANGELOG.
4. Rejoin for T019–T023.

Note: US1 and US2 share no production file after foundational; US2 owns `choosier/web.py`, so its implementation must not overlap with US1 test work.

---

## Notes

- `[P]` means different files and no dependency on an incomplete task.
- `[US1]`/`[US2]`/`[US3]` map to the three prioritized stories in `spec.md`.
- Every task includes an exact path or a validation command rooted in the repository.
- Write US2 tests first; the temporary `expectedFailure` markers keep each per-task commit green until the matching implementation lands.
- Commit after each task with a Conventional Commit, and never leave the suite or linters red.
- Do not modify `frontend/src/`, route paths, HTTP methods, request models, auth, or loopback binding.
- Domain outcomes (`invalid_path`, `empty`, `exhausted`, missing history, no-op archive/clear/remove) must remain 200.
- Binary success payloads and 200/206 range behavior must remain unchanged; only binary failures become JSON errors.
