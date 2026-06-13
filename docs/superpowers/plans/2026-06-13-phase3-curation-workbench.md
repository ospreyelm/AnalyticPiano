# Phase 3: Curation Workbench

> **Combined spec + plan** per decision D5.
> Parent: [teacher-experience-meta-plan](2026-06-12-teacher-experience-meta-plan.md)
> Decisions: [teacher-experience-decisions](../specs/2026-06-12-teacher-experience-decisions.md)
>
> **Prerequisites:** Phase 0.5 `is_official` field migration must be deployed
> before this plan begins (the Official tab and coverage grid depend on it).

---

## Design

### Goal

Replace all common legacy dashboard workflows for teachers with modern pages
inside `/teacher/...`. After this phase, a teacher should never need to visit
`/dashboard/...` for any ordinary workflow.

### Questions settled in this phase

**Q1 (official review):** Teachers submit playlists/exercises for official
review. A pending submission sets a status flag. Superusers approve or reject
from the Official tab in the Library hub. Approved content is promoted to
official and reassigned to the factory account. Normal teachers can only submit;
only superusers can approve.

**Q6 (legacy functions):** Normal teacher workflows moving into `/teacher/...`:
browse exercises/playlists, edit playlist metadata (title, tags, order,
visibility, membership), edit exercise metadata (description, tags, unit, mode,
visibility), course settings (title/dates), activity/progress report, submit for
official review, official approval queue (superuser only). Remaining
legacy/admin-only escape hatches: raw JSON editor (`Exercise.data`), chordal
analysis workbench (VexFlow debug). These are linked from the editor as
"advanced" links for admins.

---

### URL Topology

All new routes under `/teacher/library/`. Course detail tabs added inline (no
new URLs — tab state via query param or anchor).

```
/teacher/library/                   Library hub (Playlists tab default)
/teacher/library/playlists/         Playlist list (alias for hub, Playlists tab)
/teacher/library/playlists/<id>/    Playlist editor
/teacher/library/exercises/         Exercise list (alias for hub, Exercises tab)
/teacher/library/exercises/<id>/    Exercise editor
/teacher/library/official/          Official tools (alias for hub, Official tab;
                                        superuser only — 403 for others)

GET /teacher/library/exercises/<id>/preview/
    Returns { "score_data": <cir_dict> } for the exercise. Frontend restricts
    rendering to first two measures. Used by VexFlow thumbnails.

/teacher/courses/<id>/              Existing page; add Settings + Activity tabs
                                        rendered inline via ?tab=settings|activity
```

Header nav: add **Library** link to `apps/teacher/templates/teacher/base.html`
between "Courses" and "Play".

---

### Library Hub

Three-tab page at `/teacher/library/`.

**Playlists tab** — filterable list of playlists owned by or shared with the
requesting user. Columns: title, unit tag(s), mode, exercise count, official
badge, last modified. Filter controls: unit, mode, official/personal. Each row
links to the playlist editor.

**Exercises tab** — filterable list of exercises. Columns: title/description
(truncated), type badge (play/identify), unit, key, complexity (1–20), official
badge, skill tags (first 3). Filter controls: unit, type, official/personal,
analysis_review_status. Each row links to the exercise editor. Exercise rows
show a VexFlow thumbnail (lazy-loaded via `/teacher/library/exercises/<id>/preview/`).

**Official tab** (superuser only; 403 for regular teachers):
- **Pending review** section: submission cards with approve/reject buttons.
  Each card shows: title, type, submitter, submission date, exercise count/tags,
  preview link.
- **Coverage grid**: count of official playlists per unit. Highlights gaps
  (zero coverage units shown in red).

---

### Playlist Editor

`/teacher/library/playlists/<id>/`

Two-panel layout:
- **Left (sidebar):** metadata form — title, description, unit tag(s),
  visibility (private/shared/public), official status (read-only + Submit
  button), skill tags. Save button.
- **Right (main):** ordered exercise list with drag-to-reorder. Each exercise
  row shows: VexFlow thumbnail (lazy), description, type badge, key, complexity.
  Actions: remove from playlist, move to top/bottom, open exercise editor
  (opens in new tab). "Add exercises" search at the bottom opens a modal that
  searches the exercise library by description/unit/type.

Submit for official review button: enabled when playlist is public. Sets
`official_review_status="pending"` on the playlist. Button becomes disabled
"Submitted — awaiting review" until decision.

