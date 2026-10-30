# Implementation Plan: Backend Service Extraction and Unified Data Access

**Branch**: `refactor/02-backend-services` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-backend-services/spec.md`

**Design artifacts**: [research.md](./research.md) ·
[data-model.md](./data-model.md) ·
[contracts/service-boundaries.md](./contracts/service-boundaries.md) ·
[quickstart.md](./quickstart.md)

## Summary

Extract every nontrivial web-reachable operation out of FastAPI route handlers
into a new, standard-library-only `choosier/services/` package, then make the
CLI, TUI, and web adapters use those shared operations. Unify history data
access behind one structured read primitive (`storage.read_log_entries`) and one
application-layer history facade (`HistoryService`) for append, removal,
archive, and clear. Move web-only image/video mechanics into
`choosier/web_media.py` so the core stays free of Pillow and web framework
imports.

The refactor is behavior-preserving. It adds no database, route, flag,
dependency, persistence format, or user-visible feature. The existing API
contract from `specs/001-standardize-api-responses/contracts/api-contract.json`
remains authoritative, and all pre-existing behavior tests must pass with
unchanged assertions.

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >=3.12`; CI uses 3.12).

**Primary Dependencies**: No mandatory third-party runtime dependencies. Core
services use the standard library plus existing core modules. Optional extras
remain `ui` (Textual) and `web` (FastAPI, Uvicorn, Pillow). Development tools:
pytest, Ruff, mypy, httpx.

**Storage**: Local JSON Lines history file (`.choosier.jsonl`) colocated with
the target or supplied by override, plus timestamped `.old` archives. No
database exists and none will be introduced.

**Testing**: pytest/unittest, FastAPI `TestClient` for HTTP contract tests, and
direct service tests. Tests must run without a network, web server, browser, or
interactive terminal.

**Target Platform**: Local desktop CLI/TUI on Linux, macOS, and Windows, plus a
loopback-only local web UI. The Vue frontend build is unchanged.

**Project Type**: Single Python package with CLI, TUI, and local web adapters;
frontend assets are built separately and served by the web adapter.

**Performance Goals**: Preserve current I/O behavior; avoid duplicate history
reads and unnecessary preview work. The direct service test subset must finish
in under 10 seconds (`SC-009`). No throughput or latency tuning is in scope.

**Constraints**:

- Core `choosier.services` must be standard-library-only and UI-agnostic.
- No new mandatory runtime dependency; no core import of FastAPI, Textual,
  Pillow, Uvicorn, or Pydantic.
- No changes to API paths, schemas, headers, error codes/messages, CLI flags,
  exit codes, TUI shortcuts/messages, history format, archive naming, or
  on-disk layout.
- History writes remain atomic and archives preserve prior logs.
- The web server remains bound to `127.0.0.1`.
- Ruff line length is 88 and mypy strict mode must pass.

**Scale/Scope**: One Python package, 12 existing `/api` routes, three adapters,
one local history file, seven new service modules, and one new web-only media
module. No database or multi-tenant scale concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
| --- | --- | --- |
| I. Deterministic Selection | Selection remains in one UI-agnostic implementation; seeded picks use a fresh RNG; ordering, filters, and repeat prevention are unchanged. | PASS |
| II. Local and Private by Default | No network behavior, telemetry, or online dependency is added; web binding and explicit launch behavior are unchanged. | PASS |
| III. User Data Is Inviolable | No user-selected file is modified; history writes continue through the existing atomic storage mechanics; failures leave prior history intact. | PASS |
| IV. Shared Core, Thin Interfaces | New services are stdlib-only; CLI/TUI/web become adapters; Pillow stays in the optional web-only layer. | PASS |
| V. Verified, Boring Changes | Existing behavior tests remain; every extracted operation gets direct tests; full test/lint/format/mypy/frontend-build gates apply. | PASS |

**Post-design re-check**: The design preserves all five principles. There are no
violations and no complexity exceptions requested.

## Project Structure

### Documentation (this feature)

