# Frontend API Client Contract

**Feature**: `specs/003-frontend-api-client`
**Date**: 2026-11-01
**Status**: Design baseline for implementation

This contract defines the frontend boundary introduced by the feature. The
authoritative backend interface remains
`specs/001-standardize-api-responses/contracts/api-contract.json`; this
document describes how the frontend consumes it and what maintainers can rely
on.

## 1. Authority and Scope

- The backend contract JSON owns route methods, paths, success schemas, error
  codes, and statuses.
- The frontend contract is generated from that JSON into
  `frontend/src/api-contract.generated.ts`.
- The public facade is `frontend/src/api.ts`. Screens and components import
  only that facade.
- No Python module, backend route, response field, status, error message, or
  history behavior changes.

## 2. Public Client Surface

The facade exposes exactly these operations:

| Operation | HTTP | Path | Input | Success result |
| --- | --- | --- | --- | --- |
| `defaults()` | GET | `/api/defaults` | none | `DefaultsResponse` |
| `browse(path)` | GET | `/api/browse` | `path` query | `BrowseResponse` |
| `state(params)` | GET | `/api/state` | `StateQuery` | `StateResponse` |
| `pick(body)` | POST | `/api/pick` | `PickRequest` JSON | `PickResponse` |
| `preview(path)` | GET | `/api/preview` | `path` query | `PreviewModel` |
| `imageUrl(path, index?, variant?)` | GET | `/api/image` | query | media address |
| `videoUrl(path)` | GET | `/api/video` | `path` query | media address |
| `open(path)` | POST | `/api/open` | `{path}` JSON | `OpenResponse` |
| `archive(path, logFile)` | POST | `/api/history/archive` | `path`, `log_file` query | `ArchiveResponse` |
| `clear(path, logFile)` | DELETE | `/api/history` | `path`, `log_file` query | `ClearResponse` |
| `removeHistoryItem(path, logFile, item)` | DELETE | `/api/history/item` | query | `RemoveHistoryItemResponse` |
| `removeHistoryItems(path, logFile, items)` | POST | `/api/history/remove` | JSON body | `RemoveHistoryItemsResponse` |

Rules:

- Every operation above corresponds to exactly one route in the generated
  contract and uses that route's method and path.
- The operation map contains no route outside the generated contract.
- `imageUrl` and `videoUrl` return strings; they never perform network I/O.
- Request bodies use JSON with `Content-Type: application/json`.
- Query values follow the encoding rules in section 4.
- The facade also exports `ApiError` and `apiErrorMessage` for consumers.

## 3. Error Contract

Every failure is an `ApiError` with:

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | `number` | HTTP status, or `0` for a transport failure |
| `code` | `string \| null` | Backend stable code; `null` when unavailable |
| `message` | `string` | Display message |
| `details` | `unknown` | Structured backend details or `null` |

The backend envelope is:

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

Parsing rules:

| Response | `code` | `message` | `details` |
| --- | --- | --- | --- |
| Valid envelope | `error.code` | `error.message` | `error.details` |
| Valid envelope with missing message | `error.code` | `"<status> <statusText>"` | `error.details` |
| Legacy `{ "detail": "..." }` | `null` | `detail` | `null` |
| Non-JSON or empty body | `null` | `"<status> <statusText>"` | `null` |
| Unknown future code | raw code string | `error.message` | `error.details` |
| Transport rejection | `null` | readable error message | `null` |
| Invalid JSON on a 2xx response | `null` | readable invalid-response message | `null` |

Invariants:

- `ApiError` extends `Error`, so existing message display remains valid.
- No raw JSON parse exception reaches a screen.
- Known codes and statuses match the generated catalog exactly:

| Code | Status |
| --- | --- |
| `invalid_request` | 400 |
| `forbidden` | 403 |
| `not_found` | 404 |
| `method_not_allowed` | 405 |
| `payload_too_large` | 413 |
| `unsupported_media_type` | 415 |
| `range_not_satisfiable` | 416 |
| `validation_error` | 422 |
| `internal_error` | 500 |

- `error.details` is passed through without reformatting; validation issues
  remain available unchanged.
- Domain outcomes reported with HTTP 2xx are successes, never errors.

Display contract:

- `apiErrorMessage(error)` returns the `ApiError` message for typed failures
  and the existing message for any other thrown value.
- Screens display that message in the existing status area or panel error line.
- Screens do not branch on `code`, `status`, or route-specific envelopes.

## 4. Query and Media Encoding

| Input value | Result |
| --- | --- |
| `undefined`, `null`, `false`, `""` | Omitted |
| `0` | `0` |
| `true` | `true` |
| number | decimal string |
| string | form-encoded via `URLSearchParams` |

Rules:

- Optional `log_file` values are omitted when blank.
- Filters are included only when true, matching the backend defaults.
- Image `index=0` is included; `null` or absent is omitted.
- Image and video variants are encoded exactly as the backend expects.
- Media addresses are same-origin and are not fetched by the client.

## 5. Source Boundary

Allowed locations for network and endpoint details:

- `frontend/src/api.ts` for the single `fetch` call and request construction.
- `frontend/src/api-contract.generated.ts` for generated paths.
- `frontend/src/api-operations.ts` for friendly-name mapping.
- `frontend/src/api-*` helper modules for parsing and encoding.

Forbidden in `frontend/src/**/*.vue`:

- `fetch(`, `axios`, `XMLHttpRequest`, or `EventSource`;
- `/api/` path literals;
- reads of `detail`, `error.code`, or `error.details` from a response.

Screens and components may only:

- call methods on the exported `api` object;
- display `apiErrorMessage(error)` for failures;
- assign `api.imageUrl`/`api.videoUrl` results to media elements.

## 6. Drift and Coverage Checks

| Check | Fails when |
| --- | --- |
| `npm run check:api` | Generated TypeScript does not match the contract JSON. |
| `npm run test:api` route coverage | A generated route lacks exactly one operation, or an operation has no route. |
| `npm run test:api` facade coverage | The public facade is missing an operation or exposes an extra one. |
| `npm run test:api` transport checks | A method/path/body call differs from the generated route. |
| `npm run test:api` error checks | Envelope, legacy, malformed, unknown-code, or transport fallback behavior differs. |
| `npm run test:api` query checks | Omission, encoding, `0`, or `false` handling differs. |
| `npm run test:api` boundary scan | A `.vue` file bypasses the client or parses an envelope. |

The production build (`vue-tsc -b && vite build`) must also pass. Existing
Python tests, lint, format, and strict typing must remain green.

## 7. Compatibility Guarantees

- Existing screen imports and success behavior remain unchanged.
- Existing standardized error messages remain the text users see.
- No backend request or response shape changes.
- No new runtime dependency, authentication, telemetry, caching, retry, or
  offline behavior is introduced.
- Generated frontend assets are rebuilt before packaging, as today.
- The client remains same-origin and local-only.

## 8. Adding or Changing a Route

An approved backend contract change follows this sequence:

1. Update the authoritative contract JSON and its backend tests.
2. Run `npm run generate:api`.
3. Add or update the friendly operation mapping and the hand-written request
   type if the route needs one.
4. Add or update facade methods and tests.
5. Run `npm run check:api`, `npm run test:api`, and `npm run build`.
6. Update `CHANGELOG.md` and maintainer documentation when behavior or the
   workflow changes.

No screen should need a new endpoint literal or error parser.