---

### Exercise Editor

`/teacher/library/exercises/<id>/`

Two-panel layout:
- **Left (sidebar):** score preview — VexFlow render of first 2 measures
  (loaded from `/teacher/library/exercises/<id>/preview/`). Below: "in
  playlists" read-only list of playlists containing this exercise.
- **Right (main):** metadata form.

Editable fields:
- Description (text)
- Unit tag (text, e.g. `unit:9`)
- Skill tags (comma-separated)
- Complexity (1–20, integer)
- Mode (dropdown: play / identify)
- Analysis type (dropdown — see below)
- Input mode (dropdown: dropdown / text)
- Visibility (private / shared / public)
- Official status (read-only badge + "Submit for review" button)

Read-only fields:
- Exercise type (play chorale / identify chordal / etc.)
- Key, meter (from UMTO Metadata)
- `analysis_review_status` (none / generated / reviewed)

Admin-only escape hatch links (shown only to superusers):
- "Edit raw JSON (admin)" → legacy `/dashboard/exercises/<id>/edit/`
- "Analysis workbench (admin)" → legacy chordal analysis view

**Analysis type dropdown options** (canonical `analysisType` token → stored/computed path):

| Label | Token | Stored in AnalysisLayer? | Computed from |
|---|---|---|---|
| Roman numeral | `roman` | `content.roman_numeral` ✓ | Teacher / music21 |
| Figured bass | `figured_bass` | `content.figured_bass` ✓ | music21 |
| Figured bass (unabbreviated) | `figured_bass_unabbreviated` | `content.raw_figured_bass` ✓ | music21 |
| Scale degree | `scale_degree` | — | Live MIDI |
| Note name | `note_name` | — | Live MIDI |
| Solfège | `solfege` | — | Live MIDI |
| Do-based solfège | `do_based_solfege` | — | Live MIDI |
| Fixed do | `fixed_do` | — | Live MIDI |
| Pitch class | `pitch_class` | — | Live MIDI |
| Set class — prime form | `set_class_prime` | `content.set_class_prime` (new, analytics) | Live MIDI / Python |
| Set class — Forte label | `set_class_forte` | `content.set_class_forte` (new, analytics) | Live MIDI / Python |
| Set class — normal order | `set_class_normal` | `content.set_class_normal` (new, analytics) | Live MIDI / Python |
| Set class — set notation | `set_class_set` | `content.set_class_set` (new, analytics) | Live MIDI / Python |
| Spacing | `spacing` | `content.spacing` (new, analytics) | Live MIDI |
| Interval (generic) | `interval_generic` | `content.interval_generic` (new, analytics) | Live MIDI via Tonal.js |
| Interval (specific) | `interval_specific` | `content.interval_specific` (new, analytics) | Live MIDI via Tonal.js |

"Stored in AnalysisLayer" = persisted for analytics. The identification grader
reads stored values only for `roman`, `figured_bass`, and
`figured_bass_unabbreviated`; all other types recompute from MIDI at runtime.
New stored fields are for metadata enrichment and future search, not grading.

**`chord_labels` deferred:** `computeWindowLabel()` in `exercise_definition.js`
has no branch for `analysisType === "chord_labels"` — it falls through to
`analyzer.to_chord(midiStack, "roman only")` which is not the correct path.
`chord_labels` is omitted from the editor dropdown in this phase. A follow-up
task must add the correct `chord_labels` branch to `computeWindowLabel` before
exposing it as an identification type.

The selected `analysisType` is stored as a top-level key in the Exercise payload
(see AnalysisLayer expansion below). Changing it and saving rewrites only that
payload key — no UMTO schema migration needed.

---

### Course Detail: Settings Tab

New inline tab on the existing `/teacher/courses/<id>/` page.

Fields: title (text), start date (date), end date (date). Save button. Delete
course button (with confirmation). No redirect to legacy dashboard.

Replaces the `dashboardEditUrl` escape hatch in `course_detail.html`.

---

### Course Detail: Activity Tab

New inline tab on the existing `/teacher/courses/<id>/` page.

Playlist selector (dropdown of playlists assigned to this course). Per-student
table: student name, progress bar (exercises attempted / total), average score
(color-coded), last active date, attempt count. Link to legacy full-report page
labeled "Full report (legacy)" for power users.

Replaces the `dashboardActivityUrl` escape hatch in `course_detail.html`.

