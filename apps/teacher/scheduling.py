"""Semester date-spreading for the course creation wizard.

Pure stdlib — no Django imports. The wizard divides a semester into equal
windows, one per unit, publishing at each window start and making work due on
the last `due_weekday` (default Sunday) that falls inside the window.

Example::

    >>> from datetime import date
    >>> spread_schedule(date(2026, 9, 1), date(2026, 12, 15), 3)
    [Window(publish_date=datetime.date(2026, 9, 1), due_date=datetime.date(2026, 10, 4)),
     Window(publish_date=datetime.date(2026, 10, 6), due_date=datetime.date(2026, 11, 8)),
     Window(publish_date=datetime.date(2026, 11, 10), due_date=datetime.date(2026, 12, 13))]
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List, NamedTuple


class Window(NamedTuple):
    publish_date: date
    due_date: date


def _last_weekday_on_or_before(day: date, weekday: int) -> date:
    """Most recent date with .weekday() == weekday, on or before `day`."""
    return day - timedelta(days=(day.weekday() - weekday) % 7)


def spread_schedule(
    start: date,
    end: date,
    n_units: int,
    *,
    due_weekday: int = 6,
    publish_all_at_start: bool = False,
) -> List[Window]:
    """Divide [start, end] into `n_units` equal windows of publish/due dates.

    - Publish: window start (or `start` for every window when
      `publish_all_at_start`).
    - Due: last `due_weekday` (Monday=0 … Sunday=6) on or before the window
      end, but always strictly after the window start; windows too short to
      contain that weekday fall back to the window end. The final due date
      never exceeds `end`.

    Raises ValueError when `start >= end` or `n_units < 1`.
    """
    if start >= end:
        raise ValueError("start must be before end")
    if n_units < 1:
        raise ValueError("n_units must be >= 1")

    total_days = (end - start).days
    windows: List[Window] = []
    for i in range(n_units):
        win_start = start + timedelta(days=round(i * total_days / n_units))
        win_end = start + timedelta(days=round((i + 1) * total_days / n_units))
        if i == n_units - 1:
            win_end = end

        due = _last_weekday_on_or_before(win_end, due_weekday)
        if due <= win_start:
            due = win_end

        publish = start if publish_all_at_start else win_start
        windows.append(Window(publish_date=publish, due_date=due))

    return windows
