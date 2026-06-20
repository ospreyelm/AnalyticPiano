/* apps/teacher/static/teacher/modules/scheduler.js */
'use strict';

/** Parse 'YYYY-MM-DD' → Date (local noon to avoid DST issues). */
export function parseDate(str) {
  var parts = str.split('-');
  return new Date(+parts[0], +parts[1] - 1, +parts[2], 12, 0, 0);
}

/** Format Date → 'YYYY-MM-DD'. */
export function fmtDate(d) {
  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, '0');
  var dd = String(d.getDate()).padStart(2, '0');
  return y + '-' + m + '-' + dd;
}

/** Add days to a Date (returns new Date). */
export function addDays(d, n) {
  var r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

/**
 * Spread N units evenly across [start, end].
 * Returns array of { publish: 'YYYY-MM-DD', due: 'YYYY-MM-DD' }.
 * due = last Sunday (weekday 0) on or before window end, clamped > windowStart and <= end.
 */
export function spreadSchedule(startStr, endStr, n) {
  var start = parseDate(startStr);
  var end   = parseDate(endStr);
  var totalMs = end.getTime() - start.getTime();
  var windowMs = totalMs / n;
  var result = [];

  for (var i = 0; i < n; i++) {
    var winStart = new Date(start.getTime() + i * windowMs);
    var winEnd   = new Date(start.getTime() + (i + 1) * windowMs);
    if (i === n - 1) winEnd = end; // ensure last window hits end exactly

    // publish = window start
    var publish = winStart;

    // due = last Sunday on/before winEnd, but > winStart, <= end
    var due = new Date(winEnd);
    var daysBack = due.getDay(); // 0=Sun, 1=Mon … 6=Sat
    due = addDays(due, -daysBack);

    // If due <= winStart (very short window), fall back to winEnd
    if (due.getTime() <= winStart.getTime()) due = winEnd;
    // Clamp to semester end
    if (due.getTime() > end.getTime()) due = end;

    result.push({ publish: fmtDate(publish), due: fmtDate(due) });
  }
  return result;
}
