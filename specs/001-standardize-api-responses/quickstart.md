# Quickstart Validation: Standardize API Responses and Error Schemas

**Feature**: `001-standardize-api-responses`
**Date**: 2026-10-29

This guide proves the standardized error envelope and the unchanged success
contract end-to-end. It does not restate implementation details; see
[plan.md](./plan.md), [data-model.md](./data-model.md), and
[contracts/api-contract.md](./contracts/api-contract.md).

## Prerequisites

- Python 3.12 and `uv`
- Node.js 22 and npm (for the frontend build)
- A POSIX-like shell; the commands also work from Git Bash on Windows

Install the same dependency set CI uses:

```sh
uv sync --group dev --extra ui --extra web
```

## 1. Run the contract and regression tests

```sh
uv run pytest tests/test_api_contract.py -v
uv run pytest -q
```

Expected:

- The contract file and the live app expose the same 12 `(method, path)`
  pairs.
- Every JSON success schema matches FastAPI's OpenAPI schema.
- Every documented error code maps to its documented status.
- Seeded drift assertions fail as expected when a field is removed or retyped.
- The existing web API suite still passes.

## 2. Run the full quality gate

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy choosier main.py tests
```

Expected: all three commands exit 0.

## 3. Build the frontend

```sh
cd frontend
npm ci
npm run build
cd ..
```

Expected: the Vue build succeeds and writes the bundle to
`choosier/web_static/`. No frontend source file changes are required for this
feature.

## 4. Start the server

```sh
mkdir -p /tmp/choosier-api-demo
printf 'hello\n' > /tmp/choosier-api-demo/note.txt
printf 'pick me\n' > /tmp/choosier-api-demo/other.txt
uv run choosier --web /tmp/choosier-api-demo --port 8765
```

Open <http://127.0.0.1:8765> to confirm the UI loads.

## 5. Check a success response

```sh
curl -s http://127.0.0.1:8765/api/defaults | python -m json.tool
curl -s 'http://127.0.0.1:8765/api/state?path=/tmp/choosier-api-demo' \
  | python -m json.tool
```

Expected: the existing fields are all present with the same names and types;
no wrapper or renamed field appears.

Example state shape:

```json
{
  "valid_path": true,
  "path": "/tmp/choosier-api-demo",
  "log_file": "/tmp/choosier-api-demo/.choosier.jsonl",
  "remaining": ["note.txt", "other.txt"],
  "remaining_total": 2,
  "history": [],
  "history_total": 0
}
```

## 6. Check framework-generated errors

```sh
curl -s -i http://127.0.0.1:8765/api/nope
curl -s -i -X POST http://127.0.0.1:8765/api/defaults
curl -s -i 'http://127.0.0.1:8765/api/state'
```

Expected for each: HTTP 404, 405, or 422 with
`Content-Type: application/json` and the envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not Found",
    "details": null
  },
  "detail": "Not Found"
}
```

The 405 response keeps the `Allow` header. The 422 response has a string
`detail`, and `error.details.issues` contains the field-level validation
items.

## 7. Check route errors

```sh
curl -s -i 'http://127.0.0.1:8765/api/browse?path=/definitely/not/here'
curl -s -i 'http://127.0.0.1:8765/api/state?path=/tmp/choosier-api-demo&files_only=true&dirs_only=true'
curl -s -i 'http://127.0.0.1:8765/api/image?path=/definitely/not/here.png'
curl -s -i 'http://127.0.0.1:8765/api/video?path=/definitely/not/here.mp4'
```

Expected codes and statuses:

| Request | Code | Status |
|---------|------|--------|
| Missing browse directory | `not_found` | 404 |
| Conflicting filters | `invalid_request` | 400 |
| Missing image | `not_found` | 404 |
| Missing video | `not_found` | 404 |

Every response has a non-empty `detail` equal to `error.message`.

## 8. Check binary success and binary failures

