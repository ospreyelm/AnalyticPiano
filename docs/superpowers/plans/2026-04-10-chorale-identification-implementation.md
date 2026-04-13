# Chorale Identification Exercise Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the new `chorale_identification` exercise type that combines chorale rendering with identification interaction and grading, while preserving existing `chorale` and `identification` behavior.

**Architecture:** Extend exercise parsing to compute identification problems from chorale score onsets client-side using existing timeline and analysis utilities, then reuse the current `IdentificationGrader` and identification popup UI on top of chorale rendering by wiring a `windowIndex -> x` layout map from VexFlow rendering.

**Tech Stack:** Django management commands/admin/forms, RequireJS AMD modules, existing `ScoreTimeline` and `Analyze` utilities, VexFlow canvas rendering.

---

## File Structure

- Modify: `lab/static/js/src/models/exercise_definition.js`
  Responsibility: add `chorale_identification` type, compute per-window `problems` in `parse()`, and expose `isChoraleIdentification()`.
- Modify: `lab/static/js/src/components/app/exercise.js`
  Responsibility: route `chorale_identification` to `IdentificationGrader`.
- Modify: `lab/static/js/src/models/exercise_context.js`
  Responsibility: treat `chorale_identification` as identification grading flow (no chord-bank pointer movement).
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`
  Responsibility: initialize both chorale and identification modes together, use chorale onset slot geometry for popup hit-testing and label drawing.
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
  Responsibility: emit onset window x-positions for rendered columns so labels can align under chorale onsets.
- Modify: `apps/exercises/management/commands/import_chorale.py`
  Responsibility: support `--mode identify` and `--analysis` to create `chorale_identification` records.
- Create: `apps/exercises/management/commands/duplicate_chorale_as_identification.py`
  Responsibility: duplicate an existing chorale exercise into `chorale_identification`.
- Modify: `apps/exercises/forms.py`
  Responsibility: add `TYPE_CHORALE_IDENTIFICATION` and apply identification settings UI/serialization to the new type.
- Modify: `apps/exercises/admin.py`
  Responsibility: show identification settings fieldset for `chorale_identification`.
- Create: `apps/exercises/tests/test_duplicate_chorale_as_identification.py`
  Responsibility: verify the duplicate command creates correct exercise data.

### Task 1: Add Failing Coverage For Duplication Command

**Files:**
- Create: `apps/exercises/tests/test_duplicate_chorale_as_identification.py`

- [ ] **Step 1: Write a failing management-command test**

```python
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Exercise


class DuplicateChoraleAsIdentificationTests(TestCase):
    def test_creates_identification_copy_from_chorale(self):
        author = User.objects.create_user(email="teacher@example.com", password="pw")
        source = Exercise.objects.create(
            authored_by=author,
            is_public=True,
            description="BWV1.6 (mm. 1-4)",
            data={
                "type": "chorale",
                "score": {"meta": {"key": "G", "time": "4/4"}, "measures": [{"staves": {}}]},
                "staffDistribution": "chorale",
                "introText": "Play this excerpt.",
                "reviewText": "Done.",
            },
        )

        call_command(
            "duplicate_chorale_as_identification",
            str(source.id),
            author="teacher@example.com",
            analysis="roman",
        )

        clone = Exercise.objects.exclude(id=source.id).latest("created")
        self.assertEqual(clone.data["type"], "chorale_identification")
        self.assertEqual(clone.data["analysisType"], "roman")
        self.assertEqual(clone.data["identMode"], "submit")
        self.assertEqual(clone.data["score"], source.data["score"])
```

- [ ] **Step 2: Run test to confirm RED state**

Run: `./manage.py test apps.exercises.tests.test_duplicate_chorale_as_identification -v 2`
Expected: FAIL with unknown command or import error for missing file.

- [ ] **Step 3: Commit failing test checkpoint**

```bash
git add apps/exercises/tests/test_duplicate_chorale_as_identification.py
git commit -m "test: add failing duplication command coverage"
```

### Task 2: Implement Backend Creation Paths And Admin Wiring

**Files:**
- Modify: `apps/exercises/management/commands/import_chorale.py`
- Create: `apps/exercises/management/commands/duplicate_chorale_as_identification.py`
- Modify: `apps/exercises/forms.py`
- Modify: `apps/exercises/admin.py`

- [ ] **Step 1: Extend chorale import command arguments and data output**

```python
# import_chorale.py argument additions
parser.add_argument("--mode", choices=["play", "identify"], default="play")
parser.add_argument("--analysis", choices=["roman", "figured_bass"], default="roman")

