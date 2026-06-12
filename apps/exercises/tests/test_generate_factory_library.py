"""Tests for generate_factory_library management command.

Uses a tiny synthetic MANIFEST (monkeypatched) so no real generators run.
All tests use Django's TestCase (DB-backed); run via:

    DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
        apps.exercises.tests.test_generate_factory_library -v 1
"""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.exercises.factory_manifest import FactoryUnitEntry
from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()

# ---------------------------------------------------------------------------
# Minimal synthetic manifest used by all tests
# ---------------------------------------------------------------------------

FAKE_ENTRY_UNIT_1 = FactoryUnitEntry(
    unit=1,
    kind="generated",
    commands=[("generate_unit1", {"public": True})],
    tag_query=["unit:1"],
)

FAKE_ENTRY_UNIT_9 = FactoryUnitEntry(
    unit=9,
    kind="generated",
    commands=[],
    uses_shared_commands=True,
    tag_query=["unit:9"],
)

FAKE_ENTRY_CURATED = FactoryUnitEntry(
    unit=99,
    kind="curated",
    playlist_name="Unit 99 — Hand-Authored",
    tag_query=["unit:99"],
)

FAKE_MANIFEST = [FAKE_ENTRY_UNIT_1, FAKE_ENTRY_UNIT_9, FAKE_ENTRY_CURATED]

FAKE_SHARED_COMMANDS = [
    (
        "generate_bach_unit_matrix",
        {
            "riemenschneider": "1-5",
            "units": "9",
            "modes": "roman",
            "public": True,
        },
    ),
]

# Patch targets
_MANIFEST_PATH = "apps.exercises.management.commands.generate_factory_library.MANIFEST"
_SHARED_PATH = "apps.exercises.management.commands.generate_factory_library.SHARED_COMMANDS"


def _call_gfl(stdout=None, **kwargs):
    """Convenience wrapper for calling generate_factory_library."""
    out = stdout or StringIO()
    call_command("generate_factory_library", stdout=out, **kwargs)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------


class DryRunTest(TestCase):
    """--dry-run must print plans without creating Exercise rows."""

    def setUp(self):
        # Factory account for dry-run (author lookup may happen)
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password=""
        )
        self.factory_user.set_unusable_password()
        self.factory_user.save()

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_dry_run_does_not_execute_sub_commands(self, mock_call):
        out = StringIO()
        _call_gfl(
            stdout=out,
            dry_run=True,
            author="factory@monteverdi.app",
        )
        # ensure_factory_account must NOT be called in dry-run
        called_names = [c.args[0] for c in mock_call.call_args_list if c.args]
        self.assertNotIn("ensure_factory_account", called_names)
        # Generators must NOT be called
        self.assertNotIn("generate_unit1", called_names)
        self.assertNotIn("generate_bach_unit_matrix", called_names)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_dry_run_creates_no_exercise_rows(self, mock_call):
        before = Exercise.objects.count()
        _call_gfl(dry_run=True, author="factory@monteverdi.app")
        self.assertEqual(Exercise.objects.count(), before)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_dry_run_output_mentions_commands(self, mock_call):
        out = _call_gfl(dry_run=True, author="factory@monteverdi.app")
        # The log should mention the planned commands
        self.assertIn("generate_unit1", out)
        self.assertIn("generate_bach_unit_matrix", out)


# ---------------------------------------------------------------------------
# Unit-range parsing tests
# ---------------------------------------------------------------------------


class UnitRangeParsingTest(TestCase):
    """--units range parsing produces the correct manifest selection."""

    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password=""
        )
        self.factory_user.set_unusable_password()
        self.factory_user.save()

    def _selected_units(self, units_spec: str) -> set[str]:
        """Return the set of unit labels that would be selected."""
        from apps.exercises.management.commands.generate_factory_library import (
            _parse_units_arg,
            Command,
        )
        parsed = _parse_units_arg(units_spec)
        cmd = Command()
        with patch(_MANIFEST_PATH, FAKE_MANIFEST):
            entries = cmd._select_entries(parsed)
        return {str(e.unit) for e in entries}

    def test_single_unit(self):
        self.assertEqual(self._selected_units("1"), {"1"})

    def test_comma_list(self):
        self.assertEqual(self._selected_units("1,9"), {"1", "9"})

    def test_integer_range(self):
        result = self._selected_units("9-11")
        # Only unit 9 is in FAKE_MANIFEST; 10 and 11 are absent so selection is just {9}
        self.assertEqual(result, {"9"})

    def test_range_expansion(self):
        from apps.exercises.management.commands.generate_factory_library import (
            _parse_units_arg,
        )
        parsed = _parse_units_arg("9-11")
        self.assertEqual(parsed, {"9", "10", "11"})

    def test_branch_b_string(self):
        from apps.exercises.management.commands.generate_factory_library import (
            _parse_units_arg,
        )
        parsed = _parse_units_arg("B1,B2")
        self.assertEqual(parsed, {"B1", "B2"})

    def test_mixed_range_and_branch(self):
        from apps.exercises.management.commands.generate_factory_library import (
            _parse_units_arg,
        )
        parsed = _parse_units_arg("1,9-11,B1")
        self.assertIn("1", parsed)
        self.assertIn("9", parsed)
        self.assertIn("10", parsed)
        self.assertIn("11", parsed)
        self.assertIn("B1", parsed)

    def test_no_matching_units_raises(self):
        with patch(_MANIFEST_PATH, FAKE_MANIFEST):
            with self.assertRaises(CommandError):
                _call_gfl(
                    units="42",
                    author="factory@monteverdi.app",
                    dry_run=True,
                )

    def test_reverse_range_raises(self):
        from apps.exercises.management.commands.generate_factory_library import (
            _parse_units_arg,
        )
        with self.assertRaises(CommandError):
            _parse_units_arg("11-9")


