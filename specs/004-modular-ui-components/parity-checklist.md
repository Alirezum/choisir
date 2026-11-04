# Parity Checklist: Modular UI Components

**Feature**: `004-modular-ui-components`
**Branch**: `004-modular-ui-components`
**Baseline commit**: `main@d25abef`
**Implementation range**: `d25abef..HEAD` (final range recorded at sign-off)
**Baseline date**: 2026-11-03; re-captured 2026-11-04
**Reviewer**: local implementation session (Chromium headless CDP replay)

This checklist is the retained evidence for the behavior-preserving refactor.
Screenshots are captured locally and are not committed. Fill "After" during US2
and sign off only when every row is identical or an exception is recorded.

## Viewport matrix

| Range | Width | Browser size used | Baseline | After | Result |
|---|---|---|---|---|---|
| Desktop | >900px | 1280×900 | Captured at 1280×900; `scrollWidth - innerWidth = 0` | Captured at 1280×900; `scrollWidth - innerWidth = 0` | PASS |
| Tablet | 561–900px | 800×900 | Captured at 800×900; no horizontal overflow | Captured at 800×900; no horizontal overflow | PASS |
| Phone | ≤560px | 390×844 | Captured at 390×844; no horizontal overflow | Captured at 390×844; no horizontal overflow | PASS |

## Flow matrix

Record `Baseline` and `After` as the observed outcome, including exact text where
relevant. Use `PASS` only when they match; otherwise record the deviation and its
explicit decision. "Source-verified" means the baseline was confirmed by reading
the untouched implementation when the flow is not safely triggerable headlessly.

