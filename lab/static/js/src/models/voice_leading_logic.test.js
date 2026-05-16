"use strict";

var logic = require("./voice_leading_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, "got", actual, "expected", expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "smooth close motion passes",
  logic.scoreVoiceLeading([[48, 52, 57], [47, 53, 57]], { maxDisplacement: 4, leadingTonePc: 11 }).smoothOK,
  true
);

assertEqual(
  "large leap fails smoothness",
  logic.scoreVoiceLeading([[48, 52, 57], [36, 53, 69]], { maxDisplacement: 4, leadingTonePc: 11 }).smoothOK,
  false
);

assertEqual(
  "doubled leading tone detected",
  logic.scoreVoiceLeading([[47, 59, 62]], { maxDisplacement: 4, leadingTonePc: 11 }).noDoubledLT,
  false
);

assertEqual(
  "no doubled LT when only one LT",
  logic.scoreVoiceLeading([[48, 52, 59]], { maxDisplacement: 4, leadingTonePc: 11 }).noDoubledLT,
  true
);

assertEqual(
  "single sonority always smooth",
  logic.scoreVoiceLeading([[48, 52, 57]], { maxDisplacement: 4 }).smoothOK,
  true
);

console.log("\nAll voice leading tests passed.");