# ---------------------------------------------------------------------------
# --verify tests
# ---------------------------------------------------------------------------


class VerifyTest(TestCase):
    """--verify checks that each unit has >=1 non-empty factory playlist."""

    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password=""
        )
        self.factory_user.set_unusable_password()
        self.factory_user.save()

    # -- Failure cases --------------------------------------------------------

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_verify_fails_when_no_playlist(self):
        """Verify raises CommandError when unit has no factory playlist."""
        with self.assertRaises(CommandError) as ctx:
            _call_gfl(
                verify=True,
                units="1",
                author="factory@monteverdi.app",
            )
        self.assertIn("unit 1", str(ctx.exception).lower())

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_verify_fails_when_playlist_empty(self):
        """Verify raises CommandError when factory playlist has no exercises."""
        # Create playlist but leave it empty
        Playlist.objects.create(
            name="Unit 1 test",
            authored_by=self.factory_user,
            skill_tags=["unit:1"],
        )
        with self.assertRaises(CommandError) as ctx:
            _call_gfl(
                verify=True,
                units="1",
                author="factory@monteverdi.app",
            )
        self.assertIn("unit 1", str(ctx.exception).lower())

    # -- Success case ---------------------------------------------------------

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_verify_passes_with_non_empty_factory_playlist(self):
        """Verify succeeds when unit has >=1 non-empty factory playlist."""
        # Create a playlist + one exercise for unit 1
        exercise = make_umto_exercise(
            self.factory_user,
            description="unit 1 test exercise",
            unit=1,
            skill_tags=["unit:1"],
        )
        playlist = Playlist.objects.create(
            name="Unit 1 — Note Names",
            authored_by=self.factory_user,
            skill_tags=["unit:1"],
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist, exercise=exercise, order=1
        )
        # Should not raise
        out = _call_gfl(
            verify=True,
            units="1",
            author="factory@monteverdi.app",
        )
        self.assertIn("OK", out)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_verify_curated_fails_when_no_playlist(self):
        """Verify raises CommandError when curated unit has no playlist."""
        with self.assertRaises(CommandError) as ctx:
            _call_gfl(
                verify=True,
                units="99",
                author="factory@monteverdi.app",
            )
        self.assertIn("99", str(ctx.exception))

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_verify_curated_passes_with_non_empty_playlist(self):
        """Verify succeeds for a curated unit that has a non-empty playlist."""
        exercise = make_umto_exercise(
            self.factory_user,
            description="unit 99 curated exercise",
            unit=99,
            skill_tags=["unit:99"],
        )
        playlist = Playlist.objects.create(
            name="Unit 99 — Hand-Authored",
            authored_by=self.factory_user,
            skill_tags=["unit:99"],
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist, exercise=exercise, order=1
        )
        # Should not raise
        out = _call_gfl(
            verify=True,
            units="99",
            author="factory@monteverdi.app",
        )
        self.assertIn("OK", out)

    # -- Exit code / CommandError propagation ---------------------------------

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_verify_raises_command_error_on_failure(self):
        """--verify must raise CommandError (exit code 1) on failure."""
        with self.assertRaises(CommandError):
            _call_gfl(
                verify=True,
                author="factory@monteverdi.app",
            )


# ---------------------------------------------------------------------------
# --report smoke test
# ---------------------------------------------------------------------------


