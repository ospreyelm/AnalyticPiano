from django.test import SimpleTestCase
from apps.exercises.utils.corpus_filter import assign_level, SMALLEST_VALUE_ORDER


class CorpusFilterLevelAssignmentTests(SimpleTestCase):
    """assign_level returns the lowest matching level, or None if no level matches."""

    def test_simple_quarter_only_is_level_1(self):
        self.assertEqual(assign_level("3/4", "q"), 1)

    def test_simple_quarter_in_44_is_level_1(self):
        self.assertEqual(assign_level("4/4", "q"), 1)

    def test_simple_24_quarter_only_is_level_2_not_1(self):
        self.assertEqual(assign_level("2/4", "q"), 2)

    def test_simple_eighth_is_level_2(self):
        self.assertEqual(assign_level("3/4", "8"), 2)

    def test_simple_sixteenth_is_level_3(self):
        self.assertEqual(assign_level("4/4", "16"), 3)

    def test_compound_dotted_quarter_is_level_4(self):
        self.assertEqual(assign_level("6/8", "q", dots=1), 4)

    def test_compound_eighth_is_level_5(self):
        self.assertEqual(assign_level("6/8", "8"), 5)

    def test_compound_sixteenth_is_level_6(self):
        self.assertEqual(assign_level("9/8", "16"), 6)

    def test_derived_simple_half_is_level_7(self):
        self.assertEqual(assign_level("3/2", "h"), 7)

    def test_derived_compound_quarter_is_level_8(self):
        self.assertEqual(assign_level("6/4", "q"), 8)

    def test_unsupported_meter_returns_none(self):
        self.assertIsNone(assign_level("5/4", "q"))

    def test_whole_note_in_simple_is_level_1(self):
        self.assertEqual(assign_level("4/4", "w"), 1)
