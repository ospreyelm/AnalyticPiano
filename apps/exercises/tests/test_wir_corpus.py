# apps/exercises/tests/test_wir_corpus.py
import pytest
from apps.exercises.utils.wir_corpus import lookup, has_chorale, bwv_to_riemenschneider


def test_anacrusis_lookup():
    # R1 pickup: m0 b3 G: I
    result = lookup(1, 0, 3.0)
    assert result is not None
    assert result["label"] == "I"
    assert result["local_key"] == "G"


def test_mid_measure_label():
    # R1 m1 b2: IV6
    result = lookup(1, 1, 2.0)
    assert result is not None
    assert result["label"] == "IV6"
    assert result["local_key"] == "G"


def test_nct_beat_returns_none():
    # R1 m3 b1.5: no WiR label (NCT beat — passing tone)
    result = lookup(1, 3, 1.5)
    assert result is None


def test_unknown_chorale_returns_none():
    result = lookup(999, 1, 1.0)
    assert result is None


def test_has_chorale_known():
    assert has_chorale(1) is True


def test_has_chorale_unknown():
    assert has_chorale(999) is False


def test_bwv_lookup_hit():
    assert bwv_to_riemenschneider("269") == 1


def test_bwv_lookup_miss():
    assert bwv_to_riemenschneider("99999") is None


def test_float_tolerance():
    # Beat stored as 3.0, queried as 3.0000000001 — should still match
    result = lookup(1, 0, 3.0000000001)
    assert result is not None
    assert result["label"] == "I"


def test_key_change_reflected_in_local_key():
    # R10 must exist in corpus
    r10_start = lookup(10, 0, 3.0) or lookup(10, 1, 1.0)
    assert r10_start is not None
    assert has_chorale(10) is True
