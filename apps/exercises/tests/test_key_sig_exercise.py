import pytest
from apps.exercises.key_signature_problems import (
    KEY_TABLE,
    build_key_sig_problem_set,
    LEVEL_ACCIDENTAL_LIMIT,
)

def test_key_table_has_15_keys():
    assert len(KEY_TABLE) == 15

def test_key_table_c_major():
    c = next(k for k in KEY_TABLE if k["key_id"] == "jC_")
    assert c["accidentals"] == 0
    assert c["display_name"] == "C major"
    assert "C" in c["accepted_answers"]

def test_key_table_f_sharp_major():
    fs = next(k for k in KEY_TABLE if k["key_id"] == "jF#")
    assert fs["accidentals"] == 6
    assert "F#" in fs["accepted_answers"]

def test_level_limits():
    assert LEVEL_ACCIDENTAL_LIMIT == {1: 3, 2: 5, 3: 7}

def test_build_problem_set_level1():
    problems = build_key_sig_problem_set(level=1)
    assert all(p["accidentals"] <= 3 for p in problems)
    assert len(problems) == 7  # C, G, D, A, F, Bb, Eb

def test_build_problem_set_level3():
    problems = build_key_sig_problem_set(level=3)
    assert len(problems) == 15

def test_problem_structure():
    problems = build_key_sig_problem_set(level=1)
    p = problems[0]
    assert "prompt" in p
    assert p["prompt"]["kind"] == "key_signature"
    assert "sharps" in p["prompt"] or "flats" in p["prompt"]
    assert "answer" in p
    assert "accepted_answers" in p
    assert "choices" in p
    assert len(p["choices"]) == 4
