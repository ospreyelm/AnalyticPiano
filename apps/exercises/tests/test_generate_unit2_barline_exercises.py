from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist


class GenerateUnit2BarlineExercisesCommandTests(TestCase):
    def _create_user(self, email="barline-seed@example.com"):
        return get_user_model().objects.create_user(
            email=email,
            password="pw",
        )

    def test_manual_source_creates_dev_seed_exercise_and_playlist_link(self):
        user = self._create_user()

        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            public=True,
            count=1,
            meter="3/4",
            measures=2,
            pitch_mode="rhythm_only",
            source="manual",
        )

        exercise = Exercise.objects.latest("created")
        playlist = Playlist.objects.get(
            name="Unit 2 — Add Barlines",
            authored_by=user,
        )
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, order=1)

        self.assertEqual(exercise.data["type"], "umto_barline_placement")
        self.assertEqual(exercise.data["time_signature"], "3/4")
        self.assertEqual(exercise.data["measures"], 2)
        self.assertEqual(exercise.data["correct_barline_positions"], [2])
        self.assertEqual(link.exercise, exercise)
        self.assertTrue(playlist.is_public)
        self.assertIn("unit:2", playlist.skill_tags)

    def test_essen_source_is_recognized_as_real_repertoire_path(self):
        user = self._create_user("essen-seed@example.com")

        with self.assertRaisesMessage(
            CommandError, "Essen/Kern import is not implemented yet"
        ):
            call_command(
                "generate_unit2_barline_exercises",
                author=user.email,
                source="essen",
                count=1,
            )

    def test_invalid_count_does_not_clear_existing_playlist(self):
        user = self._create_user("count-seed@example.com")
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            count=1,
            source="manual",
        )
        playlist = Playlist.objects.get(name="Unit 2 — Add Barlines", authored_by=user)

        with self.assertRaisesMessage(CommandError, "--count must be at least 1"):
            call_command(
                "generate_unit2_barline_exercises",
                author=user.email,
                count=0,
                source="manual",
            )

        self.assertEqual(
            ExercisePlaylistOrdered.objects.filter(playlist=playlist).count(),
            1,
        )

    def test_invalid_meter_does_not_clear_existing_playlist(self):
        user = self._create_user("meter-seed@example.com")
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            count=1,
            source="manual",
        )
        playlist = Playlist.objects.get(name="Unit 2 — Add Barlines", authored_by=user)

        with self.assertRaisesMessage(CommandError, "Unsupported meter: 5/4"):
            call_command(
                "generate_unit2_barline_exercises",
                author=user.email,
                count=1,
                meter="5/4",
                source="manual",
            )

        self.assertEqual(
            ExercisePlaylistOrdered.objects.filter(playlist=playlist).count(),
            1,
        )

    def test_invalid_measures_does_not_save_empty_exercise(self):
        user = self._create_user("measures-seed@example.com")

        with self.assertRaisesMessage(CommandError, "--measures must be at least 1"):
            call_command(
                "generate_unit2_barline_exercises",
                author=user.email,
                measures=0,
                source="manual",
            )

        self.assertFalse(
            Playlist.objects.filter(
                name="Unit 2 — Add Barlines",
                authored_by=user,
            ).exists()
        )

    def test_rerun_keeps_exercises_public_when_playlist_is_public(self):
        user = self._create_user("public-seed@example.com")
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            public=True,
            count=1,
            source="manual",
        )

        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            count=1,
            source="manual",
        )

        playlist = Playlist.objects.get(name="Unit 2 — Add Barlines", authored_by=user)
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, order=1)
        self.assertTrue(playlist.is_public)
        self.assertTrue(link.exercise.is_public)
