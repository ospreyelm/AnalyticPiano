"""Parse scientific pitch strings ("C#4", "Eb4") into CIR pitch dicts.

Mirrors the JS helper in lab/static/js/src/components/music/chordal_spelling.js
(pitchFromSpellingString) and the spelling-string format produced by
apps/exercises/utils/umto_import_router._pitch_spelling (flats as "b").
"""
import re

_PITCH_RE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")


def spelling_str_to_cir_pitch(s):
    """Return {"step","alter","octave"} for a pitch string, or None if unparseable."""
    if not s:
        return None
    m = _PITCH_RE.match(str(s).strip())
    if not m:
        return None
    step = m.group(1).upper()
    acc = m.group(2)
    alter = acc.count("#") - acc.count("b")
    return {"step": step, "alter": alter, "octave": int(m.group(3))}
