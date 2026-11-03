# Parity Checklist: Modular UI Components

**Feature**: `004-modular-ui-components`
**Branch**: `004-modular-ui-components`
**Baseline commit**: `main@d25abef`
**Implementation range**: `d25abef..HEAD` (final range recorded at sign-off)
**Baseline date**: 2026-11-03
**Reviewer**: local implementation session (Chromium headless replay)

This checklist is the retained evidence for the behavior-preserving refactor.
Screenshots are captured locally and are not committed. Fill "After" during US2
and sign off only when every row is identical or an exception is recorded.

## Viewport matrix

| Range | Width | Browser size used | Baseline | After | Result |
|---|---|---|---|---|---|
| Desktop | >900px | 1280×900 | Captured; no horizontal overflow | Pending | Pending |
| Tablet | 561–900px | 800×900 | Captured; no horizontal overflow | Pending | Pending |
| Phone | ≤560px | 390×844 | Captured; no horizontal overflow | Pending | Pending |

## Flow matrix

Record `Baseline` and `After` as the observed outcome, including exact text where
relevant. Use `PASS` only when they match; otherwise record the deviation and its
explicit decision. "Source-verified" means the baseline was confirmed by reading
the untouched implementation when the flow is not safely triggerable headlessly.

| # | Flow / check | Baseline (main@d25abef) | After | Result |
|---|---|---|---|---|
| 1 | Initial load with defaults | Defaults path loaded; Remaining 10, History 0; board "Nothing picked yet"; preview empty copy shown | | Pending |
| 1a | Initial status text | `Choose a folder, then press Pick.` | | Pending |
| 2 | Browse: initial load for current path | Root header shows current path; folders first, then files; Parent folder row present | | Pending |
| 2a | Browse: parent navigation | Parent row loads `/tmp/opencode`; header updates | | Pending |
| 2b | Browse: child navigation | `folder-a` loads child path; Parent row returns | | Pending |
| 2c | Browse: empty folder copy | `This folder is empty.` | | Pending |
| 2d | Browse: unreadable/missing path error | Source-verified: shared error message, listing cleared | | Pending |
| 3 | Options: log file change | Applies to next pick; state refresh scheduled | | Pending |
| 3a | Options: seed change | Applies to next pick | | Pending |
| 3b | Options: dry run change | Applies to next pick | | Pending |
| 3c | Options: hidden change | Refreshes filters after 250ms; hidden entries appear | | Pending |
| 3d | Options: mode changes (all/files/dirs) | Mutually exclusive files/dirs filters | | Pending |
| 4 | Pick: success | `Picked only.txt.`; board flaps animate; preview text shown | | Pending |
| 4a | Pick: dry run | Source-verified: `Picked <item>. Dry run, so it wasn't logged.` | | Pending |
| 4b | Pick: blank path | `Enter a folder path.`; focus returns to `.path-input` | | Pending |
| 4c | Pick: non-integer seed | `Seed must be a whole number.` | | Pending |
| 4d | Pick: invalid path | `That folder doesn't exist.` | | Pending |
| 4e | Pick: empty folder | `That folder has nothing to pick.` | | Pending |
| 4f | Pick: exhausted | `All items have been picked. Clear or archive history to start over.` | | Pending |
| 4g | Pick: backend failure | Source-verified: shared `apiErrorMessage` text; refresh still runs | | Pending |
| 5 | Preview: text | Text body rendered; meta line absent | | Pending |
| 5a | Preview: single image | `1 image`; meta `PNG, 779 B`; grid has `is-single` and `variant=preview` URL | | Pending |
| 5b | Preview: archive frames | `3 images`; meta `Archive`; frames numbered `01`–`03` | | Pending |
| 5c | Preview: truncated image total | Source-verified: `N of M images` when `image_total > images.length`; not exercised because the cap is 1000 images | | Pending |
| 5d | Preview: video | `MP4, 7.2 KB`; video element with `/api/video` source; no fallback | | Pending |
| 5e | Preview: video playback failure | Source-verified: fallback copy with **Open** guidance | | Pending |
| 6 | Open: current item | `Opened only.txt.` | | Pending |
| 6a | Open: no current item | Source-verified: `Pick something first.` (Open control is hidden until an item exists) | | Pending |
| 7 | History: archive with log | `Archived history to .choosier-*.jsonl.old.`; history clears after refresh | | Pending |
| 7a | History: archive without log | `No history file at /tmp/opencode/choosier-empty/.choosier.jsonl.` | | Pending |
| 7b | History: clear confirm | Dialog title `Clear history?`, detail is the log path; confirm shows `Cleared <log>.`; history becomes 0 | | Pending |
| 7c | History: clear cancel | Dialog closes; no request; history unchanged | | Pending |
| 7d | History: single removal, 0/1/many | `No history entry for "ghost.txt".`; `Removed "solo.txt" from history.`; `Removed 2 entries for "paired.txt".` | | Pending |
| 7e | History: row click preview | Row checked and selected; `Previewing alpha.txt from history.` | | Pending |
| 7f | History: shift-click range | Anchor at first row; shift-click third row produced 3 checked rows | | Pending |
| 7g | History: select all / clear selection | 5 rows checked; link becomes `Clear selection`; delete label `Delete selected (5)` | | Pending |
| 7h | History: batch delete confirm | Title `Delete history for 5 items?`; detail explains re-pickability; labels `Cancel` / `Delete 5 items`; cancel focused | | Pending |
| 7i | History: batch delete 0/1/many | 1 item: `Removed 1 entry from history.`; 4 items: `Removed 4 entries from history.`; 0 is source-verified `No matching history entries to remove.` | | Pending |
| 7j | History: batch cancel | Dialog closes; all 5 checks remain | | Pending |
| 7k | History: busy guards | Source-verified: remove/archive/clear disabled or ignored while busy | | Pending |
| 7l | History: path/log change clears selection and pending delete | Source-verified: both watchers clear checked items and pending delete | | Pending |
| 8 | Viewer: open/close | Opens at clicked index; Close/Escape returns | | Pending |
| 8a | Viewer: next/previous wrap | 3 images: next at 3/3 → 1/3; previous at 1/3 → 3/3 | | Pending |
| 8b | Viewer: zoom levels/limits | Buttons/wheel: `Fit` → `125%` → `200%`; reset returns `Fit`; clamp is 1–8 | | Pending |
| 8c | Viewer: double-click | Toggles `Fit` ↔ `200%` | | Pending |
| 8d | Viewer: drag clamp | 2x drag clamped to image bounds; transform `translate(80px, 60px) scale(2)` at the observed edge | | Pending |
| 8e | Viewer: original link | `/api/image?path=…&index=0` in a new tab | | Pending |
| 8f | Viewer: scroll lock restore | Body overflow `hidden` while open; restored to `''` after close | | Pending |
| 8g | Viewer: single image | Counter `1 / 1`; no next/previous controls | | Pending |
| 9 | Keyboard: Ctrl+N | Picks from the page; status changed to `Picked ctrln.txt.`; blocked while the clear dialog is open | | Pending |
| 9a | Keyboard: tabs | ArrowRight → History, Home → Remaining, End → Options; focus follows | | Pending |
| 9b | Keyboard: focus visibility | Source/CSS-reviewed: interactive controls keep visible focus styling | | Pending |
| 9c | Keyboard: dialog | Cancel focused initially; Tab trapped; Escape closes; overlay click cancels | | Pending |
| 9d | Accessibility: status live region | `role="status"`, `aria-live="polite"` | | Pending |
| 9e | Accessibility: tab semantics | `role=tablist/tab/tabpanel`, `aria-selected`, `aria-controls`, roving tabindex | | Pending |
| 10 | Empty states and headers | Board, Remaining, History, Browser, Preview copy unchanged | | Pending |
| 10a | History header/counts | `5 picked`; `showing the last N` when truncated (source-verified) | | Pending |
| 10b | Remaining header/counts | `10 remaining`; `showing the first N` when truncated (source-verified) | | Pending |
| 10c | Choice board truncation | 48 flaps, last flap `…`; full 84-character name in `title`; screen-reader heading keeps full name | | Pending |
| 10d | Board stats and empty titles | `Nothing to pick` + `This folder is empty.`; `All picked` + `Clear or archive history to start over.` | | Pending |

