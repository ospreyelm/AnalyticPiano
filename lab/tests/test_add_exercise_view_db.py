import json
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class AddExerciseViewChordalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="add@example.com", password="x")
        self.client.force_login(self.user)

    def _post(self, payload):
        return self.client.post(
            "/exercises/add/",
            data={"data": json.dumps(payload)},
        )

    def _chords(self):
        # Two 4/4 bars of quarters, with explicit per-chord duration.
        return [
            {"offset": float(i), "duration": 1.0, "visible": [60, 64, 67], "hidden": []}
            for i in range(8)
        ]

    def test_free_mode_no_meter_saves_reviewed_none_when_no_analysis(self):
        payload = {"chord": self._chords(), "key": "C", "staffDistribution": "keyboard"}
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertIn("id", body)
        self.assertEqual(body["reviewStatus"], "none")

    def test_metered_with_barlines_and_analysis_saves_reviewed(self):
        payload = {
            "chord": self._chords(),
            "key": "C",
            "meter": "4/4",
            "staffDistribution": "keyboard",
            "barline_offsets": [4.0],
            "analysisSlices": [
                {"offset": 0.0, "content": {"roman_numeral": "I"}, "is_target": True, "unit_tags": []}
            ],
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["reviewStatus"], "reviewed")

    def test_invalid_metered_bars_rejected(self):
        payload = {
            "chord": [{"offset": float(i), "duration": 1.0, "visible": [60], "hidden": []} for i in range(3)],
            "key": "C",
            "meter": "4/4",
            "staffDistribution": "keyboard",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 400)

    def test_analyze_config_slots_persist_on_exercise_data(self):
        from apps.exercises.models import Exercise
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "analyzeConfig": {"above": "note_names", "below": "roman_numerals"},
            "analysisSlices": [
                {"offset": 0.0, "content": {"roman_numeral": "I"}, "is_target": True, "unit_tags": []}
            ],
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        ex = Exercise.objects.get(id=resp.json()["id"])
        self.assertEqual(ex.data.get("analyzeConfig"), {"above": "note_names", "below": "roman_numerals"})
