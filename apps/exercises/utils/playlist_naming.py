import re

_LEADING_UNIT_RE = re.compile(r"^Units?\s+\d", re.IGNORECASE)
_UNIT_TAG_RE = re.compile(r"^unit:(\w+)$")


def apply_unit_prefix(playlist_name: str, skill_tags: list) -> str:
    """Prepend "Unit N — " (or "Units N, M — " for several) to a new playlist
    name when skill_tags carries unit:N tags, matching existing playlist naming
    convention (e.g. "Unit 20 — Modulation II (play)"). No-op if the name
    already starts with "Unit"/"Units" or no unit tag is present.
    """
    if not playlist_name or _LEADING_UNIT_RE.match(playlist_name):
        return playlist_name

    units = []
    for tag in skill_tags or []:
        match = _UNIT_TAG_RE.match(tag) if isinstance(tag, str) else None
        if match and match.group(1) not in units:
            units.append(match.group(1))

    if not units:
        return playlist_name

    label = "Unit" if len(units) == 1 else "Units"
    return f"{label} {', '.join(units)} — {playlist_name}"
