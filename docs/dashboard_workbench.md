# Teacher Workbench

The Teacher Workbench (`/dashboard/workbench/`) is a dashboard tool for importing MusicXML content and projecting it into multiple exercise types in bulk — without SSH access or management commands.

---

## What it does

A two-panel UI:

**Left — Recent Mass Imports**
Lists all base exercises the logged-in teacher has imported via MusicXML upload (filtered by `description__startswith="Auto-Import:"`). Each row shows the exercise description, key, source filename, and chunk number. Supports multi-select with per-item mode overrides.

**Right — Projection Engine**
Takes the selected base exercises and creates new Exercise rows of a chosen type. One new exercise is created per selected source. The created exercises go directly into the teacher's library (private, not public).

---

## Workflow

```
MusicXML file
    ↓  (drag-upload or file picker)
POST /dashboard/workbench/upload/
    ↓  calls mass_import_performance CLI in-process
Base exercises (type=umto_chorale, description="Auto-Import: …")
    ↓  shown in Recent Mass Imports panel
Select one or more → choose projection type
    ↓  POST /dashboard/api/multiply-projection/
New exercises in teacher's library (private, ready to add to a playlist)
```

---

## Routes

| URL | Name | View | Auth |
|-----|------|------|------|
| `GET /dashboard/workbench/` | `dashboard:workbench` | `workbench_view` | `@login_required` |
| `POST /dashboard/workbench/upload/` | `dashboard:workbench-upload` | `workbench_upload_view` | `@login_required` |
| `GET /dashboard/api/recent-imports/` | `dashboard:api-recent-imports` | `api_recent_imports` | `@login_required` |
| `POST /dashboard/api/multiply-projection/` | `dashboard:api-multiply-projection` | `api_multiply_projection` | `@login_required` |

All views are in `apps/dashboard/views/api_workbench.py`.

---

## Upload endpoint

`POST /dashboard/workbench/upload/`

Accepts a `multipart/form-data` POST with field `musicxml_file` (`.xml`, `.mxl`, `.musicxml`). Writes the file to a temp path and calls `mass_import_performance` via `call_command`. Errors are logged to stdout but the user is always redirected back to the workbench page — the UI does not show upload errors yet.

The `mass_import_performance` command splits the score into chunks at rest-only measures and creates one `umto_chorale` exercise per chunk, tagged with `Auto-Import:` in the description so the workbench can retrieve them later.

---

## Recent imports API

`GET /dashboard/api/recent-imports/?limit=50`

Returns JSON:
```json
{
  "results": [
    {
      "id": "ABC123",
      "description": "Auto-Import: Heacox Example Chunk 2",
      "type": "umto_chorale",
      "key": "G",
      "measureRange": "heacox.xml - Chunk 2"
    }
  ]
}
```

Filtered to `authored_by=request.user` and `description__startswith="Auto-Import:"`, ordered by `-id`.

---

## Projection endpoint

`POST /dashboard/api/multiply-projection/`

Request body:
```json
{
  "source_ids": ["ABC123", "DEF456"],
  "target_type": "roman_numeral",
  "ident_mode": "submit",
  "per_item_modes": { "ABC123": "practice" }
}
```

- `target_type` — one of the five projection types (see table below)
- `ident_mode` — global default: `"submit"`, `"practice"`, or `"test"`
- `per_item_modes` — optional per-exercise override; takes precedence over `ident_mode`

For each source exercise, calls `save_umto_exercise` with the source's score data, skill tags, and complexity, and the mapped `InteractionMode`. Wraps all creates in a single `transaction.atomic()`.

Response:
```json
{
  "status": "success",
  "created_exercises": ["XYZ789", "XYZ790"],
  "message": "Successfully projected 2 exercises into roman_numeral."
}
```

---

## Projection types

| `target_type` | Button label | `InteractionMode` | Student does |
|---|---|---|---|
| `roman_numeral` | Roman Numeral Analysis | `IDENTIFICATION` | Identifies chords with Roman numerals |
| `figured_bass` | Figured Bass Realization | `IDENTIFICATION` | Plays upper voices over given bass |
| `exact_match` | Exact Match (Notation) | `PLAYBACK` | Plays notation exactly as written |
| `analysis_match` | Analysis Match (Note Names) | `ANALYSIS_MATCH` | Plays notes from analytical labels (notation hidden) |
| `identification` | Pitch Identification | `IDENTIFICATION` | Identifies individual pitches |

> **Note:** `roman_numeral`, `figured_bass`, and `identification` all map to `InteractionMode.IDENTIFICATION` — they differ in how the frontend renders and grades them, not in the stored mode value.

---

## Identification mode

Each projected exercise can independently be set to one of three modes, either globally via the "Default Mode for All" dropdown or per-item via the row dropdown:

| Mode | Behaviour |
|------|-----------|
| `submit` | Student answers all, then submits — results revealed at end |
| `practice` | Correct/incorrect shown immediately after each answer |
| `test` | Slots lock after answering; no colour feedback |

---

## Known limitations and incomplete areas

- **Upload errors are silent** — if `mass_import_performance` raises an exception, the user is redirected to the workbench with no error message. The exception is printed to stdout only.
- **`@csrf_exempt` on projection endpoint** — `api_multiply_projection` has `@csrf_exempt` but the JS already sends `X-CSRFToken` from the cookie. The decorator is unnecessary and should be removed.
- **No score preview** — there is no way to inspect a base exercise's score before projecting. The Phase 3 spec planned a preview panel; not yet built.
- **No playlist wiring** — projected exercises land in the teacher's library as private exercises. Adding them to a playlist requires a separate step in the exercise editor or a management command.
- **"Generate Unit N" button** — the Phase 3 spec described an HTMX-driven button to generate a full unit playlist with live progress streaming. Not yet built.
- **Upload failure feedback** — the upload form submits as a standard HTML form POST and always redirects. A future improvement would return an HTMX partial or JSON response so errors can be surfaced in the UI.
- **Description truncation** — projected exercise descriptions are capped at 60 characters to match a database constraint. Long source descriptions are silently truncated.

---

## Key files

| File | Purpose |
|------|---------|
| `apps/dashboard/views/api_workbench.py` | All four views |
| `apps/dashboard/templates/dashboard/workbench.html` | Full UI (HTML + CSS + vanilla JS) |
| `apps/dashboard/urls.py` | Route wiring (lines 71–72, 128–129) |
| `apps/exercises/management/commands/mass_import_performance.py` | MusicXML → chunked base exercises |
| `apps/exercises/umto_factory.py` | `save_umto_exercise` used by projection |

---

## Related docs

- `docs/management_commands.md` — CLI commands for content generation
- `docs/exercise_types.md` — exercise types and grading modes
- `docs/superpowers/specs/2026-04-16-mass-import-performance-design.md` — original mass import design
- `docs/superpowers/specs/2026-04-29-platform-roadmap.md` — Phase 3 workbench roadmap items
