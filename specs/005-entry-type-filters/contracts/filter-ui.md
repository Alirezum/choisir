# Contract: Filter UI State and Presentation

**Feature**: `005-entry-type-filters` | **Date**: 2026-11-05

This contract covers the two interactive adapters. The selection rule itself is
in the shared core; this document only defines ownership, presentation inputs,
user-facing outcomes, and test mapping.

## 1. Ownership matrix

| Concern | Owner |
|---|---|
| Type keys, labels, candidate filtering, outcome classification | `choosier/filters.py` and `choosier/chooser.py` |
| Filter options and filtered totals in a snapshot | `choosier/services/state.py` |
| Filtered pick and new statuses | `choosier/services/pick.py` |
| Session exclusions, reconciliation, summary text (web) | `frontend/src/state/use-filters.ts` |
| State request, debounce, out-of-order protection | `frontend/src/state/use-workspace-state.ts` |
| Pick request and filtered status messages | `frontend/src/state/use-picker.ts` |
| Composition and bindings | `frontend/src/state/use-workspace.ts` and `App.vue` |
| Rendering, focus, labels | `frontend/src/views/OptionsPanel.vue` |
| Session exclusions, widget synchronization, summary/messages (TUI) | `choosier/tui.py` |
| Shared request/response shape | `contracts/filter-api.md` |

Neither view nor the TUI computes eligibility. They render option values and
send exclusion changes to the shared request/service logic.

## 2. Frontend types and naming

The existing frontend `FilterSelection` describes the folder flags
`include_hidden` / `files_only` / `dirs_only`. Rename it to `FolderFlags` and
move it to `frontend/src/types.ts` so request interfaces can extend it without a
type-only import cycle; `view-models.ts` imports it. Rename the
`useFolderOptions` computed from `filters` to `folderFlags` so it cannot be
confused with the new exclusions. Keep the wire field names unchanged:
`include_hidden`, `files_only`, and `dirs_only`.

Add to `frontend/src/types.ts`:

```ts
export interface FolderFlags {
  include_hidden: boolean
  files_only: boolean
  dirs_only: boolean
}

export interface FilterExclusions {
  excluded_types: string[]
  excluded_entries: string[]
}

export interface FilteredStateRequest extends FolderFlags {
  path: string
  log_file?: string | null
  excluded_types?: string[]
  excluded_entries?: string[]
}

export interface PickRequest extends FolderFlags {
  path: string
  log_file?: string | null
  seed?: number | null
  dry_run: boolean
  excluded_types?: string[]
  excluded_entries?: string[]
}
```

Do not change the existing `PickRequest` fields or make the new fields required;
old callers must keep working. Re-export the generated `FilterTypeOption`,
`FilterEntryOption`, `FilterOptions`, and `FilteredStateResponse`. Keep
`StateResponse` for the unchanged GET operation. `FilteredStateResponse` is the
type of the state binding everywhere in the frontend; it is structurally
assignable to `StateResponse` for existing consumers.

Add to `frontend/src/view-models.ts` (and import `FolderFlags` from
`types.ts`):

```ts
export interface FilterEntryRow {
  name: string
  typeKey: string
  typeLabel: string
}

export interface FilterPanelModel {
  ready: boolean
  validPath: boolean
  empty: boolean
  eligibleEntries: number
  types: FilterTypeOption[]
  entries: FilterEntryRow[]
  checkedTypeKeys: ReadonlySet<string>
  checkedEntryNames: ReadonlySet<string>
  active: boolean
  summary: string
  entriesTotal: number
  entriesTruncated: boolean
}
```

`checkedTypeKeys` and `checkedEntryNames` are derived presentation sets. The
view never receives raw exclusion arrays. `WorkspaceBinding` changes `state` to
`Ref<FilteredStateResponse | null>` and gains:

```ts
filterPanel: ComputedRef<FilterPanelModel>
toggleFilterType: (key: string) => void
toggleFilterEntry: (name: string) => void
selectAllFilterTypes: () => void
clearFilterTypes: () => void
selectAllFilterEntries: () => void
clearFilterEntries: () => void
clearFilters: () => void
```

