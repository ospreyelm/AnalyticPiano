// lab/static/js/src/models/chordal_problems_logic.js
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

module.exports = { chordsToProblems: chordsToProblems };
