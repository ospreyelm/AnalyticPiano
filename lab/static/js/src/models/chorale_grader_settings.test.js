"use strict";

var { resolveChoraleGraderSettings } = require("./chorale_grader_settings");

var failed = 0;

function assertField(label, actual, expected) {
  if (actual !== expected) {
    console.log("FAIL:", label, "got:", actual, "expected:", expected);
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

function fakeDefinition(grading, unit) {
  return {
    getGrading: function () { return grading; },
    isUnit: function (n) { return n === unit; },
  };
}

// ---------------------------------------------------------------------------
// Non-unit-1 exercise: grading settings passed through unchanged.
// ---------------------------------------------------------------------------
(function () {
  var grading = { octaveIndependent: false, someOtherFlag: true };
  var def = fakeDefinition(grading, 5);
  var settings = resolveChoraleGraderSettings(def);
  assertField("non-unit-1: octaveIndependent left as-is", settings.octaveIndependent, false);
  assertField("non-unit-1: other fields preserved", settings.someOtherFlag, true);
  assertField("non-unit-1: same object reference returned (matches getGrading()'s mutate-in-place quirk)",
    settings === grading, true);
})();

// ---------------------------------------------------------------------------
// Unit 1 exercise: octaveIndependent forced true, mutating the SAME object
// getGrading() returned — matches app/exercise.js:143-148 exactly.
// ---------------------------------------------------------------------------
(function () {
  var grading = { octaveIndependent: false };
  var def = fakeDefinition(grading, 1);
  var settings = resolveChoraleGraderSettings(def);
  assertField("unit-1: octaveIndependent forced true", settings.octaveIndependent, true);
  assertField("unit-1: mutated the definition's own grading object in place",
    grading.octaveIndependent, true);
  assertField("unit-1: same object reference returned", settings === grading, true);
})();

// ---------------------------------------------------------------------------
// Unit 1 exercise where getGrading() returns a fresh {} (no exercise.grading
// set) — octaveIndependent still gets forced true on that fresh object.
// ---------------------------------------------------------------------------
(function () {
  var def = fakeDefinition({}, 1);
  var settings = resolveChoraleGraderSettings(def);
  assertField("unit-1 with default {} grading: octaveIndependent forced true", settings.octaveIndependent, true);
})();

// ---------------------------------------------------------------------------
// Guard: missing/malformed definition throws rather than silently proceeding.
// ---------------------------------------------------------------------------
(function () {
  var threw = false;
  try {
    resolveChoraleGraderSettings(null);
  } catch (_e) {
    threw = true;
  }
  assertField("null definition throws", threw, true);
})();

(function () {
  var threw = false;
  try {
    resolveChoraleGraderSettings({ getGrading: function () { return {}; } }); // no isUnit
  } catch (_e) {
    threw = true;
  }
  assertField("definition missing isUnit() throws", threw, true);
})();

(function () {
  var threw = false;
  try {
    resolveChoraleGraderSettings({ isUnit: function () { return false; } }); // no getGrading
  } catch (_e) {
    threw = true;
  }
  assertField("definition missing getGrading() throws", threw, true);
})();

console.log("");
console.log("Ran chorale_grader_settings tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}
