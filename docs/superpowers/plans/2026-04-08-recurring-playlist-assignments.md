# Recurring Playlist Assignments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add daily and weekly recurring playlist assignments so teachers can require a playlist to be completed multiple times per period, with capped counting, current-period status, and cumulative completed-period reporting.

**Architecture:** Store recurrence settings on `PlaylistCourseOrdered`, store per-period summaries in a new `RecurringPlaylistPeriodProgress` model, and keep `PerformanceData.data` as the raw attempt log. Rebuild the active period summary from raw exercise attempts using a greedy playlist-cycle algorithm, because the legacy `playlist_passed()` boolean is cumulative and cannot count multiple passes inside one period.

**Tech Stack:** Django models, Django forms, Django test runner, django-tables2, existing dashboard templates, JSON-backed performance history.

---

## File Structure

- Modify: `apps/exercises/models.py`
  Responsibility: add recurrence fields to `PlaylistCourseOrdered`, add `RecurringPlaylistPeriodProgress`, and hook recurrence refresh into `PerformanceData.submit()`.
- Create: `apps/exercises/utils/recurrence.py`
  Responsibility: period-boundary math, greedy cycle reconstruction, per-period summary refresh, and lightweight read helpers for dashboard views.
- Create: `apps/exercises/migrations/0055_recurring_playlist_assignments.py`
  Responsibility: add recurrence schema without touching existing raw performance rows.
- Create: `apps/exercises/tests/__init__.py`
- Create: `apps/exercises/tests/test_recurring_progress.py`
  Responsibility: model, utility, and submit-flow tests for recurring progress.
- Modify: `apps/dashboard/forms.py`
  Responsibility: expose recurrence settings on course playlist assignments and parse them from `ManyField` payloads.
- Modify: `apps/dashboard/views/my_work.py`
  Responsibility: replace binary recurring status with current-period progress plus cumulative completed periods.
- Modify: `apps/dashboard/views/courses.py`
  Responsibility: enrich recurring gradebook rows and CSV export with current-period status plus completed-period history.
- Modify: `apps/dashboard/tables.py`
  Responsibility: render recurring playlist cells differently from one-time `P/T/L/C/X` marks and include recurring score aggregation.
- Modify: `apps/dashboard/templates/dashboard/my-work.html`
  Responsibility: show recurring progress labels instead of one-time pass-only labels.
- Create: `apps/dashboard/tests/__init__.py`
- Create: `apps/dashboard/tests/test_recurring_playlist_views.py`
  Responsibility: course edit, My Work, and gradebook regression tests.

### Task 1: Add Recurrence Schema And Period Math

**Files:**
- Create: `apps/exercises/tests/__init__.py`
- Create: `apps/exercises/tests/test_recurring_progress.py`
- Create: `apps/exercises/utils/recurrence.py`
- Modify: `apps/exercises/models.py`
- Create: `apps/exercises/migrations/0055_recurring_playlist_assignments.py`

- [ ] **Step 1: Write the failing model and utility tests**

```python
from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered
from apps.exercises.utils.recurrence import get_assignment_period_bounds


class RecurringPeriodBoundaryTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.playlist = Playlist.objects.create(
            name="Keyboard Drill",
            authored_by=self.teacher,
        )
        self.course = Course.objects.create(
            title="Theory I",
            authored_by=self.teacher,
        )

    def test_daily_period_uses_assignment_anchor(self):
        assignment = PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=True,
            recurrence_unit="day",
            required_passes_per_period=2,
            recurrence_starts_on=timezone.make_aware(datetime(2026, 4, 8, 0, 0, 0)),
        )

        period_start, period_end = get_assignment_period_bounds(
            assignment,
            timezone.make_aware(datetime(2026, 4, 8, 14, 30, 0)),
        )

        self.assertEqual(period_start.date().isoformat(), "2026-04-08")
        self.assertEqual(period_end.date().isoformat(), "2026-04-09")

    def test_weekly_period_is_seven_days_from_anchor(self):
        assignment = PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=True,
            recurrence_unit="week",
            required_passes_per_period=3,
            recurrence_starts_on=timezone.make_aware(datetime(2026, 4, 6, 0, 0, 0)),
        )

        period_start, period_end = get_assignment_period_bounds(
            assignment,
            timezone.make_aware(datetime(2026, 4, 15, 9, 0, 0)),
        )

        self.assertEqual(period_start.date().isoformat(), "2026-04-13")
        self.assertEqual(period_end.date().isoformat(), "2026-04-20")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./manage.py test apps.exercises.tests.test_recurring_progress.RecurringPeriodBoundaryTests -v 2`
