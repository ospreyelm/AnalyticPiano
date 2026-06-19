from typing import Optional, TypedDict

from apps.exercises.umto import InteractionMode


class ModeResolution(TypedDict):
    interaction_mode: InteractionMode
    analysis_type: str
    display: Optional[dict]


def resolve_mode(mode: str) -> ModeResolution:
    """Map a teacher-play mode string to its InteractionMode, analysis_type,
    and any mode-driven display overrides.

    Single source of truth, shared by import_bach_phrases.py (Bach corpus
    pipeline) and lab/views.py AddExerciseView (manual editor), so the two
    pipelines can't drift into different meanings for the same mode string.
    """
    if mode in ("play", "play_figures"):
        interaction_mode = InteractionMode.PLAYBACK
    elif mode == "matching":
        interaction_mode = InteractionMode.ANALYSIS_MATCH
    elif mode == "harmonization":
        interaction_mode = InteractionMode.HARMONIZATION
    else:  # roman, figures, figures_unabbreviated
        interaction_mode = InteractionMode.IDENTIFICATION

    display: Optional[dict] = None
    if mode == "figures":
        analysis_type = "figured_bass"
    elif mode == "figures_unabbreviated":
        analysis_type = "figured_bass_unabbreviated"
    elif mode == "play_figures":
        analysis_type = "figured_bass"
        display = {
            "showFigures": True,
            "figureStyle": "figures_abbrev",
            "analysisRenderer": "notater",
        }
    else:
        analysis_type = "roman"

    return {
        "interaction_mode": interaction_mode,
        "analysis_type": analysis_type,
        "display": display,
    }
