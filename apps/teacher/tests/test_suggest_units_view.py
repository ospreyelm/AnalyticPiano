"""Tests for the suggest_units API view."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, Client

from apps.accounts.models import ROLE_TEACHER
from apps.exercises.models import Exercise
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()


class SuggestUnitsViewTest(TestCase):
    """Test the POST /teacher/play/api/suggest-units/ endpoint."""

    def setUp(self):
        """Create test users and client."""
        self.client = Client()

        # Create a staff/teacher user
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="testpass123",
            role=ROLE_TEACHER,
            is_staff=True,
        )

        # Create a non-staff teacher user
        self.regular_user = User.objects.create_user(
            email="regular@example.com",
            password="testpass123",
            role=ROLE_TEACHER,
            is_staff=False,
        )

        # Create a superuser
        self.superuser = User.objects.create_superuser(
            email="super@example.com",
            password="testpass123",
        )

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated request should redirect to login."""
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": "EA0001"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_staff_user_gets_403(self):
        """Non-staff user should get 403 Forbidden."""
        self.client.login(email="regular@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": "EA0001"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Permission denied.")

    def test_staff_user_allowed(self):
        """Staff user should be allowed."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": "NONEXISTENT"}),
            content_type="application/json",
        )
        # Should return 200 with empty lists (graceful degradation), not 403
        self.assertEqual(response.status_code, 200)

    def test_superuser_allowed(self):
        """Superuser should be allowed."""
        self.client.login(email="super@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": "NONEXISTENT"}),
            content_type="application/json",
        )
        # Should return 200 with empty lists (graceful degradation), not 403
        self.assertEqual(response.status_code, 200)

    def test_invalid_json_returns_200_with_empty(self):
        """Invalid JSON should gracefully return 200 with empty lists."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data="{not valid json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["skill_tags"], [])
        self.assertEqual(data["suggested_units"], [])

    def test_nonexistent_exercise_returns_empty(self):
        """Nonexistent exercise_id should gracefully return empty lists."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": "EA9999"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["skill_tags"], [])
        self.assertEqual(data["suggested_units"], [])

    def test_exercise_with_skill_tags_uses_them(self):
        """Exercise with skill_tags should use them directly (no re-analysis)."""
        # Create an exercise with skill tags
        exercise = save_umto_exercise(
            description="Test exercise",
            score_data={
                "meta": {"key": "C", "time_signature": "4/4"},
                "measures": [
                    {
                        "staves": {
                            "treble": {"voices": [{"items": []}]},
                            "bass": {"voices": [{"items": []}]},
                        }
                    }
                ],
            },
            author=self.staff_user,
            skill_tags=["Dominant_Seventh", "Diatonic_Triads"],
            complexity=9,
            umto_kwargs={
                "exercise_id": "TEST001",
                "source": "Test",
                "key": "C",
                "meter": "4/4",
                "clef": "treble",
                "complexity_score": 1,
                "mode": "playback",
                "unit": 9,
            },
        )

        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": exercise.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Should have used the skill tags
        self.assertIn("Dominant_Seventh", data["skill_tags"])
        self.assertIn("Diatonic_Triads", data["skill_tags"])

        # Should have suggested unit 9
        self.assertIn(9, data["suggested_units"])

    def test_cir_score_analysis(self):
        """Should analyze a CIR score and suggest units."""
        self.client.login(email="staff@example.com", password="testpass123")

        # Minimal CIR score with some harmonic content
        cir_score = {
            "meta": {"key": "C", "time_signature": "4/4"},
            "measures": [
                {
                    "staves": {
                        "treble": {
                            "voices": [
                                {
                                    "items": [
                                        {
                                            "kind": "chord",
                                            "pitches": [
                                                {"step": "C", "alter": 0, "octave": 4},
                                                {"step": "E", "alter": 0, "octave": 4},
                                                {"step": "G", "alter": 0, "octave": 4},
                                            ],
                                            "duration": {"type": "q", "dots": 0},
                                        }
                                    ]
                                }
                            ]
                        },
                        "bass": {
                            "voices": [
                                {
                                    "items": [
                                        {
                                            "kind": "note",
                                            "pitch": {"step": "C", "alter": 0, "octave": 3},
                                            "duration": {"type": "q", "dots": 0},
                                        }
                                    ]
                                }
                            ]
                        },
                    }
                }
            ],
        }

        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"cir_score": cir_score, "key": "C"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Should have detected some skill tags (at minimum the literacy skills)
        self.assertIsInstance(data["skill_tags"], list)
        self.assertIsInstance(data["suggested_units"], list)

    def test_empty_body_returns_empty(self):
        """Empty body should gracefully return empty lists."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["skill_tags"], [])
        self.assertEqual(data["suggested_units"], [])

    def test_response_format(self):
        """Response should always have skill_tags and suggested_units."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/suggest-units/",
            data=json.dumps({"exercise_id": "NONEXISTENT"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("skill_tags", data)
        self.assertIn("suggested_units", data)
        self.assertIsInstance(data["skill_tags"], list)
        self.assertIsInstance(data["suggested_units"], list)

    def test_method_not_allowed(self):
        """GET request should be rejected."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get(
            "/teacher/play/api/suggest-units/",
        )
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
