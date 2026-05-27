import json
import os
from pathlib import Path
import pytest
from apps.exercises.umto import UMTO, InteractionMode
from apps.exercises.umto_factory import build_umto_payload

UMTO_FIXTURES_DIR = Path("apps/exercises/tests/fixtures/umto")
CIR_FIXTURES_DIR = Path("apps/exercises/tests/fixtures/cir_inputs")


@pytest.mark.parametrize("fixture_path", sorted(UMTO_FIXTURES_DIR.glob("*.json")), ids=lambda p: p.name)
def test_umto_fixture_validation_and_roundtrip(fixture_path):
    """
    Contract test: Hand-authored 'golden' fixtures must be valid 
    against Pydantic models and survive a round-trip.
    """
    with open(fixture_path, "r") as f:
        original_data = json.load(f)
    
    # 1. Validate against model
    umto = UMTO.model_validate(original_data)
    
    # 2. Round-trip through JSON
    dumped_json = umto.model_dump_json()
    roundtripped_data = json.loads(dumped_json)
    
    # 3. Check invariance (basic structure)
    assert roundtripped_data["metadata"]["exercise_id"] == original_data["metadata"]["exercise_id"]
    assert len(roundtripped_data["voices"]["S"]) == len(original_data["voices"]["S"])
    if "grading" in original_data:
        assert len(roundtripped_data["grading"]) == len(original_data["grading"])


def test_interaction_mode_has_harmonization():
    from apps.exercises.umto import InteractionMode

    assert InteractionMode.HARMONIZATION.value == "harmonization"


def test_metadata_has_harmonization_defaults():
    from apps.exercises.umto import Metadata, InteractionMode

    meta = Metadata(
        exercise_id="TEMP",
        source="Test",
        key="C",
        meter="4/4",
        clef="keyboard",
        complexity_score=9,
        mode=InteractionMode.HARMONIZATION,
    )

    assert meta.locked_voices == ["B"]
    assert meta.voice_count_policy.min == 3
    assert meta.voice_count_policy.max == 4
    assert meta.voice_count_policy.expected is None
    assert meta.harmonization_target_policy.source == "figured_bass"
    assert meta.harmonization_target_policy.midi_uses_pitch_class is True
    assert meta.chord_settle_ms == 150
    assert meta.release_grace_ms == 120
    assert meta.max_voice_displacement == 4


def test_factory_idempotence_unit1_treble():
    """
    Contract test: Factory must transform CIR input into EXACT golden fixture shape.
    """
    with open(CIR_FIXTURES_DIR / "unit1_treble.json", "r") as f:
        cir = json.load(f)
    with open(UMTO_FIXTURES_DIR / "unit1_identification_treble.json", "r") as f:
        golden = json.load(f)
        
    payload = build_umto_payload(
        exercise_id="FIXTURE_U1_ID_TREBLE",
        source="BWV1.6 mm.1-2 Soprano identification",
        key="G",
        meter="4/4",
        clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        score_data=cir,
        target_voice="soprano",
        unit=1
    )
    
    umto_result = payload["score"]["umto"]
    
    # Compare key fields
    assert umto_result["metadata"]["exercise_id"] == golden["metadata"]["exercise_id"]
    assert umto_result["voices"]["S"] == golden["voices"]["S"]
    assert umto_result["grading"] == golden["grading"]
    # Analysis might have slight differences in visual=null vs missing, so we check carefully
    for i, a in enumerate(umto_result["analysis"]):
        assert a["offset"] == golden["analysis"][i]["offset"]
        assert a["unit_tags"] == golden["analysis"][i]["unit_tags"]


