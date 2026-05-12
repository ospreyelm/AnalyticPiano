"use strict";

var fs = require("fs");
var vm = require("vm");

var logic = require("./barline_player_logic");
var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    console.log("  PASS: " + label);
    pass++;
  } else {
    console.log("  FAIL: " + label);
    console.log("       got: " + JSON.stringify(actual));
    console.log("  expected: " + JSON.stringify(expected));
    fail++;
  }
}

console.log("\nbarline player logic:");

assertEqual(
  "grade reports exact match as correct",
  logic.gradeBarlines([2, 5], [2, 5]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "grade reports missing and extra positions",
  logic.gradeBarlines([2, 4], [2, 5]),
  { correct: false, missing: [5], extra: [4] }
);

assertEqual(
  "grade normalizes numeric strings and ordering",
  logic.gradeBarlines(["5", "2"], [2, 5]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "grade reports duplicate placed positions as extra",
  logic.gradeBarlines([2, 2, 5], [2, 5]),
  { correct: false, missing: [], extra: [2] }
);

assertEqual(
  "grade ignores malformed numeric strings",
  logic.gradeBarlines(["2px", "2.9", 5], [2, 5]),
  { correct: false, missing: [2], extra: [] }
);

assertEqual(
  "cursor clamps to navigable beat gaps",
  [logic.clampCursor(-1, 4), logic.clampCursor(99, 4)],
  [0, 2]
);

assertEqual(
  "result payload serializes barline answer",
  logic.buildResultPayload({
    config: { courseId: "C1", playlistName: "P1", exerciseNum: 3 },
    placedAt: [2, 5],
    correct: true,
  }),
  {
    course_ID: "C1",
    playlist_ID: "P1",
    exercise_num: 3,
    answers: { barlines: [2, 5] },
    correctness: { "0": true },
    score: { correct: 1, incorrect: 0, unanswered: 0 },
    page_num: 0,
    is_page_submit: false,
    mode: "barline_placement",
    attempt_type: "practice",
  }
);

assertEqual(
  "result payload tolerates missing options and preserves expected keys",
  logic.buildResultPayload(),
  {
    course_ID: null,
    playlist_ID: null,
    exercise_num: null,
    answers: { barlines: [] },
    correctness: { "0": false },
    score: { correct: 0, incorrect: 1, unanswered: 0 },
    page_num: 0,
    is_page_submit: false,
    mode: "barline_placement",
    attempt_type: "practice",
  }
);

assertEqual(
  "uniform fallback creates one x value per beat boundary",
  logic.uniformBeatX(100, 500, 4),
  [100, 200, 300, 400, 500]
);

var browserLikeGlobal = {};
browserLikeGlobal.globalThis = browserLikeGlobal;
vm.runInNewContext(
  fs.readFileSync(require.resolve("./barline_player_logic"), "utf8"),
  browserLikeGlobal
);

assertEqual(
  "module attaches to globalThis for browser script loading",
  !!browserLikeGlobal.barlinePlayerLogic &&
    browserLikeGlobal.barlinePlayerLogic.clampCursor(99, 4),
  2
);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
