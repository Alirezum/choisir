# Phase 0 Research: Skip and Snooze

**Feature**: `008-skip-snooze` | **Date**: 2026-11-17

All unknown technical choices are resolved below; the technical context has no
open clarification markers.

## R1. Where does skip state live?

**Decision**: Skip state lives only in the interface that owns the session:

- TUI: a `dict[str, float]` on `ChooserApp`, mapping each skipped entry name to
  its monotonic expiry time.
- Web: a `Map<string, SkipRecord>` owned by a new `useSkip` composable in the
  browser page.

The shared core never stores skip state. Each state and pick request carries the
active skip names as an explicit input, just as it already carries filter
exclusions.

**Rationale**: The specification requires session-only, independent-per-session
state that is never written to history, path memory, or any other record. A
client-held map makes "page reload starts a new session" and "tabs are
independent" true by construction. A server store would need a session identity,
cleanup policy, and cross-tab semantics, all of which the spec explicitly rules
out.

**Alternatives considered**: A server-side in-memory skip store keyed by a
session cookie (shared cleanup and lifecycle complexity; reload would need to
create a new identity); persisting skips in the history or path-memory record
(forbidden persistent state); deriving skips from history markers (would make
skip a history write).

## R2. How do skips affect shared selection?

**Decision**: Add a small stdlib-only `choosier/skip.py` with:

- `SKIP_COOLDOWN_SECONDS = 600`.
- A frozen `SkipSelection` containing a `frozenset[str]` of names.
- `normalize_skips(...)` that validates, deduplicates, and bounds the names.
- `MAX_SKIPPED_ENTRIES = 20000` and the same per-name rules as entry
  exclusions: non-empty, not `.` or `..`, at most 1,024 characters, no `/` or
  NUL.

`build_state(...)` and `pick(...)` gain an optional `skips: SkipSelection | None`
argument, defaulting to empty. They compute the filtered, unlogged eligible
pool, then temporarily remove active skipped names from the remaining pool.
Filter options, history, ordering, seeding, and tie-breaking are unchanged.

**Rationale**: Selection must stay in one UI-agnostic implementation. Passing
the skip set as an explicit input preserves that rule and keeps the core
time-free. A default empty set means the CLI, existing service callers, and
existing tests keep their current behavior without a new option.

**Alternatives considered**: Adding skipped names to `FilterSelection`
(conflates two different lifetimes and loses the ability to distinguish
all-skipped from filtered-empty); removing skipped names from candidate scans
(the names would look deleted and filter counts would change); retrying picks
until an unskipped entry appears (biases selection and can write history).

## R3. How is the all-skipped outcome distinguished?

**Decision**: Add `all_skipped` to `PickStatus` and to the state snapshot's
derived condition. It applies only when:

1. at least one filtered, unlogged entry exists; and
2. every one of those entries is in the active skip set.

The pick returns `all_skipped` with no item and no history write. An empty
folder, exhausted history, filtered-empty, and filtered-exhausted folder keep
their existing statuses. A pick never automatically restores or selects a
skipped entry.

**Rationale**: The person must be able to tell "everything is deferred" from
"everything is picked" or "the filters hide everything". The condition is
computed from the same eligible pool used by selection, so it cannot disagree
with the pick outcome.

**Alternatives considered**: Reusing `exhausted` or `filtered_exhausted` (hides
that entries are recoverable); automatically restoring the shortest skip (the
spec explicitly rejects an automatic pick); adding a `pick_anyway` override
(out of scope).

## R4. How is the cooldown measured and capped?

**Decision**: The cooldown is the fixed `SKIP_COOLDOWN_SECONDS` (ten minutes).
Each interface records an expiry using a monotonic clock:

- TUI: `time.monotonic() + SKIP_COOLDOWN_SECONDS`.
- Web: `performance.now() + SKIP_COOLDOWN_SECONDS * 1000`.

Each interface runs a one-second tick while the session is open. The tick
removes expired records and refreshes the affected views. The session end is a
second, implicit cap because the records live only in memory and are discarded
when the TUI exits or the page unloads/reloads. A system clock change cannot
shorten or extend a skip; a machine sleep may delay the visible tick, but the
record still disappears no later than the next session.

**Rationale**: Monotonic time is robust against wall-clock changes, and a
fixed constant keeps both interfaces identical. A one-second tick satisfies the
"without a manual reload" requirement without a background worker or a new
dependency. Both interfaces keep the clock read behind a small injectable
function, defaulting to their platform monotonic clock, so tests can advance
expiry without sleeping. Before a skip action, the interface prunes any expired
record for that name so the new action starts a fresh cooldown rather than
overlapping the old one.

