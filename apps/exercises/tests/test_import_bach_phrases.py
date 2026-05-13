import unittest

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.exercises.models import Exercise


class BuildRomanAnalysisOverridesTestCase(unittest.TestCase):
    def _call(self, phrase_score, global_key, unit_tags):
        from apps.exercises.management.commands.import_bach_phrases import (
            _build_roman_analysis_overrides,
        )

        return _build_roman_analysis_overrides(phrase_score, global_key, unit_tags)

    def test_stores_raw_roman_numeral_not_targeted(self):
        from music21 import chord, key as m21key, stream

        s = stream.Score()
        part = stream.Part()
        m = stream.Measure()
        m.append(chord.Chord(["C4", "E4", "G4"]))
        part.append(m)
        s.append(part)
        global_key = m21key.Key("C")
        overrides = self._call(s, global_key, [9])
        self.assertTrue(len(overrides) > 0)
        first = overrides[0]
        self.assertIn("raw_roman_numeral", first["content"])
        self.assertIsNotNone(first["content"]["raw_roman_numeral"])
        self.assertIsNone(first["content"]["roman_numeral"])

    def test_no_filter_applied_for_out_of_scope_chord(self):
        from music21 import chord, key as m21key, stream

        s = stream.Score()
        part = stream.Part()
        m = stream.Measure()
        m.append(chord.Chord(["D4", "F4", "A4"]))
        part.append(m)
        s.append(part)
        global_key = m21key.Key("C")
        overrides = self._call(s, global_key, [9])
        self.assertTrue(len(overrides) > 0)
        self.assertIsNotNone(overrides[0]["content"]["raw_roman_numeral"])
        self.assertIsNone(overrides[0]["content"]["roman_numeral"])

    def test_build_figured_bass_overrides_returns_slices(self):
        """_build_figured_bass_overrides produces slices with raw_figured_bass populated."""
        from apps.exercises.management.commands.import_bach_phrases import (
            _build_figured_bass_overrides,
        )
        from music21 import corpus, key as m21key
        from music21.corpus import chorales

        iterator = chorales.Iterator(1, 1, numberingSystem="riemenschneider")
        score = list(iterator)[0]
        # _build_figured_bass_overrides does its own chordify internally in the plan
        global_key = score.analyze("key")

        result = _build_figured_bass_overrides(score, global_key)
        self.assertTrue(len(result) > 0)
        first = result[0]
        self.assertIn("offset", first)
        self.assertIn("raw_figured_bass", first["content"])
        self.assertIn("figured_bass", first["content"])
        self.assertIsNone(first["content"]["roman_numeral"])
        self.assertIsNone(first["content"]["raw_roman_numeral"])
        # raw_figured_bass is a non-empty string
        self.assertIsInstance(first["content"]["raw_figured_bass"], str)
        self.assertTrue(len(first["content"]["raw_figured_bass"]) > 0)


def _create_admin_user(email: str):
    return get_user_model().objects.create_superuser(
        email=email,
        password="test-password",
    )


def _first_wir_exercise(tag: str):
    return Exercise.objects.filter(skill_tags__contains=[tag]).first()


class WiRImportIntegrationTests(TestCase):
    def test_wir_roman_first_slice_r1(self):
        admin_user = _create_admin_user("wir-r1@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=1,
            author=admin_user.email,
            mode="roman",
            extra_tags=["unit:wir_test"],
        )
        ex = _first_wir_exercise("unit:wir_test")
        self.assertIsNotNone(ex)
        first = ex.data["score"]["umto"]["analysis"][0]["content"]
        self.assertEqual(first["roman_numeral"], "I")
        self.assertEqual(first["local_key"], "G")

    def test_wir_raw_rn_populated(self):
        admin_user = _create_admin_user("wir-raw@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=1,
            author=admin_user.email,
            mode="roman",
            extra_tags=["unit:wir_test2"],
        )
        ex = _first_wir_exercise("unit:wir_test2")
        slices = ex.data["score"]["umto"]["analysis"]
        self.assertTrue(all(s["content"]["raw_roman_numeral"] is not None for s in slices))

    def test_nct_slice_omitted(self):
        admin_user = _create_admin_user("wir-nct@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=1,
            author=admin_user.email,
            mode="roman",
            extra_tags=["unit:wir_test3"],
        )
        ex = _first_wir_exercise("unit:wir_test3")
        for s in ex.data["score"]["umto"]["analysis"]:
            self.assertIsNotNone(s["content"]["roman_numeral"])

    def test_unknown_riemenschneider_raises(self):
        admin_user = _create_admin_user("wir-unknown@example.test")
        with self.assertRaises((CommandError, SystemExit)):
            call_command(
                "import_bach_phrases",
                riemenschneider=999,
                author=admin_user.email,
                mode="roman",
            )
