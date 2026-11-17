# Implementation Plan: Skip and Snooze

**Branch**: `008-skip-snooze` | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-skip-snooze/spec.md`

## Summary

Add a session-only **Not now** action to the terminal UI and the web UI. A
currently eligible remaining entry can be deferred without being treated as
picked: it leaves the remaining pool and is excluded from picks for the earlier
of a fixed ten-minute cooldown or the end of the current session. Skip state
lives only in the interface that owns the session, scoped to the active target
folder and history-log setting, and is passed as an explicit input to the
shared state and pick functions. The interfaces show skipped entries separately
with their return time, offer per-entry restore and restore-all, and report a
distinct all-skipped outcome when every eligible entry is deferred. Skipping
never writes, rewrites, or removes a history line and never changes target
content, filters, path memory, or the one-shot command line.

## Technical Context

**Language/Version**: Python 3.12+ (core, TUI, web); TypeScript with Vue 3.5
(frontend).

**Primary Dependencies**: Python standard library only for the core and skip
logic. Existing optional extras only: `textual>=8` for the TUI and
`fastapi>=0.115` + `uvicorn[standard]` + `pillow>=11` for the web UI. No new
runtime dependency.

**Storage**: No new persistent storage. The history log, its archives, and the
path-memory record are unchanged. Skip records exist only in process or browser
memory and are discarded at session end.

**Testing**: `pytest`/`unittest` backend suites, FastAPI `TestClient` route and
contract tests, Textual `run_test` TUI tests, Vitest + Vue Test Utils frontend
tests, the generated API contract check, and the frontend production build.

**Target Platform**: Linux, macOS, and Windows terminals for the TUI; a
loopback-only local web UI (`127.0.0.1`) for the browser frontend.

**Project Type**: Single Python package (`choosier/`) with a Vue frontend
(`frontend/`), served as static assets by the web adapter.

**Performance Goals**: Skip, restore, and restore-all feedback within one
second. State and pick requests stay linear in the candidate count plus the
bounded active-skip count. Expiry is reflected without a manual reload while
the interface is open.

**Constraints**: Offline and local-only; stdlib-only core; no persistent skip
state; additive HTTP fields only; one-shot CLI flags, output, prompts, and exit
codes frozen; skip never writes history or target content; skip state is
independent per interface session.

**Scale/Scope**: One local user, two interactive interfaces, a skip list bounded
by the eligible entries the person explicitly deferred, a ten-minute cooldown,
and history files bounded by the existing rotation limit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Deterministic Selection — PASS, with a documented extra input.** Skip
  does not change candidate ordering, tie-breaking, filtering, history rules, or
  the seed algorithm. For a fixed target, filter selection, seed, history, and
  active skip set, a seeded pick remains reproducible. The active skip set is an
  explicit, visible, session-only input, like a filter selection; it is not a
  hidden source of randomness. The added input is tracked under Complexity
  Tracking.
- **II. Local and Private by Default — PASS.** No network access, telemetry, or
  online service is added. Skip names already come from the local target and
  cross only the existing loopback HTTP boundary. They are never written to the
  history log, path memory, or any other record.
- **III. User Data Is Inviolable — PASS.** Skip, restore, restore-all, expiry,
  pruning, and target changes perform no history write and no target mutation.
  The core only scans candidates and checks whether a skipped name still exists.
  Existing history actions, atomic writes, archives, and confirmation rules are
  untouched.
- **IV. Shared Core, Thin Interfaces — PASS.** Skip normalization and the
  exclusion of deferred entries from remaining/pick results live in
  `choosier/skip.py` and the shared service functions. The TUI and web adapter
  only own their session clocks, timers, controls, and messages.
- **V. Verified, Boring Changes — PASS.** Core, service, API contract, TUI, and
  frontend tests are part of the task breakdown. README and CHANGELOG are
  updated. The full existing quality gate must stay green, and the CLI suite
  must pass unchanged.
- **VI. Intentional Frontend Design — PASS.** The `frontend-design` skill was
  loaded before any styling decision. Skip is a quiet secondary action inside
  the existing graphite/amber split-flap board and side-panel chrome, not a
  redesign; it inherits the established palette, type scale, focus ring, and
  disabled treatment. The new controls spend no visual boldness beyond the
  existing Pick lever.
- **Technical constraints — PASS.** The history format, CLI contract, route
  inventory, and error taxonomy are unchanged. The HTTP change is additive:
  optional request fields on `POST /api/state` and `POST /api/pick`, additive
  state-response fields, and one new pick status. No new route, error code,
  dependency, or persistent store is introduced.

**Gate result**: no blocking violations. The justified complexity additions are
tracked below.

**Post-design re-check (after research and Phase 1)**: **PASS.** The design
keeps skip state entirely in interface memory, leaves history and target content
untouched, keeps the core time-free and UI-agnostic, and adds only documented
additive API fields. The skipped view is derived from existing state refreshes
plus a small interface timer, so no background process or server session store
is introduced. No new clarification marker or unjustified gate failure was
introduced by the design.

## Project Structure

### Documentation (this feature)

```text
specs/008-skip-snooze/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Skip entities, counts, and transitions
├── quickstart.md        # End-to-end validation guide
├── contracts/
│   └── skip-snooze.md   # Additive API and interface contract
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Created by /speckit.tasks
```

### Source Code (repository root)

```text
choosier/
├── skip.py              # NEW: SkipSelection, normalization, cooldown constant
├── filters.py           # Reusable entry-name validation for skip requests
├── services/
│   ├── models.py        # StateSnapshot skip fields; PickStatus all_skipped
│   ├── state.py         # Exclude skips; report skipped/present/all-skipped
│   └── pick.py          # Exclude skips; return all_skipped
├── web.py               # Additive state/pick request and response fields
└── tui.py               # Skip map, expiry tick, Remaining tab controls