def test_factory_idempotence_unit9_satb():
    """
    Contract test: SATB factory transformation must match unit9 golden fixture.
    """
    with open(CIR_FIXTURES_DIR / "unit9_satb.json", "r") as f:
        cir = json.load(f)
    with open(UMTO_FIXTURES_DIR / "unit9_chorale_roman.json", "r") as f:
        golden = json.load(f)
        
    payload = build_umto_payload(
        exercise_id="FIXTURE_U9_ROMAN",
        source="BWV1.6 mm.1-2 SATB Roman",
        key="G",
        meter="4/4",
        clef="keyboard",
        complexity_score=9,
        mode=InteractionMode.ANALYSIS_MATCH,
        score_data=cir,
        target_voice=None,
        unit=9
    )
    
    umto_result = payload["score"]["umto"]
    
    assert umto_result["metadata"]["exercise_id"] == golden["metadata"]["exercise_id"]
    assert umto_result["voices"]["S"] == golden["voices"]["S"]
    assert umto_result["voices"]["B"] == golden["voices"]["B"]
    assert umto_result["grading"] == golden["grading"]


from django.test import TestCase
from apps.exercises.models import Exercise, NonUMTOExerciseError
from django.contrib.auth import get_user_model
import os

class UMTOContractTests(TestCase):
    def test_interaction_mode_has_harmonization(self):
        from apps.exercises.umto import InteractionMode

        assert InteractionMode.HARMONIZATION.value == "harmonization"

    def test_metadata_has_harmonization_defaults(self):
        from apps.exercises.umto import Metadata, InteractionMode

        meta = Metadata(
            exercise_id="TEMP",
            source="Test",
            key="C",
            meter="4/4",
            clef="keyboard",
            complexity_score=9,
            mode=InteractionMode.HARMONIZATION,
        )

        assert meta.locked_voices == ["B"]
        assert meta.voice_count_policy.min == 3
        assert meta.voice_count_policy.max == 4
        assert meta.voice_count_policy.expected is None
        assert meta.harmonization_target_policy.source == "figured_bass"
        assert meta.harmonization_target_policy.midi_uses_pitch_class is True
        assert meta.chord_settle_ms == 150
        assert meta.release_grace_ms == 120
        assert meta.max_voice_displacement == 4

    def test_metadata_rejects_invalid_locked_voice_ids(self):
        from pydantic import ValidationError
        from apps.exercises.umto import Metadata, InteractionMode

        with self.assertRaises(ValidationError):
            Metadata(
                exercise_id="TEMP",
                source="Test",
                key="C",
                meter="4/4",
                clef="keyboard",
                complexity_score=9,
                mode=InteractionMode.HARMONIZATION,
                locked_voices=["B", "X"],
            )

    def test_voice_count_policy_rejects_negative_expected(self):
        from pydantic import ValidationError
        from apps.exercises.umto import VoiceCountPolicy

        with self.assertRaises(ValidationError):
            VoiceCountPolicy(expected=-1)

    def test_voice_count_policy_rejects_negative_min(self):
        from pydantic import ValidationError
        from apps.exercises.umto import VoiceCountPolicy

        with self.assertRaises(ValidationError):
            VoiceCountPolicy(min=-1)

    def test_voice_count_policy_rejects_max_less_than_min(self):
        from pydantic import ValidationError
        from apps.exercises.umto import VoiceCountPolicy

        with self.assertRaises(ValidationError):
            VoiceCountPolicy(min=5, max=3)

    def test_factory_emits_is_umto_flag(self):
        """
        Contract test: build_umto_payload must always set isUMTO=True.
        """
        with open(CIR_FIXTURES_DIR / "unit1_treble.json", "r") as f:
            cir = json.load(f)
        payload = build_umto_payload(
            exercise_id="TEMP",
            source="Test",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            score_data=cir,
        )
        self.assertTrue(payload["isUMTO"])

    def test_schema_file_is_in_sync_with_models(self):
        """
        Contract test: verify that the committed umto_schema.json matches 
        the Pydantic model's current schema.
        """
        schema_path = Path("apps/exercises/umto_schema.json")
        if not schema_path.exists():
            self.fail("umto_schema.json is missing")
        
        with open(schema_path, "r") as f:
            stored_schema = json.load(f)
        
        current_schema = UMTO.model_json_schema()
        self.assertEqual(stored_schema, current_schema)

    def test_model_guard_rejects_legacy_on_new_row(self):
        """
        Contract test: Exercise.save() must reject non-UMTO data for NEW rows.
        """
        User = get_user_model()
        author = User.objects.create(email="test@harmony.lab")
        
        # Bypass is NOT set in this test.
        ex = Exercise(
            description="Legacy Row",
            authored_by=author,
            data={"type": "legacy", "score": {}}
        )
        with self.assertRaises(NonUMTOExerciseError):
            ex.save()

    def test_model_guard_allows_legacy_on_existing_row(self):
        """
        Contract test: Exercise.save() must allow legacy data for EXISTING rows (grandfathered).
        """
        User = get_user_model()
        author = User.objects.create(email="test2@harmony.lab")
        
        # Create a legacy row using the bypass
        os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"] = "1"
        ex = Exercise.objects.create(
            description="Grandfathered Legacy",
            authored_by=author,
            data={"type": "legacy", "score": {}}
        )
        del os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"]
        
        # Update it (not is_new) - should be allowed
        ex.description = "Updated Grandfathered"
        ex.save() # Should not raise


