# UI Module Contracts

**Feature**: `004-modular-ui-components`  
**Date**: 2026-11-02  
**Status**: Design contract for implementation and review

These contracts define the internal frontend interfaces created by this refactor.
They are normative for implementation: a change that violates a rule must fail the
boundary script or the documented review. They do not change any public HTTP or
history contract.

## 1. Layers

| Layer | Location | Responsibility | May import |
|---|---|---|---|
| Composition root | `src/App.vue` | Layout, instantiate the workspace, bind view models and intents, render dialogs | `state/`, `views/`, `view-models.ts` |
| Domain state units | `src/state/use-*.ts` (except the two interaction units) | Own one workflow's state, data access, validation, sequencing, derived display data, and failure-to-message conversion | Shared client, `types.ts`, `view-models.ts`, other state units via explicit arguments |
| View-local interaction units | `src/state/use-preview.ts`, `src/state/use-image-viewer.ts` | Own preview/viewer presentation interaction and media address resolution | Shared client (preview only), `types.ts`, `view-models.ts` |
| Views | `src/views/*.vue` | Render supplied data and report intents | `view-models.ts`, `components/`, and its own allowlisted interaction unit |
| Shared presentation blocks | `src/components/*.vue` | Render reusable scaffold with slots/props | `view-models.ts` only |
| Shared client | `src/api.ts`, `src/api-*.ts` | Sole network and endpoint boundary (unchanged from feature 003) | Unchanged |

**Global rules**:
- No state unit imports a view or a shared block.
- No view imports the shared client or a domain state unit.
- No view constructs a media address, parses an error envelope, or performs a
  network request.
- No shared block owns state beyond presentational props/slots.
- The dependency graph is acyclic.

## 2. Composition root contract

`App.vue` is the only file allowed to assemble the layers. Its `<script setup>` may
contain only:
1. Imports of the workspace unit, view-model types, and views.
2. Template refs required for focus (for example, the folder input).
3. One `useWorkspace(...)` call.
4. Destructuring/aliasing of the returned bindings.
5. Template bindings, layout markup, and view composition.

It must not contain:
- Imports from `api*`.
- `api.` calls, `fetch`, XHR, or endpoint literals.
- `watch(`, `computed(`, `onMounted(`, `onUnmounted(`, timers, or intervals.
- Validation, status-message construction, confirmation lifecycle, serial guards,
  busy flags, or error formatting.
- More than a trivial expression per event binding; non-trivial behavior belongs
  to a unit action.

The design target is one `useWorkspace` call plus bindings; any growth beyond
layout and wiring is a review failure.

## 3. State-unit contract

### 3.1 Shape

```ts
export function useThing(deps: ThingDeps): ThingBinding
```

- `deps` are explicit: refs, callbacks, or unit bindings. No hidden module-level
  mutable state.
