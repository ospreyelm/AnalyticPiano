import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.exercises.models import (
    Exercise,
    ExercisePlaylistOrdered,
    IdentificationAttempt,
    Playlist,
    StudentSkillMastery,
)


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
        self.exercise = Exercise.objects.create(
            data={"chord": []},
            description="Unit 1 identify notes",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        self.next_exercise = Exercise.objects.create(
            data={"chord": []},
            description="Unit 1 identify notes 2",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        self.playlist = Playlist.objects.create(
            name="Unit 1 - Identify the Notes (Treble)",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
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
            reverse("identification-answers"),
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
