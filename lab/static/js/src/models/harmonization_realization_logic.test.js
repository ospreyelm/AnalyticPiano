"use strict";

var { requireDefault } = require("../../test/require_esm");
var logic = requireDefault(require("./harmonization_realization_logic"));

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

// ticksToDurationChunks
assertEqual("quarter exact",
  logic.ticksToDurationChunks(1024),
  [{ type: "q", dots: 0, ticks: 1024 }]);

assertEqual("dotted half exact",
  logic.ticksToDurationChunks(3072),
  [{ type: "h", dots: 1, ticks: 3072 }]);

assertEqual("whole exact",
  logic.ticksToDurationChunks(4096),
  [{ type: "w", dots: 0, ticks: 4096 }]);

assertEqual("quarter + eighth (1536) prefers dotted quarter",
  logic.ticksToDurationChunks(1536),
  [{ type: "q", dots: 1, ticks: 1536 }]);

assertEqual("4096 prefers whole",
  logic.ticksToDurationChunks(3072 + 1024),
  [{ type: "w", dots: 0, ticks: 4096 }]);

assertEqual("eighth (512)",
  logic.ticksToDurationChunks(512),
  [{ type: "8", dots: 0, ticks: 512 }]);

assertEqual("128 ticks = 32nd",
  logic.ticksToDurationChunks(128),
  [{ type: "32", dots: 0, ticks: 128 }]);

assertEqual("greedy split 1280 = q + 16",
  logic.ticksToDurationChunks(1280),
  [
    { type: "q", dots: 0, ticks: 1024 },
    { type: "16", dots: 0, ticks: 256 }
  ]);

assertEqual("undivisible remainder returns null",
  logic.ticksToDurationChunks(100),
  null);

assertEqual("zero ticks returns empty array",
  logic.ticksToDurationChunks(0),
  []);

// spellMidi: octave label follows natural-letter base, not sounding pitch.
assertEqual("spellMidi C4 natural",
  logic.spellMidi(60, { 0: { step: "C", alter: 0 } }),
  { step: "C", alter: 0, octave: 4 });

assertEqual("spellMidi Cb5 (sounds B4 / midi 71)",
  logic.spellMidi(71, { 11: { step: "C", alter: -1 } }),
  { step: "C", alter: -1, octave: 5 });

assertEqual("spellMidi B#4 (sounds C5 / midi 72)",
  logic.spellMidi(72, { 0: { step: "B", alter: 1 } }),
  { step: "B", alter: 1, octave: 4 });

assertEqual("spellMidi Cbb5 (sounds Bb4 / midi 70)",
  logic.spellMidi(70, { 10: { step: "C", alter: -2 } }),
  { step: "C", alter: -2, octave: 5 });

assertEqual("spellMidi B##4 (sounds C#5 / midi 73)",
  logic.spellMidi(73, { 1: { step: "B", alter: 2 } }),
  { step: "B", alter: 2, octave: 4 });

assertEqual("spellMidi returns null when pc missing from map",
  logic.spellMidi(60, { 7: { step: "G", alter: 0 } }),
  null);

// buildPcSpellingMap
var ScoreTimelineStub = {
  events: [],
  buildTimeline: function () { return this.events; }
};
logic.__setScoreTimeline(ScoreTimelineStub);

