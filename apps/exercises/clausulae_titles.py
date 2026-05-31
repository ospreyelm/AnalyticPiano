"""Clausulae cadence families -> Compendium page_title strings + title helpers.

Titles use the musical-type vocabulary from the Galant Compendium so student
exercises read as harmony, not Clausulae jargon (per the lessons spec).

- student_title(): long, human-facing; stored in UMTO metadata.source (no limit).
- short_description(): <=60-char stable key for Exercise.description (idempotency).
"""
from __future__ import annotations

import hashlib

_BASE = {
    ("simple", 2): "Simple Cadences in Two Voices",
    ("simple", 3): "Simple Cadences in Three Voices",
    ("simple", 4): "Simple Cadences in Four Voices",
    ("compound", 2): "Compound Cadences in Two Voices",
    ("compound", 3): "Compound Cadences in Three Voices",
    ("double", 3): "Double Cadences in Three Voices",
    ("double", 4): "Double Cadences in Four Voices",
}

_COMPOUND_4V_BY_FIGURE = {
    frozenset({5, 4}): "Compound Cadences with 5/4 in Four Voices",
    frozenset({6, 5}): "Compound Cadences with 6/5 in Four Voices",
    frozenset({6, 4}): "Compound Cadences with 6/4 in Four Voices",
}
_COMPOUND_4V_DEFAULT = "Compound Cadences with 6/4 in Four Voices"


def page_title(family: str, n_voices: int, upper_figures: set | None = None) -> str:
    if family == "compound" and n_voices == 4:
        if upper_figures is not None:
            return _COMPOUND_4V_BY_FIGURE.get(frozenset(upper_figures), _COMPOUND_4V_DEFAULT)
        return _COMPOUND_4V_DEFAULT
    try:
        return _BASE[(family, n_voices)]
    except KeyError as exc:
        raise KeyError(f"No page_title for family={family!r} n_voices={n_voices}") from exc


def student_title(family: str, n_voices: int, *, key: str,
                  upper_figures: set | None = None) -> str:
    """Long student-facing title for metadata.source."""
    return f"{page_title(family, n_voices, upper_figures=upper_figures)} in {key} major"


def short_description(family: str, n_voices: int, *, key: str, unit: int,
                      fingerprint: str) -> str:
    """<=60-char stable idempotency key. Prefix is human-scannable; hash ensures
    uniqueness per voice combination."""
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:8]
    desc = f"RfC u{unit} {family} {n_voices}v {key} {digest}"
    assert len(desc) <= 60, f"description too long ({len(desc)}): {desc!r}"
    return desc
