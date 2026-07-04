"use strict";
var { requireDefault } = require("../../test/require_esm");
var mod = requireDefault(require("./analysis_slots"));

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + "\n  got:  " + g + "\n  want: " + w); }
}

assertEqual("roman_numerals allowed below only",
  mod.allowedZones("roman_numerals"), ["below"]);
assertEqual("thoroughbass allowed below only",
  mod.allowedZones("thoroughbass"), ["below"]);
assertEqual("scale_degrees allowed above only",
  mod.allowedZones("scale_degrees"), ["above"]);
assertEqual("note_names allowed above only",
  mod.allowedZones("note_names"), ["above"]);

assertEqual("typesForZone below excludes above-only",
  mod.typesForZone("below").indexOf("scale_degrees"), -1);
assertEqual("typesForZone above includes note_names",
  mod.typesForZone("above").indexOf("note_names") >= 0, true);

assertEqual("can place roman below", mod.canPlace("roman_numerals", "below"), true);
assertEqual("cannot place roman above", mod.canPlace("roman_numerals", "above"), false);

assertEqual("normalize legacy roman mode",
  mod.normalizeSlots({ mode: { roman_numerals: true } }), { above: null, below: "roman_numerals" });
assertEqual("normalize legacy thoroughbass+scale",
  mod.normalizeSlots({ mode: { thoroughbass: true, scale_degrees: true } }),
  { above: "scale_degrees", below: "thoroughbass" });
assertEqual("normalize already-slots passthrough",
  mod.normalizeSlots({ above: "note_names", below: "roman_numerals" }),
  { above: "note_names", below: "roman_numerals" });
assertEqual("normalize empty",
  mod.normalizeSlots({}), { above: null, below: null });

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll analysis_slots assertions passed (" + pass + ")."); }
