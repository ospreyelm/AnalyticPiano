import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Configure minimal Django settings for testing if not already configured
import os
import django
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "harmony.settings"
    django.setup()

from apps.exercises.mastery import compute_mastery_level, compute_decay
from apps.exercises.skill_graph import MASTERY_LEVELS, MASTERY_TAGS, LITERACY_TAGS
from django.utils import timezone

class TestMasteryLogic(unittest.TestCase):
    def test_compute_mastery_level_not_started(self):
        self.assertEqual(compute_mastery_level([], []), "not_started")

    def test_compute_mastery_level_attempted(self):
        self.assertEqual(compute_mastery_level([True], ["2026-04-17"]), "attempted")
        self.assertEqual(compute_mastery_level([False], ["2026-04-17"]), "attempted")

    def test_compute_mastery_level_familiar(self):
        # 3+ correct in last 5
        self.assertEqual(compute_mastery_level([True, True, True], ["2026-04-17"]), "familiar")
        self.assertEqual(compute_mastery_level([False, False, True, True, True], ["2026-04-17"]), "familiar")
        # 2 correct in last 5 is still attempted (unless total attempts < 5 and all correct, which is not this case)
        self.assertEqual(compute_mastery_level([False, False, False, True, True], ["2026-04-17"]), "attempted")

    def test_compute_mastery_level_proficient(self):
        # 7+ correct in last 10
        history = [True] * 7 + [False] * 3
        self.assertEqual(compute_mastery_level(history, ["2026-04-17"]), "proficient")

    def test_compute_mastery_level_mastered_requirements(self):
        # Perfect last 10 but only 1 day -> proficient
        history = [True] * 10
        days = ["2026-04-17"]
        self.assertEqual(compute_mastery_level(history, days), "proficient")

        # Perfect last 10 and 2 days -> mastered
        days = ["2026-04-17", "2026-04-18"]
        self.assertEqual(compute_mastery_level(history, days), "mastered")

        # Perfect last 8 (all available) and 2 days -> mastered
        history = [True] * 8
        self.assertEqual(compute_mastery_level(history, days), "mastered")

    def test_compute_decay_mastered(self):
        now = timezone.now()
        # 61 days idle
        last_practiced = now - timedelta(days=61)
        self.assertEqual(compute_decay("mastered", last_practiced), "proficient")
        # 59 days idle -> no decay
        last_practiced = now - timedelta(days=59)
        self.assertEqual(compute_decay("mastered", last_practiced), "mastered")

    def test_compute_decay_proficient(self):
        now = timezone.now()
        # 31 days idle
        last_practiced = now - timedelta(days=31)
        self.assertEqual(compute_decay("proficient", last_practiced), "familiar")
        # 29 days idle -> no decay
        last_practiced = now - timedelta(days=29)
        self.assertEqual(compute_decay("proficient", last_practiced), "proficient")

    def test_compute_decay_familiar(self):
        now = timezone.now()
        # 15 days idle
        last_practiced = now - timedelta(days=15)
        self.assertEqual(compute_decay("familiar", last_practiced), "attempted")
        # 13 days idle -> no decay
        last_practiced = now - timedelta(days=13)
        self.assertEqual(compute_decay("familiar", last_practiced), "familiar")

    def test_compute_decay_unaffected(self):
        now = timezone.now()
        last_practiced = now - timedelta(days=100)
        self.assertEqual(compute_decay("attempted", last_practiced), "attempted")
        self.assertEqual(compute_decay("not_started", last_practiced), "not_started")

