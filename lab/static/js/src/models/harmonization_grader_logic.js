"use strict";

function uniq(arr) {
  var seen = {};
  var result = [];
  for (var i = 0; i < arr.length; i += 1) {
    if (!seen[arr[i]]) {
      seen[arr[i]] = true;
      result.push(arr[i]);
    }
  }
  return result;
}

function pitchClassForMidi(midi) {
  return ((midi % 12) + 12) % 12;
}

function includes(arr, value) {
  return arr.indexOf(value) !== -1;
}

function harmonizationMatch(target, activeMidi) {
  var active = (activeMidi || []).slice().sort(function (a, b) { return a - b; });
  var reasons = [];
  var note = {};
  var activePcs = uniq(active.map(pitchClassForMidi));
  var locked = target.lockedVoices || {};
  var policy = target.voiceCountPolicy || { min: 3, max: 4 };

  if (locked.B && !includes(activePcs, locked.B.pc)) {
    reasons.push("wrong_bass");
  }
  if (locked.S) {
    if (typeof locked.S.midi === "number") {
      if (!includes(active, locked.S.midi)) reasons.push("wrong_locked_soprano");
    } else if (!includes(activePcs, locked.S.pc)) {
      reasons.push("wrong_locked_soprano");
    }
  }

  for (var i = 0; i < active.length; i += 1) {
    if (!includes(target.allowedPcs || [], pitchClassForMidi(active[i]))) {
      reasons.push("illegal_pc");
      note[active[i]] = "incorrect";
    } else {
      note[active[i]] = "correct";
    }
  }

  for (var r = 0; r < (target.requiredUpperPcs || []).length; r += 1) {
    if (!includes(activePcs, target.requiredUpperPcs[r])) {
      reasons.push("missing_required_pc");
    }
  }

  if (policy.min != null && active.length < policy.min) {
    reasons.push("too_few_voices");
  }
  if (policy.max != null && active.length > policy.max) {
    reasons.push("too_many_voices");
  }

  var hardReasons = reasons.filter(function (r) {
    return r !== "missing_required_pc" && r !== "too_few_voices";
  });
  var state = hardReasons.length ? "incorrect" : reasons.length ? "partial" : "correct";

  return {
    state: state,
    reasons: uniq(reasons),
    accepted: state === "correct",
    activeMidi: active,
    note: note,
    target: target
  };
}

// ---------------------------------------------------------------------------
// Held-note tracker with release grace window
// ---------------------------------------------------------------------------

function createHeldNoteTracker(options) {
  options = options || {};
  var releaseGraceMs = options.releaseGraceMs == null ? 120 : options.releaseGraceMs;
  var held = {};
  var releasedAt = {};

  return {
    noteOn: function (midi) {
      held[midi] = true;
      delete releasedAt[midi];
    },
    noteOff: function (midi, atMs) {
      if (held[midi]) {
        releasedAt[midi] = atMs;
      }
    },
    activeMidi: function (nowMs) {
      var result = [];
      var keys = Object.keys(held);
      for (var i = 0; i < keys.length; i += 1) {
        var midi = parseInt(keys[i], 10);
        if (releasedAt[midi] == null) {
          result.push(midi);
        } else if (nowMs - releasedAt[midi] <= releaseGraceMs) {
          result.push(midi);
        } else {
          delete held[midi];
          delete releasedAt[midi];
        }
      }
      return result.sort(function (a, b) { return a - b; });
    },
    reset: function () {
      held = {};
      releasedAt = {};
    }
  };
}

var exports = {
  harmonizationMatch: harmonizationMatch,
  createHeldNoteTracker: createHeldNoteTracker
};

if (typeof define === "function" && define.amd) {
  define([], function () { return exports; });
} else if (typeof module !== "undefined") {
  module.exports = exports;
}
