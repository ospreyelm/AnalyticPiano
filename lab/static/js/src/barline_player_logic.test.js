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

// gradeBarlines: both placedAt and correctAt are note-index positions — direct comparison.
assertEqual(
  "grade exact match correct",
  logic.gradeBarlines([2], [2]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "grade works with dotted notes (index 3 in q q q q. 8 q. 8 q)",
  logic.gradeBarlines([3], [3]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "grade reports missing and extra positions",
  logic.gradeBarlines([0], [2]),
  { correct: false, missing: [2], extra: [0] }
);

assertEqual(
  "grade normalizes numeric strings",
  logic.gradeBarlines(["2"], [2]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "grade ignores malformed numeric strings",
  logic.gradeBarlines(["2px", "2.9"], [2]),
  { correct: false, missing: [2], extra: [] }
);

assertEqual(
  "grade multiple barlines",
  logic.gradeBarlines([2, 5], [2, 5]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "cursor clamps to navigable note gaps",
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
    is_page_submit: true,
    mode: "submit",
    attempt_type: "practice",
  }
);

assertEqual(
  "result payload uses configured feedback mode",
  logic.buildResultPayload({
    config: { identMode: "practice" },
    placedAt: [],
    correct: false,
  }).mode,
  "practice"
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
    is_page_submit: true,
    mode: "submit",
    attempt_type: "practice",
  }
);

assertEqual(
  "uniform fallback creates one x value per beat boundary",
  logic.uniformBeatX(100, 500, 4),
  [100, 200, 300, 400, 500]
);

// noteBoundaries: midpoints between adjacent note X centers
assertEqual(
  "note boundaries use midpoints between adjacent note centers",
  logic.noteBoundaries([120, 220, 320, 420], 80, 480),
  [100, 170, 270, 370, 450]
);

assertEqual(
  "note boundaries with single note",
  logic.noteBoundaries([200], 80, 480),
  [140, 340]
);

// barlineXPositions: note-index based, renders at midpoint between notes N and N+1 plus 4px offset
assertEqual(
  "barline x positions use midpoint between note centers plus 4px offset",
  logic.barlineXPositions([100, 200, 300, 400], [1]),
  [254]
);

assertEqual(
  "barline x positions ignore out-of-range indices",
  logic.barlineXPositions([100, 200, 300], [0, 2, 7]),
  [154]
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
