import pytest
pytest.importorskip("music21")
from apps.exercises.compendium_source import load_cadence_examples
from apps.exercises.compendium_prep import prepare_compendium_exercise


def _ex(eid):
    return next(e for e in load_cadence_examples() if e["id"] == eid)


def test_prep_6_5_bins_unit_14_with_template_rns():
    out = prepare_compendium_exercise(_ex("m111-112"), "D")  # 6/5 major -> D major
    assert out is not None
    assert out["unit"] == 14
    assert out["umto_kwargs"]["key"] == "jD_"
    assert out["umto_kwargs"]["source"] == "Compound Cadences with 6/5 in Four Voices in D major"
    rns = [a["content"]["roman_numeral"] for a in out["umto_kwargs"]["analysis_overrides"]]
    assert rns == ["I", "I6", "ii65", "V", "I"]
    assert all(a["is_target"] for a in out["umto_kwargs"]["analysis_overrides"])
    assert len(out["description"]) <= 60
    assert out["score_data"]["measures"]  # non-empty CIR


def test_prep_6_4_bins_unit_12_cad64():
    out = prepare_compendium_exercise(_ex("m123-124"), "C")  # 6/4 major
    assert out["unit"] == 12
    rns = [a["content"]["roman_numeral"] for a in out["umto_kwargs"]["analysis_overrides"]]
    assert rns == ["I", "I6", "Cad64", "V", "I"]


def test_prep_simple_three_voice_unit_9():
    out = prepare_compendium_exercise(_ex("m025-026"), "G")  # simple 3v major -> G
    assert out["unit"] == 9
    assert out["umto_kwargs"]["key"] == "jG_"
