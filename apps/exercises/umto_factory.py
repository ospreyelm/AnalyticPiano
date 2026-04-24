"""Canonical factory for creating UMTO-backed Exercise rows.

This module owns the CIR→UMTO conversion. Every Exercise creation path in the
codebase flows through `save_umto_exercise`. Direct `Exercise(data={...}).save()`
for new rows is blocked by `Exercise.clean()` and `Exercise.save()` guards.

Emergency bypass: set HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 for one-shot migration
scripts only. Never set in CI, tests, or production.
"""

from __future__ import annotations


class NonUMTOExerciseError(ValueError):
    """Raised when save_umto_exercise is handed legacy-shaped data, or when
    Exercise.save() / Exercise.clean() sees a new row whose data fails UMTO
    validation."""


from typing import Optional

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
    target_voice: Optional[str] = None,
    unit: Optional[int] = None,
    analysis_overrides: Optional[list] = None,
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
    )

    voices_dict: dict[str, list[VoiceEvent]] = {"S": [], "A": [], "T": [], "B": []}
    grading_slices: list[GradingSlice] = []
    analysis_slices: list[AnalysisSlice] = []

    voice_id = _resolve_voice_id(target_voice, clef)
    current_offset = 0.0

    for measure in score_data.get("measures", []):
        staff = measure.get("staves", {}).get(clef, {})
        voice_list = staff.get("voices", [])
        if not voice_list:
            continue
        items = voice_list[0].get("items", [])
        for item in items:
            dur = item.get("duration", {})
            ql = _duration_ql(dur)
            kind = item.get("kind")
            if kind == "note":
                p = item.get("pitch", {})
                midi = _pitch_to_midi(p.get("step", "C"), p.get("alter", 0), p.get("octave", 4))
                pitch = Pitch(step=p["step"], alter=p.get("alter", 0), octave=p["octave"], midi=midi)
                voices_dict[voice_id].append(
                    VoiceEvent(
                        kind="note",
                        pitch=pitch,
                        duration=ql,
                        duration_type=dur.get("type", "q"),
                        dots=dur.get("dots", 0),
                    )
                )
                grading_slices.append(
                    GradingSlice(offset=current_offset, target_midi_pitches=[midi])
                )
                analysis_slices.append(
                    AnalysisSlice(
                        offset=current_offset,
                        content=AnalysisLayer(),
                        unit_tags=[unit] if unit is not None else [],
                    )
                )
            elif kind == "rest":
                voices_dict[voice_id].append(
                    VoiceEvent(
                        kind="rest",
                        duration=ql,
                        duration_type=dur.get("type", "q"),
                        dots=dur.get("dots", 0),
                    )
                )
            current_offset += ql

    if analysis_overrides:
        analysis_slices = [AnalysisSlice(**a) for a in analysis_overrides]

    umto = UMTO(
        metadata=metadata,
        voices=Voices(**voices_dict),
        analysis=analysis_slices,
        grading=grading_slices,
    )
    return umto.to_frontend_payload(unit=unit)
