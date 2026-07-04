from apps.exercises.umto import Pitch, VoiceEvent
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from unittest.mock import patch


def _make_voice_events(pitches_ql):
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
    return _make_voice_events([
        ("C", 0, 5, 72, 2.0, "h"),
        ("B", 0, 4, 71, 2.0, "h"),
        ("C", 0, 5, 72, 4.0, "w"),
    ])


def _alto_c():
    return _make_voice_events([
        ("E", 0, 4, 64, 2.0, "h"),
        ("D", 0, 4, 62, 2.0, "h"),
        ("E", 0, 4, 64, 4.0, "w"),
    ])


def _bass_c():
    return _make_voice_events([
        ("C", 0, 3, 48, 2.0, "h"),
        ("G", 0, 3, 55, 2.0, "h"),
        ("C", 0, 3, 48, 4.0, "w"),
    ])


def test_harmonization_payload_uses_existing_figured_bass_contract():
    from apps.exercises.management.commands.generate_harmonization_from_clausulae import (
        _build_harmonization_payload,
    )

    payload = _build_harmonization_payload(
        {"S": _discant_c(), "A": _alto_c(), "B": _bass_c()},
        key="C",
        description="3-part Harmonization Cadence in C [test]",
        unit=9,
    )

    assert payload["mode"] == "harmonization"
    assert payload["analysisType"] == "figured_bass"
    assert payload["display"]["maxMeasures"] == 2
    assert payload["score"]["umto"]["metadata"]["mode"] == "harmonization"
    assert payload["score"]["umto"]["metadata"]["locked_voices"] == ["B"]
    assert payload["score"]["umto"]["metadata"]["voice_count_policy"] == {
        "expected": None,
        "min": 3,
        "max": 4,
    }
    assert (
        payload["score"]["umto"]["metadata"]["harmonization_target_policy"]["source"]
        == "figured_bass"
    )

    analysis = payload["score"]["umto"]["analysis"]
    assert [s["offset"] for s in analysis] == [0.0, 2.0, 4.0]
    assert [s["content"]["figured_bass"] for s in analysis] == ["5/3", "5/3", "5/3"]
    assert [s["content"]["raw_figured_bass"] for s in analysis] == [
        "5/3",
        "5/3",
        "5/3",
    ]
    assert all(s["is_target"] is False for s in analysis)

    targets = payload["harmonizationTargets"]
    assert len(targets) == 3
    assert [t["offset"] for t in targets] == [0.0, 2.0, 4.0]
    assert all(t["lockedVoices"]["B"]["midi"] in {48, 55} for t in targets)
    assert targets[0]["allowedPcs"] == [0, 7, 4]
    assert targets[1]["allowedPcs"] == [7, 2, 11]


def test_harmonization_payload_keeps_bass_in_locked_voice_slot():
    from apps.exercises.management.commands.generate_harmonization_from_clausulae import (
        _build_harmonization_payload,
    )

    payload = _build_harmonization_payload(
        {"S": _discant_c(), "A": _alto_c(), "B": _bass_c()},
        key="C",
        description="3-part Harmonization Cadence in C [test]",
        unit=9,
    )

    bass_voices = payload["score"]["measures"][0]["staves"]["bass"]["voices"]
    assert len(bass_voices) == 2
    assert bass_voices[0]["items"] == []
    assert [item["pitch"]["step"] for item in bass_voices[1]["items"]] == ["C", "G"]


def test_unit9_target_keys_include_expanded_major_key_set():
    from apps.exercises.management.commands.generate_harmonization_from_clausulae import (
        TARGET_KEYS,
    )

    assert TARGET_KEYS == ["C", "F", "G", "D", "Bb", "Eb", "E", "Ab", "A"]


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
        (2, 1, 0): [
            _FakeNote("E", octave, 12 * (octave + 1) + 4),
            _FakeNote("D", octave, 12 * (octave + 1) + 2),
            _FakeNote("C", octave, 12 * (octave + 1)),
        ],
        (4, 3, 2): [
            _FakeNote("G", octave, 12 * (octave + 1) + 7),
            _FakeNote("F", octave, 12 * (octave + 1) + 5),
            _FakeNote("E", octave, 12 * (octave + 1) + 4),
        ],
        (0, 4, 0): [
            _FakeNote("C", octave, 12 * (octave + 1)),
            _FakeNote("G", octave, 12 * (octave + 1) + 7),
            _FakeNote("C", octave, 12 * (octave + 1)),
        ],
    }
    return mapping[triple]


class GenerateHarmonizationFromClausulaeCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="pw",
        )

    def test_command_generates_idempotent_harmonization_playlist(self):
        combo = (
            ("Discant", 0, (0, 6, 0)),
            ("Tenor", 1, (2, 1, 2)),
            ("Bass", 0, (0, 4, 0)),
        )

        with patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae.enumerate_simple",
            return_value=[combo],
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
                unit=9,
                voices="3",
                overwrite=True,
            )
            call_command(
                "generate_harmonization_from_clausulae",
                author="admin@example.com",
                unit=9,
                voices="3",
                overwrite=True,
            )

        from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

        exercises = Exercise.objects.filter(
            authored_by=self.user,
            skill_tags__contains=["exercise_type:harmonization_from_clausulae"],
        )
        assert exercises.count() == 1
        exercise = exercises.get()
        assert exercise.data["mode"] == "harmonization"
        assert exercise.data["analysisType"] == "figured_bass"
        assert exercise.data["score"]["umto"]["metadata"]["locked_voices"] == ["B"]
        assert len(exercise.data["harmonizationTargets"]) == 3

        playlist = Playlist.objects.get(
            name="Unit 9 - Authentic Cadences (Harmonization)",
            authored_by=self.user,
        )
        assert ExercisePlaylistOrdered.objects.filter(playlist=playlist).count() == 1

    def test_command_deduplicates_student_equivalent_upper_voice_variants(self):
        combo_a = (
            ("Discant", 0, (0, 6, 0)),
            ("Tenor", 2, (2, 1, 0)),
            ("Bass", 0, (0, 4, 0)),
        )
        combo_b = (
            ("Discant", 0, (0, 6, 0)),
            ("Tenor", 3, (2, 1, 2)),
            ("Bass", 0, (0, 4, 0)),
        )

        with patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae.enumerate_simple",
            return_value=[combo_a, combo_b],
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
                unit=9,
                voices="3",
                overwrite=True,
            )

        from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

        exercises = Exercise.objects.filter(
            authored_by=self.user,
            skill_tags__contains=["exercise_type:harmonization_from_clausulae"],
        )
        assert exercises.count() == 1
        playlist = Playlist.objects.get(
            name="Unit 9 - Authentic Cadences (Harmonization)",
            authored_by=self.user,
        )
        assert ExercisePlaylistOrdered.objects.filter(playlist=playlist).count() == 1

    def test_command_uses_student_facing_harmonization_names(self):
        combo = (
            ("Discant", 0, (0, 6, 0)),
            ("Tenor", 3, (2, 1, 2)),
            ("Bass", 0, (0, 4, 0)),
        )

        with patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae.enumerate_simple",
            return_value=[combo],
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
                unit=9,
                voices="3",
                overwrite=True,
            )

        from apps.exercises.models import Exercise, Playlist

        playlist = Playlist.objects.get(
            name="Unit 9 - Authentic Cadences (Harmonization)",
            authored_by=self.user,
        )
        exercise = Exercise.objects.get(
            authored_by=self.user,
            skill_tags__contains=["exercise_type:harmonization_from_clausulae"],
        )
        assert "3-voice" not in playlist.name
        assert "3-part" not in exercise.description
        assert exercise.description == "Harmonization Cadence in C"

    def test_command_renames_existing_legacy_voice_count_playlist(self):
        from apps.exercises.models import Playlist

        combo = (
            ("Discant", 0, (0, 6, 0)),
            ("Tenor", 3, (2, 1, 2)),
            ("Bass", 0, (0, 4, 0)),
        )
        legacy = Playlist.objects.create(
            name="Unit 9 - Authentic Cadences (Harmonization) 3-voice",
            authored_by=self.user,
            is_public=True,
        )

        with patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae._CLAUSULAE_AVAILABLE",
            True,
        ), patch(
            "apps.exercises.management.commands.generate_harmonization_from_clausulae.enumerate_simple",
            return_value=[combo],
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
                unit=9,
                voices="3",
                overwrite=True,
            )

        legacy.refresh_from_db()
        assert legacy.name == "Unit 9 - Authentic Cadences (Harmonization)"
        assert not Playlist.objects.filter(
            name="Unit 9 - Authentic Cadences (Harmonization) 3-voice",
            authored_by=self.user,
        ).exists()

    def test_unit10_command_generates_first_inversion_harmonization_profile(self):
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

        from apps.exercises.models import Exercise, Playlist

        playlist = Playlist.objects.get(
            name="Unit 10 - Third in the Bass (Harmonization)",
            authored_by=self.user,
        )
        exercise = Exercise.objects.get(
            authored_by=self.user,
            skill_tags__contains=["exercise_type:harmonization_from_clausulae"],
        )
        assert playlist.skill_tags == [
            "exercise_type:harmonization_from_clausulae",
            "unit:10",
            "Inversions_First",
        ]
        assert exercise.description == "Third-in-the-Bass Cadence in C"
        assert "Inversions_First" in exercise.skill_tags
        assert "Cadence_Perfect_Authentic" not in exercise.skill_tags

        analysis = exercise.data["score"]["umto"]["analysis"]
        assert [s["content"]["figured_bass"] for s in analysis] == ["6", "6", "6"]
        assert [s["content"]["raw_figured_bass"] for s in analysis] == [
            "6/3",
            "6/3",
            "6/3",
        ]
        targets = exercise.data["harmonizationTargets"]
        assert [t["lockedVoices"]["B"]["midi"] for t in targets] == [52, 50, 52]

    def test_student_context_preserves_figured_bass_analysis_type(self):
        from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
        from apps.exercises.services.exercise_context import generate_exercise_context

        payload = _build_context_payload()
        exercise = Exercise.objects.create(
            description="Context Harmonization From Clausulae",
            authored_by=self.user,
            data=payload,
            skill_tags=[
                "exercise_type:harmonization_from_clausulae",
                "unit:9",
                "mode:harmonization",
            ],
            complexity=9,
        )
        playlist = Playlist.objects.create(
            name="Unit 9 - Context Harmonization",
            authored_by=self.user,
            is_public=True,
            skill_tags=[
                "exercise_type:harmonization_from_clausulae",
                "unit:9",
                "mode:harmonization",
            ],
        )
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist,
            exercise=exercise,
            order=1,
        )

        context = generate_exercise_context(
            exercise=exercise,
            user=self.user,
            playlist=playlist,
            exercise_num=1,
        )

        assert context["mode"] == "harmonization"
        assert context["analysisType"] == "figured_bass"
        figures = [
            s["content"]["figured_bass"]
            for s in context["score"]["umto"]["analysis"]
        ]
        assert figures == ["5/3", "5/3", "5/3"]


def _build_context_payload():
    from apps.exercises.management.commands.generate_harmonization_from_clausulae import (
        _build_harmonization_payload,
    )

    return _build_harmonization_payload(
        {"S": _discant_c(), "A": _alto_c(), "B": _bass_c()},
        key="C",
        description="3-part Harmonization Cadence in C [context]",
        unit=9,
    )