The exposed view model is named `filterPanel`, not `filters`, to keep it
distinct from both `folderFlags` and the `useFilters` unit.

## 3. `use-filters.ts`

### Public binding

```ts
export interface FilterBinding {
  exclusions: ComputedRef<FilterExclusions>
  revision: Ref<number>
  panel: (
    options: FilterOptions | null,
    eligibleEntries: number,
    validPath: boolean,
  ) => FilterPanelModel
  reconcile: (options: FilterOptions, knownEntryExclusions: readonly string[]) => void
  reset: () => void
  toggleType: (key: string) => void
  toggleEntry: (name: string) => void
  selectAllTypes: () => void
  clearTypes: () => void
  selectAllEntries: () => void
  clearEntries: () => void
  clearFilters: () => void
}
```

Dependencies: `path: Ref<string>` and `logFile: Ref<string>`. The unit caches
the last reconciled `FilterOptions` for the select-all/clear actions; it does
not cache the whole state response.

### Rules

- Initial and reset state: both exclusion arrays are empty; all options are
  checked.
- `toggleType(key)`: toggle `key` in `excluded_types`. Entry exclusions are
  untouched, even if the type becomes fully excluded.
- `toggleEntry(name)`: toggle `name` in `excluded_entries`. Type exclusions are
  untouched.
- `selectAllTypes()` / `selectAllEntries()`: clear the corresponding exclusion
  array.
- `clearTypes()`: exclude every type currently in the cached complete type
  list. `clearEntries()`: exclude every entry currently in the cached visible
  entry list (bounded list only).
- `clearFilters()`: clear both arrays.
- `reset()`: clear both arrays and invalidate the cached options.
- `reconcile(options, knownEntryExclusions)`:
  - Keep only type keys present in the complete `options.types` list.
  - Keep only entry names present in `knownEntryExclusions`, not merely in the
    visible `options.entries` list. The server reports matching names outside
    the 1,000-entry cap, so an entry that shifts beyond the cap keeps its
    exclusion instead of silently becoming eligible.
  - Never add an exclusion. New types/entries are checked by default.
  - Store the options for the next select-all/clear action.
- Exclusions are sorted before being exposed so request bodies and tests are
  stable.
- `revision` increments on every actual change, reset, or reconcile prune.
  A no-op action does not increment it.
- Watch `path` and `logFile` with `flush: 'sync'` and call `reset()`. This
  guarantees the next debounced request sees no stale exclusions after a scope
  change. `use-workspace.ts` also calls `reset()` from its path/log reset
  callbacks; the second call is a no-op.

### `panel(options, eligibleEntries, validPath)` output

- `ready = options !== null`; when false, `validPath` is false, `summary` is
  empty, `empty` is false, and lists are empty.
- `validPath = ready && validPath`.
- `empty = ready && validPath && options.types.length === 0`.
- `checkedTypeKeys` = all option keys minus current valid `excluded_types`.
- `checkedEntryNames` = all visible entry names minus current valid
  `excluded_entries`; `typeLabel` is looked up from the type list.
- `active = excludedTypes.length > 0 || excludedEntries.length > 0`.
- `eligibleEntries` is the server's `remaining_total`, clamped at zero.
- `entriesTotal` and `entriesTruncated` come from the response unchanged.

An invalid path returns empty `FilterOptions`, but `validPath` stays false so
the panel can show a folder-state message instead of “No eligible entries to
filter.”

### Summary text

Use exact pluralization helpers:

| Condition | Text |
|---|---|
| not ready | `""` |
| `validPath` false | `Choose a valid folder to see filter options.` |
| valid path, no types | `No eligible entries to filter.` |
| no exclusions | `No filter: all {X} {type/types} checked; {B} of {Y} {entry/entries} eligible.` |
| active | `Filter active: {A} of {X} {type/types} checked; {B} of {Y} {entry/entries} eligible.` |

