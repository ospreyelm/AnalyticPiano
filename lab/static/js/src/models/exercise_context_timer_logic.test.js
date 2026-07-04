"use strict";

var { requireDefault } = require("../../test/require_esm");
var TimerLogic = requireDefault(require("./exercise_context_timer_logic"));

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + "\n    got:  " + JSON.stringify(actual) + "\n    want: " + JSON.stringify(expected)); fail++; }
}

// --- createTimerState ---
var ts = TimerLogic.createTimerState();
eq("start=null",        ts.start,          null);
eq("end=null",          ts.end,            null);
eq("duration=null",     ts.duration,       null);
eq("durationString=''", ts.durationString, "");
eq("minTempo=null",     ts.minTempo,       null);
eq("maxTempo=null",     ts.maxTempo,       null);
eq("tempoSD=null",      ts.tempoSD,        null);
eq("tempoRating=null",  ts.tempoRating,    null);
eq("timepoints={}",     ts.timepoints,     {});
eq("timeIntervals=[]",  ts.timeIntervals,  []);

// --- formatDurationString ---
eq("0ms → '0&Prime;'",                    TimerLogic.formatDurationString(0),       "0&Prime;");
eq("30000ms → '30&Prime;'",               TimerLogic.formatDurationString(30000),   "30&Prime;");
eq("60000ms → '1&prime;&nbsp;0&Prime;'",  TimerLogic.formatDurationString(60000),   "1&prime;&nbsp;0&Prime;");
eq("90000ms → '1&prime;&nbsp;30&Prime;'", TimerLogic.formatDurationString(90000),   "1&prime;&nbsp;30&Prime;");
eq("3661000ms → '61&prime;&nbsp;1&Prime;'", TimerLogic.formatDurationString(3661000), "61&prime;&nbsp;1&Prime;");

// --- computeTempoIntervals ---
eq("empty timepoints → []",        TimerLogic.computeTempoIntervals({}),             []);
eq("one timepoint → []",           TimerLogic.computeTempoIntervals({0: 100}),       []);
eq("two timepoints → [500]",       TimerLogic.computeTempoIntervals({0: 100, 1: 600}), [500]);
eq("three timepoints → [500,500]", TimerLogic.computeTempoIntervals({0: 100, 1: 600, 2: 1100}), [500, 500]);
// keys are sorted numerically not lexically
eq("out-of-order keys → [500,500]",
  TimerLogic.computeTempoIntervals({2: 1200, 0: 200, 1: 700}), [500, 500]);

// --- SEMIBREVE_FRACTION ---
eq("SEMIBREVE_FRACTION.w = 1",    TimerLogic.SEMIBREVE_FRACTION["w"], 1);
eq("SEMIBREVE_FRACTION.h = 0.5",  TimerLogic.SEMIBREVE_FRACTION["h"], 0.5);
eq("SEMIBREVE_FRACTION.q = 0.25", TimerLogic.SEMIBREVE_FRACTION["q"], 0.25);
eq("SEMIBREVE_FRACTION.e = 0.125",TimerLogic.SEMIBREVE_FRACTION["e"], 0.125);

// --- computeSemibreveCount ---
var chords3 = [
  { settings: { rhythm: "q" } },
  { settings: { rhythm: "h" } },
  { settings: { rhythm: "w" } },
];
// 3 chords, 3 input items: min=3 → [0.25, 0.5, 1.0] → pop last → [0.25, 0.5]
eq("3 chords 3 items → [0.25, 0.5]",
  TimerLogic.computeSemibreveCount(chords3, 3, "q"), [0.25, 0.5]);
// input shorter than chords → use input count
eq("3 chords 2 items → min=2 → [0.25]",
  TimerLogic.computeSemibreveCount(chords3, 2, "q"), [0.25]);
// no rhythm on chord → fall back to defaultRhythmValue
var chordsNoRhythm = [{ settings: {} }, { settings: {} }];
eq("no rhythm → default 'q'=0.25 → pop → [0.25]",
  TimerLogic.computeSemibreveCount(chordsNoRhythm, 2, "q"), [0.25]);
// empty → []
eq("empty chords → []",
  TimerLogic.computeSemibreveCount([], 0, "q"), []);

// --- computeCentisemibrevesPerMin ---
// 1000ms interval, 1.0 semibreve: round(1.0 * 6000000 / 1000) = 6000
eq("1000ms 1.0sv → [6000,6000]",
  TimerLogic.computeCentisemibrevesPerMin([1000, 1000], [1.0, 1.0]), [6000, 6000]);
// mismatched lengths → []
eq("mismatched lengths → []",
  TimerLogic.computeCentisemibrevesPerMin([1000], [1.0, 0.5]), []);
eq("both empty → []",
  TimerLogic.computeCentisemibrevesPerMin([], []), []);

// --- computeTempoStats ---
// [100,200,300]: mean=200→round(200/10)/10=2.0; sampleSD=100→round(100)/100=1.0; min=1.0; max=3.0
var stats = TimerLogic.computeTempoStats([100, 200, 300]);
eq("tempoMean of [100,200,300]", stats.tempoMean, 2.0);
eq("tempoSD of [100,200,300]",   stats.tempoSD,   1.0);
eq("minTempo of [100,200,300]",  stats.minTempo,  1.0);
eq("maxTempo of [100,200,300]",  stats.maxTempo,  3.0);
// [6000,6000,6000]: mean=6000→60.0; sd=0; min=max=60.0
var statsFlat = TimerLogic.computeTempoStats([6000, 6000, 6000]);
eq("flat tempoMean=60.0",  statsFlat.tempoMean, 60.0);
eq("flat tempoSD=0",       statsFlat.tempoSD,   0);
eq("flat minTempo=60.0",   statsFlat.minTempo,  60.0);
eq("flat maxTempo=60.0",   statsFlat.maxTempo,  60.0);

// --- computeTempoRating ---
// SD=0 → 5 stars
eq("SD=0 → 5",            TimerLogic.computeTempoRating(0,   100), 5);
// floor(100/2)=50 → "110010" 6 chars → 5 → capped 5
eq("ratio=50 → 5",        TimerLogic.computeTempoRating(2,   100), 5);
// floor(100/25)=4 → "100" 3 chars → 2
eq("ratio=4 → 2",         TimerLogic.computeTempoRating(25,  100), 2);
// floor(100/100)=1 → "1" 1 char → 0 → max(1,0)=1
eq("ratio=1 → 1",         TimerLogic.computeTempoRating(100, 100), 1);
// floor(700/100)=7 → "111" 3 chars → 2
eq("ratio=7 → 2",         TimerLogic.computeTempoRating(100, 700), 2);
// floor(100/12.5)=8 → "1000" 4 chars → 3
eq("ratio=8 → 3",         TimerLogic.computeTempoRating(12.5, 100), 3);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
