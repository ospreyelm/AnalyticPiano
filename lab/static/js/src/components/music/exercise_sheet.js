import _ from "lodash";
import BaseExerciseSheet from "./base_exercise_sheet";

/**
 * ExerciseSheetComponent — Phase 3 bridge.
 *
 * The god-class body that lived here moved to `base_exercise_sheet.js`
 * (`BaseExerciseSheet`). This file is now a thin subclass that inherits the
 * behavior-identical dispatching `renderStaves` (from the `ExerciseSheetStaves`
 * mixin) so `app/exercise.js`'s pre-Phase-3 `new ExerciseSheetComponent(...)`
 * site keeps working unchanged. It is deleted once `app/exercise.js` switches
 * to `SheetFactory` + the per-pipeline sheet classes (next slice).
 *
 * @constructor
 * @param {object} settings
 */
var ExerciseSheetComponent = function (settings) {
  BaseExerciseSheet.call(this, settings);
};

ExerciseSheetComponent.prototype = Object.create(BaseExerciseSheet.prototype);
ExerciseSheetComponent.prototype.constructor = ExerciseSheetComponent;

// No override: inherits the dispatching renderStaves from BaseExerciseSheet
// (mixed in via ExerciseSheetStaves), preserving pre-Phase-3 behavior exactly.

export default ExerciseSheetComponent;