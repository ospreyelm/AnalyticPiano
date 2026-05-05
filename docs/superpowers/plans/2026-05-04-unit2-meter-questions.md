# Unit 2 Meter Questions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1 Unit 2 symbolic meter questions as UMTO-backed multiple-choice exercises with a generated canonical meter-reference dataset, a curated drill manifest, and a dedicated score-less frontend renderer that uses a proper music font for time signatures.

**Architecture:** Keep music21 out of runtime. Generate `apps/exercises/data/unit2_meter_reference.json` from an explicit allowlist of numeric signatures, then materialize a curated question manifest into UMTO-backed Exercise rows whose top-level payload type is a new symbolic mode. Reuse the existing identification grading flow for answer state, but render symbolic prompts in a dedicated component instead of the score/staff pipeline.

**Tech Stack:** Django management commands, `music21`, JSON fixtures, existing `save_umto_exercise`/UMTO payload conventions, RequireJS frontend modules, existing `IdentificationGrader`, HarmonyLab CSS with SMuFL-capable music font support.

---

## File Structure

**Create:**
- `apps/exercises/management/commands/generate_unit2_meter_reference.py`
- `apps/exercises/data/unit2_meter_reference.json`
- `apps/exercises/data/unit2_symbolic_drill_manifest.json`
- `apps/exercises/symbolic_meter_questions.py`
- `apps/exercises/management/commands/generate_unit2_meter_exercises.py`
- `apps/exercises/tests/test_generate_unit2_meter_reference.py`
- `apps/exercises/tests/test_symbolic_meter_questions.py`
- `lab/static/js/src/components/music/symbolic_question_sheet.js`
- `lab/static/js/src/models/symbolic_meter_rendering_logic.js`
- `lab/static/js/src/models/symbolic_meter_rendering_logic.test.js`

**Modify:**
- `apps/exercises/umto_factory.py`
- `apps/exercises/umto.py`
- `lab/static/js/src/models/exercise_definition.js`
- `lab/static/js/src/components/app/exercise.js`
- `lab/static/css/harmony.css`
- `lab/templates/exercise.html`

**Why these files:**
- The reference generator and JSON fixture isolate the canonical meter facts.
- `symbolic_meter_questions.py` owns subtype generation, choice construction, and manifest expansion.
- `generate_unit2_meter_exercises.py` is the authoring/seed path that creates actual Exercise rows and can later create or refresh a Unit 2 playlist.
- Frontend changes are isolated to parse/detect the new payload type and render it without the score pipeline.

### Task 1: Generate and Validate the Canonical Meter Reference JSON

**Files:**
- Create: `apps/exercises/management/commands/generate_unit2_meter_reference.py`
- Create: `apps/exercises/data/unit2_meter_reference.json`
- Test: `apps/exercises/tests/test_generate_unit2_meter_reference.py`

- [ ] **Step 1: Write the failing reference-generator tests**

Add `apps/exercises/tests/test_generate_unit2_meter_reference.py`:

```python
from django.core.management import call_command
from django.test import SimpleTestCase

from apps.exercises.management.commands.generate_unit2_meter_reference import (
    ALLOWED_SIGNATURES,
    quarter_length_to_label,
    build_reference_entry,
)


class Unit2MeterReferenceTests(SimpleTestCase):
    def test_quarter_length_to_label_covers_phase1_values(self):
        self.assertEqual(quarter_length_to_label(0.25), "sixteenth")
        self.assertEqual(quarter_length_to_label(0.75), "dotted eighth")
        self.assertEqual(quarter_length_to_label(3.0), "dotted half")
        self.assertEqual(quarter_length_to_label(6.0), "dotted whole")

    def test_build_reference_entry_handles_compound_two_denominator(self):
        entry = build_reference_entry("6/2")
        self.assertEqual(entry["division_type"], "compound")
        self.assertEqual(entry["grouping"], "duple")
        self.assertEqual(entry["beat_count"], 2)
        self.assertEqual(entry["division_count"], 6)
        self.assertEqual(entry["beat_value"], "dotted whole")
        self.assertEqual(entry["division_value"], "half")

    def test_build_reference_entry_handles_simple_two_denominator(self):
        entry = build_reference_entry("3/2")
        self.assertEqual(entry["division_type"], "simple")
        self.assertEqual(entry["grouping"], "triple")
        self.assertEqual(entry["beat_value"], "half")
        self.assertEqual(entry["division_value"], "quarter")

    def test_allowed_signatures_match_spec_shape(self):
        self.assertIn("6/2", ALLOWED_SIGNATURES)
        self.assertIn("12/16", ALLOWED_SIGNATURES)
        self.assertNotIn("5/8", ALLOWED_SIGNATURES)

    def test_command_writes_all_entries(self):
        result = call_command("generate_unit2_meter_reference")
        self.assertIsNone(result)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit2_meter_reference -v 2
```

