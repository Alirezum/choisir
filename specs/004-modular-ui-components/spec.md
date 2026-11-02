# Feature Specification: Modular UI Components

**Feature Branch**: `004-modular-ui-components`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Refactor monolithic frontend pages into modular, reusable UI components, separating state hooks and business logic from presentation views."

## Clarifications

### Session 2026-11-02

- Q: Should this refactor add a development-only component test runner so each presentation view can be rendered and checked in isolation, or should view verification remain manual? → A: Add a development-only component test runner, wire it into CI, and test presentation views plus extracted behavior units.
- Q: Which viewport ranges must the visual-parity check cover for this refactor? → A: All three existing ranges: desktop above 900px, tablet from 561px to 900px, and phone at 560px or below.
- Q: How should visual parity be evidenced and retained, given that browser end-to-end automation is out of scope? → A: Commit a parity checklist under the feature directory, capture before/after screenshots locally for review, and add no image binaries or browser tooling.
- Q: How should duplicated visual building blocks be detected — automated enforcement, documented review, or both? → A: A focused automated static check for repeated scaffold patterns where feasible, plus a documented review item for semantic duplication.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One Owner per Web Workflow (Priority: P1)

A maintainer changes how the web interface picks, previews, opens, browses, archives, clears, or removes history. Today the main screen owns folder, log, and option state, refresh scheduling, validation, confirmation lifecycles, selection rules, failure-to-message conversion, and keyboard handling alongside its layout markup. After this feature, each workflow lives in one named state and behavior unit with a clear contract; the main screen only composes those units and the presentation views. Every interaction and message stays identical for the person using the interface.

**Why this priority**: Without extracting state and workflow logic, presentation views cannot become presentation-only and the monolith merely relocates. This is the foundation of the refactor and delivers immediate value: each workflow becomes independently testable and has one obvious home.

**Independent Test**: Run every current web flow and compare visible outcomes, text, ordering, and enabled states with the baseline. Inspect the main screen and confirm it contains no data access, validation, workflow sequencing, confirmation handling, or derived status text. Exercise each extracted behavior unit in isolation with fixed inputs and simulated success and failure results.

**Acceptance Scenarios**:

1. **Given** the web interface before and after the change, **When** a person browses folders, changes options, picks, previews, opens, archives, clears, removes one history item, or removes a batch, **Then** the visible outcome, ordering, enabled states, and status text are identical.
2. **Given** the main screen after the change, **When** a maintainer reviews it, **Then** it contains only composition, layout, and binding of presentation views to behavior units, with no data access, domain rules, or status derivation.
3. **Given** a named workflow such as batch history removal, **When** a maintainer looks for its validation, sequencing, confirmation, and failure handling, **Then** they are all in exactly one behavior unit and no duplicate implementation exists elsewhere.
4. **Given** rapid option or folder changes, **When** refreshes overlap, **Then** the latest inputs still determine the displayed state, matching current debounce behavior.
5. **Given** overlapping preview requests, **When** an older response arrives after a newer one, **Then** the stale response is ignored, matching current behavior.
6. **Given** a failed operation, **When** the interface reports it, **Then** the same shared error message path and text are used, and no behavior unit re-parses error payloads.

---

### User Story 2 - Presentation Views Render, They Do Not Decide (Priority: P2)

A maintainer builds or changes a visual area — pick board, preview, image viewer, browser, history list, remaining list, options, status bar, or confirmation dialog — using ready-to-render data and declared user intents. The view does not fetch data, own domain workflow state, validate business inputs, parse failures, or construct addresses. Repeated visual structures such as panel scaffolds, headers, empty states, list rows, action bars, and dialogs come from shared presentation building blocks instead of being reimplemented per view.

**Why this priority**: Presentation-only views are what make the modular structure reusable and safe to change. They can be rendered and reviewed in isolation, and visual changes no longer risk workflow regressions. This depends on P1 because the inputs and intents must be owned somewhere.

**Independent Test**: Render each presentation view in isolation with fixed data, empty data, and boundary data, and confirm the output and reported intents. Confirm by source review that no view performs data access, address construction, failure parsing, business validation, or workflow sequencing. Replay all flows to confirm no visual or behavioral change.

**Acceptance Scenarios**:

1. **Given** any presentation view, **When** it is rendered with supplied data, **Then** it displays that data and reports user actions as declared intents without performing data access or deciding domain outcomes.
2. **Given** a view whose data is empty, truncated, invalid, or at a boundary, **When** it renders, **Then** the same labels, empty states, truncation, and fallbacks as the baseline appear.
3. **Given** a failed operation, **When** its message reaches a view, **Then** the view only renders the supplied message and does not inspect an error payload.
4. **Given** a visual pattern used by two or more views, **When** a maintainer inspects the implementation, **Then** exactly one shared presentation building block provides it.
5. **Given** a rendered view in all three supported ranges, **When** compared with the baseline, **Then** layout, styling, focus visibility, and accessibility semantics are unchanged.
6. **Given** the image viewer, **When** a person zooms, pans, navigates, opens the original, or presses the documented shortcuts, **Then** behavior is unchanged while its interaction state is owned by a dedicated behavior unit.

---

### User Story 3 - Modular Boundaries Stay Enforced (Priority: P3)

A maintainer can trust that future changes do not quietly rebuild the monolith. Automated checks reject presentation views that fetch data or own workflows, reject the main screen when data orchestration returns, reject behavior units that depend on views, reject circular dependencies, and reject duplicated panel scaffolding. Documentation explains where each kind of concern belongs.

**Why this priority**: Refactors decay without enforcement. The first two stories deliver the structure; this story keeps it. It is last because the checks only make sense once the target structure exists.

**Independent Test**: Deliberately add a data call to a presentation view, add workflow logic back to the main screen, introduce a view dependency into a behavior unit, create a circular dependency, and duplicate a panel scaffold. Confirm each attempt fails an automated check or the documented review step. Remove the violations and confirm all checks pass.

**Acceptance Scenarios**:

1. **Given** a presentation view that gains data access, address construction, failure parsing, or workflow ownership, **When** checks run, **Then** they fail and identify the file.
2. **Given** the main screen that regains data access, validation, confirmation lifecycle, or derived status logic, **When** checks run, **Then** they fail and identify the file.
3. **Given** a behavior unit that depends on a presentation view, or any circular dependency, **When** checks run, **Then** they fail.
4. **Given** a visual pattern already provided by a shared building block, **When** a new view reimplements the scaffold instead of using it, **Then** review or an automated check identifies the duplication.
5. **Given** the maintainer documentation, **When** a contributor needs to add a view or behavior, **Then** it states the allowed dependency direction, where each concern belongs, and how to verify the result.
6. **Given** a clean tree after the refactor, **When** the full quality gate runs, **Then** every check passes with no decrease in behavior coverage.

---

### Edge Cases

