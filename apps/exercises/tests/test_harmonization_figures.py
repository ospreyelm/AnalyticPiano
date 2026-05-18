from apps.exercises.harmonization.figures import (
    expand_figure_string,
    derive_required_notes,
)


def test_blank_figure_expands_to_five_three():
    assert expand_figure_string("") == ["5", "3"]


def test_six_expands_to_six_three():
    assert expand_figure_string("6") == ["6", "3"]


def test_seven_expands_to_seven_five_three():
    assert expand_figure_string("7") == ["7", "5", "3"]


def test_arbitrary_stack_passes_through():
    assert expand_figure_string("9/7/5/3") == ["9", "7", "5", "3"]


def test_accidental_without_number_means_third():
    assert expand_figure_string("#") == ["#3", "5"]
    assert expand_figure_string("b") == ["b3", "5"]
    assert expand_figure_string("n") == ["n3", "5"]


def test_c_major_c_six_derives_e_and_a():
    result = derive_required_notes(key_name="C", bass_name="C", figure="6")
    assert result["expanded_figures"] == ["6", "3"]
    assert result["required_note_names"] == ["A", "E"]
    assert result["required_upper_pcs"] == [9, 4]
    assert result["allowed_pcs"] == [0, 9, 4]


def test_c_major_f_six_derives_d_and_a():
    result = derive_required_notes(key_name="C", bass_name="F", figure="6")
    assert result["required_note_names"] == ["D", "A"]
    assert result["required_upper_pcs"] == [2, 9]


def test_c_major_f_sharp_alters_third():
    result = derive_required_notes(key_name="C", bass_name="F", figure="#")
    assert result["expanded_figures"] == ["#3", "5"]
    assert result["required_note_names"] == ["A#", "C"]
    assert result["required_upper_pcs"] == [10, 0]


def test_c_major_b_natural_six_uses_key_default():
    result = derive_required_notes(key_name="C", bass_name="B", figure="6")
    assert result["required_note_names"] == ["G", "D"]
    assert result["required_upper_pcs"] == [7, 2]


def test_g_major_f_sharp_six_five_derives_d_c_a():
    # G major, F# bass, 6/5 expands to [6, 5, 3]
    # Diatonic above F# in G major: 6th=D, 5th=C, 3rd=A
    result = derive_required_notes(key_name="G", bass_name="F#", figure="6/5")
    assert result["expanded_figures"] == ["6", "5", "3"]
    assert result["required_note_names"] == ["D", "C", "A"]
    assert result["required_upper_pcs"] == [2, 0, 9]


def test_harmonylab_natural_major_key_id_derives_major_scale_notes():
    result = derive_required_notes(key_name="jG_", bass_name="G", figure="5/3")
    assert result["required_note_names"] == ["D", "B"]
    assert result["required_upper_pcs"] == [2, 11]
    assert result["allowed_pcs"] == [7, 2, 11]


def test_harmonylab_natural_minor_key_id_derives_minor_scale_notes():
    result = derive_required_notes(key_name="iA_", bass_name="A", figure="5/3")
    assert result["required_note_names"] == ["E", "C"]
    assert result["required_upper_pcs"] == [4, 0]
    assert result["allowed_pcs"] == [9, 4, 0]


def test_review_artifact_command_writes_html(tmp_path):
    from django.core.management import call_command

    out = tmp_path / "harmonization-review.html"
    call_command("render_harmonization_review", output=str(out))

    html = out.read_text()
    assert "Figure Parser Review" in html
    assert "C + 6" in html
    assert "F + #" in html
