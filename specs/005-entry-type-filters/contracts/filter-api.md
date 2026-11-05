# Contract: Filtered State and Pick API

**Feature**: `005-entry-type-filters` | **Date**: 2026-11-05

This contract is additive. It introduces one route (`POST /api/state`) and
optional fields on an existing route (`POST /api/pick`). `GET /api/state` and
all other routes keep their current request and response shapes.

The authoritative machine-readable inventory is
`specs/001-standardize-api-responses/contracts/api-contract.json`; the
human-readable audit is `specs/001-standardize-api-responses/contracts/api-contract.md`.
Both must be updated with this contract and the generated frontend contract
must be regenerated.

## 1. Shared filter values

### Type keys

| Key | Meaning | Label |
|---|---|---|
| `dir` | Any directory | `Folders` |
| `file:<suffix>` | File with the lowercased final suffix, including its dot | `<suffix> files` |
| `file:` | File with no suffix | `Files without an extension` |

Examples: `photo.JPG` → `file:.jpg`; `archive.tar.gz` → `file:.gz`; `README` →
`file:`. Type keys are opaque strings to clients; clients must use the keys
returned by the API, not construct new ones except when echoing a known key.

### `FilterTypeOption`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `key` | string | no | Canonical type key |
| `label` | string | no | Stable human label |
| `count` | integer | no | Base candidates of this type; `>= 1` |

### `FilterEntryOption`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `name` | string | no | Exact direct-child name |
| `type_key` | string | no | One of the keys in `filter_options.types` |

### `FilterOptions`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `types` | `FilterTypeOption[]` | no | Complete and uncapped; display order: folders, suffixes alphabetically, suffixless files; design target is at most 200 distinct types |
| `entries` | `FilterEntryOption[]` | no | Sorted by name; capped at 1,000 |
| `entries_total` | integer | no | Total base candidates; `>= entries.length` |
| `entries_truncated` | boolean | no | True exactly when `entries_total > entries.length` |

Counts are computed **before** type/entry exclusions and **before** history
subtraction. The checklist therefore describes the folder composition, not the
remaining pool. The UI summary uses the response's `remaining_total` for its
eligible-entry count; it must not derive that count from `type.count` or the
visible entry list.

### Request exclusion fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `excluded_types` | string[] | `[]` | Canonical type keys; empty means every type checked |
| `excluded_entries` | string[] | `[]` | Exact names; empty means every entry checked |

Empty arrays are omitted from the no-filter semantics: they mean all checked,
not none checked. Duplicates are deduplicated. Well-formed values that no
longer match the folder are ignored. Malformed values return
`422 validation_error` per section 5.

## 2. `POST /api/state`

**Purpose**: Return remaining candidates, recent history, and filter options
for a target with type and entry exclusions.

**Success**: `200 application/json`

Request body:

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `path` | string | yes | — | Target directory |
| `log_file` | string \| null | no | `null` | Empty/null means the colocated default |
| `include_hidden` | boolean | no | `false` | Existing option |
| `files_only` | boolean | no | `false` | Existing option; mutually exclusive with `dirs_only` |
| `dirs_only` | boolean | no | `false` | Existing option; mutually exclusive with `files_only` |
| `excluded_types` | string[] | no | `[]` | Type keys to exclude |
| `excluded_entries` | string[] | no | `[]` | Entry names to exclude |

Response body: every field of the current `GET /api/state` response, plus:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `filter_options` | `FilterOptions` | no | Empty options when `valid_path` is false |
| `known_entry_exclusions` | string[] | no | Sorted subset of the request's `excluded_entries` that matches a current base candidate, including entries outside the visible cap; empty when `valid_path` is false or no exclusions were sent |

`known_entry_exclusions` is the reconciliation input. A client keeps an entry
exclusion only while the server reports that name as present; it must not prune
against the visible `filter_options.entries` list alone, because that list is
capped. The field is request-dependent, while `filter_options` describes folder
composition.

`remaining` and `remaining_total` are filtered and history-subtracted.
`remaining` is still capped by the existing `PANEL_MAX_LINES` (200) for the
response; `remaining_total` is the full filtered total. `history` and
`history_total` are unchanged.

Example folder:

```text
B.JPG  README  a.jpg  notes.txt  sub/  .hidden  .choosier.jsonl
```

Request:

