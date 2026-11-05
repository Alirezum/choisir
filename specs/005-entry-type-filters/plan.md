# Implementation Plan: File-Type and Entry Filters

**Branch**: `005-entry-type-filters` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-entry-type-filters/spec.md`

## Summary

Add a shared, session-scoped eligibility filter to the chooser so a person can
restrict a random pick to exact file types and individual folder entries. The
filter is derived from the target folder, combines with the existing hidden and
files/folders options, and is applied by the same UI-agnostic selection logic
used by the TUI and web UI. The TUI and web options areas get paired type and
entry checklists, an active-filter summary, select-all/clear actions, and a
single reset. The one-shot CLI keeps its current behavior.

The implementation keeps the filter model in the standard-library core,
returns filter options and filtered totals through an additive state endpoint,
and keeps all filter state in the interactive client for the session. The API
gains one additive route (`POST /api/state`) with a JSON body so large
exclusion sets are not squeezed into a URL; the existing `GET /api/state`
remains unchanged for compatibility.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 6 and Vue 3.5 on the frontend.

**Primary Dependencies**: Python standard library for the core; FastAPI,
uvicorn, and Pillow as the existing optional `web` extra; Textual as the
existing optional `ui` extra; Vue, Vite, Vitest, and Vue Test Utils as existing
frontend development dependencies. No new runtime dependency is introduced.

**Storage**: Existing JSON Lines history log at `<target>/.choosier.jsonl`.
Filter selection is not persisted; no new storage format is introduced.

**Testing**: Python `unittest`/`pytest`; Vitest and Vue Test Utils for the
frontend; existing API contract, API boundary, UI boundary, and generated
contract checks. Static-serving tests still require a frontend build.

**Target Platform**: Local Linux, macOS, and Windows CLI/TUI; local-only web UI
on `127.0.0.1`.

**Project Type**: Single Python package with a CLI, a Textual TUI, and a local
FastAPI service serving a Vue single-page frontend.

**Performance Goals**: Filtered state refresh becomes visible within one
second; a folder with 5,000 entries opens the filter menu with accurate totals
within two seconds; the state payload and rendered entry list remain bounded.

**Constraints**: All filtering is local and read-only; no network, telemetry,
or new service. The core stays standard-library-only. Public API changes are
additive and documented. Filter state is folder- and session-scoped. Both
interactive interfaces remain keyboard-operable with visible focus. The entry
checklist is capped at 1,000; the type checklist is complete and targets at
most 200 distinct types. Entry exclusions outside the visible cap are preserved
through the state response's `known_entry_exclusions` set. Applying or clearing
filters preserves the current choice; path/log changes reset filters and keep
each interface's existing current-choice behavior.

**Scale/Scope**: Single local user; folders with thousands of direct children;
one new shared filter model, one new service endpoint route, two options-panel
surfaces, and their tests. Recursive selection, saved presets, content-based
MIME classification, and CLI filter flags are out of scope.

## Frontend State and API Contracts

These names are fixed for the implementation and tests:

| Concept | Name | Notes |
|---|---|---|
| Existing folder options | `FolderFlags` / `folderFlags` | Rename the old `FilterSelection`/`filters` computed. Wire fields stay `include_hidden`, `files_only`, `dirs_only`. |
| New type/entry exclusions | `FilterExclusions` | `excluded_types` and `excluded_entries` arrays. |
| Filter state unit | `useFilters` returning `FilterBinding` | Owns exclusions, revision, reconciliation, summary, and actions. |
| Exposed view model | `filterPanel` | `ComputedRef<FilterPanelModel>`; not named `filters`. |
| State binding type | `FilteredStateResponse` | Includes `filter_options` and `known_entry_exclusions`; never type the binding as `StateResponse`. |
| Pick request type | `PickRequest` | Gains optional `excluded_types` and `excluded_entries`; existing fields remain. |
| Entry reconciliation | `known_entry_exclusions` | Server-reported sorted subset of requested names that still match current candidates, including entries outside the 1,000 cap. |

`useWorkspaceState` and `usePicker` merge `folderFlags` with `filterExclusions`
in their request bodies. The filter summary uses the state response's
`remaining_total` for eligible entries and `filter_options.entries_total` for
the base total, so history and non-visible exclusions are reflected. Validation
and normalization are owned by `choosier.filters.normalize_exclusions`; the web
request models call it and services accept an already-normalized
`FilterSelection`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / constraint | Gate | Status | Evidence |
|---|---|---|---|
| I. Deterministic Selection | Filtering must use one shared candidate set and the existing seeded RNG; history must still prevent repeats | PASS | Filter rules live in the core; sorted candidate selection and existing RNG are preserved; tests cover seeded filtered sequences |
| II. Local and Private by Default | No new network or telemetry; web stays loopback-only | PASS | Filtering is local filesystem work; no new services or outbound calls |
| III. User Data Is Inviolable | Filtering must not create, modify, move, rename, or delete entries; history writes stay atomic | PASS | Filtering only narrows read-only candidates; history methods remain the only writer |
| IV. Shared Core, Thin Interfaces | Filter logic must be UI-agnostic and standard-library-only; TUI/web must remain adapters | PASS | New core filter module and chooser filtering; TUI and web only pass exclusions and render options |
| V. Verified, Boring Changes | Tests for every behavior, strict Python gates, frontend build, README/CHANGELOG updates | PASS | Planned unit, service, API-contract, TUI, and frontend tests; docs updated; smallest reversible change |
| VI. Intentional Frontend Design | Frontend visual work must load and follow the `frontend-design` skill | PASS | Skill loaded during planning; implementation reuses the existing Options panel language, typography, palette, and focus treatment rather than redesigning |
| Technical constraints | Core has no mandatory dependency; API shape changes are documented; no archive extraction; keyboard access | PASS | No new dependency; `POST /api/state` is additive with an explicit migration note, the GET contract is unchanged, and the API contract is updated; no archive behavior changes; native checkboxes and Textual selection lists are keyboard-operable |
| Development workflow | Atomic commits; full quality gate; verify through every affected interface | PASS | Tasks will be committed per logical change; TUI and web both verified; full gate listed in quickstart |

No violations require justification. The one additive API route is documented
because it is the smallest safe way to carry potentially large filter sets
without changing the existing route.

## Project Structure

### Documentation (this feature)

```text
specs/005-entry-type-filters/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── filter-api.md    # Additive state/pick API contract
│   └── filter-ui.md     # TUI/web state and presentation contracts
├── checklists/
│   └── requirements.md  # Specification quality checklist
├── spec.md              # Feature specification
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
choosier/
├── chooser.py            # Candidate scan + filtered candidate selection
├── filters.py            # New: type keys, labels, selection-filter rules
├── storage.py            # Unchanged history I/O
├── preview.py            # Unchanged
├── launcher.py           # Unchanged
├── cli.py                # Unchanged behavior; uses default (empty) filter
├── tui.py                # Options-tab filter controls + filtered state/pick
├── web.py                # Additive POST /api/state, filter body fields, statuses
├── web_media.py          # Unchanged
└── services/
    ├── models.py         # Filter option models and extended snapshots/outcomes
    ├── state.py          # Filter options, filtered totals, bounded entry list
    ├── pick.py           # Filtered pick and new filtered statuses
    ├── history.py        # Unchanged
    ├── browse.py         # Unchanged
    ├── errors.py         # Unchanged
    └── opening.py        # Unchanged