```text
specs/002-backend-services/
├── plan.md                              # This file
├── spec.md                              # Feature specification
├── research.md                          # Phase 0 architecture decisions
├── data-model.md                        # Phase 1 service entities and rules
├── quickstart.md                        # Phase 1 validation guide
├── checklists/
│   └── requirements.md                  # Specification quality checklist
├── contracts/
│   └── service-boundaries.md            # Internal service and adapter contract
└── tasks.md                             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
choosier/
├── __init__.py                          # compatibility exports (unchanged)
├── __main__.py                          # module entrypoint (unchanged)
├── chooser.py                           # selection primitives (unchanged signatures)
├── cli.py                               # CLI adapter
├── tui.py                               # Textual adapter
├── web.py                               # FastAPI adapter and frozen DTOs
├── web_media.py                         # NEW: web-only image/video mechanics
├── launcher.py                          # OS launch primitive (unchanged)
├── preview.py                           # preview primitives (unchanged)
├── storage.py                           # JSONL history I/O and single parser
└── services/                            # NEW: stdlib-only application services
    ├── __init__.py
    ├── browse.py
    ├── errors.py
    ├── history.py
    ├── models.py
    ├── opening.py
    ├── pick.py
    └── state.py

tests/
├── api_contract_support.py              # frozen contract helpers (unchanged)
├── test_api_compat.py                   # patch seams only
├── test_api_contract.py                 # unchanged assertions
├── test_api_errors.py                   # patch seams only
├── test_chooser.py                      # unchanged behavior
├── test_cli.py                          # unchanged behavior
├── test_launcher.py                     # unchanged behavior
├── test_preview.py                      # unchanged behavior
├── test_services_boundaries.py          # NEW: import/source boundary checks
├── test_services_browse.py              # NEW
├── test_services_history.py             # NEW
├── test_services_opening.py             # NEW
├── test_services_pick.py                # NEW
├── test_services_state.py               # NEW
├── test_storage.py                      # unified read-primitive coverage
├── test_tui.py                          # unchanged behavior
└── test_web.py                          # patch seams only

frontend/                                # unchanged Vue application
pyproject.toml                           # add choosier.services package
README.md                                # document service boundaries
CHANGELOG.md                             # non-behavioral refactor note
```

**Structure Decision**: Keep the single-package layout (`choosier/`) and add one
subpackage for shared services. Do not create a separate backend project or a
repository/database layer. `web_media.py` stays beside `web.py` because it
imports Pillow and is only valid with the `web` extra.

## Service Architecture

### Module responsibilities

| Module | Responsibility | May import |
| --- | --- | --- |
| `services/errors.py` | `FailureKind` and `ServiceError` vocabulary | stdlib only |
| `services/models.py` | Immutable `BrowseEntry`, `BrowseListing`, `HistorySnapshot`, `StateSnapshot`, `PickOutcome`, `OpenOutcome` | `chooser`, `preview`, `storage` types |
| `services/browse.py` | Directory listing with ordering, parent, and permission mapping | `models`, `errors`, `pathlib` |
| `services/state.py` | Candidate/history/total assembly and `PANEL_MAX_LINES` | `chooser`, `history`, `models`, `errors` |
| `services/pick.py` | Selection, seeded RNG, empty/exhausted classification, optional logging/preview | `chooser`, `history`, `models`, `errors` |
| `services/opening.py` | Existence check and OS launch mapping | `launcher`, `models`, `errors` |
| `services/history.py` | `HistoryService` read snapshot and all history mutations | `storage`, `models`, `errors` |
| `web_media.py` | Web-only image/archive/video validation and renditions | `preview`, `PIL`, `services.errors` |

### Dependency rules

1. `choosier.services` imports only stdlib and existing core modules
   (`chooser`, `preview`, `launcher`, `storage`).
2. `choosier.services` never imports `web`, `tui`, `web_media`, `cli`, FastAPI,
   Starlette, Pydantic, Uvicorn, Textual, Rich, or Pillow.
