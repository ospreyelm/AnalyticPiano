"""
Figured bass calculator utilities.

compute_figured_bass() — derives raw and abbreviated figured bass from a music21
chord + key at import time.

abbreviate_figured_bass() — applies Kellner (1732) abbreviation rules to a raw
interval stack string (e.g. "7/5/3" → "7").
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Abbreviation table: maps frozenset of numeric parts → abbreviated form.
# Chromatic prefixes on individual intervals are stripped for matching, then
# reattached to the abbreviated output.
# ---------------------------------------------------------------------------

# Each entry: (sorted-descending tuple of nums without prefixes, abbreviated form).
# Chromatic prefixes are reattached after lookup by matching interval numbers.
# Empty string means "nothing" (root-position triad convention).
_ABBREV_TABLE = [
    # Root-position triads — use "5/3" (empty string is pedagogically confusing)
    (("8", "5", "3"), "5/3"),
    (("5", "3"),      "5/3"),
    # Chromatic root-position triad: only an accidental (on the 3rd or 5th)
    # handled separately below
    # First-inversion triad (various doublings)
    (("8", "6", "3"), "6"),
    (("6", "3", "3"), "6"),
    (("6", "3"),      "6"),
    # Second-inversion triad
    (("8", "6", "4"), "6/4"),
    (("6", "4"),      "6/4"),
    # Root-position seventh
    (("8", "7", "5", "3"), "7"),
    (("7", "5", "3"),      "7"),
    # First-inversion seventh
    (("6", "5", "3"), "6/5"),
    # Second-inversion seventh
    (("6", "4", "3"), "4/3"),
    # Third-inversion seventh
    (("6", "4", "2"), "4/2"),
    # 5/4 suspension resolution chord
    (("8", "5", "4"), "5/4"),
    (("5", "4", "3"), "5/4"),
    # Ninth chords
    (("9", "5", "3"), "9"),
    (("9", "7", "3"), "9/7"),
]

_ABBREV_MAP = {k: v for k, v in _ABBREV_TABLE}


def _split_interval(token: str) -> tuple[str, str]:
    """Split a token like 'b6', '#4', '4+', '3', '5°' into (prefix, num_str)."""
    m = re.match(r'^([#b+]*)(\d+)([+°]?)$', token)
    if not m:
        return "", token
    prefix = m.group(1) + m.group(3)
    return prefix, m.group(2)


def _normalize_tritone(token: str) -> str:
    """Convert tritone marker '+' suffix to standard quality notation.

    '5+' → '5°' (diminished fifth), '4+' → '4+' (augmented fourth, keep as-is).
    Prefix-style '+5' is also normalised.
    """
    token = token.strip()
    # Handle prefix-style: '+5'
    if token.startswith("+") and token[1:].isdigit():
        n = int(token[1:])
        return f"{n}°" if n >= 5 else f"{n}+"
    # Handle suffix-style: '5+'
    if token.endswith("+") and token[:-1].isdigit():
        n = int(token[:-1])
        return f"{n}°" if n >= 5 else f"{n}+"
    # Handle compound: prefix '#'/'b' + digit + '+' suffix e.g. '#5+'
    m = re.fullmatch(r"([#b]?)(\d+)\+", token)
    if m:
        prefix, num = m.groups()
        n = int(num)
        suffix = "°" if n >= 5 else "+"
        return f"{prefix}{n}{suffix}"
    return token


def abbreviate_figured_bass(raw: str) -> str:
    """Apply Kellner abbreviation rules to a raw stack string.

    Input: descending interval stack, e.g. "7/5/3", "b6/5/3", "8/5/#3"
    Output: abbreviated form, e.g. "7", "b6/5", "#"

    Unrecognized stacks pass through unchanged.
    """
    if not raw:
        return raw

    tokens = [t.strip() for t in raw.split("/")]
    prefixes = []
    nums = []
    for tok in tokens:
        prefix, num = _split_interval(tok)
        prefixes.append(prefix)
        nums.append(num)

    key = tuple(nums)

    # Special case: root-position triad with a chromatic 3rd or 5th
    # "8/5/#3" → "#", "8/#5/3" → "#5" (just the accidental prefix, not the number)
    if key in (("8", "5", "3"), ("5", "3")):
        # Find any non-empty prefix on non-octave intervals
        altered = [(prefixes[i], nums[i]) for i in range(len(nums))
                   if prefixes[i] and nums[i] != "8"]
        if altered:
            # Return just the accidental prefix(es), not the interval number
            return "".join(p for p, n in altered if p)
        return "5/3"

    abbreviated = _ABBREV_MAP.get(key)
    if abbreviated is None:
        # Unknown pattern — pass through unabbreviated
        return raw

    if not abbreviated:
        return abbreviated

    # Reattach prefixes: match each number in the abbreviated form back to its
    # original prefix from the full stack.
    abbrev_tokens = abbreviated.split("/")
    abbrev_nums_used = set()
    result_tokens = []
    for abbrev_tok in abbrev_tokens:
        _, abbrev_num = _split_interval(abbrev_tok)
        abbrev_nums_used.add(abbrev_num)
        # Find the prefix for this number in the original stack
        original_prefix = ""
        for i, num in enumerate(nums):
            if num == abbrev_num:
                original_prefix = prefixes[i]
                break
        result_tokens.append(_normalize_tritone(original_prefix + abbrev_tok))

    # Preserve any interval that had a chromatic prefix but was dropped by
    # abbreviation — e.g. #6 in #6/4/3 abbreviated to 4/3, or #3 in 8/6/#3→6.
    for i, num in enumerate(nums):
        if prefixes[i] and num not in abbrev_nums_used and num != "8":
            result_tokens.append(_normalize_tritone(prefixes[i] + num))

    # Re-sort entire output descending by interval number
    result_tokens.sort(key=lambda t: int(_split_interval(t)[1]), reverse=True)
    return "/".join(result_tokens)


def compute_figured_bass(chord_element, key, next_pitch_map: dict | None = None) -> tuple[str, str]:
    """Compute raw and abbreviated figured bass from a music21 chord + key.

    Returns (raw_figured_bass, figured_bass).
    raw_figured_bass: descending interval stack, e.g. "8/5/3", "7/5/3"
    figured_bass: Kellner-abbreviated form, e.g. "", "7", "4/2"

    Chromatic prefix rules:
    - Pitch diatonic to key → no prefix
    - Pitch raised from diatonic → #
    - Pitch lowered from diatonic → b
    - Tritone interval (6 semitones, aug4/dim5) above bass → + marker

    next_pitch_map (optional): {midi_of_current_pitch: midi_of_next_pitch_in_same_voice}.
    Used for 9-vs-2 disambiguation:
    - Generic 9th whose voice descends next → labelled 9 (resolves downward to 8).
    - Generic 9th whose voice stays or ascends → labelled 2 (melodic passing 2nd).
    Without next_pitch_map, a 9th is always labelled 9 (previous behaviour).

    Suspensions (multi-beat) are NOT detected here; that requires look-ahead
    over consecutive slices — handled in _build_figured_bass_overrides().
    """
    from music21 import interval as m21interval

    bass = chord_element.bass()
    if bass is None:
        return "", ""

    # Build set of diatonic pitch names in the key (e.g. {"C", "D", "E", "F", "G", "A", "B"})
    diatonic_names = {p.name for p in key.pitches}  # e.g. "C", "C#", "Bb" etc.
    # Also track letter+accidental pairs for chromatic comparison
    diatonic_step_alter = {(p.step, p.alter) for p in key.pitches}

    intervals = {}  # num_str → prefix (last write wins for duplicates)

    for pitch in chord_element.pitches:
        if pitch == bass:
            continue
        itv = m21interval.Interval(bass, pitch)
        directed = itv.generic.directed  # e.g. 3, 5, 8, -3 ...
        generic = abs(directed)

        # Reduce compound intervals but preserve 9ths (conventional in figured bass).
        # 10→3, 11→4, 12→5, 13→6, 14→7, 15→8; keep 8 and 9 as-is.
        if generic > 9:
            generic = ((generic - 1) % 7) + 1
        if generic == 1:
            generic = 8  # unison above bass = octave

        # 9-vs-2 disambiguation: if voice context available and interval is a 9th,
        # check whether the voice descends next. Descends → 9; stays/rises → 2.
        if generic == 9 and next_pitch_map is not None:
            next_midi = next_pitch_map.get(pitch.midi)
            if next_midi is not None and next_midi >= pitch.midi:
                generic = 2  # stays or rises → label as 2

        num_str = str(generic)

        # Determine chromatic prefix
        semitones = abs(itv.semitones) % 12
        if semitones == 0 and generic != 8:
            semitones = 12  # true octave

        # Tritone check (6 semitones = aug4 or dim5)
        is_tritone = (semitones == 6)

        # Check diatonicism: compare pitch step + alter to key
        pitch_in_diatonic = (pitch.step, pitch.alter) in diatonic_step_alter

        if is_tritone:
            # Tritone always gets + suffix regardless of diatonicism (spec §2)
            intervals[num_str] = num_str + "+"
        elif pitch_in_diatonic:
            intervals[num_str] = num_str
        else:
            # Determine direction of alteration from diatonic
            # Find the diatonic pitch with the same step
            diatonic_alter = next(
                (a for (s, a) in diatonic_step_alter if s == pitch.step), 0
            )
            if pitch.alter > diatonic_alter:
                intervals[num_str] = "#" + num_str
            else:
                intervals[num_str] = "b" + num_str

    if not intervals:
        return "", ""

    # Sort descending by numeric value
    def _num(token):
        m = re.search(r'\d+', token)
        return int(m.group()) if m else 0

    sorted_tokens = sorted(intervals.values(), key=_num, reverse=True)
    raw = "/".join(sorted_tokens)
    abbreviated = abbreviate_figured_bass(raw)
    return raw, abbreviated
