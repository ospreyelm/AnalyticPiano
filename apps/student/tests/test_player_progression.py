from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, IdentificationAttempt, PerformanceData, Playlist
from apps.student.player_progression import (
    get_completed_exercise_ids,
    resolve_lane_launch,
    resolve_requested_step,
)

User = get_user_model()


class PlayerProgressionResolverTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="progress@test.com", password="x")
        self.author = User.objects.create_user(email="author-progress@test.com", password="x", is_staff=True)
        self.playlist = Playlist.objects.create(
            _id=91001,
            name="Unit 1 - Identify the Notes (Treble)",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        self.ex1 = Exercise.objects.create(_id=91101, data={"chord": []}, authored_by=self.author, is_public=True)
        self.ex2 = Exercise.objects.create(_id=91102, data={"chord": []}, authored_by=self.author, is_public=True)
        self.ex3 = Exercise.objects.create(_id=91103, data={"chord": []}, authored_by=self.author, is_public=True)
        ExercisePlaylistOrdered.objects.create(_id=91201, playlist=self.playlist, exercise=self.ex1, order=1)
        ExercisePlaylistOrdered.objects.create(_id=91202, playlist=self.playlist, exercise=self.ex2, order=2)
        ExercisePlaylistOrdered.objects.create(_id=91203, playlist=self.playlist, exercise=self.ex3, order=3)

    def test_get_completed_exercise_ids_combines_performance_and_identification(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[{"id": self.ex1.id, "score_numerator": 1, "score_denominator": 1}],
        )
        IdentificationAttempt.objects.create(
            user=self.student,
            playlist=self.playlist,
            exercise=self.ex2,
            answers={},
            score={"correct": 1, "incorrect": 0, "unanswered": 0},
            is_page_submit=True,
        )

        completed = get_completed_exercise_ids(self.student, self.playlist)

        self.assertEqual(completed, {self.ex1.id, self.ex2.id})

    def test_draft_identification_attempt_does_not_complete_exercise(self):
        IdentificationAttempt.objects.create(
            user=self.student,
            playlist=self.playlist,
            exercise=self.ex1,
            answers={"0": "C", "1": "E"},
            score={"correct": 2, "incorrect": 0, "unanswered": 1},
            is_page_submit=False,
        )

        completed = get_completed_exercise_ids(self.student, self.playlist)
        state = resolve_requested_step(self.student, self.playlist, requested_num=1)

        self.assertEqual(completed, set())
        self.assertFalse(state.should_redirect)
        self.assertEqual(state.exercise_num, 1)
        self.assertEqual(state.mode, "progression")

    def test_resolve_lane_launch_returns_next_pending_step(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[{"id": self.ex1.id, "score_numerator": 1, "score_denominator": 1}],
        )

        state = resolve_lane_launch(self.student, self.playlist)

        self.assertEqual(state.exercise_num, 2)
        self.assertEqual(state.mode, "progression")

    def test_resolve_lane_launch_returns_last_completed_review_when_lane_complete(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[
                {"id": self.ex1.id, "score_numerator": 1, "score_denominator": 1},
                {"id": self.ex2.id, "score_numerator": 1, "score_denominator": 1},
                {"id": self.ex3.id, "score_numerator": 1, "score_denominator": 1},
            ],
        )

        state = resolve_lane_launch(self.student, self.playlist)

        self.assertEqual(state.exercise_num, 3)
        self.assertEqual(state.mode, "review")

    def test_resolve_requested_step_redirects_future_skip_back_to_pending(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[{"id": self.ex1.id, "score_numerator": 1, "score_denominator": 1}],
        )

        state = resolve_requested_step(self.student, self.playlist, requested_num=3)

        self.assertTrue(state.should_redirect)
        self.assertEqual(state.exercise_num, 2)
        self.assertEqual(state.mode, "progression")

    def test_resolve_requested_step_allows_completed_prior_step_as_review(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[{"id": self.ex1.id, "score_numerator": 1, "score_denominator": 1}],
        )

        state = resolve_requested_step(self.student, self.playlist, requested_num=1)

        self.assertFalse(state.should_redirect)
        self.assertEqual(state.exercise_num, 1)
        self.assertEqual(state.mode, "review")
