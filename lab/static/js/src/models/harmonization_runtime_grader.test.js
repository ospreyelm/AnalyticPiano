"use strict";

/**
 * Characterization tests for `harmonization_runtime_grader.js`
 * (`computeHarmonizationGraded`), the live runtime harmonization grading path
 * mechanically extracted from `ExerciseContext.computeHarmonizationGraded`
 * (PR A).
 *
 * These lock the EXACT current behavior of the inline method before the
 * delegation wiring in slice 3, so a behavior change there is caught. The
 * grading theory itself (`HarmonizationGraderLogic.harmonizationMatch`) is
 * exercised only indirectly through these cases; it has its own test file.
 *
 * The `ctx` is a minimal stub exposing only the fields the extracted function
 * touches — no jquery/app imports, runnable under plain `node`.
 */

var { requireDefault } = require("../../test/require_esm");
var runtime = requireDefault(require("./harmonization_runtime_grader"));
var computeHarmonizationGraded = runtime.computeHarmonizationGraded;
var STATE = runtime.STATE;

var GraderState = requireDefault(require("./grader_state"));

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

function assertTrue(label, actual) {
  if (actual !== true) {
    console.log("FAIL:", label, "— expected true, got", JSON.stringify(actual));
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

// Build a target that yields the named harmonizationMatch state for a given
// activeMidi. These mirror the harmonizationMatch contract, not re-derive it.
function targetCorrect() {
  // C major triad in root position, bass locked to pc 0, 3 voices required.
  return {
    allowedPcs: [0, 4, 7],
    requiredUpperPcs: [4, 7],
    lockedVoices: { B: { pc: 0 } },
    voiceCountPolicy: { min: 3, max: 4 },
  };
}

function targetPartial() {
  // Missing required upper pc 11 (soft) — no hard reason.
  return {
    allowedPcs: [0, 4, 7],
    requiredUpperPcs: [4, 7, 11],
    voiceCountPolicy: { min: 3, max: 4 },
  };
}

function targetIncorrect() {
  // Allowed pcs exclude 8; playing pc 8 → illegal_pc (hard).
  return {
    allowedPcs: [0, 4, 7],
    requiredUpperPcs: [4, 7],
    voiceCountPolicy: { min: 3, max: 4 },
  };
}

function targetWrongBass(offset) {
  // Bass locked to pc 2; playing pcs 0/4/7 → wrong_bass (hard).
  var t = {
    allowedPcs: [0, 4, 7],
    requiredUpperPcs: [4, 7],
    lockedVoices: { B: { pc: 2 } },
    voiceCountPolicy: { min: 3, max: 4 },
  };
  if (offset != null) t.offset = offset;
  return t;
}

function makeCtx(targets, opts) {
  opts = opts || {};
  var feedbackCalls = [];
  var ctx = {
    definition: targets
      ? { getHarmonizationTargets: function () { return targets; } }
      : {}, // no getHarmonizationTargets → defaults to []
    _harmonizationPointer: opts.pointer != null ? opts.pointer : 0,
    acceptedHarmonizationSonorities: opts.accepted || [],
    _harmonizationRejected: opts.rejected !== undefined ? opts.rejected : null,
    _emitHarmonizationIncorrectFeedback: function (matchResult) {
      feedbackCalls.push(matchResult);
    },
  };
  ctx._feedbackCalls = feedbackCalls;
  return ctx;
}

// ---------------------------------------------------------------------------
// 1. Empty / null activeMidi → clean PARTIAL, no state mutation, no feedback.
// ---------------------------------------------------------------------------

(function () {
  var ctx = makeCtx([targetCorrect()], { rejected: "preexisting" });
  var r = computeHarmonizationGraded(ctx, []);
  assertEqual("empty activeMidi -> result PARTIAL", r.result, "partial");
  assertEqual("empty activeMidi -> score 1", r.score, 1);
  assertEqual("empty activeMidi -> activeIndex = ptr", r.activeIndex, 0);
  assertEqual("empty activeMidi -> problems []", r.problems, []);
  assertEqual("empty activeMidi -> pointer unchanged", ctx._harmonizationPointer, 0);
  assertEqual("empty activeMidi -> no accepted push", ctx.acceptedHarmonizationSonorities.length, 0);
  assertEqual("empty activeMidi -> rejected unchanged", ctx._harmonizationRejected, "preexisting");
  assertEqual("empty activeMidi -> no feedback", ctx._feedbackCalls.length, 0);
})();

(function () {
  var ctx = makeCtx([targetCorrect()]);
  var r = computeHarmonizationGraded(ctx, null);
  assertEqual("null activeMidi -> result PARTIAL", r.result, "partial");
  var r2 = computeHarmonizationGraded(ctx, undefined);
  assertEqual("undefined activeMidi -> result PARTIAL", r2.result, "partial");
})();

// ---------------------------------------------------------------------------
// 2. Correct intermediate target → PARTIAL (not done), pointer advances.
// ---------------------------------------------------------------------------

(function () {
  var targets = [targetCorrect(), targetCorrect()];
  var ctx = makeCtx(targets, { pointer: 0, rejected: "stale" });
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]); // C4 E4 G4 — matches targetCorrect
  assertEqual("correct intermediate -> result PARTIAL (not allDone)", r.result, "partial");
  assertEqual("correct intermediate -> score 1", r.score, 1);
  assertEqual("correct intermediate -> activeIndex 1", r.activeIndex, 1);
  assertEqual("correct intermediate -> pointer advanced to 1", ctx._harmonizationPointer, 1);
  assertEqual("correct intermediate -> rejected cleared", ctx._harmonizationRejected, null);
  assertEqual("correct intermediate -> accepted pushed", ctx.acceptedHarmonizationSonorities.length, 1);
  assertEqual("correct intermediate -> accepted targetIndex 0", ctx.acceptedHarmonizationSonorities[0].targetIndex, 0);
  assertTrue("correct intermediate -> accepted.midi is a copy", JSON.stringify(ctx.acceptedHarmonizationSonorities[0].midi) === "[60,64,67]");
  assertTrue("correct intermediate -> accepted.ts is a number", typeof ctx.acceptedHarmonizationSonorities[0].ts === "number");
  assertEqual("correct intermediate -> no feedback", ctx._feedbackCalls.length, 0);
  assertEqual("correct intermediate -> problems is 1-element array", r.problems.length, 1);
  assertEqual("correct intermediate -> problems[0].state correct", r.problems[0].state, "correct");
})();

