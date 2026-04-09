from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone
from zoneinfo import ZoneInfo

from apps.exercises.models import PlaylistCourseOrdered
from apps.exercises.utils.recurrence import (
    count_playlist_cycles,
    get_assignment_period_bounds,
    rebuild_period_progress,
)


class RecurringAssignmentPeriodBoundsTests(SimpleTestCase):
    def test_daily_period_returns_calendar_day_boundaries(self):
        """Daily recurrence always returns midnight-to-midnight for the calendar day of
        occurred_at in the project timezone, regardless of the anchor time.
        """
        assignment = PlaylistCourseOrdered(
            is_recurring=True,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_DAY,
            recurrence_starts_on=datetime(2026, 4, 1, 15, 30),
        )
        occurred_at = timezone.make_aware(
            datetime(2026, 4, 3, 2, 45),
            timezone.get_current_timezone(),
        )

        period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

        self.assertEqual(period_start.tzinfo, timezone.get_current_timezone())
        self.assertEqual(period_end.tzinfo, timezone.get_current_timezone())
        self.assertEqual(
            period_start,
            timezone.make_aware(datetime(2026, 4, 3, 0, 0), timezone.get_current_timezone()),
        )
        self.assertEqual(
            period_end,
            timezone.make_aware(datetime(2026, 4, 4, 0, 0), timezone.get_current_timezone()),
        )

    def test_weekly_period_uses_recurrence_starts_on_as_anchor(self):
        """When recurrence_starts_on is set it takes precedence over publish_date."""
        anchor = datetime(2026, 4, 1, 8, 0)  # Wednesday; local wall-clock
        assignment = PlaylistCourseOrdered(
            is_recurring=True,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_WEEK,
            recurrence_starts_on=anchor,
            publish_date=datetime(2026, 1, 1, 0, 0),  # earlier date — must be ignored
        )
        occurred_at = timezone.make_aware(
            datetime(2026, 4, 12, 10, 0),  # 11 days after anchor → 2nd week
            timezone.get_current_timezone(),
        )

        period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

        self.assertEqual(
            period_start,
            timezone.make_aware(datetime(2026, 4, 8, 8, 0), timezone.get_current_timezone()),
        )
        self.assertEqual(
            period_end,
            timezone.make_aware(datetime(2026, 4, 15, 8, 0), timezone.get_current_timezone()),
        )

    def test_weekly_period_is_seven_days_from_anchor(self):
        assignment = PlaylistCourseOrdered(
            is_recurring=True,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_WEEK,
            publish_date=datetime(2026, 4, 2, 10, 15),
            recurrence_starts_on=None,
        )
        occurred_at = timezone.make_aware(
            datetime(2026, 4, 15, 9, 0),
            timezone.get_current_timezone(),
        )

        period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

        self.assertEqual(
            period_start,
            timezone.make_aware(datetime(2026, 4, 9, 10, 15), timezone.get_current_timezone()),
        )
        self.assertEqual(
            period_end,
            timezone.make_aware(datetime(2026, 4, 16, 10, 15), timezone.get_current_timezone()),
        )

    def test_weekly_no_anchor_falls_back_to_occurred_at(self):
        """When both recurrence_starts_on and publish_date are absent, occurred_at
        becomes the anchor, so the period runs from occurred_at to +7 days.
        """
        assignment = PlaylistCourseOrdered(
            is_recurring=True,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_WEEK,
            recurrence_starts_on=None,
            publish_date=None,
        )
        occurred_at = timezone.make_aware(
            datetime(2026, 4, 9, 14, 0),
            timezone.get_current_timezone(),
        )

        period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

        self.assertEqual(period_start, occurred_at)
        self.assertEqual(
            period_end,
            timezone.make_aware(datetime(2026, 4, 16, 14, 0), timezone.get_current_timezone()),
        )

    def test_publish_date_fallback_uses_local_wallclock(self):
        """publish_date used as anchor must be treated as local wall-clock, not UTC.

        The codebase convention (publish_dates_dict, due_dates_dict) is to call
        .replace(tzinfo=settings.TIME_ZONE) on stored publish_date values because
        they are authored as local times, not stored as UTC offsets.  Verify that
        an aware UTC-stamped publish_date produces a period whose anchor hour is
        the original stored hour in local time (10:15), NOT the UTC→local conversion
        result (06:15 in America/New_York which is UTC-4 in April).
        """
        ny_tz = ZoneInfo("America/New_York")
        # Simulate what Django returns from the DB with USE_TZ=True: a UTC-aware value
        # whose numeric hour matches what the author typed (local wall-clock).
        utc_aware_publish_date = datetime(2026, 4, 2, 10, 15, tzinfo=dt_timezone.utc)
        assignment = PlaylistCourseOrdered(
            is_recurring=True,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_WEEK,
            publish_date=utc_aware_publish_date,
            recurrence_starts_on=None,
        )
        occurred_at = datetime(2026, 4, 3, 12, 0, tzinfo=ny_tz)

        period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

        # Wall-clock convention: anchor = 2026-04-02 10:15 NY (not 06:15 NY)
        # A UTC→local conversion would yield 06:15; .replace() gives 10:15.
        expected_start = datetime(2026, 4, 2, 10, 15, tzinfo=ny_tz)
        expected_end = datetime(2026, 4, 9, 10, 15, tzinfo=ny_tz)
        self.assertEqual(
            period_start.astimezone(ny_tz).replace(tzinfo=None),
            expected_start.replace(tzinfo=None),
        )
        self.assertEqual(
            period_end.astimezone(ny_tz).replace(tzinfo=None),
            expected_end.replace(tzinfo=None),
        )

    def test_daily_dst_spring_forward(self):
        """Daily period boundaries must land on calendar midnight across DST spring-forward.

        America/New_York springs forward on 2026-03-08 (02:00 → 03:00).  An event on
        2026-03-09 (the day after) anchored to a pre-DST date must still begin at
        00:00 local time, not at 01:00 which fixed-timedelta stepping would produce.
        """
        ny_tz = ZoneInfo("America/New_York")
        assignment = PlaylistCourseOrdered(
            is_recurring=True,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_DAY,
            # Anchor is in EST (UTC-5); Mar 9 is now in EDT (UTC-4)
            recurrence_starts_on=datetime(2026, 3, 7, 0, 0, tzinfo=ny_tz),
        )
        occurred_at = datetime(2026, 3, 9, 10, 0, tzinfo=ny_tz)

        period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

        local_start = period_start.astimezone(ny_tz).replace(tzinfo=None)
        local_end = period_end.astimezone(ny_tz).replace(tzinfo=None)
        # Both boundaries must be at 00:00 (not 01:00) on the expected dates
        self.assertEqual(local_start, datetime(2026, 3, 9, 0, 0))
        self.assertEqual(local_end, datetime(2026, 3, 10, 0, 0))


