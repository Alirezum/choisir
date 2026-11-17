# Phase 1 Data Model: Skip and Snooze

**Feature**: `008-skip-snooze` | **Date**: 2026-11-17

This feature adds no persistent entity and does not change the history format,
the path-memory record, or the target. It adds one shared input value, one
interface-only session record, additive state and pick results, and an
interface-level action result.

## Entity: SkipSelection

The validated set of entry names currently deferred in one request.

| Field | Type | Origin | Rules |
|-------|------|--------|-------|
| `names` | `frozenset[str]` | The interface's session skip map | At most 20,000 names; each non-empty, not `.` or `..`, at most 1,024 characters, no `/` or NUL. Missing or `None` means the empty set. |

**Lifecycle**: Constructed by an interface for each state or pick request. It is
not stored by the core, not serialized to disk, and not returned as an entity.
The web adapter normalizes the request's `skipped_entries` list into this value.

**Identity rule**: A name identifies the direct child of the active target
folder. Names are compared exactly and case-sensitively, matching the rest of
the candidate pipeline.

## Entity: SkipRecord (interface-only)

One active deferral held by a TUI or browser session.

| Field | Type | Origin | Rules |
|-------|------|--------|-------|
| `name` | string | The skipped remaining entry | Same validation as `SkipSelection.names` |
| `started_at` | monotonic number | The interface clock | Used only for display and expiry; never sent to the server |
| `expires_at` | monotonic number | `started_at + 600` seconds | The record is expired when the interface clock is at or past this value |

**Storage rule**: TUI keeps these records in `ChooserApp`; web keeps them in
`useSkip`. They are never written to the history log, path memory, browser
storage, cookies, or any file. They are discarded when the TUI exits or the web
page unloads/reloads.

**Display rule**: A record is displayed only while it is active and its name is
in the state response's `skipped` list. A record whose entry is currently
logged is retained internally (it can become displayable again if history is
removed) but hidden from the skipped display and not counted as skipped. A
state response prunes only names that were included in the request that
produced it, so a skip added while a request is in flight is not removed by
that earlier response. Before a new skip action, an expired record for the same
name is removed so the action starts a fresh cooldown instead of overlapping.

## Entity: Session Skip State

The interface-owned map of active `SkipRecord`s for the current target and
history-log setting.

| State | Meaning |
|-------|---------|
| `Empty` | No active skips |
| `Active(names)` | One or more unexpired skip records for existing entries |
| `AllSkipped` | `Active`, and the current state reports every filtered, unlogged entry as skipped |

### Transitions

| Event | Current state | Next state | Side effects |
|-------|---------------|------------|--------------|
| App/page start or restart | any | `Empty` | No skip is read from storage or the server |
| TUI/web session opens a target | `Empty` | `Empty` | First state request sends no skips |
| Person activates Not now on a remaining entry | `Empty` or `Active` | `Active + name` | Records `expires_at`; sends the name on the next state/pick request; status names the entry and return condition; history and target unchanged |
| Person activates Not now twice for the same entry | `Active(name)` | `Active(name)` | At most one record; a fresh cooldown replaces the old expiry (pruning an expired record first); no duplicate display or history change |
| Cooldown reaches `expires_at` | `Active(name)` | `Active - name` (or `Empty`) | The next state request omits the name; the entry returns to remaining automatically; history unchanged |
| Person restores one entry | `Active(names)` | `Active(names - name)` (or `Empty`) | The next state/pick request omits the name; the entry is immediately eligible under the current filters and history; history unchanged |
| Person restores all | `Active(names)` | `Empty` | All names omitted from the next request; every affected entry immediately eligible; history unchanged |
| Active folder changes | `Active` | `Empty` | All records for the previous target are discarded; the new target starts clean |
| History-log setting changes | `Active` | `Empty` | Same as a folder change |
| History log is archived, cleared, or externally edited | `Active` | `Active` | Skip records keep their own cooldown; no history write; display changes only if entries become picked/unpicked |
| Skipped entry is picked by another session | `Active(name)` | `Active(name)` | The record remains internally, is hidden from the skipped display and skipped count, and is counted as picked; history is unchanged by the skip |
| A logged skipped entry's history is removed | `Active(name)` | `Active(name)` | The record becomes displayable again; the entry is still skipped until expiry/restore |
| Skipped entry is deleted or renamed | `Active(name)` | `Active - name` | The state response omits it from `skipped_present`; the interface prunes the record without an error |
| Type or entry filter changes | `Active` | `Active` | The record survives; if the filter no longer matches, the entry is not remaining but remains in the skipped display until expiry/restore |
| Folder option (hidden/files/dirs) changes | `Active` | `Active` | The record survives because the entry still exists; it remains in the skipped display even if the option hides it from remaining |
| Pick succeeds for a name that was skipped after the request began | `Active(name)` | `Active - name` | Defensive consistency rule: the logged pick wins, the skip is removed, the outcome is explained, and history remains as written |
| Pick request starts | `Active` | `Active` | The request carries a snapshot of active names; the web UI disables skip controls until it finishes |
| Pick request fails before logging | `Active` | `Active` | No skip change; the error is reported and the person may retry |