ScoreTimelineStub.events = [
  { onset: 0, duration: 1024, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 1024, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 1024, midi: 67, step: "G", alter: 0, staff: "bass",   voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 1024, midi: 48, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];

assertEqual("pcMap at offset 0 contains C/E/G",
  logic.buildPcSpellingMap({}, 0),
  { 0: { step: "C", alter: 0 }, 4: { step: "E", alter: 0 }, 7: { step: "G", alter: 0 } });

ScoreTimelineStub.events = [
  { onset: 0, duration: 1024, midi: 66, step: "F", alter: 1, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
assertEqual("pcMap reflects sharp from source",
  logic.buildPcSpellingMap({}, 0),
  { 6: { step: "F", alter: 1 } });

ScoreTimelineStub.events = [
  { onset: 3072, duration: 2048, midi: 74, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 3, headIndex: 0 }
];
assertEqual("pcMap includes notes held across barline",
  logic.buildPcSpellingMap({}, 4),
  { 2: { step: "D", alter: 0 } });

ScoreTimelineStub.events = [
  { onset: 2560, duration: 512, midi: 62, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 5, headIndex: 0 }
];
assertEqual("pcMap honors fractional qb offsets via tick rounding",
  logic.buildPcSpellingMap({}, 2.5),
  { 2: { step: "D", alter: 0 } });

// buildRealization
ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 67, step: "G", alter: 0, staff: "bass",   voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
var meter = { numerator: 4, denominator: 4 };
var targets = [
  { offset: 0, lockedVoices: { B: { midi: 36, pc: 0, spelling: "C" } } }
];

assertEqual("buildRealization: single target, bass dropped, S/A/T spelled",
  logic.buildRealization(
    [{ midi: [36, 60, 64, 67], targetIndex: 0, ts: 1 }],
    targets, {}, meter),
  [{
    measureIndex: 0,
    onset: 0,
    midiNotes: [60, 64, 67],
    spellings: [
      { step: "C", alter: 0, octave: 4 },
      { step: "E", alter: 0, octave: 4 },
      { step: "G", alter: 0, octave: 4 }
    ],
    staff: "treble",
    stemDirection: 1,
    durationTicks: 4096
  }]);

assertEqual("buildRealization: only the bass MIDI instance dropped, not all pc matches",
  logic.buildRealization(
    [{ midi: [36, 48, 60, 64], targetIndex: 0, ts: 1 }],
    targets, {}, meter)[0].midiNotes,
  [48, 60, 64]);

var pcTargets = [
  { offset: 0, lockedVoices: { B: { pc: 0, spelling: "C" } } }
];
assertEqual("buildRealization: missing bass midi falls back to dropping one pc match",
  logic.buildRealization(
    [{ midi: [60, 64, 67], targetIndex: 0, ts: 1 }],
    pcTargets, {}, meter)[0].midiNotes,
  [64, 67]);

ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 62, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 65, step: "F", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 69, step: "A", alter: 0, staff: "bass",   voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
assertEqual("buildRealization: dedupes duplicate targetIndex, keeps most recent",
  logic.buildRealization(
    [
      { midi: [36, 60, 64, 67], targetIndex: 0, ts: 1 },
      { midi: [36, 62, 65, 69], targetIndex: 0, ts: 2 }
    ],
    targets, {}, meter)[0].midiNotes,
  [62, 65, 69]);

var twoTargets = [
  { offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } },
  { offset: 2, lockedVoices: { B: { midi: 36, pc: 0 } } }
];
ScoreTimelineStub.events = [
  { onset: 0, duration: 2048, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 2048, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 2048, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 2048, duration: 2048, midi: 62, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 1, headIndex: 0 },
  { onset: 2048, duration: 2048, midi: 67, step: "G", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 1, headIndex: 0 },
  { onset: 2048, duration: 2048, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 1, headIndex: 0 }
];
var twoOut = logic.buildRealization(
  [
    { midi: [36, 60, 64], targetIndex: 0, ts: 1 },
    { midi: [36, 62, 67], targetIndex: 1, ts: 2 }
  ],
  twoTargets, {}, meter);
assertEqual("buildRealization: first entry durationTicks = next onset",
  twoOut[0].durationTicks, 2048);
assertEqual("buildRealization: last entry durationTicks = measure end",
  twoOut[1].durationTicks, 2048);

var oneAcceptedOut = logic.buildRealization(
  [
    { midi: [36, 60, 64], targetIndex: 0, ts: 1 }
  ],
  twoTargets, {}, meter);
assertEqual("buildRealization: accepted entry durationTicks = next target onset",
  oneAcceptedOut[0].durationTicks, 2048);

ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 4096, duration: 4096, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 1, itemIndex: 0, headIndex: 0 },
  { onset: 4096, duration: 4096, midi: 43, step: "G", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 1, itemIndex: 0, headIndex: 0 }
];
var twoMeasureTargets = [
  { offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } },
  { offset: 4, lockedVoices: { B: { midi: 43, pc: 7 } } }
];
var twoMeasOut = logic.buildRealization(
  [
    { midi: [36, 60], targetIndex: 0, ts: 1 },
    { midi: [43, 64], targetIndex: 1, ts: 2 }
  ],
  twoMeasureTargets, {}, meter);