class TestMasteryTagsConstant(unittest.TestCase):
    def test_includes_all_canonical_harmony_tags(self):
        canonical = {
            "Diatonic_Triads", "Inversions_First", "Inversions_Second",
            "Dominant_Seventh", "Diminished_Seventh", "Half_Diminished_Seventh",
            "Cadence_Half", "Cadence_Perfect_Authentic", "Cadence_Deceptive", "Cadence_Plagal",
            "Secondary_Dominant", "Secondary_Leading_Tone",
            "Neapolitan_Sixth", "Augmented_Sixth",
            "Picardy_Third", "Modulation_Diatonic_Pivot",
        }
        self.assertTrue(canonical.issubset(MASTERY_TAGS))

    def test_includes_all_literacy_tags(self):
        self.assertTrue(set(LITERACY_TAGS).issubset(MASTERY_TAGS))

    def test_includes_unit_number_tags(self):
        self.assertIn("unit:1", MASTERY_TAGS)
        self.assertIn("unit:9", MASTERY_TAGS)
        self.assertIn("unit:51", MASTERY_TAGS)

    def test_includes_branch_unit_tags(self):
        self.assertIn("unit:A1", MASTERY_TAGS)
        self.assertIn("unit:A15", MASTERY_TAGS)
        self.assertIn("unit:B1", MASTERY_TAGS)
        self.assertIn("unit:B15", MASTERY_TAGS)
        self.assertIn("unit:B16", MASTERY_TAGS)
        self.assertIn("unit:B30", MASTERY_TAGS)
        self.assertIn("unit:C1", MASTERY_TAGS)
        self.assertIn("unit:C8", MASTERY_TAGS)
        self.assertIn("unit:D1", MASTERY_TAGS)
        self.assertIn("unit:D8", MASTERY_TAGS)

    def test_excludes_unit_prefixed_long_form_tags(self):
        self.assertNotIn("unit:9_Dominant_Seventh", MASTERY_TAGS)
        self.assertNotIn("unit:10_inversions_first", MASTERY_TAGS)
        self.assertNotIn("unit:16_Secondary_Dominant", MASTERY_TAGS)


class TestRecordAttemptCanonicalFilter(unittest.TestCase):
    """Verify record_attempt only updates StudentSkillMastery for MASTERY_TAGS."""

    def _make_exercise(self, tags):
        ex = MagicMock()
        ex.skill_tags = tags
        return ex

    def _make_mock_mastery_module(self):
        """Return a fake apps.exercises.models module with a mock StudentSkillMastery."""
        mock_mastery_cls = MagicMock()
        mock_models_module = MagicMock()
        mock_models_module.StudentSkillMastery = mock_mastery_cls
        return mock_models_module, mock_mastery_cls

    def _record_attempt_with_mock(self, exercise, correct):
        """Run record_attempt with apps.exercises.models replaced by a mock."""
        import sys
        mock_models_module, mock_mastery_cls = self._make_mock_mastery_module()

        mock_row = MagicMock()
        mock_row.level = "not_started"
        mock_row.last_practiced = None
        mock_row.recent_history = []
        mock_row.practice_days = []
        mock_row.total_attempts = 0
        mock_row.total_correct = 0
        mock_row.first_attempted = None
        mock_mastery_cls.objects.get_or_create.return_value = (mock_row, True)

        with patch.dict(sys.modules, {"apps.exercises.models": mock_models_module}):
            from apps.exercises.mastery import record_attempt
            record_attempt(user_id=1, exercise=exercise, correct=correct)

        return mock_mastery_cls

    def test_only_canonical_tags_trigger_mastery_updates(self):
        ex = self._make_exercise([
            "Dominant_Seventh",           # canonical — should update
            "unit:9_Dominant_Seventh",    # long-form duplicate — filtered out
            "unit:9",                     # unit-number — should update
            "bach",                       # free-form — filtered out
            "Read_Treble_Clef",           # literacy — should update
        ])

        mock_mastery_cls = self._record_attempt_with_mock(ex, correct=True)

        called_tags = [
            call.kwargs["skill_tag"]
            for call in mock_mastery_cls.objects.get_or_create.call_args_list
        ]
        self.assertIn("Dominant_Seventh", called_tags)
        self.assertIn("unit:9", called_tags)
        self.assertIn("Read_Treble_Clef", called_tags)
        self.assertNotIn("unit:9_Dominant_Seventh", called_tags)
        self.assertNotIn("bach", called_tags)

    def test_no_mastery_tags_triggers_no_updates(self):
        ex = self._make_exercise(["bach", "random_tag"])
        mock_mastery_cls = self._record_attempt_with_mock(ex, correct=True)
        mock_mastery_cls.objects.get_or_create.assert_not_called()

    def test_empty_skill_tags_triggers_no_updates(self):
        ex = self._make_exercise([])
        mock_mastery_cls = self._record_attempt_with_mock(ex, correct=True)
        mock_mastery_cls.objects.get_or_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
