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
 * Two call surfaces:
 *   - `gradeProblems(problems, deliveredNotesPerProblem)` — pure, takes
 *     already-extracted harmonization targets and already-extracted
 *     delivered-MIDI arrays. Easiest to unit-test; no ExerciseDefinition/
 *     ChordBank test doubles needed.
 *   - `grade(definition, inputChords)` — matches the SIGNATURE of
 *     ExerciseContext's generic call site (`this.grader.grade(this.definition,
 *     this.inputChords)`, exercise_context.js:273) and reproduces
 *     ExerciseGrader.grade()'s definition/inputChords → problems/delivered-
 *     notes extraction (exercise_grader.js:45-47, 130-141) for the
 *     harmonization case. IMPORTANT (found on code review, 2026-07-05):
 *     ExerciseContext.grade() (exercise_context.js:253-274) checks
 *     `_isHarmonizationExercise()` and, if true, calls
 *     `computeHarmonizationGraded(activeMidi)` instead — it NEVER reaches
 *     line 273's `this.grader.grade(...)` call for harmonization exercises.
 *     `computeHarmonizationGraded` (exercise_context.js:188-232) is a
 *     separate, already-live, stateful implementation: single target at a
 *     time via `_harmonizationPointer`, driven by `activeMidi` from a
 *     held-note tracker (`_harmonizationHeldTracker`,
 *     `HarmonizationGraderLogic.createHeldNoteTracker`), calling
 *     `HarmonizationGraderLogic.harmonizationMatch` directly — it only
 *     reads `this.grader.STATE` constants, never `.grade()`. So
 *     `ExerciseGrader.grade()`'s harmonization switch case (grader.js:
 *     154-158), and by extension this `grade(definition, inputChords)`
 *     adapter matching its call shape, are NOT on any path that production
 *     actually exercises for harmonization today, even once
 *     `GraderFactory.create()`/`app/exercise.js` are wired. This method
 *     remains a faithful, tested characterization of what
 *     ExerciseGrader.grade() does for harmonization (useful groundwork for
 *     eventually retiring that dead switch case), but it is NOT a stepping
 *     stone toward live harmonization wiring by itself — that would require
 *     reconciling with `computeHarmonizationGraded`'s stateful,
 *     single-target interface instead, a separate, larger, not-yet-scoped
 *     redesign.
 *
 * `grade()`'s extraction reproduces ExerciseGrader.grade()'s early-return
 * guard for `resolved.isChorale` (grader.js:84) too, for parity — though in
 * practice it's always false whenever this grader is invoked: `isChorale`
 * and `mode === "harmonization"` are mutually exclusive by construction
 * (resolved_mode.js's CHORALE_MODES list, the only way `isChorale` can be
 * true when `mode` is truthy, does not contain `"harmonization"`, and this
 * grader is only ever selected when mode === "harmonization"). Kept anyway
 * so this adapter's guard condition matches ExerciseGrader's literally,
 * rather than silently relying on an invariant enforced elsewhere.
 *
 * `grade()` does NOT reproduce reading `chord._unison_idx`
 * (ExerciseGrader.grade()'s `delivered_unison_idx`, exercise_grader.js:136):
 * that value is never read by `harmonizationMatch()` or by the aggregate
 * result assembly for the harmonization case — it's plumbing shared with
 * other exercise types' switch branches (notesMatch's ASSESS_UNISON_IDX
 * path) that is dead code for this one. Omitting it changes nothing
 * observable.
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
HarmonizationGrader.prototype.gradeProblems = function (problems, deliveredNotesPerProblem) {
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

/**
 * Extracts one problem's delivered MIDI notes from a ChordBank-shaped
 * `items()` entry. Mirrors exercise_grader.js:134-140 exactly: dedupe via
 * Set, then strip the dummy MIDI 109 marker if present. Returns [] if there
 * is no chord for this problem index (exercise_grader.js:134's `if
 * (chords[i])` guard).
 *
 * @param {object|undefined} item - inputChords.items()[i], or undefined
 * @returns {array} cleaned MIDI note numbers
 */
function extractDeliveredNotes(item) {
  var chord = item && item.chord;
  if (!chord) return [];
  var notes = [...new Set(chord.getNoteNumbers())];
  var dummyIdx = notes.indexOf(109);
  if (dummyIdx > -1) {
    notes.splice(dummyIdx, 1);
  }
  return notes;
}

/**
 * Grades harmonization problems directly from an ExerciseDefinition and an
 * ExerciseChordBank — the production interface ExerciseContext actually
 * calls (`this.grader.grade(this.definition, this.inputChords)`,
 * exercise_context.js:273). Mirrors ExerciseGrader.grade()'s definition/
 * inputChords → problems/delivered-notes extraction (exercise_grader.js:
 * 45-47, 84-89, 130-141) for the harmonization case, then delegates
 * aggregate scoring to gradeProblems() (unchanged, already tested).
 *
 * @param {object} definition - ExerciseDefinition (or compatible test
 *   double) exposing getProblems() and, optionally, getResolvedMode()
 * @param {object} inputChords - ExerciseChordBank (or compatible test
 *   double) exposing items(), each item shaped { chord: { getNoteNumbers()
 *   } }, positionally aligned with getProblems()'s array by index
 * @returns {object} { result, score, problems, activeIndex } — same
 *   aggregate shape as ExerciseGrader.grade().
 */
HarmonizationGrader.prototype.grade = function (definition, inputChords) {
  var problems = definition.getProblems();
  var resolved = definition && definition.getResolvedMode ? definition.getResolvedMode() : null;

  if ((resolved && resolved.isChorale) || (problems && problems.length === 0)) {
    var graded = { result: PARTIAL, score: SCORE_MAP[PARTIAL], problems: [], activeIndex: 0 };
    this._lastGradedProblems = graded.problems;
    return graded;
  }

  var items = inputChords.items();
  var deliveredNotesPerProblem = [];
  for (var i = 0, len = problems.length; i < len; i++) {
    deliveredNotesPerProblem.push(extractDeliveredNotes(items[i]));
  }

  return this.gradeProblems(problems, deliveredNotesPerProblem);
};

module.exports = HarmonizationGrader;