Where:

- `X = options.types.length`
- `Y = options.entries_total`
- `A = checkedTypeKeys.size`
- `B = eligibleEntries`, the server's `remaining_total` after type/entry
  filters and history subtraction, clamped at zero.

`B` is not a sum of `type.count` values and is not derived from the visible
entry list. That keeps the summary truthful when entries are already logged or
when an exclusion names an entry outside the 1,000-entry cap. `B` may lag a
local toggle until the debounced state refresh returns; the summary updates
when that response arrives.

Examples: `No filter: all 5 types checked; 12 of 40 entries eligible.` /
`Filter active: 2 of 5 types checked; 12 of 40 entries eligible.`

### Bounded-list notice

When `entriesTruncated` is true, the view shows:

> Showing first 1,000 of 5,000 entries. Select all and Clear selection apply
> to these visible entries. Entries outside this list are unchanged here; type
> filters still apply to them.

The actual numbers come from `entries.length` and `entriesTotal`. The sentence
is derived in the view from the model so the same rule applies in tests.

## 4. `use-workspace-state.ts`

Changes:

- Dependency types become `folderFlags: ComputedRef<FolderFlags>` and
  `filterExclusions: ComputedRef<FilterExclusions>`, plus optional
  `onState: (response: FilteredStateResponse | null) => void`.
- The binding is `state: Ref<FilteredStateResponse | null>`. Do not type it as
  `StateResponse`; the filtered response is the source of `filter_options` and
  `known_entry_exclusions`.
- `refresh()` calls
  `api.stateFiltered({ path, log_file, ...folderFlags, ...filterExclusions })`,
  not `api.state`. Folder flags and exclusions are merged, not substituted.
- Watch `path`, `logFile`, `folderFlags`, and `filterExclusions`.
- Add a monotonically increasing request number. When a request starts, capture
  it; only the newest response may assign `state` and call `onState`. A blank
  path invalidates the number, clears `state`, and calls `onState(null)`.
- On success, assign `state.value = response`, then call
  `onState?.(response)`. `use-workspace.ts` passes
  `(response) => filterState.reconcile(
  response?.filter_options ?? emptyOptions,
  response?.known_entry_exclusions ?? [])`.
  A reconcile that prunes an exclusion triggers one follow-up request; a
  no-op reconcile does not.
- Errors still go to `status.reportError`; a stale failed request does not
  overwrite a newer pool or report a misleading status. Only report an error if
  the failed request is still the newest.

The 250 ms debounce and path/log change notifications remain unchanged.

## 5. `use-picker.ts`

Changes:

- Dependencies become `folderFlags: ComputedRef<FolderFlags>` and
  `filterExclusions: Pick<FilterBinding, 'exclusions' | 'revision'>`.
- Before building the body, capture `revision` and `options.path.value`.
  Include `...folderFlags.value` and `...filterExclusions.exclusions.value` in
  the `api.pick` body, so existing folder flags and the new exclusions are
  merged rather than substituted.
- After the await, if either the revision or path changed, discard the result:
  do not set the choice, do not set a status message. The `finally` refresh
  still reloads the current pool; if the server already logged the old pick,
  the refreshed history shows it.
- New status branches, with exact text:
  - `filtered_empty`: `Filters exclude every entry. Adjust them in Options or
    clear all filters.`
  - `filtered_exhausted`: `All entries matching the filters have been picked.
    Clear filters or reset history to pick more.`
- Existing `invalid_path`, `empty`, `exhausted`, and `picked` behavior and text
  remain unchanged.
- A filtered outcome never sets the current choice and never claims the folder
  is empty.

## 6. `use-workspace.ts` and `App.vue`

Wiring order:

1. `status`, `options`, `choice`.
2. `filterState = useFilters({ path: options.path, logFile: options.logFile })`.
3. `workspaceState = useWorkspaceState({
   ..., folderFlags: options.folderFlags,
   filterExclusions: filterState.exclusions,
   onState: (response) => filterState.reconcile(
     response?.filter_options ?? emptyOptions,
     response?.known_entry_exclusions ?? []) })`.
