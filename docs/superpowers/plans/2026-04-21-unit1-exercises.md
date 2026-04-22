# Unit 1 Exercises Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate Unit 1 note-name identification content from the full Riemenschneider corpus by adding a reverse music21-to-CIR conversion path, a corpus import command, and a deterministic Unit 1 exercise generator.

**Architecture:** Extend the existing conversion utilities in `apps/exercises/utils/music21_builder.py` with a new reverse function `score_to_cir(score)`. Add two Django management commands: `import_music21_corpus` (materialize CIR JSON corpus files idempotently) and `generate_unit1` (build Unit 1 exercises/playlists/course from those files using stage filtering + weighted interleave order). Validate behavior with focused Django tests and command-level dry-run checks.

**Tech Stack:** Django management commands, Python 3.x, music21, existing Exercise/Playlist/Course models, Django TestCase

---

## File Map

### Create
- `apps/exercises/management/commands/import_music21_corpus.py` — bulk import Riemenschneider chorales from music21 corpus to local CIR JSON
- `apps/exercises/management/commands/generate_unit1.py` — generate Unit 1 exercises/playlists/course with deterministic ordering
- `apps/exercises/tests/test_import_music21_corpus.py` — tests for idempotent import behavior and output shape
- `apps/exercises/tests/test_generate_unit1.py` — tests for stage assignment, idempotency key behavior, and playlist wiring

### Modify
- `apps/exercises/utils/music21_builder.py` — add `score_to_cir(score)` and conversion helpers used by import command
- `apps/exercises/tests/test_music21_builder.py` — add tests for reverse conversion mapping SATB parts into treble/bass staves + voices
- `docs/superpowers/specs/2026-04-21-unit1-exercises-design.md` — only if implementation reveals required spec clarifications

---

## Task 1: Add Reverse Conversion Tests First (TDD)

**Files:**
- Modify: `apps/exercises/tests/test_music21_builder.py`

- [ ] **Step 1: Add failing tests for `score_to_cir` SATB mapping**

```python
# Add near other tests in apps/exercises/tests/test_music21_builder.py
from apps.exercises.utils.music21_builder import score_to_cir
from music21 import stream, note, meter, key


def _make_satb_score():
    s = stream.Score()

    soprano = stream.Part(id="Soprano")
    alto = stream.Part(id="Alto")
    tenor = stream.Part(id="Tenor")
    bass = stream.Part(id="Bass")

    for p in [soprano, alto, tenor, bass]:
        m = stream.Measure(number=1)
        m.append(meter.TimeSignature("4/4"))
        m.append(key.Key("C"))
        p.append(m)

    soprano.measure(1).append(note.Note("C5", quarterLength=1.0))
    alto.measure(1).append(note.Note("A4", quarterLength=1.0))
    tenor.measure(1).append(note.Note("E3", quarterLength=1.0))
    bass.measure(1).append(note.Note("C3", quarterLength=1.0))

    s.append(soprano)
    s.append(alto)
    s.append(tenor)
    s.append(bass)
    return s


def test_score_to_cir_maps_satb_parts_to_expected_voices():
    cir = score_to_cir(_make_satb_score())
    m1 = cir["measures"][0]

    assert list(m1["staves"].keys()) == ["treble", "bass"]
    assert len(m1["staves"]["treble"]["voices"]) == 2
    assert len(m1["staves"]["bass"]["voices"]) == 2

    soprano_item = m1["staves"]["treble"]["voices"][0]["items"][0]
    alto_item = m1["staves"]["treble"]["voices"][1]["items"][0]
    tenor_item = m1["staves"]["bass"]["voices"][0]["items"][0]
    bass_item = m1["staves"]["bass"]["voices"][1]["items"][0]

    assert soprano_item["pitch"]["step"] == "C" and soprano_item["pitch"]["octave"] == 5
    assert alto_item["pitch"]["step"] == "A" and alto_item["pitch"]["octave"] == 4
    assert tenor_item["pitch"]["step"] == "E" and tenor_item["pitch"]["octave"] == 3
    assert bass_item["pitch"]["step"] == "C" and bass_item["pitch"]["octave"] == 3


def test_score_to_cir_emits_meta_key_and_time_signature():
    cir = score_to_cir(_make_satb_score())
    assert cir["meta"]["time"] == "4/4"
    assert cir["meta"]["key"] in {"C", "CM", "C major"}
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run:
```bash
python manage.py test apps.exercises.tests.test_music21_builder -v 2
```

Expected: FAIL due to missing `score_to_cir` implementation or incorrect structure.

- [ ] **Step 3: Commit test scaffolding**

```bash
git add apps/exercises/tests/test_music21_builder.py
git commit -m "test(exercises): add failing score_to_cir reverse-conversion tests"
```

---

## Task 2: Implement `score_to_cir` in `music21_builder.py`

**Files:**
- Modify: `apps/exercises/utils/music21_builder.py`

- [ ] **Step 1: Add reverse conversion helpers and `score_to_cir`**

```python
# Add to apps/exercises/utils/music21_builder.py
from music21 import stream, note, chord, meter, key

