# Student Course Experience — Design Spec

**Date:** 2026-06-14  
**Priority:** CLAUDE.md Priority #4

---

## Goal

Students enrolled in a course land in a course-focused experience, not the full curriculum.
Course assignments, open/due states, progress, and next work must be obvious from the home page
and from a per-course detail page.

---

## Scope

Two surfaces:

1. **Home page** (`/s/`) — course panels become navigation cards to the course detail page.
   Full curriculum becomes secondary (collapsed) for enrolled students.
2. **Course detail page** (`/s/courses/<pk>/`) — new view and template; the assignment hub.

No new models or migrations needed.

---

## Home Page Changes

### Panel data

Extend `_build_course_panels` to add `course_pk` (Django auto PK, **not** `Course.id` which is a
nullable char code field) to each panel dict.

Panel dict shape (additions in bold):

```python
{
    "title": course.title,
    "progress_pct": avg_pct,         # averaged across all PCO rows (see below)
    "open_count": int,               # open assignments with progress < 100%
    "due_count": int,                # open assignments that have a due_date set
    "overdue_count": int,            # open assignments past due_date
    "course_pk": course.pk,          # NEW — used for /s/courses/<pk>/ link
    # (open_units / next_unit removed from home panel)
}
```

`avg_pct` is averaged across **all PCO rows** for this course, not distinct unit numbers, so that
multiple playlists for the same unit each contribute equally to the average.

### Template (`home.html`)

Course panel becomes a navigation card. Clicking anywhere on it goes to `/s/courses/<pk>/`.

Show inside the card:
- Course title (as the link text)
- `progress_pct`% complete
- Badge line: "N open · M due" (where M = `due_count`; omit if 0)
- If `overdue_count > 0`: red "X overdue" chip

Remove the inline "Next up" unit row and the collapsible unit list — those live on the course page.

### Curriculum secondary for enrolled students

When `course_panels` is non-empty, wrap the `<div class="s-catalog">` in a `<details>` element:

```html
{% if course_panels %}
<details class="s-curriculum-collapse">
  <summary>Browse all units</summary>
  <div class="s-catalog">...</div>
</details>
{% else %}
<div class="s-catalog">...</div>
{% endif %}
```

Students without a course: home unchanged (no `<details>` wrapper).

---

## Course Detail Page

### URL

```python
path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
```

Uses Django auto PK (`int:pk`). `Course.id` (the nullable char code) is never used in URLs.

### View — `CourseDetailView`

```python
class CourseDetailView(View):
    @_require_student
    def get(self, request, pk):
        ...
```

**Enrollment check:** query
`Course.objects.filter(pk=pk, visible_to__members=request.user).select_related("authored_by").distinct()`.
Return 404 if no course found (student not enrolled). An enrolled student in a course with no
assignments renders the page with empty assignment sections — never a 404.

**PCO rows:** separate query:
`PlaylistCourseOrdered.objects.filter(course=course).select_related("playlist").order_by("order", "pk")`.

**Playlist progress:** call `_batch_playlist_data(user, playlists)` + `_playlist_stats(playlist, raw[playlist.pk])`
from `apps/student/unit_progress.py` (3-query batch, handles Unit-4 served-order semantics, primes
`untransposed_exercises_ids` cache). Extract `done / total` for each playlist's percent.
`_playlist_stats` also returns a pre-built `url` (with correct `next_exercise_num`) — use it
directly as `play_url`.
Do **not** use `_get_course_unit_dates()` here; use each PCO's own `publish_date` / `due_date`.

**Status per PCO:**

| Status | Criteria |
|---|---|
| `upcoming` | `publish_date` is not None AND `publish_date > now` |
| `completed` | `progress_pct >= 100` (regardless of dates) |
| `open` | everything else (published and not complete) |

Overdue flag: `status == "open"` AND `due_date is not None` AND `due_date < now`.

**Assignment row dict:**

```python
{
    "playlist_id": pco.playlist.id,
    "name": pco.playlist.name,
    "order": pco.order,
    "status": "open" | "upcoming" | "completed",
    "overdue": bool,
    "progress_pct": int,           # min(100, done*100//total) from _playlist_stats; 0 if total==0
    "due_label": str | None,       # e.g. "Due Mon Jun 16" or None
    "opens_label": str | None,     # e.g. "Opens Fri Jun 19" or None
    "play_url": str | None,        # url from _playlist_stats; None if upcoming
}
```

