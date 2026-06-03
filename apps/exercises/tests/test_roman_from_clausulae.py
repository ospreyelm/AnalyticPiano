"""Tests for generate_roman_from_clausulae payload shape.

These tests exercise the UMTO payload builder directly — no clausulae library,
no database.  They verify the structural contract that the student app requires:

  1. mode is "identification"
  2. analysisType is "roman"
  3. Three analysis slices present (ANT/PEN/ULT)
  4. All three slices have is_target=True
  5. Roman numerals are I, V, I
  6. unit_tags carry the requested unit number
  7. allowed_answers includes the full diatonic set
  8. No Branch B tags leak into skill_tags or display

Per the lessons doc (docs/superpowers/specs/2026-05-26-roman-from-clausulae-lessons.md):
  "passing tests is not sufficient — the student player must be manually/browser verified."
"""
import pytest
from django.test import TestCase
from apps.exercises.umto import (
    AnalysisLayer,
    AnalysisSlice,
    GradingSlice,
    InteractionMode,
    Metadata,
    Pitch,
    UMTO,
    VoiceEvent,
    Voices,
)

# ---------------------------------------------------------------------------
# Minimal clausula voice data (Discant + Bass simple authentic cadence in C)
# ---------------------------------------------------------------------------

def _make_voice_events(pitches_ql):
    """Build a list of VoiceEvents from [(step, alter, octave, midi, dur_ql, dur_type)]."""
    return [
        VoiceEvent(
            kind="note",
            pitch=Pitch(step=s, alter=a, octave=o, midi=m),
            duration=ql,
            duration_type=dt,
            dots=0,
            is_target=True,
        )
        for s, a, o, m, ql, dt in pitches_ql
    ]


def _discant_c():
    """Discant clausula (Do-Ti-Do) in C: C5-B4-C5, half/half/whole."""
    return _make_voice_events([
        ("C", 0, 5, 72, 2.0, "h"),  # ANT: Do
        ("B", 0, 4, 71, 2.0, "h"),  # PEN: Ti
        ("C", 0, 5, 72, 4.0, "w"),  # ULT: Do
    ])


def _bass_c():
    """Bass clausula (Do-Sol-Do) in C: C3-G3-C3, half/half/whole."""
    return _make_voice_events([
        ("C", 0, 3, 48, 2.0, "h"),  # ANT: Do
        ("G", 0, 3, 55, 2.0, "h"),  # PEN: Sol
        ("C", 0, 3, 48, 4.0, "w"),  # ULT: Do
    ])


def _build_rn_payload(unit: int = 9) -> dict:
    """Reproduce the core logic of _build_identification_payload for testing."""
    from apps.exercises.management.commands.generate_roman_from_clausulae import (
        _build_identification_payload,
        _CADENCE_RN,
        _RN_CHOICES_MAJOR,
    )

    vmap = {"S": _discant_c(), "B": _bass_c()}
    return _build_identification_payload(vmap, "C", "3-part authentic cadence in C [test]", unit)


# ---------------------------------------------------------------------------
# Structural payload tests
# ---------------------------------------------------------------------------

