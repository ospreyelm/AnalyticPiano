"use strict";

var { requireDefault } = require("../../test/require_esm");
var HarmonizationGrader = requireDefault(require("./harmonization_grader"));
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
// gradeProblems() — aggregate shape, mirrors exercise_grader.js:59-227
// ---------------------------------------------------------------------------
(function () {
  var grader = new HarmonizationGrader();
  var graded = grader.gradeProblems([], []);
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
  var graded = grader.gradeProblems(problems, delivered);
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
  var graded = grader.gradeProblems(problems, delivered);
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
  var graded = grader.gradeProblems(problems, delivered);
  assertField("partial then incorrect twice: result", graded.result, GraderState.INCORRECT);
  assertField("partial then incorrect twice: score", graded.score, 2);
  assertField("partial then incorrect twice: activeIndex (first incorrect)", graded.activeIndex, 1);
})();

(function () {
  // grade() preserves the count/notes-undefined quirk in the aggregate path
  // too, not just gradeProblem().
  var grader = new HarmonizationGrader();
  var graded = grader.gradeProblems([target], [[48, 52, 57]]);
  assertField("aggregate: problems[0].count is undefined (quirk preserved)", graded.problems[0].count, undefined);
  assertField("aggregate: problems[0].notes is undefined (quirk preserved)", graded.problems[0].notes, undefined);
})();

// ---------------------------------------------------------------------------
// _lastGradedProblems bookkeeping (mirrors exercise_grader.js:226)
// ---------------------------------------------------------------------------
(function () {
  var grader = new HarmonizationGrader();
  assertEqual("_lastGradedProblems starts empty", grader._lastGradedProblems, []);
  var graded = grader.gradeProblems([target], [[48, 52, 57]]);
  assertField("_lastGradedProblems set after grade()", grader._lastGradedProblems, graded.problems);
})();

// ---------------------------------------------------------------------------
// grade(definition, inputChords) — production-interface adapter, mirrors
// ExerciseGrader.grade()'s definition/inputChords extraction (exercise_
// grader.js:45-47, 84-89, 130-141) for the harmonization case.
//
// exercise_grader.js cannot be require()'d under plain node (it imports
// app/-aliased modules — the same wall documented throughout this project;
// see chorale_grader.test.js). So these are NOT a live A/B run against the
// real ExerciseGrader instance; expected values are hand-traced against
// exercise_grader.js's actual source (read directly, not from memory) the
// same way every other characterization test in this project is derived.
// ---------------------------------------------------------------------------

function fakeDefinitionWithProblems(problems, resolvedOverrides) {
  return {
    getProblems: function () { return problems; },
    getResolvedMode: function () {
      var base = { isChorale: false };
      for (var k in resolvedOverrides) { base[k] = resolvedOverrides[k]; }
      return base;
    },
  };
}

// itemSpecs: array, one per problem, each either an array of MIDI notes
// (-> a chord with those notes) or null/undefined (-> no chord at that
// index, matching exercise_grader.js:134's `if (chords[i])` guard).
function fakeInputChords(itemSpecs) {
  return {
    items: function () {
      return itemSpecs.map(function (notes) {
        if (notes == null) return {};
        return { chord: { getNoteNumbers: function () { return notes.slice(); } } };
      });
    },
  };
}

(function () {
  // Single correct problem via the real production call shape.
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([target]);
  var inputChords = fakeInputChords([[48, 52, 57]]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): correct -> result", graded.result, GraderState.CORRECT);
  assertField("grade(definition,inputChords): correct -> score", graded.score, 0);
  assertField("grade(definition,inputChords): correct -> activeIndex", graded.activeIndex, 1);
})();

(function () {
  // Three problems, worst-state-wins and activeIndex tracking, exercised
  // through the full production interface (not gradeProblems() directly).
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([target, target, target]);
  var inputChords = fakeInputChords([
    [48, 52, 57],       // correct
    [48, 52],           // partial (missing required pc 9)
    [50, 52, 57],       // incorrect (wrong bass)
  ]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): mixed -> result is worst (INCORRECT)", graded.result, GraderState.INCORRECT);
  assertField("grade(definition,inputChords): mixed -> score", graded.score, 2);
  assertField("grade(definition,inputChords): mixed -> activeIndex (first incorrect)", graded.activeIndex, 2);
})();

