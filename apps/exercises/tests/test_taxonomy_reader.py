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
