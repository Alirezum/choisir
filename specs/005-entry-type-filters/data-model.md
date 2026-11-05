# Data Model: File-Type and Entry Filters

**Feature**: `005-entry-type-filters` | **Date**: 2026-11-05

The feature adds value objects to the standard-library core
(`choosier/filters.py`), extends the service snapshot/outcome models, and adds
transport types to the API contract. Filter selection itself is session state
owned by each interactive client; it is never written to disk.

## 1. Core value objects

### `FilterSelection`

One immutable set of exclusions for a pick or state request.

| Field | Type | Default | Invariants |
|---|---|---|---|
| `excluded_types` | `frozenset[str]` | empty | Canonical type keys; duplicates removed |
| `excluded_entries` | `frozenset[str]` | empty | Exact direct-child names; case-sensitive; duplicates removed |

Derived rules:

- `is_active` is true when either set is non-empty.
- Empty sets mean "all currently present types and entries are checked."
- The selection is not persisted and carries no folder or log path; callers
  scope it themselves.
- A `FilterSelection` is created through `normalize_exclusions()` when values
  come from an untrusted request. The TUI constructs one from keys and names
  the server already returned, so it has no user-typed key path.

### `CandidateEntry`

One direct child after the existing hidden-file, log-managed, files-only, and
dirs-only rules.

| Field | Type | Invariants |
|---|---|---|
| `name` | `str` | Exact basename; unique within the folder |
| `is_dir` | `bool` | From the directory entry type |
| `type_key` | `str` | Canonical key described below |

### Type key

A string in one of these forms:

| Key | Produced for | Label |
|---|---|---|
| `dir` | Any directory | `Folders` |
| `file:<suffix>` | File with `Path(name).suffix != ""` | `<suffix> files` |
| `file:` | File with no suffix | `Files without an extension` |

`<suffix>` is the final suffix lowercased and includes its leading dot.
Examples: `photo.JPG` → `file:.jpg`; `archive.tar.gz` → `file:.gz`;
`README` and `.bashrc` → `file:`. The key is a closed set derived only from
current candidates; it is not a path and is never used for filesystem access.

Display order for types is deterministic:

1. `dir`;
2. suffix types sorted by their lowercased suffix;
3. `file:` last.

### `FilterTypeOption`

| Field | Type | Invariants |
|---|---|---|
| `key` | `str` | Canonical type key |
| `label` | `str` | Stable human label from the table above |
| `count` | `int` | Number of base candidates of this type; `>= 1` in a returned option |

### `FilterEntryOption`

| Field | Type | Invariants |
|---|---|---|
| `name` | `str` | Exact direct-child name |
| `type_key` | `str` | Key of a type present in the same `FilterOptions` |

The client joins `type_key` to `FilterTypeOption` for the visible type label.
Entry options are sorted by exact name, matching the existing sorted candidate
order.

### `FilterOptions`

| Field | Type | Invariants |
|---|---|---|
| `types` | `tuple[FilterTypeOption, ...]` | Complete for the current base candidates; display order; totals match `entries_total` |
| `entries` | `tuple[FilterEntryOption, ...]` | Sorted by name; at most `FILTER_ENTRY_LIMIT` items |
| `entries_total` | `int` | Total base candidates; `>= len(entries)` |
| `entries_truncated` | `bool` | True exactly when `entries_total > len(entries)` |

Bounds:

- `FILTER_ENTRY_LIMIT = 1000` limits only the serialized checklist.
- Type options are complete and are not capped. The design target is at most
  200 distinct types per folder; a folder with more types still returns every
  type, but the two-second opening target does not apply.
- Entries outside the cap remain eligible. A type exclusion still removes all
  of its entries, including those outside the cap.
- An entry exclusion for a name outside the cap survives reconciliation because
  the state response reports it in `known_entry_exclusions`.

### `FilterPanelModel` (frontend view model)

Built by `use-filters.ts` from `FilterOptions` plus the current exclusions; the
view never computes eligibility.

| Field | Type | Meaning |
|---|---|---|
| `ready` | `boolean` | A state response with options has loaded |
| `validPath` | `boolean` | The loaded state says the target is a directory |
| `types` | `FilterTypeOption[]` | Ready-to-render type rows |
| `entries` | `FilterEntryRow[]` | Ready-to-render visible entry rows with a joined type label |
| `checkedTypeKeys` | `ReadonlySet<string>` | Type keys currently checked |
| `checkedEntryNames` | `ReadonlySet<string>` | Visible entry names currently checked |
| `active` | `boolean` | Any exclusion is present |
| `summary` | `string` | Active/no-filter summary with checked type and eligible entry counts |
| `eligibleEntries` | `number` | Server-reported `remaining_total` after filters and history |
| `entriesTotal` | `number` | Total base candidates |
| `entriesTruncated` | `boolean` | Whether the checklist is bounded |
| `empty` | `boolean` | The path is valid and there are no base candidates to filter |

