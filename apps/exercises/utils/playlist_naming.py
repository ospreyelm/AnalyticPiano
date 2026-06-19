import re

_LEADING_UNIT_RE = re.compile(r"^Units?\s+\d", re.IGNORECASE)
_UNIT_TAG_RE = re.compile(r"^unit:(\w+)$")
_TRAILING_MODE_RE = re.compile(r"\(([a-z_]+)\)\s*$", re.IGNORECASE)

# Display label per mode, used in the trailing "(Mode)" suffix.
_MODE_LABELS = {
    "play": "Play",
    "roman": "Roman",
    "figures": "Figures",
    "identify": "Identify",
    "harmonization": "Harmonization",
}


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
    """Build a new playlist's name for a manually-authored save (the /teacher/play/
    Save dialog and MusicXML import — never Bach/Riemenschneider-derived content,
    which uses its own playlist-naming path).

    Always appends " Exercise ({Mode})" so the playlist's accepted mode is encoded
    in its name and "Exercise" distinguishes it from Bach-corpus playlists (which
    use a bare "(mode)" suffix with no "Exercise" marker, e.g. "Unit 9 — Tonic and
    Dominant (play)"). Prepends "Unit N — " only when skill_tags carries unit tags.
    No-op on the prefix if base_name already starts with "Unit"/"Units" (avoids
    double-prefixing a name the teacher already typed with one).
    """
    if not base_name:
        return base_name

    prefix = "" if _LEADING_UNIT_RE.match(base_name) else _unit_prefix(skill_tags)
    mode_label = _MODE_LABELS.get(mode, mode.capitalize() if mode else "Play")
    return f"{prefix}{base_name} Exercise ({mode_label})"


def extract_playlist_mode(playlist_name: str) -> str | None:
    """Extract the lowercase mode token from a playlist's trailing "(Mode)" suffix
    (works for both "... Exercise (Mode)" and bare Bach-corpus "... (mode)" names).
    Returns None if the name has no parseable mode suffix — callers should treat
    that as "unrestricted" for backward compatibility with playlists predating
    this convention, not as a mismatch.
    """
    if not playlist_name:
        return None
    match = _TRAILING_MODE_RE.search(playlist_name)
    return match.group(1).lower() if match else None
