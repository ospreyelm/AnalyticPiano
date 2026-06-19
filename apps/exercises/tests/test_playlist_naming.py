from django.test import SimpleTestCase

from apps.exercises.utils.playlist_naming import build_new_playlist_name, extract_playlist_mode


class BuildNewPlaylistNameTests(SimpleTestCase):
    def test_unit_prefix_and_mode_suffix(self):
        self.assertEqual(
            build_new_playlist_name("Rule of the Octave", ["unit:13"], "play"),
            "Unit 13 — Rule of the Octave Exercise (Play)",
        )

    def test_multi_unit_prefix(self):
        self.assertEqual(
            build_new_playlist_name("Shared drill", ["unit:9", "unit:13"], "roman"),
            "Units 9, 13 — Shared drill Exercise (Roman)",
        )

    def test_no_unit_tag_skips_prefix(self):
        self.assertEqual(
            build_new_playlist_name("No unit here", ["Note_Names"], "figures"),
            "No unit here Exercise (Figures)",
        )

    def test_already_unit_prefixed_name_not_double_prefixed(self):
        self.assertEqual(
            build_new_playlist_name("Unit 13 - Rule of the Octave", ["unit:13"], "play"),
            "Unit 13 - Rule of the Octave Exercise (Play)",
        )

    def test_every_supported_mode_gets_capitalized_label(self):
        for mode, label in [
            ("play", "Play"),
            ("roman", "Roman"),
            ("figures", "Figures"),
            ("identify", "Identify"),
            ("harmonization", "Harmonization"),
        ]:
            self.assertEqual(
                build_new_playlist_name("X", [], mode),
                f"X Exercise ({label})",
            )

    def test_empty_base_name_returns_unchanged(self):
        self.assertEqual(build_new_playlist_name("", ["unit:13"], "play"), "")
        self.assertEqual(build_new_playlist_name(None, ["unit:13"], "play"), None)


class ExtractPlaylistModeTests(SimpleTestCase):
    def test_extracts_mode_from_authored_exercise_suffix(self):
        self.assertEqual(
            extract_playlist_mode("Unit 13 — Rule of the Octave Exercise (Play)"),
            "play",
        )

    def test_extracts_mode_from_bach_corpus_bare_suffix(self):
        self.assertEqual(
            extract_playlist_mode("Unit 9 — Tonic and Dominant (play)"),
            "play",
        )

    def test_returns_none_for_unsuffixed_legacy_name(self):
        self.assertIsNone(extract_playlist_mode("My Drafts"))

    def test_returns_none_for_empty_name(self):
        self.assertIsNone(extract_playlist_mode(""))
        self.assertIsNone(extract_playlist_mode(None))