**Alternatives considered**: Wall-clock timestamps (jump backwards/forwards on
clock changes); a `setTimeout` per skip (more timers and cleanup); persisting
the expiry (forbidden); a configurable duration (out of scope).

## R5. How is skip state scoped, pruned, and reset?

**Decision**:

- A path change or history-log setting change clears the entire skip map for
  the previous target. Returning to a previous target in the same session does
  not restore its skips.
- Archiving, clearing, or externally editing the history log does **not** clear
  skips. A skipped entry that is picked by another session remains in the
  session map internally, but is hidden from the skipped display and counted as
  picked. If its history entry is later removed, it becomes displayable again
  and remains skipped until expiry or restore.
- Every state response reports `skipped_present`: the active skip names that
  still exist in the target. The interface removes records that are absent from
  that set. This prunes deleted or renamed entries without an error. Existence
  is checked against the target directory itself, not only the current
  option-filtered scan, so a hidden/mode change does not silently prune a skip.
- A skipped entry that stops matching a type or entry filter keeps its skip.
  It is not shown as remaining, but it remains in the skipped display until it
  expires or is restored.
- A skipped entry that stops passing a folder option (hidden/mode change) also
  keeps its skip. It remains in the skipped display because it still exists in
  the target.
- The display list (`skipped`) excludes names that are currently logged. The
  internal map is not pruned for them, because history can change again before
  the cooldown ends.
- A state response prunes only names that were included in the request that
  produced it. A skip added while a request is in flight is not pruned by that
  earlier response; the request that includes it is the authority for its
  existence.

**Rationale**: This separates "the entry no longer exists" from "the entry is
temporarily outside the current view". Only the former is permanent, so only
the former prunes state. Keeping logged skips internally preserves the spec's
history-removal edge case while the display list keeps the picked count and the
skipped count from double-counting the same entry.

**Alternatives considered**: Clearing skips on any filter change (would make a
skip behave like a filter and lose the deferral); pruning on any state refresh
from `remaining` (would drop skips hidden by filters); displaying picked skips
as skipped (double counts one entry).

## R6. What is the HTTP contract?

**Decision**: No new route. The route inventory remains 17. The existing
`POST /api/state` and `POST /api/pick` bodies gain an optional
`skipped_entries: string[]` field, defaulting to `[]` and validated like entry
exclusions. The state responses gain four additive fields:

| Field | Type | Meaning |
|-------|------|---------|
| `skipped` | string[] | Active skip names that still exist and are not currently logged; the display list |
| `skipped_total` | integer | Length of `skipped` |
| `skipped_present` | string[] | Active skip names that still exist, including names that are currently logged; used to prune the session map |
| `all_skipped` | boolean | True exactly when at least one filtered, unlogged entry exists and every such entry is actively skipped |

`POST /api/pick` gains `all_skipped` in its `status` enum. Its body gains the
same optional `skipped_entries` field. `GET /api/state` keeps its existing query
parameters and returns empty skip fields, because it has no skip input; clients
that want skip-aware state use `POST /api/state`.

Every existing field, route, status code, and error code keeps its meaning. A
malformed `skipped_entries` value is a `validation_error` 422; a stale or
unknown name is not an error, because it is pruned or ignored.

**Rationale**: The browser already sends its session filter state on every
state and pick request; sending skip names follows the same pattern. The four
state fields give the UI enough information to display, count, prune, and show
the all-skipped condition without a server session store. No new route is
needed because skip has no server-side effect.

**Alternatives considered**: A `POST /api/skip` route (would add public surface
without any server state); a server session store (violates tab/reload
independence); returning skip timestamps from the server (the server does not
own the session clock); overloading `remaining` (would lose the skipped list).

## R7. How do the interfaces present and label Skip?

**Decision**:

- **TUI**: Replace the static Remaining tab body with a small vertical panel:
  a summary line, an `OptionList` of remaining entries, and a `Not now` button
  that acts on the highlighted entry and whose label includes the entry name
  when one is highlighted. Below it, a `Skipped` section lists each active
  skipped entry as `<name> — returns in <time>` or `<name> — returns when this
  session ends`, with a `Restore` button whose label includes the highlighted
  entry and its return time, and a `Restore all` button. Controls are disabled
  when they have no target. The one-second tick updates the labels and removes
  expired entries.
