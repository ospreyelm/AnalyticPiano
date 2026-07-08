from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
import json
import random
from pathlib import Path
from unittest.mock import patch

from apps.accounts.models import ROLE_STUDENT, ROLE_TEACHER
from apps.exercises.models import (
    Course,
    Exercise,
    ExercisePlaylistOrdered,
    IdentificationAttempt,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
    StudentSkillMastery,
)
from apps.exercises.tests.umto_test_helpers import make_umto_exercise
from apps.exercises.umto import InteractionMode


User = get_user_model()
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "exercises" / "tests" / "fixtures" / "umto"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentHomeResumeTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=37001,
            email="resume-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=37002,
            email="resume-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)

    def _make_lane_playlist(self, pk, name):
        playlist = Playlist.objects.create(
            _id=pk,
            name=name,
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        exercise = Exercise.objects.create(
            _id=pk + 100,
            description=name,
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=pk + 200,
            playlist=playlist,
            exercise=exercise,
            order=1,
        )
        return playlist, exercise

    def test_home_resume_uses_canonical_unit1_lane_order(self):
        identify_treble, identify_treble_exercise = self._make_lane_playlist(
            37100, "Unit 1 - Identify the Notes (Treble)"
        )
        identify_bass, _ = self._make_lane_playlist(
            37200, "Unit 1 - Identify the Notes (Bass)"
        )
        self._make_lane_playlist(37300, "Unit 1 - Play from Name (Treble)")
        self._make_lane_playlist(37400, "Unit 1 - Play from Name (Bass)")
        self._make_lane_playlist(37500, "Unit 1 - Play the Notes (Treble)")
        self._make_lane_playlist(37600, "Unit 1 - Play the Notes (Bass)")
        legacy_identify_treble, _ = self._make_lane_playlist(
            37700, "Unit 1 - Note Names (Treble)"
        )
        legacy_identify_bass, _ = self._make_lane_playlist(
            37800, "Unit 1 - Note Names (Bass)"
        )

        PerformanceData.objects.create(
            user=self.student,
            playlist=identify_treble,
            course=None,
            data=[{"id": identify_treble_exercise.id, "score_numerator": 1, "score_denominator": 1}],
        )

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["resume_url"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={identify_bass.id}&exercise_num=1",
        )
        self.assertNotEqual(
            response.context["resume_url"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={legacy_identify_treble.id}&exercise_num=1",
        )
        self.assertNotEqual(
            response.context["resume_url"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={legacy_identify_bass.id}&exercise_num=1",
        )
        self.assertEqual(
            response.context["units"][0]["url"],
            reverse("student:unit-progress", kwargs={"unit_n": "1"}),
        )
@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentHomeUnitDiscoveryTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=38001,
            email="unit-discovery-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=38002,
            email="unit-discovery-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)

    def _make_playlist(self, pk, name, skill_tags):
        return Playlist.objects.create(
            _id=pk,
            name=name,
            authored_by=self.author,
            is_public=True,
            skill_tags=skill_tags,
            tags=skill_tags,
        )

    def test_home_discovers_units_with_accessible_playlists(self):
        self._make_playlist(38100, "Unit 1 - Identify the Notes (Treble)", ["unit:1", "Note_Names"])
        self._make_playlist(38101, "Unit 9 - Tonic & dominant", ["unit:9", "Tonic_Triad", "Dominant_Triad"])
        self._make_playlist(38102, "Unit 11 - Pre-dominants", ["unit:11", "Predominant_Function"])
        self._make_playlist(38103, "Unit 12 - Second inversions", ["unit:12", "Second_Inversion"])

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        units = response.context["units"]
        by_num = {unit["num"]: unit for unit in units}

        from apps.student.views import unit_sort_key
        self.assertEqual([unit["num"] for unit in units], sorted(by_num.keys(), key=unit_sort_key))
        self.assertFalse(by_num["1"]["locked"])
        self.assertFalse(by_num["9"]["locked"])
        self.assertFalse(by_num["11"]["locked"])
        self.assertFalse(by_num["12"]["locked"])
        self.assertTrue(by_num["2"]["locked"])
        self.assertIsNone(by_num["2"]["url"])
        self.assertEqual(
            by_num["9"]["url"],
            reverse("student:unit-progress", kwargs={"unit_n": "9"}),
        )

    def test_home_discovers_teacher_shared_private_playlists(self):
        self.author.content_permits = [self.student.id]
        self.author.save(update_fields=["content_permits"])
        Playlist.objects.create(
            _id=38104,
            name="Unit 16 - Applied chords",
            authored_by=self.author,
            is_public=False,
            skill_tags=["unit:16", "Secondary_Dominant"],
            tags=["unit:16", "Secondary_Dominant"],
        )

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        by_num = {unit["num"]: unit for unit in response.context["units"]}
        self.assertFalse(by_num["16"]["locked"])
        self.assertEqual(
            by_num["16"]["url"],
            reverse("student:unit-progress", kwargs={"unit_n": "16"}),
        )
@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentHomeQueryBudgetTests(TransactionTestCase):
    reset_sequences = True
    # session + user + accessible playlists + batched mastery + course-unit
    # dates + enrolled-courses PCO join (two constant PCO queries)
    QUERY_BUDGET = 6

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=39001,
            email="home-budget-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=39002,
            email="home-budget-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)
        self._pk = 39100

    def _next_pk(self):
        self._pk += 1
        return self._pk

    def _taxonomy_for_units(self, count):
        units = [
            {
                "n": str(i),
                "title": f"Budget Unit {i}",
                "feat": f"Skill budget {i}",
                "tags": [f"Skill_{i}_A", f"Skill_{i}_B"],
            }
            for i in range(2, 2 + count)
        ]
        branches = [
            {
                "id": "core",
                "label": "Core",
                "tiers": [
                    {
                        "label": "Budget Tier",
                        "badge": "BT",
                        "units": units,
                    }
                ],
            }
        ]
        by_n = {unit["n"]: unit for unit in units}
        by_tag = {
            tag: unit
            for unit in units
            for tag in unit["tags"]
        }
        return branches, units, by_n, by_tag

    def _seed_units(self, count):
        for i in range(2, 2 + count):
            exercise = Exercise.objects.create(
                _id=self._next_pk(),
                description=f"Budget exercise {i}",
                data={"chord": []},
                authored_by=self.author,
                is_public=True,
                skill_tags=[f"Skill_{i}_A", f"unit:{i}"],
            )
            playlist = Playlist.objects.create(
                _id=self._next_pk(),
                name=f"Budget Unit {i}",
                authored_by=self.author,
                is_public=True,
                skill_tags=[f"Skill_{i}_A", f"unit:{i}"],
                tags=[f"Skill_{i}_A", f"unit:{i}"],
            )
            ExercisePlaylistOrdered.objects.create(
                _id=self._next_pk(),
                playlist=playlist,
                exercise=exercise,
                order=1,
            )
            PerformanceData.objects.create(
                user=self.student,
                playlist=playlist,
                data=[{"id": exercise.id, "score_numerator": 1, "score_denominator": 1}],
            )
            StudentSkillMastery.objects.create(
                user=self.student,
                skill_tag=f"Skill_{i}_A",
                level=StudentSkillMastery.LEVEL_MASTERED,
            )

    def test_home_query_count_is_constant_in_unit_count(self):
        branches, units, by_n, by_tag = self._taxonomy_for_units(6)
        self._seed_units(6)

        def get_unit(unit_n):
            return by_n.get(str(unit_n))

        def get_unit_for_tag(tag):
            return by_tag.get(tag)

        with (
            patch("apps.student.views.TaxonomyReader.get_branches", return_value=branches),
            patch("apps.student.views.TaxonomyReader.get_all_units", return_value=units),
            patch("apps.student.views.TaxonomyReader.get_unit", side_effect=get_unit),
            patch("apps.student.views.TaxonomyReader.get_unit_for_tag", side_effect=get_unit_for_tag),
            patch("apps.student.views.TaxonomyReader.get_tier_for_unit", return_value=branches[0]["tiers"][0]),
            patch("apps.student.views.TaxonomyReader.get_skill_label", side_effect=lambda tag: tag.replace("_", " ").title()),
        ):
            with self.assertNumQueries(self.QUERY_BUDGET):
                response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)

    def test_batched_home_summary_matches_unit_progress_summary(self):
        from apps.student.unit_progress import get_unit_progress_data
        from apps.student.views import _batch_home_unit_summaries, _summarize_unit_progress

        branches, units, by_n, by_tag = self._taxonomy_for_units(1)
        self._seed_units(1)

        def get_unit(unit_n):
            return by_n.get(str(unit_n))

        def get_unit_for_tag(tag):
            return by_tag.get(tag)

        with (
            patch("apps.student.views.TaxonomyReader.get_unit", side_effect=get_unit),
            patch("apps.student.views.TaxonomyReader.get_unit_for_tag", side_effect=get_unit_for_tag),
            patch("apps.student.views.TaxonomyReader.get_tier_for_unit", return_value=branches[0]["tiers"][0]),
            patch("apps.student.views.TaxonomyReader.get_skill_label", side_effect=lambda tag: tag.replace("_", " ").title()),
        ):
            expected = _summarize_unit_progress(get_unit_progress_data(self.student, "2"))
            summaries = _batch_home_unit_summaries(self.student, units, {"2"})

        self.assertEqual(summaries["2"]["percent"], expected["percent"])
        self.assertEqual(summaries["2"]["mastered_count"], expected["mastered_count"])


@override_settings(
    UNIT1_CURRICULUM_AUTHOR_EMAIL="unit1-budget-author@test.com",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
)
class StudentHomeUnit1QueryBudgetTests(TransactionTestCase):
    """Guard the Unit-1 batched query path on the home page.

    The generic ``StudentHomeQueryBudgetTests`` patches TaxonomyReader to
    units 2..7, so its ``assertNumQueries`` never reaches the
    ``if str(unit_n) == "1"`` special-case in ``_batch_home_unit_summaries``
    (home_context.py) nor the batched ``_get_unit1_resume_target``. With real
    Unit-1 lanes seeded, every home load in prod expands Unit-1 — these tests
    pin that expansion to a constant, batched budget so a per-lane N+1
    regression (the ~70-query storm fixed alongside PR #74) is caught.
    """

    reset_sequences = True
    # session + user + accessible-playlist discovery + Unit-1 summary
    # (one batched get_unit_progress_data) + resume-target lookup + the two
    # constant PCO joins. Both the fully-mastered and partially-complete
    # Unit-1 scenarios land here — resume into a player lane (Task 3 batched
    # path) adds no extra queries over the unit-page fallback.
    HOME_QUERY_BUDGET = 16
    # resolve lanes (1) + batched playlist data (3) + EPO grouping (1) +
    # two memoized challenge-mastery lookups (treble/bass).
    PROGRESS_QUERY_BUDGET = 7

    def setUp(self):
        from apps.student.unit1_curriculum import UNIT1_CANONICAL_LANES

        self.client = Client()
        self.student = User.objects.create_user(
            id=41001,
            email="unit1-budget-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=41002,
            email="unit1-budget-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)
        self._canon = UNIT1_CANONICAL_LANES
        self._pk = 41100

    def _next_pk(self):
        self._pk += 1
        return self._pk

    def _seed_unit1_lane(self, lane_key, lane, with_performance):
        exercise = Exercise.objects.create(
            _id=self._next_pk(),
            description=f"u1 {lane_key}",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1"],
        )
        playlist = Playlist.objects.create(
            _id=self._next_pk(),
            name=lane["playlist_name"],
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1"],
            tags=["unit:1"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=self._next_pk(),
            playlist=playlist,
            exercise=exercise,
            order=1,
            difficulty_tier=3,
        )
        if with_performance:
            PerformanceData.objects.create(
                user=self.student,
                playlist=playlist,
                data=[{"id": exercise.id, "score_numerator": 1, "score_denominator": 1}],
            )
        return playlist, exercise

    def _seed_all_unit1_lanes(self, mastered):
        lanes = {}
        for lane_key, lane in self._canon.items():
            lanes[lane_key] = self._seed_unit1_lane(lane_key, lane, with_performance=mastered)
        return lanes

    def test_home_unit1_query_count_is_constant(self):
        # Partially-complete Unit-1: only identify_treble is mastered, so the
        # resume target resolves INTO a Unit-1 player lane — exercising the
        # batched _get_unit1_resume_target (Task 3) alongside the batched
        # Unit-1 summary (Task 2) and lane resolution (Task 1).
        self._seed_unit1_lane("identify_treble", self._canon["identify_treble"], with_performance=True)
        for lane_key, lane in self._canon.items():
            if lane_key == "identify_treble":
                continue
            self._seed_unit1_lane(lane_key, lane, with_performance=False)

        # Warm any lazy/cached state first, then pin the steady-state budget.
        self.client.get(reverse("student:home"))
        with self.assertNumQueries(self.HOME_QUERY_BUDGET):
            response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        # Sanity: resume really did resolve into a Unit-1 player lane (the
        # Task 3 batched path), not the unit-page fallback.
        self.assertIn("/s/units/1/play/", response.context["resume_url"])

    def test_get_unit_progress_data_unit1_query_count_is_constant(self):
        # Fully-mastered Unit-1 — every lane has PerformanceData, so the
        # bar-segment / mastery compute walks all six lanes through the
        # batched path.
        self._seed_all_unit1_lanes(mastered=True)

        from apps.student.unit_progress import get_unit_progress_data

        get_unit_progress_data(self.student, "1")  # warm
        with self.assertNumQueries(self.PROGRESS_QUERY_BUDGET):
            data = get_unit_progress_data(self.student, "1")

        self.assertEqual(len(data["activity_cards"]), 3)
