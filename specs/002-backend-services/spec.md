# Feature Specification: Backend Service Extraction and Unified Data Access

**Feature Branch**: `refactor/02-backend-services`

**Created**: 2026-10-30

**Status**: Draft

**Input**: User description: "Extract inline route handler business logic into dedicated service modules and unify database access queries."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interface Behavior Unchanged After Extraction (Priority: P1)

A person using the web interface continues to browse folders, inspect the
picker state, pick entries, preview media, open entries, and manage history
exactly as before while the logic behind those actions moves out of the
request handlers. A person using the CLI or TUI sees the same output, exit
codes, ordering, and history outcomes as before.

**Why this priority**: The refactor has value only if it is invisible to
users. Any change in response shape, status, ordering, output, or history
outcome is a regression.

**Independent Test**: Replay the full set of documented web requests and
failure cases, plus representative CLI and TUI journeys, against the
refactored application and compare results with the pre-refactor baseline.

**Acceptance Scenarios**:

1. **Given** every documented web request and its valid input variants,
   **When** it is handled, **Then** the status, headers, and body match the
   baseline exactly.
2. **Given** invalid input, an invalid path, a missing entry, a conflicting
   filter, unsupported or oversized media, a malformed range, or a history
   write failure, **When** the request fails, **Then** the same error shape,
   code, message, status, and headers as the baseline are returned.
3. **Given** a seeded pick with and without dry-run, **When** it is requested
   repeatedly, **Then** the same item is selected, the same history line is
   written or skipped, and the same outcome is reported.
4. **Given** browse and state requests, **When** directories and history
   change, **Then** ordering, truncation, totals, and structured history
   remain identical.
5. **Given** representative CLI and TUI journeys, **When** they are replayed,
   **Then** output text, exit codes, ordering, selection results, and history
   changes match the baseline.

---

### User Story 2 - Thin Handlers over Shared Services (Priority: P2)

A maintainer can locate any web-exposed business operation in one shared,
interface-independent place and change it once, while request handlers only
translate input and outcomes.

**Why this priority**: Inline handler logic hides business rules, invites
duplication, and makes tests depend on the transport layer.

**Independent Test**: For each extracted operation, invoke the shared
operation directly without a web request and confirm it produces the same
decision; review the handler and confirm it contains only translation, one
service call, and outcome mapping.

**Acceptance Scenarios**:

1. **Given** a web-exposed operation with business rules, **When** a
   maintainer looks for its implementation, **Then** exactly one shared
   implementation exists and no handler contains a competing copy.
2. **Given** a shared operation, **When** it is called directly, **Then** it
   requires no web request, response, or UI object and returns an explicit
   outcome.
3. **Given** a rule change such as a panel cap, filter rule, media limit, or
   history behavior, **When** it is applied, **Then** it is changed in one
   production location and every interface receives it.
4. **Given** a shared operation that fails, **When** each adapter maps the
   failure, **Then** the interface-specific public contract is unchanged.
5. **Given** an operation that is purely transport-specific, **When** it
   remains in the adapter, **Then** it performs no selection, history, or
   media decision.
6. **Given** the repository documentation, **When** a maintainer reads it,
   **Then** the service boundaries and the single owner of history reads and
   writes are identified.

---

### User Story 3 - One History Data-Access Path for Every Interface (Priority: P3)

A maintainer can trust that the CLI, TUI, and web UI read and change history
through the same operations, so a fix or safety rule applies everywhere and
no interface can drift in how it parses or writes history.

**Why this priority**: Three interfaces already share one history file.
Duplicate reading and writing is the main risk to consistent exhaustion,
removal counts, and atomic updates.

**Independent Test**: Create a history containing current, legacy, blank, and
malformed lines; read it, pick from it, remove items, archive it, and clear it
through each interface; compare the resulting files and reported outcomes with
the shared operations' results.

**Acceptance Scenarios**:

1. **Given** one history file, **When** any interface reads it, **Then** all
   report the same structured entries, display text, logged items, and
   remaining candidates.
2. **Given** append, single removal, batch removal, archive, or clear,
   **When** it is performed through any interface, **Then** the on-disk
   result, removed count, retained lines, backup name, and visible outcome
   match.
3. **Given** duplicate entries, missing files, legacy lines, blank lines, or
   malformed lines, **When** history is read or mutated, **Then** every
   interface applies the same tolerance and counting rules.
4. **Given** a persistence failure, **When** a mutation cannot complete,
   **Then** the prior history remains intact and the interface reports its
   existing failure outcome.
5. **Given** an existing history or archive, **When** it is opened after the
   refactor, **Then** it remains readable with no migration and the file
   format and naming are unchanged.

---

### User Story 4 - Service Rules Testable Without an Interface (Priority: P4)

A contributor can verify selection, browsing, state assembly, media rules, and
history behavior directly, without launching a web server or an interactive
terminal.

**Why this priority**: Fast, focused tests make the extracted rules cheaper to
maintain and reduce the chance that a future interface change silently alters
behavior.