(function () {
  // Dummy MIDI 109 removal: delivering 109 alongside a correct three-note
  // realization must grade identically to delivering the realization alone
  // -- exercise_grader.js:137-140 strips 109 before it ever reaches
  // harmonizationMatch(). Without stripping, 109's pitch class (1) is not
  // in allowedPcs ([0,9,4]) and voice count would be 4 (still within
  // min3/max4), so an unstripped 109 would flip this to "incorrect"
  // (illegal_pc) instead of "correct" -- a real behavior difference if the
  // strip were ever skipped, not a redundant assertion.
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([target]);
  var inputChords = fakeInputChords([[48, 52, 57, 109]]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): dummy MIDI 109 stripped -> still CORRECT", graded.result, GraderState.CORRECT);
  assertField("grade(definition,inputChords): dummy MIDI 109 stripped -> score 0", graded.score, 0);
})();

(function () {
  // Deduped delivered notes: a doubled note (e.g. two voices on the same
  // pitch) must not be double-counted -- exercise_grader.js:135 dedupes via
  // Set before anything else runs.
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([target]);
  var inputChords = fakeInputChords([[48, 48, 52, 57]]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): duplicate MIDI deduped -> still CORRECT", graded.result, GraderState.CORRECT);
})();

(function () {
  // No chord delivered at all for a problem (chords[i] falsy) -> treated as
  // empty delivered notes, exactly like exercise_grader.js:132-141's guard.
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([target]);
  var inputChords = fakeInputChords([null]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): no chord delivered -> INCORRECT (wrong bass, no notes)", graded.result, GraderState.INCORRECT);
})();

(function () {
  // Empty problems (definition.getProblems() returns []) -> same PARTIAL
  // early-return guard as gradeProblems([], []), reached via the
  // definition/inputChords adapter this time.
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([]);
  var inputChords = fakeInputChords([]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): empty problems -> result PARTIAL", graded.result, GraderState.PARTIAL);
  assertField("grade(definition,inputChords): empty problems -> score 1", graded.score, 1);
  assertField("grade(definition,inputChords): empty problems -> activeIndex 0", graded.activeIndex, 0);
  assertEqual("grade(definition,inputChords): empty problems -> problems array empty", graded.problems, []);
})();

(function () {
  // resolved.isChorale === true early-return guard, for parity with
  // ExerciseGrader.grade() (exercise_grader.js:84) even though this is
  // structurally unreachable in production (isChorale and
  // mode="harmonization" are mutually exclusive by construction — see the
  // file-header comment). Confirms the CODE honors the guard if given it,
  // rather than silently relying on the invariant holding elsewhere.
  var grader = new HarmonizationGrader();
  var definition = fakeDefinitionWithProblems([target, target], { isChorale: true });
  var inputChords = fakeInputChords([[48, 52, 57], [48, 52, 57]]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): isChorale=true short-circuits to PARTIAL", graded.result, GraderState.PARTIAL);
  assertField("grade(definition,inputChords): isChorale=true -> problems array empty", graded.problems.length, 0);
})();

(function () {
  // No getResolvedMode() at all (definition doesn't expose it) must not
  // crash -- resolved stays null, only the empty-problems half of the
  // guard can fire, matching exercise_grader.js's own
  // `resolved ? resolved.isChorale : ...` style defensiveness.
  var grader = new HarmonizationGrader();
  var definition = { getProblems: function () { return [target]; } };
  var inputChords = fakeInputChords([[48, 52, 57]]);
  var graded = grader.grade(definition, inputChords);
  assertField("grade(definition,inputChords): no getResolvedMode -> still grades (CORRECT)", graded.result, GraderState.CORRECT);
})();

console.log("");
console.log("Ran harmonization_grader tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}
