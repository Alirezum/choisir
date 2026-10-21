# Changelog

## Unreleased

- Web UI: picked image files and up to 1,000 images inside `.zip`/`.cbz`
  archives are shown as lazy-loaded thumbnails. Thumbnails are resized
  to WebP with Pillow; clicking one opens a fullscreen viewer with
  prev/next buttons, arrow keys, and `Esc`. Archive members are served
  on demand by index with size/type validation; nothing is extracted to
  disk.
- Core: previews expose structured `PreviewImage` metadata and support
  `image`/`archive` kinds with bounded scanning (1,000 images, 20 MB
  each).

## 0.3.0 — 2026-10-19

- Web UI (`choosier --web`, optional `web` extra): localhost-bound
  FastAPI JSON API with a Vue 3 single-page frontend covering the pick
  loop, filters, seed, dry-run, log-file control, browse/remaining/
  history views, previews, archive, guarded clear, and Open. Without a
  path argument it starts in the current directory, with the path box
  focused so any directory can be typed in the browser.
- Core: UI-agnostic helpers (`launcher`, `preview`, `load_log`,
  `parse_seed`, `resolve_log_path`) extracted from the TUI so CLI, TUI,
  and web share one implementation; `preview_entry` returns structured
  preview data.
- CI: frontend assets are built with Node before the test suite runs.

## 0.2.0 — 2026-10-14

- Storage: JSONL history colocated with the target directory, legacy
  `<timestamp> - <item>` lines still readable, timestamped rotation
  backups, `pathlib` throughout, archive helper.
- CLI: `argparse` interface (`--log-file`, `--reset`, `--dry-run`,
  `--seed`, `--include-hidden`, `--files-only`/`--dirs-only`, `--list`),
  exit codes 0/1/3/4, `choosier` console script.
- TUI (`choosier --ui`, optional `ui` extra): pick loop with large
  choice display, text/binary/directory preview, system open button,
  remaining/history views, archive and guarded clear, layout fitting
  80x24 terminals, `ctrl+n` Pick shortcut.
- Quality: 70-test suite (stdlib `unittest`, pytest-compatible), ruff
  lint/format clean, mypy strict clean, CI workflow.
