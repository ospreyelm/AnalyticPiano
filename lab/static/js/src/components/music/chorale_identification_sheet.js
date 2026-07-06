import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * ChoraleIdentificationSheet — `chorale_identification` pipeline
 * (type=chorale_identification, or umto_chorale + mode=identification /
 * chorale_identification).
 *
 * Owns its render stack: the VexFlow stack with the chorale_identification
 * config (`isChoraleIdentification: true`). All four cfg flags are pipeline-
 * identity literals — the chorale_identification pipeline has no sub-mode that
 * flips `isAnalysisMatchMode` or `isHarmonization`, so no `ResolvedMode` read
 * is needed here. The chorale_identification-specific render work (suppressing
 * the analysis overlays that would spoil the answer, rendering all notation in
 * black from the start, drawing the "?" identification slots) lives inside
 * `_renderStavesVexFlow`, gated on `cfg.isChoraleIdentification` and the
 * base's `_isIdentificationLikeExercise()` — this sheet turns that gate on by
 * declaring its pipeline. Phase 3 replaces the prior `isChoraleLike &&
 * hasMeasures` fork with this per-pipeline class calling the stack method
 * directly.
 *
 * @constructor
 * @param {object} settings
 */
var ChoraleIdentificationSheet = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

ChoraleIdentificationSheet.prototype = Object.create(BaseExerciseSheet.prototype);
ChoraleIdentificationSheet.prototype.constructor = ChoraleIdentificationSheet;

ChoraleIdentificationSheet.prototype.renderStaves = function (exercise_midi_nums) {
  return this._renderStavesVexFlow(exercise_midi_nums, {
    isHarmonization: false,
    isChoraleIdentification: true,
    isAnalysisMatchMode: false,
    isChorale: false,
  });
};

export default ChoraleIdentificationSheet;