// ---------------------------------------------------------------------------
// 3. Correct LAST target → CORRECT, score 0.
// ---------------------------------------------------------------------------

(function () {
  var targets = [targetCorrect(), targetCorrect()];
  var ctx = makeCtx(targets, { pointer: 1 });
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]);
  assertEqual("correct last -> result CORRECT", r.result, "correct");
  assertEqual("correct last -> score 0", r.score, 0);
  assertEqual("correct last -> activeIndex 2", r.activeIndex, 2);
  assertEqual("correct last -> pointer advanced to 2", ctx._harmonizationPointer, 2);
  assertEqual("correct last -> accepted pushed", ctx.acceptedHarmonizationSonorities.length, 1);
  assertEqual("correct last -> accepted targetIndex 1", ctx.acceptedHarmonizationSonorities[0].targetIndex, 1);
})();

// ---------------------------------------------------------------------------
// 4. Partial → accepted, pointer advances (partial counts as accepted).
// ---------------------------------------------------------------------------

(function () {
  var targets = [targetPartial(), targetPartial()];
  var ctx = makeCtx(targets, { pointer: 0, rejected: "stale" });
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]); // missing required pc 11
  assertEqual("partial intermediate -> result PARTIAL", r.result, "partial");
  assertEqual("partial intermediate -> score 1", r.score, 1);
  assertEqual("partial intermediate -> pointer advanced", ctx._harmonizationPointer, 1);
  assertEqual("partial intermediate -> rejected cleared", ctx._harmonizationRejected, null);
  assertEqual("partial intermediate -> accepted pushed", ctx.acceptedHarmonizationSonorities.length, 1);
  assertEqual("partial intermediate -> no feedback", ctx._feedbackCalls.length, 0);
  assertEqual("partial intermediate -> problems[0].state partial", r.problems[0].state, "partial");
})();

