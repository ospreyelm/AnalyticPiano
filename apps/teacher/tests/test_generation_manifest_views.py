"""Tests for GenerationManifest API views."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, Client

from apps.accounts.models import ROLE_TEACHER
from apps.exercises.models import Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class GenerationManifestDryRunViewTest(TestCase):
    """Test the POST /teacher/play/api/generate-manifest/dry-run/ endpoint."""

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
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-30",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_staff_user_gets_403(self):
        """Non-staff user should get 403 Forbidden."""
        self.client.login(email="regular@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-30",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Permission denied.")

    def test_staff_user_allowed(self):
        """Staff user should be allowed."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-30",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C", "G"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("estimated_exercises", data)

    def test_superuser_allowed(self):
        """Superuser should be allowed."""
        self.client.login(email="super@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-30",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "super@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_json_returns_400(self):
        """Invalid JSON should return 400."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data="{not valid json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_non_superuser_cannot_create_official_exercises(self):
        """Non-superuser with is_official=True should get 403."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-30",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": True,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("superuser", data["error"].lower())

    def test_superuser_can_create_official_exercises(self):
        """Superuser with is_official=True should succeed."""
        self.client.login(email="super@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-30",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C", "G"],
                "playlist_target": None,
                "is_official": True,
                "author_email": "super@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("estimated_exercises", data)

    def test_response_has_correct_format(self):
        """Response should have the correct dry-run summary format."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({
                "source": "bach_riemenschneider",
                "source_ref": "1-5",
                "unit": 10,
                "skill_tags": ["unit:10"],
                "exercise_types": ["play", "roman"],
                "key_set": ["C", "G", "D"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["source"], "bach_riemenschneider")
        self.assertEqual(data["source_ref"], "1-5")
        self.assertEqual(data["unit"], 10)
        self.assertEqual(data["exercise_types"], ["play", "roman"])
        self.assertEqual(data["key_count"], 3)
        self.assertEqual(data["estimated_exercises"], 6)  # 2 * 3
        self.assertEqual(data["is_official"], False)
        self.assertIsNone(data["playlist_target"])

    def test_method_not_allowed_get(self):
        """GET request should be rejected."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/teacher/play/api/generate-manifest/dry-run/")
        self.assertEqual(response.status_code, 405)

    def test_method_not_allowed_put(self):
        """PUT request should be rejected."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.put(
            "/teacher/play/api/generate-manifest/dry-run/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)


class GenerationManifestExecuteViewTest(TestCase):
    """Test the POST /teacher/play/api/generate-manifest/execute/ endpoint."""

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
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": "EA0001",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_staff_user_gets_403(self):
        """Non-staff user should get 403 Forbidden."""
        self.client.login(email="regular@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": "EA0001",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Permission denied.")

    def test_staff_user_allowed(self):
        """Staff user should be allowed."""
        # Create a valid source exercise
        source_exercise = save_chordal_umto_exercise(
            description="Source exercise",
            author=self.staff_user,
            chords=[
                {"offset": 0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 1.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 2.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 3.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter="4/4",
            clef="keyboard",
            staff_distribution="keyboard",
            source="Test",
            skill_tags=[],
            complexity=1,
            is_public=False,
        )

        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": source_exercise.id,
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("created_count", data)
        self.assertIn("exercise_ids", data)

    def test_superuser_allowed(self):
        """Superuser should be allowed."""
        source_exercise = save_chordal_umto_exercise(
            description="Source exercise",
            author=self.superuser,
            chords=[
                {"offset": 0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 1.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 2.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 3.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter="4/4",
            clef="keyboard",
            staff_distribution="keyboard",
            source="Test",
            skill_tags=[],
            complexity=1,
            is_public=False,
        )

        self.client.login(email="super@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": source_exercise.id,
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["G"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "super@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_json_returns_400(self):
        """Invalid JSON should return 400."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data="{not valid json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_non_superuser_cannot_create_official_exercises(self):
        """Non-superuser with is_official=True should get 403."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": "EA0001",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": True,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("superuser", data["error"].lower())

    def test_superuser_can_create_official_exercises(self):
        """Superuser with is_official=True should succeed."""
        source_exercise = save_chordal_umto_exercise(
            description="Source exercise",
            author=self.superuser,
            chords=[
                {"offset": 0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 1.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 2.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 3.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter="4/4",
            clef="keyboard",
            staff_distribution="keyboard",
            source="Test",
            skill_tags=[],
            complexity=1,
            is_public=False,
        )

        self.client.login(email="super@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": source_exercise.id,
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C", "G"],
                "playlist_target": None,
                "is_official": True,
                "author_email": "super@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["created_count"], 2)
        self.assertEqual(len(data["exercise_ids"]), 2)

        # Verify created exercises are marked as official
        from apps.exercises.models import Exercise

        for ex_id in data["exercise_ids"]:
            ex = Exercise.objects.get(id=ex_id)
            self.assertTrue(ex.is_official)

    def test_missing_author_returns_400(self):
        """Request with non-existent author email should return 400."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": "EA0001",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "nonexistent@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_missing_exercise_returns_400(self):
        """Request with non-existent exercise should return 400."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": "NONEXISTENT",
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_response_has_correct_format(self):
        """Response should have created_count and exercise_ids."""
        source_exercise = save_chordal_umto_exercise(
            description="Source exercise",
            author=self.staff_user,
            chords=[
                {"offset": 0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 1.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 2.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
                {"offset": 3.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter="4/4",
            clef="keyboard",
            staff_distribution="keyboard",
            source="Test",
            skill_tags=[],
            complexity=1,
            is_public=False,
        )

        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({
                "source": "played_in",
                "source_ref": source_exercise.id,
                "unit": 9,
                "skill_tags": [],
                "exercise_types": ["play"],
                "key_set": ["C", "G", "D"],
                "playlist_target": None,
                "is_official": False,
                "author_email": "staff@example.com",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["created_count"], 3)
        self.assertEqual(len(data["exercise_ids"]), 3)
        self.assertIsInstance(data["exercise_ids"], list)
        self.assertTrue(all(isinstance(ex_id, str) for ex_id in data["exercise_ids"]))

    def test_method_not_allowed_get(self):
        """GET request should be rejected."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/teacher/play/api/generate-manifest/execute/")
        self.assertEqual(response.status_code, 405)

    def test_method_not_allowed_put(self):
        """PUT request should be rejected."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.put(
            "/teacher/play/api/generate-manifest/execute/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)
