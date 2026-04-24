import json
import os
from django.test import TestCase
from apps.exercises.umto import UMTO

FIXTURE_DIR = "apps/exercises/tests/fixtures/umto"


class UMTOContractTests(TestCase):
    """
    Contract tests to ensure hand-authored 'golden' fixtures 
    remain valid against the current UMTO Pydantic models.
    """

    def _validate_fixture(self, filename):
        path = os.path.join(FIXTURE_DIR, filename)
        with open(path, "r") as f:
            data = json.load(f)
        
        # This will raise ValidationError if the fixture doesn't match the schema
        UMTO.model_validate(data)

    def test_minimal_fixture_validates(self):
        self._validate_fixture("minimal.json")

    def test_maximal_fixture_validates(self):
        self._validate_fixture("maximal.json")

    def test_unit1_identification_treble_validates(self):
        self._validate_fixture("unit1_identification_treble.json")

    def test_unit1_identification_bass_validates(self):
        self._validate_fixture("unit1_identification_bass.json")

    def test_unit1_playback_treble_validates(self):
        self._validate_fixture("unit1_playback_treble.json")

    def test_unit1_analysis_treble_validates(self):
        self._validate_fixture("unit1_analysis_treble.json")

    def test_unit9_chorale_roman_validates(self):
        self._validate_fixture("unit9_chorale_roman.json")

    def test_unit12_chromatic_analysis_validates(self):
        self._validate_fixture("unit12_chromatic_analysis.json")
