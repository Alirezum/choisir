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
a path or browse and press *Use this folder*). Picked image files
(PNG, JPEG, GIF, WebP, BMP) and up to 1,000 images inside `.zip`/`.cbz`
archives are shown as a lazy-loaded thumbnail grid, resized to ~320px
WebP thumbnails with Pillow. Click a thumbnail for a fullscreen viewer
with `‹`/`›` buttons, arrow-key navigation, and `Esc` to close. Zoom
from fit to 8× with the toolbar controls or mouse wheel, drag to pan,
double-click to toggle fit/200%, and press `0` to reset.
Full-size images are capped at 20 MB. Archive members are served on
demand by index and never extracted to disk. In the History tab, each
row has a delete button that removes every log entry for that item, so
it becomes eligible to be picked again without touching other history.
For frontend development, run `choosier --web` and `npm run dev` in
`frontend/` (Vite proxies `/api`); `npm run build` writes the bundle to
`choosier/web_static/`, which the server serves on the same origin.

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