`summary` uses `eligibleEntries`, not a locally summed type count, so logged
entries and exclusions for non-visible entries are reflected. `validPath`
distinguishes an invalid target from a valid folder with no options.

`FilterEntryRow` is `{name, typeKey, typeLabel}`: the API entry plus the label
joined from the type list so the view does no lookup logic. The raw exclusion
arrays stay inside `use-filters.ts`.

## 2. Service model changes

### `StateSnapshot` (extended)

All existing fields keep their meaning. `remaining` and `remaining_total` now
describe the **filtered** remaining pool.

| Field | Type | Change |
|---|---|---|
| `valid_path` | `bool` | Unchanged |
| `path` | `Path` | Unchanged |
| `log_file` | `Path` | Unchanged |
| `remaining` | `tuple[str, ...]` | Filtered, history-subtracted, sorted; still capped by `max_lines` |
| `remaining_total` | `int` | Filtered, history-subtracted total |
| `history` | `tuple[LogEntry, ...]` | Unchanged; filters never alter history |
| `history_total` | `int` | Unchanged |
| `filter_options` | `FilterOptions` | New; empty options when `valid_path` is false |
| `known_entry_exclusions` | `tuple[str, ...]` | New; sorted subset of requested entry exclusions that match current base candidates, including entries outside the visible cap; empty when `valid_path` is false |

`known_entry_exclusions` is request-dependent and therefore lives beside
`filter_options`, not inside it. It lets the client prune truly removed names
without receiving an unbounded complete listing. The `FilterOptions` object
itself remains a description of folder composition.

### `PickStatus` (extended)

```text
"picked" | "empty" | "exhausted" | "invalid_path"
        | "filtered_empty" | "filtered_exhausted"
```

`PickOutcome` gains no new fields. `item` remains `None` for every non-picked
status, `logged` remains false, and `preview` remains `None`.

## 3. Filtering precedence

For a target and options, the base candidate set is produced by applying, in
order:

1. target must be a directory (`invalid_path` if not);
2. exclude dot-prefixed names unless `include_hidden`;
3. exclude the active history log and its managed rotation backups;
4. apply `files_only` or `dirs_only` (mutually exclusive; both → invalid
   input error).

Then eligibility is the intersection:

```text
base candidate
  AND type_key not in excluded_types
  AND name not in excluded_entries
  AND name not in logged history
```

The last term is subtracted after filtering, so re-checking a previously picked
entry never makes it eligible again. The eligible pool is sorted by name before
seeded selection.

## 4. Validation rules

### Ownership

| Concern | Owner | Behavior |
|---|---|---|
| Canonicalization and value validation | `choosier/filters.py` | `normalize_exclusions(excluded_types, excluded_entries) -> FilterSelection` applies every rule below, deduplicates, lowercases suffixes, and raises `FilterValidationError` (a `ValueError` subclass) with the offending field |
| HTTP request shape and 422 envelope | `choosier/web.py` | Pydantic request validators require `list[str]`, call `normalize_exclusions`, and let `ValueError` become the existing `validation_error` 422 response; the message names the offending field, and routes pass the normalized `FilterSelection` to services |
| Filtering | `choosier/services/state.py`, `choosier/services/pick.py` | Accept a `FilterSelection` and never re-validate raw strings; they do not introduce a second rule set |
| TUI values | `choosier/tui.py` | Build a `FilterSelection` only from type keys and entry names returned by the server; no free-form key entry path |
| CLI | unchanged | Uses the default empty `FilterSelection` |

`FilterValidationError` carries `field` (`excluded_types` or
`excluded_entries`) and a human-readable message. The web validator includes
that field in the 422 message. Direct service callers construct a
`FilterSelection` directly; the service may defensively copy the frozen sets
but must not silently accept malformed values.

### Request exclusions

| Rule | Behavior |
|---|---|
| `excluded_types` duplicates | Deduplicated |
| Type key is exactly `dir` | Accepted |
| Type key is `file:` (suffixless type) | Accepted |
| Type key is `file:` plus a suffix that starts with `.` and has at least one character after it | Accepted; the suffix is lowercased |
| Type key has any other shape, including `file:jpg`, `file:.`, `DIR`, or a non-`file:` prefix | `422 validation_error` |
| Type key longer than 1,024 characters | `422 validation_error` |
| Type key contains `/` or NUL | `422 validation_error` |
| Well-formed key not present in the folder | Accepted and ignored while filtering |
| `excluded_entries` duplicates | Deduplicated |
| Entry name is `.` or `..`, empty, or contains `/` or NUL | `422 validation_error` |
| Entry name longer than 1,024 characters | `422 validation_error` |
| Valid name not present in the folder | Accepted and ignored while filtering |
| More than 2,000 type exclusions | `422 validation_error` |
| More than 20,000 entry exclusions | `422 validation_error` |
| `files_only` and `dirs_only` both true | `400 invalid_request`, unchanged |

