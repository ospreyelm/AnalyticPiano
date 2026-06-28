from __future__ import annotations

from typing import Any

from apps.exercises.harmonization.figures import (
    derive_required_notes,
    expand_figure_string,
    spelling_for_pc_in_key,
)


def _chord_bass_payload(chord: dict[str, Any], key_name: str = "C") -> dict[str, Any] | None:
    """Derive bass payload from a ChordEvent dict (chordal UMTO).

    Bass is the lowest MIDI in visible[]. spelling (when present) is positional
    over visible+hidden, so spelling[visible.index(bass_midi)] names the bass.
    When spelling is absent (or too short), fall back to a KEY-APPROPRIATE name
    via spelling_for_pc_in_key — not the chromatic sharp-side name — so that a
    flat-key bass (e.g. pc 10 in Bb major) spells "Bb" rather than "A#".
    derive_required_notes locates the bass in the key scale by step+alter; an
    enharmonic chromatic spelling is absent from the scale and would force a
    step-only fallback to the wrong scale degree, yielding incorrect allowedPcs.
    """
    visible = chord.get("visible") or []
    if not visible:
        return None
    bass_midi = min(visible)
    spelling_list = chord.get("spelling")
    if spelling_list:
        bass_idx = visible.index(bass_midi)
        name = (
            spelling_list[bass_idx]
            if bass_idx < len(spelling_list)
            else spelling_for_pc_in_key(key_name, bass_midi)
        )
    else:
        name = spelling_for_pc_in_key(key_name, bass_midi)
    return {
        "midi": bass_midi,
        "pc": bass_midi % 12,
        "spelling": name,
    }


