"""Tests for course Settings and Activity tabs."""
import json
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_course(author, title="TC", start=date(2026, 9, 1), end=date(2026, 12, 1)):
    c = Course(
        title=title, authored_by=author,
        start_date=start, end_date=end,
    )
    c.save()
    return c


class CourseDetailTabsTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.course = _make_course(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_default_tab_is_timeline(self):
        resp = self.client.get(reverse("teacher:course-detail", args=[self.course.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "timeline")

    def test_settings_tab_200(self):
        resp = self.client.get(
            reverse("teacher:course-detail", args=[self.course.id]) + "?tab=settings"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "settings")

    def test_activity_tab_200(self):
        resp = self.client.get(
            reverse("teacher:course-detail", args=[self.course.id]) + "?tab=activity"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "activity")

    def test_no_dashboard_urls_in_context(self):
        resp = self.client.get(reverse("teacher:course-detail", args=[self.course.id]))
        self.assertNotIn("dashboard_edit_url", resp.context)
        self.assertNotIn("dashboard_activity_url", resp.context)


class CourseSettingsUpdateTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.course = _make_course(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")
        self.url = reverse("teacher:course-update-settings", args=[self.course.id])

    def _post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

    def test_update_title(self):
        resp = self._post({"title": "New Title"})
        self.assertEqual(resp.status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "New Title")

    def test_update_dates(self):
        self._post({"start_date": "2026-10-01", "end_date": "2027-01-15"})
        self.course.refresh_from_db()
        self.assertEqual(self.course.start_date, date(2026, 10, 1))
        self.assertEqual(self.course.end_date, date(2027, 1, 15))

    def test_clear_dates(self):
        self._post({"start_date": None, "end_date": None})
        self.course.refresh_from_db()
        self.assertIsNone(self.course.start_date)
        self.assertIsNone(self.course.end_date)

    def test_start_after_end_rejected(self):
        resp = self._post({"start_date": "2027-01-01", "end_date": "2026-01-01"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_date_string_rejected(self):
        resp = self._post({"start_date": "not-a-date"})
        self.assertEqual(resp.status_code, 400)

    def test_other_teacher_cannot_update(self):
        other = _make_teacher(email="o@t.com")
        c = Client()
        c.login(email="o@t.com", password="x")
        resp = c.post(self.url, data=json.dumps({"title": "Stolen"}),
                      content_type="application/json")
        self.assertEqual(resp.status_code, 404)
