# Phase 0 Research: Modular UI Components

**Feature**: `004-modular-ui-components`  
**Date**: 2026-11-02  
**Status**: Complete — no `NEEDS CLARIFICATION` items remain

## Scope

The feature is a behavior-preserving frontend refactor. Research therefore focuses
on four questions: which development-only tooling can test Vue components in this
project, how state units should be structured and tested, how to enforce layer
boundaries without adding runtime dependencies, and how to prove visual and
behavioral parity across the existing responsive ranges.

## Decision 1 — Component test runner

**Decision**: Add Vitest 5.1.0, `@vue/test-utils` 2.5.1, and happy-dom 21.0.4 as
development-only dependencies. Run them from a dedicated `vitest.config.ts` with
`environment: 'happy-dom'` and `include: ['tests/ui/**/*.test.ts']`.

**Rationale**:
- Vitest 5 declares Vite `^6.4 || ^7 || ^8` support and Node `^22.12 || ^24 || >=26`;
  this project has Vite 8.3.4 and Node 22.23.1.
- It uses the same Vite/Vue transform as the application, so single-file
  components, TypeScript, and path resolution work without a second bundler.
- `@vue/test-utils` provides isolated mounts, emitted-event assertions, and
  accessibility-attribute inspection without a real browser.
- happy-dom 21 supports Node 20+ and is lighter than jsdom for these tests.
- Restricting `include` to `tests/ui/**/*.test.ts` keeps the existing Node
  `.mjs` API-client suite on its own runner and avoids duplicate execution.

**Alternatives considered**:
- **Node test runner only**: cannot compile Vue single-file components without
  adding a separate SFC transform; view tests would remain manual, contradicting
  the accepted clarification.
- **Playwright/component browser testing**: adds browser downloads, CI time, and
  browser automation explicitly kept out of scope by the spec.
- **jsdom**: workable but heavier; happy-dom covers the DOM APIs needed here
  (focus, events, pointers, measured elements can be stubbed).
- **No component tests**: fails the accepted test-tooling clarification and
  weakens the presentation-only boundary.

**Constraints**:
- Development-only; no runtime dependency.
- No coverage provider is added; the spec's coverage rule is a test-file-per-module
  mapping, not a percentage threshold.
- CI installs the same `npm ci` dependencies used by the build.

## Decision 2 — State-unit shape and test strategy

**Decision**: Implement state units as Vue composables under `src/state/`, each
exporting one `useX(...)` function that returns refs, computed values, and action
functions. Units receive cross-unit dependencies as explicit arguments where
needed; `use-workspace.ts` wires them. Tests mock the shared API client with
`vi.mock`, use fake timers for the 250ms refresh debounce, and mount a minimal host
component only for units that register lifecycle hooks.

**Rationale**:
- Vue composables are the existing framework-native mechanism and require no new
  state library, satisfying the spec's assumption.
- Explicit inputs make unit boundaries visible and prevent hidden global access.
- Isolated tests can cover success, failure, and boundaries without mounting the
  whole application.
- Fake timers verify the debounce and stale-response guards deterministically.
- A minimal host component is needed only where `onMounted`/`onUnmounted` perform
  registration (bootstrap, shortcuts, image viewer); pure units test directly
  inside an `effectScope`.

**Alternatives considered**:
- **Global store (Pinia or similar)**: adds a runtime dependency and a new state
  model; explicitly excluded.
- **Plain module singletons**: harder to reset between tests and creates hidden
  shared state.
- **Dependency injection container**: over-engineered for one page; explicit
  arguments and one composition unit are enough.
- **Mount the whole app per test**: slower, less isolated, and would make failures
  point at the monolith instead of one owner.

**Constraints**:
- No unit may import a view or shared visual component.
- API access goes only through the existing shared client.
- Exact strings, serial counters, busy guards, and confirmation flows stay
  identical.

## Decision 3 — Boundary enforcement

**Decision**: Add `frontend/scripts/check-ui-boundaries.mjs`, a zero-dependency
Node ESM script. It will:
1. Parse relative imports from `.ts` and `.vue` files and build a dependency graph.
2. Reject API-client imports and network/envelope patterns in `src/views/**/*.vue`.
3. Reject domain-state imports in views, with an explicit allowlist for
   `use-preview` in `PreviewPanel.vue` and `use-image-viewer` in `ImageViewer.vue`.
