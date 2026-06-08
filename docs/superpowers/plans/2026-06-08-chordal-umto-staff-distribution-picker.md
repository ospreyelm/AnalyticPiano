# Chordal UMTO Staff Distribution Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers choose and persist staff distribution for chordal UMTO exercises, and make preview/student rendering honor the selected dashboard token.

**Architecture:** Keep dashboard detection and persistence inside `ExerciseForm`, using `score.umto.metadata.score_kind == "chordal"` as the boundary between chordal UMTO and SATB chorale UMTO. Extract chordal staff-routing logic from `exercise_sheet.js` into a small testable JavaScript helper, then call that helper from the existing chordal UMTO conversion path. Preserve existing persisted tokens and top-level `data.staffDistribution` compatibility.

**Tech Stack:** Django `ModelForm` / Django test runner, HarmonyLab UMTO factory helpers, RequireJS/AMD JavaScript, direct Node-based JS tests matching `barline_player_logic.test.js`.

---

## File Structure

- Modify: `apps/exercises/forms.py`
  - Detect chordal UMTO, initialize `staff_distribution` from UMTO metadata, and persist the selected value to both UMTO metadata and the top-level mirror.
- Create: `apps/exercises/tests/test_exercise_form_chordal_staff_distribution.py`
  - Direct `DashboardExerciseForm` tests for chordal UMTO visibility/persistence and SATB voices-kind regression.
- Create: `lab/static/js/src/components/music/chordal_umto_staff_distribution.js`
  - Testable staff-routing helper for chordal UMTO render-time conversion.
- Create: `lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js`
  - Direct Node tests for the helper, using the repo's existing no-framework JS test style.
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`
  - Add the helper as an AMD dependency and use it inside `_convertChordalUMTOToProcessedScore()`.
- Reference: `docs/superpowers/specs/2026-06-08-chordal-umto-staff-distribution-design.md`
  - Source of truth for scope and token behavior.

---

## Task 1: Add Failing Backend Form Tests

**Files:**
- Create: `apps/exercises/tests/test_exercise_form_chordal_staff_distribution.py`

- [ ] **Step 1: Create the failing test module**

Create `apps/exercises/tests/test_exercise_form_chordal_staff_distribution.py`:

```python
import copy
import json

from django.forms.widgets import HiddenInput
from django.test import TestCase

from apps.accounts.models import User
from apps.dashboard.forms import DashboardExerciseForm
from apps.exercises.models import Exercise
from apps.exercises.tests.umto_test_helpers import make_umto_exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import build_chordal_umto_payload


class ChordalUMTOStaffDistributionFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="teacher@example.com",
            password="pw",
        )

    def _create_chordal_exercise(self, staff_distribution="grandStaff"):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal staff distribution fixture",
            key="C",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [48, 60, 64]},
            ],
            analysis=[],
        )
        payload["score"]["umto"]["metadata"]["staffDistribution"] = staff_distribution
        payload["staffDistribution"] = "keyboard"
        return Exercise.objects.create(
            description="Chordal UMTO",
            data=payload,
            authored_by=self.user,
            complexity=1,
            skill_tags=["unit:1"],
        )

    def _post_data(self, exercise, *, staff_distribution):
        return {
            "description": exercise.description,
            "is_public": "on" if exercise.is_public else "",
            "tags": exercise.tags,
            "rhythm": exercise.rhythm or "",
            "visibility_pattern": "",
            "time_signature": "",
            "semibreves_per_line": "",
            "intro_text": exercise.data.get("introText", ""),
            "type": "umto_chorale",
            "staff_distribution": staff_distribution,
            "chorale_mode": exercise.data.get("mode", "play-all-voices"),
            "chorale_label_mode": "none",
            "chorale_transpose": "",
            "chorale_tempo": "60",
            "chorale_onset_window_ms": "150",
            "chorale_release_tolerance_pct": "40",
            "chorale_chord_member_min": "",
            "chorale_excerpt_start": "",
            "chorale_excerpt_end": "",
            "ident_mode": "submit",
            "compound_intervals": "",
            "data": json.dumps(exercise.data),
        }

    def test_chordal_umto_exposes_staff_distribution_from_metadata(self):
        exercise = self._create_chordal_exercise(staff_distribution="LH")

        form = DashboardExerciseForm(instance=exercise)

        field = form.fields["staff_distribution"]
        self.assertNotIsInstance(field.widget, HiddenInput)
        self.assertEqual(field.initial, "LH")
        self.assertNotIn("chorale", [value for value, _label in field.choices])

    def test_chordal_umto_staff_distribution_save_updates_metadata_and_mirror(self):
        exercise = self._create_chordal_exercise(staff_distribution="keyboard")
        form = DashboardExerciseForm(
            data=self._post_data(exercise, staff_distribution="RH"),
            instance=exercise,
        )
        form.context = {"user": self.user}

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()

        saved.refresh_from_db()
        metadata = saved.data["score"]["umto"]["metadata"]
        self.assertEqual(metadata["staffDistribution"], "RH")
        self.assertEqual(saved.data["staffDistribution"], "RH")

    def test_chordal_umto_initial_falls_back_to_top_level_then_keyboard(self):
        exercise = self._create_chordal_exercise(staff_distribution="LH")
        metadata = exercise.data["score"]["umto"]["metadata"]
        metadata.pop("staffDistribution", None)
        exercise.data["staffDistribution"] = "grandStaff"
        exercise.save()

        form = DashboardExerciseForm(instance=exercise)
        self.assertEqual(form.fields["staff_distribution"].initial, "grandStaff")

        exercise.data["staffDistribution"] = ""
        exercise.save()
        form = DashboardExerciseForm(instance=exercise)
        self.assertEqual(form.fields["staff_distribution"].initial, "keyboard")

    def test_voices_kind_umto_still_hides_staff_distribution_and_forces_chorale(self):
        exercise = make_umto_exercise(
            author=self.user,
            description="SATB UMTO",
            complexity=1,
            unit=1,
        )
        form = DashboardExerciseForm(instance=exercise)
        self.assertIsInstance(form.fields["staff_distribution"].widget, HiddenInput)
        self.assertEqual(form.fields["staff_distribution"].initial, "chorale")

        posted = self._post_data(exercise, staff_distribution="RH")
        posted["data"] = json.dumps(copy.deepcopy(exercise.data))
        form = DashboardExerciseForm(data=posted, instance=exercise)
        form.context = {"user": self.user}

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()

        saved.refresh_from_db()
        self.assertEqual(saved.data["staffDistribution"], "chorale")
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_exercise_form_chordal_staff_distribution -v 2
```

Expected: at least `test_chordal_umto_exposes_staff_distribution_from_metadata` fails because the current chorale branch hides `staff_distribution` and forces initial value `"chorale"`.

---

## Task 2: Implement Chordal UMTO Form Detection And Persistence

**Files:**
- Modify: `apps/exercises/forms.py`
- Test: `apps/exercises/tests/test_exercise_form_chordal_staff_distribution.py`

- [ ] **Step 1: Add chordal UMTO state during form initialization**

In `ExerciseForm.__init__()`, after `self._is_chorale = self._detect_chorale()`, add:

```python
self._is_chordal_umto = self._detect_chordal_umto()
```

The initialization block should keep the generic top-level fallback, but `_configure_chorale_fields()` will override it for chordal UMTO:

```python
self.fields["staff_distribution"].initial = self.instance.data.get(
    "staffDistribution", self.DISTRIBUTION_KEYBOARD
)
```

- [ ] **Step 2: Add metadata and detection helpers**

In the chorale helpers section of `apps/exercises/forms.py`, before `_configure_chorale_fields()`, add:

```python
def _get_chordal_umto_metadata(self):
    data = self.instance.data if self.instance and getattr(self.instance, "data", None) else {}
    score = data.get("score", {}) if isinstance(data, dict) else {}
    umto = score.get("umto", {}) if isinstance(score, dict) else {}
    metadata = umto.get("metadata", {}) if isinstance(umto, dict) else {}
    return metadata if isinstance(metadata, dict) else {}

