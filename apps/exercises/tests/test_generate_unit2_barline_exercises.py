from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.utils.corpus_filter import PhraseResult


def _fake_phrase(level, time_sig, measures, fingerprint, source_path="a.abc", offset=0):
    from fractions import Fraction

    from apps.exercises.utils.barline_exercise_builder import meter_info

    beats_per_measure, beat_quarters = meter_info(time_sig)
    total_quarters = beats_per_measure * measures * beat_quarters
    notes = []
    remaining = total_quarters
    if "8" in time_sig:
        unit = Fraction(3, 2)
        note_dur = "q"
        note_dots = 1
    else:
        unit = Fraction(1, 1)
        note_dur = "q"
        note_dots = 0
    count = int(remaining / unit)
    notes = [{"pitch": "B4", "duration": note_dur, "dots": note_dots}] * count
    return PhraseResult(
        level=level,
        time_signature=time_sig,
        notes=notes,
        measures=measures,
        source_path=source_path,
        phrase_offset=offset,
        fingerprint=fingerprint,
    )


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


class GenerateUnit2BarlineCorpusTests(TestCase):
    def _create_user(self, email="corpus-seed@example.com"):
        return get_user_model().objects.create_user(email=email, password="pw")

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_creates_level_playlist(self, mock_iter):
        user = self._create_user()
        mock_iter.return_value = iter([
            _fake_phrase(1, "3/4", 2, "aabbcc112233"),
        ])
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            source="corpus",
            level=1,
            public=True,
        )
        playlist = Playlist.objects.get(
            name="Unit 2 — Add Barlines, Level 1",
            authored_by=user,
        )
        self.assertTrue(playlist.is_adaptive)
        self.assertIn("unit:2_L1", playlist.skill_tags)
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, order=1)
        self.assertEqual(link.exercise.complexity, 1)
        self.assertTrue(link.is_adaptive_entry)

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_dry_run_does_not_save(self, mock_iter):
        user = self._create_user("dry-run@example.com")
        mock_iter.return_value = iter([
            _fake_phrase(1, "3/4", 2, "dryrun000001"),
        ])
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            source="corpus",
            dry_run=True,
        )
        self.assertFalse(
            Playlist.objects.filter(
                name__startswith="Unit 2 — Add Barlines, Level",
                authored_by=user,
            ).exists()
        )

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_idempotent_rerun(self, mock_iter):
        user = self._create_user("idempotent@example.com")
        phrase = _fake_phrase(1, "3/4", 2, "idempotent01")
        mock_iter.side_effect = [iter([phrase]), iter([phrase])]
        call_command("generate_unit2_barline_exercises", author=user.email, source="corpus", level=1)
        call_command("generate_unit2_barline_exercises", author=user.email, source="corpus", level=1)
        self.assertEqual(
            ExercisePlaylistOrdered.objects.filter(
                playlist__name="Unit 2 — Add Barlines, Level 1",
                playlist__authored_by=user,
            ).count(),
            1,
        )

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_limit_restricts_count(self, mock_iter):
        user = self._create_user("limit@example.com")
        mock_iter.return_value = iter([
            _fake_phrase(1, "3/4", 2, f"limit{i:06d}") for i in range(5)
        ])
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            source="corpus",
            level=1,
            limit=2,
        )
        self.assertEqual(
            ExercisePlaylistOrdered.objects.filter(
                playlist__name="Unit 2 — Add Barlines, Level 1",
                playlist__authored_by=user,
            ).count(),
            2,
        )