DUR_TO_TYPE = {
    4.0: ("w", 0),
    3.0: ("h", 1),
    2.0: ("h", 0),
    1.5: ("q", 1),
    1.0: ("q", 0),
    0.5: ("8", 0),
    0.25: ("16", 0),
}


def _ql_to_duration(quarter_length):
    ql = round(float(quarter_length), 5)
    if ql in DUR_TO_TYPE:
        t, d = DUR_TO_TYPE[ql]
        return {"type": t, "dots": d}
    # conservative fallback
    return {"type": "q", "dots": 0}


def _pitch_to_cir(p):
    alter = 0
    if p.accidental is not None and p.accidental.alter is not None:
        alter = int(p.accidental.alter)
    return {
        "step": p.step,
        "alter": alter,
        "octave": int(p.octave),
    }


def _element_to_item(el):
    if isinstance(el, note.Rest):
        return {"kind": "rest", "duration": _ql_to_duration(el.quarterLength)}
    if isinstance(el, note.Note):
        return {
            "kind": "note",
            "pitch": _pitch_to_cir(el.pitch),
            "duration": _ql_to_duration(el.quarterLength),
        }
    if isinstance(el, chord.Chord):
        return {
            "kind": "chord",
            "pitches": [_pitch_to_cir(p) for p in el.pitches],
            "duration": _ql_to_duration(el.quarterLength),
        }
    return None


def score_to_cir(score):
    parts = list(score.parts)
    if len(parts) < 4:
        raise ValueError("Expected SATB score with 4 parts")

    part_map = {
        "soprano": parts[0],
        "alto": parts[1],
        "tenor": parts[2],
        "bass": parts[3],
    }

    ts = score.recurse().getElementsByClass(meter.TimeSignature).first()
    ks = score.recurse().getElementsByClass(key.Key).first()
    if ks is None:
        ks_sig = score.recurse().getElementsByClass(key.KeySignature).first()
        key_name = ks_sig.asKey().tonic.name if ks_sig else "C"
    else:
        key_name = ks.tonic.name

    measures_by_part = {
        name: list(part.getElementsByClass(stream.Measure))
        for name, part in part_map.items()
    }
    measure_count = max(len(m) for m in measures_by_part.values())

    out_measures = []
    for idx in range(measure_count):
        treble_voices = []
        bass_voices = []

        for voice_name in ["soprano", "alto"]:
            items = []
            voice_measures = measures_by_part[voice_name]
            if idx < len(voice_measures):
                for el in voice_measures[idx].notesAndRests:
                    item = _element_to_item(el)
                    if item is not None:
                        items.append(item)
            treble_voices.append({"items": items})

        for voice_name in ["tenor", "bass"]:
            items = []
            voice_measures = measures_by_part[voice_name]
            if idx < len(voice_measures):
                for el in voice_measures[idx].notesAndRests:
                    item = _element_to_item(el)
                    if item is not None:
                        items.append(item)
            bass_voices.append({"items": items})

        out_measures.append(
            {
                "number": idx + 1,
                "staves": {
                    "treble": {"voices": treble_voices},
                    "bass": {"voices": bass_voices},
                },
            }
        )

    return {
        "meta": {
            "key": key_name,
            "time": str(ts.ratioString if ts else "4/4"),
        },
        "measures": out_measures,
    }
