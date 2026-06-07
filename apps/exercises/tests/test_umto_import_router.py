import io
import tempfile
import unittest
from unittest.mock import Mock, patch

from music21 import chord, meter, note, stream

from apps.exercises.utils.umto_import_router import (
    iter_legacy_chord_csv_rows,
    legacy_csv_row_to_chordal_payload,
    classify_musicxml_score,
    musicxml_score_to_chord_events,
)
from apps.exercises.management.commands.import_musicxml import _build_import_payload_for_score


class LegacyChordCSVTests(unittest.TestCase):
    def test_iter_legacy_chord_csv_rows_extracts_chord_data(self):
        csv_text = (
            'id,description,data\n'
            'EA1,Example,"{""type"": ""matching"", ""key"": ""jC_"", '
            '""chord"": [{""visible"": [60], ""hidden"": []}]}"\n'
        )

        rows = list(iter_legacy_chord_csv_rows(io.StringIO(csv_text)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].exercise_id, "EA1")
        self.assertEqual(rows[0].description, "Example")
        self.assertEqual(rows[0].data["chord"][0]["visible"], [60])

    def test_iter_legacy_chord_csv_rows_skips_non_chord_rows(self):
        csv_text = (
            'id,description,data\n'
            'EA1,No chord,"{""type"": ""matching"", ""key"": ""jC_""}"\n'
            'EA2,Empty chord,"{""type"": ""matching"", ""key"": ""jC_"", ""chord"": []}"\n'
        )

        rows = list(iter_legacy_chord_csv_rows(io.StringIO(csv_text)))

        self.assertEqual(rows, [])


class LegacyChordCSVPayloadTests(unittest.TestCase):
    def test_legacy_csv_row_to_chordal_payload_uses_chordal_umto(self):
        row = list(iter_legacy_chord_csv_rows(io.StringIO(
            'id,description,data\n'
            'EA1,Example,"{""type"": ""matching"", ""key"": ""jC_"", '
            '""chord"": [{""visible"": [60, 64], ""hidden"": []}]}"\n'
        )))[0]

        payload = legacy_csv_row_to_chordal_payload(row)

        self.assertTrue(payload["isUMTO"])
        self.assertEqual(payload["score"]["umto"]["metadata"]["score_kind"], "chordal")
        self.assertEqual(payload["score"]["umto"]["metadata"]["exercise_id"], "EA1")
        self.assertEqual(payload["score"]["umto"]["metadata"]["source"], "Example")
        self.assertEqual(payload["score"]["umto"]["chords"][0]["visible"], [60, 64])


def _part_with_note(name, pitch_name):
    part = stream.Part()
    part.partName = name
    measure = stream.Measure(number=1)
    measure.append(note.Note(pitch_name, quarterLength=4.0))
    part.append(measure)
    return part


class MusicXMLClassifierTests(unittest.TestCase):
    def test_four_stable_parts_classify_as_voices(self):
        score = stream.Score()
        score.append(meter.TimeSignature("4/4"))
        for name, pitch_name in [
            ("Soprano", "C5"),
            ("Alto", "A4"),
            ("Tenor", "E3"),
            ("Bass", "C3"),
        ]:
            score.append(_part_with_note(name, pitch_name))

        decision = classify_musicxml_score(score)

        self.assertEqual(decision.route, "voices")
        self.assertEqual(decision.part_count, 4)

    def test_two_stable_parts_classify_as_voices(self):
        score = stream.Score()
        score.append(_part_with_note("Right Hand", "C5"))
        score.append(_part_with_note("Left Hand", "C3"))

        self.assertEqual(classify_musicxml_score(score).route, "voices")

    def test_single_part_with_chords_classifies_as_chordal(self):
        score = stream.Score()
        part = stream.Part()
        measure = stream.Measure(number=1)
        measure.append(chord.Chord(["C4", "E4", "G4"], quarterLength=4.0))
        part.append(measure)
        score.append(part)

        decision = classify_musicxml_score(score)

        self.assertEqual(decision.route, "chordal")
        self.assertTrue(decision.has_chords)

    def test_single_monophonic_part_classifies_as_chordal(self):
        score = stream.Score()
        score.append(_part_with_note("Melody", "C4"))

        self.assertEqual(classify_musicxml_score(score).route, "chordal")


