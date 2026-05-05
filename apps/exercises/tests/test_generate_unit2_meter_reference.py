from django.core.management import call_command
from django.test import SimpleTestCase

from apps.exercises.management.commands.generate_unit2_meter_reference import (
    ALLOWED_SIGNATURES,
    build_reference_entry,
    quarter_length_to_label,
)


class Unit2MeterReferenceTests(SimpleTestCase):
    def test_quarter_length_to_label_covers_phase1_values(self):
        self.assertEqual(quarter_length_to_label(0.25), "sixteenth")
        self.assertEqual(quarter_length_to_label(0.75), "dotted eighth")
        self.assertEqual(quarter_length_to_label(3.0), "dotted half")
        self.assertEqual(quarter_length_to_label(6.0), "dotted whole")

    def test_build_reference_entry_handles_compound_two_denominator(self):
        entry = build_reference_entry("6/2")
        self.assertEqual(entry["division_type"], "compound")
        self.assertEqual(entry["grouping"], "duple")
        self.assertEqual(entry["beat_count"], 2)
        self.assertEqual(entry["division_count"], 6)
        self.assertEqual(entry["beat_value"], "dotted whole")
        self.assertEqual(entry["division_value"], "half")

    def test_build_reference_entry_handles_simple_two_denominator(self):
        entry = build_reference_entry("3/2")
        self.assertEqual(entry["division_type"], "simple")
        self.assertEqual(entry["grouping"], "triple")
        self.assertEqual(entry["beat_value"], "half")
        self.assertEqual(entry["division_value"], "quarter")

    def test_allowed_signatures_match_spec_shape(self):
        self.assertIn("6/2", ALLOWED_SIGNATURES)
        self.assertIn("12/16", ALLOWED_SIGNATURES)
        self.assertNotIn("5/8", ALLOWED_SIGNATURES)

    def test_command_writes_all_entries(self):
        result = call_command("generate_unit2_meter_reference")
        self.assertIsNone(result)
