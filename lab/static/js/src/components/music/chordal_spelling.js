

var STEP_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

  // spelledPitchFromName(name, midi) -> { step, alter, octave }
  // Converts a pitch name (e.g. "c#", "eb") and MIDI number to a spelled pitch.
  // The octave is inferred from MIDI, with an enharmonic wrap: e.g. Cb4 is written
  // C-flat but sounds as B3, so its octave bumps up to 4; B#3 sounds as C4, bumps down.
  function spelledPitchFromName(name, midi) {
    var lower = String(name).trim().toLowerCase();
    var step = lower.charAt(0).toUpperCase();
    var alter = 0;
    for (var i = 1; i < lower.length; i++) {
      var ch = lower.charAt(i);
      if (ch === "#") alter += 1;
      else if (ch === "b" || ch === "♭") alter -= 1;
      else if (ch === "x") alter += 2;
    }
    var pc = ((midi % 12) + 12) % 12;
    var naturalPc = STEP_PC[step];
    var octave = Math.floor(midi / 12) - 1;
    if (pc - naturalPc > 6) octave += 1;
    else if (naturalPc - pc > 6) octave -= 1;
    return { step: step, alter: alter, octave: octave };
  }

  // pitchFromSpellingString(str) -> { step, alter, octave } | null
  // Parses a pitch spelling string into a pitch object. Accepts BOTH:
  //   - scientific form: "C#4", "Eb5", "F##3" (no slash)
  //   - VexFlow key form: "c#/4", "eb/5", "f##/3" (lowercase, slash before octave)
  // The VexFlow form is what Unit 5 identification exercises record as the
  // chord's `spelling` (KTD2 — always carries octave). Returns null if the
  // string doesn't match either format.
  function pitchFromSpellingString(str) {
    var m = /^([A-Ga-g])([#b♭♯x]*)\/?(-?\d+)$/.exec(String(str).trim());
    if (!m) return null;
    var step = m[1].toUpperCase();
    var alter = 0;
    for (var i = 0; i < m[2].length; i++) {
      var ch = m[2].charAt(i);
      if (ch === "#" || ch === "♯") alter += 1;
      else if (ch === "b" || ch === "♭") alter -= 1;
      else if (ch === "x") alter += 2;
    }
    return { step: step, alter: alter, octave: parseInt(m[3], 10) };
  }

  // keyAwarePitch(midi, spellingTable) -> { step, alter, octave }
  // Determines the spelled pitch for a MIDI number using a spelling table (array of 12 strings per pitch class).
  // If no table provided or PC not found, defaults to sharp spellings.
  function keyAwarePitch(midi, spellingTable) {
    var pc = ((midi % 12) + 12) % 12;
    if (spellingTable && spellingTable[pc]) {
      return spelledPitchFromName(spellingTable[pc], midi);
    }
    // Default to sharps: [C, C#, D, D#, E, F, F#, G, G#, A, A#, B]
    var sharp = [["C",0],["C",1],["D",0],["D",1],["E",0],["F",0],
                 ["F",1],["G",0],["G",1],["A",0],["A",1],["B",0]][pc];
    return { step: sharp[0], alter: sharp[1], octave: Math.floor(midi / 12) - 1 };
  }

  // resolveChordPitches(chord, spellingTable) -> { <midi>: { step, alter, octave } }
  // Converts a chord object { visible, hidden, spelling } to a map of MIDI -> spelled pitch.
  // If chord.spelling is provided, those strings override the key-aware default.
  function resolveChordPitches(chord, spellingTable) {
    var out = {};
    var visible = chord.visible || [];
    var hidden = chord.hidden || [];
    var allMidis = visible.concat(hidden);
    var spelling = chord.spelling || null;
    var byMidi = {};
    if (spelling) {
      for (var i = 0; i < allMidis.length && i < spelling.length; i++) {
        var parsed = pitchFromSpellingString(spelling[i]);
        if (parsed) byMidi[allMidis[i]] = parsed;
      }
    }
    for (var j = 0; j < allMidis.length; j++) {
      var m = allMidis[j];
      out[m] = byMidi[m] || keyAwarePitch(m, spellingTable);
    }
    return out;
  }

  // Convert a VexFlow-style "name/octave" key (e.g. "bb/4", "c#/5") into a
  // scientific spelling string ("Bb4", "C#5"). Returns null if unparseable.
  function vexKeyToSpellingString(keyStr) {
    var parts = String(keyStr).split("/");
    if (parts.length !== 2 || !parts[0]) return null;
    var nm = parts[0];
    return nm.charAt(0).toUpperCase() + nm.slice(1) + parts[1];
  }

  // pitchDictToVexKey({ step, alter, octave }) -> "eb/4"
  // Structural sibling of vexKeyToSpellingString in the opposite direction:
  // a spelled-pitch dict (as returned by resolveChordPitches / keyAwarePitch)
  // into VexFlow's lowercase "<step><accidentals>/<octave>" key form. Used by
  // stave_note_factory.getNoteName to render a note's recorded spelling.
  function pitchDictToVexKey(pitch) {
    var step = String(pitch.step).toLowerCase();
    var alter = pitch.alter || 0;
    var acc = "";
    if (alter > 0) {
      for (var i = 0; i < alter; i++) acc += "#";
    } else if (alter < 0) {
      for (var j = 0; j < -alter; j++) acc += "b";
    }
    return step + acc + "/" + pitch.octave;
  }

export default {
  spelledPitchFromName: spelledPitchFromName,
    pitchFromSpellingString: pitchFromSpellingString,
    keyAwarePitch: keyAwarePitch,
    resolveChordPitches: resolveChordPitches,
    vexKeyToSpellingString: vexKeyToSpellingString,
    pitchDictToVexKey: pitchDictToVexKey,
};
