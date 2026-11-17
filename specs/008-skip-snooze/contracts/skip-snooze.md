# Interface Contract: Skip and Snooze

**Feature**: `008-skip-snooze` | **Date**: 2026-11-17

**Authoritative machine-readable contract**:
[`specs/001-standardize-api-responses/contracts/api-contract.json`](../../001-standardize-api-responses/contracts/api-contract.json)

This document defines the additive API and UI contract for skip. It does not
replace the existing contract; the 001 JSON remains the source used by the
contract tests and the frontend generator.

## Compatibility

- Existing routes, fields, statuses, and error codes keep their types and
  meanings.
- The route inventory remains **17**. No skip route is added.
- `POST /api/state` and `POST /api/pick` gain one optional request field,
  `skipped_entries`.
- The state responses gain four additive fields: `skipped`, `skipped_total`,
  `skipped_present`, and `all_skipped`.
- `POST /api/pick` gains one new status value, `all_skipped`.
- The error taxonomy is unchanged; malformed skip values use the existing
  `validation_error` 422 envelope.
- The history file format, CLI flags, output, prompts, and exit codes are
  unchanged. No skip command or option is added to the CLI.

## `POST /api/state` — additive request and response fields

**Purpose unchanged**: Return remaining candidates, recent history, and filter
options for one target and filter set.

**Request body additions**:

| Field | Type | Required | Default | Rules |
|-------|------|----------|---------|-------|
| `skipped_entries` | string[] | no | `[]` | At most 20,000 names; each non-empty, not `.` or `..`, at most 1,024 characters, no `/` or NUL. Duplicates are ignored. |

All existing request fields (`path`, `log_file`, `include_hidden`,
`files_only`, `dirs_only`, `excluded_types`, `excluded_entries`) keep their
types and meanings. A stale or unknown skip name is not an error; it is ignored
and omitted from `skipped_present`.

```json
{
  "path": "/home/me/choices",
  "log_file": null,
  "include_hidden": false,
  "files_only": false,
  "dirs_only": false,
  "excluded_types": [],
  "excluded_entries": [],
  "skipped_entries": ["notes.txt", "draft.md"]
}
```

**Success**: `200 application/json`, the existing body plus:

| Field | Type | Nullable | Meaning |
|-------|------|----------|---------|
| `skipped` | string[] | no | Active skip names that still exist and are not currently logged; sorted; the display list; returned in full, not truncated by the remaining-panel limit |
| `skipped_total` | integer | no | `len(skipped)`; the true count of displayable skipped entries |
| `skipped_present` | string[] | no | Active skip names that still exist, including names that are currently logged; sorted; used to prune the interface map; existence is checked against the target, not only the current option-filtered scan |
| `all_skipped` | boolean | no | True exactly when at least one filtered, unlogged entry exists and every such entry is in `skipped_present` |

`remaining` and `remaining_total` exclude every active skip that still exists.
`history` and `history_total` are unchanged. `filter_options` and
`known_entry_exclusions` are built exactly as before and never include skip
state.

```json
{
  "valid_path": true,
  "path": "/home/me/choices",
  "log_file": "/home/me/choices/.choosier.jsonl",
  "remaining": ["beta.txt", "gamma", "delta"],
  "remaining_total": 3,
  "history": [],
  "history_total": 0,
  "filter_options": {"types": [], "entries": [], "entries_total": 0, "entries_truncated": false},
  "known_entry_exclusions": [],
  "skipped": ["alpha.txt"],
  "skipped_total": 1,
  "skipped_present": ["alpha.txt"],
  "all_skipped": false
}
```

## `GET /api/state` — additive response fields

`GET /api/state` has no skip input. It returns the same four fields with empty
values: `skipped: []`, `skipped_total: 0`, `skipped_present: []`,
`all_skipped: false`. Existing query parameters and behavior are unchanged.
Clients that want skip-aware state use `POST /api/state`.

## `POST /api/pick` — additive request field and status

**Request body additions**:

| Field | Type | Required | Default | Rules |
|-------|------|----------|---------|-------|
| `skipped_entries` | string[] | no | `[]` | Same validation as `POST /api/state` |

**Success**: `200 application/json`, the existing body plus one new value in
the `status` enum:

| Status | Meaning | History effect |
|--------|---------|----------------|
| `all_skipped` | At least one filtered, unlogged entry exists, but every one is actively skipped | No item, no log write |
| `picked` | An unskipped eligible entry was selected | Existing behavior |
| `empty`, `exhausted`, `invalid_path`, `filtered_empty`, `filtered_exhausted` | Existing meanings, unchanged | Existing behavior |

All existing response fields (`log_file`, `item`, `logged`, `preview`,
`path_memory_notice`, `undo`) keep their types and meanings. `all_skipped`
returns `item: null`, `logged: false`, `preview: null`, `undo: null`, and
`path_memory_notice: null`.

```json
{
  "status": "all_skipped",
  "log_file": "/home/me/choices/.choosier.jsonl",
  "item": null,
  "logged": false,
  "preview": null,
  "path_memory_notice": null,
  "undo": null
}
```

A pick never automatically restores or chooses a skipped entry. A skipped entry
is never returned as `item`.

## Validation and errors

| Code | Status | Condition |
|------|--------|-----------|
| `validation_error` | 422 | The body is missing/malformed; `skipped_entries` is not an array of strings; a name is empty, `.`, `..`, longer than 1,024 characters, or contains `/` or NUL; or the list exceeds 20,000 names |
| `invalid_request` | 400 | `files_only` and `dirs_only` are both true (existing) |
| `internal_error` | 500 | Existing history read/write or unexpected failure |
| `method_not_allowed` | 405 | Existing method mismatch |
| `not_found` | 404 | No `/api` route matches |

