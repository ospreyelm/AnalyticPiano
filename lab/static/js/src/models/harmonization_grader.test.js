"use strict";

var HarmonizationGrader = require("./harmonization_grader");
var GraderState = require("./grader_state");

var failed = 0;

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label);
    console.log("  got:     ", JSON.stringify(actual));
    console.log("  expected:", JSON.stringify(expected));
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

function assertField(label, actual, expected) {
  if (actual !== expected) {
    console.log("FAIL:", label, "got:", actual, "expected:", expected);
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

// Representative harmonization target — same shape used by
// harmonization_grader_logic.test.js.
var target = {
  bassMidi: 48,
  bassPc: 0,
  requiredUpperPcs: [9, 4],
  allowedPcs: [0, 9, 4],
  lockedVoices: { B: { midi: 48, pc: 0, spelling: "C" } },
  voiceCountPolicy: { expected: 4, min: 3, max: 4 }
};

// ---------------------------------------------------------------------------
// STATE is the shared grader_state.js object, not a private copy
// ---------------------------------------------------------------------------
assertField("HarmonizationGrader.STATE is the shared GraderState.STATE object",
  HarmonizationGrader.STATE, GraderState.STATE);
assertField("instance.STATE is the shared GraderState.STATE object",
  new HarmonizationGrader().STATE, GraderState.STATE);

// ---------------------------------------------------------------------------
// gradeProblem — single-problem shape, mirrors exercise_grader.js:210-215
// ---------------------------------------------------------------------------
(function () {
  var grader = new HarmonizationGrader();
  var entry = grader.gradeProblem(target, [48, 52, 57]);
  assertField("correct realization: score", entry.score, 0);
  assertField("correct realization: score matches STATE.CORRECT", entry.score, 0);
  // Latent production quirk: HarmonizationGraderLogic.harmonizationMatch()
  // has no count/notes keys, so these are undefined here too — not "fixed."
  assertField("correct realization: count is undefined (quirk preserved)", entry.count, undefined);
  assertField("correct realization: notes is undefined (quirk preserved)", entry.notes, undefined);
  assertEqual("correct realization: note map", entry.note, { 48: "correct", 52: "correct", 57: "correct" });
})();

(function () {
  var grader = new HarmonizationGrader();
  var entry = grader.gradeProblem(target, [48, 52]); // missing required pc 9 (A)
  assertField("missing required pc: score is PARTIAL(1)", entry.score, 1);
})();

(function () {
  var grader = new HarmonizationGrader();
  var entry = grader.gradeProblem(target, [50, 52, 57]); // wrong bass (no pc 0)
  assertField("wrong bass: score is INCORRECT(2)", entry.score, 2);
})();

// ---------------------------------------------------------------------------
// grade() — aggregate shape, mirrors exercise_grader.js:59-227
// ---------------------------------------------------------------------------
(function () {
  var grader = new HarmonizationGrader();
  var graded = grader.grade([], []);
  assertField("empty problems: result is PARTIAL", graded.result, GraderState.PARTIAL);
  assertField("empty problems: score is 1", graded.score, 1);
  assertField("empty problems: activeIndex is 0", graded.activeIndex, 0);
  assertEqual("empty problems: problems array is empty", graded.problems, []);
})();

(function () {
  // All three problems correct -> aggregate result CORRECT, activeIndex
  // stays at problems.length (no severity ever exceeds CORRECT's score 0).
  var grader = new HarmonizationGrader();
  var problems = [target, target, target];
  var delivered = [[48, 52, 57], [48, 52, 57], [48, 52, 57]];
  var graded = grader.grade(problems, delivered);
  assertField("all correct: result", graded.result, GraderState.CORRECT);
  assertField("all correct: score", graded.score, 0);
  assertField("all correct: activeIndex (no update)", graded.activeIndex, 3);
  assertField("all correct: problems length", graded.problems.length, 3);
})();

(function () {
  // problem0 correct, problem1 partial (missing required pc) -> worst state
  // wins: result PARTIAL, activeIndex points at the first problem that
  // established the new worst score (index 1).
  var grader = new HarmonizationGrader();
  var problems = [target, target, target];
  var delivered = [[48, 52, 57], [48, 52], [48, 52, 57]];
  var graded = grader.grade(problems, delivered);
  assertField("correct then partial: result", graded.result, GraderState.PARTIAL);
  assertField("correct then partial: score", graded.score, 1);
  assertField("correct then partial: activeIndex", graded.activeIndex, 1);
})();

(function () {
  // problem0 partial, problem1 incorrect (wrong bass), problem2 also
  // incorrect -> activeIndex stays at the FIRST occurrence of the worst
  // score (index 1); a later problem at the same severity does not move it,
  // since exercise_grader.js's tracking only updates on strictly `>`.
  var grader = new HarmonizationGrader();
  var problems = [target, target, target];
  var delivered = [[48, 52], [50, 52, 57], [50, 52, 57]];
  var graded = grader.grade(problems, delivered);
  assertField("partial then incorrect twice: result", graded.result, GraderState.INCORRECT);
  assertField("partial then incorrect twice: score", graded.score, 2);
  assertField("partial then incorrect twice: activeIndex (first incorrect)", graded.activeIndex, 1);
})();

(function () {
  // grade() preserves the count/notes-undefined quirk in the aggregate path
  // too, not just gradeProblem().
  var grader = new HarmonizationGrader();
  var graded = grader.grade([target], [[48, 52, 57]]);
  assertField("aggregate: problems[0].count is undefined (quirk preserved)", graded.problems[0].count, undefined);
  assertField("aggregate: problems[0].notes is undefined (quirk preserved)", graded.problems[0].notes, undefined);
})();

// ---------------------------------------------------------------------------
// _lastGradedProblems bookkeeping (mirrors exercise_grader.js:226)
// ---------------------------------------------------------------------------
(function () {
  var grader = new HarmonizationGrader();
  assertEqual("_lastGradedProblems starts empty", grader._lastGradedProblems, []);
  var graded = grader.grade([target], [[48, 52, 57]]);
  assertField("_lastGradedProblems set after grade()", grader._lastGradedProblems, graded.problems);
})();

console.log("");
console.log("Ran harmonization_grader tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}
