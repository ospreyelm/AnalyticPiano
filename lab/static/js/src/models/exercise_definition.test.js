"use strict";

// Direct tests for ExerciseDefinition.parse() — the isUMTO/identification
// branch (the Unit 5 chord-quality identification path). No prior test file
// existed for this model because it relies on the Vite `app/...` alias and
// extensionless relative imports; esm_alias_loader.mjs bridges those for the
// plain-node harness. See U4 / KTD4.
//
// Run via: node lab/static/js/src/models/exercise_definition.test.js

var path = require("path");
var { pathToFileURL } = require("url");
var { register } = require("node:module");

// lab/static/js/src (this file lives in lab/static/js/src/models)
process.env.HARMONYLAB_SRC = path.join(__dirname, "..");
var loaderUrl = pathToFileURL(
  path.join(__dirname, "../../test/esm_alias_loader.mjs")
).href;
var exerciseUrl = pathToFileURL(path.join(__dirname, "exercise_definition.js")).href;

var failed = 0;

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label);
    console.log("  got:     ", JSON.stringify(actual));
    console.log("  expected:", JSON.stringify(expected));
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}
function assertTrue(label, cond) {
  if (!cond) {
    console.log("FAIL:", label);
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

function makeIdentificationDef(opts) {
  opts = opts || {};
  var chord = opts.chord || {
    notes: [48, 64, 67, 72],
    answer: "major",
    choices: ["major", "minor"],
    rhythmValue: "w",
    spelling: ["c/3", "e/4", "g/4", "c/5"],
  };
  var def = {
    isUMTO: true,
    type: "identification",
    mode: "identification",
    analysisType: "chord_quality",
    inputMode: "dropdown",
    staffDistribution: "keyboard",
    key: "jC_",
    chord: [chord],
  };
  if (opts.timeSignature !== undefined) def.timeSignature = opts.timeSignature;
  return def;
}

register(loaderUrl, pathToFileURL(__filename));
// register() returns undefined on Node 22; the hooks are active for the next
// dynamic import(). Chain the import off a resolved promise so registration is
// settled before ESM resolution runs.
Promise.resolve()
  .then(function () {
    return import(exerciseUrl);
  })
  .then(function (EDmod) {
    var ED = EDmod.default || EDmod;

    // --- KTD4 regression: timeSignature read inside the isUMTO/identification branch ---
    // The branch returns at parse() before the generic exercise.timeSignature read,
    // so the explicit assignment in the branch is what makes R2 (barlines) fire.
    var exWith = new ED({ definition: makeIdentificationDef({ timeSignature: "4/4" }) }).exercise;
    assertEqual(
      "R2 happy: identification with timeSignature 4/4 parses to 4/4 (not false)",
      exWith.timeSignature,
      "4/4"
    );
    assertTrue(
      "R2 happy: identification sets isUMTO/type/staffDistribution",
      exWith.isUMTO === true && exWith.type === "identification" && exWith.staffDistribution === "keyboard"
    );

    var exLegacy = new ED({ definition: makeIdentificationDef({ timeSignature: false }) }).exercise;
    assertEqual(
      "R2 edge: legacy identification (no timeSignature) stays false",
      exLegacy.timeSignature,
      false
    );

    // --- spelling plumbing (R1/R3) ---
    assertEqual(
      "R1 happy: problem carries recorded spelling",
      exWith.problems[0].spelling,
      ["c/3", "e/4", "g/4", "c/5"]
    );
    assertEqual(
      "R3 happy: problem.notes = sorted chord notes",
      exWith.problems[0].notes,
      [48, 64, 67, 72]
    );
    assertEqual(
      "R1 happy: problem.answer/choices/rhythm plumbed",
      [exWith.problems[0].answer, exWith.problems[0].choices, exWith.problems[0].rhythm],
      ["major", ["major", "minor"], "w"]
    );

    // Legacy exercise: no spelling key on the chord → problem.spelling is null
    // (not undefined) and nothing downstream should throw on it.
    var legacyChord = {
      notes: [60, 64, 67],
      answer: "major",
      choices: ["major", "minor"],
      rhythmValue: "w",
    };
    var exNoSpelling = new ED({
      definition: makeIdentificationDef({ chord: legacyChord, timeSignature: "4/4" }),
    }).exercise;
    assertEqual(
      "R4 edge: legacy chord (no spelling key) → problem.spelling is null",
      exNoSpelling.problems[0].spelling,
      null
    );
    assertEqual(
      "R4 edge: legacy chord notes still plumbed",
      exNoSpelling.problems[0].notes,
      [60, 64, 67]
    );

    // Multiple chords: each problem gets its own spelling, index-aligned.
    var multiChords = [
      { notes: [48, 64, 67, 72], answer: "major", choices: ["major", "minor"], rhythmValue: "w", spelling: ["c/3", "e/4", "g/4", "c/5"] },
      { notes: [51, 67, 70, 75], answer: "major", choices: ["major", "minor"], rhythmValue: "w", spelling: ["eb/3", "g/4", "bb/4", "eb/5"] },
    ];
    var exMulti = new ED({ definition: makeIdentificationDef({ chord: multiChords[0], timeSignature: "4/4" }) }).exercise;
    // build a two-chord def directly
    var twoDef = makeIdentificationDef({ timeSignature: "4/4" });
    twoDef.chord = multiChords;
    exMulti = new ED({ definition: twoDef }).exercise;
    assertEqual("multi-chord: two problems", exMulti.problems.length, 2);
    assertEqual(
      "multi-chord: problem[1] spelling index-aligned to its chord",
      exMulti.problems[1].spelling,
      ["eb/3", "g/4", "bb/4", "eb/5"]
    );
    assertEqual(
      "multi-chord: problem[1] notes index-aligned to its chord",
      exMulti.problems[1].notes,
      [51, 67, 70, 75]
    );

    if (failed > 0) {
      console.log("\n" + failed + " assertion(s) failed.");
      process.exit(1);
    }
    console.log("\nAll exercise_definition.parse() identification-branch tests passed.");
  })
  .catch(function (e) {
    console.log("LOAD/RUN ERROR:", (e && e.stack) || e);
    process.exit(1);
  });