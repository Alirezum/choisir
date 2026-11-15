# Validation Record: Undo Last Pick

**Feature**: `007-undo-last-pick` | **Date**: 2026-11-17

Interactive GUI sessions were not available in this environment. The TUI and
web scenarios below were exercised through the automated scenario suites that
drive the same widgets/routes, plus direct CLI and service runs. Every result
matched the quickstart expectations.

## Automated scenario coverage

| Scenario | Evidence | Result |
|----------|----------|--------|
| T1, T3 — undo one pick; only the latest of two | `tests/test_tui.py::TuiUndoScenarioTest` | Pass |
| T2 — second undo removes nothing | Same class; byte comparison | Pass |
| T4 — dry run/failed/empty/exhausted/filtered clear undo | `test_undo_starts_disabled_and_stays_disabled_after_a_dry_run`, `test_non_picked_outcomes_keep_undo_unavailable` | Pass |
| T5 — path/log changes clear undo | `test_folder_and_log_changes_clear_undo_availability` | Pass |
| T6 — external append/delete refuses safely | `test_undo_conflict_and_missing_history_name_the_item` | Pass |
| T7 — restart clears availability | Fresh app starts disabled (`test_undo_starts_disabled...`) | Pass |
| T8 — target tree untouched | Tree snapshot assertions in the T1 test and `test_undo_changes_only_the_history_log` | Pass |
| W1, W3, W4, W7 — web undo states and conflicts | `tests/test_web.py::WebApiTest` undo tests | Pass |
| W2 — keyboard focus and item-bearing name | `tests/test_tui.py` Tab/Enter test; `ChoiceBoard.test.ts` tab-stop/aria-label tests; `use-shortcuts.test.ts` Ctrl+Z test | Pass |
| W5 — page reload | Receipt is client-side only; fresh `useWorkspace` reports `canUndo === false` | Pass |
| W6 — two sessions | `test_two_sessions_share_only_the_latest_receipt` and `use-workspace` receipt tests | Pass |

## Direct command-line boundary

```text
uv run choosier --help                      exit 0, 24 lines, no "undo" mention
uv run choosier "$DEMO" --seed 7 --dry-run  exit 0: "The choice: delta" / "Dry run: selection not logged."
uv run choosier "$DEMO" --list              exit 0: alpha.txt, beta.txt, delta, gamma.txt
```

## Target-tree hash comparison

A disposable folder (`alpha.txt`, `beta.txt`, `gamma.txt`, `delta/`) was
hashed before and after a service-level pick/undo. `diff -u` reported no
differences. Afterwards the folder contained the same entries plus
`.choosier.jsonl` and `.choosier.jsonl.lock` only.

## One-second feedback at the rotation limit

With a 995,015-byte log (just below the 1,000,000-byte rotation limit), a pick
produced a receipt and the verified undo completed in **0.0029 s**. The undo
removed exactly the appended line and left the remaining 994,950 bytes intact.
