# -*- coding: utf-8 -*-
"""Curated, music-vetted Roman-numeral templates for Galant-compendium cadences.

Keyed by (page_title, mode). Each value is an ordered list of structural targets
(offset_in_quarter_notes, roman_numeral). RN strings match the answer vocabulary
in unit_allowed_answers. Auto-derivation is intentionally NOT used — music21
analysis of these figured examples produces suspension/passing noise. These
templates are the source of truth for student-facing labels.

The cadential six-four is labeled "Cad64" (dominant function), not I64/i64.

Page-types intentionally omitted this round (return None):
  - Two-voice cadences (harmonically ambiguous for roman ID)
  - Double Cadences (structural reading deferred)
  - "Active" Tenor / Cudworth (heavily ornamented)
"""
from __future__ import annotations

COMPENDIUM_TEMPLATES: dict[tuple[str, str], list[tuple[float, str]]] = {
    ("Simple Cadences in Three Voices", "major"): [(0.0, "I"), (2.0, "V"), (4.0, "I")],
    ("Simple Cadences in Three Voices", "minor"): [(0.0, "i"), (2.0, "V"), (4.0, "i")],
    ("Simple Cadences in Four Voices", "major"): [(0.0, "I"), (2.0, "V"), (4.0, "I")],
    ("Simple Cadences in Four Voices", "minor"): [(0.0, "i"), (2.0, "V"), (4.0, "i")],
    ("Compound Cadences in Three Voices", "major"): [(0.0, "I"), (1.0, "I6"), (2.0, "V"), (4.0, "I")],
    ("Compound Cadences in Three Voices", "minor"): [(0.0, "i"), (1.0, "i6"), (2.0, "V"), (4.0, "i")],
    ("Compound Cadences with 5/4 in Four Voices", "major"): [(0.0, "I"), (1.0, "I6"), (2.0, "V"), (4.0, "I")],
    ("Compound Cadences with 5/4 in Four Voices", "minor"): [(0.0, "i"), (1.0, "i6"), (2.0, "V"), (4.0, "i")],
    ("Compound Cadences with 6/5 in Four Voices", "major"): [(0.0, "I"), (1.0, "I6"), (2.0, "ii65"), (3.0, "V"), (4.0, "I")],
    ("Compound Cadences with 6/5 in Four Voices", "minor"): [(0.0, "i"), (1.0, "i6"), (2.0, "iiø65"), (3.0, "V"), (4.0, "i")],
    ("Compound Cadences with 6/4 in Four Voices", "major"): [(0.0, "I"), (1.0, "I6"), (2.0, "Cad64"), (3.0, "V"), (4.0, "I")],
    ("Compound Cadences with 6/4 in Four Voices", "minor"): [(0.0, "i"), (1.0, "i6"), (2.0, "Cad64"), (3.0, "V"), (4.0, "i")],
    ("Evaded Cadences in Three Voices", "major"): [(0.0, "I"), (1.0, "I6"), (2.0, "ii65"), (3.0, "V"), (4.0, "vi")],
    ("Evaded Cadences in Three Voices", "minor"): [(0.0, "i"), (1.0, "i6"), (2.0, "iiø65"), (3.0, "V"), (4.0, "bVI")],
    ("Evaded Cadences in Four Voices", "major"): [(0.0, "I"), (1.0, "I6"), (2.0, "ii65"), (3.0, "V"), (4.0, "vi")],
    ("Evaded Cadences in Four Voices", "minor"): [(0.0, "i"), (1.0, "i6"), (2.0, "iiø65"), (3.0, "V"), (4.0, "bVI")],
}


def template_for(page_title: str, mode: str):
    """Return the curated target list for a (page_title, mode), or None if not templated."""
    return COMPENDIUM_TEMPLATES.get((page_title, mode))
