"""Tests for the generate_transpositions management command.

Run with:
    DJANGO_SETTINGS_MODULE=harmony.settings.local \\
    python3 manage.py test apps.exercises.tests.test_generate_transpositions -v 1
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


# ---------------------------------------------------------------------------
# Minimal chordal exercise builder (mirrors test_add_exercise_view_db.py)
# ---------------------------------------------------------------------------

def _make_chordal_exercise(author, *, key="jC_", description="Test Chordal C",
                            skill_tags=None, chords=None):
    """Build and save a minimal UMTO chordal exercise for testing."""
    if chords is None:
        # Two half-note chords in free mode (no meter)
        chords = [
            {"offset": 0.0, "duration": 2.0, "visible": [60, 64, 67], "hidden": [55]},
            {"offset": 2.0, "duration": 2.0, "visible": [62, 65, 69], "hidden": [53]},
        ]
    return save_chordal_umto_exercise(
        description=description,
        author=author,
        chords=chords,
        key=key,
        meter=None,
        clef="keyboard",
        staff_distribution="keyboard",
        source="Test source",
        skill_tags=skill_tags or ["unit:1"],
        complexity=1,
        is_public=True,
        auto_playlist=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class GenerateTranspositionsCommandTest(TestCase):
    """DB-backed tests for generate_transpositions."""

    def setUp(self):
        self.user = User.objects.create_user(email="transpose_test@example.com", password="x")
        self.source = _make_chordal_exercise(
            self.user,
            key="jC_",
            description="My Chordal Exercise",
            skill_tags=["unit:1", "mode:roman"],
        )

    # ---- helper ----

    def _get_copy(self, clean_key):
        desc = f"{self.source.description} ({clean_key})"
        return Exercise.objects.filter(description=desc, authored_by=self.user).first()

    # ---- basic transposition ----

    def test_transpose_to_g_creates_exercise(self):
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("G")
        self.assertIsNotNone(copy, "Exercise (G) should have been created")

    def test_transpose_to_g_midi_shift(self):
        """C→G should shift every MIDI note by -5 (down a perfect fourth)."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("G")
        self.assertIsNotNone(copy)

        src_chords = self.source.data["score"]["umto"]["chords"]
        dst_chords = copy.data["score"]["umto"]["chords"]
        self.assertEqual(len(src_chords), len(dst_chords))

        for src_c, dst_c in zip(src_chords, dst_chords):
            for src_midi, dst_midi in zip(src_c["visible"], dst_c["visible"]):
                self.assertEqual(dst_midi, src_midi - 5,
                                 f"Visible MIDI: expected {src_midi - 5}, got {dst_midi}")
            for src_midi, dst_midi in zip(src_c["hidden"], dst_c["hidden"]):
                self.assertEqual(dst_midi, src_midi - 5,
                                 f"Hidden MIDI: expected {src_midi - 5}, got {dst_midi}")

    def test_transpose_to_g_metadata_key_updated(self):
        """Metadata key in UMTO should become 'jG_' for a G-major transposition."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("G")
        meta = copy.data["score"]["umto"]["metadata"]
        self.assertEqual(meta["key"], "jG_")
        self.assertEqual(copy.data.get("key"), "jG_")

    def test_transpose_preserves_key_correct_spelling(self):
        """Transposed copies must carry key-correct spelling (interval transpose)."""
        # C-major I chord (C E G); transposing to G must yield G-major spelling.
        chords_with_spelling = [
            {
                "offset": 0.0, "duration": 2.0,
                "visible": [60, 64, 67], "hidden": [],
                "spelling": ["C", "E", "G"],
            },
        ]
        src = _make_chordal_exercise(
            self.user,
            key="jC_",
            description="Chordal With Spelling",
            chords=chords_with_spelling,
        )
        call_command(
            "generate_transpositions",
            "--exercise", src.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        desc = f"Chordal With Spelling (G)"
        copy = Exercise.objects.filter(description=desc, authored_by=self.user).first()
        self.assertIsNotNone(copy)
        chord = copy.data["score"]["umto"]["chords"][0]
        spelling = chord.get("spelling")
        self.assertIsNotNone(spelling, "Transposed copy must carry spelling")
        self.assertEqual(spelling, ["G", "B", "D"])

    def test_analysis_slices_carried_unchanged(self):
        """Analysis slices should be recalculated correctly for the target key."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("G")
        src_analysis = self.source.data["score"]["umto"]["analysis"]
        dst_analysis = copy.data["score"]["umto"]["analysis"]
        self.assertEqual(len(src_analysis), len(dst_analysis))
        for src_sl, dst_sl in zip(src_analysis, dst_analysis):
            self.assertEqual(dst_sl["offset"], src_sl["offset"])
            self.assertEqual(dst_sl["content"]["local_key"], "jG_")

    def test_transposed_from_tag_set(self):
        """Each copy must carry a 'transposed_from:<source_id>' skill tag."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("G")
        expected_tag = f"transposed_from:{self.source.id}"
        self.assertIn(expected_tag, copy.skill_tags)

    def test_source_skill_tags_inherited(self):
        """Source skill tags (except transposed_from) should be present on the copy."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("G")
        self.assertIn("unit:1", copy.skill_tags)
        self.assertIn("mode:roman", copy.skill_tags)

    # ---- multiple keys ----

    def test_multiple_keys_creates_all(self):
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "C,G,Bb",
            "--author", self.user.email,
            verbosity=0,
        )
        # Source is already in C — requesting "C" again is an identity
        # transposition and is skipped rather than creating a duplicate.
        self.assertIsNone(self._get_copy("C"))
        self.assertIsNotNone(self._get_copy("G"))
        self.assertIsNotNone(self._get_copy("Bb"))

    def test_bb_midi_shift(self):
        """C→Bb should shift by -2 (shortest interval)."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "Bb",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = self._get_copy("Bb")
        self.assertIsNotNone(copy)
        src_visible_first = self.source.data["score"]["umto"]["chords"][0]["visible"]
        dst_visible_first = copy.data["score"]["umto"]["chords"][0]["visible"]
        for s, d in zip(src_visible_first, dst_visible_first):
            self.assertEqual(d, s - 2, f"C→Bb expected shift -2, got {d - s}")

    # ---- idempotency ----

    def test_idempotent_second_run_no_new_rows(self):
        """Running the command twice must not create duplicate exercises."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        count_after_first = Exercise.objects.filter(
            description=f"{self.source.description} (G)",
            authored_by=self.user,
        ).count()
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        count_after_second = Exercise.objects.filter(
            description=f"{self.source.description} (G)",
            authored_by=self.user,
        ).count()
        self.assertEqual(count_after_first, 1)
        self.assertEqual(count_after_second, 1, "Second run must not create a duplicate")

    def test_overwrite_updates_existing(self):
        """--overwrite should update the existing exercise, not create a new one."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            verbosity=0,
        )
        first_id = self._get_copy("G").id

        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--author", self.user.email,
            "--overwrite",
            verbosity=0,
        )
        copies = Exercise.objects.filter(
            description=f"{self.source.description} (G)",
            authored_by=self.user,
        )
        self.assertEqual(copies.count(), 1)
        self.assertEqual(copies.first().id, first_id, "Overwrite must update the same row")

    # ---- playlist ----

    def test_playlist_created_with_members(self):
        """--playlist creates a playlist and links all copies in key order."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "C,G,Bb",
            "--playlist", "Test Transpositions",
            "--author", self.user.email,
            verbosity=0,
        )
        pl = Playlist.objects.filter(name="Test Transpositions", authored_by=self.user).first()
        self.assertIsNotNone(pl, "Playlist should have been created")
        member_ids = list(
            ExercisePlaylistOrdered.objects.filter(playlist=pl)
            .order_by("order")
            .values_list("exercise_id", flat=True)
        )
        # Source is already in C, so "C" is skipped as an identity
        # transposition — only G and Bb are created and added.
        self.assertEqual(len(member_ids), 2)

    def test_playlist_idempotent_members(self):
        """Running again with the same playlist must not add duplicate members."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--playlist", "Idempotent Test",
            "--author", self.user.email,
            verbosity=0,
        )
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "G",
            "--playlist", "Idempotent Test",
            "--author", self.user.email,
            verbosity=0,
        )
        pl = Playlist.objects.get(name="Idempotent Test", authored_by=self.user)
        count = ExercisePlaylistOrdered.objects.filter(playlist=pl).count()
        self.assertEqual(count, 1, "Second run must not add a duplicate playlist member")

    # ---- validation errors ----

    def test_error_on_nonexistent_exercise(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command(
                "generate_transpositions",
                "--exercise", "EXXXXXX",
                "--keys", "G",
                verbosity=0,
            )

    def test_error_on_non_chordal_umto(self):
        """A voices-kind UMTO exercise must be rejected with a clear error."""
        from django.core.management.base import CommandError
        from apps.exercises.umto_factory import save_umto_exercise
        from apps.exercises.umto import InteractionMode

        # Build a minimal voices-kind UMTO exercise via save_umto_exercise
        # (score_data must be a CIR JSON with at least one measure)
        score_data = {
            "meta": {"key": "jC_", "time": "4/4", "clef": "treble"},
            "measures": [
                {
                    "staves": {
                        "treble": {
                            "voices": [
                                {
                                    "items": [
                                        {
                                            "kind": "note",
                                            "pitch": {"step": "C", "alter": 0, "octave": 4},
                                            "duration": {"type": "q", "dots": 0},
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            ],
        }
        voices_ex = save_umto_exercise(
            description="Voices UMTO Test",
            score_data=score_data,
            author=self.user,
            skill_tags=["unit:1"],
            complexity=1,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="test",
                key="jC_",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.IDENTIFICATION,
                target_voice="soprano",
                unit=1,
            ),
            auto_playlist=False,
        )
        with self.assertRaises(CommandError):
            call_command(
                "generate_transpositions",
                "--exercise", voices_ex.id,
                "--keys", "G",
                verbosity=0,
            )

    def test_invalid_key_skipped_gracefully(self):
        """An unrecognised key name should produce a SKIP row, not a crash."""
        import io
        out = io.StringIO()
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "ZZZZ",
            "--author", self.user.email,
            stdout=out,
            verbosity=0,
        )
        output = out.getvalue()
        self.assertIn("SKIP", output)


class GenerateTranspositionsMinorKeyTest(TestCase):
    """Test that minor-key sources transpose correctly."""

    def setUp(self):
        self.user = User.objects.create_user(email="minor_transpose@example.com", password="x")
        # A-minor source: key='iA_', sig=''
        self.source = _make_chordal_exercise(
            self.user,
            key="iA_",
            description="Am Chordal Exercise",
            skill_tags=["unit:1"],
        )

    def test_am_to_f_sharp_m(self):
        """A-minor → F#-minor: sig '' → '###', vector = +9 % 12 = 9 → -3 (down)."""
        call_command(
            "generate_transpositions",
            "--exercise", self.source.id,
            "--keys", "F#m",
            "--author", self.user.email,
            verbosity=0,
        )
        copy = Exercise.objects.filter(
            description="Am Chordal Exercise (F#m)",
            authored_by=self.user,
        ).first()
        self.assertIsNotNone(copy)
        meta = copy.data["score"]["umto"]["metadata"]
        self.assertEqual(meta["key"], "iF#")

        # midi_vector: pc_vector = (9 - 0) % 12 = 9; 9 >= 6 → vector = -3
        src_visible = self.source.data["score"]["umto"]["chords"][0]["visible"]
        dst_visible = copy.data["score"]["umto"]["chords"][0]["visible"]
        for s, d in zip(src_visible, dst_visible):
            self.assertEqual(d, s - 3, f"Am→F#m expected shift -3, got {d - s}")