def _detect_chordal_umto(self):
    data = self.instance.data if self.instance and getattr(self.instance, "data", None) else {}
    if not isinstance(data, dict):
        return False
    if data.get("isUMTO") is not True:
        return False
    if data.get("type") != self.TYPE_UMTO_CHORALE:
        return False
    return self._get_chordal_umto_metadata().get("score_kind") == "chordal"
```

- [ ] **Step 3: Add the chordal field configuration helper**

Add this helper near `_configure_chorale_fields()`:

```python
def _configure_chordal_umto_fields(self):
    for field in self.CHORALE_SUPPRESSED_FIELDS:
        if field in self.fields:
            self.fields[field].widget = forms.HiddenInput()

    for field in self.CHORALE_ONLY_FIELDS:
        if field in self.fields and field != "staff_distribution":
            self.fields[field].widget = forms.HiddenInput()

    metadata = self._get_chordal_umto_metadata()
    selected = (
        metadata.get("staffDistribution")
        or (self.instance.data or {}).get("staffDistribution")
        or self.DISTRIBUTION_KEYBOARD
    )
    if "staff_distribution" in self.fields:
        field = self.fields["staff_distribution"]
        field.choices = tuple(
            choice for choice in self.DISTRIBUTION_CHOICES
            if choice[0] != self.DISTRIBUTION_CHORALE
        )
        field.initial = selected if selected != self.DISTRIBUTION_CHORALE else self.DISTRIBUTION_KEYBOARD
```

- [ ] **Step 4: Branch early in `_configure_chorale_fields()`**

Change `_configure_chorale_fields()` so chordal UMTO exits before SATB voice setup:

```python
def _configure_chorale_fields(self):
    if not self._is_chorale:
        for field in self.CHORALE_ONLY_FIELDS:
            if field in self.fields:
                self.fields[field].widget = forms.HiddenInput()
        return

    if self._is_chordal_umto:
        self._configure_chordal_umto_fields()
        return

    # existing SATB chorale behavior continues here
```

- [ ] **Step 5: Add chordal persistence helper**

Add this helper before `_store_chorale_settings()`:

```python
def _store_chordal_umto_settings(self, instance):
    data = instance.data
    score = data.setdefault("score", {})
    umto = score.setdefault("umto", {})
    metadata = umto.setdefault("metadata", {})
    selected = self.cleaned_data.get("staff_distribution") or self.DISTRIBUTION_KEYBOARD
    metadata["staffDistribution"] = selected
    data["staffDistribution"] = selected
    data["type"] = self.cleaned_data.get("type") or data.get("type") or self.TYPE_UMTO_CHORALE
```

- [ ] **Step 6: Use the chordal persistence helper in `save()`**

Change the chorale save branch from:

```python
if self._is_chorale:
    self._store_chorale_settings(instance)
```

to:

```python
if self._is_chorale:
    if self._is_chordal_umto:
        self._store_chordal_umto_settings(instance)
    else:
        self._store_chorale_settings(instance)
```

- [ ] **Step 7: Run focused backend tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_exercise_form_chordal_staff_distribution -v 2
```

Expected: all tests in `test_exercise_form_chordal_staff_distribution` pass.

- [ ] **Step 8: Commit backend form work**

Run:

```bash
git add apps/exercises/forms.py apps/exercises/tests/test_exercise_form_chordal_staff_distribution.py
git commit -m "feat: persist chordal UMTO staff distribution"
```

---

## Task 3: Extract And Test Chordal UMTO Staff Routing

**Files:**
- Create: `lab/static/js/src/components/music/chordal_umto_staff_distribution.js`
- Create: `lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js`

- [ ] **Step 1: Create the failing JS tests**

Create `lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js`:

```javascript
"use strict";

var logic = require("./chordal_umto_staff_distribution");
var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    console.log("  PASS: " + label);
    pass++;
  } else {
    console.log("  FAIL: " + label);
    console.log("       got: " + JSON.stringify(actual));
    console.log("  expected: " + JSON.stringify(expected));
    fail++;
  }
}

console.log("\nchordal UMTO staff distribution:");

assertEqual(
  "LH routes every pitch to bass",
  logic.routeChordMidis([48, 60, 72], "LH"),
  { treble: [], bass: [48, 60, 72] }
);

assertEqual(
  "RH routes every pitch to treble",
  logic.routeChordMidis([48, 60, 72], "RH"),
  { treble: [48, 60, 72], bass: [] }
);

assertEqual(
  "grandStaff splits at middle C",
  logic.routeChordMidis([48, 60, 72], "grandStaff"),
  { treble: [60, 72], bass: [48] }
);

assertEqual(
  "keyboard keeps mixed register grand-staff routing",
  logic.routeChordMidis([48, 60, 64], "keyboard"),
  { treble: [60, 64], bass: [48] }
);

assertEqual(
  "keyboard moves lowest note to bass when all notes are high",
  logic.routeChordMidis([60, 64, 67], "keyboard"),
  { treble: [64, 67], bass: [60] }
);

assertEqual(
  "keyboardPlusRHBias routes non-keyboard-style chords below G3 to bass",
  logic.routeChordMidis([52, 55, 59, 62, 65], "keyboardPlusRHBias"),
  { treble: [55, 59, 62, 65], bass: [52] }
);

assertEqual(
  "keyboardPlusLHBias routes non-keyboard-style chords through F4 to bass",
  logic.routeChordMidis([52, 55, 59, 62, 65], "keyboardPlusLHBias"),
  { treble: [], bass: [52, 55, 59, 62, 65] }
);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] **Step 2: Run JS tests and verify failure**

Run:

```bash
node lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js
```

Expected: fails with `Cannot find module './chordal_umto_staff_distribution'`.

- [ ] **Step 3: Implement the staff-routing helper**

Create `lab/static/js/src/components/music/chordal_umto_staff_distribution.js`:

```javascript
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.ChordalUMTOStaffDistribution = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var HIGH_THRESHOLD = 65;
  var MID_THRESHOLD = 60;
  var LOW_THRESHOLD = 55;
  var KEYBOARD_STYLE_COUNTS = [3, 4];
  var KEYBOARD_FAMILY = ["keyboard", "keyboardPlusRHBias", "keyboardPlusLHBias"];

  function includes(list, value) {
    return list.indexOf(value) !== -1;
  }

  function sortedMidis(midis) {
    return (midis || []).slice().sort(function (a, b) {
      return a - b;
    });
  }

  function splitByThreshold(notes, threshold, includeThresholdInBass) {
    var treble = [];
    var bass = [];
    notes.forEach(function (midi) {
      var belongsToBass = includeThresholdInBass ? midi <= threshold : midi < threshold;
      if (belongsToBass) bass.push(midi);
      else treble.push(midi);
    });
    return { treble: treble, bass: bass };
  }

  function keyboardStyleSplit(notes) {
    var treble = [];
    var bass = [];
    notes.forEach(function (midi, index) {
      if (index === 0) {
        if (midi <= HIGH_THRESHOLD) bass.push(midi);
        else treble.push(midi);
      } else if (midi < LOW_THRESHOLD) {
        bass.push(midi);
      } else {
        treble.push(midi);
      }
    });
    return { treble: treble, bass: bass };
  }

  function routeChordMidis(midis, staffDistribution) {
    var dist = staffDistribution || "keyboard";
    var notes = sortedMidis(midis);

    if (dist === "LH" || dist === "bass") {
      return { treble: [], bass: notes };
    }
    if (dist === "RH" || dist === "treble") {
      return { treble: notes, bass: [] };
    }
    if (dist === "grandStaff") {
      return splitByThreshold(notes, MID_THRESHOLD, false);
    }
    if (includes(KEYBOARD_FAMILY, dist) && includes(KEYBOARD_STYLE_COUNTS, notes.length)) {
      return keyboardStyleSplit(notes);
    }
    if (dist === "keyboardPlusRHBias") {
      return splitByThreshold(notes, LOW_THRESHOLD, false);
    }
    if (dist === "keyboardPlusLHBias") {
      return splitByThreshold(notes, HIGH_THRESHOLD, true);
    }
    return splitByThreshold(notes, MID_THRESHOLD, false);
  }

  return {
    routeChordMidis: routeChordMidis,
  };
});
```

- [ ] **Step 4: Run JS tests and verify pass**

Run:

```bash
node lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js
```

Expected: prints `7 passed, 0 failed`.

- [ ] **Step 5: Commit helper and tests**

Run:

```bash
git add lab/static/js/src/components/music/chordal_umto_staff_distribution.js lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js
git commit -m "test: cover chordal UMTO staff routing"
```

---

## Task 4: Use Staff Routing Helper In Chordal UMTO Rendering

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`
- Test: `lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js`

