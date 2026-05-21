from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

User = get_user_model()


class GenerateUnit4CommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="teacher@example.com",
            password="pw",
        )

    def test_creates_generic_and_specific_stage_playlists(self):
        call_command(
            "generate_unit4",
            author="teacher@example.com",
            max_per_stage=6,
        )

        generic = Playlist.objects.filter(
            name__startswith="Unit 4 - Generic Intervals: Stage",
            authored_by=self.author,
        )
        specific = Playlist.objects.filter(
            name__startswith="Unit 4 - Specific Intervals: Stage",
            authored_by=self.author,
        )

        self.assertEqual(generic.count(), 4)
        self.assertEqual(specific.count(), 4)
        self.assertTrue(all(ExercisePlaylistOrdered.objects.filter(playlist=p).count() == 1 for p in generic))
        self.assertTrue(all(ExercisePlaylistOrdered.objects.filter(playlist=p).count() == 1 for p in specific))

    def test_created_exercise_is_synthetic_interval_worksheet(self):
        call_command(
            "generate_unit4",
            author="teacher@example.com",
            lane="specific",
            max_per_stage=6,
        )

        exercises = Exercise.objects.filter(
            authored_by=self.author,
            skill_tags__contains=["unit:4", "Interval_Specific"],
        )
        self.assertEqual(exercises.count(), 4)

        sample = exercises.order_by("description").first()
        self.assertEqual(sample.description, "Unit 4 Specific Intervals Worksheet - Stage 1")
        self.assertEqual(sample.data["type"], "umto_chorale")
        self.assertEqual(sample.data["mode"], "identification")
        self.assertEqual(sample.data["analysisType"], "interval_specific")
        self.assertEqual(sample.data["inputMode"], "dropdown")
        self.assertEqual(sample.data["staffDistribution"], "treble")
        self.assertTrue(sample.data["disableComputerKeyboardInput"])
        self.assertEqual(sample.data["score"]["umto"]["metadata"]["unit"], 4)
        self.assertEqual(sample.data["score"]["umto"]["metadata"]["clef"], "treble")
        self.assertIn("unit:4_L1", sample.skill_tags)
        self.assertEqual(len(sample.data["score"]["measures"]), 6)
        self.assertTrue(all("treble" in measure["staves"] for measure in sample.data["score"]["measures"]))
        self.assertTrue(all("bass" not in measure["staves"] or not measure["staves"]["bass"]["voices"] for measure in sample.data["score"]["measures"]))
        self.assertEqual(len(sample.data["score"]["umto"]["analysis"]), 6)
        self.assertTrue(
            all(
                analysis["content"]["functional_label"] in ["P5", "P8"]
                for analysis in sample.data["score"]["umto"]["analysis"]
            )
        )
        self.assertEqual(sample.data["allowed_answers"], ["P5", "P8"])
