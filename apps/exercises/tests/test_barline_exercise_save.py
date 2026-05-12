from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.umto_factory import save_umto_barline_exercise


class BarlineExerciseSaveTests(TestCase):
    def _payload(self, *, tags=None, source="test"):
        return {
            "type": "umto_barline_placement",
            "isUMTO": True,
            "mode": "identification",
            "time_signature": "3/4",
            "show_time_signature": False,
            "clef": "treble",
            "measures": 1,
            "pickup_beats": 0,
            "pitch_mode": "rhythm_only",
            "notes": [{"pitch": "B4", "duration": "q", "dots": 0}] * 3,
            "note_beat_onsets": [0, 1, 2],
            "correct_barline_positions": [],
            "beat_count": 3,
            "beat_positions_ticks": [0, 1, 2, 3],
            "source": source,
            "tags": tags or ["unit:2", "unit:2_meter_simple"],
        }

    def test_save_umto_barline_exercise_creates_runtime_payload(self):
        user = get_user_model().objects.create_user(
            email="barline@example.com",
            password="pw",
        )
        exercise = save_umto_barline_exercise(
            description="Unit 2 add barlines sample",
            author=user,
            payload=self._payload(),
            is_public=True,
        )

        self.assertEqual(exercise.data["type"], "umto_barline_placement")
        self.assertEqual(exercise.data["mode"], "identification")
        self.assertEqual(exercise.data["exerciseId"], exercise.id)
        self.assertEqual(exercise.data["pickup_beats"], 0)
        self.assertEqual(exercise.data["note_beat_onsets"], [0, 1, 2])
        self.assertEqual(exercise.skill_tags, ["unit:2", "unit:2_meter_simple"])

    def test_save_umto_barline_exercise_overwrite_updates_payload_and_metadata(self):
        user = get_user_model().objects.create_user(
            email="barline-overwrite@example.com",
            password="pw",
        )
        exercise = save_umto_barline_exercise(
            description="Unit 2 add barlines overwrite",
            author=user,
            payload=self._payload(tags=["unit:2"], source="first"),
            is_public=True,
        )

        updated = save_umto_barline_exercise(
            description="Unit 2 add barlines overwrite",
            author=user,
            payload=self._payload(tags=["unit:2", "unit:2_meter_triple"], source="updated"),
            is_public=False,
            overwrite=True,
        )

        self.assertEqual(updated.id, exercise.id)
        updated.refresh_from_db()
        self.assertFalse(updated.is_public)
        self.assertEqual(updated.skill_tags, ["unit:2", "unit:2_meter_triple"])
        self.assertEqual(updated.complexity, 2)
        self.assertEqual(updated.data["source"], "updated")
        self.assertEqual(updated.data["exerciseId"], exercise.id)
