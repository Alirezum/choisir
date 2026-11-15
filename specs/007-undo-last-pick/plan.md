# Implementation Plan: Undo Last Pick

**Branch**: `007-undo-last-pick` | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-undo-last-pick/spec.md`

## Summary

Add a session-only **Undo last pick** action to the TUI and web UI. A successful
logged pick returns an in-memory receipt that identifies the exact history line
it appended. Undo verifies that the log still matches the bytes written after
that pick, removes only that final line with the existing atomic rewrite, and
refreshes history, remaining, choice, and preview. Verification and removal live
in the shared storage/history core; the interfaces only hold the receipt and
present the action. No command-line flag, history format, pick algorithm, or
target content changes.

## Technical Context

**Language/Version**: Python 3.12+ (core, TUI, web); TypeScript with Vue 3.5
(frontend).

**Primary Dependencies**: Python standard library only for the core and undo
logic. Existing optional extras only: `textual>=8` for the TUI and
`fastapi>=0.115` + `uvicorn[standard]>=0.30` + `pillow>=11` for the web UI.
Vue 3.5 + Vite for the frontend. No new dependency.

**Storage**: The existing JSONL history log (`{"ts": ..., "item": ...}` plus
legacy lines). No new persistent store, no format change, no migration. History
mutations are serialized with an advisory lock file beside the log so
append and undo cannot lose a concurrent entry. The receipt itself is held only
in process/browser memory.

**Testing**: `pytest`/`unittest` backend suites, FastAPI `TestClient` contract
and route tests, Textual `run_test` TUI tests, Vitest + Vue Test Utils frontend
tests, the generated API contract check, and the frontend production build.

**Target Platform**: Linux, macOS, and Windows terminals for the TUI; a
loopback-only local web UI (`127.0.0.1`) for the browser frontend.

**Project Type**: Single Python package (`choosier/`) with a Vue frontend
(`frontend/`), served as static assets by the web adapter.

**Performance Goals**: Undo feedback within one second for a history log at the
existing 1,000,000-byte rotation threshold. Pick latency gains are not allowed:
the added digest read is linear in an already-small log.

**Constraints**: Offline and local-only; stdlib-only core; atomic history
writes; no target file/folder access beyond removing one history line; additive
HTTP API change; one-shot CLI flags, output, prompts, and exit codes frozen;
single-level, session-only undo.

**Scale/Scope**: One local user, two interactive interfaces, at most one
undoable entry per running session, and history files bounded by the existing
rotation limit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Deterministic Selection — PASS.** Undo does not change scanning,
  filtering, ordering, seeding, or the pick algorithm. It only removes one
  history line, restoring eligibility under the existing history rules, and it
  lives in one UI-agnostic core path used by both interfaces.
- **II. Local and Private by Default — PASS.** No network access, telemetry, or
  online service is added. The receipt stays in memory and crosses only the
  existing loopback HTTP boundary. No file names, history, or choices are added
  to any user-scoped record.
- **III. User Data Is Inviolable — PASS.** Undo removes exactly one history
  entry, never target content, and uses the existing atomic temp-file + rename
  rewrite. It is an explicit, single-purpose action, not an implicit bulk
  deletion; it cannot target an arbitrary row, and the existing per-item and
  batch deletion controls remain separate. History is re-verified before any
  write, and failures leave it byte-for-byte intact.
- **IV. Shared Core, Thin Interfaces — PASS.** Receipt validation and removal
  live in `choosier/storage.py` and `choosier/services/history.py`. The TUI and
  web adapter only hold the receipt, call the service, and render messages.
- **V. Verified, Boring Changes — PASS.** Storage, service, API contract, TUI,
  and frontend behavior tests are part of the task breakdown. README and
  CHANGELOG are updated. The full existing quality gate must stay green.
- **VI. Intentional Frontend Design — PASS.** The `frontend-design` skill was
  loaded before any styling decision. Undo is a secondary control inside the
  existing split-flap board chrome, not a redesign; it inherits the established
  palette, type scale, focus ring, and disabled treatment.
- **Technical constraints — PASS.** The history format and CLI contract are
  unchanged. The HTTP change is additive: one new route, one new nullable
  response field, and new schemas; no existing field or status changes. The
  generated contract, OpenAPI schema tests, and changelog document it.

**Gate result**: no blocking violations. The one justified complexity addition
is tracked below.

**Post-design re-check (after research and Phase 1)**: **PASS.** The design keeps
selection, history format, CLI behavior, and persistent user data unchanged. The
new lock file is coordination metadata and is excluded from candidate scans. The
only public-contract change is the documented additive route/field. The frontend
control follows the loaded design skill and the existing visual language. No new
clarification marker or unjustified gate failure was introduced by the design.

## Project Structure

### Documentation (this feature)

```text
specs/007-undo-last-pick/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Receipt, undo state, and transitions
├── quickstart.md        # End-to-end validation guide
├── contracts/
│   └── undo-history.md  # Undo route and receipt contract
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Created by /speckit.tasks
```

### Source Code (repository root)

```text
choosier/
├── locking.py           # NEW: shared cross-process advisory lock
├── storage.py           # UndoReceipt, receipt creation, verified removal
├── chooser.py           # Exclude the lock file from candidates
├── services/
│   ├── models.py        # PickOutcome.undo, UndoOutcome, UndoStatus re-export
│   ├── history.py       # HistoryService.append receipt + undo operation
│   └── pick.py          # Return the receipt from logged picks
├── web.py               # POST /api/history/undo, PickResponse.undo
└── tui.py               # Undo button, receipt lifecycle, status feedback

