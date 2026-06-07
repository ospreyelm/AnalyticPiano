# MusicXML UMTO Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route imported MusicXML and legacy CSV chord-bank material into the correct UMTO score kind.

**Architecture:** Add a small backend import router module that classifies music21 scores as `voices` or `chordal`, converts chordal scores into Spec A `ChordEvent` payloads, and parses legacy CSV rows through the existing chordal wrapper. The existing voices-kind import path stays in place; `import_musicxml` delegates only the representation decision and chordal payload construction.

**Tech Stack:** Django management commands, Python stdlib `csv`/`json`, music21, Pydantic UMTO models, pytest/unittest.

---

## File Structure

- Create: `apps/exercises/utils/umto_import_router.py` — classifier, chordal MusicXML conversion, legacy CSV row parsing.
- Create: `apps/exercises/tests/test_umto_import_router.py` — focused tests for routing and conversion.
- Modify: `apps/exercises/management/commands/import_musicxml.py` — call the router and use chordal payloads for chordal sources.
- Create: `apps/exercises/management/commands/import_legacy_chord_csv.py` — dry-run/import command for `exercises_2026-04-03.csv`.
- Modify: `docs/management_commands.md` — document the new command.
- Modify: `docs/UMTO_GUIDE.md` — document MusicXML representation routing.

## Task 1: Legacy CSV Parser

**Files:**
- Create: `apps/exercises/utils/umto_import_router.py`
- Test: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write failing tests**

```python
import io
import unittest

from apps.exercises.utils.umto_import_router import iter_legacy_chord_csv_rows


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::LegacyChordCSVTests::test_iter_legacy_chord_csv_rows_extracts_chord_data -v`

Expected: FAIL with import error for `umto_import_router`.

- [ ] **Step 3: Implement parser**

Create a dataclass `LegacyChordCSVRow` and `iter_legacy_chord_csv_rows(file_obj)` using stdlib `csv.DictReader` and `json.loads(row["data"])`. Yield only rows whose data has a non-empty list at `chord`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::LegacyChordCSVTests -v`

Expected: PASS.

## Task 2: Legacy CSV Payload Conversion

**Files:**
- Modify: `apps/exercises/utils/umto_import_router.py`
- Modify: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write failing test**

```python
from apps.exercises.utils.umto_import_router import legacy_csv_row_to_chordal_payload


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
        self.assertEqual(payload["score"]["umto"]["chords"][0]["visible"], [60, 64])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::LegacyChordCSVPayloadTests -v`

Expected: FAIL with missing `legacy_csv_row_to_chordal_payload`.

- [ ] **Step 3: Implement conversion**

Call `legacy_chord_row_to_chordal_payload(row.data)`, then patch the generated UMTO metadata `exercise_id` and `source` from the CSV row.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::LegacyChordCSVPayloadTests -v`

Expected: PASS.

## Task 3: MusicXML Classifier

**Files:**
- Modify: `apps/exercises/utils/umto_import_router.py`
- Modify: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write failing tests**

```python
from music21 import chord, meter, note, stream

from apps.exercises.utils.umto_import_router import classify_musicxml_score


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
        for name, pitch_name in [("Soprano", "C5"), ("Alto", "A4"), ("Tenor", "E3"), ("Bass", "C3")]:
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::MusicXMLClassifierTests -v`

Expected: FAIL with missing `classify_musicxml_score`.

- [ ] **Step 3: Implement classifier**

Return a dataclass `MusicXMLRouteDecision(route, part_count, has_chords, reason)`. Count `score.parts`; detect chord events with `part.recurse().getElementsByClass(chord.Chord)`. Route explicit chords or one-part scores to `chordal`; route 2-4 part scores with content and no chords to `voices`; otherwise route `chordal`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::MusicXMLClassifierTests -v`

Expected: PASS.

## Task 4: Chordal MusicXML Conversion

**Files:**
- Modify: `apps/exercises/utils/umto_import_router.py`
- Modify: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write failing test**

```python
from apps.exercises.utils.umto_import_router import musicxml_score_to_chord_events


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::ChordalMusicXMLConversionTests -v`

Expected: FAIL with missing `musicxml_score_to_chord_events`.

- [ ] **Step 3: Implement conversion**

Flatten notes and chords from all parts, group by absolute offset, preserve source order, convert pitches with music21 `.midi`, and use `pitch.nameWithOctave` for spelling.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py::ChordalMusicXMLConversionTests -v`

Expected: PASS.

## Task 5: Import Command Routing

**Files:**
- Modify: `apps/exercises/management/commands/import_musicxml.py`
- Modify: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write failing unit tests for command helper**

Add pure helper tests that route a voices score to existing CIR data and a chordal score to a chordal payload. Keep DB writes out of this test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py -v`

Expected: FAIL on missing command helper.

- [ ] **Step 3: Implement command helper**

Add `_build_import_payload_for_score(score, *, title, harmony_key, start_measure, end_measure, complexity)` in `import_musicxml.py`. It returns a payload dict and route decision. Voices route uses existing `m21_to_cir`; chordal route uses `musicxml_score_to_chord_events` plus `build_chordal_umto_payload`.

- [ ] **Step 4: Wire `process_file`**

Use the helper in `process_file`; save voices through `save_umto_exercise`; save chordal by creating `Exercise(data=payload)` only if the payload is UMTO and passes model guard.

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest apps/exercises/tests/test_umto_import_router.py -v`

Expected: PASS.

## Task 6: Legacy CSV Command

**Files:**
- Create: `apps/exercises/management/commands/import_legacy_chord_csv.py`
- Modify: `docs/management_commands.md`

- [ ] **Step 1: Add management command**

The command accepts `path`, `--author`, `--public`, `--dry-run`, and `--limit`. It reports importable chord rows and writes UMTO rows only without `--dry-run`.

- [ ] **Step 2: Document command**

Add an entry under exercise import commands in `docs/management_commands.md`.

- [ ] **Step 3: Smoke test dry-run**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py import_legacy_chord_csv exercises_2026-04-03.csv --author admin@example.com --dry-run --limit 3`

Expected: reports three chordal UMTO candidates or a clear author-not-found message after parsing succeeds.

## Task 7: Docs and Verification

**Files:**
- Modify: `docs/UMTO_GUIDE.md`

- [ ] **Step 1: Document routing**

Add a section describing `voices` vs `chordal` import routing and the legacy CSV command.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python3 -m pytest apps/exercises/tests/test_umto_import_router.py apps/exercises/tests/test_chordal_umto.py -v
node lab/static/js/src/models/chordal_problems_logic.test.js
git diff --check
```

Expected: focused tests pass and diff check is clean.

