from copy import deepcopy


VOICE_MAP = {
    "soprano": ("treble", 0),
    "alto": ("treble", 1),
    "tenor": ("bass", 0),
    "bass": ("bass", 1),
}


def strip_to_voice(score, voice_name):
    if voice_name not in VOICE_MAP:
        raise ValueError(f"Unsupported voice '{voice_name}'")

    staff_name, voice_idx = VOICE_MAP[voice_name]
    new_measures = []

    for measure in score.get("measures", []):
        staff = measure.get("staves", {}).get(staff_name, {})
        voices = staff.get("voices", [])
        if voice_idx >= len(voices):
            raise ValueError(
                f"Voice '{voice_name}' not found in measure {measure.get('number', '?')}"
            )

        new_measure = deepcopy(measure)
        # Always preserve both staves, even if empty, so vexflow_adapter doesn't crash
        new_staves = {
            "treble": {"voices": []},
            "bass": {"voices": []},
        }
        new_staves[staff_name] = {"voices": [deepcopy(voices[voice_idx])]}
        new_measure["staves"] = new_staves
        new_measures.append(new_measure)

    out = deepcopy(score)
    out["measures"] = new_measures
    validate_pitch_voice(out, voice_name)
    return out


def validate_pitch_voice(score, voice_name):
    for measure in score.get("measures", []):
        for staff in measure.get("staves", {}).values():
            for voice in staff.get("voices", []):
                for item in voice.get("items", []):
                    if item.get("kind") == "chord":
                        raise ValueError(
                            f"Voice '{voice_name}' measure {measure.get('number', '?')} "
                            "contains a chord; pitch identification requires single notes"
                        )
