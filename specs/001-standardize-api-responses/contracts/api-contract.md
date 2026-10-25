# API Contract Inventory

**Feature**: `001-standardize-api-responses`
**Date**: 2026-10-29
**Machine-readable source**: [api-contract.json](./api-contract.json)
**Coverage**: 12 routes under `/api`

This inventory is the human-readable audit of every route the FastAPI adapter
exposes. The JSON file is the source of truth used by the contract tests; this
document explains the same contract for maintainers and reviewers.

The static single-page app served from `/` is not part of the API contract. The
web server remains local-only and binds to `127.0.0.1`.

## Error Envelope

Every failed `/api/*` request returns a JSON object with exactly two top-level
fields:

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

| Field | Type | Notes |
|-------|------|-------|
| `error.code` | string | Stable category from the table below |
| `error.message` | string | Non-empty human-readable cause |
| `error.details` | object or `null` | Structured context; validation only today |
| `detail` | string | Legacy field; always equals `error.message` |

Invariants enforced by `tests/test_api_contract.py`:

- `detail` is a string and equals `error.message`.
- `error` has exactly `code`, `message`, and `details`.
- The HTTP status matches the code's documented status.
- The content type is `application/json`, including framework-generated 404,
  405, 422, and 500 responses.
- No HTML or plain-text body is returned from an `/api/*` failure.

### Validation Errors

