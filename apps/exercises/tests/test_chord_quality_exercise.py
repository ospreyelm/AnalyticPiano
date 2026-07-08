from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from io import StringIO

from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.exercises.umto import InteractionMode, UMTO
from apps.exercises.models import Exercise

User = get_user_model()


class ChordQualityExerciseTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="test_author@curriculum.org",
            password="test_password"
        )

    def test_save_chord_quality_exercise(self):
        chords = [
            {
                "notes": [48, 64, 67, 72],
                "spelling": ["C3", "E4", "G4", "C5"],
                "duration": 4.0,
                "offset": 0.0,
            },
            {
                "notes": [55, 70, 74, 79],
                "spelling": ["G3", "Bb4", "D5", "G5"],
                "duration": 4.0,
                "offset": 4.0,
            }
        ]

        analysis = [
            {
                "offset": 0.0,
                "is_target": True,
                "content": {
                    "chord_quality": "major"
                }
            },
            {
                "offset": 4.0,
                "is_target": True,
                "content": {
                    "chord_quality": "minor"
                }
            }
        ]

        ex = save_chordal_umto_exercise(
            description="Unit 5 test quality",
            author=self.author,
            chords=chords,
            key="jC_",
            meter="4/4",
            clef="keyboard",
            staff_distribution="keyboard",
            skill_tags=["unit:5"],
            complexity=5,
            is_public=True,
            overwrite=True,
            barline_offsets=[4.0],
            analysis=analysis,
            mode=InteractionMode.IDENTIFICATION,
            analysis_type="chord_quality",
            allowed_answers=["major", "minor", "diminished"],
        )

        # Check payload
        self.assertEqual(ex.data["type"], "umto_chorale")
        self.assertEqual(ex.data["analysisType"], "chord_quality")
        self.assertEqual(ex.data["allowed_answers"], ["major", "minor", "diminished"])

        # Check nested UMTO
        umto_data = ex.data["score"]["umto"]
        self.assertEqual(umto_data["metadata"]["score_kind"], "chordal")
        self.assertEqual(umto_data["metadata"]["allowed_answers"], ["major", "minor", "diminished"])
        
        # Verify Analysis Layer Pydantic schema contains chord_quality
        slices = umto_data["analysis"]
        self.assertEqual(slices[0]["content"]["chord_quality"], "major")
        self.assertEqual(slices[1]["content"]["chord_quality"], "minor")

        # Verify model validation passes
        umto_obj = UMTO.model_validate(umto_data)
        self.assertEqual(umto_obj.metadata.allowed_answers, ["major", "minor", "diminished"])
        self.assertEqual(umto_obj.analysis[0].content.chord_quality, "major")

    def test_generate_unit5_command(self):
        out = StringIO()
        call_command(
            "generate_unit5",
            author=self.author.email,
            type="triads",
            public=True,
            overwrite=True,
            stdout=out
        )
        output = out.getvalue()
        self.assertIn("Unit 5 — Triad Quality", output)
        self.assertIn("Stage 1", output)
        
        # Query exercises created
        exercises = Exercise.objects.filter(skill_tags__contains=["unit:5_triad_quality"], authored_by=self.author)
        self.assertGreater(exercises.count(), 0)
        
        # Spot check an exercise payload
        ex = exercises.first()
        self.assertEqual(ex.data["type"], "umto_chorale")
        self.assertEqual(ex.data["analysisType"], "chord_quality")
        self.assertEqual(ex.data["allowed_answers"], ["major", "minor"])
        self.assertEqual(ex.data["score"]["umto"]["analysis"][0]["content"]["chord_quality"], "major" or "minor")