**Independent Test**: Run the direct service tests with no web server or TUI
session running and confirm they cover each operation's success and failure
outcomes.

**Acceptance Scenarios**:

1. **Given** the extracted operations, **When** direct tests run, **Then**
   every operation has coverage for its success path and each documented
   failure outcome.
2. **Given** a service test, **When** it runs, **Then** it does not require a
   web server, an interactive terminal, a network, or a browser.
3. **Given** a behavior that previously existed only in a route handler,
   **When** it is extracted, **Then** a direct test demonstrates the same
   decision without constructing a request.
4. **Given** the complete test suite, **When** it runs, **Then** all
   pre-existing behavior tests still pass and overall behavior coverage has
   not decreased.

---

### Edge Cases

- A target that is not a directory remains a successful domain outcome for
  state and pick requests, while browse and open continue to report their
  existing failures.
- An empty target reports "empty", while a target whose entries are all in
  history reports "exhausted"; the two must never be conflated.
- Supplying both files-only and directories-only is rejected by the web API as
  invalid input, while the CLI and TUI keep their current validation behavior.
- Hidden entries are included only when explicitly requested; the history file
  and all of its archived backups are never candidates, even when hidden
  entries are included.
- A blank or whitespace-only history override falls back to the default
  location, and path expansion behaves as before.
- History may be missing, empty, contain legacy timestamp-and-item lines,
  contain malformed or blank lines, or be a directory; reads and mutations
  must preserve their current tolerant or failing behavior.
- A history with more than the display cap reports the correct totals while
  showing the first capped remaining items and the most recent capped history
  entries.
- Duplicate history entries for one item are all removed by a single-item
  removal, and the reported removed count reflects every matching line.
- Removing a batch with no items is rejected at the web boundary and is a
  no-op in the shared history operation.
- Archiving when no history exists reports no backup; clearing when no history
  exists reports that nothing was removed; neither is an error.
- A history write failure, a failed atomic rewrite, or a crash mid-rewrite
  leaves the prior history intact; readers see either the old or the new
  complete file, never a partial one.
- History rotation at the size limit and archive name collisions keep their
  current naming and retention behavior.
- Unicode item names, timestamps, whitespace, and display text survive reads,
  writes, removals, and archive operations unchanged.
- Image preview rejects missing files, unsupported types, oversized payloads,
  undecodable data, non-archives, out-of-range or negative member indexes,
  directory members, non-image members, and encrypted members with their
  existing outcomes.
- Thumbnail and preview renditions keep their current size bounds, format,
  quality behavior, and failure outcome.
- Video preview rejects missing files, unsupported types, content that does
  not match its claimed type, and malformed or unsatisfiable ranges, while
  honoring an if-range that does not match.
- Opening a missing entry and a launcher failure keep their current failure
  outcomes.
- Concurrent requests may read history while a mutation replaces it, but no
  request may observe a partially written history.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST preserve every public behavior of the web API,
  CLI, and TUI, including response shapes, status codes, error codes and
  messages, headers, exit codes, output text, ordering, and history file
  formats.
- **FR-002**: Web request handlers MUST be limited to translating input,
  invoking shared service operations, and mapping outcomes and failures to
  their existing transport responses.
- **FR-003**: Every nontrivial business operation reachable from the web API
  MUST have exactly one shared implementation that is independent of the web
  framework.
- **FR-004**: Shared service operations MUST NOT depend on web request or
  response objects, UI widgets, or interface-specific error types.
- **FR-005**: Where behavior overlaps, the CLI, TUI, and web UI MUST use the
  same shared operations rather than reimplementing the rules locally.
- **FR-006**: All history reads MUST go through one read operation that
  produces structured entries; logged-item sets, display text, and remaining
  candidates MUST be derived from that result, and no adapter may parse the
  history format independently.
- **FR-007**: All history changes — append, single removal, batch removal,
  archive, and clear — MUST go through one history service; no adapter may
  open, write, rename, or delete the history file directly.
- **FR-008**: The history service MUST preserve the append format, atomic
  rewrite, verbatim retention of unaffected lines, rotation behavior, archive
  naming, and failure semantics.
- **FR-009**: Shared operations MUST report outcomes explicitly enough for
  each adapter to distinguish success, invalid input, empty target, exhausted
  candidates, missing entry, unsupported media, oversized payload,
  unsatisfiable range, and persistence failure without inspecting error text.
- **FR-010**: Adapters MUST map each shared outcome to the interface's
  existing public contract exactly, so users see no change in statuses, exit
  codes, messages, or visible state.
- **FR-011**: Selection semantics MUST remain unchanged: deterministic seeded
  choice, stable sorted ordering, hidden and type filtering, exclusion of
  managed history files, repeat prevention, and the empty-versus-exhausted
  distinction.
- **FR-012**: State assembly MUST preserve the current totals, ordering,
  remaining and history display caps, and structured history fields.
