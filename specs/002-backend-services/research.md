# Research: Backend Service Extraction and Unified Data Access

**Feature**: `specs/002-backend-services`
**Date**: 2026-10-30

## Summary

The refactor will introduce a small, standard-library-only `choosier/services/`
package for application decisions, keep the existing `chooser`, `preview`,
`launcher`, and `storage` modules as the core primitives, and move web-only
image/video mechanics into `choosier/web_media.py`. History reads will flow
through one structured read primitive, while a history service becomes the
only application-layer entry point for history changes.

No `NEEDS CLARIFICATION` items remain. The feature specification and the
existing public contracts determine every decision below.

## Decision 1: Layer core services separately from web-only media

**Decision**: Add `choosier/services/` containing browse, state, pick, opening,
history, error, and model modules. Keep all of them free of web, TUI, and
Pillow imports. Put image decoding, thumbnails, and video validation in
`choosier/web_media.py`, which only the web adapter imports.

**Rationale**: The constitution requires a UI-agnostic, standard-library-only
core and optional UI/web dependencies. Pillow is part of the `web` extra, so
media mechanics cannot live in a core service. Browse, state, pick, opening,
and history decisions are shared application behavior and belong in the core.

**Alternatives considered**:

- Keep media helpers in `web.py` (rejected: route-local logic would remain).
- Put media in a core service (rejected: it would make Pillow a mandatory core
  import and violate the dependency boundary).
- Create one large service module (rejected: poor discoverability and harder
  independent testing).

## Decision 2: One structured history read primitive, one command service

**Decision**: Make `storage.read_log_entries` the single structured read path.
Reimplement `storage.get_logged_items` and keep `storage.load_log` as thin
derivations from it. Add `HistoryService` in `choosier/services/history.py`
for application reads and all history changes. Adapters use the service; they
do not import `choosier.storage` or touch history files directly.

`HistoryService.snapshot()` performs one read and returns entries, logged
names, and display lines. `append`, `remove`, `remove_many`, `archive`, and
`clear` call the existing storage commands and translate `OSError` into
`ServiceError` with the current user-facing messages.

**Rationale**: Today `read_log_entries`, `load_log`, and `get_logged_items`
contain overlapping parsing logic, and each adapter chooses a different
helper. One read primitive removes that drift while preserving the existing
legacy/malformed-line behavior.

**Compatibility nuance**: `read_log_entries` currently tolerates `OSError` and
returns an empty list, while `get_logged_items` propagates errors after an
existence check. The unified primitive will take an `ignore_errors` flag
(default tolerant) so `read_log_entries`/`load_log`/state keep their current
tolerant behavior and `get_logged_items` keeps its current strict behavior.
This is a behavior-preservation detail, not a new public contract.

**Alternatives considered**:

- Replace `storage.py` with a repository class (rejected: unnecessary churn and
  risk to the compatibility exports in `choosier/__init__.py` and `main.py`).
- Make every read tolerant (rejected: changes current selection error
  behavior).
- Keep the separate JSONL parser in `get_logged_items` (rejected: leaves two
  sources of truth).

## Decision 3: Explicit, interface-neutral service failures

**Decision**: Add `FailureKind` and `ServiceError` in
`choosier/services/errors.py`. Services raise `ServiceError` for business
failures and history-write failures. Compatibility-critical history read or
directory listing errors that were previously unclassified continue to
propagate so the existing web catch-all still returns 500
`"Internal server error"`. The web adapter registers one `ServiceError` handler
that maps the failure kind to the existing error envelope and status.
Transport-specific range parsing stays in `web.py` and continues to use
`ApiError`.

Mapping:

| Service failure | HTTP code | Status |
| --- | --- | --- |
| `INVALID_INPUT` | `invalid_request` | 400 |
| `FORBIDDEN` | `forbidden` | 403 |
| `NOT_FOUND` | `not_found` | 404 |
| `PAYLOAD_TOO_LARGE` | `payload_too_large` | 413 |
| `UNSUPPORTED_MEDIA_TYPE` | `unsupported_media_type` | 415 |
| `RANGE_NOT_SATISFIABLE` | `range_not_satisfiable` | 416 |
| `IO_ERROR` | `internal_error` | 500 |

**Rationale**: Services must not depend on FastAPI or HTTP statuses, but the
web adapter still needs to produce the exact existing envelope. A shared
failure vocabulary keeps the mapping in one place and makes CLI/TUI mapping
explicit.

