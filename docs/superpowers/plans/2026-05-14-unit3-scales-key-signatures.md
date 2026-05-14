# Unit 3 — Scales & Key Signatures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two new exercise types for Unit 3 (Scales & Key Signatures) in HarmonyLab: (1) identify a key from its rendered key signature (text input — student types e.g. "D" or "Bb"), and (2) play a major scale from the MusicXML corpus (MIDI playback) — both using the UMTO framework with configurable difficulty levels.

> **Note on "spell key signature" type:** The click-on-staff approach (discrete line/space mouse tracking) is too complex in Artusi's current rendering model. Replaced by keyboard text input: student types the accidental names or the key name. This can be added as a future exercise type once the staff-click UI is available.

**Architecture:**
- New exercise type `umto_key_signature` (symbolic, no score) for the identify-key exercise — modelled after `umto_symbolic_meter`. The frontend receives a `problems` array; each problem shows a rendered key signature and asks the student to type the key name.
- New management command `generate_unit3_key_sig_exercises.py` generates the identify-key exercise using a manifest approach (same pattern as Unit 2 meter).
- Scale play exercises import the existing `piano-major-scales-fingerings.mxl` via `import_musicxml.py` (already works), tagged with `unit:3` skill tags and grouped into a playlist per difficulty level (≤3 accidentals, ≤5, all 15 keys).

**Tech Stack:** Python/Django management commands, music21, UMTO/Pydantic, VexFlow (key signature rendering in JS), existing `save_umto_symbolic_exercise`-style factory pattern.

---

## File Map

| Status | Path | Purpose |
|--------|------|---------|
| **Create** | `apps/exercises/key_signature_problems.py` | Pure Python: key data table + `build_key_sig_problem_set()` |
| **Create** | `apps/exercises/management/commands/generate_unit3_key_sig_exercises.py` | Management command: create identify-key exercise + playlist |
| **Create** | `apps/exercises/management/commands/generate_unit3_scale_exercises.py` | Management command: import scale MusicXML per level, tag + playlist |
| **Modify** | `apps/exercises/umto_factory.py` | Add `save_umto_key_sig_exercise()` factory function |
| **Modify** | `lab/static/js/src/models/exercise_definition.js` | Recognise `umto_key_signature` type; `isKeySignatureExercise()` |
| **Modify** | `lab/static/js/src/components/app/exercise.js` | Route `umto_key_signature` to key-sig problem renderer |
| **Create** | `lab/static/js/src/models/key_sig_exercise.js` | JS: render VexFlow key sig + text input grading per problem |
| **Modify** | `apps/exercises/tests/test_key_sig_exercise.py` | Python unit tests for `build_key_sig_problem_set()` |
| **Create** | `lab/static/js/src/models/key_sig_exercise.test.js` | JS unit tests for grading / answer normalisation |

---

## Task 1: Key data module

**Files:**
- Create: `apps/exercises/key_signature_problems.py`
- Test: `apps/exercises/tests/test_key_sig_exercise.py`

All 15 major keys with their accidental count, display name, accepted answer strings, and level.

- [ ] **Step 1: Write the failing test**

```python
# apps/exercises/tests/test_key_sig_exercise.py
import pytest
from apps.exercises.key_signature_problems import (
    KEY_TABLE,
    build_key_sig_problem_set,
    LEVEL_ACCIDENTAL_LIMIT,
)

def test_key_table_has_15_keys():
    assert len(KEY_TABLE) == 15

def test_key_table_c_major():
    c = next(k for k in KEY_TABLE if k["key_id"] == "jC_")
    assert c["accidentals"] == 0
    assert c["display_name"] == "C major"
    assert "C" in c["accepted_answers"]

def test_key_table_f_sharp_major():
    fs = next(k for k in KEY_TABLE if k["key_id"] == "jF#")
    assert fs["accidentals"] == 6
    assert "F#" in fs["accepted_answers"]

def test_level_limits():
    assert LEVEL_ACCIDENTAL_LIMIT == {1: 3, 2: 5, 3: 7}

def test_build_problem_set_level1():
    problems = build_key_sig_problem_set(level=1)
    assert all(p["accidentals"] <= 3 for p in problems)
    assert len(problems) == 7  # C, G, D, A, F, Bb, Eb

def test_build_problem_set_level3():
    problems = build_key_sig_problem_set(level=3)
    assert len(problems) == 15

def test_problem_structure():
    problems = build_key_sig_problem_set(level=1)
    p = problems[0]
    assert "prompt" in p
    assert p["prompt"]["kind"] == "key_signature"
    assert "sharps" in p["prompt"] or "flats" in p["prompt"]
    assert "answer" in p
    assert "accepted_answers" in p
    assert "choices" in p
    assert len(p["choices"]) == 4
```

