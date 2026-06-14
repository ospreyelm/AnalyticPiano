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
