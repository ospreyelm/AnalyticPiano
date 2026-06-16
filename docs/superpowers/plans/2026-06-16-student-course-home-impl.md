# Student Course Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show enrolled students a "Next up" direct link (nearest due date) on their home course panel and a "Start first assignment" link immediately after joining a course.

**Architecture:** Three backend changes (`_build_course_panels`, `JoinCourseView.post`, `HomeView.get`) and two template changes (`home.html` panel HTML restructure + join banner). New CSS goes into `student.css`; no new inline styles. No new views, models, or URLs.

**Tech Stack:** Django 4.x, Django templates, Python 3.10+, pytest-django, `TransactionTestCase`

---

## File map

| File | Change |
|------|--------|
| `apps/student/views.py` | Add next-up candidate logic to `_build_course_panels`; add session storage to `JoinCourseView.post`; pop new session keys in `HomeView.get` |
| `apps/student/templates/student/home.html` | Restructure panel from `<a>` to `<div>`; add "Next up" row; update "View course" to real `<a>`; add banner link |
| `apps/student/static/student/student.css` | Add `.s-course-next-arrow`, `.s-course-panel-cta` link styles, remove hover-lift from non-interactive panel, `.s-join-banner-link` |
| `apps/student/tests/test_home_course_panels.py` | New test file: 8 tests for the three backend changes |
| `docs/teacher_experience_launch_followups.md` | Mark item 4 and UX polish item 3 resolved |

---

## Task 1: Tests for `_build_course_panels` next-up logic

**Files:**
- Create: `apps/student/tests/test_home_course_panels.py`

- [ ] **Step 1: Write the failing tests**

```python
# apps/student/tests/test_home_course_panels.py
"""Tests for next-up link logic in _build_course_panels and related views."""
import datetime

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
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()


def _make_playlist(teacher, name, unit_n):
    pl = Playlist(
        name=name, authored_by=teacher,
        is_public=True, skill_tags=[f"unit:{unit_n}"],
    )
    pl.save()
    return pl


def _add_exercise(playlist, teacher, unit_n):
    ex = make_umto_exercise(author=teacher, unit=unit_n)
    ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=ex, order=1)
    return ex


def _complete_exercise(user, playlist, exercise):
    PerformanceData.objects.create(
        user=user,
        playlist=playlist,
        data=[{"id": exercise.id, "score_numerator": 1, "score_denominator": 1}],
    )


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class NextUpPanelTests(TransactionTestCase):
    """_build_course_panels returns next_url/next_name/next_due_label."""
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            id=40001, email="teach@test.com", password="pw", is_staff=False
        )
        self.student = User.objects.create_user(
            id=40002, email="stu@test.com", password="pw", is_staff=False
        )
        self.group = Group.objects.create(name="Theory 2026", manager=self.teacher)
        self.group.members.add(self.student)
        self.course = Course(title="Music Theory I", authored_by=self.teacher, open=False)
        self.course.save()
        self.course.visible_to.add(self.group)
        self.client.force_login(self.student)

    def _panels(self):
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)
        return response.context["course_panels"]

    def test_next_url_set_for_open_pco(self):
        """Open PCO (published, incomplete) produces next_url."""
        pl = _make_playlist(self.teacher, "Unit 9 — Play", 9)
        _add_exercise(pl, self.teacher, 9)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
            publish_date=now() - datetime.timedelta(days=1),
        )
        panels = self._panels()
        self.assertIsNotNone(panels[0]["next_url"])
        self.assertEqual(panels[0]["next_name"], "Unit 9 — Play")

    def test_next_url_none_when_all_complete(self):
        """All PCOs at 100% → next_url is None."""
        pl = _make_playlist(self.teacher, "Unit 9 — Play", 9)
        ex = _add_exercise(pl, self.teacher, 9)
        _complete_exercise(self.student, pl, ex)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
        )
        panels = self._panels()
        self.assertIsNone(panels[0]["next_url"])

    def test_next_url_none_when_all_upcoming(self):
        """All PCOs with future publish_date → next_url is None."""
        pl = _make_playlist(self.teacher, "Unit 9 — Play", 9)
        _add_exercise(pl, self.teacher, 9)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
            publish_date=now() + datetime.timedelta(days=7),
        )
        panels = self._panels()
        self.assertIsNone(panels[0]["next_url"])

    def test_next_url_sorted_by_due_date_earliest_first(self):
        """Earlier due date wins over later due date."""
        pl_early = _make_playlist(self.teacher, "Unit 9 — Early", 9)
        _add_exercise(pl_early, self.teacher, 9)
        pl_late = _make_playlist(self.teacher, "Unit 9 — Late", 9)
        _add_exercise(pl_late, self.teacher, 9)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl_late, order=1,
            due_date=now() + datetime.timedelta(days=14),
        )
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl_early, order=2,
            due_date=now() + datetime.timedelta(days=3),
        )
        panels = self._panels()
        self.assertEqual(panels[0]["next_name"], "Unit 9 — Early")

    def test_next_url_no_due_date_sorts_last(self):
        """PCO without due_date sorts after one that has a due date."""
        pl_dated = _make_playlist(self.teacher, "Unit 9 — Dated", 9)
        _add_exercise(pl_dated, self.teacher, 9)
        pl_nodated = _make_playlist(self.teacher, "Unit 9 — No Date", 9)
        _add_exercise(pl_nodated, self.teacher, 9)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl_nodated, order=1,
            due_date=None,
        )
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl_dated, order=2,
            due_date=now() + datetime.timedelta(days=5),
        )
        panels = self._panels()
        self.assertEqual(panels[0]["next_name"], "Unit 9 — Dated")

    def test_next_url_resumes_at_first_incomplete_exercise(self):
        """Partially completed playlist: next_url has exercise_num=2, not 1."""
        pl = _make_playlist(self.teacher, "Unit 9 — Play", 9)
        ex1 = make_umto_exercise(author=self.teacher, unit=9)
        ex2 = make_umto_exercise(author=self.teacher, unit=9)
        ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex1, order=1)
        ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex2, order=2)
        _complete_exercise(self.student, pl, ex1)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
        )
        panels = self._panels()
        self.assertIsNotNone(panels[0]["next_url"])
        self.assertIn("exercise_num=2", panels[0]["next_url"])
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1
pyenv local system
python manage.py test apps.student.tests.test_home_course_panels.NextUpPanelTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -30
```

