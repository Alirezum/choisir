# Implementation Plan: Remembered Folder Paths

**Branch**: `006-remember-path` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-remember-path/spec.md`

## Summary

Add a small, user-scoped path-memory record shared by the terminal UI and the
web UI. After a successful pick (including dry-run), the active folder is
recorded as the most recent of at most ten unique folders. On launch without an
explicit path, the first valid recent folder is used; stale entries are pruned
and startup continues with the next valid entry or today's default. Both
interactive interfaces expose the recent list for one-action switching and
provide remove-one and clear-all actions. The one-shot CLI is unchanged.

The implementation adds a standard-library-only `choosier/path_memory.py` core
module, adapter hooks after successful picks in `choosier/tui.py` and
`choosier/web.py`, three additive HTTP routes plus optional response fields, and
a recent-folder section in both interactive interfaces. The constitution is
amended to v1.3.0 (MINOR, ratified 2026-11-11) to permit this narrowly scoped
persistent state.

## Technical Context

**Language/Version**: Python 3.12 (backend/core), TypeScript 5 / Vue 3 (web UI)

**Primary Dependencies**: Standard library for path memory; FastAPI for the web
adapter; Textual for the TUI; existing Vue/Vite frontend. No new runtime
dependency is introduced.

**Storage**: One versioned JSON document (`{"version": 1, "recent": [...]}`)
in an OS-appropriate user config directory. Atomic temp-file + `os.replace`
writes, `fsync`, POSIX `0o600` file mode, and a sibling lock file using
`fcntl.flock` (POSIX) or `msvcrt.locking` (Windows) for cross-process updates.

**Testing**: `unittest` via pytest (Python), Vitest (frontend unit/UI),
existing API contract/drift tests, plus the Python quality gates
(`ruff`, `ruff format --check`, `mypy`).

**Target Platform**: Linux, macOS, and Windows; local-only operation.

**Project Type**: Single Python package with a colocated Vue frontend.

**Performance Goals**: Memory load, prune, record, remove, or clear completes in
well under 50 ms for ten paths; startup adds no more than one second (SC-009).

**Constraints**: No network, no telemetry, no new dependencies; paths only —
no file names, history, filters, or choices; explicit launch paths always win;
the one-shot CLI's flags, output, and exit codes are unchanged; `--web` without
a path resolves memory before falling back to cwd; keyboard-operable UI with
visible focus; web UI remains loopback-only.

**Scale/Scope**: At most ten remembered folders per user/machine; two
interactive surfaces plus additive HTTP routes; one shared core module.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / constraint | Status | Notes |
|---|---|---|
| I. Deterministic Selection | PASS | Pick algorithm, seeds, ordering, filters, and history semantics are untouched. Recording happens after a pick succeeds and cannot change the chosen item. |
| II. Local and Private by Default | PASS | The record is local-only, contains folder paths only, and is never transmitted. No telemetry. Web binding stays `127.0.0.1`. |
| III. User Data Is Inviolable | PASS | v1.3.0 (2026-11-11) permits the user-scoped path-memory record with explicit limits: local-only, paths and ordering only, atomic writes, clearable, never touching target content. |
| IV. Shared Core, Thin Interfaces | PASS | New standard-library-only `choosier/path_memory.py` shared by TUI and web; no new core dependency; UI extras remain optional. |
| V. Verified, Boring Changes | PASS | Unit, adapter, contract, frontend, and regression tests planned; README/CHANGELOG updates; small reversible change. |
| VI. Intentional Frontend Design | PASS WITH PROCESS | The recent-folder section is a visual change; implementation must load and apply `.agents/skills/frontend-design/SKILL.md` before styling decisions. No design-system dependency. |
| Technical constraints | PASS | History remains the only pick-state log; HTTP changes are additive and documented; CLI flags/exit codes unchanged; keyboard operation retained. |
| Public contracts | PASS | New routes and optional response fields are backward-compatible. The authoritative contract JSON, frontend generated contract, and contract tests are updated in the same change; no client migration is required. |

**Gate result**: PASS. The v1.3.0 amendment is ratified, so no gate remains
blocked. No unjustified complexity remains.

## Project Structure

### Documentation (this feature)

```text
specs/006-remember-path/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── path-memory.md   # Core module behavior contract
│   └── web-paths.md     # Additive HTTP routes and fields
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks, not created here)
```

### Source Code (repository root)

```text
choosier/
├── path_memory.py              # NEW: shared standard-library path memory
├── cli.py                      # pass "" for --web when no explicit path
├── tui.py                      # startup resolution, record hook, recent UI
├── web.py                      # startup resolution, record hook, path routes
└── services/
    └── pick.py                 # unchanged; adapters record after "picked"