3. `web_media` is imported only by `web.py`.
4. Adapters depend on services; services never depend on adapters.
5. Existing compatibility wrappers keep working:
   `storage.load_log`, `storage.get_logged_items`,
   `storage.remove_log_item`, `chooser.list_available_items`,
   `chooser.get_unselected_item`, `preview.preview_entry`,
   `launcher.launch_path`, and the exports in `choosier/__init__.py` and
   `main.py`.

### Unified history access

Read path:

```text
HistoryService.snapshot()
  -> storage.read_log_entries()        # single parser and structured read
  -> entries, logged names, display lines

storage.load_log()                     # compatibility wrapper
storage.get_logged_items()             # compatibility wrapper, strict mode
chooser.list_available_items()         # existing selection wrapper
```

Write path:

```text
HistoryService.append/remove/remove_many/archive/clear
  -> existing storage commands
  -> existing JSONL append, rotation, atomic rewrite, archive naming
```

`storage.read_log_entries` gains `ignore_errors: bool = True` so
`read_log_entries`/`load_log`/state keep their tolerant behavior while
`get_logged_items` retains its current strict behavior after its existence
check. No adapter opens, writes, renames, deletes, or parses the history file.

### Request flow

Example `POST /api/pick`:

```text
PickRequest
  -> web adapter validates/parses the request
  -> services.pick.pick(..., dry_run=request.dry_run, include_preview=True)
       -> chooser.get_unselected_item (shared selection)
       -> HistoryService.append (unless dry run)
       -> preview_entry (only when requested)
  -> PickOutcome
  -> web adapter maps status/item/logged/preview to PickResponse
```

`GET /api/state`, `GET /api/browse`, `POST /api/open`, and the four history
routes follow the same one-call shape. `GET /api/image` uses `read_image` plus
an optional `make_thumbnail`; `GET /api/video` uses `read_video` and leaves
byte-range parsing in the adapter.

## Adapter Migration

### Web (`choosier/web.py`)

- Keep every Pydantic request/response model, field default, and validation
  constraint exactly as-is.
- Replace inline browse/state/pick/open/history logic with service calls.
- Move image/archive/video helpers and media constants to `web_media.py`.
- Register one `ServiceError` exception handler using the failure-to-envelope
  table in `contracts/service-boundaries.md`.
- Keep `ApiError` for transport-only byte-range parsing (`Range`, `If-Range`)
  and retain the existing `StarletteHTTPException`, validation, and catch-all
  handlers.
- Keep response headers (`Cache-Control: no-store`,
  `X-Content-Type-Options: nosniff`, `Content-Range`) and status codes
  unchanged.
- Keep `DEFAULT_PORT`, `STATIC_DIR`, and the static-file mount unchanged.
- Map `PickOutcome.preview` directly instead of re-reading the picked entry.

### CLI (`choosier/cli.py`)

- Resolve the log path through shared `chooser.resolve_log_path` semantics so
  explicit override, blank fallback, and `~` expansion are consistent.
- Use `HistoryService.clear()` for `--reset` and keep the exact success/failure
  strings and exit codes.
- Use `build_state(..., max_lines=None).remaining` for `--list`; keep the
  existing raw-directory empty/exhausted check and exit codes 3/4.
- Use `pick(..., commit=False)` for the pick flow. Print
  `"The choice: <item>"` before committing through `HistoryService.append`, so
  a write failure preserves the current output order. Keep dry-run text and
  `"Added in <log_path> with timestamp."` unchanged.
- Keep all flags, prompts, parser errors (exit 2), and `--ui`/`--web` dispatch
  unchanged.

### TUI (`choosier/tui.py`)

- Use `build_state(..., max_lines=None)` for panel refresh; feed
  `snapshot.remaining` and `entry.display` into the existing `render_panel`
  last-200 rendering. Import `PANEL_MAX_LINES` from `services.state`.
- Use `pick(..., seed=seed, dry_run=dry_run)` and map every status to the
  existing messages. Keep the current target-is-directory precheck before
  parsing the seed so `"Invalid Path."` wins over an invalid-seed message.
