/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.VexflowAdapterLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function isRestTickable(tickable) {
    if (!tickable) return false;
    var methodValue = false;
    if (typeof tickable.isRest === "function") {
      methodValue = !!tickable.isRest();
    } else {
      methodValue = !!tickable.isRest;
    }
    return !!(
      tickable._isRest ||
      methodValue ||
      String(tickable.duration || "").indexOf("r") !== -1
    );
  }

  function keyToMidi(keyStr) {
    var parts = String(keyStr || "").split("/");
    if (parts.length !== 2) return null;
    var name = parts[0];
    var octave = parseInt(parts[1], 10);
    var step = name.charAt(0).toLowerCase();
    var acc = name.slice(1);
    var base = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }[step];
    if (typeof base !== "number" || isNaN(octave)) return null;
    var delta = 0;
    if (acc === "#") delta = 1;
    else if (acc === "##") delta = 2;
    else if (acc === "b") delta = -1;
    else if (acc === "bb") delta = -2;
    else if (acc === "n") delta = 0;
    return 12 * (octave + 1) + base + delta;
  }

  function tickableToScaleDegreeMidi(tickable) {
    if (isRestTickable(tickable)) return null;
    var keys = tickable && typeof tickable.getKeys === "function" ? tickable.getKeys() : [];
    var midi = [];
    keys.forEach(function (key) {
      var value = keyToMidi(key);
      if (value !== null) midi.push(value);
    });
    return midi;
  }

  /**
   * Returns the functional_label from the UMTO analysis slice whose offset
   * is within 0.05 quarter-lengths of `quarterLength`, or null if none found.
   * Used by the clausula renderer to draw circled bass scale-degree numerals.
   *
   * @param {Array} analysisSlices  - score.umto.analysis array
   * @param {number} quarterLength  - noteOnset / 1024
   * @returns {string|null}
   */
  function getBassLabelAtOffset(analysisSlices, quarterLength) {
    if (!analysisSlices || !analysisSlices.length) return null;
    for (var i = 0; i < analysisSlices.length; i++) {
      var sl = analysisSlices[i];
      if (Math.abs(sl.offset - quarterLength) < 0.05 &&
          sl.content && sl.content.functional_label) {
        return sl.content.functional_label;
      }
    }
    return null;
  }

  function normalizeKeyForVexFlow(key) {
    if (!key) return "C";
    var k = String(key).trim();
    if (k.startsWith("i") || k.startsWith("j")) {
      var mode = k.charAt(0);
      var root = k.substring(1).replace("_", "");
      return mode === "i" ? root + "m" : root;
    }
    if (k.length > 0 && k[0] === k[0].toLowerCase()) {
      var lowerRoot = k[0].toUpperCase() + k.substring(1);
      return lowerRoot.endsWith("m") ? lowerRoot : lowerRoot + "m";
    }
    return k;
  }

  function getKeySignatureAlterations(key) {
    if (!key) return {};

    var alterations = {};
    var k = normalizeKeyForVexFlow(key);
    var map = {
      C: 0, G: 1, D: 2, A: 3, E: 4, B: 5, "F#": 6, "C#": 7,
      F: -1, Bb: -2, Eb: -3, Ab: -4, Db: -5, Gb: -6, Cb: -7,
      Am: 0, Em: 1, Bm: 2, "F#m": 3, "C#m": 4, "G#m": 5, "D#m": 6, "A#m": 7,
      Dm: -1, Gm: -2, Cm: -3, Fm: -4, Bbm: -5, Ebm: -6, Abm: -7,
    };
    var accCount = map[k] || 0;

    if (accCount > 0) {
      var sharpOrder = ["F", "C", "G", "D", "A", "E", "B"];
      for (var i = 0; i < accCount && i < sharpOrder.length; i++) {
        alterations[sharpOrder[i]] = 1;
      }
    } else if (accCount < 0) {
      var flatOrder = ["B", "E", "A", "D", "G", "C", "F"];
      for (var j = 0; j < Math.abs(accCount) && j < flatOrder.length; j++) {
        alterations[flatOrder[j]] = -1;
      }
    }

    return alterations;
  }

  // Decides chord notehead coloring for a multi-note chord tickable. A chord's
  // notehead ids run [baseId, baseId + keyCount). Returns the base (unplayed)
  // style for the whole chord plus the indices of individually-played
  // noteheads, which the caller applies via setKeyStyle.
  //
  // The base style must never be the played-black color: per-key playedness
  // can only ADD black to specific noteheads via setKeyStyle, never subtract
  // it from the others. If the base style were black, an unplayed notehead in
  // a partially-played chord would have no call to bring it back to gray —
  // it would render black even though it was never struck.
  function resolveChordNoteStyles(opts) {
    opts = opts || {};
    var keyCount = opts.keyCount || 0;
    var baseId = opts.baseId || 0;
    var playedNoteIds = opts.playedNoteIds;
    var hideBase = !opts.showNotation || opts.isAnalysisMatch || opts.hideForHarmonization;
    var baseStyle = hideBase
      ? { fillStyle: "transparent", strokeStyle: "transparent" }
      : { fillStyle: opts.voiceColor, strokeStyle: opts.voiceColor };
    var playedKeyIndices = [];
    for (var h = 0; h < keyCount; h++) {
      if (playedNoteIds && playedNoteIds.has(baseId + h)) {
        playedKeyIndices.push(h);
      }
    }
    return { baseStyle: baseStyle, playedKeyIndices: playedKeyIndices };
  }

  return {
    isRestTickable: isRestTickable,
    keyToMidi: keyToMidi,
    tickableToScaleDegreeMidi: tickableToScaleDegreeMidi,
    getBassLabelAtOffset: getBassLabelAtOffset,
    normalizeKeyForVexFlow: normalizeKeyForVexFlow,
    getKeySignatureAlterations: getKeySignatureAlterations,
    resolveChordNoteStyles: resolveChordNoteStyles,
  };
});