## Entity: StateSnapshot (extended)

The existing immutable result of `build_state`. New fields are additive and
default to empty values so existing constructors and callers keep working.

| Field | Type | Rules |
|-------|------|-------|
| `skipped` | `tuple[str, ...]` | Active skip names that still exist and are not currently logged; sorted; drives the skipped display and `skipped_total`; the full list is returned, not truncated by the remaining-panel limit |
| `skipped_total` | `int` | `len(skipped)`; never includes picked or deleted entries |
| `skipped_present` | `tuple[str, ...]` | Active skip names that still exist, including names that are currently logged; sorted; used only to prune the interface map. Existence is checked against the target, not only the current option-filtered scan. |
| `all_skipped` | `bool` | True exactly when at least one filtered, unlogged entry exists and every such entry is in `skipped_present` |

The existing `remaining` and `remaining_total` exclude every active skip name
that still exists. `filter_options` and `known_entry_exclusions` are built from
the same candidate scan as before and never include skip state.

## Entity: PickStatus (extended)

The closed set of pick outcomes gains one value:

| Value | Meaning | History effect |
|-------|---------|----------------|
| `all_skipped` | At least one filtered, unlogged entry exists, but every one is actively skipped | No change; no item is returned |
| `picked` | An unskipped eligible entry was selected | Existing behavior; one line appended unless dry run |
| `empty`, `exhausted`, `invalid_path`, `filtered_empty`, `filtered_exhausted` | Existing meanings, unchanged | Existing behavior |

`all_skipped` is never returned when the eligible pool is empty for a different
reason. In particular, a filtered folder whose unlogged entries are all picked
still returns `filtered_exhausted`, not `all_skipped`.

## Entity: SkipOutcome (interface-level)

The result the TUI or web UI reports to the person. It is not persisted and is
not sent over HTTP.

| Value | Meaning | History effect |
|-------|---------|----------------|
| `skipped` | The name was eligible and a new record was created | None |
| `restored` | The name had a record and it was removed | None |
| `restored_all` | Every record was removed | None |
| `expired` | A record reached its cooldown and was removed by the tick | None |
| `pruned` | A record's entry no longer exists and the record was removed | None |
| `unavailable` | The name was not in the current remaining/skipped set, so nothing changed | None |
| `refused` | A pick was in flight or the target changed, so the action was refused | None |

## Existing Entities (unchanged)

- **HistoryEntry**: The JSONL record remains `{"ts": <ISO-8601 string>,
  "item": <name>}`; legacy formats remain readable. Skip adds no marker,
  tombstone, or schema version.
- **FilterSelection**: Type and entry exclusions remain session-long and are
  independent of skips. A skip is not added to `excluded_types` or
  `excluded_entries`.
- **PathMemory**: The remembered-folder record is unchanged and never contains
  a skip, entry name, or cooldown.
- **CandidateScan**: The hidden, managed-file, files-only, and dirs-only rules
  are unchanged. A skipped entry is still a normal candidate; it is removed
  later by the skip selection.

## Validation and Invariants

1. Skip state is never written to disk, history, path memory, cookies, or
   browser storage.
2. A skip never appends, removes, or rewrites a history line.
3. A skip never modifies, moves, renames, or deletes a target entry.
4. A skip is created only for a name that currently appears in the remaining
   pool. The TUI revalidates against a fresh shared state; the web UI checks
   the latest loaded state.
5. At most one record exists per exact entry name in a session.
6. The active set is bounded and validated before it reaches the core.
7. `remaining` and `remaining_total` exclude every active, existing skip.
8. `skipped_total` counts only existing, unlogged skipped entries; an entry is
   never counted as both available and skipped.
9. `all_skipped` implies `remaining_total == 0`, `skipped_total > 0`, and a
   non-empty filtered/unlogged eligible pool.
10. A pick with any active skip never selects a skipped name.
11. A pick with all eligible entries skipped returns `all_skipped` and writes
    nothing.
12. Expiry, restore, restore-all, pruning, and target changes leave history,
    filters, the current choice, preview, seed, dry-run setting, remembered
    folders, and target content unchanged.
13. The one-second tick only touches interface memory and state refreshes; it
    does not write anything.
14. Skip state is independent per TUI process, browser page, and browser tab.
