# Implementation Plan: Snooze the Selected Pick

**Branch**: `009-snooze-selected-pick` | **Date**: 2026-11-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-snooze-selected-pick/spec.md`

## Summary

Add a **Snooze** action beside Undo in the terminal UI and the web UI. Snooze
removes exactly the history line written by the latest successful logged pick,
using the existing single-level undo receipt, and then adds the same item to
the existing session skipped list for the fixed ten-minute cooldown or until
the session ends. The action is a composition of the already-shipped Undo and
skip behaviors: no core, storage, HTTP, CLI, or persistent-state change is
needed.

Undo stays visible and separate. A successful Snooze consumes the single-level
undo opportunity, so Undo remains present but unavailable until the next
successful logged pick. The item moves from picked to skipped and never returns
to the remaining view, so the remaining count stays at its post-pick value
(one lower than before the pick) while the picked count drops by one and the
skipped count rises by one. Snooze refuses completely when the receipt is gone,
the current choice no longer matches it, the item no longer exists, the history
changed, or another action conflicts: no history line is removed and no skip
is created. The item is never picked again automatically, and restoring it does
not restore the removed history line. In the rare web case where the folder or
log target changes while the undo is already in flight, the completed history
removal stands but the skip is discarded instead of leaking into the new
target.

## Technical Context

**Language/Version**: Python 3.12+ (core, TUI, web); TypeScript with Vue 3.5
(frontend).

**Primary Dependencies**: Python standard library only for the core, undo, and
skip logic. Existing optional extras only: `textual>=8` for the TUI and
`fastapi>=0.115` + `uvicorn[standard]` + `pillow>=11` for the web UI. The
existing Vue frontend stack is unchanged. No new runtime dependency.

**Storage**: No new persistent storage. The history log, its archives, and the
path-memory record are unchanged. The snooze skip record exists only in the
interface that owns the session and is discarded at session end. The history
line removal is the existing atomic Undo write.

**Testing**: `pytest`/`unittest` backend suites, Textual `run_test` TUI tests,
Vitest + Vue Test Utils frontend tests, the generated API contract check, and
the frontend production build.

**Target Platform**: Linux, macOS, and Windows terminals for the TUI; a
loopback-only local web UI (`127.0.0.1`) for the browser frontend.

**Project Type**: Single Python package (`choosier/`) with a Vue frontend
(`frontend/`), served as static assets by the web adapter.

**Performance Goals**: Snooze feedback within one second. One existing undo
request, one existing browse preflight in the web UI, and the existing state
refresh. Cooldown expiry continues to use the existing one-second interface
tick; no polling, background job, or server session state is added.

**Constraints**: Offline and local-only; stdlib-only core; no new persistent
state, history format, route, or CLI behavior; the route inventory stays at
**17**; the one-shot CLI flags, output, prompts, and exit codes remain frozen;
Snooze follows the existing Undo opportunity rather than current filter
eligibility; the existing atomic history write and external-change detection
remain the safety boundary; the web action captures the target/log scope so a
skip is never added to a different scope.

**Scale/Scope**: One local user, two interactive interfaces, one latest pick
per session and target, one session skipped list bounded by the entries the
person explicitly deferred, a ten-minute cooldown, and history files bounded
by the existing rotation limit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Deterministic Selection — PASS.** Snooze does not change candidate
  ordering, tie-breaking, filtering, seed handling, or history rules. It
  removes one already-logged pick through the existing receipt and reuses the
  existing skip exclusion; a seeded pick remains reproducible for the same
  target, filters, history, seed, and skip set.
- **II. Local and Private by Default — PASS.** No network access, telemetry, or
  online service is added. The web existence preflight uses the existing
  loopback browse capability. Item names stay local and are never written to a
  new record.
- **III. User Data Is Inviolable — PASS.** Snooze never modifies, moves,
  renames, or deletes target content. Its only history write is the existing
  atomic single-line undo, triggered by an explicit control. The skip portion
  is session-only. A refused action leaves history and skips untouched.
- **IV. Shared Core, Thin Interfaces — PASS.** The shared core, services, and
  HTTP adapter are unchanged. Both interfaces compose the existing
  `HistoryService.undo` behavior and their existing session skip maps. The new
  web composition unit contains no selection or storage logic.
- **V. Verified, Boring Changes — PASS.** New TUI, undo/skip unit, snooze unit,
  ChoiceBoard, and workspace wiring tests are part of the task breakdown.
  README and CHANGELOG are updated. The full quality gate and the unchanged CLI
  suite must stay green.
- **VI. Intentional Frontend Design — PASS.** The implementation must load the
  `frontend-design` skill before styling. Snooze is a quiet secondary control
  beside Undo inside the existing graphite/amber split-flap board, not a
  redesign: it reuses the established button shape, type scale, focus ring,
  and disabled treatment. No new visual system or dependency is introduced.
- **Technical constraints — PASS.** The history format, CLI flags and exit
  codes, HTTP route inventory, and error taxonomy are unchanged. No new route,
  persistent store, schema field, or dependency is introduced.

**Gate result**: no blocking violations. The justified additions are a
client-side existence preflight and two small composition seams, tracked below.

**Post-design re-check (after research and Phase 1)**: **PASS.** The design
keeps all new state in interface memory, reuses the existing undo endpoint and
browse listing, leaves history and target content untouched except for the
explicit undo, and adds no public contract. No unresolved clarification marker
or unjustified gate failure was introduced.

## Project Structure

### Documentation (this feature)

```text
specs/009-snooze-selected-pick/
├── plan.md                        # This file
├── research.md                    # Phase 0 decisions
├── data-model.md                  # Entities, outcomes, and transitions
├── quickstart.md                  # End-to-end validation guide
├── contracts/
│   └── snooze-selected-pick.md    # Interface and compatibility contract
├── checklists/
│   └── requirements.md            # 16/16 passing
└── spec.md
```

### Source Code (repository root)

```text
choosier/
└── tui.py                         # Snooze button, sync, and action

