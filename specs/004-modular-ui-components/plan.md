# Implementation Plan: Modular UI Components

**Branch**: `004-modular-ui-components` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-modular-ui-components/spec.md`

## Summary

Refactor the Vue single-page web interface from one 495-line composition-and-logic
main screen plus data-aware panels into three explicit layers: domain state and
behavior units under `src/state/`, presentation-only views under `src/views/`, and
shared visual building blocks under `src/components/`. The main screen becomes a
thin composition root. Add a development-only Vitest + Vue Test Utils + happy-dom
suite for units and views, a dependency-free boundary script that rejects view
data access, shell orchestration, reverse dependencies, cycles, duplicated
scaffolds, and missing test files, a committed parity checklist, and CI gates.
Behavior, visuals, accessibility, the shared API client contract, and the Python
backend remain unchanged.

## Technical Context

**Language/Version**: TypeScript 6.0, Vue 3.5 single-file components, Node.js 22.23.1, npm 10.9.8

**Primary Dependencies**: Vue 3.5.44, Vite 8.3.4, @vitejs/plugin-vue 6.0.10, vue-tsc 3.3.13, TypeScript 6.0.3. Development-only additions: Vitest 5.1.0, @vue/test-utils 2.5.1, happy-dom 21.0.4. No new runtime dependency.

**Storage**: N/A. The browser keeps only in-memory UI state; the history log and archives remain backend-owned and unchanged.

**Testing**: Existing Node test runner for the 45 API-client tests; new Vitest suite for state units, views, shared building blocks, and boundary-check self-tests; new Node boundary script; existing Python `unittest`/pytest, ruff, format, and strict mypy gates unchanged.

**Target Platform**: Modern browsers at the interface's existing three ranges — desktop above 900px, tablet 561–900px, phone at or below 560px; served locally from `127.0.0.1` by the Python web adapter, with Vite for development.

**Project Type**: Web application (Python standard-library backend plus a Vue single-page frontend)

**Performance Goals**: No regression in current interaction responsiveness or first paint; no numeric target is introduced. Avoiding new runtime dependencies is the guard against added weight.

**Constraints**: Strict behavior, visual, text, timing, keyboard, and accessibility parity; no backend, API-contract, or user-visible feature change; no redesign; no new runtime dependency; production build, type check, all existing tests, new UI tests, and boundary checks must pass.

**Scale/Scope**: One single-page interface; current baseline is 1,997 frontend source lines (495 in `App.vue`, plus nine existing visual components, the API client modules, types, and the entry point). Target structure is roughly 14 state units, 10 views, 2 shared building blocks, 1 boundary script, and one isolated test file per production module.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / constraint | Gate applied to this feature | Status |
|---|---|---|
| I. Deterministic Selection | No selection, ordering, tie-breaking, exhaustion, or history-repeat logic changes; the unchanged shared client and backend remain the only data path. | Pass |
| II. Local and Private by Default | No network, telemetry, external service, or binding change; the loopback-only web UI remains as-is. | Pass |
| III. User Data Is Inviolable | All destructive flows keep their exact confirmations, busy guards, counts, messages, and failure behavior; failures still leave history and targets intact. | Pass |
| IV. Shared Core, Thin Interfaces | This is a frontend-adapter refactor only; the standard-library core and Python extras are untouched. The new test tools are development-only frontend dependencies, not runtime or core dependencies. | Pass |
| V. Verified, Boring Changes | Characterization tests precede extraction; every unit and view gets isolated tests; build, type check, boundary checks, backend gates, parity checklist, README, and CHANGELOG are required; commits stay atomic and conventional. | Pass |
| Technical constraints | Keyboard operation, visible focus, documented shortcuts, preview limits, history format, and HTTP API shape are unchanged; the generated frontend asset still builds before packaging and CI. | Pass |
| Git and commit policy | One atomic Conventional Commit per task; no commit may leave tests or lint failing. | Pass |

**Post-design re-check**: Phase 1 keeps the same boundaries. The design adds only
frontend source modules, development-only test tooling, a static boundary script,
CI steps, documentation, and a checklist; it introduces no core dependency,
network behavior, storage change, API change, or user-visible feature. **No
constitution violations; Complexity Tracking remains empty.**

## Project Structure

### Documentation (this feature)

```text
specs/004-modular-ui-components/
├── plan.md                         # This file
├── research.md                     # Phase 0 decisions
├── data-model.md                   # Phase 1 unit/view models and transitions
├── quickstart.md                   # Phase 1 validation guide
├── contracts/
│   ├── ui-module-contracts.md      # Layer, unit, view, and building-block contracts
│   └── verification-contracts.md   # Boundary rules, test mapping, parity checklist
├── parity-checklist.md             # Created during implementation; committed evidence
├── checklists/
│   └── requirements.md             # Spec quality checklist (already complete)
└── tasks.md                        # Phase 2 output (later command)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── App.vue                     # Composition root: layout + bindings only
│   ├── main.ts
│   ├── styles.css                  # Unchanged visual contract
│   ├── types.ts                    # Existing API request/response types
│   ├── view-models.ts              # NEW: shared view-model and intent types
│   ├── api.ts                      # Existing shared client (unchanged surface)
│   ├── api-query.ts
│   ├── api-operations.ts
│   ├── api-errors.ts
│   ├── api-contract.generated.ts
│   ├── state/                      # NEW: domain state and behavior units
│   │   ├── use-status.ts
│   │   ├── use-folder-options.ts
│   │   ├── use-workspace-state.ts
│   │   ├── use-choice.ts
│   │   ├── use-picker.ts
│   │   ├── use-history-selection.ts
│   │   ├── use-history-actions.ts
│   │   ├── use-browser.ts
│   │   ├── use-preview.ts          # View-local interaction/presentation unit
│   │   ├── use-image-viewer.ts     # View-local interaction unit
│   │   ├── use-tabs.ts
│   │   ├── use-shortcuts.ts
│   │   ├── use-bootstrap.ts
│   │   └── use-workspace.ts        # Thin wiring/composition unit
│   ├── views/                      # MOVED from components/, now presentation-only
│   │   ├── ChoiceBoard.vue
│   │   ├── PreviewPanel.vue
│   │   ├── ImageViewer.vue
│   │   ├── BrowserPanel.vue
│   │   ├── HistoryPanel.vue
│   │   ├── RemainingPanel.vue
│   │   ├── OptionsPanel.vue
│   │   ├── StatusBar.vue
│   │   ├── ConfirmDialog.vue
│   │   └── PanelTabs.vue           # NEW: tab strip extracted from App.vue
│   └── components/                 # Shared presentation building blocks only
│       ├── PanelShell.vue          # NEW: panel + header + actions slots
│       └── EmptyState.vue          # NEW: shared empty-state presentation
├── scripts/
│   ├── generate-api-contract.mjs   # Existing
│   └── check-ui-boundaries.mjs     # NEW: layer, cycle, scaffold, test-map checks
├── tests/
│   ├── api-*.test.mjs              # Existing 45 API-client tests (unchanged)
│   └── ui/                         # NEW Vitest suite
│       ├── state/<unit>.test.ts    # One file per state unit
│       ├── views/<View>.test.ts    # One file per view
│       ├── components/<Block>.test.ts
│       └── boundary-check.test.ts  # Self-tests for the boundary rules
├── vitest.config.ts                # NEW: happy-dom, tests/ui only
├── tsconfig.node.json              # Add vitest.config.ts to typecheck inputs
├── package.json                    # Add check:ui/test:ui + dev dependencies
└── README.md                       # Document the layer model and commands

