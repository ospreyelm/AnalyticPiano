/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.KeyboardRangeLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function addMidi(out, seen, value) {
    var midi = Number(value);
    if (!isFinite(midi)) return;
    if (midi < 0 || midi > 127) return;
    if (seen[midi]) return;
    seen[midi] = true;
    out.push(midi);
  }

  function collectFromTargetList(out, seen, list) {
    if (!list || !list.length) return;
    for (var i = 0; i < list.length; i++) {
      addMidi(out, seen, list[i]);
    }
  }

  function collectTargetMidis(definition, timeline) {
    var out = [];
    var seen = {};
    var grading = definition && definition.getGrading
      ? definition.getGrading()
      : definition && definition.grading;

    if (Array.isArray(grading)) {
      for (var i = 0; i < grading.length; i++) {
        collectFromTargetList(out, seen, grading[i] && grading[i].target_midi_pitches);
      }
    } else if (grading && grading.target_midi_pitches) {
      collectFromTargetList(out, seen, grading.target_midi_pitches);
    }

    if (!out.length && definition && definition.getHarmonizationTargets) {
      var targets = definition.getHarmonizationTargets() || [];
      for (var j = 0; j < targets.length; j++) {
        collectFromTargetList(out, seen, targets[j] && targets[j].target_midi_pitches);
      }
    }

    if (!out.length && timeline && timeline.length) {
      for (var k = 0; k < timeline.length; k++) {
        addMidi(out, seen, timeline[k] && timeline[k].midi);
      }
    }

    out.sort(function (a, b) { return a - b; });
    return out;
  }

  function scoreCandidate(targetMin, targetMax, rangeMin, rangeMax, octaveShift) {
    var lowMiss = Math.max(0, rangeMin - targetMin);
    var highMiss = Math.max(0, targetMax - rangeMax);
    var overflow = lowMiss + highMiss;
    var targetCenter = (targetMin + targetMax) / 2;
    var rangeCenter = (rangeMin + rangeMax) / 2;
    return {
      overflow: overflow,
      absShift: Math.abs(octaveShift),
      centerDistance: Math.abs(targetCenter - rangeCenter)
    };
  }

  function isBetterScore(candidate, best) {
    if (!best) return true;
    if (candidate.overflow !== best.overflow) {
      return candidate.overflow < best.overflow;
    }
    if (candidate.absShift !== best.absShift) {
      return candidate.absShift < best.absShift;
    }
    return candidate.centerDistance < best.centerDistance;
  }

  function resolveKeyboardRange(options) {
    options = options || {};
    var targetMidis = (options.targetMidis || []).slice().sort(function (a, b) { return a - b; });
    var baseNoteAnchor = Number(options.baseNoteAnchor || 0);
    var baseOctaveAdjustment = Number(options.baseOctaveAdjustment || 0);
    var shortcutMin = Number(options.shortcutMin);
    var shortcutMax = Number(options.shortcutMax);

    if (!targetMidis.length || !isFinite(shortcutMin) || !isFinite(shortcutMax)) {
      return {
        noteAnchor: baseNoteAnchor,
        octaveAdjustment: baseOctaveAdjustment,
        octaveShift: 0
      };
    }

    var targetMin = targetMidis[0];
    var targetMax = targetMidis[targetMidis.length - 1];
    var best = null;
    var bestShift = 0;

    for (var shift = -36; shift <= 36; shift += 12) {
      var candidateAnchor = baseNoteAnchor + shift;
      var rangeMin = shortcutMin + candidateAnchor;
      var rangeMax = shortcutMax + candidateAnchor;
      var candidate = scoreCandidate(targetMin, targetMax, rangeMin, rangeMax, shift);
      if (isBetterScore(candidate, best)) {
        best = candidate;
        bestShift = shift;
      }
    }

    return {
      noteAnchor: baseNoteAnchor + bestShift,
      octaveAdjustment: baseOctaveAdjustment + (bestShift / 12),
      octaveShift: bestShift
    };
  }

  function getShortcutNoteBounds(keyMap) {
    var min = null;
    var max = null;
    keyMap = keyMap || {};
    Object.keys(keyMap).forEach(function (key) {
      var entry = keyMap[key];
      if (!entry || entry.msg !== "toggleNote") return;
      var value = Number(entry.data);
      if (!isFinite(value)) return;
      min = min == null ? value : Math.min(min, value);
      max = max == null ? value : Math.max(max, value);
    });
    return { min: min, max: max };
  }

  return {
    collectTargetMidis: collectTargetMidis,
    getShortcutNoteBounds: getShortcutNoteBounds,
    resolveKeyboardRange: resolveKeyboardRange
  };
});
