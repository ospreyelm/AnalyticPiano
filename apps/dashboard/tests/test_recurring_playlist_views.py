import json

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
