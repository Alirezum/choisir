# Phase 0 Research: Remembered Folder Paths

**Feature**: 006-remember-path | **Date**: 2026-11-11

This document resolves the open technical decisions for the path-memory
feature. All decisions respect the constitution: standard library only,
local-only storage, no telemetry, and no change to one-shot CLI behavior.

## R1. Storage location

**Decision**: Store the record in an OS-appropriate per-user config directory:

| Platform | Default path |
|---|---|
| Windows | `%APPDATA%\choosier\path-memory.json` (fallback: `~/.config/choosier/path-memory.json`) |
| macOS | `~/Library/Application Support/choosier/path-memory.json` |
| Linux/other | `$XDG_CONFIG_HOME/choosier/path-memory.json`, else `~/.config/choosier/path-memory.json` |

`CHOOSIER_PATH_MEMORY_FILE` overrides the location when set (primarily for
tests, portable setups, and users who relocate config). The parent directory is
created with `0o700` where supported and the file is written with `0o600` on
POSIX. The record is never placed inside a target folder.

**Rationale**: The record is user-scoped state, not project state; it must be
shared by the TUI and web UI and survive folder changes. Standard-library
platform detection avoids the `platformdirs` dependency. Keeping it out of the
target directory also prevents it from appearing as a pick candidate or
polluting the user's project.

**Alternatives considered**:
- *Target folder file (`<target>/.choosier-paths.json`)*: rejected because
  recents must work without a target and must span folders.
- *History-log sidecar (`.choosier.jsonl.paths`)*: rejected because custom
  `--log-file` and per-folder logs would fragment memory and leak path data into
  project directories.
- *OS keyring / registry*: rejected as platform-specific and overkill for
  non-secret path strings; also adds failure modes.
- *`platformdirs` dependency*: rejected under Principle IV (new core
  dependency requires an amendment).

## R2. On-disk format and versioning

**Decision**: A single UTF-8 JSON object:

```json
{
  "version": 1,
  "recent": [
    "/home/ana/work/project-b",
    "/home/ana/work/project-a"
  ]
}
```

`recent` is ordered newest first; the array order is the only recency
information. No timestamps, item names, history, filters, or machine IDs are
stored. A missing file means empty memory. A malformed file is treated as empty
with a non-blocking warning; the next successful record replaces it atomically.
Unknown entries that are not non-empty strings are discarded during load.

**Rationale**: JSON is human-inspectable, trivially testable, and already used
by the history log. A version field gives a migration point without adding
metadata. Order-as-recency avoids clock skew and timestamp ambiguity across
processes.

**Alternatives considered**:
- *JSON Lines*: history already uses JSONL, but a single small document
  rewrites more cleanly and cannot be partially appended.
- *SQLite*: new dependency/complexity and overkill for ten strings.
- *INIREADER/TOML*: standard-library writers are awkward for ordered lists, and
  `tomllib` is read-only.
- *Timestamps per entry*: unnecessary; ordering is authoritative and avoids
  cross-process clock issues.

## R3. Canonical path identity

**Decision**: Canonicalize every recorded or compared folder with
`Path(value).expanduser().resolve()` (non-strict) and store the resulting
absolute path string. Deduplicate with `os.path.normcase` of that string so
case-insensitive platforms collapse equivalent spellings. Trailing separators,
`.`/`..` segments, and symlinks therefore map to one entry. The stored display
value is the resolved path.

**Rationale**: FR-014 requires equivalent spellings to be one remembered
location. Resolving once at write time means the list, startup resolution, and
remove action all compare canonical values. `normcase` handles Windows
case-insensitivity without changing the displayed path on POSIX.

**Alternatives considered**:
- *Store the typed string verbatim*: duplicates the same folder under multiple
  spellings and complicates removal.
- *`os.path.realpath` string handling*: equivalent to `Path.resolve()` but less
  consistent with the rest of the codebase, which uses `Path`.
- *Case-fold all stored paths*: would corrupt mixed-case display names on
  case-sensitive filesystems.

Broken or vanished symlinks resolve to their target text and are then pruned by
the availability check.

## R4. Availability and pruning

**Decision**: A remembered path is usable only when it is a directory and can be
opened for listing:

```python
path.is_dir() and os.scandir(path).close()  # wrapped in try/except OSError
```

`list_recent()` walks the stored order, keeps usable entries, writes the pruned
list back atomically when anything was removed, and returns the valid entries
plus an optional warning. Startup uses the first valid entry; if none remain it
returns the caller's default. Pruning is automatic and never surfaces dead rows.

