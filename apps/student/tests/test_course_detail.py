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
        """Panel shows 'open' badge when there are open assignments."""
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

    def test_home_panel_progress_is_pco_row_averaged(self):
        """Two PCOs in same unit: one 100%, one 0% → panel shows 50%, not 100/0."""
        pl_done = Playlist(
            name="Unit 9 — Done", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9"],
        )
        pl_done.save()
        from apps.exercises.tests.umto_test_helpers import make_umto_exercise
        ex = make_umto_exercise(author=self.teacher, unit=9)
        ExercisePlaylistOrdered.objects.create(playlist=pl_done, exercise=ex, order=1)
        PerformanceData.objects.create(
            user=self.student,
            playlist=pl_done,
            data=[{"id": ex.id, "score_numerator": 1, "score_denominator": 1}],
        )
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl_done, order=1,
        )

        # Second playlist for same unit:9, no progress
        pl_empty = Playlist(
            name="Unit 9 — Identification", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9"],
        )
        pl_empty.save()
        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl_empty, order=2,
        )

        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)
        panels = response.context["course_panels"]
        self.assertEqual(len(panels), 1)
        # 100% + 0% averaged across 2 PCO rows = 50%, not 100 (unit-level) or 0
        self.assertEqual(panels[0]["progress_pct"], 50)


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
        pl = Playlist(
            name="Unit 9 — Done", authored_by=self.teacher,
            is_public=True, skill_tags=["unit:9"],
        )
        pl.save()
        from apps.exercises.tests.umto_test_helpers import make_umto_exercise
        ex = make_umto_exercise(author=self.teacher, unit=9)
        ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex, order=1)

        PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=pl, order=1,
            publish_date=now() - timedelta(days=1),
        )
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
