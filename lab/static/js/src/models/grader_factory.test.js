"use strict";

var { requireDefault } = require("../../test/require_esm");
var factoryMod = requireDefault(require("./grader_factory"));
var resolveGraderKey = factoryMod.resolveGraderKey;
var GRADER_KEYS = factoryMod.GRADER_KEYS;

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

// Helper: resolve a raw exercise and assert its grader key in one shot.
function expectKey(label, exercise, expectedKey) {
  var r = resolvePipeline(exercise);
  assertField(label + " [pipeline]", r.pipeline, GRADER_KEYS.hasOwnProperty(r.pipeline) ? r.pipeline : "other-mapped");
  assertField(label + " [graderKey]", resolveGraderKey(r), expectedKey);
}

// ---------- matching ----------
expectKey("matching", { type: "matching" }, "legacy_exercise");

// ---------- chorale: playback ----------
expectKey("chorale-playback", { type: "umto_chorale", mode: "playback" }, "chorale");

// ---------- chorale: analysis_match (preserves current ChoraleGrader behavior) ----------
// This is the case that today selects ChoraleGrader via app/exercise.js:131,
// NOT the latent ExerciseGrader.analysisMatch path at grader.js:142.
expectKey("chorale-analysis_match", { type: "umto_chorale", mode: "analysis_match" }, "chorale");

// ---------- chorale: play-all-voices + analysis ----------
expectKey("chorale-play-all-voices", { type: "umto_chorale", mode: "play-all-voices" }, "chorale");
expectKey("chorale-analysis", { type: "umto_chorale", mode: "analysis" }, "chorale");

// ---------- chorale: legacy type=chorale (no mode) ----------
expectKey("chorale-legacy-type", { type: "chorale" }, "chorale");

// ---------- chorale: umto_chorale with no mode (type fallback) ----------
expectKey("chorale-umto-no-mode", { type: "umto_chorale" }, "chorale");

// ---------- harmonization ----------
expectKey("harmonization", { type: "umto_chorale", mode: "harmonization" }, "harmonization");

// ---------- figured_bass (legacy) ----------
expectKey("figured_bass", { type: "figured_bass" }, "legacy_exercise");
expectKey("figured_bass_pcs", { type: "figured_bass_pcs" }, "legacy_exercise");

// ---------- identification (non-chorale) ----------
expectKey("identification", { type: "identification" }, "identification");

// ---------- chorale_identification (legacy type) ----------
expectKey("chorale_identification-type", { type: "chorale_identification" }, "identification");

// ---------- chorale_identification (umto_chorale + mode) ----------
expectKey("chorale_identification-mode", { type: "umto_chorale", mode: "identification" }, "identification");
// CAVEAT: this asserts the factory's MAPPING, not current production selection.
// Production app/exercise.js does NOT route mode="chorale_identification" literal
// to IdentificationGrader (it falls through to ExerciseGrader/notesMatch). The
// factory maps to "identification" per predicate intent. See grader_factory.js
// CAVEAT + TODO. Divergence is only live if a persisted row carries this mode.
expectKey("chorale_identification-mode2", { type: "umto_chorale", mode: "chorale_identification" }, "identification");

// ---------- out-of-scope: "other" pipelines default to legacy_exercise ----------
expectKey("symbolic-meter", { type: "umto_symbolic_meter" }, "legacy_exercise");
expectKey("musicxml", { type: "musicxml" }, "legacy_exercise");
expectKey("analytical", { type: "analytical" }, "legacy_exercise");
expectKey("key-signature", { type: "umto_key_signature" }, "legacy_exercise");

// ---------- null/undefined safety ----------
assertField("null resolvedMode", resolveGraderKey(null), "legacy_exercise");
assertField("undefined resolvedMode", resolveGraderKey(undefined), "legacy_exercise");
assertField("empty object", resolveGraderKey({}), "legacy_exercise");
assertField("unknown pipeline", resolveGraderKey({ pipeline: "nonexistent" }), "legacy_exercise");

// ---------- GRADER_KEYS table integrity ----------
assertField("GRADER_KEYS has 6 canonical + other", Object.keys(GRADER_KEYS).length, 7);
assertField("GRADER_KEYS.chorale", GRADER_KEYS.chorale, "chorale");
assertField("GRADER_KEYS.identification covers chorale_identification",
  GRADER_KEYS.identification, GRADER_KEYS.chorale_identification);

// ---------- 2026-07-05 audit: legacy/unknown/dead paths collapse to ONE key ----------
// Per docs/architecture/pipeline-registry.md "Legacy grader retirement audit":
// matching, figured_bass, and "other" have zero live-student-reachable rows.
// Product direction is one retained ExerciseGrader fallback, not per-type
// legacy classes — assert they all resolve to the same fallback key.
assertField("GRADER_KEYS.matching collapses to legacy_exercise", GRADER_KEYS.matching, "legacy_exercise");
assertField("GRADER_KEYS.figured_bass collapses to legacy_exercise", GRADER_KEYS.figured_bass, "legacy_exercise");
assertField("GRADER_KEYS.other collapses to legacy_exercise", GRADER_KEYS.other, "legacy_exercise");
assertField("matching === figured_bass fallback key", GRADER_KEYS.matching, GRADER_KEYS.figured_bass);
assertField("matching === other fallback key", GRADER_KEYS.matching, GRADER_KEYS.other);
// harmonization stays its OWN key — it is live (34 reachable rows), not a
// dead/unknown path, even though today's implementation still constructs
// ExerciseGrader as the delegate. Must NOT collapse into legacy_exercise.
assertField("GRADER_KEYS.harmonization stays distinct from legacy_exercise",
  GRADER_KEYS.harmonization !== GRADER_KEYS.matching, true);

// ---------- create() is a stub that throws (skeleton guard) ----------
(function () {
  var threw = false;
  try {
    factoryMod.create({ pipeline: "matching" });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws until wired", threw, true);
})();

console.log("");
console.log("Ran grader_factory tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}