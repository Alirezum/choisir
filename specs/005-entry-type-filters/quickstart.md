# Quickstart: File-Type and Entry Filters

**Feature**: `005-entry-type-filters` | **Date**: 2026-11-05

This guide validates the feature end to end after implementation. It does not
contain implementation code; the contracts and data model define the behavior.

## 1. Setup

```sh
uv sync --group dev --extra ui --extra web
cd frontend
npm ci
npm run generate:api
npm run build
cd ..
```

`npm run build` writes the bundle used by the static-serving tests and by
`choosier --web`. For frontend development, run `npm run dev` in `frontend/`
and `uv run choosier --web <folder>` in another terminal; Vite proxies `/api`.

Create a reproducible fixture:

```sh
rm -rf /tmp/filter-demo
mkdir -p /tmp/filter-demo/sub
: > /tmp/filter-demo/a.jpg
: > /tmp/filter-demo/B.JPG
: > /tmp/filter-demo/notes.txt
: > /tmp/filter-demo/README
: > /tmp/filter-demo/.hidden
rm -f /tmp/filter-demo/.choosier.jsonl
```

Do not create `.choosier.jsonl` manually; the first logged pick creates it.
The reset keeps the expected counts reproducible when re-running this guide.

## 2. Type filtering in the TUI

1. Run:

   ```sh
   uv run choosier --ui /tmp/filter-demo
   ```

2. Open the **Options** tab. Confirm the type list contains:
   - `Folders (1)`
   - `.jpg files (2)`
   - `.txt files (1)`
   - `Files without an extension (1)`

   `.hidden` and the managed log are absent because hidden files are excluded
   and the log is managed. Every type starts checked; the summary says
   `all 4 types checked; 5 of 5 entries eligible`.
3. Select **Clear types**, then check only `.jpg files`. Confirm:
   - the summary reports `1 of 4 types checked; 2 of 5 entries eligible`;
   - the Remaining tab shows `B.JPG` and `a.jpg` only;
   - the remaining count is 2.
4. Set the seed to `42`, enable **Dry run**, and pick twice. Confirm both picks
   are from `.jpg` files and that the same seed returns the same item both
   times (dry run does not change history). Section 7 verifies the sequence
   through the API.
5. Disable **Dry run**, pick both `.jpg` entries so they enter history, then
   pick again. Confirm the message reports that all entries matching the
   filters have been selected, not that the folder is empty and not that all
   folder entries are gone. Confirm the summary now reports
   `1 of 4 types checked; 0 of 5 entries eligible`, because the summary uses
   the server's history-subtracted total.
6. Select **Clear filters**. Confirm the remaining list and count return to the
   full unfiltered pool, minus any logged entries, and the summary reports
   `3 of 5 entries eligible` for the two logged `.jpg` entries. Confirm history
   was not changed by filtering.

Expected: type filtering is exact, case-insensitive (`.JPG` and `.jpg` share
one type), keyboard-operable, and history-safe.

## 3. Individual entry filtering in the TUI

1. Clear filters, then uncheck `notes.txt` in the entry list.
2. Pick repeatedly (dry run or with history) and confirm `notes.txt` is never
   chosen and does not appear in Remaining.
3. Re-check `notes.txt` and confirm it returns when it is not in history.
4. Uncheck one `.jpg` entry while `.jpg files` remains checked, then pick
   repeatedly. Confirm the unchecked entry stays excluded and the other `.jpg`
   remains eligible: type and entry filters combine by intersection.
5. Use **Select all entries** and **Clear selection**. Confirm every *visible*
   entry is affected and the summary updates.

## 4. Filtered-empty and filtered-exhausted outcomes

Start the built web app in one terminal and use the API for exact status
checks:

```sh
rm -f /tmp/filter-demo/.choosier.jsonl
uv run choosier --web /tmp/filter-demo --port 8765
```

In another terminal:

```sh
BASE=http://127.0.0.1:8765
curl -s -X POST "$BASE/api/state" \
  -H 'Content-Type: application/json' \
  -d '{"path":"/tmp/filter-demo"}'
```

Confirm:

- The response includes `filter_options.types` with the four types above.
- `filter_options.entries` is sorted by exact name and contains five entries.
- `filter_options.entries_total` is 5 and `entries_truncated` is false.
- `known_entry_exclusions` is empty because the request sent no exclusions.
- `remaining_total` is 5.
- `GET /api/state?path=/tmp/filter-demo` still returns the old shape without
  `filter_options` or `known_entry_exclusions`.

Check reconciliation:

```sh
curl -s -X POST "$BASE/api/state" \
  -H 'Content-Type: application/json' \
  -d '{"path":"/tmp/filter-demo","excluded_entries":["notes.txt","already-gone.txt"]}'
```

Expected: `known_entry_exclusions` is exactly `["notes.txt"]`, so the client
prunes `already-gone.txt` while preserving `notes.txt`. On a folder with more
than 1,000 entries, an exclusion for an entry outside `filter_options.entries`
must still appear in `known_entry_exclusions`; the browser/TUI must not drop it.

Exclude everything:

```sh
curl -s -X POST "$BASE/api/pick" \
  -H 'Content-Type: application/json' \
  -d '{
    "path":"/tmp/filter-demo",
    "excluded_types":["dir","file:.jpg","file:.txt","file:"],
    "dry_run":true
  }'
```

Expected: `"status":"filtered_empty"`, `item: null`, `logged: false`, and no
new line in `/tmp/filter-demo/.choosier.jsonl`.

Filter to one type and exhaust it:

```sh
# Pick both .jpg entries with history enabled, then pick again.
curl -s -X POST "$BASE/api/pick" \
  -H 'Content-Type: application/json' \
  -d '{"path":"/tmp/filter-demo","excluded_types":["dir","file:.txt","file:"],"seed":1}'
# Repeat once, then:
curl -s -X POST "$BASE/api/pick" \
  -H 'Content-Type: application/json' \
  -d '{"path":"/tmp/filter-demo","excluded_types":["dir","file:.txt","file:"],"seed":1}'
```

Expected final `"status"` is `filtered_exhausted`, not `exhausted` and not
`empty`. Confirm the two `.jpg` history lines exist and no other entries were
removed.

Also verify the preserved existing behavior:

- A truly empty folder returns `empty`.
- A folder whose only child is hidden, with `include_hidden: false`, returns
  `exhausted` (today's behavior).
- With no exclusions and all entries logged, the status is `exhausted`.

## 5. Reset and scope behavior in the web UI

1. Keep the web app from Section 4 running, or start it again with the same
   command.
2. Open `http://127.0.0.1:8765`, go to **Options**, and apply a type and an
   entry exclusion. Confirm the summary shows the active counts and **Clear
   filters** is enabled.
3. Change the folder path to a second prepared folder. Confirm:
   - the filter summary resets to all options checked;
   - the previous folder's exclusions do not carry over;
   - the web UI clears the current choice on a path change, matching existing
     behavior.
4. Change the log file path. Confirm filters reset while the current choice is
   preserved, matching today's log-change behavior.
5. Restart the app. Confirm filters start fully checked.
6. With a filter active, change **Include hidden** or **Mode**. Confirm the
   type/entry lists are recalculated, options that still exist keep their
   checked state, and newly appearing options start checked.
7. Clear filters and confirm the current choice/preview are preserved until a
   new pick, folder change, or log change; history is unchanged.
8. Enter an invalid path and confirm the filter area says
   `Choose a valid folder to see filter options.` rather than
   `No eligible entries to filter.`
9. In the TUI, repeat the scope checks: changing the path or log resets the
   filters; the current choice is preserved in both cases, matching existing
   TUI behavior. The web UI continues to clear the choice on a path change and
   preserve it on a log change.

## 6. Bounded large-folder check

Create a large fixture with 5,000 entries across 200 distinct suffixes:

```sh
rm -rf /tmp/filter-large
mkdir -p /tmp/filter-large
python - <<'PY'
from pathlib import Path
root = Path('/tmp/filter-large')
for index in range(5000):
    suffix = index % 200
    (root / f'item{index:04d}.type{suffix:03d}').touch()
PY
```

Query state and time it:

```sh
time curl -s -X POST "$BASE/api/state" \
  -H 'Content-Type: application/json' \
  -d '{"path":"/tmp/filter-large"}' > /tmp/filter-large-state.json
python - <<'PY'
import json
state = json.load(open('/tmp/filter-large-state.json'))
print(state['filter_options']['entries_total'])
print(len(state['filter_options']['entries']))
print(state['filter_options']['entries_truncated'])
print(len(state['filter_options']['types']))
PY
```

Expected: `5000`, `1000`, `True`, `200`. The web/TUI entry list shows the
truncation notice, select-all/clear affect the visible 1,000, and the complete
type list is scrollable. Excluding `file:.type000` removes its 25 entries from
the pool; excluding all 200 type keys removes all 5,000. The interface remains
responsive and the state request completes within the two-second target on the
development machine.

## 7. Seeded determinism through the API

With a clean history or `dry_run: true`, send the same body twice:

```sh
BODY='{"path":"/tmp/filter-demo","excluded_types":["file:.txt","file:"],"seed":7,"dry_run":true}'
curl -s -X POST "$BASE/api/pick" -H 'Content-Type: application/json' -d "$BODY"
curl -s -X POST "$BASE/api/pick" -H 'Content-Type: application/json' -d "$BODY"
```

Expected: both responses have the same `item`, and neither writes history.

Now run the 100-pick checks required by SC-001 and SC-004. This resets history
first and uses dry runs, so every iteration starts from the same pool:

```sh
rm -f /tmp/filter-demo/.choosier.jsonl
python - <<'PY'
import json
import urllib.request

BASE = "http://127.0.0.1:8765"


def post(path, body):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


for seed in range(100):
    result = post(
        "/api/pick",
        {
            "path": "/tmp/filter-demo",
            "excluded_types": ["dir", "file:.txt", "file:"],
            "seed": seed,
            "dry_run": True,
        },
    )
    assert result["status"] == "picked", result
    assert result["item"].lower().endswith(".jpg"), result

for seed in range(100):
    result = post(
        "/api/pick",
        {
            "path": "/tmp/filter-demo",
            "excluded_entries": ["notes.txt", "README", "sub"],
            "seed": seed,
            "dry_run": True,
        },
    )
    assert result["status"] == "picked", result
    assert result["item"] in {"a.jpg", "B.JPG"}, result

print("100 type-filtered and 100 entry-filtered picks passed")
PY
```

Expected: the script prints the success line, and neither loop writes history.

## 8. Automated validation

Run the focused tests first:

```sh
uv run pytest \
  tests/test_filters.py \
  tests/test_chooser.py \
  tests/test_services_state.py \
  tests/test_services_pick.py \
  tests/test_services_boundaries.py \
  tests/test_api_contract.py \
  tests/test_api_errors.py \
  tests/test_web.py \
  tests/test_tui.py
```

Then the full Python gate:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy choosier main.py tests
```

Then the frontend gate:

```sh
cd frontend
npm run generate:api
npm run check:api
npm run test:api
npm run check:ui
npm run test:ui
npm run build
```

Re-run `uv run pytest` after the frontend build because the static-serving
tests need the bundle.

Expected results:

- All Python tests pass, including the existing 144 core tests and new filter
  coverage.
- `ruff` and `mypy` report no issues.
- The generated contract is current and the route/operation inventory is 13.
- `check:ui` finds a test for `src/state/use-filters.ts` and every new view
  behavior.
- The frontend build succeeds.

## 9. Acceptance mapping

| Success criterion | Validation |
|---|---|
| SC-001 / SC-010 | Section 2 seeded type picks; Section 7 100-pick type loop and API determinism |
| SC-002 | Sections 5 and 6; state/summary updates after options/filters |
| SC-003 | Section 2: clear types, check one type, one Clear filters action |
| SC-004 | Section 3 repeated entry-excluded picks; Section 7 100-pick entry loop |
| SC-005 | Sections 2–4 compare history/file contents before and after |
| SC-006 | Section 4 filtered-empty and filtered-exhausted messages/actions |
| SC-007 | Section 8 full existing suite plus Section 5 reset checks |
| SC-008 | Section 6 5,000-entry/200-type timing, truncation notice, complete type list |
| SC-009 | Keyboard pass through both Options panels in Sections 2–5 |

## 10. Documentation check

Before closing the feature, confirm:

- `README.md` describes the filter menu and the 13-route contract.
- `CHANGELOG.md` has an entry for the new filter capability and additive API.
- `specs/001-standardize-api-responses/contracts/api-contract.json` and
  `api-contract.md` document `POST /api/state`, the filter schemas, the pick
  fields, and the new statuses.
- `frontend/src/api-contract.generated.ts` is regenerated and committed.
- No new runtime dependency was added; the core remains standard-library-only.