- `ThingBinding` contains only `Ref`, `ComputedRef`, and action functions.
- Actions are stable closures; they do not expose mutable internals directly.
- A unit owns one concern. Cross-unit coordination lives in `use-workspace`.
- A unit may register lifecycle hooks only for the side effects it owns (for
  example, the refresh timer or the viewer's body lock).
- A unit that calls the shared client uses the existing `api` object and the
  existing failure path; it never re-implements envelope parsing.

### 3.2 Required units

The unit inventory, owned state, inputs, outputs, side effects, and test focus are
defined in [data-model.md § State-unit inventory](../data-model.md#state-unit-inventory).
The names and responsibilities are normative:

`use-status`, `use-folder-options`, `use-workspace-state`, `use-choice`,
`use-picker`, `use-history-selection`, `use-history-actions`, `use-browser`,
`use-preview`, `use-image-viewer`, `use-tabs`, `use-shortcuts`, `use-bootstrap`,
and `use-workspace`.

### 3.3 Composition-unit limit

`use-workspace.ts` may instantiate units, pass dependencies/callbacks, connect
watchers declared by those units, and return the binding surface. It must not:
- Call the shared client directly.
- Validate user input.
- Format status, confirmation, or error text.
- Implement serial counters, debounce, busy flags, or deletion sequencing.
- Import any view.

If a rule needs a home, it belongs in the unit that owns the workflow.

### 3.4 Shared status and errors

`use-status` is the only unit that converts failures to messages, using
`apiErrorMessage` from the unchanged shared client. Other units receive `setStatus`
or `reportError`; they must not format error payloads.

Exact user-visible strings are part of the contract. They must match the baseline
at `main@d25abef`; changes require an explicit recorded decision in the parity
checklist.

## 4. View contract

### 4.1 Shape

A view:
- Receives a complete view model through props. The data is ready to render;
  the view does not derive workflow outcomes.
- Reports user intent through declared events. Event names describe the intent
  (`pick`, `open`, `archive`, `remove`, `select`, `navigate`, `useFolder`,
  `confirm`, `cancel`, `close`, `select-tab`).
- May keep purely visual transient state that has no workflow meaning (for
  example, a CSS-only hover or an internal viewer flag owned by its interaction
  unit).
- Preserves existing semantic HTML, ARIA attributes, keyboard behavior, focus
  order, labels, and CSS class names unless parity is proven.

A view must not:
- Import `api*` or a domain state unit.
- Call `fetch`, XHR, `api.*`, or construct `/api/...` addresses.
- Parse an error envelope or format a failure.
- Validate path/seed/filter inputs or decide a pick/removal outcome.
- Own checked items, confirmations, busy flags, refresh timers, or selection
  ranges.
- Reimplement `.panel`, `.panel-header`, `.panel-empty`, or `.panel-actions`.

### 4.2 Interaction-unit allowlist

| View | May import |
|---|---|
| `PreviewPanel.vue` | `state/use-preview.ts` |
| `ImageViewer.vue` | `state/use-image-viewer.ts` |
| Every other view | No `state/` import |

`use-preview` and `use-image-viewer` may be imported only by their allowlisted
view; no other view or unit may import them.

### 4.3 View inventory

The complete input/intent contract for each view is defined in
[data-model.md § View-model and intent contracts](../data-model.md#view-model-and-intent-contracts).
New views must follow the same pattern and receive a matching isolated test file.

## 5. Shared building-block contracts

### 5.1 `PanelShell.vue`

| Contract | Definition |
|---|---|
| Purpose | Own the repeated panel scaffold so views do not re-declare it |
| Props | `headerClass?: string` (optional extra class merged onto the header wrapper) |
| Slots | `header` (header content), default (panel body), `actions` (action bar) |
| Renders | `<div class="panel ..."><div class="panel-header ...">…</div>…<div class="panel-actions">…</div></div>` |
| Attribute fallthrough | Root class merging is allowed so a view can add a unique class (for example, `class="browser"`) without writing `.panel` |
| Consumers | `RemainingPanel`, `HistoryPanel`, `BrowserPanel`, `OptionsPanel` |
| Forbidden | Data access, workflow state, or view-specific logic |

### 5.2 `EmptyState.vue`

| Contract | Definition |
|---|---|
| Purpose | Own the repeated empty-state presentation |
| Props | Optional class only (or equivalent presentational variation) |
| Slots | Default message content |
| Renders | A `.panel-empty` element with the existing text styles |
| Consumers | `RemainingPanel`, `HistoryPanel` |
| Forbidden | Data access or conditional workflow decisions |

Browser's `.browser-empty` list row and the preview's `.empty-copy` state are
distinct visual structures and remain inside their views.

`ConfirmDialog.vue` remains the single dialog view used by the clear and batch
removal flows. No additional shared block is justified until a pattern appears in
two or more views.

## 6. Shared types

`src/view-models.ts` holds:
- View-model interfaces for each view.
- Intent payload types (for example, `HistoryRowSelection { item: string; shift: boolean }`).
- The workspace binding interface returned by `use-workspace`.
- No runtime logic and no API implementation.

`src/types.ts` keeps its existing API request/response types. It must not gain UI
state or view-only types.

## 7. Naming and file rules

- State units: `src/state/use-<kebab-concern>.ts`, one exported `use<Concern>`
  function plus its types.
- Views: PascalCase `.vue` in `src/views/`; one visual area per file.
- Shared blocks: PascalCase `.vue` in `src/components/`; only genuinely shared
  structures.
- Tests: `frontend/tests/ui/state/<unit-name>.test.ts`,
  `frontend/tests/ui/views/<ViewName>.test.ts`,
  `frontend/tests/ui/components/<BlockName>.test.ts`.
- Test names must match the production file's basename exactly (minus extension)
  so the boundary script can enforce coverage.
- Existing API client files keep their names and locations.

## 8. Change-impact contract

- A workflow change touches exactly one domain unit, its test, and
  `use-workspace` wiring only if the binding surface changes.
- A view change touches exactly that view, its test, and at most one shared
  building block.
- Adding a view requires: the view, its view-model type, a test file, and wiring
  in `use-workspace`/`App.vue`; no unrelated unit changes.
- Adding a workflow requires: one state unit, its test, wiring, and (if it has a
  new visual area) a view. It must not add rules to `App.vue`.
- A shared-block change must keep every consumer's rendered class/ARIA contract
  identical or update all consumers and the parity checklist together.

## 9. Review gates

A change is compliant only when:
1. `npm run check:ui` passes (layer, cycle, scaffold, and test-map rules).
2. `npm run test:ui` passes with every production module covered.
3. `npm run build` and `vue-tsc` pass.
4. The parity checklist has no unexplained difference.
5. A manual review confirms semantic duplication that static checks cannot see.
6. No source file mixes data access, domain rules, and visual markup.

## References

- [Feature specification](../spec.md)
- [Implementation plan](../plan.md)
- [Data model](../data-model.md)
- [Verification contracts](./verification-contracts.md)
