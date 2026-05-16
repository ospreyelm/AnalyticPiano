from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from music21 import key as m21_key
from music21 import pitch as m21_pitch
from music21 import scale as m21_scale


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


class DerivedNotes(TypedDict):
    bass_name: str
    bass_pc: int
    expanded_figures: list[str]
    required_note_names: list[str]
    required_upper_pcs: list[int]
    allowed_pcs: list[int]


@dataclass(frozen=True)
class FigureToken:
    accidental: str  # "", "#", "b", "n"
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


def _scale_pitches_for_key(key_obj: m21_key.Key) -> list[m21_pitch.Pitch]:
    """Return pitches for the key's natural minor (or major) scale spanning ~4 octaves."""
    tonic = key_obj.tonic.name
    if key_obj.mode == "minor":
        sc = m21_scale.MinorScale(tonic)
    else:
        sc = m21_scale.MajorScale(tonic)
    return list(sc.getPitches(f"{tonic}2", f"{tonic}6"))


def _diatonic_pitch_above(
    scale_pitches: list[m21_pitch.Pitch],
    bass: m21_pitch.Pitch,
    number: int,
) -> m21_pitch.Pitch:
    """Return the scale pitch that is (number-1) diatonic steps above bass."""
    # Find bass in scale by step + alter; fall back to step-only for chromatic bass notes
    idx = next(
        (i for i, p in enumerate(scale_pitches) if p.step == bass.step and p.alter == bass.alter),
        None,
    )
    if idx is None:
        idx = next(
            (i for i, p in enumerate(scale_pitches) if p.step == bass.step),
            0,
        )
    target_idx = idx + (number - 1)
    # Clamp to list bounds (scale spans 4 octaves so this rarely fires)
    target_idx = min(target_idx, len(scale_pitches) - 1)
    return scale_pitches[target_idx]


def _apply_accidental_to_pitch(base: m21_pitch.Pitch, accidental: str) -> m21_pitch.Pitch:
    """Raise (#), lower (b), or naturalize (n) a diatonic pitch by 1 semitone."""
    if accidental == "":
        return base
    result = m21_pitch.Pitch()
    result.step = base.step
    result.octave = base.octave
    if accidental == "#":
        result.accidental = m21_pitch.Accidental(base.alter + 1)
    elif accidental == "b":
        result.accidental = m21_pitch.Accidental(base.alter - 1)
    elif accidental == "n":
        result.accidental = m21_pitch.Accidental(0)
    else:
        raise ValueError(f"Unsupported accidental: {accidental!r}")
    return result


def derive_required_notes(*, key_name: str, bass_name: str, figure: str | None) -> DerivedNotes:
    key_obj = m21_key.Key(_normalize_key_name(key_name))
    bass_pitch = m21_pitch.Pitch(bass_name)
    if bass_pitch.octave is None:
        bass_pitch.octave = 3

    scale_pitches = _scale_pitches_for_key(key_obj)
    expanded = expand_figure_string(figure)
    note_names: list[str] = []
    pcs: list[int] = []

    for raw_token in expanded:
        token = _parse_token(raw_token)
        diatonic = _diatonic_pitch_above(scale_pitches, bass_pitch, token.number)
        derived = _apply_accidental_to_pitch(diatonic, token.accidental)
        note_name = derived.name.replace("-", "b")
        pc = int(derived.pitchClass)
        if pc not in pcs:
            note_names.append(note_name)
            pcs.append(pc)

    bass_pc = int(bass_pitch.pitchClass)
    return {
        "bass_name": bass_name,
        "bass_pc": bass_pc,
        "expanded_figures": expanded,
        "required_note_names": note_names,
        "required_upper_pcs": pcs,
        "allowed_pcs": [bass_pc] + pcs,
    }
