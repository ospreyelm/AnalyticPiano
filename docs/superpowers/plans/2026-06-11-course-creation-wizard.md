# Course Creation Wizard — /teacher/courses/new/

**Goal:** Unit-first course creation: teacher picks units from the taxonomy +
semester dates; wizard auto-attaches factory playlists per unit and spreads
publish/due dates; single transactional POST creates Course +
PlaylistCourseOrdered rows. New `apps/teacher` app using the student design
tokens. Old dashboard untouched.

**Roadmap context:** Phase 2 of the production roadmap. Prereqs landed:
factory library packaging (2026-06-10 plan), `ensure_factory_account`,
tokens.css.

## Architecture

- New Django app `apps/teacher/`: `urls.py`, `views.py`, `scheduling.py`,
  `templates/teacher/`, `static/teacher/teacher.css` (imports
  `student/tokens.css`). Mounted in `harmony/urls.py` ABOVE the lab include;
  move the `teacher/play/` alias check — lab's route must keep working
  (Django url resolution: first match wins, so mount `apps/teacher` urls under
  `teacher/` and re-expose `play/` from within it OR keep lab's path and use a
  distinct prefix ordering — verify resolution, add a url test).
- `teacher_required` decorator: `user.role == ROLE_TEACHER` (or superuser);
  redirect to login otherwise.
- Wizard = ONE template with client-side steps (vanilla JS), single JSON POST
  to the create endpoint. No django-formtools, no dashboard ManyField forms.

## Steps (UI)

1. Title, semester start/end (`<input type="date">`), optional "create student
   group" (name + auto `join_code`, reuse `apps.accounts.models.Group`).
2. Unit picker from `TaxonomyReader` branches→tiers→units; each unit annotated
   with factory playlist count + modes (`Playlist.objects.filter(
   authored_by=factory, skill_tags__contains=[f"unit:{n}"])`). Zero-coverage
   units shown but flagged. Default: all factory playlists of a selected unit
   attached (roman→figures→play→play_figures order), checkboxes to prune.
3. Schedule preview table (unit → publish → due), inline-editable dates.
4. Create → POST → redirect to course page (Phase 3; until then, dashboard
   course edit URL).

## Date spreading (`apps/teacher/scheduling.py`)

Pure function, no Django imports beyond stdlib/datetime:
`spread_schedule(start: date, end: date, n_units: int, *, due_weekday: int = 6,
publish_all_at_start: bool = False) -> list[Window]` where
`Window = (publish_date: date, due_date: date)`:
- Divide [start, end] into n equal windows.
- Due date = last `due_weekday` (default Sunday) on or before window end;
  always > window start; final window's due ≤ end.
- Publish = window start, or `start` for all when `publish_all_at_start`.
- Edge cases: n_units=1; semester shorter than n weeks (windows < 7 days →
  due = window end date); start==end invalid (ValueError).

## Create endpoint

POST `/teacher/courses/create/` JSON:
```json
{"title": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD",
 "groupName": str|null,
 "units": [{"unit": 9, "playlistIds": ["PA..."],
            "publish": "YYYY-MM-DD", "due": "YYYY-MM-DD"}, ...]}
```
Transactional: create `Course(authored_by=user, open=False, start_date,
end_date)`; optional Group (manager=user) + add to `visible_to`; one PCO per
playlist with sequential `order`, timezone-aware publish/due datetimes
(due at 23:59 local, publish at 00:00 — use `django.utils.timezone`).
Validation errors → 400 JSON. Mirrors `apps/dashboard/views/courses.py:87-110`
PCO creation but with ISO date parsing.

## Migration (only schema change)

Nullable `Course.start_date`, `Course.end_date` (DateField) in
`apps/exercises/models.py` + migration. Nothing else.

## Tasks

- [x] Task 1: `apps/teacher/scheduling.py` + 11 unit tests (orchestrator wrote
      it directly after the Codex background runs kept getting killed)
- [x] Task 2 (Sonnet): scaffold, urls mount (+ test that /teacher/play/ still
      resolves to lab PlayView), teacher_required, Course.start_date/end_date
      migration 0065, create endpoint, 23 DB tests
- [x] Task 3 (Sonnet): teacher/base.html + course_wizard.html +
      teacher.css (.t-* on tokens) + course_wizard.js (vanilla, 4-step)
- [x] Task 4 (orchestrator): review (removed dead csrf_exempt import — CSRF is
      enforced on the create POST), full suite 624/624 green. Browser smoke
      deferred to post-merge (dev server serves the main checkout).
