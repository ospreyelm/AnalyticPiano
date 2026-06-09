/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("../../utils/chordal_barlines_logic"));
  } else if (typeof define === "function" && define.amd) {
    define(["app/utils/chordal_barlines_logic"], factory);
  } else { root.PlaySaveLogic = factory(root.ChordalBarlinesLogic); }
})(typeof self !== "undefined" ? self : this, function (Barlines) {
  "use strict";

  var BELOW_CONTENT_KEY = {
    roman_numerals: "roman_numeral",
    roman_numerals_exp: "roman_numeral",
    thoroughbass: "figured_bass",
  };

  function buildChordRows(notes, durations) {
    var offsets = Barlines.offsetsFromDurations(durations);
    return notes.map(function (n, i) {
      var row = {
        offset: offsets[i],
        duration: durations[i],
        visible: (n.visible || []).slice(),
        hidden: (n.hidden || []).slice(),
      };
      if (n.spelling) row.spelling = n.spelling.slice();
      if (typeof n.unison_idx !== "undefined" && n.unison_idx !== null) row.unison_idx = n.unison_idx;
      return row;
    });
  }

  function buildAnalysisSlices(offsets, slots, labels, overrides) {
    if (!slots || !slots.below) return [];
    var key = BELOW_CONTENT_KEY[slots.below];
    if (!key) return [];
    var out = [];
    for (var i = 0; i < offsets.length; i++) {
      var ov = overrides && overrides[i] && typeof overrides[i].below !== "undefined"
        ? overrides[i].below : null;
      var value = ov !== null ? ov : (labels[i] != null ? labels[i] : "");
      var content = {}; content[key] = value;
      out.push({ offset: offsets[i], content: content, is_target: true, unit_tags: [] });
    }
    return out;
  }

  return { buildChordRows: buildChordRows, buildAnalysisSlices: buildAnalysisSlices };
});