- The folder path or log file changes while a pick or preview is in flight; the current behavior (stale response ignored, choice and history selection cleared, pending confirmation cleared) must be preserved.
- The folder is empty, does not exist, or contains only filtered-out entries; the exact current status messages and empty-panel copy must appear.
- All eligible entries are exhausted; the current "all picked" state and guidance must appear.
- History is missing, truncated to the most recent slice, or has no matching entries for a removal; current no-op and count messages must appear.
- A batch removal targets items that disappeared since selection; removed counts and selection cleanup must match current behavior.
- A destructive action is in progress; duplicate archive, clear, remove, or pick actions must remain blocked or ignored exactly as today.
- A confirmation is open; Ctrl+N and background pick remain suppressed, Escape cancels, the focus trap holds, and no unintended state changes occur.
- Overlapping refreshes, picks, previews, or removals occur; ordering, debounce, stale-response guarding, and busy flags must not regress.
- Shift-range selection spans entries that were truncated or refreshed away; the anchor and selected set must resolve as today.
- An image archive has one image, index zero, more images than are shown, or a mix of numbered and unnumbered frames; labels, counts, and addresses must match.
- A video cannot play; the fallback must still direct the person to Open.
- The image viewer shows a single image or reaches zoom limits; navigation, zoom label, double-click zoom, drag clamping, scroll lock, focus, and Escape behavior must match.
- An item name exceeds the board's display limit; truncation and title behavior must match.
- A view is rendered with absent, empty, or malformed display data; it must degrade exactly like the current screen, without taking over workflow decisions.
- A boundary check is bypassed by naming a data call differently; the checks must still identify direct data access in views and workflow logic in the shell.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The refactor MUST preserve 100% of current web behavior, including browsing, default loading, state refresh and debounce, option changes, picking and validation, seed handling, dry runs, filters, previewing, opening, history archive/clear/single removal/batch removal, confirmations, keyboard shortcuts, focus behavior, status messages, and viewer interactions.
- **FR-002**: All current application state, derived display data, and workflow logic MUST reside in named state and behavior units, one concern per unit, with a clear input and output contract.
- **FR-003**: The main screen MUST be reduced to a composition root: layout, assembly of behavior units and views, and nothing else.
- **FR-004**: The main screen MUST NOT contain data access, address construction, payload parsing, business validation, workflow sequencing, confirmation lifecycle logic, debounce logic, stale-response handling, or derived status and confirmation text.
- **FR-005**: Every existing presentation area MUST become a presentation view that receives ready-to-render data and reports user intents; it MUST NOT perform data access, own domain workflow state, validate business inputs, parse failures, or construct addresses.
- **FR-006**: State and behavior units MUST own their data access through the existing shared client boundary and MUST NOT depend on presentation views.
- **FR-007**: Dependency direction MUST be acyclic and one-way: views and behavior units depend on shared types and building blocks, the composition root depends on both, views never depend on behavior units that own other views' workflows, and behavior units never depend on views.
- **FR-008**: Every visual structure repeated across two or more views (panel scaffold, header, empty state, list row, action bar, dialog) MUST be provided once as a shared presentation building block and reused.
- **FR-009**: Every confirmation and destructive-action rule MUST be preserved: clear and batch removal require explicit confirmation; cancelling changes nothing; single-item removal requires its explicit row action; failures leave data intact.
- **FR-010**: Asynchronous safety MUST be preserved: refresh debounce, stale-response rejection for previews and picks, disabled or busy controls during destructive work, and blocked shortcuts while a confirmation is open.
- **FR-011**: Accessibility and keyboard contracts MUST be unchanged: tab roles and arrow/Home/End navigation, visible focus, Ctrl+N picking, viewer shortcuts, dialog focus trap and Escape, scroll lock, labels, live status announcements, and reading order.
- **FR-012**: Visual output MUST be unchanged in all three supported ranges — desktop above 900px, tablet from 561px to 900px, and phone at 560px or below; the existing styles and markup semantics remain authoritative so the refactor introduces no redesign.
- **FR-013**: Destructive or fallible flows MUST keep their exact current messages, including success, no-op, invalid-path, empty, exhausted, missing-history, validation, and failure text.
- **FR-014**: Automated checks MUST fail when a presentation view performs data access or parses failures, when the composition root regains workflow logic, when a behavior unit depends on a view, or when a dependency cycle appears.
- **FR-015**: Automated checks MUST detect repeated panel, header, empty-state, row, action-bar, or dialog scaffold patterns where feasible, and a documented review step MUST detect semantic duplication that static checks cannot judge; together they MUST identify reimplementation of a shared visual building block.
- **FR-016**: Extracted state and behavior units and every presentation view MUST have isolated automated tests: behavior units covering success, failure, and boundary cases; views covering fixed, empty, and boundary data. The suite MUST use development-only test tooling, MUST run in CI, and MUST NOT add a runtime dependency; the existing shared-client tests MUST remain green and unchanged in intent.
- **FR-017**: The production build, type check, existing frontend and backend quality gates, the UI test suite, and manual flow replay MUST pass, with no reduction in behavior coverage and no new runtime dependency.
- **FR-018**: The feature MUST NOT add a global state library, router, UI or styling framework, server-side rendering, state persistence, telemetry, new routes, backend changes, API-contract changes, or user-visible features.
- **FR-019**: Maintainer documentation MUST describe the target module layout, the allowed dependency direction, where state and workflow versus presentation concerns belong, and how to add a view or a workflow.
- **FR-020**: A change to one workflow or one view MUST be localized to that concern and its tests, without requiring edits to unrelated behavior units or views, as confirmed by a change-impact review.
- **FR-021**: The shared client from the prior work MUST remain the only frontend network boundary; no behavior unit or view may bypass it.
- **FR-022**: User-visible text, ordering, and timing MUST be treated as a compatibility contract; any intentional deviation requires an explicit recorded decision, otherwise parity is mandatory.
- **FR-023**: A parity checklist covering every flow, message class, keyboard and accessibility behavior, and all three viewport ranges MUST be committed under the feature directory and completed against the pre-refactor baseline; before/after screenshots are captured locally for review, with no image binaries or browser automation committed.

### Key Entities

