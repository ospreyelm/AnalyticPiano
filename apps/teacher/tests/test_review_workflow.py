"""Tests for teacher library official review workflow endpoints."""

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.teacher.tests.test_views_db import (
    _make_playlist,
    _make_superuser,
    _make_teacher,
)


def _make_exercise(author, public=False):
    return save_chordal_umto_exercise(
        description="Reviewable Exercise",
        author=author,
        chords=[{"offset": 0.0, "duration": 4.0, "visible": [60, 64, 67], "hidden": []}],
        key="C",
        meter="4/4",
        clef="keyboard",
        staff_distribution="keyboard",
        source="test",
        skill_tags=[],
        complexity=1,
        is_public=public,
        auto_playlist=False,
    )


class PlaylistReviewWorkflowTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")
        self.playlist = _make_playlist(self.teacher, name="Review Playlist")

    def test_submit_requires_public_playlist(self):
        response = self.client.post(
            reverse("teacher:playlist-submit-review", args=[self.playlist.id])
        )

        self.assertEqual(response.status_code, 400)
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.official_review_status, "none")

    def test_submit_sets_pending(self):
        self.playlist.is_public = True
        self.playlist.save(update_fields=["is_public"])

        response = self.client.post(
            reverse("teacher:playlist-submit-review", args=[self.playlist.id])
        )

        self.assertEqual(response.status_code, 200)
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.official_review_status, "pending")

    def test_double_submit_rejected(self):
        self.playlist.is_public = True
        self.playlist.official_review_status = "pending"
        self.playlist.save(update_fields=["is_public", "official_review_status"])

        response = self.client.post(
            reverse("teacher:playlist-submit-review", args=[self.playlist.id])
        )

        self.assertEqual(response.status_code, 400)

    def test_other_teacher_cannot_submit_playlist(self):
        other = _make_teacher(email="other@example.com")
        self.playlist.is_public = True
        self.playlist.save(update_fields=["is_public"])
        client = Client()
        client.login(email=other.email, password="pass")

        response = client.post(
            reverse("teacher:playlist-submit-review", args=[self.playlist.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_approve_requires_superuser(self):
        response = self.client.post(
            reverse("teacher:playlist-approve", args=[self.playlist.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_approve_assigns_factory_account_and_marks_official(self):
        superuser = _make_superuser()
        client = Client()
        client.login(email=superuser.email, password="pass")

        response = client.post(reverse("teacher:playlist-approve", args=[self.playlist.id]))

        self.assertEqual(response.status_code, 200)
        self.playlist.refresh_from_db()
        self.assertTrue(self.playlist.is_official)
        self.assertEqual(self.playlist.official_review_status, "approved")
        self.assertEqual(self.playlist.authored_by.email, settings.FACTORY_USER_EMAIL)

    def test_reject_by_superuser_resets_status(self):
        self.playlist.official_review_status = "pending"
        self.playlist.save(update_fields=["official_review_status"])
        superuser = _make_superuser()
        client = Client()
        client.login(email=superuser.email, password="pass")

        response = client.post(reverse("teacher:playlist-reject", args=[self.playlist.id]))

        self.assertEqual(response.status_code, 200)
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.official_review_status, "none")


class ExerciseReviewWorkflowTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")
        self.exercise = _make_exercise(self.teacher, public=False)

    def test_submit_requires_public_exercise(self):
        response = self.client.post(
            reverse("teacher:exercise-submit-review", args=[self.exercise.id])
        )

        self.assertEqual(response.status_code, 400)

    def test_submit_sets_pending(self):
        self.exercise.is_public = True
        self.exercise.save(update_fields=["is_public"])

        response = self.client.post(
            reverse("teacher:exercise-submit-review", args=[self.exercise.id])
        )

        self.assertEqual(response.status_code, 200)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.official_review_status, "pending")

    def test_approve_requires_superuser(self):
        response = self.client.post(
            reverse("teacher:exercise-approve", args=[self.exercise.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_approve_assigns_factory_account_and_marks_official(self):
        superuser = _make_superuser()
        client = Client()
        client.login(email=superuser.email, password="pass")

        response = client.post(reverse("teacher:exercise-approve", args=[self.exercise.id]))

        self.assertEqual(response.status_code, 200)
        self.exercise.refresh_from_db()
        self.assertTrue(self.exercise.is_official)
        self.assertEqual(self.exercise.official_review_status, "approved")
        self.assertEqual(self.exercise.authored_by.email, settings.FACTORY_USER_EMAIL)

    def test_reject_by_superuser_resets_status(self):
        self.exercise.official_review_status = "pending"
        self.exercise.save(update_fields=["official_review_status"])
        superuser = _make_superuser()
        client = Client()
        client.login(email=superuser.email, password="pass")

        response = client.post(reverse("teacher:exercise-reject", args=[self.exercise.id]))

        self.assertEqual(response.status_code, 200)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.official_review_status, "none")
