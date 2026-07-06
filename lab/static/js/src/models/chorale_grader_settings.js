"use strict";

/**
 * Derives ChoraleGrader constructor settings from an ExerciseDefinition.
 *
 * Pulled out of app/exercise.js's inline grader-selection block so
 * GraderFactory.create()'s "chorale" branch (and its tests) can reproduce
 * that derivation without needing the live app/exercise.js call site or a
 * real ExerciseDefinition instance — a plain object exposing getGrading()/
 * isUnit() is enough.
 *
 * Mirrors app/exercise.js:143-148 exactly, including its mutate-in-place
 * quirk: ExerciseDefinition.getGrading() returns `this.exercise.grading ||
 * {}` (exercise_definition.js:831-833) — when `exercise.grading` is already
 * set, getGrading() returns that SAME object, and setting
 * `.octaveIndependent = true` on it mutates the definition's stored grading
 * config in place, not a copy. Not "fixed" here; preserved as-is.
 *
 * Not itself the app/ alias-import problem: this module never touches
 * chorale_grader.js, only the plain definition object passed in, so it's
 * fully testable under plain `node`.
 */

/**
 * @param {object} definition - an ExerciseDefinition (or test double)
 *   exposing getGrading(): object and isUnit(unitNum): boolean
 * @returns {object} grading settings, with octaveIndependent forced true
 *   for Unit 1 (app/exercise.js's "Unit 1 Bridge" comment: makes grading
 *   octave-agnostic for Note Identification)
 * @throws {Error} if definition is missing or doesn't expose both methods
 */
function resolveChoraleGraderSettings(definition) {
  if (!definition || typeof definition.getGrading !== "function" || typeof definition.isUnit !== "function") {
    throw new Error(
      "resolveChoraleGraderSettings requires a definition exposing " +
        "getGrading() and isUnit(unitNum), matching ExerciseDefinition's contract."
    );
  }

  var gradingSettings = definition.getGrading();
  if (definition.isUnit(1)) {
    gradingSettings.octaveIndependent = true;
  }
  return gradingSettings;
}

module.exports = {
  resolveChoraleGraderSettings: resolveChoraleGraderSettings,
};
