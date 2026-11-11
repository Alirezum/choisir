# Contract: Web Path-Memory Routes and Fields

**Feature**: 006-remember-path | **Applies to**: `choosier/web.py`,
`specs/001-standardize-api-responses/contracts/api-contract.json`,
`frontend/src/api-contract.generated.ts`

All changes are additive and backward-compatible. The existing error envelope
(`{"error": {"code", "message", "details"}, "detail"}`) and status mapping are
unchanged. Memory failures are non-fatal and never replace a successful pick or
listing with an HTTP error.

## Schema Additions

```text
DefaultsResponse (extended)
  path: string
  log_file: string
  path_warning: string | null      # NEW

PathMemoryResponse (new)
  recent: string[]                 # valid, newest first, 0..10
  warning: string | null

ClearPathMemoryResponse (new)
  cleared: boolean

RemovePathMemoryResponse (new)
  path: string                     # canonicalized request path
  removed: boolean

PickResponse (extended)
  status: "picked" | "empty" | "exhausted" | "invalid_path" |
          "filtered_empty" | "filtered_exhausted"
  log_file: string
  item: string | null
  logged: boolean
  preview: Preview | null
  path_memory_notice: string | null   # NEW
```

`path_warning`, `warning`, and `path_memory_notice` are null on clean
operation. They carry short, local, non-modal messages only.

## GET /api/defaults (extended)

Returns the startup defaults. When the server was started without an explicit
path, `path` is the first valid remembered folder, or `str(Path.cwd())` when
none is valid. When started with an explicit path, `path` is that value
unchanged and memory is not consulted. `path_warning` explains pruning,
fallback, or an unreadable record.

```json
{
  "path": "/home/ana/projects/alpha",
  "log_file": "",
  "path_warning": "Skipped 1 unavailable remembered folder."
}
```

Errors: `405 method_not_allowed`, `500 internal_error` (unchanged).

## GET /api/paths (new)

Returns the current recent list. The route validates and prunes unavailable
entries before responding, so callers never receive a dead row.

```json
{
  "recent": [
    "/home/ana/projects/alpha",
    "/home/ana/projects/beta"
  ],
  "warning": null
}
```

- **200**: always, including an empty list and an unreadable/corrupt record
  (with a warning).
- **405**: method other than `GET`.
- **500**: only an unexpected exception outside memory handling.

## DELETE /api/paths (new)

Clears all remembered folders. Does not change the active path of the running
session, history, filters, choices, or target content.

```json
{ "cleared": true }
```

- **200**: `cleared` is true when entries were removed, false when the list was
  already empty or the store was empty/unreadable.
- **405**: method other than `DELETE`.
- **500**: only an unexpected exception.

## DELETE /api/paths/item?path=<value> (new)

Removes one remembered folder. The query parameter is required, non-empty, and
must be an absolute path (after `~` expansion). Comparison uses the same
canonical identity as recording.

```json
{ "path": "/home/ana/projects/beta", "removed": true }
```

- **200**: `removed` is true when an entry was deleted, false when it was not
  present. Removing an absent path is not an error.
- **400 invalid_request**: `path` is empty, non-absolute, or cannot be
  canonicalized.
- **422 validation_error**: the required `path` query parameter is missing.
- **405**: method other than `DELETE`.
- **500**: only an unexpected exception.

Removing or clearing never changes the running session's active target. The
frontend refreshes only the recent list.

## POST /api/pick (extended)

Unchanged outcome semantics and status values. On `status == "picked"`
(including `dry_run: true`), the server records the canonical target folder and
returns `path_memory_notice: null` on success. If recording fails, the response
still has `status == "picked"` and the normal item/preview fields, with
`path_memory_notice` describing the non-fatal failure.

```json
{
  "status": "picked",
  "log_file": "/home/ana/projects/alpha/.choosier.jsonl",
  "item": "notes.txt",
  "logged": true,
  "preview": null,
  "path_memory_notice": null
}
```

Non-`picked` outcomes do not record and return `path_memory_notice: null`.
Errors are unchanged.

## Authoritative Contract Updates

`specs/001-standardize-api-responses/contracts/api-contract.json`:

1. Add `path_warning` (string, nullable) to the `GET /api/defaults` schema.
2. Add `path_memory_notice` (string, nullable) to the `POST /api/pick` schema.
3. Add three routes: `GET /api/paths`, `DELETE /api/paths`,
   `DELETE /api/paths/item`.
4. Route count becomes 16; update the count assertion in
   `tests/test_api_contract.py`.
5. Add any shared schemas needed for parity tests; keep the existing envelope
   and error taxonomy untouched.

Frontend generation:

- `frontend/scripts/generate-api-contract.mjs` response-type map gains:
  - `GET /api/paths` → `PathMemoryResponse`
  - `DELETE /api/paths` → `ClearPathMemoryResponse`
  - `DELETE /api/paths/item` → `RemovePathMemoryResponse`
- `frontend/src/api-operations.ts` gains friendly names:
  `paths`, `clearPaths`, `removePath`.
- `frontend/src/api.ts` gains facade methods:
  - `paths()` → `GET /api/paths`
  - `clearPaths()` → `DELETE /api/paths`
  - `removePath(path)` → `DELETE /api/paths/item?path=...`
- `npm run generate:api` regenerates `frontend/src/api-contract.generated.ts`;
  drift tests must pass.

## Compatibility Notes

- Existing clients that ignore unknown fields continue to work.
- No existing route, status code, error code, or CLI behavior changes.
- The one-shot CLI never calls these routes; `--web` without a path changes from
  eager cwd substitution to remembered-folder resolution, with cwd as the
  fallback.
