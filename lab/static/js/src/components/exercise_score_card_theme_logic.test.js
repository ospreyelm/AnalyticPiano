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

console.log("\nexercise_score_card_theme_logic:");

try {
  var mod = require("./exercise_score_card_theme_logic");

  assertEqual("blue arc token uses warm accent", mod.arc.blue, "#8d6b52");
  assertEqual("blue banner uses warm cream surface", mod.banner.blueBg, "#efe2d1");
  assertEqual("blue badge uses warm cream surface", mod.badge.blueBg, "#efe2d1");
  assertEqual("blue primary CTA uses dark brown", mod.button.blueBg, "#3f3127");
} catch (e) {
  console.log("  FAIL: module not found — " + e.message);
  fail += 4;
}

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) {
  process.exit(1);
}