class ReportTest(TestCase):
    """--report produces output without writing DB rows."""

    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password=""
        )
        self.factory_user.set_unusable_password()
        self.factory_user.save()

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_report_runs_without_error(self):
        """--report should complete without raising."""
        before = Exercise.objects.count()
        out = _call_gfl(
            report=True,
            units="1,9",
            author="factory@monteverdi.app",
        )
        self.assertEqual(Exercise.objects.count(), before)
        # Should mention unit numbers in some form
        self.assertIn("1", out)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_report_is_readonly(self):
        """--report must not call ensure_factory_account."""
        with patch(
            "apps.exercises.management.commands.generate_factory_library.call_command"
        ) as mock_call:
            _call_gfl(
                report=True,
                units="1",
                author="factory@monteverdi.app",
            )
        called_names = [c.args[0] for c in mock_call.call_args_list if c.args]
        self.assertNotIn("ensure_factory_account", called_names)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_report_counts_official_playlists_only(self):
        """--report must include official playlists and exclude non-official ones."""
        # Create an official playlist with an exercise for unit 1
        official_exercise = make_umto_exercise(
            self.factory_user,
            description="official unit 1 exercise",
            unit=1,
            skill_tags=["unit:1"],
        )
        official_playlist = Playlist.objects.create(
            name="Unit 1 — Official",
            authored_by=self.factory_user,
            skill_tags=["unit:1"],
            is_official=True,
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=official_playlist, exercise=official_exercise, order=1
        )

        # Create a non-official playlist with the same tag — should NOT appear in report coverage
        other_user = User.objects.create_user(
            email="teacher@example.com", password="x"
        )
        unofficial_exercise = make_umto_exercise(
            other_user,
            description="unofficial unit 1 exercise",
            unit=1,
            skill_tags=["unit:1"],
        )
        unofficial_playlist = Playlist.objects.create(
            name="Unit 1 — Mine",
            authored_by=other_user,
            skill_tags=["unit:1"],
            is_official=False,
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=unofficial_playlist, exercise=unofficial_exercise, order=1
        )

        # Report should show unit 1 as covered (official playlist exists)
        out = _call_gfl(
            report=True,
            units="1",
            author="factory@monteverdi.app",
        )
        # Official playlist means no "NO COVERAGE" flag for unit 1
        self.assertNotIn("NO COVERAGE", out)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    def test_report_shows_no_coverage_when_only_unofficial_playlist(self):
        """--report flags unit as uncovered when only non-official playlists exist."""
        other_user = User.objects.create_user(
            email="teacher2@example.com", password="x"
        )
        unofficial_exercise = make_umto_exercise(
            other_user,
            description="unofficial unit 1 exercise",
            unit=1,
            skill_tags=["unit:1"],
        )
        unofficial_playlist = Playlist.objects.create(
            name="Unit 1 — Mine",
            authored_by=other_user,
            skill_tags=["unit:1"],
            is_official=False,
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=unofficial_playlist, exercise=unofficial_exercise, order=1
        )

        out = _call_gfl(
            report=True,
            units="1",
            author="factory@monteverdi.app",
        )
        # Non-official playlist should not count; unit 1 should show as uncovered
        self.assertIn("NO COVERAGE", out)


# ---------------------------------------------------------------------------
# Normal run: ensure_factory_account called first
# ---------------------------------------------------------------------------


class NormalRunTest(TestCase):
    """On a non-dry-run, ensure_factory_account must be called first."""

    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password=""
        )
        self.factory_user.set_unusable_password()
        self.factory_user.save()

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_ensure_factory_account_called_first(self, mock_call):
        _call_gfl(units="1", author="factory@monteverdi.app")
        called_names = [c.args[0] for c in mock_call.call_args_list if c.args]
        self.assertIn("ensure_factory_account", called_names)
        # Must be first
        self.assertEqual(called_names[0], "ensure_factory_account")

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_unit_1_generator_called(self, mock_call):
        _call_gfl(units="1", author="factory@monteverdi.app")
        called_names = [c.args[0] for c in mock_call.call_args_list if c.args]
        self.assertIn("generate_unit1", called_names)

    @patch(_SHARED_PATH, FAKE_SHARED_COMMANDS)
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_shared_command_called_once_for_unit_9(self, mock_call):
        """Selecting unit 9 (uses_shared_commands) triggers SHARED_COMMANDS."""
        _call_gfl(units="9", author="factory@monteverdi.app")
        called_names = [c.args[0] for c in mock_call.call_args_list if c.args]
        bach_calls = [n for n in called_names if n == "generate_bach_unit_matrix"]
        self.assertEqual(len(bach_calls), 1)

    @patch(_SHARED_PATH, [])
    @patch(_MANIFEST_PATH, FAKE_MANIFEST)
    @patch(
        "apps.exercises.management.commands.generate_factory_library.call_command"
    )
    def test_curated_entry_skipped(self, mock_call):
        """Curated entries must not trigger any generator call."""
        _call_gfl(units="99", author="factory@monteverdi.app")
        called_names = [c.args[0] for c in mock_call.call_args_list if c.args]
        # Only ensure_factory_account may be called; no generators
        non_account_calls = [
            n for n in called_names if n != "ensure_factory_account"
        ]
        self.assertEqual(non_account_calls, [])


# ---------------------------------------------------------------------------
# Manifest dataclass validation
# ---------------------------------------------------------------------------


class ManifestDataclassTest(TestCase):
    """FactoryUnitEntry validates kind field."""

    def test_invalid_kind_raises(self):
        with self.assertRaises(ValueError):
            FactoryUnitEntry(unit=1, kind="invalid")

    def test_valid_generated(self):
        e = FactoryUnitEntry(unit=1, kind="generated")
        self.assertEqual(e.kind, "generated")

    def test_valid_curated(self):
        e = FactoryUnitEntry(unit=1, kind="curated")
        self.assertEqual(e.kind, "curated")
