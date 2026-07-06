import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * FiguredBassSheet — `figured_bass` / `figured_bass_pcs` pipeline (legacy).
 *
 * Owns its render stack: the legacy stave stack, plus the identification
 * overlay (`_isIdentificationLikeExercise()` is true for figured_bass, so
 * the identification mixins on the base light up — same self-gating as the
 * prior single-class behavior). Phase 3 replaces the prior
 * `isChoraleLike && hasMeasures` fork with this per-pipeline class calling
 * the right stack method directly.
 *
 * @constructor
 * @param {object} settings
 */
var FiguredBassSheet = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

FiguredBassSheet.prototype = Object.create(BaseExerciseSheet.prototype);
FiguredBassSheet.prototype.constructor = FiguredBassSheet;

FiguredBassSheet.prototype.renderStaves = function (exercise_midi_nums) {
  return this._renderStavesLegacy(exercise_midi_nums);
};

export default FiguredBassSheet;