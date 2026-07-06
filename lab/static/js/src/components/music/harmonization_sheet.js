import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * HarmonizationSheet — `harmonization` pipeline (umto_chorale + mode=harmonization).
 *
 * Owns its render stack: the VexFlow stack with the harmonization config
 * (`isHarmonization: true`). All four cfg flags are pipeline-identity literals
 * — the harmonization pipeline has no sub-mode that flips `isAnalysisMatchMode`
 * or `isChorale`, so no `ResolvedMode` read is needed here. The harmonization-
 * specific render work (selectVoices, accepted-target playedNoteIds, realization
 * payload, lockedVoices) lives inside `_renderStavesVexFlow`, gated on
 * `cfg.isHarmonization` — this sheet turns that gate on by declaring its
 * pipeline. Phase 3 replaces the prior `isChoraleLike && hasMeasures` fork
 * with this per-pipeline class calling the stack method directly.
 *
 * @constructor
 * @param {object} settings
 */
var HarmonizationSheet = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

HarmonizationSheet.prototype = Object.create(BaseExerciseSheet.prototype);
HarmonizationSheet.prototype.constructor = HarmonizationSheet;

HarmonizationSheet.prototype.renderStaves = function (exercise_midi_nums) {
  return this._renderStavesVexFlow(exercise_midi_nums, {
    isHarmonization: true,
    isChoraleIdentification: false,
    isAnalysisMatchMode: false,
    isChorale: false,
  });
};

export default HarmonizationSheet;