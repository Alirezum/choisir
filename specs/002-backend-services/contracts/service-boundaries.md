# Service Boundary Contract

**Feature**: `specs/002-backend-services`
**Date**: 2026-10-30
**Status**: Design baseline for implementation

This contract defines the internal service layer introduced by the refactor. It
freezes the adapter-facing behavior that must not change and names the exact
seams that tests may patch. Public HTTP, CLI, TUI, and history contracts remain
owned by their existing specifications; the authoritative HTTP contract is
`specs/001-standardize-api-responses/contracts/api-contract.json`.

## 1. Layers and Dependency Rules

```text
CLI adapter ─┐
TUI adapter ─┼──> choosier.services ──> chooser / preview / launcher / storage
Web adapter ─┘                              (stdlib-only core primitives)

Web adapter ────> choosier.web_media ────> preview + Pillow (web extra only)
```

Rules:

1. `choosier.services` is standard-library-only. It must not import `fastapi`,
   `starlette`, `uvicorn`, `pydantic`, `textual`, `rich`, `PIL`, `choosier.web`,
   `choosier.tui`, `choosier.web_media`, or `choosier.cli`.
2. `choosier.web_media` is web-only. It may import Pillow and
   `choosier.services.errors`, and must not be imported by `choosier.services`,
   `choosier.cli`, or `choosier.tui`.
3. Adapters (`cli.py`, `tui.py`, `web.py`) translate input and outcomes. They do
   not parse history files, choose candidates, validate media, or perform
   history mutations directly.
4. `choosier.storage` owns history file I/O and parsing. `HistoryService` is the
   application-layer facade over that ownership. `chooser.py` and compatibility
   wrappers may read history only through the derived storage read functions.
5. Adapters create a `HistoryService` per operation from an already resolved
   log path. Log-path resolution remains the shared
   `chooser.resolve_log_path` / `resolve_default_log` behavior.

## 2. Package Layout

```text
choosier/
├── services/
│   ├── __init__.py       # public service exports
│   ├── browse.py         # browse_directory
│   ├── errors.py         # FailureKind, ServiceError
│   ├── history.py        # HistoryService
│   ├── models.py         # service result dataclasses
│   ├── opening.py        # open_entry
│   ├── pick.py           # pick
│   └── state.py          # PANEL_MAX_LINES, build_state
├── web_media.py          # web-only image/video mechanics
├── web.py                # FastAPI adapter
├── cli.py                # CLI adapter
├── tui.py                # Textual adapter
├── chooser.py            # shared selection primitives
├── preview.py            # shared preview primitives
├── storage.py            # JSONL history I/O and parsing
└── launcher.py           # OS launch primitive
```

`services/__init__.py` re-exports the adapter-facing surface:
`FailureKind`, `ServiceError`, `HistoryService`, `PANEL_MAX_LINES`,
`BrowseEntry`, `BrowseListing`, `HistorySnapshot`, `StateSnapshot`,
`PickOutcome`, `OpenOutcome`, `browse_directory`, `build_state`, `pick`, and
`open_entry`.

`pyproject.toml` must list both packages explicitly:

```toml
[tool.setuptools]
packages = ["choosier", "choosier.services"]
```

## 3. Shared Failure Vocabulary

`choosier/services/errors.py`:

```python
class FailureKind(StrEnum):
    INVALID_INPUT = "invalid_input"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    RANGE_NOT_SATISFIABLE = "range_not_satisfiable"
    IO_ERROR = "io_error"


class ServiceError(Exception):
    def __init__(
        self,
        kind: FailureKind,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None: ...
```

`ServiceError` contains no HTTP status, framework type, or UI widget. The web
adapter maps it through one exception handler:

| `FailureKind` | HTTP `error.code` | Status |
| --- | --- | --- |
| `INVALID_INPUT` | `invalid_request` | 400 |
| `FORBIDDEN` | `forbidden` | 403 |
| `NOT_FOUND` | `not_found` | 404 |
| `PAYLOAD_TOO_LARGE` | `payload_too_large` | 413 |
| `UNSUPPORTED_MEDIA_TYPE` | `unsupported_media_type` | 415 |
| `RANGE_NOT_SATISFIABLE` | `range_not_satisfiable` | 416 |
| `IO_ERROR` | `internal_error` | 500 |

