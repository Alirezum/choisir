# Quickstart Validation: Snooze the Selected Pick

**Feature**: `009-snooze-selected-pick` | **Date**: 2026-11-18

This guide proves Snooze end to end in both interactive interfaces and confirms
that no API, CLI, or persistent-state boundary changed. The normative rules are
in [spec.md](./spec.md), [data-model.md](./data-model.md), and
[contracts/snooze-selected-pick.md](./contracts/snooze-selected-pick.md).

## Prerequisites

From the repository root:

```sh
uv sync --group dev --extra ui --extra web
cd frontend && npm ci && npm run build && cd ..
```

**Design gate for T027**: before editing `frontend/src/styles.css`, load
`.agents/skills/frontend-design/SKILL.md` and follow its plan,
review-against-the-brief, build, and critique steps. `.board-snooze` must reuse
the existing board button treatment; do not introduce a new palette, typeface,
card, animation, or layout system.

Create a disposable target folder with a folder entry, a plain file, a video,
an image, and a file with spaces:

```sh
export SNOOZE_DEMO="$(mktemp -d)"
printf 'alpha\n' > "$SNOOZE_DEMO/alpha.txt"
printf 'beta\n'  > "$SNOOZE_DEMO/beta.txt"
printf 'notes\n' > "$SNOOZE_DEMO/notes with space.txt"
printf 'video\n' > "$SNOOZE_DEMO/clip.mp4"
printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z1uQAAAAASUVORK5CYII=' \
  | base64 -d > "$SNOOZE_DEMO/preview.png"
mkdir "$SNOOZE_DEMO/delta"
```

`$SNOOZE_DEMO/.choosier.jsonl` is the default log. Use only a disposable
folder for these checks.

## Automated Checks

Focused suites:

```sh
uv run pytest tests/test_tui.py
cd frontend && npx vitest run \
  tests/ui/state/use-undo.test.ts \
  tests/ui/state/use-skip.test.ts \
  tests/ui/state/use-snooze.test.ts \
  tests/ui/state/use-workspace.test.ts \
  tests/ui/views/ChoiceBoard.test.ts && cd ..
```

The full quality gate:

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy choosier main.py tests
cd frontend && npm run check:api && npm run test:api \
  && npm run check:ui && npm run test:ui && npm run build && cd ..
```

Expected: every command passes; the API contract check reports no generated
change, and the route inventory stays at 17. The new coverage must show:

- Snooze is disabled before a successful logged pick and after a dry run,
  failed/empty pick, completed Undo, target or log change, and log clear.
- A successful Snooze removes exactly one history line, adds one skip with the
  ten-minute cooldown, and clears the matching board/preview.
- Undo remains present and becomes disabled after success, then works normally
  for the next successful logged pick.
- A second Snooze of the same item is refused without a second history removal
  or duplicate skip.
- Missing items, externally changed history, empty history, transport errors,
  and competing actions refuse without adding a skip.
- Folder, video, image (`.png`), and spaced or Unicode names follow identical
  behavior with no media-specific branch.
- Snoozing the last remaining entry produces the existing all-skipped or
  neutral no-items state, offers restore, and picks nothing automatically.
- A real archive or clear disables both controls and retains the skip; an
  archive or clear that finds no log leaves the receipt available; an external
  log rotation refuses with the history-changed message.
- The two-session receipt shape matches the existing web test: an older receipt
  reports `changed`, the newest reports `undone`, and a re-picked skipped item
  is hidden and counted as picked until its new history line is removed.
- Restore, restore-all, and cooldown expiry make the item eligible without
  restoring its history line or re-enabling Undo.
- The same starting state produces the same outcome and message in the TUI and
  the web UI.
- The existing CLI assertions pass and the generated API contract is unchanged.

## Manual Terminal UI Check

Start against the disposable folder:

```sh
uv run choosier --ui "$SNOOZE_DEMO"
```

1. **Successful Snooze.** Pick an item with **Pick** (or `Ctrl+N`).
   - Expected: the item is logged and shown on the board.
   - Expected: **Undo** is enabled and **Snooze** is enabled and names the item.
2. Activate **Snooze**.
   - Expected status: `Snoozed <item>. Its pick was removed; it returns in ten
     minutes or when this session ends.`
   - Expected: exactly that latest history line disappears from the History
     tab and the log.
   - Expected: the item appears in the separate Skipped list with a live
     return time. The picked count decreases by one, the skipped count
     increases by one, and the remaining count stays at its post-pick value
     (it does not increase as it would after a plain Undo).
   - Expected: the board and preview clear only if they still showed the item;
     no replacement is picked.
   - Expected: **Undo** is still visible but disabled; **Snooze** is disabled.
3. **New pick.** Pick another item.
   - Expected: both **Undo** and **Snooze** are enabled for the new item.
   - Expected: the previously snoozed item cannot be picked while its skip is
     active.
4. **Restore.** Restore the snoozed item from the Skipped list.
   - Expected: `Restored <item>.` and the item is immediately eligible in
     Remaining.
   - Expected: its removed history line does not return and Undo does not
     become available for it.
5. **Restore all.** Snooze two items, then use **Restore all**.
   - Expected: both return immediately, the skipped list clears, and history is
     unchanged by the restore.
6. **Dry run.** Enable **Dry run** and pick.
   - Expected: **Snooze** is disabled; no history line is written.
7. **Deleted item.** Pick a file, delete it outside the app, then activate
   **Snooze** before refreshing the folder.
   - Expected: `Could not snooze <item>: it is no longer available.`
   - Expected: the history line is unchanged, no skip is added, and **Undo**
     remains available.
8. **External history change.** Pick a file, then edit or append to the log in
   another terminal. Activate **Snooze**.
   - Expected: `Could not snooze <item>: history changed.`
   - Expected: no additional line is removed, no skip is added, and the stale
     undo opportunity is gone.
9. **Target and log-file change.** Snooze an item, then change the folder or
   log-file field and change it back.
   - Expected: the skip and the undo opportunity clear for the new scope; the
     history removal already performed persists.
10. **Archive and clear.** Snooze an item, then use **Archive** on a real log
    and repeat with a successful **Clear**.
    - Expected: both **Undo** and **Snooze** are disabled because the receipt is
      gone; the skip remains until restore or session end.
    - Expected: invoking **Archive** or **Clear** when no log exists leaves the
      receipt and both controls available.
11. **Last remaining entry.** Reduce the folder to one eligible item (or skip
    all the others), pick it, and snooze it.
    - Expected: the existing all-skipped or neutral no-items state appears,
      restore is offered, and nothing is picked automatically.
12. **Keyboard-only pass.** Use Tab/Shift+Tab and Enter to reach **Pick**,
    **Open**, **Undo**, and **Snooze**. Confirm visible focus and that the
    Snooze accessible name/label names the item when enabled.
13. **Other item kinds.** Repeat the happy path with `delta` (folder),
    `clip.mp4` (video), `preview.png` (image), and `notes with space.txt`
    (spaces/Unicode path).
    - Expected: identical behavior; no media-specific branch.

## Manual Web UI Check

Start the loopback-only UI:

```sh
uv run choosier --web "$SNOOZE_DEMO"
```

Open `http://127.0.0.1:8765`.

