from django.http import Http404
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch


class LocalContentGenerationViewTests(SimpleTestCase):
    def test_local_content_guard_raises_404_when_disabled(self):
        from apps.exercises import local_tools

        with override_settings(ENABLE_LOCAL_CONTENT_TOOLS=False):
            with self.assertRaises(Http404):
                local_tools.require_local_content_tools()

    def test_local_db_target_normalizes_banner_contract(self):
        from apps.exercises import local_tools

        with override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True), patch(
            "apps.exercises.local_tools.settings.DATABASES",
            {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "HOST": "",
                    "PORT": 5433,
                    "NAME": "postgres",
                }
            },
        ):
            self.assertEqual(
                local_tools.get_database_target(),
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


class LocalContentGenerationRenderTests(TestCase):
    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True, ALLOWED_HOSTS=["testserver"])
    @patch("apps.exercises.views_tools.get_database_target")
    @patch("apps.exercises.views_tools.require_local_content_tools")
    def test_content_generation_route_renders_basic_local_page(
        self,
        require_local_content_tools_mock,
        get_database_target_mock,
    ):
        get_database_target_mock.return_value = {
            "engine": "django.db.backends.postgresql_psycopg2",
            "host": "localhost",
            "port": "5432",
            "name": "analyticpiano",
        }

        response = self.client.get(reverse("content-generation"))

        self.assertEqual(response.status_code, 200)
        require_local_content_tools_mock.assert_called_once_with()
        get_database_target_mock.assert_called_once_with()
        self.assertTemplateUsed(response, "tools/content_generation.html")
        self.assertEqual(
            response.context["db_target"],
            {
                "engine": "django.db.backends.postgresql_psycopg2",
                "host": "localhost",
                "port": "5432",
                "name": "analyticpiano",
            },
        )
        self.assertEqual(
            response.context["form_data"],
            {
                "author": "",
                "unit": "9",
                "riemenschneider": "1-30",
                "mode": "roman",
            },
        )


class LocalContentGenerationPostTests(TestCase):
    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True, ALLOWED_HOSTS=["testserver"])
    @patch("apps.exercises.views_tools.call_command")
    def test_post_missing_author_rerenders_with_error(self, call_command_mock):
        response = self.client.post(
            reverse("content-generation"),
            {
                "command": "generate_unit1",
                "author": "",
                "unit": "11",
                "riemenschneider": "21-30",
                "mode": "roman",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tools/content_generation.html")
        call_command_mock.assert_not_called()
        self.assertTrue(response.context["messages"])
        self.assertEqual(response.context["messages"][0]["level"], "error")
        self.assertIn("Author email is required", response.context["messages"][0]["text"])
        self.assertEqual(response.context["result"], None)
        self.assertEqual(
            response.context["form_data"],
            {
                "author": "",
                "unit": "11",
                "riemenschneider": "21-30",
                "mode": "roman",
            },
        )

    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True, ALLOWED_HOSTS=["testserver"])
    @patch("apps.exercises.views_tools.call_command")
    def test_post_generate_unit1_dispatches_call_command(self, call_command_mock):
        response = self.client.post(
            reverse("content-generation"),
            {
                "command": "generate_unit1",
                "author": "author@example.com",
                "unit": "9",
                "riemenschneider": "1-30",
                "mode": "roman",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tools/content_generation.html")
        call_command_mock.assert_called_once_with("generate_unit1", author="author@example.com")
        self.assertEqual(response.context["result"]["command"], "generate_unit1")
        self.assertEqual(response.context["result"]["status"], "success")

    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True, ALLOWED_HOSTS=["testserver"])
    @patch("apps.exercises.views_tools.call_command")
    def test_post_generate_unit2_dispatches_with_public_true(self, call_command_mock):
        response = self.client.post(
            reverse("content-generation"),
            {
                "command": "generate_unit2_meter_exercises",
                "author": "author@example.com",
                "unit": "9",
                "riemenschneider": "1-30",
                "mode": "roman",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tools/content_generation.html")
        call_command_mock.assert_called_once_with(
            "generate_unit2_meter_exercises",
            author="author@example.com",
            public=True,
        )
        self.assertEqual(response.context["result"]["command"], "generate_unit2_meter_exercises")
        self.assertEqual(response.context["result"]["status"], "success")

    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True, ALLOWED_HOSTS=["testserver"])
    @patch("apps.exercises.views_tools.call_command")
    def test_post_create_unit_playlist_dispatches_with_parsed_fields(self, call_command_mock):
        response = self.client.post(
            reverse("content-generation"),
            {
                "command": "create_unit_playlist",
                "author": "author@example.com",
                "unit": "11",
                "riemenschneider": "21-30",
                "mode": "roman",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tools/content_generation.html")
        call_command_mock.assert_called_once_with(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21-30",
            mode="roman",
            author="author@example.com",
            public=True,
        )
        self.assertEqual(response.context["result"]["command"], "create_unit_playlist")
        self.assertEqual(response.context["result"]["status"], "success")

    @override_settings(ENABLE_LOCAL_CONTENT_TOOLS=True, ALLOWED_HOSTS=["testserver"])
    @patch("apps.exercises.views_tools.call_command")
    def test_post_preserves_form_data_on_success(self, call_command_mock):
        response = self.client.post(
            reverse("content-generation"),
            {
                "command": "create_unit_playlist",
                "author": "author@example.com",
                "unit": "14",
                "riemenschneider": "31-40",
                "mode": "figures",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tools/content_generation.html")
        call_command_mock.assert_called_once()
        self.assertEqual(
            response.context["form_data"],
            {
                "author": "author@example.com",
                "unit": "14",
                "riemenschneider": "31-40",
                "mode": "figures",
            },
        )
