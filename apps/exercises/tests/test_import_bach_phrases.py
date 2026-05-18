import unittest

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.exercises.models import Exercise


class BuildRomanAnalysisOverridesTestCase(unittest.TestCase):
    def _call(self, phrase_score, global_key, unit_tags, riemenschneider=1):
        from apps.exercises.management.commands.import_bach_phrases import (
            _build_roman_analysis_overrides,
        )

        return _build_roman_analysis_overrides(phrase_score, global_key, unit_tags, riemenschneider)

    def test_stores_wir_roman_and_raw_roman_numeral(self):
        from music21.corpus import chorales

        score = list(chorales.Iterator(1, 1, numberingSystem="riemenschneider"))[0]
        global_key = score.analyze("key")
        overrides = self._call(score.measures(8, 12), global_key, [9])
        self.assertTrue(len(overrides) > 0)
        first = overrides[0]
        self.assertIn("raw_roman_numeral", first["content"])
        self.assertIsNotNone(first["content"]["raw_roman_numeral"])
        self.assertEqual(first["content"]["roman_numeral"], "I")
        self.assertEqual(first["content"]["local_key"], "G")

    def test_roman_mode_populates_figured_bass_fields(self):
        from music21.corpus import chorales

        score = list(chorales.Iterator(1, 1, numberingSystem="riemenschneider"))[0]
        global_key = score.analyze("key")
        overrides = self._call(score.measures(8, 12), global_key, [9])

        computable = [
            o for o in overrides
            if o["content"]["roman_numeral"] is not None
        ]
        self.assertTrue(len(computable) > 0)
        self.assertTrue(
            all(o["content"]["raw_figured_bass"] is not None for o in computable)
        )
        self.assertTrue(
            all(o["content"]["figured_bass"] is not None for o in computable)
        )

    def test_roman_mode_figured_bass_uses_declared_chorale_key_not_phrase_analysis(self):
        from music21.corpus import chorales
        from apps.exercises.management.commands.import_bach_phrases import (
            _declared_score_key,
        )

        score = list(chorales.Iterator(3, 3, numberingSystem="riemenschneider"))[0]
        global_key = _declared_score_key(score)
        self.assertEqual(global_key.tonic.name, "E")
        self.assertEqual(global_key.mode, "minor")

        overrides = self._call(score.measures(5, 10), global_key, [], riemenschneider=3)
        target = next(o for o in overrides if o["offset"] == 2.0)
        content = target["content"]
        self.assertEqual(content["roman_numeral"], "V")
        self.assertEqual(content["local_key"], "e")
        self.assertEqual(content["raw_figured_bass"], "5/#3")
        self.assertEqual(content["figured_bass"], "#")

    def test_roman_mode_reconciles_wir_v7_with_4_3_suspension(self):
        from music21.corpus import chorales

        score = list(chorales.Iterator(1, 1, numberingSystem="riemenschneider"))[0]
        global_key = score.analyze("key")
        overrides = self._call(score.measures(8, 12), global_key, [9])

        target = next(o for o in overrides if o["offset"] == 14.0)
        content = target["content"]
        self.assertEqual(content["roman_numeral"], "V7")
        self.assertEqual(content["raw_roman_numeral"], "iv74")
        self.assertEqual(content["raw_figured_bass"], "8/7/4")
        self.assertEqual(content["figured_bass"], "7/4-3")

    def test_emits_null_content_for_beats_without_wir_labels(self):
        from music21.corpus import chorales

        score = list(chorales.Iterator(1, 1, numberingSystem="riemenschneider"))[0]
        global_key = score.analyze("key")
        overrides = self._call(score.measures(8, 12), global_key, [9])
        self.assertEqual(len(overrides), 22)

        nct = next(o for o in overrides if o["offset"] == 0.5)
        content = nct["content"]
        self.assertIsNone(content["roman_numeral"])
        self.assertIsNone(content["local_key"])
        self.assertIsNotNone(content["raw_roman_numeral"])
        self.assertIsNone(content["raw_figured_bass"])
        self.assertIsNone(content["figured_bass"])
        self.assertIsNone(content["pop_symbol"])
        self.assertIsNone(content["functional_label"])

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

    def test_nct_slice_has_null_display_content(self):
        admin_user = _create_admin_user("wir-nct@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=1,
            author=admin_user.email,
            mode="roman",
            extra_tags=["unit:wir_test3"],
        )
        ex = _first_wir_exercise("unit:wir_test3")
        slices = ex.data["score"]["umto"]["analysis"]
        self.assertTrue(any(s["content"]["roman_numeral"] is None for s in slices))
        for s in slices:
            content = s["content"]
            if content["roman_numeral"] is None:
                self.assertIsNone(content["local_key"])
                self.assertIsNone(content["raw_figured_bass"])
                self.assertIsNone(content["figured_bass"])
                self.assertIsNone(content["pop_symbol"])
                self.assertIsNone(content["functional_label"])

    def test_unknown_riemenschneider_raises(self):
        admin_user = _create_admin_user("wir-unknown@example.test")
        with self.assertRaises((CommandError, SystemExit)):
            call_command(
                "import_bach_phrases",
                riemenschneider=999,
                author=admin_user.email,
                mode="roman",
            )

    def test_play_mode_stores_wir_roman_and_figured_bass_analysis(self):
        admin_user = _create_admin_user("wir-play@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=1,
            author=admin_user.email,
            mode="play",
            extra_tags=["unit:wir_play"],
        )
        ex = _first_wir_exercise("unit:wir_play")
        self.assertIsNotNone(ex)
        self.assertEqual(ex.data["mode"], "playback")
        self.assertEqual(ex.data["analysisType"], "roman")

        target = next(
            s for s in ex.data["score"]["umto"]["analysis"]
            if s["offset"] == 14.0
        )
        content = target["content"]
        self.assertEqual(content["roman_numeral"], "V7")
        self.assertEqual(content["local_key"], "G")
        self.assertEqual(content["raw_roman_numeral"], "iv74")
        self.assertEqual(content["raw_figured_bass"], "8/7/4")
        self.assertEqual(content["figured_bass"], "7/4-3")

    def test_play_figures_mode_is_playback_with_figured_bass_display(self):
        admin_user = _create_admin_user("wir-play-figures@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=1,
            author=admin_user.email,
            mode="play_figures",
            extra_tags=["unit:wir_play_figures"],
        )
        ex = _first_wir_exercise("unit:wir_play_figures")
        self.assertIsNotNone(ex)
        self.assertEqual(ex.data["mode"], "playback")
        self.assertEqual(ex.data["analysisType"], "figured_bass")
        self.assertEqual(ex.data["display"]["showFigures"], True)
        self.assertEqual(ex.data["display"]["figureStyle"], "figures_abbrev")

        target = next(
            s for s in ex.data["score"]["umto"]["analysis"]
            if s["offset"] == 14.0
        )
        self.assertEqual(target["content"]["roman_numeral"], "V7")
        self.assertEqual(target["content"]["figured_bass"], "7/4-3")

    def test_r3_import_uses_declared_e_minor_key_for_figures_without_breaking_slices(self):
        admin_user = _create_admin_user("wir-r3-key@example.test")
        call_command(
            "import_bach_phrases",
            riemenschneider=3,
            author=admin_user.email,
            mode="roman",
            extra_tags=["unit:wir_r3_key"],
        )
        ex = Exercise.objects.get(
            authored_by=admin_user,
            description__contains="Phrase 2",
        )
        self.assertEqual(ex.data["score"]["umto"]["metadata"]["key"], "iE_")

        target = next(
            s for s in ex.data["score"]["umto"]["analysis"]
            if s["offset"] == 2.0
        )
        self.assertEqual(target["content"]["roman_numeral"], "V")
        self.assertEqual(target["content"]["local_key"], "e")
        self.assertEqual(target["content"]["raw_figured_bass"], "5/#3")
        self.assertEqual(target["content"]["figured_bass"], "#")
