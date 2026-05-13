"""Canonical factory for creating UMTO-backed Exercise rows.

This module owns the CIR→UMTO conversion. Every Exercise creation path in the
codebase flows through `save_umto_exercise`. Direct `Exercise(data={...}).save()`
for new rows is blocked by `Exercise.clean()` and `Exercise.save()` guards.

Emergency bypass: set HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 for one-shot migration
scripts only. Never set in CI, tests, or production.
"""

from __future__ import annotations


from apps.exercises.models import NonUMTOExerciseError


from typing import Literal, Optional

from apps.exercises.umto import (
    UMTO,
    Metadata,
    Voices,
    VoiceEvent,
    Pitch,
    GradingSlice,
    AnalysisSlice,
    AnalysisLayer,
    InteractionMode,
)
from apps.exercises.utils.music21_builder import build_score_from_data
try:
    from music21 import roman, key as m21_key
    _MUSIC21_AVAILABLE = True
except ImportError:
    _MUSIC21_AVAILABLE = False


_DUR_QL = {"w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "16": 0.25, "32": 0.125}
_STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_VOICE_NAME_TO_ID = {"soprano": "S", "alto": "A", "tenor": "T", "bass": "B"}


def _duration_ql(duration: dict) -> float:
    base = _DUR_QL.get(duration.get("type", "q"), 1.0)
    dots = duration.get("dots", 0)
    return base * (2.0 - 0.5 ** dots) if dots else base


def _pitch_to_midi(step: str, alter: int, octave: int) -> int:
    return ((int(octave) + 1) * 12) + _STEP_SEMITONES[step] + int(alter)


def _resolve_voice_id(target_voice: Optional[str], clef: str) -> str:
    if target_voice:
        vid = _VOICE_NAME_TO_ID.get(target_voice.lower())
        if vid is None:
            raise ValueError(f"Unknown target_voice: {target_voice}")
        return vid
    return "S" if clef == "treble" else "B"


_QL_TO_DUR_TYPE = {4.0: "w", 2.0: "h", 1.0: "q", 0.5: "8", 0.25: "16", 0.125: "32"}


def _ql_to_dur_type(ql: float) -> str:
    return _QL_TO_DUR_TYPE.get(round(ql, 6), "q")


def _split_voices_at_onsets(
    voices_dict: dict[str, list[VoiceEvent]],
    attack_onsets: set[float],
) -> dict[str, list[VoiceEvent]]:
    """Split held notes at beat-boundary onsets where another voice attacks.

    Only splits at integer quarter-note positions (beat boundaries), not at
    eighth-note or finer subdivisions. A half note in the alto at beat 2
    becomes two quarter notes — one per beat — so each beat's slot renders
    with filled noteheads and remains readable.
    """
    # Only cut at beat boundaries (integer quarter-note positions)
    beat_onsets = {o for o in attack_onsets if abs(o - round(o)) < 1e-6}

    result: dict[str, list[VoiceEvent]] = {}
    for vid, events in voices_dict.items():
        new_events: list[VoiceEvent] = []
        t = 0.0
        for ev in events:
            if ev.kind != "note" or ev.duration <= 1.0:
                new_events.append(ev)
                t += ev.duration
                continue
            # Find beat-boundary onsets strictly inside this note
            end = t + ev.duration
            cuts = sorted(
                o for o in beat_onsets
                if o > round(t, 5) + 1e-6 and o < round(end, 5) - 1e-6
            )
            if not cuts:
                new_events.append(ev)
                t += ev.duration
                continue
            # Split into quarter notes at each beat boundary
            boundaries = [t] + cuts + [end]
            for i in range(len(boundaries) - 1):
                seg_dur = round(boundaries[i + 1] - boundaries[i], 6)
                new_events.append(VoiceEvent(
                    kind="note",
                    pitch=ev.pitch,
                    duration=seg_dur,
                    duration_type=_ql_to_dur_type(seg_dur),
                    dots=0,
                ))
            t += ev.duration
        result[vid] = new_events
    return result


def _to_music21_key(key_name: str):
    text = (key_name or "").strip()
    if not text:
        return m21_key.Key("C")
    parts = text.split()
    if len(parts) >= 2 and parts[-1].lower() in {"major", "minor"}:
        tonic = " ".join(parts[:-1]).replace("b", "-")
        mode = parts[-1].lower()
        return m21_key.Key(tonic, mode)
    return m21_key.Key(text)


def build_umto_payload(
    *,
    exercise_id: str,
    source: str,
    key: str,
    meter: str,
    clef: str,
    complexity_score: int,
    mode: InteractionMode,
    score_data: dict,
    input_mode: Literal["dropdown", "text"] = "dropdown",
    target_voice: Optional[str] = None,
    unit: Optional[int] = None,
    analysis_overrides: Optional[list] = None,
    analysis_type: Optional[str] = None,
) -> dict:
    """Build a UMTO frontend payload from CIR-shaped score_data.

    Owns all CIR→UMTO conversion. See spec
    docs/superpowers/specs/2026-04-23-umto-consistency-design.md for contract.
    """
    metadata = Metadata(
        exercise_id=exercise_id,
        source=source,
        key=key,
        meter=meter,
        clef=clef,
        complexity_score=complexity_score,
        mode=mode,
        input_mode=input_mode,
        unit=unit,
    )

    voices_dict: dict[str, list[VoiceEvent]] = {"S": [], "A": [], "T": [], "B": []}
    grading_slices: list[GradingSlice] = []
    analysis_slices: list[AnalysisSlice] = []

    voice_id = _resolve_voice_id(target_voice, clef)

    # Per-voice running offsets so each voice's timeline is independent.
    voice_offsets: dict[str, float] = {"S": 0.0, "A": 0.0, "T": 0.0, "B": 0.0}
    # Pair (staff, voice_index_in_staff) → voice id for SATB convention.
    # treble[0]=S, treble[1]=A, bass[0]=T, bass[1]=B
    SATB_MAP = {("treble", 0): "S", ("treble", 1): "A", ("bass", 0): "T", ("bass", 1): "B"}

    single_voice_mode = target_voice is not None or clef in ("treble", "bass")

    for measure in score_data.get("measures", []):
        if single_voice_mode:
            staves_to_walk = [(clef, 0)]
        else:
            staves_to_walk = [(s, i) for s in ("treble", "bass") for i in range(2)]

        for staff_name, v_idx in staves_to_walk:
            staff = measure.get("staves", {}).get(staff_name, {})
            voice_list = staff.get("voices", [])
            if v_idx >= len(voice_list):
                continue
            items = voice_list[v_idx].get("items", [])

            if single_voice_mode:
                target_id = voice_id
            else:
                target_id = SATB_MAP[(staff_name, v_idx)]

            for item in items:
                dur = item.get("duration", {})
                ql = _duration_ql(dur)
                kind = item.get("kind")
                cur_offset = voice_offsets[target_id]
                if kind == "note":
                    p = item.get("pitch", {})
                    midi = _pitch_to_midi(p.get("step", "C"), p.get("alter", 0), p.get("octave", 4))
                    pitch = Pitch(step=p["step"], alter=p.get("alter", 0), octave=p["octave"], midi=midi)
                    voices_dict[target_id].append(
                        VoiceEvent(
                            kind="note",
                            pitch=pitch,
                            duration=ql,
                            duration_type=dur.get("type", "q"),
                            dots=dur.get("dots", 0),
                        )
                    )
                    if single_voice_mode:
                        grading_slices.append(
                            GradingSlice(offset=cur_offset, target_midi_pitches=[midi])
                        )
                        
                        # Unit 1: identification uses pitch names as analysis
                        content = AnalysisLayer()
                        if unit == 1:
                            content.roman_numeral = None
                            content.raw_roman_numeral = pitch.to_long_name()

                        analysis_slices.append(
                            AnalysisSlice(
                                offset=cur_offset,
                                content=content,
                                unit_tags=[unit] if unit is not None else [],
                            )
                        )
                elif kind == "rest":
                    voices_dict[target_id].append(
                        VoiceEvent(
                            kind="rest",
                            duration=ql,
                            duration_type=dur.get("type", "q"),
                            dots=dur.get("dots", 0),
                        )
                    )
                voice_offsets[target_id] += ql

    # For SATB (non-single-voice) modes, synthesize one grading slice per
    # unique onset across all four voices. Callers that need roman-numeral
    # analysis_slices must pass analysis_overrides.
    if not single_voice_mode:
        # First pass: collect all attack onsets before splitting
        onsets: set[float] = set()
        for vid in ("S", "A", "T", "B"):
            t = 0.0
            for ev in voices_dict[vid]:
                if ev.kind == "note":
                    onsets.add(round(t, 5))
                t += ev.duration

        # Split held notes at interior onsets so each slot gets the correct notehead
        voices_dict = _split_voices_at_onsets(voices_dict, onsets)

        # Recompute onsets after splitting (new attack points may have been added)
        onsets = set()
        for vid in ("S", "A", "T", "B"):
            t = 0.0
            for ev in voices_dict[vid]:
                if ev.kind == "note":
                    onsets.add(round(t, 5))
                t += ev.duration
        
        # Unit 9+: Generate Roman Numerals via music21
        theory_map = {}
        if unit and unit >= 9:
            try:
                m21_score = build_score_from_data({"score": score_data})
                chordified = m21_score.chordify()
                k_obj = _to_music21_key(key)
                for off in sorted(onsets):
                    # Get the chord exactly at this offset
                    c = chordified.getElementAtOrBefore(off)
                    if c and hasattr(c, 'pitches'):
                        rn = roman.romanNumeralFromChord(c, k_obj)
                        theory_map[off] = (rn.figure, rn.figure) # (roman, raw)
            except Exception as e:
                # Log or handle failure? For now, just skip theory.
                print(f"Warning: music21 analysis failed for {exercise_id}: {e}")

        for off in sorted(onsets):
            pitches_at = []
            for vid in ("S", "A", "T", "B"):
                t = 0.0
                for ev in voices_dict[vid]:
                    if ev.kind == "note" and abs(t - off) < 0.001:
                        pitches_at.append(ev.pitch.midi)
                        break
                    t += ev.duration
            if pitches_at:
                grading_slices.append(
                    GradingSlice(offset=off, target_midi_pitches=sorted(pitches_at))
                )
                
                content = AnalysisLayer()
                if off in theory_map:
                    content.roman_numeral = None
                    content.raw_roman_numeral = theory_map[off][1]

                analysis_slices.append(
                    AnalysisSlice(
                        offset=off,
                        content=content,
                        unit_tags=[unit] if unit is not None else [],
                    )
                )

    if analysis_overrides:
        analysis_slices = [AnalysisSlice(**a) for a in analysis_overrides]

    umto = UMTO(
        metadata=metadata,
        voices=Voices(**voices_dict),
        analysis=analysis_slices,
        grading=grading_slices,
    )
    return umto.to_frontend_payload(unit=unit, analysis_type=analysis_type)


import os

from apps.exercises.models import Exercise


def _legacy_bypass_enabled() -> bool:
    return os.environ.get("HARMONYLAB_ALLOW_LEGACY_EXERCISE") == "1"


def save_umto_exercise(
    *,
    description: str,
    score_data: dict,
    author,
    skill_tags: list,
    complexity: int,
    is_public: bool = True,
    umto_kwargs: dict,
    overwrite: bool = False,
    auto_playlist: bool = True,
) -> Exercise:
    """Build a UMTO payload from score_data + umto_kwargs, validate, save Exercise,
    and backfill exercise_id in the stored payload.

    If overwrite=True and an exercise with the same description and author exists,
    it will be updated instead of creating a new one.
    """
    try:
        payload = build_umto_payload(score_data=score_data, **umto_kwargs)
    except Exception as e:
        raise NonUMTOExerciseError(f"Failed to build UMTO payload: {e}") from e

    # Validate before DB write.
    try:
        UMTO.model_validate(payload["score"]["umto"])
    except Exception as e:
        raise NonUMTOExerciseError(f"UMTO validation failed: {e}") from e

    ex = None
    if overwrite:
        ex = (
            Exercise.objects.filter(description=description, authored_by=author)
            .defer("data")
            .first()
        )

    if ex is None:
        ex = Exercise(
            description=description,
            data=payload,
            authored_by=author,
            is_public=is_public,
            skill_tags=list(skill_tags),
            complexity=complexity,
        )
    else:
        ex.data = payload
        ex.skill_tags = list(skill_tags)
        ex.complexity = complexity
        ex.is_public = is_public

    ex.save(skip_auto_playlist=not auto_playlist)
    # Backfill now that the DB-assigned id is known.
    ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.data["exerciseId"] = ex.id
    ex.save()
    return ex


def save_umto_symbolic_exercise(
    *,
    description: str,
    author,
    problems: list[dict],
    source: str,
    unit: int = 2,
    is_public: bool = True,
) -> Exercise:
    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=source,
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=unit,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="dropdown",
            unit=unit,
        ),
        voices=Voices(),
        analysis=[],
        grading=[],
    )

    payload = {
        "type": "umto_symbolic_meter",
        "isUMTO": True,
        "mode": InteractionMode.IDENTIFICATION.value,
        "analysisType": "unit2_symbolic_meter",
        "inputMode": "dropdown",
        "staffDistribution": "none",
        "complexity_score": unit,
        "key": "C",
        "meter": "4/4",
        "clef": "treble",
        "introText": source,
        "reviewText": "Well done!",
        "allowed_answers": [],
        "problems": problems,
        "score": {
            "meta": {
                "key": "C",
                "time": "4/4",
                "clef": "treble",
                "staffDistribution": "none",
            },
            "measures": [],
            "umto": umto.model_dump(mode='json'),
        },
        "grading": [],
    }

    UMTO.model_validate(payload["score"]["umto"])

    skill_tags = [
        "unit:2",
        "unit:2_rhythm",
        "unit:2_meter_simple",
        "unit:2_meter_compound",
    ]

    ex = Exercise.objects.filter(description=description, authored_by=author).first()
    if ex is not None:
        ex.data = payload
        ex.is_public = is_public
        ex.skill_tags = skill_tags
        ex.complexity = unit
        ex.save(update_fields=["data", "is_public", "skill_tags", "complexity"])
    else:
        ex = Exercise(
            description=description,
            data=payload,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags,
            complexity=unit,
        )
        ex.save()

    ex.data["exerciseId"] = ex.id
    ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.save(update_fields=["data"])
    return ex


def save_umto_barline_exercise(
    *,
    description: str,
    author,
    payload: dict,
    is_public: bool = True,
    overwrite: bool = False,
) -> Exercise:
    data = dict(payload)
    data["type"] = "umto_barline_placement"
    data["isUMTO"] = True
    data["mode"] = InteractionMode.IDENTIFICATION.value

    skill_tags = list(data.get("tags") or ["unit:2", "unit:2_rhythm"])
    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

    if ex is None:
        ex = Exercise(
            description=description,
            data=data,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags,
            complexity=2,
        )
    else:
        ex.data = data
        ex.skill_tags = skill_tags
        ex.complexity = 2
        ex.is_public = is_public

    if ex._state.adding:
        ex.save()
    else:
        ex.save(update_fields=["data", "skill_tags", "complexity", "is_public"])
    ex.data["exerciseId"] = ex.id
    ex.save(update_fields=["data"])
    return ex