4. `picker = usePicker({ ..., folderFlags: options.folderFlags,
   filterExclusions: filterState })`.
5. `filterPanel = computed(() => filterState.panel(
   workspaceState.state.value?.filter_options ?? null,
   workspaceState.state.value?.remaining_total ?? 0,
   workspaceState.state.value?.valid_path ?? false))`.
6. Add `filterState.reset()` to `resetOnPathChange()` and
   `resetOnLogChange()`.

Return `filterPanel` plus the seven filter actions from `use-workspace.ts`.
`App.vue` passes `:filter-panel="filterPanel"` and the action events to
`OptionsPanel`.

## 7. `OptionsPanel.vue` contract

Keep the existing `log`, `seed`, `dry`, `hidden`, and `mode` models and their
markup/behavior. Add:

Props:

```ts
interface Props {
  filterPanel: FilterPanelModel
}
```

Emits:

```ts
type FilterEmits = {
  toggleType: [key: string]
  toggleEntry: [name: string]
  selectAllTypes: []
  clearTypes: []
  selectAllEntries: []
  clearEntries: []
  clearFilters: []
}
```

Structure:

- A filter section below Mode, separated by the same hairline rule as Mode.
- Summary line (`aria-live="polite"`) with the text from `use-filters`.
- Type group: legend `Types`, action row (`Select all types`, `Clear types`),
  and a scrollable checkbox list. Each row shows a native checkbox, the type
  label, and the count. Checked state comes from
  `filterPanel.checkedTypeKeys.has(type.key)`.
- Entry group: legend `Entries`, action row (`Select all entries`,
  `Clear selection`), and a scrollable checkbox list. Each row shows a native
  checkbox, the exact name, and a quiet type label. Checked state comes from
  `filterPanel.checkedEntryNames.has(entry.name)`.
- Global `Clear filters` action, enabled only when `filterPanel.active`.
- Truncation notice under the entry list when `filterPanel.entriesTruncated`.
- Not-ready state: `Choose a folder to see filter options.`
- Invalid path: `Choose a valid folder to see filter options.` with lists and
  actions disabled or absent. This must not be shown as “No eligible entries to
  filter.”
- Valid path with no options: `No eligible entries to filter.` with lists and
  actions disabled or absent.
- Every checklist is a `<fieldset>` with a `<legend>`; every input has a label;
  action buttons are `type="button"` and have text labels; the summary and
  truncation notice are referenced by `aria-describedby` on the lists.
- Emitted events change only filter state. The view never filters, sorts, or
  requests.

Presentation details:

- Reuse the existing graphite/Archivo design tokens, amber checkbox accent,
  hairline rules, 3px radius, and focus-visible outline. Do not add a new
  palette, font family, or a modal.
- Both lists are independently scrollable and bounded (`max-height` around
  220px) inside the existing 420px options column. Long names truncate with an
  ellipsis but keep the full name in the label/title for assistive access.
- Counts and type tags use the existing monospace data treatment and quiet
  `--ink-soft` color. The name remains the strongest element in an entry row.
- Focus order: summary → type actions → type checkboxes → entry actions →
  entry checkboxes → Clear filters. `:focus-visible` remains visible on every
  control.
- The filter section must not shift the existing Log/Seed/Dry run/Include
  hidden/Mode controls out of reach; the Options body already scrolls.

## 8. TUI contract

### Widgets and state

- Keep the existing Log/Seed/Dry run/Include hidden/Mode controls.
- Add to the Options tab:
  - `Static` summary (`id="filter-summary"`);
  - type action buttons (`types-all`, `types-none`);
  - `SelectionList` (`id="type-filter"`) with one option per type, prompt
    `"{label} ({count})"`, value = type key;
  - entry action buttons (`entries-all`, `entries-none`);
  - `SelectionList` (`id="entry-filter"`) with one option per visible entry,
    prompt `"{name}   {type label}"`, value = entry name;
  - truncation notice (`id="filter-notice"`);
  - `Clear filters` button (`id="clear-filters"`).