---

### AnalysisLayer Expansion

**Data shape (corrected):** `UMTO.analysis` is `List[AnalysisSlice]` where each
`AnalysisSlice.content: AnalysisLayer`. The slice also carries `offset`,
`visual`, `unit_tags`, and `is_target`.

**How the frontend currently reads stored content** (`exercise_definition.js`):
- `analysisType === "figured_bass_unabbreviated"` → reads `slice.content.raw_figured_bass`
- `analysisType === "figured_bass"` → reads `slice.content.figured_bass`
- Anything else → falls through to `computeWindowLabel(midiStack, analysisType, ...)`,
  which computes the answer live from MIDI using `analyze.js` functions.

This means: `roman_numeral`, `figured_bass`, `raw_figured_bass` are read from
stored content; all other analysis types are computed live. The new fields
below are **not read by the identification grader in this phase** — they are
stored for analytics, metadata enrichment, and future search/filtering. A
deferred follow-up task ("stored-analysis identification mode") would wire
the frontend to read these fields instead of recomputing, if needed.

**New optional fields on `AnalysisLayer`** (`apps/exercises/umto.py`):
```python
set_class_prime: Optional[str] = None     # e.g. "(0,1,4)"
set_class_forte: Optional[str] = None     # e.g. "3-11B"
set_class_normal: Optional[str] = None    # e.g. "[0,3,7]"
set_class_set: Optional[str] = None       # e.g. "{C,E,G}"
spacing: Optional[str] = None             # output of analyze.to_spacing()
interval_specific: Optional[str] = None   # specific interval name
interval_generic: Optional[str] = None    # generic interval size
```

(`chord_label` deferred — no functional `chord_labels` path in `computeWindowLabel` yet.)

**JS compute path** (`play_sheet.js` + `play_save_logic.js`):
`buildAnalysisSlices(offsets, slots, labels, overrides)` currently has no access
to MIDI stacks. Fix: in `play_sheet.js`, before calling `buildAnalysisSlices`,
compute deterministic fields for each chord onset using the available `Analyze`
instance and the chord MIDI arrays already in scope. Pass a new
`deterministicFieldsArr` argument (array indexed by chord position). Update
`buildAnalysisSlices` signature to accept and merge this array into each output
slice's `content`.

**Python compute path** (`apps/exercises/utils/umto_import_router.py`):
`build_chordal_analysis_slices()` generates slices for non-Play paths (bulk
import, MusicXML, management commands). Expand this function to compute and
populate the same new fields using music21 (for chord label) and pure-Python
pitch math (for set class, spacing, intervals). This keeps Play-saved and
Python-generated exercises consistent.

**`analysisType` storage:** stored as `exercise.data["analysisType"]` (top-level
key in the UMTO wrapper dict, not inside `UMTO.metadata`). `to_frontend_payload()`
has no access to the outer wrapper dict — the fix lives at the serving boundary
in `lab/views.py`. Where `exercise_context["analysisType"] = _family` is set
(line ~505), first check `exercise.data.get("analysisType")` and prefer it.
This is backward-compatible — exercises without the key keep the heuristic.

---

### VexFlow Score Thumbnails

The preview endpoint `GET /teacher/library/exercises/<id>/preview/` returns
`{ "score_data": <cir_dict> }` from the UMTO exercise. The frontend renders it
using the existing VexFlow adapter, restricted to the first 2 measures. Lazy-
loaded in the playlist editor and library list: thumbnail images are requested
only when the row scrolls into view (Intersection Observer). Render target: a
`<canvas>` 220px wide × 120px tall. No new dependencies; VexFlow is already
bundled.

---

### Official Review Flow (end-to-end)

```
Teacher clicks "Submit for review"
  → POST /teacher/library/playlists/<id>/submit-review/
  → sets Playlist.official_review_status = "pending"
  → button disables

Superuser visits /teacher/library/ → Official tab
  → sees pending submissions card list
  → clicks "✓ Approve"
    → POST /teacher/library/playlists/<id>/approve/
    → sets Playlist.is_official = True
    → sets Playlist.authored_by = factory account
    → sets official_review_status = "approved"
  → or clicks "✗ Reject"
    → POST /teacher/library/playlists/<id>/reject/
    → sets official_review_status = "none"
    → teacher's submit button re-enables
```

Same flow applies to individual exercises submitted from the exercise editor.

