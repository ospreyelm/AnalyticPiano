"""Tests for teacher library hub browse, preview, and search views."""

import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.exercises.models import Exercise
from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.teacher.tests.test_views_db import (
    _make_playlist,
    _make_superuser,
    _make_teacher,
)


def _make_exercise(author, public=False, description="Reviewable Exercise"):
    return save_chordal_umto_exercise(
        description=description,
        author=author,
        chords=[{"offset": 0.0, "duration": 4.0, "visible": [60, 64, 67], "hidden": []}],
        key="C",
        meter="4/4",
        clef="keyboard",
        staff_distribution="keyboard",
        source="test",
        skill_tags=["unit:9"],
        complexity=1,
        is_public=public,
        auto_playlist=False,
    )


class LibraryHubAccessTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def test_anonymous_redirected(self):
        response = Client().get(reverse("teacher:library-hub"))

        self.assertEqual(response.status_code, 302)

    def test_teacher_gets_playlists_tab_by_default(self):
        response = self.client.get(reverse("teacher:library-hub"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tab"], "playlists")

    def test_teacher_gets_exercises_tab(self):
        response = self.client.get(reverse("teacher:library-hub") + "?tab=exercises")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tab"], "exercises")

    def test_official_tab_403_for_regular_teacher(self):
        response = self.client.get(reverse("teacher:library-hub") + "?tab=official")

        self.assertEqual(response.status_code, 403)

    def test_official_tab_200_for_superuser(self):
        superuser = _make_superuser()
        client = Client()
        client.login(email=superuser.email, password="pass")

        response = client.get(reverse("teacher:library-hub") + "?tab=official")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tab"], "official")

    def test_own_playlist_appears_in_list(self):
        playlist = _make_playlist(self.teacher, name="Mine")

        response = self.client.get(reverse("teacher:library-hub") + "?tab=playlists")

        self.assertIn(playlist, response.context["playlists"])

    def test_public_playlist_from_other_teacher_appears(self):
        other = _make_teacher(email="other@example.com")
        playlist = _make_playlist(other, name="Public")
        playlist.is_public = True
        playlist.save(update_fields=["is_public"])

        response = self.client.get(reverse("teacher:library-hub") + "?tab=playlists")

        self.assertIn(playlist, response.context["playlists"])

    def test_private_other_teacher_playlist_hidden(self):
        other = _make_teacher(email="other@example.com")
        playlist = _make_playlist(other, name="Private")

        response = self.client.get(reverse("teacher:library-hub") + "?tab=playlists")

        self.assertNotIn(playlist, response.context["playlists"])

    def test_pending_content_shows_in_official_tab_for_superuser(self):
        playlist = _make_playlist(self.teacher, name="Pending")
        playlist.official_review_status = Exercise.REVIEW_PENDING
        playlist.save(update_fields=["official_review_status"])
        exercise = _make_exercise(self.teacher, public=True)
        exercise.official_review_status = Exercise.REVIEW_PENDING
        exercise.save(update_fields=["official_review_status"])
        superuser = _make_superuser()
        client = Client()
        client.login(email=superuser.email, password="pass")

        response = client.get(reverse("teacher:library-hub") + "?tab=official")

        self.assertIn(playlist, response.context["pending_playlists"])
        self.assertIn(exercise, response.context["pending_exercises"])


class ExercisePreviewTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")
        self.exercise = _make_exercise(self.teacher)

    def test_preview_returns_score_data(self):
        response = self.client.get(
            reverse("teacher:exercise-preview", args=[self.exercise.id])
        )

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertIn("score_data", body)
        self.assertIsNotNone(body["score_data"])

    def test_preview_public_other_exercise_allowed(self):
        other = _make_teacher(email="other@example.com")
        exercise = _make_exercise(other, public=True)

        response = self.client.get(reverse("teacher:exercise-preview", args=[exercise.id]))

        self.assertEqual(response.status_code, 200)

    def test_preview_private_other_exercise_404(self):
        other = _make_teacher(email="other@example.com")
        exercise = _make_exercise(other, public=False)

        response = self.client.get(reverse("teacher:exercise-preview", args=[exercise.id]))

        self.assertEqual(response.status_code, 404)


class ExerciseDetailInputStyleTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def test_per_voice_input_style_appears_in_umto_meta(self):
        exercise = _make_exercise(self.teacher)
        exercise.data["score"]["umto"]["metadata"]["input_style"] = "per_voice"
        exercise.save(update_fields=["data"])

        response = self.client.get(
            reverse("teacher:exercise-detail", args=[exercise.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["umto_meta"]["input_style"], "per_voice")

    def test_missing_input_style_omits_without_error(self):
        exercise = _make_exercise(self.teacher)

        response = self.client.get(
            reverse("teacher:exercise-detail", args=[exercise.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["umto_meta"]["input_style"], "")


class ExercisesSearchTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def test_search_returns_own_exercise(self):
        exercise = _make_exercise(self.teacher, description="Unique name XYZ")

        response = self.client.get(
            reverse("teacher:exercises-search") + "?q=Unique+name+XYZ"
        )

        self.assertEqual(response.status_code, 200)
        ids = [result["id"] for result in json.loads(response.content)["results"]]
        self.assertIn(exercise.id, ids)

    def test_search_hides_private_other_exercise(self):
        other = _make_teacher(email="other@example.com")
        exercise = _make_exercise(other, public=False, description="Hidden needle")

        response = self.client.get(reverse("teacher:exercises-search") + "?q=Hidden")

        self.assertEqual(response.status_code, 200)
        ids = [result["id"] for result in json.loads(response.content)["results"]]
        self.assertNotIn(exercise.id, ids)

    def test_search_filters_by_unit_tag(self):
        exercise = _make_exercise(self.teacher, description="Tagged")
        other = _make_exercise(self.teacher, description="Untagged")
        other.skill_tags = ["unit:10"]
        other.save(update_fields=["skill_tags"])

        response = self.client.get(reverse("teacher:exercises-search") + "?unit=9")

        self.assertEqual(response.status_code, 200)
        ids = [result["id"] for result in json.loads(response.content)["results"]]
        self.assertIn(exercise.id, ids)
        self.assertNotIn(other.id, ids)