.github/workflows/ci.yml            # Add check:ui and test:ui before build
CHANGELOG.md                        # Add the behavior-preserving refactor entry
```

**Structure Decision**: Keep the existing Vue + Vite single-project layout. Move
all visual files to `views/`, reserve `components/` for shared presentation
building blocks, and add a `state/` layer for Vue composables. The API client
modules stay at the source root so the existing 003 boundary tests and generated
contract workflow remain valid. Tests are split by runner: `.mjs` stays with the
Node test runner, `.ts` under `tests/ui/` is Vitest-only.

## Architecture and Responsibilities

### Layers and dependency direction

```text
App.vue (composition root)
   ├── imports → state/use-workspace.ts and domain state units
   ├── imports → views/*.vue
   └── renders layout + binds view models and intents

state/*.ts
   ├── may import → api.ts, api-*.ts, types.ts, view-models.ts
   ├── may use → Vue reactivity/lifecycle, browser APIs for interaction units
   └── must not import → views/*.vue, components/*.vue

views/*.vue
   ├── may import → view-models.ts, components/*.vue, own interaction unit
   ├── must not import → api.ts/api-*.ts, domain state units
   └── must not perform → data access, address construction, error parsing,
                          business validation, workflow sequencing

components/*.vue
   └── may import → view-models.ts only; pure presentation slots/props
```

The two view-local units are explicitly allowlisted: `PreviewPanel.vue` may import
`state/use-preview.ts`, and `ImageViewer.vue` may import
`state/use-image-viewer.ts`. No other view may import a state unit.

### State units (one concern each)

| Unit | Owns | Depends on |
|---|---|---|
| `use-status` | Current status message and failure-to-message conversion | `api-errors.ts` |
| `use-folder-options` | Path, log file, seed, dry run, hidden filter, mode, derived filters, entry path joining | `view-models.ts` |
| `use-workspace-state` | Loaded state, refresh, 250ms debounce, path/log change notifications, blank-path handling | API client, status, folder options |
| `use-choice` | Current choice, pick serial, preview serial and stale-response guard | view models |
| `use-picker` | Pick validation, seed parsing, outcomes, dry-run message, open current item | folder options, choice, status, workspace state |
| `use-history-selection` | Checked items, anchor, shift-range selection, select all, clearing | view models |
| `use-history-actions` | Archive, clear, single removal, batch removal, confirmations, busy flags, counts/messages, refresh and cleanup | folder options, state, choice, selection, status |
| `use-browser` | Directory listing, load on path change, parent/child navigation, use-folder intent | folder options, status |
| `use-preview` | Preview labels/fallbacks, media addresses, viewer index, video error state | API client, view models |
| `use-image-viewer` | Viewer index, zoom, pan, keyboard, preload, body scroll lock | view models |
| `use-tabs` | Active tab, tab counts, arrow/Home/End navigation and focus | workspace state |
| `use-shortcuts` | Ctrl+N registration and blocked conditions | picker, history actions |
| `use-bootstrap` | Defaults load and initial refresh | folder options, workspace state, status |
| `use-workspace` | Wiring only: instantiate units, connect callbacks, return the binding surface | all of the above |

`use-workspace` is a composition unit, not a second home for domain rules. It may
instantiate, pass callbacks, and return values; it must not validate inputs,
format messages, call the API directly, or implement workflow decisions.

### Views and shared building blocks

All existing components move to `views/` and receive ready-to-render data plus
declared intents. `PanelTabs.vue` is extracted from the main template so the tab
strip is also a reviewed publication surface.

`PanelShell.vue` owns the repeated `.panel`, `.panel-header`, and `.panel-actions`
scaffold through `header`, default, and `actions` slots plus an optional
`headerClass`; `EmptyState.vue` owns the repeated `.panel-empty` presentation.
Remaining, History, Browser, and Options use `PanelShell`; Remaining and History
use `EmptyState`. Browser keeps its distinct in-list `.browser-empty` row, and the
preview keeps its `.empty-copy` state. Existing class names remain on the rendered
output so `styles.css` needs no redesign.

### Verification design

- **Behavior units**: Vitest tests with mocked shared client, fake timers for the
  250ms debounce, and minimal host components for units that register lifecycle
  hooks. Success, failure, and boundary cases per unit.
- **Views**: Vue Test Utils mount each view in isolation with fixed, empty, and
  boundary view models; assert rendered text, classes, fallbacks, accessibility
  attributes, and emitted intents.
- **Boundary script**: `check-ui-boundaries.mjs` parses imports, builds the
  dependency graph, and fails on view API access, forbidden view-to-state imports,
  state-to-view imports, cycles, raw panel scaffold markup in views, and missing
  per-module test files. It has Vitest self-tests using fixtures for each rule.
- **Parity**: A committed `parity-checklist.md` records every flow, message class,
  keyboard/accessibility behavior, and the three viewport ranges. Screenshots are
  captured locally before and after; no image binaries or browser automation are
  committed.
- **CI**: `check:api`, `test:api`, `check:ui`, `test:ui`, then `build` in the
  frontend; all existing Python gates continue unchanged.

## Phase 0 Research Summary

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| UI test runner | Vitest 5.1 + @vue/test-utils 2.5.1 + happy-dom 21.0.4 | Vite-native SFC transform, Node 22 support, fast isolated mounts, dev-only | Node test runner without SFC compilation; Playwright component testing (browser automation out of scope); jsdom (heavier, no benefit here) |
| Test placement | `tests/ui/state`, `tests/ui/views`, `tests/ui/components`, one file per module | Enforces 100% module coverage mapping and keeps runners separate | Mixed `.mjs`/`.ts` in one folder (runner ambiguity); broad integration-only tests (weak isolation) |
| Boundary enforcement | Custom zero-dependency Node ESM script | Tailored rules, no new runtime dependency, easy CI wiring, testable with fixtures | dependency-cruiser (extra config/dependency); ESLint layer rules (no ESLint in project); TypeScript project references (cannot express runtime/data rules) |
| Layer layout | `state/`, `views/`, `components/`; API client at root | Clear ownership, existing API boundary untouched, shared blocks separated from views | Keep `components/` for everything (status quo ambiguity); feature folders (overkill for one page) |
| Shared building blocks | `PanelShell` slots + `EmptyState` | Removes duplicated scaffold with minimal abstraction | Full design system (out of scope); CSS-only dedup (cannot remove markup duplication) |
| View-local interactions | `use-preview`, `use-image-viewer` imported only by their views | Keeps viewer/preview interaction state out of views without inflating the composition root | All state via props (noisy plumbing for zoom/pan); local state in views (violates presentation-only rule) |
| Parity evidence | Committed checklist + local screenshots | Repeatable review evidence without browser infrastructure or binaries | Automated screenshot diffs (heavy/flaky); manual-only with no artifact (unreviewable) |
| Status/error path | Reuse `apiErrorMessage` in `use-status` only | Preserves 003's single error path and exact messages | Per-unit error formatting (duplicates behavior) |

## Phase 1 Design Summary

- `data-model.md` defines the state-unit inventory, view models, intent contracts,
  state transitions, validation rules, and dependency matrix. There is no
  persisted data model.
- `contracts/ui-module-contracts.md` fixes the layer boundaries, unit/view/
  composition-root contracts, building-block slot APIs, and naming rules.
- `contracts/verification-contracts.md` fixes the boundary check rules, test file
  mapping, parity checklist fields, and the five required violation trials.
- `quickstart.md` provides the runnable automated and manual validation path,
  including the three viewport ranges and the baseline/after procedure.

## Implementation Strategy

1. **Foundation**: Add Vitest, Vue Test Utils, happy-dom, `vitest.config.ts`,
   `check:ui`/`test:ui` scripts, CI steps, `view-models.ts`, and the boundary
   script with self-tests. Establish the baseline parity checklist before moving
   behavior.
2. **Shared presentation**: Add `PanelShell` and `EmptyState` tests and
   implementations; prove rendered classes match the current markup.
3. **US1 — state extraction**: Add characterization tests for each workflow, then
   extract the 14 state units behind the unchanged API client. Move logic without
   changing strings, timers, ordering, or guards. Keep the interface working after
   every commit.
4. **US2 — view conversion**: Move components to `views/`, remove data access and
   domain state from them, introduce `PanelTabs`, and wire the slim composition
   root. Add isolated view tests and complete the parity checklist at all three
   viewport ranges.
5. **US3 — enforcement and docs**: Turn on all boundary rules, run the five
   deliberate violation trials, update `frontend/README.md` and `CHANGELOG.md`,
   and record check results in the parity checklist.
6. **Polish**: Run the full frontend and backend gates, confirm the API contract
   and lockfiles are current, and mark tasks complete.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Behavior drift while moving logic | Characterization tests before extraction; exact-string assertions; incremental commits; full flow replay |
| Viewer/debounce regressions in a DOM environment | happy-dom tests for keyboard/zoom/clamp/scroll lock; fake timers for debounce; manual viewer checklist |
| Boundary script false positives or blind spots | Narrow rules, explicit allowlist, fixture-based self-tests, five violation trials |
| `use-workspace` becoming a new monolith | Composition-only contract; size/responsibility review; domain rules tested in their own units |
| Test suite slows CI | Vitest run with `tests/ui` only; no browser download; small isolated mounts |
| Duplicated scaffold persists in unfamiliar markup | Automated class-token checks plus documented semantic review in the parity checklist |

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations. The status quo is the simpler alternative, but it is
rejected because it preserves the maintenance risk and cannot enforce
presentation-only views or one owner per workflow.