class RecurringCycleCountingTests(SimpleTestCase):
    def test_count_playlist_cycles_uses_set_semantics_for_cycle_requirements(self):
        exercise_ids = ["EA0001", "EA0001", "EA0002"]
        attempts = [
            {
                "id": "EA0001-A",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 9, 0)),
                "error_tally": 0,
            },
            {
                "id": "EA0002-A",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 9, 1)),
                "error_tally": 0,
            },
        ]

        counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
            exercise_ids,
            attempts,
            cap=99,
        )

        self.assertEqual(counted_passes, 1)
        self.assertEqual(first_pass_at, attempts[1]["performed_at"])
        self.assertEqual(last_counted_pass_at, attempts[1]["performed_at"])

    def test_count_playlist_cycles_consumes_error_free_attempts_greedily(self):
        exercise_ids = ["EA0001", "EA0002", "EA0003"]
        attempts = [
            {
                "id": "EA0001-T1",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 0)),
                "error_tally": 0,
            },
            {
                "id": "EA0002-X",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 1)),
                "error_tally": None,
            },
            {
                "id": "EA0001-Y",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 2)),
                "error_tally": 0,
            },
            {
                "id": "EA0003-Z",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 3)),
                "error_tally": 0,
            },
            {
                "id": "EA0002-A",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 4)),
                "error_tally": 0,
            },
            {
                "id": "EA0001-B",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 5)),
                "error_tally": 2,
            },
            {
                "id": "EA0003-C",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 6)),
                "error_tally": 0,
            },
            {
                "id": "EA0001-D",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 10, 7)),
                "error_tally": 0,
            },
        ]

        counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
            exercise_ids,
            attempts,
            cap=99,
        )

        self.assertEqual(counted_passes, 2)
        self.assertEqual(first_pass_at, attempts[3]["performed_at"])
        self.assertEqual(last_counted_pass_at, attempts[7]["performed_at"])

    def test_count_playlist_cycles_caps_the_result(self):
        exercise_ids = ["EA0001", "EA0002"]
        attempts = [
            {
                "id": "EA0001-1",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 11, 0)),
                "error_tally": 0,
            },
            {
                "id": "EA0002-1",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 11, 1)),
                "error_tally": 0,
            },
            {
                "id": "EA0001-2",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 11, 2)),
                "error_tally": 0,
            },
            {
                "id": "EA0002-2",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 11, 3)),
                "error_tally": 0,
            },
            {
                "id": "EA0001-3",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 11, 4)),
                "error_tally": 0,
            },
            {
                "id": "EA0002-3",
                "performed_at": timezone.make_aware(datetime(2026, 4, 9, 11, 5)),
                "error_tally": 0,
            },
        ]

        counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
            exercise_ids,
            attempts,
            cap=2,
        )

        self.assertEqual(counted_passes, 2)
        self.assertEqual(first_pass_at, attempts[1]["performed_at"])
        self.assertEqual(last_counted_pass_at, attempts[3]["performed_at"])

    def test_count_playlist_cycles_skips_malformed_attempt_entries(self):
        valid_performed_at = timezone.make_aware(datetime(2026, 4, 9, 12, 0))
        attempts = [
            None,
            "not-a-dict",
            ["also", "not", "a", "dict"],
            {"performed_at": valid_performed_at, "error_tally": 0},
            {"id": "EA0001-A", "performed_at": valid_performed_at, "error_tally": 0},
        ]

        counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
            ["EA0001"],
            attempts,
            cap=1,
        )

        self.assertEqual(counted_passes, 1)
        self.assertEqual(first_pass_at, valid_performed_at)
        self.assertEqual(last_counted_pass_at, valid_performed_at)


