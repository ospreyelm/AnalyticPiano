

// Simple helpers to construct a renderer-agnostic score model

  function note(step, alter, octave, durationType, dots) {
    return {
      kind: "note",
      pitch: { step: step, alter: alter || 0, octave: octave },
      duration: { type: durationType, dots: dots || 0 },
    };
  }

  function rest(durationType, dots) {
    return { kind: "rest", duration: { type: durationType, dots: dots || 0 } };
  }

  function chord(notesArray, durationType, dots) {
    return {
      kind: "chord",
      notes: notesArray,
      duration: { type: durationType, dots: dots || 0 },
    };
  }

  function voice(items, direction) {
    return { direction: direction || "auto", items: items || [] };
  }

  function staff(clef, voices) {
    return { clef: clef, voices: voices || [] };
  }

  function measure(number, staves) {
    return { number: number, staves: staves };
  }

  function score(meta, measures) {
    return { meta: meta || {}, measures: measures || [] };
  }

  // Export API

export default {
  note: note,
    rest: rest,
    chord: chord,
    voice: voice,
    staff: staff,
    measure: measure,
    score: score,
};