Expected:

```text
ImportError or ModuleNotFoundError for generate_unit2_meter_reference
```

- [ ] **Step 3: Implement the generator command and validator**

Create `apps/exercises/management/commands/generate_unit2_meter_reference.py`:

```python
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from music21 import meter


ALLOWED_SIGNATURES = [
    "2/2", "2/4", "2/8", "2/16",
    "3/2", "3/4", "3/8", "3/16",
    "4/2", "4/4", "4/8", "4/16",
    "6/2", "6/4", "6/8", "6/16",
    "9/2", "9/4", "9/8", "9/16",
    "12/2", "12/4", "12/8", "12/16",
]

QL_TO_LABEL = {
    0.25: "sixteenth",
    0.5: "eighth",
    0.75: "dotted eighth",
    1.0: "quarter",
    1.5: "dotted quarter",
    2.0: "half",
    3.0: "dotted half",
    4.0: "whole",
    6.0: "dotted whole",
}


def quarter_length_to_label(value: float) -> str:
    rounded = round(float(value), 6)
    try:
        return QL_TO_LABEL[rounded]
    except KeyError as exc:
        raise CommandError(f"Unsupported quarterLength for Unit 2 meter labels: {rounded}") from exc


def _normalize_words(text: str) -> str:
    return text.strip().lower()


def build_reference_entry(ts_string: str) -> dict:
    ts = meter.TimeSignature(ts_string)
    classification = _normalize_words(ts.classification)
    parts = classification.split()
    if len(parts) != 2:
        raise CommandError(f"Unexpected classification for {ts_string}: {ts.classification}")

    beat_duration = ts.beatDuration
    division_durations = ts.beatDivisionDurations
    if not division_durations:
        raise CommandError(f"No beatDivisionDurations found for {ts_string}")

    numerator, denominator = [int(x) for x in ts_string.split("/")]
    entry = {
        "time_signature": ts_string,
        "numerator": numerator,
        "denominator": denominator,
        "division_type": parts[0],
        "grouping": parts[1],
        "full_meter": classification,
        "beat_count": int(ts.beatCount),
        "division_count": numerator if parts[0] == "compound" else numerator * 2,
        "beat_value": quarter_length_to_label(beat_duration.quarterLength),
        "division_value": quarter_length_to_label(division_durations[0].quarterLength),
    }
    validate_reference_entry(entry)
    return entry


def validate_reference_entry(entry: dict) -> None:
    numerator = entry["numerator"]
    denominator = entry["denominator"]
    division_type = entry["division_type"]

    if division_type == "simple":
        expected_beat_count = numerator
        expected_division_count = numerator * 2
    elif division_type == "compound":
        expected_beat_count = numerator // 3
        expected_division_count = numerator
        if numerator % 3 != 0:
            raise CommandError(f"Compound signature must divide evenly by 3: {entry['time_signature']}")
    else:
        raise CommandError(f"Unexpected division_type: {division_type}")

    if entry["beat_count"] != expected_beat_count:
        raise CommandError(f"Bad beat_count for {entry['time_signature']}: {entry['beat_count']}")
    if entry["division_count"] != expected_division_count:
        raise CommandError(f"Bad division_count for {entry['time_signature']}: {entry['division_count']}")
    if division_type == "simple" and denominator not in (2, 4, 8, 16):
        raise CommandError(f"Unsupported denominator in {entry['time_signature']}")


class Command(BaseCommand):
    help = "Generate apps/exercises/data/unit2_meter_reference.json from music21"

    def handle(self, *args, **options):
        data = [build_reference_entry(ts) for ts in ALLOWED_SIGNATURES]
        path = Path("apps/exercises/data/unit2_meter_reference.json")
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit2_meter_reference -v 2
```

Expected:

```text
OK
```

