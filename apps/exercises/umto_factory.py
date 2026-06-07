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
    ChordEvent,
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


_QL_TO_DURATION = {
    4.0: ("w", 0),
    3.0: ("h", 1),
    2.0: ("h", 0),
    1.5: ("q", 1),
    1.0: ("q", 0),
    0.75: ("8", 1),
    0.5: ("8", 0),
    0.375: ("16", 1),
    0.25: ("16", 0),
    0.125: ("32", 0),
}


def _ql_to_dur_type(ql: float) -> str:
    return _QL_TO_DURATION.get(round(ql, 6), ("q", 0))[0]


def _ql_to_duration_parts(ql: float) -> tuple[str, int]:
    return _QL_TO_DURATION.get(round(ql, 6), ("q", 0))


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


def _event_onsets(events: list[VoiceEvent]) -> list[float]:
    out: list[float] = []
    t = 0.0
    for ev in events:
        out.append(round(t, 5))
        t += ev.duration
    return out


def _absorb_trailing_rests_after_final_attack(
    voices_dict: dict[str, list[VoiceEvent]],
) -> dict[str, list[VoiceEvent]]:
    final_attack = None
    for events in voices_dict.values():
        t = 0.0
        for ev in events:
            if ev.kind == "note":
                final_attack = max(final_attack if final_attack is not None else t, t)
            t += ev.duration

    if final_attack is None:
        return voices_dict

    result: dict[str, list[VoiceEvent]] = {}
    for vid, events in voices_dict.items():
        onsets = _event_onsets(events)
        target_index = next(
            (
                idx for idx, ev in enumerate(events)
                if ev.kind == "note" and abs(onsets[idx] - final_attack) < 0.0001
            ),
            None,
        )
        if target_index is None:
            result[vid] = events
            continue

        trailing = events[target_index + 1:]
        if not trailing or any(ev.kind != "rest" for ev in trailing):
            result[vid] = events
            continue

        new_events = list(events[:target_index])
        final_note = events[target_index].copy(deep=True)
        final_note.duration = round(
            final_note.duration + sum(ev.duration for ev in trailing),
            6,
        )
        final_note.duration_type, final_note.dots = _ql_to_duration_parts(final_note.duration)
        new_events.append(final_note)
        result[vid] = new_events

    return result


def _to_music21_key(key_name: str):
    text = (key_name or "").strip()
    if not text:
        return m21_key.Key("C")
    if len(text) >= 2 and text[0] in {"i", "j"}:
        mode = "minor" if text[0] == "i" else "major"
        tonic = text[1:].replace("_", "").replace("b", "-")
        return m21_key.Key(tonic, mode)
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
    display: Optional[dict] = None,
    preserve_source_durations: bool = False,
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

        # Split held notes at interior onsets so each slot gets the correct notehead.
        # Some curated imported material already carries pedagogically meaningful
        # durations/ties; for those paths, preserve the source rhythm.
        if not preserve_source_durations:
            voices_dict = _split_voices_at_onsets(voices_dict, onsets)
            voices_dict = _absorb_trailing_rests_after_final_attack(voices_dict)

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
    payload = umto.to_frontend_payload(unit=unit, analysis_type=analysis_type)
    if display is not None:
        payload["display"] = display
    return payload


def _midi_to_cir_pitch(midi: int) -> dict:
    """MIDI -> CIR spelled pitch. C-major-ish spelling; sharps for black keys.
    Octave convention matches the frontend: C4 (MIDI 60) -> octave 4
    (frontend computes MIDI as (octave+1)*12 + semitone)."""
    names = [("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0),
             ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0)]
    step, alter = names[midi % 12]
    octave = midi // 12 - 1
    return {"step": step, "alter": alter, "octave": octave}


def _meter_quarter_length(meter: str) -> float:
    try:
        num_s, denom_s = meter.split("/", 1)
        return int(num_s) * (4.0 / int(denom_s))
    except (ValueError, AttributeError, ZeroDivisionError):
        return 4.0


def _duration_dict(ql: float) -> dict:
    dur_type, dots = _ql_to_duration_parts(ql)
    return {"type": dur_type, "dots": dots}


# Keyboard staff split: pitches at or above middle C (MIDI 60) render on the
# treble staff, below on the bass staff. Matches the "keyboard" clef convention.
_KEYBOARD_SPLIT_MIDI = 60