**Rationale**: `is_dir()` alone can succeed while permission is denied; opening a
scandir handle verifies read access. Pruning on every list/startup read keeps
the store honest even when a drive is unmounted or a folder is deleted by
another process.

**Alternatives considered**:
- *Check only at startup*: dead rows could remain in a long-running web session.
- *Keep unavailable entries marked in the UI*: the clarified spec requires
  automatic removal, and dead rows add interaction cost.
- *Check on every render*: wasteful; refresh boundaries are deterministic.

## R5. Atomic writes and cross-process locking

**Decision**: Serialize every read-modify-write operation with an exclusive lock
on a sibling `<memory>.lock` file:

- POSIX: `fcntl.flock(fd, fcntl.LOCK_EX)` (released automatically on process
  exit or crash).
- Windows: `msvcrt.locking(fd, msvcrt.LK_LOCK, 1)`.

Inside the lock, read the current document, apply the mutation, write a temp
file in the same directory, `flush`, `fsync`, `os.replace`, and best-effort
`chmod 0o600`. Temporary files are removed on failure. Read-only listing also
takes the exclusive lock when it might prune; a shared lock is not necessary at
this scale.

If locking or I/O fails, the operation degrades: picks still work, memory is
left untouched where possible, and the adapter shows a non-blocking notice.

**Rationale**: Two interfaces can be open at once (FR-015). Atomic replacement
alone prevents truncation but not lost updates; the lock makes
read-modify-write linearizable. OS locks release on crash, avoiding stale
lockfiles.

**Alternatives considered**:
- *`O_CREAT | O_EXCL` lockfile*: portable but stale after a crash and requires
  PID/timeout heuristics.
- *Atomic replace without a lock*: last writer wins and can drop a concurrent
  pick from another session.
- *In-process `threading.Lock` only*: does not protect separate TUI/web
  processes.

## R6. Startup resolution and explicit-path precedence

**Decision**:

- If a launch path is supplied (non-empty after argument parsing), it is used
  verbatim. Memory is not consulted, even when the explicit path is invalid.
- TUI: an empty `initial_path` triggers resolution on mount; if no valid recent
  exists the path input stays empty, preserving today's first-run behavior.
- Web: `create_app(initial_path="")` resolves on app construction. If no valid
  recent exists it falls back to `str(Path.cwd())`, preserving today's `--web`
  default. If an explicit path is given, the defaults endpoint returns it
  unchanged.
- `choosier --web` without a path now passes `""` instead of eagerly
  substituting cwd, so the web layer can resolve memory first.
- The resolved path and any warning are returned by `GET /api/defaults`.

Warnings are plain, non-modal messages such as `Skipped 1 unavailable remembered
folder; using /next/folder.` They never block startup or picking.

**Rationale**: Resolution belongs in the adapters' startup path because only
they know their historical default (empty input for TUI, cwd for web). The core
module accepts the default as a parameter, keeping it UI-agnostic.

**Alternatives considered**:
- *Resolve inside `services.pick`*: would affect one-shot CLI behavior and
  couple selection to startup policy.
- *Resolve in `cli.py` for both UIs*: TUI and web have different defaults and
  the TUI is also constructed directly in tests.
- *Fall back to cwd for TUI*: changes today's first-run behavior.

## R7. Recording point

**Decision**: Record only in the interactive adapters, immediately after
`services.pick` returns `status == "picked"` (including dry-run):

- TUI: in `do_pick`, before `_finish_pick`.
- Web: in the `POST /api/pick` route after a successful outcome; include an
  optional `path_memory_notice` in the response when recording fails.
- One-shot CLI: never records, preserving every flag, output line, and exit code.

Recording uses the canonical target folder, not the chosen item. Failed,
empty, exhausted, filtered-empty, filtered-exhausted, and invalid-path outcomes
do not record.

**Rationale**: `services.pick` is shared by all three interfaces (Principle I),
and only the interactive adapters are in scope. A post-success hook keeps pick
logic unchanged and makes the invocation explicit and testable.

**Alternatives considered**:
- *Record inside `services.pick` behind a flag*: easy to misuse and risks
  changing CLI behavior; conflates selection and session memory.
- *Record on path-input change or folder browse*: rejected by the clarified
  spec; abandoned browsing must not displace recency.

## R8. Web API surface

**Decision**: Additive changes only:

- Extend `GET /api/defaults` with `path_warning: string | null`; `path` now
  carries the resolved startup path when no explicit path was supplied.
- Add `GET /api/paths` →
  `{"recent": string[], "warning": string | null}`. Listing validates and
  prunes stale entries.
