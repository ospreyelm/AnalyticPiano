import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * IdentificationSheet — `identification` pipeline (legacy non-chorale).
 *
 * Owns its render stack: the legacy stave stack, plus the identification
 * overlay (`_isIdentificationLikeExercise()` is true for identification, so
 * the identification mixins on the base light up — same self-gating as the
 * prior single-class behavior). Phase 3 replaces the prior
 * `isChoraleLike && hasMeasures` fork with this per-pipeline class calling
 * the right stack method directly.
 *
 * @constructor
 * @param {object} settings
 */
var IdentificationSheet = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

IdentificationSheet.prototype = Object.create(BaseExerciseSheet.prototype);
IdentificationSheet.prototype.constructor = IdentificationSheet;

IdentificationSheet.prototype.renderStaves = function (exercise_midi_nums) {
  return this._renderStavesLegacy(exercise_midi_nums);
};

export default IdentificationSheet;