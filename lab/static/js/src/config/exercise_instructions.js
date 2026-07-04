

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
        "Alterations: an accidental next to a number adds that accidental to that generic interval above the bass; a '+' (or strikethrough) raises the interval, a '-' lowers it. Otherwise the note comes from the key signature.",
        "Press Backspace or Delete to remove the last note, or x Clear to start over.",
      ],
    },
    identification: {
      short: "Identify the Roman numeral for each chord.",
      help:  "Name the Roman numeral by where the chord sits in the key. A I chord = 1, 3, 5 of the key = Do-Mi-So. A IV = 4, 6, 1 = Fa-La-Do. The figure after the numeral (6, 6/4, 7…) names intervals above the bass, like figured bass: 6 = 6/3 (third in the bass), 6/4 = a 4th and 6th above the bass. Uppercase = major, lowercase = minor, ° = diminished, + = augmented. First identify the key — Roman numerals have no meaning without one — then find the root with the circle of thirds: the letters always run in the same order (C-E-G-B-D-F-A), and the chordal root is the pitch furthest counter-clockwise before the large gap of a fourth; the next clockwise stops are the third and the fifth (a seventh chord adds one more).",
      hints: [
        "Quality comes from which syllables are present: Do-Mi-So = major, Do-Me-So = minor, Do-Me-Se = diminished, Do-Mi-Si = augmented.",
        "The figure after the numeral names intervals above the bass, just like figured bass: 6 means 6/3 (the third of the chord is in the bass), 6/4 means a 4th and 6th above the bass, 7 means 7/5/3, 6/5 means 6/5/3. The numeral itself is the chord's scale degree and quality.",
        "Find the root with the circle of thirds: the letters always run in the same order (C-E-G-B-D-F-A), and the chordal root is the pitch furthest counter-clockwise before the large gap of a fourth; the next clockwise stops are the third and the fifth (a seventh chord adds one more).",
        "Name the chord as root + quality first (e.g. 'g minor', 'a diminished', 'F augmented', 'F♯ major'), then read its scale degree for the Roman numeral.",
        "Find the quality in two steps: the bounding fifth (root→fifth), then the lower third (root→third). Perfect fifth + major third = major; perfect fifth + minor third = minor; diminished fifth = diminished; augmented fifth = augmented.",
        "If this exercise has a seventh chord, it adds a seventh above the root to a triad; name its quality in two parts — the triad quality, then the seventh (root→seventh).",
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
      help:  "Name each chord's Roman numeral by where it sits in the key. A I chord = 1, 3, 5 = Do-Mi-So; a IV = 4, 6, 1 = Fa-La-Do. The figure after the numeral (6, 6/4, 7…) names intervals above the bass, like figured bass: 6 = 6/3 (third in the bass), 6/4 = a 4th and 6th above the bass. Uppercase = major, lowercase = minor, ° = diminished, + = augmented. First identify the key — Roman numerals have no meaning without one — then find the root with the circle of thirds: the letters always run in the same order (C-E-G-B-D-F-A), and the chordal root is the pitch furthest counter-clockwise before the large gap of a fourth; the next clockwise stops are the third and the fifth (a seventh chord adds one more).",
      hints: [
        "Quality comes from which syllables are present: Do-Mi-So = major, Do-Me-So = minor, Do-Me-Se = diminished, Do-Mi-Si = augmented.",
        "The figure after the numeral names intervals above the bass, just like figured bass: 6 means 6/3 (the third of the chord is in the bass), 6/4 means a 4th and 6th above the bass, 7 means 7/5/3, 6/5 means 6/5/3. The numeral itself is the chord's scale degree and quality.",
        "Find the root with the circle of thirds: the letters always run in the same order (C-E-G-B-D-F-A), and the chordal root is the pitch furthest counter-clockwise before the large gap of a fourth; the next clockwise stops are the third and the fifth (a seventh chord adds one more).",
        "Name the chord as root + quality first (e.g. 'g minor', 'a diminished', 'F augmented', 'F♯ major'), then read its scale degree for the Roman numeral.",
        "Find the quality in two steps: the bounding fifth (root→fifth), then the lower third (root→third). Perfect fifth + major third = major; perfect fifth + minor third = minor; diminished fifth = diminished; augmented fifth = augmented.",
        "If this exercise has a seventh chord, it adds a seventh above the root to a triad; name its quality in two parts — the triad quality, then the seventh (root→seventh).",
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
