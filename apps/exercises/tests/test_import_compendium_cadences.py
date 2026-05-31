# -*- coding: utf-8 -*-
"""Tests for import_compendium_cadences management command (pure, no DB).

The central assertion: after iterating all templated examples across their
mode-appropriate key set, units 10, 12, and 14 are populated. Unit 9 (simple
cadences) must also appear. If this fails, the histogram is printed so the
caller can diagnose coverage gaps.
"""
import pytest

pytest.importorskip("music21")

from apps.exercises.compendium_source import load_cadence_examples
from apps.exercises.compendium_prep import prepare_compendium_exercise

KEYS_BY_MODE = {
    "major": ["C", "G", "D", "F", "Bb"],
    "minor": ["A", "E", "B", "D", "G"],
}


def test_corpus_populates_units_10_12_14():
    """Across all templated examples x their mode's keys, units 10/12/14 are populated."""
    units: dict[int, int] = {}
    skipped = 0
    for e in load_cadence_examples():
        for tonic in KEYS_BY_MODE[e["mode"]]:
            prep = prepare_compendium_exercise(e, tonic)
            if prep is None:
                skipped += 1
                continue
            u = prep["unit"]
            units[u] = units.get(u, 0) + 1

    # The whole point: higher units are reached, not just 9.
    for u in (10, 12, 14):
        assert units.get(u, 0) > 0, (
            f"unit {u} unpopulated; histogram={units}; skipped={skipped}"
        )
    assert units.get(9, 0) > 0, (
        f"unit 9 unpopulated; histogram={units}; skipped={skipped}"
    )
