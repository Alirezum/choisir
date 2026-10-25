# Phase 0 Research: Standardize API Responses and Error Schemas

**Feature**: `001-standardize-api-responses`
**Date**: 2026-10-29
**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Scope of the Audit

The web adapter exposes 12 routes under `/api`:

| Method | Path |
|--------|------|
| GET | `/api/defaults` |
| GET | `/api/browse` |
| GET | `/api/state` |
| POST | `/api/pick` |
| GET | `/api/preview` |
| GET | `/api/image` |
| GET | `/api/video` |
| POST | `/api/open` |
| POST | `/api/history/archive` |
| DELETE | `/api/history` |
| DELETE | `/api/history/item` |
| POST | `/api/history/remove` |

The Vue client reads `detail` from JSON error bodies only when it is a string
(`frontend/src/api.ts`). Every other consumed field belongs to a success
response. Binary URLs are consumed directly by `<img>` and `<video>` elements,
not through the shared `request()` helper.

Existing framework-generated failures are:

- Unknown path: `404 {"detail": "Not Found"}`
- Wrong method: `405 {"detail": "Method Not Allowed"}`
- Request validation: `422 {"detail": [ ... ]}`
- Unhandled exception: plain-text `500 Internal Server Error`
- Invalid video `Range`: plain-text `400` or `416` from `FileResponse`

Existing route failures use `HTTPException` with a string `detail` and status
codes 400, 403, 404, 413, 415, or 500.

## Decision 1: One namespaced error envelope with a legacy `detail`

**Decision**: Every JSON error uses this exact top-level shape:

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

Invariants:

- `detail` is always a non-empty string.
- `detail` equals `error.message`.
- `error` contains exactly `code`, `message`, and `details`.
- `error.details` is `null` unless the failure has structured context.
- The HTTP status is the status mapped to `error.code`.
- The response content type is `application/json`, including 404, 405, 422,
  and 500 responses generated outside route bodies.

**Rationale**: The namespaced object separates new structured data from the
legacy string the frontend already reads. Keeping `detail` as a string means
`frontend/src/api.ts` needs no change and every current error toast continues to
work. Equating `detail` with `message` avoids two divergent human-readable
messages. A fixed top-level shape makes the contract test trivial and prevents
per-route error bodies from reappearing.

**Alternatives considered**:

- *Flat `{code, message, details, detail}`*: fewer nesting levels, but mixes
  new and legacy fields at the top level and makes future error metadata harder
  to group.
- *Nested `{"detail": {"code", "message"}}`*: breaks the frontend because it
  only accepts a string `detail`; rejected.
- *RFC 7807 `application/problem+json`*: standard, but changes the media type
  and uses `title`/`detail`/`status` fields that do not preserve the current
  `detail` contract. It would require frontend changes, contrary to FR-001 and
  FR-006.

## Decision 2: Preserve existing status codes; normalize only the body

**Decision**: Existing route statuses stay exactly as they are: 400, 403, 404,
413, 415, and 500. Framework-generated responses keep their conventional
statuses: 404 for unknown paths, 405 for wrong methods, 422 for request
validation, and 500 for unhandled failures. Binary range failures keep 400 and
416 but return JSON bodies.

**Rationale**: This follows the additive-only compatibility policy in the spec
and the recommended Option A from the unresolved status-code clarification.
The current codes already fall into the categories required by FR-007, so
changing them would add risk without improving the only consumer. Keeping the
status mapping stable also lets the contract inventory describe current
behavior rather than a migration.

**Alternatives considered**:

- *Normalize everything to a new status table*: rejected because it would
  change frontend-visible outcomes and existing tests for no user benefit.
- *Change only framework errors*: partially normalized the body but left
  route-specific shapes, failing FR-003.
- *Map "not a directory" from 404 to 400*: semantically arguable, but a
  breaking status change; the current 404 is retained and documented.

## Decision 3: Use category-level error codes

**Decision**: `error.code` comes from a fixed, status-aligned vocabulary:

| Code | Status | Meaning |
|------|--------|---------|
| `invalid_request` | 400 | Malformed request or invalid combination of otherwise valid parameters |
| `forbidden` | 403 | The target exists but cannot be accessed |
| `not_found` | 404 | Unknown route, missing entry, or missing archive member |
| `method_not_allowed` | 405 | The route does not support the request method |
| `payload_too_large` | 413 | The requested binary exceeds a preview limit |
| `unsupported_media_type` | 415 | The file is not a supported image/video or cannot be decoded |
| `range_not_satisfiable` | 416 | The requested video byte range is outside the file |
| `validation_error` | 422 | Query/body schema validation failed |
| `internal_error` | 500 | I/O failure, log failure, launch failure, or unexpected defect |

