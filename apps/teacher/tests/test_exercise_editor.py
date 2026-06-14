"""Tests for teacher-app exercise editor views."""

import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.teacher.tests.test_views_db import _make_teacher


def _make_exercise(author, public=False):
    return save_chordal_umto_exercise(
        description="Ex",
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


class ExerciseDetailTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.exercise = _make_exercise(self.teacher)
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def test_get_200(self):
        response = self.client.get(
            reverse("teacher:exercise-detail", args=[self.exercise.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ex")

    def test_private_other_exercise_404(self):
        other = _make_teacher(email="other@example.com")
        exercise = _make_exercise(other, public=False)

        response = self.client.get(reverse("teacher:exercise-detail", args=[exercise.id]))

        self.assertEqual(response.status_code, 404)

    def test_context_has_analysis_type_choices(self):
        response = self.client.get(
            reverse("teacher:exercise-detail", args=[self.exercise.id])
        )

        self.assertIn("analysis_type_choices", response.context)
        tokens = [token for token, _label in response.context["analysis_type_choices"]]
        self.assertIn("roman", tokens)
        self.assertIn("figured_bass", tokens)

    def test_can_edit_own_exercise(self):
        response = self.client.get(
            reverse("teacher:exercise-detail", args=[self.exercise.id])
        )

        self.assertTrue(response.context["can_edit"])

    def test_cannot_edit_others_public_exercise(self):
        other = _make_teacher(email="other@example.com")
        exercise = _make_exercise(other, public=True)

        response = self.client.get(reverse("teacher:exercise-detail", args=[exercise.id]))

        self.assertFalse(response.context["can_edit"])


class ExerciseSaveTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.exercise = _make_exercise(self.teacher)
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def _post(self, payload):
        return self.client.post(
            reverse("teacher:exercise-save", args=[self.exercise.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_save_updates_description(self):
        self._post({"description": "Updated desc"})

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.description, "Updated desc")

    def test_save_trims_description_to_60_chars(self):
        self._post({"description": "x" * 100})

        self.exercise.refresh_from_db()
        self.assertLessEqual(len(self.exercise.description), 60)

    def test_save_updates_complexity(self):
        self._post({"complexity": 7})

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.complexity, 7)

    def test_save_clamps_complexity(self):
        self._post({"complexity": 99})

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.complexity, 20)

    def test_save_stores_analysis_type(self):
        self._post({"analysisType": "figured_bass"})

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.data.get("analysisType"), "figured_bass")

    def test_save_updates_skill_tags(self):
        self._post({"skill_tags": ["unit:9", "Cadence_PAC"]})

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.skill_tags, ["unit:9", "Cadence_PAC"])

    def test_other_teacher_cannot_save(self):
        other = _make_teacher(email="other@example.com")
        client = Client()
        client.login(email=other.email, password="pass")

        response = client.post(
            reverse("teacher:exercise-save", args=[self.exercise.id]),
            data=json.dumps({"description": "Stolen"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
