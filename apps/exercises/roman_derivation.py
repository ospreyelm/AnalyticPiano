"""Derive Roman numerals + grading pitches for generated cadence targets.

Chordify the SATB Score and, for each requested target, run romanNumeralFromChord
at the requested analysis-source offset while emitting the AnalysisSlice at the
target offset. This lets compound cadences place the student target at the
dominant onset with suspension (2.0) while normalizing the answer from the
resolved sonority (3.0). The compound penult is pedagogically V(5)4 resolving
to V(5)3, i.e. V4-3; the RN answer label remains V. Figured-bass display is
handled separately by HarmonyLab's figured-bass engine, not by Music21 RN.

Do not analyze every chordified vertical: compound cadences contain τ=1
preparations/suspensions that are valid counterpoint but not RN targets.
"""
from __future__ import annotations

from music21 import key as m21key
from music21 import roman

from apps.exercises.utils.voice_events_music21 import score_from_voices


def normalize_figure(figure: str) -> str:
    """music21 figure -> answer-vocabulary string (e.g. 'viio6' -> 'vii°6')."""
    return figure.replace("o", "°")


def _chord_at_offset(chords, target):
    for chord in chords:
        start = float(chord.offset)
        dur = float(chord.quarterLength)
        if start <= target < start + dur:
            return chord
    return None


def bin_unit(rn_set, table: dict, candidate_units) -> int | None:
    """Lowest candidate unit whose allowed-answer set covers rn_set, else None.

    Unit 13 is intentionally excluded from candidate_units (deferred); since
    unit 14 is a superset of 13, RNs needing 13-only chords land in 14.
    """
    needed = set(rn_set)
    for unit in sorted(candidate_units):
        allowed = table.get(unit)
        if allowed is None:
            continue
        if needed.issubset(set(allowed)):
            return unit
    return None


def derive_cadence(voices, *, key: str, targets=None) -> list[dict]:
    """Return [{"offset": target, "rn": str, "midi": [int, ...]}, ...].

    targets is [(target_offset, analysis_source_offset), ...].
    """
    if targets is None:
        raise ValueError("derive_cadence requires explicit structural targets")
    score = score_from_voices(voices)
    tonal_key = m21key.Key(key)
    chords = list(score.chordify().recurse().getElementsByClass("Chord"))
    result: list[dict] = []
    for target, source in targets:
        chord = _chord_at_offset(chords, float(source))
        if chord is None:
            raise ValueError(f"No chordified vertical sounding at offset {source}")
        rn = roman.romanNumeralFromChord(chord, tonal_key)
        result.append({
            "offset": float(target),
            "rn": normalize_figure(rn.figure),
            "midi": sorted(p.midi for p in chord.pitches),
        })
    return result
