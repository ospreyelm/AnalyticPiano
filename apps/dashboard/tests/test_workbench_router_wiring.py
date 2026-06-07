import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.exercises.models import Exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import build_chordal_umto_payload
from apps.exercises.tests.umto_test_helpers import make_umto_exercise


User = get_user_model()


class WorkbenchRouterWiringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="teacher@example.com", password="pw")
        self.client.force_login(self.user)

    def test_upload_delegates_to_router_backed_import_musicxml_command(self):
        uploaded = SimpleUploadedFile(
            "chords.musicxml",
            b"<?xml version='1.0'?><score-partwise version='3.1'></score-partwise>",
            content_type="application/vnd.recordare.musicxml+xml",
        )

        with patch("apps.dashboard.views.api_workbench.call_command") as call_command:
            response = self.client.post(
                reverse("dashboard:workbench-upload"),
                {"musicxml_file": uploaded},
            )

        self.assertEqual(response.status_code, 302)
        command_name, temp_path = call_command.call_args.args[:2]
        self.assertEqual(command_name, "import_musicxml")
        self.assertTrue(temp_path.endswith(".xml"))
        self.assertEqual(call_command.call_args.kwargs["author"], self.user.email)

    def test_workbench_template_includes_chordal_review_editor(self):
        response = self.client.get(reverse("dashboard:workbench"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "analysisReviewPanel")
        self.assertContains(response, "openAnalysisReview")
        self.assertContains(response, "api/workbench/chordal-analysis")

    def test_recent_imports_exposes_umto_score_kind(self):
        make_umto_exercise(
            self.user,
            description="Multipart upload",
            complexity=3,
            skill_tags=["import:musicxml"],
            mode=InteractionMode.PLAYBACK,
        )
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            skill_tags=["import:musicxml"],
            complexity=1,
        )
        chordal.data["score"]["umto"]["metadata"]["exercise_id"] = chordal.id
        chordal.save(update_fields=["data"])

        response = self.client.get(reverse("dashboard:api-recent-imports"))

        self.assertEqual(response.status_code, 200)
        by_description = {
            item["description"]: item
            for item in response.json()["results"]
        }
        self.assertEqual(by_description["Multipart upload"]["scoreKind"], "voices")
        self.assertEqual(by_description["Chordal upload"]["scoreKind"], "chordal")

    def test_chordal_import_rejects_unreviewed_analysis_projection(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis=[{
                "offset": 0.0,
                "content": {"roman_numeral": "I", "figured_bass": "5/3"},
                "is_target": True,
            }],
            analysis_review_status="generated",
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            skill_tags=["import:musicxml"],
            complexity=1,
        )

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({
                "source_ids": [chordal.id],
                "target_type": "roman_numeral",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("review", response.json()["error"].lower())

    def test_reviewed_chordal_roman_projection_creates_identification_clone(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis=[{
                "offset": 0.0,
                "content": {"roman_numeral": "I", "figured_bass": "5/3"},
                "is_target": True,
            }],
            analysis_review_status="reviewed",
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            skill_tags=["import:musicxml"],
            complexity=1,
        )

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({
                "source_ids": [chordal.id],
                "target_type": "roman_numeral",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        created = Exercise.objects.get(id=response.json()["created_exercises"][0])
        metadata = created.data["score"]["umto"]["metadata"]
        self.assertEqual(metadata["score_kind"], "chordal")
        self.assertEqual(metadata["mode"], "identification")
        self.assertEqual(created.data["analysisType"], "roman")
        self.assertEqual(
            created.data["score"]["umto"]["analysis"][0]["content"]["roman_numeral"],
            "I",
        )

    def test_mixed_chordal_and_voices_projection_is_rejected(self):
        voices = make_umto_exercise(
            self.user,
            description="Voices",
            complexity=3,
            mode=InteractionMode.PLAYBACK,
        )
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis_review_status="reviewed",
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            complexity=1,
        )

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({
                "source_ids": [voices.id, chordal.id],
                "target_type": "roman_numeral",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("mixed", response.json()["error"].lower())

    def test_chordal_import_allows_exact_match_projection(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            skill_tags=["import:musicxml"],
            complexity=1,
        )

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({
                "source_ids": [chordal.id],
                "target_type": "exact_match",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        created = Exercise.objects.get(id=body["created_exercises"][0])
        self.assertEqual(created.data["score"]["umto"]["metadata"]["score_kind"], "chordal")

    def test_chordal_analysis_review_fetch_returns_rows(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{
                "offset": 0.0,
                "duration": 1.0,
                "visible": [60, 64, 67],
                "spelling": ["C4", "E4", "G4"],
            }],
            analysis=[{
                "offset": 0.0,
                "content": {"roman_numeral": "I", "figured_bass": "5/3"},
                "is_target": True,
            }],
            analysis_review_status="generated",
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            complexity=1,
        )

        response = self.client.get(
            reverse("dashboard:api-chordal-analysis-review", args=[chordal.id])
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["reviewStatus"], "generated")
        self.assertEqual(body["rows"][0]["visible"], [60, 64, 67])
        self.assertEqual(body["rows"][0]["spelling"], ["C4", "E4", "G4"])
        self.assertEqual(body["rows"][0]["content"]["roman_numeral"], "I")

    def test_chordal_analysis_review_save_persists_reviewed_analysis(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis_review_status="generated",
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            complexity=1,
        )

        response = self.client.post(
            reverse("dashboard:api-chordal-analysis-review", args=[chordal.id]),
            data=json.dumps({
                "rows": [{
                    "offset": 0.0,
                    "content": {"roman_numeral": "I6", "figured_bass": "6"},
                }]
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        chordal.refresh_from_db()
        umto = chordal.data["score"]["umto"]
        self.assertEqual(umto["metadata"]["analysis_review_status"], "reviewed")
        self.assertEqual(umto["analysis"][0]["content"]["roman_numeral"], "I6")
        self.assertEqual(chordal.data["analysis"], umto["analysis"])

    def test_chordal_analysis_review_save_rejects_unknown_offsets(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
        )
        chordal = Exercise.objects.create(
            description="Chordal upload",
            data=payload,
            authored_by=self.user,
            complexity=1,
        )

        response = self.client.post(
            reverse("dashboard:api-chordal-analysis-review", args=[chordal.id]),
            data=json.dumps({
                "rows": [{
                    "offset": 1.0,
                    "content": {"roman_numeral": "V"},
                }]
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("offset", response.json()["error"])