- [ ] **Step 1: Add the AMD dependency**

In `lab/static/js/src/components/music/exercise_sheet.js`, add the dependency after `app/models/chordal_problems_logic`:

```javascript
"./chordal_umto_staff_distribution",
```

Add the matching factory argument after `ChordalProblemsLogic`:

```javascript
ChordalUMTOStaffDistribution
```

- [ ] **Step 2: Replace inline chordal staff split logic**

Inside `_convertChordalUMTOToProcessedScore()`, keep:

```javascript
var dist = meta.staffDistribution || "keyboard";
```

Replace:

```javascript
// Decide which staves are active.
var forceTreble = dist === "treble";
var forceBass = dist === "bass";
```

with:

```javascript
var forceTreble = dist === "RH" || dist === "treble";
var forceBass = dist === "LH" || dist === "bass";
```

Then replace the `hi` / `lo` assignment block inside `_.each(umto.chords, function (c) { ... })` with:

```javascript
var routed = ChordalUMTOStaffDistribution.routeChordMidis(midis, dist);
hi = routed.treble;
lo = routed.bass;
```

Remove the old local split block:

```javascript
if (forceTreble) { hi = midis; lo = []; }
else if (forceBass) { hi = []; lo = midis; }
else {
  var sorted = midis.slice().sort(function (a, b) { return a - b; });
  hi = sorted.filter(function (m) { return m >= SPLIT; });
  lo = sorted.filter(function (m) { return m < SPLIT; });
  if (lo.length === 0 && hi.length > 1) {
    lo = [hi.shift()];
  } else if (hi.length === 0 && lo.length > 1) {
    hi = [lo.pop()];
  }
}
```

Also remove the now-unused local constant:

```javascript
var SPLIT = 60; // middle C
```

- [ ] **Step 3: Run JS tests**

Run:

```bash
node lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js
```

Expected: prints `7 passed, 0 failed`.

- [ ] **Step 4: Run a syntax smoke check for `exercise_sheet.js` dependencies**

Run:

```bash
node -e "const fs=require('fs'); const s=fs.readFileSync('lab/static/js/src/components/music/exercise_sheet.js','utf8'); if(!s.includes('./chordal_umto_staff_distribution')) process.exit(1); if(!s.includes('ChordalUMTOStaffDistribution.routeChordMidis')) process.exit(1); console.log('exercise_sheet chordal helper wiring present');"
```

Expected: prints `exercise_sheet chordal helper wiring present`.

- [ ] **Step 5: Commit renderer integration**

Run:

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: apply chordal UMTO staff distribution in renderer"
```

---

## Task 5: Final Verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused backend form tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_exercise_form_chordal_staff_distribution -v 2
```

Expected: all tests pass.

- [ ] **Step 2: Run nearby chordal UMTO backend tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_chordal_umto -v 2
```

Expected: all tests pass.

- [ ] **Step 3: Run focused JS tests**

Run:

```bash
node lab/static/js/src/components/music/chordal_umto_staff_distribution.test.js
node lab/static/js/src/barline_player_logic.test.js
```

Expected: both scripts finish with zero failures.

- [ ] **Step 4: Check Django project health**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: only intentional files are modified or the working tree is clean if all task commits were made.
