from django.test import SimpleTestCase

from apps.exercises.models import PerformanceData


def _son(n):
    """n accepted sonorities, minimal shape used by the renderer."""
    return [{"midi": [60 + i], "targetIndex": i, "ts": i} for i in range(n)]


class GetBestHarmonizationPassTests(SimpleTestCase):
    def _pd(self, data):
        # Unsaved instance; method only reads self.data, no DB needed.
        return PerformanceData(data=data)

    def test_picks_most_complete_pass(self):
        pd = self._pd([
            {"id": "ABC123", "harmonization_accepted_sonorities": _son(1)},
            {"id": "ABC123", "harmonization_accepted_sonorities": _son(3)},
            {"id": "ABC123", "harmonization_accepted_sonorities": _son(2)},
        ])
        self.assertEqual(len(pd.get_best_harmonization_pass("ABC123")), 3)

    def test_tie_prefers_most_recent(self):
        pd = self._pd([
            {"id": "ABC123", "harmonization_accepted_sonorities": [{"midi": [1], "targetIndex": 0}]},
            {"id": "ABC123", "harmonization_accepted_sonorities": [{"midi": [2], "targetIndex": 0}]},
        ])
        self.assertEqual(pd.get_best_harmonization_pass("ABC123")[0]["midi"], [2])

    def test_ignores_other_exercise_ids(self):
        pd = self._pd([
            {"id": "ZZZ999", "harmonization_accepted_sonorities": _son(3)},
        ])
        self.assertIsNone(pd.get_best_harmonization_pass("ABC123"))

    def test_matches_transposed_variant_by_base_id(self):
        pd = self._pd([
            {"id": "ABC123_T05", "harmonization_accepted_sonorities": _son(2)},
        ])
        self.assertEqual(len(pd.get_best_harmonization_pass("ABC123")), 2)

    def test_no_sonorities_returns_none(self):
        pd = self._pd([
            {"id": "ABC123"},
            {"id": "ABC123", "harmonization_accepted_sonorities": []},
        ])
        self.assertIsNone(pd.get_best_harmonization_pass("ABC123"))

    def test_empty_data_returns_none(self):
        self.assertIsNone(self._pd([]).get_best_harmonization_pass("ABC123"))
