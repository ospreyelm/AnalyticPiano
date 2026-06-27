from apps.exercises.harmonization import figure_realization as fr


def test_normalize_strips_octave_and_records_altered():
    # 8 dropped (octave doubles bass); accidental on 5 recorded as altered.
    assert fr.normalize("8/5/3") == ("5/3", frozenset())
    assert fr.normalize("7/5°/3") == ("7/5/3", frozenset({5}))
    assert fr.normalize("#6/3") == ("6/3", frozenset({6}))


def test_normalize_reduced_voicings_map_to_prototype():
    assert fr.normalize("7/3")[0] == "7/5/3"   # 3-voice realization of root 7th
    assert fr.normalize("8/3")[0] == "5/3"     # 3-voice 5/3 (octave + 3rd)


def test_normalize_alias_and_unknown():
    assert fr.normalize("9/6/4")[0] == "6/4/2"          # explicit alias
    assert fr.normalize("7/6/5")[0] is None             # rare tail → fail-safe


def test_required_numbers_fifth_omittable_in_root_triad():
    # 5/3 over min=3..max=4: only the 3rd is required.
    assert fr.required_numbers("5/3", {"min": 3, "max": 4},
                               present={5, 3}, altered=frozenset()) == {3}


def test_required_numbers_first_inversion_keeps_both_until_two_voices():
    assert fr.required_numbers("6/3", {"min": 3, "max": 4},
                               present={6, 3}, altered=frozenset()) == {6, 3}


def test_required_numbers_dominant_ninth_drops_fifth_and_third():
    assert fr.required_numbers("9/7/5/3", {"min": 3, "max": 4},
                               present={9, 7, 5, 3}, altered=frozenset()) == {9, 7}


def test_required_numbers_altered_tone_forced():
    # 5/3 with a diminished 5th: the altered 5 is required even though plain 5 is not.
    assert fr.required_numbers("5/3", {"min": 3, "max": 4},
                               present={5, 3}, altered=frozenset({5})) == {3, 5}


def test_required_numbers_four_voice_only_chord_all_required():
    assert fr.required_numbers("7/5/2", {"min": 3, "max": 4},
                               present={7, 5, 2}, altered=frozenset()) == {7, 5, 2}


def test_required_numbers_min4_keeps_fifth():
    # With min=max=4, the 5/3 fifth stays required (4-voice full set).
    assert fr.required_numbers("5/3", {"min": 4, "max": 4},
                               present={5, 3}, altered=frozenset()) == {5, 3}


def test_table_invariant_two_or_nine_excludes_eight():
    # The module asserts this at import; re-check explicitly.
    for key, by_voice in fr.TABLE.items():
        nums = {int(n) for alts in by_voice.values() for alt in alts for n in alt}
        if 2 in nums or 9 in nums:
            assert 8 not in nums, f"{key} violates 2|9 -> no 8"


# ---------------------------------------------------------------------------
# Integration tests: derive_required_notes wired to figure_realization table
# ---------------------------------------------------------------------------

from apps.exercises.harmonization.figures import derive_required_notes


def test_derive_5_3_omits_fifth_from_required():
    d = derive_required_notes(key_name="C", bass_name="C3", figure="5/3",
                              voice_count_policy={"min": 3, "max": 4})
    # 3rd (E, pc4) required; 5th (G, pc7) allowed but not required.
    assert d["required_upper_pcs"] == [4]
    assert d["required_note_names"] == ["E"]
    assert d["allowed_pcs"] == [0, 7, 4]  # bass + all named tones, unchanged


def test_derive_6_3_keeps_both_required():
    d = derive_required_notes(key_name="C", bass_name="E3", figure="6/3",
                              voice_count_policy={"min": 3, "max": 4})
    assert set(d["required_upper_pcs"]) == {0, 7}  # C (6th) + G (3rd)


def test_derive_min4_keeps_fifth_required():
    d = derive_required_notes(key_name="C", bass_name="C3", figure="5/3",
                              voice_count_policy={"min": 4, "max": 4})
    assert set(d["required_upper_pcs"]) == {4, 7}  # E and G both required


def test_derive_unknown_figure_failsafe_all_required():
    d = derive_required_notes(key_name="C", bass_name="C3", figure="7/6/5",
                              voice_count_policy={"min": 3, "max": 4})
    # rare-tail fail-safe: every named upper tone required (legacy behavior).
    assert set(d["required_upper_pcs"]) == set(d["allowed_pcs"]) - {0}


def test_derive_default_policy_is_3_4():
    d = derive_required_notes(key_name="C", bass_name="C3", figure="5/3")
    assert d["required_upper_pcs"] == [4]