frontend/
├── scripts/generate-api-contract.mjs   # Unchanged; contract regeneration
├── src/
│   ├── api-contract.generated.ts       # Regenerated, not hand-edited
│   ├── types.ts                        # Skip request/response aliases
│   ├── view-models.ts                  # Skip binding and row types
│   ├── state/
│   │   ├── use-skip.ts                 # NEW: session records, cooldown, reconcile
│   │   ├── use-picker.ts               # Send skips; guard overlap; all_skipped
│   │   ├── use-workspace-state.ts      # Send skips; prune from state response
│   │   └── use-workspace.ts            # Compose skip, reset, and reconcile wiring
│   ├── views/RemainingPanel.vue        # Skip/restore controls and skipped list
│   ├── views/ChoiceBoard.vue           # No markup change expected; consumes the skip-aware total
│   ├── App.vue                         # Wire the panel bindings and events
│   └── styles.css                      # Secondary action and skipped-row styling
└── tests/ui/
    ├── state/use-skip.test.ts          # NEW
    ├── state/use-picker.test.ts
    ├── state/use-workspace-state.test.ts
    ├── state/use-workspace.test.ts
    └── views/RemainingPanel.test.ts

tests/
├── test_skip.py                        # NEW: normalization, bounds, cooldown
├── test_services_state.py              # Remaining exclusion, counts, pruning
├── test_services_pick.py               # all_skipped and unchanged outcomes
├── test_web.py                         # State/pick skip fields and outcomes
├── test_api_contract.py                # Additive schema and enum checks
├── test_api_errors.py                  # Malformed skip payloads
├── test_tui.py                         # Controls, expiry, restore, messages
└── test_history_consistency.py         # History/target/CLI unchanged

specs/001-standardize-api-responses/contracts/
├── api-contract.json                   # Authoritative route contract
└── api-contract.md                     # Human-readable inventory
```

**Structure Decision**: Keep the existing single-package + Vue frontend layout.
Skip is a small shared concept, so its validation and cooldown constant live in
one new stdlib-only module, `choosier/skip.py`, while the existing state and
pick services own the selection effects. The TUI and web adapter remain thin:
they hold the in-memory skip records, run their own expiry tick, and render the
shared results. No server session store, new route, or new layer is introduced.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Active skip set as an additional input to state and pick selection | The feature's core promise is to keep a deferred entry out of the pool without writing history or changing filters. The shared picker must know which names are temporarily deferred. | Reusing history writes would treat a skip as a pick and violate history immutability; reusing filters would make the exclusion last the whole session, require the filter UI to represent it, and lose the distinct all-skipped outcome; filtering only in each adapter would duplicate selection logic and break TUI/web parity. |
| Additive skip fields on `POST /api/state` and `POST /api/pick` | The browser must carry its session skip state to the shared core on every state and pick request, and the core must report which skips are displayable, which still exist, and whether all eligible entries are skipped. | A server-side skip store would be shared across tabs and reloads, violating per-session independence; a new skip route would add public surface without adding server state; deriving skip data from history would make skip look like a history record. |
