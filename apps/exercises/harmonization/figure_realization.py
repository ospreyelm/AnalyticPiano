"""Figured-bass realization table — which figure tones are *required* vs merely
*allowed*, per voice count.

A figure names the generic intervals available above the bass; it does NOT say
all of them must sound. Kellner (1732) / Remes give, for each chord, what you
actually play in 4-, 3-, and 2-voice textures. This module encodes that table
and derives the required tones for a target given its voice-count policy.

SOURCE OF TRUTH. Do not change a realization here without expert (avner) review:
these values are music theory, not implementation detail. See
docs/music-theory-canon.md (§"Figured bass — required vs allowed tones") and
docs/superpowers/specs/2026-06-26-figured-bass-required-tones-design.md.

Conventions:
- Keys/cells use generic interval NUMBERS as ints. "8" (octave) doubles the bass
  and is dropped at the pitch-class level — it never appears below.
- A voice-count cell is a list of ALTERNATE realizations ("choose one"); the
  must-play set at that voice count is the intersection of the alternates.
- A voice count absent from a prototype = not realizable there ("none").
- Invariant: a chord containing 2 or 9 never contains 8 (you don't double the
  bass at the octave under a second or ninth). Asserted at import.
"""
from __future__ import annotations

# prototype key (string, descending distinct intervals) -> {voices: [alt-sets]}
TABLE: dict[str, dict[int, list[frozenset[int]]]] = {
    # --- Core: triads, sevenths, inversions ---
    "5/3":   {4: [frozenset({5, 3})], 3: [frozenset({5, 3}), frozenset({3})], 2: [frozenset({3})]},
    "6/3":   {4: [frozenset({6, 3})], 3: [frozenset({6, 3})], 2: [frozenset({6})]},
    "6/4":   {4: [frozenset({6, 4})], 3: [frozenset({6, 4})]},
    "7/5/3": {4: [frozenset({7, 5, 3})], 3: [frozenset({7, 3})], 2: [frozenset({7})]},
    "6/5/3": {4: [frozenset({6, 5, 3})], 3: [frozenset({6, 5})]},
    "6/4/3": {4: [frozenset({6, 4, 3})], 3: [frozenset({6, 3}), frozenset({6, 4})]},
    "6/4/2": {4: [frozenset({6, 4, 2})], 3: [frozenset({4, 2})], 2: [frozenset({2})]},
    "5/4":   {4: [frozenset({5, 4})], 3: [frozenset({5, 4})]},
    # --- Ninth chords ---
    # 9/7/5 and 9/7/3 are DISTINCT figures (double suspensions resolving to 8/5/3
    # and 8/6/3 respectively); both drop to 9/7 at three voices. 9/7/5/3 is the
    # later-repertoire complete ninth (too many notes for four parts), realized as
    # either 9/7/3 or 9/7/5. All three keep the 9th+7th dissonances required.
    "9/7/5":   {4: [frozenset({9, 7, 5})], 3: [frozenset({9, 7})]},
    "9/7/3":   {4: [frozenset({9, 7, 3})], 3: [frozenset({9, 7})]},
    "9/7/5/3": {4: [frozenset({9, 7, 3}), frozenset({9, 7, 5})], 3: [frozenset({9, 7})]},
    "9/5/3":   {4: [frozenset({9, 5, 3})], 3: [frozenset({9, 3})], 2: [frozenset({9})]},
    "9/6/3":   {4: [frozenset({9, 6, 3})], 3: [frozenset({9, 6})]},
    "9/7/4":   {4: [frozenset({9, 7, 4})]},
    # --- Suspension / bass-2 figures ---
    "5/2":   {4: [frozenset({5, 2})], 3: [frozenset({5, 2})]},
    "5/3/2": {4: [frozenset({5, 3, 2})], 3: [frozenset({3, 2})]},
    "5/4/2": {4: [frozenset({5, 4, 2})]},
    "6/2":   {4: [frozenset({6, 2})]},
    "7/6/3": {4: [frozenset({7, 6, 3})]},
    "7/5/2": {4: [frozenset({7, 5, 2})]},
    "7/4/2": {4: [frozenset({7, 4, 2})]},
    "7/4/3": {4: [frozenset({7, 4, 3})]},
}

