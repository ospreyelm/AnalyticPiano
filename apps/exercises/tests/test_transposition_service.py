"""Tests for the transposition service."""
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.exercises.models import Exercise, Playlist
from apps.exercises.services.transposition_service import generate_transposed_copies
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class TranspositionServiceTest(TestCase):
    """Test suite for generate_transposed_copies function."""

    def setUp(self):
        """Create a test user and a minimal UMTO chordal exercise."""
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

        # Create a minimal UMTO chordal exercise (source) in free mode
        # Key: C major, simple 4-chord progression
        # Free mode (meter=None) doesn't require exact metric alignment
        self.source = save_chordal_umto_exercise(
            description="Test Chords in C",
            author=self.author,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},  # C major
                {"offset": 1.0, "duration": 1.0, "visible": [62, 65, 69], "hidden": []},  # D minor
                {"offset": 2.0, "duration": 1.0, "visible": [65, 69, 72], "hidden": []},  # E minor
                {"offset": 3.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},  # C major
            ],
            key="jC_",  # C major in HarmonyLab format
            meter=None,  # Free mode (no meter)
            clef="keyboard",
            staff_distribution="keyboard",
            barline_offsets=[],  # No barlines in free mode
            skill_tags=["unit:1", "Diatonic_Triads"],
            is_public=True,
        )

    def test_raises_on_non_umto_exercise(self):
        """Test that ValueError is raised for non-UMTO exercises."""
        # Create a mock non-UMTO exercise (don't save to avoid schema validation)
        non_umto = Exercise(
            id="LEGACY001",
            description="Non-UMTO Exercise",
            authored_by=self.author,
            data={"isUMTO": False},
        )

        with self.assertRaises(ValueError) as cm:
            generate_transposed_copies(
                source_exercise=non_umto,
                key_set=["G"],
                author=self.author,
            )

        self.assertIn("not a UMTO exercise", str(cm.exception))

    def test_raises_on_non_chordal_umto(self):
        """Test that ValueError is raised for UMTO exercises that are not chordal."""
        # Create a UMTO exercise with a different score_kind (don't save to avoid schema validation)
        non_chordal = Exercise(
            id="UM0001",
            description="UMTO Non-Chordal",
            authored_by=self.author,
            data={
                "isUMTO": True,
                "score": {
                    "umto": {
                        "metadata": {"score_kind": "voice_leading"},
                    }
                },
            },
        )

        with self.assertRaises(ValueError) as cm:
            generate_transposed_copies(
                source_exercise=non_chordal,
                key_set=["G"],
                author=self.author,
            )

        self.assertIn("not chordal", str(cm.exception))

    def test_creates_transposed_copies(self):
        """Test that transposed copies are created for each key in key_set."""
        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G", "Bb"],
            author=self.author,
        )

        # Should create 2 exercises
        self.assertEqual(len(created), 2)

        # Verify they have correct descriptions
        descriptions = {ex.description for ex in created}
        self.assertIn("Test Chords in C (G)", descriptions)
        self.assertIn("Test Chords in C (Bb)", descriptions)

        # Verify they were created as separate rows
        for ex in created:
            self.assertEqual(ex.authored_by, self.author)
            self.assertTrue(ex.data.get("isUMTO"))
            self.assertEqual(ex.data.get("score", {}).get("umto", {}).get("metadata", {}).get("score_kind"), "chordal")

    def test_sets_is_official_flag(self):
        """Test that is_official flag is set on created exercises."""
        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=self.author,
            is_official=True,
        )

        self.assertEqual(len(created), 1)
        ex = created[0]
        self.assertTrue(ex.is_official)

    def test_idempotent_with_overwrite_false(self):
        """Test that calling twice with same keys doesn't create duplicates when overwrite=False."""
        # First call
        created1 = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=self.author,
            overwrite=False,
        )
        self.assertEqual(len(created1), 1)
        first_ex = created1[0]

        # Second call with same key
        created2 = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=self.author,
            overwrite=False,
        )
        self.assertEqual(len(created2), 1)
        second_ex = created2[0]

        # Should be the same exercise (idempotent)
        self.assertEqual(first_ex.id, second_ex.id)

        # Total count in DB should still be only 1 new exercise (+ source)
        all_in_key_g = Exercise.objects.filter(description="Test Chords in C (G)")
        self.assertEqual(all_in_key_g.count(), 1)

    def test_preserves_skill_tags_and_adds_transposed_from_tag(self):
        """Test that skill tags are preserved and transposed_from tag is added."""
        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=self.author,
        )

        self.assertEqual(len(created), 1)
        ex = created[0]
        tags = ex.skill_tags

        # Should have original tags (minus any transposed_from tags)
        self.assertIn("unit:1", tags)
        self.assertIn("Diatonic_Triads", tags)

        # Should have transposed_from tag
        transposed_from_tags = [t for t in tags if t.startswith("transposed_from:")]
        self.assertEqual(len(transposed_from_tags), 1)
        self.assertEqual(transposed_from_tags[0], f"transposed_from:{self.source.id}")

    def test_adds_to_playlist_when_provided(self):
        """Test that exercises are added to playlist when playlist is provided."""
        playlist = Playlist.objects.create(
            name="Test Playlist",
            authored_by=self.author,
        )

        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G", "Bb"],
            playlist=playlist,
            author=self.author,
        )

        self.assertEqual(len(created), 2)

        # Verify both exercises are in the playlist
        playlist_ordered = playlist.exerciseplaylistordered_set.all()
        self.assertEqual(playlist_ordered.count(), 2)

        # Check that created exercises are in the playlist by comparing Exercise objects
        created_set = {ex for ex in created}
        playlist_exercises = {entry.exercise for entry in playlist_ordered}
        self.assertEqual(created_set, playlist_exercises)

    def test_uses_source_author_by_default(self):
        """Test that source author is used when author is not provided."""
        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=None,  # Use default
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].authored_by, self.source.authored_by)

    def test_transposes_chords_correctly(self):
        """Test that chord pitches are transposed by the correct MIDI vector."""
        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],  # From C to G using shortest-interval rule
            author=self.author,
        )

        self.assertEqual(len(created), 1)
        transposed_ex = created[0]

        # Get source and transposed chords
        source_chords = self.source.data.get("score", {}).get("umto", {}).get("chords", [])
        transposed_chords = transposed_ex.data.get("score", {}).get("umto", {}).get("chords", [])

        # Each transposed chord should use the shortest-interval rule
        # From C (sig="") to G (sig="#"):
        # pc_vector = (12 + 7 - 0) % 12 = 7
        # Since 7 >= 6, midi_vector = 7 - 12 = -5 (down 5 semitones is closer than up 7)
        self.assertEqual(len(source_chords), len(transposed_chords))

        for src_chord, tgt_chord in zip(source_chords, transposed_chords):
            src_visible = src_chord.get("visible", [])
            tgt_visible = tgt_chord.get("visible", [])

            # Check that each pitch is transposed by -5 semitones (shortest interval)
            expected_tgt = [p - 5 for p in src_visible]
            self.assertEqual(tgt_visible, expected_tgt)

    def test_preserves_analysis_type_and_display(self):
        """Test that transposed copies inherit the source's analysisType and display,
        instead of silently defaulting to 'roman' (regression: prod created
        figured-bass-unabbreviated transpositions typed as Roman numerals)."""
        source_fb = save_chordal_umto_exercise(
            description="Figured Bass Source",
            author=self.author,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter=None,
            clef="keyboard",
            staff_distribution="keyboard",
            barline_offsets=[],
            analysis_type="figured_bass_unabbreviated",
            display={"showFigures": True, "showRomans": False},
        )

        created = generate_transposed_copies(
            source_exercise=source_fb,
            key_set=["G"],
            author=self.author,
        )

        self.assertEqual(len(created), 1)
        ex = created[0]
        self.assertEqual(ex.data.get("analysisType"), "figured_bass_unabbreviated")
        self.assertEqual(ex.data.get("display"), {"showFigures": True, "showRomans": False})

    def test_skips_invalid_keys(self):
        """Test that invalid keys are skipped gracefully."""
        created = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G", "InvalidKey", "Bb"],
            author=self.author,
        )

        # Should only create 2 exercises (G and Bb), skipping InvalidKey
        self.assertEqual(len(created), 2)
        descriptions = {ex.description for ex in created}
        self.assertIn("Test Chords in C (G)", descriptions)
        self.assertIn("Test Chords in C (Bb)", descriptions)

    def test_skips_identity_key_transposition(self):
        """Test that a key matching the source's own key is skipped, not cloned.

        Regression: a preset key-set that always includes the source's key
        (e.g. 'common' = C, G, D, F, Bb, Eb for a source already in C) created
        an exact duplicate of the original exercise."""
        created = generate_transposed_copies(
            source_exercise=self.source,  # key="jC_" (C major)
            key_set=["C", "G"],
            author=self.author,
        )

        # Only G should be created; C (identity) is skipped.
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].description, "Test Chords in C (G)")

    def test_preserves_analysis_slices(self):
        """Test that analysis slices are preserved in transposed exercises."""
        # Create source with analysis (free mode, no meter)
        source_with_analysis = save_chordal_umto_exercise(
            description="Chords with Analysis",
            author=self.author,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter=None,  # Free mode
            clef="keyboard",
            staff_distribution="keyboard",
            barline_offsets=[],  # Empty barlines for free mode
            analysis=[
                {"offset": 0.0, "content": {"roman_numeral": "I"}, "unit_tags": [], "is_target": True}
            ],
        )

        created = generate_transposed_copies(
            source_exercise=source_with_analysis,
            key_set=["G"],
            author=self.author,
        )

        self.assertEqual(len(created), 1)
        transposed_ex = created[0]

        # Check that analysis is preserved and recalculated for the target key
        analysis = transposed_ex.data.get("score", {}).get("umto", {}).get("analysis", [])
        self.assertEqual(len(analysis), 1)
        self.assertEqual(analysis[0]["content"]["roman_numeral"], "I")
        self.assertEqual(analysis[0]["content"]["local_key"], "jG_")
        self.assertEqual(analysis[0]["content"]["set_class_set"], "{G,B,D}")
        self.assertTrue(analysis[0]["is_target"])

    def test_overwrite_flag_updates_existing_exercise(self):
        """Test that overwrite=True updates an existing exercise."""
        # Create first
        created1 = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=self.author,
            overwrite=False,
        )
        first_ex = created1[0]
        first_id = first_ex.id

        # Create again with overwrite=True (same source, same key)
        created2 = generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            author=self.author,
            overwrite=True,
        )

        # Should return the same exercise (same ID)
        second_ex = created2[0]
        self.assertEqual(second_ex.id, first_id)

        # Should still be only 1 in DB
        all_in_key_g = Exercise.objects.filter(description="Test Chords in C (G)")
        self.assertEqual(all_in_key_g.count(), 1)
