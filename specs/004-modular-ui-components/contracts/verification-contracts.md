# Verification Contracts

**Feature**: `004-modular-ui-components`  
**Date**: 2026-11-02  
**Status**: Design contract for implementation and review

This file fixes how the refactor is proven: the boundary rules, the test-file
mapping, the parity checklist, the required violation trials, and the gate order.
It complements [ui-module-contracts.md](./ui-module-contracts.md).

## 1. Quality gates

| Command | Location | Required result |
|---|---|---|
| `npm run check:api` | `frontend/` | Generated contract matches the frozen JSON; exit 0 |
| `npm run test:api` | `frontend/` | All existing 45 API-client tests pass; exit 0 |
| `npm run check:ui` | `frontend/` | Boundary script passes; exit 0 |
| `npm run test:ui` | `frontend/` | All Vitest state/view/building-block/boundary tests pass; exit 0 |
| `npm run build` | `frontend/` | `vue-tsc -b` and Vite production build pass; exit 0 |
| `uv run ruff check .` | repository root | No lint errors |
| `uv run ruff format --check .` | repository root | No formatting changes |
| `uv run pytest` | repository root | All Python tests pass, unchanged count or greater |
| `uv run mypy choosier main.py tests` | repository root | No type errors |
| `uv build` | repository root | Package builds |

CI order in `.github/workflows/ci.yml`:

```text
check:api → test:api → check:ui → test:ui → build → Python gates → uv build
```

The UI checks must run before the frontend build so a boundary violation fails
before packaging.

## 2. Boundary check rules

The script is `frontend/scripts/check-ui-boundaries.mjs`; the npm script is
`check:ui`. It scans `frontend/src/**/*.{ts,vue}` and fails with the offending file
and rule name. It must exit non-zero on any violation.

### R-01 View API isolation

For every `src/views/**/*.vue`, fail if the file:
- Imports any module whose resolved path is `api.ts`, `api-query.ts`,
  `api-operations.ts`, `api-errors.ts`, or `api-contract.generated.ts`.
- Contains `fetch(`, `XMLHttpRequest`, `EventSource`, `axios`, `/api/`, or an
  error-envelope field read (`error.code`, `error.details`, `.detail`).

### R-02 View state isolation

For every `src/views/**/*.vue`, fail if it imports any `src/state/**` module,
except:
- `src/views/PreviewPanel.vue` → `src/state/use-preview.ts`
- `src/views/ImageViewer.vue` → `src/state/use-image-viewer.ts`

No other exception is allowed. `use-preview.ts` and `use-image-viewer.ts` may not
be imported by any other file.

### R-03 State isolation

For every `src/state/**/*.ts`, fail if it imports any `src/views/**` or
`src/components/**` module.

### R-04 Composition-root thinness

For `src/App.vue`, fail if it:
- Imports any `api*` module.
- Contains `api.`, `fetch(`, `XMLHttpRequest`, `EventSource`, `axios`, or
  `/api/`.
- Contains `watch(`, `computed(`, `onMounted(`, `onUnmounted(`, `setTimeout`,
  `setInterval`, `apiErrorMessage`, or an `async` function declaration.
- Declares a non-trivial function body beyond destructuring/bindings.

The last item is a documented review rule; the preceding items are automated.

### R-05 Acyclic dependency graph

Build the relative-import graph for all `src/**/*.{ts,vue}` files. Fail on any
cycle. External package imports are excluded. Unresolved relative imports fail
closed.

### R-06 Shared scaffold

For every `src/views/**/*.vue`, fail if the template contains raw scaffold class
tokens:
- `panel` used as a standalone root class,
- `panel-header`,
- `panel-empty`,
- `panel-actions`.

Allowed only in `src/components/PanelShell.vue` and
`src/components/EmptyState.vue`. A unique consumer class (for example,
`browser`, `options-panel`, `history-header`) is allowed through `PanelShell`
attribute fallthrough or the `headerClass` prop.

### R-07 Test-file mapping

Fail if any of the following lacks a matching test file:

| Production file | Required test file |
|---|---|
| `src/state/<name>.ts` | `tests/ui/state/<name>.test.ts` |
| `src/views/<Name>.vue` | `tests/ui/views/<Name>.test.ts` |
| `src/components/<Name>.vue` | `tests/ui/components/<Name>.test.ts` |

The boundary script prints the missing path. `tests/ui/boundary-check.test.ts`
must cover each rule with a failing fixture and a passing fixture.

## 3. Test suite contract

