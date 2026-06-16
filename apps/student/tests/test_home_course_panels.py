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
