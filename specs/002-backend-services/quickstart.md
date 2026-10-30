# Quickstart: Backend Service Extraction and Unified Data Access

**Feature**: `specs/002-backend-services`
**Date**: 2026-10-30

Use this guide to validate the refactor end to end. It assumes the service
boundaries in [contracts/service-boundaries.md](./contracts/service-boundaries.md)
and the entities in [data-model.md](./data-model.md) are implemented. The
refactor must not change any public behavior.

## Prerequisites

- Python 3.12 and `uv`.
- Node.js 22 and npm for the frontend build and static-serving tests.
- Linux, macOS, or Windows. Web commands below use a POSIX shell; adapt paths
  for other shells.
- No database, network service, browser automation, or running TUI is needed
  for the automated checks.

Install the same extras CI uses:

```bash
uv sync --group dev --extra ui --extra web
```

Build the frontend before running the full Python suite because static-serving
tests need `choosier/web_static/`:

```bash
(
  cd frontend
  npm ci
  npm run build
)
```

## 1. Full Quality Gate

Run the authoritative CI commands from the repository root:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy choosier main.py tests
uv build
```

Expected results:

- Ruff lint and format checks pass with no edits.
- The full pytest suite passes, including every pre-existing behavior test.
- Strict mypy passes for `choosier`, `main.py`, and `tests`.
- `uv build` produces both the sdist and wheel.

Confirm the wheel contains the new subpackage:

```bash
uv run python -m zipfile -l dist/choosier-*.whl | grep 'choosier/services/'
```

Expected: archive entries for `choosier/services/__init__.py`,
`browse.py`, `errors.py`, `history.py`, `models.py`, `opening.py`, `pick.py`,
and `state.py`.

## 2. Direct Service Tests

The extracted rules must be testable without a server or terminal:

```bash
time uv run pytest tests/test_services_*.py -q
```

Expected:

- All direct service tests pass.
- No test starts a web server, TUI session, browser, or network listener.
- The subset completes in under 10 seconds on the development machine
  (`SC-009`).

Coverage must include:

| Service | Success and failure cases |
| --- | --- |
| Browse | directories-first ordering, parent at root, missing target, permission failure |
| State | invalid path, conflicting filters, hidden/type filters, managed-file exclusion, totals, 200 cap, no-cap shape, malformed history |
| Pick | seeded repeatability, dry-run, `commit=False`, empty vs exhausted, invalid path, conflicting filters, write failure, optional preview |
| Opening | success, missing entry, launcher failure |
| History | snapshot derivation, tolerant/strict reads, append, remove, batch remove, archive, clear, duplicates, missing file, failure messages |

## 3. History Scenario Across Interfaces

Create a disposable target with current, legacy, blank, malformed, and plain
history lines:

```bash
tmp="${TMPDIR:-/tmp}/choosier-002-check"
rm -rf "$tmp"
mkdir -p "$tmp/target/sub"
touch "$tmp/target/a" "$tmp/target/b"
log="$tmp/target/.choosier.jsonl"
cat >"$log" <<'EOF'
{"ts": "2026-01-01T00:00:00+00:00", "item": "a"}
2026-01-02T00:00:00+00:00 - b
{"ts": 1}

plain-name
EOF
```

Expected structured contents:

- `a` with a timestamp and display `"2026-01-01T00:00:00+00:00  a"`.
- `b` from the legacy line, display equal to the original stripped line.
- `plain-name` from the plain line, display equal to the original line.
- The `{"ts": 1}` line and the blank line are ignored.
- Logged items are `{"a", "b", "plain-name"}`.
- Remaining candidates are `sub` only; the history file is never a candidate.

CLI check:

```bash
uv run choosier --list "$tmp/target"
```

Expected output:

```text
sub
```

Exit status must be `0`. Then verify empty versus exhausted with a fresh target:

```bash
empty="$tmp/empty"
mkdir -p "$empty"
uv run choosier --list "$empty"; echo "exit=$?"
```

Expected: `Path Empty.` and `exit=3`.

```bash
spent="$tmp/spent"
mkdir -p "$spent"
touch "$spent/only"
printf '{"ts": "2026-01-01T00:00:00+00:00", "item": "only"}\n' >"$spent/.choosier.jsonl"
uv run choosier --list "$spent"; echo "exit=$?"
```

Expected: `All choices have been selected. Delete log to reset.` and `exit=4`.

Start the web UI in a second terminal. Set the same disposable path there:

```bash
tmp="${TMPDIR:-/tmp}/choosier-002-check"
uv run choosier --web --port 8765 "$tmp/target"
```

Read the same state through the API:

```bash
curl -sG http://127.0.0.1:8765/api/state \
  --data-urlencode "path=$tmp/target" \
  | python -m json.tool
