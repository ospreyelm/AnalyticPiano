"""Tests for choosing the analysis type served to the exercise frontend."""

from django.test import SimpleTestCase

from lab.views import _resolve_analysis_type


class ResolveAnalysisTypeTest(SimpleTestCase):
    def test_stored_value_wins_over_heuristic(self):
        data = {"isUMTO": True, "analysisType": "figured_bass", "score": {}}
        self.assertEqual(_resolve_analysis_type(data, "roman"), "figured_bass")

    def test_fallback_to_heuristic_when_not_stored(self):
        data = {"isUMTO": True, "score": {}}
        self.assertEqual(_resolve_analysis_type(data, "roman"), "roman")

    def test_empty_string_treated_as_absent(self):
        data = {"isUMTO": True, "analysisType": "", "score": {}}
        self.assertEqual(_resolve_analysis_type(data, "note_name"), "note_name")

    def test_none_treated_as_absent(self):
        data = {"isUMTO": True, "analysisType": None, "score": {}}
        self.assertEqual(_resolve_analysis_type(data, "scale_degree"), "scale_degree")

    def test_non_dict_data_falls_back(self):
        self.assertEqual(_resolve_analysis_type(None, "roman"), "roman")
        self.assertEqual(_resolve_analysis_type("bad", "roman"), "roman")

    def test_legacy_wrapper_data_uses_heuristic(self):
        data = {"isUMTO": False, "analysisType": "roman", "score": {}}
        self.assertEqual(_resolve_analysis_type(data, "figured_bass"), "figured_bass")
