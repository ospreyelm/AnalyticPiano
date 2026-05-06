from django.http import Http404
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from unittest.mock import patch


class LocalContentGenerationViewTests(SimpleTestCase):
    def test_local_content_guard_raises_404_when_disabled(self):
        from apps.exercises import local_tools

        with override_settings(ENABLE_LOCAL_CONTENT_TOOLS=False):
            with self.assertRaises(Http404):
                local_tools.require_local_content_tools_enabled()

    def test_local_db_target_uses_default_database_settings(self):
        from apps.exercises import local_tools

        with override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True), patch(
            "apps.exercises.local_tools.settings.DATABASES",
            {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "HOST": "localhost",
                    "PORT": "5433",
                    "NAME": "postgres",
                }
            },
        ):
            self.assertEqual(
                local_tools.get_local_content_db_target(),
                {
                    "engine": "django.db.backends.postgresql",
                    "host": "localhost",
                    "port": "5433",
                    "name": "postgres",
                },
            )

    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=False, ALLOWED_HOSTS=["testserver"])
    def test_content_generation_route_returns_404_when_disabled(self):
        response = self.client.get(reverse("content-generation"))

        self.assertEqual(response.status_code, 404)
