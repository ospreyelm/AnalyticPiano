"""Student-side course connection: due chips, /s/join/, course attribution.

Courses do not gate unit availability — they add publish/due dates and grading
attribution. These tests pin that contract.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now

from apps.accounts.models import Group
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered
from apps.student.views import (
    _get_course_unit_dates,
    _unit_date_labels,
    resolve_course_for_playlist,
)

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class CourseConnectionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=20001, email="sasha@test.com", password="pw", is_staff=False
        )
        self.teacher = User.objects.create_user(
            id=20002, email="teach@test.com", password="pw", is_staff=False
        )
        self.group = Group.objects.create(name="Theory I 2026", manager=self.teacher)
        self.group.members.add(self.student)

        self.course = Course(title="Theory I", authored_by=self.teacher, open=False)
        self.course.save()
        self.course.visible_to.add(self.group)

        self.playlist = Playlist(
            name="Unit 9 — Roman", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9", "mode:roman"],
        )
        self.playlist.save()

    def _add_pco(self, course=None, playlist=None, publish_delta=-1, due_delta=7, order=1):
        return PlaylistCourseOrdered.objects.create(
            course=course or self.course,
            playlist=playlist or self.playlist,
            order=order,
            publish_date=now() + timedelta(days=publish_delta),
            due_date=now() + timedelta(days=due_delta),
        )

    # ── course date map ─────────────────────────────────────────────────

    def test_no_enrollment_no_dates(self):
        self._add_pco()
        loner = User.objects.create_user(id=20003, email="solo@test.com", password="pw")
        self.assertEqual(_get_course_unit_dates(loner), {})

    def test_enrolled_published_unit_has_due(self):
        pco = self._add_pco()
        dates = _get_course_unit_dates(self.student)
        self.assertIn("9", dates)
        self.assertTrue(dates["9"]["published"])
        self.assertEqual(dates["9"]["due"], pco.due_date)
        labels = _unit_date_labels(dates["9"])
        self.assertIsNotNone(labels["due_label"])
        self.assertTrue(labels["due_label"].startswith("Due "))
        self.assertFalse(labels["overdue"])

    def test_unpublished_unit_gets_opens_label(self):
        self._add_pco(publish_delta=+3)
        labels = _unit_date_labels(_get_course_unit_dates(self.student).get("9"))
        self.assertIsNone(labels["due_label"])
        self.assertTrue(labels["opens_label"].startswith("Opens "))

    def test_overdue_flag(self):
        self._add_pco(publish_delta=-10, due_delta=-1)
        labels = _unit_date_labels(_get_course_unit_dates(self.student).get("9"))
        self.assertTrue(labels["overdue"])

    def test_earliest_due_wins(self):
        self._add_pco(due_delta=14, order=1)
        early = self._add_pco(due_delta=3, order=2)
        dates = _get_course_unit_dates(self.student)
        self.assertEqual(dates["9"]["due"], early.due_date)

    def test_home_renders_chip_for_enrolled_student(self):
        self._add_pco()
        self.client.force_login(self.student)
        resp = self.client.get(reverse("student:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "s-due-chip")
        self.assertContains(resp, "Due ")

    def test_home_renders_without_chips_when_not_enrolled(self):
        self._add_pco()
        loner = User.objects.create_user(id=20004, email="solo2@test.com", password="pw")
        self.client.force_login(loner)
        resp = self.client.get(reverse("student:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "s-due-chip\"")

    # ── /s/join/ ────────────────────────────────────────────────────────

    def test_join_get_prefills_code(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse("student:join") + f"?code={self.group.join_code.lower()}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.group.join_code)

    def test_join_post_enrolls_and_redirects_home(self):
        newbie = User.objects.create_user(id=20005, email="new@test.com", password="pw")
        self.client.force_login(newbie)
        resp = self.client.post(reverse("student:join"), {"join_code": self.group.join_code})
        self.assertRedirects(resp, reverse("student:home"))
        self.assertTrue(self.group.members.filter(pk=newbie.pk).exists())

    def test_join_bad_code_shows_error(self):
        self.client.force_login(self.student)
        resp = self.client.post(reverse("student:join"), {"join_code": "NOPE99"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No class found")

    def test_join_is_idempotent(self):
        self.client.force_login(self.student)
        resp = self.client.post(reverse("student:join"), {"join_code": self.group.join_code})
        self.assertRedirects(resp, reverse("student:home"))
        self.assertEqual(
            self.group.members.filter(pk=self.student.pk).count(), 1
        )

    def test_teacher_cannot_join_own_group(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(reverse("student:join"), {"join_code": self.group.join_code})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "cannot join")
        self.assertFalse(self.group.members.filter(pk=self.teacher.pk).exists())

    # ── course attribution ──────────────────────────────────────────────

    def test_resolve_course_prefers_enrolled_course(self):
        # Same playlist in two courses; student enrolled only in the second.
        other_course = Course(title="Other section", authored_by=self.teacher, open=False)
        other_course.save()
        PlaylistCourseOrdered.objects.create(
            course=other_course, playlist=self.playlist, order=1
        )
        self._add_pco(order=2)  # self.course — student's course, later order
        self.assertEqual(
            resolve_course_for_playlist(self.student, self.playlist), self.course
        )

    def test_resolve_course_falls_back_to_first(self):
        other_course = Course(title="Other section", authored_by=self.teacher, open=False)
        other_course.save()
        PlaylistCourseOrdered.objects.create(
            course=other_course, playlist=self.playlist, order=1
        )
        loner = User.objects.create_user(id=20006, email="solo3@test.com", password="pw")
        self.assertEqual(
            resolve_course_for_playlist(loner, self.playlist), other_course
        )

    def test_resolve_course_none_when_unattached(self):
        self.assertIsNone(resolve_course_for_playlist(self.student, self.playlist))
