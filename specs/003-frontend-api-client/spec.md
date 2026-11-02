# Feature Specification: Frontend API Client Layer

**Feature Branch**: `003-frontend-api-client`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Centralize all frontend API calls into a dedicated, typed API client layer that matches the standardized backend routes and error schemas. Remove direct fetch/axios calls from UI components."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every Web Flow Keeps Working Through One Client Boundary (Priority: P1)

A person using the web interface continues to browse folders, pick entries,
preview files and media, open entries, and manage history exactly as before.
Behind those interactions, every screen obtains data and triggers actions
through one shared client layer; no screen or reusable UI component performs
its own network request or constructs its own endpoint address.

**Why this priority**: Centralization is the foundation of the feature. Without
one boundary, local behavior may still work, but typed errors and drift
protection cannot be guaranteed.

**Independent Test**: Run every current web flow against the local server and
compare visible outcomes with the pre-change baseline. Review the frontend
source and confirm that only the shared client layer contains network calls or
endpoint addresses.

**Acceptance Scenarios**:

1. **Given** any web action that needs backend data or produces a backend
   outcome, **When** the action runs, **Then** the request is issued through the
   shared client and the screen receives a typed result.
2. **Given** the frontend source, **When** a reviewer searches screens and
   reusable components for network calls or hard-coded endpoint addresses,
   **Then** none are found outside the shared client layer.
3. **Given** an image or video preview, **When** the interface displays the
   media, **Then** the shared client supplies the encoded media address and the
   component performs no endpoint construction.
4. **Given** all current successful flows, **When** they are replayed after the
   change, **Then** visible results, ordering, status messages, and history
   outcomes are unchanged.
5. **Given** a route or parameter change in the backend contract, **When** the
   shared client is updated, **Then** existing screens continue to work without
   changes to their request logic.

---

### User Story 2 - Failures Share One Typed, User-Readable Path (Priority: P2)

A person using the web interface sees a clear message whenever an operation
fails. Every failure, regardless of its cause, reaches the interface as one
shared error result carrying the backend's stable code, human-readable message,
HTTP status, and optional structured details, so screens never need
route-specific error handling.

**Why this priority**: The backend already defines one standardized error
envelope. The interface only benefits from it if failures are interpreted in
one place and presented consistently.

**Independent Test**: Trigger every documented failure category, including
invalid input, missing resources, forbidden access, oversized payloads,
unsupported media, unsatisfiable ranges, validation failures, and internal
errors. Confirm that each produces the same typed error shape and that the
interface displays the backend's message. Repeat with a malformed error body
and with the server unavailable.

**Acceptance Scenarios**:

1. **Given** a failed operation returning the standardized error envelope,
   **When** the client receives it, **Then** it produces one shared error result
   exposing the HTTP status, stable code, message, optional details, and a
   message compatible with the existing interface.
2. **Given** any screen that handles a failed operation, **When** it displays
   the failure, **Then** it shows the shared human-readable message without
   inspecting the error envelope or branching on a specific route.
3. **Given** a failure response with a missing, malformed, or non-JSON body,
   **When** the client handles it, **Then** it produces a readable status-based
   message and no raw parsing failure reaches the interface.
4. **Given** a network or connection failure, **When** the client handles it,
   **Then** it produces the same shared error result with a readable message.
5. **Given** a validation failure with structured details, **When** the client
   produces the error, **Then** the details remain available unchanged.
6. **Given** a domain outcome such as an invalid path, an empty directory, or
   exhausted choices, **When** the backend reports it successfully, **Then** it
   is not treated as an error and current screen behavior is unchanged.

---

### User Story 3 - Contract Drift Is Caught in One Place (Priority: P3)

A maintainer can map every standardized backend route to exactly one frontend
client operation and trust that an unannounced route, field, or error-code
change fails an automated check before release. A legitimate route addition
requires changes only in the shared client and its related types and tests, not
in individual screens.

**Why this priority**: Centralization and typing deliver immediate value, but
the boundary only stays reliable if drift and bypasses are detected
automatically.

**Independent Test**: Compare the documented route inventory with the client's
operations and confirm a one-to-one match. Remove or rename a route, success
field, or error code without updating the client and confirm that a type check,
build, or automated test fails. Add a direct network call to a UI component and
confirm that the source-boundary check fails.

