# Implementation Plan: Standardize API Responses and Error Schemas

**Branch**: `refactor/01-api-contracts` (feature `001-standardize-api-responses`) | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-standardize-api-responses/spec.md`

## Summary

Introduce one documented JSON error envelope for every `/api/*` response while
leaving every existing success payload and every route path, method, and
request parameter unchanged. The envelope keeps the current string `detail`
for the Vue client and adds a stable category code, message, and optional
structured details:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not a directory",
    "details": null
  },
  "detail": "Not a directory"
}
```

Framework-generated 404, 405, 422, and 500 responses are normalized through
the same handlers, as are malformed byte-range failures from the binary video
endpoint. A machine-readable contract inventory in
`specs/001-standardize-api-responses/contracts/api-contract.json` records every
route's success shape, statuses, content types, and error cases, and new
stdlib tests compare it against FastAPI's OpenAPI schema, the live route table,
and representative error responses. No frontend source change is required.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript/Vue 3 source remains
unchanged.

**Primary Dependencies**: FastAPI, Starlette, and Pydantic from the existing
optional `web` extra; Pillow for image previews. No new runtime or development
dependencies.

**Storage**: JSON Lines history log and timestamped archives; no storage format
change. Error handling never writes history.

**Testing**: `pytest` / stdlib `unittest` with `fastapi.testclient.TestClient`;
new contract and drift tests; existing `tests/test_web.py` behavior suite;
`ruff check`, `ruff format --check`, and strict `mypy`; frontend `npm run build`
remains green.

**Target Platform**: Local desktop use on Linux, macOS, and Windows; the web
server continues to bind to `127.0.0.1` only.

**Project Type**: Python library plus CLI, TUI, and a local web application
(FastAPI backend with a Vue single-page frontend).

**Performance Goals**: No measurable request-latency regression. Exception
handling is constant-time; binary image and video success paths still stream
without buffering; contract tests complete within the existing suite runtime.

**Constraints**: No route paths, HTTP methods, request semantics, emitted
success values, authentication model, or loopback binding may change. No new
dependencies. No success payload wrapping. The only annotation tightening is
`PreviewModel.kind` from `str` to the existing `PreviewKind` Literal, which
emits the same values and the same JSON type. Binary endpoints keep their
current bytes and byte-range behavior. Failure paths must leave the target
directory and history log untouched.

**Scale/Scope**: 12 existing `/api/*` routes, one local user, and small
filesystem targets; preview work stays bounded by the existing 1,000-image,
20 MB, and 8 KB/10-line caps.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Result |
|-----------|------|--------|
| I. Deterministic Selection | Selection logic (`list_candidates`, `get_unselected_item`, ordering, history exhaustion) is not modified; seeded and domain-outcome behavior is covered by existing tests. | PASS |
| II. Local and Private by Default | No network, telemetry, auth, or binding change; error bodies add no file contents, only the existing human-readable messages. | PASS |
| III. User Data Is Inviolable | Error handling only formats responses. No route writes on failure; tests assert failed requests leave the target and log bytes unchanged. | PASS |
| IV. Shared Core, Thin Interfaces | All production changes stay in the web adapter (`choosier/web.py`); `choosier/preview.py` and `choosier/storage.py` remain unchanged; no new dependencies; core stays stdlib-only. | PASS |
| V. Verified, Boring Changes | Adds route-contract and regression tests, updates `README.md` and `CHANGELOG.md`, and runs the full test/lint/format/typecheck/frontend-build gate. | PASS |

No violations and no complexity exceptions. The feature deliberately avoids a
new error module, runtime schema package, or frontend refactor.

## Project Structure

### Documentation (this feature)

```text
specs/001-standardize-api-responses/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Error and contract entities
├── quickstart.md        # Validation and smoke-test guide
├── contracts/
│   ├── api-contract.json # Machine-readable route inventory (test source of truth)
│   └── api-contract.md   # Human-readable route and error audit
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
choosier/
├── web.py               # Error envelope, handlers, route error migration,
│                        # PreviewModel.kind typing, video range validation
├── preview.py           # Unchanged; PreviewKind Literal is reused
├── storage.py           # Unchanged history read/rewrite/archive helpers
├── chooser.py           # Unchanged selection logic
└── web_static/          # Built frontend bundle (generated, not edited)

frontend/
└── src/                 # Unchanged; existing request() continues to read detail

tests/
├── test_web.py          # Existing route behavior tests (unchanged assertions)
└── test_api_contract.py # New route inventory, success-shape, error-envelope,
                         # binary-response, and seeded-drift tests

README.md                # Document the error envelope and contract location
CHANGELOG.md             # Unreleased entry for the standardized errors
```

**Structure Decision**: Single Python package with a colocated Vue frontend.
This feature is confined to the existing FastAPI adapter, its tests, and
documentation; the core library, TUI, CLI, and frontend source are untouched.

## Implementation Outline

1. Add a small error vocabulary and helpers to `choosier/web.py`: a code-to-
   status map, an `ApiError` exception carrying code/message/details, and one
   envelope serializer.
2. Register handlers for `ApiError`, `RequestValidationError`,
   `StarletteHTTPException`, and unexpected `Exception`, so route, framework,
   unknown-path, and server failures all use the envelope. Preserve the
   `Allow` header on 405 and emit JSON for unhandled 500s.
3. Replace route-level `HTTPException` raises with `ApiError` codes while
   keeping every existing message string and status. Leave all success returns
   and domain outcomes untouched.
4. Pre-validate `Range` on `/api/video` using Starlette's parser, converting
   malformed/unsatisfiable ranges to `invalid_request` (400) and
   `range_not_satisfiable` (416) JSON while delegating valid single, suffix,
   and multipart ranges to `FileResponse`.
5. Narrow `PreviewModel.kind` to the existing `PreviewKind` Literal (same
   values) so the success contract is explicitly enumerable.
6. Add `tests/test_api_contract.py` with inventory parity, OpenAPI success-
   schema comparison, live error-envelope checks, binary content checks, and
   seeded-drift assertions.
7. Update `README.md` and `CHANGELOG.md`; run the full quality gate and the
   frontend production build.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. No additional projects, layers, dependencies, or runtime
artifacts are introduced.

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design on 2026-10-29.*

| Principle | Post-design evidence | Result |
|-----------|----------------------|--------|
| I. Deterministic Selection | The design touches only response formatting; no selection, ordering, seed, or history-eligibility code path changes. | PASS |
| II. Local and Private by Default | Error serialization contains only existing messages and validation field locations; no new data leaves the machine and the bind address is unchanged. | PASS |
| III. User Data Is Inviolable | Handlers are read-only; the only writes remain the existing pick/archive/clear/remove operations, and contract tests cover failure no-op behavior. | PASS |
| IV. Shared Core, Thin Interfaces | The contract lives in feature documentation, not runtime code; no core dependency or duplicated selection/preview logic is added. | PASS |
| V. Verified, Boring Changes | The design includes the complete contract inventory, automated drift checks, existing-test preservation, docs, and the repository's full gate. | PASS |
