from unittest import TestCase

from apps.exercises.umto import InteractionMode
from apps.exercises.utils.teacher_play_modes import resolve_mode


class ResolveModeTests(TestCase):
    def test_play_is_playback_with_roman_analysis_type_and_no_display(self):
        result = resolve_mode("play")
        self.assertEqual(result["interaction_mode"], InteractionMode.PLAYBACK)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])

    def test_play_figures_is_playback_with_figured_bass_display_overlay(self):
        result = resolve_mode("play_figures")
        self.assertEqual(result["interaction_mode"], InteractionMode.PLAYBACK)
        self.assertEqual(result["analysis_type"], "figured_bass")
        self.assertEqual(
            result["display"],
            {
                "showFigures": True,
                "figureStyle": "figures_abbrev",
                "analysisRenderer": "notater",
            },
        )

    def test_roman_is_identification_with_roman_analysis_type(self):
        result = resolve_mode("roman")
        self.assertEqual(result["interaction_mode"], InteractionMode.IDENTIFICATION)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])

    def test_figures_is_identification_with_figured_bass_analysis_type(self):
        result = resolve_mode("figures")
        self.assertEqual(result["interaction_mode"], InteractionMode.IDENTIFICATION)
        self.assertEqual(result["analysis_type"], "figured_bass")
        self.assertIsNone(result["display"])

    def test_figures_unabbreviated_uses_unabbreviated_analysis_type(self):
        result = resolve_mode("figures_unabbreviated")
        self.assertEqual(result["interaction_mode"], InteractionMode.IDENTIFICATION)
        self.assertEqual(result["analysis_type"], "figured_bass_unabbreviated")
        self.assertIsNone(result["display"])

    def test_matching_is_analysis_match_with_roman_analysis_type(self):
        result = resolve_mode("matching")
        self.assertEqual(result["interaction_mode"], InteractionMode.ANALYSIS_MATCH)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])

    def test_harmonization_is_harmonization_mode_with_roman_analysis_type(self):
        result = resolve_mode("harmonization")
        self.assertEqual(result["interaction_mode"], InteractionMode.HARMONIZATION)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])