Copy a real image (`.png`, `.jpg`, `.gif`, `.webp`, or `.bmp`) and a supported
video (`.mp4`, `.webm`, `.mov`, `.mkv`, `.ogv`, or `.m4v`) into the demo
directory, then adjust the paths below:

```sh
curl -s -D - -o /tmp/choosier-image.bin \
  'http://127.0.0.1:8765/api/image?path=/tmp/choosier-api-demo/photo.png'
curl -s -D - -o /tmp/choosier-thumb.bin \
  'http://127.0.0.1:8765/api/image?path=/tmp/choosier-api-demo/photo.png&variant=thumb'

curl -s -D - -o /tmp/choosier-video.bin \
  'http://127.0.0.1:8765/api/video?path=/tmp/choosier-api-demo/clip.mp4'
curl -s -D - -o /tmp/choosier-range.bin -H 'Range: bytes=0-3' \
  'http://127.0.0.1:8765/api/video?path=/tmp/choosier-api-demo/clip.mp4'
curl -s -i -H 'Range: bytes=999999-' \
  'http://127.0.0.1:8765/api/video?path=/tmp/choosier-api-demo/clip.mp4'
curl -s -i -H 'Range: garbage' \
  'http://127.0.0.1:8765/api/video?path=/tmp/choosier-api-demo/clip.mp4'

# A non-image and a missing file must fail with the JSON envelope.
curl -s -i \
  'http://127.0.0.1:8765/api/image?path=/tmp/choosier-api-demo/note.txt'
curl -s -i \
  'http://127.0.0.1:8765/api/video?path=/tmp/choosier-api-demo/gone.mp4'
```

Expected:

- A supported image returns image bytes with the original MIME type and
  `X-Content-Type-Options: nosniff`.
- `variant=thumb` returns `image/webp`.
- A supported video returns 200 (full), 206 (range) with
  `Accept-Ranges: bytes`, and the correct `Content-Range`.
- An unsatisfiable range returns 416 with a JSON envelope and
  `Content-Range: bytes */<size>`.
- A malformed range returns 400 with a JSON envelope.
- A non-image returns 415 JSON and a missing video returns 404 JSON, not an
  HTML or plain-text error.

## 9. Frontend smoke test

In the browser:

1. Pick an item; confirm it lands on the board and previews.
2. Open the item; confirm the OS default program launches.
3. Browse into a directory and back out.
4. Archive the history, then clear it with confirmation.
5. Pick again, then delete one history row and a highlighted batch.
6. Enter a missing directory in the browser path; confirm the error message
   appears in the panel's error text.
7. Trigger a conflicting filter through the UI if available; confirm a
   readable message appears.

Expected: every flow behaves as before, and no error shows a raw status line
when a JSON `detail` is available.

## 10. Domain outcomes remain successful

```sh
curl -s 'http://127.0.0.1:8765/api/state?path=/definitely/not/here' \
  | python -m json.tool
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"path": "/definitely/not/here"}' \
  http://127.0.0.1:8765/api/pick | python -m json.tool
```

Expected: HTTP 200 with `valid_path: false` or `status: "invalid_path"`,
respectively. These are domain outcomes, not errors.

Similarly, archive/clear/remove on a missing log return 200 with
`backup: null`, `removed: false`, or `removed: 0`.

## 11. Demonstrate drift detection (optional)

The contract tests include seeded-drift cases. To see the failure mode from the
outside, temporarily remove a field from a success model or from
`contracts/api-contract.json` and run:

```sh
uv run pytest tests/test_api_contract.py -q
```

Expected: the suite fails, naming the route and the missing/renamed/retyped
field. Revert the temporary change afterward.

## Done When

- [ ] Contract tests pass and cover all 12 `/api` routes
- [ ] Existing web tests pass unchanged
- [ ] Ruff lint/format and strict mypy pass
- [ ] Frontend production build passes with no source changes
- [ ] Every sampled error uses the JSON envelope with a string `detail`
- [ ] Domain outcomes still return 200 with their existing shapes
- [ ] Binary image/video success and range behavior are unchanged
- [ ] Frontend smoke flows all work
