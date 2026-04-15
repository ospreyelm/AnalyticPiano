import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.exercises.models import Exercise


class DashboardPitchDuplicationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="teacher@example.com", password="pw")
        self.client.force_login(self.user)
        self.source = Exercise(
            authored_by=self.user,
            is_public=True,
            description="Source chorale",
            data={
                "type": "chorale",
                "score": {
                    "meta": {"key": "G", "time": "4/4"},
                    "measures": [
                        {
                            "number": 1,
                            "staves": {
                                "treble": {
                                    "voices": [
                                        {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                                        {"items": [{"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                                    ]
                                },
                                "bass": {
                                    "voices": [
                                        {"items": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 3}, "duration": {"type": "q", "dots": 0}}]},
                                        {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 2}, "duration": {"type": "q", "dots": 0}}]},
                                    ]
                                },
                            },
                        }
                    ],
                },
                "staffDistribution": "chorale",
                "introText": "Play this excerpt.",
                "reviewText": "Done.",
            },
        )
        self.source.save()

    def _base_post_data(self):
        return {
            "description": self.source.description,
            "is_public": "on",
            "data": json.dumps(self.source.data),
            "type": "chorale",
            "staff_distribution": "chorale",
            "identMode": "practice",
            "analysisType": "note_name",
            "duplicate-as-pitch-identification": "1",
        }

    def test_pitch_duplication_creates_one_identification_per_voice(self):
        response = self.client.post(
            reverse("dashboard:edit-exercise", kwargs={"exercise_id": self.source.id}),
            {
                **self._base_post_data(),
                "voices": ["soprano", "alto"],
            },
        )

        self.assertEqual(response.status_code, 302)

        clones = Exercise.objects.exclude(id=self.source.id).order_by("created")
        self.assertEqual(clones.count(), 2)

        for clone in clones:
            self.assertEqual(clone.data["type"], "chorale_identification")
            self.assertEqual(clone.data["analysisType"], "note_name")
            self.assertEqual(clone.data["identMode"], "practice")

        # soprano and alto should each map to one treble voice in isolated scores.
        for clone in clones:
            score = clone.data["score"]
            staves = score["measures"][0]["staves"]
            # Both staves must exist for vexflow_adapter to work
            self.assertEqual(sorted(staves.keys()), ["bass", "treble"])
            self.assertEqual(len(staves["treble"]["voices"]), 1)
            self.assertEqual(len(staves["bass"]["voices"]), 0)

    def test_pitch_duplication_rolls_back_all_clones_on_invalid_voice(self):
        before_count = Exercise.objects.count()

        response = self.client.post(
            reverse("dashboard:edit-exercise", kwargs={"exercise_id": self.source.id}),
            {
                **self._base_post_data(),
                "voices": ["soprano", "mezzo"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Exercise.objects.count(), before_count)