| # | Flow / check | Baseline (main@d25abef) | After | Result |
|---|---|---|---|---|
| 1 | Initial load with defaults | `/tmp/opencode/choosier` loaded; Remaining 10, History 0; board `Nothing picked yet` / `Press Pick to choose the first one.`; preview `Pick an item to preview it here.` | PASS — same path, counts, board copy, and preview copy | PASS |
| 1a | Initial status text | `Choose a folder, then press Pick.` | PASS — exact text | PASS |
| 2 | Browse: initial load for current path | Root header shows `/tmp/opencode/choosier`; parent row first, `folder-a` before files, then `alpha.txt` … `photo.png`; Use enabled | PASS — same header, parent-first order, sorted rows, and enabled Use button | PASS |
| 2a | Browse: parent navigation | Parent row loads `/tmp/opencode`; header updates | PASS — parent navigation reached `/tmp/opencode`; header updated | PASS |
| 2b | Browse: child navigation | `folder-a` loads `/tmp/opencode/choosier/folder-a`; rows are Parent, `empty`, `inner.txt` | PASS — child path and rows match | PASS |
| 2c | Browse: empty folder copy | `This folder is empty.` | PASS — exact copy at `folder-a/empty` | PASS |
| 2d | Browse: unreadable/missing path error | Live: `Not a directory` in the shared `.panel-empty error` element; listing cleared | PASS — live-verified exact shared error path | PASS |
| 3 | Options: log file change | Inputs/labels/placeholders match; a changed log path persists and is used by the next state refresh/pick | PASS — live input change plus unit-tested 250 ms state refresh | PASS |
| 3a | Options: seed change | Seed input persists; the picker sends the parsed nullable seed | PASS — live seed input plus unit-tested null/parse behavior | PASS |
| 3b | Options: dry run change | Dry-run checkbox toggles; the next pick is not logged | PASS — live dry-run pick in row 4a; history stayed 0 | PASS |
| 3c | Options: hidden change | Checkbox toggles; hidden entries refresh after 250 ms | PASS — live checkbox plus unit-tested debounce | PASS |
| 3d | Options: mode changes (all/files/dirs) | Radios are mutually exclusive; files/dirs filters map to the API flags | PASS — live mode change to `files`; unit-tested mutual exclusion | PASS |
| 4 | Pick: success | `Picked only.txt.`; board shows 8 flaps; preview body `Only text.`; Remaining 0, History 1 | PASS — exact text, flap count, preview, and counts | PASS |
| 4a | Pick: dry run | `Picked dry.txt. Dry run, so it wasn't logged.`; History remains 0 | PASS — exact text and counts | PASS |
| 4b | Pick: blank path | `Enter a folder path.`; focus returns to `.path-input` | PASS — live exact text; focus return covered by `use-picker` test | PASS |
| 4c | Pick: non-integer seed | `Seed must be a whole number.` | PASS — exact text | PASS |
| 4d | Pick: invalid path | `That folder doesn't exist.` | PASS — exact text | PASS |
| 4e | Pick: empty folder | `That folder has nothing to pick.` | PASS — exact text | PASS |
| 4f | Pick: exhausted | `All items have been picked. Clear or archive history to start over.` | PASS — exact text | PASS |
| 4g | Pick: backend failure | Source-verified: shared `apiErrorMessage` text; refresh still runs | PASS — unit-tested shared error path; no live failure induced | PASS |
| 5 | Preview: text | Text body rendered; meta line absent | PASS — text body rendered; no meta line | PASS |
| 5a | Preview: single image | `1 image`; meta `PNG, 1.7 KB`; grid has `is-single` and `variant=preview` URL | PASS — exact label/meta/class; preview-variant URL | PASS |
| 5b | Preview: archive frames | `3 images`; meta `Archive`; frames numbered `01`–`03` with thumbnail URLs | PASS — exact labels, numbers, and `variant=thumb` URLs | PASS |
| 5c | Preview: truncated image total | Source-verified: `N of M images` when `image_total > images.length`; not exercised because the cap is 1000 images | PASS — source-verified; preview internals unchanged in US1 | PASS |
| 5d | Preview: video | `MP4, 2.2 KB`; video element with `/api/video` source and `aria-label` | PASS — exact meta, URL, and aria-label | PASS |
| 5e | Preview: video playback failure | Fallback copy with **Open** guidance | PASS — live-dispatched media error produced the exact fallback copy | PASS |
| 6 | Open: current item | `Opened only.txt.` | PASS — exact text | PASS |
| 6a | Open: no current item | Source-verified/unit-tested: `Pick something first.` (Open control is hidden until an item exists) | PASS — exact copy covered by `use-picker` test | PASS |
| 7 | History: archive with log | `Archived history to .choosier-20261104T084346Z.jsonl.old.`; history clears after refresh | PASS — same message pattern; history 0 | PASS |
| 7a | History: archive without log | `No history file at /tmp/opencode/choosier-empty/.choosier.jsonl.` | PASS — exact text | PASS |
| 7b | History: clear confirm | Dialog title `Clear history?`, detail is the log path; confirm shows `Cleared <log>.`; history becomes 0 | PASS — title/detail/focus match; `Cleared /tmp/opencode/choosier-history-cancel/.choosier.jsonl.`; history 0 | PASS |
| 7c | History: clear cancel | Dialog closes; no request; history unchanged | PASS — Escape and overlay-click cancels; 6 history rows remained | PASS |
| 7d | History: single removal, 0/1/many | `No history entry for "ghost.txt".`; `Removed "solo.txt" from history.`; `Removed 2 entries for "paired.txt".` | PASS — 1 and 2 messages live; 0 is unit-tested exact copy | PASS |
| 7e | History: row click preview | Row checked and selected; `Previewing alpha.txt from history.` | PASS — row checked/selected; exact status | PASS |
| 7f | History: shift-click range | Anchor at first row; shift-click third row produced 3 checked rows | PASS — 3 checked rows | PASS |
| 7g | History: select all / clear selection | 5 unique rows checked from 6 log entries; link becomes `Clear selection`; delete label `Delete selected (5)` | PASS — 5 checked; `Clear selection`; `Delete selected (5)` | PASS |
| 7h | History: batch delete confirm | Title `Delete history for 5 items?`; detail explains re-pickability; labels `Cancel` / `Delete 5 items`; cancel focused | PASS — exact title/detail/labels; Cancel focused | PASS |
| 7i | History: batch delete 0/1/many | 1 item: `Removed 1 entry from history.`; 5 unique items (6 entries): `Removed 6 entries from history.`; 0 is source-verified `No matching history entries to remove.` | PASS — 1 and 6 exact; 0 unit-tested exact copy | PASS |
| 7j | History: batch cancel | Dialog closes; all 5 checks remain | PASS — dialog closed; 5 checks remained | PASS |
| 7k | History: busy guards | Source-verified: remove/archive/clear disabled or ignored while busy | PASS — unit-tested busy guards | PASS |
| 7l | History: path/log change clears selection and pending delete | Live: changing the path closed the open batch dialog and cleared the old path's checks | PASS — dialog closed; new path showed 0 history | PASS |
| 8 | Viewer: open/close | Opens at clicked index; Close/Escape returns | PASS — opened at index 0; Escape returned | PASS |
| 8a | Viewer: next/previous wrap | 3 images: next at 1/3 → 2/3; previous at 2/3 → 1/3; previous at 1/3 → 3/3; next at 3/3 → 1/3 | PASS — all wraps match | PASS |
| 8b | Viewer: zoom levels/limits | Buttons/wheel: `Fit` → `125%` → `150%`; reset returns `Fit`; double-click gives `200%`; clamp is 1–8 | PASS — 125%/150%, reset `Fit`, double-click `200%`; clamp unit-tested | PASS |
| 8c | Viewer: double-click | Toggles `Fit` ↔ `200%` | PASS — toggles `Fit` ↔ `200%` | PASS |
| 8d | Viewer: drag clamp | 2x drag clamped to image bounds; transform `translate(240px, 150px) scale(2)` at the observed edge | PASS — transform and 480×300 clamp match | PASS |
| 8e | Viewer: original link | `/api/image?...&index=0` in a new tab, without a `variant` parameter | PASS — exact href | PASS |
| 8f | Viewer: scroll lock restore | Body overflow `hidden` while open; restored to `''` after close | PASS — `hidden` then `''` | PASS |
| 8g | Viewer: single image | Counter `1 / 1`; no next/previous controls | PASS — `1 / 1`; no nav controls | PASS |
| 9 | Keyboard: Ctrl+N | Picks from the page; status changed to `Picked ctrln.txt.`; blocked while the clear dialog or viewer is open | PASS — exact text; both blocked states live-verified | PASS |
| 9a | Keyboard: tabs | ArrowRight → History, Home → Remaining, End → Options; focus follows | PASS — all three moves; focus follows (unit-tested) | PASS |
| 9b | Keyboard: focus visibility | Source/CSS-reviewed: interactive controls keep visible focus styling | PASS — no style changes; CSS-reviewed | PASS |
| 9c | Keyboard: dialog | Cancel focused initially; Tab trapped; Escape closes; overlay click cancels | PASS — initial focus, both Tab directions, Escape, and overlay click live-verified | PASS |
| 9d | Accessibility: status live region | `role="status"`, `aria-live="polite"` | PASS — exact attributes | PASS |
| 9e | Accessibility: tab semantics | `role=tablist/tab/tabpanel`, `aria-selected`, `aria-controls`, roving tabindex | PASS — roles/ARIA/roving tabindex match | PASS |
| 10 | Empty states and headers | Board, Remaining, History, Browser, Preview copy unchanged | PASS — all empty-state and header copy matches | PASS |
| 10a | History header/counts | `6 picked` for the 6-entry fixture; `showing the last N` when truncated (source-verified) | PASS — `6 picked`; only dynamic timestamps differ | PASS |
| 10b | Remaining header/counts | `10 remaining`; `showing the first N` when truncated (source-verified) | PASS — `10 remaining` | PASS |
| 10c | Choice board truncation | 48 flaps, last flap `…`; full 84-character name in `title`; screen-reader heading keeps full name | PASS — 48 flaps, last `…`, 84-character title, full SR heading | PASS |
| 10d | Board stats and empty titles | `Nothing picked yet` + `Press Pick to choose the first one.`; `Nothing to pick` + `This folder is empty.`; `All picked` + `Clear or archive history to start over.` | PASS — all three title/meta pairs exact | PASS |

