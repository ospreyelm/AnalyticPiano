from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


User = get_user_model()


class GenerateBachUnitMatrixCommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

    @patch("apps.exercises.management.commands.generate_bach_unit_matrix.call_command")
    def test_imports_each_mode_once_with_all_unit_tags_then_builds_playlists(self, mock_call):
        call_command(
            "generate_bach_unit_matrix",
            units="9,10,11",
            modes="roman,play",
            riemenschneider="1-2",
            author="teacher@example.com",
            public=True,
            skip_refresh=True,
        )

        import_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "import_bach_phrases"]
        playlist_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "create_unit_playlist"]

        self.assertEqual(len(import_calls), 2)
        self.assertEqual(import_calls[0].kwargs["mode"], "roman")
        self.assertEqual(import_calls[0].kwargs["riemenschneider"], "1-2")
        self.assertEqual(
            import_calls[0].kwargs["extra_tags"],
            ["unit:9", "unit:10", "unit:11", "mode:roman"],
        )
        self.assertTrue(import_calls[0].kwargs["overwrite"])
        self.assertTrue(import_calls[0].kwargs["public"])

        self.assertEqual(len(playlist_calls), 6)
        self.assertTrue(all(c.kwargs["playlist_only"] for c in playlist_calls))

    @patch("apps.exercises.management.commands.generate_bach_unit_matrix.call_command")
    def test_playlist_only_skips_imports(self, mock_call):
        call_command(
            "generate_bach_unit_matrix",
            units="9,10",
            modes="roman",
            riemenschneider="1-2",
            author="teacher@example.com",
            playlist_only=True,
            skip_refresh=True,
        )

        self.assertFalse(any(c.args and c.args[0] == "import_bach_phrases" for c in mock_call.call_args_list))
        playlist_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "create_unit_playlist"]
        self.assertEqual(len(playlist_calls), 2)

    def test_rejects_unknown_author(self):
        with self.assertRaisesMessage(Exception, "No user with email"):
            call_command(
                "generate_bach_unit_matrix",
                units="9",
                modes="roman",
                riemenschneider="1",
                author="missing@example.com",
                skip_refresh=True,
            )
