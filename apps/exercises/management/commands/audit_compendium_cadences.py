# -*- coding: utf-8 -*-
"""Export a no-DB harmonic review CSV for Galant-compendium cadence exercises."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

from django.core.management.base import BaseCommand, CommandError
from music21 import key as m21key
from music21 import roman

from apps.exercises.compendium_inverse import pitch_to_z7
from apps.exercises.compendium_prep import prepare_compendium_exercise
from apps.exercises.compendium_source import (
    load_cadence_examples,
    nearest_interval,
    score_from_example,
    transpose_score,
)
from apps.exercises.management.commands.import_compendium_cadences import KEYS_BY_MODE
from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers
from apps.exercises.utils.figured_bass import compute_figured_bass
from apps.exercises.utils.legacy_roman import legacy_roman_from_pitches


CSV_FIELDS = [
    "source_id",
    "page_title",
    "mode",
    "unit",
    "target_key",
    "offset",
    "analysis_offset",
    "notes",
    "bass",
    "z7_stack",
    "bass_z7",
    "legacy_chord_code",
    "legacy_rn_raw",
    "our_rn",
    "raw_figured_bass",
    "figured_bass",
    "proposed_rn",
    "music21_rn",
    "final_rn",
    "status",
    "exception_reason",
]


def _chord_at_offset(chords, target: float):
    for chord in chords:
        start = float(chord.offset)
        end = start + float(chord.quarterLength)
        if start <= target < end:
            return chord
    return None


def _normalize_figure(figure: str) -> str:
    return figure.replace("o", "°")


def _analysis_offset(page_title: str, proposed_rn: str, offset: float) -> float:
    if (
        proposed_rn == "V"
        and offset == 2.0
        and page_title in {
            "Compound Cadences in Three Voices",
            "Compound Cadences with 5/4 in Four Voices",
        }
    ):
        return 3.0
    return offset


def _classify_status(*, mode: str, proposed_rn: str, music21_rn: str) -> tuple[str, str]:
    if proposed_rn == music21_rn:
        return "match", ""
    if proposed_rn == "Cad64" and music21_rn in {"I64", "i64", "V64"}:
        return "accepted", "cadential six-four labeled Cad64"
    if proposed_rn == "V" and music21_rn == "V#3":
        return "accepted", "dominant with explicit raised third"
    if proposed_rn == "iiø65" and music21_rn == "ii65":
        return "accepted", "half-diminished quality supplied by minor-key spelling"
    if mode == "minor" and proposed_rn == "VI" and music21_rn == "bVI":
        return "accepted", "minor VI displayed without flat"
    return "review", "music21 differs from proposed label"


def _pitch_list(chord) -> list[str]:
    return [pitch.nameWithOctave for pitch in sorted(chord.pitches, key=lambda p: p.midi)]


def _bass(chord) -> str:
    return min(chord.pitches, key=lambda p: p.midi).nameWithOctave


def _z7_stack(chord, tonic: str, mode: str) -> list[int]:
    return [
        pitch_to_z7(p.nameWithOctave, tonic, mode)[0]
        for p in sorted(chord.pitches, key=lambda p: p.midi)
    ]


def build_audit_rows(*, unit: int | None = None, keys: list[str] | None = None) -> list[dict]:
    rows: list[dict] = []
    allowed_by_unit = compute_unit_allowed_answers()
    for example in load_cadence_examples():
        tonics = keys if keys else KEYS_BY_MODE[example["mode"]]
        for tonic in tonics:
            prep = prepare_compendium_exercise(example, tonic)
            if prep is None:
                continue
            if unit is not None and prep["unit"] != unit:
                continue

            score = transpose_score(
                score_from_example(example),
                nearest_interval(example["key"], tonic),
            )
            tonal_key = m21key.Key(tonic, example["mode"])
            chords = list(score.chordify().flatten().getElementsByClass("Chord"))

            for target in prep["umto_kwargs"]["analysis_overrides"]:
                offset = float(target["offset"])
                proposed_rn = target["content"]["roman_numeral"]
                analysis_offset = _analysis_offset(example["page_title"], proposed_rn, offset)
                chord = _chord_at_offset(chords, analysis_offset)
                if chord is None:
                    music21_rn = ""
                    notes = ""
                    bass = ""
                    z7_stack = []
                    bass_z7 = ""
                    legacy_chord_code = ""
                    legacy_rn_raw = ""
                    our_rn = ""
                    final_rn = ""
                    raw_figured_bass = ""
                    figured_bass = ""
                    status = "review"
                    exception_reason = "no chord sounding at analysis offset"
                else:
                    sorted_pitches = sorted(chord.pitches, key=lambda p: p.midi)
                    legacy_result = legacy_roman_from_pitches(
                        sorted_pitches,
                        tonic,
                        example["mode"],
                    )
                    z7_values = _z7_stack(chord, tonic, example["mode"])
                    bass_pitch = min(chord.pitches, key=lambda p: p.midi)
                    bass_z7 = str(
                        pitch_to_z7(bass_pitch.nameWithOctave, tonic, example["mode"])[0]
                    )
                    raw_figured_bass, figured_bass = compute_figured_bass(chord, tonal_key)
                    legacy_chord_code = legacy_result.chord_code
                    legacy_rn_raw = legacy_result.label
                    our_rn = legacy_result.normalized_label
                    final_rn = proposed_rn if proposed_rn == "Cad64" else (our_rn or proposed_rn)
                    allowed_answers = allowed_by_unit.get(prep["unit"])
                    if allowed_answers is not None and final_rn not in allowed_answers:
                        final_rn = proposed_rn
                    music21_rn = _normalize_figure(
                        roman.romanNumeralFromChord(chord, tonal_key).figure
                    )
                    notes = " ".join(_pitch_list(chord))
                    bass = _bass(chord)
                    status, exception_reason = _classify_status(
                        mode=example["mode"],
                        proposed_rn=final_rn,
                        music21_rn=music21_rn,
                    )
                    z7_stack = z7_values
                rows.append(
                    {
                        "source_id": example["id"],
                        "page_title": example["page_title"],
                        "mode": example["mode"],
                        "unit": str(prep["unit"]),
                        "target_key": tonic,
                        "offset": f"{offset:.1f}",
                        "analysis_offset": f"{analysis_offset:.1f}",
                        "notes": notes,
                        "bass": bass,
                        "z7_stack": " ".join(str(v) for v in z7_stack),
                        "bass_z7": bass_z7,
                        "legacy_chord_code": legacy_chord_code,
                        "legacy_rn_raw": legacy_rn_raw,
                        "our_rn": our_rn,
                        "raw_figured_bass": raw_figured_bass,
                        "figured_bass": figured_bass,
                        "proposed_rn": proposed_rn,
                        "music21_rn": music21_rn,
                        "final_rn": final_rn,
                        "status": status,
                        "exception_reason": exception_reason,
                    }
                )
    return rows


def write_audit_csv(rows: list[dict], output: TextIO) -> None:
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


class Command(BaseCommand):
    help = "Export a no-DB CSV for reviewing Galant-compendium Roman numeral labels."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="CSV output path.")
        parser.add_argument("--unit", type=int, default=None, help="Only audit one unit.")
        parser.add_argument(
            "--keys",
            nargs="+",
            default=None,
            metavar="KEY",
            help="Override target tonic letters for this audit.",
        )

    def handle(self, *args, **options):
        out_path = Path(options["out"])
        if out_path.exists() and out_path.is_dir():
            raise CommandError(f"--out must be a file path, not a directory: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        rows = build_audit_rows(unit=options.get("unit"), keys=options.get("keys"))
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            write_audit_csv(rows, fh)

        status_counts: dict[str, int] = {}
        for row in rows:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(rows)} audit rows to {out_path} ({summary})"
            )
        )