The specific cause stays in the human-readable message (for example
`"Not a directory"`, `"Image is gone"`, `"Not a supported video"`). The
contract inventory records every route condition that produces each code.

**Rationale**: The category vocabulary maps one-to-one to the status categories
in FR-007 and stays stable as routes evolve. It avoids a large code surface
where every error branch invents a new string and where renaming a branch
becomes a breaking contract change. The frontend displays the message, not the
code, so per-branch codes would add maintenance cost without a consumer.
Machine clients still get a stable category, the HTTP status, the message, and
(for validation) structured field details.

**Alternatives considered**:

- *Granular codes such as `image_gone`, `not_a_zip_archive`, and
  `log_archive_error`*: more precise, but roughly two dozen codes for a local
  single-client app, with a higher chance of accidental renames. The contract
  inventory already captures the precise condition.
- *Code plus a `details.reason` subcode*: preserves precision without top-level
  code churn, but adds a second vocabulary for no current consumer.
- *String keys from exception classes*: unstable across refactors and not
  documented.

## Decision 4: Normalize validation errors without echoing raw input

**Decision**: `RequestValidationError` becomes:

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

- `location` is the Pydantic error `loc` converted to strings.
- `message` is the Pydantic `msg`.
- `type` is the Pydantic error type.
- The top-level message summarizes the first issue; all issues remain in
  `details.issues`.
- Raw `input` and exception `ctx` values are omitted because they may contain
  non-serializable values and are not needed by the client.

**Rationale**: FR-004 requires field-level detail to survive normalization.
The current FastAPI body is a list inside `detail`, which the frontend cannot
display as a string. Moving the list to `details.issues` and producing a string
`detail` satisfies both requirements without changing the validation rules.

**Alternatives considered**:

- *Keep the list in `detail` and add a parallel string*: violates the fixed
  envelope and leaves two detail meanings.
- *Stringify the whole Pydantic list into `detail`*: loses field structure.
- *Include raw input and ctx*: can leak or fail serialization; not needed for
  local form fields.

## Decision 5: Keep success payloads unchanged and publish a machine-readable contract

**Decision**: No success field, type, nullability, status, or domain outcome
changes. The only schema-visible adjustment is narrowing `PreviewModel.kind`
from `str` to the existing `PreviewKind` Literal so the allowed values are
explicit. Success conventions are documented rather than wrapped:

- snake_case keys; explicit `null` for absent optional values
- list/count pairs (`remaining`/`remaining_total`, `history`/`history_total`,
  `images`/`image_total`) where the list is capped and the total is not
- domain outcomes stay 200 (`valid_path: false`, `status:
  "invalid_path" | "empty" | "exhausted"`, `backup: null`, `removed: false`,
  `removed: 0`)
- array order remains the current deterministic order

The inventory lives at `contracts/api-contract.json`; the readable audit lives
at `contracts/api-contract.md`.

**Rationale**: The success payloads are already internally consistent and are
consumed by the only client. Wrapping or renaming them would violate FR-001,
FR-002, and FR-018. Publishing the exact shapes turns the audit into an
executable baseline without changing runtime behavior.

**Alternatives considered**:

- *Wrap all successes in `{"data": ...}`*: breaks every frontend screen.
- *Add a `success: true` field everywhere*: redundant; HTTP status and the
  existing route-specific shapes already carry success.
- *Rely on FastAPI's generated OpenAPI only*: it documents types but not
  consumed-field intent, error cases, domain outcomes, or binary content types.

## Decision 6: Enforce the contract with stdlib tests

**Decision**: Add `tests/test_api_contract.py` that:

1. Loads `contracts/api-contract.json`.
2. Compares the contract's `(method, path)` set with the app's `APIRoute` set
   under `/api`, in both directions, so a new or removed route fails.
3. Compares every JSON success schema with the OpenAPI schema generated by
   FastAPI: field names, JSON types, nullability, nested objects/arrays, and
   enums. Extra or missing fields fail.
4. Exercises representative failures for every documented error code and route
   condition, asserting status, JSON content type, envelope keys, code-to-status
   mapping, non-empty message, `detail == error.message`, and validation issue
   structure.
