"""Tests for choosing the analysis type served to the exercise frontend."""

from django.test import SimpleTestCase

from apps.exercises.services.exercise_context import _resolve_analysis_type


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


from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.exercises.services.exercise_context import generate_exercise_context
from apps.exercises.models import Exercise

User = get_user_model()

class GenerateExerciseContextAnalysisPolicyTest(TestCase):
    def test_analysis_policy_family_falls_back_to_stored_analysis_type(self):
        author = User.objects.create_user(email="testauthor@example.com", password="pw")
        exercise = Exercise.objects.create(
            id="EXTEST",
            authored_by=author,
            data={
                "isUMTO": True,
                "analysisType": "figured_bass",
                "score": {"umto": {"analysis": []}},
                "complexity_score": 1,
            },
            skill_tags=["unit:13"],
        )
        ctx = generate_exercise_context(
            exercise_num=1,
            exercise=exercise,
        )
        self.assertIsNotNone(ctx.get("analysisPolicy"))
        self.assertEqual(ctx["analysisPolicy"]["family"], "figured_bass")
        self.assertEqual(ctx.get("analysisType"), "figured_bass")