# Figures that are not their own row but resolve to one (context-collapsed).
ALIASES: dict[str, str] = {
    "9/6/4": "6/4/2",  # genuine 9/6/4 only resolves into 8/6/4; default to 6/4/2
}


def _full_set(by_voice: dict[int, list[frozenset[int]]]) -> frozenset[int]:
    """Union of every interval named across all realizations of a prototype."""
    out: set[int] = set()
    for alts in by_voice.values():
        for alt in alts:
            out |= set(alt)
    return frozenset(out)


def _assert_invariant() -> None:
    for key, by_voice in TABLE.items():
        nums = _full_set(by_voice)
        if (2 in nums or 9 in nums) and 8 in nums:
            raise AssertionError(f"figure_realization: {key} violates 2|9 -> no 8")


_assert_invariant()


def _parse_numbers(raw_figure: str) -> tuple[frozenset[int], frozenset[int]]:
    """Return (present_numbers, altered_numbers) for a raw figure string.

    Drops octave (8). A token is altered if it carries #, b, n, ° or +.
    """
    import re

    present: set[int] = set()
    altered: set[int] = set()
    for tok in (raw_figure or "").split("/"):
        tok = tok.strip()
        if not tok:
            continue
        m = re.search(r"(\d+)", tok)
        if not m:
            continue
        n = int(m.group(1))
        if re.search(r"[#bn]|°|\+", tok):
            altered.add(n)
        if n == 8:
            continue
        present.add(n)
    return frozenset(present), frozenset(altered)


# Reverse index: every realization number-set (and full set) -> prototype key.
# On collision, prefer the prototype whose full set is smallest (most specific).
def _build_index() -> dict[frozenset[int], str]:
    idx: dict[frozenset[int], str] = {}
    for key, by_voice in TABLE.items():
        full = _full_set(by_voice)
        # Seed the key's own parsed set too: a prototype whose realizations omit a
        # named tone (e.g. 9/7/5/3, whose 4-voice cell {9,7,3} drops the 5th) must
        # still resolve from its complete figure string, not fall through to fail-safe.
        from_key = frozenset(_parse_numbers(key)[0])
        candidate_sets = {full, from_key}
        for alts in by_voice.values():
            candidate_sets.update(alts)
        for s in candidate_sets:
            if not s:
                continue
            prior = idx.get(s)
            if prior is None or len(_full_set(TABLE[key])) < len(_full_set(TABLE[prior])):
                idx[s] = key
    return idx


_INDEX = _build_index()


def normalize(raw_figure: str) -> tuple[str | None, frozenset[int]]:
    """Map a raw figure to (prototype_key, altered_numbers).

    prototype_key is a TABLE key, an ALIAS target, or None when no prototype
    matches (caller fails safe = all present tones required).
    """
    if raw_figure in ALIASES:
        _, altered = _parse_numbers(raw_figure)
        return ALIASES[raw_figure], altered
    present, altered = _parse_numbers(raw_figure)
    key = _INDEX.get(present)
    return key, altered


def required_numbers(
    prototype_key: str,
    voice_count_policy: dict,
    present: set[int] | frozenset[int],
    altered: frozenset[int],
) -> set[int]:
    """Required generic intervals for a prototype under a voice-count policy.

    required = (intersection over voice counts in [min..max] of each count's
    must-play set) restricted to tones actually present, plus any altered tones
    that are present. If no voice count in range is realizable, fall back to the
    prototype's full set.
    """
    by_voice = TABLE[prototype_key]
    lo = int(voice_count_policy.get("min", 3) or 3)
    hi = int(voice_count_policy.get("max", 4) or 4)
    per_voice: list[set[int]] = []
    for v in range(lo, hi + 1):
        cells = by_voice.get(v)
        if not cells:  # 'none' at this voice count
            continue
        must = set(cells[0])
        for alt in cells[1:]:
            must &= set(alt)
        per_voice.append(must)
    if per_voice:
        base = set(per_voice[0])
        for s in per_voice[1:]:
            base &= s
    else:
        base = set(_full_set(by_voice))
    present_set = set(present)
    return (base & present_set) | (set(altered) & present_set)