**Teacher name:**

```python
author = course.authored_by
teacher_name = author.get_full_name() or author.email
```

**Context:**

```python
{
    "course": course,
    "teacher_name": teacher_name,
    "overall_pct": int,            # avg of all PCO progress_pcts
    "open_assignments": [...],     # status == "open", order preserved
    "upcoming_assignments": [...], # status == "upcoming"
    "completed_assignments": [...],# status == "completed"
}
```

### CTA links (play URL)

`play_url` comes directly from `_playlist_stats(playlist, raw[playlist.pk])["url"]`.
That function already resolves `next_exercise_num` (first incomplete exercise in served order) and
builds the correct `/s/units/<unit_n>/play/?playlist=<id>&exercise_num=<n>` URL, including
Unit-4 shuffle semantics.

Label: "Start →" if `progress_pct == 0`, else "Continue →".

`upcoming` assignments: `play_url = None`, no CTA rendered.  
`completed` assignments: show "Review →" using the same `play_url`.

---

## Playlist Progress — No New Helper

No new `_batch_playlist_summaries` function. Use the existing infrastructure from
`apps/student/unit_progress.py`:

```python
from apps.student.unit_progress import _batch_playlist_data, _playlist_stats

raw_by_pk = _batch_playlist_data(user, playlists)   # 3 queries total
for pco in pcos:
    pl = pco.playlist
    stats = _playlist_stats(pl, raw_by_pk[pl.pk])
    progress_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0
    play_url = stats["url"]   # already built with correct next_exercise_num
```

`_batch_playlist_data` fires exactly 3 queries regardless of playlist count:
`PerformanceData`, `IdentificationAttempt`, `ExercisePlaylistOrdered`. It also primes
`untransposed_exercises_ids` cache and applies Unit-4 serving-order semantics via
`get_ordered_exercise_ids_for_serving`.

Update the test `test_batch_playlist_summaries` → `test_playlist_progress_via_unit_progress`
to reflect this (no new public function to test; test `CourseDetailView` context values instead).

---

## Template (`student/course_detail.html`)

Extends `student/base.html`. Uses existing student CSS variables only.

**Header:** course title + teacher name + overall % progress bar.

**Three sections (status-grouped):**

```
● Open now      (red section label if any overdue)
  [assignment row with progress bar + Continue/Start CTA]
  ...

○ Upcoming
  [greyed-out rows with "Opens [date]" chip, no CTA]
  ...

✓ Completed
  [muted rows with green checkmark + Review link]
  ...
```

Sections with no assignments are omitted entirely.

---

## "M due" definition

`due_count` = number of open assignments (status == "open") where `due_date is not None`.
Overdue assignments (due_date < now) are included in this count and also in `overdue_count`.
"M due" on the home panel omits the count entirely when M == 0.

---

## Tests

File: `apps/student/tests/test_course_detail.py`

| Test | Assertion |
|---|---|
| `test_enrolled_student_can_view` | 200 for enrolled student |
| `test_unenrolled_student_gets_404` | 404 for non-member |
| `test_status_grouping_open` | published PCO with progress < 100 → open |
| `test_status_grouping_upcoming` | publish_date in future → upcoming |
| `test_status_grouping_completed` | 100% progress → completed |
| `test_overdue_flag` | due_date < now → overdue=True |
| `test_teacher_name_fallback` | author with no name → email used |
| `test_batch_playlist_summaries` | correct percent from PerformanceData |
| `test_home_panel_links_to_course_page` | panel href contains /s/courses/<pk>/ |
| `test_home_curriculum_collapsed_when_enrolled` | `<details>` wrapper present |

---

## Files to change

| File | Change |
|---|---|
| `apps/student/views.py` | Extend `_build_course_panels`; add `CourseDetailView` (uses `unit_progress._batch_playlist_data`) |
| `apps/student/urls.py` | Add `courses/<int:pk>/` route |
| `apps/student/templates/student/home.html` | Course panels → nav cards; curriculum in `<details>` |
| `apps/student/templates/student/course_detail.html` | New template |
| `apps/student/tests/test_course_detail.py` | New test file |