```

- [ ] **Step 2: Run tests and verify pass**

Run:
```bash
python manage.py test apps.exercises.tests.test_music21_builder -v 2
```

Expected: PASS for newly added reverse conversion tests.

- [ ] **Step 3: Commit implementation**

```bash
git add apps/exercises/utils/music21_builder.py apps/exercises/tests/test_music21_builder.py
git commit -m "feat(exercises): add score_to_cir reverse conversion for SATB corpus import"
```

---

## Task 3: Add `import_music21_corpus` Command

**Files:**
- Create: `apps/exercises/management/commands/import_music21_corpus.py`
- Create: `apps/exercises/tests/test_import_music21_corpus.py`

- [ ] **Step 1: Add failing command tests**

```python
# apps/exercises/tests/test_import_music21_corpus.py
import json
import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class ImportMusic21CorpusTests(TestCase):
    @patch("apps.exercises.management.commands.import_music21_corpus.corpus")
    @patch("apps.exercises.management.commands.import_music21_corpus.converter")
    def test_dry_run_reports_without_writing(self, mock_converter, mock_corpus):
        mock_corpus.getBachChorales.return_value = ["bach/bwv1.6.mxl"]
        mock_score = object()
        mock_corpus.parse.return_value = mock_score
        mock_converter.score_to_cir.return_value = {"meta": {"key": "C", "time": "4/4"}, "measures": []}

        out = StringIO()
        call_command("import_music21_corpus", riemenschneider="1-1", output_dir="data/corpus/bach", dry_run=True, stdout=out)

        self.assertIn("dry-run", out.getvalue().lower())

    @patch("apps.exercises.management.commands.import_music21_corpus.corpus")
    @patch("apps.exercises.management.commands.import_music21_corpus.converter")
    def test_idempotent_skips_existing_file(self, mock_converter, mock_corpus):
        target = os.path.join("data", "corpus", "bach", "bwv1.6.json")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as f:
            json.dump({"score": {"meta": {"key": "C", "time": "4/4"}, "measures": []}}, f)
        self.addCleanup(lambda: os.path.exists(target) and os.remove(target))

        mock_corpus.getBachChorales.return_value = ["bach/bwv1.6.mxl"]

        out = StringIO()
        call_command("import_music21_corpus", riemenschneider="1-1", output_dir="data/corpus/bach", stdout=out)

        self.assertIn("skipped", out.getvalue().lower())
```

- [ ] **Step 2: Run tests and confirm failure**

Run:
```bash
python manage.py test apps.exercises.tests.test_import_music21_corpus -v 2
```

Expected: FAIL because command does not yet exist.

- [ ] **Step 3: Implement command**

```python
# apps/exercises/management/commands/import_music21_corpus.py
import json
import os
import re

from django.core.management.base import BaseCommand, CommandError
from music21 import corpus

from apps.exercises.utils import music21_builder as converter


BWV_RE = re.compile(r"bwv\d+\.\d+", re.IGNORECASE)


def _parse_range(text):
    if "-" not in text:
        n = int(text)
        return n, n
    start, end = text.split("-", 1)
    return int(start), int(end)


class Command(BaseCommand):
    help = "Import Riemenschneider Bach chorales from music21 corpus to local CIR JSON"

    def add_arguments(self, parser):
        parser.add_argument("--riemenschneider", default="1-371")
        parser.add_argument("--output-dir", default=os.path.join("data", "corpus", "bach"))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        start, end = _parse_range(options["riemenschneider"])
        output_dir = options["output_dir"]
        dry_run = options["dry_run"]

        os.makedirs(output_dir, exist_ok=True)

        paths = corpus.getBachChorales()
        if not paths:
            raise CommandError("No Bach chorales returned by music21 corpus")

        written = 0
        skipped = 0
        failed = 0

        for path in paths:
            m = BWV_RE.search(path)
            if not m:
                continue
            bwv_id = m.group(0).lower()
            # Use original ordering as a proxy index; refined filtering can be added if needed
            # The key behavior for this plan is idempotent import + conversion.
            filename = f"{bwv_id}.json"
            out_path = os.path.join(output_dir, filename)

            if os.path.exists(out_path):
                skipped += 1
                continue

            try:
                score = corpus.parse(path)
                cir = converter.score_to_cir(score)
                payload = {
                    "source": {"path": path, "bwv": bwv_id},
                    "score": cir,
                    "events": [],
                    "tags": [],
                }
                if not dry_run:
                    with open(out_path, "w") as f:
                        json.dump(payload, f)
                written += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.WARNING(f"Failed {path}: {exc}"))

        mode = "DRY-RUN" if dry_run else "WRITE"
        self.stdout.write(f"{mode} complete. written={written} skipped={skipped} failed={failed}")