1. **Successful Snooze.** Pick an item and activate **Snooze** beside **Undo**.
   - Expected status: `Snoozed <item>. Its pick was removed; it returns in ten
     minutes or when this session ends.`
   - Expected: the board clears when it shows that item, the history line is
     removed, the Remaining tab lists the item as skipped with its countdown,
     and the counts match the TUI.
   - Expected: **Undo** remains visible but disabled; **Snooze** is disabled.
   - Expected: the status and counts update without a manual reload, and
     feedback appears within one second.
2. **New pick.** Pick again.
   - Expected: both controls are enabled for the new item; the older snoozed
     item stays skipped and cannot be picked.
3. **Restore and restore all.** Use the existing skipped-list controls.
   - Expected: restored items become eligible; history and Undo remain
     unchanged.
4. **Reload.** Reload the page on the same folder.
   - Expected: the removed history line stays removed, the skip and undo
     opportunity are gone, and the item is eligible again.
5. **Deleted item.** Pick an item, delete it outside the app, activate
   **Snooze**.
   - Expected: `Could not snooze <item>: it is no longer available.`
   - Expected: no history change and no skip.
6. **External history change.** Pick an item, edit the log outside the app,
   activate **Snooze**.
   - Expected: `Could not snooze <item>: history changed.`
   - Expected: no additional line removed and no skip.
7. **Two tabs.** Open a second tab on the same folder and pick in both so each
   tab holds a different latest receipt.
   - Expected: the older tab's Snooze refuses with
     `Could not snooze <item>: history changed.` and removes nothing; the tab
     with the newest receipt snoozes normally.
   - Expected: after a snoozed item is picked again, the existing
     skipped-entry rule hides it from the skipped display and counts it as
     picked until that new history line is removed.
8. **Archive and clear.** Snooze an item, then archive the history and repeat
   with a successful clear.
   - Expected: both controls become disabled; closing and reopening the page
     starts with no receipt and no skip.
   - Expected: when there is no log, archiving or clearing leaves the receipt
     and both controls available.
9. **Last remaining entry.** Leave one eligible item, pick it, and snooze it.
   - Expected: the existing all-skipped or neutral no-items state appears,
     restore is offered, and no replacement is picked.
10. **Accessibility.** Reach **Snooze** with the keyboard alone. Confirm visible
    focus, Enter/Space activation, and the accessible name
    `Snooze last pick: <item>` when a receipt exists. Confirm the feedback appears in
    the existing accessible status region.
11. **Other item kinds.** Repeat the happy path with the folder, video, image
    (`preview.png`), and spaced-name entries. Expected: identical behavior.

## Cross-Interface Parity

For the same target, log, filters, and seed, perform the same sequence in both
interfaces and compare:

| Starting state | Expected outcome in both |
|----------------|--------------------------|
| Latest logged pick | Snooze and Undo available for that item |
| Latest logged pick previewed as a different history item | Undo remains available for the receipt; Snooze is disabled and refuses without changes |
| Successful Snooze | Same item, one line removed, one skip, same message |
| After Snooze | Undo visible and disabled; skip countdown shown |
| Dry run / empty / failed pick | Snooze unavailable; nothing changes |
| Deleted item | Item-unavailable refusal; no history or skip change |
| Changed history | History-changed refusal; no skip |
| Archive or clear a real log | Both controls disabled; skip retained |
| Archive or clear with no log | Receipt retained; both controls stay available |
| Last remaining item snoozed | All-skipped or neutral state; restore offered; no auto-pick |
| Restore / restore-all / expiry | Item eligible; history line not restored; Undo not re-enabled |

## Unchanged CLI Check

```sh
uv run choosier --help
uv run pytest tests/test_cli.py
```

Expected: no `snooze` option or command appears; flags, prompt behavior,
output, and exit codes are unchanged, and all existing CLI tests pass. The
additive no-snooze guard in `tests/test_cli.py` is test-only and does not
change CLI behavior.

## Cooldown Note

The ten-minute cooldown is validated by the automated tests with an injected
monotonic clock; do not wait ten minutes manually. The manual checks cover the
restore path and the visible countdown. A session restart is the practical
expiry equivalent: history stays removed and the item is eligible again.