4. Reject view/component imports in `src/state/**/*.ts`.
5. Reject API imports and orchestration primitives (`api.`, `fetch`, timers,
   watchers, mounted hooks, computed state, error formatting) in `App.vue`.
6. Detect import cycles across `src/**/*.ts` and `src/**/*.vue`.
7. Reject raw `.panel`, `.panel-header`, `.panel-empty`, and `.panel-actions`
   scaffold tokens in view templates.
8. Require one test file per production module and fail with the missing path.

The script's pure helpers are exercised by `tests/ui/boundary-check.test.ts` with
fixtures for each rule.

**Rationale**:
- The rules are specific to this project and can be expressed in a small script;
  no parser or graph library is needed for relative ESM imports.
- It adds no dependency and runs quickly in CI.
- Fixture tests make the five required violation trials repeatable.
- The test-file mapping directly enforces the spec's 100% unit/view test rule.

**Alternatives considered**:
- **dependency-cruiser**: capable but adds a dependency, configuration surface, and
  rules that still need custom extensions for scaffold tokens and test mapping.
- **ESLint with `no-restricted-imports`**: the project has no ESLint setup; adding a
  full lint stack for one rule set is disproportionate.
- **TypeScript project references only**: cannot express data access, scaffold
  duplication, or test-file mapping.
- **Review-only enforcement**: rejected by the accepted clarification; review
  remains only for semantic duplication.

**Known limits**: import extraction is syntactic, not a full TypeScript parse.
Aliased dynamic imports and unusual re-exports could evade it; the rule set covers
the actual source patterns and the review step covers semantic duplication. The
script fails closed when a file cannot be read or an import cannot be resolved.

## Decision 4 — Layer layout and composition

**Decision**: Use three source layers — `src/state/` (domain and interaction
units), `src/views/` (presentation-only visual areas), and `src/components/`
(shared presentation building blocks) — with `App.vue` as the composition root.
Keep the existing API client modules at the source root.

**Rationale**:
- The names state/views/components match the feature language and make the
  dependency rule obvious.
- Moving all visual files out of `components/` lets `components/` mean "shared
  building blocks only", which prevents the old ambiguity.
- Keeping API modules at the root preserves the 003 boundary tests, generated
  contract workflow, and documentation links.
- The composition root remains a Vue single-file component because layout and
  template bindings are its legitimate responsibilities.

**Alternatives considered**:
- **Feature folders**: each workflow in its own folder with state/view/tests; more
  directories than the one-page scope justifies, and cross-workflow wiring becomes
  harder to see.
- **Keep everything in `components/`**: cannot distinguish shared blocks from
  views; boundary checks become naming-based and fragile.
- **Move the API client under a service folder**: would invalidate existing
  boundary tests and documentation for no behavioral gain.

## Decision 5 — Shared visual building blocks

**Decision**: Add two shared blocks:
- `PanelShell.vue`: renders `.panel`, a header wrapper with an optional
  `headerClass`, the default body, and an action wrapper via slots.
- `EmptyState.vue`: renders `.panel-empty` with slotted content and an optional
  class.

Use `PanelShell` in Remaining, History, Browser, and Options; use `EmptyState` in
Remaining and History. Browser's in-list `.browser-empty` row and the preview's
`.empty-copy` state are distinct visual structures and stay view-specific.
`ConfirmDialog` remains the single dialog view used by both confirmation flows.

**Rationale**:
- These are the only markup patterns currently repeated across two or more views.
- Slots preserve each view's content and accessibility attributes while the shared
  block owns the scaffold classes.
- Vue attribute fallthrough lets a view add its unique class (for example,
  `class="browser"`) without re-declaring `.panel`.
- No CSS changes are needed; the rendered class contract stays identical.

**Alternatives considered**:
- **Generic `Panel` with a configuration object**: less readable than slots for
  heterogeneous content.
- **CSS-only deduplication**: leaves duplicated markup and does not satisfy FR-008.
- **Component library/design system**: out of scope and would add abstraction for
  only one page.

## Decision 6 — Preview and viewer interaction units

**Decision**: Allow exactly two view-local interaction units:
- `PreviewPanel.vue` may import `use-preview.ts`, which owns media address
  construction, preview labels, viewer-open state, and video-error state.
