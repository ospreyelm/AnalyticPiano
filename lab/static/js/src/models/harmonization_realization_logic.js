import ST from "app/components/music/score_timeline";

"use strict";


// Supported atoms in descending tick order. Each atom matches the CIR duration
// shape used by score_timeline.js and vexflow_adapter.js.
var ATOMS = [
  { type: "w",  dots: 0, ticks: 4096 },
  { type: "h",  dots: 1, ticks: 3072 },
  { type: "h",  dots: 0, ticks: 2048 },
  { type: "q",  dots: 1, ticks: 1536 },
  { type: "q",  dots: 0, ticks: 1024 },
  { type: "8",  dots: 1, ticks: 768 },
  { type: "8",  dots: 0, ticks: 512 },
  { type: "16", dots: 1, ticks: 384 },
  { type: "16", dots: 0, ticks: 256 },
  { type: "32", dots: 0, ticks: 128 }
];

function pitchClassForMidi(midi) {
  return ((midi % 12) + 12) % 12;
}

function pitchClassForSpelling(step, alter) {
  var base = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[String(step || "").toUpperCase()];
  if (typeof base !== "number") return null;
  return ((base + (alter || 0)) % 12 + 12) % 12;
}

function parseNoteNameSpelling(name) {
  var match = String(name || "").match(/^([A-Ga-g])([#b]*)/);
  if (!match) return null;

  var acc = match[2] || "";
  var alter = 0;
  for (var i = 0; i < acc.length; i += 1) {
    alter += acc.charAt(i) === "#" ? 1 : -1;
  }

  return { step: match[1].toUpperCase(), alter: alter };
}

function ticksToDurationChunks(ticks) {
  if (ticks === 0) return [];
  var remaining = ticks;
  var out = [];
  while (remaining > 0) {
    var picked = null;
    for (var i = 0; i < ATOMS.length; i += 1) {
      if (ATOMS[i].ticks <= remaining) {
        picked = ATOMS[i];
        break;
      }
    }
    if (!picked) return null;
    out.push({ type: picked.type, dots: picked.dots, ticks: picked.ticks });
    remaining -= picked.ticks;
  }
  return out;
}

function spellMidi(midi, pcMap) {
  var entry = pcMap[pitchClassForMidi(midi)];
  if (!entry) return null;

  // Octave label follows the natural letter, not the sounding pitch. Subtract
  // alter to land on the letter's natural MIDI, then convert to octave label.
  var letterBaseMidi = midi - entry.alter;
  var octave = Math.floor(letterBaseMidi / 12) - 1;
  return { step: entry.step, alter: entry.alter, octave: octave };
}

var _ScoreTimeline = ST;


function getScoreTimeline() {
  if (_ScoreTimeline) return _ScoreTimeline;
  if (typeof require === "function" && typeof module !== "undefined") {
    try {
      _ScoreTimeline = require("../components/music/score_timeline");
    } catch (e) {
      _ScoreTimeline = null;
    }
  }
  return _ScoreTimeline;
}

function __setScoreTimeline(stub) {
  _ScoreTimeline = stub;
}

function buildPcSpellingMap(score, targetOffsetQb) {
  var ST = getScoreTimeline();
  if (!ST || typeof ST.buildTimeline !== "function") return {};

  var timeline = ST.buildTimeline(score) || [];
  var targetTick = Math.round(targetOffsetQb * 1024);
  var pcMap = {};

  for (var i = 0; i < timeline.length; i += 1) {
    var ev = timeline[i];
    if (typeof ev.midi !== "number") continue;
    if (!(ev.onset <= targetTick && ev.onset + ev.duration > targetTick)) continue;

    var evPc = pitchClassForMidi(ev.midi);
    if (!pcMap[evPc]) {
      pcMap[evPc] = { step: ev.step, alter: ev.alter || 0 };
    }
  }

  return pcMap;
}

function addSpellingToPcMap(pcMap, spelling) {
  if (!spelling) return;
  var pc = pitchClassForSpelling(spelling.step, spelling.alter || 0);
  if (pc === null || pcMap[pc]) return;
  pcMap[pc] = { step: spelling.step, alter: spelling.alter || 0 };
}

function addSpellingNameToPcMap(pcMap, name) {
  addSpellingToPcMap(pcMap, parseNoteNameSpelling(name));
}

function buildTargetPcSpellingMap(target) {
  var pcMap = {};
  if (!target) return pcMap;

  addSpellingNameToPcMap(pcMap, target.bassSpelling);

  var lockedVoices = target.lockedVoices || {};
  Object.keys(lockedVoices).forEach(function (voiceId) {
    addSpellingNameToPcMap(pcMap, lockedVoices[voiceId] && lockedVoices[voiceId].spelling);
  });

  (target.requiredNoteNames || []).forEach(function (name) {
    addSpellingNameToPcMap(pcMap, name);
  });

  return pcMap;
}

function mergePcSpellingMaps(primary, fallback) {
  var out = {};
  var key;
  primary = primary || {};
  fallback = fallback || {};

  for (key in primary) {
    if (Object.prototype.hasOwnProperty.call(primary, key)) {
      out[key] = primary[key];
    }
  }
  for (key in fallback) {
    if (Object.prototype.hasOwnProperty.call(fallback, key) && !out[key]) {
      out[key] = fallback[key];
    }
  }
  return out;
}

function measureTickTotal(meter) {
  var num = (meter && meter.numerator) || 4;
  var den = (meter && meter.denominator) || 4;
  return num * (4096 / den);
}

// Strips one pitch instance per locked voice from a merged commit snapshot
// (buildCommitSnapshot's locked-voice pitches + the student's entered
// pitch(es)), leaving only the student-entered answer. Generalizes the old
// bass-only stripping to an arbitrary locked-voice set — correct for both
// the current single-bass-locked chord-entry configuration (one voice
// stripped) and the per-voice-completion variant (three voices stripped:
// bass plus whichever two of S/A/T are given). Mirrors the locked-voice
// exclusion `click_note.js#_commit` already applies on the rejected-state
// path ("must not appear in the ... overlay").
function dropFirstMatch(arr, predicate) {
  var dropped = false;
  return arr.filter(function (item) {
    if (!dropped && predicate(item)) {
      dropped = true;
      return false;
    }
    return true;
  });
}

function dropLockedVoiceInstances(midiArr, target) {
  var lockedVoices = (target && target.lockedVoices) || {};
  var remaining = midiArr.slice();

  Object.keys(lockedVoices).forEach(function (voiceId) {
    var locked = lockedVoices[voiceId];
    var lockedMidi = locked && locked.midi;
    var lockedPc = locked && locked.pc;

    if (typeof lockedMidi === "number") {
      remaining = dropFirstMatch(remaining, function (m) {
        return m === lockedMidi;
      });
    } else if (typeof lockedPc === "number") {
      remaining = dropFirstMatch(remaining, function (m) {
        return pitchClassForMidi(m) === lockedPc;
      });
    }
  });

  return remaining;
}

// SATB voice-id -> staff mapping (treble: S/A, bass: T/B). Single source of
// truth shared with vexflow_staff_voice_builder.js, which imports this
// module for it. Determines which staff the accepted-answer overlay belongs
// on. When exactly one SATB voice is missing from target.lockedVoices (the
// per-voice-completion configurations), the overlay renders on that voice's
// staff. Otherwise (the current chord-entry configuration, where only bass
// is locked and S/A/T are all missing as one blob) it defaults to treble,
// preserving existing behavior exactly.
var SATB_MAP = { treble: ["S", "A"], bass: ["T", "B"] };
var ALL_SATB_VOICES = SATB_MAP.treble.concat(SATB_MAP.bass);
// Outer voices of each staff (soprano on treble, tenor on bass) stem up;
// inner voices (alto, bass) stem down — standard SATB engraving convention.
var UP_STEM_VOICES = [SATB_MAP.treble[0], SATB_MAP.bass[0]];

function missingVoiceForTarget(target) {
  var lockedVoices = (target && target.lockedVoices) || {};
  var missing = ALL_SATB_VOICES.filter(function (voiceId) {
    return !Object.prototype.hasOwnProperty.call(lockedVoices, voiceId);
  });
  return missing.length === 1 ? missing[0] : null;
}

function staffForTarget(target) {
  var missing = missingVoiceForTarget(target);
  if (missing && SATB_MAP.bass.indexOf(missing) !== -1) {
    return "bass";
  }
  return "treble";
}

// Stem direction for the answer-overlay note, per SATB convention. Falls
// back to up (1) when there isn't exactly one missing voice (the current
// chord-entry configuration, where the overlay represents multiple upper
// voices as one blob) — preserves existing behavior exactly for that case.
// If the exercise is chordal (i.e. score_kind is "chordal"), it returns "auto".
function stemDirectionForTarget(target, score) {
  var missing = missingVoiceForTarget(target);
  if (!missing) {
    var isChordal = !!(score && score.umto && score.umto.metadata && score.umto.metadata.score_kind === "chordal");
    return isChordal ? "auto" : 1;
  }
  return UP_STEM_VOICES.indexOf(missing) !== -1 ? 1 : -1;
}

function buildRealization(accepted, targets, score, meter) {
  if (!accepted || !accepted.length) return [];
  targets = targets || [];

  var measureTotal = measureTickTotal(meter);
  var byIndex = {};

  for (var i = 0; i < accepted.length; i += 1) {
    var ent = accepted[i];
    var existing = byIndex[ent.targetIndex];
    if (!existing || (ent.ts || 0) >= (existing.ts || 0)) {
      byIndex[ent.targetIndex] = ent;
    }
  }

  var raw = [];
  var indices = Object.keys(byIndex)
    .map(function (k) { return parseInt(k, 10); })
    .sort(function (a, b) { return a - b; });

  for (var k = 0; k < indices.length; k += 1) {
    var ti = indices[k];
    var target = targets[ti];
    if (!target || typeof target.offset !== "number") continue;

    var absOffsetQb = target.offset;
    var absOffsetTicks = Math.round(absOffsetQb * 1024);
    var measureIndex = Math.floor(absOffsetTicks / measureTotal);
    var onsetWithinMeasure = absOffsetTicks - (measureIndex * measureTotal);

    var upperMidi = dropLockedVoiceInstances(byIndex[ti].midi || [], target);
    if (!upperMidi.length) continue;
    upperMidi = upperMidi.slice().sort(function (a, b) { return a - b; });
    var staff = staffForTarget(target);
    var stemDirection = stemDirectionForTarget(target, score);

    var pcMap = mergePcSpellingMaps(
      buildPcSpellingMap(score, absOffsetQb),
      buildTargetPcSpellingMap(target)
    );

    // Not every legally-allowed chord tone has a recorded spelling: the target
    // only carries the bass and its one requiredUpperPc, and buildPcSpellingMap
    // deliberately excludes the answer voice being realized. Per
    // docs/music-theory-canon.md ("Pitch spelling and octave are load-bearing
    // data"), a missing spelling must not be guessed from bare pitch-class.
    // Omit just that note (and say why) rather than silently dropping the
    // whole chord.
    var spelledMidi = [];
    var spellings = [];
    upperMidi.forEach(function (m) {
      var spelling = spellMidi(m, pcMap);
      if (!spelling) {
        console.warn(
          "[harmonization_realization_logic] no recorded spelling for pc " +
          pitchClassForMidi(m) + " (midi " + m + ") at target index " + ti +
          " — omitting this note from the realized chord rather than guessing its spelling."
        );
        return;
      }
      spelledMidi.push(m);
      spellings.push(spelling);
    });
    if (!spelledMidi.length) continue;

    raw.push({
      measureIndex: measureIndex,
      onset: onsetWithinMeasure,
      _absOnsetTicks: absOffsetTicks,
      _targetIndex: ti,
      midiNotes: spelledMidi,
      spellings: spellings,
      staff: staff,
      stemDirection: stemDirection
    });
  }

  raw.sort(function (a, b) {
    if (a.measureIndex !== b.measureIndex) return a.measureIndex - b.measureIndex;
    return a.onset - b.onset;
  });

  for (var j = 0; j < raw.length; j += 1) {
    var cur = raw[j];
    var nextTargetOnset = null;
    for (var nt = 0; nt < targets.length; nt += 1) {
      if (!targets[nt] || typeof targets[nt].offset !== "number") continue;
      var nextAbsTicks = Math.round(targets[nt].offset * 1024);
      if (nextAbsTicks <= cur._absOnsetTicks) continue;
      var nextMeasureIndex = Math.floor(nextAbsTicks / measureTotal);
      if (nextMeasureIndex !== cur.measureIndex) continue;
      var nextOnset = nextAbsTicks - (nextMeasureIndex * measureTotal);
      if (nextTargetOnset === null || nextOnset < nextTargetOnset) {
        nextTargetOnset = nextOnset;
      }
    }
    cur.durationTicks = nextTargetOnset !== null
      ? nextTargetOnset - cur.onset
      : measureTotal - cur.onset;
    delete cur._absOnsetTicks;
    delete cur._targetIndex;
  }

  return raw;
}

var exports = {
  ticksToDurationChunks: ticksToDurationChunks,
  spellMidi: spellMidi,
  buildPcSpellingMap: buildPcSpellingMap,
  buildRealization: buildRealization,
  staffForTarget: staffForTarget,
  stemDirectionForTarget: stemDirectionForTarget,
  SATB_MAP: SATB_MAP,
  __setScoreTimeline: __setScoreTimeline
};

export default exports;

