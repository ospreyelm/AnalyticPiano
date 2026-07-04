"use strict";

// Golden lock for figured-bass hint prose, one case per analysisType × mode.
// Locks the student-facing hint text against regression; the required-tones
// data underneath is locked separately by figure_realization.json (the
// realization-table golden) and test_figured_bass_hints_data.py (the
// codegen sync). This file locks *prose*, not table correctness.
//
// Run: node theory_golden/figured_bass_hints.test.js

var fs = require("fs");
var path = require("path");
// figured_bass_hints.js is ESM `export default`; Node's require() returns the
// default under `.default` rather than spreading it. Unwrap once.
var _mod = require("../lab/static/js/src/config/figured_bass_hints");
var FbHints = _mod.default || _mod;

var failed = 0;
function fail(label, detail) {
  console.log("FAIL:", label);
  if (detail) console.log("  " + detail);
  failed += 1;
}
function pass(label) { console.log("PASS:", label); }

// Wrap a golden case's serialized input as a mock definition exposing the
// accessors the builders read (getHarmonizationTargets / getProblems /
// getAnalysisType / getMode). Golden JSON cannot carry functions, so the
// runner adapts the plain-data input into the shape the builder expects.
function mockDefinition(input) {
  var mode = input.mode;
  var analysisType = input.analysisType;
  if (mode === "harmonization") {
    return {
      getHarmonizationTargets: function () { return input.targets || []; },
      getAnalysisType: function () { return analysisType; },
      getMode: function () { return mode; },
    };
  }
  var slices = input.slices || [];
  return {
    getProblems: function () { return slices.map(function (c) { return { content: c }; }); },
    getAnalysisType: function () { return analysisType; },
    getMode: function () { return mode; },
  };
}

function buildFor(input) {
  var def = mockDefinition(input);
  if (input.mode === "harmonization") {
    return FbHints.buildHarmonizationHints(def, input.analysisType);
  }
  return FbHints.buildIdentificationHints(def, input.analysisType);
}

var golden = JSON.parse(
  fs.readFileSync(path.join(__dirname, "figured_bass_hints.json"), "utf8")
);

golden.cases.forEach(function (c) {
  var input = c.input;
  var expected = c.expected;

  // Non-vacuity: a case with empty hints must not pass silently.
  if (!expected || !expected.hints || !expected.hints.length) {
    fail(c.id + " has no expected hints (cannot prove prose is locked)");
    return;
  }

  var actual = buildFor(input);
  if (!actual) {
    fail(c.id + " builder returned null (expected a hint object)");
    return;
  }

  var ok = actual.help === expected.help &&
    JSON.stringify(actual.hints) === JSON.stringify(expected.hints) &&
    actual.moreInfo === expected.moreInfo;
  if (ok) {
    pass(c.id + " hint prose matches golden");
  } else {
    fail(c.id + " hint prose drift",
      "expected: " + JSON.stringify(expected) +
      "\n  actual:   " + JSON.stringify(actual));
  }
});

if (failed > 0) { console.log("\n" + failed + " test(s) FAILED"); process.exit(1); }
else { console.log("\nAll tests passed."); }