- [ ] **Step 5: Regenerate and inspect the JSON fixture**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py generate_unit2_meter_reference
sed -n '1,220p' apps/exercises/data/unit2_meter_reference.json
```

Expected:

```text
Wrote apps/exercises/data/unit2_meter_reference.json
```

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/management/commands/generate_unit2_meter_reference.py apps/exercises/data/unit2_meter_reference.json apps/exercises/tests/test_generate_unit2_meter_reference.py
git commit -m "feat: generate Unit 2 meter reference data"
```

### Task 2: Build Symbolic Question Materialization From a Curated Manifest

**Files:**
- Create: `apps/exercises/data/unit2_symbolic_drill_manifest.json`
- Create: `apps/exercises/symbolic_meter_questions.py`
- Test: `apps/exercises/tests/test_symbolic_meter_questions.py`

- [ ] **Step 1: Write the failing builder tests**

Create `apps/exercises/tests/test_symbolic_meter_questions.py`:

```python
from django.test import SimpleTestCase

from apps.exercises.symbolic_meter_questions import (
    load_reference_rows,
    build_symbolic_problem,
    build_symbolic_problem_set,
)


class SymbolicMeterQuestionTests(SimpleTestCase):
    def test_build_ts_to_full_meter_problem(self):
        ref = {row["time_signature"]: row for row in load_reference_rows()}
        problem = build_symbolic_problem(
            subtype="ts_to_full_meter",
            source_signature="6/4",
            reference_map=ref,
        )
        self.assertEqual(problem["prompt"]["text"], "6/4")
        self.assertEqual(problem["answer"], "compound duple")
        self.assertEqual(len(problem["choices"]), 4)
        self.assertIn("compound duple", problem["choices"])

    def test_meter_to_ts_has_only_one_matching_choice(self):
        ref = {row["time_signature"]: row for row in load_reference_rows()}
        problem = build_symbolic_problem(
            subtype="meter_to_ts",
            source_signature="9/4",
            reference_map=ref,
        )
        matches = [ts for ts in problem["choices"] if ref[ts]["full_meter"] == "compound triple"]
        self.assertEqual(matches, ["9/4"])

    def test_build_problem_set_preserves_manifest_order(self):
        problems = build_symbolic_problem_set([
            {"subtype": "ts_to_grouping", "source_signature": "3/4"},
            {"subtype": "ts_to_division_type", "source_signature": "6/8"},
        ])
        self.assertEqual([p["subtype"] for p in problems], ["ts_to_grouping", "ts_to_division_type"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_symbolic_meter_questions -v 2
```

Expected:

```text
ImportError for apps.exercises.symbolic_meter_questions
```

- [ ] **Step 3: Add the curated manifest and builder module**

Create `apps/exercises/data/unit2_symbolic_drill_manifest.json`:

```json
[
  { "subtype": "ts_to_grouping", "source_signature": "3/4" },
  { "subtype": "ts_to_grouping", "source_signature": "6/8" },
  { "subtype": "ts_to_division_type", "source_signature": "6/4" },
  { "subtype": "ts_to_beat_value", "source_signature": "3/2" },
  { "subtype": "ts_to_beat_value", "source_signature": "6/2" },
  { "subtype": "ts_to_division_count", "source_signature": "3/4" },
  { "subtype": "ts_to_full_meter", "source_signature": "12/8" },
  { "subtype": "meter_to_ts", "source_signature": "9/4" }
]
```

Create `apps/exercises/symbolic_meter_questions.py`:

```python
import json
from pathlib import Path


REFERENCE_PATH = Path("apps/exercises/data/unit2_meter_reference.json")
MANIFEST_PATH = Path("apps/exercises/data/unit2_symbolic_drill_manifest.json")


def load_reference_rows():
    return json.loads(REFERENCE_PATH.read_text())


def load_manifest_rows():
    return json.loads(MANIFEST_PATH.read_text())


def _grouping_choices(correct):
    return [x for x in ["duple", "triple", "quadruple"] if x != correct]


def _division_type_choices(correct):
    return ["compound"] if correct == "simple" else ["simple"]


def _full_meter_choices(correct):
    ordered = [
        "simple duple",
        "simple triple",
        "simple quadruple",
        "compound duple",
        "compound triple",
        "compound quadruple",
    ]
    return [x for x in ordered if x != correct]


def _ensure_four(correct, distractors):
    unique = []
    for value in [correct] + list(distractors):
        if value not in unique:
            unique.append(value)
    return unique[:4]


def build_symbolic_problem(subtype: str, source_signature: str, reference_map: dict) -> dict:
    row = reference_map[source_signature]
    full_meter = row["full_meter"]

    if subtype == "ts_to_grouping":
        answer = row["grouping"]
        choices = _ensure_four(answer, _grouping_choices(answer))
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_division_type":
        answer = row["division_type"]
        choices = _ensure_four(answer, _division_type_choices(answer) + ["simple", "compound"])
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_beat_value":
        answer = row["beat_value"]
        choices = _ensure_four(answer, [row["division_value"], "quarter", "dotted quarter", "half", "dotted whole"])
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_division_count":
        answer = str(row["division_count"])
        choices = _ensure_four(answer, [str(row["beat_count"]), str(row["numerator"]), "4", "6", "9", "12"])
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_full_meter":
        answer = full_meter
        choices = _ensure_four(answer, _full_meter_choices(answer))
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "meter_to_ts":
        answer = source_signature
        wrong = [k for k, v in reference_map.items() if v["full_meter"] != full_meter and k != source_signature]
        choices = _ensure_four(answer, wrong)
        prompt = {"kind": "meter_label", "text": full_meter}
    else:
        raise ValueError(f"Unsupported subtype: {subtype}")

    return {
        "subtype": subtype,
        "prompt": prompt,
        "choices": choices,
        "answer": answer,
        "correct_index": choices.index(answer),
        "source_signature": source_signature,
        "explanation": f"{source_signature} maps to {full_meter}.",
        "tags": ["unit:2", f"unit:2_{subtype}"],
    }


def build_symbolic_problem_set(manifest_rows):
    ref = {row["time_signature"]: row for row in load_reference_rows()}
    return [build_symbolic_problem(row["subtype"], row["source_signature"], ref) for row in manifest_rows]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_symbolic_meter_questions -v 2
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/data/unit2_symbolic_drill_manifest.json apps/exercises/symbolic_meter_questions.py apps/exercises/tests/test_symbolic_meter_questions.py
git commit -m "feat: build Unit 2 symbolic meter question sets"
```

### Task 3: Add a Sanctioned UMTO-Backed Wrapper for Symbolic Meter Exercises

**Files:**
- Modify: `apps/exercises/umto.py`
- Modify: `apps/exercises/umto_factory.py`
- Create: `apps/exercises/management/commands/generate_unit2_meter_exercises.py`
- Test: `apps/exercises/tests/test_symbolic_meter_questions.py`

- [ ] **Step 1: Add the failing backend exercise-creation test**

Append to `apps/exercises/tests/test_symbolic_meter_questions.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.management.commands.generate_unit2_meter_reference import build_reference_entry
from apps.exercises.symbolic_meter_questions import build_symbolic_problem
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_symbolic_exercise


class SymbolicMeterExerciseSaveTests(TestCase):
    def test_save_umto_symbolic_exercise_creates_umto_wrapped_payload(self):
        user = get_user_model().objects.create_user("meter@example.com", "meter@example.com", "pw")
        ref = {"6/4": build_reference_entry("6/4")}
        problem = build_symbolic_problem("ts_to_full_meter", "6/4", ref)
        exercise = save_umto_symbolic_exercise(
            description="Unit 2 meter question set",
            author=user,
            problems=[problem],
            source="Unit 2 symbolic meter questions",
            unit=2,
        )
        self.assertTrue(exercise.data["isUMTO"])
        self.assertEqual(exercise.data["type"], "umto_symbolic_meter")
        self.assertEqual(exercise.data["mode"], InteractionMode.IDENTIFICATION.value)
        self.assertEqual(exercise.data["problems"][0]["answer"], "compound duple")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_symbolic_meter_questions.SymbolicMeterExerciseSaveTests -v 2
```

Expected:

```text
ImportError for save_umto_symbolic_exercise
```

- [ ] **Step 3: Implement the symbolic UMTO wrapper and seeding command**

Modify `apps/exercises/umto.py`:

```python
class InteractionMode(str, Enum):
    IDENTIFICATION = "identification"
    PLAYBACK = "playback"
    ANALYSIS_MATCH = "analysis_match"
    SYMBOLIC_IDENTIFICATION = "symbolic_identification"
```

