"use strict";
var mod = require("./chordal_barlines_logic");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + "\n  got:  " + g + "\n  want: " + w); }
}
function assertThrows(name, fn) {
  try { fn(); fail++; console.error("FAIL - " + name + " (no throw)"); }
  catch (e) { pass++; console.log("ok - " + name); }
}

// PALETTE
assertEqual("palette is the eight authoring values",
  mod.PALETTE, [4, 3, 2, 1.5, 1, 0.75, 0.5, 0.25]);
assertEqual("isPaletteDuration accepts 1.5", mod.isPaletteDuration(1.5), true);
assertEqual("isPaletteDuration rejects 1.25", mod.isPaletteDuration(1.25), false);

// CUMULATIVE OFFSETS
assertEqual("offsetsFromDurations cumulative",
  mod.offsetsFromDurations([1, 1, 2, 0.5]), [0, 1, 2, 4]);

// AUTO-SUGGEST BARLINES (4/4, eight quarters -> barline at 4.0; excludes 0 and end=8)
assertEqual("suggestBarlines 4/4 eight quarters",
  mod.suggestBarlines([0,1,2,3,4,5,6,7], [1,1,1,1,1,1,1,1], "4/4"), [4]);
assertEqual("suggestBarlines free mode (null meter) -> none",
  mod.suggestBarlines([0,1,2], [1,1,1], null), []);

// SPLIT INDICES: item counts per measure, given chord onsets + barline offsets
assertEqual("splitCounts 6 quarters, barlines [2,4] -> [2,2,2]",
  mod.measureItemCounts([0,1,2,3,4,5], [2,4]), [2, 2, 2]);
assertEqual("splitCounts free single measure",
  mod.measureItemCounts([0,1,1.5], []), [3]);

// VALIDITY MIRROR (returns {ok, error?} — never throws; UI gates on .ok)
assertEqual("validity free mode ok",
  mod.checkRhythm([0,1,1.75], [1,0.75,0.25], null, []).ok, true);
assertEqual("validity free rejects off-palette",
  mod.checkRhythm([0], [1.25], null, []).ok, false);
assertEqual("validity metered exact tiling ok",
  mod.checkRhythm([0,1,2,3,4,5,6,7], [1,1,1,1,1,1,1,1], "4/4", [4]).ok, true);
var short = mod.checkRhythm([0,1,2], [1,1,1], "4/4", []);
assertEqual("validity metered short bar not ok", short.ok, false);
assertEqual("validity metered short bar names the bar",
  /bar/i.test(short.error), true);
assertEqual("validity barline off-onset not ok",
  mod.checkRhythm([0,1,2,3], [1,1,1,1], "4/4", [2.5]).ok, false);
assertEqual("validity overlap not ok (free)",
  mod.checkRhythm([0,1], [4,1], null, []).ok, false);

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll chordal_barlines_logic assertions passed (" + pass + ")."); }
