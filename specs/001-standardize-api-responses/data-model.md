# Phase 1 Data Model: Standardized API Responses and Error Schemas

**Feature**: `001-standardize-api-responses`
**Date**: 2026-10-29

This feature adds no persisted data. The entities below describe the HTTP
payloads and the documentation artifacts that define them. All existing
success models and the JSONL history format remain unchanged.

## Entity: ErrorResponse

The complete JSON body returned for every failed `/api/*` request.

| Field | Type | Required | Nullable | Notes |
|-------|------|----------|----------|-------|
| `error` | ErrorBody | yes | no | Structured error object |
| `detail` | string | yes | no | Legacy human-readable message; equals `error.message` |

Invariants:

- `detail` is non-empty and byte-for-byte equal to `error.message`.
- The body contains exactly `error` and `detail` at the top level.
- The HTTP status code equals `ERROR_STATUS[error.code]`.
- The response `Content-Type` is `application/json`.
- No success field is ever added to an error body.

## Entity: ErrorBody

| Field | Type | Required | Nullable | Notes |
|-------|------|----------|----------|-------|
| `code` | ErrorCode | yes | no | Stable category from the table below |
| `message` | string | yes | no | Human-readable cause; same string as `detail` |
| `details` | object \| null | yes (key present) | yes (value `null`) | Structured context; currently only validation uses it |

Invariants:

- `code` is one of the documented `ErrorCode` values.
- `message` is non-empty.
- `details` is `null` for all non-validation errors.
- For `validation_error`, `details` has the ValidationDetails shape.
- Unknown fields are not part of the contract; tests reject shape drift.

## Entity: ErrorCode

A closed vocabulary aligned one-to-one with HTTP status categories.

| Code | Status | Applies to |
|------|--------|-----------|
| `invalid_request` | 400 | Conflicting filters (`files_only` + `dirs_only`), non-zip archive when an index was requested, corrupt/encrypted archive member, malformed video `Range` |
| `forbidden` | 403 | A directory exists but cannot be listed |
| `not_found` | 404 | Unknown `/api/*` path, browse target missing/not a directory, missing open target, missing image/video file, archive index out of range |
| `method_not_allowed` | 405 | Any route called with an unsupported method |
| `payload_too_large` | 413 | Image exceeds `PREVIEW_MAX_IMAGE_BYTES` (20 MB) |
| `unsupported_media_type` | 415 | Unsupported image/video extension, content mismatch, or undecodable thumbnail |
| `range_not_satisfiable` | 416 | A syntactically valid video byte range starts outside the file |
| `validation_error` | 422 | Missing/invalid query parameter or request body |
| `internal_error` | 500 | Image/archive/video read failure, log write/archive/reset failure, history remove failure, launch failure, unexpected exception |

Adding a code is additive and requires a contract update. Removing or renaming a
code is a breaking contract change.

## Entity: ValidationDetails

| Field | Type | Required | Nullable | Notes |
|-------|------|----------|----------|-------|
| `issues` | ValidationIssue[] | yes | no | One entry per framework validation error |

## Entity: ValidationIssue

| Field | Type | Required | Nullable | Notes |
|-------|------|----------|----------|-------|
| `location` | string[] | yes | no | Pydantic `loc` converted to strings, e.g. `["query", "path"]` |
| `message` | string | yes | no | Pydantic `msg` |
| `type` | string | yes | no | Pydantic error type, e.g. `missing`, `literal_error` |

Raw `input` and `ctx` values are deliberately excluded. `details` for a
validation error is therefore exactly `{"issues": [...]}`.

## Entity: RouteContract

One entry in `contracts/api-contract.json`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `method` | string | yes | Uppercase HTTP method |
| `path` | string | yes | Exact `/api/...` path |
| `purpose` | string | yes | Human-readable responsibility |
| `success.statuses` | integer[] | yes | All success statuses (200; video also 206) |
| `success.contentType` | string or string[] | yes | Exact MIME type, prefix (`image/*`), or accepted list |
| `success.body` | `"json"` or `"binary"` | yes | Selects schema comparison or binary checks |
| `success.schema` | SuccessSchema | JSON only | Top-level field contract |
| `success.headers` | object | no | Required success headers such as `Accept-Ranges: bytes` |
| `errors` | ErrorCase[] | yes | Every documented failure for the route |

## Entity: ErrorCase

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `code` | ErrorCode | yes | Must exist in the error vocabulary |
| `status` | integer | yes | Must equal `ERROR_STATUS[code]` |
| `when` | string | yes | The condition that produces it |

Every route lists at least `method_not_allowed` and `internal_error`. Routes
with required query parameters or bodies also list `validation_error`.
`not_found` for an unknown path is a global case, not a per-route case.

## Entity: SuccessSchema

A small, JSON-only schema used for drift comparison:

| Field | Type | Notes |
|-------|------|-------|
| `ref` | string | Optional reference to a shared schema under top-level `schemas` |
| `type` | `"object"` / `"array"` / `"string"` / `"integer"` / `"boolean"` / `"number"` | JSON type |
| `nullable` | boolean | Whether `null` is accepted |
| `enum` | array | Optional closed value set |
| `fields` | map<string, SuccessSchema> | Object properties |
| `items` | SuccessSchema | Array element schema |

