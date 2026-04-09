import json
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.forms import DashboardCourseForm
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered, RecurringPlaylistPeriodProgress
from apps.accounts.models import Group

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


class RecurringPlaylistDashboardViewTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.student = User.objects.create_user(
            "student@example.com", "secret", first_name="Student", last_name="One"
        )
        self.teacher.content_permits = [self.student.id]
        self.teacher.save()
        self.group = Group.objects.create(name="Section A", manager=self.teacher)
        self.group.members.add(self.student)
        self.playlist = Playlist(name="Recurring Drill", authored_by=self.teacher)
        self.playlist.save()
        self.course = Course(title="Theory I", authored_by=self.teacher)
        self.course.save()
        self.course.visible_to.add(self.group)
        self.assignment = PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=True,
            recurrence_unit="week",
            required_passes_per_period=3,
            recurrence_starts_on=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
        )
        period_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        RecurringPlaylistPeriodProgress.objects.create(
            user=self.student,
            course=self.course,
            playlist=self.playlist,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            counted_passes=2,
            required_passes=3,
            target_met=False,
        )
        RecurringPlaylistPeriodProgress.objects.create(
            user=self.student,
            course=self.course,
            playlist=self.playlist,
            period_start=period_start - timedelta(days=7),
            period_end=period_start,
            counted_passes=3,
            required_passes=3,
            target_met=True,
        )

    def test_my_work_shows_current_progress_and_completed_periods(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard:my-work"))
        self.assertContains(response, "2 of 3 this week")
        self.assertContains(response, "1 periods completed")

    def test_course_activity_csv_includes_recurring_status_text(self):
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("dashboard:course-activity", args=[self.course.id]) + "?format=csv"
        )
        self.assertContains(response, "2 of 3 this week")
        self.assertContains(response, "1 periods met")


class LegacyPlaylistRegressionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher@example.com", "secret")
        self.student = User.objects.create_user(
            "student@example.com", "secret", first_name="Student", last_name="One"
        )
        self.teacher.content_permits = [self.student.id]
        self.teacher.save()
        self.group = Group.objects.create(name="Section A", manager=self.teacher)
        self.group.members.add(self.student)
        self.playlist = Playlist(name="One-Time Drill", authored_by=self.teacher)
        self.playlist.save()
        self.course = Course(title="Theory I", authored_by=self.teacher)
        self.course.save()
        self.course.visible_to.add(self.group)
        PlaylistCourseOrdered.objects.create(
            playlist=self.playlist,
            course=self.course,
            order=1,
            is_recurring=False,
        )
        self.course.performance_dict = {
            str(self.student): {
                self.playlist.id: "P",
                "time_elapsed": 10,
                "reset": True,
            },
            str(self.teacher): {},
        }
        self.course.save()

    def test_non_recurring_my_work_still_shows_no_periods_label(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard:my-work"))
        self.assertNotContains(response, "periods completed")

    def test_non_recurring_rows_still_use_mark_codes_in_gradebook(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("dashboard:course-activity", args=[self.course.id]))
        self.assertContains(response, 'title="On time"')
