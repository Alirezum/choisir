# Quickstart Validation: Skip and Snooze

**Feature**: `008-skip-snooze` | **Date**: 2026-11-17

This guide proves the feature end to end in both interactive interfaces. It does
not replace the automated tests; it records the manual checks and the expected
observable outcomes.

## Prerequisites

From the repository root:

```sh
uv sync --group dev --extra ui --extra web
cd frontend && npm ci && npm run build && cd ..
```

Use a disposable target folder so history and target hashes are easy to compare:

```sh
export SKIP_DEMO="$(mktemp -d)"
printf 'alpha\n' > "$SKIP_DEMO/alpha.txt"
printf 'beta\n'  > "$SKIP_DEMO/beta.txt"
printf 'gamma\n' > "$SKIP_DEMO/gamma.txt"
mkdir "$SKIP_DEMO/delta"
```

`$SKIP_DEMO/.choosier.jsonl` is the default log. Never point a real folder at
this guide.

## Automated checks

```sh
uv run pytest tests/test_skip.py tests/test_services_state.py \
  tests/test_services_pick.py tests/test_tui.py
uv run pytest tests/test_web.py tests/test_api_contract.py \
  tests/test_api_errors.py tests/test_history_consistency.py
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy choosier main.py tests
cd frontend && npm run check:api && npm run test:api && npm run check:ui \
  && npm run test:ui && npm run build && cd ..
uv build
```

The tests cover:

- Request validation and name bounds.
- Remaining exclusion, skipped/present lists, and all-skipped classification.
- Picked entries hidden from the skipped display but retained for pruning.
- Deleted/renamed pruning and filter/option changes.
- Expiry with an injected monotonic clock (no ten-minute wait).
- TUI controls, keyboard reachability, messages, and target/log resets.
- Web state/pick fields, all-skipped, and unchanged history bytes.
- The generated contract and the unchanged CLI behavior.

## Manual TUI check

Start the TUI against the disposable folder:

```sh
uv run choosier --ui "$SKIP_DEMO"
```

1. Open the **Remaining** tab. Confirm the three files and the `delta` folder
   are listed, with a `Not now` action.
2. Highlight `alpha.txt` and activate **Not now**.
   - Expected: `alpha.txt` leaves the remaining list and remaining count.
   - Expected status: `Skipped alpha.txt. It returns in ten minutes or when this
     session ends.`
   - Expected: a separate skipped row shows `alpha.txt` and its return time.
   - Expected: the History tab is empty and the history log does not exist or
     has the same bytes as before.
3. Press **Pick** several times.
   - Expected: `alpha.txt` is never chosen while skipped.
   - Expected: every other eligible entry can still be chosen and logged.
4. Restore one skipped entry.
   - Expected: `Restored alpha.txt.` It reappears in Remaining immediately and
     leaves the skipped list.
   - Expected: history is unchanged.
5. Skip two entries, then use **Restore all**.
   - Expected: both return immediately, the skipped list clears, and history is
     unchanged.
6. Skip every remaining entry.
   - Expected: the remaining area explains that every available item is
     skipped, shows zero available, and keeps **Restore all** available.
   - Press **Pick**.
   - Expected status: `Every available item is skipped. Restore skipped items to
     pick again.`
   - Expected: no new history line and no target change.
7. Change the active folder or the log-file setting while skips are active.
   - Expected: the skipped list clears for the previous target and the new
     target starts with no skips.
   - Change back to the previous target. Expected: the old skips are not
     restored.
8. Restart the TUI on the same folder.
   - Expected: every previously skipped entry is eligible again; no skip is
     restored.
9. Keyboard-only pass: use Tab/Shift+Tab and Enter to reach the remaining list,
   **Not now**, the skipped list, **Restore**, and **Restore all**. Confirm
   visible focus and that each action's label names the entry it affects.

## Manual web check

Start the web UI against the disposable folder:

```sh
uv run choosier --web --port 8765 "$SKIP_DEMO"
```

Open `http://127.0.0.1:8765`.

1. In the Remaining panel, activate **Not now** on `alpha.txt`.
   - Expected: the row leaves the remaining list, the remaining count drops,
     the status names the entry and the return condition, and the skipped
     section shows `alpha.txt` with its remaining cooldown.
2. Pick several times.
   - Expected: `alpha.txt` is never selected while skipped; history grows
     exactly by the picks that were logged.
3. Restore `alpha.txt` with its **Restore** button.
   - Expected: it returns to the remaining list immediately; history is
     unchanged.
4. Skip two entries and use **Restore all**.
   - Expected: both return, the skipped section clears, and history is
     unchanged.
5. Skip every remaining entry, then press **Pick**.
   - Expected: the all-skipped message appears, no history line is written, and
     **Restore all** is available.
6. Reload the page.
   - Expected: every previously skipped entry is eligible again; no skip is
     restored. The skipped section is empty.
7. Open a second tab on the same folder and skip different entries in each tab.
   - Expected: each tab shows only its own skips; neither tab blocks the other
     tab's picks.
8. Keyboard-only pass: Tab to each **Not now**, **Restore**, and **Restore all**
   control. Confirm visible focus and that each accessible name identifies the
   entry it affects.

## Cooldown expiry check

The automated tests inject a monotonic clock, so they verify the ten-minute
expiry without waiting. For a manual observation, skip one entry and leave the
interface open:

- At the ten-minute mark, the skipped row disappears and the entry returns to
  Remaining without a reload or button press.
- If the interface is closed before then, the next session starts with the
  entry eligible (no skip is restored).

## History and target integrity check

Capture the baseline before any skip:

```sh
if [ -f "$SKIP_DEMO/.choosier.jsonl" ]; then
  sha256sum "$SKIP_DEMO/.choosier.jsonl"
else
  echo "no history log yet"
fi
find "$SKIP_DEMO" -mindepth 1 -maxdepth 1 ! -name '.choosier.jsonl' -printf '%P\n' | sort
```

Repeat after every skip, restore, restore-all, expiry, all-skipped pick, and
target change. Expected:

- The history file hash is identical, or the file is still absent.
- The target listing is identical.
- No `.lock`, skip, or cooldown file appears in the target.
- The history line count changes only when a normal `picked` result is logged.

## One-shot CLI check

Run the existing command-line path against a disposable folder:

```sh
printf 'a\n' > "$SKIP_DEMO/cli-a.txt"
uv run choosier "$SKIP_DEMO"
```

Expected:

- The same prompt, flags, output, and exit codes as before.
- No skip command, option, or prompt is offered.
- The history log is written exactly as a normal CLI pick.
- `uv run pytest tests/test_cli.py` passes unchanged.

## Expected result summary

| Scenario | Expected |
|----------|----------|
| Skip a remaining entry | Leaves remaining; separate skipped row; zero history writes |
| Pick during cooldown | Skipped entry never chosen; others remain available |
| Restore one | Returns immediately; only that entry changes |
| Restore all | All return immediately; skipped list clears |
| All eligible skipped | Distinct all-skipped message; pick writes nothing; restore offered |
| Folder or log setting change | Skips clear for the previous target and do not return |
| New session or reload | All skips gone; entries eligible again |
| Concurrent sessions/tabs | Independent skips; neither blocks the other's picks |
| Deleted/renamed skipped entry | Pruned silently; no error; no other entry affected |
| History archive/clear/edit | Skips keep their own cooldown; history behavior is unchanged |
| CLI | Flags, prompt, output, exit codes, and history behavior unchanged |
