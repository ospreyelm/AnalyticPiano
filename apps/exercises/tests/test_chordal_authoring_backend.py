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


from apps.exercises.umto_factory import validate_chordal_rhythm
from apps.exercises.models import NonUMTOExerciseError


def _ch(offset, duration, visible=(60,)):
    return {"offset": offset, "duration": duration, "visible": list(visible)}


def test_free_mode_skips_rhythm_validation_but_checks_palette():
    chords = [_ch(0.0, 1.0), _ch(1.0, 0.75), _ch(1.75, 0.25)]
    validate_chordal_rhythm(chords, meter=None, barline_offsets=[])  # no raise


def test_free_mode_rejects_off_palette_duration():
    chords = [_ch(0.0, 1.25)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "palette" in str(exc).lower()


def test_metered_exact_tiling_passes():
    chords = [_ch(float(i), 1.0) for i in range(8)]
    validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[4.0])  # no raise


def test_metered_short_bar_blocks():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0), _ch(2.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "bar" in str(exc).lower()


def test_metered_overfull_bar_blocks():
    chords = [_ch(0.0, 2.0), _ch(2.0, 2.0), _ch(4.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass


def test_metered_barline_not_on_onset_blocks():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0), _ch(2.0, 1.0), _ch(3.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[2.5])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "onset" in str(exc).lower()


def test_metered_gap_blocks():
    chords = [_ch(0.0, 1.0), _ch(2.0, 1.0), _ch(3.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass


def test_free_mode_still_rejects_barline_not_on_onset():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[0.5])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "onset" in str(exc).lower()


def test_free_mode_still_rejects_overlap():
    chords = [_ch(0.0, 4.0), _ch(1.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "overlap" in str(exc).lower()


from apps.exercises.umto_factory import _chordal_to_measures


def test_measures_split_at_explicit_barlines():
    chords = [_ch(float(i), 1.0) for i in range(6)]
    measures = _chordal_to_measures(chords, meter="2/4", barline_offsets=[2.0, 4.0])
    assert len(measures) == 3
    for m in measures:
        assert len(m["staves"]["treble"]["voices"][0]["items"]) == 2


def test_free_mode_single_measure_when_no_barlines():
    chords = [_ch(0.0, 1.0), _ch(1.0, 0.5), _ch(1.5, 0.5)]
    measures = _chordal_to_measures(chords, meter=None, barline_offsets=[])
    assert len(measures) == 1
    assert len(measures[0]["staves"]["treble"]["voices"][0]["items"]) == 3


def test_barline_at_zero_rejected_free_mode():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[0.0])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass


def test_barline_at_stream_end_rejected():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[2.0])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass


def test_duplicate_barline_rejected():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0), _ch(2.0, 1.0), _ch(3.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[1.0, 1.0])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass
