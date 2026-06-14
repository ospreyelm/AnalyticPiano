"""Routing helpers for importing external material into UMTO shapes."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import Iterator, Literal, TextIO

from music21 import chord as m21_chord
from music21 import key as m21_key
from music21 import interval as m21_interval
from music21 import note as m21_note
from music21 import pitch as m21_pitch
from music21 import roman as m21_roman

from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload
from apps.exercises.utils.figured_bass import compute_figured_bass
from apps.exercises.utils.legacy_roman import legacy_roman_from_pitches


@dataclass(frozen=True)
class LegacyChordCSVRow:
    exercise_id: str
    description: str
    data: dict


@dataclass(frozen=True)
class MusicXMLRouteDecision:
    route: Literal["voices", "chordal"]
    part_count: int
    has_chords: bool
    reason: str


def iter_legacy_chord_csv_rows(file_obj: TextIO) -> Iterator[LegacyChordCSVRow]:
    """Yield legacy CSV rows whose JSON data contains a non-empty chord array."""
    reader = csv.DictReader(file_obj)
    for row in reader:
        raw_data = row.get("data") or "{}"
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            continue
        if not isinstance(data.get("chord"), list) or not data["chord"]:
            continue
        yield LegacyChordCSVRow(
            exercise_id=row.get("id") or "",
            description=row.get("description") or "",
            data=data,
        )


def legacy_csv_row_to_chordal_payload(row: LegacyChordCSVRow) -> dict:
    """Convert a parsed legacy CSV chord row into a chordal UMTO payload."""
    payload = legacy_chord_row_to_chordal_payload(row.data)
    umto = payload["score"]["umto"]
    umto["metadata"]["exercise_id"] = row.exercise_id
    umto["metadata"]["source"] = row.description or row.data.get("description", "Legacy exercise")
    return payload


def _parts_with_content(score) -> list:
    parts = list(score.parts)
    return [
        part for part in parts
        if len(part.recurse().notesAndRests) > 0
    ]


def classify_musicxml_score(score) -> MusicXMLRouteDecision:
    """Choose the UMTO score kind for a parsed music21 score."""
    parts = _parts_with_content(score)
    part_count = len(parts)
    has_chords = any(
        len(part.recurse().getElementsByClass(m21_chord.Chord)) > 0
        for part in parts
    )

    if has_chords:
        return MusicXMLRouteDecision(
            route="chordal",
            part_count=part_count,
            has_chords=True,
            reason="explicit chord events",
        )
    if part_count in (2, 3, 4):
        return MusicXMLRouteDecision(
            route="voices",
            part_count=part_count,
            has_chords=False,
            reason=f"stable {part_count}-part score",
        )
    return MusicXMLRouteDecision(
        route="chordal",
        part_count=part_count,
        has_chords=False,
        reason="non-multipart or ragged source",
    )


def _pitch_spelling(pitch) -> str:
    return pitch.nameWithOctave.replace("-", "b")


def _harmony_key_to_tonic_mode(harmony_key: str) -> tuple[str, str]:
    text = (harmony_key or "jC_").strip()
    if text and text[0] in {"i", "j"}:
        tonic = text[1:].replace("_", "").replace("b", "-") or "C"
        mode = "minor" if text[0] == "i" else "major"
        return tonic, mode
    return text.replace("b", "-") or "C", "major"


def _pitches_for_chord_event(chord_event: dict) -> list:
    spellings = chord_event.get("spelling") or []
    if spellings:
        return [
            m21_pitch.Pitch(str(name).replace("b", "-"))
            for name in spellings
        ]
    midi_values = (
        list(chord_event.get("visible") or [])
        + list(chord_event.get("hidden") or [])
    )
    return [m21_pitch.Pitch(midi=int(midi)) for midi in midi_values]


def build_chordal_analysis_slices(chords: list[dict], *, harmony_key: str) -> list[dict]:
    """Build HarmonyLab-first analysis slices for chordal UMTO chord events."""
    tonic, mode = _harmony_key_to_tonic_mode(harmony_key)
    tonal_key = m21_key.Key(tonic, mode)
    legacy_tonic = tonic.replace("-", "b")
    analysis = []

    for chord_event in chords:
        pitches = _pitches_for_chord_event(chord_event)
        if not pitches:
            continue
        chord_obj = m21_chord.Chord(pitches)
        try:
            raw_fb, figured_bass = compute_figured_bass(chord_obj, tonal_key)
        except Exception:
            raw_fb, figured_bass = None, None

        legacy = legacy_roman_from_pitches(
            sorted(chord_obj.pitches, key=lambda p: p.midi),
            legacy_tonic,
            mode,
        )
        # Store the braced legacy label (e.g. "V{r3}", "V{z5}") as the canonical
        # roman_numeral. Both the renderer (drawInlineRoman) and the answer path
        # (stripFiguredBassTokens) expect this brace-token format to stack figures
        # correctly. The brace-stripped normalized form (e.g. "V43", "V65") renders
        # flat and is kept only as raw_roman_numeral for data/audit consumers.
        roman_label = legacy.label or None
        raw_roman = legacy.normalized_label or legacy.label or None
        if not roman_label:
            try:
                rn = m21_roman.romanNumeralFromChord(chord_obj, tonal_key)
                roman_label = rn.figure
                raw_roman = rn.figure
            except Exception:
                pass

        sc_prime = sc_forte = sc_normal = sc_set = None
        try:
            sc_prime = chord_obj.primeFormString
            sc_forte = chord_obj.forteClassTnI
            sc_normal = str(list(chord_obj.normalOrder))
            sc_set = "{" + ",".join(p.name for p in chord_obj.pitches) + "}"
        except Exception:
            pass

        interval_specific = interval_generic = None
        if len(pitches) == 2:
            try:
                interval_obj = m21_interval.Interval(chord_obj.pitches[0], chord_obj.pitches[1])
                interval_specific = interval_obj.directedName
                interval_generic = str(abs(interval_obj.generic.directed))
            except Exception:
                pass

        analysis.append({
            "offset": float(chord_event.get("offset", 0.0)),
            "content": {
                "roman_numeral": roman_label,
                "raw_roman_numeral": raw_roman,
                "local_key": harmony_key,
                "raw_figured_bass": raw_fb,
                "figured_bass": figured_bass,
                "set_class_prime": sc_prime,
                "set_class_forte": sc_forte,
                "set_class_normal": sc_normal,
                "set_class_set": sc_set,
                "spacing": None,
                "interval_specific": interval_specific,
                "interval_generic": interval_generic,
            },
            "unit_tags": [],
            "is_target": True,
        })
    return analysis


def musicxml_score_to_chord_events(score) -> list[dict]:
    """Convert a music21 score into onset-grouped chordal UMTO ChordEvent dicts."""
    grouped: dict[float, dict] = {}
    for part in _parts_with_content(score):
        for el in part.recurse().notes:
            offset = round(float(el.getOffsetInHierarchy(part)), 6)
            bucket = grouped.setdefault(
                offset,
                {"offset": offset, "duration": None, "visible": [], "hidden": [], "spelling": []},
            )
            duration = float(el.quarterLength)
            if bucket["duration"] is None or duration < bucket["duration"]:
                bucket["duration"] = duration

            if isinstance(el, m21_note.Note):
                bucket["visible"].append(int(el.pitch.midi))
                bucket["spelling"].append(_pitch_spelling(el.pitch))
            elif isinstance(el, m21_chord.Chord):
                for pitch in el.pitches:
                    bucket["visible"].append(int(pitch.midi))
                    bucket["spelling"].append(_pitch_spelling(pitch))

    events = []
    for offset in sorted(grouped):
        event = grouped[offset]
        event["duration"] = float(event["duration"] or 1.0)
        events.append(event)
    return events
