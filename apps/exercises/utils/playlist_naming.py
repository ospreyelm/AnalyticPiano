import re

SUPPORTED_TEACHER_PLAY_MODES = (
    "play",
    "play_figures",
    "roman",
    "figures",
    "figures_unabbreviated",
    "matching",
    "harmonization",
)

_LEADING_UNIT_RE = re.compile(r"^Units?\s+\d", re.IGNORECASE)
_UNIT_TAG_RE = re.compile(r"^unit:(\w+)$")
_TRAILING_MODE_RE = re.compile(r"\(([a-z_]+)\)\s*$", re.IGNORECASE)

_MODE_LABELS = {
    "play": "Play",
    "play_figures": "Play + figures",
    "roman": "Roman",
    "figures": "Figures",
    "figures_unabbreviated": "Figures (unabbreviated)",
    "matching": "Matching",
    "harmonization": "Harmonization",
}


def canonical_mode_label(mode: str) -> str:
    try:
        return _MODE_LABELS[mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported interaction mode: {mode}") from exc


def build_canonical_playlist_name(unit: int, mode: str) -> str:
    return f"Unit {int(unit)} — Exercises ({canonical_mode_label(mode)})"


def _unit_prefix(skill_tags: list) -> str:
    units = []
    for tag in skill_tags or []:
        match = _UNIT_TAG_RE.match(tag) if isinstance(tag, str) else None
        if match and match.group(1) not in units:
            units.append(match.group(1))
    if not units:
        return ""
    label = "Unit" if len(units) == 1 else "Units"
    return f"{label} {', '.join(units)} — "


def build_new_playlist_name(base_name: str, skill_tags: list, mode: str) -> str:
    """Temporary compatibility helper for older teacher-play callers."""
    if not base_name:
        return base_name

    prefix = "" if _LEADING_UNIT_RE.match(base_name) else _unit_prefix(skill_tags)
    mode_label = canonical_mode_label(mode)
    return f"{prefix}{base_name} Exercise ({mode_label})"


def extract_playlist_mode(playlist_name: str) -> str | None:
    """Temporary compatibility helper for older teacher-play callers."""
    if not playlist_name:
        return None
    match = _TRAILING_MODE_RE.search(playlist_name)
    return match.group(1).lower() if match else None
