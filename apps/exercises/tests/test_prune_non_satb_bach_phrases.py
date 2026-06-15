from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist


def _create_admin_user(email: str):
    return get_user_model().objects.create_superuser(
        email=email,
        password="test-password",
    )


def _make_exercise(user, description):
    exercise = Exercise(
        description=description,
        authored_by=user,
        data={
            "isUMTO": True,
            "type": "umto_chorale",
            "score": {"umto": {"metadata": {"source": description}}},
        },
    )
    exercise.save(skip_auto_playlist=True)
    return exercise


class PruneNonSatbBachPhrasesTest(TestCase):
    def test_dry_run_reports_without_deleting(self):
        user = _create_admin_user("prune-dry-run@example.test")
        bad = _make_exercise(user, "Bach R150 - Phrase 5 (mm.19-22) [play]")
        good = _make_exercise(user, "Bach R1 - Phrase 1 (mm.0-4) [play]")
        playlist = Playlist.objects.create(name="Unit 12", authored_by=user)
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=bad, order=1)
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=good, order=2)

        out = StringIO()
        call_command(
            "prune_non_satb_bach_phrases",
            author=user.email,
            list=True,
            stdout=out,
        )

        self.assertIn("Target exercises: 1", out.getvalue())
        self.assertIn("Playlist links to remove: 1", out.getvalue())
        self.assertIn("Bach R150 - Phrase 5", out.getvalue())
        self.assertTrue(Exercise.objects.filter(pk=bad.pk).exists())
        self.assertTrue(ExercisePlaylistOrdered.objects.filter(exercise=bad).exists())
        self.assertTrue(Exercise.objects.filter(pk=good.pk).exists())

    def test_execute_deletes_non_satb_rows_and_keeps_satb_rows(self):
        user = _create_admin_user("prune-execute@example.test")
        bad = _make_exercise(user, "Bach R150 - Phrase 5 (mm.19-22) [play]")
        good = _make_exercise(user, "Bach R1 - Phrase 1 (mm.0-4) [play]")
        playlist = Playlist.objects.create(name="Unit 12", authored_by=user)
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=bad, order=1)
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=good, order=2)

        call_command(
            "prune_non_satb_bach_phrases",
            author=user.email,
            execute=True,
        )

        self.assertFalse(Exercise.objects.filter(pk=bad.pk).exists())
        self.assertFalse(ExercisePlaylistOrdered.objects.filter(exercise_id=bad.pk).exists())
        self.assertTrue(Exercise.objects.filter(pk=good.pk).exists())
        self.assertTrue(ExercisePlaylistOrdered.objects.filter(exercise=good).exists())
