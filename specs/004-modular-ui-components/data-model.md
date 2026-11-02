# Phase 1 Data Model: Modular UI Components

**Feature**: `004-modular-ui-components`  
**Date**: 2026-11-02

## Scope note

This feature introduces no persisted data, database, schema, or protocol change.
The "model" here is the in-memory contract between the composition root, state and
behavior units, presentation views, and shared building blocks. The backend history
format, API response shapes, and shared client types remain authoritative and
unchanged.

## Layer and dependency matrix

| From \ To | `api*` | `types` / `view-models` | `state/` domain units | `state/` own interaction unit | `views/` | `components/` |
|---|---|---|---|---|---|---|
| `App.vue` | Forbidden | Allowed | Allowed | Allowed | Allowed | Indirect |
| `state/` domain unit | Allowed via shared client | Allowed | Allowed (explicit dependency) | Allowed | **Forbidden** | **Forbidden** |
| `state/use-preview` | Allowed via shared client | Allowed | Allowed | N/A | **Forbidden** | **Forbidden** |
| `state/use-image-viewer` | Forbidden | Allowed | Allowed | N/A | **Forbidden** | **Forbidden** |
| `views/PreviewPanel.vue` | **Forbidden** | Allowed | **Forbidden** | `use-preview` only | N/A | Allowed |
| `views/ImageViewer.vue` | **Forbidden** | Allowed | **Forbidden** | `use-image-viewer` only | N/A | Allowed |
| Other `views/*.vue` | **Forbidden** | Allowed | **Forbidden** | **Forbidden** | N/A | Allowed |
| `components/*.vue` | **Forbidden** | Allowed | **Forbidden** | **Forbidden** | **Forbidden** | Allowed (blocks only) |

## State-unit inventory

Every unit returns plain refs, computed refs, and action functions. Units never
return or import a view. Side effects are listed explicitly.

| Unit | Owned state | Inputs | Outputs / actions | Side effects | Test focus |
|---|---|---|---|---|---|
| `use-status` | `status` | Initial message | `setStatus`, `reportError` | None | Exact message replacement; `ApiError` and unknown failures use `apiErrorMessage` |
| `use-folder-options` | `path`, `logFile`, `seed`, `dryRun`, `includeHidden`, `mode` | None | Fields, `filters`, `entryPath(item)` | None | Filter mapping; trailing separator handling; mode exclusivity |
| `use-workspace-state` | `state`, refresh timer | `path`, `logFile`, `filters`, status setter, path/log callbacks | `refresh()`, `scheduleRefresh()` | Debounced API `state` call; timers; watchers | Blank path clears state; success/error; 250ms debounce; timer cleanup |
| `use-choice` | `choice`, `pickSerial`, preview serial | None | `setPicked`, `beginPreview`, `applyPreview`, `invalidate` | None | Stale preview rejection; serial monotonicity; invalidation clears choice |
| `use-picker` | In-flight pick guard | folder options, choice, status, refresh, path input ref | `pick()`, `openEntry()`, `openCurrent()` | API `pick`/`open`; refresh after pick | Path/seed validation; invalid/empty/exhausted outcomes; dry-run text; failure message |
| `use-history-selection` | `checkedItems`, `anchor` | Entries | `toggle`, `toggleWithShift`, `addRange`, `toggleAll`, `clear`, `pruneMissing` | None | Anchor reset; shift range; select all/clear; entries refresh pruning |
| `use-history-actions` | `clearing`, `removingItem`, `removingHistory`, `pendingHistoryDelete` | Folder options, state, choice, selection, status, refresh | `archive`, `requestClear`, `confirmClear`, `cancelClear`, `removeOne`, `requestDeleteSelected`, `confirmDeleteSelected`, `cancelDelete`, `previewHistoryItem`, `openHistoryItem`, derived counts/messages | API archive/clear/remove/preview/open; refresh; selection cleanup | Confirmation lifecycle; busy guards; removed counts; stale preview; exact messages |
| `use-browser` | `listing`, `error` | `path`, use-folder callback, status | `navigate(entry)`, `useThisFolder()`, `load(target)` | API `browse`; path watcher | Immediate load; parent/child navigation; error state; empty folder |
| `use-preview` | `viewerIndex`, `videoError` | `path`, `preview` | `images` with `src` (grid preview/thumb variant) and `fullSrc` (viewer/original), `videoUrl`, labels, meta/body, `openViewer`, `closeViewer`, `reset` | Client media address construction; no network request | Labels/counts/fallbacks; preview vs thumb selection; full URL; reset on preview change |
| `use-image-viewer` | `index`, `zoom`, `offset`, `dragging`, `imageEl` | `images` (with `fullSrc`), `start`, close callback | `current`, `counter`, `zoomLabel`, `imageStyle`, `step`, `stepZoom`, `setZoom`, `resetZoom`, `toggleZoom`, wheel/pointer/key handlers, `preload` | Body overflow lock; window keydown; pointer capture; image preload | Wrap navigation; zoom levels/limits; clamp; double-click; keys; scroll lock restore |
| `use-tabs` | `activeTab` | Tabs definition, state | `count(id)`, `onKey(event, id)` | `nextTick` focus via document element | Arrow/Home/End wrap; focus target; count values |
| `use-shortcuts` | None | Pick action, blocked predicate | `onKeydown` | Window keydown registration | Ctrl+N only; blocked by confirmation/overlay; cleanup |
| `use-bootstrap` | None | Folder options, workspace state, status | `start()` | API `defaults`; initial refresh; mounted hook | Defaults applied in order; failure message; initial refresh |
| `use-workspace` | None (wiring) | All unit factories | Binding surface for `App.vue` | Connects watchers/callbacks and lifecycle | Path/log reset wiring; unit composition; no domain rules |

