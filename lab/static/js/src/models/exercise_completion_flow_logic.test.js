"use strict";

var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  if (actual === expected) {
    console.log("PASS: " + label);
    pass += 1;
    return;
  }
  console.log(
    "FAIL: " + label + " got=" + JSON.stringify(actual) + " expected=" + JSON.stringify(expected)
  );
  fail += 1;
}

var logic = require("./exercise_completion_flow_logic");

assertEqual("null score card does not block", logic._shouldDeferCompletionAutomation(null), false);
assertEqual(
  "configured hidden score card does not block",
  logic._shouldDeferCompletionAutomation({ isVisible: function () { return false; } }),
  false
);
assertEqual(
  "visible score card blocks",
  logic._shouldDeferCompletionAutomation({ isVisible: function () { return true; } }),
  true
);
assertEqual(
  "legacy visible flag blocks",
  logic._shouldDeferCompletionAutomation({ visible: true }),
  true
);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) {
  process.exit(1);
}