**Acceptance Scenarios**:

1. **Given** the documented backend route inventory, **When** a maintainer
   reviews the client, **Then** every route has exactly one client operation
   with matching method, path, parameters, and success type.
2. **Given** the documented error codes and status mapping, **When** the client
   types are reviewed, **Then** every documented code is represented and no
   undocumented code is assumed.
3. **Given** a route, success field, or error code is removed or renamed
   without a matching client update, **When** the automated checks run,
   **Then** they fail.
4. **Given** a UI screen or component introduces a direct network call or a
   hard-coded endpoint address, **When** the automated checks run, **Then** they
   fail.
5. **Given** a legitimate route addition, **When** it is implemented, **Then**
   only the shared client, its types, and its tests change; no screen needs to
   construct the request.
6. **Given** the maintainer documentation, **When** a contributor needs to add
   or change a route or error code, **Then** it identifies the shared client as
   the only frontend API boundary and describes the required updates.

---

### Edge Cases

- A failure may return the standardized error envelope, a legacy message field
  only, an empty body, or a non-JSON body; all must produce a readable error
  without leaking parsing failures.
- An error may carry `null` details, structured validation details, or details
  for a future error code; the client must preserve what it receives without
  crashing.
- A future error code that is not yet known to the client must still surface
  its message and status rather than being discarded.
- A failure response may omit a message; the client must fall back to the HTTP
  status text.
- Domain outcomes that are deliberately successful — invalid path, empty
  directory, exhausted choices, missing history, and no-op archive or clear —
  must never be converted into errors.
- Optional request parameters that are absent, `null`, `false`, or an empty
  string must be encoded with the same meaning as the current interface.
- Parameter values containing spaces, Unicode, punctuation, or path separators
  must be encoded correctly and must not alter route selection.
- An archive image member at index zero must be addressable without being
  mistaken for an absent index.
- Binary image and video responses must not be parsed as JSON; the client's
  responsibility for them ends at producing the correct media address.
- A media element failing to load an image or video must continue to be handled
  by the existing screen behavior, not by the JSON error path.
- Two routes that share a path but use different methods must remain distinct
  client operations.
- A duplicated client operation or a missing client operation must fail the
  route-coverage check.
- Overlapping requests and out-of-order responses must retain the current
  screen behavior; retries, cancellation, request queues, and offline behavior
  are not introduced by this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All frontend access to the backend MUST flow through one
  dedicated API client layer, including JSON requests, actions that change
  state, and address construction for binary media.
- **FR-002**: Screens and reusable UI components MUST NOT perform network
  requests, construct backend endpoint addresses, or parse error payloads
  directly.
- **FR-003**: The client MUST expose exactly one operation for every documented
  backend route, with the route's method, path, parameters, and request body
  semantics.
- **FR-004**: The client MUST define request, success-response, and error types
  that match the standardized contract's field names, types, nullability,
  enumerated values, and status mapping.
- **FR-005**: Every non-success response MUST become one shared typed error
  result carrying the HTTP status, stable error code, human-readable message,
  optional structured details, and a message field compatible with the existing
  interface.
- **FR-006**: All frontend failure handling MUST use the shared error result;
  screens MUST NOT branch on route-specific error shapes or reimplement error
  parsing.
- **FR-007**: Missing, malformed, non-JSON, or unknown error payloads MUST fall
  back to a readable status-based error, and an unknown future error code MUST
  still preserve its message and status.
- **FR-008**: Network and connection failures MUST use the same shared error
  path and produce a readable message.
- **FR-009**: Successful JSON responses MUST preserve their current fields,
  shapes, and meanings, and all existing screen outcomes MUST remain unchanged.
- **FR-010**: Deliberately successful domain outcomes MUST remain successful
  and MUST NOT be converted into errors.
- **FR-011**: Image and video media addresses MUST be produced centrally with
  the same parameter encoding and conditional inclusion rules as the existing
  interface.
- **FR-012**: Automated checks MUST fail when a documented route is missing
  from the client, when a route is represented more than once, or when a
  documented error code is absent from the client's error types.
- **FR-013**: Automated checks MUST fail when a screen or reusable component
  introduces a direct network request, a hard-coded endpoint address, or
  direct error-envelope parsing.
