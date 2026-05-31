import pytest
pytest.importorskip("music21")
from music21 import key, roman
from apps.exercises.compendium_source import (
    INDEX_PATH, load_cadence_examples, score_from_example, transpose_score, nearest_interval,
)


def _example(eid):
    return next(e for e in load_cadence_examples() if e["id"] == eid)


def test_only_templated_pagetypes_loaded():
    exs = load_cadence_examples()
    pts = {e["page_title"] for e in exs}
    assert "Compound Cadences with 6/5 in Four Voices" in pts
    assert "Simple Cadences in Two Voices" not in pts   # not templated
    assert "Cudworth Cadence" not in pts
    assert all("notes" in e and e.get("mode") in ("major", "minor") for e in exs)


def test_default_index_path_is_repo_local():
    assert "clausulae-project" not in INDEX_PATH
    assert INDEX_PATH.endswith("apps/exercises/data/galant_compendium_cadences.json")


def test_score_build_and_trim_gives_correct_rns():
    e = _example("m111-112")  # Compound 6/5, C major
    sc = score_from_example(e)
    k = key.Key(e["key"], e["mode"])
    figs = [roman.romanNumeralFromChord(c, k).figure for c in sc.chordify().recurse().getElementsByClass("Chord")]
    # trimmed build must recover the inversion (I6) and the ii6/5
    assert "I6" in figs and "ii65" in figs


def test_nearest_interval_centers_near_c():
    # C->D up M2 (+2), C->Bb down M2 (-2), C->G down P4 (-5) preferred over +7
    assert nearest_interval("C", "D").semitones == 2
    assert nearest_interval("C", "Bb").semitones == -2
    assert nearest_interval("C", "G").semitones == -5


def test_transpose_shifts_pitches():
    e = _example("m111-112")
    sc = score_from_example(e)
    up = transpose_score(sc, nearest_interval("C", "D"))
    # transposing C major example up a major 2nd -> D; lowest note rises by 2 semitones
    lo_before = min(n.pitch.midi for n in sc.recurse().notes)
    lo_after = min(n.pitch.midi for n in up.recurse().notes)
    assert lo_after - lo_before == 2
