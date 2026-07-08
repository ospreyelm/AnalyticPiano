// lab/static/js/src/components/music/chordal_spelling.test.js
// Run: node lab/static/js/src/components/music/chordal_spelling.test.js
"use strict";
var { requireDefault } = require("../../../test/require_esm");
var S = requireDefault(require("./chordal_spelling"));

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + " got " + JSON.stringify(actual) + " want " + JSON.stringify(expected)); fail++; }
}

// spelledPitchFromName(name, midi)
eq("c#4 from midi 61", S.spelledPitchFromName("c#", 61), { step: "C", alter: 1, octave: 4 });
eq("eb4 from midi 63", S.spelledPitchFromName("eb", 63), { step: "E", alter: -1, octave: 4 });
eq("cb wraps up (B3->Cb4)", S.spelledPitchFromName("cb", 59), { step: "C", alter: -1, octave: 4 });
eq("b# wraps down (C4->B#3)", S.spelledPitchFromName("b#", 60), { step: "B", alter: 1, octave: 3 });

// pitchFromSpellingString(str)
eq("parse C#4", S.pitchFromSpellingString("C#4"), { step: "C", alter: 1, octave: 4 });
eq("parse Eb4", S.pitchFromSpellingString("Eb4"), { step: "E", alter: -1, octave: 4 });
eq("parse Cb5", S.pitchFromSpellingString("Cb5"), { step: "C", alter: -1, octave: 5 });
eq("parse F##3", S.pitchFromSpellingString("F##3"), { step: "F", alter: 2, octave: 3 });
eq("parse junk -> null", S.pitchFromSpellingString("nope"), null);

// keyAwarePitch(midi, spellingTable) — F major table: pc10 -> "bb"
var fMajor = ["c","c#","d","eb","e","f","f#","g","g#","a","bb","b"];
eq("Bb in F major (midi 70)", S.keyAwarePitch(70, fMajor), { step: "B", alter: -1, octave: 4 });
eq("no table -> sharps (midi 70)", S.keyAwarePitch(70, null), { step: "A", alter: 1, octave: 4 });

// resolveChordPitches(chord, spellingTable) -> { <midi>: {step,alter,octave} }
eq("override wins",
   S.resolveChordPitches({ visible: [70], hidden: [], spelling: ["A#4"] }, fMajor),
   { 70: { step: "A", alter: 1, octave: 4 } });
eq("no spelling -> key-aware",
   S.resolveChordPitches({ visible: [70], hidden: [] }, fMajor),
   { 70: { step: "B", alter: -1, octave: 4 } });

// Partial spelling: only some notes overridden; the rest use key-aware default.
eq("partial spelling falls back to default",
   S.resolveChordPitches({ visible: [60, 64], hidden: [], spelling: ["C4"] }, null),
   { 60: { step: "C", alter: 0, octave: 4 }, 64: { step: "E", alter: 0, octave: 4 } });

// Hidden MIDI entries are resolved too (positional order is visible then hidden).
eq("hidden notes are resolved",
   S.resolveChordPitches({ visible: [60], hidden: [70] }, ["c","c#","d","eb","e","f","f#","g","g#","a","bb","b"]),
   { 60: { step: "C", alter: 0, octave: 4 }, 70: { step: "B", alter: -1, octave: 4 } });

// vexKeyToSpellingString: "bb/4" -> "Bb4"
eq("vexKey bb/4 -> Bb4", S.vexKeyToSpellingString("bb/4"), "Bb4");
eq("vexKey c#/5 -> C#5", S.vexKeyToSpellingString("c#/5"), "C#5");
eq("vexKey cb/4 -> Cb4", S.vexKeyToSpellingString("cb/4"), "Cb4");
eq("vexKey e/4 -> E4", S.vexKeyToSpellingString("e/4"), "E4");
eq("vexKey junk -> null", S.vexKeyToSpellingString("nope"), null);