Expected: 6 failures — `next_url` key not in panel dict (KeyError or None when it should not be).

- [ ] **Step 3: Implement next-up logic in `_build_course_panels`**

Edit `apps/student/views.py`. Find `_build_course_panels` (around line 562) and replace its body with:

```python
def _build_course_panels(
    user,
    courses_and_pcos=None,
) -> list[dict]:
    """Return one dict per enrolled course for the student home page."""
    import datetime as _dt
    from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
    from django.utils.timezone import now as tz_now

    _FAR_FUTURE = _dt.datetime(2999, 12, 31, tzinfo=_dt.timezone.utc)

    if courses_and_pcos is not None:
        courses, pcos_by_course = courses_and_pcos
    else:
        courses, pcos_by_course = _get_enrolled_courses_with_pcos(user)

    all_playlists = [
        pco.playlist
        for pco_rows in pcos_by_course.values()
        for pco in pco_rows
    ]
    raw_by_pk = _batch_playlist_data(user, all_playlists) if all_playlists else {}
    current = tz_now()

    panels = []
    for course in courses:
        pco_rows = pcos_by_course[course.pk]

        pct_sum = 0
        open_count = 0
        due_count = 0
        overdue_count = 0
        next_candidates = []  # (pco, stats) tuples for open, incomplete PCOs

        for pco in pco_rows:
            pl = pco.playlist
            stats = (
                _playlist_stats(pl, raw_by_pk[pl.pk])
                if pl.pk in raw_by_pk
                else {"done": 0, "total": 0, "url": None}
            )
            pco_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0
            pct_sum += pco_pct

            is_upcoming = pco.publish_date is not None and pco.publish_date > current
            is_complete = pco_pct >= 100
            if not is_upcoming and not is_complete:
                open_count += 1
                if stats.get("total", 0) > 0:
                    next_candidates.append((pco, stats))
                if pco.due_date is not None:
                    due_count += 1
                    if pco.due_date < current:
                        overdue_count += 1

        # Pick the "next up" assignment: earliest due date (nulls last), then order.
        next_candidates.sort(
            key=lambda t: (
                t[0].due_date is None,
                t[0].due_date if t[0].due_date is not None else _FAR_FUTURE,
                t[0].order,
            )
        )

        next_url = None
        next_name = None
        next_due_label = None
        if next_candidates:
            winner_pco, winner_stats = next_candidates[0]
            next_url = winner_stats.get("url")
            next_name = winner_pco.playlist.name
            date_labels = _unit_date_labels({
                "due": winner_pco.due_date,
                "publish": None,
                "published": True,
            })
            next_due_label = date_labels["due_label"]

        avg_pct = int(pct_sum / len(pco_rows)) if pco_rows else 0
        panels.append({
            "title": course.title,
            "progress_pct": avg_pct,
            "course_pk": course.pk,
            "open_count": open_count,
            "due_count": due_count,
            "overdue_count": overdue_count,
            "next_url": next_url,
            "next_name": next_name,
            "next_due_label": next_due_label,
        })

    return panels
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python manage.py test apps.student.tests.test_home_course_panels.NextUpPanelTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -20
```

