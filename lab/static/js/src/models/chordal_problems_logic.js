/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ChordalProblemsLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Convert chordal UMTO chords[] into chord-bank gradeable "problems".
  // notes = sorted(visible + hidden) for grading; visible/hidden keep source order.
  function chordsToProblems(chords) {
    return (chords || []).map(function (c) {
      var visible = (c.visible || []).slice();
      var hidden = (c.hidden || []).slice();
      var notes = visible.concat(hidden).slice().sort(function (a, b) { return a - b; });
      return { visible: visible, hidden: hidden, notes: notes };
    });
  }

  // Detect chordal score-kind from a parsed definition-like object.
  function isChordalUMTO(def) {
    return !!(def && def.score && def.score.umto && def.score.umto.metadata &&
              def.score.umto.metadata.score_kind === "chordal");
  }

  function shouldPreserveChordalMeasures(score) {
    return !!(score && score.measures && score.measures.length &&
              score.umto && score.umto.metadata &&
              score.umto.metadata.score_kind === "chordal");
  }

  return {
    chordsToProblems: chordsToProblems,
    isChordalUMTO: isChordalUMTO,
    shouldPreserveChordalMeasures: shouldPreserveChordalMeasures,
  };
});
