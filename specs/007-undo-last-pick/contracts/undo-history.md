# Interface Contract: Undo Last Pick

**Feature**: `007-undo-last-pick` | **Date**: 2026-11-17

**Authoritative machine-readable contract**:
[`specs/001-standardize-api-responses/contracts/api-contract.json`](../../001-standardize-api-responses/contracts/api-contract.json)

This document defines the additive API and UI contract for undo. It does not
replace the existing contract; the 001 JSON remains the source used by the
contract tests and the frontend generator.

## Compatibility

- Existing routes, fields, statuses, and error codes are unchanged.
- `POST /api/pick` gains one nullable field. Clients that ignore it continue to
  work.
- The route inventory grows from 16 to 17.
- The error taxonomy is unchanged; no new code or HTTP status is introduced.
- The history file format, CLI flags, output, prompts, and exit codes are
  unchanged.

## Schema: UndoReceipt

| Field | Type | Nullable | Rules |
|-------|------|----------|-------|
| `item` | string | no | Non-empty; the picked entry name |
| `entry` | string | no | Non-empty; exact appended JSON line without a line terminator |
| `digest` | string | no | Exactly 64 lowercase hexadecimal characters |

```json
{
  "item": "notes.txt",
  "entry": "{\"ts\": \"2026-11-17T10:00:00+00:00\", \"item\": \"notes.txt\"}",
  "digest": "9f2c...64 hex characters..."
}
```

## `POST /api/pick` — additive field

**Request**: unchanged.

**Success**: the existing `200` body plus:

| Field | Type | Nullable | Meaning |
|-------|------|----------|---------|
| `undo` | UndoReceipt | yes | Receipt for the appended line; `null` for every non-logged outcome, dry runs, unlogged picks, and a pick that triggered rotation |

All existing fields (`status`, `log_file`, `item`, `logged`, `preview`,
`path_memory_notice`) keep their types and meanings.

## `POST /api/history/undo`

**Purpose**: Remove the exact history line identified by a session receipt, if
and only if the log still matches the bytes written by that pick.

**Request body**: `application/json`

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `path` | string | yes | Active target folder, used to resolve the default log |
| `log_file` | string or null | no | Explicit log override; empty/null uses `<path>/.choosier.jsonl` |
| `receipt` | UndoReceipt | yes | Must match the schema above |

```json
{
  "path": "/home/me/choices",
  "log_file": null,
  "receipt": {
    "item": "notes.txt",
    "entry": "{\"ts\": \"2026-11-17T10:00:00+00:00\", \"item\": \"notes.txt\"}",
    "digest": "9f2c...64 hex characters..."
  }
}
```

**Success**: `200 application/json`

| Field | Type | Nullable | Meaning |
|-------|------|----------|---------|
| `log_file` | string | no | Resolved history file |
| `status` | string enum | no | `undone`, `nothing_to_undo`, or `changed` |
| `item` | string | no | Echo of the receipt's item |
| `removed` | boolean | no | `true` only for `undone` |

**Domain outcomes (all `200`)**:

- `undone`: the digest matched, the final line matched, and one line was
  removed. The item becomes eligible under the existing history rules.
- `nothing_to_undo`: the log is missing, empty, or its parent folder no longer
  exists. Nothing is created or rewritten.
- `changed`: the log is non-empty but the digest, trailing line, or parsed item
  did not match. No line is removed, so another session's entry can never be
  targeted.

**Errors**:

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | Missing/malformed body, missing `path`, missing receipt fields, empty `item`/`entry`, or a digest that is not 64 lowercase hex characters |
| `internal_error` | 500 | The log cannot be read or the atomic rewrite fails; the log remains as found |
| `method_not_allowed` | 405 | A method other than POST |
| `not_found` | 404 | No `/api` route matches |

**Concurrency guarantee**: The server holds the same exclusive history lock used
by append/remove/archive/clear for the read, digest verification, and rewrite.
A concurrent append either lands before the verification (causing `changed`) or
after the rewrite (remaining intact). It cannot be overwritten by undo.

**Byte guarantee**: `undone` rewrites the file with every line except the final
receipt line, preserving the bytes of all other lines. `nothing_to_undo` and
`changed` write nothing.

## TUI contract

| Element | Contract |
|---------|----------|
| Control | `Button(id="undo")` in `#actions`, after Pick and Open |
| Disabled | No receipt in the current session, or after a clear event |
| Label | `Undo <item>` when available; `Undo` when unavailable |
| Status on success | `Undid pick of <item>.` |
| Status on `changed` | `Could not undo <item>: history changed.` |
| Status on `nothing_to_undo` | `Could not undo <item>: history is empty.` |
| Status on I/O failure | The service message, with the receipt retained for retry |
| Choice clearing | Clears `#choice`, `#open`, and the preview only when the current choice equals `<target>/<item>` |
| Refresh | Remaining, history, filter options, and the Undo control refresh after every attempt |

## Web UI contract

| Element | Contract |
|---------|----------|
| Control | Secondary `<button type="button">` beside Open in the board meta row |
| Disabled | `disabled` when no receipt |
| Visible text | `Undo` |
| Accessible name | `Undo last pick: <item>` when available; `Undo last pick (nothing to undo)` when unavailable |
| Focus | Native tab focus with the existing visible focus ring |
| Shortcut | None added; no interception of text-field undo |
| Messages | Same three success/domain messages, announced through the existing `role="status"` status bar |
| Choice clearing | Invalidates the choice only when its item equals the undone item |
| Refresh | Calls the existing workspace refresh after every attempt |

## Contract tests required

1. The live app exposes exactly the 17 contract routes.
2. `PickResponse` in OpenAPI has exactly the existing six fields plus `undo`,
   nullable, referencing `UndoReceipt`.
3. `UndoReceipt` has `item`, `entry`, `digest`, all non-nullable strings.
4. `POST /api/history/undo` success schema has exactly `log_file`, `status`,
   `item`, `removed`; `status` has exactly the three-value enum.
5. A malformed receipt or a 63-character/non-hex digest returns 422.
6. A missing/empty log returns 200 `nothing_to_undo`.
7. An appended external line after the pick returns 200 `changed` with zero
   bytes changed.
8. An external rewrite or removal returns 200 `changed` with zero bytes changed.
9. A simulated `OSError` returns the existing 500 error envelope.
10. The generated TypeScript module is current (`npm run check:api`).
