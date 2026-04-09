import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def _to_project_timezone(value):
    """Convert an aware or naive datetime to the project timezone via proper UTC conversion."""
    project_tz = ZoneInfo(settings.TIME_ZONE)
    if timezone.is_naive(value):
        return timezone.make_aware(value, project_tz)
    return value.astimezone(project_tz)


def _publish_date_as_local(value):
    """Interpret a publish_date value as local wall-clock time in the project timezone.

    Mirrors the convention in models.py (publish_dates_dict, due_dates_dict): stored
    values are treated as local wall-clock times in settings.TIME_ZONE, NOT converted
    from UTC.  Matches the .replace(tzinfo=ZoneInfo(settings.TIME_ZONE)) pattern used
    throughout the codebase.
    """
    project_tz = ZoneInfo(settings.TIME_ZONE)
    return value.replace(tzinfo=project_tz)


def get_assignment_period_bounds(assignment, occurred_at):
    project_tz = ZoneInfo(settings.TIME_ZONE)
    occurred_local = _to_project_timezone(occurred_at)

    if assignment.recurrence_starts_on is not None:
        anchor_local = _to_project_timezone(assignment.recurrence_starts_on)
    elif assignment.publish_date is not None:
        # publish_date follows the codebase wall-clock convention: treat the stored
        # value as a local time in settings.TIME_ZONE, never convert from UTC.
        anchor_local = _publish_date_as_local(assignment.publish_date)
    else:
        anchor_local = occurred_local

    if assignment.recurrence_unit == assignment.RECURRENCE_UNIT_DAY:
        # Compute boundaries from the calendar date of occurred_local so that period
        # starts always land at midnight in the project timezone regardless of DST
        # transitions.  Fixed-offset timedelta stepping from a localized anchor would
        # drift by one hour across a DST boundary.
        period_date = occurred_local.date()
        next_date = period_date + timedelta(days=1)
        period_start = datetime(period_date.year, period_date.month, period_date.day, tzinfo=project_tz)
        period_end = datetime(next_date.year, next_date.month, next_date.day, tzinfo=project_tz)
    elif assignment.recurrence_unit == assignment.RECURRENCE_UNIT_WEEK:
        anchor_start = anchor_local
        unit = timedelta(days=7)
        period_index = math.floor((occurred_local - anchor_start) / unit)
        period_start = anchor_start + (period_index * unit)
        period_end = period_start + unit
    else:
        raise ValueError("Unsupported recurrence unit")

    return period_start.astimezone(project_tz), period_end.astimezone(project_tz)