- **Web person**: A person using the local web interface; all flows and visible outcomes must remain unchanged for them.
- **Workflow**: A named user-facing sequence such as pick, preview, open, browse, archive, clear, single removal, batch removal, or viewer interaction.
- **State and behavior unit**: A named module owning one workflow's state, data access, validation, sequencing, derived display data, and failure-to-message conversion.
- **Composition root / main screen**: The thin assembly layer that lays out the interface and connects behavior units to presentation views.
- **Presentation view**: A visual area that renders supplied data and reports user intents without owning workflow decisions.
- **Shared presentation building block**: One reusable visual structure (panel scaffold, header, empty state, row, action bar, dialog) used by multiple views.
- **View model**: Ready-to-render data supplied to a view, including display labels and fallbacks.
- **User intent**: A declared action a view reports, such as pick, open, preview, archive, clear, remove, toggle selection, navigate, zoom, or close.
- **Parity baseline**: The current interface's visible behavior, text, ordering, and accessibility contract captured before the refactor and recorded in the committed parity checklist.
- **Boundary rule**: An allowed or forbidden dependency between the composition root, behavior units, views, shared building blocks, and the shared client.
- **Boundary check**: An automated verification that rejects monolith regression, view data access, reverse dependencies, cycles, and duplicated scaffolds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing web flows — browse, options, pick, preview, open, archive, clear, single removal, batch removal, and viewer — produce identical visible outcomes, status text, ordering, and enabled states compared with the pre-refactor baseline.
- **SC-002**: A responsibility audit of the main screen finds zero data access, business validation, workflow sequencing, confirmation lifecycle, debounce, stale-response, or derived status logic; 100% of that logic is owned by named behavior units.
- **SC-003**: A source audit finds zero presentation views that perform data access, construct addresses, parse failures, or own domain workflow state.
- **SC-004**: 100% of extracted behavior units have isolated automated tests covering at least one success path, one failure path, and one boundary case, and 100% of presentation views have isolated automated rendering tests covering fixed, empty, and boundary data; the UI suite runs in CI and all pre-existing client tests still pass.
- **SC-005**: A dependency audit finds zero reverse dependencies and zero cycles.
- **SC-006**: 100% of visual structures used by two or more views are supplied by exactly one shared building block, with zero duplicated scaffolds.
- **SC-007**: Each of five deliberate violations — data access in a view, workflow logic in the main screen, a behavior unit depending on a view, a dependency cycle, and a duplicated scaffold — is detected in 100% of trials, by the automated check where the pattern is static and by the documented review otherwise.
- **SC-008**: Every named workflow can be located in exactly one owner within two minutes by a maintainer using the module layout and documentation.
- **SC-009**: A change-impact review shows that editing one workflow or one view requires changes only in that concern, its shared building block if applicable, and its tests.
- **SC-010**: The production build, type check, all frontend and backend quality gates, and the manual flow replay pass with zero new runtime dependencies and zero reduction in test coverage.
- **SC-011**: A side-by-side comparison in all three supported ranges — desktop above 900px, tablet from 561px to 900px, and phone at 560px or below — finds zero visual differences and zero changes to focus order, labels, live announcements, or keyboard behavior.
- **SC-012**: A new contributor can add a presentation view or a behavior unit by following the documentation without modifying unrelated modules, verified by a walkthrough.
- **SC-013**: The committed parity checklist covers 100% of flows, message classes, keyboard and accessibility behaviors, and the three viewport ranges, and records zero unexplained differences between the baseline and the refactored interface.

## Assumptions

- The request uses "pages" to mean the single web interface and its visual areas; there is one page today, and it will remain one page.
- The refactor is internal: no user-visible behavior, visual design, text, timing, route, API, or backend change is intended. The current interface is the parity baseline.
- "State hooks" means reusable state and behavior units native to the existing frontend approach, not a new global state management library or additional runtime dependency.
- Reuse is internal to this web interface; no published component library, design system, theming system, or cross-application package is created.
- All current web UI concerns are in scope: the main screen, pick board, preview, image viewer, browser, history panel, remaining panel, options panel, status bar, and confirmation dialog.
- State and workflow logic includes data access, validation, sequencing, confirmation lifecycle, debounce, stale-response handling, selection rules, and derived display text. Pure formatting used only for rendering may live with the view.
- The shared client boundary from the prior feature remains authoritative and unchanged; views and behavior units keep using it, and nothing bypasses it.
- Existing styles and markup semantics are reused so the refactor does not become a redesign; class names and structure may be reorganized only when visual and accessibility parity is proven.
- "Supported viewport sizes" means the three ranges already defined by the interface: desktop above 900px, tablet from 561px to 900px, and phone at 560px or below.
- Verification uses static boundary checks, isolated behavior tests, isolated view rendering, type checking, the production build, the existing test suites, a committed parity checklist, and a manual flow replay with locally captured screenshots.
- A development-only component test runner and DOM environment are added and run in CI; they add no runtime dependency and do not change shipped behavior. Browser end-to-end automation and automated screenshot comparison remain out of scope.
- Exact module names, folder layout, state-unit granularity, and check implementation are planning decisions. This specification fixes separation of concerns, dependency direction, behavior parity, reuse, and enforcement.
- No performance or bundle-size target is introduced beyond the requirement that current behavior, responsiveness, and startup experience do not regress; avoiding new runtime dependencies is the guard against added weight.
- No new feature, route, persistence, authentication, telemetry, retry, caching, offline mode, or backend capability is introduced.