- `ImageViewer.vue` may import `use-image-viewer.ts`, which owns index, zoom, pan,
  keyboard handling, preload, and body scroll lock.

No other view may import a state unit.

**Rationale**:
- These interactions are presentation-local but must not live in the view; the
  spec explicitly requires viewer interaction state in a dedicated unit.
- Keeping them view-local avoids threading a large zoom/pan handler surface through
  the composition root.
- Media addresses are still constructed by the shared client, not the view.

**Alternatives considered**:
- **All interaction state in the composition root**: huge prop/handler surface and
  a less testable viewer.
- **Keep zoom/pan in `ImageViewer.vue`**: violates the presentation-only rule and
  the viewer acceptance scenario.
- **Move preview/viewer state into domain units**: couples domain workflows to
  presentation lifecycle for no benefit.

## Decision 7 — Parity verification

**Decision**: Capture the baseline before extraction, then complete a committed
`parity-checklist.md` covering every flow, message class, keyboard/accessibility
behavior, and the three viewport ranges. Capture before/after screenshots locally
for review only; commit no binaries and add no browser automation.

**Rationale**:
- Visual parity is a primary acceptance criterion for a refactor.
- A checklist is reviewable, diffable, and durable; local screenshots provide
  evidence without repository bloat.
- Avoiding browser tooling keeps CI fast and within the accepted scope.

**Alternatives considered**:
- **Automated screenshot diffing**: high-value for large design systems, but adds
  browser downloads, flake risk, and infrastructure beyond this feature.
- **No retained artifact**: makes the parity claim unverifiable after the fact.

**Checklist fields**: flow, baseline result, after result, pass/fail, notes;
message classes with exact expected text; keyboard/focus/ARIA checks; viewport
rows for >900, 561–900, and ≤560; boundary-rule trial results; sign-off commit.

## Decision 8 — Preserve async behavior exactly

**Decision**: Keep the current 250ms refresh debounce, the monotonic preview serial
guard, the busy flags for removal/archive/clear, the blocked-shortcut conditions,
and the existing confirmation lifecycle. Extract them unchanged into units and
test them with fake timers and deferred promises.

**Rationale**:
- These are the behaviors most likely to regress during extraction and are hard to
  see in a manual happy-path replay.
- Fake timers and controlled promise resolution make stale and overlap cases
  deterministic.

**Alternatives considered**:
- **Redesign the async model** (cancellation tokens, request deduplication): out of
  scope and would change behavior.
- **Rely on manual testing for overlaps**: too easy to miss.

## Decision 9 — CI and scripts

**Decision**: Add:
- `npm run check:ui` → `node scripts/check-ui-boundaries.mjs`
- `npm run test:ui` → `vitest run`
- CI steps `Check UI boundaries` and `Test UI` after the API steps and before
  `Build frontend`.

Keep `check:api`, `test:api`, `build`, and all Python gates unchanged.

**Rationale**:
- The boundaries and tests become required gates rather than conventions.
- Running before the build means a broken layer or view fails before packaging.
- The existing API contract and Python gates remain authoritative.

**Alternatives considered**:
- **Run UI checks only locally**: drifts immediately.
- **Run after the build**: wastes build time on code that should fail earlier.
- **Combine with `test:api`**: mixes runners and makes failures harder to diagnose.

## Decision 10 — Dependencies and versioning

**Decision**: Add only `devDependencies` (`vitest`, `@vue/test-utils`,
`happy-dom`) and update `frontend/package-lock.json`. Do not change `dependencies`
or the Python project metadata.

**Rationale**:
- Satisfies the spec's no-new-runtime-dependency requirement and the constitution's
  thin-interface principle.
- Vitest 5.1.0, Vue Test Utils 2.5.1, and happy-dom 21.0.4 are verified compatible
  with the existing Vite 8, Vue 3.5, TypeScript 6, and Node 22 toolchain.

**Alternatives considered**:
- **Upgrade Vite/Vue as part of this refactor**: adds unrelated risk; not needed.
- **Add a coverage provider**: no percentage target in the spec and an extra
  dependency; the per-module test mapping is the chosen coverage gate.

## Open items

None. The spec has no `NEEDS CLARIFICATION` markers, and the four clarification
decisions (test tooling, viewport matrix, parity evidence, duplication detection)
are fixed in the spec and reflected above.
