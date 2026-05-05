import json, os, sys
sys.path.append(os.getcwd())
from apps.exercises.utils.music21_builder import build_score_from_data
from music21 import roman, key as m21_key, chord

cir = {
  "meta": {"key": "G", "time": "4/4"},
  "measures": [
    {
      "staves": {
        "treble": {
          "voices": [
            {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "w", "dots": 0}}]},
            {"items": [{"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 4}, "duration": {"type": "w", "dots": 0}}]}
          ]
        },
        "bass": {
          "voices": [
            {"items": [{"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 3}, "duration": {"type": "w", "dots": 0}}]},
            {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 2}, "duration": {"type": "w", "dots": 0}}]}
          ]
        }
      }
    }
  ]
}

score = build_score_from_data({"score": cir})
chordified = score.chordify()
k_obj = m21_key.Key("G")
c = chordified.getElementAtOrBefore(0.0)
print(f"Chord pitches: {[p.nameWithOctave for p in c.pitches]}")
rn = roman.romanNumeralFromChord(c, k_obj)
print(f"Roman Numeral: {rn.figure}")