The suffix rule follows `Path(name).suffix`: the final dot and the characters
after it. A filename ending in a bare dot has no suffix and maps to `file:`.
Entry names are case-sensitive. A name containing a backslash is accepted as an
opaque string because it can be a legal POSIX filename; it is only ever matched
against scanned child names and is never joined to a path. Limits are checked
before deduplication so a request cannot bypass them with duplicates; the
resulting sets are at most the same size.

### Option construction

- Counts are computed from base candidates before type/entry filters and before
  history subtraction, so the checklist reflects the folder's actual
  composition and remains stable as picks are logged.
- The entry list is also built from base candidates before type/entry filters,
  preserving the clarified independence of the two checklists.
- `known_entry_exclusions` is the intersection of the request's
  `excluded_entries` with the complete base-candidate names, sorted. It is
  computed before the visible-entry cap, so a name outside the cap is still
  reported as present.
- `valid_path: false` returns no types, no entries, `entries_total: 0`,
  `entries_truncated: false`, and `known_entry_exclusions: ()`.
- Missing history is not an error; all base candidates remain remaining.
- The UI summary's entry count is `remaining_total`, which is after type/entry
  filters and history subtraction. Its total is `entries_total`, which is the
  base candidate count. This keeps the summary truthful without re-deriving
  history or non-visible exclusions in the client.

## 5. State transitions

### Selection lifecycle

| Event | Effect |
|---|---|
| Folder first loaded | `excluded_types = {}`, `excluded_entries = {}`; every option checked |
| Uncheck type | Add its key to `excluded_types`; all entries of that type become ineligible |
| Re-check type | Remove its key; entries remain individually checked/unchecked |
| Uncheck entry | Add its name to `excluded_entries`; only that entry becomes ineligible |
| Re-check entry | Remove its name; history still excludes it if logged |
| Select all types/entries | Clear the corresponding exclusion set |
| Clear types/entries | Add every currently visible key/name to the corresponding set |
| Clear filters | Clear both sets |
| Target folder changes | Clear both sets; reload options for the new folder |
| Log file changes | Clear both sets; reload state for the new log |
| Existing hidden/files/folders option changes | Keep matching exclusions; prune vanished type keys and entry names reported absent; new options start checked |
| Folder contents change | Keep matching exclusions; prune type keys absent from `filter_options.types` and entry names absent from `known_entry_exclusions`; new entries/types start checked |
| Application restart | No persisted selection; everything starts checked |

Reconciliation prunes only; it never adds an exclusion for an option that was
not explicitly unchecked. This is what makes newly appearing entries checked.
Type pruning uses the complete `types` list. Entry pruning uses
`known_entry_exclusions`, which reports matching names outside the visible
1,000-entry cap; the client must not prune against the visible `entries` list
alone.

### Pick outcome matrix

| Folder children | Base candidates | Filtered candidates | Remaining | Status | History write |
|---|---|---|---|---|---|
| none | 0 | 0 | 0 | `empty` | no |
| present | 0 | 0 | 0 | `exhausted` | no |
| present | >0 | 0 | 0 | `filtered_empty` | no |
| present | >0 | >0 | 0 and filters removed ≥1 | `filtered_exhausted` | no |
| present | >0 | >0 | 0 and filters removed 0 | `exhausted` | no |
| present | >0 | >0 | >0 | `picked` | yes unless dry run |

"Filters removed ≥1" means the filtered candidate count is smaller than the
base candidate count; stale exclusions that match nothing therefore do not
change the ordinary status. `filtered_empty` takes precedence over
`filtered_exhausted` because there is nothing to call exhausted.

### Side effects

- A non-picked outcome writes nothing and leaves the history file untouched.
- A picked outcome appends exactly one item through `HistoryService`, unless
  `dry_run` or `commit=False`.
- Applying, reconciling, clearing, or resetting filters never calls a history
  mutation and never creates, modifies, moves, renames, or deletes a file or
  folder.
- `StateSnapshot` assembly is read-only apart from reading the history log.

## 6. Serialization mapping

| Core / service | API JSON | Frontend generated type |
|---|---|---|
| `FilterTypeOption` | `{key, label, count}` | `FilterTypeOption` |
| `FilterEntryOption` | `{name, type_key}` | `FilterEntryOption` |
| `FilterOptions` | `filter_options` object | `FilterOptions` |
| `FilterSelection` | `excluded_types`, `excluded_entries` arrays | `FilterExclusions` |
| `PickStatus` | `status` enum | `PickStatus` union |
| `StateSnapshot` | state response fields | `StateResponse` / `FilteredStateResponse` |
| `known_entry_exclusions` | `known_entry_exclusions` string array | `FilteredStateResponse['known_entry_exclusions']` |

The API contract adds a persistent `FilterTypeOption` schema, a
`FilterEntryOption` schema, and a `FilterOptions` schema so the frontend
generator can emit named interfaces.
