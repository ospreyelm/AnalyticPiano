from apps.exercises.chordal_spelling import spelling_str_to_cir_pitch


def test_sharp_with_octave():
    assert spelling_str_to_cir_pitch("C#4") == {"step": "C", "alter": 1, "octave": 4}


def test_flat():
    assert spelling_str_to_cir_pitch("Eb4") == {"step": "E", "alter": -1, "octave": 4}


def test_cb_keeps_letter():
    assert spelling_str_to_cir_pitch("Cb5") == {"step": "C", "alter": -1, "octave": 5}


def test_double_sharp():
    assert spelling_str_to_cir_pitch("F##3") == {"step": "F", "alter": 2, "octave": 3}


def test_double_flat():
    assert spelling_str_to_cir_pitch("Bbb3") == {"step": "B", "alter": -2, "octave": 3}


def test_negative_octave():
    assert spelling_str_to_cir_pitch("C0") == {"step": "C", "alter": 0, "octave": 0}


def test_invalid_returns_none():
    assert spelling_str_to_cir_pitch("nonsense") is None


def test_empty_returns_none():
    assert spelling_str_to_cir_pitch("") is None