Modify `apps/exercises/umto_factory.py` by adding a helper:

```python
def save_umto_symbolic_exercise(
    *,
    description: str,
    author,
    problems: list[dict],
    source: str,
    unit: int = 2,
    is_public: bool = True,
):
    payload = {
        "type": "umto_symbolic_meter",
        "isUMTO": True,
        "mode": InteractionMode.IDENTIFICATION.value,
        "analysisType": "unit2_symbolic_meter",
        "inputMode": "dropdown",
        "staffDistribution": "none",
        "complexity_score": unit,
        "key": "C",
        "meter": "4/4",
        "clef": "treble",
        "introText": source,
        "reviewText": "Well done!",
        "allowed_answers": [],
        "problems": problems,
        "score": {
            "meta": {
                "key": "C",
                "time": "4/4",
                "clef": "treble",
                "staffDistribution": "none",
            },
            "measures": [],
            "umto": UMTO(
                metadata=Metadata(
                    exercise_id="TEMP",
                    source=source,
                    key="C",
                    meter="4/4",
                    clef="treble",
                    complexity_score=unit,
                    mode=InteractionMode.IDENTIFICATION,
                    unit=unit,
                ),
                voices=Voices(),
                analysis=[],
                grading=[],
            ).model_dump(),
        },
        "grading": [],
    }
    UMTO.model_validate(payload["score"]["umto"])
    ex = Exercise(
        description=description,
        data=payload,
        authored_by=author,
        is_public=is_public,
        skill_tags=["unit:2", "unit:2_rhythm", "unit:2_meter_simple", "unit:2_meter_compound"],
        complexity=unit,
    )
    ex.save()
    payload["exerciseId"] = ex.id
    payload["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.data = payload
    ex.save(update_fields=["data"])
    return ex
```

Create `apps/exercises/management/commands/generate_unit2_meter_exercises.py`:

```python
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.symbolic_meter_questions import build_symbolic_problem_set, load_manifest_rows
from apps.exercises.umto_factory import save_umto_symbolic_exercise


class Command(BaseCommand):
    help = "Create Unit 2 symbolic meter exercises from the curated manifest"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        problems = build_symbolic_problem_set(load_manifest_rows())
        ex = save_umto_symbolic_exercise(
            description="Unit 2 symbolic meter questions",
            author=author,
            problems=problems,
            source="Unit 2 symbolic meter questions",
            unit=2,
        )
        self.stdout.write(self.style.SUCCESS(f"Created {ex.id}"))
```

- [ ] **Step 4: Run the targeted backend test**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_symbolic_meter_questions.SymbolicMeterExerciseSaveTests -v 2
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_factory.py apps/exercises/management/commands/generate_unit2_meter_exercises.py apps/exercises/tests/test_symbolic_meter_questions.py
git commit -m "feat: add UMTO-backed symbolic meter exercises"
```

### Task 4: Parse and Render Symbolic Meter Questions in the Frontend

**Files:**
- Create: `lab/static/js/src/components/music/symbolic_question_sheet.js`
- Create: `lab/static/js/src/models/symbolic_meter_rendering_logic.js`
- Create: `lab/static/js/src/models/symbolic_meter_rendering_logic.test.js`
- Modify: `lab/static/js/src/models/exercise_definition.js`
- Modify: `lab/static/js/src/components/app/exercise.js`
- Modify: `lab/static/css/harmony.css`
- Modify: `lab/templates/exercise.html`

- [ ] **Step 1: Write the failing frontend logic test**

Create `lab/static/js/src/models/symbolic_meter_rendering_logic.test.js`:

```javascript
"use strict";

var logic = require("./symbolic_meter_rendering_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, actual, expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "stacked time signature markup keeps numerator and denominator separate",
  logic.renderTimeSignatureMarkup("12/16"),
  '<span class="meter-ts"><span class="meter-ts-top">12</span><span class="meter-ts-bottom">16</span></span>'
);

assertEqual(
  "music font stack begins with SMuFL-capable family",
  logic.getTimeSignatureFontStack().split(",")[0],
  '"Bravura Text"'
);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node lab/static/js/src/models/symbolic_meter_rendering_logic.test.js
```

Expected:

```text
Error: Cannot find module './symbolic_meter_rendering_logic'
```

- [ ] **Step 3: Implement renderer helper, symbolic sheet, and parse path**

Create `lab/static/js/src/models/symbolic_meter_rendering_logic.js`:

```javascript
"use strict";