- **FR-013**: Directory browsing MUST preserve its directories-first,
  case-insensitive ordering, parent reporting, and permission failure
  behavior.
- **FR-014**: Preview and media rules MUST preserve supported types, content
  sniffing, size limits, archive-member selection by position, encryption
  rejection, thumbnail bounds and format, video range handling, and every
  existing failure outcome.
- **FR-015**: History mutations MUST remain atomic, and any failure MUST leave
  the target entries and the prior history intact.
- **FR-016**: The refactor MUST NOT add a mandatory runtime dependency, MUST
  keep interface-specific dependencies optional, and MUST NOT make core
  services import interface-specific modules.
- **FR-017**: The refactor MUST NOT change API paths, CLI flags, TUI
  shortcuts, history format, archive naming, or on-disk layout.
- **FR-018**: All pre-existing behavior tests MUST continue to pass, and every
  extracted operation MUST gain direct tests covering its success path and
  documented failure outcomes.
- **FR-019**: Repository documentation MUST identify the service boundaries
  and state which component owns history reads and writes, so maintainers can
  find the single source of truth.
- **FR-020**: Opening an entry with the operating system's default program
  MUST preserve its existing success and failure behavior, and launching MUST
  remain an explicit user action.
- **FR-021**: Effective history location resolution MUST be shared and MUST
  preserve explicit override, blank fallback to the target directory, and path
  expansion behavior across all interfaces.
- **FR-022**: Preview descriptors MUST preserve the current preview kind,
  text, truncation flag, archive image inventory and totals, and video
  metadata for every supported entry type.

### Key Entities *(include if feature involves data)*

- **History entry**: One parsed history record with an optional timestamp, an
  item name, and display text. It is the common representation all interfaces
  consume.
- **History store**: The local history file and its archives. It owns reading,
  appending, removal, rotation, archiving, and clearing, and is the only
  component allowed to touch the underlying files.
- **Candidate entry**: A target-directory entry eligible for picking after
  hidden, type, and managed-file exclusions are applied.
- **Pick outcome**: The result of a pick attempt: picked, empty, exhausted, or
  invalid target, plus whether the selection was logged and its preview.
- **Browse listing**: A directory path, its parent, and its ordered entries
  with directory indicators.
- **Application state**: The current target, effective history location,
  remaining candidates with totals, and recent history with totals.
- **Preview descriptor**: The structured description of a picked entry,
  including text, archive images, or video metadata, with truncation and size
  information.
- **Service outcome**: A shared, interface-neutral result that distinguishes
  success from invalid input, missing data, unsupported content, range
  failures, and persistence failures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pre-existing behavior and contract tests pass without
  changes to their assertions.
- **SC-002**: A comparison of every documented web request and failure case
  against the pre-refactor baseline reports zero differences in status,
  headers, and body.
- **SC-003**: Exactly one production component reads history and one service
  owns each history mutation; a repository review finds zero direct history
  parsing or file manipulation outside that component.
- **SC-004**: 100% of extracted operations have direct tests for their success
  path and every documented failure outcome, runnable without a web server or
  interactive terminal.
- **SC-005**: For every nontrivial web-exposed operation, a maintainer can
  find its decision logic in exactly one service location in under two
  minutes, with zero competing copies in request handlers.
- **SC-006**: A change to any shared rule — panel caps, filters, media limits,
  or history behavior — requires edits in exactly one production location
  plus adapter wiring, confirmed by a change-impact review.
- **SC-007**: The same history scenario executed through the CLI, TUI, and web
  UI produces identical history files, removed counts, remaining candidates,
  and displayed history.
- **SC-008**: The full quality gate passes: tests, lint, format check, strict
  type check, and the production frontend build, all with zero new mandatory
  runtime dependencies.
- **SC-009**: The direct service test subset completes in under 10 seconds
  without a network, web server, or interactive terminal.

## Assumptions

- The project has no relational database and will not gain one. "Database
  access queries" refers to the local history persistence layer — the history
  file and its archives — and unification applies to that data access.
- Filesystem inspection for browsing, preview, and media remains behind the
  extracted services. It is not database access, and no caching, indexing, or
  migration layer is introduced.
- This is a behavior-preserving refactor. The public contracts established by
  the API standardization feature are the frozen baseline.
- "Service modules" means in-process, interface-independent application
  modules, not separately deployed network services.
- The core remains free of new mandatory runtime dependencies; web and UI
  packages remain optional extras.
- Existing history files and archives remain readable without migration, and
  no new persistence format is introduced.
- Tests may be reorganized or renamed, but existing behavior coverage must not
  shrink.
- Purely transport-specific behavior, such as echoing configured defaults or
  serving built frontend assets, may remain in the adapter because it contains
  no business rule.
- New endpoints, new user-facing features, frontend changes, dependency
  upgrades, and performance tuning are out of scope.
- The exact number and names of service modules are planning decisions; this
  specification fixes only the ownership and behavior boundaries.
