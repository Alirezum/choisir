# Research: Frontend API Client Layer

**Feature**: `specs/003-frontend-api-client`
**Date**: 2026-11-01

## Summary

No `NEEDS CLARIFICATION` items remain. The feature will keep one public client
facade, generate its route and response-type surface from the frozen backend
contract, convert every failure into one typed error, and enforce route,
error-code, and source-boundary invariants with Node's built-in test runner.
The implementation adds no runtime dependency and changes no backend behavior.

## Decision 1: Generate the frontend contract surface from the authoritative JSON

**Decision**: Add `frontend/scripts/generate-api-contract.mjs`, which reads
`specs/001-standardize-api-responses/contracts/api-contract.json` and writes a
checked-in `frontend/src/api-contract.generated.ts`. The generated module
contains:

- route method/path entries keyed by a stable `METHOD path` key;
- success interfaces for shared schemas and JSON routes;
- the known error-code union, catalog, and status map;
- the standardized error-envelope type.

The script supports a `--check` mode that regenerates in memory and exits
non-zero when the checked-in file is stale.

**Rationale**: The contract JSON is already the authoritative source used by
the backend tests. Generating the frontend types and routes from it removes a
second hand-maintained copy and makes removed/renamed fields, routes, or error
codes fail before release.

**Alternatives considered**:

- Hand-write the types and add a separate field-name manifest for tests
  (rejected: duplicates the same contract in two places and still misses type
  or nullability drift).
- Import the JSON at build time and decode schema descriptors with conditional
  TypeScript types (rejected: complex, brittle, and hard to read).
- Add runtime response validation with a schema library (rejected: introduces
  a runtime dependency for a local-first tool and is unnecessary for trusted
  same-origin responses).
- Keep the current hand-written `types.ts` only (rejected: no automated link
  between the frozen contract and the client).

## Decision 2: Keep one public facade and isolate pure helpers

**Decision**: Keep `frontend/src/api.ts` as the only public client import used
by screens and components. Add small modules around it:

- `api-query.ts`: query-string encoding and conditional omission;
- `api-errors.ts`: `ApiError`, error-envelope parsing, and the shared display
  helper;
- `api-operations.ts`: friendly operation names mapped to generated route
  keys;
- `api-contract.generated.ts`: generated contract data and types.

`api.ts` builds every request from the operation map and generated route, and
re-exports the error helper. Screens keep importing from `./api` or `../api`.

**Rationale**: The existing facade already gives screens a single import path.
Splitting only the pure, testable pieces keeps the change reversible and lets
Node tests import the modules without Vue, Vite, or jsdom.

**Alternatives considered**:

- Keep everything in one `api.ts` (rejected: the transport, route data, and
  parser become harder to test in isolation).
- Create a nested `frontend/src/api/` package and rewrite all imports
  (rejected: import churn with no user-facing benefit).
- Put the client in a global store or composable (rejected: adds state
  management scope that the feature explicitly excludes).

## Decision 3: One typed error parser with explicit fallbacks

**Decision**: Represent every frontend failure as `ApiError`, carrying:

- `status`: the HTTP status, or `0` for a transport failure;
- `code`: the backend's stable code as a string, or `null` when no envelope
  code exists;
- `message`: the backend message, legacy `detail`, or status fallback;
- `details`: the structured backend details, or `null`.

Parsing rules:

| Response body | Result |
| --- | --- |
| Standardized envelope with `error.message` | Use code, message, and details; verify fields by shape, not by route. |
| Legacy object with only a string `detail` | Use `detail` as the message and a `null` code. |
| Non-JSON, empty, or malformed body | Fall back to `"<status> <statusText>"`. |
| Missing message in an otherwise valid envelope | Fall back to the status text. |
| Unknown future error code | Preserve the raw code and message; do not discard the failure. |
| Successful response with invalid JSON | Produce an `ApiError` with a readable invalid-response message. |
| Transport rejection | Produce an `ApiError` with status `0` and a readable message. |

The known codes and status mapping come from the generated contract. The
`code` field stays a string so future backend codes remain representable.
`apiErrorMessage(error)` returns the shared message for screens; components do
not inspect codes or details.

**Rationale**: The backend already guarantees one envelope. Parsing it in one
place makes every failure uniformly inspectable while preserving the message
users see today.

**Alternatives considered**:

- Continue throwing plain `Error` with only `detail` (rejected: loses code,
  status, and structured details and leaves parsing duplicated).
