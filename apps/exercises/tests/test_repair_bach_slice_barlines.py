from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist


def _create_admin_user(email: str):
    return get_user_model().objects.create_superuser(
        email=email,
        password="test-password",
    )


def _note(duration_type):
    return {
        "kind": "note",
        "pitch": {"step": "C", "alter": 0, "octave": 4},
        "duration": {"type": duration_type, "dots": 0},
    }


def _measure_with_duration(duration_type):
    return {
        "staves": {
            "treble": {
                "voices": [
                    {"items": [_note(duration_type)]},
                    {"items": [_note(duration_type)]},
                ]
            },
            "bass": {
                "voices": [
                    {"items": [_note(duration_type)]},
                    {"items": [_note(duration_type)]},
                ]
            },
        }
    }


EXPECTED_PICKUP_MEASURES = [
    _measure_with_duration("q"),
    _measure_with_duration("w"),
    _measure_with_duration("w"),
]

BAD_REBARRED_MEASURES = [
    _measure_with_duration("w"),
    _measure_with_duration("w"),
    _measure_with_duration("q"),
]


def _make_exercise(user, description, measures):
    exercise = Exercise(
        description=description,
        authored_by=user,
        data={
            "isUMTO": True,
            "type": "umto_chorale",
            "key": "iG_",
            "score": {
                "measures": measures,
                "umto": {"metadata": {"source": description}},
            },
        },
    )
    exercise.save(skip_auto_playlist=True)
    return exercise


class RepairBachSliceBarlinesTest(TestCase):
    def test_dry_run_reports_mismatches_without_updating_rows(self):
        user = _create_admin_user("barline-dry-run@example.test")
        bad = _make_exercise(
            user,
            "Bach R204 - Phrase 1 (mm.0-2) [play]",
            BAD_REBARRED_MEASURES,
        )
        good = _make_exercise(
            user,
            "Bach R204 - Phrase 2 (mm.3-5) [play]",
            EXPECTED_PICKUP_MEASURES,
        )

        out = StringIO()
        with patch(
            "apps.exercises.management.commands.repair_bach_slice_barlines._expected_measures_for_slice",
            return_value=EXPECTED_PICKUP_MEASURES,
        ):
            call_command(
                "repair_bach_slice_barlines",
                author=user.email,
                stdout=out,
            )

        self.assertIn("Checked exercises: 2", out.getvalue())
        self.assertIn("Mismatched exercises: 1", out.getvalue())
        self.assertIn("Dry run only", out.getvalue())
        bad.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual(bad.data["score"]["measures"], BAD_REBARRED_MEASURES)
        self.assertEqual(good.data["score"]["measures"], EXPECTED_PICKUP_MEASURES)

    def test_execute_repairs_measures_and_barlines_without_deleting_links(self):
        user = _create_admin_user("barline-execute@example.test")
        bad = _make_exercise(
            user,
            "Bach R204 - Phrase 1 (mm.0-2) [play]",
            BAD_REBARRED_MEASURES,
        )
        playlist = Playlist.objects.create(name="Unit 12", authored_by=user)
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=bad, order=1)

        with patch(
            "apps.exercises.management.commands.repair_bach_slice_barlines._expected_measures_for_slice",
            return_value=EXPECTED_PICKUP_MEASURES,
        ):
            call_command(
                "repair_bach_slice_barlines",
                author=user.email,
                execute=True,
            )

        bad.refresh_from_db()
        self.assertEqual(bad.data["score"]["measures"], EXPECTED_PICKUP_MEASURES)
        self.assertEqual(
            bad.data["score"]["umto"]["metadata"]["barline_offsets"],
            [1.0, 5.0],
        )
        self.assertTrue(ExercisePlaylistOrdered.objects.filter(exercise=bad).exists())