def _chordal_to_measures(chords: list, meter: str) -> list:
    """Generate minimal CIR measures from chordal chords[] (spike 5a, W1).

    Each chord is split across treble + bass staves by register (keyboard style):
    pitches >= MIDI 60 go to treble, below to bass. Both staves stay rhythmically
    aligned — every onset places a chord/note/rest on each staff so durations
    match. Measures break when accumulated quarter-length reaches the meter's
    beats-per-measure."""
    beats = _meter_quarter_length(meter)
    STAVES = ("treble", "bass")

    def _new_measure():
        return {"staves": {s: {"voices": [{"items": []}]} for s in STAVES}}

    def _items(staff):
        return current["staves"][staff]["voices"][0]["items"]

    def _any_items():
        return any(_items(s) for s in STAVES)

    def _finish_measure():
        nonlocal current, used
        if _any_items():
            measures.append(current)
        current = _new_measure()
        used = 0.0

    def _append_rest(ql: float):
        if ql <= 0:
            return
        for staff in STAVES:
            _items(staff).append({"kind": "rest", "duration": _duration_dict(ql)})

    def _staff_item(midis, duration):
        pitches = [_midi_to_cir_pitch(m) for m in midis]
        if len(pitches) > 1:
            return {"kind": "chord",
                    "notes": [{"pitch": p} for p in pitches],
                    "duration": duration}
        if len(pitches) == 1:
            return {"kind": "note", "pitch": pitches[0], "duration": duration}
        return {"kind": "rest", "duration": duration}

    def _append_chord_item(c: dict):
        visible_midis = list(c.get("visible", []))
        duration = _duration_dict(float(c["duration"]))
        treble = [m for m in visible_midis if m >= _KEYBOARD_SPLIT_MIDI]
        bass = [m for m in visible_midis if m < _KEYBOARD_SPLIT_MIDI]
        _items("treble").append(_staff_item(treble, duration))
        _items("bass").append(_staff_item(bass, duration))

    measures = []
    current = _new_measure()
    used = 0.0
    cursor = 0.0
    for c in sorted(chords, key=lambda item: float(item.get("offset", 0.0))):
        offset = float(c.get("offset", cursor))
        if offset < cursor - 1e-6:
            raise ValueError("Chord offsets must be non-overlapping and monotonic")

        while cursor < offset - 1e-6:
            gap = min(offset - cursor, beats - used)
            _append_rest(gap)
            used += gap
            cursor += gap
            if abs(used - beats) < 1e-6 or used > beats:
                _finish_measure()

        if abs(used - beats) < 1e-6:
            _finish_measure()

        dur = float(c["duration"])
        _append_chord_item(c)
        used += dur
        cursor = offset + dur
        if abs(used - beats) < 1e-6 or used > beats:
            _finish_measure()
    if _any_items():
        measures.append(current)
    return measures


def build_chordal_umto_payload(
    *,
    exercise_id: str,
    source: str,
    key: str,
    meter: str,
    clef: str,
    complexity_score: int,
    mode: InteractionMode,
    chords: list,
    analysis: Optional[list] = None,
    unit: Optional[int] = None,
    input_mode: Literal["dropdown", "text"] = "dropdown",
    analysis_review_status: Literal["none", "generated", "reviewed"] = "none",
) -> dict:
    """Build a UMTO frontend payload for a chordal score-kind exercise.

    chords: list of dicts compatible with ChordEvent
            (offset, duration, visible, hidden?, spelling?).
    analysis: list of dicts compatible with AnalysisSlice (canonical, top-level).
    score.measures is generated from chords[] per the spike 5a W1 decision, so
    the existing ScoreTimeline and VexFlow paths can consume chordal UMTO.
    """
    analysis = analysis or []
    umto = UMTO(
        metadata=Metadata(
            exercise_id=exercise_id,
            source=source,
            key=key,
            meter=meter,
            clef=clef,
            complexity_score=complexity_score,
            mode=mode,
            input_mode=input_mode,
            unit=unit,
            score_kind="chordal",
            analysis_review_status=analysis_review_status,
        ),
        chords=[ChordEvent(**c) for c in chords],
        analysis=[AnalysisSlice(**a) for a in analysis],
    )
    umto_json = umto.model_dump(mode="json")
    UMTO.model_validate(umto_json)  # explicit round-trip validation
    return {
        "type": "umto_chorale",
        "isUMTO": True,
        "mode": mode.value if hasattr(mode, "value") else mode,
        "key": key,
        "meter": meter,
        "clef": clef,
        "complexity_score": complexity_score,
        "score": {
            "meta": {"key": key, "time": meter, "clef": clef},
            "measures": _chordal_to_measures(chords, meter),
            "umto": umto_json,
        },
        "analysis": umto_json["analysis"],
        "grading": [],
    }


def legacy_chord_row_to_chordal_payload(data, *, meter="4/4", clef="keyboard",
                                        complexity_score=1):
    """Wrap a legacy data.chord row into a chordal UMTO payload (runtime read only).

    Accepts chords as dicts ({visible,hidden} or {notes}) or bare midi lists.
    Never writes back to the DB — call this only at serve time.
    """
    raw = data.get("chord") or []
    chords = []
    analysis = []
    offset = 0.0
    for c in raw:
        if isinstance(c, dict):
            visible = list(c.get("visible") or c.get("notes") or [])
            hidden = list(c.get("hidden") or [])
        else:  # bare list of midi
            visible, hidden = list(c), []
        chords.append({"offset": offset, "duration": 1.0,
                       "visible": visible, "hidden": hidden})
        if isinstance(c, dict) and c.get("answer"):
            analysis.append({
                "offset": offset,
                "content": {"functional_label": c.get("answer")},
                "is_target": True,
            })
        offset += 1.0
    legacy_type = data.get("type")
    is_identification = legacy_type == "identification"
    payload = build_chordal_umto_payload(
        exercise_id=str(data.get("id", "LEGACY")),
        source=data.get("description", "Legacy exercise"),
        key=data.get("key", "C"), meter=meter, clef=clef,
        complexity_score=complexity_score,
        mode=InteractionMode.IDENTIFICATION if is_identification else InteractionMode.PLAYBACK,
        chords=chords, analysis=analysis,
    )
    if is_identification:
        choices = []
        for c in raw:
            if isinstance(c, dict):
                for choice in c.get("choices") or []:
                    if choice not in choices:
                        choices.append(choice)
        payload["analysisType"] = data.get("analysisType", "chord_quality")
        payload["inputMode"] = data.get("inputMode", "dropdown")
        payload["identMode"] = data.get("identMode", "practice")
        payload["allowed_answers"] = choices
    return payload


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


