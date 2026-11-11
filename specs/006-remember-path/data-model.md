# Phase 1 Data Model: Remembered Folder Paths

**Feature**: 006-remember-path | **Date**: 2026-11-11

## Entity Overview

```text
PathMemoryRecord (1 per user/machine)
└── RecentLocationsList (0..1)
    └── RememberedLocation (0..10, ordered newest → oldest)

StartupResolution (derived per launch)
MemoryMutationResult (derived per record/remove/clear)
```

The record is independent of target folders, history logs, filters, choices, and
previews. It stores no file names and no timestamps.

## PathMemoryRecord

The persisted document.

| Field | Type | Required | Rules |
|---|---|---|---|
| `version` | integer | yes on write | Must be `1` for this implementation. A missing or unknown value is treated as empty memory for reading; the next successful write normalizes to `1`. |
| `recent` | array of strings | yes on write | Newest first. Each entry is a non-empty absolute canonical folder path. Maximum 10 entries. No duplicates after canonicalization. |

**On-disk example**

```json
{
  "version": 1,
  "recent": [
    "/home/ana/projects/alpha",
    "/home/ana/projects/beta"
  ]
}
```

**Location**: OS-appropriate user config directory (see
[research.md](./research.md#r1-storage-location)), overridable by
`CHOOSIER_PATH_MEMORY_FILE`. Never inside a target folder.

**Encoding**: UTF-8, no BOM, trailing newline on write. File mode `0o600` on
POSIX; parent directory `0o700` where created.

## RememberedLocation

A folder the person has successfully picked from.

| Field | Type | Derivation |
|---|---|---|
| `path` | string | `str(Path(input).expanduser().resolve())`; absolute, symlinks resolved, no trailing separator (except filesystem root). |
| `identity` | string | `os.path.normcase(path)`; used only for equality/deduplication, never stored. |
| `rank` | integer (derived) | Zero-based index in `recent`; `0` is most recent. Not stored. |

**Validation on load**: each element must be a non-empty string whose
canonicalized form is an absolute path. Blank, non-string, relative-only, and
unresolvable values are discarded. Duplicate identities are collapsed, keeping
the first (most recent) occurrence. The list is truncated to ten.

**Availability check**: `path.is_dir()` and a scannable directory handle. A
path that fails is unavailable even if it remains syntactically valid.

## RecentLocationsList

Ordered, duplicate-free collection shared by the TUI and web UI.

**Invariants**

1. `0 <= len(recent) <= 10`.
2. Order is recency: index `0` is the last successful pick folder.
3. Identities are unique under `os.path.normcase`.
4. Every returned entry is an existing, readable directory; unavailable entries
   are pruned before the list is exposed.
5. Recording an existing folder moves it to index `0` without duplicating it.
6. Adding beyond ten evicts the oldest entry.
7. Clearing yields an empty list; the file may remain with
   `{"version": 1, "recent": []}` or be removed. The implementation keeps a
   valid empty document for predictable subsequent operations.

## StartupResolution

Derived at launch, never stored.

| Field | Type | Rules |
|---|---|---|
| `path` | string | The first valid remembered folder, or the caller's default when none are valid. |
| `source` | `"recent"` \| `"default"` | Why the path was chosen. Explicit launch paths bypass resolution entirely. |
| `warning` | string \| null | Non-blocking explanation when entries were skipped, pruned, or unreadable. Null on a clean resolution. |

**Precedence**: explicit launch path (even invalid) → first valid recent →
caller default (TUI: empty input; web: current working directory).

## MemoryMutationResult

Derived from `record`, `remove`, or `clear`.

| Field | Type | Rules |
|---|---|---|
| `ok` | boolean | False only when the store could not be read/written. |
| `changed` | boolean | False when the request was already satisfied (removing an absent path, clearing an empty list). |
| `notice` | string \| null | Non-blocking message for failures, or null on success. |

Adapters surface `notice` without failing the pick or changing the active path.

## State Transitions

### Record a successful pick

```text
canonical = canonicalize(folder)
recent' = [canonical] + [p for p in recent if identity(p) != identity(canonical)]
recent' = recent'[:10]
persist(recent')
```

Triggered only when a pick outcome is `picked`, including dry-run. Not
triggered by browsing, path edits, invalid paths, empty/exhausted/filtered
outcomes, history actions, or one-shot CLI picks.

### Remove one

```text
recent' = [p for p in recent if identity(p) != identity(target)]
persist(recent') if changed
```

Does not change the running session's active path, history, filters, choice, or
target content.

### Clear all

```text
persist([])
```

Does not change the running session's active path or any other state.

### Prune on read (startup or list refresh)

```text
stored = read()
valid = []
for p in stored:
    if identity(p) not in seen and is_usable_directory(p):
        valid.append(p)
    else:
        skipped += 1
if valid != stored:
    persist(valid)
return valid, warning_if_skipped
```

Pruning is automatic. A dead entry is never returned to either interface.

### Corrupt or unreadable record

```text
on parse/shape error:
    recent = []
    warning = "Remembered folders could not be read; ..."
on read I/O error:
    recent = []
    warning = "Could not read remembered folders; ..."
```

The store is left untouched until the next successful mutation.

### Concurrent updates

Every mutation and pruning read runs while holding the exclusive sibling lock
(see [research.md](./research.md#r5-atomic-writes-and-cross-process-locking)).
Operations observe either the previous or the next complete document, never a
partial one. The most recent successful write wins.

## Size Bounds and Performance

| Bound | Value | Rationale |
|---|---|---|
| Maximum entries | 10 | Spec cap; keeps the list scannable |
| Maximum on-disk size | ~10 × maximum path length + JSON overhead (well under 64 KiB) | Bounded by entry count and OS path limits |
| Operation cost | O(10) canonicalization/stat checks; one small atomic write | Startup overhead far below SC-009's one second |

## Explicit Non-Goals

The record never contains: item/file names, history entries, timestamps,
filters, the current choice, previews, log paths, telemetry, machine identifiers,
or any data transmitted over a network. It never modifies, moves, renames, or
deletes target files or folders.
