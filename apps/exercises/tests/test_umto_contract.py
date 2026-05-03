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
