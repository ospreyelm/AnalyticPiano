# Local Content Generation UI Design

## Goal

Provide a simple local-only Django UI for running heavyweight content generation commands without using the deployed Fly web app.

The UI must cover:

- Unit 1 generation
- Unit 2 meter exercise generation
- Units 9+ Bach corpus playlist creation

The UI is intended to run on the developer's machine against whichever database the local Django process is configured to use. That allows the same page to target:

- local Postgres for testing
- Fly Postgres through a local tunnel for production writes

## Problem

The current `Generate Content` admin page runs synchronously inside the deployed web app. Unit 1 generation is too heavy for that environment:

- it can exceed Gunicorn request timeouts
- it can exceed Fly app memory limits
- failures are difficult to interpret from the current admin UX

The user does not need this generation workflow often, so a local operational tool is a better fit than making the Fly web app absorb large one-off generation tasks.

## Non-Goals

This design does not include:

- background jobs
- queue workers
- true streaming progress over websockets
- in-browser database credential entry
- JSON import/export workflows
- generation history persistence

Those can be added later if needed, but they are not necessary for the current problem.

## Recommended Approach

Add a separate Django page dedicated to local content generation rather than extending the current admin page further.

Reasons:

- keeps generation operations separate from CRUD-heavy admin screens
- makes it easier to show database targeting and local-only warnings prominently
- avoids coupling the workflow to Django admin templates and messaging behavior
- keeps all execution inside the existing Django app and management command system

## User Experience

### Entry Point

Add a new internal page with a URL such as:

- `/tools/content-generation/`

The page is intended for local use only.

### Access Rules

The page must refuse to run in production.

Recommended guard:

- allow only when `DEBUG` is true, or
- allow only when an explicit setting such as `ENABLE_LOCAL_CONTENT_TOOLS = True` is enabled

If the route is hit without the guard enabled:

- return `404` or `403`
- do not expose form contents or command wiring

### Page Content

The page contains one shared author-email field and three sections.

#### Section 1: Unit 1

- author email
- button: `Generate Unit 1`

#### Section 2: Unit 2

- author email
- button: `Generate Unit 2 Meter Exercises`

#### Section 3: Units 9+ Bach Corpus Playlist

- author email
- unit number
- Riemenschneider range
- mode selector:
  - Roman numerals
  - Figured bass
  - Play
- button: `Create Unit Playlist`

### Feedback Area

The page includes a dedicated results panel below the forms showing:

- command started
- command completed
- explicit error message if failed
- full captured stdout transcript
- summary counts when available

The page does not need true live streaming in v1. A submit-and-return flow is acceptable as long as the output is shown clearly on completion or failure.

### Database Target Visibility

The page should display a prominent banner showing the current database target derived from Django settings, for example:

- engine
- host
- port
- database name

This is operationally important because the same local page may target either:

- the local database
- a Fly-tunneled database on `localhost:5433`

The user should be able to confirm where writes are going before clicking a generation button.

## Technical Design

### Routing

Add a dedicated route in a small internal tools area, either by:

- creating a new app namespace for internal tools, or
- adding a narrow view module and URL include under the existing project URLs

For v1, a minimal internal tools module is sufficient. A whole new app is optional if the code footprint stays small.

### View Behavior

Use a standard Django view handling:

- `GET` to render the form
- `POST` to run exactly one selected command

Command dispatch mirrors the current admin logic:

- `generate_unit1`
- `generate_unit2_meter_exercises`
- `create_unit_playlist`

Output handling:

- capture `stdout` with `StringIO`
- on success, render the page with `status=success` and transcript
- on failure, render the page with `status=error`, exception text, and transcript if any

Avoid redirect-after-post for this page. Rendering the response directly is simpler and preserves the output block naturally.

### Command Summaries

The page should display summary counts if the command output includes them.

Preferred implementation:

- continue improving command output at the management-command layer
- parse structured summary lines in the view only if necessary

This keeps the source of truth close to the command itself and avoids duplicating generation knowledge in the UI.

### Template

Create a dedicated template for the page instead of reusing the admin template.

The template should emphasize:

- local-only warning
- current DB target
- simple forms
- large, readable output panel

Visual complexity should stay low. This is an operational tool, not a product-facing screen.

### Production Guard

Add a reusable helper for local-only views so the rule is explicit and testable.

Recommended behavior:

- when disabled, raise `Http404`

That avoids advertising the tool on deployed environments.

## Data Flow

1. User starts local Django against a chosen database.
2. User opens the local content-generation page.
3. Page shows current DB host/name and available actions.
4. User submits one action.
5. View runs the corresponding management command in-process.
6. View captures stdout and success/failure.
7. Page re-renders with transcript and outcome summary.

## Error Handling

The page should handle these cases clearly:

- missing author email
- missing unit or Riemenschneider range for playlist creation
- unknown command value
- command exception with partial output
- local-only guard disabled

Error messages should be explicit and operational, for example:

- `Generation failed after creating 38 exercises. See transcript below.`
- `This tool is disabled outside local development.`

## Testing Strategy

Add tests for:

- page unavailable when local-only guard is off
- `GET` renders all three sections
- `POST` dispatches `generate_unit1`
- `POST` dispatches `generate_unit2_meter_exercises`
- `POST` dispatches `create_unit_playlist` with correct arguments
- validation errors re-render page without running a command
- exceptions show failure state and captured partial output
- database target banner renders expected connection details

Use mocking around `call_command` so tests stay fast and deterministic.

## Rollout Plan

1. Add the local-only tools view, route, template, and guard.
2. Reuse existing management commands without changing their core semantics.
3. Reuse the improved command transcript output already added for Unit 1.
4. Add tests for routing, validation, dispatch, and error handling.
5. Optionally link to the page from a developer-facing local index later, but do not expose it in production.

## Open Questions Resolved

### Why not keep using the existing admin page?

Because the current admin workflow is tied to deployed operational behavior and Django admin conventions. The user needs a local operational tool with clearer output and stronger environment signaling.

### Why not let the page accept raw DB credentials?

Because Django already owns database configuration. A second connection system in the browser would add complexity, security risk, and drift. The local Django process should remain the single source of truth for DB targeting.

### Why not build JSON export/import instead?

That would require new serialization, import idempotency rules, and reference management. Running the existing management commands locally against the target database is lower risk and closer to existing code.
