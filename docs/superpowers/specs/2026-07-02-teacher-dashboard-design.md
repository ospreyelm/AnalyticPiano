# Teacher Class Progress Dashboard — Design Spec

**Date:** 2026-07-02
**Status:** Draft — awaiting product owner review, not authorized for implementation
**Feature scope:** Teacher-facing class/student progress view inside `apps/teacher`.

---

## Constraint that shapes this whole spec

AGENTS.md is explicit: *"Work started in `/teacher/...` stays in the teacher
app. Do not route normal teacher workflows through `/dashboard/...`."*

There is a legacy `apps/dashboard` app that already has per-student
performance views — `course_activity_view`
(`apps/dashboard/views/courses.py:287-339`, builds a per-performer table
from `course.performance_dict`, filterable by group) and
`performances_list_view` / `playlist_performance_view`
(`apps/dashboard/views/performance.py:18-70+`, shows a student's
playlist-by-playlist pass/fail history). This is real prior art for what
data a "class progress" view needs — but it is legacy code, keyed off
`course.performance_dict` (a denormalized JSON blob) and `error_tally`
pass/fail logic that predates the mastery engine. **This spec is not "add
a link to the old dashboard from the teacher app."** It's "build the
equivalent view natively in `apps/teacher`, sourced from
`StudentSkillMastery` — the same data source the student-facing pages
already use" — and treat the legacy `apps/dashboard` views as a retirement
candidate once the new view covers their use cases (per the
replacement/retirement policy in `docs/architecture/engineering-principles.md`).

---

## Current state of `apps/teacher`

`apps/teacher/urls.py` has `course-list`, `course-detail`, plus
library/playlist-review routes. **No student-progress endpoint exists.**
`course_detail_view` (`apps/teacher/views.py:271+`) currently builds PCO
rows (assignment metadata: playlist, publish/due dates, order) and a
groups/roster payload (`_serialize_course_groups`), rendered by
`teacher/course_detail.html` with "Timeline" and "Roster" tabs
(lines 41-44, 130+). `roster.js` renders group membership and join codes
only — no per-student mastery or completion data. `timeline.js` renders
the assignment schedule, not scores.

So the natural landing spot is a **third tab** on the existing course
detail page — "Progress" — next to Timeline and Roster, not a new
top-level route. This matches how the page is already organized around one
course at a time.

---

## Proposed: `Progress` tab on `/teacher/courses/<course_id>/`

### Data needed, and where it already exists

| Column | Source |
|---|---|
| Student roster for this course | `course.visible_to` groups → `Group.members` (same relation `_serialize_course_groups` already walks for the Roster tab) |
| Per-assignment (PCO) completion % | `_batch_playlist_data` + `_playlist_stats` (`apps/student/unit_progress.py:142-289`) — **already computed for the student-facing course page**, reusable as-is per student |
| Per-skill mastery level | `StudentSkillMastery` filtered by `user__in=roster, skill_tag__in=<course's taxonomy tags>` — one query for the whole class, same shape as `_batch_skill_levels` but batched across users instead of one |
| Last activity / recency | `StudentSkillMastery.last_practiced`, or `PerformanceData.created` max per user |

**No new models required.** This is a query-and-aggregate view over
existing tables, the same way the student dashboard spec's Part B is.

### View shape

```python
# apps/teacher/views.py (or a new apps/teacher/progress.py service module,
# per the "extract focused service" guidance in AGENTS.md rather than
# growing views.py further)

def course_progress_view(request, course_id):
    course = get_object_or_404(Course, id=course_id, authored_by=request.user)
    roster = _course_roster(course)  # same group-walk as roster.js's data source
    pcos = PlaylistCourseOrdered.objects.filter(course=course).select_related("playlist")

    # one row per student: {name, per-assignment %, overall %, last_active}
    rows = _build_class_progress_rows(roster, pcos)
    ...
```

`_build_class_progress_rows` is new but thin: for each student, call the
same `_batch_playlist_data`/`_playlist_stats` pair the student pages use
(so a teacher's "72%" and the student's own "72%" are guaranteed to be the
same number, computed by the same code — no parallel logic, per AGENTS.md's
"prefer one shared service over parallel logic" rule).

### Table layout (matches the existing Roster tab's plain-table style)

```
Progress                                          [Group filter ▾]

Student          Assignment 1   Assignment 2   Assignment 3   Overall   Last active
────────────────────────────────────────────────────────────────────────────────────
Ana García            94%            78%          Not started    58%    2 hours ago
Sam Lee                — (upcoming)   —              —            —     —
Priya Nair            100%           100%           45%           82%   Yesterday
```

