import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * ChoraleSheet — `chorale` pipeline (playback / analysis_match /
 * play-all-voices / analysis, or legacy type=chorale / umto_chorale without
 * an identification/harmonization mode).
 *
 * Owns its render stack: the VexFlow stack. The pipeline-identity flags
 * (`isHarmonization`, `isChoraleIdentification`) are declared as literals —
 * this sheet IS the chorale pipeline, not harmonization or
 * chorale_identification. The two flags that vary WITHIN the chorale pipeline
 * are read from this exercise's own `ResolvedMode`: `isAnalysisMatchMode`
 * (true for analysis_match) and `isChorale` (always true for a correctly-
 * routed chorale exercise; read defensively rather than hard-coded). This is
 * the sheet tuning its own config, not a runtime pipeline-discrimination fork
 * — the stack selection is owned by this class, not by a resolved-mode check
 * inside the render path.
 *
 * @constructor
 * @param {object} settings
 */
var ChoraleSheet = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

ChoraleSheet.prototype = Object.create(BaseExerciseSheet.prototype);
ChoraleSheet.prototype.constructor = ChoraleSheet;

ChoraleSheet.prototype.renderStaves = function (exercise_midi_nums) {
  var definition = this.exerciseContext.getDefinition();
  var resolved = definition && definition.getResolvedMode ? definition.getResolvedMode() : null;
  return this._renderStavesVexFlow(exercise_midi_nums, {
    isHarmonization: false,
    isChoraleIdentification: false,
    isAnalysisMatchMode: !!(resolved && resolved.isAnalysisMatch),
    isChorale: !!(resolved && resolved.isChorale),
  });
};

export default ChoraleSheet;