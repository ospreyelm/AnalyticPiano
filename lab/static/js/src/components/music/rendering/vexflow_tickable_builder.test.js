/*
 * Run: node lab/static/js/src/components/music/rendering/vexflow_tickable_builder.test.js
 */
"use strict";

var assert = require("assert");
var { requireDefault } = require("../../../../test/require_esm");
var TickableBuilder = requireDefault(require("./vexflow_tickable_builder"));

function restItem() {
  return { kind: "rest", duration: { type: "quarter", dots: 0 } };
}

function noteItem(step, alter, octave) {
  return {
    kind: "note",
    pitch: { step: step, alter: alter || 0, octave: octave },
    duration: { type: "quarter", dots: 0 },
  };
}

function chordItem(notes) {
  return {
    kind: "chord",
    notes: notes.map(function (n) {
      return { pitch: { step: n[0], alter: n[1] || 0, octave: n[2] } };
    }),
    duration: { type: "quarter", dots: 0 },
  };
}

function testRestItemBecomesRestTickable() {
  var rest = TickableBuilder.itemToTickable("treble", restItem(), 0, null, {}, 0, 0, true, false, {}, {});
  assert.strictEqual(rest._isRest, true);
  assert.strictEqual(rest._onset, 0);
}

function testNoteItemBecomesNoteTickableWithCorrectKey() {
  var note = TickableBuilder.itemToTickable("treble", noteItem("C", 0, 4), 0, null, {}, 0, 0, true, false, {}, {});
  assert.deepStrictEqual(note.getKeys(), ["c/4"]);
}

function testSharpNoteAddsAccidentalWhenNotInKeySignature() {
  var note = TickableBuilder.itemToTickable("treble", noteItem("F", 1, 4), 0, null, {}, 0, 0, true, false, {}, {});
  assert.deepStrictEqual(note.getKeys(), ["f#/4"]);
  assert.strictEqual(note.getModifiers().length, 1);
}

function testSharpNoteSkipsAccidentalWhenKeySignatureAlreadyHasIt() {
  // F# key signature: F is already sharped, so an F# note needs no accidental.
  var note = TickableBuilder.itemToTickable("treble", noteItem("F", 1, 4), 0, null, { F: 1 }, 0, 0, true, false, {}, {});
  assert.strictEqual(note.getModifiers().length, 0);
}

function testBarAlterationsCarriesForwardWithinMeasure() {
  var barAlterations = {};
  // First F# in the bar gets an explicit accidental...
  TickableBuilder.itemToTickable("treble", noteItem("F", 1, 4), 0, null, {}, 0, 0, true, false, {}, barAlterations);
  // ...a second F# later in the same bar should not need a repeated accidental.
  var second = TickableBuilder.itemToTickable("treble", noteItem("F", 1, 4), 0, null, {}, 100, 0, true, false, {}, barAlterations);
  assert.strictEqual(second.getModifiers().length, 0);
}

function testChordItemBecomesChordTickableWithAllKeys() {
  var chord = TickableBuilder.itemToTickable("treble", chordItem([["C", 0, 4], ["E", 0, 4], ["G", 0, 4]]), 0, null, {}, 0, 0, true, false, {}, {});
  assert.deepStrictEqual(chord.getKeys(), ["c/4", "e/4", "g/4"]);
}

function testUnknownItemKindReturnsNull() {
  var result = TickableBuilder.itemToTickable("treble", { kind: "bogus" }, 0, null, {}, 0, 0, true, false, {}, {});
  assert.strictEqual(result, null);
}

testRestItemBecomesRestTickable();
testNoteItemBecomesNoteTickableWithCorrectKey();
testSharpNoteAddsAccidentalWhenNotInKeySignature();
testSharpNoteSkipsAccidentalWhenKeySignatureAlreadyHasIt();
testBarAlterationsCarriesForwardWithinMeasure();
testChordItemBecomesChordTickableWithAllKeys();
testUnknownItemKindReturnsNull();

function testBuildVoiceAllowsIncompleteVoices() {
  var note = TickableBuilder.itemToTickable("treble", noteItem("C", 0, 4), 0, null, {}, 0, 0, true, false, {}, {});
  var voice = TickableBuilder.buildVoice({ num_beats: 4, beat_value: 4 }, [note]);
  assert.ok(voice);
  // SOFT mode permits a voice with fewer ticks than the time signature requires
  // (pickup measures) without throwing.
  assert.doesNotThrow(function () { voice.getTicksUsed(); });
}

testBuildVoiceAllowsIncompleteVoices();

function testBuildHarmonizationOverlayVoiceReturnsNullWithoutEntries() {
  var voice = TickableBuilder.buildHarmonizationOverlayVoice([], 4096, { num_beats: 4, beat_value: 4 }, {}, null);
  assert.strictEqual(voice, null);
}

testBuildHarmonizationOverlayVoiceReturnsNullWithoutEntries();

function testBuildHarmonizationOverlayVoiceWithMissingAndPartialSpellings() {
  var entries = [
    {
      onset: 0,
      durationTicks: 2048,
      midiNotes: [60, 64, 67], // C4, E4, G4
      spellings: null
    }
  ];
  var voice = TickableBuilder.buildHarmonizationOverlayVoice(entries, 4096, { num_beats: 4, beat_value: 4 }, {}, null);
  assert.ok(voice, "should return a valid voice for null spellings");

  var partialEntries = [
    {
      onset: 0,
      durationTicks: 2048,
      midiNotes: [60, 64, 67], // C4, E4, G4
      spellings: [{ step: "c", alter: 0, octave: 4 }]
    }
  ];
  var voice2 = TickableBuilder.buildHarmonizationOverlayVoice(partialEntries, 4096, { num_beats: 4, beat_value: 4 }, {}, null);
  assert.ok(voice2, "should return a valid voice for partial/shorter spellings");
}

testBuildHarmonizationOverlayVoiceWithMissingAndPartialSpellings();

// Regression: in analysis_match mode, resolveChordNoteStyles() sets a
// transparent base style on the chord (which VexFlow's StaveNote.setStyle
// propagates to the shared Stem). setKeyStyle() only recolors individual
// noteheads, never the stem, so a correctly-played chord used to show a
// black notehead with an invisible stem forever. itemToTickable() must
// call chord.setStemStyle() once any key in the chord has been played.
function testChordRevealsStemOnceAnyKeyPlayed() {
  var idState = { nextId: 0, playedNoteIds: new Set([0]) }; // key 0 already played
  var item = chordItem([["C", 0, 4], ["E", 0, 4]]);
  var chord = TickableBuilder.itemToTickable("treble", item, 0, idState, {}, 0, 0, true, true, {}, {});
  assert.deepStrictEqual(
    chord.getStemStyle(),
    { fillStyle: "#000000", strokeStyle: "#000000" },
    "stem should be revealed once any key in the chord has been played"
  );
}

testChordRevealsStemOnceAnyKeyPlayed();

function testChordKeepsStemHiddenWhenNothingPlayedYet() {
  var idState = { nextId: 0, playedNoteIds: new Set() };
  var item = chordItem([["C", 0, 4], ["E", 0, 4]]);
  var chord = TickableBuilder.itemToTickable("treble", item, 0, idState, {}, 0, 0, true, true, {}, {});
  assert.deepStrictEqual(
    chord.getStemStyle(),
    { fillStyle: "transparent", strokeStyle: "transparent" },
    "stem should match the hidden notehead base style until something is played"
  );
}

testChordKeepsStemHiddenWhenNothingPlayedYet();

console.log("vexflow_tickable_builder tests passed");