frontend/
├── src/
│   ├── api.ts                     # Add stateFiltered facade method
│   ├── api-operations.ts          # Map POST /api/state
│   ├── api-contract.generated.ts  # Regenerated after contract update
│   ├── types.ts                   # FolderFlags, FilterExclusions, filtered request/response types
│   ├── view-models.ts             # FilterPanelModel, FolderFlags binding, view contracts
│   ├── App.vue                    # Bind filterPanel props/intents
│   ├── state/
│   │   ├── use-filters.ts         # New: exclusions, reconciliation, summary, reset
│   │   ├── use-folder-options.ts  # Existing folder flags renamed to folderFlags
│   │   ├── use-workspace.ts       # Compose the filter unit and expose filterPanel
│   │   ├── use-workspace-state.ts # POST state with folder flags plus exclusions
│   │   └── use-picker.ts          # Send folder flags plus exclusions; map filtered statuses
│   ├── views/
│   │   └── OptionsPanel.vue       # Presentation-only checklists and reset
│   ├── components/                # Existing shared presentation blocks
│   └── styles.css                 # Reuse existing tokens; add bounded list layout
└── tests/
    ├── api-contract.test.mjs      # Updated route/operation inventory and body test
    └── ui/
        ├── state/use-filters.test.ts
        ├── state/use-workspace-state.test.ts
        ├── state/use-picker.test.ts
        ├── state/use-workspace.test.ts
        └── views/OptionsPanel.test.ts

