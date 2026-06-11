# Student-Side Course Connection — /s/ meets Course

**Goal:** Enrolled students see their course's schedule on the student app:
due/opens chips on unit cards, a student-styled `/s/join/?code=` enrollment
page, and correct course attribution when a playlist sits in several courses.

**Decision (pinned):** Courses do NOT gate unit availability — factory
playlists stay public and every unit remains open to open learners. A course
adds publish/due dates (sequencing) and grading attribution only. Revisit
gating at the multi-teacher stage.

**Roadmap context:** Phase 5; implemented directly by the orchestrator
(highest regression risk — live students). Retrospective plan per repo rules.

## What landed

- [x] `_get_course_unit_dates(user)` (apps/student/views.py): one constant
      PCO join (groups → visible courses → PCO → playlist `unit:N` tags) →
      `{unit_n: {due, publish, published, course_title}}`, earliest due wins.
      Home query budget moved 4 → 5 (constant, not O(units); budget test
      updated with comment).
- [x] `_unit_date_labels()` → `due_label` ("Due Sun Oct 12") / `opens_label`
      ("Opens …" when publish is future) / `overdue` flag; merged into both
      home unit-card dicts; `.s-due-chip` styles in student/home.html.
- [x] `JoinCourseView` at `/s/join/` (`student:join`): student-styled
      (tokens), `?code=` deep link prefill (uppercased), idempotent join,
      teacher-of-group blocked; template student/join.html. Teacher course
      page's "Copy join link" points here.
- [x] `resolve_course_for_playlist(user, playlist)`: prefers a course the
      user is enrolled in over bare `.first()` — fixes grading attribution
      when one playlist is in multiple courses. Both PlayerView and
      PlayerDefinitionView use it.
- [x] 15 tests in apps/student/tests/test_course_connection.py; full suite
      686/686 green (no behavior change for non-enrolled users).
