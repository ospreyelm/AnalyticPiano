from apps.exercises.harmonization.targets import build_targets_from_umto


def _event(midi, step, octave, duration=1.0, alter=0):
    return {
        "kind": "note",
        "pitch": {"step": step, "alter": alter, "octave": octave, "midi": midi},
        "duration": duration,
        "duration_type": "q",
        "dots": 0,
        "is_tied_start": False,
        "is_tied_stop": False,
        "is_target": True,
    }


def test_build_target_from_figured_bass_slice():
    umto = {
        "metadata": {
            "key": "C",
            "locked_voices": ["B"],
            "voice_count_policy": {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {
            "S": [_event(60, "C", 4)],
            "A": [_event(57, "A", 3)],
            "T": [_event(52, "E", 3)],
            "B": [_event(48, "C", 3)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "6",
                    "raw_figured_bass": "6/3",
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "local_key": "C",
                    "pop_symbol": None,
                    "functional_label": None,
                },
            }
        ],
        "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60]}],
    }

    targets = build_targets_from_umto(umto)

    assert len(targets) == 1
    assert targets[0]["bassMidi"] == 48
    assert targets[0]["bassPc"] == 0
    assert targets[0]["figures"] == ["6", "3"]
    assert targets[0]["displayFigure"] == "6"
    assert targets[0]["requiredUpperPcs"] == [9, 4]
    assert targets[0]["allowedPcs"] == [0, 9, 4]
    assert targets[0]["lockedVoices"]["B"]["midi"] == 48
    assert targets[0]["voiceCountPolicy"] == {"expected": 4, "min": 3, "max": 4}


def test_locked_soprano_is_included_when_configured():
    umto = {
        "metadata": {
            "key": "C",
            "locked_voices": ["B", "S"],
            "voice_count_policy": {"expected": 4, "min": 4, "max": 4},
        },
        "voices": {
            "S": [_event(60, "C", 4)],
            "A": [_event(57, "A", 3)],
            "T": [_event(52, "E", 3)],
            "B": [_event(48, "C", 3)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "6",
                    "raw_figured_bass": "6/3",
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "local_key": "C",
                    "pop_symbol": None,
                    "functional_label": None,
                },
            }
        ],
        "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60]}],
    }

    targets = build_targets_from_umto(umto)

    assert targets[0]["lockedVoices"]["S"]["midi"] == 60
    assert targets[0]["lockedVoices"]["S"]["pc"] == 0


def test_raw_figured_bass_used_not_abbreviated():
    # figured_bass absent — raw_figured_bass must drive derivation
    umto = {
        "metadata": {
            "key": "G",
            "locked_voices": ["B"],
            "voice_count_policy": {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {
            "S": [_event(74, "D", 5)],
            "A": [_event(69, "A", 4)],
            "T": [_event(62, "D", 4)],
            "B": [_event(55, "G", 3)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": None,
                    "raw_figured_bass": "8/5/3",
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "local_key": "G",
                    "pop_symbol": None,
                    "functional_label": None,
                },
            }
        ],
        "grading": [{"offset": 0.0, "target_midi_pitches": [55, 62, 69, 74]}],
    }

    targets = build_targets_from_umto(umto)

    assert targets[0]["figures"] == ["8", "5", "3"]
    assert targets[0]["displayFigure"] == "8/5/3"  # falls back to raw when no abbrev
    assert 7 in targets[0]["allowedPcs"]   # G
    assert 2 in targets[0]["allowedPcs"]   # D
    assert 11 in targets[0]["allowedPcs"]  # B (3rd above G in G major)


def test_multiple_slices_produce_multiple_targets():
    umto = {
        "metadata": {
            "key": "C",
            "locked_voices": ["B"],
            "voice_count_policy": {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {
            "B": [_event(48, "C", 3, duration=1.0), _event(43, "G", 2, duration=1.0)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "5/3",
                    "raw_figured_bass": "5/3",
                    "local_key": "C",
                    "roman_numeral": None, "raw_roman_numeral": None,
                    "pop_symbol": None, "functional_label": None,
                },
            },
            {
                "offset": 1.0,
                "content": {
                    "figured_bass": "7",
                    "raw_figured_bass": "7/5/3",
                    "local_key": "C",
                    "roman_numeral": None, "raw_roman_numeral": None,
                    "pop_symbol": None, "functional_label": None,
                },
            },
        ],
        "grading": [],
    }

    targets = build_targets_from_umto(umto)

    assert len(targets) == 2
    assert targets[0]["bassPc"] == 0   # C
    assert targets[1]["bassPc"] == 7   # G
    assert targets[1]["figures"] == ["7", "5", "3"]


def test_misaligned_analysis_slice_uses_local_grading_offset_for_bass_attack():
    umto = {
        "metadata": {
            "key": "G",
            "locked_voices": ["B"],
            "voice_count_policy": {"expected": None, "min": 3, "max": 4},
        },
        "voices": {
            "B": [
                _event(42, "F", 2, duration=1.0, alter=1),
                _event(43, "G", 2, duration=1.0),
            ],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "6",
                    "raw_figured_bass": "6/3",
                    "local_key": "G",
                    "roman_numeral": None, "raw_roman_numeral": None,
                    "pop_symbol": None, "functional_label": None,
                },
            },
            {
                # Imported phrase analysis can retain a later source-score offset
                # even though voices/grading have been clipped to local offsets.
                "offset": 3.0,
                "content": {
                    "figured_bass": "5/3",
                    "raw_figured_bass": "8/5/3",
                    "local_key": "G",
                    "roman_numeral": None, "raw_roman_numeral": None,
                    "pop_symbol": None, "functional_label": None,
                },
            },
        ],
        "grading": [
            {"offset": 0.0, "target_midi_pitches": [42, 57, 62]},
            {"offset": 1.0, "target_midi_pitches": [43, 62, 67, 71]},
        ],
    }

    targets = build_targets_from_umto(umto)

    assert [t["offset"] for t in targets] == [0.0, 1.0]
    assert targets[1]["bassMidi"] == 43
    assert targets[1]["displayFigure"] == "5/3"
    assert targets[1]["requiredNoteNames"] == ["G", "D", "B"]


