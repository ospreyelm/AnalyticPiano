# Unit 2 Add Barlines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 Unit 2 add-barlines exercise as a QA-player route with generated barline-placement exercise data, VexFlow rendering, keyboard/touch placement, grading, and result submission.

**Architecture:** Store each add-barlines exercise as a UMTO-adjacent `Exercise.data` payload with `type: "umto_barline_placement"`. Backend builder code computes beat structure and validates exercises; the lab/student views route this payload to `qa_player.html`; a new `barline_player.js` ES module owns the VexFlow UI and delegates pure grading/payload logic to a Node-testable `barline_player_logic.js` module.

**Tech Stack:** Django management commands/tests, music21 duration parsing, existing `Exercise`/`Playlist` models, VexFlow global script loaded in `qa_player.html`, vanilla JS ES modules, lightweight Node tests.

---

## File Structure

- Create `apps/exercises/utils/barline_exercise_builder.py` for meter parsing, note duration conversion, beat-position computation, payload validation, and hand-authored/corpus-ready build helpers.
- Create `apps/exercises/tests/test_barline_exercise_builder.py` for Python builder tests.
- Modify `apps/exercises/umto_factory.py` to add `save_umto_barline_exercise()` mirroring `save_umto_symbolic_exercise()`.
- Modify `apps/exercises/tests/test_symbolic_meter_questions.py` or create `apps/exercises/tests/test_barline_exercise_save.py` for save-helper coverage.
- Create `apps/exercises/management/commands/generate_unit2_barline_exercises.py` for initial hand-authored generation and playlist wiring; add Essen/Kern support behind the same builder API.
- Create `apps/exercises/tests/test_generate_unit2_barline_exercises.py` for command coverage.
- Modify `lab/views.py` to route `umto_barline_placement` to `qa_player.html` alongside `umto_symbolic_meter`.
- Extend `apps/exercises/tests/test_generate_exercise_context.py` with a raw-payload preservation test for barline placement.
- Modify `lab/templates/qa_player.html` to load `vexflow.js`, `barline_player_logic.js`, and `barline_player.js`.
- Create `lab/static/js/src/barline_player_logic.js` for pure JS functions: grade, payload, cursor bounds, duration normalization, beat-x fallback.
- Create `lab/static/js/src/barline_player_logic.test.js` for Node tests.
- Create `lab/static/js/src/barline_player.js` for DOM/VexFlow rendering and interaction.

---

### Task 1: Backend Builder Core

**Files:**
- Create: `apps/exercises/utils/barline_exercise_builder.py`
- Create: `apps/exercises/tests/test_barline_exercise_builder.py`

- [ ] **Step 1: Write failing tests for simple and compound beat structure**

Create `apps/exercises/tests/test_barline_exercise_builder.py`:

```python
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
                {"pitch": "B4", "duration": "q", "dots": 0},
            ],
            measures=3,
            show_time_signature=False,
            pitch_mode="rhythm_only",
            source="test",
        )

        self.assertEqual(payload["type"], "umto_barline_placement")
        self.assertEqual(payload["beat_count"], 9)
        self.assertEqual(payload["correct_barline_positions"], [2, 5])
        self.assertEqual(payload["beat_positions_ticks"], list(range(10)))

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
        self.assertEqual(payload["correct_barline_positions"], [1])
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
```

- [ ] **Step 2: Run tests and verify they fail because the module does not exist**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_barline_exercise_builder -v 2
```

Expected: import failure for `apps.exercises.utils.barline_exercise_builder`.

- [ ] **Step 3: Implement the builder**

Create `apps/exercises/utils/barline_exercise_builder.py`:

```python
from fractions import Fraction

SIMPLE_METERS = {
    "2/4": (2, Fraction(1, 1)),
    "3/4": (3, Fraction(1, 1)),
    "4/4": (4, Fraction(1, 1)),
}
COMPOUND_METERS = {
    "6/8": (2, Fraction(3, 1)),
    "9/8": (3, Fraction(3, 1)),
    "12/8": (4, Fraction(3, 1)),
}
DURATION_TO_QUARTERS = {
    "w": Fraction(4, 1),
    "h": Fraction(2, 1),
    "q": Fraction(1, 1),
    "8": Fraction(1, 2),
    "16": Fraction(1, 4),
}


