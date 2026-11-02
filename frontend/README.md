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

## API client boundary

`src/api.ts` is the only frontend module that makes network calls, names
`/api/...` endpoints, or reads error envelopes. Screens and components
call the exported `api` object and display failures through
`apiErrorMessage`. `src/api-contract.generated.ts` is generated from the
frozen backend contract (`../specs/001-standardize-api-responses/contracts/api-contract.json`)
by `scripts/generate-api-contract.mjs` and must never be hand-edited.

| Script | Purpose |
| --- | --- |
| `npm run generate:api` | regenerate the contract module from the contract JSON |
| `npm run check:api` | fail with a `stale API contract` message when the generated module no longer matches |
| `npm run test:api` | node test runner covering query encoding, route coverage, the facade, error parsing, drift, and the `.vue` source boundary |

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