def _build_targets_from_chordal_umto(umto: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = umto.get("metadata", {})
    key_name = metadata.get("key") or "C"
    locked_voices: list[str] = metadata.get("locked_voices") or ["B"]
    vcp = metadata.get("voice_count_policy") or {}
    voice_count_policy = {
        "expected": vcp.get("expected"),
        "min": vcp.get("min", 3),
        "max": vcp.get("max", 4),
    }

    chords = umto.get("chords") or []
    analyses = list(umto.get("analysis", []))
    grading_pcs_by_offset = _grading_pcs_by_offset(umto)
    used_analysis_indexes: set[int] = set()
    targets = []

    for chord in chords:
        offset = round(float(chord.get("offset", 0)), 5)
        bass = _chord_bass_payload(chord, key_name)
        if bass is None:
            continue

        analysis_idx, analysis = _analysis_for_target_offset(
            analyses=analyses,
            used_analysis_indexes=used_analysis_indexes,
            offset=offset,
            key_name=key_name,
            bass=bass,
            grading_pcs=grading_pcs_by_offset.get(offset, set()),
        )
        if analysis_idx is None or analysis is None:
            continue
        used_analysis_indexes.add(analysis_idx)

        content = analysis.get("content", {})
        raw_figure = content.get("raw_figured_bass") or content.get("figured_bass") or "5/3"
        display_figure = content.get("figured_bass") or raw_figure
        local_key = content.get("local_key") or key_name

        derived = derive_required_notes(
            key_name=local_key,
            bass_name=bass["spelling"],
            figure=raw_figure,
            voice_count_policy=voice_count_policy,
        )

        locked: dict[str, Any] = {}
        if "B" in locked_voices:
            locked["B"] = bass

        targets.append({
            "offset": offset,
            "bassMidi": bass["midi"],
            "bassPc": bass["pc"],
            "bassSpelling": bass["spelling"],
            "figures": expand_figure_string(raw_figure),
            "displayFigure": display_figure,
            "requiredUpperPcs": derived["required_upper_pcs"],
            "requiredNoteNames": derived["required_note_names"],
            "allowedPcs": derived["allowed_pcs"],
            "lockedVoices": locked,
            "voiceCountPolicy": voice_count_policy,
            "source": {
                "kind": "analysis_slice",
                "label": display_figure or content.get("roman_numeral") or "",
                "key": local_key,
            },
        })

    return targets


def _voice_event_at_offset(
    events: list[dict[str, Any]], offset: float
) -> dict[str, Any] | None:
    t = 0.0
    for event in events:
        dur = float(event.get("duration") or 0)
        if t <= offset < t + dur - 0.0001:
            return event if event.get("kind") == "note" else None
        t += dur
    return None


def _voice_attacks_at_offset(events: list[dict[str, Any]], offset: float) -> bool:
    """True when a new note event begins at exactly this offset (not held from earlier)."""
    t = 0.0
    for event in events:
        if abs(t - offset) < 0.0001:
            return event.get("kind") == "note"
        dur = float(event.get("duration") or 0)
        t += dur
        if t > offset + 0.0001:
            break
    return False


def _voice_attack_offsets(events: list[dict[str, Any]]) -> list[float]:
    offsets = []
    t = 0.0
    for event in events:
        if event.get("kind") == "note":
            offsets.append(round(t, 5))
        t += float(event.get("duration") or 0)
    return offsets


def _pitch_name(pitch: dict[str, Any]) -> str:
    alter = int(pitch.get("alter") or 0)
    acc = {0: "", 1: "#", -1: "b", 2: "##", -2: "bb"}.get(alter, "")
    return f"{pitch['step']}{acc}"


def _locked_voice_payload(
    umto: dict[str, Any], voice_id: str, offset: float
) -> dict[str, Any] | None:
    event = _voice_event_at_offset(
        umto.get("voices", {}).get(voice_id, []), offset
    )
    if not event or not event.get("pitch"):
        return None
    pitch = event["pitch"]
    midi = int(pitch["midi"])
    return {
        "midi": midi,
        "pc": midi % 12,
        "spelling": _pitch_name(pitch),
    }


def _grading_pcs_by_offset(umto: dict[str, Any]) -> dict[float, set[int]]:
    out: dict[float, set[int]] = {}
    for grading in umto.get("grading", []):
        try:
            offset = round(float(grading["offset"]), 5)
        except (KeyError, TypeError, ValueError):
            continue
        pcs = {
            int(midi) % 12
            for midi in grading.get("target_midi_pitches", [])
            if midi is not None
        }
        if pcs:
            out[offset] = pcs
    return out


def _analysis_matches_grading(
    *,
    analysis: dict[str, Any],
    key_name: str,
    bass: dict[str, Any],
    grading_pcs: set[int],
) -> bool:
    if not grading_pcs:
        return False
    content = analysis.get("content", {})
    raw_figure = content.get("raw_figured_bass") or content.get("figured_bass") or "5/3"
    local_key = content.get("local_key") or key_name
    try:
        derived = derive_required_notes(
            key_name=local_key,
            bass_name=bass["spelling"],
            figure=raw_figure,
        )
    except Exception:
        return False
    return set(derived["allowed_pcs"]) == grading_pcs


def _analysis_for_target_offset(
    *,
    analyses: list[dict[str, Any]],
    used_analysis_indexes: set[int],
    offset: float,
    key_name: str,
    bass: dict[str, Any],
    grading_pcs: set[int],
) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for idx, analysis in enumerate(analyses):
        if idx in used_analysis_indexes:
            continue
        if abs(round(float(analysis["offset"]), 5) - offset) < 0.0001:
            return idx, analysis

    for idx, analysis in enumerate(analyses):
        if idx in used_analysis_indexes:
            continue
        analysis_offset = round(float(analysis["offset"]), 5)
        if analysis_offset <= offset + 0.0001:
            continue
        if _analysis_matches_grading(
            analysis=analysis,
            key_name=key_name,
            bass=bass,
            grading_pcs=grading_pcs,
        ):
            return idx, analysis

    return None, None


def build_targets_from_umto(umto: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = umto.get("metadata", {})
    if metadata.get("score_kind") == "chordal":
        return _build_targets_from_chordal_umto(umto)
    key_name = metadata.get("key") or "C"
    locked_voices: list[str] = metadata.get("locked_voices") or ["B"]
    vcp = metadata.get("voice_count_policy") or {}
    voice_count_policy = {
        "expected": vcp.get("expected"),
        "min": vcp.get("min", 3),
        "max": vcp.get("max", 4),
    }

    bass_events = umto.get("voices", {}).get("B", [])
    analyses = list(umto.get("analysis", []))
    grading_pcs_by_offset = _grading_pcs_by_offset(umto)
    used_analysis_indexes: set[int] = set()
    targets = []
    for offset in _voice_attack_offsets(bass_events):
        bass = _locked_voice_payload(umto, "B", offset)
        if bass is None:
            continue

        analysis_idx, analysis = _analysis_for_target_offset(
            analyses=analyses,
            used_analysis_indexes=used_analysis_indexes,
            offset=offset,
            key_name=key_name,
            bass=bass,
            grading_pcs=grading_pcs_by_offset.get(offset, set()),
        )
        if analysis_idx is None or analysis is None:
            continue
        used_analysis_indexes.add(analysis_idx)

        content = analysis.get("content", {})

        # raw_figured_bass drives pitch derivation (full interval stack, no dropped intervals).
        # figured_bass (abbreviated) is display-only.
        raw_figure = content.get("raw_figured_bass") or content.get("figured_bass") or "5/3"
        display_figure = content.get("figured_bass") or raw_figure
        local_key = content.get("local_key") or key_name

        derived = derive_required_notes(
            key_name=local_key,
            bass_name=bass["spelling"],
            figure=raw_figure,
            voice_count_policy=voice_count_policy,
        )

        locked: dict[str, Any] = {}
        for voice_id in locked_voices:
            payload = _locked_voice_payload(umto, voice_id, offset)
            if payload is not None:
                locked[voice_id] = payload

        targets.append({
            "offset": offset,
            "bassMidi": bass["midi"],
            "bassPc": bass["pc"],
            "bassSpelling": bass["spelling"],
            "figures": expand_figure_string(raw_figure),
            "displayFigure": display_figure,
            "requiredUpperPcs": derived["required_upper_pcs"],
            "requiredNoteNames": derived["required_note_names"],
            "allowedPcs": derived["allowed_pcs"],
            "lockedVoices": locked,
            "voiceCountPolicy": voice_count_policy,
            "source": {
                "kind": "analysis_slice",
                "label": display_figure or content.get("roman_numeral") or "",
                "key": local_key,
            },
        })

    return targets