(function () {
  var targets = [targetPartial(), targetPartial()];
  var ctx = makeCtx(targets, { pointer: 1 });
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]); // partial on LAST target
  assertEqual("partial on last -> result CORRECT (allDone wins)", r.result, "correct");
  assertEqual("partial on last -> score 0", r.score, 0);
  assertEqual("partial on last -> pointer advanced to 2", ctx._harmonizationPointer, 2);
})();

// ---------------------------------------------------------------------------
// 5. Incorrect → no advance, rejected set, feedback emitted, INCORRECT.
// ---------------------------------------------------------------------------

(function () {
  var targets = [targetWrongBass(5.5), targetCorrect()]; // offset 5.5 qb
  var ctx = makeCtx(targets, { pointer: 0, rejected: null });
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]); // wrong bass (locked pc 2)
  assertEqual("incorrect -> result INCORRECT", r.result, "incorrect");
  assertEqual("incorrect -> score 2", r.score, 2);
  assertEqual("incorrect -> activeIndex = ptr (no advance)", r.activeIndex, 0);
  assertEqual("incorrect -> pointer unchanged", ctx._harmonizationPointer, 0);
  assertEqual("incorrect -> no accepted push", ctx.acceptedHarmonizationSonorities.length, 0);
  assertEqual("incorrect -> feedback called once", ctx._feedbackCalls.length, 1);
  assertTrue("incorrect -> feedback received the matchResult", ctx._feedbackCalls[0] === r.problems[0]);
  assertTrue("incorrect -> rejected set", ctx._harmonizationRejected !== null);
  assertEqual("incorrect -> rejected.midi copy", JSON.stringify(ctx._harmonizationRejected.midi), "[60,64,67]");
  assertEqual("incorrect -> rejected.spellings null", ctx._harmonizationRejected.spellings, null);
  assertEqual("incorrect -> rejected.measureIndex (offset 5.5 -> mIdx 1)", ctx._harmonizationRejected.measureIndex, 1);
  assertEqual("incorrect -> rejected.onset (1.5 qb * 1024 = 1536)", ctx._harmonizationRejected.onset, 1536);
  assertEqual("incorrect -> rejected.reasons", ctx._harmonizationRejected.reasons, r.problems[0].reasons);
  assertTrue("incorrect -> rejected.target is targets[0]", ctx._harmonizationRejected.target === targets[0]);
  assertEqual("incorrect -> problems[0].state incorrect", r.problems[0].state, "incorrect");
})();

(function () {
  // offset 0 → measureIndex 0, onset 0.
  var ctx = makeCtx([targetWrongBass(0)], { pointer: 0 });
  computeHarmonizationGraded(ctx, [60, 64, 67]);
  assertEqual("offset 0 -> measureIndex 0", ctx._harmonizationRejected.measureIndex, 0);
  assertEqual("offset 0 -> onset 0", ctx._harmonizationRejected.onset, 0);
})();

(function () {
  // offset 4 → measureIndex 1, onset 0.
  var ctx = makeCtx([targetWrongBass(4)], { pointer: 0 });
  computeHarmonizationGraded(ctx, [60, 64, 67]);
  assertEqual("offset 4 -> measureIndex 1", ctx._harmonizationRejected.measureIndex, 1);
  assertEqual("offset 4 -> onset 0", ctx._harmonizationRejected.onset, 0);
})();

// ---------------------------------------------------------------------------
// 6. All-done-then-incorrect edge: allDone wins → result CORRECT, but the
//    incorrect side effects (rejected set, feedback emitted) STILL fire.
//    This is the current (quirky) behavior; locked here, not "fixed".
// ---------------------------------------------------------------------------

