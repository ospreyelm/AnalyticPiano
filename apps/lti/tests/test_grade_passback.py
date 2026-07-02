"""
apps/lti/tests/test_grade_passback.py

Grade passback (Phase 6): ensure_line_item / publish_score against a
mocked AGS endpoint -- no real Moodle needed. Reuses the exact scoring
_playlist_stats already computes for the student's own course page, so
this only tests the LTI-specific plumbing (line item find-or-create,
score push, the recipient-ambiguity guard), not scoring logic.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import (
    Course,
    Exercise,
    ExercisePlaylistOrdered,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
)
from apps.lti.models import LtiLineItem, LtiPlatform, LtiUserLink
from apps.lti.services import _ags_service_for, ensure_line_item, publish_score

User = get_user_model()

FAKE_LINEITEMS_URL = "https://moodle.example.edu/mod/lti/services.php/2/lineitems"
FAKE_CREATED_LINE_ITEM_ID = "https://moodle.example.edu/mod/lti/services.php/2/lineitems/99/lineitem"

FAKE_AGS_ENDPOINT = {
    "scope": [
        "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
        "https://purl.imsglobal.org/spec/lti-ags/scope/score",
        "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly",
    ],
    "lineitems": FAKE_LINEITEMS_URL,
}


class _FakeAgsServer:
    """Records every AGS request it receives and answers the way a real
    Moodle/Canvas would: GET the lineitems collection to search by tag,
    POST to create one if not found, POST .../scores to publish a grade."""

    def __init__(self, existing_lineitems=None):
        self.existing_lineitems = existing_lineitems or []
        self.requests = []  # list of (is_post, url, parsed_data_or_None)

    def __call__(self, service_connector, scopes, url, is_post=False, data=None, **kwargs):
        parsed = json.loads(data) if data else None
        self.requests.append((is_post, url, parsed))

        if not is_post and url == FAKE_LINEITEMS_URL:
            return {"body": self.existing_lineitems, "headers": {}, "next_page_url": None}
        if is_post and url == FAKE_LINEITEMS_URL:
            body = dict(parsed)
            body["id"] = FAKE_CREATED_LINE_ITEM_ID
            return {"body": body, "headers": {}, "next_page_url": None}
        if is_post and url.endswith("/scores"):
            return {"body": {}, "headers": {}, "next_page_url": None}
        raise AssertionError(f"Unexpected AGS request: is_post={is_post} url={url}")


class GradePassbackTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(id=40001, email="prof@test.com", password="x")
        self.student = User.objects.create_user(id=40002, email="student@test.com", password="x")

        self.platform = LtiPlatform.objects.create(
            name="Test Moodle",
            issuer="https://moodle.example.edu",
            client_id="test-client-id",
            deployment_ids=["deployment-1"],
            auth_login_url="https://moodle.example.edu/mod/lti/auth.php",
            auth_token_url="https://moodle.example.edu/mod/lti/token.php",
            jwks_url="https://moodle.example.edu/mod/lti/certs.php",
            is_active=True,
        )
        self.link = LtiUserLink.objects.create(
            user=self.student,
            platform=self.platform,
            sub="student-sub",
            ags_endpoint=FAKE_AGS_ENDPOINT,
        )

        self.course = Course(title="Theory I", authored_by=self.teacher, open=False)
        self.course.save()
        self.playlist = Playlist.objects.create(
            name="Unit 1 Playlist", authored_by=self.teacher, is_public=True,
        )
        self.pco = PlaylistCourseOrdered.objects.create(
            course=self.course, playlist=self.playlist, order=1,
        )
        self.exercise = Exercise.objects.create(
            _id=40010, data={"chord": []}, authored_by=self.teacher, is_public=True,
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist, exercise=self.exercise, order=1,
        )

    def _patch_ags(self, existing_lineitems=None):
        server = _FakeAgsServer(existing_lineitems)
        patcher = patch(
            "pylti1p3.service_connector.ServiceConnector.make_service_request",
            autospec=True,
            side_effect=server,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return server


class EnsureLineItemTest(GradePassbackTestCase):
    def test_creates_a_line_item_when_none_exists(self):
        server = self._patch_ags()
        ags_service = _ags_service_for(self.student, self.platform)

        line_item = ensure_line_item(ags_service, self.platform, self.pco)

        self.assertEqual(line_item.line_item_id, FAKE_CREATED_LINE_ITEM_ID)
        self.assertEqual(LtiLineItem.objects.filter(pco=self.pco, platform=self.platform).count(), 1)
        # one GET to search by tag, one POST to create
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.requests[1][2]["tag"], f"harmonylab-pco-{self.pco.pk}")

    def test_reuses_existing_line_item_without_any_ags_request(self):
        LtiLineItem.objects.create(pco=self.pco, platform=self.platform, line_item_id="already-known")
        server = self._patch_ags()
        ags_service = _ags_service_for(self.student, self.platform)

        line_item = ensure_line_item(ags_service, self.platform, self.pco)

        self.assertEqual(line_item.line_item_id, "already-known")
        self.assertEqual(server.requests, [])

    def test_finds_existing_platform_side_line_item_by_tag(self):
        tag = f"harmonylab-pco-{self.pco.pk}"
        server = self._patch_ags(
            existing_lineitems=[{"id": "https://moodle.example.edu/.../lineitems/7/lineitem", "tag": tag}]
        )
        ags_service = _ags_service_for(self.student, self.platform)

        line_item = ensure_line_item(ags_service, self.platform, self.pco)

        self.assertEqual(line_item.line_item_id, "https://moodle.example.edu/.../lineitems/7/lineitem")
        # only the search GET -- no create POST, since a match was found
        self.assertEqual(len(server.requests), 1)


class PublishScoreTest(GradePassbackTestCase):
    def _add_perfect_performance(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=self.course,
            data=[{"id": self.exercise.id, "score_numerator": 1, "score_denominator": 1}],
        )

    def test_publishes_score_and_reuses_line_item_next_time(self):
        self._add_perfect_performance()
        server = self._patch_ags()

        result = publish_score(self.student, self.pco)

        self.assertTrue(result)
        self.assertEqual(LtiLineItem.objects.filter(pco=self.pco, platform=self.platform).count(), 1)
        scores_requests = [r for r in server.requests if r[1].endswith("/scores")]
        self.assertEqual(len(scores_requests), 1)
        self.assertEqual(scores_requests[0][2]["scoreGiven"], 100)
        self.assertEqual(scores_requests[0][2]["scoreMaximum"], 100)

        # A second publish reuses the persisted line item -- no repeat
        # find-or-create traffic, only the new scores POST.
        result_2 = publish_score(self.student, self.pco)
        self.assertTrue(result_2)
        self.assertEqual(
            len([r for r in server.requests if r[1].endswith("/scores")]), 2
        )
        self.assertEqual(len([r for r in server.requests if r[1] == FAKE_LINEITEMS_URL]), 2)

    def test_score_payload_identifies_recipient_by_sub_not_pii(self):
        self._add_perfect_performance()
        server = self._patch_ags()

        publish_score(self.student, self.pco)

        scores_requests = [r for r in server.requests if r[1].endswith("/scores")]
        payload = scores_requests[0][2]
        self.assertEqual(payload["userId"], "student-sub")
        self.assertNotIn(self.student.email, json.dumps(payload))

    def test_no_op_when_student_has_no_captured_ags_context(self):
        self.link.ags_endpoint = None
        self.link.save()
        server = self._patch_ags()

        result = publish_score(self.student, self.pco)

        self.assertFalse(result)
        self.assertEqual(server.requests, [])

    def test_no_op_when_student_linked_to_multiple_platforms(self):
        """A misdirected grade is worse than a missing one -- publishing
        is skipped rather than guessing which institution to send it to."""
        other_platform = LtiPlatform.objects.create(
            name="Other College Canvas",
            issuer="https://canvas.example.edu",
            client_id="other-client-id",
            deployment_ids=["deployment-x"],
            auth_login_url="https://canvas.example.edu/auth",
            auth_token_url="https://canvas.example.edu/token",
            jwks_url="https://canvas.example.edu/certs",
            is_active=True,
        )
        LtiUserLink.objects.create(
            user=self.student,
            platform=other_platform,
            sub="student-sub-2",
            ags_endpoint=FAKE_AGS_ENDPOINT,
        )
        server = self._patch_ags()

        result = publish_score(self.student, self.pco)

        self.assertFalse(result)
        self.assertEqual(server.requests, [])
