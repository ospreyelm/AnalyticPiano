# -*- coding: utf-8 -*-
"""Pure (no-DB) helper for building UMTO exercise dicts from Galant-compendium cadence examples.

Public API
----------
prepare_compendium_exercise(example, target_tonic) -> dict | None
    Build all inputs needed to call save_umto_exercise, without touching the DB.
    Returns None if the example is untemplated or has a note-alignment mismatch.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from music21 import key as m21key
from music21 import roman

from apps.exercises.compendium_source import (
    nearest_interval,
    score_from_example,
    transpose_score,
)
from apps.exercises.compendium_templates import template_for
from apps.exercises.roman_derivation import bin_unit
from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers
from apps.exercises.utils.m21_cir_converter import m21_to_cir
from apps.exercises.utils.legacy_roman import legacy_roman_from_pitches
from apps.exercises.umto import InteractionMode

logger = logging.getLogger(__name__)

# Full Roman-analysis curriculum range; units with ``None`` answer tables are
# pass-through bins and will be ignored by ``bin_unit`` until they gain pools.
CANDIDATE_UNITS = list(range(9, 21))
FAMILY_UNIT_OVERRIDES = {
    "Evaded Cadences in Three Voices": 17,
    "Evaded Cadences in Four Voices": 17,
}
MUSIC21_CONFIRMED_THROUGH_MEASURE = 217


def _hl_key(tonic: str, mode: str) -> str:
    """Return HarmonyLab key string for a tonic + mode pair.

    Format rules:
      major: "j" + tonic + ("_" if no accidental else "")
      minor: "i" + tonic + ("_" if no accidental else "")

    Examples:
      C major  -> "jC_"
      D major  -> "jD_"
      Bb major -> "jBb"
      A minor  -> "iA_"
      F# minor -> "iF#"
    """
    prefix = "j" if mode == "major" else "i"
    natural = "#" not in tonic and "b" not in tonic
    suffix = "_" if natural else ""
    return f"{prefix}{tonic}{suffix}"


def _has_chord_at_offset(chords: list, target: float) -> bool:
    """Return True if any chord in the chordified list sounds at *target*."""
    for chord in chords:
        start = float(chord.offset)
        dur = float(chord.quarterLength)
        if start <= target < start + dur:
            return True
    return False


def _chord_at_offset(chords: list, target: float):
    for chord in chords:
        start = float(chord.offset)
        dur = float(chord.quarterLength)
        if start <= target < start + dur:
            return chord
    return None


def _example_end_measure(example_id: str) -> int | None:
    match = re.fullmatch(r"m\d+-(\d+)", example_id)
    if match is None:
        return None
    return int(match.group(1))


def _use_confirmed_music21_label(example: dict[str, Any]) -> bool:
    end_measure = _example_end_measure(example["id"])
    return (
        example["page_title"] == "Evaded Cadences in Three Voices"
        and example["mode"] == "major"
        and end_measure is not None
        and end_measure <= MUSIC21_CONFIRMED_THROUGH_MEASURE
    )


def _display_roman_label(label: str) -> str:
    label = label.replace("o", "°")
    if label == "vii°4":
        return "vii°64"
    return label


def _final_roman_label(
    *,
    example: dict[str, Any],
    template_rn: str,
    chord,
    tonic: str,
    mode: str,
    allowed_answers: list[str] | None,
) -> tuple[str, str]:
    if chord is None:
        return template_rn, template_rn
    if _use_confirmed_music21_label(example):
        music21_label = _display_roman_label(
            roman.romanNumeralFromChord(chord, m21key.Key(tonic, mode)).figure
        )
        return music21_label, template_rn
    legacy = legacy_roman_from_pitches(
        sorted(chord.pitches, key=lambda p: p.midi),
        tonic,
        mode,
    )
    if template_rn == "Cad64":
        return "Cad64", legacy.label or template_rn
    candidate = legacy.normalized_label or template_rn
    if allowed_answers is not None and candidate not in allowed_answers:
        candidate = template_rn
    return candidate, legacy.label or template_rn


def prepare_compendium_exercise(example: dict[str, Any], target_tonic: str) -> dict | None:
    """Build all inputs needed to call save_umto_exercise, without touching the DB.

    Parameters
    ----------
    example:
        A single example dict from load_cadence_examples().
    target_tonic:
        Destination key tonic letter, e.g. "D", "Bb", "F#".

    Returns
    -------
    dict with keys: description, score_data, skill_tags, complexity, unit, umto_kwargs.
    None if the example has no template, a note-alignment mismatch, or cannot be binned.
    """
    # Step 1: look up curated template
    template = template_for(example["page_title"], example["mode"])
    if template is None:
        return None

    # Step 2: build source score and verify a pitch sounds at every template offset
    sc = score_from_example(example)
    chords = list(sc.chordify().flatten().getElementsByClass("Chord"))
    for off, _rn in template:
        if not _has_chord_at_offset(chords, float(off)):
            logger.warning(
                "compendium_prep: example %s has no sounding chord at offset %s — skipping",
                example["id"],
                off,
            )
            return None

    # Step 3: transpose to target_tonic
    iv = nearest_interval(example["key"], target_tonic)
    tscore = transpose_score(sc, iv)
    transposed_chords = list(tscore.chordify().flatten().getElementsByClass("Chord"))

    # Step 4: build HarmonyLab key string
    hl_key = _hl_key(target_tonic, example["mode"])

    # Step 5: convert to CIR
    cir = m21_to_cir(tscore, key_override=hl_key)
    score_data = {"meta": cir["meta"], "measures": cir["measures"]}

    # Step 6: bin to lowest covering unit
    rn_set = {rn for _off, rn in template}
    table = compute_unit_allowed_answers()
    unit = FAMILY_UNIT_OVERRIDES.get(example["page_title"])
    if unit is None:
        unit = bin_unit(rn_set, table, CANDIDATE_UNITS)
    if unit is None:
        logger.warning(
            "compendium_prep: example %s rn_set %s cannot be binned to any candidate unit",
            example["id"],
            rn_set,
        )
        return None

    # Step 7: build analysis_overrides in AnalysisSlice(**a) shape
    # AnalysisSlice fields: offset, content (AnalysisLayer dict), unit_tags, is_target
    # content fields: roman_numeral, raw_roman_numeral, local_key, raw_figured_bass,
    #                 figured_bass, pop_symbol, functional_label, scale_degrees
    analysis_overrides = []
    for off, rn in template:
        final_rn, raw_rn = _final_roman_label(
            example=example,
            template_rn=rn,
            chord=_chord_at_offset(transposed_chords, float(off)),
            tonic=target_tonic,
            mode=example["mode"],
            allowed_answers=table.get(unit),
        )
        analysis_overrides.append(
            {
                "offset": float(off),
                "content": {
                    "roman_numeral": final_rn,
                    "raw_roman_numeral": raw_rn,
                    "local_key": None,
                    "raw_figured_bass": None,
                    "figured_bass": None,
                    "pop_symbol": None,
                    "functional_label": None,
                },
                "unit_tags": [unit],
                "is_target": True,
            }
        )

    # Step 8: title (student-facing source string)
    mode_word = example["mode"]
    title = f'{example["page_title"]} in {target_tonic} {mode_word}'

    # Step 9: description (<=60 chars)
    minor_suffix = "m" if example["mode"] == "minor" else ""
    description = f'Cmp {example["id"]} {target_tonic}{minor_suffix}'
    assert len(description) <= 60, f"description too long: {len(description)} chars: {description!r}"

    # Step 10: skill tags
    skill_tags = [
        "exercise_type:roman_from_compendium",
        "corpus:galant_compendium",
        f"unit:{unit}",
        "mode:roman",
        f'page:{example["page_title"]}',
    ]

    # Step 11: return assembled dict
    return {
        "description": description,
        "score_data": score_data,
        "skill_tags": skill_tags,
        "complexity": unit,
        "unit": unit,
        "umto_kwargs": {
            "exercise_id": "TEMP",
            "source": title,
            "key": hl_key,
            "meter": score_data["meta"].get("time", "2/2"),
            "clef": score_data["meta"].get("clef", "treble"),
            "complexity_score": unit,
            "mode": InteractionMode.IDENTIFICATION,
            "unit": unit,
            "analysis_type": "roman",
            "input_mode": "dropdown",
            "analysis_overrides": analysis_overrides,
        },
    }
