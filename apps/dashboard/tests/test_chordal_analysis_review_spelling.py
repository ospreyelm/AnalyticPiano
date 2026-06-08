import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class ChordalReviewSpellingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="respell@example.com", password="pw12345")
        self.ex = save_chordal_umto_exercise(
            description="Respell test",
            author=self.user,
            chords=[{"offset": 0.0, "duration": 4.0, "visible": [70], "hidden": []}],
            key="jF_", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        )
        self.url = reverse("dashboard:api-chordal-analysis-review", kwargs={"exercise_id": self.ex.id})
        self.client.force_login(self.user)

    def test_post_persists_spelling(self):
        resp = self.client.post(self.url, data=json.dumps({"rows": [
            {"offset": 0.0, "content": {"roman_numeral": "V{z5}"}, "spelling": ["A#4"]}
        ]}), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.ex.refresh_from_db()
        chords = self.ex.data["score"]["umto"]["chords"]
        self.assertEqual(chords[0]["spelling"], ["A#4"])

    def test_post_rejects_bad_spelling_length(self):
        resp = self.client.post(self.url, data=json.dumps({"rows": [
            {"offset": 0.0, "content": {"roman_numeral": "V"}, "spelling": ["A#4", "C5"]}  # len 2 != 1
        ]}), content_type="application/json")
        self.assertEqual(resp.status_code, 400)
