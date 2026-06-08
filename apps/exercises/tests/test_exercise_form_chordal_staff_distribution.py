import copy
import json

from django.forms.widgets import HiddenInput
from django.test import TestCase

from apps.accounts.models import User
from apps.dashboard.forms import DashboardExerciseForm
from apps.exercises.models import Exercise
from apps.exercises.tests.umto_test_helpers import make_umto_exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import build_chordal_umto_payload


class ChordalUMTOStaffDistributionFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="teacher@example.com",
            password="pw",
        )

    def _create_chordal_exercise(self, staff_distribution="grandStaff"):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal staff distribution fixture",
            key="C",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [48, 60, 64]},
            ],
            analysis=[],
        )
        payload["score"]["umto"]["metadata"]["staffDistribution"] = staff_distribution
        payload["staffDistribution"] = "keyboard"
        return Exercise.objects.create(
            description="Chordal UMTO",
            data=payload,
            authored_by=self.user,
            complexity=1,
            skill_tags=["unit:1"],
        )

    def _post_data(self, exercise, *, staff_distribution):
        return {
            "description": exercise.description,
            "is_public": "on" if exercise.is_public else "",
            "tags": exercise.tags,
            "rhythm": exercise.rhythm or "",
            "complexity": str(exercise.complexity),
            "visibility_pattern": "",
            "time_signature": "",
            "semibreves_per_line": "",
            "intro_text": exercise.data.get("introText", ""),
            "type": "umto_chorale",
            "staff_distribution": staff_distribution,
            "chorale_mode": "play-all-voices",
            "chorale_label_mode": "none",
            "chorale_transpose": "",
            "chorale_tempo": "60",
            "chorale_onset_window_ms": "150",
            "chorale_release_tolerance_pct": "40",
            "chorale_chord_member_min": "",
            "chorale_excerpt_start": "",
            "chorale_excerpt_end": "",
            "ident_mode": "submit",
            "compound_intervals": "",
            "data": json.dumps(exercise.data),
        }

    def test_chordal_umto_exposes_staff_distribution_from_metadata(self):
        exercise = self._create_chordal_exercise(staff_distribution="LH")

        form = DashboardExerciseForm(instance=exercise)

        field = form.fields["staff_distribution"]
        self.assertNotIsInstance(field.widget, HiddenInput)
        self.assertEqual(field.initial, "LH")
        self.assertNotIn("chorale", [value for value, _label in field.choices])

    def test_chordal_umto_staff_distribution_save_updates_metadata_and_mirror(self):
        exercise = self._create_chordal_exercise(staff_distribution="keyboard")
        form = DashboardExerciseForm(
            data=self._post_data(exercise, staff_distribution="RH"),
            instance=exercise,
        )
        form.context = {"user": self.user}

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()

        saved.refresh_from_db()
        metadata = saved.data["score"]["umto"]["metadata"]
        self.assertEqual(metadata["staffDistribution"], "RH")
        self.assertEqual(saved.data["staffDistribution"], "RH")

    def test_chordal_umto_initial_falls_back_to_top_level_then_keyboard(self):
        exercise = self._create_chordal_exercise(staff_distribution="LH")
        metadata = exercise.data["score"]["umto"]["metadata"]
        metadata.pop("staffDistribution", None)
        exercise.data["staffDistribution"] = "grandStaff"
        exercise.save()

        form = DashboardExerciseForm(instance=exercise)
        self.assertEqual(form.fields["staff_distribution"].initial, "grandStaff")

        exercise.data["staffDistribution"] = ""
        exercise.save()
        form = DashboardExerciseForm(instance=exercise)
        self.assertEqual(form.fields["staff_distribution"].initial, "keyboard")

    def test_voices_kind_umto_still_hides_staff_distribution_and_forces_chorale(self):
        exercise = make_umto_exercise(
            author=self.user,
            description="SATB UMTO",
            complexity=1,
            unit=1,
        )
        form = DashboardExerciseForm(instance=exercise)
        self.assertIsInstance(form.fields["staff_distribution"].widget, HiddenInput)
        self.assertEqual(form.fields["staff_distribution"].initial, "chorale")

        posted = self._post_data(exercise, staff_distribution="RH")
        posted["data"] = json.dumps(copy.deepcopy(exercise.data))
        form = DashboardExerciseForm(data=posted, instance=exercise)
        form.context = {"user": self.user}

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()

        saved.refresh_from_db()
        self.assertEqual(saved.data["staffDistribution"], "chorale")