frontend/
├── scripts/generate-api-contract.mjs   # Name the new response type
├── src/
│   ├── api-operations.ts               # undoHistory route key
│   ├── api.ts                          # undoHistory facade method
│   ├── api-contract.generated.ts       # Regenerated, not hand-edited
│   ├── types.ts                        # Undo request/response aliases
│   ├── view-models.ts                  # Undo binding surface
│   ├── state/
│   │   ├── use-undo.ts                 # NEW: receipt, availability, request
│   │   ├── use-picker.ts               # Store/clear receipt on pick
│   │   ├── use-history-actions.ts      # Clear after history mutation
│   │   └── use-workspace.ts            # Compose undo and reset wiring
│   ├── views/ChoiceBoard.vue           # Undo control beside Open
│   ├── App.vue                         # Wire the control and binding
│   └── styles.css                      # Secondary control styling
└── tests/ui/
    ├── state/use-undo.test.ts          # NEW
    ├── state/use-picker.test.ts
    ├── state/use-history-actions.test.ts
    ├── state/use-workspace.test.ts
    └── views/ChoiceBoard.test.ts

tests/
├── test_storage.py                     # Receipt, undo, conflicts, rotation
├── test_services_history.py            # Service statuses and I/O mapping
├── test_services_pick.py               # Receipt only for logged picks
├── test_chooser.py                     # Lock file is never a candidate
├── test_web.py                         # Route outcomes and conflict safety
├── test_api_contract.py                # 17 routes and schemas
├── test_api_errors.py                  # Error envelope and I/O failure
├── test_tui.py                         # Availability, labels, clearing
└── test_history_consistency.py         # CLI unchanged, web/service agree

specs/001-standardize-api-responses/contracts/
├── api-contract.json                   # Authoritative route contract
└── api-contract.md                     # Human-readable inventory
```

**Structure Decision**: Keep the existing single-package + frontend layout.
Undo follows the same layering as feature 006: storage owns the byte-level
operation, `HistoryService` owns service error mapping, and each interface is a
thin adapter over the shared result objects. The only new module is the generic
lock helper extracted from `path_memory.py`; adding it avoids duplicating
platform-specific locking in `storage.py`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Advisory lock file beside the history log (`<log>.lock`) | Undo is a compare-and-swap (verify digest, then rewrite). Without a cross-process lock, a concurrent append between verification and `os.replace` would be silently overwritten, violating FR-009. | Locking the log inode fails after the atomic rewrite swaps it; in-process locks do not cover a TUI, web server, and CLI running at once; a temp-directory lock can be cleaned by the OS and is harder to discover. The lock is coordination metadata only, contains no user data, and is excluded from candidate scans. |
| One additive HTTP route and one additive `PickResponse` field | The browser must hold the receipt so undo remains session-only, and the server must verify/remove the exact entry. | Server-global receipt state would make a pick in one tab or session undoable from another, violating the session boundary; re-deriving the target from the log would remove a substitute entry, violating FR-008. |