- [ ] **Step 2: Run test — verify fails**

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1
python -m pytest apps/exercises/tests/test_key_sig_exercise.py -v 2>&1 | head -30
```
Expected: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Create `apps/exercises/key_signature_problems.py`**

```python
"""Key signature data and problem-set builder for Unit 3."""

# Ordered by circle of fifths (sharps ascending, then flats ascending).
# key_id uses HarmonyLab internal format: 'j'=major, 'i'=minor; '_' = natural.
KEY_TABLE = [
    {"key_id": "jC_",  "accidentals": 0, "sharps": 0, "flats": 0, "display_name": "C major",  "accepted_answers": ["C"]},
    {"key_id": "jG_",  "accidentals": 1, "sharps": 1, "flats": 0, "display_name": "G major",  "accepted_answers": ["G"]},
    {"key_id": "jD_",  "accidentals": 2, "sharps": 2, "flats": 0, "display_name": "D major",  "accepted_answers": ["D"]},
    {"key_id": "jA_",  "accidentals": 3, "sharps": 3, "flats": 0, "display_name": "A major",  "accepted_answers": ["A"]},
    {"key_id": "jE_",  "accidentals": 4, "sharps": 4, "flats": 0, "display_name": "E major",  "accepted_answers": ["E"]},
    {"key_id": "jB_",  "accidentals": 5, "sharps": 5, "flats": 0, "display_name": "B major",  "accepted_answers": ["B"]},
    {"key_id": "jF#",  "accidentals": 6, "sharps": 6, "flats": 0, "display_name": "F# major", "accepted_answers": ["F#", "Gb"]},
    {"key_id": "jF_",  "accidentals": 1, "sharps": 0, "flats": 1, "display_name": "F major",  "accepted_answers": ["F"]},
    {"key_id": "jBb",  "accidentals": 2, "sharps": 0, "flats": 2, "display_name": "Bb major", "accepted_answers": ["Bb", "A#"]},
    {"key_id": "jEb",  "accidentals": 3, "sharps": 0, "flats": 3, "display_name": "Eb major", "accepted_answers": ["Eb", "D#"]},
    {"key_id": "jAb",  "accidentals": 4, "sharps": 0, "flats": 4, "display_name": "Ab major", "accepted_answers": ["Ab", "G#"]},
    {"key_id": "jDb",  "accidentals": 5, "sharps": 0, "flats": 5, "display_name": "Db major", "accepted_answers": ["Db", "C#"]},
    {"key_id": "jGb",  "accidentals": 6, "sharps": 0, "flats": 6, "display_name": "Gb major", "accepted_answers": ["Gb", "F#"]},
    {"key_id": "jC#",  "accidentals": 7, "sharps": 7, "flats": 0, "display_name": "C# major", "accepted_answers": ["C#", "Db"]},
    {"key_id": "jCb",  "accidentals": 7, "sharps": 0, "flats": 7, "display_name": "Cb major", "accepted_answers": ["Cb", "B"]},
]

LEVEL_ACCIDENTAL_LIMIT = {1: 3, 2: 5, 3: 7}

# Keys that are enharmonically equivalent — only one appears per level set to
# avoid asking the same key signature twice with different names.
# F#/Gb share 6 accidentals; C#/Db and Cb/B share 7.
_ENHARMONIC_EXCLUDE_ABOVE_LEVEL = {
    "jGb": 2,   # Gb excluded at level ≤2 (F# covers it)
    "jCb": 2,   # Cb excluded at level ≤2 (B covers it)
    "jC#": 2,   # C# excluded at level ≤2 (Db covers it)
}


def _distractor_keys(correct_key_id, all_keys):
    """Return 3 distractor display_names for the multiple-choice set."""
    others = [k for k in all_keys if k["key_id"] != correct_key_id]
    # prefer same accidental count if possible, else random spread
    same_acc = [k for k in others if k["accidentals"] == _get_acc(correct_key_id, all_keys)]
    diff_acc = [k for k in others if k["accidentals"] != _get_acc(correct_key_id, all_keys)]
    pool = (same_acc + diff_acc)[:3]
    return [k["display_name"] for k in pool]


