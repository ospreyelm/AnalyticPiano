"""Round-trip realization helpers copied from the Clausulae compendium workflow.

This module intentionally does not import from ``clausulae-project``.  It keeps
HarmonyLab's production/test path self-contained while preserving the same
Z7-based note regeneration check Gemini built in the Clausulae repo.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from music21 import pitch, scale


def pitch_to_z7(
    pitch_name: str, key: str, mode: str = "major"
) -> tuple[int, str | None]:
    """Convert a pitch name to a Z7 scale degree and chromatic accidental."""
    sc = scale.MinorScale(key) if mode == "minor" else scale.MajorScale(key)
    p = pitch.Pitch(pitch_name)
    scale_degree, acc = sc.getScaleDegreeAndAccidentalFromPitch(p)
    if scale_degree is None:
        raise ValueError(f"Cannot resolve pitch {pitch_name!r} in {key} {mode}")
    return (scale_degree - 1) % 7, str(acc) if acc is not None else None


def z7_to_pitch_name(
    z7_degree: int, key: str, mode: str = "major", octave: int = 4
) -> str:
    """Convert a Z7 scale degree to a pitch name at a given octave."""
    sc = scale.MinorScale(key) if mode == "minor" else scale.MajorScale(key)
    m21_degree = (z7_degree % 7) + 1
    p = sc.pitchFromDegree(m21_degree)
    p = pitch.Pitch(p.name)
    p.octave = octave
    return p.nameWithOctave


def _apply_relative_accidental(base_pitch_name: str, accidental: str | None) -> str:
    p = pitch.Pitch(base_pitch_name)
    if accidental is None:
        return p.nameWithOctave
    if accidental == "natural":
        p.accidental = pitch.Accidental("natural")
        return p.nameWithOctave

    delta_by_accidental = {
        "double-flat": -2,
        "flat": -1,
        "sharp": 1,
        "double-sharp": 2,
    }
    delta = delta_by_accidental.get(accidental)
    if delta is None:
        p.accidental = pitch.Accidental(accidental)
        return p.nameWithOctave

    current_alter = p.accidental.alter if p.accidental is not None else 0
    p.accidental = pitch.Accidental(current_alter + delta)
    return p.nameWithOctave


def _realize_staff_notes(
    notes: list[dict[str, Any]], *, key: str, mode: str, is_staff6: bool
) -> list[dict[str, Any]]:
    if not notes:
        return []

    by_offset: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for n in notes:
        by_offset[round(float(n["offset"]), 9)].append(n)

    realized_notes: list[dict[str, Any]] = []
    for offset, note_list in by_offset.items():
        sorted_notes = sorted(note_list, key=lambda n: pitch.Pitch(n["pitch"]).midi)
        for n in sorted_notes:
            original_pitch = pitch.Pitch(n["pitch"])
            degree, accidental = pitch_to_z7(n["pitch"], key, mode)
            realized_pitch = z7_to_pitch_name(degree, key, mode, original_pitch.octave)

            note_dict = {
                "pitch": _apply_relative_accidental(realized_pitch, accidental),
                "offset": n["offset"],
                "ql": n["ql"],
                "z7": degree,
            }
            if "tie" in n:
                note_dict["tie"] = n["tie"]
            realized_notes.append(note_dict)

    if is_staff6:
        return sorted(realized_notes, key=lambda n: n["offset"])
    return sorted(
        realized_notes, key=lambda n: (n["offset"], pitch.Pitch(n["pitch"]).midi)
    )


def realize_example_from_clausulae(
    entry: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Regenerate an example's notes from pitch->Z7->pitch round-trip data."""
    key = entry["key"]
    mode = entry["mode"]
    notes = entry.get("notes", {})
    return {
        "staff5": _realize_staff_notes(
            notes.get("staff5", []), key=key, mode=mode, is_staff6=False
        ),
        "staff6": _realize_staff_notes(
            notes.get("staff6", []), key=key, mode=mode, is_staff6=True
        ),
    }


def _note_without_derived_fields(note: dict[str, Any]) -> dict[str, Any]:
    cleaned = deepcopy(note)
    cleaned.pop("z7", None)
    return cleaned


def _canonical_notes(
    notes: list[dict[str, Any]], *, is_staff6: bool
) -> list[dict[str, Any]]:
    stripped = [_note_without_derived_fields(note) for note in notes]
    return sorted(
        stripped,
        key=lambda n: (
            n["offset"],
            pitch.Pitch(n["pitch"]).midi,
            n["ql"],
            n.get("tie", ""),
        ),
    )


def compare_realized_notes(
    expected: dict[str, list[dict[str, Any]]],
    realized: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Return human-readable note mismatches between source JSON and regenerated notes."""
    differences: list[str] = []
    for staff in ("staff5", "staff6"):
        expected_notes = _canonical_notes(
            expected.get(staff, []), is_staff6=(staff == "staff6")
        )
        realized_notes = _canonical_notes(
            realized.get(staff, []), is_staff6=(staff == "staff6")
        )
        if expected_notes != realized_notes:
            differences.append(f"{staff}: expected {expected_notes!r}, got {realized_notes!r}")
    return differences