class RecurringProgressRebuildTests(SimpleTestCase):
    @patch("apps.exercises.models.RecurringPlaylistPeriodProgress.objects.update_or_create")
    def test_rebuild_period_progress_treats_naive_performed_at_as_utc(self, update_or_create_mock):
        ny_tz = ZoneInfo("America/New_York")
        update_or_create_mock.return_value = (SimpleNamespace(), True)

        assignment = SimpleNamespace(
            RECURRENCE_UNIT_DAY=PlaylistCourseOrdered.RECURRENCE_UNIT_DAY,
            RECURRENCE_UNIT_WEEK=PlaylistCourseOrdered.RECURRENCE_UNIT_WEEK,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_DAY,
            recurrence_starts_on=None,
            publish_date=None,
            required_passes_per_period=1,
            course=SimpleNamespace(id=123),
            playlist=SimpleNamespace(exercise_list=["EA0001"]),
        )

        performance_data = SimpleNamespace(
            user=SimpleNamespace(id=456),
            playlist=assignment.playlist,
            data=[
                # Naive string interpreted as UTC => 2026-04-08 23:59:59 NY (outside period)
                {"id": "EA0001-OLD", "performed_at": "2026-04-09T03:59:59", "error_tally": 0},
                # Naive string interpreted as UTC => 2026-04-09 00:00:00 NY (period start)
                {"id": "EA0001-NEW", "performed_at": "2026-04-09T04:00:00", "error_tally": 0},
            ],
        )

        with timezone.override("America/New_York"):
            occurred_at = datetime(2026, 4, 9, 12, 0, tzinfo=ny_tz)
            rebuild_period_progress(assignment, performance_data, occurred_at)

        defaults = update_or_create_mock.call_args.kwargs["defaults"]
        expected_first_pass = datetime(2026, 4, 9, 0, 0, tzinfo=ny_tz)
        self.assertEqual(defaults["counted_passes"], 1)
        self.assertEqual(defaults["first_pass_at"], expected_first_pass)

    @patch("apps.exercises.models.RecurringPlaylistPeriodProgress.objects.update_or_create")
    def test_rebuild_period_progress_skips_malformed_attempt_entries(self, update_or_create_mock):
        update_or_create_mock.return_value = (SimpleNamespace(), True)

        assignment = SimpleNamespace(
            RECURRENCE_UNIT_DAY=PlaylistCourseOrdered.RECURRENCE_UNIT_DAY,
            RECURRENCE_UNIT_WEEK=PlaylistCourseOrdered.RECURRENCE_UNIT_WEEK,
            recurrence_unit=PlaylistCourseOrdered.RECURRENCE_UNIT_DAY,
            recurrence_starts_on=None,
            publish_date=None,
            required_passes_per_period=1,
            course=SimpleNamespace(id=321),
            playlist=SimpleNamespace(exercise_list=["EA0001"]),
        )

        valid_performed_at = timezone.make_aware(datetime(2026, 4, 9, 13, 0))
        performance_data = SimpleNamespace(
            user=SimpleNamespace(id=654),
            playlist=assignment.playlist,
            data=[
                None,
                "not-a-dict",
                42,
                {"id": "EA0001-A", "performed_at": "not-a-datetime", "error_tally": 0},
                {"id": "EA0001-B", "error_tally": 0},
                {"id": "EA0001-C", "performed_at": valid_performed_at, "error_tally": 0},
            ],
        )

        occurred_at = timezone.make_aware(datetime(2026, 4, 9, 14, 0))
        rebuild_period_progress(assignment, performance_data, occurred_at)

        defaults = update_or_create_mock.call_args.kwargs["defaults"]
        self.assertEqual(defaults["counted_passes"], 1)
        self.assertEqual(defaults["first_pass_at"], valid_performed_at)