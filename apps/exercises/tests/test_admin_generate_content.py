from unittest.mock import ANY, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ExerciseAdminGenerateContentTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="pw",
        )
        self.client.force_login(self.admin_user)

    @patch("apps.exercises.admin.call_command")
    def test_post_generate_unit2_add_barlines_dispatches_manual_seed_command(self, call_command_mock):
        response = self.client.post(
            reverse("admin:exercises_exercise_generate_content"),
            {
                "command": "generate_unit2_barline_exercises",
                "author": "author@example.com",
                "barline_count": "3",
                "barline_meter": "6/8",
                "barline_measures": "4",
                "barline_pitch_mode": "melody",
            },
        )

        self.assertEqual(response.status_code, 302)
        call_command_mock.assert_called_once_with(
            "generate_unit2_barline_exercises",
            author="author@example.com",
            public=True,
            count=3,
            meter="6/8",
            measures=4,
            pitch_mode="melody",
            source="manual",
            stdout=ANY,
        )
