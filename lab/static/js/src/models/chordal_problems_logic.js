

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

  // Staff layout for chordal UMTO is a render-time VIEW option (like the legacy
  // chord-bank path): chords[] store flat verticalities and the renderer splits
  // them across staves per staffDistribution. So we do NOT preserve any stored
  // (import-time) measures — always re-convert from umto.chords at render so the
  // current staffDistribution applies. Returns false for chordal to force the
  // _convertChordalUMTOToProcessedScore path.
  function shouldPreserveChordalMeasures(score) {
    return false;
  }

export default {
  chordsToProblems: chordsToProblems,
    isChordalUMTO: isChordalUMTO,
    shouldPreserveChordalMeasures: shouldPreserveChordalMeasures,
};
