# -*- coding: utf-8 -*-
"""Load and build music21 Scores from the Galant-compendium index.

Public API
----------
load_cadence_examples()
    Return a filtered list of example dicts from the compendium index whose
    (page_title, mode) pair is registered in COMPENDIUM_TEMPLATES.

score_from_example(example)
    Build a music21 Score from a single example dict.  Notes are trimmed so
    that each note ends at the next onset within its staff — without this,
    overlapping durations produce wrong chord inversions under chordify().

nearest_interval(src_tonic, dst_tonic)
    Return a music21 Interval for the shortest path (in semitones, [-6, +6])
    from src_tonic to dst_tonic.

transpose_score(score, iv)
    Return a new Score transposed by the given Interval (input not mutated).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from music21 import interval, meter, note, pitch, stream
from music21.interval import ChromaticInterval

from apps.exercises.compendium_templates import COMPENDIUM_TEMPLATES

# ---------------------------------------------------------------------------
# Module constant — override via env COMPENDIUM_INDEX for local regeneration.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_INDEX_PATH = _REPO_ROOT / "apps" / "exercises" / "data" / "galant_compendium_cadences.json"
INDEX_PATH: str = os.environ.get(
    "COMPENDIUM_INDEX",
    str(_DEFAULT_INDEX_PATH),
)

EXCLUDED_EXAMPLE_IDS = {
    # Modulating/tonicizing cadence: original bass D-G-C in G-major metadata is
    # properly V/V-V-I in C. Keep it out of the single-key Z7/RN import path
    # until the local-key/Z6 model exists.
    "m203-205",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def load_cadence_examples() -> list[dict[str, Any]]:
    """Return example dicts whose (page_title, mode) is in COMPENDIUM_TEMPLATES."""
    try:
        fh = open(INDEX_PATH, encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Compendium cadence index not found at {INDEX_PATH!r}. "
            "Use the checked-in apps/exercises/data/galant_compendium_cadences.json "
            "or set COMPENDIUM_INDEX to a local compendium index.json."
        ) from exc

    with fh:
        all_examples: list[dict] = json.load(fh)

    return [
        ex for ex in all_examples
        if (ex.get("page_title"), ex.get("mode")) in COMPENDIUM_TEMPLATES
        and ex.get("id") not in EXCLUDED_EXAMPLE_IDS
    ]


def score_from_example(example: dict[str, Any]) -> stream.Score:
    """Build a music21 Score from a compendium example dict.

    Each staff in ``example["notes"]`` becomes a separate ``stream.Part``.
    Note durations are trimmed per staff so that no note overlaps the next
    distinct onset — required for chordify() to read inversions correctly.
    """
    sc = stream.Score()
    for staff_name, notes_list in example["notes"].items():
        part = stream.Part()
        part.id = staff_name
        part.insert(0, meter.TimeSignature("2/2"))
        for pch_str, off, ql in _trim_notes(notes_list):
            n = note.Note(pch_str, quarterLength=ql)
            part.insert(off, n)
        sc.append(part)
    sc.makeMeasures(inPlace=True)
    return sc


def nearest_interval(src_tonic: str, dst_tonic: str) -> interval.Interval:
    """Return an Interval for the shortest semitone path from src to dst.

    The signed semitone count is in the range [-6, +6]:  if the raw upward
    distance is exactly 6 it is kept positive; any larger value wraps to the
    negative direction.
    """
    src_pc = pitch.Pitch(src_tonic).pitchClass
    dst_pc = pitch.Pitch(dst_tonic).pitchClass
    diff = (dst_pc - src_pc) % 12
    if diff > 6:
        diff -= 12
    # Build a proper Interval via two concrete Pitch objects so that
    # .semitones is reliable (interval.Interval(semitones=N) is unreliable).
    src_p = pitch.Pitch(src_tonic)
    src_p.octave = 4
    dst_p = src_p.transpose(ChromaticInterval(diff))
    return interval.Interval(src_p, dst_p)


def transpose_score(score: stream.Score, iv: interval.Interval) -> stream.Score:
    """Return a new Score transposed by *iv*; the input Score is not mutated."""
    return score.transpose(iv)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _trim_notes(notes_list: list[dict]) -> list[tuple[str, float, float]]:
    """Trim each note's ql so it ends at the next distinct onset in the staff.

    Returns a list of (pitch_string, offset, trimmed_ql) tuples sorted by
    offset.  Notes whose trimmed duration would be <= 0 are dropped.
    """
    if not notes_list:
        return []

    # Build sorted list of (offset, ql, pitch)
    items = sorted(
        ((n["offset"], n["ql"], n["pitch"]) for n in notes_list),
        key=lambda x: x[0],
    )

    # Collect the distinct onset values in order so we can look up the
    # "next onset after this one".
    distinct_onsets: list[float] = sorted({off for off, _, _ in items})

    # Map each onset to the next onset (or None if it's the last).
    next_onset: dict[float, float | None] = {}
    for i, on in enumerate(distinct_onsets):
        next_onset[on] = distinct_onsets[i + 1] if i + 1 < len(distinct_onsets) else None

    result: list[tuple[str, float, float]] = []
    for off, ql, pch in items:
        nxt = next_onset[off]
        if nxt is not None:
            trimmed = min(ql, nxt - off)
        else:
            trimmed = ql
        if trimmed > 0:
            result.append((pch, off, trimmed))

    return result
