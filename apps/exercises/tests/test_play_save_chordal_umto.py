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
        self.assertEqual(umto_meta["analysis_review_status"], "generated")

        # Verify chords
        chords = score["umto"]["chords"]
        self.assertEqual(len(chords), 2)
        self.assertEqual(chords[0]["offset"], 0.0)
        self.assertEqual(chords[0]["duration"], 1.0)
        self.assertEqual(chords[0]["visible"], [60, 64, 67])
        self.assertEqual(chords[0]["hidden"], [48])

        self.assertEqual(chords[1]["offset"], 1.0)
        self.assertEqual(chords[1]["duration"], 2.0)
        self.assertEqual(chords[1]["visible"], [62, 65, 69])
        self.assertEqual(chords[1]["hidden"], [])

        # Verify analysis slices
        analysis = score["umto"]["analysis"]
        self.assertEqual(len(analysis), 2)
        self.assertEqual(analysis[0]["offset"], 0.0)
        self.assertEqual(analysis[0]["content"]["roman_numeral"], "IV")
        self.assertEqual(analysis[0]["content"]["raw_roman_numeral"], "IV")
        self.assertEqual(analysis[0]["content"]["figured_bass"], "5/3")
        self.assertEqual(analysis[0]["content"]["raw_figured_bass"], "8/5/3")

        self.assertEqual(analysis[1]["offset"], 1.0)
        self.assertEqual(analysis[1]["content"]["roman_numeral"], "v")
        self.assertEqual(analysis[1]["content"]["raw_roman_numeral"], "v")
        self.assertEqual(analysis[1]["content"]["figured_bass"], "b")
        self.assertEqual(analysis[1]["content"]["raw_figured_bass"], "5/b3")

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

    def test_spelling_is_persisted(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {
            "key": "jF_", "meter": "4/4", "staffDistribution": "keyboard",
            "chord": [
                {"visible": [70, 74, 77], "hidden": [], "rhythmValue": "w",
                 "spelling": ["Bb4", "D5", "F5"]},
            ],
        }
        resp = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(resp.status_code, 201)
        ex = Exercise.objects.get(id=resp.json()["id"])
        chords = ex.data["score"]["umto"]["chords"]
        self.assertEqual(chords[0]["spelling"], ["Bb4", "D5", "F5"])

    def test_save_returns_review_status_and_url(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {"key": "jC_", "meter": "4/4", "staffDistribution": "keyboard",
                   "chord": [{"visible": [60, 64, 67], "hidden": [], "rhythmValue": "w"}]}
        # match the login pattern the other tests use
        resp = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertIn(body["reviewStatus"], ("generated", "none"))
        self.assertIn("review=" + str(body["id"]), body["reviewUrl"])

    def test_malformed_spelling_length_is_dropped(self):
        self.client.login(email="teacher@example.com", password="pw")
        payload = {
            "key": "jF_", "meter": "4/4", "staffDistribution": "keyboard",
            "chord": [
                {"visible": [70, 74, 77], "hidden": [], "rhythmValue": "w",
                 "spelling": ["Bb4"]},  # wrong length (1 != 3)
            ],
        }
        resp = self.client.post(self.add_url, {"data": json.dumps(payload)})
        self.assertEqual(resp.status_code, 201)  # save still succeeds
        ex = Exercise.objects.get(id=resp.json()["id"])
        chords = ex.data["score"]["umto"]["chords"]
        self.assertIsNone(chords[0].get("spelling"))
