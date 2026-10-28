# choosier

A random file-or-directory chooser with persistent history. Each run picks a
random unselected entry from a directory and records it, so repeats are
avoided until every choice has been selected.

## Usage

```sh
python -m choosier PATH
python main.py PATH
choosier PATH            # after installing the project scripts
```

With no `PATH`, the tool prompts with `Enter Path:`.

| Flag | Effect |
| --- | --- |
| `--log-file PATH` | History log (default: `<target>/.choosier.jsonl`) |
| `--reset` | Delete the history log and exit |
| `--dry-run` | Pick without recording the selection |
| `--seed N` | Deterministic picks |
| `--include-hidden` | Consider dotfiles |
| `--files-only` / `--dirs-only` | Restrict to files or directories |
| `--list` | Print remaining picks instead of choosing |

Exit codes: `0` success, `1` runtime error (invalid path, unwritable log),
`3` directory empty, `4` all choices already selected (`2` is argparse usage
errors).

## Terminal UI

Full-parity interactive UI (pick loop, filters, seed, dry-run, log-file
control, remaining/history views, guarded reset):

```sh
pip install "choosier[ui]"
choosier --ui [PATH]
```

`python -m choosier --ui` works too. Edge states that are CLI exit codes
appear as status-bar messages in the UI. Each pick also shows a short
preview (text head, directory entry count, or binary/empty notice). The
`Open` button launches the current choice with the OS default program
(`xdg-open` / `open` / file association) — only use it on directories
you trust, since opening a file runs its associated application.
`Archive history` files the current log away as a timestamped backup;
`Clear history` deletes it (with confirmation).

## Web UI

Local-only FastAPI server with a Vue single-page frontend covering the
same features as the TUI (pick loop, filters, seed, dry-run, log-file
control, browse/remaining/history views, previews, archive, guarded
clear, and Open):

```sh
pip install "choosier[web]"
choosier --web [PATH] [--port 8765]
```

The server binds to `127.0.0.1` only. Without `PATH` it starts in the
current directory, and the path box stays editable in the browser (type
a path or browse and press *Use this folder*). The current choice lands
on a dark split-flap board, with *Pick* and *Open* controls attached to
it. Remaining, History, Browse, and Options share one workspace below the
preview; the tabs support arrow-key navigation, and `Ctrl+N` picks again.
The layout collapses from two columns to one on narrow screens.

Picked image files (PNG, JPEG, GIF, WebP, BMP) and up to 1,000 images
inside `.zip`/`.cbz` archives are shown as a lazy-loaded contact sheet.
Single-image previews use a high-resolution (~1600px) WebP rendition at
the image's native aspect ratio; archive grids use ~480px thumbnails.
Click a thumbnail for a fullscreen viewer with previous/next buttons,
arrow-key navigation, and `Esc` to close. The viewer loads original image
bytes rather than the WebP rendition. Zoom from fit to 8× with the toolbar
controls or mouse wheel, drag to pan, double-click to toggle fit/200%, and
press `0` to reset. Full-size images are capped at 20 MB. Archive members
are served on demand by index and never extracted to disk.

Standalone MP4, WebM, MOV, and MKV files play in a native video preview
with metadata and byte-range streaming. Actual playback depends on the
browser's codecs; WebM and MP4 are the most reliable, while MOV and MKV
are best-effort. If the browser cannot play a file, the preview explains
this and the board's *Open* button launches it in the system player. No
transcoding is performed, and videos inside archives are not previewed.

In the History tab, clicking a row loads that item onto the board and into
the preview; the `↗` button next to it opens the item with the OS default
program. Each row's delete button removes every log entry for that item,
so it becomes eligible to be picked again without touching other
history. Clicking a row highlights it for batch deletion, and clicking it
again deselects it; hold `Shift` while clicking to select the whole
range, use *Select all* / *Clear selection* for the visible rows, then
*Delete selected* and confirm. For frontend development, run `choosier --web` and `npm run dev`
in `frontend/` (Vite proxies `/api`); `npm run build` writes the bundle to
`choosier/web_static/`, which the server serves on the same origin.

## API contract

Every failed `/api/*` request returns the same JSON envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not a directory",
    "details": null
  },
  "detail": "Not a directory"
}
```

`detail` is kept as a string and always equals `error.message`, so existing
frontend error handling keeps working. Validation failures add
`error.details.issues` (each with string `location`, `message`, and `type`);
raw request input is never echoed.

| Code | Status | Meaning |
| --- | --- | --- |
| `invalid_request` | 400 | Invalid parameter combination, archive operation, or byte range |
| `forbidden` | 403 | Target exists but cannot be accessed |
| `not_found` | 404 | Unknown route or missing path/entry/image/video/archive member |
| `method_not_allowed` | 405 | Route does not support the method |
| `payload_too_large` | 413 | Image exceeds the 20 MB preview limit |
| `unsupported_media_type` | 415 | Unsupported or undecodable image/video |
| `range_not_satisfiable` | 416 | Range starts beyond the end of the video |
| `validation_error` | 422 | Query/body validation failed |
| `internal_error` | 500 | I/O, log, launch, or unexpected server failure |

Domain outcomes are not errors: an invalid target path in `/api/state`,
`invalid_path`/`empty`/`exhausted` picks, and no-op archive/clear/remove calls
still return `200` with their normal payloads. The image endpoint keeps binary
bytes and MIME types; the video endpoint keeps `200`/`206` streaming and
answers malformed or unsatisfiable `Range` headers with the JSON envelope
(400/416) instead of plain text.

The machine-readable inventory (12 `/api` routes and all error codes) lives in
[`specs/001-standardize-api-responses/contracts/api-contract.json`](specs/001-standardize-api-responses/contracts/api-contract.json),
with a human-readable audit in
[`api-contract.md`](specs/001-standardize-api-responses/contracts/api-contract.md).
When changing an API response, update both files and run
`uv run pytest tests/test_api_contract.py`; the tests reject route, field,
type, nullability, enum, binary/content-type, and error-status drift.

## History log

Selections are stored as JSON Lines (`{"ts": ..., "item": ...}`) in
`<target>/.choosier.jsonl`, colocated with the target so history is shared
across working directories. Legacy `<timestamp> - <item>` lines are still
read. Logs over 1MB rotate to timestamped `.old` backups.

## Development

```sh
uv sync --group dev --extra ui --extra web
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy choosier main.py tests

# Static-serving tests need a frontend build.
cd frontend && npm ci && npm run build && cd ..
```

`python -m unittest` also runs the suite (tests use stdlib `unittest`).
