

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
      help:  "Each measure shows a figured bass symbol above the staff. Count those intervals up from the bass note, find those pitches, then press Lock Chord. In three voices you may leave out the 5th and double another note — the figure lists what's available, not everything you must play.",
      hints: [
        "Figured bass intervals above the bass note (Kellner):\n  No symbol  1 - 3 - 5\n  6          3 - 6 - 8\n  6/4        4 - 6 - 8\n  7          1 - 3 - 5 - 7\n  6/5        3 - 5 - 6 - 8\n  4/3        3 - 4 - 6 - 8\n  2          2 - 4 - 6 - 8",
        "Count from the bass note: 1 = the bass itself (or its octave), 3 = two staff steps up, 5 = four steps up, 6 = five steps up. Key-signature accidentals apply unless the figure shows a sharp or flat.",
        "Press Backspace or Delete to remove the last note, or x Clear to start over.",
      ],
    },
    identification: {
      short: "Identify the Roman numeral for each chord.",
      help:  "Name the Roman numeral by where the chord sits in the key. A I chord = 1, 3, 5 of the key = do-mi-sol. A I6 = the third of the chord in the bass = 3, 5, 1 = mi-sol-do. A IV = 4, 6, 1 = fa-la-do. Uppercase = major, lowercase = minor, ° = diminished, + = augmented.",
      hints: [
        "Find the root: rearrange the chord's notes so thirds stack from the bottom. Then compare the bass to the root — same note is root position; a third above is third in the bass (e.g. I6); a fifth above is fifth in the bass (e.g. I6/4). Count scale degrees from the tonic to name the numeral itself.",
        "Decide quality from the stacked thirds, then match major/minor/diminished/augmented to the case and symbol.",
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
      help:  "Name each chord's Roman numeral by where it sits in the key. A I chord = 1, 3, 5 = do-mi-sol; a I6 = the third in the bass = 3, 5, 1 = mi-sol-do; a IV = 4, 6, 1 = fa-la-do. Uppercase = major, lowercase = minor, ° = diminished, + = augmented.",
      hints: [
        "Find the root of each chord: rearrange its notes so thirds stack from the bottom. Then compare the bass to the root — same note is root position; a third above is third in the bass (e.g. I6); a fifth above is fifth in the bass (e.g. I6/4). Count scale degrees from the tonic to name the numeral itself.",
        "Decide quality from the stacked thirds, then match major/minor/diminished/augmented to the case and symbol.",
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