- Runner: Vitest 5.1.0 with `environment: 'happy-dom'`.
- Config: `frontend/vitest.config.ts` with
  `include: ['tests/ui/**/*.test.ts']`; existing `.mjs` tests remain on the Node
  runner and must not be picked up by Vitest.
- One test file per state unit, view, and shared block; the mapping is enforced by
  R-07.
- Each state-unit test covers at least one success path, one failure path, and one
  boundary case.
- Each view test mounts in isolation with fixed, empty, and boundary view models
  and asserts rendered text/classes/ARIA plus emitted intents.
- Lifecycle-bearing units are tested through a minimal host component or an
  `effectScope`; the full app is not mounted.
- API calls are mocked at the `src/api` boundary; no test performs real network
  I/O.
- Fake timers verify the 250ms debounce and stale-response guards.
- No coverage percentage threshold is introduced; the per-module mapping is the
  required coverage gate.

## 4. Five required violation trials

Perform each trial on a clean tree, confirm the expected failure, then restore the
tree. Record the result in the parity checklist.

| # | Trial | Expected detection |
|---|---|---|
| 1 | Add `import { api } from '../api'` and `await api.state(...)` to a view | R-01 fails |
| 2 | Add a `watch(...)` or `api.defaults()` call to `App.vue` | R-04 fails |
| 3 | Add `import PreviewPanel from '../views/PreviewPanel.vue'` to a state unit | R-03 fails |
| 4 | Create a two-file relative-import cycle | R-05 fails |
| 5 | Duplicate `<div class="panel"><div class="panel-header">…` in a view | R-06 fails |

For semantic duplication that static checks cannot judge (for example, two
differently named row structures that are visually identical), the reviewer records
the finding in the parity checklist and resolves it before sign-off.

## 5. Parity checklist contract

The implementation must commit
`specs/004-modular-ui-components/parity-checklist.md` before the final merge. It
must contain:

### 5.1 Header

- Feature, branch, baseline commit (`main@d25abef`), implementation commit range,
  date, reviewer.
- Three viewport rows: desktop >900px, tablet 561–900px, phone ≤560px.

### 5.2 Flow matrix

For each flow, record baseline result, after result, and pass/fail:

1. Initial load with defaults.
2. Browse: load, parent, child, empty folder, error.
3. Options: log file, seed, dry run, hidden, mode changes.
4. Pick: success, dry run, blank path, non-integer seed, invalid path, empty,
   exhausted, backend failure.
5. Preview: text, single image, archive frames, truncated image total, video,
   video playback failure.
6. Open: current item and history item.
7. History: archive with/without log, clear confirm/cancel, single removal with
   0/1/many entries, batch select/range/select-all/delete/cancel.
8. Viewer: open, close, next/previous wrap, zoom levels, double-click, drag clamp,
   original link, Escape, scroll lock restore.
9. Keyboard: Ctrl+N, blocked while dialog/overlay is open, tab arrow/Home/End,
   focus visibility.
10. Status and empty-state text for every message class.

### 5.3 Evidence

- Before/after screenshots are captured locally at each viewport; they are not
  committed.
- Record the local file names or a short note per screenshot. No binaries in the
  repository.
- Record the five violation-trial results.
- Record any intentional deviation with its explicit decision; otherwise the row
  must be identical.

### 5.4 Sign-off

- All rows pass, or every exception has a recorded decision.
- `check:api`, `test:api`, `check:ui`, `test:ui`, `build`, and all Python gates
  pass.
- No unexplained visual difference at any viewport.

## 6. Manual baseline procedure

1. On `main@d25abef`, run the app (`uv run choosier --web --port 8765` plus
   `npm run dev` if using the dev server) and capture the baseline for every flow
   in §5.2 at each viewport.
2. Implement the refactor on `004-modular-ui-components` without changing the
   visible behavior.
3. Replay the same flows against the refactored app at the same viewports.
4. Compare text, ordering, enabled states, focus order, ARIA, layout, and
   screenshots; record each row.
5. Run the automated gates and the five violation trials.
6. Commit the completed checklist; do not commit screenshots or browser tooling.

## 7. Merge gate

The branch may merge to `main` only when:
- Every checklist row is pass or has a recorded decision.
- All quality gates in §1 pass.
- The five violation trials are recorded as detected.
- `frontend/README.md` documents the layer model and commands.
- `CHANGELOG.md` has the behavior-preserving refactor entry.
- The working tree is clean and the API contract/lockfile state is intentional.
