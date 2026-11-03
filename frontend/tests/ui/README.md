# Frontend tests

The frontend has two independent test runners. They must stay separate:

| Runner | Files | Command | Scope |
| --- | --- | --- | --- |
| Node's built-in test runner | `tests/**/*.test.mjs` | `npm run test:api` | API client, generated contract, and static source boundaries |
| Vitest + happy-dom | `tests/ui/**/*.test.ts` | `npm run test:ui` | State units, presentation views, and shared blocks |

Vitest includes only `tests/ui/**/*.test.ts`, so the Node tests are never
collected by it. `npm run test:api` likewise targets only `.mjs` files. There is
no single command that merges the two; the verification steps run both.

## UI test layout

Every state unit, view, and shared block gets exactly one isolated test file, at
the path that mirrors its production module:

| Production file | Required test file |
| --- | --- |
| `src/state/<name>.ts` | `tests/ui/state/<name>.test.ts` |
| `src/views/<Name>.vue` | `tests/ui/views/<Name>.test.ts` |
| `src/components/<Name>.vue` | `tests/ui/components/<Name>.test.ts` |

`scripts/check-ui-boundaries.mjs` (R-07 in
`../specs/004-modular-ui-components/contracts/verification-contracts.md`) fails
when a production file has no matching test file. Do not merge two modules into
one test file or add a second test file for the same module.

## Writing a UI test

- Write the failing test first, then implement the module.
- Mount views and blocks in isolation with `@vue/test-utils`; do not mount the
  whole app.
- Test lifecycle-bearing state units through the host-component helper in
  `tests/ui/test-helpers.ts`, or an `effectScope`.
- Mock API calls at the `src/api` boundary with the helpers in
  `tests/ui/test-helpers.ts`; no test performs network I/O.
- Use fake timers for the 250ms debounce and for stale-response guards.
- Assert exact user-visible text, classes, ARIA attributes, keyboard behavior,
  and emitted intents. Those are part of the behavior-preserving contract.

Shared helpers live in `tests/ui/test-helpers.ts`; they are test-only and are not
picked up as a test file.

## Commands

```sh
npm run test:ui      # Vitest UI tests
npm run test:api     # Node API/contract tests
npm run check:ui     # module, import, duplicate, and test-mapping rules
npm run check:api    # generated contract freshness
npm run build        # type check and production bundle
```
