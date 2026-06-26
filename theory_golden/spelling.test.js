"use strict";

var fs = require("fs");
var path = require("path");
var adapter = require("./spelling_adapter");

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

var golden = JSON.parse(
  fs.readFileSync(path.join(__dirname, "spelling.json"), "utf8")
);

golden.cases.forEach(function (c) {
  var actual = adapter.spellMidisInKey(c.input.key, c.input.midis);
  assertEqual("spelling " + c.id, actual, c.expected.spelling);
});

if (failed > 0) {
  console.log("\n" + failed + " test(s) FAILED");
  process.exit(1);
} else {
  console.log("\nAll tests passed.");
}