Expected: 6 tests pass.

- [ ] **Step 5: Confirm existing home panel tests still pass**

```bash
python manage.py test apps.student.tests.test_course_detail.HomePanelTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -15
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/student/tests/test_home_course_panels.py apps/student/views.py
git commit -m "feat(student): add next-up link data to home course panels"
```

---

## Task 2: `JoinCourseView` — session storage for first open assignment

**Files:**
- Modify: `apps/student/tests/test_home_course_panels.py` (add new test class)
- Modify: `apps/student/views.py` (`JoinCourseView.post`)

- [ ] **Step 1: Write the failing tests**

Append this class to `apps/student/tests/test_home_course_panels.py`:

```python
@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class JoinNextAssignmentTests(TransactionTestCase):
    """JoinCourseView.post stores next_assignment_url in session."""
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            id=41001, email="jteach@test.com", password="pw", is_staff=False
        )
        self.student = User.objects.create_user(
            id=41002, email="jstu@test.com", password="pw", is_staff=False
        )
        self.group = Group.objects.create(
            name="Theory Fall", manager=self.teacher, join_code="FALL26"
        )
        self.course = Course(title="Music Theory I", authored_by=self.teacher, open=False)
        self.course.save()
        self.course.visible_to.add(self.group)
        self.client.force_login(self.student)

    def _join(self):
        return self.client.post(
            reverse("student:join"),
            {"join_code": "FALL26"},
            follow=False,
        )

    def test_session_stores_next_url_when_open_pco_exists(self):
        """Session gets next_assignment_url after joining with a published open PCO."""
        pl = _make_playlist(self.teacher, "Unit 9 — Play", 9)
        _add_exercise(pl, self.teacher, 9)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
        )
        response = self._join()
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertIn("next_assignment_url", session)
        self.assertIn("next_assignment_name", session)
        self.assertEqual(session["next_assignment_name"], "Unit 9 — Play")

    def test_session_omits_next_url_when_no_pco(self):
        """No PCOs → session has no next_assignment_url."""
        response = self._join()
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertNotIn("next_assignment_url", session)

    def test_session_omits_next_url_when_all_complete(self):
        """All published PCOs at 100% → session has no next_assignment_url."""
        pl = _make_playlist(self.teacher, "Unit 9 — Play", 9)
        ex = _add_exercise(pl, self.teacher, 9)
        # Pre-complete the exercise before joining
        _complete_exercise(self.student, pl, ex)
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
        )
        response = self._join()
        session = self.client.session
        self.assertNotIn("next_assignment_url", session)

    def test_session_omits_next_url_when_no_unit_tag(self):
        """Playlist without unit:N tag → session has no next_assignment_url."""
        pl = Playlist(
            name="Untagged playlist", authored_by=self.teacher,
            is_public=True, skill_tags=[],
        )
        pl.save()
        _add_exercise(pl, self.teacher, 9)  # exercise has unit tag; playlist doesn't
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
        )
        response = self._join()
        session = self.client.session
        self.assertNotIn("next_assignment_url", session)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python manage.py test apps.student.tests.test_home_course_panels.JoinNextAssignmentTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -20
```

