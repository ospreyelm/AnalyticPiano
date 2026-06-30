import ast
import inspect
from unittest.mock import MagicMock, patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
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
            name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
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
                name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
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
            name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
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

    def test_fails_on_unknown_exercise_author(self):
        with self.assertRaises(CommandError):
            call_command("create_unit_playlist", unit=11, riemenschneider="21",
                         author="teacher@example.com", exercise_author="nobody@example.com")

    def test_exercise_author_used_for_candidates_when_playlist_author_differs(self):
        # Reproduces a real incident: a Playlist row is owned by one account
        # (e.g. a "factory" service account) but its actual candidate
        # Exercise rows are owned by a different account. --exercise-author
        # must be used for exercise selection while --author still matches
        # the existing Playlist, so a re-run updates the live playlist in
        # place instead of creating an empty duplicate.
        exercise_owner = User.objects.create_user(email="exercises@example.com", password="pw")
        existing_playlist = Playlist.objects.create(
            name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
            authored_by=self.author,
            is_dynamic=False,
            is_adaptive=True,
            skill_tags=["unit:11", "mode:roman"],
            is_public=True,
        )
        ex = make_umto_exercise(
            author=exercise_owner,
            skill_tags=["unit:11", "mode:roman", "no_key_change", "no_interior_rests"],
            complexity=1,
            description="Bach R21 - Phrase 1 (mm.1-4) [roman]",
        )

        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21",
            author="teacher@example.com",
            exercise_author="exercises@example.com",
            mode="roman",
            playlist_only=True,
            no_chord_filter=True,
        )

        self.assertEqual(
            Playlist.objects.filter(
                name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
                authored_by=self.author,
            ).count(),
            1,
        )
        linked = ExercisePlaylistOrdered.objects.filter(playlist=existing_playlist)
        self.assertEqual(linked.count(), 1)
        self.assertEqual(linked.first().exercise, ex)

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_roman_playlist_uses_display_label(self, mock_call):
        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21",
            author="teacher@example.com",
            mode="roman",
        )
        self.assertTrue(
            Playlist.objects.filter(
                name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
                authored_by=self.author,
            ).exists()
        )

    def test_select_bach_candidates_excludes_modulation_for_early_units(self):
        from apps.exercises.management.commands.create_unit_playlist import _select_bach_candidates
        # Create an exercise with no_key_change and one without (modulation)
        ex_no_mod = make_umto_exercise(
            author=self.author,
            skill_tags=["unit:11", "mode:roman", "no_key_change", "no_interior_rests"],
            complexity=1,
            description="Bach R21 - Phrase 1 (mm.1-4) [roman]"
        )
        ex_with_mod = make_umto_exercise(
            author=self.author,
            skill_tags=["unit:11", "mode:roman", "no_interior_rests"], # missing no_key_change
            complexity=1,
            description="Bach R22 - Phrase 1 (mm.1-4) [roman]"
        )

        # For unit 11 (< 16), ex_with_mod is excluded
        selected_early = _select_bach_candidates(
            author=self.author,
            unit_num=11,
            mode="roman",
            riem_range=[21, 22],
            no_chord_filter=True,
        )
        self.assertIn(ex_no_mod, selected_early)
        self.assertNotIn(ex_with_mod, selected_early)

        # Update unit tag to unit:19 and test for unit 19 (>= 19, modulation taught)
        ex_with_mod.skill_tags.append("unit:19")
        ex_with_mod.save()
        ex_no_mod.skill_tags.append("unit:19")
        ex_no_mod.save()

        selected_late = _select_bach_candidates(
            author=self.author,
            unit_num=19,
            mode="roman",
            riem_range=[21, 22],
            no_chord_filter=True,
        )
        self.assertIn(ex_no_mod, selected_late)
        self.assertIn(ex_with_mod, selected_late)

    def test_select_bach_candidates_excludes_interior_rests(self):
        from apps.exercises.management.commands.create_unit_playlist import _select_bach_candidates
        # Create an exercise with no_interior_rests and one with interior rests
        ex_no_rest = make_umto_exercise(
            author=self.author,
            skill_tags=["unit:11", "mode:roman", "no_key_change", "no_interior_rests"],
            complexity=1,
            description="Bach R21 - Phrase 1 (mm.1-4) [roman]"
        )
        ex_with_rest = make_umto_exercise(
            author=self.author,
            skill_tags=["unit:11", "mode:roman", "no_key_change"], # missing no_interior_rests
            complexity=1,
            description="Bach R22 - Phrase 1 (mm.1-4) [roman]"
        )

        selected = _select_bach_candidates(
            author=self.author,
            unit_num=11,
            mode="roman",
            riem_range=[21, 22],
            no_chord_filter=True,
        )
        self.assertIn(ex_no_rest, selected)
        self.assertNotIn(ex_with_rest, selected)
