# Student Course Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give enrolled students a course-focused home page and a per-course assignment hub at `/s/courses/<pk>/`.

**Architecture:** Extend `_build_course_panels` with counts/pk for the home nav card, add `CourseDetailView` that verifies enrollment via `Course.objects.filter(visible_to__members=user)`, fetches PCOs, computes per-playlist progress using existing `_batch_playlist_data`/`_playlist_stats` from `unit_progress.py`, groups assignments into open/upcoming/completed, and renders a new template. Home wraps the curriculum grid in `<details>` for enrolled students.

**Tech Stack:** Django (CBV), existing student CSS variables, `apps/student/unit_progress._batch_playlist_data` + `_playlist_stats`, no new models/migrations.

---

## File Map

| File | Action | What changes |
|---|---|---|
| `apps/student/views.py` | Modify | Extend `_build_course_panels`; add `CourseDetailView` |
| `apps/student/urls.py` | Modify | Add `courses/<int:pk>/` route |
| `apps/student/templates/student/home.html` | Modify | Course panels → nav cards; curriculum in `<details>` |
| `apps/student/templates/student/course_detail.html` | Create | New assignment-hub template |
| `apps/student/tests/test_course_detail.py` | Create | Tests for new view + home panel changes |

---

## Task 1: Tests for `_build_course_panels` extension (TDD)

**Files:**
- Create: `apps/student/tests/test_course_detail.py`

These tests verify the panel dict shape before we change any code.

- [ ] **Step 1.1: Create test file with setUp**

```python
# apps/student/tests/test_course_detail.py
"""Tests for the course detail view and home panel changes."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now

from apps.accounts.models import Group
from apps.exercises.models import (
    Course,
    ExercisePlaylistOrdered,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
)

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class HomePanelTests(TransactionTestCase):
    """Home page course panel becomes a nav card to /s/courses/<pk>/."""
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=30001, email="alex@test.com", password="pw", is_staff=False
        )
        self.teacher = User.objects.create_user(
            id=30002, email="prof@test.com", password="pw", is_staff=False
        )
        self.group = Group.objects.create(name="Theory 2026", manager=self.teacher)
        self.group.members.add(self.student)
        self.course = Course(title="Music Theory I", authored_by=self.teacher, open=False)
        self.course.save()
        self.course.visible_to.add(self.group)
        self.playlist = Playlist(
            name="Unit 9 — Roman", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9"],
        )
        self.playlist.save()
        self.client.force_login(self.student)
```

- [ ] **Step 1.2: Add panel link test**

Append to the test file:

```python
    def test_home_panel_links_to_course_detail(self):
        """Course panel href must point to /s/courses/<pk>/."""
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.playlist, order=1,
        )
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)
        expected_url = reverse("student:course-detail", kwargs={"pk": self.course.pk})
        self.assertContains(response, expected_url)

    def test_home_panel_has_open_count(self):
        """Panel shows 'N open' badge when there are open assignments."""
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.playlist, order=1,
            publish_date=now() - timedelta(days=1),
        )
        response = self.client.get(reverse("student:home"))
        self.assertContains(response, "open")

    def test_home_curriculum_collapsed_when_enrolled(self):
        """s-curriculum-collapse <details> wrapper present for enrolled students."""
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.playlist, order=1,
        )
        response = self.client.get(reverse("student:home"))
        self.assertContains(response, "s-curriculum-collapse")

    def test_home_curriculum_not_collapsed_when_not_enrolled(self):
        """No <details> wrapper for students with no courses."""
        loner = User.objects.create_user(
            id=30099, email="loner@test.com", password="pw", is_staff=False
        )
        self.client.force_login(loner)
        response = self.client.get(reverse("student:home"))
        self.assertNotContains(response, "s-curriculum-collapse")
```

- [ ] **Step 1.3: Run tests — expect FAIL (URL not defined yet)**

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_course_detail -v 1 2>&1 | tail -20
```

Expected: errors about `NoReverseMatch` for `student:course-detail` and missing `s-curriculum-collapse`.

---

## Task 2: URL + stub view (make Task 1 tests pass)

**Files:**
- Modify: `apps/student/urls.py`
- Modify: `apps/student/views.py`

- [ ] **Step 2.1: Add URL**

In `apps/student/urls.py`, add after the `join/` line:

```python
path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
```

Full file after edit:

```python
from django.urls import path
from . import views

