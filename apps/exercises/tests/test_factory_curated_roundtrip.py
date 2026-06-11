"""Round-trip test for export_factory_curated / import_factory_curated.

Verifies:
  1. Export produces JSON files with the correct structure.
  2. After deleting the exercises+playlist, import --update restores them with
     identical ids, data payloads, and playlist membership order.
  3. Import without --update (dry run) mutates nothing.

Run with:
    DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
        apps.exercises.tests.test_factory_curated_roundtrip -v 1
"""

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()


def _make_factory_user() -> "User":
    """Create or retrieve the factory account."""
    call_command("ensure_factory_account", stdout=StringIO())
    email = getattr(settings, "FACTORY_USER_EMAIL", "factory@monteverdi.app")
    return User.objects.get(email=email)


class ExportImportRoundTripTest(TestCase):
    """DB-backed round-trip: export → delete → import → assert identical."""

    def setUp(self):
        self.factory_user = _make_factory_user()

        # Create two curated exercises tagged unit:9
        self.ex1 = make_umto_exercise(
            author=self.factory_user,
            description="Curated RT exercise 1",
            skill_tags=["curated", "unit:9"],
            complexity=3,
        )
        self.ex2 = make_umto_exercise(
            author=self.factory_user,
            description="Curated RT exercise 2",
            skill_tags=["curated:test", "unit:9"],
            complexity=5,
        )

        # Make them public so is_public round-trips correctly
        self.ex1.is_public = True
        self.ex1.save()
        self.ex2.is_public = True
        self.ex2.save()

        # Capture ids and data before export
        self.ex1_id = self.ex1.id
        self.ex2_id = self.ex2.id
        self.ex1_data = json.loads(json.dumps(self.ex1.data))
        self.ex2_data = json.loads(json.dumps(self.ex2.data))

        # Create a playlist with both exercises
        self.playlist = Playlist(
            name="Unit 9 Curated Test Playlist",
            authored_by=self.factory_user,
            skill_tags=["unit:9", "curated"],
            is_public=True,
        )
        self.playlist.save()
        ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=self.ex1,
            order=1,
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=self.ex2,
            order=2,
        )

        self.playlist_name = self.playlist.name

    def test_full_roundtrip(self):
        """Export → delete all → import --update → everything restored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # --- EXPORT ---
            out = StringIO()
            call_command("export_factory_curated", out_dir=tmpdir, stdout=out)
            export_output = out.getvalue()
            self.assertIn("Exported", export_output)

            # Verify at least one JSON file was written
            json_files = list(Path(tmpdir).glob("*.json"))
            self.assertGreater(len(json_files), 0, "Expected at least one JSON export file")

            # Check the unit9 file was created and has our exercises
            unit9_file = Path(tmpdir) / "unit9.json"
            self.assertTrue(unit9_file.exists(), "unit9.json should have been created")
            with open(unit9_file) as f:
                exported = json.load(f)

            self.assertEqual(exported["version"], 1)
            self.assertEqual(exported["author_email"], settings.FACTORY_USER_EMAIL)
            exported_ex_ids = [e["id"] for e in exported["exercises"]]
            self.assertIn(self.ex1_id, exported_ex_ids)
            self.assertIn(self.ex2_id, exported_ex_ids)

            # Check playlist exported
            self.assertEqual(len(exported["playlists"]), 1)
            pl_export = exported["playlists"][0]
            self.assertEqual(pl_export["name"], self.playlist_name)
            self.assertEqual(len(pl_export["members"]), 2)

            # --- DELETE ---
            # Delete playlist first (EPO cascade handles membership rows)
            ExercisePlaylistOrdered.objects.filter(playlist=self.playlist).delete()
            self.playlist.delete()
            self.ex1.delete()
            self.ex2.delete()

            # Confirm deletion
            self.assertFalse(Exercise.objects.filter(id=self.ex1_id).exists())
            self.assertFalse(Exercise.objects.filter(id=self.ex2_id).exists())
            self.assertFalse(
                Playlist.objects.filter(name=self.playlist_name, authored_by=self.factory_user).exists()
            )

            # --- IMPORT with --update ---
            out = StringIO()
            call_command("import_factory_curated", dir=tmpdir, update=True, stdout=out)
            import_output = out.getvalue()
            self.assertIn("created", import_output.lower())

            # --- ASSERT exercises restored with same ids ---
            restored_ex1 = Exercise.objects.filter(id=self.ex1_id).first()
            restored_ex2 = Exercise.objects.filter(id=self.ex2_id).first()
            self.assertIsNotNone(restored_ex1, f"Exercise {self.ex1_id} not found after import")
            self.assertIsNotNone(restored_ex2, f"Exercise {self.ex2_id} not found after import")

            # Verify data round-trips (compare JSON-serialised form)
            self.assertEqual(
                json.dumps(restored_ex1.data, sort_keys=True),
                json.dumps(self.ex1_data, sort_keys=True),
                "Exercise 1 data mismatch after round-trip",
            )
            self.assertEqual(
                json.dumps(restored_ex2.data, sort_keys=True),
                json.dumps(self.ex2_data, sort_keys=True),
                "Exercise 2 data mismatch after round-trip",
            )

            # Verify skill_tags preserved
            self.assertIn("curated", restored_ex1.skill_tags)
            self.assertIn("unit:9", restored_ex1.skill_tags)
            self.assertIn("curated:test", restored_ex2.skill_tags)

            # Verify authored_by is factory user
            self.assertEqual(restored_ex1.authored_by, self.factory_user)
            self.assertEqual(restored_ex2.authored_by, self.factory_user)

            # --- ASSERT playlist restored ---
            restored_pl = Playlist.objects.filter(
                name=self.playlist_name, authored_by=self.factory_user
            ).first()
            self.assertIsNotNone(restored_pl, "Playlist not found after import")

            # Verify playlist membership order
            epo_rows = list(
                ExercisePlaylistOrdered.objects.filter(playlist=restored_pl)
                .order_by("order")
                .values_list("exercise__id", "order")
            )
            self.assertEqual(len(epo_rows), 2, "Expected 2 EPO rows after import")
            epo_ids_in_order = [row[0] for row in epo_rows]
            epo_orders = [row[1] for row in epo_rows]
            # Exercises should be in the exported order (ex1 order=1, ex2 order=2)
            self.assertIn(self.ex1_id, epo_ids_in_order)
            self.assertIn(self.ex2_id, epo_ids_in_order)
            idx1 = epo_ids_in_order.index(self.ex1_id)
            idx2 = epo_ids_in_order.index(self.ex2_id)
            self.assertLess(
                epo_orders[idx1], epo_orders[idx2],
                "ex1 should come before ex2 in playlist order"
            )

    def test_dry_run_mutates_nothing(self):
        """Import without --update should make no DB changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Export first
            call_command("export_factory_curated", out_dir=tmpdir, stdout=StringIO())

            # Delete exercises and playlist
            ExercisePlaylistOrdered.objects.filter(playlist=self.playlist).delete()
            self.playlist.delete()
            self.ex1.delete()
            self.ex2.delete()

            ex_count_before = Exercise.objects.count()
            pl_count_before = Playlist.objects.count()

            # Run import WITHOUT --update (dry run)
            out = StringIO()
            call_command("import_factory_curated", dir=tmpdir, stdout=out)
            dry_output = out.getvalue()

            # Output should mention dry-run
            self.assertIn("dry", dry_output.lower())

            # Nothing should have changed
            self.assertEqual(Exercise.objects.count(), ex_count_before)
            self.assertEqual(Playlist.objects.count(), pl_count_before)
            self.assertFalse(Exercise.objects.filter(id=self.ex1_id).exists())
            self.assertFalse(Exercise.objects.filter(id=self.ex2_id).exists())

    def test_update_idempotent(self):
        """Running import --update twice yields the same result (no duplicates)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_factory_curated", out_dir=tmpdir, stdout=StringIO())

            # First import
            call_command("import_factory_curated", dir=tmpdir, update=True, stdout=StringIO())
            ex_count_after_first = Exercise.objects.count()
            pl_count_after_first = Playlist.objects.count()

            # Second import (idempotent)
            call_command("import_factory_curated", dir=tmpdir, update=True, stdout=StringIO())
            self.assertEqual(Exercise.objects.count(), ex_count_after_first)
            self.assertEqual(Playlist.objects.count(), pl_count_after_first)

    def test_non_curated_exercise_not_exported(self):
        """Exercises without curated tag should not appear in the export."""
        # Create a factory-authored exercise WITHOUT a curated tag
        non_curated = make_umto_exercise(
            author=self.factory_user,
            description="Not curated exercise",
            skill_tags=["unit:9"],  # no curated tag
            complexity=1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_factory_curated", out_dir=tmpdir, stdout=StringIO())
            unit9_file = Path(tmpdir) / "unit9.json"
            with open(unit9_file) as f:
                exported = json.load(f)
            exported_ids = [e["id"] for e in exported["exercises"]]
            self.assertNotIn(non_curated.id, exported_ids)
        non_curated.delete()

    def test_non_factory_exercise_not_exported(self):
        """Exercises authored by other users should not appear in the export."""
        other_user = User.objects.create_user(
            email="other@example.com", password="pw"
        )
        non_factory = make_umto_exercise(
            author=other_user,
            description="Other user curated",
            skill_tags=["curated", "unit:9"],
            complexity=1,
        )
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                call_command("export_factory_curated", out_dir=tmpdir, stdout=StringIO())
                unit9_file = Path(tmpdir) / "unit9.json"
                if unit9_file.exists():
                    with open(unit9_file) as f:
                        exported = json.load(f)
                    exported_ids = [e["id"] for e in exported["exercises"]]
                    self.assertNotIn(non_factory.id, exported_ids)
        finally:
            # Delete playlists first (PROTECT constraint on authored_by)
            ExercisePlaylistOrdered.objects.filter(exercise=non_factory).delete()
            Playlist.objects.filter(authored_by=other_user).delete()
            non_factory.delete()
            other_user.delete()

    def test_preserved_id_survives_resave(self):
        """An imported exercise keeps its cross-environment id across save() calls.

        Exercise.save() derives id from the auto-increment _id; the guard added
        for import_factory_curated must keep a preserved id from being clobbered
        when refresh/backfill commands later re-save the row.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_factory_curated", out_dir=tmpdir, stdout=StringIO())

            ExercisePlaylistOrdered.objects.filter(playlist=self.playlist).delete()
            self.playlist.delete()
            self.ex1.delete()
            self.ex2.delete()

            call_command("import_factory_curated", dir=tmpdir, update=True, stdout=StringIO())

            restored = Exercise.objects.get(id=self.ex1_id)
            # _id differs from the original row, so an unguarded set_id would
            # rewrite id to a different value here.
            restored.save()
            restored.refresh_from_db()
            self.assertEqual(restored.id, self.ex1_id)