def test_empty_analysis_returns_empty_targets():
    umto = {
        "metadata": {"key": "C", "locked_voices": ["B"],
                     "voice_count_policy": {"min": 3, "max": 4}},
        "voices": {"B": [_event(48, "C", 3)]},
        "analysis": [],
        "grading": [],
    }
    assert build_targets_from_umto(umto) == []


def test_local_key_overrides_metadata_key():
    # Bass=F in local key Bb major: 5/3 above F = C(0), A(9)
    umto = {
        "metadata": {
            "key": "C",  # global key differs from local
            "locked_voices": ["B"],
            "voice_count_policy": {"min": 3, "max": 4},
        },
        "voices": {
            "B": [_event(41, "F", 2)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "5/3",
                    "raw_figured_bass": "5/3",
                    "local_key": "Bb",
                    "roman_numeral": None, "raw_roman_numeral": None,
                    "pop_symbol": None, "functional_label": None,
                },
            }
        ],
        "grading": [],
    }

    targets = build_targets_from_umto(umto)

    assert targets[0]["source"]["key"] == "Bb"
    # 5th above F in Bb major = C (pc 0), 3rd = A (pc 9)
    assert 0 in targets[0]["allowedPcs"]
    assert 9 in targets[0]["allowedPcs"]


# --- Chordal UMTO tests ---

def _chordal_umto(chords, analysis, *, key="C", locked_voices=None, voice_count_policy=None):
    """Helper: build a minimal chordal UMTO dict for testing."""
    return {
        "metadata": {
            "key": key,
            "score_kind": "chordal",
            "locked_voices": locked_voices or ["B"],
            "voice_count_policy": voice_count_policy or {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {"S": [], "A": [], "T": [], "B": []},
        "chords": chords,
        "analysis": analysis,
        "grading": [],
    }


def _analysis_slice(offset, *, local_key="C", figured_bass="5/3", raw_figured_bass="5/3"):
    return {
        "offset": offset,
        "content": {
            "figured_bass": figured_bass,
            "raw_figured_bass": raw_figured_bass,
            "local_key": local_key,
            "roman_numeral": None,
            "raw_roman_numeral": None,
            "pop_symbol": None,
            "functional_label": None,
        },
    }


def test_chordal_umto_produces_targets_from_chords():
    # C major triad in root position: C3=48 is bass, E3=52 and G3=55 are upper
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": [], "spelling": ["C", "E", "G"]}],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    t = targets[0]
    assert t["bassMidi"] == 48
    assert t["bassPc"] == 0
    assert t["bassSpelling"] == "C"
    assert t["lockedVoices"]["B"]["midi"] == 48
    assert t["lockedVoices"]["B"]["pc"] == 0
    assert 7 in t["allowedPcs"]   # G
    assert 4 in t["allowedPcs"]   # E
    assert t["voiceCountPolicy"] == {"expected": 4, "min": 3, "max": 4}


def test_chordal_umto_bass_is_lowest_midi():
    # visible=[52,43,55], bass is 43 (G2) at index 1, spelling[1]="G"
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [52, 43, 55], "hidden": [], "spelling": ["E", "G", "G"]}],
        analysis=[_analysis_slice(0.0, local_key="G", figured_bass="6/3", raw_figured_bass="6/3")],
        key="G",
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["bassMidi"] == 43
    assert targets[0]["bassPc"] == 7
    assert targets[0]["bassSpelling"] == "G"


def test_chordal_umto_spelling_fallback_when_none():
    # No spelling provided — fall back to chromatic MIDI name
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": []}],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["bassSpelling"] == "C"   # MIDI 48 % 12 = 0 → "C"


def test_chordal_umto_skips_chord_with_no_matching_analysis():
    # Two chords, only one has a matching analysis slice
    umto = _chordal_umto(
        chords=[
            {"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": [], "spelling": ["C", "E", "G"]},
            {"offset": 1.0, "duration": 1.0, "visible": [43, 47, 50], "hidden": [], "spelling": ["G", "B", "D"]},
        ],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["offset"] == 0.0


def test_chordal_umto_skips_empty_chord():
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [], "hidden": []}],
        analysis=[_analysis_slice(0.0)],
    )
    targets = build_targets_from_umto(umto)
    assert targets == []


def test_chordal_umto_single_note_chord_bass_only():
    # Only 1 visible note = bass only
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [48], "hidden": [], "spelling": ["C"]}],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["bassMidi"] == 48
    assert targets[0]["lockedVoices"]["B"]["midi"] == 48


def test_chordal_umto_multiple_chords_produce_multiple_targets():
    umto = _chordal_umto(
        chords=[
            {"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": [], "spelling": ["C", "E", "G"]},
            {"offset": 1.0, "duration": 1.0, "visible": [43, 47, 50], "hidden": [], "spelling": ["G", "B", "D"]},
        ],
        analysis=[
            _analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3"),
            _analysis_slice(1.0, local_key="G", figured_bass="5/3", raw_figured_bass="5/3"),
        ],
        key="C",
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 2
    assert targets[0]["bassMidi"] == 48
    assert targets[1]["bassMidi"] == 43