- **Web**: `RemainingPanel.vue` gains a `Not now` button on each remaining row,
  a separate `Skipped` section below it with each name, its remaining cooldown,
  a `Restore` button per row, and a `Restore all` button. The all-skipped empty
  state says that every available item is skipped and keeps the restore-all
  action visible. When no item is available but some entries are skipped, the
  panel uses a neutral "No items are available right now." message instead of
  claiming the folder is empty or everything is picked, so the skipped section
  remains the explanation. Buttons are native tab stops with `aria-label`s that
  name the entry; the existing status bar announces results.
- **Messages**: Skip: `Skipped <item>. It returns in ten minutes or when this
  session ends.` Restore: `Restored <item>.` Restore all: `Restored N skipped
  items.` All skipped: `Every available item is skipped. Restore skipped items
  to pick again.` Refused/stale: `Could not skip <item>: it is no longer
  available.` The skip list is separate from history and from filter options.
- **Visual language**: Follow the loaded `frontend-design` skill and the
  existing split-flap board: the new controls are quiet secondary actions,
  reuse the amber focus ring and disabled treatment, and introduce no new
  palette, typeface, card, gradient, or animation. The skipped section uses the
  existing panel rhythm rather than a new component family.

**Rationale**: A visible, named action for every remaining row and every
skipped row satisfies the one-action, keyboard, focus, and accessible-name
requirements in both interfaces. Keeping skip out of the history panel makes
the "not picked" promise visible.

**Alternatives considered**: A single global Skip button for the whole list
without per-entry controls (fails per-entry restore/accessibility); putting
skips in the History tab (makes them look like picks); a confirmation dialog
(the spec requires no dialog and skip is reversible).

## R8. How are pick/skip races handled?

**Decision**:

- The web picker owns a `picking` flag; the skip unit owns a `skipping` flag.
  The composition root owns the shared `picking` guard and passes it to both
  units, so neither unit depends on the other. Skip is refused while a pick is
  in flight, and pick is refused or disabled while a skip/restore action is in
  flight. The TUI is synchronous, so its actions cannot overlap, but it applies
  the same validation before adding a skip.
- Before a skip is added, the interface checks that the name is in the current
  remaining set. The TUI rebuilds the shared state immediately before adding;
  the web uses the latest state response and refuses if the name is no longer
  present.
- If a pick response nevertheless names an entry that has since been skipped
  (for example, a response that arrives after a refused overlap), the pick is
  treated as authoritative because its history line already exists. The
  interface removes that entry's skip, reports the outcome, and refreshes.
  This is a defensive check, not the normal path.
- A concurrent pick in another session is allowed to choose a skipped entry.
  The skip is session-local and does not block another session; the current
  session sees the new history entry after its next refresh and stops
  displaying the entry as available.

**Rationale**: This satisfies "never both skipped and recorded as picked" and
"explain any refused or stale action" without adding a lock or server session
state. The history log remains the sole source of truth for picks.

**Alternatives considered**: Server-side locking of skip names (would make skip
a shared lock and block other sessions); silently dropping a conflicting skip
(no user feedback); refusing a pick that became skipped after it started (the
history line is already written, so the interface cannot undo it without
Undo).

## R9. How is the skip set validated and bounded?

**Decision**: `normalize_skips` mirrors entry-exclusion validation: at most
20,000 names, each at most 1,024 characters, non-empty, not `.` or `..`, and no
`/` or NUL. The web request model normalizes the list before the service call
and returns the existing `validation_error` 422 envelope for malformed values.
Unknown or stale names are not validation errors; the state builder ignores
names that no longer exist and reports the surviving set in `skipped_present`.

**Rationale**: The list crosses a local HTTP boundary and must not be allowed to
grow without bound or inject path-like values. Reusing the existing entry-name
rules keeps the behavior consistent with filters, and treating stale names as a
normal domain condition avoids surfacing a scary error when a file is deleted
between refreshes.

**Alternatives considered**: Unbounded `list[str]` (resource risk); rejecting
stale names with 422 (turns a normal folder change into an error); separate
validation in the TUI and web (drift risk).

## R10. What remains explicitly unchanged?

**Decision**: The one-shot CLI keeps every flag, prompt, output line, and exit
code, and gains no skip option. The history JSONL format, legacy parsing,
rotation threshold, archive naming, and path-memory record are unchanged. Pick
selection, seed determinism, filters, ordering, preview, open, and all existing
history actions are unchanged when the skip set is empty. Skip adds no route,
error code, runtime dependency, target write, or persistent store.

**Rationale**: These are the feature's stated boundaries and the
constitution's public-contract constraints. The only visible additions are the
TUI/web controls, the skipped list, the distinct all-skipped outcome, and the
documented additive API fields.