Validation failures keep field-level detail under `details.issues`:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed: query.path: Field required",
    "details": {
      "issues": [
        {
          "location": ["query", "path"],
          "message": "Field required",
          "type": "missing"
        }
      ]
    }
  },
  "detail": "Request validation failed: query.path: Field required"
}
```

Raw request input is not echoed. The top-level message summarizes the first
issue; all issues remain in `details.issues`.

## Error Code Vocabulary

| Code | Status | Meaning |
|------|--------|---------|
| `invalid_request` | 400 | Invalid combination of parameters, unsupported archive operation, or malformed byte range |
| `forbidden` | 403 | Target exists but cannot be accessed |
| `not_found` | 404 | Unknown route, missing directory/entry/image/video, or missing archive member |
| `method_not_allowed` | 405 | Route does not support the method |
| `payload_too_large` | 413 | Image exceeds the preview size limit |
| `unsupported_media_type` | 415 | Unsupported or undecodable image/video |
| `range_not_satisfiable` | 416 | Video byte range starts beyond the file |
| `validation_error` | 422 | Query or body schema validation failed |
| `internal_error` | 500 | I/O, log, launch, or unexpected server failure |

Every route also supports `method_not_allowed` and `internal_error`. Routes
with required query parameters or a body also support `validation_error`.
Unknown paths return the global `not_found` case.

## Shared Success Objects

These objects are referenced by more than one route. Field names, types, and
nullability are frozen by the contract tests.

### BrowserEntry

| Field | Type | Nullable |
|-------|------|----------|
| `name` | string | no |
| `is_dir` | boolean | no |

### HistoryEntry

| Field | Type | Nullable |
|-------|------|----------|
| `timestamp` | string | yes |
| `item` | string | no |
| `display` | string | no |

### PreviewImage

| Field | Type | Nullable |
|-------|------|----------|
| `index` | integer | yes |
| `name` | string | no |
| `media_type` | string | no |
| `size` | integer | no |

`index` is the member position inside an archive; it is `null` for a
standalone image.

### PreviewVideo

| Field | Type | Nullable |
|-------|------|----------|
| `name` | string | no |
| `media_type` | string | no |
| `size` | integer | no |

### PreviewModel

| Field | Type | Nullable | Values |
|-------|------|----------|--------|
| `kind` | string enum | no | `text`, `directory`, `binary`, `empty`, `gone`, `unreadable`, `archive`, `image`, `video` |
| `text` | string | no | — |
| `truncated` | boolean | no | — |
| `entry_count` | integer | yes | — |
| `size` | integer | yes | — |
| `images` | PreviewImage[] | no | — |
| `image_total` | integer | no | — |
| `video` | PreviewVideo | yes | — |

## Route Summary

| Method | Path | Purpose | Success |
|--------|------|---------|---------|
| GET | `/api/defaults` | Initial path and log file | 200 JSON |
| GET | `/api/browse` | Directory listing | 200 JSON |
| GET | `/api/state` | Remaining choices and history | 200 JSON |
| POST | `/api/pick` | Pick and optionally log an entry | 200 JSON |
| GET | `/api/preview` | Structured entry preview | 200 JSON |
| GET | `/api/image` | Image bytes or WebP rendition | 200 binary |
| GET | `/api/video` | Video stream with ranges | 200/206 binary |
| POST | `/api/open` | Launch with the OS default program | 200 JSON |
| POST | `/api/history/archive` | Rotate the log to a backup | 200 JSON |
| DELETE | `/api/history` | Delete the log | 200 JSON |
| DELETE | `/api/history/item` | Remove one item's history | 200 JSON |
| POST | `/api/history/remove` | Remove selected items in one rewrite | 200 JSON |

---

## GET /api/defaults

**Purpose**: Return the initial path and log file supplied when the server
started.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `path` | string | no |
| `log_file` | string | no |

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `method_not_allowed` | 405 | Method other than GET |
| `internal_error` | 500 | Unexpected exception |

---

## GET /api/browse

**Purpose**: List one directory's children with directories first.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `path` | string | no |
| `parent` | string | yes |
| `entries` | BrowserEntry[] | no |

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing or malformed `path` query parameter |
| `not_found` | 404 | Path does not exist or is not a directory (`"Not a directory"`) |
| `forbidden` | 403 | Directory exists but cannot be listed |
| `method_not_allowed` | 405 | Method other than GET |
| `internal_error` | 500 | Unexpected exception |

---

## GET /api/state

**Purpose**: Return remaining candidates and recent history for a target and
filter set.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `valid_path` | boolean | no |
| `path` | string | no |
| `log_file` | string | no |
| `remaining` | string[] | no |
| `remaining_total` | integer | no |
| `history` | HistoryEntry[] | no |
| `history_total` | integer | no |

**Domain outcomes (still 200)**

- Target not a directory: `valid_path: false`, empty remaining/history, totals
  zero.
- Missing history file: empty history, total zero.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing `path` or malformed boolean filter |
| `invalid_request` | 400 | `files_only` and `dirs_only` are both true |
| `method_not_allowed` | 405 | Method other than GET |
| `internal_error` | 500 | Unexpected exception |

---

## POST /api/pick

**Purpose**: Pick one unselected entry and optionally record it in the history
log.

**Success**: `200 application/json`

| Field | Type | Nullable | Values |
|-------|------|----------|--------|
| `status` | string enum | no | `picked`, `empty`, `exhausted`, `invalid_path` |
| `log_file` | string | no | — |
| `item` | string | yes | — |
| `logged` | boolean | no | — |
| `preview` | PreviewModel | yes | — |

**Domain outcomes (still 200)**

- Invalid target: `status: "invalid_path"`, no item, not logged.
- No candidates: `status: "empty"`.
- All eligible entries logged: `status: "exhausted"`.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing/malformed body or wrong field types |
| `invalid_request` | 400 | `files_only` and `dirs_only` are both true |
| `internal_error` | 500 | Log write failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than POST |

---

## GET /api/preview

**Purpose**: Return a structured, bounded preview for an entry path.

**Success**: `200 application/json` with a [PreviewModel](#previewmodel).

**Domain outcomes (still 200)**

- Missing entry: `kind: "gone"`.
- Unreadable entry: `kind: "unreadable"`.
- Empty file: `kind: "empty"`.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing or malformed `path` query parameter |
| `method_not_allowed` | 405 | Method other than GET |
| `internal_error` | 500 | Unexpected exception |

---

## GET /api/image

**Purpose**: Serve original image bytes or a WebP rendition, including archive
members by index.

**Success**: `200` binary

- Content type: `image/png`, `image/jpeg`, `image/gif`, `image/webp`, or
  `image/bmp` for original bytes.
- `variant=thumb` and `variant=preview` return `image/webp`.
- Headers: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- Archive members are read by index; nothing is extracted to disk.
- Full-size reads are capped at 20 MB (`PREVIEW_MAX_IMAGE_BYTES`).

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing `path`, non-integer `index`, or invalid `variant` |
| `not_found` | 404 | Image file missing or disappears before reading |
| `not_found` | 404 | Archive index outside the entry list |
| `invalid_request` | 400 | Not a zip archive, corrupt archive, or encrypted member |
| `payload_too_large` | 413 | Image exceeds 20 MB |
| `unsupported_media_type` | 415 | Unsupported image extension/bytes or undecodable thumbnail |
| `internal_error` | 500 | Image/archive read failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than GET |

---

## GET /api/video

**Purpose**: Stream a standalone video with byte-range support.

**Success**: `200` or `206` binary

- `200`: full file.
- `206`: a single, suffix, or multipart byte range.
- Content types: `video/mp4` (`.mp4`, `.m4v`), `video/webm` (`.webm`),
  `video/ogg` (`.ogv`), `video/quicktime` (`.mov`), `video/x-matroska`
  (`.mkv`); a multi-range response uses `multipart/byteranges`.
- Headers: `Accept-Ranges: bytes`, `Cache-Control: no-store`,
  `X-Content-Type-Options: nosniff`.
- The leading bytes must match the container extension.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing or malformed `path` query parameter |
| `not_found` | 404 | Video file missing |
| `unsupported_media_type` | 415 | Unsupported extension or content mismatch |
| `invalid_request` | 400 | Malformed `Range` header |
| `range_not_satisfiable` | 416 | Range starts beyond the file; includes `Content-Range: bytes */<size>` |
| `internal_error` | 500 | Video read failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than GET |

---

## POST /api/open

**Purpose**: Open an entry with the operating system's default program.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `opened` | string | no |

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing/malformed body or non-string `path` |
| `not_found` | 404 | Entry does not exist (`"Entry is gone"`) |
| `internal_error` | 500 | Launch failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than POST |

---

## POST /api/history/archive

**Purpose**: Rotate the history log to a timestamped backup.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `backup` | string | yes |

**Domain outcome (still 200)**: No log to archive returns `backup: null`.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing or malformed `path` query parameter |
| `internal_error` | 500 | Archive failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than POST |

---

## DELETE /api/history

**Purpose**: Delete the history log.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `removed` | boolean | no |

**Domain outcome (still 200)**: No log to clear returns `removed: false`.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing or malformed `path` query parameter |
| `internal_error` | 500 | Reset failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than DELETE |

---

## DELETE /api/history/item

**Purpose**: Remove every history entry for one item.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `item` | string | no |
| `removed` | integer | no |

**Domain outcome (still 200)**: Unknown item returns `removed: 0` and leaves
the log bytes unchanged.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing/malformed `path` or `item` query parameter |
| `internal_error` | 500 | Remove failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than DELETE |

---

## POST /api/history/remove

**Purpose**: Remove every history entry for a batch of items in one rewrite.

**Success**: `200 application/json`

| Field | Type | Nullable |
|-------|------|----------|
| `log_file` | string | no |
| `items` | string[] | no |
| `removed` | integer | no |

**Domain outcome (still 200)**: No matching items returns `removed: 0` and
leaves the log bytes unchanged.

**Errors**

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing/malformed body, missing `path`, or empty `items` |
| `internal_error` | 500 | Remove failure or unexpected exception |
| `method_not_allowed` | 405 | Method other than POST |

---

## Success Conventions

- Field names are snake_case and meanings are stable.
- Optional values are present as `null`, not omitted.
- Capped lists are paired with an uncapped count:
  `remaining`/`remaining_total`, `history`/`history_total`, and
  `images`/`image_total`.
- `remaining` is sorted; `history` preserves log order; browser entries are
  directories first, then case-insensitive name order.
- Domain outcomes listed above remain successful responses and must not be
  converted into errors.
- No success payload is wrapped in a new envelope.

## Updating the Contract

When adding or changing a route:

1. Update the FastAPI route and its Pydantic model.
2. Update `api-contract.json` (route, success schema, or error case).
3. Update this markdown inventory.
4. Add or update a live error case in `tests/test_api_contract.py` if the
   failure behavior changed.
5. Run `uv run pytest tests/test_api_contract.py -v` plus the full quality
   gate.

The contract tests fail when a route is missing from either side, when a success
field is removed/renamed/retyped, when nullability or an enum changes, when an
error code is undocumented, or when the envelope shape drifts.