```json
{
  "path": "/tmp/filter-demo",
  "log_file": null,
  "include_hidden": false,
  "files_only": false,
  "dirs_only": false,
  "excluded_types": ["file:.jpg"],
  "excluded_entries": ["notes.txt"]
}
```

Response (history is empty in this example):

```json
{
  "valid_path": true,
  "path": "/tmp/filter-demo",
  "log_file": "/tmp/filter-demo/.choosier.jsonl",
  "remaining": ["README", "sub"],
  "remaining_total": 2,
  "history": [],
  "history_total": 0,
  "filter_options": {
    "types": [
      {"key": "dir", "label": "Folders", "count": 1},
      {"key": "file:.jpg", "label": ".jpg files", "count": 2},
      {"key": "file:.txt", "label": ".txt files", "count": 1},
      {"key": "file:", "label": "Files without an extension", "count": 1}
    ],
    "entries": [
      {"name": "B.JPG", "type_key": "file:.jpg"},
      {"name": "README", "type_key": "file:"},
      {"name": "a.jpg", "type_key": "file:.jpg"},
      {"name": "notes.txt", "type_key": "file:.txt"},
      {"name": "sub", "type_key": "dir"}
    ],
    "entries_total": 5,
    "entries_truncated": false
  },
  "known_entry_exclusions": ["notes.txt"]
}
```

Domain outcomes (still `200`):

- Target not a directory: `valid_path: false`, `remaining`/`history` empty,
  totals zero, `filter_options` empty with total zero, and
  `known_entry_exclusions` empty.
- Missing history file: empty history, total zero.
- Exclusions matching nothing: normal response; options and remaining reflect
  the actual folder.

Errors:

| Code | Status | Condition |
|---|---|---|
| `validation_error` | 422 | Missing/malformed body, wrong field types, malformed exclusion values, or over the list limits |
| `invalid_request` | 400 | `files_only` and `dirs_only` are both true |
| `method_not_allowed` | 405 | A method other than GET or POST on `/api/state` |
| `internal_error` | 500 | Unexpected exception |

## 3. `POST /api/pick` (additive fields)

The existing request fields and `200` behavior are unchanged. Two optional
fields are added:

| Field | Type | Default | Notes |
|---|---|---|---|
| `excluded_types` | string[] | `[]` | Same rules as `POST /api/state` |
| `excluded_entries` | string[] | `[]` | Same rules as `POST /api/state` |

The response shape is unchanged. `status` gains two values:

| Status | Meaning | `item` | `logged` | History effect |
|---|---|---|---|---|
| `picked` | One eligible entry was chosen | name | true unless dry run | One append unless dry run |
| `empty` | The folder has no children at all | null | false | None |
| `exhausted` | No candidates under existing options/history, or all such candidates are logged and filters removed nothing | null | false | None |
| `invalid_path` | Target is not a directory | null | false | None |
| `filtered_empty` | Base candidates exist, but type/entry exclusions leave none | null | false | None |
| `filtered_exhausted` | Filtered candidates exist, but all are already in history | null | false | None |

Classification order: `invalid_path` → `empty` (no folder children) →
`exhausted` (no base candidate) → `filtered_empty` (no filtered candidate) →
`filtered_exhausted` (no remaining and filters removed at least one candidate)
→ `exhausted` (no remaining, filters removed nothing) → `picked`.

Additional errors are the same as `POST /api/state`; the existing
`invalid_request` for conflicting folder options remains `400`.

Examples:

- Exclude every type key and every entry name → `filtered_empty`; no log write.
- Exclude all types except `file:.jpg`, pick and log both `.jpg` files, then
  pick again → `filtered_exhausted`; the rest of the folder is untouched.
- No exclusions and every visible candidate is logged → `exhausted` (existing
  behavior).
