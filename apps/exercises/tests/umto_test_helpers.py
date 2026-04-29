"""Helpers for tests that need to create Exercise rows without manually
shaping UMTO payloads."""
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode


DEFAULT_CIR = {
    "meta": {"key": "C", "time": "4/4"},
    "measures": [{
        "staves": {"treble": {"voices": [{"items": [
            {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
        ]}]}}
    }]
}


def make_umto_exercise(
    author,
    *,
    description="test",
    unit=1,
    skill_tags=None,
    complexity=11,
    mode=None,
    input_mode="dropdown",
):
    return save_umto_exercise(
        description=description,
        score_data=DEFAULT_CIR,
        author=author,
        skill_tags=skill_tags or [f"unit:{unit}"],
        complexity=complexity,
        umto_kwargs=dict(
            exercise_id="TEMP",
            source=description,
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=mode or InteractionMode.PLAYBACK,
            target_voice="soprano",
            unit=unit,
            input_mode=input_mode,
        ),
    )