**Alternatives considered**:

- Reuse `ApiError` in services (rejected: couples core logic to the web
  adapter).
- Return result objects (rejected: larger control-flow change and more churn
  than typed exceptions for this codebase).
- Let all raw exceptions escape (rejected: business and history-write failures
  would keep route-local branching and messages could drift).

## Decision 4: State assembly returns full data; adapters keep their existing caps

**Decision**: `build_state` computes candidates, history, totals, and an
optional cap. The web adapter uses the 200-line cap with its current
first-remaining/last-history slicing. The TUI passes `max_lines=None` and keeps
its existing "last 200" rendering behavior. `PANEL_MAX_LINES = 200` moves to
`services/state.py` so the cap value has one source.

**Rationale**: The web and TUI currently differ in which end of the remaining
list is shown. Unifying the slice direction would change TUI behavior. The
service should own candidate/history/total assembly, while each adapter keeps
its established presentation policy.

**Alternatives considered**:

- One shared cap policy (rejected: changes existing TUI presentation).
- Have the service return only web-capped data (rejected: TUI would need a
  second read or would silently change behavior).
- Move rendering into the service (rejected: UI coupling).

## Decision 5: Pick service with optional preview work

**Decision**: `pick()` owns target validation, seed/RNG construction, candidate
selection, empty-versus-exhausted classification, optional logging, and an
optional preview. The web adapter requests a preview; the CLI does not; the TUI
keeps its existing preview update path. `commit=False` lets the CLI print the
selected name before appending through `HistoryService`, preserving output
order if the write fails.

**Rationale**: The web response needs a preview, but the CLI should not pay for
extra file reads. Keeping preview work optional preserves current performance
and avoids forcing a preview representation into the CLI.

**Alternatives considered**:

- Always build a preview (rejected: extra I/O for CLI picks).
- Keep separate web/CLI/TUI pick flows (rejected: duplicated state mapping and
  logging behavior).

## Decision 6: Preserve existing history write mechanics

**Decision**: Do not change `log_selection` append mechanics, rotation, archive
naming, or the atomic temp-file rewrite used by removals. `HistoryService`
wraps errors but does not introduce file locking or a new persistence format.

**Rationale**: The feature is behavior-preserving and the constitution requires
history writes to remain atomic and archives to preserve prior logs. Existing
removals already rewrite atomically; appends are single-line additions, and the
parser ignores malformed/partial trailing lines. Introducing whole-file
rewrites for every append would change concurrency and permission behavior.

**Alternatives considered**:

- Rewrite the whole log on every append (rejected: behavior/performance change
  and risk of lost concurrent updates).
- Add cross-process locking (rejected: new behavior not requested by the
  specification).
- Introduce a database (rejected: the project has no database and the
  constitution favors local, dependency-light storage).

## Decision 7: Preserve compatibility exports and test seams

**Decision**: Keep the existing `storage` functions and `chooser` signatures.
Keep the public re-exports in `choosier/__init__.py` and `main.py` working.
Existing behavior tests keep their assertions; only imports and patch targets
move when code moves. Add direct tests for every service operation and
source-level boundary checks.

**Rationale**: The specification freezes CLI, TUI, web, and history behavior.
The package also exports convenience helpers, and `main.py` is a documented
backward-compatible entrypoint. Removing those would create unrelated breakage.

**Alternatives considered**:

- Delete legacy helpers and update all callers/tests (rejected: unnecessary
  public-API risk and larger diff).
- Test only through adapters (rejected: fails the requirement for direct,
  interface-free service tests).

## Packaging Decision

Add `choosier.services` to `[tool.setuptools] packages` in `pyproject.toml`.
The current explicit package list only includes `choosier`; without this change,
`uv build` would omit the new subpackage from the wheel. This is a packaging
configuration update, not a new dependency.

## Resolved Unknowns

- **Database interpretation**: The project has no database; the feature applies
  to the local JSON Lines history store. No database is introduced.
- **Interface scope**: CLI, TUI, and web all use the shared history service and
  applicable shared application services.
- **State cap behavior**: Preserve the web and TUI differences described in
  Decision 4.
- **Preview cost**: Preserve CLI behavior by making preview generation optional.
- **Error compatibility**: Preserve the 001 API error envelope, CLI exit codes,
  and TUI messages through explicit adapter mapping.
