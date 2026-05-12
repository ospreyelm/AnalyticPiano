"use strict";

var fs = require("fs");
var vm = require("vm");

var logic = require("./barline_player_placeholder_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, actual, expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "boots only for barline placement payloads",
  [
    logic.shouldBoot({ type: "umto_barline_placement" }),
    logic.shouldBoot({ type: "umto_symbolic_meter" }),
  ],
  [true, false]
);

assertEqual(
  "placeholder renders visible barline prompt",
  logic.buildPlaceholderHTML({ time_signature: "3/4" }).indexOf("Place the barlines.") >= 0,
  true
);

assertEqual(
  "placeholder escapes payload text",
  logic.buildPlaceholderHTML({ time_signature: '<img src=x onerror="bad">' }).indexOf("<img") === -1,
  true
);

var browserLikeGlobal = {};
browserLikeGlobal.globalThis = browserLikeGlobal;
vm.runInNewContext(
  fs.readFileSync(require.resolve("./barline_player_placeholder_logic"), "utf8"),
  browserLikeGlobal
);

assertEqual(
  "module attaches to globalThis for browser module imports",
  !!browserLikeGlobal.BarlinePlayerPlaceholderLogic &&
    browserLikeGlobal.BarlinePlayerPlaceholderLogic.shouldBoot({ type: "umto_barline_placement" }),
  true
);