- Lists have a bounded height and their own scrollbar. Both are hidden or
  disabled when there are no options.
- The TUI keeps `_excluded_types: set[str]` and
  `_excluded_entries: set[str]`, `_filter_options: FilterOptions | None`,
  `_known_entry_exclusions: set[str]`, and
  `_filter_scope: tuple[Path, Path] | None`.
- Option prompts must be Rich-safe. Pass `Text` objects or escape names with
  `rich.markup.escape`; a filename containing `[` must render literally, just
  as the existing panel renderer does.

### Behavior

- `_sync_filter_scope()` compares `(_target, _current_log_path())` with
  `_filter_scope`. On a change, clear both exclusion sets and forget cached
  options; update the scope. This runs before a pick, before a panel refresh,
  and from the path/log `Input.Changed` handlers, so a scope edit resets the
  summary immediately and cannot carry exclusions into another folder. The
  list rebuild still follows the existing refresh cadence (submit, pick, or
  tab activation).
- `_refresh_panels(rebuild_filters: bool = True)`:
  1. sync scope;
  2. call `build_state(..., selection=FilterSelection(...))`;
  3. store `snapshot.filter_options` and
     `snapshot.known_entry_exclusions`;
  4. prune type keys absent from `filter_options.types` and entry names absent
     from `known_entry_exclusions`; never prune entry exclusions against the
     visible entry list alone;
  5. update remaining/history/summary/truncation using
     `snapshot.remaining_total` and `filter_options.entries_total`;
  6. rebuild both `SelectionList`s only when requested, guarded by a
     `_syncing_filters` flag so programmatic changes do not emit state changes.
- A `SelectionList.SelectedChanged` event:
  - ignored while `_syncing_filters`;
  - for `type-filter`, recompute `excluded_types` as current type keys minus
    selected values;
  - for `entry-filter`, update only the visible names: keep existing
    exclusions for names not in the visible list, then replace the visible
    subset with visible entry names minus selected values. A non-visible
    exclusion must survive toggling a visible entry; recomputing from the
    visible list alone would drop it;
  - then `_refresh_panels(rebuild_filters=False)` so remaining/history/summary
    update without destroying the focused list.
- Action buttons:
  - `types-all`: select all types; `types-none`: clear all type selections.
  - `entries-all`: select all visible entries; `entries-none`: clear all
    visible entry selections.
  - `clear-filters`: clear both sets.
  - After any action, refresh without rebuilding the lists that are still
    valid; on the next tab activation or pick, rebuild and reconcile.
- Rebuild when the Options tab is activated, a pick finishes, or the existing
  hidden/files/folders option changes. `on_tabbed_content_tab_activated` must
  include the `options-tab` pane, not only the remaining/history panes.
- Wire these events explicitly:
  - `Checkbox.Changed` for `#include-hidden` → `_refresh_panels(rebuild_filters=True)`;
  - `RadioSet.Changed` for `#mode` → `_refresh_panels(rebuild_filters=True)`;
  - `Input.Changed` for `#path-input` and `#log-input` → `_sync_filter_scope()`
    and update the summary immediately; the list rebuild continues on the
    existing refresh cadence.
  Ignore events whose widget ID is not one of these controls, and ignore
  programmatic changes while `_syncing_filters` is set.
- Rebuilding uses `select_all`/`deselect_all` or per-option selection from the
  exclusion sets; it preserves checked state for names that still exist.
- Existing behavior is unchanged: the TUI preserves the current choice on both
  path and log changes (the web UI clears it on a path change and preserves it
  on a log change). Filters reset in both cases.

### TUI messages

Keep the pick results distinct:

