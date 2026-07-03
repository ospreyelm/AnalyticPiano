"use strict";

var logic = require("./key_context_logic");
logic = logic.default || logic;

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

assertEqual("major natural key has display name, prefix, and HarmonyLab key",
  logic.getKeyContext("G"),
  { displayName: "G major", prefix: "G:", harmonyLabKey: "jG_" });

assertEqual("minor lowercase key has lowercase prefix",
  logic.getKeyContext("f#"),
  { displayName: "F# minor", prefix: "f#:", harmonyLabKey: "iF#" });

assertEqual("minor m-suffix key has lowercase prefix",
  logic.getKeyContext("Bbm"),
  { displayName: "Bb minor", prefix: "bb:", harmonyLabKey: "iBb" });

assertEqual("major flat key preserves accidental case in prefix",
  logic.getKeyContext("Bb"),
  { displayName: "Bb major", prefix: "Bb:", harmonyLabKey: "jBb" });

assertEqual("HarmonyLab minor key is idempotent",
  logic.getKeyContext("iF#"),
  { displayName: "F# minor", prefix: "f#:", harmonyLabKey: "iF#" });

assertEqual("invalid key context returns null",
  logic.getKeyContext("?"),
  null);

assertEqual("same normalized key contexts compare equal",
  logic.sameKeyContext("f#", "F#m"),
  true);

assertEqual("different normalized key contexts compare unequal",
  logic.sameKeyContext("f#", "G"),
  false);

if (failed > 0) {
  console.log("\n" + failed + " test(s) FAILED");
  process.exit(1);
} else {
  console.log("\nAll tests passed.");
}
