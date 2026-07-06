"use strict";

var { requireDefault } = require("../../test/require_esm");
var factoryMod = requireDefault(require("./sheet_factory"));
var resolveSheetKey = factoryMod.resolveSheetKey;
var SHEET_KEYS = factoryMod.SHEET_KEYS;

var rmMod = requireDefault(require("./resolved_mode"));
var resolvePipeline = rmMod.resolvePipeline;

var failed = 0;

function assertField(label, actual, expected) {
  if (actual !== expected) {
    console.log("FAIL:", label, "got:", actual, "expected:", expected);
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

// Helper: resolve a raw exercise and assert its sheet key in one shot.
function expectKey(label, exercise, expectedKey) {
  var r = resolvePipeline(exercise);
  assertField(label + " [pipeline]", r.pipeline, r.pipeline);
  assertField(label + " [sheetKey]", resolveSheetKey(r), expectedKey);
}

// ---------- matching ----------
expectKey("matching", { type: "matching" }, "matching");

// ---------- chorale: all four CHORALE_MODES + type fallback ----------
expectKey("chorale-playback", { type: "umto_chorale", mode: "playback" }, "chorale");
expectKey("chorale-analysis_match", { type: "umto_chorale", mode: "analysis_match" }, "chorale");
expectKey("chorale-play-all-voices", { type: "umto_chorale", mode: "play-all-voices" }, "chorale");
expectKey("chorale-analysis", { type: "umto_chorale", mode: "analysis" }, "chorale");
expectKey("chorale-legacy-type", { type: "chorale" }, "chorale");
expectKey("chorale-umto-no-mode", { type: "umto_chorale" }, "chorale");

// ---------- harmonization ----------
expectKey("harmonization", { type: "umto_chorale", mode: "harmonization" }, "harmonization");

// ---------- figured_bass (legacy) ----------
expectKey("figured_bass", { type: "figured_bass" }, "figured_bass");
expectKey("figured_bass_pcs", { type: "figured_bass_pcs" }, "figured_bass");

// ---------- identification (non-chorale) ----------
expectKey("identification", { type: "identification" }, "identification");

// ---------- chorale_identification (legacy type + umto_chorale + mode) ----------
expectKey("chorale_identification-type", { type: "chorale_identification" }, "chorale_identification");
expectKey("chorale_identification-mode", { type: "umto_chorale", mode: "identification" }, "chorale_identification");
expectKey("chorale_identification-mode2", { type: "umto_chorale", mode: "chorale_identification" }, "chorale_identification");

// ---------- out-of-scope: "other" pipelines collapse to "matching" ----------
// Mirrors GraderFactory's collapse of dead/unknown pipelines into one fallback
// key. Out-of-scope types render through the plain legacy-stave stack with no
// identification overlay today (ExerciseSheetComponent's legacy-render
// fall-through), identical to the matching sheet. symbolic-meter + key-signature
// are intercepted by earlier early-returns in app/exercise.js and never reach
// this factory, but resolveSheetKey still maps them safely.
expectKey("symbolic-meter", { type: "umto_symbolic_meter" }, "matching");
expectKey("musicxml", { type: "musicxml" }, "matching");
expectKey("analytical", { type: "analytical" }, "matching");
expectKey("key-signature", { type: "umto_key_signature" }, "matching");
expectKey("barline-placement", { type: "umto_barline_placement" }, "matching");

// ---------- null/undefined safety ----------
assertField("null resolvedMode", resolveSheetKey(null), "matching");
assertField("undefined resolvedMode", resolveSheetKey(undefined), "matching");
assertField("empty object", resolveSheetKey({}), "matching");
assertField("unknown pipeline", resolveSheetKey({ pipeline: "nonexistent" }), "matching");

// ---------- SHEET_KEYS table integrity ----------
assertField("SHEET_KEYS has 6 canonical + other", Object.keys(SHEET_KEYS).length, 7);
assertField("SHEET_KEYS.matching", SHEET_KEYS.matching, "matching");
assertField("SHEET_KEYS.chorale", SHEET_KEYS.chorale, "chorale");
assertField("SHEET_KEYS.harmonization", SHEET_KEYS.harmonization, "harmonization");
assertField("SHEET_KEYS.figured_bass", SHEET_KEYS.figured_bass, "figured_bass");
assertField("SHEET_KEYS.identification", SHEET_KEYS.identification, "identification");
assertField("SHEET_KEYS.chorale_identification", SHEET_KEYS.chorale_identification, "chorale_identification");
assertField("SHEET_KEYS.other collapses to matching", SHEET_KEYS.other, "matching");

// ---------- create() injection seam: constructs the right class per key ----------
// Fake constructor that records the settings it was called with. Tests never
// touch the real sheet classes (which carry app/-aliased imports and would
// crash this file under plain node with ERR_MODULE_NOT_FOUND) — a clean full
// run here is itself part of the proof that the seam works as designed, same
// property grader_factory.test.js relies on for the chorale branch.
function makeFakeCtor(key) {
  function FakeSheet(settings) {
    this.settings = settings;
    this.__sheetKey = key;
  }
  return FakeSheet;
}

var ALL_FAKES = {
  matching: makeFakeCtor("matching"),
  chorale: makeFakeCtor("chorale"),
  harmonization: makeFakeCtor("harmonization"),
  figured_bass: makeFakeCtor("figured_bass"),
  identification: makeFakeCtor("identification"),
  chorale_identification: makeFakeCtor("chorale_identification"),
};

function expectCreate(label, exercise, expectedKey) {
  var resolved = resolvePipeline(exercise);
  var key = resolveSheetKey(resolved);
  var sheet = factoryMod.create(resolved, {
    exerciseContext: { ctx: true },
    keySignature: { ks: true },
    midiDevice: { md: true },
    constructors: ALL_FAKES,
  });
  assertField(label + " [sheetKey]", key, expectedKey);
  assertField(label + " [constructed the right sheet]", sheet.__sheetKey, expectedKey);
  assertField(label + " [ctor received exerciseContext]", sheet.settings.exerciseContext.ctx, true);
  assertField(label + " [ctor received keySignature]", sheet.settings.keySignature.ks, true);
  assertField(label + " [ctor received midiDevice]", sheet.settings.midiDevice.md, true);
}

expectCreate("create matching", { type: "matching" }, "matching");
expectCreate("create chorale", { type: "umto_chorale", mode: "playback" }, "chorale");
expectCreate("create harmonization", { type: "umto_chorale", mode: "harmonization" }, "harmonization");
expectCreate("create figured_bass", { type: "figured_bass" }, "figured_bass");
expectCreate("create identification", { type: "identification" }, "identification");
expectCreate("create chorale_identification-type", { type: "chorale_identification" }, "chorale_identification");
expectCreate("create chorale_identification-mode", { type: "umto_chorale", mode: "identification" }, "chorale_identification");
// "other" → matching sheet (the collapse)
expectCreate("create other (barline_placement)", { type: "umto_barline_placement" }, "matching");

// ---------- create() throws when constructors[key] is missing ----------
(function () {
  var threw = false;
  try {
    factoryMod.create(resolvePipeline({ type: "umto_chorale", mode: "playback" }), {
      exerciseContext: {}, keySignature: {}, midiDevice: {},
      constructors: { matching: makeFakeCtor("MatchingSheet") }, // missing "chorale"
    });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws when constructors[chorale] missing", threw, true);
})();

(function () {
  var threw = false;
  try {
    factoryMod.create(resolvePipeline({ type: "matching" }), {
      exerciseContext: {}, keySignature: {}, midiDevice: {},
      // no constructors at all
    });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws when constructors absent", threw, true);
})();

(function () {
  var threw = false;
  try {
    factoryMod.create({ pipeline: "nonexistent" }, {
      exerciseContext: {}, keySignature: {}, midiDevice: {},
      constructors: {}, // unknown pipeline → "matching" → missing
    });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws for unknown pipeline (resolves to matching, missing ctor)", threw, true);
})();

// ---------- create() ignores caller-supplied extra settings (uniform shape) ----------
// All sheets take the same {exerciseContext, keySignature, midiDevice} — no
// per-key context variation. Extra keys on context are not forwarded.
(function () {
  var resolved = resolvePipeline({ type: "matching" });
  var sheet = factoryMod.create(resolved, {
    exerciseContext: { ctx: 1 },
    keySignature: { ks: 1 },
    midiDevice: { md: 1 },
    extraField: "should not appear on settings",
    constructors: ALL_FAKES,
  });
  assertField("create() does not forward extraneous context keys",
    sheet.settings.extraField, undefined);
  assertField("create() forwards exactly 3 setting keys",
    Object.keys(sheet.settings).length, 3);
})();

console.log("");
console.log("Ran sheet_factory tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}