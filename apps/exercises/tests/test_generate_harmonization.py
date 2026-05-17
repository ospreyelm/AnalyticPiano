import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.exercises.models import Exercise


def _source_data(analysis=None):
    if analysis is None:
        analysis = [{
            "offset": 0.0,
            "content": {
                "roman_numeral": None,
                "raw_roman_numeral": None,
                "local_key": "C",
                "raw_figured_bass": "6/3",
                "figured_bass": "6",
                "pop_symbol": None,
                "functional_label": None,
            },
            "visual": None,
            "unit_tags": [],
            "is_target": False,
        }]
    return {
        "isUMTO": True,
        "type": "umto_chorale",
        "mode": "playback",
        "analysisType": "figured_bass",
        "score": {
            "umto": {
                "metadata": {
                    "exercise_id": "SRC001",
                    "source": "Synthetic source",
                    "key": "C",
                    "meter": "4/4",
                    "clef": "keyboard",
                    "complexity_score": 9,
                    "mode": "playback",
                    "is_umto": True,
                    "input_mode": "dropdown",
                },
                "voices": {
                    "S": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4, "midi": 60}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                    "A": [{"kind": "note", "pitch": {"step": "A", "alter": 0, "octave": 3, "midi": 57}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                    "T": [{"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 3, "midi": 52}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                    "B": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 3, "midi": 48}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                },
                "analysis": analysis,
                "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60], "rhythmic_flexibility": False}],
            }
        },
        "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60], "rhythmic_flexibility": False}],
    }


class GenerateHarmonizationCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="pw",
        )
        self.source = Exercise.objects.create(
            description="Source UMTO",
            authored_by=self.user,
            data=_source_data(),
        )

    def _created(self):
        return Exercise.objects.filter(authored_by=self.user).exclude(id=self.source.id)

    def test_command_creates_harmonization_exercise(self):
        call_command(
            "generate_harmonization",
            source=self.source.id,
            author="admin@example.com",
            locked_voices="B",
            min_voices=3,
            max_voices=4,
        )

        created = self._created().get()
        umto = created.data["score"]["umto"]
        assert umto["metadata"]["mode"] == "harmonization"
        assert umto["metadata"]["locked_voices"] == ["B"]
        assert created.data["introText"].startswith("Realize the Figured Bass of ")
        assert umto["metadata"]["source"].startswith("Realize the Figured Bass of ")
        assert created.data["harmonizationTargets"][0]["figures"] == ["6", "3"]

    def test_command_sets_voice_count_policy(self):
        call_command(
            "generate_harmonization",
            source=self.source.id,
            author="admin@example.com",
            locked_voices="B",
            voice_count=4,
            min_voices=3,
            max_voices=4,
        )
        created = self._created().get()
        umto = created.data["score"]["umto"]
        assert umto["metadata"]["voice_count_policy"] == {"expected": 4, "min": 3, "max": 4}

    def test_command_is_idempotent(self):
        call_command(
            "generate_harmonization",
            source=self.source.id,
            author="admin@example.com",
            locked_voices="B",
            min_voices=3,
            max_voices=4,
        )
        call_command(
            "generate_harmonization",
            source=self.source.id,
            author="admin@example.com",
            locked_voices="B",
            min_voices=3,
            max_voices=4,
        )
        assert self._created().count() == 1

    def test_command_raises_on_zero_targets(self):
        source_no_analysis = Exercise.objects.create(
            description="No analysis",
            authored_by=self.user,
            data=_source_data(analysis=[]),
        )
        with pytest.raises(CommandError, match="zero targets"):
            call_command(
                "generate_harmonization",
                source=source_no_analysis.id,
                author="admin@example.com",
                locked_voices="B",
                min_voices=3,
                max_voices=4,
            )

    def test_command_raises_on_missing_source(self):
        with pytest.raises(CommandError, match="not found"):
            call_command(
                "generate_harmonization",
                source=999999,
                author="admin@example.com",
                locked_voices="B",
                min_voices=3,
                max_voices=4,
            )

    def test_harmonization_targets_have_display_figure(self):
        call_command(
            "generate_harmonization",
            source=self.source.id,
            author="admin@example.com",
            locked_voices="B",
            min_voices=3,
            max_voices=4,
        )
        created = self._created().get()
        target = created.data["harmonizationTargets"][0]
        assert target["displayFigure"] == "6"
        assert target["figures"] == ["6", "3"]   # from raw_figured_bass "6/3"
