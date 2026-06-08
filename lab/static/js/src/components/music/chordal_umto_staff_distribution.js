(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define(["app/config"], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.ChordalUMTOStaffDistribution = factory(root.Config);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (Config) {
  "use strict";

  var HIGH_THRESHOLD = 65;
  var MID_THRESHOLD = 60;
  var LOW_THRESHOLD = 55;
  var KEYBOARD_STYLE_COUNTS = [2, 3, 4, 5];
  if (Config && typeof Config.get === "function") {
    try {
      KEYBOARD_STYLE_COUNTS = Config.get("general.voiceCountForKeyboardStyle") || KEYBOARD_STYLE_COUNTS;
    } catch (e) {}
  }
  var KEYBOARD_FAMILY = ["keyboard", "keyboardPlusRHBias", "keyboardPlusLHBias"];

  function includes(list, value) {
    return list.indexOf(value) !== -1;
  }

  function sortedMidis(midis) {
    return (midis || []).slice().sort(function (a, b) {
      return a - b;
    });
  }

  function splitByThreshold(notes, threshold, includeThresholdInBass) {
    var treble = [];
    var bass = [];
    notes.forEach(function (midi) {
      var belongsToBass = includeThresholdInBass ? midi <= threshold : midi < threshold;
      if (belongsToBass) bass.push(midi);
      else treble.push(midi);
    });
    return { treble: treble, bass: bass };
  }

  function keyboardStyleSplit(notes) {
    var treble = [];
    var bass = [];
    notes.forEach(function (midi, index) {
      if (index === 0) {
        if (midi <= HIGH_THRESHOLD) bass.push(midi);
        else treble.push(midi);
      } else if (midi < LOW_THRESHOLD) {
        bass.push(midi);
      } else {
        treble.push(midi);
      }
    });
    return { treble: treble, bass: bass };
  }

  function routeChordMidis(midis, staffDistribution) {
    var dist = staffDistribution || "keyboard";
    var notes = sortedMidis(midis);

    if (dist === "LH" || dist === "bass") {
      return { treble: [], bass: notes };
    }
    if (dist === "RH" || dist === "treble") {
      return { treble: notes, bass: [] };
    }
    if (dist === "grandStaff") {
      return splitByThreshold(notes, MID_THRESHOLD, false);
    }
    if (includes(KEYBOARD_FAMILY, dist) && includes(KEYBOARD_STYLE_COUNTS, notes.length)) {
      return keyboardStyleSplit(notes);
    }
    if (dist === "keyboardPlusRHBias") {
      return splitByThreshold(notes, LOW_THRESHOLD, false);
    }
    if (dist === "keyboardPlusLHBias") {
      return splitByThreshold(notes, HIGH_THRESHOLD, true);
    }
    return splitByThreshold(notes, MID_THRESHOLD, false);
  }

  return {
    routeChordMidis: routeChordMidis,
    _getKeyboardStyleCounts: function () {
      return KEYBOARD_STYLE_COUNTS;
    },
    _setKeyboardStyleCounts: function (counts) {
      KEYBOARD_STYLE_COUNTS = counts;
    }
  };
});