### US2 replay notes (T036, 2026-11-04)

The US2 replay re-captured `main@d25abef` and the refactored tree with the same
fixtures and the same headless Chromium CDP script. Both runs recorded 71 states
and 25 screenshots. The recorded JSON is identical after normalizing the archive
backup timestamp and the history clock times (the only dynamic values). 21 of
the 25 screenshots are byte-identical; the four exceptions differ only in
transient board-flap animation frames, native video-control chrome, or a handful
of 1-value antialiasing pixels at panel corners. No functional, textual, timing,
keyboard, or accessibility differences were observed.

### US1 replay notes (T024, 2026-11-03)

The US1 replay used the same headless Chromium scripts as the baseline against
`main@d25abef`'s evidence. Compared JSON keys are identical, and every value
matches except the expected dynamic values below:

- History row timestamps differ because the fixtures are regenerated at capture
  time (`17:33` baseline vs `18:27` after). The date/time formatting is identical.
- The archive backup name embeds the archive time
  (`.choosier-20261103T140430Z.jsonl.old` baseline vs
  `.choosier-20261103T145743Z.jsonl.old` after), and the Ctrl+N `before` status
  embeds that name. The pattern and message are identical.
- `previewArchive.meta` was empty in the baseline JSON while the baseline
  screenshot shows `Archive`; the after run captured `Archive`. This is a
  baseline capture timing flake, not a behavior change.