A `ref` resolves to the named shared schema; `nullable` on the referencing
object is applied after resolution.

This is intentionally narrower than JSON Schema. It mirrors the subset of
FastAPI/Pydantic output the tests compare and keeps the inventory readable.

## Existing Success Models (Unchanged)

All fields below are always serialized by their Pydantic models. No field is
removed, renamed, or retyped.

### DefaultsResponse

| Field | Type | Nullable |
|-------|------|----------|
| `path` | string | no |
| `log_file` | string | no |

### BrowseResponse

| Field | Type | Nullable |
|-------|------|----------|
| `path` | string | no |
| `parent` | string | yes |
| `entries` | BrowserEntry[] | no |

BrowserEntry: `name` string, `is_dir` boolean.

### StateResponse

| Field | Type | Nullable |
|-------|------|----------|
| `valid_path` | boolean | no |
| `path` | string | no |
| `log_file` | string | no |
| `remaining` | string[] | no |
| `remaining_total` | integer | no |
| `history` | HistoryEntry[] | no |
| `history_total` | integer | no |

HistoryEntry: `timestamp` string|null, `item` string, `display` string.

### PickResponse

| Field | Type | Nullable |
|-------|------|----------|
| `status` | `picked` \| `empty` \| `exhausted` \| `invalid_path` | no |
| `log_file` | string | no |
| `item` | string | yes |
| `logged` | boolean | no |
| `preview` | PreviewModel | yes |

### PreviewModel

| Field | Type | Nullable |
|-------|------|----------|
| `kind` | `text` \| `directory` \| `binary` \| `empty` \| `gone` \| `unreadable` \| `archive` \| `image` \| `video` | no |
| `text` | string | no |
| `truncated` | boolean | no |
| `entry_count` | integer | yes |
| `size` | integer | yes |
| `images` | PreviewImage[] | no |
| `image_total` | integer | no |
| `video` | PreviewVideo | yes |

PreviewImage: `index` integer|null, `name` string, `media_type` string,
`size` integer.

PreviewVideo: `name` string, `media_type` string, `size` integer.

`kind` is narrowed from `str` to the existing `PreviewKind` Literal; the set of
emitted values does not change.

### OpenResponse

| Field | Type | Nullable |
|-------|------|----------|
| `opened` | string | no |

### ArchiveResponse

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `backup` | string | yes |

### ClearResponse

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `removed` | boolean | no |

### RemoveHistoryItemResponse

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `item` | string | no |
| `removed` | integer | no |

### RemoveHistoryItemsResponse

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `items` | string[] | no |
| `removed` | integer | no |

## Domain Outcomes (Not Errors)

These are intentional successful responses and remain 200:

| Route | Outcome | Shape |
|-------|---------|-------|
| `GET /api/state` | target is not a directory | `valid_path: false`, empty remaining/history, totals 0 |
| `GET /api/state` | missing history file | empty history, totals 0 |
| `POST /api/pick` | target is not a directory | `status: "invalid_path"`, no item, not logged |
| `POST /api/pick` | directory has no candidates | `status: "empty"` |
| `POST /api/pick` | all eligible entries logged | `status: "exhausted"` |
| `POST /api/history/archive` | no log to archive | `backup: null` |
| `DELETE /api/history` | no log to clear | `removed: false` |
| `DELETE /api/history/item` | item absent from log | `removed: 0` |
| `POST /api/history/remove` | no selected items present | `removed: 0` |
| `GET /api/preview` | entry gone/unreadable/empty | `kind: "gone"` / `"unreadable"` / `"empty"` |

## State Transitions

A failed request has one terminal state: the JSON error response. It must not
transition the target directory, the history log, or the archive state.

The only routes that write are unchanged:

- `POST /api/pick` appends one log entry unless `dry_run` is true.
- `POST /api/history/archive` rotates the log to a timestamped backup.
- `DELETE /api/history` deletes the log.
- `DELETE /api/history/item` and `POST /api/history/remove` rewrite the log
  atomically through `remove_log_item` / `remove_log_items`.

Failure while formatting a response happens after those operations and must not
trigger a second write. Contract tests cover failed requests that leave the log
bytes unchanged.

## Validation Rules

1. `detail == error.message`, both non-empty.
2. `error.code` is in the documented vocabulary and its mapped status equals
   the HTTP status.
3. `error.details` is `null` except for `validation_error`, which carries
   `{"issues": [...]}` with non-empty `location`, `message`, and `type`.
4. JSON errors always use `application/json`; no HTML or plain-text error body
   escapes an `/api/*` route.
5. Every route in the FastAPI app appears exactly once in the contract, with
   the same method and path.
6. Every JSON success schema matches the OpenAPI schema exactly for field
   names, types, nullability, enums, and nested structures.
7. Binary success responses keep their current bytes, MIME types, headers, and
   range statuses; binary failures use the error envelope.
8. No success model gains, loses, or retypes a field; no route path, method, or
   request model changes.
