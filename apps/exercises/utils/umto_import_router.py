"""Routing helpers for importing external material into UMTO shapes."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import Iterator, Literal, TextIO

from music21 import chord as m21_chord
from music21 import note as m21_note

from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload


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
