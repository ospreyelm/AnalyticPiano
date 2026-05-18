from __future__ import annotations

from typing import Any

from apps.exercises.harmonization.figures import derive_required_notes, expand_figure_string


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


def build_targets_from_umto(umto: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = umto.get("metadata", {})
    key_name = metadata.get("key") or "C"
    locked_voices: list[str] = metadata.get("locked_voices") or ["B"]
    vcp = metadata.get("voice_count_policy") or {}
    voice_count_policy = {
        "expected": vcp.get("expected"),
        "min": vcp.get("min", 3),
        "max": vcp.get("max", 4),
    }

    bass_events = umto.get("voices", {}).get("B", [])
    targets = []
    for analysis in umto.get("analysis", []):
        offset = float(analysis["offset"])
        content = analysis.get("content", {})

        # Skip slices where the bass is held (inner-voice passing tones/suspensions).
        # Keep slices where the bass itself attacks a new note — this naturally
        # handles compound figures like 4-3 where the bass steps under a suspension.
        if not _voice_attacks_at_offset(bass_events, offset):
            continue

        bass = _locked_voice_payload(umto, "B", offset)
        if bass is None:
            continue

        # raw_figured_bass drives pitch derivation (full interval stack, no dropped intervals).
        # figured_bass (abbreviated) is display-only.
        raw_figure = content.get("raw_figured_bass") or content.get("figured_bass") or "5/3"
        display_figure = content.get("figured_bass") or raw_figure
        local_key = content.get("local_key") or key_name

        derived = derive_required_notes(
            key_name=local_key,
            bass_name=bass["spelling"],
            figure=raw_figure,
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