def _get_acc(key_id, table):
    return next(k["accidentals"] for k in table if k["key_id"] == key_id)


def build_key_sig_problem_set(level: int = 1) -> list[dict]:
    """Return a list of problem dicts for the given difficulty level."""
    limit = LEVEL_ACCIDENTAL_LIMIT[level]
    eligible = [
        k for k in KEY_TABLE
        if k["accidentals"] <= limit
        and _ENHARMONIC_EXCLUDE_ABOVE_LEVEL.get(k["key_id"], 99) >= level
    ]
    problems = []
    for k in eligible:
        prompt = {"kind": "key_signature", "sharps": k["sharps"], "flats": k["flats"]}
        distractors = _distractor_keys(k["key_id"], eligible)
        choices = [k["display_name"]] + distractors
        problems.append({
            "prompt": prompt,
            "answer": k["display_name"],
            "accepted_answers": k["accepted_answers"],
            "key_id": k["key_id"],
            "accidentals": k["accidentals"],
            "choices": choices,
        })
    return problems
```

- [ ] **Step 4: Run tests — verify pass**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/key_signature_problems.py apps/exercises/tests/test_key_sig_exercise.py
git commit -m "feat(unit3): add key signature data table and problem-set builder"
```

---

## Task 2: Backend factory for key-sig exercises

**Files:**
- Modify: `apps/exercises/umto_factory.py` (append `save_umto_key_sig_exercise`)

Follows same pattern as `save_umto_symbolic_exercise`.

- [ ] **Step 1: Write failing test** (add to `test_key_sig_exercise.py`)

```python
# append to apps/exercises/tests/test_key_sig_exercise.py
import pytest

@pytest.mark.django_db
def test_save_umto_key_sig_exercise_creates_exercise(django_user_model):
    from apps.exercises.umto_factory import save_umto_key_sig_exercise
    from apps.exercises.key_signature_problems import build_key_sig_problem_set

    author = django_user_model.objects.create_user(
        email="test@example.com", password="x", username="test"
    )
    problems = build_key_sig_problem_set(level=1)
    ex = save_umto_key_sig_exercise(
        description="Unit 3 Key Sig Level 1",
        author=author,
        problems=problems,
        level=1,
        is_public=False,
    )
    assert ex.pk is not None
    assert ex.data["type"] == "umto_key_signature"
    assert ex.data["analysisType"] == "unit3_key_signature"
    assert len(ex.data["problems"]) == 7
    assert "unit:3" in ex.skill_tags
```

- [ ] **Step 2: Run — verify fails**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py::test_save_umto_key_sig_exercise_creates_exercise -v
```
Expected: `ImportError` on `save_umto_key_sig_exercise`.

- [ ] **Step 3: Add `save_umto_key_sig_exercise` to `apps/exercises/umto_factory.py`**

Append after `save_umto_barline_exercise`:

```python
def save_umto_key_sig_exercise(
    *,
    description: str,
    author,
    problems: list[dict],
    level: int = 1,
    is_public: bool = True,
    overwrite: bool = False,
) -> "Exercise":
    from apps.exercises.models import Exercise

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=f"Unit 3 Key Signatures — Level {level}",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=3,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="text",
            unit=3,
        ),
        voices=Voices(),
        analysis=[],
        grading=[],
    )

    skill_tags = ["unit:3", "unit:3_key_signature"]

    payload = {
        "type": "umto_key_signature",
        "isUMTO": True,
        "mode": InteractionMode.IDENTIFICATION.value,
        "analysisType": "unit3_key_signature",
        "inputMode": "text",
        "staffDistribution": "none",
        "complexity_score": 3,
        "level": level,
        "key": "C",
        "meter": "4/4",
        "clef": "treble",
        "introText": f"Identify the following key signatures. Level {level}.",
        "reviewText": "Well done!",
        "allowed_answers": [],
        "problems": problems,
        "score": {
            "meta": {"key": "C", "time": "4/4", "clef": "treble", "staffDistribution": "none"},
            "measures": [],
            "umto": umto.model_dump(mode="json"),
        },
        "grading": [],
    }

    UMTO.model_validate(payload["score"]["umto"])

    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

    if ex is None:
        ex = Exercise(
            description=description,
            data=payload,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags,
            complexity=3,
        )
        ex.save()
    else:
        ex.data = payload
        ex.is_public = is_public
        ex.skill_tags = skill_tags
        ex.save(update_fields=["data", "is_public", "skill_tags"])

    ex.data["exerciseId"] = ex.id
    ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.save(update_fields=["data"])
    return ex
