# choosier frontend

Vue 3 + Vite single-page app for the choosier web UI. The API it talks
to lives in `../choosier/web.py`.

## Development

Terminal 1 — API server:

```sh
uv run choosier --web --port 8765
```

Terminal 2 — Vite dev server with hot reload (proxies `/api` to 8765):

```sh
npm install
npm run dev
```

## Production build

```sh
npm run build
```

Output lands in `../choosier/web_static/`, which `choosier --web`
serves from the same origin.

## Module layout

The interface is split into three layers, with `src/App.vue` as the only
composition root:

```text
src/App.vue              layout + view-model/intent bindings only
src/state/use-*.ts       workflow state, validation, API access, sequencing
src/views/*.vue          presentation-only visual areas
src/components/*.vue     shared presentation blocks (PanelShell, EmptyState)
```

The allowed dependency direction is `App.vue → state/`, `App.vue → views/`,
`views/ → components/`, and `state/ → api*`. State units never import views or
shared blocks; views never import the API client or a domain state unit. The two
view-local interaction units are the only exceptions: `PreviewPanel.vue` may
import `state/use-preview.ts`, and `ImageViewer.vue` may import
`state/use-image-viewer.ts`. No other module may import those two units.

`src/components/` holds only genuinely shared presentation blocks. Panel
scaffold classes (`.panel`, `.panel-header`, `.panel-empty`, `.panel-actions`)
are owned by `PanelShell.vue` and `EmptyState.vue`; views compose them through
slots and unique consumer classes.

Every production module under `src/state/`, `src/views/`, and `src/components/`
must have a matching test file under `tests/ui/` with the same basename:
`tests/ui/state/use-thing.test.ts`, `tests/ui/views/Thing.test.ts`, or
`tests/ui/components/ThingBlock.test.ts`. The boundary check fails when a
mapped test file is missing.

## API client boundary

`src/api.ts` is the only frontend module that makes network calls, names
`/api/...` endpoints, or reads error envelopes. State units call the exported
`api` object; views receive ready-to-render data and report intents. Failures
are converted to messages by `src/state/use-status.ts` through
`apiErrorMessage`. `src/api-contract.generated.ts` is generated from the
frozen backend contract (`../specs/001-standardize-api-responses/contracts/api-contract.json`)
by `scripts/generate-api-contract.mjs` and must never be hand-edited.

| Script | Purpose |
| --- | --- |
| `npm run generate:api` | regenerate the contract module from the contract JSON |
| `npm run check:api` | fail with a `stale API contract` message when the generated module no longer matches |
| `npm run test:api` | node test runner covering query encoding, route coverage, the facade, error parsing, drift, and the `.vue` source boundary |
| `npm run check:ui` | dependency-free boundary check for view API/state isolation, state isolation, thin `App.vue`, acyclic imports, raw panel scaffold, and test-file mapping |
| `npm run test:ui` | Vitest + Vue Test Utils tests for state units, views, shared blocks, and the boundary rules |

Node 22.18 or newer is required: the client tests use the built-in test
runner and TypeScript type stripping.

Adding or changing a route (frozen contract JSON first):

1. Update `../specs/001-standardize-api-responses/contracts/api-contract.json`
   and its backend tests.
2. Run `npm run generate:api`.
3. Add or update the operation map in `src/api-operations.ts` and the
   facade methods in `src/api.ts` (plus `src/types.ts` when a new request
   type is needed).
4. Add or update `src` client tests in `tests/`.
5. Run `npm run check:api`, `npm run test:api`, and `npm run build`.
