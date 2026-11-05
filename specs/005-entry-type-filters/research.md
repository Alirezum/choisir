# Phase 0 Research: File-Type and Entry Filters

**Feature**: `005-entry-type-filters` | **Date**: 2026-11-05

This research resolves the open implementation choices for the spec. There are
no remaining `NEEDS CLARIFICATION` items in the plan's Technical Context.

## 1. Filter identity and grouping

**Decision**: Identify a type with a canonical string key in one of three
shapes:

| Key | Meaning | Display label |
|---|---|---|
| `dir` | Any directory, regardless of name | `Folders` |
| `file:<suffix>` | A file whose final suffix is `<suffix>` after lowercasing | `<suffix> files` (for example `.jpg files`) |
| `file:` | A file with no suffix | `Files without an extension` |

The suffix is `Path(name).suffix.lower()`, so `archive.tar.gz` belongs to
`.gz` and `photo.JPG` and `photo.jpg` share `.jpg`. Names with a trailing dot
and dotfiles such as `.bashrc` have no suffix when hidden files are included.

Types are ordered for display as: `dir` first, then suffix types sorted by
their lowercased suffix, then the suffixless `file:` type last. Type groups are complete:
every distinct type in the eligible candidate set is returned, because the
spec requires every present type to be selectable.

**Rationale**: A structured key is stable across Python, JSON, and TypeScript,
avoids collisions between a folder literally named `.jpg` and a suffix, and
keeps later sorting and seeded selection deterministic. Using only the final
suffix matches `Path.suffix` and normal filesystem expectations, avoids
inventing a multi-suffix grouping rule, and keeps the type list small.

**Alternatives considered**:

- Human labels as keys: not unique after case-folding and not safe for names
  containing `:`.
- `(kind, suffix)` objects in sets: correct but awkward to serialize, compare,
  and validate; a string key is simpler and the shape is still explicit.
- Full multi-suffix extensions (`.tar.gz`): requires guessing which dots are
  part of the type and can make every compound filename a new type.
- MIME/content classification: explicitly out of scope in the spec and would
  add dependencies and slower scanning.
- Broad categories: rejected during clarification in favor of exact types.

## 2. Exclusion sets, not inclusion sets

**Decision**: The request and client state carry `excluded_types` and
`excluded_entries`. Empty arrays mean "everything is checked". Checking an item
removes it from the exclusion set; unchecking adds it. Resetting a folder or log
scope empties both sets.

**Rationale**: The clarified default is all entries checked. With exclusion
sets, a newly appearing entry or type is automatically eligible without the
client having to notice and add it to an include list. Exclusion sets also let
the default (no filter) serialize as no data, keep old pick requests working
unchanged, and make "Clear filters" a single reset operation. This directly
satisfies the "new entries start checked" rule in FR-015.

**Alternatives considered**:

- Included type/name sets: requires the client to enumerate the entire folder
  before its first request and would silently exclude newly added entries until
  the next refresh.
- A boolean `filter_active` flag alongside sets: redundant; empty sets are the
  canonical no-filter state.
- Storing the checked lists in the API: doubles payload size and creates two
  sources of truth for the same rule.

## 3. One scan feeds candidates, options, and totals

**Decision**: Add a single core scan that returns facts for every direct child:
name, whether it is a directory, its type key, and whether it survived the
existing hidden/log-managed/files-only/dirs-only rules. The scan result is
consumed in one pass to produce:

- the pre-history, pre-filter candidate set;
- complete type options with candidate counts;
- sorted entry options (bounded);
- the base entry total and whether the list is truncated;
- the directory-has-children flag used to keep the existing `empty` versus
  `exhausted` distinction.

`list_candidates`, `list_available_items`, `get_unselected_item`, `build_state`,
and `pick` all delegate to this scan or to the pure filter helpers built on it.
No interface performs its own filesystem filtering.