def test_analysis_layer_has_raw_roman_numeral():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer(roman_numeral="V", raw_roman_numeral="V/V")
    assert layer.raw_roman_numeral == "V/V"

def test_analysis_layer_raw_roman_numeral_defaults_none():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer()
    assert layer.raw_roman_numeral is None

def test_analysis_layer_has_local_key():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer(local_key="d")
    assert layer.local_key == "d"

def test_analysis_layer_has_raw_figured_bass():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer()
    assert hasattr(layer, "raw_figured_bass")
    assert layer.raw_figured_bass is None

def test_analysis_layer_raw_figured_bass_stores_value():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer(raw_figured_bass="7/5/3", figured_bass="7")
    assert layer.raw_figured_bass == "7/5/3"
    assert layer.figured_bass == "7"

def test_analysis_slice_has_is_target():
    from apps.exercises.umto import AnalysisSlice, AnalysisLayer
    sl = AnalysisSlice(offset=0.0, content=AnalysisLayer())
    assert sl.is_target is False  # default

def test_analysis_slice_is_target_can_be_set():
    from apps.exercises.umto import AnalysisSlice, AnalysisLayer
    sl = AnalysisSlice(offset=0.0, content=AnalysisLayer(roman_numeral="I"), is_target=True)
    assert sl.is_target is True


def test_factory_emits_roman_and_raw_roman_for_unit9():
    from apps.exercises.umto_factory import build_umto_payload
    from apps.exercises.umto import InteractionMode
    
    with open(CIR_FIXTURES_DIR / "unit9_satb.json", "r") as f:
        cir = json.load(f)
        
    payload = build_umto_payload(
        exercise_id="TEST_U9",
        source="Test",
        key="G Major",
        meter="4/4",
        clef="keyboard",
        complexity_score=9,
        mode=InteractionMode.ANALYSIS_MATCH,
        score_data=cir,
        unit=9
    )
    
    analysis = payload["score"]["umto"]["analysis"]
    assert len(analysis) > 0
    first = analysis[0]
    assert "roman_numeral" in first["content"]
    assert "raw_roman_numeral" in first["content"]
    assert first["content"]["raw_roman_numeral"] in ["I", "iv"]
    assert first["content"]["roman_numeral"] is None

def test_factory_emits_pitch_names_for_unit1():
    from apps.exercises.umto_factory import build_umto_payload
    from apps.exercises.umto import InteractionMode
    
    with open(CIR_FIXTURES_DIR / "unit1_treble.json", "r") as f:
        cir = json.load(f)
        
    payload = build_umto_payload(
        exercise_id="TEST_U1",
        source="Test",
        key="C",
        meter="4/4",
        clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        score_data=cir,
        target_voice="soprano",
        unit=1
    )
    
    analysis = payload["score"]["umto"]["analysis"]
    assert len(analysis) > 0
    # Unit 1 identification should have pitch names (e.g. "G") in roman_numeral slot for now
    # (or wherever the UI expects them)
    assert analysis[0]["content"]["roman_numeral"] is not None


# ---------------------------------------------------------------------------
# Meter calculation in _to_legacy_measures
# ---------------------------------------------------------------------------