specs/001-standardize-api-responses/contracts/
├── api-contract.json              # Add POST /api/state and filter success/status fields
└── api-contract.md                # Document the additive route and semantics

tests/
├── test_filters.py                # New core filter tests
├── test_chooser.py                # Candidate scan/filter behavior
├── test_services_state.py         # Filter options, totals, bounds
├── test_services_pick.py          # Filtered outcomes and history safety
├── test_services_boundaries.py    # Confirm stdlib-only core boundary
├── test_api_contract.py           # New route/schema/status contract
├── test_api_errors.py             # Validation/error envelope for new body
├── test_web.py                    # POST state and filtered pick flows
└── test_tui.py                    # Filter controls and messages
```

**Structure Decision**: Keep the existing single-project layering. Filter
classification and eligibility rules belong in the standard-library core
(`choosier/filters.py` and `choosier/chooser.py`); `choosier/services/` maps
them into immutable snapshots and outcomes; `tui.py` and `web.py` are adapters.
On the frontend, the new `state/use-filters.ts` owns selection state and
`views/OptionsPanel.vue` stays presentation-only. This preserves the existing
`check:ui` dependency direction and test mapping.

## Phase 0: Research

Research findings are recorded in [research.md](./research.md). The decisions
cover the filter identity model, single-scan candidate processing, the
additive API route, bounded entry options, TUI/web ownership of selection
state, and reuse of the existing visual system.

## Phase 1: Design & Contracts

Design artifacts:

- [data-model.md](./data-model.md) — filter types, entry options, exclusion
  sets, `known_entry_exclusions`, snapshot/outcome additions, validation
  ownership, bounds, and state transitions.
- [contracts/filter-api.md](./contracts/filter-api.md) — additive
  `POST /api/state` contract, expanded pick body, new statuses,
  reconciliation field, validation ownership, and compatibility rules.
- [contracts/filter-ui.md](./contracts/filter-ui.md) — TUI and frontend state
  unit/view responsibilities, `FolderFlags`/`FilterExclusions`/`filterPanel`
  naming, summary counts, filter actions, reset behavior, and test mapping.
- [quickstart.md](./quickstart.md) — end-to-end validation scenarios and the
  full quality gate.

## Post-Design Constitution Re-check

| Gate | Result | Notes |
|---|---|---|
| Shared core and thin interfaces | PASS | No presentation imports in `choosier.filters`, `chooser`, or services; frontend view imports remain presentation-only |
| Deterministic selection | PASS | Filtered candidates are sorted before seeded choice; history filtering is unchanged |
| User data and history safety | PASS | No write path is added; history remains append/rewrite/archive only |
| Local/private and dependency constraints | PASS | No new dependencies or network calls |
| API contract discipline | PASS | One additive route plus additive fields/statuses with a documented migration note; the GET contract is unchanged; contract JSON, Markdown, generated client, and tests update together |
| Validation ownership | PASS | `normalize_exclusions` owns canon/limits; web validators produce 422; services accept normalized `FilterSelection`; no duplicate rule set |
| Reconciliation and bounds | PASS | `known_entry_exclusions` preserves exclusions beyond the 1,000-entry cap; type list is complete with a 200-type performance target |
| State typing and naming | PASS | `FilteredStateResponse` state binding, `PickRequest` exclusions, and `FolderFlags`/`FilterExclusions`/`filterPanel` names are fixed in the tasks |
| Frontend design discipline | PASS | Existing Options panel design reused; `frontend-design` skill loaded; no new visual language |
| Testability and interfaces | PASS | Core, service, API, TUI, and frontend test layers identified; both interactive interfaces covered; 100-pick and 200-type checks included |

## Complexity Tracking

No constitution violations. No complexity table entries are required.
