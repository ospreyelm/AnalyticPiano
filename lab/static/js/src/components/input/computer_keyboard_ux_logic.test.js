"use strict";

var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  var ok = actual === expected;
  if (ok) {
    console.log("  PASS: " + label);
    pass++;
    return;
  }

  console.log(
    "  FAIL: " + label + "\n" +
    "       got: " + JSON.stringify(actual) + "\n" +
    "  expected: " + JSON.stringify(expected)
  );
  fail++;
}

console.log("\ncomputer_keyboard_ux_logic:");

try {
  var mod = require("./computer_keyboard_ux_logic");
  mod = mod.default || mod;

  assertEqual(
    "exercise default input mode is qwerty",
    mod._getDefaultExerciseInputMode(),
    "qwerty"
  );
  assertEqual(
    "grave shortcut renders as a backtick badge",
    mod._getShortcutDisplayLabel("GRAVE"),
    "`"
  );
  assertEqual(
    "letter shortcut remains uppercase",
    mod._getShortcutDisplayLabel("q"),
    "Q"
  );
} catch (e) {
  console.log("  FAIL: module not found — " + e.message);
  fail += 3;
}

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) {
  process.exit(1);
}
