# Quickstart Validation: Undo Last Pick

**Feature**: `007-undo-last-pick` | **Date**: 2026-11-17

This guide proves the feature end to end in both interactive interfaces. It does
not replace the automated tests; it records the manual checks and the expected
observable outcomes.

## Prerequisites

From the repository root:

```sh
uv sync --group dev --extra ui --extra web
cd frontend && npm ci && npm run build && cd ..
```

Use a disposable target folder so hashes are easy to compare:

```sh
export UNDO_DEMO="$(mktemp -d)"
printf 'alpha\n' > "$UNDO_DEMO/alpha.txt"
printf 'beta\n'  > "$UNDO_DEMO/beta.txt"
printf 'gamma\n' > "$UNDO_DEMO/gamma.txt"
mkdir "$UNDO_DEMO/delta"
```

`$UNDO_DEMO/.choosier.jsonl` is the default log. Never point a real folder at
this guide.

## Automated checks

```sh
uv run pytest tests/test_storage.py tests/test_services_history.py \
  tests/test_services_pick.py tests/test_chooser.py
uv run pytest tests/test_web.py tests/test_api_contract.py \
  tests/test_api_errors.py
uv run pytest tests/test_tui.py tests/test_history_consistency.py
cd frontend
npm run check:api
npm run check:ui
npm run test:api
npm run test:ui
npm run build
```

Full gate before handoff:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy choosier main.py tests
cd frontend && npm run build
```

Expected: all suites pass, the generated contract is current, and the route
inventory test reports 17 routes.

## Terminal UI scenarios

Start the TUI:

```sh
uv run choosier --ui "$UNDO_DEMO"
```

### T1 — Undo a logged pick

1. Press **Pick**. Note the item and confirm the status line says
   `Logged in ...`.
2. Verify **Undo** is enabled and its label includes the item (for example
   `Undo alpha.txt`).
3. Verify the history tab has one line and Remaining no longer lists the item.
4. Activate **Undo**.

Expected:

- Status: `Undid pick of <item>.`
- Exactly one history line removed; the other lines are byte-identical.
- The item returns to Remaining and can be picked again.
- The choice board clears, the preview returns to its placeholder, and Open is
  disabled.
- Undo is now disabled.

### T2 — Single-level and no redo

Press **Undo** again with the button disabled.

Expected: nothing changes; no second entry is removed and no redo action exists.

### T3 — Two picks, only the latest is removed

With at least three entries available, pick twice. Note the second item, then
undo.

Expected: only the second item's line disappears; the first line remains and
the board shows no choice. Pick again and confirm the undone item is eligible
while the first item is still logged.

### T4 — Dry run and failed outcomes clear undo

1. Make a logged pick, then enable **Dry run** and press **Pick**.
2. Verify Undo becomes disabled and history did not gain a line.
3. Disable Dry run. Delete the log with **Clear history**, then press Pick until
   the folder is exhausted or use an empty folder.

Expected: Undo stays disabled for every non-logged outcome; no line is removed.

### T5 — Folder and log changes clear undo

1. Make a logged pick.
2. Change the path input to another folder.

Expected: Undo becomes disabled immediately and the previous session's entry is
not removed from either folder's log. Repeat by changing the log-file input.

### T6 — External change refuses

1. Make a logged pick in the TUI.
2. In another terminal, append a valid JSONL line to `$UNDO_DEMO/.choosier.jsonl`.
3. Activate **Undo** in the TUI.

Expected: status `Could not undo <item>: history changed.`; the file is
byte-identical to its pre-undo state; the history view refreshes; the Undo
button becomes disabled.

Repeat by deleting the log instead of appending: expected
`Could not undo <item>: history is empty.` and no file is recreated.

### T7 — Restart clears availability

1. Make a logged pick, then quit the TUI.
2. Start it again with the same folder.

Expected: Undo is disabled until a new logged pick succeeds.

### T8 — Target content is untouched

Before a pick, record the tree:

```sh
find "$UNDO_DEMO" -mindepth 1 ! -name '.choosier.jsonl*' -print0 \
  | sort -z | xargs -0 sha256sum > /tmp/undo-before.txt
```

After undoing, run the same command to `/tmp/undo-after.txt` and compare.

Expected: identical target hashes and names. Only the history log changed, plus
the small `<log>.lock` coordination file.

## Web UI scenarios

Start the server and open the printed loopback URL:

```sh
uv run choosier --web "$UNDO_DEMO"
```

### W1 — Undo a logged pick

1. Press **Pick**. Confirm the board shows the item and history gains one line.
2. Confirm the **Undo** button is enabled and its accessible name includes the
   item. Inspect it in the browser accessibility tree or with
   `aria-label`.
3. Click **Undo**.

Expected: board and preview clear, history drops exactly one line, the item
returns to Remaining, the status region announces `Undid pick of <item>.`, and
Undo is disabled. The item can be picked again.

### W2 — Keyboard-only

Tab to Undo and press Enter/Space. Confirm the focus ring is visible and the
control has the item in its accessible name.

Expected: the same result as W1. No new keyboard shortcut is introduced, so
`Ctrl+Z` inside a text field continues to edit that field and never triggers
undo.

### W3 — No-pick and non-logged states

Check a fresh page, a dry-run pick, an empty folder, and an exhausted folder.

Expected: Undo is visible, disabled, and labelled as having nothing to undo. No
request is made while disabled.

### W4 — Folder/log changes

1. Make a logged pick.
2. Change the folder or the log-file field in Options.

Expected: Undo becomes disabled and no entry is removed from either log.

### W5 — Page reload

Make a logged pick, then reload the page.

Expected: Undo is disabled; the receipt was in memory only. The history line
remains.

### W6 — Two tabs / two sessions

1. Open two tabs on the same folder.
2. Pick in tab 1, then pick in tab 2.
3. Try Undo in tab 1.

Expected: tab 1 reports `history changed` and removes nothing, because its pick
is no longer the newest line. Undo in tab 2 succeeds and removes only tab 2's
line. Tab 1's entry remains.

### W7 — External edit

Use a terminal to append, rewrite, or delete the log between a pick and Undo.

Expected: `changed` or `nothing_to_undo`; the file is never rewritten; the
history view refreshes.

## Command-line boundary

```sh
uv run choosier --help
uv run choosier "$UNDO_DEMO" --seed 7 --dry-run
uv run choosier "$UNDO_DEMO" --list
```

Expected: no `--undo` option, no new output line, and the existing exit codes
(`0`, `1`, `3`, `4`) are unchanged. The CLI picks still use the same history
format and remain readable by the TUI and web UI.

## Pass criteria

- [ ] Exactly one history line is removed per successful undo in both interfaces.
- [ ] The undone item is eligible for the next pick.
- [ ] Repeated undo, dry runs, failed picks, history loads, other sessions, and
      restarts do not remove anything.
- [ ] External append/removal/rewrite leaves the log byte-identical.
- [ ] Folder/log changes clear the action.
- [ ] Target files/folders, active path, log setting, filters, seed, dry-run
      mode, and remembered folders are unchanged.
- [ ] Keyboard focus and the item-bearing accessible name work in both
      interfaces.
- [ ] The undo status appears within one second at the rotation limit.
- [ ] The CLI and contract gates are unchanged except for the documented
      additive route and field.