- Add `DELETE /api/paths` → `{"cleared": boolean}`.
- Add `DELETE /api/paths/item?path=<value>` →
  `{"path": string, "removed": boolean}`. The query parameter is required;
  missing or empty values produce the standard `validation_error` envelope.
- Extend `POST /api/pick` with `path_memory_notice: string | null`.

Update `specs/001-standardize-api-responses/contracts/api-contract.json`
(13 → 16 routes), adjust the route-count assertion, regenerate
`frontend/src/api-contract.generated.ts`, and add the operation names to
`frontend/src/api-operations.ts` and facade methods to `frontend/src/api.ts`.

Remove/clear never alter the active path in a running session; the frontend
leaves `options.path` untouched and only refreshes the recent list.

**Rationale**: A dedicated collection resource keeps the recent list refreshable
after picks and destructive actions without overloading `/api/defaults`. All
changes are backward-compatible; the contract JSON remains the single source of
truth and its drift tests enforce parity.

**Alternatives considered**:
- *Bundle recents into `/api/defaults`*: bootstrap-only and requires re-fetching
  unrelated defaults after every change.
- *Use `POST /api/paths/remove` with a body*: `DELETE` on an item resource is
  simpler and consistent with `DELETE /api/history/item`.
- *Remove via `POST /api/paths` mutation commands*: less discoverable and
  weaker HTTP semantics.

## R9. Recent-list UI placement and accessibility

**Decision**:

- **TUI**: Add a "Recent folders" section to the Options tab containing a
  keyboard-focusable `OptionList` of full paths plus `Use`, `Remove`, and
  `Clear recent` buttons. `Use` sets the path input (normal refresh follows);
  `Remove` acts on the highlighted row; `Clear recent` requires no confirmation
  because it only affects memory and is immediately visible. Status-line
  messages report each action.
- **Web**: Add a "Recent folders" section to the Options panel: a list of
  buttons whose labels are the full paths (selecting one sets the path), a
  per-row "Remove" button with an `aria-label` naming the folder, and a "Clear
  recent folders" button. Use `aria-live="polite"` for action feedback, native
  buttons for focus/keyboard support, and preserve the existing focus-visible
  styling language.
- The web path memory state is a new `usePathMemory` unit that loads on
  bootstrap, refreshes after successful picks and remove/clear actions, and
  exposes `recent`, `warning`, `remove`, and `clear`.

Implementation must load `.agents/skills/frontend-design/SKILL.md` and apply its
plan/review/build/critique process before making visual decisions
(Constitution VI).

**Rationale**: Options is already the place for folder-scoped settings and has
room for a list in both surfaces. Full-path labels satisfy unambiguous
identification; native controls provide keyboard and screen-reader support
without custom widgets. Keeping memory actions out of the topbar avoids
accidental clicks near the primary path input.

**Alternatives considered**:
- *Topbar dropdown*: cramped for full paths and risks path-input focus conflicts.
- *New tab*: over-promotes a secondary convenience and adds navigation cost.
- *Browser-panel list*: conflates navigation with memory management.

## R10. Failure and degradation policy

**Decision**: Memory failures never block picks:

| Failure | Behavior |
|---|---|
| File missing | Empty memory; normal first-run behavior |
| Malformed JSON / wrong shape | Treat as empty; warn; replace on next successful record |
| Unreadable/unwritable file or directory | Skip memory; warn; pick proceeds |
| Lock unavailable / I/O error | Skip the memory mutation; warn; pick proceeds |
| Stale folder | Prune; use next valid recent; otherwise caller default |
| Unknown future `version` | Treat as empty; warn; do not crash |

Warnings are short, local, and non-modal: TUI status line, web status bar via
`path_warning`/`path_memory_notice`, and action feedback. They do not expose
file contents or history.

**Rationale**: FR-010/FR-011 require graceful degradation. A convenience
feature must never turn into a pick blocker or data-loss path.

## R11. Documentation and governance

**Decision**: Amend the constitution to v1.3.0 (MINOR) before implementation:

- Principle III gains an explicit, bounded exception for a user-scoped path
  memory record: local-only, folder paths and ordering only, atomic writes,
  clearable, never containing file names, choices, or history.
- Technical Constraints note the versioned JSON record and its OS-appropriate
  location.
- Amendment date becomes 2026-11-11; rationale is recorded in the amendment.

Update `README.md` (launch behavior, recent list, privacy/clear actions) and
`CHANGELOG.md` under the next unreleased minor. No CLI flag documentation
changes; document that `--web` without a path now prefers a remembered folder
and otherwise keeps the cwd default.

**Rationale**: Governance requires a documented rationale and semantic version
bump for materially expanded principles. User-visible behavior requires README
and CHANGELOG updates per Principle V.
