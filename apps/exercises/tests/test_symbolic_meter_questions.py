from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.exercises.management.commands.generate_unit2_meter_reference import (
    build_reference_entry,
)
from apps.exercises.symbolic_meter_questions import (
    build_symbolic_problem,
    build_symbolic_problem_set,
    load_reference_rows,
)
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_symbolic_exercise


class SymbolicMeterQuestionTests(SimpleTestCase):
    def test_build_ts_to_full_meter_problem(self):
        ref = {row["time_signature"]: row for row in load_reference_rows()}
        problem = build_symbolic_problem(
            subtype="ts_to_full_meter",
            source_signature="6/4",
            reference_map=ref,
        )
        self.assertEqual(problem["prompt"]["text"], "6/4")
        self.assertEqual(problem["answer"], "compound duple")
        self.assertEqual(len(problem["choices"]), 4)
        self.assertIn("compound duple", problem["choices"])

    def test_meter_to_ts_has_only_one_matching_choice(self):
        ref = {row["time_signature"]: row for row in load_reference_rows()}
        problem = build_symbolic_problem(
            subtype="meter_to_ts",
            source_signature="9/4",
            reference_map=ref,
        )
        matches = [
            ts
            for ts in problem["choices"]
            if ref[ts]["full_meter"] == "compound triple"
        ]
        self.assertEqual(matches, ["9/4"])

    def test_build_problem_set_preserves_manifest_order(self):
        problems = build_symbolic_problem_set(
            [
                {"subtype": "ts_to_grouping", "source_signature": "3/4"},
                {"subtype": "ts_to_division_type", "source_signature": "6/8"},
            ]
        )
        self.assertEqual(
            [p["subtype"] for p in problems],
            ["ts_to_grouping", "ts_to_division_type"],
        )


class SymbolicMeterExerciseSaveTests(TestCase):
    def test_save_umto_symbolic_exercise_creates_umto_wrapped_payload(self):
        user = get_user_model().objects.create_user(
            email="meter@example.com",
            password="pw",
        )
        ref = {"6/4": build_reference_entry("6/4")}
        problem = build_symbolic_problem("ts_to_full_meter", "6/4", ref)
        exercise = save_umto_symbolic_exercise(
            description="Unit 2 meter question set",
            author=user,
            problems=[problem],
            source="Unit 2 symbolic meter questions",
            unit=2,
        )
        self.assertTrue(exercise.data["isUMTO"])
        self.assertEqual(exercise.data["type"], "umto_symbolic_meter")
        self.assertEqual(
            exercise.data["mode"],
            InteractionMode.IDENTIFICATION.value,
        )
        self.assertEqual(exercise.data["problems"][0]["answer"], "compound duple")
