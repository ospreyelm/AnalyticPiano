

export default  {
    playback: {
      short: "Play each chord in the score.",
      help:  "Use your keyboard (QWERTY) or the on-screen piano to play every note in the chord at the same time. Match the pitches shown — any octave works.",
      hints: [
        "Make sure you're pressing all the notes at once, not one after another.",
        "Look for the highlighted notes on the on-screen piano to see which keys to press.",
      ],
    },
    analysis_match: {
      short: "Play each chord in the score.",
      help:  "Use your keyboard or the on-screen piano to play each chord. The notes are shown in the staff above.",
      hints: [
        "Press all the notes of the chord simultaneously.",
      ],
    },
    "play-all-voices": {
      short: "Play all voices of the score.",
      help:  "Play every note across all staves. Use the keyboard or on-screen piano.",
      hints: [
        "Work through the score one chord at a time, playing all voices.",
      ],
    },
    harmonization: {
      short: "Click or play notes to complete the missing chord.",
      help:  "Each measure shows a figured bass symbol below the staff. The figures name intervals above the bass — count up from the bass note, find those pitches, then press Lock Chord. In three voices you may leave out the 5th and double another note — the figure lists what's available, not everything you must play.",
      hints: [
        "Figured bass intervals above the bass note (Kellner):\n  No symbol  1 - 3 - 5\n  6          3 - 6 - 8\n  6/4        4 - 6 - 8\n  7          1 - 3 - 5 - 7\n  6/5        3 - 5 - 6 - 8\n  4/3        3 - 4 - 6 - 8\n  2          2 - 4 - 6 - 8",
        "Count from the bass note: 1 = the bass itself (or its octave), 3 = two staff steps up, 5 = four steps up, 6 = five steps up. Key-signature accidentals apply unless the figure shows a sharp or flat.",
        "Press Backspace or Delete to remove the last note, or x Clear to start over.",
      ],
    },
    identification: {
      short: "Identify the Roman numeral for each chord.",
      help:  "Name the Roman numeral by where the chord sits in the key. A I chord = 1, 3, 5 of the key = Do-Mi-So. A I6 = the third of the chord in the bass = 3, 5, 1 = Mi-So-Do. A IV = 4, 6, 1 = Fa-La-Do. Uppercase = major, lowercase = minor, ° = diminished, + = augmented.",
      hints: [
        "The same three syllables name the chord regardless of which one is in the bass — whichever one is in the bass gives you the position: Do-Mi-So = I; Mi-So-Do = I6; So-Do-Mi = I6/4.",
        "Quality comes from which syllables are present: Do-Mi-So = major, Do-Me-So = minor, Do-Me-Se = diminished, Do-Mi-Si = augmented.",
        "Click the question-mark labels on the score and type or select the Roman numeral (e.g. IV, V7, ii°).",
      ],
    },
    symbolic_identification: {
      short: "Identify each symbol in the score.",
      help:  "Click the question marks on the score and enter the correct symbol.",
      hints: [
        "Think about the key signature and scale degrees.",
      ],
    },
    chorale_identification: {
      short: "Identify the Roman numerals in the chorale.",
      help:  "Name each chord's Roman numeral by where it sits in the key. A I chord = 1, 3, 5 = Do-Mi-So; a I6 = the third in the bass = 3, 5, 1 = Mi-So-Do; a IV = 4, 6, 1 = Fa-La-Do. Uppercase = major, lowercase = minor, ° = diminished, + = augmented.",
      hints: [
        "The same three syllables name the chord regardless of which one is in the bass — whichever one is in the bass gives you the position: Do-Mi-So = I; Mi-So-Do = I6; So-Do-Mi = I6/4.",
        "Quality comes from which syllables are present: Do-Mi-So = major, Do-Me-So = minor, Do-Me-Se = diminished, Do-Mi-Si = augmented.",
      ],
    },
    analysis: {
      short: "Analyse the score.",
      help:  "Follow the on-screen prompts to label the musical elements.",
      hints: [
        "Read the prompt carefully -- it tells you what to identify.",
      ],
    },
  };