# identify payload shape
exercise_data = {
    "type": "chorale_identification",
    "identMode": "submit",
    "analysisType": analysis_type,
    "score": {"meta": meta, "measures": excerpt_measures},
    "key": meta.get("key", "C"),
    "staffDistribution": "chorale",
    "introText": f"Label the {analysis_label} for {bwv}, measures {start_measure+1}\u2013{end_measure}.",
    "reviewText": f"Well done! You labeled {bwv}, measures {start_measure+1}\u2013{end_measure}.",
}
```

- [ ] **Step 2: Implement duplicate command**

```python
# duplicate_chorale_as_identification.py core behavior
source = Exercise.objects.get(id=exercise_id)
if source.data.get("type") != "chorale":
    raise CommandError("Source exercise must be type 'chorale'")

new_data = {
    "type": "chorale_identification",
    "identMode": "submit",
    "analysisType": analysis,
    "score": source.data.get("score", {}),
    "key": source.data.get("key") or source.data.get("score", {}).get("meta", {}).get("key", "C"),
    "staffDistribution": "chorale",
    "introText": source.data.get("introText") or "Label each onset.",
    "reviewText": source.data.get("reviewText") or "Well done!",
}
Exercise.objects.create(..., data=new_data)
```

- [ ] **Step 3: Add new type support in forms/admin**

```python
# forms.py constants and detection
TYPE_CHORALE_IDENTIFICATION = "chorale_identification"

def _detect_identification(self):
    ...
    return form_type in (self.TYPE_IDENTIFICATION, self.TYPE_CHORALE_IDENTIFICATION)

# keep type choice visible for existing records
if (self.TYPE_CHORALE_IDENTIFICATION, "Chorale identification") not in choices:
    choices.append((self.TYPE_CHORALE_IDENTIFICATION, "Chorale identification"))

# admin.py fieldset detection
identification = obj.data.get("type") in (
    ExerciseForm.TYPE_IDENTIFICATION,
    ExerciseForm.TYPE_CHORALE_IDENTIFICATION,
)
```

- [ ] **Step 4: Run backend test suite slice**

Run: `./manage.py test apps.exercises.tests.test_duplicate_chorale_as_identification -v 2`
Expected: PASS.

- [ ] **Step 5: Commit backend implementation**

```bash
git add apps/exercises/management/commands/import_chorale.py apps/exercises/management/commands/duplicate_chorale_as_identification.py apps/exercises/forms.py apps/exercises/admin.py apps/exercises/tests/test_duplicate_chorale_as_identification.py
git commit -m "feat: add chorale identification creation workflows"
```

### Task 3: Implement Frontend Type Parsing, Grader Routing, And Chorale Label Geometry

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`
- Modify: `lab/static/js/src/components/app/exercise.js`
- Modify: `lab/static/js/src/models/exercise_context.js`
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`

- [ ] **Step 1: Parse and compute `chorale_identification` problems in ExerciseDefinition**

```javascript
// dependency additions: score_timeline, analyze, key_signature

isChoraleIdentification: function () {
  return this.exercise.type === "chorale_identification";
}

// parse branch
if (definition.type === "chorale_identification") {
  exercise.type = "chorale_identification";
  exercise.score = definition.score || {};
  exercise.analysisType = definition.analysisType || "roman";
  exercise.identMode = definition.identMode || "submit";
  exercise.staffDistribution = "chorale";
  exercise.key = definition.key || convertCIRKeyToHarmonyLabKey((exercise.score.meta || {}).key || "C");
  exercise.keySignature = false;
  exercise.analysis = _.cloneDeep(ANALYSIS_SETTINGS);
  for (var modeKey in exercise.analysis.mode) {
    if (exercise.analysis.mode.hasOwnProperty(modeKey)) {
      exercise.analysis.mode[modeKey] = false;
    }
  }
  exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
  exercise.problems = buildChoraleIdentificationProblems(exercise);
  return exercise;
}
```

- [ ] **Step 2: Route grader selection and context identification checks**

```javascript
// app/exercise.js
} else if ((models.exerciseDefinition.isIdentification && models.exerciseDefinition.isIdentification()) ||
           (models.exerciseDefinition.isChoraleIdentification && models.exerciseDefinition.isChoraleIdentification())) {
  models.exerciseGrader = new IdentificationGrader({});
}