app_name = "student"

urlpatterns = [
    path("login/", views.StudentLoginView.as_view(), name="login"),
    path("logout/", views.StudentLogoutView.as_view(), name="logout"),
    path("signup/", views.StudentSignupView.as_view(), name="signup"),
    path("", views.HomeView.as_view(), name="home"),
    path("join/", views.JoinCourseView.as_view(), name="join"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
    path("units/<str:unit_n>/", views.UnitProgressView.as_view(), name="unit-progress"),
    path("units/<str:unit_num>/", views.UnitView.as_view(), name="unit"),
    path("units/<str:unit_num>/play/", views.PlayerView.as_view(), name="player"),
    path("units/<str:unit_num>/play/definition/", views.PlayerDefinitionView.as_view(), name="player-definition"),
    path("unit1-challenge/<str:group_key>/", views.ChallengeView.as_view(), name="unit1-challenge"),
]
```

- [ ] **Step 2.2: Add stub `CourseDetailView` at end of `apps/student/views.py`**

Append before the last line of the file (after `JoinCourseView`):

```python
class CourseDetailView(View):
    @_require_student
    def get(self, request, pk):
        from apps.exercises.models import Course, PlaylistCourseOrdered
        from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
        from django.utils.timezone import now as tz_now

        course = Course.objects.filter(
            pk=pk, visible_to__members=request.user
        ).select_related("authored_by").distinct().first()
        if course is None:
            from django.http import Http404
            raise Http404("Course not found or not enrolled.")

        author = course.authored_by
        teacher_name = author.get_full_name() or author.email

        pcos = list(
            PlaylistCourseOrdered.objects
            .filter(course=course)
            .select_related("playlist")
            .order_by("order", "pk")
        )
        playlists = [pco.playlist for pco in pcos]
        raw_by_pk = _batch_playlist_data(request.user, playlists) if playlists else {}

        current = tz_now()
        open_assignments = []
        upcoming_assignments = []
        completed_assignments = []

        for pco in pcos:
            pl = pco.playlist
            stats = _playlist_stats(pl, raw_by_pk[pl.pk]) if pl.pk in raw_by_pk else {"done": 0, "total": 0, "url": None}
            progress_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0

            # Status
            if pco.publish_date is not None and pco.publish_date > current:
                status = "upcoming"
            elif progress_pct >= 100:
                status = "completed"
            else:
                status = "open"

            overdue = (
                status == "open"
                and pco.due_date is not None
                and pco.due_date < current
            )

            due_label = None
            opens_label = None
            if status == "upcoming" and pco.publish_date:
                from django.utils.timezone import localtime
                opens_label = localtime(pco.publish_date).strftime("Opens %a %b %-d")
            elif pco.due_date is not None:
                from django.utils.timezone import localtime
                due_label = localtime(pco.due_date).strftime("Due %a %b %-d")

            row = {
                "playlist_id": pl.id,
                "name": pl.name,
                "order": pco.order,
                "status": status,
                "overdue": overdue,
                "progress_pct": progress_pct,
                "due_label": due_label,
                "opens_label": opens_label,
                "play_url": stats["url"] if status != "upcoming" else None,
            }

            if status == "open":
                open_assignments.append(row)
            elif status == "upcoming":
                upcoming_assignments.append(row)
            else:
                completed_assignments.append(row)

        all_pcts = [
            r["progress_pct"]
            for r in open_assignments + upcoming_assignments + completed_assignments
        ]
        overall_pct = int(sum(all_pcts) / len(all_pcts)) if all_pcts else 0

        return render(request, "student/course_detail.html", {
            "course": course,
            "teacher_name": teacher_name,
            "overall_pct": overall_pct,
            "open_assignments": open_assignments,
            "upcoming_assignments": upcoming_assignments,
            "completed_assignments": completed_assignments,
        })
```

- [ ] **Step 2.3: Create minimal `course_detail.html` template**

```html
{# apps/student/templates/student/course_detail.html #}
{% extends "student/base.html" %}
{% block title %}{{ course.title }} — Monteverdi{% endblock %}
{% block content %}
<h1>{{ course.title }}</h1>
<p>{{ teacher_name }}</p>
{% endblock %}
```

- [ ] **Step 2.4: Run Task 1 tests — expect FAIL (panel dict missing `course_pk` until Task 3.4)**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_course_detail -v 1 2>&1 | tail -20
```

Expected: `test_home_panel_links_to_course_detail` passes once template is updated in Task 3. `s-curriculum-collapse` tests still fail.

---

## Task 3: Home template — nav card + collapsible curriculum

**Files:**
- Modify: `apps/student/templates/student/home.html`

The existing course panels section (lines 13–43) needs to become a link card. The `s-catalog` div (line 533) needs to be wrapped in `<details>` for enrolled students.

- [ ] **Step 3.1: Replace course panel section**

Find and replace the `{% if course_panels %}...{% endif %}` block (lines 13–43) with:

```html
{% if course_panels %}
<section class="s-course-panels">
  {% for panel in course_panels %}
  <a class="s-course-panel" href="{% url 'student:course-detail' pk=panel.course_pk %}">
    <div class="s-course-panel-header">
      <h2 class="s-course-panel-title">{{ panel.title }}</h2>
      {% if panel.progress_pct > 0 %}
      <span class="s-course-panel-progress">{{ panel.progress_pct }}% complete</span>
      {% endif %}
    </div>
    <div class="s-course-panel-footer">
      {% if panel.open_count %}
      <span class="s-course-panel-badge">{{ panel.open_count }} open{% if panel.due_count %} · {{ panel.due_count }} due{% endif %}</span>
      {% endif %}
      {% if panel.overdue_count %}
      <span class="s-due-chip overdue">{{ panel.overdue_count }} overdue</span>
      {% endif %}
      <span class="s-course-panel-cta">View course →</span>
    </div>
  </a>
  {% endfor %}
</section>
{% endif %}
```

- [ ] **Step 3.2: Wrap curriculum grid in `<details>` for enrolled students**

Find the line `<!-- Course catalog — all branches equal -->` (around line 532). Replace:

```html
<!-- Course catalog — all branches equal -->
<div class="s-catalog">
```

with:

```html
<!-- Course catalog — secondary for enrolled students -->
{% if course_panels %}
<details class="s-curriculum-collapse">
  <summary>Browse all units</summary>
  <div class="s-catalog">
{% else %}
<div class="s-catalog">
{% endif %}
```

And at the end of the `</div>` that closes `.s-catalog` (just before the `<script>` tag, around line 641), replace:

```html
</div>
```

with:

```html
</div>
{% if course_panels %}</details>{% endif %}
```

- [ ] **Step 3.3: Add CSS for new panel elements + curriculum collapse**

In `home.html`, inside the existing `<style>` block (around line 56), append after the `.s-join-banner button:hover` rule:

```css
  /* ── Course panel as nav card ────────────────────────────────── */
  .s-course-panel {
    display: block;
    text-decoration: none;
    color: inherit;
    transition: box-shadow 200ms ease, transform 150ms ease;
  }
  .s-course-panel:hover {
    box-shadow: 0 6px 20px rgba(0,0,0,0.10);
    transform: translateY(-2px);
  }
  .s-course-panel-footer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px 12px;
    border-top: 1px solid var(--border);
    font-size: 0.82rem;
  }
  .s-course-panel-badge {
    color: var(--text-muted);
  }
  .s-course-panel-cta {
    margin-left: auto;
    color: var(--teal);
    font-weight: 600;
    font-size: 0.82rem;
  }

  /* ── Curriculum collapse ─────────────────────────────────────── */
  .s-curriculum-collapse {
    margin-top: 8px;
  }
  .s-curriculum-collapse > summary {
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-muted);
    padding: 8px 4px;
    user-select: none;
    list-style: none;
  }
  .s-curriculum-collapse > summary::before {
    content: "▶ ";
    font-size: 0.65rem;
  }
  .s-curriculum-collapse[open] > summary::before {
    content: "▼ ";
  }
```

- [ ] **Step 3.4: Update `_build_course_panels` to compute counts + PCO-row-based `avg_pct`**

The spec requires `progress_pct` averaged across PCO rows (not distinct unit numbers). We also
need `open_count`, `due_count`, `overdue_count`. Both changes happen in `_build_course_panels`.

First, add an import near the top of the function (or at top of views.py import block):

```python
from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
```

Then restructure `_build_course_panels` to batch playlist progress. The key change: before the
`for course in courses:` loop, collect all playlists and call `_batch_playlist_data` once:

```python
def _build_course_panels(
    user,
    available_unit_numbers: set[str],
    progress_by_unit: dict[str, dict],
    course_dates: dict[str, dict],
    courses_and_pcos: tuple | None = None,
) -> list[dict]:
    """Return one dict per enrolled course for the student home page."""
    from apps.student.unit_progress import _batch_playlist_data, _playlist_stats

    if courses_and_pcos is not None:
        courses, pcos_by_course = courses_and_pcos
    else:
        courses, pcos_by_course = _get_enrolled_courses_with_pcos(user)

    units = TaxonomyReader.get_all_units()
    unit_meta_by_n = {str(u["n"]): u for u in units}

    # Batch playlist progress across all enrolled courses (3 queries total).
    all_playlists = [
        pco.playlist
        for pco_rows in pcos_by_course.values()
        for pco in pco_rows
    ]
    raw_by_pk = _batch_playlist_data(user, all_playlists) if all_playlists else {}

    from django.utils.timezone import now as tz_now
    current = tz_now()

    panels = []
    for course in courses:
        pco_rows = pcos_by_course[course.id]
        course_unit_numbers = set()
        for pco in pco_rows:
            tags = list(pco.playlist.skill_tags or []) + list(pco.playlist.tags or [])
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("unit:"):
                    course_unit_numbers.add(tag.split(":", 1)[1])

        # Build open units (for unit availability check — kept for next_unit compat)
        open_units = []
        for unit_n in sorted(course_unit_numbers, key=unit_sort_key):
            if unit_n not in available_unit_numbers:
                continue
            info = course_dates.get(unit_n)
            published = info.get("published", True) if info else True
            if not published:
                continue
            progress = progress_by_unit.get(unit_n, _empty_unit_progress_summary())
            if progress["percent"] >= 100:
                continue
            date_labels = _unit_date_labels(info)
            unit_meta = unit_meta_by_n.get(unit_n, {})
            open_units.append({
                "n": unit_n,
                "title": unit_meta.get("title", f"Unit {unit_n}"),
                "url": f"/s/units/{unit_n}/play/",
                "due_label": date_labels.get("due_label") or "",
                "overdue": date_labels.get("overdue", False),
                "progress_pct": progress["percent"],
            })

        # PCO-row-level progress and counts.
        pct_sum = 0
        open_count = 0
        due_count = 0
        overdue_count = 0
        for pco in pco_rows:
            pl = pco.playlist
            stats = _playlist_stats(pl, raw_by_pk[pl.pk]) if pl.pk in raw_by_pk else {"done": 0, "total": 0}
            pco_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0
            pct_sum += pco_pct

            is_upcoming = pco.publish_date is not None and pco.publish_date > current
            is_complete = pco_pct >= 100
            if not is_upcoming and not is_complete:
                open_count += 1
                if pco.due_date is not None:
                    due_count += 1
                    if pco.due_date < current:
                        overdue_count += 1

        avg_pct = int(pct_sum / len(pco_rows)) if pco_rows else 0

        panels.append({
            "title": course.title,
            "open_units": open_units,
            "next_unit": open_units[0] if open_units else None,
            "progress_pct": avg_pct,
            "course_pk": course.pk,
            "open_count": open_count,
            "due_count": due_count,
            "overdue_count": overdue_count,
        })

    return panels
```

This replaces the entire `_build_course_panels` function body. The function signature is unchanged.

- [ ] **Step 3.5: Run home panel tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_course_detail.HomePanelTests -v 1 2>&1 | tail -20
```

Expected: all 4 HomePanelTests pass.

- [ ] **Step 3.6: Run full student test suite to check for regressions**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests -v 1 2>&1 | tail -20
```

Expected: all existing tests still pass.

- [ ] **Step 3.7: Commit**

```bash
git add apps/student/views.py apps/student/urls.py \
        apps/student/templates/student/home.html \
        apps/student/templates/student/course_detail.html \
        apps/student/tests/test_course_detail.py
git commit -m "feat: course-first home — panel nav cards + collapsible curriculum"
```

---

## Task 4: Tests for `CourseDetailView` (TDD)

**Files:**
- Modify: `apps/student/tests/test_course_detail.py`

Add a second test class after `HomePanelTests`.

- [ ] **Step 4.1: Add `CourseDetailViewTests` class**

Append to `apps/student/tests/test_course_detail.py`:

```python

@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class CourseDetailViewTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=31001, email="sam@test.com", password="pw", is_staff=False
        )
        self.teacher = User.objects.create_user(
            id=31002, email="dr@test.com", password="pw",
            first_name="", last_name="", is_staff=False,
        )
        self.group = Group.objects.create(name="Grp", manager=self.teacher)
        self.group.members.add(self.student)
        self.course = Course(title="Counterpoint 101", authored_by=self.teacher, open=False)
        self.course.save()
        self.course.visible_to.add(self.group)

        self.pl_open = Playlist(
            name="Unit 9 — Roman", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9"],
        )
        self.pl_open.save()

        self.pl_upcoming = Playlist(
            name="Unit 10 — Modulation", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:10"],
        )
        self.pl_upcoming.save()

        self.client.force_login(self.student)

    def _url(self):
        return reverse("student:course-detail", kwargs={"pk": self.course.pk})

    def test_enrolled_student_can_view(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Counterpoint 101")

    def test_unenrolled_student_gets_404(self):
        outsider = User.objects.create_user(
            id=31099, email="out@test.com", password="pw", is_staff=False
        )
        self.client.force_login(outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/s/login/", response["Location"])

    def test_status_grouping_open(self):
        """Published PCO with no progress → open_assignments."""
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_open, order=1,
            publish_date=now() - timedelta(days=1),
        )
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        open_a = response.context["open_assignments"]
        self.assertEqual(len(open_a), 1)
        self.assertEqual(open_a[0]["name"], "Unit 9 — Roman")
        self.assertEqual(open_a[0]["status"], "open")
        self.assertEqual(len(response.context["upcoming_assignments"]), 0)

    def test_status_grouping_upcoming(self):
        """Unpublished PCO (publish_date in future) → upcoming_assignments."""
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_upcoming, order=1,
            publish_date=now() + timedelta(days=5),
        )
        response = self.client.get(self._url())
        upcoming = response.context["upcoming_assignments"]
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0]["name"], "Unit 10 — Modulation")
        self.assertEqual(upcoming[0]["status"], "upcoming")
        self.assertIsNone(upcoming[0]["play_url"])

    def test_status_grouping_completed(self):
        """PCO where playlist has all exercises done → completed_assignments."""
        # Create a playlist with 1 exercise and mark it complete via PerformanceData
        pl = Playlist(
            name="Unit 9 — Done", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9"],
        )
        pl.save()
        from apps.exercises.tests.umto_test_helpers import make_umto_exercise
        ex = make_umto_exercise(author=self.teacher, unit=9)
        epo = ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex, order=1)

        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
            publish_date=now() - timedelta(days=1),
        )
        # Record a completed performance for this exercise
        PerformanceData.objects.create(
            user=self.student,
            playlist=pl,
            data=[{"id": ex.id, "score_numerator": 1, "score_denominator": 1}],
        )
        response = self.client.get(self._url())
        completed = response.context["completed_assignments"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["status"], "completed")
        self.assertEqual(completed[0]["progress_pct"], 100)

    def test_overdue_flag(self):
        """Open assignment with due_date in the past → overdue=True."""
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_open, order=1,
            publish_date=now() - timedelta(days=5),
            due_date=now() - timedelta(days=1),
        )
        response = self.client.get(self._url())
        open_a = response.context["open_assignments"]
        self.assertEqual(len(open_a), 1)
        self.assertTrue(open_a[0]["overdue"])

    def test_not_overdue_when_due_in_future(self):
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_open, order=1,
            publish_date=now() - timedelta(days=1),
            due_date=now() + timedelta(days=3),
        )
        response = self.client.get(self._url())
        self.assertFalse(response.context["open_assignments"][0]["overdue"])

    def test_teacher_name_fallback_to_email(self):
        """Author with empty first+last name → email shown."""
        # teacher has first_name="" last_name="" set in setUp
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_open, order=1,
        )
        response = self.client.get(self._url())
        self.assertContains(response, self.teacher.email)

    def test_empty_course_renders_ok(self):
        """Course with no PCOs → 200, all assignment lists empty."""
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_assignments"], [])
        self.assertEqual(response.context["upcoming_assignments"], [])
        self.assertEqual(response.context["completed_assignments"], [])

    def test_due_label_present_for_open_with_due_date(self):
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_open, order=1,
            publish_date=now() - timedelta(days=1),
            due_date=now() + timedelta(days=2),
        )
        response = self.client.get(self._url())
        row = response.context["open_assignments"][0]
        self.assertIsNotNone(row["due_label"])
        self.assertTrue(row["due_label"].startswith("Due "))

    def test_opens_label_present_for_upcoming(self):
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.pl_upcoming, order=1,
            publish_date=now() + timedelta(days=3),
        )
        response = self.client.get(self._url())
        row = response.context["upcoming_assignments"][0]
        self.assertIsNotNone(row["opens_label"])
        self.assertTrue(row["opens_label"].startswith("Opens "))
```

- [ ] **Step 4.2: Run new tests — expect FAIL on content assertions**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_course_detail.CourseDetailViewTests -v 1 2>&1 | tail -30
```

Expected: most context-assertion tests fail because the template stub doesn't pass context checks correctly, but the view itself should return 200 for enrolled and 404 for unenrolled.

---

## Task 5: Full `course_detail.html` template

**Files:**
- Modify: `apps/student/templates/student/course_detail.html`

- [ ] **Step 5.1: Replace stub with full template**

```html
{# apps/student/templates/student/course_detail.html #}
{% extends "student/base.html" %}
{% block title %}{{ course.title }} — Monteverdi{% endblock %}
{% block content %}

<header class="s-cd-header">
  <a class="s-cd-back" href="{% url 'student:home' %}">← Home</a>
  <div class="s-cd-title-row">
    <h1 class="s-cd-title">{{ course.title }}</h1>
    <span class="s-cd-teacher">{{ teacher_name }}</span>
  </div>
  {% if overall_pct > 0 %}
  <div class="s-cd-overall">
    <div class="s-progress-bar-track">
      <div class="s-progress-bar-fill" style="width: {{ overall_pct }}%"></div>
    </div>
    <span class="s-cd-overall-label">{{ overall_pct }}% overall</span>
  </div>
  {% endif %}
</header>

{% if open_assignments %}
<section class="s-cd-section">
  <div class="s-cd-section-label s-cd-label-open">
    {% if open_assignments|length > 0 and open_assignments.0.overdue %}● Open now{% else %}● Open now{% endif %}
  </div>
  {% for row in open_assignments %}
  <div class="s-cd-row{% if row.overdue %} s-cd-row-overdue{% endif %}">
    <div class="s-cd-row-main">
      <span class="s-cd-row-name">{{ row.name }}</span>
      <div class="s-cd-row-chips">
        {% if row.overdue %}
          <span class="s-due-chip overdue">{{ row.due_label }}</span>
        {% elif row.due_label %}
          <span class="s-due-chip">{{ row.due_label }}</span>
        {% endif %}
        <span class="s-cd-pct">{{ row.progress_pct }}%</span>
      </div>
    </div>
    {% if row.progress_pct > 0 %}
    <div class="s-progress-bar-track s-cd-bar">
      <div class="s-progress-bar-fill" style="width: {{ row.progress_pct }}%"></div>
    </div>
    {% endif %}
    {% if row.play_url %}
    <a class="s-cd-cta" href="{{ row.play_url }}">
      {% if row.progress_pct == 0 %}Start →{% else %}Continue →{% endif %}
    </a>
    {% endif %}
  </div>
  {% endfor %}
</section>
{% endif %}

{% if upcoming_assignments %}
<section class="s-cd-section">
  <div class="s-cd-section-label s-cd-label-upcoming">○ Upcoming</div>
  {% for row in upcoming_assignments %}
  <div class="s-cd-row s-cd-row-upcoming">
    <div class="s-cd-row-main">
      <span class="s-cd-row-name">{{ row.name }}</span>
      {% if row.opens_label %}
        <span class="s-due-chip opens">{{ row.opens_label }}</span>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</section>
{% endif %}

{% if completed_assignments %}
<section class="s-cd-section">
  <div class="s-cd-section-label s-cd-label-done">✓ Completed</div>
  {% for row in completed_assignments %}
  <div class="s-cd-row s-cd-row-done">
    <div class="s-cd-row-main">
      <span class="s-cd-row-name">{{ row.name }}</span>
      <span class="s-cd-pct s-cd-done-pct">100%</span>
    </div>
    {% if row.play_url %}
    <a class="s-cd-cta s-cd-review" href="{{ row.play_url }}">Review →</a>
    {% endif %}
  </div>
  {% endfor %}
</section>
{% endif %}

{% if not open_assignments and not upcoming_assignments and not completed_assignments %}
<p class="s-cd-empty">No assignments yet. Check back soon.</p>
{% endif %}

<style>
  .s-cd-header {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .s-cd-back {
    display: inline-block;
    font-size: 0.82rem;
    color: var(--teal);
    text-decoration: none;
    margin-bottom: 10px;
  }
  .s-cd-back:hover { text-decoration: underline; }
  .s-cd-title-row {
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
  }
  .s-cd-title {
    font-family: var(--font-ui);
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text);
    margin: 0;
  }
  .s-cd-teacher {
    font-size: 0.85rem;
    color: var(--text-muted);
  }
  .s-cd-overall {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
  }
  .s-cd-overall .s-progress-bar-track { flex: 1; }
  .s-cd-overall-label {
    font-size: 0.78rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .s-cd-section {
    margin-bottom: 18px;
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    background: var(--surface-2);
  }
  .s-cd-section-label {
    padding: 8px 14px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid var(--border);
  }
  .s-cd-label-open { color: var(--teal); background: color-mix(in srgb, var(--teal) 6%, var(--surface-2)); }
  .s-cd-label-upcoming { color: var(--text-muted); background: var(--surface); }
  .s-cd-label-done { color: #10b981; background: color-mix(in srgb, #10b981 6%, var(--surface-2)); }

  .s-cd-row {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }
  .s-cd-row:last-child { border-bottom: none; }
  .s-cd-row-main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .s-cd-row-name {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text);
    flex: 1;
    min-width: 0;
  }
  .s-cd-row-chips {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .s-cd-pct {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--teal);
  }
  .s-cd-done-pct { color: #10b981; }
  .s-cd-bar { margin-top: 6px; }
  .s-cd-cta {
    display: inline-block;
    margin-top: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--teal);
    text-decoration: none;
  }
  .s-cd-cta:hover { text-decoration: underline; }
  .s-cd-review { color: #10b981; }
  .s-cd-row-upcoming { opacity: 0.6; }
  .s-cd-row-done { opacity: 0.75; }
  .s-cd-row-overdue .s-cd-row-name { color: var(--text); }
  .s-cd-empty {
    color: var(--text-muted);
    font-size: 0.9rem;
    text-align: center;
    padding: 32px 0;
  }

  /* reuse existing progress bar classes from student.css */
</style>

{% endblock %}
```

- [ ] **Step 5.2: Run CourseDetailView tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_course_detail.CourseDetailViewTests -v 1 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 5.3: Run full student suite**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests -v 1 2>&1 | tail -20
```

Expected: all pass, no regressions.

- [ ] **Step 5.4: Commit**

```bash
git add apps/student/views.py \
        apps/student/urls.py \
        apps/student/templates/student/home.html \
        apps/student/templates/student/course_detail.html \
        apps/student/tests/test_course_detail.py
git commit -m "feat: student course detail page — status-grouped assignments"
```

---

## Task 6: Verify in browser

> **Note:** This task requires the dev server and a browser. If running as an automated agent, skip to Task 7.

- [ ] **Step 6.1: Start dev server**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py runserver 8080
```

- [ ] **Step 6.2: Verify home page for enrolled student**

Log in as a student enrolled in a course. Check:
- Course panel appears as a nav card (whole card is clickable)
- No "Next up" row inside the panel
- "N open · M due" badge visible
- "Browse all units" `<details>` element present below course panel
- Clicking the card navigates to `/s/courses/<pk>/`

- [ ] **Step 6.3: Verify course detail page**

On `/s/courses/<pk>/`:
- Header shows course title + teacher name
- "Open now" section lists open assignments with progress bars and Continue/Start CTA
- "Upcoming" section shows greyed-out rows with "Opens" chips, no CTA
- "Completed" section shows muted rows with "Review →" link
- Empty sections are hidden entirely
- "← Home" back link works

- [ ] **Step 6.4: Verify unenrolled student gets 404**

Log in as a student not in the course and navigate to `/s/courses/<pk>/`. Expected: 404.

---

## Task 7: Final test run + commit

- [ ] **Step 7.1: Run full student test suite one last time**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests -v 1 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 7.2: Final commit if any stray changes**

```bash
git status
git diff --stat
```

If clean, no commit needed. If any outstanding changes, commit them with a descriptive message.
