# choosier Constitution

## Core Principles

### I. Deterministic Selection
A pick MUST be reproducible from the target path, active filters, and seed
when a seed is supplied. Candidate ordering and tie-breaking MUST be stable.
History MUST prevent repeats until all eligible entries are exhausted.
Selection logic MUST live in one UI-agnostic implementation shared by the
CLI, TUI, and web UI.

Rationale: seeded results and predictable exhaustion are user-facing
promises; divergent interface logic would make them unexplainable.

### II. Local and Private by Default
The tool MUST NOT send user data over a network, collect telemetry, or
require an online service. The web UI MUST bind to loopback only. Launching
an external program MUST require an explicit user action. Any future
networked feature requires a constitutional amendment, not an implementation
detail.

Rationale: choosier inspects local filesystem entries, which may be
sensitive or private.

### III. User Data Is Inviolable
The tool MUST NOT modify, move, rename, or delete user-selected files or
directories. Persistent state MUST be limited to the history log and its
archives. History writes MUST be atomic. Clearing or batch-deleting history
MUST be confirmed; single-item removal MUST require an explicit row action.
Archives MUST preserve the prior log. Failures MUST leave the target and
existing history intact.

Rationale: a chooser must never risk the content it is choosing among.

### IV. Shared Core, Thin Interfaces
The core MUST remain UI-agnostic and standard-library-only. CLI, TUI, and
web MUST be adapters over shared storage, selection, preview, and launcher
helpers. UI-specific dependencies MUST remain optional extras. Adding a new
optional dependency requires justification; adding a core dependency
requires a constitutional amendment.

Rationale: three interfaces already exist; duplicated core logic is the main
maintenance risk.

### V. Verified, Boring Changes
Every behavior change MUST include tests. Bug fixes MUST include a
regression test. Python MUST pass the repository's test, lint, format, and
strict type-check gates; frontend changes MUST pass the production build.
Tests MUST remain runnable with the standard-library `unittest` runner.
User-visible changes MUST update `README.md` and `CHANGELOG.md`. Changes
SHOULD be the smallest reversible change that satisfies the requirement.

Rationale: the project is small; predictable quality gates matter more than
cleverness.

## Technical Constraints

- The Python core has no mandatory third-party runtime dependencies; `ui`
  and `web` are optional extras.
- History is JSON Lines, readable in its legacy timestamp-and-item format,
  and rotates to timestamped backups.
- The web server binds to `127.0.0.1` only; it is a local UI, not a shared
  service.
- Preview work MUST be bounded by explicit limits, MUST stream large
  payloads where practical, and MUST NOT extract archive members to disk.
- Interactive interfaces MUST remain keyboard-operable with visible focus
  and documented shortcuts.
- Public contracts — CLI flags and exit codes, the history format, and the
  HTTP API shape — change only with a documented migration or a MAJOR
  amendment.
- Generated frontend assets are built before packaging and CI; frontend
  source remains in `frontend/`.

## Development Workflow

- Make atomic commits: one logical, reviewable change per commit.
- Update `README.md` and `CHANGELOG.md` for user-visible behavior.
- Before committing, run the full quality gate: tests, lint, format check,
  strict type-check, and the frontend production build. CI defines the
  authoritative commands.
- Add or update tests for every behavior change; bug fixes include a
  regression test.
- A core change MUST be verified through every interface it affects.
- Preserve backward compatibility unless a migration is documented and
  approved.
- Review changes for privacy, data safety, resource bounds, and consistency
  across CLI, TUI, and web.

## Governance

This constitution supersedes conflicting development practices. Amendments
MUST include a documented rationale, a semantic version bump, and an updated
amendment date. MAJOR versions remove or redefine governance incompatibly;
MINOR versions add or materially expand principles; PATCH versions clarify
wording without changing meaning. Breaking changes to public contracts
require a migration note.

Every review MUST verify compliance; deviations require explicit
justification. The temporary Sync Impact Report MUST be removed before
committing the amended constitution.

## 5. Git & Commit Policy

- **Atomic Commits:** Each individual task from `tasks.md` must be committed separately upon completion and test verification.
- **Convention:** All commit messages must follow the Conventional Commits specification:
  - Format: `<type>(<scope>): <short description>`
  - Allowed types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`, `style`.
- **Validation:** Never commit code that fails existing test suites or linters.

**Version**: 1.1.0 | **Ratified**: 2026-10-29 | **Last Amended**: 2026-10-29