**Rationale**: Multiple scans can observe different folder states, double the
I/O on large folders, and let the type counts, entry list, and remaining pool
disagree. The spec requires accurate totals and one shared eligibility rule.
A single scan also keeps the pick path efficient: one read of the directory,
then set operations for type/entry exclusions and history subtraction.

**Alternatives considered**:

- Build options from one scan and candidates from another: risks inconsistent
  snapshots and doubles large-folder latency.
- Push filtering into each interface: violates the shared-core principle and
  would let the TUI and web UI drift.
- Scan lazily per type: more complex and slower for counts.

## 4. Bounded entry options

**Decision**: Return complete type options but cap serialized entry options at
**1,000** names, sorted by name. Include `entries_total` and
`entries_truncated`. The type list is not independently capped; the design
target is at most 200 distinct types, and a folder with more types remains
complete and scrollable but is outside the two-second target. The cap applies
only to the entry checklist, not to eligibility: entries beyond the cap remain
eligible unless their type is excluded. Select-all/clear on the entry list
affects visible entries only, and the UI states this.

To preserve an entry exclusion when its name moves outside the cap, the state
response also includes `known_entry_exclusions`: the sorted subset of requested
entry names that still match a current base candidate, computed before the
visible-entry cap. The client reconciles against that set, not the capped
`entries` list. This avoids an unbounded full listing while ensuring an entry
that shifts beyond the cap does not silently become eligible.

**Rationale**: A 5,000-entry folder must open quickly and remain usable, and
both Textual and the browser suffer with thousands of checkbox widgets. The
spec explicitly allows a bounded visible entry list when the bound and total
are stated. Excluding a type still removes all entries of that type, including
ones beyond the cap, so type filtering remains a way to narrow the pool.
Default-all-checked means capped entries are not accidentally excluded.
Keeping the type list complete preserves the exact-type promise; the 200-type
target keeps the common case bounded without introducing a second truncation
notice and a second class of unreachable filters.

**Alternatives considered**:

- Return every entry: unbounded payload and rendering cost; violates the
  large-folder success criterion's usability intent.
- Paginate: makes every entry reachable, but adds request fields, paging state,
  and UI controls beyond the requested feature. The spec does not require it.
- Truncate entries of unchecked types only: couples the two checklists, which
  the clarification rejected.

## 5. Filtered outcome classification

**Decision**: Keep the existing `empty` meaning (the folder has no children at
all) and the existing `exhausted` meaning (no remaining candidates under the
current folder options/history). Add:

- `filtered_empty`: the folder has candidate entries, but the type/entry
  exclusions leave no candidate at all.
- `filtered_exhausted`: the filters leave at least one matching candidate, but
  every matching candidate is already in history.

Classification order in `pick`:

1. Invalid target → `invalid_path`.
2. No children at all → `empty`.
3. No candidate survives hidden/files-only/dirs-only/log-managed rules →
   `exhausted` (preserves today's hidden-only folder behavior).
4. No candidate survives the type/entry filters → `filtered_empty`.
5. No remaining candidate after history → `filtered_exhausted` if the filters
   actually removed at least one candidate, otherwise `exhausted`.
6. Otherwise → `picked`.

**Rationale**: This preserves every existing unfiltered outcome and its tests,
while making the new states truthful. A folder with only hidden files is still
`exhausted` as it is today, not `empty`; a folder whose visible entries are all
excluded by a filter is `filtered_empty`, not an empty folder. Comparing the
filtered candidate count with the base candidate count prevents a stale or
empty exclusion set from mislabeling ordinary exhaustion.

**Alternatives considered**:

- Recompute `empty` from candidates: would change today's hidden-only behavior
  and break existing acceptance tests.
- Always use `filtered_exhausted` whenever exclusions are present: mislabels
  ordinary exhaustion when exclusions do not match anything.
- Only report a generic `empty`/`exhausted`: fails the spec's requirement for
  distinct, actionable filtered outcomes.

## 6. API transport: additive `POST /api/state`

**Decision**: Add `POST /api/state` with a JSON body containing the existing
state fields plus `excluded_types` and `excluded_entries`. Its response is the
existing state payload plus `filter_options` and `known_entry_exclusions`.
Keep `GET /api/state` unchanged. Add the same two exclusion fields to the
`POST /api/pick` body. New pick statuses appear only when exclusions are
supplied, so old clients cannot observe them. `choosier.filters.normalize_exclusions`
owns canonicalization and the exact value/limit rules; the web request models
call it and pass a normalized `FilterSelection` to services, so the 422
behavior has one source of truth.

**Rationale**: Exclusion sets can contain thousands of names and are awkward
and length-limited as query strings. A JSON body is the natural transport and
leaves the existing GET contract untouched for compatibility. One new route is
smaller and safer than changing the semantics of the widely used GET. The
contract is versioned and machine-readable, and the frontend generator can add
a second method for the same path without disturbing the existing operation.

**Alternatives considered**:

- Extend GET with repeated query parameters: URL length limits, awkward
  encoding, and cache/proxy ambiguity.
- Change GET `/api/state` to accept a body: GET bodies are not portable and
  many clients/proxies drop them.
- Add a separate `/api/filter-options` route: requires two requests and can
  return options inconsistent with the remaining pool.
- Send only included names: payload grows with folder size and breaks the
  "new entries checked" rule.

## 7. Filter state ownership in the web UI

**Decision**: Add `frontend/src/state/use-filters.ts` as the sole owner of the
exclusion sets, reconciliation, reset, active summary, and filter actions. The
composition root creates it before `useWorkspaceState`, passes its request
payload into the state and pick requests, and passes the response's
`filter_options` and `known_entry_exclusions` back through `reconcile`.
`OptionsPanel.vue` receives a ready-to-render `FilterPanelModel` and emits
intents; it owns no selection logic.

The existing folder flags keep their wire names but are renamed to
`FolderFlags` / `folderFlags` so they cannot be confused with the new
`FilterExclusions`; the exposed filter view model is `filterPanel`. Request
bodies merge both sets.

`useWorkspaceState` switches to `POST /api/state`, includes folder flags and
exclusions in the body, types its state as `FilteredStateResponse`, and
discards out-of-order responses with a request generation counter. `usePicker`
captures the filter revision and path before awaiting the pick and discards a
stale result if either changed. `useFilters` resets on path or log change and
prunes exclusions against the complete type list and
`known_entry_exclusions`. The summary's eligible-entry count is the response's
`remaining_total`, so history and non-visible exclusions are reflected; it is
not a sum of pre-history type counts.

**Rationale**: The existing boundary gate requires one state unit per concern
and forbids views from importing state or API modules. Separating filter
selection from workspace loading keeps each unit testable, prevents the view
from becoming a second source of truth, and makes race handling explicit. The
revision counter satisfies the spec's stale-pick edge case without coupling the
picker to the details of individual filter actions.

**Alternatives considered**:

- Put exclusions in `use-folder-options`: mixes a large selection model with
  the small existing option flags and makes the state/pick wiring harder to
  test.
- Keep selection in `OptionsPanel.vue`: violates the presentation-only view
  boundary.
- Let `useWorkspaceState` own exclusions: the state loader would become a
  second source of truth and the picker would need to reach into it.
- Re-fetch options on every keystroke: unnecessary traffic; the debounced state
  refresh already covers changes.

## 8. TUI structure

**Decision**: Keep the TUI as an adapter. Add a filter controller section to
the Options tab using two Textual `SelectionList` widgets (types and entries),
small action buttons, an active-summary line, and a bounded-list notice. The
TUI keeps `excluded_types` and `excluded_entries` sets and its last
path/log scope. On a scope change it clears both sets; otherwise it reconciles
against the latest `FilterOptions.types` and `known_entry_exclusions`.
Rebuilding the widgets is guarded so programmatic selection changes do not feed
back into the state. Option prompts use `Text` or `rich.markup.escape` so a
filename containing `[` renders literally.

Filter actions update the sets, refresh remaining/history/summary through the
shared `build_state`, and do not rebuild the selection widgets on every toggle
(only when the tab is activated, a pick finishes, or the scope/content
changes). `SelectionList.SelectedChanged` is the change signal; checked means
not excluded. Buttons provide select-all/clear for each list and one Clear
filters action. Explicit handlers connect `Checkbox.Changed` for Include
hidden, `RadioSet.Changed` for Mode, and `Input.Changed` for path/log to the
appropriate refresh or scope reset; `on_tabbed_content_tab_activated` includes
the `options-tab`. Keyboard operation uses Textual's native focus, space/enter
toggling, and button activation; the lists get visible focus styles from the
existing app.

Path and log changes reset filters. The TUI keeps its existing current-choice
behavior on both changes (preserve); the web UI clears the choice on a path
change and preserves it on a log change. The feature does not introduce a new
current-choice rule.

**Rationale**: Textual 8's `SelectionList` is multi-select, scrollable, and
keyboard-operable, which matches the requested checklist semantics without
building a custom widget. Guarded rebuilds avoid recursive events and preserve
the selected state when folder options or contents change. Keeping exclusions
in the TUI adapter mirrors the web state unit while the shared core remains
UI-agnostic.

**Alternatives considered**:

- A `Checkbox` per entry inside a scroll container: thousands of widgets and
  no built-in multi-select behavior; more work to keep focus and state.
- A custom modal filter screen: larger change, new navigation, and unnecessary
  for an Options-tab feature.
- Put exclusions in the core service layer: would make session selection part
  of the service state and complicate the stateless service contract.

## 9. Visual direction and accessibility

**Decision**: Reuse the existing Options panel visual language rather than
introducing a new one. The filter section uses the same graphite surfaces,
Archivo/Archivo Narrow typography, amber checkbox accent, hairline rules, and
focus-visible outline. It adds two bordered, independently scrollable
checklists with aligned counts, a compact action row per list, a summary line,
and a single Clear filters button. Entry rows use the existing data/monospace
treatment for names and a quiet metadata label for the type. The frontend
`frontend-design` skill is loaded and applies to this frontend visual work.

Accessibility: each checklist is a native `fieldset` with a `legend`; every row
is a native checkbox with a label containing the name/type/count; action
buttons have text labels; the summary and truncation notice are associated
with the lists via `aria-describedby`; focus order follows summary → type list
actions → type checkboxes → entry list actions → entry checkboxes → Clear
filters. No state is conveyed by color alone. The TUI relies on Textual's
native checkbox/selection announcements and focus.

**Rationale**: The feature adds controls to an existing panel; a new visual
language would compete with the pick board and make the filter feel bolted on.
Native controls satisfy keyboard and assistive-technology requirements with
less custom code, and the bounded scroll areas keep the 420px options column
usable.

**Alternatives considered**:

- A modal or drawer: larger interaction change and extra navigation for a
  frequently adjusted setting.
- Tags/chips instead of checkboxes: less discoverable and weaker keyboard
  semantics.
- A second accent color for filters: unnecessary; amber already means
  selection in this product.

## 10. History and determinism

**Decision**: Filters run before history subtraction. The eligible set is
`sorted(base ∩ type ∩ entry − logged)`. History is never filtered, rewritten,
or deleted by this feature. Seeded picks continue to use the existing
`random.Random(seed).choice` over that sorted list, and the TUI/web pass the
same seed and exclusions to the same service.

**Rationale**: This preserves the existing reproducibility guarantee and
ensures an entry re-checked after being picked stays excluded by history. The
spec requires filters not to alter history and requires the same seed/filter
selection/history to produce the same sequence.

**Alternatives considered**:

- Remove logged entries before filtering: same result for eligibility but
  hides history totals and complicates filtered-exhaustion classification.
- Reseed when filters change: violates the user's supplied seed and makes
  results unexplainable.
- Exclude logged types from the type counts: would make counts change after
  every pick and hide the folder's actual composition.