// pitchDictToVexKey: {step,alter,octave} -> VexFlow "step/acc/octave" (U5)
eq("pitchDict E- 4 -> eb/4", S.pitchDictToVexKey({ step: "E", alter: -1, octave: 4 }), "eb/4");
eq("pitchDict C# 4 -> c#/4", S.pitchDictToVexKey({ step: "C", alter: 1, octave: 4 }), "c#/4");
eq("pitchDict G natural 4 -> g/4", S.pitchDictToVexKey({ step: "G", alter: 0, octave: 4 }), "g/4");
eq("pitchDict C## 4 -> c##/4", S.pitchDictToVexKey({ step: "C", alter: 2, octave: 4 }), "c##/4");
eq("pitchDict Bbb 4 -> bbb/4", S.pitchDictToVexKey({ step: "B", alter: -2, octave: 4 }), "bbb/4");
eq("pitchDict Eb 3 -> eb/3", S.pitchDictToVexKey({ step: "E", alter: -1, octave: 3 }), "eb/3");

// Eb major triad round-trip — the exact reported bug (D#-G-Bb-Eb). Recorded
// spelling must round-trip through resolveChordPitches + pitchDictToVexKey,
// not be re-derived to a sharp spelling.
(function () {
  var resolved = S.resolveChordPitches(
    { visible: [63, 67, 70], hidden: [], spelling: ["eb/4", "g/4", "bb/4"] },
    null
  );
  eq("Eb triad: midi 63 -> eb/4", S.pitchDictToVexKey(resolved[63]), "eb/4");
  eq("Eb triad: midi 67 -> g/4", S.pitchDictToVexKey(resolved[67]), "g/4");
  eq("Eb triad: midi 70 -> bb/4", S.pitchDictToVexKey(resolved[70]), "bb/4");
})();

// Augmented triad: the raised 5th stays G# (sharp), not its enharmonic Ab
// neighbor — the failure mode that produced the reported bug.
(function () {
  var resolved = S.resolveChordPitches(
    { visible: [48, 64, 68, 72], hidden: [], spelling: ["c/3", "e/4", "g#/4", "c/5"] },
    null
  );
  eq("Aug triad: raised 5th midi 68 -> g#/4", S.pitchDictToVexKey(resolved[68]), "g#/4");
  eq("Aug triad: doubled root midi 72 -> c/5", S.pitchDictToVexKey(resolved[72]), "c/5");
})();

// Doubled pitch class at two octaves resolves independently (byMidi keyed by
// MIDI value, not letter name).
(function () {
  var resolved = S.resolveChordPitches(
    { visible: [60, 72], hidden: [], spelling: ["c/4", "c/5"] },
    null
  );
  eq("doubled C: midi 60 -> c/4", S.pitchDictToVexKey(resolved[60]), "c/4");
  eq("doubled C: midi 72 -> c/5", S.pitchDictToVexKey(resolved[72]), "c/5");
})();

// Keyboard-split chord (KTD5): getNoteName passes the FULL chord as `notes`
// (all_note_nums) with the full-chord spelling, then looks up each per-stave
// note by MIDI value. So a treble-only subset of notes resolves correctly from
// the one full-chord spelling — resolution is by MIDI value in the byMidi map,
// not a positional index into a per-stave array.
(function () {
  var resolved = S.resolveChordPitches(
    { visible: [48, 64, 67, 72], hidden: [], spelling: ["c/3", "e/4", "g/4", "c/5"] },
    null
  );
  // Treble clef sees only 64,67,72 — look each up from the full-chord map.
  eq("split treble: midi 64 -> e/4", S.pitchDictToVexKey(resolved[64]), "e/4");
  eq("split treble: midi 67 -> g/4", S.pitchDictToVexKey(resolved[67]), "g/4");
  eq("split treble: midi 72 -> c/5", S.pitchDictToVexKey(resolved[72]), "c/5");
  // Bass clef sees 48 — also resolvable from the same full-chord map.
  eq("split bass: midi 48 -> c/3", S.pitchDictToVexKey(resolved[48]), "c/3");
})();

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