Expected: `ImportError` for `apps.exercises.utils.recurrence` or `TypeError` because the recurrence fields do not exist yet.

- [ ] **Step 3: Write the minimal schema and utility implementation**

```python
# apps/exercises/models.py

class PlaylistCourseOrdered(ClonableModelMixin, BaseContentModel):
    RECURRENCE_DAY = "day"
    RECURRENCE_WEEK = "week"
    RECURRENCE_UNIT_CHOICES = (
        (RECURRENCE_DAY, "Daily"),
        (RECURRENCE_WEEK, "Weekly"),
    )

    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    order = models.IntegerField("Order", help_text="Unit #")
    due_date = models.DateTimeField("Due Date", blank=True, default=None, null=True)
    publish_date = models.DateTimeField("Publish Date", blank=True, default=None, null=True)
    is_recurring = models.BooleanField("Recurring assignment", default=False)
    recurrence_unit = models.CharField(
        "Recurrence unit",
        max_length=8,
        choices=RECURRENCE_UNIT_CHOICES,
        blank=True,
        default="",
    )
    required_passes_per_period = models.PositiveIntegerField(
        "Required passes per period",
        default=1,
    )
    recurrence_starts_on = models.DateTimeField(
        "Recurrence starts on",
        blank=True,
        null=True,
        default=None,
    )


class RecurringPlaylistPeriodProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recurring_playlist_progress")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="recurring_playlist_progress")
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="recurring_playlist_progress")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    counted_passes = models.PositiveIntegerField(default=0)
    required_passes = models.PositiveIntegerField(default=1)
    target_met = models.BooleanField(default=False)
    first_pass_at = models.DateTimeField(blank=True, null=True, default=None)
    last_counted_pass_at = models.DateTimeField(blank=True, null=True, default=None)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "course", "playlist", "period_start"),)


# apps/exercises/utils/recurrence.py

from datetime import timedelta

from django.utils import timezone

from apps.exercises.models import PlaylistCourseOrdered


def get_assignment_period_bounds(assignment, occurred_at):
    anchor = assignment.recurrence_starts_on or assignment.publish_date or occurred_at
    anchor_local = timezone.localtime(anchor)
    current_local = timezone.localtime(occurred_at)
    period_days = 1 if assignment.recurrence_unit == PlaylistCourseOrdered.RECURRENCE_DAY else 7
    days_since_anchor = max((current_local.date() - anchor_local.date()).days, 0)
    period_index = days_since_anchor // period_days
    period_start = anchor_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=period_index * period_days)
    period_end = period_start + timedelta(days=period_days)
    return period_start, period_end
```

```python
# apps/exercises/migrations/0055_recurring_playlist_assignments.py

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("exercises", "0054_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="playlistcourseordered",
            name="is_recurring",
            field=models.BooleanField(default=False, verbose_name="Recurring assignment"),
        ),
        migrations.AddField(
            model_name="playlistcourseordered",
            name="recurrence_unit",
            field=models.CharField(blank=True, choices=[("day", "Daily"), ("week", "Weekly")], default="", max_length=8, verbose_name="Recurrence unit"),
        ),
        migrations.AddField(
            model_name="playlistcourseordered",
            name="required_passes_per_period",
            field=models.PositiveIntegerField(default=1, verbose_name="Required passes per period"),
        ),
        migrations.AddField(
            model_name="playlistcourseordered",
            name="recurrence_starts_on",
            field=models.DateTimeField(blank=True, default=None, null=True, verbose_name="Recurrence starts on"),
        ),
        migrations.CreateModel(
            name="RecurringPlaylistPeriodProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("counted_passes", models.PositiveIntegerField(default=0)),
                ("required_passes", models.PositiveIntegerField(default=1)),
                ("target_met", models.BooleanField(default=False)),
                ("first_pass_at", models.DateTimeField(blank=True, default=None, null=True)),
                ("last_counted_pass_at", models.DateTimeField(blank=True, default=None, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="recurring_playlist_progress", to="exercises.course")),
                ("playlist", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="recurring_playlist_progress", to="exercises.playlist")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="recurring_playlist_progress", to="accounts.user")),
            ],
            options={"unique_together": {("user", "course", "playlist", "period_start")}},
        ),
    ]
```

