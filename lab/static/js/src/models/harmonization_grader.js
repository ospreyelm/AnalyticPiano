"use strict";

/**
 * HarmonizationGrader — Phase 2 isolation of the live `mode="harmonization"`
 * grading path out of ExerciseGrader's god-class switch
 * (exercise_grader.js:152-166, the `case "umto_chorale": if (mode ===
 * "harmonization")` branch).
 *
 * This wraps HarmonizationGraderLogic.harmonizationMatch — the theory/
 * grading logic is NOT reimplemented here, only the per-problem result-shape
 * assembly and aggregate scoring that ExerciseGrader.grade() currently does
 * inline for every mode (lines 59-227), scoped to the harmonization case.
 *
 * Mirrors ExerciseGrader.grade()'s current output shape exactly, INCLUDING
 * its latent quirk: HarmonizationGraderLogic.harmonizationMatch()'s return
 * value has no `count`/`notes` keys (only `state`/`reasons`/`accepted`/
 * `activeMidi`/`note`/`target`), so graded.problems[i].count and .notes are
 * `undefined` for harmonization results today, in production, same as here.
 * Not "fixed" in this wrapper — see docs/architecture/pipeline-registry.md
 * "Legacy grader retirement audit" for the standing rule against incidental
 * behavior changes while isolating live paths.
 *
 * Scope: this wrapper takes already-extracted `problems` (harmonization
 * targets) and already-extracted delivered-MIDI arrays, not a full
 * ExerciseDefinition/ChordBank pair. The definition/inputChords → problems/
 * delivered-notes extraction that ExerciseGrader.grade() does today
 * (exercise_grader.js:45-47, 130-141) is shared plumbing, not harmonization-
 * specific theory, and adapting this wrapper to that exact call signature is
 * deferred to the production-wiring slice (not done here; no app/exercise.js
 * changes, no GraderFactory.create() wiring).
 *
 * Note: ExerciseGrader.grade() also has an early-return guard for
 * `resolved.isChorale` (grader.js:84) that this wrapper does not reproduce.
 * That's not an accidental omission — `isChorale` and `mode === "harmonization"`
 * are mutually exclusive by construction: resolved_mode.js's CHORALE_MODES
 * list (the only way `isChorale` can be true when `mode` is truthy) does not
 * contain `"harmonization"`, and this code path only runs when
 * mode === "harmonization" (grader.js:154). So `isChorale` is always false
 * whenever this branch executes; there is nothing for this wrapper to check.
 */

var GraderState = require("./grader_state");
var harmonizationLogicModule = require("./harmonization_grader_logic");
var HarmonizationGraderLogic = harmonizationLogicModule.default || harmonizationLogicModule;

var STATE = GraderState.STATE;
var CORRECT = GraderState.CORRECT;
var PARTIAL = GraderState.PARTIAL;
var INCORRECT = GraderState.INCORRECT;

var SCORE_MAP = {};
SCORE_MAP[CORRECT] = 0;
SCORE_MAP[PARTIAL] = 1;
SCORE_MAP[INCORRECT] = 2;
var RESULT_MAP = [CORRECT, PARTIAL, INCORRECT];

function HarmonizationGrader(settings) {
  this.settings = settings || {};
  this._lastGradedProblems = [];
}

HarmonizationGrader.STATE = STATE;

HarmonizationGrader.prototype.STATE = STATE;

/**
 * Grades one harmonization target against the notes currently delivered.
 * Mirrors exercise_grader.js:157 (the harmonizationMatch call) + 210-215
 * (the graded.problems[i] assembly) for a single problem.
 *
 * @param {object} target - a harmonization target (problems[i] shape:
 *   bassMidi/bassPc/requiredUpperPcs/allowedPcs/lockedVoices/voiceCountPolicy)
 * @param {array} deliveredNotes - array of MIDI note numbers currently held
 * @returns {object} { score, count, note, notes } — same shape (including
 *   the count/notes-undefined quirk) as ExerciseGrader.grade()'s
 *   graded.problems[i] entry for harmonization.
 */
HarmonizationGrader.prototype.gradeProblem = function (target, deliveredNotes) {
  var result = HarmonizationGraderLogic.harmonizationMatch(target, deliveredNotes);
  return {
    score: SCORE_MAP[result.state],
    count: result.count,
    note: result.note,
    notes: result.notes,
  };
};

/**
 * Grades a full set of harmonization problems against delivered notes.
 * Mirrors ExerciseGrader.grade()'s aggregate loop (lines 59-227) restricted
 * to the harmonization branch: same empty-problems guard (PARTIAL, line
 * 84-89), same worst-state-wins scoring (lines 216-219), same final
 * result/score/activeIndex assembly (lines 222-224).
 *
 * @param {array} problems - array of harmonization targets
 * @param {array} deliveredNotesPerProblem - array of MIDI-number arrays,
 *   one per problem, already extracted/cleaned by the caller (same shape as
 *   ExerciseGrader.grade()'s `actual_notes` per problem)
 * @returns {object} { result, score, problems, activeIndex } — same
 *   aggregate shape as ExerciseGrader.grade().
 */
HarmonizationGrader.prototype.grade = function (problems, deliveredNotesPerProblem) {
  var graded = { result: null, score: 0, problems: [] };

  if (!problems || problems.length === 0) {
    graded.score = SCORE_MAP[PARTIAL];
    graded.result = PARTIAL;
    graded.activeIndex = 0;
    this._lastGradedProblems = graded.problems;
    return graded;
  }

  var score = SCORE_MAP[CORRECT];
  var activeIndex = problems.length;

  for (var i = 0, len = problems.length; i < len; i++) {
    var deliveredNotes = (deliveredNotesPerProblem && deliveredNotesPerProblem[i]) || [];
    var entry = this.gradeProblem(problems[i], deliveredNotes);
    graded.problems[i] = entry;
    if (entry.score > score) {
      score = entry.score;
      activeIndex = i;
    }
  }

  graded.score = score;
  graded.result = RESULT_MAP[score];
  graded.activeIndex = activeIndex;
  this._lastGradedProblems = graded.problems;
  return graded;
};

module.exports = HarmonizationGrader;