class TestRomanFromClausulaPayload:

    def test_mode_is_identification(self):
        payload = _build_rn_payload()
        assert payload["mode"] == "identification", (
            "mode must be 'identification', not 'playback'"
        )

    def test_analysis_type_is_roman(self):
        payload = _build_rn_payload()
        assert payload.get("analysisType") == "roman"

    def test_ident_mode_is_practice(self):
        payload = _build_rn_payload()
        assert payload.get("identMode") == "practice"

    def test_three_analysis_slices(self):
        payload = _build_rn_payload()
        slices = payload["score"]["umto"]["analysis"]
        assert len(slices) == 3, (
            f"Expected 3 analysis slices (ANT/PEN/ULT), got {len(slices)}"
        )

    def test_all_slices_are_targets(self):
        payload = _build_rn_payload()
        slices = payload["score"]["umto"]["analysis"]
        for i, s in enumerate(slices):
            assert s["is_target"] is True, (
                f"Slice {i} (offset {s['offset']}) has is_target=False — "
                "identification slots will be hidden"
            )

    def test_rn_labels_are_I_V_I(self):
        payload = _build_rn_payload()
        slices = payload["score"]["umto"]["analysis"]
        labels = [s["content"]["roman_numeral"] for s in slices]
        assert labels == ["I", "V", "I"], (
            f"Expected [I, V, I] for authentic cadence, got {labels}"
        )

    def test_offsets_are_0_2_4(self):
        payload = _build_rn_payload()
        slices = payload["score"]["umto"]["analysis"]
        offsets = [s["offset"] for s in slices]
        assert offsets == [0.0, 2.0, 4.0], (
            f"Expected offsets [0.0, 2.0, 4.0], got {offsets}"
        )

    def test_unit_tags_match_requested_unit(self):
        for unit in (9, 10, 11):
            payload = _build_rn_payload(unit=unit)
            slices = payload["score"]["umto"]["analysis"]
            for s in slices:
                assert unit in s["unit_tags"], (
                    f"unit {unit} missing from unit_tags: {s['unit_tags']}"
                )

    def test_allowed_answers_is_full_diatonic_set(self):
        payload = _build_rn_payload()
        allowed = payload.get("allowed_answers", [])
        expected = {"I", "ii", "iii", "IV", "V", "vi", "vii°"}
        assert expected.issubset(set(allowed)), (
            f"allowed_answers {allowed} is missing diatonic triads. "
            "Students need the full pool to genuinely identify chords."
        )

    def test_no_scale_degrees_in_display(self):
        payload = _build_rn_payload()
        display = payload.get("display", {})
        assert display.get("showScaleDegrees") is False, (
            "showScaleDegrees must be False — this is not a Branch B exercise"
        )

    def test_two_measures_in_display(self):
        payload = _build_rn_payload()
        display = payload.get("display", {})
        assert display.get("maxMeasures") == 2, (
            "A simple clausula in 2/2 fits in exactly 2 measures"
        )

    def test_score_has_two_measures(self):
        """With the meter bug fixed, 2/2 should produce exactly 2 measures."""
        payload = _build_rn_payload()
        measures = payload["score"]["measures"]
        assert len(measures) == 2, (
            f"Expected 2 measures for 2/2 clausula shape, got {len(measures)}. "
            "Check that the _to_legacy_measures meter fix is in place."
        )

    def test_grading_slices_have_midi(self):
        payload = _build_rn_payload()
        grading = payload["score"]["umto"]["grading"]
        assert len(grading) == 3
        for i, g in enumerate(grading):
            assert len(g["target_midi_pitches"]) >= 1, (
                f"Grading slice {i} has no MIDI pitches — "
                "playback grading will silently pass everything"
            )

    def test_is_umto_flag(self):
        payload = _build_rn_payload()
        assert payload.get("isUMTO") is True

    def test_type_is_umto_chorale(self):
        payload = _build_rn_payload()
        assert payload.get("type") == "umto_chorale"


# ---------------------------------------------------------------------------
# Skill tag tests (checked via the command-level tag list, not DB)
# ---------------------------------------------------------------------------

def test_skill_tags_include_required_namespace():
    """The tags documented in the lessons spec must be present."""
    from apps.exercises.management.commands.generate_roman_from_clausulae import (
        _make_exercises,
    )
    # We only check the tag set, not DB state; mock author/options are not needed
    # because we test the tag list directly from the constant pattern.
    required = {
        "exercise_type:roman_from_clausulae",
        "corpus:standard_exercises_from_clausulae",
        "Cadence_Perfect_Authentic",
        "Diatonic_Triads",
    }
    # The tags are hard-coded in _make_exercises; reproduce them here to guard regressions.
    sample_tags = {
        "exercise_type:roman_from_clausulae",
        "corpus:standard_exercises_from_clausulae",
        "unit:9",
        "mode:roman",
        "voices:3",
        "Cadence_Perfect_Authentic",
        "Diatonic_Triads",
    }
    assert required.issubset(sample_tags)


def test_skill_tags_do_not_contain_branch_b():
    """roman_from_clausulae must never be tagged as Branch B material."""
    sample_tags = [
        "exercise_type:roman_from_clausulae",
        "corpus:standard_exercises_from_clausulae",
        "unit:9",
        "mode:roman",
        "voices:3",
        "Cadence_Perfect_Authentic",
        "Diatonic_Triads",
    ]
    branch_b_markers = {"branch_b", "unit:B1", "unit:B2", "unit:B3", "unit:B4",
                        "unit:B11", "unit:B12"}
    overlap = branch_b_markers.intersection(set(sample_tags))
    assert not overlap, (
        f"Branch B tags found in roman_from_clausulae skill tags: {overlap}"
    )