- Hidden-only folder with `include_hidden: false` → `exhausted` (preserves
  today's behavior).

## 4. Compatibility rules

- `GET /api/state` is frozen for this feature: no new query fields and no
  `filter_options` field. Existing callers keep working.
- Old `POST /api/pick` callers that omit the exclusion fields never receive
  `filtered_empty` or `filtered_exhausted`, because those states require
  exclusions that remove candidates.
- New response fields are additive; new request fields are optional.
- The API contract version stays `1`; the route inventory grows from 12 to 13.
- `api-contract.json` must add:
  - the `POST /api/state` route;
  - `FilterTypeOption`, `FilterEntryOption`, and `FilterOptions` schemas;
  - the new route's inline success schema, including `known_entry_exclusions`,
    and errors;
  - `excluded_types` / `excluded_entries` request documentation for pick;
  - the expanded pick status enum.
- `api-contract.md` must document the new route, fields, statuses, and
  examples.
- `frontend/scripts/generate-api-contract.mjs` must map
  `POST /api/state` to `FilteredStateResponse` (not the fallback name) and the
  regenerated `frontend/src/api-contract.generated.ts` must include the new
  schemas and route.
- `frontend/src/api-operations.ts` must add `stateFiltered: 'POST /api/state'`
  while keeping `state: 'GET /api/state'`. The operation inventory grows to 13;
  `frontend/tests/api-contract.test.mjs`, the README route count, and the
  generated-contract checks must be updated together.
- Python contract tests must assert the new route, success fields, statuses,
  nullability, request validation, and error taxonomy. No existing route may
  change.

## 5. Validation details

### Ownership

| Concern | Owner |
|---|---|
| Canonicalization, exact value rules, limits, `FilterValidationError` | `choosier/filters.py::normalize_exclusions` |
| HTTP `list[str]` shape and 422 envelope | `choosier/web.py` Pydantic request validators calling `normalize_exclusions` |
| Filtering with an already-normalized `FilterSelection` | `choosier/services/state.py` and `choosier/services/pick.py` |
| Constructing exclusions from server-returned keys/names | `choosier/tui.py` |

The web layer must not duplicate the rules and the services must not accept raw
strings. A validator failure becomes the existing `validation_error` 422
envelope through `RequestValidationError`, and the error message identifies
`excluded_types` or `excluded_entries`.

### Rules

| Value | Accepted | Rejected |
|---|---|---|
| Type key | Exactly `dir`; exactly `file:`; or `file:` plus a suffix starting with `.` and containing at least one character after it | Other prefixes, `file:jpg`, `file:.`, uppercase `DIR`, `/`, NUL, over 1,024 characters |
| Type suffix case | Lowercased before deduplication and filtering | — |
| Entry name | Non-empty string other than `.`/`..`, no `/` or NUL, at most 1,024 characters | Empty, `.`, `..`, path separators, NUL, over 1,024 characters |
| Exclusion count | Up to 2,000 type keys and 20,000 entry names, checked before deduplication | Over either limit → 422 |
| Unknown but well-formed key/name | Accepted and ignored | — |
| Duplicate values | Deduplicated | — |
| Conflicting folder options | — | `files_only` and `dirs_only` → 400 |

A backslash in an entry name is accepted as an opaque character because it can
be legal on POSIX. Names are only compared with scanned direct-child names and
are never joined to a path. The suffix rule follows `Path(name).suffix`; a
filename ending in a bare dot has no suffix and maps to `file:`.

## 6. Determinism and side effects

- `normalize_exclusions` lowercases the suffix portion of `file:` keys,
  dedupes, and returns frozen sets; clients sort arrays before sending them so
  request bodies and tests are stable.
- Eligible candidates are sorted by exact name before the existing seeded RNG
  chooses one. The same folder contents, exclusions, history, and seed produce
  the same sequence.
- `known_entry_exclusions` is sorted and request-dependent; it never changes
  eligibility.
- Filtered state assembly is read-only.
- Non-picked outcomes write nothing.
- `POST /api/state` never modifies history, files, or folders.

## 7. Migration note

This is an additive HTTP API change with no data-format migration:

- Existing `GET /api/state` callers need no change and receive no new fields.
- Existing `POST /api/pick` callers need no change; the new request fields
  default to empty, so they cannot receive the new statuses.
- New clients adopt `POST /api/state` and may send the exclusion fields. They
  must use `known_entry_exclusions` for reconciliation and must not prune
  against the capped `filter_options.entries` list. Clients that switch
  exhaustively over `status` must add the two new values, but only requests
  that send exclusions can observe them.
- The route inventory grows from 12 to 13. The machine-readable contract,
  human-readable contract, generated frontend client, README route count, and
  frontend contract tests must ship in the same change.
- Rollback is a straight removal of the additive route and optional fields;
  history, files, and existing clients are unaffected.