```

- [ ] **Step 4: Run test — verify passes**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_key_sig_exercise.py
git commit -m "feat(unit3): add save_umto_key_sig_exercise factory"
```

---

## Task 3: Management command — identify key exercises

**Files:**
- Create: `apps/exercises/management/commands/generate_unit3_key_sig_exercises.py`

Creates 3 exercises (one per level) and one playlist per level.

- [ ] **Step 1: Write the failing test**

```python
# append to apps/exercises/tests/test_key_sig_exercise.py

@pytest.mark.django_db
def test_generate_unit3_command_creates_exercises(django_user_model):
    from django.core.management import call_command
    from apps.exercises.models import Exercise, Playlist

    author = django_user_model.objects.create_user(
        email="cmd@example.com", password="x", username="cmd"
    )
    call_command("generate_unit3_key_sig_exercises", author="cmd@example.com")

    exercises = Exercise.objects.filter(description__startswith="Unit 3 Key Sig")
    assert exercises.count() == 3  # levels 1, 2, 3

    playlists = Playlist.objects.filter(name__startswith="Unit 3 — Key Signatures")
    assert playlists.count() == 3
```

- [ ] **Step 2: Run — verify fails**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py::test_generate_unit3_command_creates_exercises -v
```
Expected: `CommandError` or `No such command`.

- [ ] **Step 3: Create `apps/exercises/management/commands/generate_unit3_key_sig_exercises.py`**

```python
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.key_signature_problems import build_key_sig_problem_set
from apps.exercises.umto_factory import save_umto_key_sig_exercise

User = get_user_model()

LEVEL_DESCRIPTIONS = {
    1: "Major keys up to 3 accidentals",
    2: "Major keys up to 5 accidentals",
    3: "All major keys",
}


class Command(BaseCommand):
    help = "Create Unit 3 key signature identification exercises (3 difficulty levels)"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        for level in [1, 2, 3]:
            desc = f"Unit 3 Key Sig — Identify, Level {level}"
            problems = build_key_sig_problem_set(level=level)

            exercise = save_umto_key_sig_exercise(
                description=desc,
                author=author,
                problems=problems,
                level=level,
                is_public=options["public"],
                overwrite=options["overwrite"],
            )

            playlist_name = f"Unit 3 — Key Signatures, Level {level}"
            playlist_skill_tags = ["unit:3", "unit:3_key_signature", f"unit:3_L{level}"]

            playlist, created = Playlist.objects.get_or_create(
                name=playlist_name,
                authored_by=author,
                defaults=dict(
                    is_dynamic=False,
                    is_adaptive=False,
                    is_public=options["public"],
                    skill_tags=playlist_skill_tags,
                ),
            )
            if not created:
                playlist.skill_tags = playlist_skill_tags
                if options["public"]:
                    playlist.is_public = True
                playlist.save()

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist, exercise=exercise, order=1
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Level {level}: exercise {exercise.id} → playlist '{playlist_name}'"
                )
            )
```

- [ ] **Step 4: Run test — verify passes**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_unit3_key_sig_exercises.py \
        apps/exercises/tests/test_key_sig_exercise.py
git commit -m "feat(unit3): add generate_unit3_key_sig_exercises management command"
```

---

## Task 4: Management command — scale play exercises

**Files:**
- Create: `apps/exercises/management/commands/generate_unit3_scale_exercises.py`

Imports scales from `docs/scales-key-signatures/piano-major-scales-fingerings.mxl`, creates one exercise per key per level, tagged `unit:3`, `unit:3_major_scale`, and a playlist per level.

