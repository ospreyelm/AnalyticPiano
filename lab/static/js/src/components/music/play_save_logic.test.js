"use strict";
var mod = require("./play_save_logic");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + "\n  got:  " + g + "\n  want: " + w); }
}

// buildChordRows: per-chord offset+duration from a durations array, preserving notes.
var rows = mod.buildChordRows(
  [{ visible: [60, 64, 67], hidden: [], spelling: ["C4", "E4", "G4"] },
   { visible: [62, 65, 69], hidden: [], spelling: ["D4", "F4", "A4"] }],
  [1, 2]
);
assertEqual("row 0 offset/duration", [rows[0].offset, rows[0].duration], [0, 1]);
assertEqual("row 1 offset/duration", [rows[1].offset, rows[1].duration], [1, 2]);
assertEqual("row 0 keeps visible+spelling",
  [rows[0].visible, rows[0].spelling], [[60, 64, 67], ["C4", "E4", "G4"]]);

// buildAnalysisSlices: below-zone harmonic labels -> slices; empty when no below zone.
assertEqual("no below zone -> no slices",
  mod.buildAnalysisSlices([0, 1], { above: "scale_degrees", below: null }, [], {}), []);
var slices = mod.buildAnalysisSlices(
  [0, 1],
  { above: null, below: "roman_numerals" },
  ["I", "V"],
  {}
);
assertEqual("roman slices count", slices.length, 2);
assertEqual("roman slice 0 content", slices[0].content, { roman_numeral: "I" });
assertEqual("roman slice is_target", slices[0].is_target, true);
var fb = mod.buildAnalysisSlices([0], { above: null, below: "thoroughbass" }, ["6"], {});
assertEqual("thoroughbass content key", fb[0].content, { figured_bass: "6" });
var ov = mod.buildAnalysisSlices([0, 1], { above: null, below: "roman_numerals" },
  ["I", "V"], { 1: { below: "V7" } });
assertEqual("override applied", ov[1].content, { roman_numeral: "V7" });

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll play_save_logic assertions passed (" + pass + ")."); }
