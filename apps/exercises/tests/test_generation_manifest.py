"""Tests for GenerationManifest dataclass and execution."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import Exercise, Playlist
from apps.exercises.services.generation_manifest import GenerationManifest
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class GenerationManifestTest(TestCase):
    """Test GenerationManifest dataclass and methods."""

    def setUp(self):
        """Create test users."""
        self.author = User.objects.create_user(
            email="author@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
        )

    def test_dry_run_summary_bach_riemenschneider(self):
        """Test dry_run_summary for Bach Riemenschneider source."""
        manifest = GenerationManifest(
            source="bach_riemenschneider",
            source_ref="1-5",
            unit=9,
            skill_tags=["unit:9"],
            exercise_types=["play", "roman"],
            key_set=["C", "G", "D"],
            playlist_target=None,
            is_official=False,
            author_email="author@example.com",
        )
        summary = manifest.dry_run_summary()

        self.assertEqual(summary["source"], "bach_riemenschneider")
        self.assertEqual(summary["source_ref"], "1-5")
        self.assertEqual(summary["unit"], 9)
        self.assertEqual(summary["exercise_types"], ["play", "roman"])
        self.assertEqual(summary["key_count"], 3)
        self.assertEqual(summary["estimated_exercises"], 6)  # 2 types * 3 keys
        self.assertEqual(summary["is_official"], False)
        self.assertIsNone(summary["playlist_target"])

    def test_dry_run_summary_played_in(self):
        """Test dry_run_summary for played_in source."""
        manifest = GenerationManifest(
            source="played_in",
            source_ref="EA0001",
            unit=10,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C", "G", "D", "A"],
            playlist_target=123,
            is_official=True,
            author_email="author@example.com",
        )
        summary = manifest.dry_run_summary()

        self.assertEqual(summary["source"], "played_in")
        self.assertEqual(summary["source_ref"], "EA0001")
        self.assertEqual(summary["unit"], 10)
        self.assertEqual(summary["key_count"], 4)
        self.assertEqual(summary["estimated_exercises"], 4)  # 1 type * 4 keys
        self.assertEqual(summary["is_official"], True)
        self.assertEqual(summary["playlist_target"], 123)

    def test_execute_dry_run_mode_returns_summary(self):
        """Test execute() in dry_run mode returns summary dict."""
        manifest = GenerationManifest(
            source="bach_riemenschneider",
            source_ref="1-30",
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C", "G"],
            playlist_target=None,
            is_official=False,
            author_email="author@example.com",
            dry_run=True,
        )
        result = manifest.execute()

        self.assertIsInstance(result, dict)
        self.assertIn("estimated_exercises", result)
        self.assertEqual(result["estimated_exercises"], 2)

    def test_execute_raises_on_unknown_author(self):
        """Test execute() raises ValueError if author not found."""
        manifest = GenerationManifest(
            source="played_in",
            source_ref="EA0001",
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C"],
            playlist_target=None,
            is_official=False,
            author_email="nonexistent@example.com",
            dry_run=False,
        )
        with self.assertRaises(ValueError) as ctx:
            manifest.execute()
        self.assertIn("No user with email", str(ctx.exception))

    def test_execute_raises_on_unknown_source(self):
        """Test execute() raises ValueError for unknown source."""
        manifest = GenerationManifest(
            source="invalid_source",
            source_ref="1-30",
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C"],
            playlist_target=None,
            is_official=False,
            author_email="author@example.com",
            dry_run=False,
        )
        with self.assertRaises(ValueError) as ctx:
            manifest.execute()
        self.assertIn("Unknown source", str(ctx.exception))

    def test_execute_played_in_raises_on_missing_exercise(self):
        """Test execute() with played_in source raises if exercise not found."""
        manifest = GenerationManifest(
            source="played_in",
            source_ref="NONEXISTENT",
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C"],
            playlist_target=None,
            is_official=False,
            author_email="author@example.com",
            dry_run=False,
        )
        with self.assertRaises(ValueError) as ctx:
            manifest.execute()
        self.assertIn("not found", str(ctx.exception))

    def test_execute_played_in_raises_on_missing_playlist(self):
        """Test execute() with played_in source raises if playlist not found."""
        # Create a valid UMTO chordal exercise
        exercise = save_chordal_umto_exercise(
            description="Test exercise",
            author=self.author,
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

        manifest = GenerationManifest(
            source="played_in",
            source_ref=exercise.id,
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C"],
            playlist_target=99999,  # Non-existent playlist
            is_official=False,
            author_email="author@example.com",
            dry_run=False,
        )
        with self.assertRaises(ValueError) as ctx:
            manifest.execute()
        self.assertIn("Playlist", str(ctx.exception))

    def test_execute_played_in_creates_transposed_copies(self):
        """Test execute() with played_in source creates transposed copies."""
        # Create a valid UMTO chordal exercise
        exercise = save_chordal_umto_exercise(
            description="Test exercise",
            author=self.author,
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
            skill_tags=["Test_Skill"],
            complexity=3,
            is_public=False,
        )

        manifest = GenerationManifest(
            source="played_in",
            source_ref=exercise.id,
            unit=9,
            skill_tags=["Additional_Skill"],
            exercise_types=["play"],
            key_set=["C", "G"],
            playlist_target=None,
            is_official=False,
            author_email="author@example.com",
            dry_run=False,
        )
        created = manifest.execute()

        # Should return list of created exercises
        self.assertIsInstance(created, list)
        self.assertEqual(len(created), 2)  # One for each key

        # Check that exercises were created with correct properties
        for ex in created:
            self.assertEqual(ex.authored_by, self.author)
            self.assertIn(f"transposed_from:{exercise.id}", ex.skill_tags)
            self.assertIn("Test_Skill", ex.skill_tags)

    def test_execute_played_in_adds_to_playlist(self):
        """Test execute() adds created exercises to playlist when specified."""
        # Create a valid UMTO chordal exercise
        source_exercise = save_chordal_umto_exercise(
            description="Source exercise",
            author=self.author,
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

        # Create a playlist
        playlist = Playlist.objects.create(
            name="Test Playlist",
            authored_by=self.author,
        )

        manifest = GenerationManifest(
            source="played_in",
            source_ref=source_exercise.id,
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C", "G"],
            playlist_target=playlist.pk,
            is_official=False,
            author_email="author@example.com",
            dry_run=False,
        )
        created = manifest.execute()

        # Check that created exercises are in the playlist
        self.assertEqual(len(created), 2)
        playlist_exercise_ids = set(playlist.untransposed_exercises_ids)
        for ex in created:
            self.assertIn(ex.id, playlist_exercise_ids)

    def test_execute_played_in_with_is_official(self):
        """Test execute() with is_official=True sets is_official on created exercises."""
        source_exercise = save_chordal_umto_exercise(
            description="Source exercise",
            author=self.author,
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

        manifest = GenerationManifest(
            source="played_in",
            source_ref=source_exercise.id,
            unit=9,
            skill_tags=[],
            exercise_types=["play"],
            key_set=["C"],
            playlist_target=None,
            is_official=True,
            author_email="author@example.com",
            dry_run=False,
        )
        created = manifest.execute()

        # Check that created exercises have is_official=True
        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].is_official)
