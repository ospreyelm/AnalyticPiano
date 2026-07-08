import unittest
from apps.exercises.taxonomy_reader import TaxonomyReader

class TaxonomyReaderTestCase(unittest.TestCase):
    def test_get_unit_returns_correct_unit(self):
        unit = TaxonomyReader.get_unit("1")
        self.assertIsNotNone(unit)
        self.assertEqual(unit["title"], "Pitch & staff notation")
        
        unit9 = TaxonomyReader.get_unit("9")
        self.assertIsNotNone(unit9)
        self.assertEqual(unit9["title"], "Tonic & dominant")

    def test_get_unit_for_tag_finds_unit(self):
        unit = TaxonomyReader.get_unit_for_tag("Note_Names")
        self.assertIsNotNone(unit)
        self.assertEqual(unit["n"], "1")

    def test_get_unit_for_unknown_tag_returns_none(self):
        unit = TaxonomyReader.get_unit_for_tag("non_existent_tag")
        self.assertIsNone(unit)

    def test_get_all_units_includes_all_tiers(self):
        units = TaxonomyReader.get_all_units()
        self.assertTrue(len(units) > 0)
        unit_ns = [str(u["n"]) for u in units]
        self.assertIn("1", unit_ns)
        self.assertIn("51", unit_ns)

    def test_skill_label_formatting(self):
        self.assertEqual(TaxonomyReader.get_skill_label("Note_Names"), "Note Names")
        self.assertEqual(TaxonomyReader.get_skill_label("satb_spacing"), "Satb Spacing")

    def test_get_all_units_is_cached_not_rebuilt_per_call(self):
        # The admin Exercise change_list calls TaxonomyReader.get_unit_for_tag
        # per row via _playlist_unit_num. get_unit_for_tag delegates to
        # get_all_units, so the flat unit list must be built once and reused,
        # not reallocated + rescanned on every call.
        first = TaxonomyReader.get_all_units()
        second = TaxonomyReader.get_all_units()
        self.assertIs(first, second)

    def test_get_unit_for_tag_uses_cached_unit_index(self):
        # A tag->unit lookup index is built once; repeated lookups for the
        # same tag return the same cached unit dict without rebuilding.
        unit_a = TaxonomyReader.get_unit_for_tag("Note_Names")
        unit_b = TaxonomyReader.get_unit_for_tag("Note_Names")
        self.assertIsNotNone(unit_a)
        self.assertIs(unit_a, unit_b)


class TaxonomyReaderAnalysisTestCase(unittest.TestCase):
    def test_get_unit_analysis_returns_dict_for_unit_with_analysis(self):
        result = TaxonomyReader.get_unit_analysis("11", "roman")
        self.assertIsNotNone(result)
        self.assertIn("cumulative", result)
        self.assertIn("new", result)
        self.assertIsInstance(result["cumulative"], list)
        self.assertIsInstance(result["new"], list)

    def test_get_unit_analysis_returns_none_for_unit_without_analysis(self):
        # Unit 1 has no roman analysis
        result = TaxonomyReader.get_unit_analysis("1", "roman")
        self.assertIsNone(result)

    def test_get_unit_analysis_returns_none_for_unknown_family(self):
        result = TaxonomyReader.get_unit_analysis("11", "nonexistent_family")
        self.assertIsNone(result)

    def test_get_cumulative_values_returns_set_of_strings(self):
        result = TaxonomyReader.get_cumulative_values("11", "roman")
        self.assertIsInstance(result, set)
        self.assertIn("IV", result)
        self.assertIn("I", result)
        self.assertIn("V7", result)

    def test_get_cumulative_values_returns_empty_for_no_analysis(self):
        result = TaxonomyReader.get_cumulative_values("1", "roman")
        self.assertEqual(result, set())

    def test_get_new_values_returns_delta(self):
        result = TaxonomyReader.get_new_values("11", "roman")
        self.assertIn("IV", result)
        self.assertIn("ii", result)
        # Unit 9 chords are NOT in new for unit 11
        self.assertNotIn("I", result)
        self.assertNotIn("V", result)

    def test_get_new_values_returns_empty_for_no_analysis(self):
        result = TaxonomyReader.get_new_values("1", "roman")
        self.assertEqual(result, set())

    def test_figured_bass_sequence_units_12_and_13_matches_curriculum_policy(self):
        unit12_new = TaxonomyReader.get_new_values("12", "figured_bass")
        unit12_cumulative = TaxonomyReader.get_cumulative_values("12", "figured_bass")
        unit13_new = TaxonomyReader.get_new_values("13", "figured_bass")
        unit13_cumulative = TaxonomyReader.get_cumulative_values("13", "figured_bass")

        self.assertEqual(unit12_new, {"6/4", "4/3"})
        self.assertEqual(unit12_cumulative, {"5/3", "7", "6", "6/5", "6/4", "4/3"})
        self.assertEqual(unit13_new, {"4/2"})
        self.assertEqual(unit13_cumulative, {"5/3", "7", "6", "6/5", "6/4", "4/3", "4/2"})
        self.assertNotIn("5/4", unit12_cumulative)
        self.assertNotIn("5/4", unit13_cumulative)
