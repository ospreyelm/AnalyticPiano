/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseDefinitionLabelLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function normalizeAnalysisLabel(label) {
    if (label === null || label === undefined) {
      return "";
    }
    var result = String(label).trim();
    result = result.replace(/♭/g, "b").replace(/♯/g, "#");
    result = result.replace(/^[\s,;:\-()]+|[\s,;:\-()]+$/g, "");
    return result;
  }

  var FIGURE_TOKEN_MAP = {
    "z": "6",
    "z4": "6/4",
    "Cz4": "b6/4",
    "z5": "6/5",
    "u": "7",
    "u3": "6/5",
    "u5": "7/5",
    "r": "4",
    "r2": "4/2",
    "r3": "4/3",
    "i3": "3",
    "q e": "13",
  };

  function expandFiguredBassToken(abbrev) {
    if (FIGURE_TOKEN_MAP[abbrev]) {
      return FIGURE_TOKEN_MAP[abbrev];
    }
    for (var key in FIGURE_TOKEN_MAP) {
      if (FIGURE_TOKEN_MAP.hasOwnProperty(key) && abbrev.indexOf(key) === 0) {
        return FIGURE_TOKEN_MAP[key];
      }
    }
    return abbrev;
  }

  function stripFiguredBassTokens(label) {
    if (!label) return label;
    var result = String(label);
    result = result.replace(/\{([A-Za-z0-9]+)\}/g, function (match, token) {
      return FIGURE_TOKEN_MAP[token] || "";
    });
    return result.trim();
  }

  function isPitchAnalysisType(analysisType) {
    return [
      "note_name",
      "solfege",
      "do_based_solfege",
      "scale_degree",
      "fixed_do",
      "pitch_class",
    ].indexOf(analysisType) !== -1;
  }

  function computeNoteNameFromEvent(ev) {
    if (!ev) return "";
    var name = ev.step.toUpperCase();
    if (ev.alter === 1) name += "#";
    else if (ev.alter === -1) name += "b";
    else if (ev.alter === 2) name += "##";
    else if (ev.alter === -2) name += "bb";
    return name;
  }

  function buildAnalysisWindows(timeline) {
    var grouped = [];
    var onsetIndex = Object.create(null);
    var activeNotes = [];

    (timeline || []).forEach(function (ev) {
      if (!Object.prototype.hasOwnProperty.call(onsetIndex, ev.onset)) {
        onsetIndex[ev.onset] = { onset: ev.onset, events: [] };
        grouped.push(onsetIndex[ev.onset]);
      }
      onsetIndex[ev.onset].events.push(ev);
    });

    grouped.sort(function (a, b) { return a.onset - b.onset; });

    grouped.forEach(function (window) {
      activeNotes = activeNotes.filter(function (n) {
        return n.end > window.onset;
      });
      (window.events || []).forEach(function (ev) {
        activeNotes.push({ midi: ev.midi, end: ev.onset + ev.duration });
      });
      var midiMap = Object.create(null);
      activeNotes.forEach(function (n) { midiMap[n.midi] = true; });
      window.midiStack = Object.keys(midiMap)
        .map(function (k) { return parseInt(k, 10); })
        .sort(function (a, b) { return a - b; });
    });

    return grouped;
  }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function buildChoices(correctLabel, allLabels, analysisType, compoundIntervals) {
    var seen = Object.create(null);
    var pool = (allLabels || []).filter(function (l) {
      if (!l || l === correctLabel) return false;
      if (seen[l]) return false;
      seen[l] = true;
      return true;
    });

    var fallbacks = analysisType === "figured_bass"
      ? ["5/3", "6", "6/4", "7", "6/5", "4/3", "4/2"]
      : analysisType === "figured_bass_unabbreviated"
      ? ["8/5/3", "6/3", "6/4", "7/5/3", "6/5/3", "6/4/3", "6/4/2"]
      : analysisType === "note_name"
      ? ["C", "D", "E", "F", "G", "A", "B"]
      : (analysisType === "solfege" || analysisType === "do_based_solfege" || analysisType === "fixed_do")
      ? ["Do", "Re", "Mi", "Fa", "So", "La", "Ti"]
      : analysisType === "scale_degree"
      ? ["1", "2", "3", "4", "5", "6", "7"]
      : analysisType === "pitch_class"
      ? ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
      : analysisType === "interval_generic"
      ? (compoundIntervals
        ? ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"]
        : ["2", "3", "4", "5", "6", "7", "8"])
      : analysisType === "interval_specific"
      ? (compoundIntervals
        ? ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8", "m9", "M9", "m10", "M10", "P11", "P12", "m13", "M13", "m14", "M14"]
        : ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8"])
      : ["I", "ii", "IV", "V", "vi", "I6/4", "i6/4", "V6/4", "Cad6/4", "Cadb6/4"];

    if (pool.length < 4) {
      fallbacks.forEach(function (item) {
        if (item !== correctLabel && pool.indexOf(item) === -1) {
          pool.push(item);
        }
      });
    }

    var distractors = shuffle(pool).slice(0, 4);
    var choices = shuffle([correctLabel].concat(distractors));
    while (choices.length < 5) { choices.push(correctLabel); }
    return choices.slice(0, 5);
  }

  return {
    normalizeAnalysisLabel: normalizeAnalysisLabel,
    FIGURE_TOKEN_MAP: FIGURE_TOKEN_MAP,
    expandFiguredBassToken: expandFiguredBassToken,
    stripFiguredBassTokens: stripFiguredBassTokens,
    isPitchAnalysisType: isPitchAnalysisType,
    computeNoteNameFromEvent: computeNoteNameFromEvent,
    buildAnalysisWindows: buildAnalysisWindows,
    buildChoices: buildChoices,
  };
});