frontend/src/
├── api.ts                      # add paths/removePath/clearPaths facade calls
├── api-operations.ts           # add operation-name mappings
├── api-contract.generated.ts   # regenerate from the contract JSON
├── types.ts                    # derive updated response types
├── App.vue                     # pass the new binding into OptionsPanel
├── state/
│   ├── use-path-memory.ts      # NEW: recent list state/actions
│   ├── use-workspace.ts        # compose the new state unit
│   ├── use-workspace-state.ts  # unchanged
│   ├── use-bootstrap.ts        # apply startup warning; load recent list
│   └── use-picker.ts           # refresh recent list after a successful pick
└── views/
    └── OptionsPanel.vue        # recent-folder list, remove, clear

frontend/scripts/
└── generate-api-contract.mjs   # add new response type names

tests/
├── test_path_memory.py         # NEW: unit + cross-process locking tests
├── test_web.py                 # extend route/behavior tests
├── test_tui.py                 # extend startup/record/UI tests
├── test_cli.py                 # adjust --web default-path expectation
├── test_api_contract.py        # 13 → 16 routes and new schemas
└── api_contract_support.py     # unchanged helpers

specs/001-standardize-api-responses/contracts/api-contract.json
                                # authoritative additive contract update

frontend/tests/
├── api-contract.test.mjs       # generated-contract drift expectations
└── ui/
    ├── test-helpers.ts         # new API mock methods
    ├── state/use-path-memory.test.ts   # NEW
    ├── state/use-bootstrap.test.ts     # startup warning/recent load
    ├── state/use-picker.test.ts        # refresh after successful pick
    └── views/OptionsPanel.test.ts      # recent list actions/a11y

.specify/memory/constitution.md # v1.3.0 amendment
README.md, CHANGELOG.md         # user-visible documentation
```

**Structure Decision**: Keep the existing single-package layout. Path memory is
a standard-library core module beside `storage.py`; TUI and web remain thin
adapters over it. The frontend keeps its state-unit/view split and adds one
state unit plus one Options-panel section.

## Phase 0: Research Outputs

`research.md` resolves storage location, on-disk format, canonical path
identity, atomic concurrent updates, startup fallback/pruning, adapter recording
points, HTTP surface, and recent-list placement/accessibility.

## Phase 1: Design Outputs

- `data-model.md`: remembered record, recent list invariants, validation and
  state transitions.
- `contracts/path-memory.md`: core module behavior, errors, and concurrency.
- `contracts/web-paths.md`: additive routes, fields, statuses, and errors.
- `quickstart.md`: end-to-end TUI, web, API, concurrency, and privacy checks.

## Post-Design Constitution Re-check

| Gate | Result |
|---|---|
| I. Deterministic Selection | PASS — no selection logic change |
| II. Local and Private by Default | PASS — paths-only local file, no network |
| III. User Data Is Inviolable | PASS — v1.3.0 amendment ratified; memory is separate from targets and history, atomic, clearable |
| IV. Shared Core, Thin Interfaces | PASS — one standard-library module, adapters only |
| V. Verified, Boring Changes | PASS — tests and docs included in scope |
| VI. Intentional Frontend Design | PASS — skill-driven UI work required before styling |
| Public contracts | PASS — additive routes/fields, contract and generated client updated together |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| New persistent state beyond the history log (Principle III) | Restoring the last folder and a shared recent list requires a durable record that outlives a session and spans UI processes. | Session-only memory fails the core user story; storing inside target folders fragments memory and pollutes projects; adding a database or keyring is heavier and platform-specific. Mitigation: v1.3.0 MINOR amendment limits the record to local folder paths, ten entries, atomic writes, and user-clearable storage. |

No other violations remain. The new record is deliberately the smallest
possible exception: one JSON document, ten path strings, no file metadata, and
no new dependency. The v1.3.0 amendment is ratified and recorded by T001.