frontend/src/
├── state/
│   ├── use-undo.ts                # Extract performUndo; keep undo wrapper
│   ├── use-skip.ts                # Add programmatic add()
│   ├── use-snooze.ts              # NEW: eligibility, preflight, composition
│   └── use-workspace.ts           # Compose snooze and expose bindings
├── view-models.ts                 # WorkspaceBinding snooze fields
├── App.vue                        # Pass bindings and Snooze event
├── views/ChoiceBoard.vue          # Snooze control beside Undo
└── styles.css                     # Shared secondary-control styling

frontend/tests/ui/
├── state/use-undo.test.ts         # performUndo behavior preserved
├── state/use-skip.test.ts         # add() record semantics
├── state/use-snooze.test.ts       # NEW: success, refusal, conflict
├── state/use-workspace.test.ts    # Binding wiring
└── views/ChoiceBoard.test.ts      # Snooze control, label, disabled state

tests/
├── test_tui.py                    # TUI success, refusal, restore, keyboard
├── test_web.py                    # Two-session receipt and skip-visibility shape
├── test_api_contract.py           # Route inventory and undo/pick contract guard
└── test_cli.py                    # Additive no-snooze CLI guard

README.md                          # User-visible Snooze documentation
CHANGELOG.md                       # Unreleased entry
```

**Structure Decision**: Keep the existing single-package + Vue frontend layout
and make no core or route change. The terminal UI composes its existing
`HistoryService.undo` call and `_skips` map directly. The web UI adds one
session-scoped composition unit, `useSnooze`, that consumes the refactored
`useUndo.performUndo` and the new `useSkip.add`; `useWorkspace` only wires the
units together. This keeps the combined behavior in one place per interface
without duplicating storage, selection, or skip logic in the core.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| Client-side existence preflight before the undo request | The spec requires refusing when the picked item was deleted or renamed, while the existing undo endpoint intentionally checks only the history receipt. | A combined atomic "snooze" endpoint or an undo-request existence flag would expand the public HTTP contract and duplicate undo semantics, both explicitly out of scope. A post-undo existence check cannot put the removed history line back. |
| `useUndo.performUndo` extraction and `useSkip.add` | Snooze must reuse the exact undo behavior and add a skip only after the undo succeeds, without emitting Undo's status message or duplicating API/record code. | Calling the public `undo()` and reverse-engineering its status text would make Snooze depend on presentation strings and could add a skip after a refused undo; duplicating the API call and record shape in `useSnooze` would fork the undo and cooldown rules. |

## Phase 0 and Phase 1 Outputs

- [research.md](./research.md) resolves the composition, eligibility,
  existence-check, refusal, and concurrency decisions.
- [data-model.md](./data-model.md) defines the latest-pick receipt, snooze
  eligibility and outcome, the session skipped entry, and the transitions.
- [contracts/snooze-selected-pick.md](./contracts/snooze-selected-pick.md)
  defines the TUI and web control behavior, messages, and unchanged API/CLI
  boundaries.
- [quickstart.md](./quickstart.md) defines the automated and manual validation
  scenarios for both interfaces and the unchanged CLI.
