"use strict";

var { requireDefault } = require("../../test/require_esm");
var logic = requireDefault(require("./key_sig_exercise_logic"));

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, "got", actual, "expected", expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "normalizeKeyAnswer capitalises tonic",
  logic.normalizeKeyAnswer("bb"),
  "Bb"
);
assertEqual(
  "normalizeKeyAnswer preserves sharp",
  logic.normalizeKeyAnswer("f#"),
  "F#"
);
assertEqual(
  "checkKeyAnswer accepts exact match",
  logic.checkKeyAnswer("Bb", { accepted_answers: ["Bb", "A#"] }),
  true
);
assertEqual(
  "checkKeyAnswer accepts enharmonic",
  logic.checkKeyAnswer("A#", { accepted_answers: ["Bb", "A#"] }),
  true
);
assertEqual(
  "checkKeyAnswer accepts normalised lowercase",
  logic.checkKeyAnswer("bb", { accepted_answers: ["Bb", "A#"] }),
  true
);
assertEqual(
  "checkKeyAnswer rejects wrong key",
  logic.checkKeyAnswer("Eb", { accepted_answers: ["Bb", "A#"] }),
  false
);
