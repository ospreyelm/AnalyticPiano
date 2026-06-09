from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class SaveChordalAuthoringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="t@example.com", password="x"
        )

    def _chords(self):
        return [{"offset": float(i), "duration": 1.0, "visible": [60, 64, 67]}
                for i in range(8)]

    def test_no_auto_stretch_last_chord_keeps_duration(self):
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=self._chords(),
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
        )
        chords = ex.data["score"]["umto"]["chords"]
        assert chords[-1]["duration"] == 1.0

    def test_reviewed_analysis_sets_status_reviewed_without_regeneration(self):
        analysis = [{"offset": 0.0, "content": {"roman_numeral": "I"},
                     "unit_tags": [], "is_target": True}]
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=self._chords(),
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
            analysis=analysis,
        )
        md = ex.data["score"]["umto"]["metadata"]
        assert md["analysis_review_status"] == "reviewed"
        assert ex.data["score"]["umto"]["analysis"][0]["content"]["roman_numeral"] == "I"

    def test_no_analysis_slot_saves_playback_status_none(self):
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=self._chords(),
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
            analysis=[],
        )
        md = ex.data["score"]["umto"]["metadata"]
        assert md["analysis_review_status"] == "none"

    def test_invalid_metered_rhythm_rejected(self):
        from apps.exercises.models import NonUMTOExerciseError
        bad = [{"offset": 0.0, "duration": 1.0, "visible": [60]},
               {"offset": 1.0, "duration": 1.0, "visible": [60]},
               {"offset": 2.0, "duration": 1.0, "visible": [60]}]
        with self.assertRaises(NonUMTOExerciseError):
            save_chordal_umto_exercise(
                description="t", author=self.user, chords=bad,
                key="C major", meter="4/4", clef="keyboard",
                staff_distribution="keyboard",
            )

    def test_free_mode_saves_uneven_durations(self):
        chords = [{"offset": 0.0, "duration": 1.0, "visible": [60]},
                  {"offset": 1.0, "duration": 0.5, "visible": [62]}]
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=chords,
            key="C major", meter=None, clef="keyboard",
            staff_distribution="keyboard",
        )
        assert ex.data["score"]["umto"]["metadata"]["meter"] is None
