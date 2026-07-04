/* Run: node lab/static/js/src/models/input_method_logic.test.js */
"use strict";
var { requireDefault } = require("../../test/require_esm");
var mod = requireDefault(require("./input_method_logic"));
var fail = 0;
function assertEqual(label, actual, expected) {
  var a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { console.log("ok - " + label); }
  else { fail += 1; console.error("FAIL - " + label + "\n  expected: " + e + "\n  actual:   " + a); }
}

// Explicit inputMode wins.
assertEqual("dropdown explicit", mod.resolveInputMethod({ inputMode: "dropdown" }), "dropdown");
assertEqual("text explicit", mod.resolveInputMethod({ inputMode: "text" }), "text");
assertEqual("inputModeFixed beats inputMode", mod.resolveInputMethod({ inputModeFixed: "dropdown", inputMode: "midi" }), "dropdown");
assertEqual("metaInputMode used when others absent", mod.resolveInputMethod({ metaInputMode: "dropdown" }), "dropdown");

// EB61KJ shape (umto_chorale, mode identification, dropdown) -> dropdown.
assertEqual("EB61KJ-like", mod.resolveInputMethod({
  inputModeFixed: "dropdown", inputMode: "dropdown", metaInputMode: "dropdown",
  mode: "identification"
}), "dropdown");

// Mode fallback when no inputMode.
assertEqual("mode identification", mod.resolveInputMethod({ mode: "identification" }), "dropdown");
assertEqual("mode analysis_match", mod.resolveInputMethod({ mode: "analysis_match" }), "dropdown");
assertEqual("mode chorale_identification", mod.resolveInputMethod({ mode: "chorale_identification" }), "dropdown");

// Predicate fallback.
assertEqual("isIdentification", mod.resolveInputMethod({ isIdentification: true }), "dropdown");
assertEqual("isChoraleIdentification", mod.resolveInputMethod({ isChoraleIdentification: true }), "dropdown");

// Note-entry: harmonization / chorale play / empty.
assertEqual("harmonization mode", mod.resolveInputMethod({ mode: "harmonization" }), "note_entry");
assertEqual("playback mode", mod.resolveInputMethod({ mode: "playback" }), "note_entry");
assertEqual("empty -> note_entry", mod.resolveInputMethod({}), "note_entry");
assertEqual("null arg -> note_entry", mod.resolveInputMethod(null), "note_entry");

// usesNoteEntry convenience.
assertEqual("usesNoteEntry dropdown false", mod.usesNoteEntry({ inputMode: "dropdown" }), false);
assertEqual("usesNoteEntry harmonization true", mod.usesNoteEntry({ mode: "harmonization" }), true);

if (fail > 0) { console.error("\n" + fail + " test(s) failed"); process.exit(1); }
console.log("\nAll tests passed");