def duration_quarters(duration, dots=0):
    if duration not in DURATION_TO_QUARTERS:
        raise ValueError(f"Unsupported duration: {duration}")
    base = DURATION_TO_QUARTERS[duration]
    total = base
    add = base
    for _ in range(int(dots or 0)):
        add /= 2
        total += add
    return total


def meter_info(time_signature):
    if time_signature in SIMPLE_METERS:
        beats_per_measure, beat_quarters = SIMPLE_METERS[time_signature]
        return beats_per_measure, beat_quarters
    if time_signature in COMPOUND_METERS:
        beats_per_measure, beat_quarters = COMPOUND_METERS[time_signature]
        return beats_per_measure, beat_quarters
    raise ValueError(f"Unsupported time signature: {time_signature}")


def _tick_scale(beat_quarters):
    return beat_quarters.denominator


def build_barline_payload(
    *,
    time_signature,
    clef,
    notes,
    measures,
    show_time_signature,
    pitch_mode,
    source,
    tags=None,
):
    beats_per_measure, beat_quarters = meter_info(time_signature)
    total_quarters = sum(
        duration_quarters(note["duration"], note.get("dots", 0))
        for note in notes
    )
    expected_quarters = Fraction(measures, 1) * beats_per_measure * beat_quarters
    if total_quarters != expected_quarters:
        raise ValueError(
            f"total duration {total_quarters} does not equal expected {expected_quarters}"
        )

    beat_count = measures * beats_per_measure
    scale = _tick_scale(beat_quarters)
    beat_ticks = int(beat_quarters * scale)
    beat_positions_ticks = [i * beat_ticks for i in range(beat_count + 1)]
    correct_barline_positions = [
        (measure_index * beats_per_measure) - 1
        for measure_index in range(1, measures)
    ]

    return {
        "type": "umto_barline_placement",
        "isUMTO": True,
        "mode": "identification",
        "time_signature": time_signature,
        "show_time_signature": bool(show_time_signature),
        "clef": clef,
        "measures": measures,
        "pitch_mode": pitch_mode,
        "notes": list(notes),
        "correct_barline_positions": correct_barline_positions,
        "beat_count": beat_count,
        "beat_positions_ticks": beat_positions_ticks,
        "source": source,
        "tags": list(tags or ["unit:2", "unit:2_rhythm"]),
    }
```

- [ ] **Step 4: Run builder tests and verify green**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_barline_exercise_builder -v 2
```

Expected: all four tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/barline_exercise_builder.py apps/exercises/tests/test_barline_exercise_builder.py
git commit -m "feat: add Unit 2 barline exercise builder"
```

---

### Task 2: Save Helper and Context Routing

**Files:**
- Modify: `apps/exercises/umto_factory.py`
- Modify: `apps/exercises/tests/test_symbolic_meter_questions.py` or create `apps/exercises/tests/test_barline_exercise_save.py`
- Modify: `apps/exercises/tests/test_generate_exercise_context.py`
- Modify: `lab/views.py`

- [ ] **Step 1: Write failing save-helper test**

Create `apps/exercises/tests/test_barline_exercise_save.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.umto_factory import save_umto_barline_exercise


class BarlineExerciseSaveTests(TestCase):
    def test_save_umto_barline_exercise_creates_runtime_payload(self):
        user = get_user_model().objects.create_user(
            email="barline@example.com",
            password="pw",
        )
        exercise = save_umto_barline_exercise(
            description="Unit 2 add barlines sample",
            author=user,
            payload={
                "type": "umto_barline_placement",
                "isUMTO": True,
                "mode": "identification",
                "time_signature": "3/4",
                "show_time_signature": False,
                "clef": "treble",
                "measures": 1,
                "pitch_mode": "rhythm_only",
                "notes": [{"pitch": "B4", "duration": "q", "dots": 0}] * 3,
                "correct_barline_positions": [],
                "beat_count": 3,
                "beat_positions_ticks": [0, 1, 2, 3],
                "source": "test",
                "tags": ["unit:2", "unit:2_meter_simple"],
            },
            is_public=True,
        )

        self.assertEqual(exercise.data["type"], "umto_barline_placement")
        self.assertEqual(exercise.data["mode"], "identification")
        self.assertEqual(exercise.data["exerciseId"], exercise.id)
        self.assertEqual(exercise.skill_tags, ["unit:2", "unit:2_meter_simple"])
```

- [ ] **Step 2: Run test and verify it fails on missing helper**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_barline_exercise_save -v 2
```

Expected: import failure for `save_umto_barline_exercise`.

- [ ] **Step 3: Implement save helper**