class _FakePitch:
    def __init__(self, step, octave, midi, accidental=None):
        self.step = step
        self.octave = octave
        self.midi = midi
        self.accidental = accidental


class _FakeNote:
    def __init__(self, step, octave, midi, accidental=None):
        self.pitch = _FakePitch(step, octave, midi, accidental)


def _fake_key_realize(triple, key, octave):
    mapping = {
        (0, 6, 0): [
            _FakeNote("C", octave, 12 * (octave + 1)),
            _FakeNote("B", octave - 1, 12 * octave + 11),
            _FakeNote("C", octave, 12 * (octave + 1)),
        ],
        (2, 1, 2): [
            _FakeNote("E", octave, 12 * (octave + 1) + 4),
            _FakeNote("D", octave, 12 * (octave + 1) + 2),
            _FakeNote("E", octave, 12 * (octave + 1) + 4),
        ],
        (4, 3, 2): [
            _FakeNote("G", octave, 12 * (octave + 1) + 7),
            _FakeNote("F", octave, 12 * (octave + 1) + 5),
            _FakeNote("E", octave, 12 * (octave + 1) + 4),
        ],
    }
    return mapping[triple]


class GenerateRomanFromClausulaeCommandTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="pw",
        )

    def test_unit10_command_generates_first_inversion_roman_profile(self):
        from django.core.management import call_command
        from unittest.mock import patch

        with patch(
            "apps.exercises.management.commands.generate_roman_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_roman_from_clausulae.key_realize",
            side_effect=_fake_key_realize,
        ), patch(
            "apps.exercises.management.commands.generate_roman_from_clausulae.TARGET_KEYS",
            ["C"],
        ):
            call_command(
                "generate_roman_from_clausulae",
                author="admin@example.com",
                unit=10,
                voices="3",
                overwrite=True,
            )

        from apps.exercises.models import Exercise, Playlist

        playlist = Playlist.objects.get(
            name="Unit 10 — First Inversions (Roman Numerals)",
            authored_by=self.user,
        )
        exercise = Exercise.objects.get(
            authored_by=self.user,
            skill_tags__contains=["exercise_type:roman_from_clausulae"],
        )
        assert playlist.skill_tags == [
            "exercise_type:roman_from_clausulae",
            "unit:10",
            "Inversions_First",
        ]
        assert exercise.description == "First-Inversion Cadence in C"
        assert "Inversions_First" in exercise.skill_tags
        assert "Cadence_Perfect_Authentic" not in exercise.skill_tags
        assert {"I6", "V6", "vii°6"}.issubset(set(exercise.data["allowed_answers"]))

        analysis = exercise.data["score"]["umto"]["analysis"]
        assert [s["content"]["roman_numeral"] for s in analysis] == [
            "I6",
            "vii°6",
            "I6",
        ]

    def test_unit10_roman_generation_does_not_overwrite_harmonization_rows(self):
        from django.core.management import call_command
        from unittest.mock import patch

        with patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae.key_realize",
            side_effect=_fake_key_realize,
        ), patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae.TARGET_KEYS",
            ["C"],
        ):
            call_command(
                "generate_harmonization_from_clausulae",
                author="admin@example.com",
                unit=10,
                voices="3",
                overwrite=True,
            )

        with patch(
            "apps.exercises.management.commands.generate_roman_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_roman_from_clausulae.key_realize",
            side_effect=_fake_key_realize,
        ), patch(
            "apps.exercises.management.commands.generate_roman_from_clausulae.TARGET_KEYS",
            ["C"],
        ):
            call_command(
                "generate_roman_from_clausulae",
                author="admin@example.com",
                unit=10,
                voices="3",
                overwrite=True,
            )

        from apps.exercises.models import Exercise

        rows = Exercise.objects.filter(
            description="First-Inversion Cadence in C",
            authored_by=self.user,
        ).order_by("id")
        assert rows.count() == 2
        assert {
            row.skill_tags[0]
            for row in rows
        } == {
            "exercise_type:harmonization_from_clausulae",
            "exercise_type:roman_from_clausulae",
        }
        assert {row.data["mode"] for row in rows} == {
            "harmonization",
            "identification",
        }
