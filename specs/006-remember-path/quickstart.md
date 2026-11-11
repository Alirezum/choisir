# Quickstart Validation: Remembered Folder Paths

**Feature**: 006-remember-path | **Date**: 2026-11-11

Runnable checks that prove the feature end-to-end. Use an isolated memory file
for every scenario so the developer's real memory is untouched:

```bash
export CHOOSIER_PATH_MEMORY_FILE=/tmp/choosier-path-memory.json
rm -f "$CHOOSIER_PATH_MEMORY_FILE" "$CHOOSIER_PATH_MEMORY_FILE.lock"
```

References: [spec.md](./spec.md), [data-model.md](./data-model.md),
[contracts/path-memory.md](./contracts/path-memory.md),
[contracts/web-paths.md](./contracts/web-paths.md).

## Prerequisites

```bash
cd /workspace/choosier
uv sync --group dev --extra ui --extra web
mkdir -p /tmp/choosier-demo/alpha /tmp/choosier-demo/beta /tmp/choosier-demo/gamma
printf 'one\n' > /tmp/choosier-demo/alpha/a.txt
printf 'two\n' > /tmp/choosier-demo/beta/b.txt
printf 'three\n' > /tmp/choosier-demo/gamma/c.txt
```

## 1. Automated Gates

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy choosier

cd frontend
npm ci
npm test
npm run build
npm run generate:api -- --check   # or the repository's documented check command
```

Expected: all Python tests (including the new path-memory, TUI, web, and
contract tests), frontend tests, contract drift check, and production build
pass.

## 2. First Run (no memory)

```bash
rm -f "$CHOOSIER_PATH_MEMORY_FILE" "$CHOOSIER_PATH_MEMORY_FILE.lock"
uv run choosier --ui
```

Expected:

- Path input is empty, exactly like today.
- No warning and no error dialog.
- Closing without a pick leaves no memory file.

Repeat with the web UI:

```bash
uv run choosier --web --port 8765
curl -s http://127.0.0.1:8765/api/defaults | python -m json.tool
```

Expected: `path` is the current working directory, `path_warning` is null, and
`GET /api/paths` returns `{"recent": [], "warning": null}`.

## 3. Record on a Successful Pick (TUI)

1. `uv run choosier --ui /tmp/choosier-demo/alpha`
2. Press **Pick** (or `ctrl+n`); confirm a file is shown.
3. Quit.
4. `uv run choosier --ui`

Expected:

- The TUI reopens with `/tmp/choosier-demo/alpha` in the path input.
- The memory file contains exactly that folder under `recent`.
- No item names appear in the memory file.

Repeat with **Dry run** enabled in Options: a dry-run pick must also update
memory, while `.choosier.jsonl` receives no new line.

## 4. Explicit Path Wins

```bash
uv run choosier --ui /tmp/choosier-demo/beta
```

Expected: beta is active even though alpha is remembered. Then:

```bash
uv run choosier --ui /tmp/choosier-demo/does-not-exist
```

Expected: the normal invalid-path outcome. The remembered alpha folder is not
silently substituted.

## 5. Recent Ordering, Deduplication, and Cap

Record picks in alpha, beta, gamma (each in a fresh session or from the Options
recent list), then inspect:

```bash
python -m json.tool "$CHOOSIER_PATH_MEMORY_FILE"
```

Expected order: `gamma, beta, alpha`. Pick again from alpha; order becomes
`alpha, gamma, beta` with no duplicate. Repeat with more than ten distinct
folders; the newest ten remain and the oldest are evicted.

## 6. Switch from the Recent List

**TUI**: open Options → Recent folders; use arrow keys to highlight beta;
activate **Use**. Expected: the path input becomes beta, the panels refresh,
and focus remains visible on the list. **Remove** deletes only the highlighted
entry. **Clear recent** empties the list.

**Web**: open Options → Recent folders; activate the beta row. Expected: the
topbar path becomes beta and the workspace refreshes. The row-level **Remove**
button removes only beta; **Clear recent folders** empties the list. All
controls are reachable and operable with Tab/Enter/Space and show a visible
focus ring.

After either action, verify the current path did not change when removing a
folder that is not active.

## 7. Stale Folder Fallback and Pruning

With memory ordered `gamma, beta, alpha`:

```bash
mv /tmp/choosier-demo/gamma /tmp/choosier-demo/gamma-moved
uv run choosier --web --port 8765
curl -s http://127.0.0.1:8765/api/defaults | python -m json.tool
curl -s http://127.0.0.1:8765/api/paths | python -m json.tool
```

Expected:

- Startup falls back to beta (next valid recent), with a non-blocking
  `path_warning`.
- The recent list no longer contains gamma.
- Restarting after that keeps beta at the top with no repeated warning.

Delete every remembered folder and relaunch: startup falls back to the normal
default (cwd for web, empty input for TUI) and remains usable.

## 8. API Contract Checks

With the web server running:

```bash
curl -s http://127.0.0.1:8765/api/paths
curl -s -X DELETE 'http://127.0.0.1:8765/api/paths/item?path=/tmp/choosier-demo/alpha'
curl -s -X DELETE http://127.0.0.1:8765/api/paths
```

Expected shapes match [contracts/web-paths.md](./contracts/web-paths.md):

- `GET /api/paths` → `{ "recent": [...], "warning": null }`
- `DELETE /api/paths/item?path=...` → `{ "path": "...", "removed": true|false }`
- `DELETE /api/paths` → `{ "cleared": true|false }`

Validation:

```bash
curl -s -o /tmp/out.json -w '%{http_code}\n' 'http://127.0.0.1:8765/api/paths/item'
curl -s -o /tmp/out.json -w '%{http_code}\n' 'http://127.0.0.1:8765/api/paths/item?path=relative'
```

Expected: `422` with `validation_error` for the missing parameter, `400` with
`invalid_request` for the relative path, both using the standard error
envelope.

A successful `POST /api/pick` in a valid folder returns `status: "picked"` and
`path_memory_notice: null`; the folder appears at the top of `GET /api/paths`.
A dry-run pick behaves the same for memory. An invalid path returns
`status: "invalid_path"` and does not change memory.

## 9. No Side Effects on History, Filters, or Target Content

```bash
sha256sum /tmp/choosier-demo/alpha/.choosier.jsonl > /tmp/log.before
find /tmp/choosier-demo -type f -exec sha256sum {} + | sort > /tmp/tree.before

# remove one and clear all from the UI or API, then:
sha256sum /tmp/choosier-demo/alpha/.choosier.jsonl > /tmp/log.after
find /tmp/choosier-demo -type f -exec sha256sum {} + | sort > /tmp/tree.after
diff /tmp/log.before /tmp/log.after
diff /tmp/tree.before /tmp/tree.after
```

Expected: no diffs. Active filters, the displayed choice, and the current path
are also unchanged by remove/clear.

## 10. Concurrent Sessions

Open the TUI and web UI against different recent folders, then perform
successful picks in both within a second or two. Then:

```bash
python -m json.tool "$CHOOSIER_PATH_MEMORY_FILE"
curl -s http://127.0.0.1:8765/api/paths
```

Expected: valid JSON, at most ten unique entries, no duplicates, and the most
recent successful pick at index 0. Repeat with clear/remove in one session while
the other picks; no corruption and no lost entries from successful writes.

## 11. Privacy and Storage Scope

```bash
python - <<'PY'
import json, os
path = os.environ["CHOOSIER_PATH_MEMORY_FILE"]
data = json.load(open(path, encoding="utf-8"))
print(data)
assert set(data) <= {"version", "recent"}
assert all(isinstance(item, str) for item in data["recent"])
PY
```

Expected: only `version` and `recent`; no file names, timestamps, history,
filters, choices, or machine identifiers. No network activity is required for
any scenario, and the web server still binds only to `127.0.0.1`.

## 12. One-Shot CLI Regression

```bash
uv run choosier --dry-run --seed 1 /tmp/choosier-demo/alpha
uv run choosier --list /tmp/choosier-demo/alpha
uv run choosier --reset /tmp/choosier-demo/alpha
```

Expected: output, flags, and exit codes are unchanged and do not consult or
update the path memory. `choosier --web` without a path prefers a remembered
folder but still falls back to cwd when memory is empty.

## Done Criteria

- Sections 1–12 pass on the reference machine.
- Both interactive interfaces restore, list, switch, remove, and clear paths.
- Stale entries never appear and startup never blocks.
- No test or manual check finds a change to history, filters, choices, target
  files, or folders caused by path memory.
