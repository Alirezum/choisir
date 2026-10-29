# Changelog

## Unreleased

- Web UI: history rows have checkboxes for batch deletion. Hold Shift
  while checking or clicking a row to select a range, use Select
  all/Clear selection for the shown rows, then Delete selected with a
  confirmation. The log is rewritten once per batch.
- Web UI: history rows are clickable and load the item onto the board
  and into the preview. A new `↗` action beside each row's delete button
  opens the item with the OS default program.
- Web UI: redesigned the interface around a split-flap board, with a
  bundled Archivo/Archivo Narrow type system, dark graphite palette,
  responsive two-column workspace, contact-sheet previews with archive
  frame numbers, and matching full-screen viewer chrome. Pick, Open,
  archive, clear, and per-item history deletion keep their existing
  behavior.
- Web UI: Remaining/History/Browse/Options now use keyboard-navigable
  tabs, compact 24-hour history timestamps, and clearer empty states;
  `Ctrl+N` picks again from anywhere.
- Web UI: picked image files and up to 1,000 images inside `.zip`/`.cbz`
  archives are shown as lazy-loaded thumbnails. Single-image previews
  now use a high-resolution (~1600 px) WebP rendition at the image's
  native aspect ratio, while archive grids use ~480 px thumbnails.
  Clicking a thumbnail opens a fullscreen viewer with prev/next buttons,
  arrow keys, and `Esc`; the viewer loads the original image bytes.
  Archive members are served on demand by index with size/type
  validation; nothing is extracted to disk.
- Web UI: standalone MP4, WebM, MOV, and MKV files play in a native
  video preview with metadata and byte-range streaming. If the browser
  cannot decode the container or codec, the preview falls back to the
  existing Open action; nothing is transcoded, and videos inside
  archives remain binary.
- Web UI: the fullscreen image viewer supports zooming from fit to 8×
  with toolbar buttons, keyboard shortcuts, or the mouse wheel; drag to
  pan while zoomed, double-click to toggle fit/200%, and `0` to reset.
- Web UI: each History row has a delete button that removes every log
  entry for that item, returning it to Remaining without touching other
  history.
- Core: previews expose structured `PreviewImage` and `PreviewVideo`
  metadata and support `image`/`archive`/`video` kinds, with bounded
  image scanning (1,000 images, 20 MB each) and video container sniffing
  for MP4, WebM, MOV, and MKV.

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