Expected: 3–4 failures — `next_assignment_url` not stored or wrongly absent.

- [ ] **Step 3: Implement session storage in `JoinCourseView.post`**

In `apps/student/views.py`, find `JoinCourseView.post` (around line 836). Replace the session-store block after `group.members.add(request.user)` with:

```python
        if not group.members.filter(pk=request.user.pk).exists():
            group.members.add(request.user)
        request.session['joined_course'] = group.name

        # Find first open published assignment for the "start here" link.
        from django.db.models import F as _F
        from apps.student.unit_progress import _playlist_stats_by_id
        _tz_now = tz_now()
        candidate_pcos = (
            PlaylistCourseOrdered.objects
            .filter(course__visible_to=group)
            .select_related("playlist")
            .order_by(_F("due_date").asc(nulls_last=True), "order")
        )
        for _pco in candidate_pcos:
            # Skip upcoming (not yet published).
            if _pco.publish_date is not None and _pco.publish_date > _tz_now:
                continue
            _pl = _pco.playlist
            # Skip playlists with no explicit unit:N tag.
            _pl_tags = list(_pl.skill_tags or []) + list(_pl.tags or [])
            if not any(isinstance(t, str) and t.startswith("unit:") for t in _pl_tags):
                continue
            # Skip completed playlists.
            _stats = _playlist_stats_by_id(request.user, _pl.id)
            if _stats["total"] == 0 or _stats["done"] >= _stats["total"]:
                continue
            request.session["next_assignment_url"] = _stats["url"]
            request.session["next_assignment_name"] = _pl.name or ""
            break

        return redirect(reverse("student:home"))
```

You also need to add the `tz_now` import at the top of `JoinCourseView.post`. Add it as a local import:

```python
        from django.utils.timezone import now as tz_now
```

Place it just before the `candidate_pcos` query (the function already uses `tz_now()` at module scope but as a local import it's fine here).

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python manage.py test apps.student.tests.test_home_course_panels.JoinNextAssignmentTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -20
```

Expected: 4 tests pass.

- [ ] **Step 5: Confirm existing join tests still pass**

```bash
python manage.py test apps.student.tests.test_views \
  --settings=harmony.settings.local -v 2 2>&1 | tail -15
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/student/tests/test_home_course_panels.py apps/student/views.py
git commit -m "feat(student): store next_assignment_url in session after joining course"
```

---

## Task 3: `HomeView.get` — pop new session keys

**Files:**
- Modify: `apps/student/tests/test_home_course_panels.py` (add new test class)
- Modify: `apps/student/views.py` (`HomeView.get`)

- [ ] **Step 1: Write the failing test**

Append to `apps/student/tests/test_home_course_panels.py`:

```python
@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class HomeViewSessionPopTests(TransactionTestCase):
    """HomeView pops next_assignment_url/name from session and passes to context."""
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=42001, email="hsess@test.com", password="pw", is_staff=False
        )
        self.client.force_login(self.student)

    def test_session_keys_passed_to_context_and_cleared(self):
        """next_assignment_url in session → in context; cleared on second request."""
        session = self.client.session
        session["next_assignment_url"] = "/s/9/player/?playlist=abc&exercise_num=1"
        session["next_assignment_name"] = "Unit 9 — Play"
        session.save()

        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["next_assignment_url"],
            "/s/9/player/?playlist=abc&exercise_num=1",
        )
        self.assertEqual(response.context["next_assignment_name"], "Unit 9 — Play")

        # Second request: keys gone from context (popped from session).
        response2 = self.client.get(reverse("student:home"))
        self.assertIsNone(response2.context.get("next_assignment_url"))
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python manage.py test apps.student.tests.test_home_course_panels.HomeViewSessionPopTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -15
```

Expected: FAIL — `next_assignment_url` missing from context.

- [ ] **Step 3: Implement the session pop in `HomeView.get`**

In `apps/student/views.py`, find `HomeView.get` (around line 819):

```python
class HomeView(View):
    @_require_student
    def get(self, request):
        context = _build_home_context(request.user)
        context['joined_course'] = request.session.pop('joined_course', None)
        return render(request, "student/home.html", context)