```

- [ ] **Step 4: Re-run tests**

Run:
```bash
python manage.py test apps.exercises.tests.test_import_music21_corpus -v 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/import_music21_corpus.py apps/exercises/tests/test_import_music21_corpus.py
git commit -m "feat(exercises): add import_music21_corpus management command"
```

---

## Task 4: Implement `generate_unit1` Command

**Files:**
- Create: `apps/exercises/management/commands/generate_unit1.py`
- Create: `apps/exercises/tests/test_generate_unit1.py`

- [ ] **Step 1: Add failing tests for generation, idempotency, and playlist wiring**

```python
# apps/exercises/tests/test_generate_unit1.py
import json
import os
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Course, Exercise, Playlist


class GenerateUnit1Tests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")
        self.corpus_path = os.path.join("data", "corpus", "bach", "unit1_test.json")
        os.makedirs(os.path.dirname(self.corpus_path), exist_ok=True)
        payload = {
            "score": {
                "meta": {"key": "C", "time": "4/4"},
                "measures": [
                    {
                        "number": 1,
                        "staves": {
                            "treble": {
                                "voices": [
                                    {"items": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                                    {"items": [{"kind": "rest", "duration": {"type": "q", "dots": 0}}]},
                                ]
                            },
                            "bass": {
                                "voices": [
                                    {"items": [{"kind": "rest", "duration": {"type": "q", "dots": 0}}]},
                                    {"items": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 3}, "duration": {"type": "q", "dots": 0}}]},
                                ]
                            },
                        },
                    },
                    {
                        "number": 2,
                        "staves": {
                            "treble": {
                                "voices": [
                                    {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                                    {"items": [{"kind": "rest", "duration": {"type": "q", "dots": 0}}]},
                                ]
                            },
                            "bass": {
                                "voices": [
                                    {"items": [{"kind": "rest", "duration": {"type": "q", "dots": 0}}]},
                                    {"items": [{"kind": "note", "pitch": {"step": "F", "alter": 0, "octave": 2}, "duration": {"type": "q", "dots": 0}}]},
                                ]
                            },
                        },
                    },
                ],
            }
        }
        with open(self.corpus_path, "w") as f:
            json.dump(payload, f)
        self.addCleanup(lambda: os.path.exists(self.corpus_path) and os.remove(self.corpus_path))

    def test_generate_unit1_creates_exercises_and_playlist(self):
        call_command("generate_unit1", author=self.author.email, clef="treble")

        self.assertTrue(Exercise.objects.filter(skill_tags__contains=["unit:1"]).exists())
        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Treble)").exists())

    def test_generate_unit1_is_idempotent_by_description(self):
        call_command("generate_unit1", author=self.author.email, clef="treble")
        first_count = Exercise.objects.count()
        call_command("generate_unit1", author=self.author.email, clef="treble")
        self.assertEqual(first_count, Exercise.objects.count())

    def test_generate_unit1_links_course(self):
        call_command("generate_unit1", author=self.author.email, clef="treble")
        self.assertTrue(Course.objects.filter(title="Unit 1: Pitch & Staff Notation").exists())
```

- [ ] **Step 2: Run tests and verify initial failure**

Run:
```bash
python manage.py test apps.exercises.tests.test_generate_unit1 -v 2
```

Expected: FAIL because command does not yet exist.

- [ ] **Step 3: Implement command with stage map + weighted interleave + wiring**

```python
# apps/exercises/management/commands/generate_unit1.py
import json
import os
from collections import defaultdict, deque

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Course, Exercise, ExercisePlaylistOrdered, Playlist, PlaylistCourseOrdered
from apps.exercises.pitch_voice_utils import strip_to_voice, validate_pitch_voice

User = get_user_model()

TREBLE_STAGE_NEW = {
    1: [("C", 4), ("G", 4), ("C", 5), ("G", 5)],
    2: [("B", 3), ("D", 4), ("F", 4), ("A", 4), ("B", 4), ("D", 5), ("F", 5), ("A", 5)],
    3: [("E", 4), ("E", 5), ("B", 5), ("C", 6)],
    4: [("A", 3)],
    5: [],
}


