# Quickstart: Frontend API Client Layer

**Feature**: `specs/003-frontend-api-client`
**Date**: 2026-11-01

Use this guide to validate the typed client boundary end to end. It assumes the
backend contract at
`specs/001-standardize-api-responses/contracts/api-contract.json` is frozen and
the existing web UI behavior is the compatibility baseline.

## Prerequisites

- Node.js 22.18 or newer (the built-in test runner and default TypeScript type
  stripping are used).
- Python 3.12 and `uv` for the backend and full quality gate.
- A local browser for the optional manual smoke test.
- No database, external service, or browser automation framework is required.

## Setup

Install the same dependencies CI uses:

```bash
uv sync --group dev --extra ui --extra web
cd frontend
npm ci
```

Return to the repository root for the Python commands:

```bash
cd ..
```

## 1. Generated Contract Is Current

```bash
cd frontend
npm run check:api
```

Expected: the command exits `0` and reports that the generated contract matches
the authoritative JSON. It must fail if the generated module is edited or the
contract changes without regeneration.

To regenerate after an approved contract change:

```bash
npm run generate:api
npm run check:api
```

## 2. Client Contract, Error, Query, and Boundary Tests

```bash
cd frontend
npm run test:api
```

Expected: all Node tests pass. They cover:

- every contract route has exactly one friendly operation and every operation
  maps back to a generated route;
- the public facade exposes exactly those operations;
- request method, path, query, and body construction match the contract;
- standardized, legacy, malformed, empty, unknown-code, invalid-success, and
  transport failures become one `ApiError`;
- query omission and encoding rules, including `0`, `false`, empty strings, and
  Unicode;
- no `.vue` file contains `fetch`, `axios`, `XMLHttpRequest`, `EventSource`, an
  `/api/` literal, or direct error-envelope parsing.

## 3. Production Type Check and Build

```bash
cd frontend
npm run build
```

Expected: `vue-tsc -b` reports no type errors and Vite builds into
`choosier/web_static/`. The generated bundle remains ignored by git, as today.

## 4. Manual Source-Boundary Review

From the repository root:

```bash
rg -n "fetch\\(|axios|XMLHttpRequest|EventSource|/api/" frontend/src
```

Expected: network calls and endpoint literals appear only in the client
modules (`api.ts`, `api-operations.ts`, and the generated contract). No
`.vue` file appears in the results.

```bash
rg -n "detail|error\\.code|error\\.details" frontend/src --glob '*.vue'
```

Expected: no output. Screens display `apiErrorMessage(error)` and never inspect
the envelope.

## 5. Full Quality Gate

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy choosier main.py tests
```

Expected: the complete backend suite, lint, format, and strict type check pass
unchanged. The frontend change must not require a Python test or assertion
change.

## 6. Manual Web Smoke Test

Start the local server:

```bash
uv run choosier --web --port 8765
```

Open `http://127.0.0.1:8765` and verify:

1. The default folder loads and the Remaining/History counts match the current
   behavior.
2. Browse a folder, pick an item, preview text, and open an entry.
3. Pick and display an image and a video.
4. Archive, clear, single-remove, and batch-remove history; confirm the same
   status messages and confirmation behavior as before.
5. Enter a missing directory in the Browse panel and confirm the backend's
   `Not a directory` message appears.
6. Stop the server and trigger an action; confirm a readable connection failure
   appears instead of a raw parser error.

Expected: every successful flow and standardized error message matches the
pre-change behavior; only the internal handling location changes.

## 7. Drift Drill (Optional)

Verify the contract check catches stale generated code using a temporary copy:

```bash
cd frontend
tmp_copy="${TMPDIR:-/tmp}/api-contract.generated.ts"
cp src/api-contract.generated.ts "$tmp_copy"
printf '\n' >> src/api-contract.generated.ts
npm run check:api   # expected: non-zero, stale-generated-contract message
cp "$tmp_copy" src/api-contract.generated.ts
npm run check:api   # expected: zero
```

Expected: the first check fails and the restored check passes. Do not commit the
temporary edit.

## 8. Expected Results Summary

| Check | Expected |
| --- | --- |
| `npm run check:api` | Generated contract matches the frozen JSON. |
| `npm run test:api` | All route, facade, parser, query, and boundary tests pass. |
| `npm run build` | Type check and production bundle succeed. |
| Source scans | No network calls or envelope parsing in `.vue` files. |
| `uv run pytest` | Existing backend suite passes unchanged. |
| `ruff` / `mypy` | No new findings. |
| Manual web smoke | Successful flows and standardized error messages are unchanged. |
