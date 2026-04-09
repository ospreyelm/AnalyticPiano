import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.dashboard.forms import DashboardCourseForm
from apps.exercises.models import Course, Playlist

User = get_user_model()


class DashboardCourseFormRecurringTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher@test.com",
            password="testpass123",
        )
        self.playlist = Playlist(
            name="Test Playlist",
            authored_by=self.teacher,
        )
        self.playlist.save()
        self.course = Course(
            title="Test Course",
            authored_by=self.teacher,
        )
        self.course.save()

    def test_clean_parses_recurrence_fields_for_playlist_assignments(self):
        through_data = {
            "order": 1,
            "publish_date": None,
            "due_date": None,
            "is_recurring": "true",
            "recurrence_unit": "week",
            "required_passes_per_period": "3",
            "recurrence_starts_on": "2026-04-08",
        }
        playlists_json = json.dumps(
            [[self.playlist.id, self.playlist.id, through_data]]
        )
        data = {
            "title": "Test Course",
            "timely_credit": "1.0",
            "tardy_credit": "0.9",
            "late_credit": "0.6",
            "tardy_threshold": "120",
            "playlists": [playlists_json],
            "visible_to": [json.dumps([])],
        }
        form = DashboardCourseForm(data=data, instance=self.course, user=self.teacher)

        self.assertTrue(form.is_valid(), form.errors)

        cleaned_playlists = form.cleaned_data["playlists"]
        self.assertEqual(len(cleaned_playlists), 1)
        _, through = cleaned_playlists[0]
        self.assertEqual(through["is_recurring"], True)
        self.assertEqual(through["recurrence_unit"], "week")
        self.assertEqual(through["required_passes_per_period"], 3)
        self.assertEqual(through["recurrence_starts_on"], datetime(2026, 4, 8))

    def test_blank_recurrence_starts_on_is_accepted(self):
        through_data = {
            "order": 1,
            "publish_date": None,
            "due_date": None,
            "is_recurring": "true",
            "recurrence_unit": "week",
            "required_passes_per_period": "2",
            "recurrence_starts_on": "",
        }
        playlists_json = json.dumps(
            [[self.playlist.id, self.playlist.id, through_data]]
        )
        data = {
            "title": "Test Course",
            "timely_credit": "1.0",
            "tardy_credit": "0.9",
            "late_credit": "0.6",
            "tardy_threshold": "120",
            "playlists": [playlists_json],
            "visible_to": [json.dumps([])],
        }
        form = DashboardCourseForm(data=data, instance=self.course, user=self.teacher)

        self.assertTrue(form.is_valid(), form.errors)

        cleaned_playlists = form.cleaned_data["playlists"]
        self.assertEqual(len(cleaned_playlists), 1)
        _, through = cleaned_playlists[0]
        self.assertIsNone(through["recurrence_starts_on"])

    def test_whitespace_only_recurrence_starts_on_is_treated_as_blank(self):
        through_data = {
            "order": 1,
            "publish_date": None,
            "due_date": None,
            "is_recurring": "true",
            "recurrence_unit": "week",
            "required_passes_per_period": "2",
            "recurrence_starts_on": "   ",
        }
        playlists_json = json.dumps(
            [[self.playlist.id, self.playlist.id, through_data]]
        )
        data = {
            "title": "Test Course",
            "timely_credit": "1.0",
            "tardy_credit": "0.9",
            "late_credit": "0.6",
            "tardy_threshold": "120",
            "playlists": [playlists_json],
            "visible_to": [json.dumps([])],
        }
        form = DashboardCourseForm(data=data, instance=self.course, user=self.teacher)
        self.assertTrue(form.is_valid(), form.errors)
        _, through = form.cleaned_data["playlists"][0]
        self.assertIsNone(through["recurrence_starts_on"])

    def test_is_recurring_true_with_surrounding_whitespace(self):
        through_data = {
            "order": 1,
            "publish_date": None,
            "due_date": None,
            "is_recurring": "  true  ",
            "recurrence_unit": "week",
            "required_passes_per_period": "2",
            "recurrence_starts_on": "",
        }
        playlists_json = json.dumps(
            [[self.playlist.id, self.playlist.id, through_data]]
        )
        data = {
            "title": "Test Course",
            "timely_credit": "1.0",
            "tardy_credit": "0.9",
            "late_credit": "0.6",
            "tardy_threshold": "120",
            "playlists": [playlists_json],
            "visible_to": [json.dumps([])],
        }
        form = DashboardCourseForm(data=data, instance=self.course, user=self.teacher)
        self.assertTrue(form.is_valid(), form.errors)
        _, through = form.cleaned_data["playlists"][0]
        self.assertTrue(through["is_recurring"])

    def test_is_recurring_false_when_absent(self):
        through_data = {
            "order": 1,
            "publish_date": None,
            "due_date": None,
            "recurrence_unit": "week",
            "required_passes_per_period": "2",
            "recurrence_starts_on": "2026-04-08",
        }
        playlists_json = json.dumps(
            [[self.playlist.id, self.playlist.id, through_data]]
        )
        data = {
            "title": "Test Course",
            "timely_credit": "1.0",
            "tardy_credit": "0.9",
            "late_credit": "0.6",
            "tardy_threshold": "120",
            "playlists": [playlists_json],
            "visible_to": [json.dumps([])],
        }
        form = DashboardCourseForm(data=data, instance=self.course, user=self.teacher)

        self.assertTrue(form.is_valid(), form.errors)

        cleaned_playlists = form.cleaned_data["playlists"]
        self.assertEqual(len(cleaned_playlists), 1)
        _, through = cleaned_playlists[0]
        self.assertEqual(through["is_recurring"], False)

    def test_required_passes_per_period_defaults_to_one_when_blank(self):
        through_data = {
            "order": 1,
            "publish_date": None,
            "due_date": None,
            "is_recurring": "true",
            "recurrence_unit": "week",
            "required_passes_per_period": "",
            "recurrence_starts_on": "2026-04-08",
        }
        playlists_json = json.dumps(
            [[self.playlist.id, self.playlist.id, through_data]]
        )
        data = {
            "title": "Test Course",
            "timely_credit": "1.0",
            "tardy_credit": "0.9",
            "late_credit": "0.6",
            "tardy_threshold": "120",
            "playlists": [playlists_json],
            "visible_to": [json.dumps([])],
        }
        form = DashboardCourseForm(data=data, instance=self.course, user=self.teacher)

        self.assertTrue(form.is_valid(), form.errors)

        cleaned_playlists = form.cleaned_data["playlists"]
        self.assertEqual(len(cleaned_playlists), 1)
        _, through = cleaned_playlists[0]
        self.assertEqual(through["required_passes_per_period"], 1)