**Name column depends on what the LTI-connected institution actually
releases** (see `2026-07-02-student-dashboard-lti-design.md`'s revised
identity section). For a student provisioned via an "anonymous"-mode LTI
launch, `User.get_full_name()` will be blank — fall back to the same
non-identifying label used elsewhere (`Student <hash>`), not to email or
any other field that might inadvertently carry PII the institution chose
not to release. A teacher in that configuration cross-references against
their own Moodle/Canvas gradebook to know who's who; that's a real
usability cost of the strict-privacy mode and the institution's tradeoff
to make, not something this view should try to work around by pulling
identity from somewhere else.

- Reuse the existing `status` concept from
  `2026-06-14-student-course-experience-design.md` (`open` / `upcoming` /
  `completed`) per assignment cell.
- Group filter reuses the same `Group` queryset/filter pattern
  `course_activity_view` already has (`CourseActivityGroupsFilter`) — this
  is the one piece of the legacy dashboard worth porting forward as-is,
  since it's generic filtering logic, not performance-computation logic.
- Clicking a student name could deep-link to a per-student detail (skill
  mastery breakdown), but that is a **v2 stretch**, not required for the
  class-overview table to be useful. Flag as open question below.

### Skill mastery summary (secondary section, below the assignment table)

A compact grid: rows = skill tags in this course's units, columns = mastery
tier, cells = count of students at that tier. Gives the teacher a
"where is the class stuck" view that the assignment-completion table alone
doesn't answer (a student can be "78% done" with an assignment while still
`not_started` on the actual skill, if e.g. they're grinding an adaptive
pool without hitting the mastery threshold). This is the class-level
mirror of the segmented bar students already see on `/s/units/<n>/`.

---

## LTI angle (per product owner's framing: "with an eye toward LTI
integration")

If the LTI groundwork from
`2026-07-02-student-dashboard-lti-design.md` (Part A) is built, an
instructor's LTI launch (role = Instructor) should land here — on
`/teacher/courses/<course_id>/?tab=progress` for the course tied to that
LMS assignment — rather than requiring the teacher to separately log into
HarmonyLab and navigate. That's a routing decision at LTI-launch time
(Part A's `services.py`/`views.py`), not a change to this view. No design
changes needed in this spec to accommodate it, beyond confirming the view
is reachable by a plain course-scoped URL with no required query state
(it already is).

---

## Retirement path for legacy `apps/dashboard` performance views

Per AGENTS.md's replacement/retirement policy: once the new Progress tab
covers `course_activity_view`'s use case (per-student, per-course,
group-filterable performance table), `course_activity_view` and its
`performance_dict`-based computation become a second, stale source of
truth for the same information. Recommend:
1. Ship the new tab.
2. Confirm with the product owner that no current workflow still depends
   on `/dashboard/courses/<id>/activity/` specifically.
3. Redirect or remove the legacy route in a follow-up change — not bundled
   into this feature's initial PR, to keep the diff reviewable.

`performances_list_view`/`playlist_performance_view` (individual student
drill-down, pass/fail by playlist) are a separate concern from the class
table and are not necessarily superseded by this spec — only
`course_activity_view` maps directly onto the new Progress tab.

---

## Open questions for product owner

1. Per-student drill-down (click a name → skill-level breakdown for that
   one student) — v1 or v2?
2. Should the Progress tab's "overall %" match `CourseDetailView`'s
   `overall_pct` definition (average of PCO progress_pcts) exactly, so a
   teacher and a student are looking at literally the same formula? (This
   spec assumes yes.)
3. Retire `apps/dashboard.course_activity_view` now, later, or leave
   indefinitely as an admin-only fallback?

---

## Out of scope

- Any change to assignment/playlist data models (Assignment Slot
  Foundation work remains unauthorized per AGENTS.md).
- CSV/gradebook export — natural follow-on, not requested yet.
- Real-time updates (this is a page-load snapshot, not live-updating).

---

## Files to change (implementation-time)

| File | Change |
|---|---|
| `apps/teacher/progress.py` (new) | `_build_class_progress_rows`, skill-mastery-grid aggregation — thin service module, reuses `apps/student/unit_progress.py` functions |
| `apps/teacher/views.py` | Extend `course_detail_view` (or add a sibling view) to serve the Progress tab's data |
| `apps/teacher/templates/teacher/course_detail.html` | Add "Progress" tab alongside Timeline/Roster |
| `apps/teacher/static/teacher/modules/progress.js` (new, keep under 400-line limit) | Renders the assignment table + mastery grid, mirrors `roster.js`/`timeline.js` module pattern |
| `apps/teacher/tests/` | New coverage for `_build_class_progress_rows` and the tab view |
