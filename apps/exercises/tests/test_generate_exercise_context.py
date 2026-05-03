from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class GenerateExerciseContextAnalysisPolicyTest(SimpleTestCase):
    def _make_exercise_data(self, raw_rn_list, unit_tags=None):
        if isinstance(raw_rn_list, str):
            raw_rn_list = [raw_rn_list]
        slices = []
        for i, raw_rn in enumerate(raw_rn_list):
            slices.append(
                {
                    "offset": float(i),
                    "content": {
                        "roman_numeral": None,
                        "raw_roman_numeral": raw_rn,
                        "figured_bass": None,
                        "pop_symbol": None,
                        "functional_label": None,
                    },
                    "unit_tags": unit_tags or [12],
                    "is_target": False,
                }
            )
        return {
            "isUMTO": False,
            "type": "test",
            "key": "jC_",
            "keySignature": "",
            "analysisType": "roman",
            "score": {
                "meta": {"key": "jC_", "time": "4/4"},
                "measures": [],
                "umto": {
                    "metadata": {
                        "exercise_id": "TEST01",
                        "source": "test",
                        "key": "C",
                        "meter": "4/4",
                        "complexity_score": 9,
                        "mode": "identification",
                    },
                    "voices": {"S": [], "A": [], "T": [], "B": []},
                    "analysis": slices,
                    "grading": [],
                },
            },
            "complexity_score": 9,
        }

    def _make_mocks(self, cumulative, new_set, mock_reader, mock_perf):
        mock_reader.get_cumulative_values.return_value = cumulative
        mock_reader.get_new_values.return_value = new_set
        mock_reader.get_unit_analysis.return_value = {
            "cumulative": [{"value": v, "display": v} for v in sorted(cumulative)],
            "new": [{"value": v, "display": v} for v in sorted(new_set)],
        }
        mock_reader.get_unit_for_tag.return_value = None
        mock_perf.objects.filter.return_value.last.return_value = None

    def _run_context(self, data, unit_n="12"):
        from apps.exercises.models import Exercise, Playlist
        from lab.views import generate_exercise_context

        ex = MagicMock(spec=Exercise)
        ex.data = data
        ex.skill_tags = [f"unit:{unit_n}", "mode:roman"]
        ex.id = "TEST01"
        ex.complexity = 9
        ex.is_public = True

        pl = MagicMock(spec=Playlist)
        pl.skill_tags = [f"unit:{unit_n}", "mode:roman"]
        pl.is_adaptive = False
        pl.is_dynamic = False
        pl.tags = []
        pl.feedback_mode = ""
        pl.exercise_count = 1
        pl.prev_num.return_value = None
        pl.next_num.return_value = None
        pl.get_exercise_obj_by_num.return_value = None
        pl.get_exercise_url_by_num.return_value = None
        pl.exercise_list = [ex]
        pl.id = "PLTEST"
        pl.min_complexity = 1
        pl.max_complexity = 12

        return generate_exercise_context(
            exercise_num=1,
            exercise=ex,
            user=MagicMock(id=1),
            playlist=pl,
            course=None,
        )

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_analysis_policy_included_in_context(self, mock_reader, mock_perf):
        cumulative = {"I", "V", "IV"}
        self._make_mocks(cumulative, {"IV"}, mock_reader, mock_perf)

        ctx = self._run_context(self._make_exercise_data("I"), unit_n="11")

        self.assertIn("analysisPolicy", ctx)
        policy = ctx["analysisPolicy"]
        self.assertEqual(policy["family"], "roman")
        self.assertEqual(policy["unit"], 11)
        self.assertIn("allowedValues", policy)
        self.assertIn("newValues", policy)
        self.assertIn("displayMap", policy)

        slices = ctx["score"]["umto"]["analysis"]
        self.assertEqual(len(slices), 1)
        self.assertTrue(slices[0]["is_target"])
        self.assertEqual(slices[0]["content"]["roman_numeral"], "I")

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_cadential_64_rewrite_i64_to_v64(self, mock_reader, mock_perf):
        cumulative = {"I", "i", "V", "V7", "I64", "V64", "IV", "ii"}
        self._make_mocks(cumulative, {"I64", "V64"}, mock_reader, mock_perf)

        ctx = self._run_context(self._make_exercise_data(["I64", "V"]))

        slices = ctx["score"]["umto"]["analysis"]
        self.assertEqual(len(slices), 2)
        self.assertEqual(slices[0]["content"]["roman_numeral"], "V64")
        self.assertTrue(slices[0]["is_target"])
        self.assertEqual(slices[1]["content"]["roman_numeral"], "V")
        self.assertTrue(slices[1]["is_target"])

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_non_cadential_i64_stays_as_i64(self, mock_reader, mock_perf):
        cumulative = {"I", "i", "V", "V7", "I64", "V64", "IV", "ii"}
        self._make_mocks(cumulative, {"I64", "V64"}, mock_reader, mock_perf)

        ctx = self._run_context(self._make_exercise_data(["I64", "IV"]))

        slices = ctx["score"]["umto"]["analysis"]
        self.assertEqual(slices[0]["content"]["roman_numeral"], "I64")
        self.assertTrue(slices[0]["is_target"])
        self.assertEqual(slices[1]["content"]["roman_numeral"], "IV")

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_analysis_policy_figured_bass(self, mock_reader, mock_perf):
        """Verify that mode:figures produces a figured_bass policy family."""
        cumulative = {"", "6", "6/4"}
        mock_reader.get_cumulative_values.return_value = cumulative
        mock_reader.get_new_values.return_value = {"6/4"}
        mock_reader.get_unit_analysis.return_value = {
            "cumulative": [{"value": v, "display": v or "5/3"} for v in sorted(cumulative)],
            "new": [{"value": v, "display": v or "5/3"} for v in sorted({"6/4"})],
        }
        mock_reader.get_unit_for_tag.return_value = None
        mock_perf.objects.filter.return_value.last.return_value = None

        from apps.exercises.models import Exercise, Playlist
        from lab.views import generate_exercise_context

        ex = MagicMock(spec=Exercise)
        # raw_figured_bass populated, figured_bass (abbreviated) populated
        ex.data = self._make_exercise_data([]) # empty analysis for now
        ex.data["score"]["umto"]["analysis"] = [
            {
                "offset": 0.0,
                "content": {
                    "roman_numeral": None,
                    "raw_figured_bass": "8/5/3", # raw
                    "figured_bass": "",         # abbreviated
                },
                "is_target": False
            }
        ]
        ex.skill_tags = ["unit:12", "mode:figures"]
        ex.id = "TESTFB"
        ex.complexity = 9

        pl = MagicMock(spec=Playlist)
        pl.skill_tags = ["unit:12", "mode:figures"]
        pl.is_adaptive = False
        pl.is_dynamic = False
        pl.tags = []
        pl.feedback_mode = ""
        pl.prev_num.return_value = None
        pl.next_num.return_value = None
        pl.get_exercise_obj_by_num.return_value = None
        pl.get_exercise_url_by_num.return_value = None
        pl.exercise_list = [ex]
        pl.id = "PLFB"

        ctx = generate_exercise_context(
            exercise_num=1,
            exercise=ex,
            user=MagicMock(id=1),
            playlist=pl,
            course=None,
        )

        self.assertIn("analysisPolicy", ctx)
        policy = ctx["analysisPolicy"]
        self.assertEqual(policy["family"], "figured_bass")
        self.assertEqual(ctx["analysisType"], "figured_bass")

        slices = ctx["score"]["umto"]["analysis"]
        # abbreviated value "" is in cumulative, so it should be target
        self.assertTrue(slices[0]["is_target"])
        self.assertEqual(slices[0]["content"]["figured_bass"], "")