No functional, textual, timing, keyboard, or accessibility regressions were
observed in the US1 flow set. T036 re-ran the full replay at all three viewport
ranges and recorded the US2 notes above.


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

Re-captured on 2026-11-04 from a clean `main@d25abef` worktree serving the same
built frontend against the same fixtures as the after run.

| Evidence | Contents |
|---|---|
| `results.json` | 71 recorded states: initial load, options, browser, pick/validation, text/image/archive/video previews, viewer interactions, dry run, history/dialogs/archive/clear, keyboard/ARIA, empty states, and board truncation |
| `initial-desktop.png`, `initial-tablet.png`, `initial-phone.png` | Initial load at 1280×900, 800×900, 390×844 |
| `pick-text-desktop.png` | Picked text item, preview, remaining/history counts |
| `preview-image-desktop.png`, `preview-archive-desktop.png`, `preview-video-desktop.png` | Preview types |
| `viewer-single-desktop.png`, `viewer-archive-desktop.png`, `viewer-zoom-desktop.png` | Viewer states |
| `browser-root-desktop.png`, `browser-empty-desktop.png`, `browser-error-desktop.png` | Browser states |
| `history-desktop.png`, `history-after-remove-desktop.png`, `history-tablet.png`, `history-phone.png` | History and responsive states |
| `options-desktop.png`, `options-tablet.png`, `options-phone.png` | Options responsive states |
| `batch-dialog-desktop.png`, `clear-dialog-desktop.png`, `clear-confirmed-desktop.png` | Confirmation and removal states |
| `board-empty-desktop.png`, `board-truncated-desktop.png` | Board empty/truncation states |

## After evidence

Local directory: `/tmp/opencode/choosier-parity/after/` (not committed).

The after run used the same harness and fixture reset as the baseline. It
contains `results.json` and the same 25 screenshot names:

```text
batch-dialog-desktop.png            history-desktop.png
board-empty-desktop.png             history-phone.png
board-truncated-desktop.png         history-tablet.png
browser-empty-desktop.png           initial-desktop.png
browser-error-desktop.png           initial-phone.png
browser-root-desktop.png            initial-tablet.png
clear-confirmed-desktop.png         options-desktop.png
clear-dialog-desktop.png            options-phone.png
history-after-remove-desktop.png    options-tablet.png
pick-text-desktop.png               preview-archive-desktop.png
preview-image-desktop.png           preview-video-desktop.png
viewer-archive-desktop.png          viewer-single-desktop.png
viewer-zoom-desktop.png
```

`results.json` matches the baseline after normalizing the dynamic archive
timestamp and history clock times. 21 screenshots are byte-identical; the four
remaining images differ only in transient flap animation frames, native video
controls, or 1-value antialiasing pixels. No unexplained visual difference was
found at any viewport.

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
