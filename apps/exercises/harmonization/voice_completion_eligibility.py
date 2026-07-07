from __future__ import annotations

from typing import Any

from apps.exercises.harmonization import targets

ALL_VOICES = ("S", "A", "T", "B")


class VoiceCompletionEligibilityError(ValueError):
    """Raised when a UMTO source is not eligible for per-voice harmonization completion."""


def validate_voice_completion_eligibility(umto: dict[str, Any]) -> str:
    """Validate a score_kind="voices" UMTO for per-voice harmonization completion.

    Milestone-1 eligibility: bass is locked (never the missing voice); exactly one
    of S/A/T is missing; every locked voice has a pitched (non-rest) event at every
    bass-onset target; the missing voice has exactly one fresh attack per bass onset,
    with no ties or rests at target onsets and no attacks between bass onsets.

    Returns the id of the single missing voice (S, A, or T) on success. Raises
    VoiceCompletionEligibilityError naming the onset/voice on failure -- callers
    must not treat a validation failure as tolerable and proceed with generation.
    """
    metadata = umto.get("metadata", {})
    locked_voices = list(metadata.get("locked_voices") or [])

    if "B" not in locked_voices:
        raise VoiceCompletionEligibilityError(
            "Bass must be in locked_voices for per-voice harmonization completion "
            "-- bass is never the missing voice in this milestone."
        )

    missing_candidates = [v for v in ALL_VOICES if v != "B" and v not in locked_voices]
    if len(missing_candidates) != 1:
        raise VoiceCompletionEligibilityError(
            "Expected exactly one missing voice besides bass, found "
            f"{len(missing_candidates)} ({missing_candidates or 'none'}). "
            f"locked_voices={locked_voices}"
        )
    missing_voice = missing_candidates[0]

    voices = umto.get("voices", {})
    bass_events = voices.get("B", [])
    bass_onsets = targets.voice_attack_offsets(bass_events)
    if not bass_onsets:
        raise VoiceCompletionEligibilityError(
            "Bass voice has no note attacks -- cannot derive a target grid."
        )

    for offset in bass_onsets:
        for voice_id in locked_voices:
            payload = targets.locked_voice_payload(umto, voice_id, offset)
            if payload is None:
                raise VoiceCompletionEligibilityError(
                    f"Locked voice {voice_id} has a rest at bass onset {offset} "
                    "-- full four-voice texture is required at every target onset."
                )

    missing_events = voices.get(missing_voice, [])
    missing_attack_offsets = targets.voice_attack_offsets(
        missing_events, exclude_tied_stops=True
    )

    if missing_attack_offsets != bass_onsets:
        extra = sorted(set(missing_attack_offsets) - set(bass_onsets))
        absent = sorted(set(bass_onsets) - set(missing_attack_offsets))
        if extra:
            raise VoiceCompletionEligibilityError(
                f"Voice {missing_voice} has attack(s) at offset(s) {extra} that "
                "don't align with a bass onset (passing tone or independent "
                "rhythm) -- source must be homophonic for this milestone."
            )
        raise VoiceCompletionEligibilityError(
            f"Voice {missing_voice} has no fresh attack at bass onset(s) {absent} "
            "-- likely a tie or rest at a target onset, which isn't supported "
            "in this milestone."
        )

    return missing_voice
