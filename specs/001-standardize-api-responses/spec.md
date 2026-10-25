# Feature Specification: Standardize API Responses and Error Schemas

**Feature Branch**: `001-standardize-api-responses`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Audit and standardize API response formats and error schemas across existing backend routes, ensuring current frontend consumption does not break."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Existing Web Flows Keep Working (Priority: P1)

A person using the web interface continues to browse folders, pick items,
preview files, open entries, and manage history exactly as before while the
backend response formats are audited and standardized.

**Why this priority**: The feature is only safe if every current screen keeps
working. A cleaner API contract has no value if it breaks the only consumer.

**Independent Test**: Run the existing frontend against the standardized
backend and complete every current flow without frontend changes. Confirm that
every field the frontend reads is still present with the same type and meaning.

**Acceptance Scenarios**:

1. **Given** an existing web screen that loads API data, **When** it requests
   its current endpoint, **Then** every field it reads is still present with the
   same name, type, nullability, and meaning.
2. **Given** a response that needs normalization, **When** the normalized form
   is introduced, **Then** the change is additive and existing fields remain
   unchanged.
3. **Given** the complete set of existing routes, **When** the audit finishes,
   **Then** no success field consumed by the frontend has been removed,
   renamed, or retyped.
4. **Given** a success response, **When** its format is reviewed, **Then** it
   follows the documented field-naming, nullability, and status conventions
   without changing the fields the frontend already reads.

---

### User Story 2 - Consistent, Actionable Errors (Priority: P2)

A person using the web interface sees a clear message when an operation fails,
regardless of whether the failure came from invalid input, a missing file, an
unsupported format, a permission problem, or a server error.

**Why this priority**: Error handling is currently route-specific in shape and
sometimes falls back to a generic status line. A consistent contract makes
failures understandable and lets the frontend handle them uniformly.

**Independent Test**: Trigger each failure category through the API and confirm
that the response uses one documented error shape, the correct status category,
and a non-empty human-readable message that the current frontend can display.

**Acceptance Scenarios**:

1. **Given** a request with invalid input, **When** the backend rejects it,
   **Then** the response contains a stable machine-readable error code, a
   human-readable message, and optional structured details.
2. **Given** a missing file, page, or target, **When** the request fails,
   **Then** the response uses the same error shape and an appropriate
   not-found status.
3. **Given** an unsupported or oversized payload, **When** the request is
   rejected, **Then** the response uses the same error shape and the correct
   status category.
4. **Given** the current frontend, **When** any standardized error is returned,
   **Then** the interface still shows a useful message without route-specific
   error parsing.

---

### User Story 3 - Auditable Contracts and Drift Protection (Priority: P3)

A maintainer can see every route's success and error contract in one place and
trust that CI rejects accidental drift before it reaches users.

**Why this priority**: The audit is a one-time activity, but the contract needs
to stay consistent as routes are added or changed.

**Independent Test**: Review the contract inventory, then introduce a temporary
field removal and an error-shape change in a test harness. Confirm that the
contract checks fail for both.

**Acceptance Scenarios**:

1. **Given** the API route inventory, **When** a maintainer reviews it, **Then**
   every route lists its purpose, success structure, error cases, status codes,
   and content types.
2. **Given** a change that removes or renames a consumed success field, **When**
   CI runs, **Then** the contract check fails.
3. **Given** a new route or a changed error response, **When** it is proposed
   without updating the contract inventory and tests, **Then** CI fails.

---

### Edge Cases

- Framework-generated request validation failures currently expose a list of
  validation items; they must be normalized without losing field-level detail.
- Unknown API paths currently rely on the framework's default error body; they
  must still conform to the standard error shape.
- Binary responses (image previews and video streams) must keep their binary
  success payloads and use the standard error shape only when they fail.
- `/api/state` and `/api/pick` intentionally report invalid paths as successful
  domain outcomes (`valid_path: false` and `status: invalid_path`); these must
  remain successful responses, not errors.
- Empty or exhausted directories, missing history files, and no-op archive or
  clear operations must remain successful outcomes with their current fields
  and meanings.
- Error responses must retain the current human-readable `detail` value so the
  existing frontend continues to display messages during the transition.
- A failure while handling a request must not change the target directory, the
  history log, or the semantics of earlier successful requests.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every success response MUST preserve all fields currently read by
  the frontend, including their names, types, nullability, and meaning.
- **FR-002**: Success-format standardization MUST be additive. Removing,
  renaming, or retyping a consumed field is out of scope for this feature.