```

Expected:

- `valid_path` is `true`.
- `remaining` is `["sub"]`, `remaining_total` is `1`.
- `history_total` is `3`.
- `history` contains the three valid entries with the same items and display
  text as the CLI result.
- `log_file` is `$tmp/target/.choosier.jsonl`.

Browse:

```bash
curl -sG http://127.0.0.1:8765/api/browse \
  --data-urlencode "path=$tmp/target" \
  | python -m json.tool
```

Expected: `sub` (directory) appears before `a` and `b`; the hidden history file
is included by browse because browse is a directory listing, not a picker
candidate list.

Seeded dry-run pick:

```bash
for run in 1 2; do
  curl -s -X POST http://127.0.0.1:8765/api/pick \
    -H 'Content-Type: application/json' \
    -d "{\"path\":\"$tmp/target\",\"seed\":7,\"dry_run\":true}"
  echo
done
```

Expected: both responses have the same `status` and `item`, and `logged` is
`false`. The history file must be byte-for-byte unchanged.

Cross-interface mutations:

```bash
uv run choosier --reset "$tmp/target"; echo "exit=$?"
```

Expected: `Removed <log>.` and `exit=0`. The web state for the same target now
reports zero history and `a`, `b`, and `sub` as remaining.

With the web server still running, seed a fresh log, then archive through the
API:

```bash
printf '{"ts": "2026-01-01T00:00:00+00:00", "item": "a"}\n' >"$log"
curl -s -X POST "http://127.0.0.1:8765/api/history/archive?path=$tmp/target" \
  | python -m json.tool
```

Expected: `backup` is a timestamped `.old` filename and the active log is gone.
`/api/history/archive` again must return `backup: null`; it is not an error.

TUI manual check (optional but recommended for `SC-007`):

```bash
uv run choosier --ui "$tmp/target"
```

Pick once and confirm the selected item moves from Remaining to History with
`"Logged in <log_path>."`. Clear with confirmation and confirm
`"Removed <log_path>."`. Pick again, archive, and confirm
`"Archived to <backup>."`. Remaining/History should show at most the last 200
lines in each panel.

## 4. Web Smoke Checks

With the server running:

```bash
curl -s http://127.0.0.1:8765/api/defaults | python -m json.tool
```

Expected: `path` and `log_file` echo the values used to launch the server.

Error envelope and missing browse target:

```bash
curl -sG http://127.0.0.1:8765/api/browse \
  --data-urlencode "path=$tmp/target/missing" \
  | python -m json.tool
```

Expected: HTTP 404 with:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not a directory",
    "details": null
  },
  "detail": "Not a directory"
}
```

Conflicting filters:

```bash
curl -sG http://127.0.0.1:8765/api/state \
  --data-urlencode "path=$tmp/target" \
  --data-urlencode "files_only=true" \
  --data-urlencode "dirs_only=true" \
  | python -m json.tool
```

Expected: HTTP 400, `error.code == "invalid_request"`, message
`"files_only and dirs_only are mutually exclusive"`.

Create and serve a real image:

```bash
uv run python -c "
from PIL import Image
Image.new('RGB', (32, 24), (10, 80, 160)).save('$tmp/target/pic.png')
"
curl -sG http://127.0.0.1:8765/api/image \
  --data-urlencode "path=$tmp/target/pic.png" \
  -o "$tmp/out.png"
file "$tmp/out.png"
```

