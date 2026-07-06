"use strict";

var { requireDefault } = require("../../test/require_esm");
var logic = requireDefault(require("./harmonization_targets_logic"));

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

var definition = {
  mode: "harmonization",
  harmonizationTargets: [{ offset: 0, bassMidi: 48, figures: ["6", "3"] }]
};

assertEqual("returns harmonization targets",
  logic.getHarmonizationTargets(definition),
  definition.harmonizationTargets);

assertEqual("detects harmonization mode",
  logic.isHarmonization(definition), true);

assertEqual("non-harmonization mode is false",
  logic.isHarmonization({ mode: "playback" }), false);

// mode from nested umto metadata
var nestedDef = {
  score: { umto: { metadata: { mode: "harmonization" } } },
  harmonizationTargets: [{ offset: 0, bassMidi: 55 }]
};
assertEqual("reads mode from score.umto.metadata",
  logic.isHarmonization(nestedDef), true);

assertEqual("returns empty array when no targets",
  logic.getHarmonizationTargets({ mode: "harmonization" }), []);

assertEqual("getMode returns null when absent",
  logic.getMode({}), null);

var metaDef = {
  score: { umto: { metadata: { chord_settle_ms: 150, locked_voices: ["B"] } } }
};
assertEqual("getHarmonizationMetadata returns metadata",
  logic.getHarmonizationMetadata(metaDef).chord_settle_ms, 150);

if (failed > 0) {
  console.log("\n" + failed + " test(s) FAILED");
  process.exit(1);
} else {
  console.log("\nAll tests passed.");
}
