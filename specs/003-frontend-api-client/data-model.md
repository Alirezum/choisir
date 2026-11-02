# Data Model: Frontend API Client Layer

**Feature**: `specs/003-frontend-api-client`
**Date**: 2026-11-01

## Overview

This feature introduces no persistence and no backend data change. The model
below describes the frontend contract surface, the one typed failure result,
and the request lifecycle that every screen uses. The authoritative interface
data remains
`specs/001-standardize-api-responses/contracts/api-contract.json`.

## Generated Contract

### `GeneratedContract`

The checked-in `frontend/src/api-contract.generated.ts` produced from the JSON
contract.

| Field | Type | Notes |
| --- | --- | --- |
| `routes` | `Record<RouteKey, RouteContract>` | One entry per documented route, keyed as `"<METHOD> <path>"`. |
| `errorCodes` | `readonly KnownApiErrorCode[]` | Every documented stable code. |
| `errorStatus` | `Record<KnownApiErrorCode, number>` | Documented HTTP status for each known code. |
| `envelope` | `ApiErrorEnvelope` | The standardized failure payload type. |
| response interfaces | TypeScript interfaces | Shared schemas and one response type per JSON route. |

Rules:

- Generated only from the authoritative JSON contract; never edited by hand.
- Deterministic output order and content.
- Regeneration is required after an approved contract change.
- The generated file contains no runtime dependency and no backend import.

### `RouteKey` and `RouteContract`

| Field | Type | Notes |
| --- | --- | --- |
| `key` | `"<METHOD> <path>"` | Identity used by the operation map and tests. |
| `method` | `"GET" \| "POST" \| "DELETE"` | The documented HTTP method. |
| `path` | `string` | The documented `/api/...` path. |

Rules:

- Every route has one key and one method/path pair.
- Two routes with the same path but different methods remain distinct.
- A route key is unique across the contract.

## Client Operations

### `ClientOperation`

One friendly method on the public client facade.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | `ApiOperation` | Method name exposed on `api`. |
| `route` | `RouteKey` | Generated route used for method, path, and coverage checks. |
| `input` | Query parameters or JSON body | Hand-written request type where the contract does not describe requests. |
| `result` | Generated response type or media address | The typed success result. |

Operation map:

| Client method | Route key | Input | Result |
| --- | --- | --- | --- |
| `defaults` | `GET /api/defaults` | none | `DefaultsResponse` |
| `browse` | `GET /api/browse` | `path` query | `BrowseResponse` |
| `state` | `GET /api/state` | `StateQuery` | `StateResponse` |
| `pick` | `POST /api/pick` | `PickRequest` body | `PickResponse` |
| `preview` | `GET /api/preview` | `path` query | `PreviewModel` |
| `imageUrl` | `GET /api/image` | `path`, `index`, `variant` query | media address |
| `videoUrl` | `GET /api/video` | `path` query | media address |
| `open` | `POST /api/open` | `path` body | `OpenResponse` |
| `archive` | `POST /api/history/archive` | `path`, `log_file` query | `ArchiveResponse` |
| `clear` | `DELETE /api/history` | `path`, `log_file` query | `ClearResponse` |
| `removeHistoryItem` | `DELETE /api/history/item` | `path`, `item`, `log_file` query | `RemoveHistoryItemResponse` |
| `removeHistoryItems` | `POST /api/history/remove` | `RemoveHistoryItemsRequest` body | `RemoveHistoryItemsResponse` |

Rules:

- Every generated route is mapped exactly once.
- Every operation name exists on the public facade.
- The facade has no extra operation outside the map.
- Requests derive their method and path from the generated route, never from a
  literal in a screen.

### Request types

These remain hand-written because the frozen contract documents success and
error shapes, not request bodies:

| Type | Fields | Rules |
| --- | --- | --- |
| `StateQuery` | `path`, optional `log_file`, `include_hidden`, `files_only`, `dirs_only` | Filters are booleans; absence keeps backend defaults. |
| `PickRequest` | `path`, optional `log_file`, `seed`, `dry_run`, `include_hidden`, `files_only`, `dirs_only` | `seed` and filters match the backend Pydantic model. |
| `RemoveHistoryItemsRequest` | `path`, optional `log_file`, `items` | `items` must be non-empty at the backend; the client passes the selected list unchanged. |