The handler emits the existing envelope with `detail == error.message` and
`error.details` from the exception. `ApiError` remains only for transport
behavior, specifically byte-range parsing and validation of `Range` /
`If-Range`. The existing `StarletteHTTPException`,
`RequestValidationError`, and catch-all handlers are unchanged.

Service failure sets:

| Operation | Possible `FailureKind`s |
| --- | --- |
| Browse | `NOT_FOUND`, `FORBIDDEN` |
| State | `INVALID_INPUT`; unexpected listing errors propagate as today |
| Pick | `INVALID_INPUT`, `IO_ERROR` for writes; unexpected history/list read errors propagate as today |
| Open | `NOT_FOUND`, `IO_ERROR` |
| History append/remove/archive/clear | `IO_ERROR` |
| Image read/render | `NOT_FOUND`, `INVALID_INPUT`, `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `IO_ERROR` |
| Video read | `NOT_FOUND`, `UNSUPPORTED_MEDIA_TYPE`, `IO_ERROR` |
| Range handling (adapter) | `ApiError` (`invalid_request`, `range_not_satisfiable`) |

## 4. Service Models

`choosier/services/models.py` defines immutable result objects:

```python
@dataclass(frozen=True)
class BrowseEntry:
    name: str
    is_dir: bool

@dataclass(frozen=True)
class BrowseListing:
    path: Path
    parent: Path | None
    entries: tuple[BrowseEntry, ...]

@dataclass(frozen=True)
class HistorySnapshot:
    entries: tuple[LogEntry, ...]
    logged: frozenset[str]
    display: tuple[str, ...]

@dataclass(frozen=True)
class StateSnapshot:
    valid_path: bool
    path: Path
    log_file: Path
    remaining: tuple[str, ...]
    remaining_total: int
    history: tuple[LogEntry, ...]
    history_total: int

PickStatus = Literal["picked", "empty", "exhausted", "invalid_path"]

@dataclass(frozen=True)
class PickOutcome:
    status: PickStatus
    log_file: Path
    item: str | None = None
    logged: bool = False
    preview: Preview | None = None

@dataclass(frozen=True)
class OpenOutcome:
    name: str
```

Invariants:

- `HistorySnapshot.logged` and `.display` are derived from `.entries`; one
  snapshot performs one history read.
- `StateSnapshot.remaining_total` and `.history_total` are full counts before
  any display cap.
- `PickOutcome.item` is non-`None` exactly when `status == "picked"`.
- `PickOutcome.preview` is populated only when the caller requests it.
- `PickOutcome.logged` is true only when this call appended the selection.

## 5. Service Operations

### 5.1 Browse

```python
def browse_directory(path: str | Path) -> BrowseListing
```

Behavior:

- Expand `~`, then preserve the current `Path.is_dir()` check.
- Missing or non-directory target: `ServiceError(NOT_FOUND, "Not a directory")`.
- `iterdir()` failure: `ServiceError(FORBIDDEN, f"Cannot list: {e}")`.
- Order entries directories-first, then case-insensitively by name, with the
  current stable sort key `(not p.is_dir(), p.name.lower())`.
- `parent` is `None` at a filesystem root, otherwise the parent path.

### 5.2 State

```python
PANEL_MAX_LINES = 200