The MusicXML has 15 measures, each a different major key (circle of fifths order: C, F, G, Bb, D, Eb, A, Ab, E, Db, B, Gb, F#, Cb, C#). Measures map to accidental count 0–7.

- [ ] **Step 1: Write the failing test**

```python
# append to apps/exercises/tests/test_key_sig_exercise.py

@pytest.mark.django_db
def test_generate_unit3_scales_command(django_user_model):
    from django.core.management import call_command
    from apps.exercises.models import Exercise, Playlist

    author = django_user_model.objects.create_user(
        email="scale@example.com", password="x", username="scale"
    )
    mxl_path = "docs/scales-key-signatures/piano-major-scales-fingerings.mxl"
    call_command("generate_unit3_scale_exercises", author="scale@example.com", mxl=mxl_path)

    # Level 1 has ≤3 accidentals → 7 keys
    playlist = Playlist.objects.get(name="Unit 3 — Major Scales, Level 1")
    assert playlist.exerciseplaylistordered_set.count() == 7

    # All 3 levels created
    assert Playlist.objects.filter(name__startswith="Unit 3 — Major Scales").count() == 3

    # Exercises are tagged correctly
    ex = Exercise.objects.filter(skill_tags__contains=["unit:3_major_scale"]).first()
    assert ex is not None
    assert ex.data["type"] == "umto_chorale"
```

- [ ] **Step 2: Run — verify fails**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py::test_generate_unit3_scales_command -v
```
Expected: `No such command`.

- [ ] **Step 3: Create `apps/exercises/management/commands/generate_unit3_scale_exercises.py`**

```python
"""Import piano major scales from MusicXML and create Unit 3 play exercises."""
import sys
import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()

# MusicXML measure index → (key_id, accidentals, display_name)
# Order matches piano-major-scales-fingerings.mxl (circle of fifths, alternating)
SCALE_MEASURE_MAP = [
    (0,  "jC_",  0, "C major"),
    (1,  "jF_",  1, "F major"),
    (2,  "jG_",  1, "G major"),
    (3,  "jBb",  2, "Bb major"),
    (4,  "jD_",  2, "D major"),
    (5,  "jEb",  3, "Eb major"),
    (6,  "jA_",  3, "A major"),
    (7,  "jAb",  4, "Ab major"),
    (8,  "jE_",  4, "E major"),
    (9,  "jDb",  5, "Db major"),
    (10, "jB_",  5, "B major"),
    (11, "jGb",  6, "Gb major"),
    (12, "jF#",  6, "F# major"),
    (13, "jCb",  7, "Cb major"),
    (14, "jC#",  7, "C# major"),
]

LEVEL_MAX_ACC = {1: 3, 2: 5, 3: 7}


def _measure_to_cir(measure_treble, measure_bass, key_id, display_name):
    """Convert a single measure's music21 Measure objects to a CIR dict."""
    from music21 import note as m21_note, chord as m21_chord

    def _item(el):
        if isinstance(el, m21_note.Rest):
            return {"kind": "rest", "duration": _dur(el)}
        elif isinstance(el, m21_note.Note):
            return {
                "kind": "note",
                "pitch": {"step": el.pitch.step, "alter": int(el.pitch.alter), "octave": el.pitch.octave},
                "duration": _dur(el),
            }
        elif isinstance(el, m21_chord.Chord):
            return {
                "kind": "note",
                "pitch": {"step": el.pitches[-1].step, "alter": int(el.pitches[-1].alter), "octave": el.pitches[-1].octave},
                "duration": _dur(el),
            }
        return None

    def _dur(el):
        t = el.duration.type
        dots = el.duration.dots
        type_map = {"whole": "w", "half": "h", "quarter": "q", "eighth": "8",
                    "16th": "16", "32nd": "32"}
        return {"type": type_map.get(t, "q"), "dots": dots}

    def _voice_items(m21_measure):
        items = []
        for el in m21_measure.flatten().notesAndRests:
            it = _item(el)
            if it:
                items.append(it)
        return items

    treble_items = _voice_items(measure_treble)
    bass_items = _voice_items(measure_bass)

    return {
        "meta": {"key": display_name, "time": "4/4", "clef": "keyboard"},
        "measures": [{
            "staves": {
                "treble": {"clef": "treble", "voices": [{"items": treble_items, "direction": "auto"}]},
                "bass":   {"clef": "bass",   "voices": [{"items": bass_items,   "direction": "auto"}]},
            }
        }]
    }


class Command(BaseCommand):
    help = "Create Unit 3 major scale play exercises from MusicXML"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument(
            "--mxl",
            default="docs/scales-key-signatures/piano-major-scales-fingerings.mxl",
        )
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        from music21 import converter

        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        mxl_path = options["mxl"]
        if not os.path.exists(mxl_path):
            raise CommandError(f"MusicXML not found: {mxl_path}")

        score = converter.parse(mxl_path)
        treble_part = score.parts[0]
        bass_part   = score.parts[1]

        treble_measures = list(treble_part.getElementsByClass("Measure"))
        bass_measures   = list(bass_part.getElementsByClass("Measure"))

        # Build one exercise per scale
        created_exercises = []
        for m_idx, key_id, n_acc, display_name in SCALE_MEASURE_MAP:
            if m_idx >= len(treble_measures):
                self.stdout.write(self.style.WARNING(f"Missing measure {m_idx}, skipping {display_name}"))
                continue

            cir = _measure_to_cir(treble_measures[m_idx], bass_measures[m_idx], key_id, display_name)
            desc = f"Unit 3 Scale — {display_name}"
            skill_tags = ["unit:3", "unit:3_major_scale"]

            ex = save_umto_exercise(
                description=desc,
                score_data=cir,
                author=author,
                skill_tags=skill_tags,
                complexity=3,
                is_public=options["public"],
                overwrite=options["overwrite"],
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source=f"Play the {display_name} scale on the keyboard.",
                    key=display_name,
                    meter="4/4",
                    clef="keyboard",
                    complexity_score=3,
                    mode=InteractionMode.PLAYBACK,
                    unit=3,
                ),
            )
            created_exercises.append((ex, n_acc, display_name))
            self.stdout.write(f"  Created: {desc} (id={ex.id})")

        # Build playlists per level
        for level, max_acc in LEVEL_MAX_ACC.items():
            playlist_name = f"Unit 3 — Major Scales, Level {level}"
            playlist_tags = ["unit:3", "unit:3_major_scale", f"unit:3_L{level}"]

            playlist, _ = Playlist.objects.get_or_create(
                name=playlist_name,
                authored_by=author,
                defaults=dict(
                    is_dynamic=False,
                    is_adaptive=False,
                    is_public=options["public"],
                    skill_tags=playlist_tags,
                ),
            )
            playlist.skill_tags = playlist_tags
            if options["public"]:
                playlist.is_public = True
            playlist.save()

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            level_exercises = [(ex, n) for ex, n, _ in created_exercises if n <= max_acc]
            for order, (ex, _) in enumerate(level_exercises, start=1):
                ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=ex, order=order)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Level {level}: {len(level_exercises)} scales → playlist '{playlist_name}'"
                )
            )