- [ ] **Step 4: Run the tests to verify the schema and period math pass**

Run: `./manage.py test apps.exercises.tests.test_recurring_progress.RecurringPeriodBoundaryTests -v 2`
Expected: `OK` with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/models.py apps/exercises/utils/recurrence.py apps/exercises/migrations/0055_recurring_playlist_assignments.py apps/exercises/tests/__init__.py apps/exercises/tests/test_recurring_progress.py
git commit -m "feat: add recurring assignment schema"
```

### Task 2: Rebuild Period Progress From Raw Attempts

**Files:**
- Modify: `apps/exercises/utils/recurrence.py`
- Modify: `apps/exercises/tests/test_recurring_progress.py`

- [ ] **Step 1: Write the failing cycle-reconstruction tests**

```python
from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from apps.exercises.utils.recurrence import count_playlist_cycles


class RecurringCycleCountingTests(TestCase):
    def test_count_playlist_cycles_consumes_error_free_attempts_greedily(self):
        attempts = [
            {"id": "EA00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 9, 0, 0))},
            {"id": "EB00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 9, 5, 0))},
            {"id": "EA00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 10, 0, 0))},
            {"id": "EB00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 10, 5, 0))},
        ]

        counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
            ["EA00A0", "EB00A0"],
            attempts,
            cap=3,
        )

        self.assertEqual(counted_passes, 2)
        self.assertEqual(first_pass_at.isoformat(), timezone.make_aware(datetime(2026, 4, 8, 9, 5, 0)).isoformat())
        self.assertEqual(last_counted_pass_at.isoformat(), timezone.make_aware(datetime(2026, 4, 8, 10, 5, 0)).isoformat())

    def test_count_playlist_cycles_caps_the_result(self):
        attempts = [
            {"id": "EA00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 9, 0, 0))},
            {"id": "EB00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 9, 5, 0))},
            {"id": "EA00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 10, 0, 0))},
            {"id": "EB00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 10, 5, 0))},
            {"id": "EA00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 11, 0, 0))},
            {"id": "EB00A0", "error_tally": 0, "performed_at": timezone.make_aware(datetime(2026, 4, 8, 11, 5, 0))},
        ]

        counted_passes, _, last_counted_pass_at = count_playlist_cycles(
            ["EA00A0", "EB00A0"],
            attempts,
            cap=2,
        )

        self.assertEqual(counted_passes, 2)
        self.assertEqual(last_counted_pass_at.isoformat(), timezone.make_aware(datetime(2026, 4, 8, 10, 5, 0)).isoformat())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./manage.py test apps.exercises.tests.test_recurring_progress.RecurringCycleCountingTests -v 2`
Expected: `ImportError` because `count_playlist_cycles` does not exist yet.

- [ ] **Step 3: Implement greedy cycle reconstruction and summary refresh**

```python
# apps/exercises/utils/recurrence.py

from django.utils.dateparse import parse_datetime

from apps.exercises.models import RecurringPlaylistPeriodProgress


def count_playlist_cycles(exercise_ids, attempts, cap):
    remaining = set(exercise_ids)
    counted_passes = 0
    first_pass_at = None
    last_counted_pass_at = None

    if not remaining:
        return counted_passes, first_pass_at, last_counted_pass_at

    for attempt in attempts:
        exercise_id = attempt["id"][:6]
        error_tally = attempt["error_tally"]
        if isinstance(error_tally, int) and error_tally > 0:
            continue
        if exercise_id not in remaining:
            continue

        remaining.remove(exercise_id)
        if not remaining:
            counted_passes += 1
            completed_at = attempt["performed_at"]
            first_pass_at = first_pass_at or completed_at
            last_counted_pass_at = completed_at
            if counted_passes >= cap:
                break
            remaining = set(exercise_ids)

    return counted_passes, first_pass_at, last_counted_pass_at


def rebuild_period_progress(assignment, performance_data, occurred_at):
    period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)
    period_attempts = []
    for attempt in performance_data.data:
        performed_at = parse_datetime(attempt["performed_at"])
        performed_at = performed_at.replace(tzinfo=timezone.utc)
        if period_start <= timezone.localtime(performed_at) < period_end:
            period_attempts.append(
                {
                    **attempt,
                    "performed_at": timezone.localtime(performed_at),
                }
            )

    counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
        performance_data.playlist.exercise_list,
        period_attempts,
        cap=assignment.required_passes_per_period,
    )

    progress, _ = RecurringPlaylistPeriodProgress.objects.update_or_create(
        user=performance_data.user,
        course=performance_data.course,
        playlist=performance_data.playlist,
        period_start=period_start,
        defaults={
            "period_end": period_end,
            "counted_passes": counted_passes,
            "required_passes": assignment.required_passes_per_period,
            "target_met": counted_passes >= assignment.required_passes_per_period,
            "first_pass_at": first_pass_at,
            "last_counted_pass_at": last_counted_pass_at,
        },
    )
    return progress
```

- [ ] **Step 4: Run the tests to verify cycle counting works**

Run: `./manage.py test apps.exercises.tests.test_recurring_progress.RecurringCycleCountingTests -v 2`
Expected: `OK` with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/recurrence.py apps/exercises/tests/test_recurring_progress.py
git commit -m "feat: rebuild recurring progress from raw attempts"
```

### Task 3: Hook Recurrence Refresh Into Performance Submission

**Files:**
- Modify: `apps/exercises/models.py`
- Modify: `apps/exercises/tests/test_recurring_progress.py`

- [ ] **Step 1: Write the failing submit-flow tests**

```python
from apps.exercises.models import (
    Course,
    Exercise,
    ExercisePlaylistOrdered,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
    RecurringPlaylistPeriodProgress,
)


class RecurringSubmitFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.student = User.objects.create_user("student@example.com", "secret")
        self.exercise = Exercise.objects.create(
            description="Chord",
            data={"type": "analytical", "chord": [{"visible": [60], "hidden": []}]},
            rhythm="w",
            authored_by=self.teacher,
        )
        self.playlist = Playlist.objects.create(name="Recurring Drill", authored_by=self.teacher)
        ExercisePlaylistOrdered.objects.create(playlist=self.playlist, exercise=self.exercise, order=1)
        self.course = Course.objects.create(title="Theory I", authored_by=self.teacher)
        PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=True,
            recurrence_unit="day",
            required_passes_per_period=2,
            recurrence_starts_on=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
        )

    def test_submit_refreshes_recurring_progress_for_recurring_assignments(self):
        payload = {"error_tally": 0, "tempo_rating": None, "performance_duration_in_seconds": 3.5}
        PerformanceData.submit(self.student.pk, self.course.pk, self.playlist.pk, self.exercise.id, payload)
        PerformanceData.submit(self.student.pk, self.course.pk, self.playlist.pk, self.exercise.id, payload)

        progress = RecurringPlaylistPeriodProgress.objects.get(
            user=self.student,
            course=self.course,
            playlist=self.playlist,
        )

        self.assertEqual(progress.counted_passes, 2)
        self.assertTrue(progress.target_met)

    def test_submit_leaves_non_recurring_assignments_without_progress_rows(self):
        PlaylistCourseOrdered.objects.filter(course=self.course, playlist=self.playlist).update(is_recurring=False)
        payload = {"error_tally": 0, "tempo_rating": None, "performance_duration_in_seconds": 3.5}
        PerformanceData.submit(self.student.pk, self.course.pk, self.playlist.pk, self.exercise.id, payload)

        self.assertFalse(
            RecurringPlaylistPeriodProgress.objects.filter(
                user=self.student,
                course=self.course,
                playlist=self.playlist,
            ).exists()
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./manage.py test apps.exercises.tests.test_recurring_progress.RecurringSubmitFlowTests -v 2`
Expected: `DoesNotExist` for `RecurringPlaylistPeriodProgress` or `AssertionError` because `PerformanceData.submit()` does not refresh recurrence yet.

- [ ] **Step 3: Add the submission hook**

```python
# apps/exercises/models.py

from apps.exercises.utils.recurrence import rebuild_period_progress


class PerformanceData(models.Model):
    @classmethod
    def submit(cls, user_id: int, course_id: int, playlist_id: int, exercise_id: str, data: dict):
        pd, _ = cls.objects.get_or_create(
            user_id=user_id,
            course_id=course_id,
            playlist_id=playlist_id,
        )
        exercise_data = dict(
            **data,
            id=exercise_id,
            performed_at=dateformat.format(now(), "Y-m-d H:i:s"),
        )
        pd.data.append(exercise_data)
        pd.full_clean()
        pd.save()

        if course_id:
            assignment = PlaylistCourseOrdered.objects.filter(
                course_id=course_id,
                playlist_id=playlist_id,
                is_recurring=True,
            ).first()
            if assignment:
                rebuild_period_progress(
                    assignment=assignment,
                    performance_data=pd,
                    occurred_at=now(),
                )

        return pd
```

- [ ] **Step 4: Run the tests to verify submit refresh works**

Run: `./manage.py test apps.exercises.tests.test_recurring_progress.RecurringSubmitFlowTests -v 2`
Expected: `OK` with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/models.py apps/exercises/tests/test_recurring_progress.py
git commit -m "feat: refresh recurring progress on submit"
```

### Task 4: Expose Recurrence Settings In Course Editing

**Files:**
- Modify: `apps/dashboard/forms.py`
- Create: `apps/dashboard/tests/__init__.py`
- Create: `apps/dashboard/tests/test_recurring_playlist_views.py`

- [ ] **Step 1: Write the failing form test**

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.dashboard.forms import DashboardCourseForm
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered


class DashboardCourseFormRecurringTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.playlist = Playlist.objects.create(name="Recurring Drill", authored_by=self.teacher)
        self.course = Course.objects.create(title="Theory I", authored_by=self.teacher)

    def test_clean_parses_recurrence_fields_for_playlist_assignments(self):
        form = DashboardCourseForm(
            data={
                "title": self.course.title,
                "timely_credit": "1.0",
                "tardy_credit": "0.9",
                "late_credit": "0.6",
                "tardy_threshold": "120",
                "visible_to": [],
                "playlists": [
                    (
                        self.playlist.id,
                        {
                            "order": 1,
                            "publish_date": None,
                            "due_date": None,
                            "is_recurring": "true",
                            "recurrence_unit": "week",
                            "required_passes_per_period": "3",
                            "recurrence_starts_on": "2026-04-08",
                        },
                    )
                ],
            },
            instance=self.course,
            user=self.teacher,
        )
        form.context = {"user": self.teacher}
        self.assertTrue(form.is_valid(), form.errors)
        playlist, through_data = form.cleaned_data["playlists"][0]
        self.assertEqual(playlist, self.playlist)
        self.assertTrue(through_data["is_recurring"])
        self.assertEqual(through_data["recurrence_unit"], "week")
        self.assertEqual(through_data["required_passes_per_period"], 3)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./manage.py test apps.dashboard.tests.test_recurring_playlist_views.DashboardCourseFormRecurringTests -v 2`
Expected: `AssertionError` because the recurrence fields are not parsed from the `ManyField` payload.

- [ ] **Step 3: Add recurrence fields to the dashboard course form**

```python
# apps/dashboard/forms.py

playlists = ManyField(
    order_attr="order",
    format_title=lambda p: p.id + (f" • {p.name}" if p.name else ""),
    additional_fields=[
        {"attr_name": "publish_date", "placeholder": "Publish Date (YYYY-MM-DD)"},
        {"attr_name": "due_date", "placeholder": "Due Date (YYYY-MM-DD)"},
        {"attr_name": "is_recurring", "placeholder": "Recurring (true/false)"},
        {"attr_name": "recurrence_unit", "placeholder": "Recurrence Unit (day|week)"},
        {"attr_name": "required_passes_per_period", "placeholder": "Required Passes"},
        {"attr_name": "recurrence_starts_on", "placeholder": "Recurrence Start (YYYY-MM-DD)"},
    ],
    through_prepare=lambda through_values: {
        **through_values,
        "publish_date": through_values["publish_date"].strftime(course_date_format) if through_values["publish_date"] else None,
        "due_date": through_values["due_date"].strftime(course_date_format) if through_values["due_date"] else None,
        "recurrence_starts_on": through_values["recurrence_starts_on"].strftime(course_date_format) if through_values.get("recurrence_starts_on") else None,
    },
    csv=True,
    id_attr="id",
    additional_html=render_to_string("dashboard/date-increment-button.html"),
)


def clean(self):
    self.cleaned_data["playlists"] = [
        (Playlist.objects.get(id=value_pair[0]), value_pair[1])
        for value_pair in self.cleaned_data["playlists"]
    ]
    for value_pair in self.cleaned_data["playlists"]:
        value_pair[1]["is_recurring"] = str(value_pair[1].get("is_recurring", "")).lower() in ["1", "true", "yes", "on"]
        if value_pair[1].get("required_passes_per_period"):
            value_pair[1]["required_passes_per_period"] = int(value_pair[1]["required_passes_per_period"])
        else:
            value_pair[1]["required_passes_per_period"] = 1
        if value_pair[1].get("recurrence_starts_on"):
            value_pair[1]["recurrence_starts_on"] = datetime.strptime(value_pair[1]["recurrence_starts_on"], course_date_format)
    return super().clean()
```

- [ ] **Step 4: Run the test to verify the form parses recurrence fields**

Run: `./manage.py test apps.dashboard.tests.test_recurring_playlist_views.DashboardCourseFormRecurringTests -v 2`
Expected: `OK` with 1 test passing.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/forms.py apps/dashboard/tests/__init__.py apps/dashboard/tests/test_recurring_playlist_views.py
git commit -m "feat: add recurring settings to course form"
```

### Task 5: Show Recurring Progress In My Work And The Gradebook

**Files:**
- Modify: `apps/exercises/utils/recurrence.py`
- Modify: `apps/dashboard/views/my_work.py`
- Modify: `apps/dashboard/views/courses.py`
- Modify: `apps/dashboard/tables.py`
- Modify: `apps/dashboard/templates/dashboard/my-work.html`
- Modify: `apps/dashboard/tests/test_recurring_playlist_views.py`

- [ ] **Step 1: Write the failing dashboard view tests**

```python
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Group, User
from apps.exercises.models import (
    Course,
    Playlist,
    PlaylistCourseOrdered,
    RecurringPlaylistPeriodProgress,
)


class RecurringPlaylistDashboardViewTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.student = User.objects.create_user("student@example.com", "secret", first_name="Student", last_name="One")
        self.group = Group.objects.create(name="Section A", manager=self.teacher)
        self.group.members.add(self.student)
        self.playlist = Playlist.objects.create(name="Recurring Drill", authored_by=self.teacher)
        self.course = Course.objects.create(title="Theory I", authored_by=self.teacher)
        self.course.visible_to.add(self.group)
        self.assignment = PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=True,
            recurrence_unit="week",
            required_passes_per_period=3,
            recurrence_starts_on=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
        )
        period_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        RecurringPlaylistPeriodProgress.objects.create(
            user=self.student,
            course=self.course,
            playlist=self.playlist,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            counted_passes=2,
            required_passes=3,
            target_met=False,
        )
        RecurringPlaylistPeriodProgress.objects.create(
            user=self.student,
            course=self.course,
            playlist=self.playlist,
            period_start=period_start - timedelta(days=7),
            period_end=period_start,
            counted_passes=3,
            required_passes=3,
            target_met=True,
        )

    def test_my_work_shows_current_progress_and_completed_periods(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard:my-work"))
        self.assertContains(response, "2 of 3 this week")
        self.assertContains(response, "1 periods completed")

    def test_course_activity_csv_includes_recurring_status_text(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("dashboard:course-activity", args=[self.course.id]) + "?format=csv")
        self.assertContains(response, "2 of 3 this week")
        self.assertContains(response, "1 periods met")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./manage.py test apps.dashboard.tests.test_recurring_playlist_views.RecurringPlaylistDashboardViewTests -v 2`
Expected: My Work still renders one-time status and the gradebook CSV does not include recurring progress.

- [ ] **Step 3: Add recurring read helpers and wire the dashboard views**

```python
# apps/exercises/utils/recurrence.py

def get_recurring_assignment_snapshot(user, assignment, occurred_at=None):
    occurred_at = occurred_at or timezone.now()
    period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)
    current_progress = RecurringPlaylistPeriodProgress.objects.filter(
        user=user,
        course=assignment.course,
        playlist=assignment.playlist,
        period_start=period_start,
    ).first()
    completed_periods = RecurringPlaylistPeriodProgress.objects.filter(
        user=user,
        course=assignment.course,
        playlist=assignment.playlist,
        target_met=True,
    ).count()
    counted_passes = current_progress.counted_passes if current_progress else 0
    required_passes = assignment.required_passes_per_period
    period_label = "today" if assignment.recurrence_unit == "day" else "this week"
    return {
        "is_recurring": True,
        "counted_passes": counted_passes,
        "required_passes": required_passes,
        "progress_label": f"{counted_passes} of {required_passes} {period_label}",
        "target_met": counted_passes >= required_passes,
        "completed_periods": completed_periods,
        "next_reset_at": period_end,
    }


# apps/dashboard/views/my_work.py

from apps.exercises.utils.recurrence import get_recurring_assignment_snapshot


for pco in pcos:
    playlist = pco.playlist
    if pco.is_recurring:
        recurring = get_recurring_assignment_snapshot(request.user, pco)
        playlists_data.append(
            {
                "playlist": playlist,
                "due_date": pco.due_date,
                "passed": recurring["target_met"],
                "pass_date": None,
                "mark_code": None,
                "mark_label": recurring["progress_label"],
                "mark_class": "badge-success" if recurring["target_met"] else "badge-warning",
                "course_id": course.id,
                "is_recurring": True,
                "completed_periods": recurring["completed_periods"],
                "next_reset_at": recurring["next_reset_at"],
            }
        )
        continue


# apps/dashboard/views/courses.py

from apps.exercises.utils.recurrence import get_recurring_assignment_snapshot


recurring_assignments = {
    pco.playlist.id: pco
    for pco in course_pcos
    if pco.is_recurring
}

for performer, performance_data in relevant_data.items():
    for playlist_id, assignment in recurring_assignments.items():
        snapshot = get_recurring_assignment_snapshot(performer, assignment)
        relevant_data[performer][str(playlist_id)] = {
            "kind": "recurring",
            "progress_label": snapshot["progress_label"],
            "completed_periods": snapshot["completed_periods"],
            "target_met": snapshot["target_met"],
        }
```

```python
# apps/dashboard/tables.py

class PlaylistActivityColumn(columns.Column):
    def render(self, value):
        if isinstance(value, dict) and value.get("kind") == "recurring":
            icon = '<span class="true due-date-on-time" title="Recurring assignment"></span>' if value["target_met"] else '<span class="false did-not-finish" title="Recurring assignment"></span>'
            return format_html(
                "{} {}<br><small>{} periods met</small>",
                mark_safe(icon),
                value["progress_label"],
                value["completed_periods"],
            )
        return super().render(value)


class CourseActivityTable(tables.Table):
    def render_score(self, record):
        recurring_points = 0
        result_count = {"P": 0, "C": 0, "T": 0, "L": 0, "X": 0}
        for value in record.values():
            if isinstance(value, dict) and value.get("kind") == "recurring":
                recurring_points += value["completed_periods"] * self.course.timely_credit
            elif value in result_count:
                result_count[value] += 1
        one_time_points = (
            result_count["P"] * self.course.timely_credit
            + result_count["C"] * self.course.timely_credit
            + result_count["T"] * self.course.tardy_credit
            + result_count["L"] * self.course.late_credit
        )
        return round(one_time_points + recurring_points, 1)
```

```html
<!-- apps/dashboard/templates/dashboard/my-work.html -->

<td>
    {% if item.is_recurring %}
        <span class="badge {{ item.mark_class }}">{{ item.mark_label }}</span>
        <div><small>{{ item.completed_periods }} periods completed</small></div>
    {% elif item.passed %}
        {% if item.mark_label %}
            <span class="badge {{ item.mark_class }}">{{ item.mark_label }}</span>
        {% else %}
            <span class="badge badge-success">Complete</span>
        {% endif %}
    {% else %}
        <span class="badge badge-secondary">Not complete</span>
    {% endif %}
</td>
```

- [ ] **Step 4: Run the dashboard tests to verify the recurring views now render correctly**

Run: `./manage.py test apps.dashboard.tests.test_recurring_playlist_views.RecurringPlaylistDashboardViewTests -v 2`
Expected: `OK` with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/recurrence.py apps/dashboard/views/my_work.py apps/dashboard/views/courses.py apps/dashboard/tables.py apps/dashboard/templates/dashboard/my-work.html apps/dashboard/tests/test_recurring_playlist_views.py
git commit -m "feat: show recurring progress in dashboard views"
```

### Task 6: Run Regression Coverage For One-Time Playlists

**Files:**
- Modify: `apps/dashboard/tests/test_recurring_playlist_views.py`
- Modify: `apps/exercises/tests/test_recurring_progress.py`

- [ ] **Step 1: Add explicit regression tests for non-recurring behavior**

```python
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Group, User
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered


class LegacyPlaylistRegressionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.student = User.objects.create_user("student@example.com", "secret", first_name="Student", last_name="One")
        self.group = Group.objects.create(name="Section A", manager=self.teacher)
        self.group.members.add(self.student)
        self.playlist = Playlist.objects.create(name="One-Time Drill", authored_by=self.teacher)
        self.course = Course.objects.create(title="Theory I", authored_by=self.teacher)
        self.course.visible_to.add(self.group)
        PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=False,
        )
        self.course.performance_dict = {
            str(self.student): {self.playlist.id: "P", "time_elapsed": 10, "reset": True},
            str(self.teacher): {},
        }
        self.course.save()

    def test_non_recurring_my_work_still_shows_complete_badge(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard:my-work"))
        self.assertNotContains(response, "periods completed")

    def test_non_recurring_rows_still_use_mark_codes_in_gradebook(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("dashboard:course-activity", args=[self.course.id]))
        self.assertContains(response, "title=\"On time\"")
```

- [ ] **Step 2: Run the targeted regression tests and verify they fail if behavior drifted**

Run: `./manage.py test apps.dashboard.tests.test_recurring_playlist_views apps.exercises.tests.test_recurring_progress -v 2`
Expected: all tests pass; if one fails, fix the regression before moving on.

- [ ] **Step 3: Run the broader dashboard and exercises suites**

Run: `./manage.py test apps.dashboard apps.exercises -v 2`
Expected: `OK` with all dashboard and exercises tests passing.

- [ ] **Step 4: Run migrations check**

Run: `./manage.py makemigrations --check`
Expected: `No changes detected`

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/tests/test_recurring_playlist_views.py apps/exercises/tests/test_recurring_progress.py
git commit -m "test: cover recurring and legacy playlist flows"
```

## Self-Review

- Spec coverage: the plan covers schema, recurrence math, greedy cycle reconstruction, submit-flow integration, teacher editing, My Work rendering, gradebook rendering, CSV output, migration behavior, and non-recurring regressions.
- Placeholder scan: no `TODO`, `TBD`, or task references without concrete files, code, or commands remain.
- Type consistency: the plan uses one naming set throughout: `RecurringPlaylistPeriodProgress`, `get_assignment_period_bounds`, `count_playlist_cycles`, `rebuild_period_progress`, and `get_recurring_assignment_snapshot`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-08-recurring-playlist-assignments.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?