Expected: `file` reports PNG image data. Request
`/api/image?path=...&variant=thumb` and confirm a WebP response with
`Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

Video preview and range behavior are covered by
`tests/test_web.py`, `tests/test_api_compat.py`, and
`tests/test_api_errors.py`; no real codec is required.

Stop the server after the checks.

## 5. Source-Boundary Checks

The core service package must stay interface-independent:

```bash
if rg -n \
  'fastapi|starlette|uvicorn|pydantic|textual|rich|PIL|choosier\.web|choosier\.tui|choosier\.web_media|choosier\.cli' \
  choosier/services; then
  echo "service boundary violation"
  exit 1
else
  echo "service boundary OK"
fi
```

Adapters must not mutate history or parse it directly:

```bash
if rg -n \
  'storage\.(log_selection|remove_log_item|remove_log_items|archive_log|reset_log)|read_log_entries|parse_log_line' \
  choosier/cli.py choosier/tui.py choosier/web.py; then
  echo "adapter bypasses HistoryService"
  exit 1
else
  echo "history ownership OK"
fi
```

There must be exactly one history parser and one read primitive:

```bash
rg -n '^def (read_log_entries|parse_log_line)' choosier
```

Expected: one definition each in `choosier/storage.py`.

There must be exactly one application-layer history command facade:

```bash
rg -n '^class HistoryService' choosier
```

Expected: one definition in `choosier/services/history.py`.

Confirm the existing public compatibility exports still import:

```bash
uv run python -c "
from choosier import (
    archive_log, get_logged_items, get_unselected_item, launch_path,
    list_available_items, list_candidates, load_log, log_selection,
    parse_log_line, parse_seed, preview_entry, reset_log,
    resolve_default_log, resolve_log_path,
)
from main import get_logged_items as main_get, log_selection as main_log, main
print('compat exports OK')
"
```

## 6. Behavior and Contract Checks

Run the frozen-contract suites explicitly:

```bash
uv run pytest \
  tests/test_api_contract.py \
  tests/test_api_compat.py \
  tests/test_api_errors.py \
  tests/test_web.py \
  tests/test_cli.py \
  tests/test_tui.py \
  tests/test_chooser.py \
  tests/test_storage.py \
  tests/test_preview.py \
  tests/test_launcher.py \
  -q
```

Expected: all pass with unchanged assertions. Only imports and patch targets
listed in `contracts/service-boundaries.md` may differ.

Confirm the authoritative API contract was not edited:

```bash
git diff --exit-code 3ec1c7f -- \
  specs/001-standardize-api-responses/contracts/api-contract.json \
  specs/001-standardize-api-responses/contracts/api-contract.md
```

Expected: no diff.

Review the storage diff:

```bash
git diff 3ec1c7f -- choosier/storage.py
```

Expected: only the unified read primitive, the derived `load_log` /
`get_logged_items` wrappers, and the `ignore_errors` parameter change;
append/remove/archive/clear mechanics are untouched.

## 7. Documentation and Packaging

Review `README.md` for:

- The service-package boundary (`choosier/services/`).
- The statement that `choosier.storage` owns history I/O and
  `HistoryService` owns application-layer history reads/writes.
- The rule that core services are standard-library-only and web media is
  web-only.

Review `CHANGELOG.md` for a non-behavioral note describing the extraction.

Build a clean wheel and confirm runtime imports:

```bash
uv build
uv run python -c "
from choosier.services import HistoryService, build_state, browse_directory, pick, open_entry
from choosier.web_media import read_image, read_video
print('service imports OK')
"
```

Expected: imports succeed with the `web` extra installed. The source-boundary
check in section 5 proves that `choosier.services` itself has no UI, web, or
Pillow imports and therefore remains usable with only the base install.

## 8. Completion Checklist

- [ ] Full quality gate passes.
- [ ] Direct service subset passes in under 10 seconds.
- [ ] CLI, web, and TUI history scenario reports identical entries, totals,
      remaining candidates, removed counts, and archive results.
- [ ] Seeded dry-run picks are repeatable and do not write history.
- [ ] Every documented error still uses the existing envelope/status/message.
- [ ] Every documented success still uses the existing schema/headers.
- [ ] Source-boundary checks find no interface imports in `choosier/services`.
- [ ] Adapters do not parse or mutate history directly.
- [ ] Wheel contains `choosier/services/`.
- [ ] README and CHANGELOG identify the new boundaries.