```

- [ ] **Step 4: Run test — verify passes**

```bash
python -m pytest apps/exercises/tests/test_key_sig_exercise.py -v
```
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_unit3_scale_exercises.py \
        apps/exercises/tests/test_key_sig_exercise.py
git commit -m "feat(unit3): add generate_unit3_scale_exercises management command"
```

---

## Task 5: Frontend — exercise_definition.js recognises `umto_key_signature`

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`

Add `isKeySignatureExercise()` predicate alongside the existing `isSymbolicMeter()` pattern (line ~794).

- [ ] **Step 1: Write failing JS test**

The project uses plain Node `require()` tests (no Jest/describe). Follow the pattern of `symbolic_meter_rendering_logic.test.js`:

```javascript
// lab/static/js/src/models/key_sig_exercise.test.js
"use strict";

var logic = require("./key_sig_exercise_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, "got", actual, "expected", expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "normalizeKeyAnswer capitalises tonic",
  logic.normalizeKeyAnswer("bb"),
  "Bb"
);
assertEqual(
  "normalizeKeyAnswer preserves sharp",
  logic.normalizeKeyAnswer("f#"),
  "F#"
);
assertEqual(
  "checkKeyAnswer accepts exact match",
  logic.checkKeyAnswer("Bb", { accepted_answers: ["Bb", "A#"] }),
  true
);
assertEqual(
  "checkKeyAnswer accepts enharmonic",
  logic.checkKeyAnswer("A#", { accepted_answers: ["Bb", "A#"] }),
  true
);
assertEqual(
  "checkKeyAnswer accepts normalised lowercase",
  logic.checkKeyAnswer("bb", { accepted_answers: ["Bb", "A#"] }),
  true
);
assertEqual(
  "checkKeyAnswer rejects wrong key",
  logic.checkKeyAnswer("Eb", { accepted_answers: ["Bb", "A#"] }),
  false
);
```

- [ ] **Step 2: Run — verify fails**

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1
node lab/static/js/src/models/key_sig_exercise.test.js 2>&1 | head -5
```
Expected: `Cannot find module './key_sig_exercise_logic'`.

- [ ] **Step 3: Add `isKeySignatureExercise()` to `exercise_definition.js`**

