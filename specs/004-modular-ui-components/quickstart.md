# Quickstart Validation: Modular UI Components

**Feature**: `004-modular-ui-components`  
**Date**: 2026-11-02

This guide proves the refactor preserved behavior while moving logic into state
units, views, and shared building blocks. It is a validation guide, not an
implementation tutorial. The module contracts live in
[`contracts/ui-module-contracts.md`](./contracts/ui-module-contracts.md), the data
model in [`data-model.md`](./data-model.md), and the enforcement rules in
[`contracts/verification-contracts.md`](./contracts/verification-contracts.md).

## Prerequisites

- Node.js 22.12 or newer (the project uses 22.23.1) and npm.
- Python 3.12 with `uv`.
- A checkout of the feature branch `004-modular-ui-components`.
- No running service on port 8765 unless you choose another port.

## 1. Install

From the repository root:

```sh
uv sync --group dev --extra ui --extra web
cd frontend
npm ci
```

## 2. Automated gates

Run from `frontend/`:

```sh
npm run check:api     # generated contract is current
npm run test:api      # existing Node API-client suite (45 tests)
npm run check:ui      # layer, cycle, scaffold, and test-map rules
npm run test:ui       # Vitest state/view/building-block suite
npm run build         # vue-tsc strict type check + production build
```

From the repository root:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy choosier main.py tests
uv build
```

**Expected**: every command exits 0; the existing 45 API-client tests still pass;
every state unit, view, and shared block has a passing isolated test; no new
runtime dependency appears in `frontend/package.json`.

## 3. Baseline and parity replay

### 3.1 Capture the baseline first

On `main@d25abef` (before any refactor commit), or from a clean checkout of that
commit:

1. Start the API server:
   ```sh
   uv run choosier --web --port 8765
   ```
2. If using the Vite dev server, start it in `frontend/` with `npm run dev`; it
   proxies `/api` to 8765.
3. Open the interface and perform every flow in
   [`contracts/verification-contracts.md §5.2`](./contracts/verification-contracts.md#52-flow-matrix).
4. Repeat at all three viewport ranges:
   - desktop: width above 900px
   - tablet: width from 561px to 900px
   - phone: width at or below 560px
5. Capture local screenshots for each viewport and flow group. Do not commit the
   images.

### 3.2 Replay after the refactor

Run the same server and the same flow matrix against the refactored tree. Compare:

- visible text, ordering, counts, and enabled/disabled states;
- layout, spacing, truncation, and responsive behavior;
- focus order, visible focus, ARIA labels, live status announcements;
- keyboard shortcuts and dialog/viewer behavior;
- empty, error, exhausted, missing-history, and no-op states;
- timing-sensitive behavior: rapid option changes, overlapping previews, blocked
  actions while a confirmation is open.

Record each row in `specs/004-modular-ui-components/parity-checklist.md`.

## 4. Targeted behavior checks

### 4.1 Pick and preview

- Blank path → "Enter a folder path." and focus returns to the folder input.
- Non-integer seed → "Seed must be a whole number."
- Invalid path, empty folder, exhausted choices → exact baseline messages.
- Dry run → picked message says it was not logged; history does not gain an entry.
- Rapidly change the folder or log file while a preview is in flight → the older
  preview must not replace the newer choice, and the choice/selection must clear.
- Pick repeatedly with long names → the board truncates at 48 characters while the
  title retains the full name.

### 4.2 History

- Archive with and without a log file; clear confirm and cancel; single removal
  with zero, one, and many matching entries.
- Batch: click a row, shift-click a range, select all/clear selection, delete
  selected; confirm the dialog and repeat with cancel.
- While a removal is in progress, duplicate actions must remain blocked.
- Change the log file or folder → checked items and any pending confirmation clear.

### 4.3 Browser, options, and viewer

- Browser loads immediately for the current path, navigates parent/child, handles
  an empty folder and a failure, and "Use this folder" updates the path.
- Options changes affect the next pick only.
- Viewer: open from a grid, next/previous wrap, zoom in/out, reset, double-click,
  drag when zoomed, clamp at edges, open original, Escape closes, body scroll
  restores after closing.
- Single-image viewer shows no navigation controls.

### 4.4 Accessibility and keyboard

- Tabs: Left/Right wrap, Home/End jump, focus follows the active tab, counts match
  Remaining and History totals.
- Ctrl+N picks from the page, but is blocked while the clear confirmation is active
  or a dialog/viewer overlay is open (the exact current condition).
- Dialog: cancel receives initial focus, Tab is trapped, Escape cancels, clicking
  outside cancels.
- Status changes are announced through the live region.
- All interactive controls remain keyboard-operable with visible focus.

## 5. Boundary violation trials

On a clean tree, perform each trial and confirm the expected failure from
`npm run check:ui`. Restore the tree after each trial.

| # | Trial | Expected |
|---|---|---|
| 1 | Import the shared client and call it from a view | R-01 view API isolation fails |
| 2 | Add a watcher or API call to `App.vue` | R-04 composition-root thinness fails |
| 3 | Import a view from a state unit | R-03 state isolation fails |
| 4 | Create a two-file relative-import cycle | R-05 acyclic graph fails |
| 5 | Duplicate raw `.panel`/`.panel-header` markup in a view | R-06 shared scaffold fails |

Record the results in the parity checklist.

## 6. Expected artifacts

After implementation, the feature directory contains:

```text
specs/004-modular-ui-components/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ui-module-contracts.md
│   └── verification-contracts.md
├── parity-checklist.md      # completed and committed
└── checklists/requirements.md
```

The source tree has `frontend/src/state/`, `frontend/src/views/`, and a minimal
`frontend/src/components/` containing only shared presentation blocks.

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| `npm run test:ui` runs no tests | `vitest.config.ts` include path; tests must be `tests/ui/**/*.test.ts` |
| Vitest picks up the `.mjs` API tests | Keep the include restricted to `tests/ui`; do not broaden it to all tests |
| happy-dom lacks a browser API | Stub the specific API in the test; do not switch the whole suite to a real browser |
| Dev server cannot reach the API | Ensure the Python server runs on 8765 and the Vite proxy is unchanged |
| A view test fails on an emitted event name | Match the intent contract in `data-model.md`; do not rename an intent without updating the contract |
| The boundary script reports a false positive | Tighten the rule in the script and add a fixture test; do not add a blanket allowlist |
| A parity row differs only by focus order | Treat it as a failure until the cause is understood; focus order is part of the accessibility contract |

## 8. Definition of done

- [ ] All automated gates pass.
- [ ] Every `state/`, `views/`, and shared `components/` module has a matching test.
- [ ] The parity checklist is complete at all three viewport ranges.
- [ ] The five violation trials are recorded as detected.
- [ ] `frontend/README.md` documents the layer model and commands.
- [ ] `CHANGELOG.md` records the behavior-preserving refactor.
- [ ] No new runtime dependency, API change, backend change, or visual redesign.
