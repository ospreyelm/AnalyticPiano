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

  function gradeBarlines(placedAt, correctAt) {
    var placed = sortedNumbers(placedAt);
    var correct = sortedNumbers(correctAt);
    var remainingPlaced = placed.slice();
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

  function clampCursor(cursorPos, beatCount) {
    var max = Math.max(0, (parseInt(beatCount, 10) || 1) - 2);
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
      is_page_submit: false,
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

  var api = {
    gradeBarlines: gradeBarlines,
    clampCursor: clampCursor,
    buildResultPayload: buildResultPayload,
    uniformBeatX: uniformBeatX,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.barlinePlayerLogic = api;
})(typeof window !== "undefined" ? window : globalThis);