- **FR-014**: A legitimate route, field, or error-code change MUST require
  edits only to the shared client and its related types and tests, not to
  individual screens.
- **FR-015**: The feature MUST NOT change backend routes, methods, request or
  response schemas, status codes, error codes, messages, or error envelopes.
- **FR-016**: The feature MUST NOT add a runtime dependency, authentication,
  telemetry, caching, request retry, offline queue, global state library, or
  user-visible feature.
- **FR-017**: The frontend production build, strict type check, existing tests,
  and source-boundary checks MUST pass with no decrease in behavior coverage.
- **FR-018**: Maintainer documentation MUST identify the shared client as the
  only frontend API boundary and explain how to add or change a route and an
  error code.

### Key Entities *(include if feature involves data)*

- **Client operation**: One named frontend operation corresponding to exactly
  one backend route, including its request inputs and typed successful result.
- **Route contract**: The documented method, path, parameters, success
  structure, error cases, status codes, and content types for one backend
  route.
- **Success result**: The typed payload a screen receives from a successful
  client operation.
- **API error**: The single typed failure result containing HTTP status, stable
  code, human-readable message, optional structured details, and the legacy
  message value used for display.
- **Error code catalog**: The complete set of documented failure codes and
  their HTTP status mapping.
- **Media address**: A client-produced address for an image or video endpoint,
  including correctly encoded optional parameters.
- **UI consumer**: A screen or reusable component that requests work through
  the client and renders either a success result or the shared error message.
- **Coverage report**: The automated comparison of documented routes and error
  codes against the client's operations and types.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of documented backend routes are represented by exactly one
  client operation, with zero missing or duplicate routes.
- **SC-002**: A source-boundary review finds zero direct network calls,
  hard-coded endpoint addresses, or error-envelope parsing in screens and
  reusable UI components.
- **SC-003**: 100% of documented error codes are represented in the client, and
  every failed operation produces the shared typed error result.
- **SC-004**: Every current web flow — browse, state, pick, preview, media
  display, open, archive, clear, single removal, and batch removal — produces
  the same visible outcome as before the change.
- **SC-005**: Deliberately removing or renaming a route, success field, or error
  code without a client update causes an automated check to fail in 100% of
  tested cases.
- **SC-006**: Adding a direct network call or endpoint address to a UI component
  causes the source-boundary check to fail.
- **SC-007**: For every documented failure category, the message displayed to
  the user equals the backend's human-readable message, including validation,
  missing-resource, unsupported-media, and internal failures.
- **SC-008**: A legitimate route change requires edits in exactly one frontend
  production component — the shared client — plus its types and tests, as
  confirmed by a change-impact review.
- **SC-009**: The frontend production build and strict type check pass with zero
  new runtime dependencies.
- **SC-010**: A maintainer can locate the client operation for any documented
  route in under two minutes using the client and its route map.

## Assumptions

- The standardized API contract from the existing backend response work remains
  authoritative and unchanged; this feature adapts the frontend to it rather
  than redefining it.
- "All frontend API calls" includes JSON requests, actions that change backend
  state, and address construction for binary image and video responses. The
  browser still performs the actual media loading.
- The current user-visible success behavior and error messages are the
  compatibility baseline; this feature changes where requests and errors are
  handled, not what users see on successful flows.
- The existing legacy message field remains part of error compatibility, while
  the structured code, message, details, and status become available through
  the typed error.
- Validation details keep their existing structured meaning; the client passes
  them through rather than reformatting or discarding them.
- Unknown future error codes are handled generically so that adding a backend
  code does not crash the interface before the client is updated; coverage
  checks still require the catalog to stay in sync.
- Media elements keep their current loading and playback behavior; binary
  payloads are not buffered or parsed by the JSON client.
- Retry, cancellation, request deduplication, offline support, caching, and
  global state management are out of scope.
- No backend routes, response fields, status codes, error codes, or messages
  change; no new user-facing feature, authentication, or telemetry is
  introduced.
- Verification uses the existing production build, strict type checking, unit
  or component tests, source-boundary checks, and a manual flow replay; browser
  end-to-end automation is not required.
- The exact file layout, type-generation mechanism, and check implementation
  are planning decisions; this specification fixes only the boundary,
  contract-matching, error-handling, and drift-protection requirements.