def build_state(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    max_lines: int | None = PANEL_MAX_LINES,
) -> StateSnapshot
```

Behavior:

- Resolve `log_file` through shared `resolve_log_path` semantics: explicit
  override, blank/whitespace fallback, or default colocated with the target.
- If the target is not a directory, return `valid_path=False` with empty
  remaining/history and zero totals. This is a domain outcome, not an error.
- If `files_only` and `dirs_only` are both true, raise
  `ServiceError(INVALID_INPUT, "files_only and dirs_only are mutually exclusive")`.
  The invalid-path outcome takes precedence, as it does today.
- Use `list_candidates` for filtering and managed-file exclusion.
- Treat `FileNotFoundError` from candidate listing as an empty candidate set.
- Read history once through `HistoryService.snapshot()`; derive logged names and
  remaining candidates from that snapshot.
- `max_lines=None` returns full `remaining` and `history`. Otherwise return
  `remaining[:max_lines]` (first items) and `history[-max_lines:]` (most recent
  entries), while totals remain full. The web adapter uses the default 200; the
  TUI passes `None` and keeps its own last-200 panel rendering.
- Preserve current behavior for unexpected listing `OSError`s; do not silently
  convert them into a different HTTP status or message.

### 5.3 Pick

```python
def pick(
    path: str | Path,
    log_file: str | Path | None = None,
    *,
    seed: int | None = None,
    dry_run: bool = False,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
    commit: bool = True,
    include_preview: bool = False,
) -> PickOutcome
```

Behavior:

- Resolve the target and log path as in `build_state`.
- Not a directory: return `status="invalid_path"`, no error.
- Build a fresh `random.Random(seed)` when a seed is supplied; otherwise use the
  existing random choice path. Selection continues to use
  `chooser.get_unselected_item`, so ordering, filters, repeat prevention, and
  the seeded algorithm are unchanged.
- Conflicting filters raise
  `ServiceError(INVALID_INPUT, "files_only and dirs_only are mutually exclusive")`.
- No eligible item: return `"exhausted"` when `any(target.iterdir())` is true,
  otherwise `"empty"`. Preserve the current raw-directory distinction.
- On a pick, append through `HistoryService.append` only when `commit` is true
  and `dry_run` is false; set `logged=True` after a successful append.
  `ServiceError(IO_ERROR, f"Error writing log: {e}")` is raised on failure.
- History read and directory-listing errors raised during selection keep their
  current classification: the web adapter's generic handler still returns 500
  `"Internal server error"`, and direct CLI/TUI callers see the same failure as
  before. Only history writes are wrapped as `ServiceError`.
- `commit=False` suppresses logging and leaves `logged=False`; the caller is
  responsible for calling `HistoryService.append`. The CLI uses this to print
  `"The choice: <item>"` before a potential write failure, preserving output
  order.
- Generate `preview_entry(target / item)` only when `include_preview` is true.
  The web adapter requests it; CLI and TUI keep their current preview behavior.
- `dry_run=True` never appends, regardless of `commit`.

### 5.4 Opening

```python
def open_entry(path: str | Path) -> OpenOutcome
```

Behavior:

- Expand `~`.
- Missing entry: `ServiceError(NOT_FOUND, "Entry is gone")`.
- Delegate to `launcher.launch_path`; an `OSError` becomes
  `ServiceError(IO_ERROR, f"Cannot open: {e}")`.
- Return the entry name on success. Launching remains an explicit adapter action.

### 5.5 History

```python
class HistoryService:
    def __init__(self, log_file: str | Path) -> None: ...

    @property
    def log_file(self) -> Path: ...

    def snapshot(self, *, ignore_errors: bool = True) -> HistorySnapshot: ...
    def read_entries(self, *, ignore_errors: bool = True) -> tuple[LogEntry, ...]: ...
    def logged_items(self, *, ignore_errors: bool = True) -> set[str]: ...
    def display_lines(self, *, ignore_errors: bool = True) -> list[str]: ...

    def append(self, item: str) -> None: ...
    def remove(self, item: str) -> int: ...
    def remove_many(self, items: Collection[str]) -> int: ...
    def archive(self) -> Path | None: ...
    def clear(self) -> bool: ...
```

Behavior:

- The constructor expands `~` once and stores the resolved `Path`.
- `snapshot` calls `storage.read_log_entries` exactly once and derives `logged`
  and `display`. Default reads are tolerant, matching state/TUI behavior.
  `ignore_errors=False` propagates `OSError` for callers that need strict reads.
- `read_entries`, `logged_items`, and `display_lines` are derived convenience
  views over `snapshot`; they do not add another parsing path.
- `append` calls `storage.log_selection`; `remove` calls
  `storage.remove_log_item`; `remove_many` calls `storage.remove_log_items`;
  `archive` calls `storage.archive_log`; `clear` calls `storage.reset_log`.
- Map `OSError` to `ServiceError(IO_ERROR, ...)` with the current messages:
  - append: `"Error writing log: {e}"`
  - remove: `"Error removing history item: {e}"`
  - remove_many: `"Error removing history items: {e}"`
  - archive: `"Error archiving log: {e}"`
  - clear: `"Error resetting log: {e}"`
- `remove_many` with no items returns `0`; the web Pydantic model still rejects
  an empty list with 422.
- Missing history is not an error: `archive` returns `None`, `clear` returns
  `False`, removals return `0`.
- All mutation mechanics (append format, rotation, atomic rewrite, archive
  naming) stay in `storage.py`.

## 6. Web-Only Media Contract

`choosier/web_media.py`:

```python
THUMBNAIL_MAX_SIZE = (480, 480)
THUMBNAIL_QUALITY = 84
PREVIEW_MAX_SIZE = (1600, 1600)
PREVIEW_QUALITY = 90