## View-model and intent contracts

| View | Inputs (ready to render) | Intents (emitted) | Presentation constraints |
|---|---|---|---|
| `ChoiceBoard` | `item`, `remaining`, `picked`, `serial` | `pick`, `open` | Truncation at 48 characters; empty title/meta; stats; Ctrl+N hint |
| `PanelTabs` | `tabs`, `activeTab`, counts | `select(id)`, `keydown(event, id)` | Tab roles, `aria-selected`, `aria-controls`, roving tabindex |
| `RemainingPanel` | `items`, `total`, header text | None | Header truncation copy; empty states |
| `HistoryPanel` | `entries`, `total`, `busy`, `selected`, `checkedItems`, derived header/labels | `archive`, `clear`, `remove(item)`, `open(item)`, `select(item, shift)`, `toggleAll`, `removeSelected` | No anchor; no data access; timestamps and row semantics unchanged |
| `BrowserPanel` | `path`, `listing`, `error` | `navigate(target)`, `useFolder(path)` | No `api` import; parent/child icons and empty copy unchanged |
| `OptionsPanel` | `logFile`, `seed`, `dryRun`, `includeHidden`, `mode` | Field updates | Existing labels and placeholders unchanged |
| `StatusBar` | `message` | None | `role="status"`, `aria-live="polite"` |
| `ConfirmDialog` | `message`, `confirmLabel`, `cancelLabel` | `confirm`, `cancel` | Focus trap, Escape, cancel focus, overlay click |
| `PreviewPanel` | `path`, `preview` | `openViewer(index)` internal, `closeViewer` internal | Uses `use-preview`; no API import; labels/meta/fallbacks unchanged |
| `ImageViewer` | `images` (with `src`/`fullSrc`), `start` | `close` | Uses `use-image-viewer`; no API import; keyboard/zoom/scroll lock unchanged |
| `PanelShell` | `headerClass` | Slots: `header`, default, `actions` | Owns `.panel`, `.panel-header`, `.panel-actions`; class fallthrough |
| `EmptyState` | Optional class | Default slot | Owns `.panel-empty` |

## State transitions

### Bootstrap

1. `use-bootstrap.start()` calls `api.defaults()`.
2. On success, `path` and `logFile` are assigned, then `refresh()` runs.
3. The path/log assignments also trigger the existing 250ms debounced refresh;
   do not suppress that duplicate, because the current timing/sequence is part of
   the parity contract.
4. On failure, the status message is set through the shared error path; refresh
   still runs with the current (empty) path and clears state.

### Refresh and debounce

1. A change to `path`, `logFile`, `includeHidden`, or `mode` schedules a refresh.
2. The timer is cleared and restarted at 250ms.
3. If `path` is blank after trimming, `state` becomes `null` and no request runs.
4. Otherwise `api.state({ path, log_file, filters })` runs; success replaces
   `state`; failure sets the shared error message; prior state remains until the
   response replaces it.
5. Unmount clears the timer.

### Path change

1. Preview serial increments, invalidating in-flight previews.
2. `choice` becomes `null`; `pickSerial` is unchanged.
3. History checked items, anchor, and pending batch confirmation clear.
4. A refresh is scheduled.

### Log-file change

1. History checked items, anchor, and pending batch confirmation clear.
2. A refresh is scheduled.

### Pick