## Message classes

Expected exact text at baseline. `*` marks an interpolated value.

| Class | Expected text |
|---|---|
| Initial status | `Choose a folder, then press Pick.` |
| Missing path | `Enter a folder path.` |
| Invalid seed | `Seed must be a whole number.` |
| Invalid path | `That folder doesn't exist.` |
| Empty folder | `That folder has nothing to pick.` |
| Exhausted | `All items have been picked. Clear or archive history to start over.` |
| Picked | `Picked *item*.` |
| Picked dry run | `Picked *item*. Dry run, so it wasn't logged.` |
| Opened | `Opened *opened*.` |
| Nothing to open | `Pick something first.` |
| Previewing history | `Previewing *item* from history.` |
| Archive success | `Archived history to *backup*.` |
| Archive no file | `No history file at *log*.` |
| Clear success | `Cleared *log*.` |
| Clear no file | `No history file at *log*.` |
| Remove item 0 | `No history entry for "*item*".` |
| Remove item 1 | `Removed "*item*" from history.` |
| Remove item many | `Removed *n* entries for "*item*".` |
| Batch remove 0 | `No matching history entries to remove.` |
| Batch remove 1 | `Removed 1 entry from history.` |
| Batch remove many | `Removed *n* entries from history.` |
| Shared failure | `apiErrorMessage(error)` output in all failure paths |
| Clear confirmation | `Clear history?` plus log file or path |
| Batch confirmation | `Delete history for *n* item(s)?` plus removal explanation |

