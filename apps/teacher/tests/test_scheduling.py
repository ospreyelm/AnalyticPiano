"""Pure-logic tests for spread_schedule — run with bare pytest (no DB):

    python3 -m pytest apps/teacher/tests/test_scheduling.py -q
"""
from datetime import date

import pytest

from apps.teacher.scheduling import Window, spread_schedule


SEMESTER_START = date(2026, 9, 1)   # Tuesday
SEMESTER_END = date(2026, 12, 15)   # 15 weeks later


def test_even_spread_five_units():
    windows = spread_schedule(SEMESTER_START, SEMESTER_END, 5)
    assert len(windows) == 5
    assert windows[0].publish_date == SEMESTER_START
    # Windows partition the semester roughly evenly (105 days / 5 = 21).
    spans = [
        (windows[i + 1].publish_date - windows[i].publish_date).days
        for i in range(4)
    ]
    assert all(19 <= s <= 23 for s in spans)


def test_due_dates_are_sundays_by_default():
    windows = spread_schedule(SEMESTER_START, SEMESTER_END, 5)
    assert all(w.due_date.weekday() == 6 for w in windows)


def test_due_dates_strictly_increasing_and_within_semester():
    windows = spread_schedule(SEMESTER_START, SEMESTER_END, 8)
    dues = [w.due_date for w in windows]
    assert dues == sorted(dues)
    assert len(set(dues)) == len(dues)
    assert all(SEMESTER_START < d <= SEMESTER_END for d in dues)


def test_final_due_no_later_than_end():
    windows = spread_schedule(SEMESTER_START, SEMESTER_END, 5)
    assert windows[-1].due_date <= SEMESTER_END


def test_single_unit():
    (w,) = spread_schedule(SEMESTER_START, SEMESTER_END, 1)
    assert w.publish_date == SEMESTER_START
    assert SEMESTER_START < w.due_date <= SEMESTER_END
    assert w.due_date.weekday() == 6


def test_publish_all_at_start():
    windows = spread_schedule(SEMESTER_START, SEMESTER_END, 4, publish_all_at_start=True)
    assert all(w.publish_date == SEMESTER_START for w in windows)
    dues = [w.due_date for w in windows]
    assert dues == sorted(dues)


def test_short_semester_windows_fall_back_to_window_end():
    # 6 days, 3 units → 2-day windows that cannot all contain a Sunday.
    start, end = date(2026, 9, 1), date(2026, 9, 7)
    windows = spread_schedule(start, end, 3)
    assert len(windows) == 3
    for w in windows:
        assert start <= w.publish_date < w.due_date <= end


def test_custom_due_weekday_friday():
    windows = spread_schedule(SEMESTER_START, SEMESTER_END, 5, due_weekday=4)
    assert all(w.due_date.weekday() == 4 for w in windows)


def test_start_not_before_end_raises():
    with pytest.raises(ValueError):
        spread_schedule(SEMESTER_END, SEMESTER_START, 3)
    with pytest.raises(ValueError):
        spread_schedule(SEMESTER_START, SEMESTER_START, 3)


def test_n_units_below_one_raises():
    with pytest.raises(ValueError):
        spread_schedule(SEMESTER_START, SEMESTER_END, 0)


def test_window_namedtuple_fields():
    (w,) = spread_schedule(SEMESTER_START, SEMESTER_END, 1)
    assert isinstance(w, Window)
    assert w._fields == ("publish_date", "due_date")