(function () {
  var targets = [targetCorrect(), targetCorrect()];
  var ctx = makeCtx(targets, { pointer: 2 }); // already past all targets
  var r = computeHarmonizationGraded(ctx, [60, 64, 68]); // pc 8 → illegal_pc → incorrect
  assertEqual("all-done+incorrect -> result CORRECT (allDone wins)", r.result, "correct");
  assertEqual("all-done+incorrect -> score 0", r.score, 0);
  assertEqual("all-done+incorrect -> activeIndex = ptr (no advance)", r.activeIndex, 2);
  assertEqual("all-done+incorrect -> pointer unchanged", ctx._harmonizationPointer, 2);
  assertTrue("all-done+incorrect -> rejected still set (side effect fired)", ctx._harmonizationRejected !== null);
  assertEqual("all-done+incorrect -> feedback still emitted", ctx._feedbackCalls.length, 1);
  assertEqual("all-done+incorrect -> problems[0].state incorrect", r.problems[0].state, "incorrect");
})();

// ---------------------------------------------------------------------------
// 7. No getHarmonizationTargets on definition → targets defaults to [].
//    With activeMidi present and empty targets, harmonizationMatch({}, ...) →
//    illegal_pc (no allowed pcs) → incorrect; not allDone → INCORRECT.
// ---------------------------------------------------------------------------

(function () {
  var ctx = makeCtx(null, { pointer: 0 });
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]);
  assertEqual("no targets fn -> result INCORRECT", r.result, "incorrect");
  assertEqual("no targets fn -> score 2", r.score, 2);
  assertEqual("no targets fn -> pointer unchanged", ctx._harmonizationPointer, 0);
  assertTrue("no targets fn -> rejected set", ctx._harmonizationRejected !== null);
  assertEqual("no targets fn -> feedback emitted", ctx._feedbackCalls.length, 1);
})();

// ---------------------------------------------------------------------------
// 8. Result shape + STATE constants.
// ---------------------------------------------------------------------------

(function () {
  var ctx = makeCtx([targetCorrect()]);
  var r = computeHarmonizationGraded(ctx, [60, 64, 67]);
  assertTrue("result shape has exactly result/score/activeIndex/problems",
    Object.keys(r).sort().join(",") === "activeIndex,problems,result,score");
  assertTrue("STATE.CORRECT === grader_state", STATE.CORRECT === GraderState.STATE.CORRECT);
  assertTrue("STATE.PARTIAL === grader_state", STATE.PARTIAL === GraderState.STATE.PARTIAL);
  assertTrue("STATE.INCORRECT === grader_state", STATE.INCORRECT === GraderState.STATE.INCORRECT);
  assertEqual("STATE.CORRECT value", STATE.CORRECT, "correct");
  assertEqual("STATE.PARTIAL value", STATE.PARTIAL, "partial");
  assertEqual("STATE.INCORRECT value", STATE.INCORRECT, "incorrect");
})();

// ---------------------------------------------------------------------------
// 9. Input activeMidi is not mutated; stored midi is a copy.
// ---------------------------------------------------------------------------

(function () {
  var ctx = makeCtx([targetCorrect(), targetCorrect()], { pointer: 0 });
  var input = [67, 60, 64]; // unsorted
  computeHarmonizationGraded(ctx, input);
  assertEqual("input array not reordered by reference", JSON.stringify(input), "[67,60,64]");
  assertTrue("stored accepted.midi is a copy, not the input ref",
    ctx.acceptedHarmonizationSonorities[0].midi !== input);

  var ctx2 = makeCtx([targetWrongBass(0)], { pointer: 0 });
  var input2 = [60, 64, 67];
  computeHarmonizationGraded(ctx2, input2);
  assertTrue("stored rejected.midi is a copy, not the input ref",
    ctx2._harmonizationRejected.midi !== input2);
  input2.push(99);
  assertEqual("mutating input after the call does not affect rejected.midi",
    JSON.stringify(ctx2._harmonizationRejected.midi), "[60,64,67]");
})();

if (failed > 0) {
  console.log("\n" + failed + " test(s) FAILED.");
  process.exit(1);
} else {
  console.log("\nRan harmonization_runtime_grader tests; 0 failed.");
}