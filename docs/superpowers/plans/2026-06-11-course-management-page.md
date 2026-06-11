# Course Management Page — /teacher/courses/

**Goal:** Teacher's day-to-day course home replacing dashboard course editing
for common operations: list courses, unit timeline with date editing and
reordering, re-spread remaining dates, add playlists, roster with join code,
activity summary. New-design (tokens); dashboard remains the power tool.

**Roadmap context:** Phase 3. Prereqs landed: course wizard (2026-06-11 plan),
`Course.start_date/end_date`, `apps/teacher` app.

## Pages & endpoints (all `teacher_required`, author-scoped)

- GET `/teacher/courses/` — list view: teacher's courses (authored_by), title,
  semester window, unit count, student count (sum of visible_to groups'
  members), link to detail + "New course" → wizard.
- GET `/teacher/courses/<course_id>/` — detail: vertical timeline of PCO rows
  ordered by `order`: playlist name, mode badge, publish/due (inline date
  inputs), drag handle, remove button. Side panels: roster (groups, members,
  join code + copy link `/s/join/?code=...`), activity summary
  (course.performance_dict cache — read only, never recompute), link to
  dashboard course edit + activity for deep dives.
- POST `/teacher/courses/<course_id>/update-pco/` — JSON
  `{"changes": [{"pcoId": int, "publish": "YYYY-MM-DD"|null,
  "due": "YYYY-MM-DD"|null, "order": int|null}], "removals": [pcoId...]}`
  — update_or_create pattern per dashboard courses.py:170-205; tz-aware
  datetimes as in wizard create.
- POST `/teacher/courses/<course_id>/respread/` — JSON `{"fromOrder": int,
  "publishAllAtStart": bool}`: re-spread publish/due of PCO rows with
  `order >= fromOrder` across [today or window start, course.end_date] via
  `scheduling.spread_schedule`; 400 if course.end_date missing.
- POST `/teacher/courses/<course_id>/add-playlist/` — JSON `{"playlistId",
  "publish", "due"}`: append PCO at next order. Playlist must be authored by
  teacher, factory user, or be public.

Authorization: every endpoint 404s courses not authored by request.user
(superuser sees own only too — keep simple).

## UI

`apps/teacher/templates/teacher/course_list.html` + `course_detail.html`
(extend teacher/base.html), `course_detail.js` (vanilla; drag-reorder via
HTML5 drag events writing order ints; save batches changes per action).
Styles extend `teacher.css` `.t-*` vocabulary.

## Tasks

- [x] Task 1 (Sonnet): views + urls + 47 tests (list/detail context, update-pco,
      respread via scheduling.spread_schedule, add-playlist, authz 404s)
- [x] Task 2 (Sonnet): course_list/course_detail templates + course_detail.js
      (drag-reorder timeline, batch save, re-spread, add playlist, roster with
      copy-join-link, defensive activity table) + .t-* css additions
- [x] Task 3 (orchestrator): review, full suite 686/686 green, commit
