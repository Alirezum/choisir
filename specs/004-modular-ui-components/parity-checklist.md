# Parity Checklist: Modular UI Components

**Feature**: `004-modular-ui-components`
**Branch**: `004-modular-ui-components`
**Baseline commit**: `main@d25abef`
**Implementation range**: `d25abef..HEAD` (final range recorded at sign-off)
**Baseline date**: 2026-11-03
**Reviewer**: local implementation session

This checklist is the retained evidence for the behavior-preserving refactor.
Screenshots are captured locally and are not committed. Fill "After" during US2
and sign off only when every row is identical or an exception is recorded.

## Viewport matrix

| Range | Width | Browser size used | Baseline | After | Result |
|---|---|---|---|---|---|
| Desktop | >900px | 1280×900 | Captured locally | Pending | Pending |
| Tablet | 561–900px | 800×900 | Captured locally | Pending | Pending |
| Phone | ≤560px | 390×844 | Captured locally | Pending | Pending |

## Flow matrix

Record `Baseline` and `After` as the observed outcome, including exact text where
relevant. Use `PASS` only when they match; otherwise record the deviation and its
explicit decision.

| # | Flow / check | Baseline (main@d25abef) | After | Result |
|---|---|---|---|---|
| 1 | Initial load with defaults | | | Pending |
| 1a | Initial status text | `Choose a folder, then press Pick.` | | Pending |
| 2 | Browse: initial load for current path | | | Pending |
| 2a | Browse: parent navigation | | | Pending |
| 2b | Browse: child navigation | | | Pending |
| 2c | Browse: empty folder copy | `This folder is empty.` | | Pending |
| 2d | Browse: unreadable/missing path error | Shared error message, listing cleared | | Pending |
| 3 | Options: log file change | Applies to next pick; refreshes state | | Pending |
| 3a | Options: seed change | Applies to next pick | | Pending |
| 3b | Options: dry run change | Applies to next pick | | Pending |
| 3c | Options: hidden change | Refreshes filters after 250ms | | Pending |
| 3d | Options: mode changes (all/files/dirs) | Mutually exclusive filters | | Pending |
| 4 | Pick: success | `Picked <item>.` | | Pending |
| 4a | Pick: dry run | `Picked <item>. Dry run, so it wasn't logged.` | | Pending |
| 4b | Pick: blank path | `Enter a folder path.` and focus returns to input | | Pending |
| 4c | Pick: non-integer seed | `Seed must be a whole number.` | | Pending |
| 4d | Pick: invalid path | `That folder doesn't exist.` | | Pending |
| 4e | Pick: empty folder | `That folder has nothing to pick.` | | Pending |
| 4f | Pick: exhausted | `All items have been picked. Clear or archive history to start over.` | | Pending |
| 4g | Pick: backend failure | Shared error message; state refreshes | | Pending |
| 5 | Preview: text | Meta line absent, text body rendered | | Pending |
| 5a | Preview: single image | `1 image`, single-frame grid variant | | Pending |
| 5b | Preview: archive frames | `N images` and numbered frames | | Pending |
| 5c | Preview: truncated image total | `N of M images` | | Pending |
| 5d | Preview: video | Media label/size meta and video controls | | Pending |
| 5e | Preview: video playback failure | Fallback copy with **Open** guidance | | Pending |
| 6 | Open: current item | `Opened <path>.` | | Pending |
| 6a | Open: no current item | `Pick something first.` | | Pending |
| 7 | History: archive with log | `Archived history to <backup>.` | | Pending |
| 7a | History: archive without log | `No history file at <log>.` | | Pending |
| 7b | History: clear confirm | Dialog message uses log file or path; `Cleared <log>.` | | Pending |
| 7c | History: clear cancel | Dialog closes; no request | | Pending |
| 7d | History: single removal, 0/1/many | Exact 0/1/many messages | | Pending |
| 7e | History: row click preview | Row selected/checked; `Previewing <item> from history.` | | Pending |
| 7f | History: shift-click range | Contiguous range checked; anchor preserved | | Pending |
| 7g | History: select all / clear selection | All unique row items toggle | | Pending |
| 7h | History: batch delete confirm | Count message and `Delete N item(s)` label | | Pending |
| 7i | History: batch delete 0/1/many | Exact 0/1/many messages | | Pending |
| 7j | History: batch cancel | Dialog closes; selection remains | | Pending |
| 7k | History: busy guards | Duplicate remove/archive/clear actions disabled or ignored | | Pending |
| 7l | History: path/log change clears selection and pending delete | Checked items and dialog clear | | Pending |
| 8 | Viewer: open/close | Opens at clicked index; Close/Escape returns | | Pending |
| 8a | Viewer: next/previous wrap | Counter wraps at both ends | | Pending |
| 8b | Viewer: zoom levels/limits | 1.25 step levels, clamp 1–8, `Fit` label | | Pending |
| 8c | Viewer: double-click | Toggles 2x/Fit | | Pending |
| 8d | Viewer: drag clamp | Pan clamps to scaled image bounds | | Pending |
| 8e | Viewer: original link | `/api/image` full-size URL in new tab | | Pending |
| 8f | Viewer: scroll lock restore | Body overflow restored after close | | Pending |
| 8g | Viewer: single image | No next/previous controls | | Pending |
| 9 | Keyboard: Ctrl+N | Picks from page; blocked by clear dialog/viewer overlay | | Pending |
| 9a | Keyboard: tabs | ArrowLeft/Right wrap, Home/End jump, focus follows | | Pending |
| 9b | Keyboard: focus visibility | All controls have visible focus | | Pending |
| 9c | Keyboard: dialog | Cancel focused, Tab trapped, Escape cancels, overlay click cancels | | Pending |
| 9d | Accessibility: status live region | `role="status"`, `aria-live="polite"` announces changes | | Pending |
| 9e | Accessibility: tab semantics | `role=tablist/tab/tabpanel`, `aria-selected`, `aria-controls`, roving tabindex | | Pending |
| 10 | Empty states and headers | Board, Remaining, History, Browser, Preview copy unchanged | | Pending |
| 10a | History header/counts | `<total> picked` or `showing the last N` | | Pending |
| 10b | Remaining header/counts | `<total> remaining` or `showing the first N` | | Pending |
| 10c | Choice board truncation | 48 characters with ellipsis; full name in title | | Pending |
| 10d | Board stats and empty titles | `Nothing picked yet`, `All picked`, `Nothing to pick` | | Pending |

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