```

Replace with:

```python
class HomeView(View):
    @_require_student
    def get(self, request):
        context = _build_home_context(request.user)
        context['joined_course'] = request.session.pop('joined_course', None)
        context['next_assignment_url'] = request.session.pop('next_assignment_url', None)
        context['next_assignment_name'] = request.session.pop('next_assignment_name', None)
        return render(request, "student/home.html", context)
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python manage.py test apps.student.tests.test_home_course_panels.HomeViewSessionPopTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 5: Run all new tests together**

```bash
python manage.py test apps.student.tests.test_home_course_panels \
  --settings=harmony.settings.local -v 2 2>&1 | tail -20
```

Expected: all 11 tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/student/views.py apps/student/tests/test_home_course_panels.py
git commit -m "feat(student): pop next_assignment session keys in HomeView"
```

---

## Task 4: Template — panel restructure and "Next up" row

**Files:**
- Modify: `apps/student/static/student/student.css`
- Modify: `apps/student/templates/student/home.html`

- [ ] **Step 1: Add new CSS rules to `student.css`**

Open `apps/student/static/student/student.css` and append at the end:

```css
/* ── Course panel next-up row and link overrides (home.html panel restructure) ── */

/* Panel is now a <div>, not a <a> — suppress the link hover lift from inline styles. */
.s-course-panel {
  cursor: default;
}
.s-course-panel:hover {
  box-shadow: none !important;
  transform: none !important;
}

/* "View course →" footer link. */
.s-course-panel-cta {
  text-decoration: none;
}
.s-course-panel-cta:hover {
  text-decoration: underline;
}

/* Arrow inside the next-up row. */
.s-course-next-arrow {
  color: var(--teal);
  font-weight: 600;
  flex-shrink: 0;
}
```

- [ ] **Step 2: Restructure the course panel in `home.html`**

In `apps/student/templates/student/home.html`, find the course panels section (lines 13–35). Replace the entire `{% for panel in course_panels %}...{% endfor %}` block with:

```html
  {% for panel in course_panels %}
  <div class="s-course-panel">
    <div class="s-course-panel-header">
      <h2 class="s-course-panel-title">{{ panel.title }}</h2>
      {% if panel.progress_pct > 0 %}
      <span class="s-course-panel-progress">{{ panel.progress_pct }}% complete</span>
      {% endif %}
    </div>
    {% if panel.next_url %}
    <a class="s-course-next" href="{{ panel.next_url }}">
      <span class="s-course-next-label">Next up</span>
      <span class="s-course-next-title">{{ panel.next_name }}</span>
      {% if panel.next_due_label %}
      <span class="s-due-chip">{{ panel.next_due_label }}</span>
      {% endif %}
      <span class="s-course-next-arrow">→</span>
    </a>
    {% endif %}
    <div class="s-course-panel-footer">
      {% if panel.open_count %}
      <span class="s-course-panel-badge">{{ panel.open_count }} open{% if panel.due_count %} · {{ panel.due_count }} due{% endif %}</span>
      {% endif %}
      {% if panel.overdue_count %}
      <span class="s-due-chip overdue">{{ panel.overdue_count }} overdue</span>
      {% endif %}
      <a class="s-course-panel-cta" href="{% url 'student:course-detail' pk=panel.course_pk %}">View course →</a>
    </div>
  </div>
  {% endfor %}
```

- [ ] **Step 3: Run existing home panel tests to confirm no regressions**

```bash
python manage.py test apps.student.tests.test_course_detail.HomePanelTests \
  --settings=harmony.settings.local -v 2 2>&1 | tail -15
```

Expected: all tests pass. Note: `test_home_panel_links_to_course_detail` checks that the course detail URL appears somewhere on the page — it will now be in the footer `<a>` rather than the card wrapper, which still satisfies `assertContains`.

- [ ] **Step 4: Commit**

```bash
git add apps/student/static/student/student.css \
        apps/student/templates/student/home.html
