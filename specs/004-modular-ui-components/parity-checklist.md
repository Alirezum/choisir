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
| Desktop | >900px | 1280×900 | Captured; no horizontal overflow | Captured; no horizontal overflow | PASS |
| Tablet | 561–900px | 800×900 | Captured; no horizontal overflow | Captured; no horizontal overflow | PASS |
| Phone | ≤560px | 390×844 | Captured; no horizontal overflow | Captured; no horizontal overflow | PASS |

## Flow matrix

Record `Baseline` and `After` as the observed outcome, including exact text where
relevant. Use `PASS` only when they match; otherwise record the deviation and its
explicit decision. "Source-verified" means the baseline was confirmed by reading
the untouched implementation when the flow is not safely triggerable headlessly.

| # | Flow / check | Baseline (main@d25abef) | After | Result |
|---|---|---|---|---|
| 1 | Initial load with defaults | Defaults path loaded; Remaining 10, History 0; board "Nothing picked yet"; preview empty copy shown | PASS — defaults path loaded; Remaining 10, History 0; board and preview empty copy unchanged | PASS |
| 1a | Initial status text | `Choose a folder, then press Pick.` | PASS — exact text | PASS |
| 2 | Browse: initial load for current path | Root header shows current path; folders first, then files; Parent folder row present | PASS — root header, parent-first order, rows, and disabled Use button match | PASS |
| 2a | Browse: parent navigation | Parent row loads `/tmp/opencode`; header updates | PASS — parent navigation reached `/tmp/opencode`; header updated | PASS |
| 2b | Browse: child navigation | `folder-a` loads child path; Parent row returns | PASS — `folder-a` child path loaded; Parent row returns | PASS |
| 2c | Browse: empty folder copy | `This folder is empty.` | PASS — exact copy | PASS |
| 2d | Browse: unreadable/missing path error | Source-verified: shared error message, listing cleared | PASS — source-verified; shared error path unchanged | PASS |
| 3 | Options: log file change | Applies to next pick; state refresh scheduled | PASS — live labels/placeholders match; `use-workspace-state` debounces log changes and `use-picker` sends the nullable log file | PASS |
| 3a | Options: seed change | Applies to next pick | PASS — `use-picker` sends the parsed nullable seed; invalid seed text matches | PASS |
| 3b | Options: dry run change | Applies to next pick | PASS — `use-picker` sends `dry_run` and emits the dry-run message when not logged | PASS |
| 3c | Options: hidden change | Refreshes filters after 250ms; hidden entries appear | PASS — unit test covers the 250ms hidden-filter refresh | PASS |
| 3d | Options: mode changes (all/files/dirs) | Mutually exclusive files/dirs filters | PASS — unit tests cover the mutually exclusive filters | PASS |
| 4 | Pick: success | `Picked only.txt.`; board flaps animate; preview text shown | PASS — `Picked only.txt.`; board flaps animate; preview text unchanged | PASS |
| 4a | Pick: dry run | Source-verified: `Picked <item>. Dry run, so it wasn't logged.` | PASS — unit-tested exact dry-run copy | PASS |
| 4b | Pick: blank path | `Enter a folder path.`; focus returns to `.path-input` | PASS — exact text; focus returned to `.path-input` | PASS |
| 4c | Pick: non-integer seed | `Seed must be a whole number.` | PASS — exact text | PASS |
| 4d | Pick: invalid path | `That folder doesn't exist.` | PASS — exact text | PASS |
| 4e | Pick: empty folder | `That folder has nothing to pick.` | PASS — exact text | PASS |
| 4f | Pick: exhausted | `All items have been picked. Clear or archive history to start over.` | PASS — exact text | PASS |
| 4g | Pick: backend failure | Source-verified: shared `apiErrorMessage` text; refresh still runs | PASS — unit-tested shared error path; refresh still runs | PASS |
| 5 | Preview: text | Text body rendered; meta line absent | PASS — text body rendered; no meta line | PASS |
| 5a | Preview: single image | `1 image`; meta `PNG, 779 B`; grid has `is-single` and `variant=preview` URL | PASS — `1 image`; `PNG, 779 B`; `is-single`; preview-variant URL | PASS |
| 5b | Preview: archive frames | `3 images`; meta `Archive`; frames numbered `01`–`03` | PASS — `3 images`; `Archive`; frames `01`–`03` (baseline JSON missed the meta line; the baseline screenshot confirms it was rendered) | PASS |
| 5c | Preview: truncated image total | Source-verified: `N of M images` when `image_total > images.length`; not exercised because the cap is 1000 images | PASS — source-verified; preview internals unchanged in US1 | PASS |
| 5d | Preview: video | `MP4, 7.2 KB`; video element with `/api/video` source; no fallback | PASS — `MP4, 7.2 KB`; `/api/video` source; no fallback | PASS |
| 5e | Preview: video playback failure | Source-verified: fallback copy with **Open** guidance | PASS — source-verified; fallback copy unchanged | PASS |
| 6 | Open: current item | `Opened only.txt.` | PASS — exact text | PASS |
| 6a | Open: no current item | Source-verified: `Pick something first.` (Open control is hidden until an item exists) | PASS — unit-tested exact copy | PASS |
| 7 | History: archive with log | `Archived history to .choosier-*.jsonl.old.`; history clears after refresh | PASS — `.choosier-20261103T145743Z.jsonl.old.`; history cleared (timestamp is dynamic) | PASS |
| 7a | History: archive without log | `No history file at /tmp/opencode/choosier-empty/.choosier.jsonl.` | PASS — exact text | PASS |
| 7b | History: clear confirm | Dialog title `Clear history?`, detail is the log path; confirm shows `Cleared <log>.`; history becomes 0 | PASS — title/detail/focus match; `Cleared <log>.`; history 0 | PASS |
| 7c | History: clear cancel | Dialog closes; no request; history unchanged | PASS — dialog closed; unit test confirms no request | PASS |
| 7d | History: single removal, 0/1/many | `No history entry for "ghost.txt".`; `Removed "solo.txt" from history.`; `Removed 2 entries for "paired.txt".` | PASS — all three messages exact | PASS |
| 7e | History: row click preview | Row checked and selected; `Previewing alpha.txt from history.` | PASS — row checked and selected; exact status | PASS |
| 7f | History: shift-click range | Anchor at first row; shift-click third row produced 3 checked rows | PASS — 3 checked rows | PASS |
| 7g | History: select all / clear selection | 5 rows checked; link becomes `Clear selection`; delete label `Delete selected (5)` | PASS — 5 checked; `Clear selection`; `Delete selected (5)` | PASS |
| 7h | History: batch delete confirm | Title `Delete history for 5 items?`; detail explains re-pickability; labels `Cancel` / `Delete 5 items`; cancel focused | PASS — exact title/detail/labels; Cancel focused | PASS |
| 7i | History: batch delete 0/1/many | 1 item: `Removed 1 entry from history.`; 4 items: `Removed 4 entries from history.`; 0 is source-verified `No matching history entries to remove.` | PASS — 1 and 4 exact; 0 unit-tested exact copy | PASS |
| 7j | History: batch cancel | Dialog closes; all 5 checks remain | PASS — dialog closed; 5 checks remain | PASS |
| 7k | History: busy guards | Source-verified: remove/archive/clear disabled or ignored while busy | PASS — unit-tested busy guards | PASS |
| 7l | History: path/log change clears selection and pending delete | Source-verified: both watchers clear checked items and pending delete | PASS — unit-tested path/log resets | PASS |
| 8 | Viewer: open/close | Opens at clicked index; Close/Escape returns | PASS — opened at clicked index; Escape returned | PASS |
| 8a | Viewer: next/previous wrap | 3 images: next at 3/3 → 1/3; previous at 1/3 → 3/3 | PASS — both wraps match | PASS |
| 8b | Viewer: zoom levels/limits | Buttons/wheel: `Fit` → `125%` → `200%`; reset returns `Fit`; clamp is 1–8 | PASS — 125%/200%, reset `Fit`, clamp 1–8 | PASS |
| 8c | Viewer: double-click | Toggles `Fit` ↔ `200%` | PASS — toggles `Fit` ↔ `200%` | PASS |
| 8d | Viewer: drag clamp | 2x drag clamped to image bounds; transform `translate(80px, 60px) scale(2)` at the observed edge | PASS — transform and 160×120 clamp match | PASS |
| 8e | Viewer: original link | `/api/image?path=…&index=0` in a new tab | PASS — exact href | PASS |
| 8f | Viewer: scroll lock restore | Body overflow `hidden` while open; restored to `''` after close | PASS — `hidden` then `''` | PASS |
| 8g | Viewer: single image | Counter `1 / 1`; no next/previous controls | PASS — `1 / 1`; no nav controls | PASS |
| 9 | Keyboard: Ctrl+N | Picks from the page; status changed to `Picked ctrln.txt.`; blocked while the clear dialog is open | PASS — `Picked ctrln.txt.`; blocked while the clear dialog was open | PASS |
| 9a | Keyboard: tabs | ArrowRight → History, Home → Remaining, End → Options; focus follows | PASS — all three moves; focus follows | PASS |
| 9b | Keyboard: focus visibility | Source/CSS-reviewed: interactive controls keep visible focus styling | PASS — no style changes; CSS-reviewed | PASS |
| 9c | Keyboard: dialog | Cancel focused initially; Tab trapped; Escape closes; overlay click cancels | PASS — initial focus and Escape verified; Tab trap source-verified | PASS |
| 9d | Accessibility: status live region | `role="status"`, `aria-live="polite"` | PASS — exact attributes | PASS |
| 9e | Accessibility: tab semantics | `role=tablist/tab/tabpanel`, `aria-selected`, `aria-controls`, roving tabindex | PASS — roles/ARIA/roving tabindex match | PASS |
| 10 | Empty states and headers | Board, Remaining, History, Browser, Preview copy unchanged | PASS — all empty-state and header copy matches | PASS |
| 10a | History header/counts | `5 picked`; `showing the last N` when truncated (source-verified) | PASS — `5 picked`; only dynamic timestamps differ | PASS |
| 10b | Remaining header/counts | `10 remaining`; `showing the first N` when truncated (source-verified) | PASS — `10 remaining` | PASS |
| 10c | Choice board truncation | 48 flaps, last flap `…`; full 84-character name in `title`; screen-reader heading keeps full name | PASS — 48 flaps, last `…`, 84-character title, 91-character SR heading | PASS |
| 10d | Board stats and empty titles | `Nothing to pick` + `This folder is empty.`; `All picked` + `Clear or archive history to start over.` | PASS — both title/meta pairs exact | PASS |

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
observed in the US1 flow set. US2 conversion must keep these rows green; T036
re-runs the full replay at all three viewport ranges.


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

## After evidence

Local directory: `/tmp/opencode/choosier-parity/after/` (not committed).

| Evidence | Contents |
|---|---|
| `baseline-results.json`, `baseline-extra-results.json` | Same harness as the baseline; keys and values identical except the dynamic values recorded in the US1 replay notes |
| `*-desktop.png`, `*-tablet.png`, `*-phone.png` | US1 replay screenshots at 1280×900, 800×900, 390×844 |

The US1 replay directory currently contains the 24 screenshots and both JSON
files listed above. US2 re-captures the full matrix in the same local directory.

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