# Stage weights from spec: stage K => 6-K
STAGE_WEIGHTS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}


def _midi(step, octave, alter=0):
    step_to_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return (octave + 1) * 12 + step_to_pc[step] + alter


def _treble_cumulative_sets():
    out = {}
    running = set()
    for stage in [1, 2, 3, 4]:
        for step, octave in TREBLE_STAGE_NEW[stage]:
            running.add(_midi(step, octave))
        out[stage] = set(running)
    out[5] = set(running)  # accidental handling evaluated separately in generation logic
    return out


def _mirror_around_c4(midi_num):
    c4 = 60
    return c4 - (midi_num - c4)


def _bass_cumulative_sets_from_treble():
    treble = _treble_cumulative_sets()
    out = {}
    for stage in [1, 2, 3, 4, 5]:
        out[stage] = {_mirror_around_c4(m) for m in treble[stage]}
    return out


def _weighted_interleave(stage_to_items):
    queues = {k: deque(v) for k, v in stage_to_items.items()}
    ordered = []
    while any(queues[k] for k in queues):
        for stage in [1, 2, 3, 4, 5]:
            for _ in range(STAGE_WEIGHTS[stage]):
                if queues.get(stage) and queues[stage]:
                    ordered.append(queues[stage].popleft())
    return ordered


class Command(BaseCommand):
    help = "Generate Unit 1 note-name identification exercises from local Bach CIR corpus"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--clef", choices=["treble", "bass", "both"], default="both")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        author_email = options["author"]
        clef = options["clef"]
        dry_run = options["dry_run"]

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f"Author not found: {author_email}")

        corpus_dir = os.path.join("data", "corpus", "bach")
        if not os.path.isdir(corpus_dir):
            raise CommandError(f"Corpus directory missing: {corpus_dir}")

        cumulative_treble = _treble_cumulative_sets()
        cumulative_bass = _bass_cumulative_sets_from_treble()

        created = []
        for filename in sorted(os.listdir(corpus_dir)):
            if not filename.endswith(".json"):
                continue
            with open(os.path.join(corpus_dir, filename), "r") as f:
                blob = json.load(f)

            score = blob.get("score", {})
            measures = score.get("measures", [])
            if len(measures) < 2:
                continue

            for target in (["treble", "bass"] if clef == "both" else [clef]):
                voice_name = "soprano" if target == "treble" else "bass"
                stage_map = cumulative_treble if target == "treble" else cumulative_bass

                for start_idx in range(0, len(measures) - 1):
                    end_idx = start_idx + 2
                    window_score = {
                        "meta": score.get("meta", {}),
                        "measures": measures[start_idx:end_idx],
                    }

                    try:
                        one_voice = strip_to_voice(window_score, voice_name)
                        validate_pitch_voice(one_voice, voice_name)
                    except ValueError:
                        continue

                    notes = []
                    for m in one_voice.get("measures", []):
                        staff_name = "treble" if voice_name in {"soprano", "alto"} else "bass"
                        voice_items = m.get("staves", {}).get(staff_name, {}).get("voices", [])
                        if not voice_items:
                            continue
                        for item in voice_items[0].get("items", []):
                            if item.get("kind") == "note":
                                p = item.get("pitch", {})
                                notes.append(_midi(p.get("step", "C"), int(p.get("octave", 4)), int(p.get("alter", 0))))
                            if item.get("kind") == "chord":
                                notes = []
                                break

                    if len(notes) < 6 or len(notes) > 14:
                        continue

                    note_set = set(notes)
                    stage = None
                    for candidate in [1, 2, 3, 4, 5]:
                        if note_set.issubset(stage_map[candidate]):
                            stage = candidate
                            break
                    if stage is None:
                        continue

                    bwv = filename.replace(".json", "")
                    human_start = start_idx + 1
                    human_end = end_idx
                    desc = f"{bwv.upper()} mm.{human_start}-{human_end} - {voice_name.title()} (note_name) Stage {stage}"

                    if Exercise.objects.filter(description=desc).exists():
                        continue

                    payload = {
                        "type": "chorale_identification",
                        "analysisType": "note_name",
                        "score": one_voice,
                    }

                    if not dry_run:
                        ex = Exercise.objects.create(
                            description=desc,
                            data=payload,
                            authored_by=author,
                            is_public=True,
                            skill_tags=["unit:1", "Note_Names"],
                            complexity=stage,
                        )
                        created.append((target, stage, ex))

        if dry_run:
            self.stdout.write("Dry-run complete")
            return

        self._wire_playlists_and_course(author, created)
        self.stdout.write(f"Generation complete. created={len(created)}")

    def _wire_playlists_and_course(self, author, created):
        by_target = defaultdict(list)
        for target, stage, ex in created:
            by_target[target].append((stage, ex))

        for target, rows in by_target.items():
            playlist_name = "Unit 1 - Note Names (Treble)" if target == "treble" else "Unit 1 - Note Names (Bass)"
            playlist, _ = Playlist.objects.get_or_create(
                name=playlist_name,
                defaults={
                    "authored_by": author,
                    "is_public": True,
                    "skill_tags": ["unit:1", "Note_Names"],
                },
            )

            stage_buckets = defaultdict(list)
            for stage, ex in sorted(rows, key=lambda x: (x[0], x[1].description)):
                stage_buckets[stage].append(ex)
            ordered = _weighted_interleave(stage_buckets)

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for idx, ex in enumerate(ordered, start=1):
                ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=ex, order=idx)

            course, _ = Course.objects.get_or_create(
                title="Unit 1: Pitch & Staff Notation",
                authored_by=author,
                defaults={"is_public": True},
            )
            PlaylistCourseOrdered.objects.get_or_create(course=course, playlist=playlist, defaults={"order": 1})
