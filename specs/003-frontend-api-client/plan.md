# Implementation Plan: Frontend API Client Layer

**Branch**: `003-frontend-api-client` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-frontend-api-client/spec.md`

## Summary

Centralize every frontend request behind the existing `frontend/src/api.ts`
facade, make its route methods, success response types, and error-code catalog
come from the frozen backend contract in
`specs/001-standardize-api-responses/contracts/api-contract.json`, and replace
ad-hoc `Error` handling with one typed `ApiError` parser. UI components keep
their current imports and visible behavior but may no longer contain network
calls, endpoint address literals, or error-envelope parsing.

A small Node script generates a checked-in TypeScript contract module from the
authoritative JSON. Contract freshness, route coverage, error parsing, query
encoding, and UI source boundaries are verified by Node's built-in test runner,
so the feature adds no runtime or test-framework dependency. The production
build and the existing Python quality gate remain authoritative.

## Technical Context

**Language/Version**: TypeScript ~6.0.3 with Vue 3.5, Vite 8, and Node.js
22.18+ (the repository's existing frontend toolchain; 22.18+ provides default
TypeScript type stripping for the tests)

**Primary Dependencies**: Existing Vue, Vite, TypeScript, and `vue-tsc` only;
no new runtime or test-framework dependency. Node's built-in test runner and
type stripping execute the pure client modules in tests.

**Storage**: N/A. The authoritative interface data is the frozen JSON contract
at `specs/001-standardize-api-responses/contracts/api-contract.json`; the
frontend keeps no new persistence.

**Testing**: `npm run check:api` for generated-contract freshness,
`npm run test:api` for Node tests covering route coverage, error parsing, query
encoding, transport calls, and source boundaries, and `npm run build` for the
production type check and bundle. Existing `uv run pytest`, `ruff`, and `mypy`
remain the backend regression gate.

**Target Platform**: Browser frontend served locally by the Python web adapter;
Node.js 22.18+ for development, tests, and CI builds.

**Project Type**: Web application frontend inside the existing Python CLI
package (`frontend/` source, generated bundle under `choosier/web_static/`).

**Performance Goals**: No additional network requests and no user-visible
latency change. The client wrapper adds only request construction and response
parsing that already happen today.

**Constraints**: The backend route, success schema, error envelope, status
codes, and messages are frozen. The client remains same-origin and loopback
only. No new runtime dependency, authentication, telemetry, caching, retry,
offline behavior, or browser end-to-end framework is introduced. Node 22 is
required because the tests run TypeScript through built-in type stripping.

**Scale/Scope**: 12 API routes, 9 documented error codes, one public client
facade, and the existing set of screens and reusable components. Single local
user; no multi-tenant or high-concurrency concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Constraint | Status | Notes |
| --- | --- | --- |
| I. Deterministic Selection | PASS | No selection, ordering, seeding, or history logic is touched. |
| II. Local and Private by Default | PASS | The client calls only the same-origin `/api` routes and adds no external service, telemetry, or authentication. |
| III. User Data Is Inviolable | PASS | No file or history mutation is added; existing endpoints and confirmation behavior are unchanged. |
| IV. Shared Core, Thin Interfaces | PASS | The frontend remains an adapter; no Python core change and no new mandatory runtime dependency. Generated code is build-time only. |
| V. Verified, Boring Changes | PASS | Contract, parser, query, transport, and source-boundary tests are planned; production build and existing Python gates remain required. Documentation and changelog updates are included. |
| Technical constraints | PASS | The public HTTP contract and generated asset flow are unchanged; frontend source stays in `frontend/`, and the contract JSON stays authoritative. |
| Git and commit policy | PASS | Implementation tasks will be committed atomically with Conventional Commit messages after verification. |

No violations or complexity exceptions are required.

**Post-design re-check (after Phase 1)**: all gates remain PASS. The design
adds only frontend source, a build-time generator, checked-in generated types,
and Node tests. It introduces no backend change, runtime dependency, external
network access, or user-visible feature.

## Project Structure

### Documentation (this feature)

```text
specs/003-frontend-api-client/
├── plan.md                          # This file
├── research.md                      # Phase 0 output
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output
├── contracts/
│   └── frontend-api-client.md       # Client surface and boundary contract
├── checklists/
│   └── requirements.md              # Specification quality checklist
├── spec.md
└── tasks.md                         # Created by /speckit.tasks
```

### Source Code (repository root)

```text
frontend/
├── scripts/
│   └── generate-api-contract.mjs    # Contract JSON -> checked-in TS module
├── src/
│   ├── api.ts                       # Public client facade
│   ├── api-contract.generated.ts    # Generated routes, types, error catalog
│   ├── api-errors.ts                # ApiError and response error parser
│   ├── api-operations.ts            # Friendly operation -> contract route map
│   ├── api-query.ts                 # Query-string encoder
│   ├── types.ts                     # Re-exports generated types + request types
│   ├── App.vue                      # Uses the facade only
│   └── components/                  # Use the facade only
├── tests/
│   ├── api-boundary.test.mjs        # Source-boundary scan
│   ├── api-contract.test.mjs        # Route/operation coverage and calls
│   ├── api-errors.test.mjs          # Envelope and fallback parsing
│   └── api-query.test.mjs           # Encoding and omission rules
├── package.json                     # Add check/test scripts only
└── README.md                        # Maintainer boundary documentation
.github/workflows/ci.yml             # Add contract and client test step
README.md                            # One architecture note
CHANGELOG.md                         # Non-behavioral entry
specs/001-standardize-api-responses/contracts/api-contract.json  # Read-only source
choosier/                            # Unchanged backend
```

**Structure Decision**: Keep the existing `frontend/src/api.ts` import path as
the single public facade so screens and components change only where they need
the shared error message helper. Pure helpers are split into small modules that
Node can import directly, while the generated module is the only place that
duplicates contract route and response information. No backend or Python
package structure changes.

## Complexity Tracking

No constitution violations; no complexity justification is required.