@dataclass(frozen=True)
class ImagePayload:
    data: bytes
    media_type: str

@dataclass(frozen=True)
class VideoFile:
    path: Path
    media_type: str
    stat_result: os.stat_result


def read_image(path: Path, index: int | None = None) -> ImagePayload: ...
def make_thumbnail(
    data: bytes,
    max_size: tuple[int, int] = THUMBNAIL_MAX_SIZE,
    quality: int = THUMBNAIL_QUALITY,
) -> bytes: ...
def read_video(path: Path) -> VideoFile: ...
```

Behavior:

- `read_image` first preserves the current `is_file()` check
  (`NOT_FOUND, "Image is gone"`). With `index=None` it reads a standalone image;
  otherwise it reads the archive member at that position.
- Standalone validation preserves: supported extension, stat existence,
  `PREVIEW_MAX_IMAGE_BYTES` size limit, read failure, and content signature.
  Failures map to the existing messages: `"Not a supported image"`,
  `"Image is gone: {e}"`, `"Image is too large to preview"`,
  `"Cannot read image: {e}"`. As today, the served media type comes from the
  content signature and is not required to match the filename extension.
- Archive validation preserves: zip check (`"Not a zip archive"`), index range
  (`"Image not found in archive"`), directory/non-image member
  (`"Not a supported image"`), encryption
  (`"Encrypted archive members are not supported"`), member size, bad zip
  (`"Not a valid archive: {e}"`), unreadable member
  (`"Cannot read archive member: {e}"`), OSError (`"Cannot read archive: {e}"`),
  and content signature.
- `make_thumbnail` preserves EXIF transposition, LANCZOS thumbnail bounds,
  RGB/RGBA conversion, WebP output, quality defaults, and the
  `"Cannot decode image: {e}"` failure.
- `read_video` preserves missing-file `"Video is gone"`, extension and content
  sniffing (`"Not a supported video"`), and read/stat failure
  (`"Cannot read video: {e}"`).
- `web_media` reads `PREVIEW_MAX_IMAGE_BYTES` through the `choosier.preview`
  module at call time so the existing preview-limit test seam still works.
- HTTP byte-range parsing, `If-Range`, and `FileResponse` streaming stay in
  `web.py`; they are transport behavior, not media validation.

## 7. Route-to-Service Mapping

| Route | Handler translation | Shared implementation | Response model |
| --- | --- | --- | --- |
| `GET /api/defaults` | Echo configured defaults | None (transport only) | `DefaultsResponse` |
| `GET /api/browse` | Parse `path` | `browse_directory` | `BrowseResponse` |
| `GET /api/state` | Parse query, filters | `build_state` | `StateResponse` |
| `POST /api/pick` | Parse `PickRequest` | `pick(..., include_preview=True)` | `PickResponse` |
| `GET /api/preview` | Parse `path` | `preview_entry` | `PreviewModel` |
| `GET /api/image` | Parse `path`, `index`, `variant` | `read_image`, `make_thumbnail` | Binary `Response` |
| `GET /api/video` | Parse `path`, `Range`/`If-Range` | `read_video`; range stays adapter | `FileResponse` |
| `POST /api/open` | Parse `path` | `open_entry` | `OpenResponse` |
| `POST /api/history/archive` | Resolve log path | `HistoryService.archive` | `ArchiveResponse` |
| `DELETE /api/history` | Resolve log path | `HistoryService.clear` | `ClearResponse` |
| `DELETE /api/history/item` | Parse `item`, resolve log path | `HistoryService.remove` | `RemoveHistoryItemResponse` |
| `POST /api/history/remove` | Parse `items`, resolve log path | `HistoryService.remove_many` | `RemoveHistoryItemsResponse` |

Handler rules:

- Route functions contain input parsing, one service call (or one media
  call plus a variant mapping), and response/error mapping only.
- No route reads or writes the history file directly.
- No route reimplements selection, filtering, empty/exhausted classification,
  history counting, or media validation.
- `_log_path` may remain as a small adapter helper around
  `resolve_log_path`; it contains no business rule.
- The Pydantic request/response models in `web.py` keep their exact names,
  fields, defaults, and validation constraints.

## 8. Adapter Mapping

### Web

- `ServiceError` -> existing error envelope through the new handler.
- `ApiError` -> existing envelope for range failures.
- `PickOutcome` -> `PickResponse`; `pick` supplies the preview so no second
  preview read is needed. Use one `Preview -> PreviewModel` mapper for both
  `/api/preview` and the pick response.
- `StateSnapshot` -> `StateResponse`; `LogEntry` -> `HistoryEntryModel`.
- `BrowseListing` -> `BrowseResponse`; `BrowseEntry` -> `BrowserEntry`.
- `OpenOutcome` -> `OpenResponse(opened=outcome.name)`.
- `HistoryService.archive()` `Path | None` -> `backup.name` or `None`.
- Keep existing headers (`Cache-Control`, `X-Content-Type-Options`,
  `Content-Range`) and status codes unchanged.

### CLI

- Effective log path uses shared `resolve_log_path` semantics, including blank
  fallback.
- `--reset` uses `HistoryService.clear()`; success/failure text and exit code
  stay `"Removed {log_path}."` / `"No log at {log_path}."` / `1`.
- `--list` uses `build_state(..., max_lines=None).remaining`; empty/exhausted
  still uses the existing raw-directory check and exit codes 3/4.
- Pick uses `pick(..., commit=False)`; after printing
  `"The choice: <item>"`, a non-dry-run selection is committed through
  `HistoryService.append`. Success text, dry-run text, and write-failure text
  remain unchanged.
- Flags, parser errors (exit 2), prompts, output strings, and exit codes 0/1/3/4
  are unchanged.

### TUI

- Panel refresh uses `build_state(..., max_lines=None)`; remaining and history
  display lines feed the existing `render_panel` last-200 behavior. Import
  `PANEL_MAX_LINES` from `services.state` so the cap value has one source.
- Pick uses `pick(..., seed=seed, dry_run=dry_run)` and maps
  `picked`/`empty`/`exhausted`/`invalid_path` to the existing status strings.
  Keep the current target-is-directory precheck before parsing the seed so
  `"Invalid Path."` still wins over `"Invalid seed (must be an integer)."`.
- Archive and clear use `HistoryService`; success and failure status text is
  unchanged. Open uses `open_entry`; `NOT_FOUND` maps to `"Gone: <name>"`,
  `IO_ERROR` maps to the service message (`"Cannot open: ..."`).
- Preview display continues through `preview_entry`.
- Widgets, shortcuts, focus behavior, and messages are unchanged.

## 9. Frozen Public Contracts

The following must not change:

1. The 12 `/api` routes, methods, request models, success schemas, headers,
   and the error envelope defined by
   `specs/001-standardize-api-responses/contracts/api-contract.json`.
2. CLI flags, prompts, output text, exit codes, and `--ui`/`--web` dispatch.
3. TUI shortcuts, messages, panel contents, and last-200 rendering.
4. JSONL history format, legacy-line tolerance, rotation threshold, archive
   naming, and on-disk layout.
5. Compatibility exports in `choosier/__init__.py` and `main.py`.
6. `chooser`, `preview`, `launcher`, and `storage` public function signatures
   that existing callers and tests use.

Compatibility wrappers that remain:

- `storage.load_log` -> derived from `read_log_entries`.
- `storage.get_logged_items` -> derived from `read_log_entries`, preserving its
  missing-file tolerance and its propagation of non-missing `OSError`s.
- `storage.remove_log_item` -> delegates to `remove_log_items`.
- `chooser.list_available_items`, `get_unselected_item`, `list_candidates`,
  `resolve_default_log`, `resolve_log_path`, `parse_seed` keep their signatures.
- `preview.preview_entry`, `launcher.launch_path`, and all existing storage
  commands remain importable.

## 10. Unified History Read/Write Path

Reads:

```text
web state ─┐
TUI panels ─┼──> HistoryService.snapshot ──> storage.read_log_entries
CLI list ──┘                                      │
                                                  ├──> load_log (compat)
                                                  └──> get_logged_items (compat)
                                                       └──> chooser selection