def save_umto_chord_id_exercise(
    *,
    description: str,
    author,
    chord_key: str,
    midi_notes: list,
    answer: str,
    choices: list,
    skill_tags: list,
    complexity: int,
    is_public: bool = True,
    overwrite: bool = False,
) -> "Exercise":
    """Save a single root-position chord quality identification exercise.

    chord_key: HarmonyLab key string (e.g. "jG_") used for staff rendering/accidental display.
    midi_notes: sorted list of MIDI integers for the chord.
    answer: quality display label (e.g. "major", "dominant 7").
    choices: ordered list of answer choices shown to the student.
    """
    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source="Identify the chord quality.",
            key=chord_key,
            meter="4/4",
            clef="keyboard",
            complexity_score=complexity,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="dropdown",
            unit=5,
        ),
        voices=Voices(),
        analysis=[],
        grading=[],
    )

    payload = {
        "type": "identification",
        "isUMTO": True,
        "mode": InteractionMode.IDENTIFICATION.value,
        "analysisType": "chord_quality",
        "inputMode": "dropdown",
        "identMode": "practice",
        "staffDistribution": "keyboard",
        "key": chord_key,
        "meter": "4/4",
        "complexity_score": complexity,
        "introText": "Identify the chord quality.",
        "reviewText": "Well done!",
        "chord": [
            {
                "notes": sorted(midi_notes),
                "answer": answer,
                "choices": choices,
                "rhythmValue": "w",
            }
        ],
        "score": {
            "meta": {
                "key": chord_key,
                "time": "4/4",
                "clef": "keyboard",
                "staffDistribution": "keyboard",
            },
            "measures": [],
            "umto": umto.model_dump(mode="json"),
        },
        "grading": [],
    }

    UMTO.model_validate(payload["score"]["umto"])

    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

    if ex is None:
        ex = Exercise(
            description=description,
            data=payload,
            authored_by=author,
            is_public=is_public,
            skill_tags=list(skill_tags),
            complexity=complexity,
        )
        ex.save()
    else:
        ex.data = payload
        ex.skill_tags = list(skill_tags)
        ex.complexity = complexity
        ex.is_public = is_public
        ex.save(update_fields=["data", "skill_tags", "complexity", "is_public"])

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
    complexity: int = 2,
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
            complexity=complexity,
        )
    else:
        ex.data = data
        ex.skill_tags = skill_tags
        ex.complexity = complexity
        ex.is_public = is_public

    if ex._state.adding:
        ex.save()
    else:
        ex.save(update_fields=["data", "skill_tags", "complexity", "is_public"])
    ex.data["exerciseId"] = ex.id
    ex.save(update_fields=["data"])
    return ex


def save_umto_key_sig_exercise(
    *,
    description: str,
    author,
    problems: list[dict],
    level: int = 1,
    is_public: bool = True,
    overwrite: bool = False,
) -> "Exercise":
    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=f"Unit 3 Key Signatures — Level {level}",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=3,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="text",
            unit=3,
        ),
        voices=Voices(),
        analysis=[],
        grading=[],
    )

    skill_tags = ["unit:3", "unit:3_key_signature"]

    payload = {
        "type": "umto_key_signature",
        "isUMTO": True,
        "mode": InteractionMode.IDENTIFICATION.value,
        "analysisType": "unit3_key_signature",
        "inputMode": "text",
        "staffDistribution": "none",
        "complexity_score": 3,
        "level": level,
        "key": "C",
        "meter": "4/4",
        "clef": "treble",
        "introText": f"Identify the following key signatures. Level {level}.",
        "reviewText": "Well done!",
        "allowed_answers": [],
        "problems": problems,
        "score": {
            "meta": {"key": "C", "time": "4/4", "clef": "treble", "staffDistribution": "none"},
            "measures": [],
            "umto": umto.model_dump(mode="json"),
        },
        "grading": [],
    }

    UMTO.model_validate(payload["score"]["umto"])

    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

    if ex is None:
        ex = Exercise(
            description=description,
            data=payload,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags,
            complexity=3,
        )
        ex.save()
    else:
        ex.data = payload
        ex.is_public = is_public
        ex.skill_tags = skill_tags
        ex.complexity = 3
        ex.save(update_fields=["data", "is_public", "skill_tags", "complexity"])

    ex.data["exerciseId"] = ex.id
    ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.save(update_fields=["data"])
    return ex
