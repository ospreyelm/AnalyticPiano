import json
from fractions import Fraction

from django.test import SimpleTestCase

from apps.exercises.utils.barline_exercise_builder import build_barline_payload


class BarlineExerciseBuilderTests(SimpleTestCase):
    def test_simple_triple_quarter_notes_compute_barlines(self):
        payload = build_barline_payload(
            time_signature="3/4",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "8", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
            ],
            measures=3,
            show_time_signature=False,
            pitch_mode="rhythm_only",
            source="test",
        )

        self.assertEqual(payload["type"], "umto_barline_placement")
        self.assertEqual(payload["pickup_beats"], 0)
        self.assertEqual(payload["beat_count"], 9)
        self.assertEqual(payload["correct_barline_positions"], [2, 4])
        self.assertEqual(payload["beat_positions_ticks"], list(range(10)))
        self.assertEqual(payload["note_beat_onsets"], [0, 1, 2, 3, 5, 6, 7.5, 8])

    def test_compound_meter_counts_dotted_quarter_tactus_beats(self):
        payload = build_barline_payload(
            time_signature="6/8",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
            ],
            measures=2,
            show_time_signature=True,
            pitch_mode="rhythm_only",
            source="compound test",
        )

        self.assertEqual(payload["beat_count"], 4)
        self.assertEqual(payload["correct_barline_positions"], [1])
        self.assertEqual(payload["beat_positions_ticks"], [0, 3, 6, 9, 12])
        self.assertEqual(payload["note_beat_onsets"], [0, 1, 2, 3])

    def test_nine_eight_counts_three_tactus_beats_per_measure(self):
        payload = build_barline_payload(
            time_signature="9/8",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
            ],
            measures=2,
            show_time_signature=True,
            pitch_mode="rhythm_only",
            source="nine eight test",
        )

        self.assertEqual(payload["beat_count"], 6)
        self.assertEqual(payload["correct_barline_positions"], [2])
        self.assertEqual(payload["beat_positions_ticks"], [0, 3, 6, 9, 12, 15, 18])

    def test_twelve_eight_counts_four_tactus_beats_per_measure(self):
        payload = build_barline_payload(
            time_signature="12/8",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
            ],
            measures=2,
            show_time_signature=True,
            pitch_mode="rhythm_only",
            source="twelve eight test",
        )

        self.assertEqual(payload["beat_count"], 8)
        self.assertEqual(payload["correct_barline_positions"], [3])
        self.assertEqual(
            payload["beat_positions_ticks"], [0, 3, 6, 9, 12, 15, 18, 21, 24]
        )

    def test_pickup_beats_extend_duration_and_offset_internal_barlines(self):
        payload = build_barline_payload(
            time_signature="3/4",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
            ],
            measures=2,
            pickup_beats=1,
            show_time_signature=False,
            pitch_mode="rhythm_only",
            source="pickup test",
        )

        self.assertEqual(payload["pickup_beats"], 1)
        self.assertEqual(payload["beat_count"], 7)
        self.assertEqual(payload["correct_barline_positions"], [0, 3])
        self.assertEqual(payload["beat_positions_ticks"], list(range(8)))
        self.assertEqual(payload["note_beat_onsets"], [0, 1, 2, 3, 4, 5, 6])

    def test_fractional_pickup_uses_single_shortened_initial_slot(self):
        payload = build_barline_payload(
            time_signature="3/4",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "8", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
                {"pitch": "B4", "duration": "q", "dots": 0},
            ],
            measures=2,
            pickup_beats=Fraction(1, 2),
            show_time_signature=False,
            pitch_mode="rhythm_only",
            source="fractional pickup test",
        )

        beat_positions = payload["beat_positions_ticks"]
        self.assertEqual(payload["pickup_beats"], 0.5)
        self.assertEqual(payload["beat_count"], 7)
        self.assertEqual(payload["correct_barline_positions"], [0, 3])
        self.assertEqual(beat_positions, [0, 1, 3, 5, 7, 9, 11, 13])
        self.assertLess(
            beat_positions[1] - beat_positions[0],
            beat_positions[2] - beat_positions[1],
        )
        self.assertEqual(payload["note_beat_onsets"][:3], [0, 0.5, 1.5])
        json.dumps(payload)

    def test_note_spanning_beat_boundary_still_stores_boundary_ticks(self):
        payload = build_barline_payload(
            time_signature="2/4",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
            ],
            measures=2,
            show_time_signature=False,
            pitch_mode="rhythm_only",
            source="spanning test",
        )

        self.assertEqual(payload["beat_count"], 4)
        self.assertEqual(payload["correct_barline_positions"], [0])
        self.assertEqual(payload["beat_positions_ticks"], [0, 1, 2, 3, 4])

    def test_rejects_duration_total_that_does_not_fill_measures(self):
        with self.assertRaisesMessage(ValueError, "total duration"):
            build_barline_payload(
                time_signature="3/4",
                clef="treble",
                notes=[{"pitch": "B4", "duration": "q", "dots": 0}],
                measures=1,
                show_time_signature=False,
                pitch_mode="rhythm_only",
                source="invalid",
            )

    def test_rejects_duration_total_that_overfills_measures(self):
        with self.assertRaisesMessage(ValueError, "total duration"):
            build_barline_payload(
                time_signature="3/4",
                clef="treble",
                notes=[{"pitch": "B4", "duration": "w", "dots": 0}],
                measures=1,
                show_time_signature=False,
                pitch_mode="rhythm_only",
                source="invalid overfill",
            )

    def test_rejects_negative_pickup_beats(self):
        with self.assertRaisesMessage(ValueError, "pickup_beats"):
            build_barline_payload(
                time_signature="3/4",
                clef="treble",
                notes=[
                    {"pitch": "B4", "duration": "h", "dots": 0},
                    {"pitch": "B4", "duration": "q", "dots": 0},
                ],
                measures=1,
                pickup_beats=-1,
                show_time_signature=False,
                pitch_mode="rhythm_only",
                source="invalid negative pickup",
            )

    def test_rejects_pickup_beats_at_least_full_measure(self):
        with self.assertRaisesMessage(ValueError, "pickup_beats"):
            build_barline_payload(
                time_signature="3/4",
                clef="treble",
                notes=[
                    {"pitch": "B4", "duration": "w", "dots": 1},
                ],
                measures=1,
                pickup_beats=3,
                show_time_signature=False,
                pitch_mode="rhythm_only",
                source="invalid full-measure pickup",
            )

    def test_simple_derived_meter_2_2(self):
        payload = build_barline_payload(
            time_signature="2/2",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
            ],
            measures=2,
            show_time_signature=True,
            pitch_mode="rhythm_only",
            source="test",
        )
        self.assertEqual(payload["type"], "umto_barline_placement")
        self.assertEqual(payload["beat_count"], 4)
        self.assertEqual(payload["correct_barline_positions"], [1])

    def test_simple_derived_meter_3_2(self):
        payload = build_barline_payload(
            time_signature="3/2",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
                {"pitch": "B4", "duration": "h", "dots": 0},
            ],
            measures=2,
            show_time_signature=True,
            pitch_mode="rhythm_only",
            source="test",
        )
        self.assertEqual(payload["beat_count"], 6)
        self.assertEqual(payload["correct_barline_positions"], [2])

    def test_compound_derived_meter_6_4(self):
        payload = build_barline_payload(
            time_signature="6/4",
            clef="treble",
            notes=[
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
                {"pitch": "B4", "duration": "q", "dots": 1},
            ],
            measures=2,
            show_time_signature=True,
            pitch_mode="rhythm_only",
            source="test",
        )
        self.assertEqual(payload["beat_count"], 4)
        self.assertEqual(payload["correct_barline_positions"], [3])
