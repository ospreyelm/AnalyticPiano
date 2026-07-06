"use strict";

var { requireDefault } = require("../../test/require_esm");
var factoryMod = requireDefault(require("./grader_factory"));
var resolveGraderKey = factoryMod.resolveGraderKey;
var GRADER_KEYS = factoryMod.GRADER_KEYS;

var rmMod = requireDefault(require("./resolved_mode"));
var resolvePipeline = rmMod.resolvePipeline;

var HarmonizationGrader = requireDefault(require("./harmonization_grader"));
var IdentificationGrader = requireDefault(require("./identification_grader"));

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

// ---------- create() is wired ONLY for harmonization (2026-07-05) ----------
(function () {
  // resolveGraderKey still maps harmonization distinctly (not collapsed into
  // legacy_exercise, not aliased to chorale/identification).
  var resolved = resolvePipeline({ type: "umto_chorale", mode: "harmonization" });
  var key = resolveGraderKey(resolved);
  assertField("harmonization pipeline resolves distinctly", key, "harmonization");
  assertField("harmonization key !== legacy_exercise", key !== "legacy_exercise", true);
  assertField("harmonization key !== chorale", key !== "chorale", true);
  assertField("harmonization key !== identification", key !== "identification", true);

  // create() returns a real HarmonizationGrader instance for harmonization.
  var grader = factoryMod.create(resolved, { keySignature: null });
  assertField("create() returns a HarmonizationGrader instance",
    grader instanceof HarmonizationGrader, true);
  assertField("create()'d grader exposes the shared STATE object",
    grader.STATE, HarmonizationGrader.STATE);
})();

// ---------- create() is now ALSO wired for identification (2026-07-05) ----------
(function () {
  var resolved = resolvePipeline({ type: "identification" });
  var key = resolveGraderKey(resolved);
  assertField("identification pipeline resolves to identification key", key, "identification");

  var grader = factoryMod.create(resolved, { anything: "ignored" });
  assertField("create() returns an IdentificationGrader instance for identification",
    grader instanceof IdentificationGrader, true);
})();

(function () {
  // chorale_identification maps to the SAME "identification" key (see the
  // CAVEAT in grader_factory.js), so create() must construct the same class.
  var resolved = resolvePipeline({ type: "chorale_identification" });
  var key = resolveGraderKey(resolved);
  assertField("chorale_identification pipeline resolves to identification key", key, "identification");

  var grader = factoryMod.create(resolved);
  assertField("create() returns an IdentificationGrader instance for chorale_identification",
    grader instanceof IdentificationGrader, true);
})();

(function () {
  // app/exercise.js:135 always constructs `new IdentificationGrader({})` —
  // caller-supplied settings are never threaded through for this grader in
  // production, so create() must ignore them too, not pass them along.
  var resolved = resolvePipeline({ type: "identification" });
  var grader = factoryMod.create(resolved, { keySignature: "should be ignored" });
  assertField("identification grader construction ignores caller settings (matches app/exercise.js:135)",
    grader.settings && Object.keys(grader.settings).length === 0, true);
})();