| Status | Message |
|---|---|
| `filtered_empty` | `Filters exclude every entry. Clear filters or adjust selections.` |
| `filtered_exhausted` | `All entries matching the filters have been selected. Clear filters or reset history.` |
| `empty` | `Path Empty.` (unchanged) |
| `exhausted` | `All choices have been selected. Delete log to reset.` (unchanged) |

The summary and truncation text follow the same rules as the web model, with
the same counts. An invalid path shows `Choose a valid folder to see filter
options.` rather than the no-options message. The `Clear filters` button is the
visible reset action. The TUI keeps its existing current-choice behavior on
path and log changes, as stated above.

### Keyboard and accessibility

- Tab/Shift+Tab moves focus through summary actions, lists, and the reset
  button; Space/Enter toggles a focused selection; buttons activate normally.
- Textual's native `SelectionList` and `Button` provide focus and announced
  checked state. Do not remove focus styling.
- The type and entry lists have visible labels above them, and the count/type
  metadata is part of the option prompt.
- No filter action is available only through a global shortcut.

## 9. Test mapping

| Layer | File | Required coverage |
|---|---|---|
| Core | `tests/test_filters.py` (new) | Type keys/labels/counts/order, suffix case, suffixless, folders, exclusions, `normalize_exclusions` success and every 422 rule, limit boundaries, 200 distinct types, `FILTER_ENTRY_LIMIT`, deterministic sorted names |
| Core | `tests/test_chooser.py` | Single scan, filtered candidates, intersection, history subtraction, seeded sequence, hidden/mode combination, unchanged no-filter behavior, 100-pick type/entry loops |
| Services | `tests/test_services_state.py` | `filter_options`, filtered totals, bounds, invalid path, exclusions ignored when stale, `known_entry_exclusions` including an entry outside the visible cap, counts pre-history |
| Services | `tests/test_services_pick.py` | `filtered_empty`/`filtered_exhausted`, no writes, dry run, stale exclusions, existing statuses unchanged, 100-pick loops |
| Boundaries | `tests/test_services_boundaries.py` | `choosier.filters` allowed in services; no UI/web imports; single filter definition |
| API contract | `tests/test_api_contract.py` | New route/schemas/statuses, `known_entry_exclusions`, request fields, error taxonomy, GET unchanged |
| API errors | `tests/test_api_errors.py` | Malformed type keys and entry names, every limit, conflicting options, 422 messages identifying `excluded_types` or `excluded_entries` |
| Web | `tests/test_web.py` | POST state with exclusions, filter options, `known_entry_exclusions`, filtered picks, no history writes, compatibility |
| TUI | `tests/test_tui.py` | Summary counts, invalid path message, reconciliation via `known_entry_exclusions`, reset, filtered messages, bounded notice, `[`-name prompts, event wiring for hidden/mode/path/log/Options tab; widget scenario if Textual pilot is used |
| Frontend API | `frontend/tests/api-contract.test.mjs` | 13 routes/operations, `stateFiltered` method/path/body, `api.state` unchanged |
| Frontend state | `frontend/tests/ui/state/use-filters.test.ts` (new) | Defaults, toggles, select/clear, reset on path/log, reconcile with non-visible names, summary counts, invalid path, revision |
| Frontend state | `use-workspace-state.test.ts` | `FilteredStateResponse` typing, POST body merging folder flags and exclusions, debounce, stale response discarded, `onState` reconcile |
| Frontend state | `use-picker.test.ts` | Folder flags plus exclusion body, filtered messages, no choice on filtered status, stale pick discarded |
| Frontend state | `use-workspace.test.ts` | Filter unit wiring, resets, `filterPanel` composition, current-choice behavior |
| Frontend view | `frontend/tests/ui/views/OptionsPanel.test.ts` | Props/emits, checked states, labels, buttons, summary, truncation, invalid/empty/not-ready states, keyboard/focus markup |

`frontend/scripts/check-ui-boundaries.mjs` requires a test file for every
`src/state/*.ts` and `src/views/*.vue`; the new `use-filters.ts` test is
mandatory, and `OptionsPanel.test.ts` must continue to cover every emit.