Add to `apps/exercises/umto_factory.py` after `save_umto_symbolic_exercise()`:

```python
def save_umto_barline_exercise(
    *,
    description: str,
    author,
    payload: dict,
    is_public: bool = True,
    overwrite: bool = False,
) -> Exercise:
    data = dict(payload)
    data["type"] = "umto_barline_placement"
    data["isUMTO"] = True
    data["mode"] = InteractionMode.IDENTIFICATION.value

    skill_tags = list(data.get("tags") or ["unit:2", "unit:2_rhythm"])
    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

    if ex is None:
        ex = Exercise(
            description=description,
            data=data,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags,
            complexity=2,
        )
    else:
        ex.data = data
        ex.skill_tags = skill_tags
        ex.complexity = 2
        ex.is_public = is_public
    ex.save()
    ex.data["exerciseId"] = ex.id
    ex.save()
    return ex
```

- [ ] **Step 4: Run save-helper test and verify green**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_barline_exercise_save -v 2
```

Expected: tests pass, including the explicit `essen` source guard that documents the real repertoire path.

- [ ] **Step 5: Write failing context routing tests**

Append to `apps/exercises/tests/test_generate_exercise_context.py`:

```python
class GenerateExerciseContextBarlinePlacementTest(SimpleTestCase):
    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_barline_payload_passes_through_without_umto_validation(self, mock_reader, mock_perf):
        from apps.exercises.models import Exercise, Playlist
        from lab.views import generate_exercise_context

        mock_reader.get_unit_for_tag.return_value = None
        mock_perf.objects.filter.return_value.last.return_value = None

        ex = MagicMock(spec=Exercise)
        ex.id = "BAR01"
        ex.data = {
            "type": "umto_barline_placement",
            "isUMTO": True,
            "mode": "identification",
            "time_signature": "3/4",
            "show_time_signature": False,
            "clef": "treble",
            "measures": 1,
            "pitch_mode": "rhythm_only",
            "notes": [{"pitch": "B4", "duration": "q", "dots": 0}] * 3,
            "correct_barline_positions": [],
            "beat_count": 3,
            "beat_positions_ticks": [0, 1, 2, 3],
            "source": "test",
            "tags": ["unit:2"],
        }
        ex.skill_tags = ["unit:2"]
        ex.complexity = 2

        pl = MagicMock(spec=Playlist)
        pl.skill_tags = ["unit:2"]
        pl.is_adaptive = False
        pl.is_dynamic = False
        pl.tags = []
        pl.feedback_mode = ""
        pl.exercise_list = [ex]
        pl.id = "PLBAR"
        pl.prev_num.return_value = None
        pl.next_num.return_value = None
        pl.get_exercise_obj_by_num.return_value = None
        pl.get_exercise_url_by_num.return_value = None

        ctx = generate_exercise_context(
            exercise_num=1,
            exercise=ex,
            user=MagicMock(id=1),
            playlist=pl,
            course=None,
        )

        self.assertEqual(ctx["type"], "umto_barline_placement")
        self.assertEqual(ctx["time_signature"], "3/4")
        self.assertEqual(ctx["playlistName"], "PLBAR")
```

- [ ] **Step 6: Run context test and verify it fails if current UMTO validation swallows raw payload**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_exercise_context.GenerateExerciseContextBarlinePlacementTest -v 2
```

Expected: failure until `generate_exercise_context()` treats `umto_barline_placement` as raw QA data.

- [ ] **Step 7: Modify `generate_exercise_context()` to bypass UMTO validation for barline placement**

In `lab/views.py`, immediately before the existing `is_umto = ...` line inside `generate_exercise_context()`, add:

```python
    if exercise.data.get("type") == "umto_barline_placement":
        exercise_context.update(exercise.data)
    else:
        # UMTO Alignment: If the data follows the UMTO schema, use its frontend payload generator
        is_umto = exercise.data.get("isUMTO", False) or ("metadata" in exercise.data and "voices" in exercise.data)
        if is_umto:
            try:
                from apps.exercises.umto import UMTO
                umto_obj = UMTO.model_validate(exercise.data)
                unit_focus = None
                playlist_tags = playlist.skill_tags if playlist else []
                fallback_tags = exercise.skill_tags or []
                for tag in list(playlist_tags) + list(fallback_tags):
                    if isinstance(tag, str) and tag.startswith("unit:"):
                        try:
                            unit_focus = int(tag.split(":")[1])
                        except (ValueError, IndexError):
                            continue
                exercise_context.update(umto_obj.to_frontend_payload(unit=unit_focus))
            except Exception as e:
                logger.warning(
                    "[LEGACY EXERCISE] Exercise %s failed UMTO validation: %s. "
                    "Falling back to raw data. Migrate via apps.exercises.umto_factory.",
                    exercise.id, e,
                )
                exercise_context.update(exercise.data)
        else:
            exercise_context.update(exercise.data)
```