1. Blank path → status "Enter a folder path." and focus the path input; stop.
2. Non-integer seed → status "Seed must be a whole number."; stop.
3. Call `api.pick` with path, nullable log file, nullable seed, dry-run, filters.
4. `invalid_path` / `empty` / `exhausted` → exact current messages; no choice.
5. Success → set choice `{ item, path: entryPath(item), preview }`, increment
   `pickSerial`, invalidate earlier preview requests, set logged or dry-run message.
6. Failure → shared error message.
7. Always refresh after the attempt.

### Preview from history

1. Increment preview serial; set choice to `{ item, path, preview: null }`.
2. Fetch `api.preview(path)`.
3. If the serial no longer matches, ignore the result.
4. Success → replace choice preview; status "Previewing {item} from history."
5. Failure → only apply the shared error message if the serial still matches.

### History archive / clear

1. Archive has no confirmation; clear sets `clearing = true`.
2. Confirm clear calls `api.clear`; cancel clears the flag without a request.
3. Success messages depend on `removed`/`backup` being null; failure uses the shared
   error message.
4. Both always refresh and clear history selection.

### Single removal

1. Ignore if another single removal is in progress.
2. Set `removingItem`; call `api.removeHistoryItem`.
3. `removed` 0/1/many → exact messages.
4. Always clear the item from selection, clear `removingItem`, and refresh.

### Batch removal

1. `requestDeleteSelected` copies checked items into `pendingHistoryDelete`; no
   request runs yet.
2. Confirm closes the dialog first, sets `removingHistory`, and calls
   `api.removeHistoryItems` with the copied list.
3. `removed` 0/1/many → exact messages.
4. Always prune the removed items from selection, clear the busy flag, and refresh.
5. Cancel clears the pending list without a request.

### Browser

1. Watching `path` with `immediate: true` loads the listing when the path is
   non-blank.
2. Success replaces `listing` and clears `error`; failure sets the shared error and
   clears `listing`.
3. Navigating a directory appends the entry name to the current listing path.
4. "Use this folder" reports the listing path to the folder options owner.

### Preview and viewer

1. A new preview resets `viewerIndex` to `null` and `videoError` to `false`.
2. Opening the viewer sets the index; closing clears it.
3. The viewer starts at the requested index, resets zoom on image change, preloads
   neighbors, and restores body overflow on unmount.
4. Zoom is clamped to 1–8; offsets are clamped to the scaled image bounds; pointer
   capture is used while dragging.

### Tabs and shortcuts

1. Active tab defaults to Remaining.
2. Arrow keys wrap, Home/End jump, and focus moves to the active tab.
3. Ctrl+N triggers pick unless the clear confirmation is active or a dialog/viewer
   overlay is present (the exact current `clearing || overlay` condition; removal
   busy flags do not add a new block).

## Validation rules

| Rule | Source |
|---|---|
| Trimmed path must be non-empty for refresh, pick, and browser load | FR-001, edge cases |
| Seed must be an integer when non-empty | FR-001 |
| Filter mapping: hidden flag; files-only and folders-only are mutually exclusive | FR-001 |
| Preview responses apply only when their serial is current | FR-010 |
| Refresh requests debounce at 250ms | FR-010 |
| Single and batch removals share one busy gate per concern | FR-010 |
| Clear and batch removal require confirmation; cancel is a no-op | FR-009 |
| No request runs while the relevant busy flag is set | FR-009, FR-010 |
| Error text always comes from the shared `apiErrorMessage` path | FR-001, FR-013 |
| Media URLs come only from the shared client, never from a view | FR-005, FR-021 |
| Exact status, empty-state, confirmation, and count text is preserved | FR-013, FR-022 |

## Boundary-check model

| Check | Applies to | Failure condition |
|---|---|---|
| View API isolation | `src/views/**/*.vue` | Imports `api*`; contains `fetch`, XHR, `/api/`, or envelope reads |
| View state isolation | `src/views/**/*.vue` | Imports a domain state unit; imports any state unit outside the two allowlisted view-local units |
| State isolation | `src/state/**/*.ts` | Imports `views/**` or `components/**` |
| Composition-root thinness | `src/App.vue` | Imports `api*`; contains API calls, timers, watchers, computed state, mounted hooks, or error formatting |
| Acyclic graph | All `src/**/*.{ts,vue}` | Any relative-import cycle |
| Shared scaffold | `src/views/**/*.vue` | Raw `.panel`, `.panel-header`, `.panel-empty`, or `.panel-actions` tokens |
| Test mapping | Every state unit, view, and shared block | No matching `tests/ui/**/<name>.test.ts` file |

## No migration or persistence

No data migration, schema, archive format, history format, or API version change is
part of this feature. Existing history files and API responses are read exactly as
before.