```

Writes:

```text
web routes ─┐
CLI ────────┼──> HistoryService ──> storage commands ──> history file
TUI ────────┘
```

Rules:

- `storage.read_log_entries` is the only function that reads the history file
  into structured entries; `storage.parse_log_line` is the single line parser
  it uses.
- `HistoryService` is the only application-layer component that mutates
  history; adapters never call storage mutations directly.
- `chooser.py` may consume `get_logged_items`, which is a derived view over the
  same read primitive. It must not parse history itself.
- No database, cache, index, migration, or new persistence format is added.

## 11. Test Seams

Existing behavior assertions stay unchanged. Only imports and patch targets
move to the new seam:

| Test | Old target | New target |
| --- | --- | --- |
| `test_api_errors.py` unexpected read failure | `choosier.web.read_log_entries` | `choosier.storage.read_log_entries` |
| `test_api_errors.py` browse permission | `choosier.web.Path.iterdir` | `choosier.services.browse.Path.iterdir` |
| `test_api_errors.py` pick log failure | `choosier.web.log_selection` | `choosier.storage.log_selection` |
| `test_api_errors.py` image size limit | `choosier.web.PREVIEW_MAX_IMAGE_BYTES` | `choosier.preview.PREVIEW_MAX_IMAGE_BYTES` |
| `test_api_errors.py` open failure | `choosier.web.launch_path` | `choosier.launcher.launch_path` |
| `test_api_errors.py` archive/clear/remove failures | `choosier.web.archive_log`, `reset_log`, `remove_log_item`, `remove_log_items` | `choosier.storage.*` |
| `test_web.py` image size limit | `choosier.web.PREVIEW_MAX_IMAGE_BYTES` | `choosier.preview.PREVIEW_MAX_IMAGE_BYTES` |
| `test_web.py`, `test_api_compat.py` open success | `choosier.web.launch_path` | `choosier.launcher.launch_path` |

To keep those seams effective:

- `HistoryService` calls `storage.<function>` through the module, not through
  copied function references.
- `open_entry` calls `launcher.launch_path` through the module.
- `web_media` reads `preview.PREVIEW_MAX_IMAGE_BYTES` at call time.
- `browse_directory` uses `pathlib.Path` so class-level `iterdir` patching
  remains effective.

## 12. Direct Service Test Contract

Every service operation needs direct tests with no web server, TUI session,
network, or browser:

| Module | Required coverage |
| --- | --- |
| `services/browse.py` | ordering, parent at root, missing target, listing permission failure |
| `services/state.py` | invalid path, filter conflict, hidden/type filtering, managed-file exclusion, totals, 200 cap, no-cap TUI shape, empty/malformed history |
| `services/pick.py` | seeded repeatability, dry-run, commit suppression, empty vs exhausted, invalid path, filter conflict, logging failure, preview optionality, include-hidden/type filters |
| `services/opening.py` | success, missing entry, launcher failure |
| `services/history.py` | snapshot derivation, tolerant vs strict reads, append/remove/remove-many/archive/clear, missing history, duplicate lines, retained lines, failure messages |
| `services/errors.py` | failure kinds and message/details propagation |
| `tests/test_services_boundaries.py` | import boundary and no duplicate history parser |

## 13. Non-Goals

- No new API routes, request fields, response fields, CLI flags, TUI controls,
  or frontend changes.
- No database, ORM, repository abstraction over a database, query language, or
  migration layer.
- No new mandatory runtime dependency.
- No change to selection ordering, seeded results, history format, archive
  naming, media limits, or user-visible messages.
- No performance tuning beyond avoiding duplicate reads and preview work.
