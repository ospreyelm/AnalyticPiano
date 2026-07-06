/**
 * HarmonizationRuntimeGrader — live runtime harmonization grading extracted
 * mechanically from `ExerciseContext.computeHarmonizationGraded` (PR A).
 *
 * This is the STATEFUL single-target-at-a-time live grading path: it reads the
 * current target at `ctx._harmonizationPointer`, calls
 * `HarmonizationGraderLogic.harmonizationMatch`, advances the pointer on
 * correct/partial, records a rejected sonority on incorrect, and returns the
 * exact graded object shape `ExerciseContext.grade()`'s switch consumes.
 *
 * The grading/state machine is NOT reimplemented here — only relocated. The
 * body is byte-for-byte the prior `computeHarmonizationGraded` with `this.`
 * replaced by `ctx.`. See `docs/architecture/pipeline-registry.md` (PR A) for
 * the extraction contract.
 *
 * State stays on `ExerciseContext` (`_harmonizationPointer`,
 * `acceptedHarmonizationSonorities`, `_harmonizationRejected`) because many
 * external components read and write those fields directly off the context
 * (`components/music.js`, `components/input/click_note.js`,
 * `components/music/exercise_sheet_playback.js`,
 * `components/music/exercise_sheet_staves.js`,
 * `components/music/exercise_sheet_status.js`, `components/app/exercise.js`).
 * This module owns only the COMPUTATION; it mutates the same fields on the
 * passed-in `ctx` that the inline method did, so those external reads are
 * unaffected.
 *
 * Uses the shared `grader_state.js` STATE constants instead of
 * `ctx.grader.STATE` — behavior-identical: Phase 2 made `ExerciseGrader.STATE`
 * a compatibility alias for this same shared object, and the underlying string
 * values ("correct"/"incorrect"/"partial") are unchanged, so
 * `ExerciseContext.grade()`'s switch on `graded.result` against
 * `this.grader.STATE.*` still matches exactly. Decoupling the runtime grader
 * from `ctx.grader` is the point of the extraction; the equality is proven, not
 * assumed.
 *
 * `grade(definition, inputChords)` on `HarmonizationGrader`
 * (`harmonization_grader.js`) is a DIFFERENT, characterization-only path — it
 * wraps the dead `ExerciseGrader.grade()` harmonization switch case, not this
 * live `computeHarmonizationGraded` path. The two must not be conflated: this
 * module is the live one.
 */

import GraderState from "./grader_state.js";
import HarmonizationGraderLogic from "./harmonization_grader_logic.js";

var STATE = GraderState.STATE;

/**
 * Grades the current harmonization target against the notes currently held.
 * Mechanical extraction of `ExerciseContext.computeHarmonizationGraded`
 * (exercise_context.js, pre-PR-A).
 *
 * @param {object} ctx - the ExerciseContext (or a compatible test double)
 *   exposing:
 *     - `ctx.definition.getHarmonizationTargets()` → array of targets
 *     - `ctx._harmonizationPointer` (number, mutated on correct/partial)
 *     - `ctx.acceptedHarmonizationSonorities` (array, pushed on correct/partial)
 *     - `ctx._harmonizationRejected` (mutated: null on correct/partial, set on
 *       incorrect)
 *     - `ctx._emitHarmonizationIncorrectFeedback(matchResult)` (called on
 *       incorrect)
 * @param {array|null|undefined} activeMidi - MIDI note numbers currently held
 * @returns {object} `{ result, score, activeIndex, problems }` — same shape
 *   `ExerciseContext.grade()`'s switch consumes (result is a grader_state STATE
 *   string).
 */
function computeHarmonizationGraded(ctx, activeMidi) {
  var targets = ctx.definition.getHarmonizationTargets
    ? ctx.definition.getHarmonizationTargets() : [];
  var ptr = ctx._harmonizationPointer;
  if (!activeMidi || !activeMidi.length) {
    return {
      result: STATE.PARTIAL,
      score: 1,
      activeIndex: ptr,
      problems: [],
    };
  }
  var matchResult = HarmonizationGraderLogic.harmonizationMatch(targets[ptr] || {}, activeMidi);
  if (matchResult.state === "correct" || matchResult.state === "partial") {
    ctx._harmonizationRejected = null;
    ctx.acceptedHarmonizationSonorities.push({
      midi: activeMidi.slice(),
      targetIndex: ptr,
      ts: Date.now(),
    });
    ctx._harmonizationPointer = ptr + 1;
  } else if (matchResult.state === "incorrect") {
    var tgt = targets[ptr] || {};
    var offsetQb = tgt.offset || 0;
    var beatsPerMeasure = 4; // quarter-beat denominator; most exercises are 4/4
    var mIdx = Math.floor(offsetQb / beatsPerMeasure);
    var onsetWithinMeasure = Math.round((offsetQb - mIdx * beatsPerMeasure) * 1024);
    ctx._harmonizationRejected = {
      midi: activeMidi.slice(),
      spellings: null, // populated by click_note._commit for click path
      measureIndex: mIdx,
      onset: onsetWithinMeasure,
      reasons: matchResult.reasons,
      target: tgt,
    };
    ctx._emitHarmonizationIncorrectFeedback(matchResult);
  }
  var allDone = ctx._harmonizationPointer >= targets.length && targets.length > 0;
  return {
    result: allDone ? STATE.CORRECT
      : (matchResult.state === "incorrect" ? STATE.INCORRECT : STATE.PARTIAL),
    score: allDone ? 0 : (matchResult.state === "incorrect" ? 2 : 1),
    activeIndex: ctx._harmonizationPointer,
    problems: [matchResult],
  };
}

var exports = {
  computeHarmonizationGraded: computeHarmonizationGraded,
  STATE: STATE,
};

export default exports;