- **FR-003**: Every JSON error returned by an API route MUST use one documented
  error contract containing a stable machine-readable code, a human-readable
  message, and optional structured details.
- **FR-004**: Framework-generated validation errors MUST be normalized into the
  same error contract while preserving field-level details.
- **FR-005**: Unknown API paths MUST return the standard JSON error contract
  rather than an undocumented error body.
- **FR-006**: Every JSON error MUST include a string `detail` value compatible
  with the current frontend, including normalized validation failures, so
  existing screens display a useful message without changes.
- **FR-007**: Error responses MUST use appropriate status categories:
  malformed or invalid input, forbidden access, missing resource, oversized
  payload, unsupported media, request validation failure, and internal failure.
- **FR-008**: Error responses MUST declare a JSON content type. API routes MUST
  NOT return HTML error pages.
- **FR-009**: Domain outcomes that are not failures — invalid path, empty
  directory, exhausted choices, and missing history — MUST remain successful
  responses with their current shapes and semantics.
- **FR-010**: Binary endpoints MUST keep their current binary success payloads
  and byte-range behavior; failures MUST use the standard JSON error contract.
- **FR-011**: A contract inventory MUST document every API route, including its
  purpose, success structure, error cases, status codes, and content types.
- **FR-012**: Automated contract checks MUST cover every API route and assert
  success structure, error structure, status category, and content type.
- **FR-013**: Contract checks MUST fail when a consumed success field is
  removed, renamed, or retyped, or when an error response drifts from the
  documented shape.
- **FR-014**: Error codes MUST be documented and stable. Adding a new code is
  additive; removing or renaming one is a breaking contract change.
- **FR-015**: The frontend MUST be able to handle all API failures through one
  shared error path; no route-specific error parsing is required.
- **FR-016**: The contract inventory and conformance checks MUST be updated
  whenever a route, success field, error case, or status mapping changes.
- **FR-017**: Route paths, HTTP methods, request semantics, and the existing
  no-authentication local-only model MUST remain unchanged.
- **FR-018**: Success responses MUST follow documented conventions for field
  naming, nullability, collection/count pairing, and enumerated status values,
  without renaming fields consumed by the frontend.

### Key Entities *(include if feature involves data)*

- **Route Contract**: One API route's method, path, purpose, success structure,
  error cases, status codes, and content types.
- **Success Response**: The route-specific JSON object consumed by the
  frontend, with stable field names, types, nullability, and meanings.
- **Error Response**: The shared failure payload containing a stable error
  code, human-readable message, optional structured details, and the legacy
  `detail` string.
- **Contract Inventory**: The complete catalog of route contracts that
  maintainers review and update alongside route changes.
- **Compatibility Baseline**: The existing frontend API client, types, and
  screens whose current behavior must not regress.
- **Conformance Check**: Automated assertions that every route matches its
  documented success and error contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing web flows — defaults, browse, state, pick,
  preview, open, archive, clear, and history deletion — complete successfully
  against the standardized API without frontend changes.
- **SC-002**: 100% of tested error cases across all API routes return the
  documented error contract and correct status category; zero routes expose a
  separate JSON error shape.
- **SC-003**: The contract inventory covers 100% of API routes, with no
  undocumented route.
- **SC-004**: The contract checks detect 100% of seeded breaking changes to
  consumed success fields and error structures.
- **SC-005**: The existing web API test suite passes with no regression in
  route behavior; any new assertions are additive or specific to the new error
  contract.
- **SC-006**: Every tested error category produces a non-empty, human-readable
  message that the current frontend displays without route-specific handling.
- **SC-007**: A route added without a contract inventory entry or conformance
  check fails CI 100% of the time.

## Assumptions

- The local web frontend is the only consumer of these routes; there are no
  external or third-party API clients to preserve.
- Existing route paths, methods, and request parameters remain unchanged.
- Success payloads will not be wrapped in a new envelope; standardization is
  additive and convention-based.
- The existing `detail` string remains for backward compatibility while the
  structured error fields are introduced alongside it.
- Binary endpoints are in scope for error standardization but not for success
  payload restructuring.
- Existing successful domain outcomes such as invalid paths, empty directories,
  exhausted choices, and missing history are intentional behavior and stay as
  successful responses.
- Contract verification runs within the existing test suite and CI pipeline;
  no external service or manual audit process is required.
- Breaking changes are out of scope. A future breaking change requires explicit
  versioning and a coordinated frontend migration.
