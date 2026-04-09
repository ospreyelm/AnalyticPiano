import math
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime


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


def _is_error_free_attempt(attempt):
    error_tally = attempt.get("error_tally")
    if error_tally is None:
        return True
    try:
        return int(error_tally) == 0
    except (TypeError, ValueError):
        return False


def _normalize_attempt_exercise_id(attempt):
    attempt_id = attempt.get("id")
    if attempt_id is None:
        return None
    return str(attempt_id)[:6]


def _build_remaining_requirements(exercise_ids):
    return set(exercise_ids)


def _parse_attempt_performed_at(value):
    if isinstance(value, datetime):
        return value
    return parse_datetime(str(value))


def count_playlist_cycles(exercise_ids, attempts, cap):
    if not exercise_ids or cap <= 0:
        return 0, None, None

    counted_passes = 0
    first_pass_at = None
    last_counted_pass_at = None
    remaining = _build_remaining_requirements(exercise_ids)

    for attempt in attempts:
        if counted_passes >= cap:
            break
        if not isinstance(attempt, dict):
            continue
        if not _is_error_free_attempt(attempt):
            continue

        completed_at = _parse_attempt_performed_at(attempt.get("performed_at"))
        if completed_at is None:
            continue

        normalized_exercise_id = _normalize_attempt_exercise_id(attempt)
        if normalized_exercise_id not in remaining:
            continue

        remaining.remove(normalized_exercise_id)

        if not remaining:
            counted_passes += 1
            if first_pass_at is None:
                first_pass_at = completed_at
            last_counted_pass_at = completed_at
            if counted_passes >= cap:
                break
            remaining = _build_remaining_requirements(exercise_ids)

    return counted_passes, first_pass_at, last_counted_pass_at


def rebuild_period_progress(assignment, performance_data, occurred_at):
    from apps.exercises.models import RecurringPlaylistPeriodProgress

    period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)
    attempts_in_period = []
    for attempt in performance_data.data:
        if not isinstance(attempt, dict):
            continue

        parsed_performed_at = _parse_attempt_performed_at(attempt.get("performed_at"))
        if parsed_performed_at is None:
            continue

        # Historical performance payloads store naive timestamp strings that are
        # intended as UTC wall-clock values (e.g. "2026-04-09T04:00:00").
        if timezone.is_naive(parsed_performed_at):
            parsed_performed_at = timezone.make_aware(parsed_performed_at, dt_timezone.utc)

        performed_at_local = _to_project_timezone(parsed_performed_at)
        if period_start <= performed_at_local < period_end:
            attempt_for_counting = dict(attempt)
            attempt_for_counting["performed_at"] = performed_at_local
            attempts_in_period.append(attempt_for_counting)

    attempts_in_period.sort(key=lambda attempt: attempt["performed_at"])

    counted_passes, first_pass_at, last_counted_pass_at = count_playlist_cycles(
        performance_data.playlist.exercise_list,
        attempts_in_period,
        cap=assignment.required_passes_per_period,
    )

    progress, _ = RecurringPlaylistPeriodProgress.objects.update_or_create(
        user=performance_data.user,
        course=assignment.course,
        playlist=assignment.playlist,
        period_start=period_start,
        defaults={
            "period_end": period_end,
            "counted_passes": counted_passes,
            "required_passes": assignment.required_passes_per_period,
            "target_met": counted_passes >= assignment.required_passes_per_period,
            "first_pass_at": first_pass_at,
            "last_counted_pass_at": last_counted_pass_at,
        },
    )
    return progress


def get_recurring_assignment_snapshot(user, assignment, occurred_at=None):
    from apps.exercises.models import RecurringPlaylistPeriodProgress

    occurred_at = occurred_at or timezone.now()
    period_start, period_end = get_assignment_period_bounds(assignment, occurred_at)

    current_progress = RecurringPlaylistPeriodProgress.objects.filter(
        user=user,
        course=assignment.course,
        playlist=assignment.playlist,
        period_start=period_start,
    ).first()

    completed_periods = RecurringPlaylistPeriodProgress.objects.filter(
        user=user,
        course=assignment.course,
        playlist=assignment.playlist,
        target_met=True,
    ).count()

    counted_passes = current_progress.counted_passes if current_progress else 0
    required_passes = assignment.required_passes_per_period
    period_label = (
        "today"
        if assignment.recurrence_unit == assignment.RECURRENCE_UNIT_DAY
        else "this week"
    )
    target_met = counted_passes >= required_passes

    return {
        "is_recurring": True,
        "counted_passes": counted_passes,
        "required_passes": required_passes,
        "progress_label": f"{counted_passes} of {required_passes} {period_label}",
        "target_met": target_met,
        "completed_periods": completed_periods,
        "next_reset_at": period_end,
    }