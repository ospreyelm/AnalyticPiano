import json

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.exercises.models import Exercise


class PlayViewSaveChordalUMTOTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="teacher@example.com",
            password="pw",
        )
        self.client = Client()
        self.add_url = reverse("lab:add-exercise")

    def test_anonymous_post_returns_400(self):
        payload = {
            "chord": [
                {"visible": [60, 64, 67], "hidden": [], "rhythmValue": "w"}
            ],
            "key": "C",
            "meter": "4/4",
            "clef": "keyboard",
            "staffDistribution": "keyboard",
        }
        response = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Exercise.objects.count(), 0)

    def test_valid_post_creates_private_chordal_umto_exercise(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {
            "chord": [
                {"visible": [60, 64, 67], "hidden": [48], "rhythmValue": "w"},
                {"visible": [62, 65, 69], "hidden": [], "rhythmValue": "w"},
            ],
            "key": "jG_",
            "meter": "3/4",
            "clef": "keyboard",
            "staffDistribution": "keyboardPlusLHBias",
        }
        response = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 201)
        res_data = response.json()
        self.assertIn("id", res_data)

        # Retrieve and verify exercise
        ex = Exercise.objects.get(id=res_data["id"])
        self.assertEqual(ex.authored_by, self.user)
        self.assertFalse(ex.is_public)
        self.assertEqual(ex.complexity, 1)

        # Verify payload structure
        data = ex.data
        self.assertTrue(data.get("isUMTO"))
        self.assertEqual(data.get("type"), "umto_chorale")
        self.assertEqual(data.get("key"), "jG_")
        self.assertEqual(data.get("meter"), "3/4")
        self.assertEqual(data.get("staffDistribution"), "keyboardPlusLHBias")

        # Verify metadata
        score = data["score"]
        umto_meta = score["umto"]["metadata"]
        self.assertEqual(umto_meta["score_kind"], "chordal")
        self.assertEqual(umto_meta["staffDistribution"], "keyboardPlusLHBias")
        self.assertEqual(umto_meta["exercise_id"], ex.id)
        self.assertEqual(data["exerciseId"], ex.id)

        # Verify chords
        chords = score["umto"]["chords"]
        self.assertEqual(len(chords), 2)
        self.assertEqual(chords[0]["offset"], 0.0)
        self.assertEqual(chords[0]["duration"], 1.0)
        self.assertEqual(chords[0]["visible"], [60, 64, 67])
        self.assertEqual(chords[0]["hidden"], [48])

        self.assertEqual(chords[1]["offset"], 1.0)
        self.assertEqual(chords[1]["duration"], 1.0)
        self.assertEqual(chords[1]["visible"], [62, 65, 69])
        self.assertEqual(chords[1]["hidden"], [])

    def test_null_data_returns_400(self):
        self.client.login(email="teacher@example.com", password="pw")
        response = self.client.post(self.add_url, {"data": "null"})
        self.assertEqual(response.status_code, 400)

    def test_missing_chord_returns_400(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {
            "key": "C",
            "meter": "4/4",
            "clef": "keyboard",
        }
        response = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)

    def test_empty_chord_returns_400(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {
            "chord": [],
            "key": "C",
            "meter": "4/4",
            "clef": "keyboard",
        }
        response = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)

    def test_pitchless_chord_returns_400(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {
            "chord": [
                {"visible": [], "hidden": [], "rhythmValue": "w"}
            ],
            "key": "C",
            "meter": "4/4",
            "clef": "keyboard",
        }
        response = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)

    def test_malformed_json_returns_400(self):
        self.client.login(email="teacher@example.com", password="pw")
        response = self.client.post(self.add_url, {"data": "{bad json"})
        self.assertEqual(response.status_code, 400)
