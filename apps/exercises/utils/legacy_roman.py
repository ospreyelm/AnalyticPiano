"""Python adapter for HarmonyLab's legacy Roman-numeral lookup tables.

The browser analyzer computes a chord code from pitch classes relative to the
tonic, then looks that code up in ``iChords.js`` or ``jChords.js``.  This module
keeps the backend audit/import path on that same deterministic table logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from music21 import pitch as m21pitch

PITCH_CLASSES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "y", "z"]


@dataclass(frozen=True)
class LegacyRomanResult:
    chord_code: str
    label: str
    normalized_label: str
    root: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=2)
def _load_table(mode: str) -> dict[str, dict[str, str]]:
    table_name = "iChords.js" if mode == "minor" else "jChords.js"
    table_path = (
        _repo_root()
        / "lab"
        / "static"
        / "js"
        / "src"
        / "config"
        / "analysis"
        / table_name
    )
    text = table_path.read_text(encoding="utf-8")
    matches = re.finditer(
        r'"(?P<code>[0-9yz]+/[0-9yz]*)"\s*:\s*\{[^}]*?'
        r'root:\s*"(?P<root>[^"]+)".*?'
        r'label:\s*"(?P<label>[^"]+)"',
        text,
        re.DOTALL,
    )
    return {
        match.group("code"): {
            "root": match.group("root"),
            "label": match.group("label"),
        }
        for match in matches
    }


def _tonic_pitch_class(tonic: str) -> int:
    return m21pitch.Pitch(tonic.replace("b", "-")).pitchClass


def _relative_pitch_class(note_pc: int, tonic_pc: int) -> int:
    while note_pc < tonic_pc:
        note_pc += 12
    return (note_pc - tonic_pc) % 12


def _pitch_classes_in_lowest_order(pitches) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for p in sorted(pitches, key=lambda pitch: pitch.midi):
        pc = p.pitchClass
        if pc not in seen:
            seen.add(pc)
            ordered.append(pc)
    return ordered


def legacy_chord_code(pitches, tonic: str) -> str:
    """Return the same chord-code key as ``Analyze.get_chord_code()``.

    Example: A-minor D-F-B over D gives ``5/28``.
    """
    pcs = _pitch_classes_in_lowest_order(pitches)
    if not pcs:
        return ""
    tonic_pc = _tonic_pitch_class(tonic)
    relative = [_relative_pitch_class(pc, tonic_pc) for pc in pcs]
    bass = PITCH_CLASSES[relative[0]]
    uppers = "".join(PITCH_CLASSES[pc] for pc in sorted(relative[1:]))
    return f"{bass}/{uppers}"


_FIGURED_BASS_GLYPHS = {
    "Z": "6",
    "U": "7",
    "e": "3",
    "r": "4",
    "t": "5",
    "z": "6",
    "u": "7",
    "d": "+",
    "'": "#",
    "C": "♭",
    "K": "♯",
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
}


def _code_contains_chordal_seventh(chord_code: str, root: str) -> bool:
    if not chord_code or not root or root not in PITCH_CLASSES:
        return False
    try:
        _bass, upper = chord_code.split("/", 1)
    except ValueError:
        return False
    seventh_pc = (PITCH_CLASSES.index(root) + 10) % 12
    return PITCH_CLASSES[seventh_pc] in upper


def normalize_legacy_roman_label(
    label: str, *, chord_code: str = "", root: str = ""
) -> str:
    """Convert legacy Sebastian-font brace codes to readable Roman text.

    The legacy tables store figures as font glyph mnemonics, e.g. ``ii°{z}``
    for first inversion.  UMTO/import/review data should use plain text.
    """
    if not label:
        return label

    def replace(match: re.Match) -> str:
        content = match.group(1)
        if content in {"u3", "u5"}:
            content = "u" if _code_contains_chordal_seventh(chord_code, root) else ""
        return "".join(
            _FIGURED_BASS_GLYPHS.get(ch, ch) for ch in content if ch != " "
        )

    return re.sub(r"\{([^}]*)\}", replace, label).replace("⌀", "ø")


def legacy_roman_from_pitches(pitches, tonic: str, mode: str) -> LegacyRomanResult:
    """Look up a Roman label using HarmonyLab's existing major/minor tables."""
    normalized_mode = "minor" if mode == "minor" else "major"
    chord_code = legacy_chord_code(pitches, tonic)
    entry = _load_table(normalized_mode).get(chord_code, {})
    label = entry.get("label", "")
    root = entry.get("root", "")
    return LegacyRomanResult(
        chord_code=chord_code,
        label=label,
        normalized_label=normalize_legacy_roman_label(
            label, chord_code=chord_code, root=root
        ),
        root=root,
    )
