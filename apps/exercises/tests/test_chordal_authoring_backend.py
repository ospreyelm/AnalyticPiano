from apps.exercises.umto import Metadata, InteractionMode


def _base_metadata_kwargs(**overrides):
    kwargs = dict(
        exercise_id="TEMP",
        source="Play view chordal exercise",
        key="C major",
        clef="keyboard",
        complexity_score=1,
        mode=InteractionMode.PLAYBACK,
        score_kind="chordal",
    )
    kwargs.update(overrides)
    return kwargs


def test_metadata_meter_optional_defaults_none():
    md = Metadata(**_base_metadata_kwargs())
    assert md.meter is None


def test_metadata_accepts_explicit_meter():
    md = Metadata(**_base_metadata_kwargs(meter="3/4"))
    assert md.meter == "3/4"


def test_metadata_barline_offsets_defaults_empty():
    md = Metadata(**_base_metadata_kwargs())
    assert md.barline_offsets == []


def test_metadata_round_trips_barline_offsets():
    md = Metadata(**_base_metadata_kwargs(meter="4/4", barline_offsets=[4.0, 8.0]))
    dumped = md.model_dump(mode="json")
    again = Metadata(**dumped)
    assert again.barline_offsets == [4.0, 8.0]


def test_voices_kind_still_requires_meter():
    import pytest
    with pytest.raises(Exception):
        Metadata(**_base_metadata_kwargs(score_kind="voices", meter=None))


def test_chordal_kind_allows_none_meter():
    md = Metadata(**_base_metadata_kwargs(score_kind="chordal", meter=None))
    assert md.meter is None


from apps.exercises.umto_factory import CHORDAL_DURATION_PALETTE, _is_palette_duration


def test_palette_contains_the_eight_authoring_values():
    assert CHORDAL_DURATION_PALETTE == {4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25}


def test_is_palette_duration_accepts_palette_values():
    for ql in [4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25]:
        assert _is_palette_duration(ql) is True


def test_is_palette_duration_rejects_off_palette():
    # 0.375 (dotted-16) and 0.125 (32nd) render but are NOT in the authoring palette
    for ql in [0.375, 0.125, 1.25, 2.5, 0.0, 3.5]:
        assert _is_palette_duration(ql) is False