- Return a discriminated result union instead of throwing (rejected: larger
  control-flow change across every screen for no user-visible benefit).
- Use an HTTP client library (rejected: adds a dependency and still needs a
  custom envelope parser).
- Reject unknown future codes (rejected: a backend addition would break the UI
  before the client catches up).

## Decision 4: Node built-in tests with TypeScript type stripping

**Decision**: Put client tests in `frontend/tests/*.test.mjs` and run them with
`node --test "tests/**/*.test.mjs"`. The tests import the pure `.ts` helper
modules directly; Node 22.18+ strips the type annotations at runtime by default.
Client modules that tests import use explicit `.ts` import extensions, which the
existing TypeScript configuration already permits. No test framework or new
package is added.

**Rationale**: The repository currently has no frontend test runner, and the
constitution discourages unnecessary dependencies. Node 22 is already the CI
and development runtime, and its built-in runner covers the parser, query,
route, and source-scan tests without a bundler. Pure helpers use only erasable
TypeScript syntax, matching the repository's `erasableSyntaxOnly` setting.

**Alternatives considered**:

- Vitest or Jest (rejected: new dev dependencies and configuration for a small
  set of pure-module tests).
- Playwright or browser automation (rejected: heavy and unnecessary for
  contract, parser, and boundary checks; manual smoke remains in the
  quickstart).
- Python tests that parse TypeScript source (rejected: brittle and unrelated
  to the frontend toolchain).
- Rely only on `vue-tsc` (rejected: type checking cannot compare the client
  against the external JSON contract or detect direct `fetch` calls).

## Decision 5: Three complementary drift and boundary checks

**Decision**:

1. `npm run check:api` runs the generator in `--check` mode and fails when the
   generated module does not match the contract JSON.
2. `npm run test:api` checks that every generated route has exactly one
   friendly operation mapping, that the public facade exposes every operation,
   that calls use the generated path and method, that every known error code is
   present, and that media/query construction matches the contract.
3. A boundary test scans every `.vue` file and fails on `fetch`, `axios`,
   `XMLHttpRequest`, `EventSource`, `/api/` address literals, or direct error
   envelope access.

**Rationale**: Each check catches a different failure: stale generated code,
missing client coverage, or a component bypassing the client. All are
deterministic, fast, and dependency-free.

**Alternatives considered**:

- Manual review only (rejected: does not satisfy the drift and bypass success
  criteria).
- A custom ESLint rule (rejected: adds a lint stack the repository does not
  use).
- Runtime assertions in the browser (rejected: too late and not run in CI).

## Decision 6: Preserve visible behavior and centralize display

**Decision**: Successful flows, screen state, status messages for domain
outcomes, and standardized error text remain unchanged. `App.vue` and
`BrowserPanel.vue` replace their local `instanceof Error` formatting with the
shared `apiErrorMessage` helper. No route-specific branching is added.

**Rationale**: The feature is an internal boundary refactor. Users should not
notice it on successful flows, and the standardized backend message is already
the text they see today.

**Alternatives considered**:

- Redesign error display with code-specific messages (rejected: new UX scope).
- Keep duplicated local error formatting (rejected: leaves multiple error
  paths and weakens the shared-boundary guarantee).

## Decision 7: Centralize media addresses without fetching binary data

**Decision**: `api.imageUrl` and `api.videoUrl` build their addresses from the
generated image/video route plus the shared query encoder. Components continue
to assign those addresses to `<img>` and `<video>`; the client does not fetch or
buffer binary payloads.

**Rationale**: The browser already streams and caches media efficiently. Moving
binary data through the JSON client would add memory pressure and change
loading behavior.

**Alternatives considered**:

- Fetch image/video blobs in the client (rejected: unnecessary buffering and
  new object-URL lifecycle).
- Leave URL construction in components (rejected: violates the single
  boundary and duplicates encoding rules).

## Decision 8: Documentation and CI integration

**Decision**: Add `generate:api`, `check:api`, and `test:api` scripts to
`frontend/package.json`; run `check:api` and `test:api` in CI before the
existing production build; document the boundary and regeneration workflow in
`frontend/README.md` and the root architecture notes; add a non-behavioral
`CHANGELOG.md` entry. No dependency sections change.

**Rationale**: The checks are only useful if CI runs them and maintainers know
how to regenerate the contract module after an approved API change.

**Alternatives considered**:

- Run generation during `npm run build` (rejected: hides stale checked-in code
  and makes builds mutate tracked source).
- Document only in the feature spec (rejected: future contributors start from
  the repository READMEs).