- Use `HistoryService` for archive and clear; keep status text and confirmation
  behavior unchanged.
- Use `open_entry`; map `NOT_FOUND` to `"Gone: <name>"` and `IO_ERROR` to the
  service message.
- Keep `preview_entry` for the preview pane, widgets, shortcuts, focus behavior,
  and `PANEL_MAX_LINES` rendering.

### Core primitives

- `storage.py`: implement the single `read_log_entries` parser, derive
  `load_log` and `get_logged_items`, and leave append/removal/archive/clear
  mechanics unchanged.
- `chooser.py`: keep all signatures and deterministic selection behavior; no
  service imports.
- `preview.py` and `launcher.py`: unchanged public behavior.
- `__init__.py` and `main.py`: keep compatibility exports unchanged.

## Data Flow and Compatibility

| Nuance | Required preservation |
| --- | --- |
| State caps | Web shows first 200 remaining and last 200 history; TUI passes `max_lines=None` and `render_panel` shows the last 200 of both. Do not unify slice direction. |
| Invalid path | State and pick return a successful domain outcome (`valid_path=false` / `invalid_path`); browse and open keep their existing errors. |
| Empty vs exhausted | `pick` uses raw directory contents: empty target -> `empty`, non-empty but all logged -> `exhausted`. |
| Filter conflict | Web state/pick reject `files_only && dirs_only` with the existing 400 message; CLI keeps argparse validation; TUI uses a radio group. |
| History tolerance | Readers ignore blank/malformed lines, accept current JSONL/legacy/plain lines, and preserve duplicate entries. State reads stay tolerant; selection keeps `get_logged_items` strictness. |
| History writes | Append format, rotation threshold, atomic rewrites, verbatim retention, archive naming, and failure messages are unchanged. |
| Dry run / commit | `dry_run=True` never logs. `commit=False` supports CLI output ordering; the caller appends through `HistoryService`. |
| Preview cost | Web requests previews; CLI does not; TUI keeps its existing preview update path. |
| Media limits | Use the existing preview constants and Pillow behavior; keep `PREVIEW_MAX_IMAGE_BYTES` patchable through `choosier.preview`. |
| Public exports | `choosier/__init__.py` and `main.py` continue to import the same names. |
| Packaging | Add `choosier.services` to `[tool.setuptools] packages`; otherwise the wheel omits the subpackage. |

## Testing Strategy

### Existing behavior tests

- Keep every assertion in `tests/test_api_contract.py`,
  `tests/test_api_compat.py`, `tests/test_api_errors.py`, `tests/test_web.py`,
  `tests/test_cli.py`, `tests/test_tui.py`, `tests/test_chooser.py`,
  `tests/test_storage.py`, `tests/test_preview.py`, and
  `tests/test_launcher.py` unchanged.
- Update only imports and patch targets to the new seams:
  - `choosier.storage.read_log_entries` and storage mutations for history.
  - `choosier.launcher.launch_path` for opening.
  - `choosier.preview.PREVIEW_MAX_IMAGE_BYTES` for image limits.
  - `choosier.services.browse.Path.iterdir` for browse permission tests.
- The authoritative API contract JSON and Markdown files are not edited.

### Direct service tests

Add focused tests that construct no request or UI object:

| Test file | Coverage |
| --- | --- |
| `test_services_browse.py` | ordering, parent/root, missing target, permission failure |
| `test_services_state.py` | invalid path, filter conflict, hidden/type filters, managed-file exclusion, totals, 200 cap, no-cap, malformed history |
| `test_services_pick.py` | seeded repeatability, dry-run, `commit=False`, empty/exhausted, invalid path, conflict, write failure, optional preview |
| `test_services_opening.py` | success, missing entry, launcher failure |
| `test_services_history.py` | snapshot derivation, tolerant/strict reads, append, remove, batch remove, archive, clear, duplicates, missing file, exact failure messages |
| `test_services_boundaries.py` | services import only allowed modules; no duplicate history parser; adapters do not bypass services |

