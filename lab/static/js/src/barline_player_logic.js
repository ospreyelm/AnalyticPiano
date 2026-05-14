(function (root) {
  "use strict";

  function sortedNumbers(values) {
    return (values || [])
      .slice()
      .map(function (value) {
        if (typeof value === "number") {
          return Math.floor(value) === value ? value : NaN;
        }
        if (typeof value === "string" && /^-?\d+$/.test(value)) {
          return parseInt(value, 10);
        }
        return NaN;
      })
      .filter(function (value) {
        return !isNaN(value);
      })
      .sort(function (a, b) {
        return a - b;
      });
  }

  // Grade barlines where placedAt is note-index positions and correctAt is beat positions.
  // noteBeatOnsets maps note index → beat onset value.
  // A barline placed after note index N is at beat = noteBeatOnsets[N+1].
  function gradeBarlines(placedAt, correctAt, noteBeatOnsets) {
    var placed = sortedNumbers(placedAt);
    var correct = sortedNumbers(correctAt);
    var onsets = noteBeatOnsets || [];

    // Convert placed note-index positions to beat positions
    var placedBeats = placed.map(function (noteIdx) {
      return (noteIdx + 1 < onsets.length) ? onsets[noteIdx + 1] : NaN;
    }).filter(function (b) { return !isNaN(b); });
    placedBeats.sort(function (a, b) { return a - b; });

    var remainingPlaced = placedBeats.slice();
    var missing = [];
    var extra;

    correct.forEach(function (position) {
      var matchIndex = remainingPlaced.indexOf(position);
      if (matchIndex === -1) {
        missing.push(position);
      } else {
        remainingPlaced.splice(matchIndex, 1);
      }
    });
    extra = remainingPlaced;

    return {
      correct: missing.length === 0 && extra.length === 0,
      missing: missing,
      extra: extra,
    };
  }

  // Cursor ranges over note-index slots: 0 .. noteCount-2 (can't place after last note)
  function clampCursor(cursorPos, noteCount) {
    var max = Math.max(0, (parseInt(noteCount, 10) || 1) - 2);
    var cursor = parseInt(cursorPos, 10) || 0;
    return Math.min(Math.max(cursor, 0), max);
  }

  function buildResultPayload(options) {
    options = options || {};
    var config = options.config || {};
    var correct = !!options.correct;
    return {
      course_ID: config.courseId || null,
      playlist_ID: config.playlistName || null,
      exercise_num: config.exerciseNum || null,
      answers: { barlines: sortedNumbers(options.placedAt) },
      correctness: { "0": correct },
      score: {
        correct: correct ? 1 : 0,
        incorrect: correct ? 0 : 1,
        unanswered: 0,
      },
      page_num: 0,
      is_page_submit: true,
      mode: config.identMode || "submit",
      attempt_type: "practice",
    };
  }

  function uniformBeatX(startX, endX, beatCount) {
    var count = parseInt(beatCount, 10) || 0;
    var width;
    var xs = [];
    var i;

    if (count <= 0) return [];

    width = (endX - startX) / count;
    for (i = 0; i <= count; i++) {
      xs.push(Math.round(startX + width * i));
    }
    return xs;
  }

  // Returns X boundaries between notes (length = noteCount + 1).
  // noteXCenters: array of X center per note (from VexFlow getAbsoluteX).
  // fallbackStart, fallbackEnd: stave left/right edges.
  function noteBoundaries(noteXCenters, fallbackStart, fallbackEnd) {
    var centers = noteXCenters || [];
    var n = centers.length;
    var boundaries = [];
    var i;

    if (n === 0) return [];

    // Left edge: midpoint before first note
    boundaries.push(Math.round((fallbackStart + centers[0]) / 2));

    for (i = 0; i < n - 1; i++) {
      boundaries.push(Math.round((centers[i] + centers[i + 1]) / 2));
    }

    // Right edge: midpoint after last note
    boundaries.push(Math.round((centers[n - 1] + fallbackEnd) / 2));

    return boundaries;
  }

  // X positions for placed barlines (note-index based).
  // A barline placed after note index N renders at noteXCenters[N+1].
  function barlineXPositions(noteXCenters, placedAt) {
    var centers = noteXCenters || [];
    var positions = sortedNumbers(placedAt);
    var xs = [];

    positions.forEach(function (noteIdx) {
      var x = centers[noteIdx + 1];
      if (typeof x === "number" && !isNaN(x)) {
        xs.push(x);
      }
    });

    return xs;
  }

  var api = {
    gradeBarlines: gradeBarlines,
    clampCursor: clampCursor,
    buildResultPayload: buildResultPayload,
    uniformBeatX: uniformBeatX,
    noteBoundaries: noteBoundaries,
    barlineXPositions: barlineXPositions,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.barlinePlayerLogic = api;
})(typeof window !== "undefined" ? window : globalThis);