class ChordalMusicXMLConversionTests(unittest.TestCase):
    def test_chordal_conversion_groups_offsets_and_preserves_spelling(self):
        score = stream.Score()
        part = stream.Part()
        measure = stream.Measure(number=1)
        measure.append(note.Note("C4", quarterLength=1.0))
        measure.append(chord.Chord(["F#4", "A4"], quarterLength=2.0))
        part.append(measure)
        score.append(part)

        events = musicxml_score_to_chord_events(score)

        self.assertEqual(events[0]["offset"], 0.0)
        self.assertEqual(events[0]["duration"], 1.0)
        self.assertEqual(events[0]["visible"], [60])
        self.assertEqual(events[0]["spelling"], ["C4"])
        self.assertEqual(events[1]["offset"], 1.0)
        self.assertEqual(events[1]["duration"], 2.0)
        self.assertEqual(events[1]["visible"], [66, 69])
        self.assertEqual(events[1]["spelling"], ["F#4", "A4"])

    def test_chordal_conversion_groups_simultaneous_parts(self):
        score = stream.Score()
        score.append(_part_with_note("Top", "C5"))
        score.append(_part_with_note("Bass", "C3"))

        events = musicxml_score_to_chord_events(score)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["offset"], 0.0)
        self.assertEqual(events[0]["visible"], [72, 48])


class ImportMusicXMLRoutingTests(unittest.TestCase):
    def test_build_import_payload_for_score_keeps_multipart_as_voices(self):
        score = stream.Score()
        for name, pitch_name in [
            ("Soprano", "C5"),
            ("Alto", "A4"),
            ("Tenor", "E3"),
            ("Bass", "C3"),
        ]:
            score.append(_part_with_note(name, pitch_name))

        result = _build_import_payload_for_score(
            score,
            title="multipart",
            harmony_key="jC_",
            start_measure=0,
            end_measure=None,
            complexity=1,
        )

        self.assertEqual(result.decision.route, "voices")
        self.assertIsNone(result.payload)
        self.assertTrue(result.score_data["measures"])

    def test_build_import_payload_for_score_builds_chordal_payload_for_chords(self):
        score = stream.Score()
        part = stream.Part()
        measure = stream.Measure(number=1)
        measure.append(chord.Chord(["C4", "E4", "G4"], quarterLength=1.0))
        part.append(measure)
        score.append(part)

        result = _build_import_payload_for_score(
            score,
            title="chords",
            harmony_key="jC_",
            start_measure=0,
            end_measure=None,
            complexity=1,
        )

        self.assertEqual(result.decision.route, "chordal")
        self.assertIsNone(result.score_data)
        self.assertEqual(result.payload["score"]["umto"]["metadata"]["score_kind"], "chordal")
        self.assertEqual(result.payload["score"]["umto"]["chords"][0]["visible"], [60, 64, 67])

    def test_chordal_route_honors_start_and_end_measure(self):
        score = stream.Score()
        score.append(meter.TimeSignature("4/4"))
        part = stream.Part()
        first = stream.Measure(number=1)
        first.append(chord.Chord(["C4", "E4", "G4"], quarterLength=4.0))
        second = stream.Measure(number=2)
        second.append(chord.Chord(["D4", "F4", "A4"], quarterLength=4.0))
        part.append(first)
        part.append(second)
        score.append(part)

        result = _build_import_payload_for_score(
            score,
            title="chords",
            harmony_key="jC_",
            start_measure=1,
            end_measure=2,
            complexity=1,
        )

        chords = result.payload["score"]["umto"]["chords"]
        self.assertEqual(len(chords), 1)
        self.assertEqual(chords[0]["offset"], 0.0)
        self.assertEqual(chords[0]["visible"], [62, 65, 69])


class ImportLegacyChordCSVCommandTests(unittest.TestCase):
    def test_dry_run_parses_rows_without_saving(self):
        from apps.exercises.management.commands.import_legacy_chord_csv import Command

        csv_text = (
            'id,description,data\n'
            'EA1,Example,"{""type"": ""matching"", ""key"": ""jC_"", '
            '""chord"": [{""visible"": [60], ""hidden"": []}]}"\n'
        )
        with tempfile.NamedTemporaryFile("w+", suffix=".csv") as handle:
            handle.write(csv_text)
            handle.flush()

            command = Command()
            command.stdout = io.StringIO()
            with patch("apps.exercises.management.commands.import_legacy_chord_csv.User") as user_cls:
                user_cls.objects.get.return_value = Mock()
                command.handle(
                    path=handle.name,
                    author="admin@example.com",
                    public=False,
                    dry_run=True,
                    limit=None,
                )

        self.assertIn("Parsed 1 legacy chord rows", command.stdout.getvalue())