## Baseline evidence

Local directory: `/tmp/opencode/choosier-parity/baseline/` (not committed).

| Evidence | Contents |
|---|---|
| `baseline-results.json` | Initial load, pick, options, validation, image/archive/video preview, browser, history, dialogs, Ctrl+N, tabs, ARIA, viewport overflow |
| `baseline-extra-results.json` | Board empty states, truncation, clear success, archive without log, single/batch removal counts, viewer zoom/drag/close |
| `initial-desktop.png`, `initial-tablet.png`, `initial-phone.png` | Initial load at 1280×900, 800×900, 390×844 |
| `pick-text-desktop.png` | Picked text item, preview, remaining/history counts |
| `preview-image-desktop.png`, `preview-archive-desktop.png`, `preview-video-desktop.png` | Preview types |
| `viewer-single-desktop.png`, `viewer-archive-desktop.png`, `viewer-zoom-desktop.png` | Viewer states |
| `browser-root-desktop.png`, `browser-empty-desktop.png` | Browser states |
| `history-desktop.png`, `history-after-remove-desktop.png`, `history-tablet.png`, `history-phone.png` | History and responsive states |
| `options-desktop.png`, `options-tablet.png`, `options-phone.png` | Options responsive states |
| `batch-dialog-desktop.png`, `clear-dialog-desktop.png`, `clear-confirmed-desktop.png`, `remove-zero-desktop.png` | Confirmation and removal states |
| `board-empty-desktop.png`, `board-truncated-desktop.png` | Board empty/truncation states |

## Boundary violation trials

Perform each trial on a clean tree, confirm the expected failure, then restore.

| # | Trial | Expected rule | Result |
|---|---|---|---|
| 1 | View imports/calls the shared client | R-01 view API isolation | Pending |
| 2 | `App.vue` gains a watcher or API call | R-04 composition-root thinness | Pending |
| 3 | State unit imports a view | R-03 state isolation | Pending |
| 4 | Two-file relative-import cycle | R-05 acyclic graph | Pending |
| 5 | Raw `.panel`/`.panel-header` markup in a view | R-06 shared scaffold | Pending |

Semantic duplication review (static checks cannot judge this):

| Finding | Location | Resolution |
|---|---|---|
| Pending | | |

## Automated gates

| Gate | Result |
|---|---|
| `npm run check:api` | Pending |
| `npm run test:api` | Pending |
| `npm run check:ui` | Pending |
| `npm run test:ui` | Pending |
| `npm run build` | Pending |
| `uv run ruff check .` | Pending |
| `uv run ruff format --check .` | Pending |
| `uv run pytest` | Pending |
| `uv run mypy choosier main.py tests` | Pending |
| `uv build` | Pending |

## Sign-off

- [ ] Every flow row is `PASS` or has a recorded decision.
- [ ] All three viewport ranges match the baseline.
- [ ] All five violation trials were detected.
- [ ] All automated gates pass.
- [ ] No screenshots or browser tooling are committed.
- [ ] Final implementation commit range recorded above.