**Model changes needed** (on `Playlist` and `Exercise`):
- `official_review_status`: Literal["none", "pending", "approved", "rejected"]
  default "none". (Phase 0.5 adds `is_official`; this phase adds the status
  field.)

---

## Implementation Plan

### 0. Prerequisites

- [ ] Confirm Phase 0.5 `is_official` migration is deployed. [Tier 2 — verify, unblock]

---

### 1. Model + API foundations

- [ ] Add `official_review_status` field to `Exercise` and `Playlist` models;
  migration. Default "none". [Tier 2]
- [ ] Add `GET /teacher/library/exercises/<id>/preview/` view returning
  `{ "score_data": <cir> }`. Requires staff login. [Tier 2]
- [ ] Add `POST /teacher/library/playlists/<id>/submit-review/`,
  `/approve/`, `/reject/` endpoints. Superuser check on approve/reject.
  [Tier 2]
- [ ] Add same submit/approve/reject endpoints for exercises. [Tier 2]
- [ ] Expand `AnalysisLayer` in `apps/exercises/umto.py` with 7 new optional
  fields (set_class_prime/forte/normal/set, spacing, interval_specific,
  interval_generic). Run `python manage.py make_umto_schema` to regenerate
  schema. [Tier 2]
- [ ] Fix `analysisType` serving boundary in `lab/views.py`: at the line
  `exercise_context["analysisType"] = _family` (~line 505), first check
  `exercise.data.get("analysisType")` and prefer that value. The
  `to_frontend_payload()` method cannot access the outer wrapper dict; the fix
  belongs at the view layer. [Tier 2]

---

### 2. `buildAnalysisSlices` expansion

- [ ] In `lab/static/js/src/components/music/play_sheet.js`, before calling
  `buildAnalysisSlices`, compute deterministic fields for each chord onset using
  the available `Analyze` instance and the chord MIDI arrays already in scope
  (the same arrays used to drive the ANALYZE panel). Build a
  `deterministicFieldsArr` indexed by chord position containing
  `{ set_class_set, set_class_normal, set_class_prime, set_class_forte,
  spacing, interval_specific, interval_generic }` using
  existing `analyze.js` exports. [Tier 2]
- [ ] Update `buildAnalysisSlices(offsets, slots, labels, overrides)` in
  `lab/static/js/src/components/music/play_save_logic.js` to accept a 5th
  argument `deterministicFieldsArr` and merge those fields into each output
  slice's `content`. Update the single call site in `play_sheet.js`. [Tier 2]
- [ ] Expand `build_chordal_analysis_slices()` in
  `apps/exercises/utils/umto_import_router.py` to compute and populate the same
  8 new AnalysisLayer fields using music21 (for chord_label) and pure-Python
  pitch math (for set class, spacing, intervals). This ensures Python-generated
  exercises (bulk import, MusicXML, management commands) have the same stored
  fields as Play-saved exercises. [Tier 2]
- [ ] Verify the expanded slices pass through `lab/views.py` AddExercise →
  `save_chordal_umto_exercise` without Pydantic rejection. [Tier 2]
