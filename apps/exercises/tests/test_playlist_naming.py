from django.test import SimpleTestCase

from apps.exercises.utils.playlist_naming import (
    SUPPORTED_TEACHER_PLAY_MODES,
    build_canonical_playlist_name,
    build_new_playlist_name,
    canonical_mode_label,
    extract_playlist_mode,
)


class CanonicalPlaylistNamingTests(SimpleTestCase):
    def test_every_supported_mode_has_a_stable_name(self):
        expected = {
            "play": "Play",
            "play_figures": "Play + figures",
            "roman": "Roman",
            "figures": "Figures",
            "figures_unabbreviated": "Figures (unabbreviated)",
            "matching": "Matching",
            "harmonization": "Harmonization",
        }

        self.assertEqual(SUPPORTED_TEACHER_PLAY_MODES, tuple(expected))

        for mode, label in expected.items():
            self.assertEqual(canonical_mode_label(mode), label)
            self.assertEqual(
                build_canonical_playlist_name(11, mode),
                f"Unit 11 — Exercises ({label})",
            )

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "Unsupported interaction mode: counterpoint",
        ):
            canonical_mode_label("counterpoint")

        with self.assertRaisesMessage(
            ValueError,
            "Unsupported interaction mode: counterpoint",
        ):
            build_canonical_playlist_name(11, "counterpoint")

    def test_build_new_playlist_name_keeps_current_compatibility_behavior(self):
        self.assertEqual(
            build_new_playlist_name("Rule of the Octave", ["unit:13"], "play"),
            "Unit 13 — Rule of the Octave Exercise (Play)",
        )
        self.assertEqual(
            build_new_playlist_name("Unit 13 - Existing Prefix", ["unit:13"], "roman"),
            "Unit 13 - Existing Prefix Exercise (Roman)",
        )

    def test_extract_playlist_mode_keeps_current_compatibility_behavior(self):
        self.assertEqual(
            extract_playlist_mode("Unit 13 — Rule of the Octave Exercise (Play)"),
            "play",
        )
        self.assertEqual(
            extract_playlist_mode("Unit 9 — Tonic and Dominant (play)"),
            "play",
        )
        self.assertIsNone(extract_playlist_mode("Legacy Drafts"))
