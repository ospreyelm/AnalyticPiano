import keyMap from "app/config/key_map";

export default  {
  defaultKeyboardSize: [25, 32, 37, 49, 61, 88][3] /* key count */,
  maskTrebleStaff: false /* if true, staffDistribution should == "LH" */,
  flexNoKeySpelling: true /* boolean */,
  validStaffDistributions: [
    "keyboard",
    "keyboardPlusLHBias",
    "keyboardPlusRHBias",
    "chorale",
    "grandStaff",
    "LH",
    "RH",
  ],
  staffDistribution: "keyboard",
  voiceCountForKeyboardStyle: [2, 3, 4, 5],
  voiceCountForChoraleStyle: [4],
  defaultNoteColor: "rgb(180,180,180)" /* gray */,
  defaultRhythmValue: "w" /* whole note (semibreve) */,
  chordBank: {
    displaySize: 9,
  } /* number of chords spread across the sheet music */,
  defaultKeyAndSignature: ["jC_", "h"][0],
  metronomeSettings: { defaultTempo: 40, maxTempo: 360 },
  bankAfterMetronomeTick: 0.25 /* fraction of beat */,
  keyboardShortcutsEnabled: true,

  noDoubleVision: false,

  autoAdvance: false,
  autoAdvanceDelay: 4,
  autoRepeat: false,
  autoRepeatDelay: 6,
  hideNextForAutoAdvance: false,
  ignoreMistakesOnAutoAdvance: false,

  numberedExerciseCount: 40,

  analysisSettings: {
    enabled: true,
    mode: {
      abbreviate_thoroughbass: false,

      /* max one of the following may be true */
      note_names: true,
      fixed_do: false,
      scientific_pitch: false,
      pitch_class: false,
      spacing: false,

      /* max one of the following may be true */
      scale_degrees: false,
      solfege: false,
      do_based_solfege: false,

      thoroughbass: false,
      roman_numerals: true,
      roman_numerals_exp: false,
      chord_labels: false,

      /* max one of the following may be true */
      intervals: false,
      intervals_wrap_after_octave: false,
      intervals_wrap_after_octave_plus_ditone: false,
      generic_intervals: false,
      generic_intervals_wrap_after_octave: false,
      generic_intervals_wrap_after_octave_plus_ditone: false,
      pci: false,

      /* max one of the following may be true */
      set_class_set: false,
      set_class_normal: false,
      set_class_prime: false,
      set_class_forte: false,
    },
  },

  highlightSettings: {
    enabled: false,
    mode: {
      roothighlight: true,
      tritonehighlight: true,
      doublinghighlight: false,
      modalmixturehighlight: false /* minor mixture in a major key */,
      loweredhighlight: false /* shifted flatwise enharmonically */,
      solobass: false,
      octaveshighlight: false /* not recommended, hidden from UI */,
    },
  },

  orderOfSharps: ["F", "C", "G", "D", "A", "E", "B"],

  /* default spelling of chromatic scale per D-minor */
  noteNames: ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"],

  /* single character per pitch class */
  pitchClasses: ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "y", "z"],

  keyMap: keyMap,

  /* In case the user chooses a key signature and the key-to-staff-signature lock is enabled */
  keySignatureMap: {
    bbbbbbb: "jCb",
    bbbbbb: "jGb",
    bbbbb: "jDb",
    bbbb: "jAb",
    bbb: "jEb",
    bb: "jBb",
    b: "jF_",
    "": "jC_",
    "#": "jG_",
    "##": "jD_",
    "###": "jA_",
    "####": "jE_",
    "#####": "jB_",
    "######": "jF#",
    "#######": "jC#",
  },

  keyDisplayGroups: [
    /* grouping of keys on UI */
    /* [label, key1, key2, key3, ..., keyN] */
    /* To do: change to dictionary with arrays as values */
    // ["basic", "h","jC_","iA_","jG_","jF_","iD_"],
    // ["sharps", "iE_","jD_","iB_","jA_","iF#","jE_","iC#","jB_","iG#","jF#","iD#","jC#","iA#"],
    // ["flats", "jBb","iG_","jEb","iC_","jAb","iF_","jDb","iBb","jGb","iEb","jCb","iAb"],
    ["basic", "h", "jC_", "iA_"],
    [
      "major",
      "jCb",
      "jGb",
      "jDb",
      "jAb",
      "jEb",
      "jBb",
      "jF_",
      "jC_",
      "jG_",
      "jD_",
      "jA_",
      "jE_",
      "jB_",
      "jF#",
      "jC#",
    ],
    [
      "minor",
      "iAb",
      "iEb",
      "iBb",
      "iF_",
      "iC_",
      "iG_",
      "iD_",
      "iA_",
      "iE_",
      "iB_",
      "iF#",
      "iC#",
      "iG#",
      "iD#",
      "iA#",
    ],
  ],

  keyWheel: [
    [
      /* Chopin Preludes */ "jC_",
      "iA_",
      "jG_",
      "iE_",
      "jD_",
      "iB_",
      "jA_",
      "iF#",
      "jE_",
      "iC#",
      "jB_",
      "iG#",
      "jF#",
      "iEb",
      "jDb",
      "iBb",
      "jAb",
      "iF_",
      "jEb",
      "iC_",
      "jBb",
      "iG_",
      "jF_",
      "iD_",
    ],
    [
      "jC_",
      "iE_",
      "jG_",
      "iB_",
      "jD_",
      "iF#",
      "jA_",
      "iC#",
      "jE_",
      "iG#",
      "jB_",
      "iEb",
      "jGb",
      "iBb",
      "jDb",
      "iF_",
      "jAb",
      "iC_",
      "jEb",
      "iG_",
      "jBb",
      "iD_",
      "jF_",
      "iA_",
    ],
  ][0] /* choose one! */,
  };