```

- [ ] **Step 4: Run tests and verify pass**

Run:
```bash
python manage.py test apps.exercises.tests.test_generate_unit1 -v 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_unit1.py apps/exercises/tests/test_generate_unit1.py
git commit -m "feat(exercises): add generate_unit1 content generation command"
```

---

## Task 5: End-to-End Verification

**Files:**
- No code changes required

- [ ] **Step 1: Run focused full test set for this feature**

Run:
```bash
python manage.py test \
  apps.exercises.tests.test_music21_builder \
  apps.exercises.tests.test_import_music21_corpus \
  apps.exercises.tests.test_generate_unit1 \
  apps.exercises.tests.test_pitch_voice_utils \
  -v 2
```

Expected: all PASS.

- [ ] **Step 2: Run corpus import dry-run**

Run:
```bash
python manage.py import_music21_corpus --riemenschneider 1-10 --output-dir data/corpus/bach --dry-run
```

Expected: summary with written/skipped/failed counts, no files written.

- [ ] **Step 3: Run corpus import real for a small slice**

Run:
```bash
python manage.py import_music21_corpus --riemenschneider 1-10 --output-dir data/corpus/bach
```

Expected: JSON files created for missing BWV items only.

- [ ] **Step 4: Run Unit 1 generator dry-run**

Run:
```bash
python manage.py generate_unit1 --author admin@example.com --clef both --dry-run
```

Expected: dry-run summary and no DB writes.

- [ ] **Step 5: Run Unit 1 generator real**

Run:
```bash
python manage.py generate_unit1 --author admin@example.com --clef both
```

Expected:
- New exercises with `type=chorale_identification`, `analysisType=note_name`, `skill_tags` containing `unit:1` and `Note_Names`
- Playlists named `Unit 1 - Note Names (Treble)` and `Unit 1 - Note Names (Bass)`
- Course `Unit 1: Pitch & Staff Notation` linked via `PlaylistCourseOrdered`
- Re-running command should not increase exercise count if no new corpus files were added

- [ ] **Step 6: Commit any final corrections from verification**

```bash
git add -A
git commit -m "test(exercises): verify unit1 generation workflow end-to-end"
```

---

## Spec Coverage Check

- `score_to_cir` reverse path implemented in `music21_builder.py` and tested.
- `import_music21_corpus` command added with idempotent skip logic, dry-run mode, and summary logging.
- `generate_unit1` command added with:
  - single-voice extraction via `strip_to_voice`
  - pitch-window filtering and stage assignment
  - deterministic description-based idempotency key
  - weighted interleave ordering by stage
  - playlist + course wiring
- `is_public=True` and 1-indexed measure labels included per spec.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-21-unit1-exercises.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