Keep the surrounding navigation/context update code unchanged. Remove the original duplicated `is_umto` block when moving it under the `else`.

- [ ] **Step 8: Add template-routing branch**

In `lab/views.py`, change the existing QA render condition near the `qa_player.html` render from:

```python
        if exercise_context.get("type") == "umto_symbolic_meter":
```

to:

```python
        if exercise_context.get("type") in {"umto_symbolic_meter", "umto_barline_placement"}:
```

- [ ] **Step 9: Run backend routing tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_barline_exercise_save apps.exercises.tests.test_generate_exercise_context.GenerateExerciseContextBarlinePlacementTest -v 2
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_barline_exercise_save.py apps/exercises/tests/test_generate_exercise_context.py lab/views.py
git commit -m "feat: route Unit 2 barline placement payloads"
```

---

### Task 3: Generation Command

**Files:**
- Create: `apps/exercises/management/commands/generate_unit2_barline_exercises.py`
- Create: `apps/exercises/tests/test_generate_unit2_barline_exercises.py`

**Source policy:** `manual` is only a deterministic test/dev seed source. Real repertoire examples should come from Essen Folk Song Collection / Kern-Humdrum material via music21 (`--source essen`) or from an explicit local Kern/Humdrum file (`--source kern`).

- [ ] **Step 1: Write failing command test**

Create `apps/exercises/tests/test_generate_unit2_barline_exercises.py`:

```python
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist


class GenerateUnit2BarlineExercisesCommandTests(TestCase):
    def test_manual_source_creates_dev_seed_exercise_and_playlist_link(self):
        user = get_user_model().objects.create_user(
            email="barline-seed@example.com",
            password="pw",
        )

        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            public=True,
            count=1,
            meter="3/4",
            measures=2,
            pitch_mode="rhythm_only",
            source="manual",
        )

        exercise = Exercise.objects.latest("created")
        playlist = Playlist.objects.get(
            name="Unit 2 — Add Barlines",
            authored_by=user,
        )
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, order=1)

        self.assertEqual(exercise.data["type"], "umto_barline_placement")
        self.assertEqual(exercise.data["time_signature"], "3/4")
        self.assertEqual(exercise.data["measures"], 2)
        self.assertEqual(exercise.data["correct_barline_positions"], [2])
        self.assertEqual(link.exercise, exercise)
        self.assertTrue(playlist.is_public)
        self.assertIn("unit:2", playlist.skill_tags)

    def test_essen_source_is_recognized_as_real_repertoire_path(self):
        user = get_user_model().objects.create_user(
            email="essen-seed@example.com",
            password="pw",
        )

        with self.assertRaisesMessage(CommandError, "Essen/Kern import is not implemented yet"):
            call_command(
                "generate_unit2_barline_exercises",
                author=user.email,
                source="essen",
                count=1,
            )
```

Add this import at the top of the test file:

```python
from django.core.management.base import CommandError
```

- [ ] **Step 2: Run test and verify command missing**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit2_barline_exercises -v 2
```

Expected: `Unknown command: 'generate_unit2_barline_exercises'`.

- [ ] **Step 3: Implement command with deterministic manual seed first**

Create `apps/exercises/management/commands/generate_unit2_barline_exercises.py`:

```python
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_umto_barline_exercise
from apps.exercises.utils.barline_exercise_builder import build_barline_payload

PLAYLIST_NAME = "Unit 2 — Add Barlines"
PLAYLIST_SKILL_TAGS = [
    "unit:2",
    "unit:2_rhythm",
    "unit:2_meter_simple",
    "unit:2_meter_compound",
]


def _manual_notes(meter, measures):
    if meter in {"2/4", "3/4", "4/4"}:
        beats = int(meter.split("/")[0]) * measures
        return [{"pitch": "B4", "duration": "q", "dots": 0} for _ in range(beats)]
    if meter == "6/8":
        return [{"pitch": "B4", "duration": "q", "dots": 1} for _ in range(2 * measures)]
    if meter == "9/8":
        return [{"pitch": "B4", "duration": "q", "dots": 1} for _ in range(3 * measures)]
    if meter == "12/8":
        return [{"pitch": "B4", "duration": "q", "dots": 1} for _ in range(4 * measures)]
    raise CommandError(f"Unsupported meter: {meter}")


class Command(BaseCommand):
    help = "Create Unit 2 add-barlines exercises"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--count", type=int, default=1)
        parser.add_argument("--meter", default="3/4")
        parser.add_argument("--measures", type=int, default=2)
        parser.add_argument("--pitch-mode", default="rhythm_only")
        parser.add_argument("--source", choices=["manual", "essen", "kern"], default="manual")

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            author = user_model.objects.get(email=options["author"])
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        if options["source"] != "manual":
            raise CommandError("Essen/Kern import is not implemented yet; use --source manual for deterministic dev seed")

        playlist, created = Playlist.objects.get_or_create(
            name=PLAYLIST_NAME,
            authored_by=author,
            defaults=dict(
                is_dynamic=False,
                is_adaptive=False,
                is_public=options["public"],
                skill_tags=list(PLAYLIST_SKILL_TAGS),
            ),
        )
        if not created:
            playlist.is_dynamic = False
            playlist.is_adaptive = False
            if options["public"]:
                playlist.is_public = True
            tags = list(playlist.skill_tags or [])
            for tag in PLAYLIST_SKILL_TAGS:
                if tag not in tags:
                    tags.append(tag)
            playlist.skill_tags = tags
            playlist.save()

        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        for idx in range(options["count"]):
            payload = build_barline_payload(
                time_signature=options["meter"],
                clef="treble",
                notes=_manual_notes(options["meter"], options["measures"]),
                measures=options["measures"],
                show_time_signature=(idx % 2 == 0),
                pitch_mode=options["pitch_mode"],
                source="Unit 2 add barlines manual seed",
                tags=list(PLAYLIST_SKILL_TAGS),
            )
            exercise = save_umto_barline_exercise(
                description=f"Unit 2 add barlines {options['meter']} #{idx + 1}",
                author=author,
                payload=payload,
                is_public=options["public"],
                overwrite=True,
            )
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist,
                exercise=exercise,
                order=idx + 1,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {options['count']} barline exercise(s) in '{playlist.name}'"
            )
        )
```

- [ ] **Step 4: Run command test and verify green**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit2_barline_exercises -v 2
```

Expected: tests pass, including the explicit `essen` source guard that documents the real repertoire path.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_unit2_barline_exercises.py apps/exercises/tests/test_generate_unit2_barline_exercises.py
git commit -m "feat: seed Unit 2 barline exercises"
```

---

### Task 4: Pure Frontend Logic

**Files:**
- Create: `lab/static/js/src/barline_player_logic.js`
- Create: `lab/static/js/src/barline_player_logic.test.js`

- [ ] **Step 1: Write failing Node tests**

Create `lab/static/js/src/barline_player_logic.test.js`:

```javascript
"use strict";

var logic = require("./barline_player_logic");
var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    console.log("  PASS: " + label);
    pass++;
  } else {
    console.log("  FAIL: " + label);
    console.log("       got: " + JSON.stringify(actual) + ", expected: " + JSON.stringify(expected));
    fail++;
  }
}

console.log("\nbarline player logic:");

assertEqual(
  "grade reports exact match as correct",
  logic.gradeBarlines([2, 5], [2, 5]),
  { correct: true, missing: [], extra: [] }
);

assertEqual(
  "grade reports missing and extra positions",
  logic.gradeBarlines([2, 4], [2, 5]),
  { correct: false, missing: [5], extra: [4] }
);

assertEqual(
  "cursor clamps to navigable beat gaps",
  [logic.clampCursor(-1, 4), logic.clampCursor(99, 4)],
  [0, 2]
);

assertEqual(
  "result payload serializes barline answer",
  logic.buildResultPayload({
    config: { courseId: "C1", playlistName: "P1", exerciseNum: 3 },
    placedAt: [2, 5],
    correct: true,
  }),
  {
    course_ID: "C1",
    playlist_ID: "P1",
    exercise_num: 3,
    answers: { barlines: [2, 5] },
    correctness: { "0": true },
    score: { correct: 1, incorrect: 0, unanswered: 0 },
    page_num: 0,
    is_page_submit: false,
    mode: "barline_placement",
    attempt_type: "practice"
  }
);

assertEqual(
  "uniform fallback creates one x value per beat boundary",
  logic.uniformBeatX(100, 500, 4),
  [100, 200, 300, 400, 500]
);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] **Step 2: Run test and verify module missing**

Run:

```bash
node lab/static/js/src/barline_player_logic.test.js
```

Expected: `Cannot find module './barline_player_logic'`.

- [ ] **Step 3: Implement pure logic**

Create `lab/static/js/src/barline_player_logic.js` as a small UMD-style file so Node tests can `require()` it and the browser player can read `window.barlinePlayerLogic`:

```javascript
(function (root) {
"use strict";

function sortedNumbers(values) {
  return (values || []).slice().map(function (v) { return parseInt(v, 10); })
    .filter(function (v) { return !isNaN(v); })
    .sort(function (a, b) { return a - b; });
}

function gradeBarlines(placedAt, correctAt) {
  var placed = sortedNumbers(placedAt);
  var correct = sortedNumbers(correctAt);
  var missing = correct.filter(function (i) { return placed.indexOf(i) === -1; });
  var extra = placed.filter(function (i) { return correct.indexOf(i) === -1; });
  return { correct: missing.length === 0 && extra.length === 0, missing: missing, extra: extra };
}

function clampCursor(cursorPos, beatCount) {
  var max = Math.max(0, (parseInt(beatCount, 10) || 1) - 2);
  return Math.min(Math.max(parseInt(cursorPos, 10) || 0, 0), max);
}

function buildResultPayload(options) {
  var config = options.config || {};
  var correct = !!options.correct;
  return {
    course_ID: config.courseId || null,
    playlist_ID: config.playlistName,
    exercise_num: config.exerciseNum,
    answers: { barlines: sortedNumbers(options.placedAt) },
    correctness: { "0": correct },
    score: { correct: correct ? 1 : 0, incorrect: correct ? 0 : 1, unanswered: 0 },
    page_num: 0,
    is_page_submit: false,
    mode: "barline_placement",
    attempt_type: "practice"
  };
}

function uniformBeatX(startX, endX, beatCount) {
  var count = parseInt(beatCount, 10) || 0;
  if (count <= 0) return [];
  var width = (endX - startX) / count;
  var xs = [];
  for (var i = 0; i <= count; i++) {
    xs.push(Math.round(startX + width * i));
  }
  return xs;
}

var api = {
  gradeBarlines: gradeBarlines,
  clampCursor: clampCursor,
  buildResultPayload: buildResultPayload,
  uniformBeatX: uniformBeatX
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = api;
}
root.barlinePlayerLogic = api;
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: Run Node test and verify green**

Run:

```bash
node lab/static/js/src/barline_player_logic.test.js
```

Expected: `5 passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/barline_player_logic.js lab/static/js/src/barline_player_logic.test.js
git commit -m "feat: add barline player grading logic"
```

---

### Task 5: QA Template and Barline Player UI

**Files:**
- Modify: `lab/templates/qa_player.html`
- Create: `lab/static/js/src/barline_player.js`

- [ ] **Step 1: Add VexFlow and barline module to QA template**

Modify `lab/templates/qa_player.html` JS block to load VexFlow before the ES modules:

```html
<script>
  window.__EXERCISE_CONFIG__ = {{ exercise_config_json|safe }};
</script>
<script src="{% static 'js/lib/vexflow.js' %}"></script>
<script src="{% static 'js/src/barline_player_logic.js' %}"></script>
<script type="module" src="{% static 'js/src/qa_player.js' %}"></script>
<script type="module" src="{% static 'js/src/barline_player.js' %}"></script>
```

- [ ] **Step 2: Create barline player module with guarded boot and UI skeleton**

Create `lab/static/js/src/barline_player.js`:

```javascript
const logic = window.barlinePlayerLogic;

function getCookie(name) {
  const value = "; " + document.cookie;
  const parts = value.split("; " + name + "=");
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function vex() {
  return window.Vex && (window.Vex.Flow || window.Vex);
}

function vfKey(pitch) {
  const m = String(pitch || "B4").match(/^([A-Ga-g])([#b]?)(\d)$/);
  if (!m) return "b/4";
  return (m[1].toLowerCase() + m[2].replace("#", "#").replace("b", "b") + "/" + m[3]);
}

function renderShell(root, config) {
  root.innerHTML = `
    <div class="qa-card barline-card">
      <div class="qa-stem">Place the barlines.</div>
      <div class="barline-stage" style="position:relative; min-height:180px;"></div>
      <div class="barline-pips" aria-label="Beat positions"></div>
      <div class="qa-submit-bar">
        <button type="button" class="qa-choice" data-action="left" aria-label="Move left">←</button>
        <button type="button" class="qa-choice" data-action="toggle">Place / Remove</button>
        <button type="button" class="qa-choice" data-action="right" aria-label="Move right">→</button>
        <button type="button" class="qa-submit-btn" data-action="submit">Submit</button>
      </div>
      <div class="qa-feedback" aria-live="polite"></div>
    </div>`;
}

function drawNotation(stage, config) {
  const VF = vex();
  if (!VF) throw new Error("VexFlow is not loaded");

  stage.innerHTML = "";
  const renderer = new VF.Renderer(stage, VF.Renderer.Backends.SVG);
  const width = Math.max(stage.clientWidth || 600, 360);
  renderer.resize(width, 170);
  const context = renderer.getContext();
  const stave = new VF.Stave(20, 30, width - 40);
  stave.addClef(config.clef || "treble");
  if (config.show_time_signature) stave.addTimeSignature(config.time_signature);
  stave.setBegBarType(VF.Barline.type.SINGLE);
  stave.setEndBarType(VF.Barline.type.SINGLE);
  stave.setContext(context).draw();

  const notes = (config.notes || []).map(function (item) {
    const note = new VF.StaveNote({
      clef: config.clef || "treble",
      keys: [vfKey(item.pitch)],
      duration: item.duration,
    });
    if (item.dots) VF.Dot.buildAndAttach([note], { all: true });
    return note;
  });

  const voice = new VF.Voice({ num_beats: 4, beat_value: 4 });
  voice.setMode(VF.Voice.Mode.SOFT);
  voice.addTickables(notes);
  new VF.Formatter().joinVoices([voice]).format([voice], width - 100);
  voice.draw(context, stave);

  const xValues = notes.map(function (note) { return note.getAbsoluteX && note.getAbsoluteX(); })
    .filter(function (x) { return typeof x === "number" && !isNaN(x); });
  if (xValues.length >= config.beat_count) {
    xValues.push(stave.getX() + stave.getWidth());
    return xValues.slice(0, config.beat_count + 1);
  }
  return logic.uniformBeatX(stave.getX() + 45, stave.getX() + stave.getWidth(), config.beat_count);
}

function updateVisuals(root, state, config) {
  const stage = root.querySelector(".barline-stage");
  const feedback = root.querySelector(".qa-feedback");
  let overlay = stage.querySelector(".barline-cursor");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.className = "barline-cursor";
    overlay.style.position = "absolute";
    overlay.style.top = "28px";
    overlay.style.height = "100px";
    overlay.style.background = "rgba(33, 150, 243, 0.12)";
    overlay.style.border = "1px dashed #1976d2";
    overlay.style.pointerEvents = "none";
    stage.appendChild(overlay);
  }
  const x0 = state.beatX[state.cursorPos] || 0;
  const x1 = state.beatX[state.cursorPos + 1] || x0 + 20;
  overlay.style.left = x0 + "px";
  overlay.style.width = Math.max(12, x1 - x0) + "px";

  stage.querySelectorAll(".placed-barline").forEach(function (el) { el.remove(); });
  state.placedAt.forEach(function (pos) {
    const line = document.createElement("div");
    line.className = "placed-barline";
    line.style.position = "absolute";
    line.style.left = (state.beatX[pos + 1] || 0) + "px";
    line.style.top = "30px";
    line.style.height = "95px";
    line.style.borderLeft = "2px solid #111";
    stage.appendChild(line);
  });

  if (state.lastGrade) {
    feedback.textContent = state.lastGrade.correct ? "Correct" : "Try again";
    feedback.className = state.lastGrade.correct ? "qa-feedback qa-feedback-correct" : "qa-feedback qa-feedback-incorrect";
  }
}

function submit(config, state) {
  const grade = logic.gradeBarlines(Array.from(state.placedAt), config.correct_barline_positions || []);
  state.lastGrade = grade;
  const payload = logic.buildResultPayload({ config: config, placedAt: Array.from(state.placedAt), correct: grade.correct });
  fetch("/ajax/identification-answers/", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": getCookie("csrftoken") },
    body: "data=" + encodeURIComponent(JSON.stringify(payload))
  }).catch(function () { return; });
  return grade;
}

function boot() {
  const config = window.__EXERCISE_CONFIG__;
  if (!config || config.type !== "umto_barline_placement") return;
  const root = document.getElementById("qa-root");
  if (!root) return;
  renderShell(root, config);
  const stage = root.querySelector(".barline-stage");
  const state = { cursorPos: 0, placedAt: new Set(), beatX: drawNotation(stage, config), lastGrade: null };
  updateVisuals(root, state, config);

  function move(delta) {
    state.cursorPos = logic.clampCursor(state.cursorPos + delta, config.beat_count);
    updateVisuals(root, state, config);
  }
  function toggle() {
    if (state.placedAt.has(state.cursorPos)) state.placedAt.delete(state.cursorPos);
    else state.placedAt.add(state.cursorPos);
    updateVisuals(root, state, config);
  }

  root.addEventListener("click", function (event) {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.action === "left") move(-1);
    if (button.dataset.action === "right") move(1);
    if (button.dataset.action === "toggle") toggle();
    if (button.dataset.action === "submit") { submit(config, state); updateVisuals(root, state, config); }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { event.preventDefault(); move(-1); }
    if (event.key === "ArrowRight") { event.preventDefault(); move(1); }
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
  });
  window.addEventListener("resize", function () {
    state.beatX = drawNotation(stage, config);
    updateVisuals(root, state, config);
  });
}

document.addEventListener("DOMContentLoaded", boot);
```

- [ ] **Step 3: Run existing JS logic test to make sure CommonJS module remains valid**

Run:

```bash
node lab/static/js/src/barline_player_logic.test.js
```

Expected: `5 passed, 0 failed`.

- [ ] **Step 4: Run a local server and manually spike VexFlow access**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver 127.0.0.1:8001 --noreload
```

Open a generated `umto_barline_placement` exercise in the browser. Expected: no console error for `VexFlow is not loaded`, one unbarred staff renders, left/right/space update visible state.

- [ ] **Step 5: Commit**

```bash
git add lab/templates/qa_player.html lab/static/js/src/barline_player.js
git commit -m "feat: render barline placement player"
```

---

### Task 6: Verification Pass

**Files:**
- No new files unless fixing failures.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_barline_exercise_builder apps.exercises.tests.test_barline_exercise_save apps.exercises.tests.test_generate_unit2_barline_exercises apps.exercises.tests.test_generate_exercise_context -v 2
```

Expected: all listed tests pass.

- [ ] **Step 2: Run focused frontend logic tests**

Run:

```bash
node lab/static/js/src/barline_player_logic.test.js
node lab/static/js/src/models/symbolic_meter_rendering_logic.test.js
```

Expected: all tests print `0 failed` or all `PASS` lines.

- [ ] **Step 3: Generate one local exercise set**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py generate_unit2_barline_exercises --author avner-local2025@localhost --public --count 1 --meter 3/4 --measures 2 --pitch-mode rhythm_only --source manual
```

Expected: command prints `Created 1 barline exercise(s) in 'Unit 2 — Add Barlines'`.

- [ ] **Step 4: Browser smoke test**

Run the dev server and open the created exercise. Verify:

- Staff renders with opening and closing barlines only.
- Time signature visibility follows the generated payload.
- Arrow keys and on-screen arrow buttons move the cursor.
- Enter/Space and Place/Remove toggle a barline.
- Submit posts to `/ajax/identification-answers/` and shows Correct/Try again feedback.
- Existing symbolic meter QA exercises still render as multiple choice.

- [ ] **Step 5: Commit any fixes from verification**

If verification required changes, stage the concrete files changed by the previous tasks and commit them. For the expected verification-only path, there should be no changes to commit.

```bash
git status --short
```

Expected when no fixes were required: no output.

---

## Self-Review

- Spec coverage: Phase 1 backend storage, QA routing, VexFlow loading, pure grader, cursor behavior, result submission, and manual seed generation are covered. Essen/Kern corpus import is intentionally represented by command options but only manual generation is implemented in this first shippable slice for deterministic tests; Essen/Kern import is the intended repertoire path and should be implemented once the VexFlow spike validates the interaction.
- Placeholder scan: The plan contains no unresolved implementation placeholders. Every code-creating step includes concrete code.
- Type consistency: The discriminator is consistently `umto_barline_placement`; barline answer positions are consistently 0-indexed beat indices after which a barline falls; `beat_positions_ticks` is present for all meters.
