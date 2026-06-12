"""DB-backed tests for apps.teacher views (Task 2).

Run with:
    DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.teacher.tests.test_views_db -v 1
"""
import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.utils import timezone

from apps.accounts.models import User, Group, ROLE_TEACHER, ROLE_STUDENT
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_teacher(**kwargs):
    defaults = dict(email="teacher@example.com", password="pass", role=ROLE_TEACHER)
    defaults.update(kwargs)
    user = User.objects.create_user(**defaults)
    return user


def _make_student(**kwargs):
    defaults = dict(email="student@example.com", password="pass", role=ROLE_STUDENT)
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def _make_superuser(**kwargs):
    defaults = dict(email="super@example.com", password="pass")
    defaults.update(kwargs)
    return User.objects.create_superuser(**defaults)


def _make_playlist(author, name="Test Playlist", skill_tags=None):
    pl = Playlist(name=name, authored_by=author, skill_tags=skill_tags or [])
    pl.save()
    return pl


def _post_create(client, payload):
    url = reverse("teacher:course-create")
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

class UrlResolutionTests(TestCase):

    def test_teacher_courses_new_resolves_to_wizard_view(self):
        from apps.teacher.views import wizard_view

        match = resolve("/teacher/courses/new/")
        self.assertEqual(match.func, wizard_view)

    def test_teacher_courses_create_resolves_to_create_course_view(self):
        from apps.teacher.views import create_course_view

        match = resolve("/teacher/courses/create/")
        self.assertEqual(match.func, create_course_view)

    def test_teacher_play_still_resolves_to_lab_play_view(self):
        """lab's teacher/play/ route must still resolve after mounting apps.teacher."""
        from lab.views import PlayView

        match = resolve("/teacher/play/")
        self.assertEqual(match.func.view_class, PlayView)


# ---------------------------------------------------------------------------
# Decorator / authentication
# ---------------------------------------------------------------------------

class TeacherRequiredTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.wizard_url = reverse("teacher:course-wizard")

    def test_anonymous_redirected(self):
        resp = self.client.get(self.wizard_url)
        self.assertEqual(resp.status_code, 302)

    def test_student_redirected(self):
        student = _make_student()
        self.client.force_login(student)
        resp = self.client.get(self.wizard_url)
        self.assertEqual(resp.status_code, 302)

    def test_teacher_allowed(self):
        teacher = _make_teacher()
        self.client.force_login(teacher)
        # The template doesn't exist yet (Task 3), so we just check not 302/403.
        resp = self.client.get(self.wizard_url)
        # 200 (if template exists) or 500 (TemplateDoesNotExist) — either means auth passed
        self.assertNotEqual(resp.status_code, 302)
        self.assertNotEqual(resp.status_code, 403)

    def test_superuser_allowed(self):
        sup = _make_superuser()
        self.client.force_login(sup)
        resp = self.client.get(self.wizard_url)
        self.assertNotEqual(resp.status_code, 302)
        self.assertNotEqual(resp.status_code, 403)


class CourseWizardRenderTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.factory = _make_teacher(email=settings.FACTORY_USER_EMAIL)
        self.client.force_login(self.teacher)

    def test_units_json_is_embedded_as_valid_javascript(self):
        _make_playlist(
            self.factory,
            name="Unit 9 — Tonic & Dominant",
            skill_tags=["unit:9", "mode:roman"],
        )

        resp = self.client.get(reverse("teacher:course-wizard"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        self.assertIn("window.__WIZARD_DATA__", html)
        self.assertIn('unitsJson: [{"branch"', html)
        self.assertNotIn("unitsJson: [{&quot;", html)

    def test_create_success_redirects_to_teacher_course_detail(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "teacher"
            / "course_wizard.js"
        ).read_text()

        self.assertIn("'/teacher/courses/' + courseId + '/'", script)
        self.assertNotIn("'/dashboard/courses/' + courseId + '/'", script)


# ---------------------------------------------------------------------------
# create_course happy path
# ---------------------------------------------------------------------------

class CreateCourseHappyPathTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.client.force_login(self.teacher)
        self.playlist = _make_playlist(self.teacher, "Unit 9 Roman")

    def test_creates_course_row(self):
        payload = {
            "title": "Fall 2026",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 9,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("courseId", data)
        course = Course.objects.get(id=data["courseId"])
        self.assertEqual(course.title, "Fall 2026")
        self.assertFalse(course.open)
        self.assertEqual(course.authored_by, self.teacher)

    def test_course_has_start_end_dates(self):
        import datetime

        payload = {
            "title": "Dated Course",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 1,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 201)
        course = Course.objects.get(id=resp.json()["courseId"])
        self.assertEqual(course.start_date, datetime.date(2026, 9, 1))
        self.assertEqual(course.end_date, datetime.date(2026, 12, 15))

    def test_pco_created_with_correct_order_and_timezone_aware_datetimes(self):
        import datetime

        pl2 = _make_playlist(self.teacher, "Unit 9 Figures")
        payload = {
            "title": "PCO Test",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 9,
                    "playlistIds": [self.playlist.id, pl2.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 201)
        course = Course.objects.get(id=resp.json()["courseId"])
        pcos = list(
            PlaylistCourseOrdered.objects.filter(course=course).order_by("order")
        )
        self.assertEqual(len(pcos), 2)
        self.assertEqual(pcos[0].order, 1)
        self.assertEqual(pcos[1].order, 2)
        # datetimes must be timezone-aware
        self.assertIsNotNone(pcos[0].publish_date.tzinfo)
        self.assertIsNotNone(pcos[0].due_date.tzinfo)
        # publish = 00:00 local; due = 23:59 local — check in local tz
        tz = timezone.get_current_timezone()
        local_publish = pcos[0].publish_date.astimezone(tz)
        local_due = pcos[0].due_date.astimezone(tz)
        self.assertEqual(local_publish.time(), datetime.time(0, 0, 0))
        self.assertEqual(local_due.time(), datetime.time(23, 59, 0))

    def test_group_created_and_linked_when_group_name_given(self):
        payload = {
            "title": "Grouped Course",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": "Section A",
            "units": [
                {
                    "unit": 1,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 201)
        course = Course.objects.get(id=resp.json()["courseId"])
        groups = list(course.visible_to.all())
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].name, "Section A")
        self.assertEqual(groups[0].manager, self.teacher)
        # join_code auto-generated
        self.assertIsNotNone(groups[0].join_code)

    def test_no_group_created_when_group_name_null(self):
        payload = {
            "title": "No Group",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 1,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 201)
        course = Course.objects.get(id=resp.json()["courseId"])
        self.assertEqual(course.visible_to.count(), 0)

    def test_multiple_units_sequential_order(self):
        pl2 = _make_playlist(self.teacher, "Unit 10 Roman")
        payload = {
            "title": "Multi-unit",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 9,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                },
                {
                    "unit": 10,
                    "playlistIds": [pl2.id],
                    "publish": "2026-10-06",
                    "due": "2026-11-10",
                },
            ],
        }
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 201)
        course = Course.objects.get(id=resp.json()["courseId"])
        orders = list(
            PlaylistCourseOrdered.objects.filter(course=course)
            .order_by("order")
            .values_list("order", flat=True)
        )
        self.assertEqual(orders, [1, 2])


# ---------------------------------------------------------------------------
# Validation errors → 400
# ---------------------------------------------------------------------------

class CreateCourseValidationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.client.force_login(self.teacher)
        self.playlist = _make_playlist(self.teacher)

    def _base_payload(self):
        return {
            "title": "Valid Title",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 1,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }

    def test_missing_title_400(self):
        payload = self._base_payload()
        payload["title"] = ""
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_title_too_long_400(self):
        payload = self._base_payload()
        payload["title"] = "x" * 65
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)

    def test_bad_start_date_400(self):
        payload = self._base_payload()
        payload["start"] = "not-a-date"
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)

    def test_start_equals_end_400(self):
        payload = self._base_payload()
        payload["start"] = "2026-09-01"
        payload["end"] = "2026-09-01"
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)

    def test_start_after_end_400(self):
        payload = self._base_payload()
        payload["start"] = "2026-12-15"
        payload["end"] = "2026-09-01"
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)

    def test_empty_units_400(self):
        payload = self._base_payload()
        payload["units"] = []
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)

    def test_missing_units_400(self):
        payload = self._base_payload()
        del payload["units"]
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)

    def test_bad_playlist_id_400(self):
        payload = self._base_payload()
        payload["units"][0]["playlistIds"] = ["PA00NONEXISTENT"]
        resp = _post_create(self.client, payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())


# ---------------------------------------------------------------------------
# Non-teacher blocked on create endpoint
# ---------------------------------------------------------------------------

class CreateCoursePermissionTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.playlist = _make_playlist(self.teacher)

    def _payload(self):
        return {
            "title": "Should Fail",
            "start": "2026-09-01",
            "end": "2026-12-15",
            "groupName": None,
            "units": [
                {
                    "unit": 1,
                    "playlistIds": [self.playlist.id],
                    "publish": "2026-09-01",
                    "due": "2026-10-05",
                }
            ],
        }

    def test_anonymous_blocked(self):
        resp = _post_create(self.client, self._payload())
        self.assertEqual(resp.status_code, 302)

    def test_student_blocked(self):
        student = _make_student()
        self.client.force_login(student)
        resp = _post_create(self.client, self._payload())
        self.assertEqual(resp.status_code, 302)
