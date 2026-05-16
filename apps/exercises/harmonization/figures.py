from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from music21 import interval as m21_interval
from music21 import key as m21_key
from music21 import pitch as m21_pitch


_SHORTHANDS = {
    "": ["5", "3"],
    "5/3": ["5", "3"],
    "6": ["6", "3"],
    "6/4": ["6", "4"],
    "7": ["7", "5", "3"],
    "6/5": ["6", "5", "3"],
    "4/3": ["6", "4", "3"],
    "4/2": ["6", "4", "2"],
    "2": ["6", "4", "2"],
}


_STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class DerivedNotes(TypedDict):
    bass_name: str
    bass_pc: int
    expanded_figures: list[str]
    required_note_names: list[str]
    required_upper_pcs: list[int]
    allowed_pcs: list[int]


@dataclass(frozen=True)
class FigureToken:
    accidental: str
    number: int


def _normalize_key_name(key_name: str) -> str:
    text = (key_name or "C").strip()
    if text.startswith(("j", "i")) and len(text) >= 2:
        mode = "minor" if text.startswith("i") else "major"
        tonic = text[1:].replace("_", "")
        return f"{tonic} {mode}"
    return text


def _parse_token(token: str) -> FigureToken:
    token = token.strip()
    if token in {"#", "b", "n"}:
        token = token + "3"
    match = re.fullmatch(r"([#bn]?)(\d+)", token)
    if not match:
        raise ValueError(f"Invalid figure token: {token!r}")
    accidental, number = match.groups()
    return FigureToken(accidental=accidental, number=int(number))


def expand_figure_string(figure: str | None) -> list[str]:
    text = (figure or "").strip()
    if text in _SHORTHANDS:
        return list(_SHORTHANDS[text])
    if text in {"#", "b", "n"}:
        return [text + "3", "5"]
    tokens = [part.strip() for part in text.split("/") if part.strip()]
    if not tokens:
        return list(_SHORTHANDS[""])
    return tokens


def _pitch_class_from_name(name: str) -> int:
    p = m21_pitch.Pitch(name)
    return int(p.pitchClass)


def _apply_accidental(default_pitch: m21_pitch.Pitch, accidental: str, key_obj: m21_key.Key) -> m21_pitch.Pitch:
    if accidental == "":
        return default_pitch

    step = default_pitch.step
    octave = default_pitch.octave

    if accidental == "#":
        acc_obj = m21_pitch.Accidental("#")
    elif accidental == "b":
        acc_obj = m21_pitch.Accidental("flat")
    elif accidental == "n":
        acc_obj = m21_pitch.Accidental("natural")
    else:
        raise ValueError(f"Unsupported accidental: {accidental!r}")

    result = m21_pitch.Pitch()
    result.step = step
    result.octave = octave
    result.accidental = acc_obj
    return result


def derive_required_notes(*, key_name: str, bass_name: str, figure: str | None) -> DerivedNotes:
    key_obj = m21_key.Key(_normalize_key_name(key_name))
    bass_pitch = m21_pitch.Pitch(bass_name)
    if bass_pitch.octave is None:
        bass_pitch.octave = 3

    expanded = expand_figure_string(figure)
    note_names: list[str] = []
    pcs: list[int] = []

    for raw_token in expanded:
        token = _parse_token(raw_token)
        # Use GenericInterval for diatonic (step-wise) transposition; accidentals
        # are applied separately so that "#3 above F" gives A# rather than A.
        derived = m21_interval.GenericInterval(token.number).transposePitch(bass_pitch)
        derived = _apply_accidental(derived, token.accidental, key_obj)
        note_name = derived.name.replace("-", "b")
        pc = int(derived.pitchClass)
        if pc not in pcs:
            note_names.append(note_name)
            pcs.append(pc)

    bass_pc = _pitch_class_from_name(bass_name)
    return {
        "bass_name": bass_name,
        "bass_pc": bass_pc,
        "expanded_figures": expanded,
        "required_note_names": note_names,
        "required_upper_pcs": pcs,
        "allowed_pcs": [bass_pc] + pcs,
    }