function getTimeSignatureFontStack() {
  return '"Bravura Text","Finale Maestro Text","Petaluma Script","Noto Music",serif';
}

function renderTimeSignatureMarkup(text) {
  var parts = String(text).split("/");
  if (parts.length !== 2) return text;
  return '<span class="meter-ts"><span class="meter-ts-top">' + parts[0] +
    '</span><span class="meter-ts-bottom">' + parts[1] + '</span></span>';
}

module.exports = {
  getTimeSignatureFontStack: getTimeSignatureFontStack,
  renderTimeSignatureMarkup: renderTimeSignatureMarkup
};
```

Create `lab/static/js/src/components/music/symbolic_question_sheet.js`:

```javascript
define(["jquery", "lodash"], function ($, _) {
  var SymbolicQuestionSheet = function (settings) {
    this.settings = settings || {};
    this.exerciseContext = this.settings.exerciseContext;
  };

  _.extend(SymbolicQuestionSheet.prototype, {
    renderTo: function (el) {
      var definition = this.exerciseContext.getDefinition();
      var problems = definition.getProblems();
      var $el = $(el);
      $el.empty().addClass("symbolic-meter-area");
      _.each(problems, function (problem, idx) {
        var $card = $('<div class="symbolic-meter-card"></div>');
        $card.append($('<div class="symbolic-meter-prompt"></div>').html(problem.promptHtml || problem.prompt.text));
        var $choices = $('<div class="symbolic-meter-choices"></div>');
        _.each(problem.choices, function (choice) {
          var $btn = $('<button type="button" class="symbolic-meter-choice"></button>').text(choice);
          $btn.on("click", function () {
            this.exerciseContext.grader.setAnswer(idx, choice);
            this.exerciseContext.trigger("change");
          }.bind(this));
          $choices.append($btn);
        }.bind(this));
        $card.append($choices);
        $el.append($card);
      }.bind(this));
    }
  });

  return SymbolicQuestionSheet;
});
```

Modify `lab/static/js/src/models/exercise_definition.js`:

```javascript
isSymbolicMeterQuestion: function () {
  return this.exercise.type === "umto_symbolic_meter";
},
```

and in `parse()` add:

```javascript
if (definition.type === "umto_symbolic_meter") {
  exercise.type = definition.type;
  exercise.isUMTO = true;
  exercise.mode = definition.mode || "identification";
  exercise.analysisType = definition.analysisType || "unit2_symbolic_meter";
  exercise.inputMode = "dropdown";
  exercise.introText = definition.introText || "";
  exercise.reviewText = definition.reviewText || "Well done!";
  exercise.problems = _.map(definition.problems || [], function (problem) {
    return _.assign({}, problem, {
      promptHtml: problem.prompt && problem.prompt.kind === "time_signature"
        ? require("app/models/symbolic_meter_rendering_logic").renderTimeSignatureMarkup(problem.prompt.text)
        : (problem.prompt ? problem.prompt.text : "")
    });
  });
  return exercise;
}
```

Modify `lab/static/js/src/components/app/exercise.js` to skip `MusicComponent` for symbolic meter and render the new sheet directly:

```javascript
function () {
  var definition = this.models.exerciseContext.getDefinition();
  if (definition.isSymbolicMeterQuestion && definition.isSymbolicMeterQuestion()) {
    var c = new SymbolicQuestionSheet({
      exerciseContext: this.models.exerciseContext
    });
    c.renderTo("#staff-area");
    this.addComponent(c);
    return;
  }
  var c = new MusicComponent({
    el: $("#staff-area"),
    sheet: new ExerciseSheetComponent({
      exerciseContext: this.models.exerciseContext,
      keySignature: this.models.keySignature,
      midiDevice: this.models.midiDevice,
    }),
    analysisSettings: definition.getAnalysisSettings(),
    staffDistribution: definition.getStaffDistribution(),
    highlightSettings: definition.getHighlightSettings(),
  });
  c.init(this);
  c.render([]);
  this.addComponent(c);
},
```

Modify `lab/static/css/harmony.css`:

```css
.meter-ts {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 0.9;
  font-family: "Bravura Text","Finale Maestro Text","Petaluma Script","Noto Music",serif;
  font-size: 54px;
}

