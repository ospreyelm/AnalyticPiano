"use strict";

var { requireDefault } = require("../../test/require_esm");
var mod = requireDefault(require("./resolved_mode"));
var resolvePipeline = mod.resolvePipeline;

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

function assertField(label, actual, expected) {
  if (actual !== expected) {
    console.log("FAIL:", label, "got:", actual, "expected:", expected);
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

// ---------- matching ----------
(function () {
  var r = resolvePipeline({ type: "matching" });
  assertField("matching.pipeline", r.pipeline, "matching");
  assertField("matching.stack", r.stack, "legacy-stave");
  assertField("matching.isChorale", r.isChorale, false);
  assertField("matching.isIdentification", r.isIdentification, false);
})();

// ---------- chorale: umto_chorale + playback ----------
(function () {
  var r = resolvePipeline({ type: "umto_chorale", mode: "playback" });
  assertField("chorale-playback.pipeline", r.pipeline, "chorale");
  assertField("chorale-playback.stack", r.stack, "vexflow");
  assertField("chorale-playback.isChorale", r.isChorale, true);
  assertField("chorale-playback.isAnalysisMatch", r.isAnalysisMatch, false);
})();

// ---------- chorale: umto_chorale + analysis_match ----------
(function () {
  var r = resolvePipeline({ type: "umto_chorale", mode: "analysis_match" });
  assertField("chorale-analysis_match.pipeline", r.pipeline, "chorale");
  assertField("chorale-analysis_match.stack", r.stack, "vexflow");
  assertField("chorale-analysis_match.isAnalysisMatch", r.isAnalysisMatch, true);
  assertField("chorale-analysis_match.isChorale", r.isChorale, true);
})();

// ---------- chorale: legacy type=chorale, no mode (type fallback) ----------
(function () {
  var r = resolvePipeline({ type: "chorale" });
  assertField("chorale-legacy-type.pipeline", r.pipeline, "chorale");
  assertField("chorale-legacy-type.stack", r.stack, "vexflow");
  assertField("chorale-legacy-type.isChorale", r.isChorale, true);
  assertField("chorale-legacy-type.interactionMode", r.interactionMode, null);
})();

// ---------- "play" default-fill (mode=play, type=chorale) ----------
// Documents ACTUAL current predicate behavior, which is surprising: isChorale()
// only falls back to the type axis when mode is FALSY. With a truthy mode="play"
// (the default fill from exercise_definition.js:893), the mode check runs,
// "play" is not in CHORALE_MODES, and isChorale() returns FALSE. The exercise
// then resolves to pipeline "other" + legacy-stave. This may be a latent bug
// (legacy type=chorale exercises with the "play" default do NOT route as
// chorale), but resolvePipeline must mirror current behavior exactly —
// Phase 1.1 guarantees "behavior identical." Investigate separately, do not
// "fix" it in the resolver without a Phase 0 snapshot proving the desired
// behavior.
(function () {
  var r = resolvePipeline({ type: "chorale", mode: "play" });
  assertField("chorale-play-default.isChorale", r.isChorale, false);
  assertField("chorale-play-default.pipeline", r.pipeline, "other");
  assertField("chorale-play-default.stack", r.stack, "legacy-stave");
})();

// ---------- chorale: play-all-voices + analysis modes ----------
(function () {
  assertField("play-all-voices.isChorale", resolvePipeline({ type: "umto_chorale", mode: "play-all-voices" }).isChorale, true);
  assertField("analysis.isChorale", resolvePipeline({ type: "umto_chorale", mode: "analysis" }).isChorale, true);
})();

// ---------- harmonization ----------
(function () {
  var r = resolvePipeline({ type: "umto_chorale", mode: "harmonization" });
  assertField("harmonization.pipeline", r.pipeline, "harmonization");
  assertField("harmonization.stack", r.stack, "vexflow");
  assertField("harmonization.isHarmonization", r.isHarmonization, true);
  // isChorale is false: mode="harmonization" is truthy → mode-check only → not in CHORALE_MODES.
  // Type fallback only fires when mode is falsy. isChoraleLike still true via isHarmonization → vexflow.
  assertField("harmonization.isChorale", r.isChorale, false);
  assertField("harmonization.isChoraleIdentification", r.isChoraleIdentification, false);
})();

// ---------- figured_bass (legacy) ----------
(function () {
  var r = resolvePipeline({ type: "figured_bass" });
  assertField("figured_bass.pipeline", r.pipeline, "figured_bass");
  assertField("figured_bass.stack", r.stack, "legacy-stave");
  assertField("figured_bass.isChorale", r.isChorale, false);
  assertField("figured_bass.isIdentification", r.isIdentification, false);
  // analysisType axis is independent of pipeline here
  var r2 = resolvePipeline({ type: "figured_bass", analysisType: "figured_bass" });
  assertField("figured_bass.analysisKind", r2.analysisKind, "figured_bass");
})();

// ---------- figured_bass_pcs ----------
(function () {
  var r = resolvePipeline({ type: "figured_bass_pcs" });
  assertField("figured_bass_pcs.pipeline", r.pipeline, "figured_bass");
  assertField("figured_bass_pcs.stack", r.stack, "legacy-stave");
})();

// ---------- identification (non-chorale) ----------
(function () {
  var r = resolvePipeline({ type: "identification" });
  assertField("identification.pipeline", r.pipeline, "identification");
  assertField("identification.stack", r.stack, "legacy-stave");
  assertField("identification.isIdentification", r.isIdentification, true);
  assertField("identification.isChorale", r.isChorale, false);
  assertField("identification.isChoraleIdentification", r.isChoraleIdentification, false);
})();

// ---------- chorale_identification (legacy type) ----------
(function () {
  var r = resolvePipeline({ type: "chorale_identification" });
  assertField("chorale_identification-type.pipeline", r.pipeline, "chorale_identification");
  assertField("chorale_identification-type.stack", r.stack, "vexflow");
  assertField("chorale_identification-type.isChoraleIdentification", r.isChoraleIdentification, true);
  assertField("chorale_identification-type.isIdentification", r.isIdentification, true); // type in isIdentification list
  assertField("chorale_identification-type.isChorale", r.isChorale, false); // type not in CHORALE_TYPES, no mode
})();

// ---------- chorale_identification (umto_chorale + mode=identification) ----------
(function () {
  var r = resolvePipeline({ type: "umto_chorale", mode: "identification" });
  assertField("chorale_identification-mode.pipeline", r.pipeline, "chorale_identification");
  assertField("chorale_identification-mode.stack", r.stack, "vexflow");
  assertField("chorale_identification-mode.isChoraleIdentification", r.isChoraleIdentification, true);
  // isChorale is false: mode="identification" is truthy → mode-check only → not in CHORALE_MODES.
  // Type fallback only fires when mode is falsy. isChoraleLike still true via isChoraleIdentification → vexflow.
  assertField("chorale_identification-mode.isChorale", r.isChorale, false);
})();

// ---------- chorale_identification (umto_chorale + mode=chorale_identification) ----------
(function () {
  var r = resolvePipeline({ type: "umto_chorale", mode: "chorale_identification" });
  assertField("chorale_identification-mode2.pipeline", r.pipeline, "chorale_identification");
  assertField("chorale_identification-mode2.isChoraleIdentification", r.isChoraleIdentification, true);
})();

// ---------- mode fallback: score.umto.metadata.mode ----------
(function () {
  var r = resolvePipeline({
    type: "umto_chorale",
    score: { umto: { metadata: { mode: "playback" } } },
  });
  assertField("mode-fallback.interactionMode", r.interactionMode, "playback");
  assertField("mode-fallback.isChorale", r.isChorale, true);
  assertField("mode-fallback.pipeline", r.pipeline, "chorale");
})();

// ---------- umto_chorale with no mode at all (type fallback) ----------
(function () {
  var r = resolvePipeline({ type: "umto_chorale" });
  assertField("umto_chorale-no-mode.pipeline", r.pipeline, "chorale");
  assertField("umto_chorale-no-mode.isChorale", r.isChorale, true);
  assertField("umto_chorale-no-mode.interactionMode", r.interactionMode, null);
})();

// ---------- out-of-scope: symbolic meter ----------
(function () {
  var r = resolvePipeline({ type: "umto_symbolic_meter" });
  assertField("symbolic-meter.pipeline", r.pipeline, "other");
  assertField("symbolic-meter.isSymbolicMeter", r.isSymbolicMeter, true);
  assertField("symbolic-meter.isChoraleIdentification", r.isChoraleIdentification, false);
  assertField("symbolic-meter.isIdentification", r.isIdentification, true); // predicate includes symbolic meter
  assertField("symbolic-meter.stack", r.stack, "legacy-stave");
})();

// ---------- out-of-scope: key signature, barline, musicxml, analytical ----------
(function () {
  assertField("key-signature.pipeline", resolvePipeline({ type: "umto_key_signature" }).pipeline, "other");
  assertField("musicxml.pipeline", resolvePipeline({ type: "musicxml" }).pipeline, "other");
  assertField("analytical.pipeline", resolvePipeline({ type: "analytical" }).pipeline, "other");
  assertField("analytical_pcs.pipeline", resolvePipeline({ type: "analytical_pcs" }).pipeline, "other");
})();

// ---------- staffStyle passthrough ----------
(function () {
  var r = resolvePipeline({ type: "matching", staffDistribution: "chorale" });
  assertField("staffStyle passthrough", r.staffStyle, "chorale");
  // staffStyle "chorale" is the layout axis, NOT the type axis — pipeline is still matching
  assertField("staffStyle does not change pipeline", r.pipeline, "matching");
  assertField("staffStyle does not change stack", r.stack, "legacy-stave");
})();

// ---------- null/empty input safety ----------
(function () {
  var r = resolvePipeline(null);
  assertField("null.pipeline", r.pipeline, "other");
  assertField("null.exerciseType", r.exerciseType, null);
  assertField("null.stack", r.stack, "legacy-stave");
})();

// ---------- frozen output ----------
(function () {
  var r = resolvePipeline({ type: "matching" });
  var threw = false;
  try {
    r.pipeline = "tampered";
  } catch (_e) {
    threw = true;
  }
  assertField("output is frozen", threw, true);
})();

console.log("");
console.log("Ran resolved_mode tests; " + failed + " failed.");
if (failed > 0) {
  process.exit(1);
}