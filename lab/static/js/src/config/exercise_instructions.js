/**
 * Per-mode instruction and hint text shown to students in the player.
 *
 * Keyed by InteractionMode value (see umto.py).  The "hint" array is
 * progressive: each element is revealed in order when the student presses
 * the Hint button.
 */
define([], function () {
  return {
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
      help:  "Each measure shows a figured bass symbol (e.g. 6/4, 7) above the staff that tells you which chord to build. Click notes on the piano or the staff, then press “Lock Chord” when finished.",
      hints: [
        "The figured bass symbol above the measure tells you the chord quality and inversion:\n  • No symbol = root position (1-3-5 above the bass)\n  • 6 = first inversion (bass is the third)\n  • 6/4 = second inversion (bass is the fifth)\n  • 7 = root-position seventh chord",
        "Count up from the bass note: identify what the figured bass intervals are, then find those notes on the piano.",
        "You can press Backspace or Delete to remove the last note you added, or click × Clear to start the chord over.",
      ],
    },
    identification: {
      short: "Identify the Roman numeral for each chord.",
      help:  "Click the question-mark labels on the score and type or select the Roman numeral (e.g. IV, V7, ii°). Uppercase = major, lowercase = minor.",
      hints: [
        "Find the root of the chord: look at the bottom note in root position (rearrange the chord so thirds stack from the bottom).",
        "Decide the quality: major (uppercase), minor (lowercase), diminished (°), augmented (+).",
        "Count scale degrees from the tonic to name the Roman numeral.",
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
      help:  "Work through each chord in the chorale and enter its Roman numeral. Consider the key and all voices.",
      hints: [
        "Look at the bass line: the lowest note (in root position) gives you the scale degree.",
        "Check whether the chord is major, minor, or diminished to choose uppercase/lowercase.",
      ],
    },
    analysis: {
      short: "Analyse the score.",
      help:  "Follow the on-screen prompts to label the musical elements.",
      hints: [
        "Read the prompt carefully — it tells you what to identify.",
      ],
    },
  };
});