// ---------- create() still throws for every OTHER key until wired ----------
(function () {
  var threw = false;
  try {
    factoryMod.create({ pipeline: "matching" });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws for legacy_exercise (matching) until wired", threw, true);
})();

(function () {
  var threw = false;
  try {
    factoryMod.create({ pipeline: "figured_bass" });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws for legacy_exercise (figured_bass) until wired", threw, true);
})();

(function () {
  var threw = false;
  try {
    factoryMod.create({ pipeline: "other" });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws for legacy_exercise (other) until wired", threw, true);
})();

// ---------- create() "chorale" context contract (2026-07-05) ----------
// chorale_grader.js imports an app/-aliased module and cannot be required
// under plain node (confirmed: it's one of the 9 known pre-existing app/
// alias test failures). These tests NEVER let create() reach its
// `require("./chorale_grader")` fallback — every case below either throws
// before that point, or supplies context.constructors.ChoraleGrader so the
// real module is never touched. If any of these accidentally exercised the
// real require, this whole test FILE would crash (ERR_MODULE_NOT_FOUND),
// not just fail one assertion — so a clean full run here is itself part of
// the proof that the seam works as designed.

function FakeChoraleGrader(settings) {
  this.settings = settings;
  this.initFromDefinitionCalls = [];
}
FakeChoraleGrader.prototype.initFromDefinition = function (definition) {
  this.initFromDefinitionCalls.push(definition);
};

function fakeDefinition(grading, unitNum) {
  return {
    getGrading: function () { return grading; },
    isUnit: function (n) { return n === unitNum; },
  };
}

(function () {
  // No context at all -> throws before touching resolveChoraleGraderSettings
  // or any require.
  var threw = false;
  try {
    factoryMod.create({ pipeline: "chorale" });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws for chorale with no context (missing definition)", threw, true);
})();

(function () {
  // context present but no .definition -> still throws.
  var threw = false;
  try {
    factoryMod.create({ pipeline: "chorale" }, { constructors: { ChoraleGrader: FakeChoraleGrader } });
  } catch (_e) {
    threw = true;
  }
  assertField("create() throws for chorale with context missing .definition", threw, true);
})();

(function () {
  // Full context, non-Unit-1: gradingSettings passed through unchanged,
  // initFromDefinition called once with the same definition object.
  var resolved = resolvePipeline({ type: "umto_chorale", mode: "playback" });
  var def = fakeDefinition({ octaveIndependent: false, foo: 1 }, 5);
  var grader = factoryMod.create(resolved, {
    definition: def,
    constructors: { ChoraleGrader: FakeChoraleGrader },
  });
  assertField("chorale (non-unit-1): returns the injected fake instance",
    grader instanceof FakeChoraleGrader, true);
  assertField("chorale (non-unit-1): octaveIndependent left as-is",
    grader.settings.octaveIndependent, false);
  assertField("chorale (non-unit-1): other grading fields preserved",
    grader.settings.foo, 1);
  assertField("chorale (non-unit-1): initFromDefinition called exactly once",
    grader.initFromDefinitionCalls.length, 1);
  assertField("chorale (non-unit-1): initFromDefinition called with the same definition",
    grader.initFromDefinitionCalls[0], def);
})();

(function () {
  // Full context, Unit 1: octaveIndependent forced true (the "Unit 1
  // Bridge" from app/exercise.js:144-147), same initFromDefinition contract.
  var resolved = resolvePipeline({ type: "umto_chorale", mode: "playback" });
  var def = fakeDefinition({ octaveIndependent: false }, 1);
  var grader = factoryMod.create(resolved, {
    definition: def,
    constructors: { ChoraleGrader: FakeChoraleGrader },
  });
  assertField("chorale (unit-1): octaveIndependent forced true",
    grader.settings.octaveIndependent, true);
  assertField("chorale (unit-1): initFromDefinition called with the same definition",
    grader.initFromDefinitionCalls[0], def);
})();

// ---------- production-wiring guard: out-of-scope types + mode="identification" ----------
// Discovered while wiring app/exercise.js (2026-07-05): app/exercise.js's raw
// `interactionMode === "identification"` check is type-agnostic — it routes
// to IdentificationGrader for ANY exercise type with mode="identification",
// including types the six-pipeline split explicitly put out of scope
// (umto_barline_placement, umto_key_signature, umto_symbolic_meter — see
// pipeline-registry.md "Out of scope for the 6-pipeline split"). But
// resolvePipeline()'s pipeline field only recognizes literal
// type="identification"/"chorale_identification" as the "identification"
// pipeline; it does NOT consult the `isIdentification` mirror field. So for
// umto_barline_placement — 26,491 rows as of the 2026-07-05 DB audit, the
// single largest exercise-type bucket in the whole database — pipeline
// resolves to "other" and resolveGraderKey returns "legacy_exercise", which
// create() throws for. app/exercise.js's identification branch MUST guard
// on resolveGraderKey(resolved) === "identification" before ever calling
// create() — calling it unconditionally would break IdentificationGrader
// selection for the largest live exercise-type bucket. This test locks in
// the divergence so it can't silently regress.
assertField("umto_barline_placement + mode=identification resolves to legacy_exercise, NOT identification",
  resolveGraderKey(resolvePipeline({ type: "umto_barline_placement", mode: "identification" })),
  "legacy_exercise");
assertField("umto_key_signature + mode=identification resolves to legacy_exercise, NOT identification",
  resolveGraderKey(resolvePipeline({ type: "umto_key_signature", mode: "identification" })),
  "legacy_exercise");
assertField("umto_symbolic_meter + mode=identification resolves to legacy_exercise, NOT identification",
  resolveGraderKey(resolvePipeline({ type: "umto_symbolic_meter", mode: "identification" })),
  "legacy_exercise");
// Contrast: literal type="identification" and type="umto_chorale" (which
// resolves to the chorale_identification pipeline for this mode) DO
// correctly resolve to the "identification" key — these are the genuinely
// in-scope cases app/exercise.js's guard should route through the factory.
assertField("literal type=identification + mode=identification resolves to identification key",
  resolveGraderKey(resolvePipeline({ type: "identification", mode: "identification" })),
  "identification");
assertField("umto_chorale + mode=identification resolves to identification key (via chorale_identification pipeline)",
  resolveGraderKey(resolvePipeline({ type: "umto_chorale", mode: "identification" })),
  "identification");

// ---------- production-wiring guard: legacy type="chorale_identification" + chorale modes ----------
// Found during code review of the app/exercise.js wiring commit (2026-07-05):
// app/exercise.js's chorale branch condition (interactionMode === "playback"
// || interactionMode === "analysis_match" || (!interactionMode &&
// resolved.isChorale)) does NOT check exercise type. resolved.isChorale IS
// mode-gated (type-independent) for every LIVE type, so resolveGraderKey
// resolves to "chorale" for all of them — but the literal legacy type
// "chorale_identification" (distinct from "umto_chorale") breaks that: its
// isChoraleIdentification predicate (type === "chorale_identification",
// with NO mode check) is evaluated before isChorale in resolvePipeline's
// if/else chain, so it wins regardless of mode. type="chorale_identification"
// + mode="playback"/"analysis_match" therefore resolves to the
// "chorale_identification" pipeline -> "identification" key, NOT "chorale".
// Calling create() unconditionally in the chorale branch would silently
// construct IdentificationGrader under the "Selecting ChoraleGrader" log
// and skip initFromDefinition() entirely for this case. Not live today —
// type="chorale_identification" has 0 rows and is frozen for new writes
// (AGENTS.md) — but app/exercise.js guards on resolveGraderKey(resolved)
// === "chorale" before calling create() specifically because of this. This
// test locks in the divergence so it can't silently regress.
assertField("chorale_identification type + mode=playback resolves to identification key, NOT chorale",
  resolveGraderKey(resolvePipeline({ type: "chorale_identification", mode: "playback" })),
  "identification");
assertField("chorale_identification type + mode=analysis_match resolves to identification key, NOT chorale",
  resolveGraderKey(resolvePipeline({ type: "chorale_identification", mode: "analysis_match" })),
  "identification");
// Contrast: umto_chorale with the same modes correctly resolves to "chorale"
// — these are the genuinely in-scope cases app/exercise.js's chorale guard
// should route through the factory.
assertField("umto_chorale + mode=playback resolves to chorale key", resolveGraderKey(resolvePipeline({ type: "umto_chorale", mode: "playback" })), "chorale");
assertField("umto_chorale + mode=analysis_match resolves to chorale key", resolveGraderKey(resolvePipeline({ type: "umto_chorale", mode: "analysis_match" })), "chorale");

console.log("");
console.log("Ran grader_factory tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}