assertEqual("buildRealization: second target lands in measure 1",
  twoMeasOut[1].measureIndex, 1);
assertEqual("buildRealization: second target onset within its measure",
  twoMeasOut[1].onset, 0);

ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 66, step: "F", alter: 1, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
var sharpOut = logic.buildRealization(
  [{ midi: [36, 66], targetIndex: 0, ts: 1 }],
  [{ offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } }],
  {}, meter);
assertEqual("buildRealization: F# spelled from source",
  sharpOut[0].spellings, [{ step: "F", alter: 1, octave: 4 }]);

ScoreTimelineStub.events = [
  { onset: 8704, duration: 512, midi: 72, step: "C", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 2, itemIndex: 3, headIndex: 0 },
  { onset: 8704, duration: 512, midi: 45, step: "A", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 2, itemIndex: 3, headIndex: 0 }
];
var targetSpellingOut = logic.buildRealization(
  [{ midi: [45, 57, 66, 72], targetIndex: 0, ts: 1 }],
  [{
    offset: 8.5,
    lockedVoices: { B: { midi: 45, pc: 9, spelling: "A" } },
    requiredNoteNames: ["A", "F#", "C"]
  }],
  {}, { numerator: 3, denominator: 4 });
assertEqual("buildRealization: target note names spell accepted chord tones missing from source timeline",
  targetSpellingOut,
  [{
    measureIndex: 2,
    onset: 2560,
    midiNotes: [57, 66, 72],
    spellings: [
      { step: "A", alter: 0, octave: 3 },
      { step: "F", alter: 1, octave: 4 },
      { step: "C", alter: 0, octave: 5 }
    ],
    staff: "treble",
    stemDirection: 1,
    durationTicks: 512
  }]);

ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
assertEqual("buildRealization: skips entry when no upper voices remain",
  logic.buildRealization(
    [{ midi: [36], targetIndex: 0, ts: 1 }],
    [{ offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } }],
    {}, meter),
  []);

assertEqual("buildRealization: returns [] for empty accepted",
  logic.buildRealization([], targets, {}, meter), []);

// staffForTarget: SATB voice -> staff mapping (treble: S/A, bass: T/B),
// matching vexflow_staff_voice_builder.js's SATB_MAP. Only routes to bass
// when exactly one voice is missing and it's T or B — the chordal
// configuration (only bass locked, S/A/T all "missing" as one blob) must
// keep defaulting to treble.
assertEqual("staffForTarget: missing soprano only -> treble",
  logic.staffForTarget({ lockedVoices: { B: {}, A: {}, T: {} } }), "treble");
assertEqual("staffForTarget: missing alto only -> treble",
  logic.staffForTarget({ lockedVoices: { B: {}, S: {}, T: {} } }), "treble");
assertEqual("staffForTarget: missing tenor only -> bass",
  logic.staffForTarget({ lockedVoices: { B: {}, S: {}, A: {} } }), "bass");
assertEqual("staffForTarget: only bass locked (chordal) -> treble",
  logic.staffForTarget({ lockedVoices: { B: {} } }), "treble");

// Per-voice-completion configurations (U5 / plan R6, R9): three of four SATB
// voices locked, one missing. dropLockedVoiceInstances must strip ALL locked
// pitches (not just bass), and the overlay must land on the missing voice's
// staff. A C-major sonority is reused across the three configurations:
// B=48/C3, T=55/G3, A=64/E4, S=72/C5.
var perVoiceMeter = { numerator: 4, denominator: 4 };

ScoreTimelineStub.events = [];
var missingSopranoTargets = [{
  offset: 0,
  lockedVoices: {
    B: { midi: 48, pc: 0, spelling: "C" },
    A: { midi: 64, pc: 4, spelling: "E" },
    T: { midi: 55, pc: 7, spelling: "G" }
  }
}];
assertEqual("buildRealization: missing soprano, correct answer -> overlay is soprano only, treble, no leaked notes",
  logic.buildRealization(
    [{ midi: [48, 55, 64, 72], targetIndex: 0, ts: 1 }],
    missingSopranoTargets, {}, perVoiceMeter),
  [{
    measureIndex: 0,
    onset: 0,
    midiNotes: [72],
    spellings: [{ step: "C", alter: 0, octave: 5 }],
    staff: "treble",
    stemDirection: 1,
    durationTicks: 4096
  }]);