### Contract and integration tests

- Run the frozen API contract suite and the full behavior suite.
- Verify the web envelope for every service failure kind through the existing
  tests.
- Verify CLI exit codes 0/1/3/4 and output strings.
- Verify TUI panel/status behavior through the existing tests.
- Add a cross-interface history test using one fixture file with current,
  legacy, blank, malformed, and duplicate lines; compare entries, totals,
  remaining candidates, removal counts, and archive results.

### Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy choosier main.py tests
(
  cd frontend
  npm run build
)
uv build
```

## Packaging and Documentation

- Add `choosier.services` to `[tool.setuptools] packages`.
- Keep package data and frontend asset rules unchanged.
- Update `README.md` with the service boundaries and history ownership:
  storage owns file I/O/parsing, `HistoryService` owns application history
  reads/writes, adapters are thin, and media is web-only.
- Add a non-behavioral `CHANGELOG.md` note under `Unreleased`.
- Do not change version numbers, extras, entry points, or dependencies.

## Implementation Sequence

1. **Service scaffolding**: add `choosier/services/` with `errors.py` and
   `models.py`; update `pyproject.toml` package list.
2. **Unified history**: add `ignore_errors` to `read_log_entries`, derive
   `load_log`/`get_logged_items`, implement `HistoryService`, and add storage /
   history service tests.
3. **Shared operations**: implement browse, state, pick, and opening services
   with direct tests.
4. **Web media**: extract image/archive/video mechanics and constants into
   `web_media.py` with direct tests and exact failure messages.
5. **Web adapter**: migrate the business routes to services, keep
   `/api/defaults` transport-only, add the `ServiceError` handler, preserve
   DTOs/headers/ranges, and update patch targets.
6. **CLI adapter**: migrate reset/list/pick to `HistoryService`, `build_state`,
   and `pick(..., commit=False)` while preserving output and exit codes.
7. **TUI adapter**: migrate panels, pick, archive, clear, and open while
   preserving rendering and messages.
8. **Documentation and gate**: update README/CHANGELOG, run the full quality
   gate, verify the wheel contains `choosier/services/`, and compare behavior
   against the frozen contract.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| State cap direction drifts between web and TUI | Keep the cap in `build_state`, pass `max_lines=None` for TUI, and add direct tests for both shapes. |
| `get_logged_items` loses its strict error behavior | Keep the existence check and call `read_log_entries(..., ignore_errors=False)`; test missing-file and permission cases. |
| Patch targets stop affecting moved code | Access `storage`, `launcher`, and `preview` through their modules; document exact seams and update only targets. |
| CLI output order changes on a write failure | Use `pick(..., commit=False)`, print the choice, then append through `HistoryService`. |
| History is mutated outside the service | Keep all writes in `storage.py` behind `HistoryService`; add adapter source checks and review the diff. |
| API envelope or messages drift | Map `FailureKind` in one handler; run the 001 contract and error suites unchanged. |
| Preview or media work becomes mandatory in core | Keep `web_media.py` web-only, make preview work optional in `pick`, and enforce import boundaries in tests. |
| Wheel omits the new package | Add `choosier.services` to the explicit package list and inspect the built wheel in quickstart. |

## Complexity Tracking

No constitution violations and no complexity exceptions are requested. The
design adds one small service package and one web-only media module; it does not
introduce a database, repository framework, dependency, or deployment boundary.

## Definition of Done

- All 22 functional requirements and 9 success criteria in `spec.md` are
  satisfied.
- Existing behavior and API contract tests pass with unchanged assertions.
- Every extracted operation has direct success and failure tests.
- CLI, TUI, and web use the same history read/write path.
- Adapters contain only input parsing, one service call, and outcome mapping.
- `choosier.services` has no UI/web/Pillow imports.
- Full quality gate passes and the wheel contains `choosier/services/`.
- README and CHANGELOG document the new boundaries.