5. Exercises binary success behavior: image MIME types/WebP variants, video
   200/206 and `Accept-Ranges`, and JSON bodies for binary failures.
6. Runs seeded-drift assertions against the comparison helpers (remove a
   field, retype a field, add/remove a route) and confirms each mutation is
   rejected.

The test imports the code-to-status map from `choosier.web` and asserts it
matches the contract vocabulary exactly, so an undocumented code cannot be
introduced.

**Rationale**: This covers FR-011 through FR-016 and SC-003/SC-004 without a
new dependency, code-generation step, or separate CI job. FastAPI's OpenAPI
schema is the actual serialization contract, so comparing against it catches
field removal, renaming, and retyping. Live error tests catch handler drift.

**Alternatives considered**:

- *JSON Schema validation library*: adds a dependency and duplicates checks
  already expressible with plain assertions.
- *Snapshot tests of full responses*: brittle around paths, timestamps, and
  dynamic error messages.
- *Manual audit only*: fails FR-012 and SC-004.
- *Runtime middleware that validates every response*: adds production overhead
  and risk for a local app.

## Decision 7: No frontend source change

**Decision**: Leave `frontend/src/api.ts`, `types.ts`, and all components
unchanged. The invariant `typeof detail === "string"` is enforced by contract
tests.

**Rationale**: The current error path already does the right thing when
`detail` is a string. Changing the frontend would expand scope and make the
compatibility claim harder to verify. Binary failures are rendered through the
existing `<img>`/`<video>` error fallbacks, not through JSON parsing.

**Alternatives considered**:

- *Teach `request()` to read `error.message` as a fallback*: harmless but
  unnecessary; the contract guarantees `detail`.
- *Add a typed `ApiError` class and per-code UI messages*: no product
  requirement, and it would make the frontend depend on the new fields before
  they are proven stable.

## Decision 8: Keep binary success behavior; normalize binary failures

**Decision**:

- `/api/image` keeps returning original bytes for a full image and WebP for
  `thumb`/`preview`, with the existing `Cache-Control` and
  `X-Content-Type-Options` headers.
- `/api/video` keeps `FileResponse` streaming, `Accept-Ranges: bytes`, 200 for
  full responses, 206 for single/suffix/multipart ranges, and the existing
  MIME types.
- Before constructing the video response, a present `Range` header is validated
  with Starlette's range parser. Malformed ranges raise
  `invalid_request` (400); unsatisfiable ranges raise
  `range_not_satisfiable` (416) with `Content-Range: bytes */<size>`.
  Valid ranges are still delegated to `FileResponse`.
- Missing, unsupported, or unreadable binary targets use the standard JSON
  envelope.

**Rationale**: FR-010 requires preserving binary success bytes and range
behavior while standardizing failures. Starlette currently emits plain-text
400/416 responses from inside `FileResponse`, which would violate FR-008 and
FR-010. Pre-validation closes that gap without reimplementing streaming.

**Alternatives considered**:

- *Leave range errors as plain text*: fails the no-non-JSON-errors rule.
- *Replace `FileResponse` with a custom streaming implementation*: risks
  breaking multipart ranges and adds substantial code.
- *Buffer the whole file to inspect the response*: unacceptable for large
  videos and defeats streaming.

## Decision 9: Preserve existing messages; use one generic unhandled message

**Decision**: Route failures keep their current human-readable strings,
including dynamic `OSError` suffixes. Unknown routes use the framework's
`"Not Found"`; wrong methods keep `"Method Not Allowed"`; validation uses the
summary described in Decision 4. Unhandled exceptions return
`"Internal server error"` rather than exposing a traceback or exception text.

**Rationale**: Existing users see familiar messages, and the frontend keeps
working. Generic text for unhandled defects avoids leaking internals while
still satisfying the non-empty-message requirement.

**Alternatives considered**:

- *Prefix every message with the code*: noisy and changes current output.
- *Expose `repr(exc)` for 500s*: leaks implementation details and may include
  paths or values.

## Decision 10: Document the contract in README and CHANGELOG

**Decision**: Add a concise error-envelope section to `README.md`, link the
feature contract inventory, and add an Unreleased `CHANGELOG.md` entry. The
contract markdown includes a route-by-route audit and a checklist for adding
routes.

**Rationale**: The constitution requires user-visible changes to update both
files, and maintainers need a discoverable place to learn the update workflow.

**Alternatives considered**:

- *CHANGELOG only*: not enough for API maintainers.
- *Put the full inventory in README*: too long and would drift from the
  machine-readable source.