## Error Model

### `ApiError`

The single typed failure result.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | `"ApiError"` | Distinguishes it from generic errors. |
| `status` | `number` | HTTP status, or `0` for transport failure. |
| `code` | `string \| null` | Known or future backend code; `null` when no envelope code exists. |
| `message` | `string` | Backend message, legacy `detail`, or readable fallback. |
| `details` | `unknown` | Backend structured details, or `null`. |

Rules:

- Extends the built-in `Error` so existing `instanceof Error` display paths
  continue to work.
- Never exposes a raw JSON parse exception to a screen.
- Unknown future codes are preserved rather than rejected.
- The display helper returns `message`; screens do not inspect `code` or
  `details`.

### `ErrorCodeCatalog`

| Field | Type | Notes |
| --- | --- | --- |
| `code` | `KnownApiErrorCode` | One of the nine documented codes. |
| `status` | `number` | HTTP status frozen by the contract. |

Known codes:

`invalid_request` (400), `forbidden` (403), `not_found` (404),
`method_not_allowed` (405), `payload_too_large` (413),
`unsupported_media_type` (415), `range_not_satisfiable` (416),
`validation_error` (422), `internal_error` (500).

Rules:

- The generated catalog must match the contract exactly.
- A future code may appear at runtime; it remains representable as a string and
  still produces an `ApiError`.
- Status mapping is used by tests, not by screens.

### `ApiErrorEnvelope`

The standardized non-success payload:

```text
{
  error: {
    code: string,
    message: string,
    details: unknown | null
  },
  detail: string
}
```

Parsing precedence:

1. Validate the nested `error` object by shape.
2. Use `error.code`, `error.message`, and `error.details`.
3. If no valid envelope but a string `detail` exists, use it as the message.
4. Otherwise use `"<status> <statusText>"`.
5. A missing message falls back to the status text.
6. A malformed or empty body never escapes as a parser exception.

## Query and Media Model

### `QueryParameters`

| Value | Encoding |
| --- | --- |
| `undefined`, `null`, `false`, `""` | Omitted |
| `0` | Included as `"0"` |
| `true` | Included as `"true"` |
| number | Included as its decimal string |
| string | URL-encoded with `URLSearchParams` |

Rules:

- Keys preserve the backend's snake_case names.
- Ordering is stable and irrelevant to the backend.
- A blank log override is omitted.
- An archive image index of `0` is included.
- Media addresses use the same encoder as JSON requests.

### `MediaAddress`

A same-origin `/api/image` or `/api/video` address built by the client.

| Field | Type | Notes |
| --- | --- | --- |
| `path` | `string` | Generated route path. |
| `query` | `string` | Empty or `?` plus encoded parameters. |

Rules:

- The client never fetches or buffers binary payloads.
- Components assign the address to the media element.
- Existing media load/error handling stays in the component.

## Request Lifecycle

```text
Screen action
    |
    v
Client operation (route from generated contract)
    |
    +--> transport rejection -------------------------> ApiError(status=0)
    |
    +--> non-2xx response --> parse envelope ---------> ApiError(status, code, message, details)
    |                         | no envelope/detail ---> status fallback
    |
    +--> 2xx response --> parse JSON -----------------> typed success result
                          | invalid JSON -------------> ApiError(status, invalid response)
```

State rules:

- The client performs one fetch per operation and never retries.
- A non-success response is never returned as a typed success result.
- A successful domain outcome (`invalid_path`, `empty`, `exhausted`, missing
  history, no-op archive/clear) remains a success result.
- Screens render the typed success or the shared error message; they do not
  add route-specific branches.
- Overlapping requests keep their current screen behavior; no queue,
  cancellation, deduplication, or retry state is introduced.

## Validation and Coverage Rules

1. Every contract route maps to exactly one client operation.
2. Every client operation maps to an existing generated route.
3. Every known error code is present in the generated catalog.
4. No `.vue` file contains `fetch`, `axios`, `XMLHttpRequest`, `EventSource`,
   an `/api/` address literal, or direct envelope parsing.
5. The generated module is byte-for-byte current with the contract JSON.
6. Response interfaces preserve field names, nullability, enums, and array
   element types.
7. No backend file, route, schema, status, message, or history behavior changes.