.meter-ts-top,
.meter-ts-bottom {
  display: block;
}

.symbolic-meter-area {
  max-width: 760px;
  margin: 24px auto;
}

.symbolic-meter-card {
  background: #fff;
  border: 1px solid #d8dee9;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
}

.symbolic-meter-choices {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}
```

- [ ] **Step 4: Run the frontend logic test**

Run:

```bash
node lab/static/js/src/models/symbolic_meter_rendering_logic.test.js
```

Expected:

```text
PASS
PASS
```

- [ ] **Step 5: Smoke-test in the browser with a seeded exercise**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py generate_unit2_meter_exercises --author avner-local2025@localhost
```

Expected:

```text
Created E...
```

Then open the created exercise in the app and verify:
- stacked time signature prompt uses the music font
- no staff is rendered
- four answer buttons render
- choosing an answer updates the identification grader state

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/components/music/symbolic_question_sheet.js lab/static/js/src/models/symbolic_meter_rendering_logic.js lab/static/js/src/models/symbolic_meter_rendering_logic.test.js lab/static/js/src/models/exercise_definition.js lab/static/js/src/components/app/exercise.js lab/static/css/harmony.css lab/templates/exercise.html
git commit -m "feat: render symbolic Unit 2 meter questions"
```

### Task 5: Add End-to-End Backend/Frontend Safeguards

**Files:**
- Modify: `apps/exercises/tests/test_symbolic_meter_questions.py`
- Modify: `lab/static/js/src/models/symbolic_meter_rendering_logic.test.js`

- [ ] **Step 1: Add a regression test that the management command creates a valid exercise**

Append to `apps/exercises/tests/test_symbolic_meter_questions.py`:

```python
from django.core.management import call_command


class GenerateUnit2MeterExercisesCommandTests(TestCase):
    def test_command_creates_symbolic_umto_exercise(self):
        user = get_user_model().objects.create_user("seed@example.com", "seed@example.com", "pw")
        call_command("generate_unit2_meter_reference")
        call_command("generate_unit2_meter_exercises", author=user.email)
        ex = Exercise.objects.latest("created")
        self.assertEqual(ex.data["type"], "umto_symbolic_meter")
        self.assertTrue(ex.data["isUMTO"])
        self.assertGreater(len(ex.data["problems"]), 0)
```

- [ ] **Step 2: Run the test to verify it passes**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_symbolic_meter_questions.GenerateUnit2MeterExercisesCommandTests -v 2
```

Expected:

```text
OK
```

- [ ] **Step 3: Add a JS regression for non-time-signature prompts**

Append to `lab/static/js/src/models/symbolic_meter_rendering_logic.test.js`:

```javascript
assertEqual(
  "non time-signature labels pass through unchanged",
  logic.renderTimeSignatureMarkup("compound triple"),
  "compound triple"
);
```

- [ ] **Step 4: Run the JS regression**

Run:

```bash
node lab/static/js/src/models/symbolic_meter_rendering_logic.test.js
```

Expected:

```text
PASS
PASS
PASS
```

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/tests/test_symbolic_meter_questions.py lab/static/js/src/models/symbolic_meter_rendering_logic.test.js
git commit -m "test: cover Unit 2 symbolic meter exercise pipeline"
```

## Self-Review

**Spec coverage**
- Reference dataset generation: Task 1
- Canonical JSON + validation: Task 1
- Symbolic question JSON shape and deterministic choice generation: Task 2
- Generated vs hand-authored decision: Task 2 resolves this as hybrid
  - generated canonical reference dataset
  - curated hand-authored drill manifest
- UMTO-only exercise creation path: Task 3
- Score-less symbolic renderer: Task 4
- Proper music font / SMuFL-first stack for time signatures: Task 4
- End-to-end seeding and regression coverage: Task 5

**Placeholder scan**
- No `TODO` / `TBD` markers
- Every code-changing step includes a concrete snippet
- Every verification step includes an exact command

**Type consistency**
- Canonical runtime type is `umto_symbolic_meter`
- Canonical family string is `unit2_symbolic_meter`
- Reference dataset fields are `grouping`, `division_type`, `beat_value`, `division_value`
- Management commands are `generate_unit2_meter_reference` and `generate_unit2_meter_exercises`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-04-unit2-meter-questions.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
