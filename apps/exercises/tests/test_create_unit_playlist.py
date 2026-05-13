import ast
import inspect
from unittest.mock import MagicMock, patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.models import Exercise, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()


def test_has_new_chord_uses_taxonomy_not_import():
    import apps.exercises.management.commands.create_unit_playlist as mod

    src = inspect.getsource(mod)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "import_bach_phrases" in node.module:
                for alias in node.names:
                    assert alias.name != "UNIT_ALLOWED_ANSWERS"


def test_has_new_chord_prefers_raw_roman_numeral():
    ex = MagicMock()
    ex.data = {
        "score": {
            "umto": {
                "analysis": [
                    {"content": {"roman_numeral": None, "raw_roman_numeral": "IV"}},
                ]
            }
        }
    }
    with patch(
        "apps.exercises.management.commands.create_unit_playlist.TaxonomyReader.get_new_values",
        return_value={"IV"},
    ):
        from apps.exercises.management.commands.create_unit_playlist import Command

        assert Command._has_new_chord(ex, 11) is True


def test_exercise_order_key_prefers_more_in_scope_and_new_material():
    from apps.exercises.management.commands.create_unit_playlist import _exercise_order_key

    better = MagicMock()
    better.description = "Bach R21 - Phrase 1 (mm.1-4) [roman]"
    better.complexity = 3
    better.data = {
        "score": {
            "umto": {
                "analysis": [
                    {"content": {"raw_roman_numeral": "IV", "roman_numeral": None}},
                    {"content": {"raw_roman_numeral": "I", "roman_numeral": None}},
                ]
            }
        }
    }

    worse = MagicMock()
    worse.description = "Bach R22 - Phrase 1 (mm.1-4) [roman]"
    worse.complexity = 2
    worse.data = {
        "score": {
            "umto": {
                "analysis": [
                    {"content": {"raw_roman_numeral": "Ger+6", "roman_numeral": None}},
                    {"content": {"raw_roman_numeral": "I", "roman_numeral": None}},
                ]
            }
        }
    }

    with patch(
        "apps.exercises.management.commands.create_unit_playlist.TaxonomyReader.get_cumulative_values",
        return_value={"I", "IV"},
    ), patch(
        "apps.exercises.management.commands.create_unit_playlist.TaxonomyReader.get_new_values",
        return_value={"IV"},
    ):
        assert _exercise_order_key(better, 11) < _exercise_order_key(worse, 11)


class ImportBachPhrasesIdempotencyTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")
        self.other = User.objects.create_user(email="teacher2@example.com", password="pw")

    def test_skips_existing_description(self):
        make_umto_exercise(author=self.author, skill_tags=[], complexity=1,
                           description="Bach R1 - Phrase 1 (mm.1-4) [roman]")
        count_before = Exercise.objects.count()
        from apps.exercises.management.commands.import_bach_phrases import _description_exists
        self.assertTrue(_description_exists("Bach R1 - Phrase 1 (mm.1-4) [roman]", authored_by=self.author))
        self.assertFalse(_description_exists("Bach R1 - Phrase 1 (mm.1-4) [roman]", authored_by=self.other))
        self.assertFalse(_description_exists("Bach R1 - Phrase 1 (mm.1-4) [play]"))  # different mode = not duplicate
        self.assertFalse(_description_exists("Bach R1 - Phrase 99 (mm.99-200) [roman]"))
        self.assertEqual(Exercise.objects.count(), count_before)


class TaxonomyLookupTest(TestCase):
    def test_finds_unit_by_number(self):
        from apps.exercises.management.commands.create_unit_playlist import _lookup_unit
        unit = _lookup_unit(9)
        self.assertIsNotNone(unit)
        self.assertEqual(str(unit['n']), '9')
        self.assertIn('title', unit)
        self.assertIn('tags', unit)

    def test_returns_none_for_missing_unit(self):
        from apps.exercises.management.commands.create_unit_playlist import _lookup_unit
        self.assertIsNone(_lookup_unit(999))


class CreateUnitPlaylistCommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_creates_playlist(self, mock_call):
        call_command("create_unit_playlist", unit=11, riemenschneider="21-22",
                     author="teacher@example.com", mode="roman")
        p = Playlist.objects.get(
            name="Unit 11 — Pre-dominants (roman)",
            authored_by=self.author,
        )
        self.assertFalse(p.is_dynamic)
        self.assertTrue(p.is_adaptive)
        self.assertIn("unit:11", p.skill_tags)
        self.assertIn("mode:roman", p.skill_tags)

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_calls_import_for_each_chorale(self, mock_call):
        call_command("create_unit_playlist", unit=11, riemenschneider="21-23",
                     author="teacher@example.com", mode="roman")
        import_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "import_bach_phrases"]
        self.assertEqual(len(import_calls), 3)

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_idempotent_playlist(self, mock_call):
        for _ in range(2):
            call_command("create_unit_playlist", unit=11, riemenschneider="21-22",
                         author="teacher@example.com", mode="roman")
        self.assertEqual(
            Playlist.objects.filter(
                name="Unit 11 — Pre-dominants (roman)",
                authored_by=self.author,
            ).count(),
            1,
        )

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_extra_tags_passed_to_import(self, mock_call):
        call_command("create_unit_playlist", unit=11, riemenschneider="21",
                     author="teacher@example.com", mode="roman")
        import_call = next(c for c in mock_call.call_args_list if c.args and c.args[0] == "import_bach_phrases")
        self.assertIn("unit:11", import_call.kwargs.get("extra_tags", []))
        self.assertIn("mode:roman", import_call.kwargs.get("extra_tags", []))

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_public_passthrough(self, mock_call):
        call_command("create_unit_playlist", unit=11, riemenschneider="21",
                     author="teacher@example.com", mode="roman", public=True)
        p = Playlist.objects.get(
            name="Unit 11 — Pre-dominants (roman)",
            authored_by=self.author,
        )
        self.assertTrue(p.is_public)
        import_call = next(c for c in mock_call.call_args_list if c.args and c.args[0] == "import_bach_phrases")
        self.assertTrue(import_call.kwargs.get("public", False))

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_overwrite_passthrough(self, mock_call):
        call_command("create_unit_playlist", unit=11, riemenschneider="21",
                     author="teacher@example.com", mode="roman", overwrite=True)
        import_call = next(c for c in mock_call.call_args_list if c.args and c.args[0] == "import_bach_phrases")
        self.assertTrue(import_call.kwargs.get("overwrite", False))

    def test_fails_on_unknown_unit(self):
        with self.assertRaises(CommandError):
            call_command("create_unit_playlist", unit=999, riemenschneider="1",
                         author="teacher@example.com")

    def test_fails_on_unknown_author(self):
        with self.assertRaises(CommandError):
            call_command("create_unit_playlist", unit=11, riemenschneider="21",
                         author="nobody@example.com")
