---

description: "Task list for the frontend API client layer"

---

# Tasks: Frontend API Client Layer

**Input**: Design documents from `/specs/003-frontend-api-client/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/frontend-api-client.md](./contracts/frontend-api-client.md),
[quickstart.md](./quickstart.md)

**Tests**: Tests are required by `FR-012`, `FR-013`, `FR-017`, `SC-005`, and
`SC-006`. Client tests are written before the implementation they exercise and
must fail for the expected missing-module or missing-behavior reason. The drift
gate is `npm run check:api`; `npm run test:api` covers query encoding, route and
facade coverage, transport construction, error parsing, contract drift, and
source boundaries. No new test framework is added.

**Organization**: Tasks are grouped by user story. User Story 1 is the P1
single-boundary refactor. User Story 2 adds the one typed error path. User Story
3 adds drift and bypass protection. The generated contract and shared types are
the only Foundational prerequisites.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (`US1`–`US3`)
- Every task includes an exact file path or an exact command with its target files

## Path Conventions

- Frontend source: `frontend/src/`
- Frontend build tooling: `frontend/scripts/`
- Frontend tests: `frontend/tests/`
- Frontend configuration: `frontend/package.json`, `frontend/tsconfig*.json`
- CI: `.github/workflows/ci.yml`
- Documentation: `frontend/README.md`, `README.md`, `CHANGELOG.md`
- Authoritative contract (read-only): `specs/001-standardize-api-responses/contracts/api-contract.json`

## Task Summary

| Phase | Tasks | Count |
| --- | --- | --- |
| Setup | T001–T002 | 2 |
| Foundational | T003–T008 | 6 |
| User Story 1 (P1) | T009–T015 | 7 |
| User Story 2 (P2) | T016–T021 | 6 |
| User Story 3 (P3) | T022–T027 | 6 |
| Polish | T028–T031 | 4 |
| **Total** | **T001–T031** | **31** |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the pre-change baseline and create the generator entry point.

- [X] T001 Verify the pre-change baseline: run `node --version` (must be 22.18 or newer), `cd frontend && npm ci && npm run build`, and `git diff --exit-code -- specs/001-standardize-api-responses/contracts/api-contract.json specs/001-standardize-api-responses/contracts/api-contract.md`; record the 12-route/9-error-code inventory and the current success/error behavior from `specs/003-frontend-api-client/quickstart.md` §6.
- [X] T002 [P] Create `frontend/scripts/generate-api-contract.mjs` as an ESM scaffold that resolves the repository root, defaults to `specs/001-standardize-api-responses/contracts/api-contract.json` and `frontend/src/api-contract.generated.ts`, parses `--check`, `--contract <path>`, and `--out <path>`, reads and validates the contract JSON, and prints the route/error counts without emitting output; full emission is added in T003–T004.

**Checkpoint**: The baseline is reproducible and the generator entry point exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Generate the frontend contract surface and replace the duplicated
hand-written response types. Every user story depends on this phase.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T003 Implement contract loading, validation, and metadata emission in `frontend/scripts/generate-api-contract.mjs`: read the contract, require `version === 1`, `apiPrefix === '/api'`, a non-empty `routes` list with unique `"<METHOD> <path>"` keys, and non-empty `errorCodes`; emit deterministic TypeScript with a `DO NOT EDIT` header, `ApiMethod`, `RouteContract`, `routes` (`as const satisfies Record<string, RouteContract>`), `RouteKey`, `ApiErrorEnvelope`, `errorCodes`, `KnownApiErrorCode`, and `errorStatus`; preserve contract order, omit timestamps and absolute paths so output is machine-independent, write atomically, and make `--check` compare bytes and exit 1 with a `stale API contract` message.
- [X] T004 Extend `frontend/scripts/generate-api-contract.mjs` to emit response interfaces from the contract `schemas`: shared schemas `BrowserEntry`, `HistoryEntry`, `PreviewImage`, `PreviewVideo`, and `PreviewModel`, plus inline route responses named `DefaultsResponse`, `BrowseResponse`, `StateResponse`, `PickResponse`, `OpenResponse`, `ArchiveResponse`, `ClearResponse`, `RemoveHistoryItemResponse`, and `RemoveHistoryItemsResponse`; map `string` to `string`, `boolean` to `boolean`, `integer`/`number` to `number`, `array` to `T[]`, `{ref}` to the referenced interface, `enum` to a literal union, and `nullable: true` to `| null`; skip routes whose success schema is `null` and throw a clear error on an unknown type or ref.
- [X] T005 Run `cd frontend && node scripts/generate-api-contract.mjs` to create the checked-in `frontend/src/api-contract.generated.ts`, then run `node scripts/generate-api-contract.mjs --check`; confirm 12 route keys, 9 error codes, the five shared schema interfaces, and the nine route response interfaces are present in deterministic order, and spot-check `BrowseResponse.parent: string | null`, `PickResponse.status` as the four-value literal union, `PreviewModel.video: PreviewVideo | null`, and array element types such as `HistoryEntry[]` and `string[]`.
- [X] T006 Add `generate:api` (`node scripts/generate-api-contract.mjs`) and `check:api` (`node scripts/generate-api-contract.mjs --check`) scripts to `frontend/package.json`; do not add or change any dependency, and confirm both commands exit 0 against the checked-in generated file.
- [X] T007 Replace the hand-written response interfaces in `frontend/src/types.ts` with re-exports from `./api-contract.generated.ts` for `ArchiveResponse`, `BrowseResponse`, `BrowserEntry`, `ClearResponse`, `DefaultsResponse`, `HistoryEntry`, `OpenResponse`, `PickResponse`, `PreviewImage`, `PreviewModel`, `PreviewVideo`, `RemoveHistoryItemResponse`, `RemoveHistoryItemsResponse`, and `StateResponse`; derive `PreviewKind = PreviewModel['kind']` and `PickStatus = PickResponse['status']`, keep the existing `StateQuery` and `PickRequest` field lists, and add `RemoveHistoryItemsRequest { path: string; log_file: string | null; items: string[] }`.
- [X] T008 Verify the foundational build: `cd frontend && npm run build` and `npm run check:api`; confirm `frontend/package-lock.json` is unchanged and `frontend/package.json` differs only in the new API scripts.

**Checkpoint**: The contract surface is generated and type-checked; all user
stories can now use it.

---

## Phase 3: User Story 1 — Every Web Flow Keeps Working Through One Client Boundary (Priority: P1) 🎯 MVP

**Goal**: Move every JSON request and media address behind the single
`frontend/src/api.ts` facade while preserving all visible behavior.

**Independent Test**: Run `npm run test:api` and replay every current web flow
against the local server; confirm that only the client modules contain network
calls or endpoint addresses and that successful outcomes are unchanged.

### Tests for User Story 1 (required)

> **NOTE: Write these tests first and confirm they fail for the expected reason
> before implementing T011–T013.**

- [X] T009 [P] [US1] Write `frontend/tests/api-query.test.mjs` first, covering `undefined`, `null`, `false`, and `''` omitted; `0` included as `"0"`; `true` included; numbers as decimal strings; and strings containing spaces, Unicode, punctuation, `/`, and `\` round-tripping through `URLSearchParams` without changing route selection; run `cd frontend && node --test tests/api-query.test.mjs` and confirm it fails because `frontend/src/api-query.ts` does not exist.
- [X] T010 [P] [US1] Write `frontend/tests/api-contract.test.mjs` first, importing the frozen contract JSON, `frontend/src/api-contract.generated.ts`, `frontend/src/api-operations.ts`, and `frontend/src/api.ts`; assert the generated route set equals the 12 contract routes, every route maps to exactly one operation and vice versa, `Object.keys(api)` equals the 12 operation names, and each stubbed `fetch` call uses the generated method/path/body: `GET /api/defaults`, `GET /api/browse?path=...`, `GET /api/state` with `path`, a non-blank `log_file`, and only true filters, `POST /api/pick` with the existing body including `log_file: null` when blank, `GET /api/preview?path=...`, `POST /api/open`, `POST /api/history/archive`, `DELETE /api/history`, `DELETE /api/history/item`, and `POST /api/history/remove` with `log_file: null` when blank and the selected items; also assert `imageUrl`/`videoUrl` produce encoded addresses without fetching, including `index=0` and omitted null values, and that 2xx JSON is returned unchanged; run `cd frontend && node --test tests/api-contract.test.mjs` and confirm it fails because the operation map and rewritten facade do not exist.
- [X] T011 [P] [US1] Create `frontend/src/api-query.ts` with `QueryValue = string | number | boolean | undefined | null` and `encodeQuery(params: Record<string, QueryValue>): string`; omit `undefined`, `null`, `false`, and `''`, include `0` and `true`, stringify numbers, encode with `URLSearchParams`, preserve snake_case keys, and return `''` or `'?'` plus the encoded pairs.
- [X] T012 [P] [US1] Create `frontend/src/api-operations.ts` mapping exactly the 12 facade methods to generated route keys: `defaults`, `browse`, `state`, `pick`, `preview`, `imageUrl`, `videoUrl`, `open`, `archive`, `clear`, `removeHistoryItem`, and `removeHistoryItems`; type it as `as const satisfies Record<string, RouteKey>` and export `ApiOperation = keyof typeof operations`.
- [X] T013 [US1] Rewrite `frontend/src/api.ts` so every JSON operation derives its method and path from `routes[operations.<name>]` and appends `encodeQuery`; the facade exposes exactly the 12 operations from `frontend/src/api-operations.ts`, with `imageUrl`/`videoUrl` returning generated media addresses without fetching. Preserve query omission and JSON body semantics, including `log_file: null` for blank overrides in `pick` and `removeHistoryItems`; keep the one-`fetch`-per-operation rule, no retry/caching/queue, and preserve the current non-2xx fallback (legacy `detail`, then status text) until US2.
- [X] T014 [US1] Add `test:api` (`node --test "tests/**/*.test.mjs"`) to `frontend/package.json` and run `cd frontend && npm run test:api`; fix only client code until T009 and T010 pass, confirm the process exits 0, and confirm the tests use a stubbed transport rather than a real server.
- [X] T015 [US1] Run `cd frontend && npm run build` and replay `specs/003-frontend-api-client/quickstart.md` §6 items 1–4 (defaults, state, browse, pick, text preview, image/video display, open, archive, clear, single and batch removal, and history counts); confirm visible outcomes are unchanged, then run `rg -n "fetch\\(|axios|XMLHttpRequest|EventSource|/api/" frontend/src --glob '*.vue'` and confirm no output.

**Checkpoint**: User Story 1 is complete. All web flows use the single facade,
and successful behavior matches the pre-change baseline.

---

## Phase 4: User Story 2 — Failures Share One Typed, User-Readable Path (Priority: P2)

**Goal**: Convert every failure, including malformed and transport failures, into
one `ApiError` and display it through one shared helper.

**Independent Test**: Run `npm run test:api`; trigger documented failures, a
malformed body, an unknown code, and a stopped server; confirm each produces the
same typed shape and a readable message in the existing status area.

### Tests for User Story 2 (required)

> **NOTE: Write this test first and confirm it fails before implementing T017–T018.**

- [ ] T016 [P] [US2] Write `frontend/tests/api-errors.test.mjs` first, covering the standardized envelope with code/message/details, validation details preserved unchanged, legacy `{ detail }`, missing message with status fallback, empty and non-JSON bodies, malformed JSON, an unknown future code preserved, invalid JSON on a 2xx response, a transport rejection with status `0` and a readable message, and `apiErrorMessage` for both `ApiError` and arbitrary thrown values; run `cd frontend && node --test tests/api-errors.test.mjs` and confirm it fails because `frontend/src/api-errors.ts` does not exist.
- [ ] T017 [US2] Create `frontend/src/api-errors.ts` with `ApiError` extending `Error`, setting `name = 'ApiError'` and explicit `readonly` fields `status: number`, `code: string | null`, and `details: unknown` (no parameter properties); add `errorFromResponse(response): Promise<ApiError>`, `errorFromTransport(cause): ApiError`, `parseSuccessJson<T>(response): Promise<T>`, and `apiErrorMessage(error): string`; parse the valid envelope by shape first, then legacy `detail`, then `"<status> <statusText>"`, preserve unknown codes and details, and never leak a raw JSON parse exception.
- [ ] T018 [US2] Replace the legacy error block and unchecked JSON cast in `frontend/src/api.ts` with `errorFromResponse`, `errorFromTransport` around the `fetch` rejection, and `parseSuccessJson` for 2xx responses; re-export `ApiError` and `apiErrorMessage` from `frontend/src/api.ts`, keep one fetch per operation, and do not branch on route-specific codes.
- [ ] T019 [P] [US2] Update `frontend/src/App.vue` to import `apiErrorMessage` from `./api`, delete the local `describeError` function, and replace every catch-site formatting call with `apiErrorMessage(error)`; do not inspect `code`, `detail`, or `details`.
- [ ] T020 [P] [US2] Update `frontend/src/components/BrowserPanel.vue` to import `apiErrorMessage` from `../api` and replace the local `instanceof Error` formatting in the `load` catch block; do not inspect the error envelope.
- [ ] T021 [US2] Run `cd frontend && npm run test:api && npm run build`; confirm all 9 documented codes, legacy/missing/malformed/non-JSON bodies, unknown codes, validation details, invalid 2xx JSON, and transport failures become `ApiError`; then verify a missing-directory message and a stopped-server message in the browser per `specs/003-frontend-api-client/quickstart.md` §6 items 5–6.

**Checkpoint**: User Story 2 is complete. Every failure has one typed shape and
one display path, with backend messages unchanged.

---

## Phase 5: User Story 3 — Contract Drift Is Caught in One Place (Priority: P3)

**Goal**: Make stale generated contracts, missing routes or codes, and component
bypasses fail automated checks in CI.

**Independent Test**: Mutate the contract without regenerating, remove a route or
error code, and add a direct network call to a `.vue` file; confirm each change
fails `npm run check:api`, `npm run test:api`, or the source-boundary test.

- [ ] T022 [P] [US3] Create `frontend/tests/api-boundary.test.mjs` scanning every `frontend/src/**/*.vue` file for `fetch(`, `axios`, `XMLHttpRequest`, `EventSource`, `/api/`, `error.code`, `error.details`, and `.detail`; assert `fetch(` appears only in `frontend/src/api.ts` (exactly one call), `/api/` literals only in the generated contract and operation map, and envelope field names only in `frontend/src/api-errors.ts` and generated types.
- [ ] T023 [P] [US3] Create `frontend/tests/api-drift.test.mjs` using `node:child_process` and a temporary directory: copy the contract, run `frontend/scripts/generate-api-contract.mjs --contract <temp> --out <temp-out>` and `--check` successfully; then remove one route, rename one success field, and remove one error code in separate variants, and confirm each stale `--check` exits non-zero with the `stale API contract` message; regenerate and confirm the check recovers.
- [ ] T024 [US3] Add `Check generated API contract` (`npm run check:api`) and `Test API client` (`npm run test:api`) steps to `.github/workflows/ci.yml` with `working-directory: frontend`, placed after `Install frontend dependencies` and before `Build frontend`; keep the existing Python, lint, test, typecheck, and package steps unchanged.
- [ ] T025 [P] [US3] Update `frontend/README.md` to identify `frontend/src/api.ts` as the only frontend API boundary, explain that `frontend/src/api-contract.generated.ts` is generated and never hand-edited, document `generate:api`, `check:api`, `test:api`, the Node 22.18+ requirement, and the add/change-route sequence from `specs/003-frontend-api-client/contracts/frontend-api-client.md` §8.
- [ ] T026 [P] [US3] Add a short frontend client-boundary note to the Architecture section of `README.md` and a non-behavioral `Unreleased` entry to `CHANGELOG.md`; do not change version numbers, extras, entry points, or dependencies.
- [ ] T027 [US3] Execute the drift drill in `specs/003-frontend-api-client/quickstart.md` §7 (append a newline to the generated file, confirm `npm run check:api` fails, restore, confirm it passes); then temporarily add a direct `fetch('/api/defaults')` to one `frontend/src/components/*.vue` file, confirm `npm run test:api` fails on the boundary test, restore the file, and run `cd frontend && npm run check:api && npm run test:api && npm run build`; confirm the final run is green and reports no `.vue` bypasses.

**Checkpoint**: User Story 3 is complete. Stale contracts and component bypasses
fail automated checks, and CI runs them before the production build.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final regression, frozen-contract, dependency, and end-to-end
validation across all stories.

- [ ] T028 [P] Run the unchanged backend gate for `choosier/`, `main.py`, and `tests/` from the repository root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, and `uv run mypy choosier main.py tests`; if `uv run` cannot resolve packages, use the existing `.venv/bin/python -m ...` equivalents; do not modify backend files.
- [ ] T029 [P] Verify the frozen boundary and dependency policy: `git diff --exit-code -- specs/001-standardize-api-responses/contracts/api-contract.json specs/001-standardize-api-responses/contracts/api-contract.md`, `git diff --exit-code -- frontend/package-lock.json`, inspect `git diff -- frontend/package.json` for scripts only, and confirm `git status --short choosier/web_static frontend/dist` is empty; no backend route, schema, status, message, or dependency may change.
- [ ] T030 Execute `specs/003-frontend-api-client/quickstart.md` §1–§7 end to end, including starting `uv run choosier --web --port 8765` and replaying defaults, state, browse, pick, text/image/video preview, open, archive, clear, single and batch removal, the missing-directory error, and the stopped-server error; record any mismatch with the baseline as a regression.
- [ ] T031 Review the complete diff: confirm changes are limited to `frontend/src/api*.ts`, `frontend/src/types.ts`, `frontend/src/App.vue`, `frontend/src/components/BrowserPanel.vue`, `frontend/scripts/`, `frontend/tests/`, `frontend/package.json`, `frontend/README.md`, `specs/003-frontend-api-client/`, `.github/workflows/ci.yml`, `README.md`, and `CHANGELOG.md`; confirm 12 routes and 9 codes, no `.vue` bypass, accurate docs, Conventional Commit messages, and no temporary files.

**Checkpoint**: All stories, documentation, CI, and quality gates are complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 and T002 can start immediately.
- **Foundational (Phase 2)**: Depends on T002; BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers the P1 client
  boundary.
- **User Story 2 (Phase 4)**: Depends on Foundational and T013; adds the typed
  error path without changing successful flows.
- **User Story 3 (Phase 5)**: Depends on US1 and US2 for the final boundary scan
  and CI checks.
- **Polish (Phase 6)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories after Foundational; it is the MVP.
- **US2 (P2)**: Integrates with the US1 facade but can be tested independently
  through `api-errors.test.mjs` and direct `ApiError` assertions.
- **US3 (P3)**: Integrates with US1's operation map and US2's display helper;
  independently testable through the drift, boundary, and CI checks.

### Within Each User Story

- Tests are written first and must fail for the expected reason.
- US1: query and operation modules before the facade; facade before
  `test:api`; tests before the production build and flow replay.
- US2: error parser before facade integration; facade integration before the two
  UI edits; UI edits before the final verification.
- US3: generator `--check` support from T003–T004 before the drift test;
  boundary and drift tests before CI wiring; docs before the final drill.
- Polish: backend gate and frozen-contract checks before the end-to-end
  quickstart review.

### Parallel Opportunities

- T001 and T002 are independent.
- T003 → T004 → T005 are sequential in the same generator file; T006 and T007
  can run in parallel after T005.
- T009 and T010 are separate test files and can be written together; T011 and
  T012 are separate implementation files and can run together.
- T019 and T020 touch separate Vue files and can run in parallel after T018.
- T022, T023, T025, and T026 touch separate files and can run in parallel.
- T028 and T029 are independent final checks.
- After T018, US2 UI work and US3 boundary-test authoring can proceed in
  parallel; T024 waits for T014 and T023, and T027 waits for T022–T026.

---

## Parallel Example: User Story 1

```bash
# Write both tests first; each should fail for its missing module or facade:
Task: "Write frontend/tests/api-query.test.mjs"
Task: "Write frontend/tests/api-contract.test.mjs"

# Then implement the two independent pure modules:
Task: "Create frontend/src/api-query.ts"
Task: "Create frontend/src/api-operations.ts"
```

## Parallel Example: User Story 2

```bash
# After the typed parser is integrated into the facade:
Task: "Update frontend/src/App.vue"
Task: "Update frontend/src/components/BrowserPanel.vue"
```

## Parallel Example: User Story 3

```bash
Task: "Create frontend/tests/api-boundary.test.mjs"
Task: "Create frontend/tests/api-drift.test.mjs"
Task: "Update frontend/README.md"
Task: "Update README.md and CHANGELOG.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational — the generated contract and shared types are
   hard prerequisites.
3. Complete Phase 3: User Story 1 — centralize every request and media address.
4. **STOP and VALIDATE**: run T014's `npm run test:api` and T015's production
   build plus flow replay.
5. Demo the single-boundary refactor.

The MVP proves centralization, but the feature is not complete until US2 and
US3 pass: `FR-005`, `FR-012`, and `FR-013` require the typed error path and the
automated drift/boundary checks.

### Incremental Delivery

1. Setup + Foundational → generated contract ready.
2. US1 → one client boundary, unchanged successful behavior.
3. US2 → one typed error path, unchanged visible messages.
4. US3 → drift and bypass checks enforced locally and in CI.
5. Polish → full backend gate, frozen contract, and manual smoke.

Each increment is independently testable and must leave `npm run build`,
`npm run check:api`, and `npm run test:api` green before the next story starts.

### Parallel Team Strategy

1. One developer completes Setup + Foundational.
2. After T013, one developer finishes US1 verification while another implements
   US2's parser and UI integration.
3. After US2, a third developer can author the US3 boundary and drift tests
   while documentation and CI wiring proceed.
4. Rejoin for Polish; no story is declared complete until its checkpoint and the
   final quickstart pass.

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task.
- `[Story]` labels map every user-story task to `US1`, `US2`, or `US3`.
- Tests MUST fail for the expected reason before the matching implementation is
  written; do not commit a failing test, build, or check.
- Commit after each task or logical group with a Conventional Commit message only
  after the task's listed verification passes.
- The authoritative contract and all backend files are read-only for this
  feature; `frontend/src/api-contract.generated.ts` must never be hand-edited.
- Do not add a runtime or test-framework dependency, ESLint stack, browser
  automation, retry, caching, or global state.
- Node 22.18+ is required for built-in TypeScript type stripping; use
  `.venv/bin/python -m ...` only as the fallback when `uv run` cannot resolve
  packages in an isolated environment.
