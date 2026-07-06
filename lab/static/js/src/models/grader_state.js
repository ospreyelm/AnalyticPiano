"use strict";

/**
 * Shared exercise-result state constants.
 *
 * `ExerciseGrader`, `ChoraleGrader`, and `IdentificationGrader` each define
 * their own identical INCORRECT/CORRECT/PARTIAL literals and STATE map today.
 * This module is the Phase 2 extraction target for that constant — no
 * behavior change: values are unchanged, still "incorrect"/"correct"/"partial".
 */

var INCORRECT = "incorrect";
var CORRECT = "correct";
var PARTIAL = "partial";

var STATE = {
  INCORRECT: INCORRECT,
  CORRECT: CORRECT,
  PARTIAL: PARTIAL,
};

var exports = {
  STATE: STATE,
  INCORRECT: INCORRECT,
  CORRECT: CORRECT,
  PARTIAL: PARTIAL,
};

export default exports;