// exercise_context.js
var isIdentificationExercise =
  (typeof this.definition.isIdentification === "function" && this.definition.isIdentification()) ||
  (typeof this.definition.isChoraleIdentification === "function" && this.definition.isChoraleIdentification());
```

- [ ] **Step 3: Expose onset x-layout from VexFlow adapter and consume in exercise sheet**

```javascript
// vexflow_adapter.js option callback
if (opts && typeof opts.onWindowPosition === "function" && typeof matchedIndex === "number") {
  opts.onWindowPosition({
    windowIndex: matchedIndex,
    x: getColumnCenterX(col),
    y: bassStave.getBottomY() + 18,
  });
}

// exercise_sheet.js: render chorale + labels
var isChoraleLike = definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification());

if (isChoraleLike) {
  this._identWindowLayout = {};
  VexFlowAdapter.render(score, this.vexRenderer, {
    ...,
    onWindowPosition: function (slot) {
      self._identWindowLayout[slot.windowIndex] = slot;
    }
  });
  if (definition.isIdentification() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
    this.drawIdentificationLabels();
  }
  return this;
}
```

- [ ] **Step 4: Reuse popup/hit-testing for chorale window slots**

```javascript
// exercise_sheet.js helper
_getIdentificationSlots: function () {
  if (definition.isChoraleIdentification()) {
    return definition.getProblems().map(function (problem, idx) {
      var slot = self._identWindowLayout[idx];
      return slot ? { index: idx, x: slot.x, y: slot.y } : null;
    }).filter(Boolean);
  }
  // existing noteStaves fallback
}
```

- [ ] **Step 5: Run syntax and startup checks**

Run: `./manage.py check`
Expected: `System check identified no issues`.

### Task 4: End-to-End Verification And Regression Guard

**Files:**
- Modify (if needed): any touched files above to fix issues uncovered in verification.

- [ ] **Step 1: Run command-level smoke tests**

Run:
```bash
./manage.py import_chorale data/corpus/bach/bwv1.6.json --author=admin@example.com --start=0 --end=4 --mode identify --analysis roman
./manage.py duplicate_chorale_as_identification <existing_chorale_id> --author=admin@example.com --analysis figured_bass
```
Expected: both commands print success and create new exercise rows.

- [ ] **Step 2: Run automated checks**

Run:
```bash
./manage.py test apps.exercises.tests.test_duplicate_chorale_as_identification -v 2
./manage.py check
```
Expected: tests pass and no Django system-check errors.

- [ ] **Step 3: Manual browser validation**

Validate in UI:
- Open an exercise with `data.type = chorale_identification` and confirm full SATB renders.
- Confirm `?` slots appear under each onset and popup shows exactly 5 choices.
- Confirm `practice`, `submit`, and `test` modes behave like existing identification mode.
- Confirm no regression on existing `chorale` and existing `identification` exercises.

- [ ] **Step 4: Commit frontend implementation**

```bash
git add lab/static/js/src/models/exercise_definition.js lab/static/js/src/components/app/exercise.js lab/static/js/src/models/exercise_context.js lab/static/js/src/components/music/rendering/vexflow_adapter.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: support chorale identification rendering and grading"
```

- [ ] **Step 5: Final verification commit**

```bash
git add -A
git commit -m "test: cover chorale identification command path"
```

## Self-Review

- Spec coverage: includes all required files from the approved spec (`exercise_definition`, `exercise_sheet`, `exercise_context`, `import_chorale`, duplicate command, `admin`) and keeps forbidden files unchanged (`analyze.js`, `identification_grader.js`, `score_timeline.js`).
- Placeholder scan: no `TODO`, `TBD`, or unresolved references remain.
- Type consistency: `chorale_identification` string, `identMode`, and `analysisType` are used consistently across backend and frontend tasks.
