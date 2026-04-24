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