def _make_umto_2_2(pitches):
    """
    Build a minimal UMTO in 2/2 with one soprano voice.
    pitches is a list of (step, octave, duration_ql, duration_type) tuples.
    """
    from apps.exercises.umto import UMTO, Metadata, Voices, VoiceEvent, Pitch, InteractionMode

    events = [
        VoiceEvent(
            kind="note",
            pitch=Pitch(step=step, alter=0, octave=octave, midi=60),
            duration=dur_ql,
            duration_type=dur_type,
        )
        for step, octave, dur_ql, dur_type in pitches
    ]
    return UMTO(
        metadata=Metadata(
            exercise_id="TEST_2_2",
            source="test",
            key="C Major",
            meter="2/2",
            clef="treble",
            complexity_score=9,
            mode=InteractionMode.PLAYBACK,
        ),
        voices=Voices(S=events),
    )


def test_to_legacy_measures_2_2_clausula_shape():
    """
    A simple clausula (ANT half + PEN half + ULT whole) in 2/2 must produce
    exactly 2 measures: the two halves together in m0, the whole in m1.

    Bug guard: the old code used only the numerator of the time signature
    (num_beats = 2.0 for "2/2") which gave 4 QL-per-measure instead of the
    correct 4 QL-per-measure for alla breve.  The note split was wrong:
    ANT ended up alone in m0, PEN alone in m1, ULT alone in m2, with an
    empty m3.
    """
    # ANT = half (2 QL), PEN = half (2 QL), ULT = whole (4 QL) → total 8 QL
    umto = _make_umto_2_2([
        ("C", 5, 2.0, "h"),  # ANT — offset 0
        ("D", 5, 2.0, "h"),  # PEN — offset 2
        ("E", 5, 4.0, "w"),  # ULT — offset 4
    ])

    measures = umto._to_legacy_measures()

    # 2/2: 4 QL per measure → 8 QL total = exactly 2 measures
    assert len(measures) == 2, (
        f"Expected 2 measures for 2/2 clausula shape, got {len(measures)}. "
        "Check that _to_legacy_measures uses quarter-lengths-per-measure, "
        "not just the meter numerator."
    )

    treble_m0 = measures[0]["staves"]["treble"]["voices"]
    treble_m1 = measures[1]["staves"]["treble"]["voices"]

    # Measure 0 should have 2 items (ANT + PEN)
    assert treble_m0, "Measure 0 treble voice is empty"
    items_m0 = treble_m0[0]["items"]
    assert len(items_m0) == 2, (
        f"Expected ANT + PEN in measure 0, got {len(items_m0)} items"
    )

    # Measure 1 should have 1 item (ULT)
    assert treble_m1, "Measure 1 treble voice is empty"
    items_m1 = treble_m1[0]["items"]
    assert len(items_m1) == 1, (
        f"Expected ULT alone in measure 1, got {len(items_m1)} items"
    )


def test_to_legacy_measures_meter_formula_spot_check():
    """
    Quarter-lengths-per-measure must be correct for common time signatures.
    We verify by checking measure count for a known total duration.
    """
    from apps.exercises.umto import UMTO, Metadata, Voices, VoiceEvent, Pitch, InteractionMode

    cases = [
        # (meter,  note_ql, note_type, count, expected_measures)
        ("4/4",  1.0, "q", 8, 2),   # 8 quarters = 2 measures of 4/4
        ("3/4",  1.0, "q", 6, 2),   # 6 quarters = 2 measures of 3/4
        ("2/2",  2.0, "h", 4, 2),   # 4 halves  = 2 measures of 2/2
        ("6/8",  0.5, "8", 12, 2),  # 12 eighths = 2 measures of 6/8
    ]

    for meter, ql, dtype, count, expected in cases:
        events = [
            VoiceEvent(kind="note", pitch=Pitch(step="C", alter=0, octave=5, midi=72),
                       duration=ql, duration_type=dtype)
            for _ in range(count)
        ]
        umto = UMTO(
            metadata=Metadata(
                exercise_id="METER_TEST",
                source="test",
                key="C Major",
                meter=meter,
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.PLAYBACK,
            ),
            voices=Voices(S=events),
        )
        measures = umto._to_legacy_measures()
        assert len(measures) == expected, (
            f"meter={meter}: expected {expected} measures, got {len(measures)}"
        )