ScoreTimelineStub.events = [];
var missingAltoTargets = [{
  offset: 0,
  lockedVoices: {
    B: { midi: 48, pc: 0, spelling: "C" },
    S: { midi: 72, pc: 0, spelling: "C" },
    T: { midi: 55, pc: 7, spelling: "G" }
  },
  requiredNoteNames: ["E"]
}];
assertEqual("buildRealization: missing alto, correct answer -> overlay is alto only, treble, no leaked notes",
  logic.buildRealization(
    [{ midi: [48, 55, 64, 72], targetIndex: 0, ts: 1 }],
    missingAltoTargets, {}, perVoiceMeter),
  [{
    measureIndex: 0,
    onset: 0,
    midiNotes: [64],
    spellings: [{ step: "E", alter: 0, octave: 4 }],
    staff: "treble",
    stemDirection: -1,
    durationTicks: 4096
  }]);

ScoreTimelineStub.events = [];
var missingTenorTargets = [{
  offset: 0,
  lockedVoices: {
    B: { midi: 48, pc: 0, spelling: "C" },
    S: { midi: 72, pc: 0, spelling: "C" },
    A: { midi: 64, pc: 4, spelling: "E" }
  },
  requiredNoteNames: ["G"]
}];
assertEqual("buildRealization: missing tenor, correct answer -> overlay is tenor only, on BASS staff (not treble), no leaked notes",
  logic.buildRealization(
    [{ midi: [48, 55, 64, 72], targetIndex: 0, ts: 1 }],
    missingTenorTargets, {}, perVoiceMeter),
  [{
    measureIndex: 0,
    onset: 0,
    midiNotes: [55],
    spellings: [{ step: "G", alter: 0, octave: 3 }],
    staff: "bass",
    stemDirection: 1,
    durationTicks: 4096
  }]);

// Regression: the existing bass-only-locked (chordal) configuration must
// keep producing the full S/A/T upper chord on the treble staff, exactly as
// before this fix — dropLockedVoiceInstances/staffForTarget generalize the
// mechanism but must not change behavior when bass is the only locked voice.
ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 67, step: "G", alter: 0, staff: "bass",   voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
assertEqual("regression: bass-only-locked exercise accepted overlay unchanged (full upper chord, treble staff)",
  logic.buildRealization(
    [{ midi: [36, 60, 64, 67], targetIndex: 0, ts: 1 }],
    targets, {}, meter),
  [{
    measureIndex: 0,
    onset: 0,
    midiNotes: [60, 64, 67],
    spellings: [
      { step: "C", alter: 0, octave: 4 },
      { step: "E", alter: 0, octave: 4 },
      { step: "G", alter: 0, octave: 4 }
    ],
    staff: "treble",
    stemDirection: 1,
    durationTicks: 4096
  }]);

// stemDirectionForTarget: SATB voice -> stem convention (S/T up, A/B down).
// Regression for the "alto/bass answer note always stems up" bug: the
// overlay-rendering fix generalized clef/staff routing but originally left
// stem direction hardcoded to up regardless of which voice was missing.
assertEqual("stemDirectionForTarget: missing soprano -> up",
  logic.stemDirectionForTarget({ lockedVoices: { B: {}, A: {}, T: {} } }), 1);
assertEqual("stemDirectionForTarget: missing alto -> down",
  logic.stemDirectionForTarget({ lockedVoices: { B: {}, S: {}, T: {} } }), -1);
assertEqual("stemDirectionForTarget: missing tenor -> up",
  logic.stemDirectionForTarget({ lockedVoices: { B: {}, S: {}, A: {} } }), 1);
assertEqual("stemDirectionForTarget: only bass locked (chordal) -> up (unchanged default)",
  logic.stemDirectionForTarget({ lockedVoices: { B: {} } }), 1);

if (failed > 0) {
  console.log("\n" + failed + " test(s) FAILED");
  process.exit(1);
} else {
  console.log("\nAll tests passed.");
}