Find the block containing `isSymbolicMeter` (around line 794). Add directly after it:

```javascript
    isKeySignatureExercise: function () {
      return this.exercise.type === "umto_key_signature";
    },
```

Also add the type guard in the `build` / initialisation section where `umto_symbolic_meter` is handled, so the definition loads without errors.

- [ ] **Step 4: Run JS tests**

```bash
node lab/static/js/src/models/key_sig_exercise.test.js
```
Expected: all PASS lines.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js \
        lab/static/js/src/models/key_sig_exercise.test.js
git commit -m "feat(unit3): add isKeySignatureExercise() to ExerciseDefinition"
```

---

## Task 6: Frontend renderer — key signature exercise UI

**Files:**
- Create: `lab/static/js/src/models/key_sig_exercise_logic.js` (pure logic, UMD, Node-testable)
- Create: `lab/static/js/src/models/key_sig_exercise.js` (AMD, VexFlow renderer + KeySigExercise driver; wraps logic)
- Modify: `lab/static/js/src/components/app/exercise.js` (route new type)

Split logic from DOM so the logic module can be `require()`d in Node tests (same pattern as `symbolic_meter_rendering_logic.js`).

- [ ] **Step 1: Write failing JS unit test (grading logic only)**

Tests already live in `key_sig_exercise.test.js` from Task 5 (they test `key_sig_exercise_logic`). No new test file needed. Run to confirm they still fail:

```bash
node lab/static/js/src/models/key_sig_exercise.test.js
```
Expected: `Cannot find module './key_sig_exercise_logic'`.

- [ ] **Step 2: Create `lab/static/js/src/models/key_sig_exercise_logic.js`**

UMD wrapper so it works in both AMD (browser) and CommonJS (Node tests):

```javascript
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.KeySigExerciseLogic = factory();
  }
})(this, function () {
  "use strict";

  function normalizeKeyAnswer(raw) {
    var s = (raw || "").trim();
    if (!s) return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function checkKeyAnswer(raw, problem) {
    var norm = normalizeKeyAnswer(raw);
    return (problem.accepted_answers || []).some(function (a) {
      return a === norm;
    });
  }

  return { normalizeKeyAnswer: normalizeKeyAnswer, checkKeyAnswer: checkKeyAnswer };
});
```

- [ ] **Step 3: Run tests — verify pass**

```bash
node lab/static/js/src/models/key_sig_exercise.test.js
```
Expected: all PASS.

- [ ] **Step 4: Create `lab/static/js/src/models/key_sig_exercise.js`**

AMD module (requires VexFlow + jQuery, so not Node-testable). Wraps the logic module and adds DOM rendering + exercise driver:

```javascript
/* global define: false */
define(
  ["models/key_sig_exercise_logic", "vexflow", "jquery"],
  function (logic, Vex, $) {
    "use strict";

    var SHARPS_KEY = ["C", "G", "D", "A", "E", "B", "F#", "C#"];
    var FLATS_KEY  = ["C", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"];

    function renderKeySignatureStaff(container, prompt) {
      $(container).empty();
      var VF = Vex.Flow;
      var renderer = new VF.Renderer(container, VF.Renderer.Backends.SVG);
      renderer.resize(200, 120);
      var context = renderer.getContext();
      var stave = new VF.Stave(10, 20, 160);
      stave.addClef("treble");

      var vexKey;
      if ((prompt.sharps || 0) > 0) {
        vexKey = SHARPS_KEY[prompt.sharps];
      } else if ((prompt.flats || 0) > 0) {
        vexKey = FLATS_KEY[prompt.flats];
      } else {
        vexKey = "C";
      }
      stave.addKeySignature(vexKey);
      stave.setContext(context).draw();
    }

    var KeySigExercise = function (definition, options) {
      this.problems = definition.exercise.problems || [];
      this.index    = 0;
      this.mistakes = 0;
      this.options  = options || {};
    };

    KeySigExercise.prototype = {
      start: function () { this._showProblem(); },

      _showProblem: function () {
        var p = this.problems[this.index];
        if (!p) return;
        if (this.options.staffContainer) {
          renderKeySignatureStaff(this.options.staffContainer, p.prompt);
        }
        if (this.options.inputEl) {
          $(this.options.inputEl).val("").focus();
        }
      },

      submit: function (rawAnswer) {
        var p = this.problems[this.index];
        if (!p) return;
        if (!logic.checkKeyAnswer(rawAnswer, p)) {
          this.mistakes++;
          return { correct: false, message: "Try again." };
        }
        this.index++;
        if (this.index >= this.problems.length) {
          if (this.options.onComplete) {
            this.options.onComplete({ score: this.mistakes === 0 ? 0 : 1 });
          }
        } else {
          if (this.options.onAdvance) {
            this.options.onAdvance({ index: this.index, total: this.problems.length });
          }
          this._showProblem();
        }
        return { correct: true };
      },
    };

    return { KeySigExercise: KeySigExercise };
  }
);
```

- [ ] **Step 5: Wire into `exercise.js`**

Open `lab/static/js/src/components/app/exercise.js`. Find where `umto_symbolic_meter` is routed (grep for `isSymbolicMeterQuestion`). Add an analogous branch directly after it for `umto_key_signature`:

```javascript
} else if (definition.isKeySignatureExercise()) {
  require(["models/key_sig_exercise"], function (KeySigMod) {
    var keySigEx = new KeySigMod.KeySigExercise(definition, {
      staffContainer: self.$el.find(".key-sig-staff-container")[0],
      inputEl: self.$el.find(".key-sig-input")[0],
      onComplete: function (grade) { self._onExerciseComplete(grade); },
      onAdvance: function (info) { self._onKeyExerciseAdvance(info); },
    });
    keySigEx.start();
  });
```

Also search for the Handlebars/Underscore template used by `exercise.js` for the problem area and add the two required DOM elements if they don't already exist:
```html
<div class="key-sig-staff-container"></div>
<input class="key-sig-input" type="text" placeholder="e.g. D or Bb" />
```

- [ ] **Step 6: Run logic tests again to confirm no regression**

```bash
node lab/static/js/src/models/key_sig_exercise.test.js
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/models/key_sig_exercise_logic.js \
        lab/static/js/src/models/key_sig_exercise.js \
        lab/static/js/src/models/key_sig_exercise.test.js \
        lab/static/js/src/components/app/exercise.js
git commit -m "feat(unit3): add key signature exercise renderer and grading"
```

---

## Task 7: Generate content and smoke-test end-to-end

- [ ] **Step 1: Run identify-key exercise generation**

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1
python manage.py generate_unit3_key_sig_exercises \
  --author avnerdorman@gmail.com --public
```
Expected: 3 success lines, each with an exercise ID and playlist name.

- [ ] **Step 2: Run scale exercise generation**

```bash
python manage.py generate_unit3_scale_exercises \
  --author avnerdorman@gmail.com \
  --mxl docs/scales-key-signatures/piano-major-scales-fingerings.mxl \
  --public
```
Expected: 15 "Created" lines, then 3 "Level N: X scales → playlist" lines.

- [ ] **Step 3: Verify in Django shell**

```bash
python manage.py shell -c "
from apps.exercises.models import Exercise, Playlist
ks = Exercise.objects.filter(skill_tags__contains=['unit:3_key_signature'])
sc = Exercise.objects.filter(skill_tags__contains=['unit:3_major_scale'])
pl = Playlist.objects.filter(name__startswith='Unit 3')
print('Key sig exercises:', ks.count())   # expect 3
print('Scale exercises:', sc.count())     # expect 15
print('Playlists:', pl.count())           # expect 6
"
```

- [ ] **Step 4: Load app in browser, navigate to a Unit 3 playlist, play through one key-sig exercise and one scale exercise**

Check:
- Key sig: staff renders with correct sharps/flats, text input accepts correct answer, advances to next problem, completes playlist item.
- Scale: score renders, MIDI input plays scale notes in order, exercise completes.

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -p  # stage only intentional fixes
git commit -m "fix(unit3): smoke-test fixes after end-to-end review"
```

---

## Verification

```bash
# All Python tests
python -m pytest apps/exercises/tests/test_key_sig_exercise.py -v

# All JS tests
node lab/static/js/src/models/key_sig_exercise.test.js

# Content counts
python manage.py shell -c "
from apps.exercises.models import Exercise, Playlist
print('Unit 3 key sig:', Exercise.objects.filter(skill_tags__contains=['unit:3_key_signature']).count())
print('Unit 3 scales:', Exercise.objects.filter(skill_tags__contains=['unit:3_major_scale']).count())
print('Unit 3 playlists:', Playlist.objects.filter(name__startswith='Unit 3').count())
"
```
