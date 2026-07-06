import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * MatchingSheet — `matching` pipeline (legacy exact-match).
 *
 * Owns its render stack: the legacy stave stack. No identification overlay
 * (`_isIdentificationLikeExercise()` is false for matching, so the overlay
 * self-gates off even though the identification mixins are present on the
 * base). Phase 3 replaces the prior `isChoraleLike && hasMeasures` fork in
 * `exercise_sheet_staves.js` with this per-pipeline class calling the right
 * stack method directly.
 *
 * @constructor
 * @param {object} settings
 */
var MatchingSheet = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

MatchingSheet.prototype = Object.create(BaseExerciseSheet.prototype);
MatchingSheet.prototype.constructor = MatchingSheet;

MatchingSheet.prototype.renderStaves = function (exercise_midi_nums) {
  return this._renderStavesLegacy(exercise_midi_nums);
};

export default MatchingSheet;