A stale or unknown skip name is a normal domain condition, not a request error.
It is ignored and omitted from `skipped_present`.

## Concurrency and state guarantees

- Skip state is held only by the interface. The server never stores it, so two
  browser tabs and two TUI processes are independent by construction.
- The server does not lock skip names. A pick in another session may select a
  name that this session skipped, because a skip is a session-local deferral,
  not a global exclusion. The current session sees the new history entry on its
  next state refresh.
- A request carries a snapshot of the active skip names. A pick result and a
  skip action never make one entry both skipped and newly logged: the web UI
  refuses skip while a pick is in flight, and a defensive post-result check
  removes a skip if a logged pick somehow wins the race.
- Skip, restore, restore-all, expiry, pruning, and target changes never write
  history. The history log remains the sole source of truth for picks.
- Expiry is interface-local. The server does not return skip timestamps; the
  interface owns its monotonic clock and the fixed ten-minute cooldown.
- A state response reflects the skip snapshot sent with its request. A skip
  added while a request is in flight is not pruned by that earlier response;
  only names included in the request can be pruned from it.
- Entries outside the visible remaining list are never skipped automatically.
  Skip controls exist only on rendered remaining rows, and `skipped_total`
  reports the true number of explicit skips.

## Empty-state precedence

The remaining area chooses its message in this order:

1. `all_skipped` is true: the distinct all-skipped message, with restore-all
   available.
2. `remaining_total == 0` and `skipped_total > 0`: a neutral "No items are
   available right now." message, with the skipped list visible. Do not claim
   the folder is empty or that everything has been picked.
3. The existing invalid-path, empty, exhausted, filtered-empty, and
   filtered-exhausted messages, unchanged.

This precedence keeps a skipped entry from looking like data loss and keeps the
all-skipped outcome distinct from the existing empty and exhausted outcomes.

## TUI contract

| Element | Contract |
|---------|----------|
| Location | Remaining tab, separate from History and filter options |
| Availability | Skip controls appear only for remaining entries; nothing is offered when the folder is empty, exhausted, or filtered-empty |
| Remaining list | Entry names with a `Not now` action for the highlighted entry |
| Skip label | `Not now: <item>` when an entry is highlighted; disabled otherwise |
| Skipped list | `<name> — returns in <time>` or `<name> — returns when this session ends`; separate from remaining and history |
| Restore | `Restore: <item> (returns in <time>)` for the highlighted skipped entry; disabled when none |
| Restore all | `Restore all`; disabled when no skipped entry is displayed |
| Expiry | One-second tick removes expired entries and refreshes the remaining/skipped views without manual action |
| Status on skip | `Skipped <item>. It returns in ten minutes or when this session ends.` |
| Status on restore | `Restored <item>.` |
| Status on restore all | `Restored N skipped items.` |
| Status on all-skipped pick | `Every available item is skipped. Restore skipped items to pick again.` |
| Status on stale/refused action | `Could not skip <item>: it is no longer available.` or the equivalent restore message |
| History | No write, no rewrite, no removal; the Undo control is unaffected |
| Target/log change | Clears the skip map; filters reset as they already do; history is untouched |
| Session restart | Clears all skips; previously skipped entries are eligible again |

## Web UI contract

| Element | Contract |
|---------|----------|
| Location | Remaining panel, below the remaining list |
| Availability | Skip buttons appear only on remaining rows; nothing is offered when the folder is empty, exhausted, or filtered-empty |
| Remaining row | Visible `Not now` button with `aria-label="Skip <item>"` |
| Skipped section | Each row shows the name and remaining cooldown, with a `Restore` button whose `aria-label` is `Restore <item>, returns in <time>` |
| Restore all | Visible `Restore all` button; disabled when no skipped entry is displayed |
| All-skipped state | Distinct message that every available item is skipped, plus the restore-all action; never reports empty, exhausted, or filtered-empty |
| Focus | Native tab stops with the existing visible focus ring |
| Shortcut | None added; no interception of text-field shortcuts |
| Messages | Same messages as the TUI, announced through the existing `role="status"` status bar |
| Expiry | One-second timer updates the countdown, removes expired rows, and triggers the existing state refresh |
| Reload/new tab | New session with no skips; tabs never share skip state |
| History | No write, no rewrite, no removal; Undo remains independent |

## Contract tests required

1. The live app exposes exactly the 17 contract routes; no skip route exists.
2. `POST /api/state` accepts `skipped_entries`, and the response has exactly the
   existing fields plus `skipped`, `skipped_total`, `skipped_present`, and
   `all_skipped` with the documented types.
3. `GET /api/state` returns the four skip fields with empty values.
4. `POST /api/pick` accepts `skipped_entries` and its `status` enum contains
   exactly the existing six values plus `all_skipped`.
5. A pick with one skipped eligible entry never returns that entry and never
   writes a line for it.
6. A pick with every eligible entry skipped returns `200 all_skipped`, does not
   change the log's bytes, and returns no item.
7. A pick with a skipped entry that is also filtered out returns the existing
   filtered status, not `all_skipped`.
8. A deleted or renamed skipped entry is absent from `skipped_present` and
   `skipped`; the request still succeeds.
9. `skipped_total` excludes picked entries; `skipped_present` includes them.
10. Malformed `skipped_entries` values return the existing 422 envelope.
11. The generated TypeScript module is current (`npm run check:api`).
12. The history log and target hashes are unchanged after every skip, restore,
    restore-all, expiry, and target-change check.