git commit -m "feat(student): restructure course panel to div with Next-up row"
```

---

## Task 5: Template — join banner "Start" link

**Files:**
- Modify: `apps/student/static/student/student.css`
- Modify: `apps/student/templates/student/home.html`

- [ ] **Step 1: Add banner link CSS to `student.css`**

Append to `apps/student/static/student/student.css`:

```css
/* Join success banner — "Start: <name> →" link. */
.s-join-banner-link {
  color: var(--teal);
  font-weight: 600;
  text-decoration: none;
  margin-left: 8px;
  white-space: nowrap;
}
.s-join-banner-link:hover {
  text-decoration: underline;
}
```

- [ ] **Step 2: Update the join banner in `home.html`**

Find the join banner block (lines 6–11):

```html
{% if joined_course %}
<div class="s-join-banner" id="join-banner">
  You've joined <strong>{{ joined_course }}</strong>.
  <button onclick="this.closest('.s-join-banner').remove()" aria-label="Dismiss">×</button>
</div>
{% endif %}
```

Replace with:

```html
{% if joined_course %}
<div class="s-join-banner" id="join-banner">
  <span>You've joined <strong>{{ joined_course }}</strong>.{% if next_assignment_url %}<a class="s-join-banner-link" href="{{ next_assignment_url }}">Start: {{ next_assignment_name }} →</a>{% endif %}</span>
  <button onclick="this.closest('.s-join-banner').remove()" aria-label="Dismiss">×</button>
</div>
{% endif %}
```

- [ ] **Step 3: Run all student tests**

```bash
python manage.py test apps.student \
  --settings=harmony.settings.local -v 2 2>&1 | tail -25
```

Expected: all tests pass, including `HomePanelTests`, `CourseDetailViewTests`, and the new `test_home_course_panels` suite.

- [ ] **Step 4: Commit**

```bash
git add apps/student/static/student/student.css \
        apps/student/templates/student/home.html
git commit -m "feat(student): add start-link to join success banner"
```

---

## Task 6: Documentation update

**Files:**
- Modify: `docs/teacher_experience_launch_followups.md`

- [ ] **Step 1: Mark resolved items**

In `docs/teacher_experience_launch_followups.md`:

Under **"Add a course-focused student home section"** (P0/P1 item 4), prepend:
`> **Resolved 2026-06-16** — course panels show "Next up →" row (nearest due date); curriculum collapsible below. See plan 2026-06-16-student-course-home.md.`

Under **"Student join success should be explicit"** (UX polish item 3), prepend:
`> **Resolved 2026-06-16** — banner now shows "Start: <playlist name> →" link to first open assignment.`

- [ ] **Step 2: Commit**

```bash
git add docs/teacher_experience_launch_followups.md
git commit -m "docs: mark student-course-home follow-up items resolved"
```

---

## Self-review

**Spec coverage:**
- ✅ `_build_course_panels` next-up per course — Task 1
- ✅ Sort by due date ASC nulls last — Task 1
- ✅ `pco_pct < 100` completeness check — Task 1 (skips complete pcos from `next_candidates`)
- ✅ Empty playlist guard (`total == 0`) — Task 1 (`stats.get("total", 0) > 0` gate)
- ✅ `_playlist_stats["url"]` for resume URL — Task 1 (`winner_stats.get("url")`)
- ✅ `_unit_date_labels` for due label — Task 1
- ✅ Panel HTML from `<a>` to `<div>`, no nested anchors — Task 4
- ✅ "View course →" becomes real `<a>` — Task 4
- ✅ `JoinCourseView` session storage with unit:N guard — Task 2
- ✅ `JoinCourseView` skips completed, skips upcoming, skips no-unit playlists — Task 2
- ✅ `HomeView.get` pops both new session keys — Task 3
- ✅ Banner link only when `next_assignment_url` truthy — Task 5
- ✅ New CSS to `student.css`, no new inline styles — Tasks 4 and 5
- ✅ 11 tests across 3 test classes — Tasks 1–3
- ✅ Docs update — Task 6

**Placeholder scan:** No TBDs, no "similar to Task N" references, all code blocks complete.

**Type consistency:** `next_url`/`next_name`/`next_due_label` defined in Task 1, consumed in Task 4 template — names match. Session keys `next_assignment_url`/`next_assignment_name` written in Task 2, popped in Task 3, read in Task 5 template — names match.