- [ ] Add `analysisType` to the save payload in `play_sheet.js` (reads from the
  currently selected analysis type in the teacher's session UI). [Tier 2]

---

### 3. Library hub

- [ ] Add `apps/teacher/views/library.py` with list views:
  `LibraryHubView`, `PlaylistListView`, `ExerciseListView`,
  `OfficialToolsView`. [Tier 2]
- [ ] Register URLs in `apps/teacher/urls.py`:
  `/library/`, `/library/playlists/`, `/library/exercises/`,
  `/library/official/`. [Tier 2]
- [ ] Add "Library" link to teacher header nav in
  `apps/teacher/templates/teacher/base.html`. [Tier 1]
- [ ] Template `apps/teacher/templates/teacher/library_hub.html`:
  three-tab layout (Playlists, Exercises, Official). Official tab 403s for
  non-superusers. [Tier 2]
- [ ] Playlists tab: filterable list, columns per spec. [Tier 2]
- [ ] Exercises tab: filterable list, columns per spec, lazy VexFlow thumbnail
  via Intersection Observer + fetch of `/preview/` endpoint. [Tier 2]
- [ ] Official tab: pending submission cards + unit coverage grid. [Tier 2]
- [ ] Test: regular teacher gets 403 on `/library/official/`. [Tier 1]

---

### 4. Playlist editor

- [ ] Add `PlaylistDetailView` to `apps/teacher/views/library.py`;
  URL `/library/playlists/<id>/`. [Tier 2]
- [ ] Template `apps/teacher/templates/teacher/playlist_editor.html`:
  two-panel layout (sidebar metadata form + exercise list). [Tier 2]
- [ ] Drag-to-reorder: use existing Sortable.js or browser-native drag API;
  POST reorder to `/teacher/library/playlists/<id>/reorder/`. [Tier 2]
- [ ] "Add exercises" modal: search endpoint
  `GET /teacher/library/exercises/?q=<term>&unit=<n>` returns JSON list;
  POST to `/teacher/library/playlists/<id>/add-exercise/`. [Tier 2]
- [ ] VexFlow thumbnails in exercise rows (same lazy pattern as hub). [Tier 2]
- [ ] "Submit for review" button (calls submit-review endpoint). [Tier 2]

---

### 5. Exercise editor

- [ ] Add `ExerciseDetailView` to `apps/teacher/views/library.py`;
  URL `/library/exercises/<id>/`. [Tier 2]
- [ ] Template `apps/teacher/templates/teacher/exercise_editor.html`:
  two-panel layout (score thumbnail sidebar + metadata form). [Tier 2]
- [ ] Metadata form: all editable fields per spec (description, unit, skill
  tags, complexity, mode, analysisType, input_mode, visibility). [Tier 2]
- [ ] analysisType dropdown: full 16-option list per spec. On save, PATCH
  `/teacher/library/exercises/<id>/` writing only top-level `payload["analysisType"]`
  plus all editable Metadata fields. [Tier 2]
- [ ] "Submit for review" button. Admin escape hatch links (superuser only). [Tier 2]
- [ ] "In playlists" sidebar panel: list playlists containing this exercise
  (reverse relation query). [Tier 2]

---

### 6. Course detail tabs

- [ ] Settings tab: add to `apps/teacher/templates/teacher/course_detail.html`;
  form for title/start_date/end_date; POST to existing course update view or
  new `CourseSettingsView`. Remove `dashboardEditUrl` escape hatch. [Tier 2]
- [ ] Activity tab: add to `course_detail.html`; playlist selector dropdown;
  per-student table (progress %, avg score, last active, attempts). Query:
  `PerformanceData.objects.filter(Q(course=self) | Q(course=None, playlist__in=...))`,
  same pattern as `Course.refresh_performance_dict()` (`apps/exercises/models.py:1237`)
  and `Course.add_performance_to_dict()` (`apps/exercises/models.py:1168`). [Tier 2]
- [ ] Remove `dashboardActivityUrl` escape hatch (replace with new Activity
  tab; keep "Full report (legacy)" link for power users). [Tier 1]

---

### 7. Backfill

- [ ] Management command `backfill_analysis_layer` (Tier 1): for each UMTO
  chordal exercise, re-run `build_chordal_analysis_slices` to populate new
  AnalysisLayer fields. Safe to re-run; skips exercises with no score_data.
  Add entry to `docs/management_commands.md`. [Tier 1]

---

### 8. Docs + cleanup

- [ ] Update `docs/exercise_types.md`: note that `analysisType` is now stored
  explicitly as `payload["analysisType"]`. [Tier 1]
- [ ] Update `docs/UMTO_GUIDE.md`: document new AnalysisLayer fields. [Tier 1]
- [ ] Add Phase 3 entries to `docs/management_commands.md` (backfill command).
  [Tier 1]
- [ ] Retrospective plan: mark tasks `[x]` as completed. [Tier 1]

---

## Scope boundary

**In scope:** library hub, playlist/exercise editors, course settings/activity
tabs, AnalysisLayer expansion, VexFlow thumbnails, official review flow.

**Out of scope (deferred):** export/import of playlists, bulk exercise
operations, exercise connections/links between exercises, exercise duplication
from this editor (use existing play/ save flow), CSS identity overhaul (Phase 5),
"stored-analysis identification mode" (wiring `exercise_definition.js` to read
new AnalysisLayer fields instead of live-computing for chord_labels/set_class/
spacing/intervals identification exercises).

**Escape hatches retained (legacy, not replaced):** raw JSON editor, chordal
analysis workbench. These remain at `/dashboard/...` and are linked from the
exercise editor for admin users only.
