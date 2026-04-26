import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.exercises.models import (
    ExercisePlaylistOrdered,
    IdentificationAttempt,
    Playlist,
    StudentSkillMastery,
)
from apps.exercises.tests.umto_test_helpers import make_umto_exercise
from apps.exercises.umto import InteractionMode


User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class IdentificationSubmissionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email="student-ident@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            email="author-ident@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.exercise = make_umto_exercise(
            self.author,
            description="Unit 1 identify notes",
            skill_tags=["unit:1", "Note_Names"],
            mode=InteractionMode.IDENTIFICATION,
        )
        self.next_exercise = make_umto_exercise(
            self.author,
            description="Unit 1 identify notes 2",
            skill_tags=["unit:1", "Note_Names"],
            mode=InteractionMode.IDENTIFICATION,
        )
        self.playlist = Playlist(
            name="Unit 1 - Identify the Notes (Treble)",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        self.playlist.save()
        ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=self.exercise,
            order=1,
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=self.next_exercise,
            order=2,
        )
        self.client.force_login(self.student)

    def test_identification_submission_returns_completion_payload(self):
        response = self.client.post(
            reverse("lab:identification-answers"),
            {
                "data": json.dumps(
                    {
                        "course_ID": None,
                        "playlist_ID": self.playlist.id,
                        "exercise_num": 1,
                        "answers": {"0": "C"},
                        "correctness": {"0": True},
                        "score": {"correct": 1, "incorrect": 0, "unanswered": 0},
                        "correct_answers": {"0": "C"},
                        "page_num": 0,
                        "is_page_submit": True,
                        "mode": "submit",
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["score_numerator"], 1)
        self.assertEqual(data["score_denominator"], 1)
        self.assertEqual(data["exercise_num"], 1)
        self.assertEqual(data["total_exercises"], 2)
        self.assertEqual(
            data["next_exercise_url"],
            f"/s/units/1/play/?playlist={self.playlist.id}&exercise_num=2",
        )
        self.assertIn("Note_Names", data["mastery_changes"])
        self.assertEqual(
            data["mastery_changes"]["Note_Names"],
            {"old": "not_started", "new": "attempted"},
        )
        self.assertTrue(any(seg["tag"] == "Note_Names" for seg in data["unit_bar_segments"]))

        attempt = IdentificationAttempt.objects.get(user=self.student, exercise=self.exercise)
        self.assertEqual(attempt.score, {"correct": 1, "incorrect": 0, "unanswered": 0})
        mastery = StudentSkillMastery.objects.get(user=self.student, skill_tag="Note_Names")
        self.assertEqual(mastery.level, StudentSkillMastery.LEVEL_ATTEMPTED)

    def test_partial_identification_autosave_does_not_record_mastery(self):
        response = self.client.post(
            reverse("lab:identification-answers"),
            {
                "data": json.dumps(
                    {
                        "course_ID": None,
                        "playlist_ID": self.playlist.id,
                        "exercise_num": 1,
                        "answers": {"0": "D"},
                        "correctness": {"0": False},
                        "score": {"correct": 0, "incorrect": 1, "unanswered": 2},
                        "correct_answers": {"0": "C", "1": "E", "2": "G"},
                        "page_num": 0,
                        "is_page_submit": False,
                        "mode": "submit",
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "saved")
        attempt = IdentificationAttempt.objects.get(user=self.student, exercise=self.exercise)
        self.assertEqual(attempt.answers, {"0": "D"})
        self.assertFalse(attempt.is_page_submit)
        self.assertFalse(
            StudentSkillMastery.objects.filter(
                user=self.student,
                skill_tag="Note_Names",
            ).exists()
        )

    def test_partial_identification_autosave_allows_missing_course_id(self):
        response = self.client.post(
            reverse("lab:identification-answers"),
            {
                "data": json.dumps(
                    {
                        "playlist_ID": self.playlist.id,
                        "exercise_num": 1,
                        "answers": {"0": "C"},
                        "correctness": {"0": True},
                        "score": {"correct": 1, "incorrect": 0, "unanswered": 2},
                        "correct_answers": {"0": "C", "1": "E", "2": "G"},
                        "page_num": 0,
                        "is_page_submit": False,
                        "mode": "submit",
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "saved")
        attempt = IdentificationAttempt.objects.get(user=self.student, exercise=self.exercise)
        self.assertIsNone(attempt.course)

    def test_identification_answers_get_returns_correct_answers_for_review_restore(self):
        IdentificationAttempt.objects.create(
            user=self.student,
            exercise=self.exercise,
            playlist=self.playlist,
            answers={"0": "C"},
            correctness={"0": True},
            score={"correct": 1, "incorrect": 0, "unanswered": 0},
            correct_answers={"0": "C"},
            page_num=0,
            is_page_submit=True,
            mode="submit",
        )

        response = self.client.get(
            reverse("lab:identification-answers"),
            {"exercise_id": self.exercise.id},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answers"], {"0": "C"})
        self.assertEqual(data["correct_answers"], {"0": "C"})
        self.assertTrue(data["is_page_submit"])

    def test_identification_answers_get_marks_partial_autosave_as_not_submitted(self):
        IdentificationAttempt.objects.create(
            user=self.student,
            exercise=self.exercise,
            playlist=self.playlist,
            answers={"0": "C", "1": "E"},
            correctness={"0": True, "1": True},
            score={"correct": 2, "incorrect": 0, "unanswered": 1},
            correct_answers={"0": "C", "1": "E", "2": "G"},
            page_num=0,
            is_page_submit=False,
            mode="submit",
        )

        response = self.client.get(
            reverse("lab:identification-answers"),
            {"exercise_id": self.exercise.id},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answers"], {"0": "C", "1": "E"})
        self.assertEqual(data["correct_answers"], {"0": "C", "1": "E", "2": "G"})
        self.assertFalse(data["is_page_submit"])
