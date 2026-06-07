# Chordal UMTO Score-Kind Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a chordal score-kind to UMTO so ragged / monophonic / chord-on-staff music is stored losslessly as onset verticalities, and let existing legacy `chord[]` exercises load through the UMTO path.

**Architecture:** Additive change to the canonical `UMTO` Pydantic object — a `Metadata.score_kind` discriminator and a top-level `chords: List[ChordEvent]`. Analysis stays in canonical `analysis[]`. The frontend gets a new chordal case at the top of the `umto_chorale` block that populates `exercise.problems` from `chords[]` via a shared, node-testable normalization helper. A backend wrapper lets legacy `data.chord` rows reuse this path. Transpose is out of scope (Spec B).

**Tech Stack:** Python 3.11, Pydantic v2, Django management commands, pytest (`unittest.TestCase`), vanilla-JS logic modules tested with `node *.test.js`.

**Spec:** [docs/superpowers/specs/2026-06-07-chordal-umto-score-kind-design.md](../specs/2026-06-07-chordal-umto-score-kind-design.md)

**Critical ordering note (from review):** Task 5 is the §5a spike (W1 vs W2). It is the first implementation checkpoint after the model/schema tests because the outcome shapes the backend payload, frontend parsing, and later test structure. Do not start Tasks 6+ until Task 5 resolves W1 vs W2.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `apps/exercises/umto.py` | Add `ChordEvent`, `Metadata.score_kind`, `UMTO.chords`, default `voices`, validators | 1–4 |
| `apps/exercises/umto_schema.json` | Regenerated schema (do not hand-edit) | 4 |
| `apps/exercises/tests/test_chordal_umto.py` | All Python model/validator/factory tests | 1–4, 8 |
| `apps/exercises/umto_factory.py` | `build_chordal_umto_payload` + `save_chordal_umto_exercise` | 8 |
| `docs/superpowers/plans/spike-5a-window-source.md` | Spike findings + W1/W2 decision (created in Task 5) | 5 |
| `lab/static/js/src/models/chordal_problems_logic.js` | Shared chord→`{visible,hidden,notes}` normalization (node-testable) | 6 |
| `lab/static/js/src/models/chordal_problems_logic.test.js` | Tests for the helper | 6 |
| `lab/static/js/src/models/exercise_definition.js` | Chordal case at top of `umto_chorale` block | 7 |
| `apps/exercises/umto.py` (`to_frontend_payload`) and/or `lab/views.py` | Chordal payload + legacy wrapper | 5 (decides), 9, 10 |
| `docs/UMTO_GUIDE.md` | Document the chordal score-kind | 11 |

---

## Task 1: `ChordEvent` model

**Files:**
- Modify: `apps/exercises/umto.py` (add `ChordEvent` after `VoiceEvent`, ~line 50)
- Test: `apps/exercises/tests/test_chordal_umto.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# apps/exercises/tests/test_chordal_umto.py
from unittest import TestCase
from pydantic import ValidationError
from apps.exercises.umto import ChordEvent


class TestChordEvent(TestCase):
    def test_minimal_chord(self):
        c = ChordEvent(offset=0.0, duration=1.0, visible=[60, 64, 67])
        self.assertEqual(c.visible, [60, 64, 67])
        self.assertEqual(c.hidden, [])
        self.assertIsNone(c.spelling)

    def test_input_order_preserved(self):
        # bass-first ordering must NOT be sorted
        c = ChordEvent(offset=0.0, duration=1.0, visible=[36, 60, 64])
        self.assertEqual(c.visible, [36, 60, 64])

    def test_spelling_length_must_match_visible_plus_hidden(self):
        with self.assertRaises(ValidationError):
            ChordEvent(offset=0.0, duration=1.0, visible=[60, 64], spelling=["C4"])

    def test_spelling_ok_when_length_matches(self):
        c = ChordEvent(offset=0.0, duration=1.0, visible=[60], hidden=[64],
                       spelling=["C4", "E4"])
        self.assertEqual(c.spelling, ["C4", "E4"])

    def test_negative_offset_rejected(self):
        with self.assertRaises(ValidationError):
            ChordEvent(offset=-1.0, duration=1.0, visible=[60])

    def test_nonpositive_duration_rejected(self):
        with self.assertRaises(ValidationError):
            ChordEvent(offset=0.0, duration=0.0, visible=[60])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py -v`
Expected: FAIL — `ImportError: cannot import name 'ChordEvent'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/exercises/umto.py — insert after the VoiceEvent class
class ChordEvent(BaseModel):
    offset: float = Field(ge=0.0)          # quarter-lengths from start
    duration: float = Field(gt=0.0)         # quarter-lengths
    visible: List[int] = Field(default_factory=list)  # MIDI pitches sounding
    hidden: List[int] = Field(default_factory=list)   # MIDI pitches not shown
    spelling: Optional[List[str]] = None    # positional: visible then hidden

    @model_validator(mode="after")
    def validate_spelling_length(self):
        if self.spelling is not None:
            expected = len(self.visible) + len(self.hidden)
            if len(self.spelling) != expected:
                raise ValueError(
                    f"spelling length {len(self.spelling)} must equal "
                    f"visible+hidden length {expected}"
                )
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/tests/test_chordal_umto.py
git commit -m "feat(umto): add ChordEvent model with spelling-length validation"
```

---

## Task 2: `Metadata.score_kind` discriminator

**Files:**
- Modify: `apps/exercises/umto.py` (`Metadata`, ~line 105)
- Test: `apps/exercises/tests/test_chordal_umto.py`

- [ ] **Step 1: Write the failing test**

```python
# append to test_chordal_umto.py
from apps.exercises.umto import Metadata


class TestScoreKind(TestCase):
    def _meta(self, **kw):
        base = dict(exercise_id="T", source="t", key="C", meter="4/4",
                    complexity_score=1)
        base.update(kw)
        return Metadata(**base)

    def test_default_is_voices(self):
        self.assertEqual(self._meta().score_kind, "voices")

    def test_chordal_allowed(self):
        self.assertEqual(self._meta(score_kind="chordal").score_kind, "chordal")

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValidationError):
            self._meta(score_kind="bogus")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestScoreKind -v`
Expected: FAIL — `Metadata` has no `score_kind` (extra field ignored or AttributeError)

- [ ] **Step 3: Write minimal implementation**

```python
# apps/exercises/umto.py — add to Metadata, near input_mode
    score_kind: Literal["voices", "chordal"] = "voices"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestScoreKind -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/tests/test_chordal_umto.py
git commit -m "feat(umto): add Metadata.score_kind discriminator (default voices)"
```

---

## Task 3: `UMTO.chords` + cross-field validator (chordal requires chords; voices-kind requires explicit voices)

**Files:**
- Modify: `apps/exercises/umto.py` (`UMTO`, ~line 152+)
- Test: `apps/exercises/tests/test_chordal_umto.py`

This is the validator from spec §4. `voices` becomes optional via `default_factory`, but a `voices`-kind payload that *omits* `voices` must still be rejected — detected with Pydantic v2 `model_fields_set`.

- [ ] **Step 1: Write the failing test**

```python
# append to test_chordal_umto.py
from apps.exercises.umto import UMTO

META_VOICES = {"exercise_id": "T", "source": "t", "key": "C", "meter": "4/4",
               "complexity_score": 1, "score_kind": "voices"}
META_CHORDAL = {**META_VOICES, "score_kind": "chordal"}
ONE_CHORD = [{"offset": 0.0, "duration": 1.0, "visible": [60]}]


class TestUMTOValidator(TestCase):
    def test_chordal_requires_chords(self):
        with self.assertRaises(ValidationError):
            UMTO.model_validate({"metadata": META_CHORDAL, "chords": []})

    def test_chordal_ok_without_voices(self):
        obj = UMTO.model_validate({"metadata": META_CHORDAL, "chords": ONE_CHORD})
        self.assertEqual(obj.metadata.score_kind, "chordal")
        self.assertEqual(len(obj.chords), 1)

    def test_voices_kind_requires_explicit_voices(self):
        # omitting voices for a voices-kind payload must FAIL (preserve old behavior)
        with self.assertRaises(ValidationError):
            UMTO.model_validate({"metadata": META_VOICES})

    def test_voices_kind_ok_with_explicit_voices(self):
        obj = UMTO.model_validate({
            "metadata": META_VOICES,
            "voices": {"S": [], "A": [], "T": [], "B": []},
        })
        self.assertEqual(obj.metadata.score_kind, "voices")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestUMTOValidator -v`
Expected: FAIL — `UMTO` has no `chords`; `voices` still required so `test_chordal_ok_without_voices` fails, and no validator so `test_chordal_requires_chords` / `test_voices_kind_requires_explicit_voices` fail.

- [ ] **Step 3: Write minimal implementation**

```python
# apps/exercises/umto.py — change UMTO fields:
#   voices: Voices                       ->  voices: Voices = Field(default_factory=Voices)
#   add:                                     chords: List[ChordEvent] = Field(default_factory=list)
# then add this validator to the UMTO class:

    @model_validator(mode="after")
    def validate_score_kind(self):
        if self.metadata.score_kind == "chordal":
            if not self.chords:
                raise ValueError("score_kind 'chordal' requires non-empty chords")
        else:  # "voices"
            if "voices" not in self.model_fields_set:
                raise ValueError("score_kind 'voices' requires an explicit voices field")
        return self
```

Note: `model_fields_set` reflects fields actually supplied to `model_validate`; the `default_factory` provides a value at runtime but does not add `voices` to `model_fields_set`, so omission is still detectable.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestUMTOValidator -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the FULL existing UMTO suite to confirm no regression**

Run: `python -m pytest apps/exercises/tests/test_umto_factory.py apps/exercises/tests/test_voice_events_music21.py -v`
Expected: PASS — existing voices-kind exercises always pass explicit `voices`, so the new rule does not break them. If any fail because they omit `voices`, that test was relying on the old implicit default; fix by adding explicit `voices` in that test's fixture (do NOT weaken the validator).

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/tests/test_chordal_umto.py
git commit -m "feat(umto): add UMTO.chords + score_kind validator (voices still requires explicit voices)"
```

---

## Task 4: Regenerate JSON schema

**Files:**
- Modify: `apps/exercises/umto_schema.json` (generated)
- Test: `apps/exercises/tests/test_chordal_umto.py`

- [ ] **Step 1: Write the failing test**

```python
# append to test_chordal_umto.py
import json, os


class TestSchemaUpToDate(TestCase):
    def test_schema_contains_chord_and_score_kind(self):
        path = os.path.join(os.path.dirname(__file__), "..", "umto_schema.json")
        with open(path) as f:
            schema = json.load(f)
        text = json.dumps(schema)
        self.assertIn("ChordEvent", text)
        self.assertIn("score_kind", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestSchemaUpToDate -v`
Expected: FAIL — schema not yet regenerated, `ChordEvent` absent.

- [ ] **Step 3: Regenerate the schema (no hand-editing)**

Run: `python manage.py make_umto_schema --settings=harmony.settings.local`
Expected stdout: `Successfully saved UMTO schema to apps/exercises/umto_schema.json`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestSchemaUpToDate -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto_schema.json apps/exercises/tests/test_chordal_umto.py
git commit -m "chore(umto): regenerate schema for chordal score-kind"
```

---

## Task 5: SPIKE — §5a window/slot source decision (W1 vs W2) — FIRST CHECKPOINT

**Files:**
- Create: `docs/superpowers/plans/spike-5a-window-source.md`

This task produces a **decision document**, not shipping code. Per review, it gates all frontend/backend payload work. Time-box ~1–2 hours.

- [ ] **Step 1: Read the two window-building code paths**

Read and note exact behavior:
- `lab/static/js/src/components/music/score_timeline.js` — `buildTimeline(score)`: how it walks `score.measures[].staves[].voices[].items[]` and assigns `onset`.
- `lab/static/js/src/models/exercise_definition.js:448` — `buildAnalysisWindows(timeline)` and the `winMeta.hasSlot` check at `:572`.
- `apps/exercises/umto.py` — `UMTO._to_legacy_measures()` (how voices-kind synthesizes `score.measures`).

- [ ] **Step 2: Prototype W1 on paper/REPL — chords[] → score.measures**

Map `ONE_CHORD`-style data to a minimal `score.measures` structure that `buildTimeline` accepts. Confirm: can a single staff with one voice whose `items` are `kind:"chord"` carry multiple MIDI pitches per onset? Check whether `score_timeline.js` reads chord heads. Record findings.

- [ ] **Step 3: Prototype W2 on paper — buildTimeline reads umto.chords**

Sketch the minimal branch in `buildTimeline` that, when `score.umto.metadata.score_kind === "chordal"`, emits one timeline entry per chord. Estimate lines touched in the working timeline path.

- [ ] **Step 4: Write the decision doc**

```markdown
# Spike 5a: Chordal Window/Slot Source — Decision

## W1 (generate score.measures from chords[])
- Feasible: yes/no
- Code touched: <files/lines>
- Risk: <ragged durations, chord heads, ...>

## W2 (teach buildTimeline to read umto.chords)
- Feasible: yes/no
- Code touched: <files/lines>
- Risk: <touches working path>

## DECISION: W1 | W2
## Rationale: <2-3 sentences>
## Consequence for Task 9 (backend payload) and Task 7 (frontend case)
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/spike-5a-window-source.md
git commit -m "docs: spike 5a decision on chordal window/slot source"
```

**STOP. Review the decision with the user before continuing. Tasks 7 and 9 below assume W1 (generate measures). If W2 is chosen, adjust those tasks accordingly during execution.**

---

## Task 6: Shared chord-normalization helper (node-testable logic module)

**Files:**
- Create: `lab/static/js/src/models/chordal_problems_logic.js`
- Test: `lab/static/js/src/models/chordal_problems_logic.test.js`

Follows the existing `*_logic.js` + `node *.test.js` pattern (see `identification_submit_flow_logic.js`). Extracts the `{visible, hidden, notes}` normalization so both the new chordal case and (eventually) the legacy branch share one implementation.

- [ ] **Step 1: Write the failing test**

```javascript
// lab/static/js/src/models/chordal_problems_logic.test.js
// Run: node lab/static/js/src/models/chordal_problems_logic.test.js
"use strict";
var logic = require("./chordal_problems_logic");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + " got " + JSON.stringify(actual) + " want " + JSON.stringify(expected)); fail++; }
}

// chordsToProblems: chordal UMTO chords[] -> chord-bank gradeable problems
var chords = [
  { offset: 0.0, duration: 1.0, visible: [60, 64, 67], hidden: [] },
  { offset: 1.0, duration: 1.0, visible: [62], hidden: [50] }
];
var problems = logic.chordsToProblems(chords);
eq("two problems", problems.length, 2);
eq("first visible preserved order", problems[0].visible, [60, 64, 67]);
eq("first notes = visible+hidden", problems[0].notes, [60, 64, 67]);
eq("second merges hidden into notes", problems[1].notes, [50, 62]); // notes sorted for grading
eq("second visible only visible", problems[1].visible, [62]);
eq("second hidden preserved", problems[1].hidden, [50]);

console.log(pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node lab/static/js/src/models/chordal_problems_logic.test.js`
Expected: FAIL — `Cannot find module './chordal_problems_logic'`

- [ ] **Step 3: Write minimal implementation**

```javascript
// lab/static/js/src/models/chordal_problems_logic.js
"use strict";

// Convert chordal UMTO chords[] into chord-bank gradeable "problems".
// notes = sorted(visible + hidden) for grading; visible/hidden keep source order.
function chordsToProblems(chords) {
  return (chords || []).map(function (c) {
    var visible = (c.visible || []).slice();
    var hidden = (c.hidden || []).slice();
    var notes = visible.concat(hidden).slice().sort(function (a, b) { return a - b; });
    return { visible: visible, hidden: hidden, notes: notes };
  });
}

module.exports = { chordsToProblems: chordsToProblems };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node lab/static/js/src/models/chordal_problems_logic.test.js`
Expected: `6 passed, 0 failed`

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/chordal_problems_logic.js lab/static/js/src/models/chordal_problems_logic.test.js
git commit -m "feat(frontend): chordal problems normalization logic module"
```

---

## Task 7: Chordal case at top of the `umto_chorale` block

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js` (inside `if (exercise.type === "umto_chorale")`, ~line 1072)
- Test: `lab/static/js/src/models/chordal_problems_logic.test.js` (extend with the branch-decision helper)

Spec §5c: the chordal case must run BEFORE the existing `isHarm/isIdent/isPlayback` logic (which sets `problems = isPlayback ? [] : …` at `:1095`) and must populate `exercise.problems`. To keep it testable, the *decision* (is this chordal? what problems?) lives in the logic module; `exercise_definition.js` just wires it.

- [ ] **Step 1: Write the failing test (extend the logic test)**

```javascript
// append to chordal_problems_logic.test.js (before the summary print)
// isChordalUMTO: detect chordal score-kind from a parsed definition-ish object
eq("chordal detected", logic.isChordalUMTO({ score: { umto: { metadata: { score_kind: "chordal" } } } }), true);
eq("voices not chordal", logic.isChordalUMTO({ score: { umto: { metadata: { score_kind: "voices" } } } }), false);
eq("missing umto not chordal", logic.isChordalUMTO({ score: {} }), false);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node lab/static/js/src/models/chordal_problems_logic.test.js`
Expected: FAIL — `logic.isChordalUMTO is not a function`

- [ ] **Step 3: Add the detector to the logic module**

```javascript
// chordal_problems_logic.js — add and export
function isChordalUMTO(def) {
  return !!(def && def.score && def.score.umto && def.score.umto.metadata &&
            def.score.umto.metadata.score_kind === "chordal");
}
module.exports = { chordsToProblems: chordsToProblems, isChordalUMTO: isChordalUMTO };
```

- [ ] **Step 4: Run logic test to verify it passes**

Run: `node lab/static/js/src/models/chordal_problems_logic.test.js`
Expected: `9 passed, 0 failed`

- [ ] **Step 5: Wire the chordal case into exercise_definition.js**

At the very top of `if (exercise.type === "umto_chorale") {` (line ~1072), before `exercise.harmonizationTargets = …`, insert:

```javascript
        // Chordal UMTO: onset verticalities graded as chord-bank problems.
        // MUST run before the isHarm/isIdent/isPlayback logic, which would
        // otherwise set problems = [] for playback (see spec §5c).
        if (definition.score && definition.score.umto &&
            definition.score.umto.metadata &&
            definition.score.umto.metadata.score_kind === "chordal") {
          var _chordalChords = definition.score.umto.chords || [];
          exercise.problems = chordalProblemsLogic.chordsToProblems(_chordalChords);
          exercise.analysis = { enabled: true, mode: {} };
          // identification/figured_bass/roman targets come from canonical analysis[]
          // correlated by offset; window/slot source per spike 5a (Task 9 payload).
          exercise.complexity_score = definition.complexity_score || 0;
          return exercise;
        }
```

Add the require near the other module imports at the top of the file (match existing `require`/module pattern in this file; if the file uses a module loader rather than CommonJS, expose `chordalProblemsLogic` the same way sibling logic modules are consumed):

```javascript
var chordalProblemsLogic = require("./chordal_problems_logic");
```

- [ ] **Step 6: Build the frontend bundle and smoke-check**

Run the project's JS build (check `package.json`/Makefile; e.g. `make build-js` or the documented bundler). Confirm no build error referencing `chordal_problems_logic`.
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/models/chordal_problems_logic.js lab/static/js/src/models/chordal_problems_logic.test.js lab/static/js/src/models/exercise_definition.js
git commit -m "feat(frontend): chordal UMTO case populates problems before umto_chorale playback logic"
```

---

## Task 8: Factory — `build_chordal_umto_payload` + `save_chordal_umto_exercise`

**Files:**
- Modify: `apps/exercises/umto_factory.py`
- Test: `apps/exercises/tests/test_chordal_umto.py`

- [ ] **Step 1: Write the failing test**

```python
# append to test_chordal_umto.py
from apps.exercises.umto_factory import build_chordal_umto_payload


class TestChordalFactory(TestCase):
    def test_payload_stores_chords_under_score_umto(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Rule of the octave, C major, 3 voices",
            key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis=[],
        )
        umto = payload["score"]["umto"]
        self.assertEqual(umto["metadata"]["score_kind"], "chordal")
        self.assertEqual(len(umto["chords"]), 1)
        self.assertEqual(payload["type"], "umto_chorale")
        self.assertTrue(payload["isUMTO"])

    def test_payload_validates_against_umto(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP", source="t", key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60]}], analysis=[],
        )
        # Must not raise:
        UMTO.model_validate(payload["score"]["umto"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestChordalFactory -v`
Expected: FAIL — `cannot import name 'build_chordal_umto_payload'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/exercises/umto_factory.py — new function (mirror build_umto_payload's return shape)
from apps.exercises.umto import UMTO, Metadata, ChordEvent, AnalysisSlice  # adjust to existing imports

def build_chordal_umto_payload(*, exercise_id, source, key, meter, clef,
                               complexity_score, mode, chords, analysis=None,
                               unit=None, input_mode="dropdown"):
    """Build a UMTO frontend payload for a chordal score-kind exercise."""
    analysis = analysis or []
    umto = UMTO(
        metadata=Metadata(
            exercise_id=exercise_id, source=source, key=key, meter=meter,
            clef=clef, complexity_score=complexity_score, mode=mode,
            input_mode=input_mode, unit=unit, score_kind="chordal",
        ),
        chords=[ChordEvent(**c) for c in chords],
        analysis=[AnalysisSlice(**a) for a in analysis],
    )
    UMTO.model_validate(umto.model_dump(mode="json"))  # explicit validation
    return {
        "type": "umto_chorale",
        "isUMTO": True,
        "mode": mode.value if hasattr(mode, "value") else mode,
        "key": key,
        "meter": meter,
        "clef": clef,
        "complexity_score": complexity_score,
        "score": {
            "meta": {"key": key, "time": meter, "clef": clef},
            # measures populated per spike 5a decision (Task 9 if W1)
            "umto": umto.model_dump(mode="json"),
        },
        "analysis": umto.model_dump(mode="json")["analysis"],
        "grading": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestChordalFactory -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_umto.py
git commit -m "feat(umto): build_chordal_umto_payload factory"
```

---

## Task 9: Backend payload — populate window source per spike 5a (assumes W1)

**Files:**
- Modify: `apps/exercises/umto_factory.py` (`build_chordal_umto_payload`) and/or `apps/exercises/umto.py`
- Test: `apps/exercises/tests/test_chordal_umto.py`

> **Conditional on Task 5.** If W1 was chosen: generate `score.measures` from `chords[]`. If W2 was chosen: skip measure generation here and instead implement the `buildTimeline` chordal branch in the frontend (move this task's work into Task 7's scope). The steps below assume **W1**.

- [ ] **Step 1: Write the failing test (W1)**

```python
# append to test_chordal_umto.py
class TestChordalMeasures(TestCase):
    def test_chords_become_measures_with_chord_items(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP", source="t", key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]},
                {"offset": 1.0, "duration": 1.0, "visible": [62, 65, 69]},
            ],
            analysis=[],
        )
        measures = payload["score"]["measures"]
        self.assertTrue(len(measures) >= 1)
        # first onset carries all three pitches as one chord item
        first_items = measures[0]["staves"]["treble"]["voices"][0]["items"]
        self.assertEqual(first_items[0]["kind"], "chord")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestChordalMeasures -v`
Expected: FAIL — `KeyError: 'measures'` (payload has no measures yet).

- [ ] **Step 3: Implement chords→measures (W1)**

```python
# apps/exercises/umto_factory.py — add helper and call it from build_chordal_umto_payload
def _chordal_to_measures(chords, meter):
    """Minimal CIR measures: each chord -> a chord item on the treble staff.
    Honors spec §5a option W1. Beats-per-measure from meter numerator."""
    beats = int(meter.split("/")[0]) if "/" in meter else 4
    DUR_TYPE = {4.0: "w", 2.0: "h", 1.0: "q", 0.5: "8", 0.25: "16"}
    measures, current, used = [], {"staves": {"treble": {"voices": [{"items": []}]}}}, 0.0
    for c in chords:
        pitches = [_midi_to_cir_pitch(m) for m in (c.get("visible", []) + c.get("hidden", []))]
        item = {
            "kind": "chord" if len(pitches) > 1 else "note",
            "duration": {"type": DUR_TYPE.get(float(c["duration"]), "q"), "dots": 0},
        }
        if len(pitches) > 1:
            item["pitches"] = pitches
        else:
            item["pitch"] = pitches[0] if pitches else None
        current["staves"]["treble"]["voices"][0]["items"].append(item)
        used += float(c["duration"])
        if used >= beats:
            measures.append(current)
            current, used = {"staves": {"treble": {"voices": [{"items": []}]}}}, 0.0
    if current["staves"]["treble"]["voices"][0]["items"]:
        measures.append(current)
    return measures


def _midi_to_cir_pitch(midi):
    # C-major-ish default spelling; spelling[] override handled in Spec B transpose.
    names = [("C",0),("C",1),("D",0),("D",1),("E",0),("F",0),("F",1),("G",0),("G",1),("A",0),("A",1),("B",0)]
    step, alter = names[midi % 12]
    octave = midi // 12 - 1
    return {"step": step, "alter": alter, "octave": octave}
```

Then in `build_chordal_umto_payload`, set:

```python
        "score": {
            "meta": {"key": key, "time": meter, "clef": clef},
            "measures": _chordal_to_measures(chords, meter),
            "umto": umto.model_dump(mode="json"),
        },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestChordalMeasures -v`
Expected: PASS

- [ ] **Step 5: Verify timeline consumes it (cross-check with score_timeline.js)**

Confirm the chord-item shape (`kind:"chord"`, `pitches:[...]`) matches what `score_timeline.js buildTimeline` reads for chords (from the spike). If `score_timeline.js` expects a different chord key (e.g. `heads` not `pitches`), align the helper to the renderer's actual key and update the test.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_umto.py
git commit -m "feat(umto): generate score.measures from chordal chords[] (spike 5a W1)"
```

---

## Task 10: Legacy load-path — backend wrapper

**Files:**
- Modify: `lab/views.py` (~line 285, the `is_umto` gate) or `generate_exercise_context`
- Test: `apps/exercises/tests/test_chordal_umto.py`

Spec §9: legacy `data.chord` rows do not satisfy the `is_umto` gate. Wrap them into a chordal UMTO contract on the backend so the frontend has one path. Keep it a runtime *read* transform — never write back to the DB.

- [ ] **Step 1: Write the failing test**

```python
# append to test_chordal_umto.py
from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload


class TestLegacyWrap(TestCase):
    def test_legacy_chord_array_wraps_to_chordal(self):
        legacy_data = {
            "type": "matching",
            "key": "C",
            "chord": [
                {"visible": [60, 64, 67], "hidden": []},
                {"visible": [62, 65, 69], "hidden": []},
            ],
        }
        payload = legacy_chord_row_to_chordal_payload(legacy_data)
        umto = payload["score"]["umto"]
        self.assertEqual(umto["metadata"]["score_kind"], "chordal")
        self.assertEqual(len(umto["chords"]), 2)
        self.assertEqual(umto["chords"][0]["visible"], [60, 64, 67])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestLegacyWrap -v`
Expected: FAIL — `cannot import name 'legacy_chord_row_to_chordal_payload'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/exercises/umto_factory.py
def legacy_chord_row_to_chordal_payload(data, *, meter="4/4", clef="keyboard",
                                        complexity_score=1):
    """Wrap a legacy data.chord row into a chordal UMTO payload (runtime read only)."""
    raw = data.get("chord") or []
    chords = []
    offset = 0.0
    for c in raw:
        if isinstance(c, dict):
            visible = list(c.get("visible") or c.get("notes") or [])
            hidden = list(c.get("hidden") or [])
        else:  # bare list of midi
            visible, hidden = list(c), []
        chords.append({"offset": offset, "duration": 1.0,
                       "visible": visible, "hidden": hidden})
        offset += 1.0
    return build_chordal_umto_payload(
        exercise_id=str(data.get("id", "LEGACY")),
        source=data.get("description", "Legacy exercise"),
        key=data.get("key", "C"), meter=meter, clef=clef,
        complexity_score=complexity_score, mode=InteractionMode.PLAYBACK,
        chords=chords, analysis=[],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestLegacyWrap -v`
Expected: PASS

- [ ] **Step 5: Wire the wrapper into the serving path (gating round-trip)**

In `lab/views.py` near the `is_umto` decision (~line 285), add: if the row is NOT already UMTO **and** `exercise.data.get("chord")` exists, build the context from `legacy_chord_row_to_chordal_payload(exercise.data)` instead of the legacy path. Guard behind a feature check so existing legacy rendering is the fallback if wrapping fails.

```python
        is_umto = exercise.data.get("isUMTO", False) or ("metadata" in exercise.data and "voices" in exercise.data)
        if not is_umto and exercise.data.get("chord"):
            try:
                from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload
                exercise_context.update(legacy_chord_row_to_chordal_payload(exercise.data))
                is_umto = True  # routed through UMTO contract
            except Exception:
                pass  # fall back to existing legacy path below
```

- [ ] **Step 6: Round-trip equivalence test (spec test 1 — the gate)**

```python
# append to test_chordal_umto.py
from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload
# Reuse the JS normalization expectation: notes = sorted(visible+hidden)

class TestRoundTripEquivalence(TestCase):
    def test_wrapped_legacy_matches_legacy_grading_semantics(self):
        legacy = {"type": "matching", "key": "C",
                  "chord": [{"visible": [67, 60, 64], "hidden": []}]}
        payload = legacy_chord_row_to_chordal_payload(legacy)
        chords = payload["score"]["umto"]["chords"]
        # visible order preserved from source
        self.assertEqual(chords[0]["visible"], [67, 60, 64])
        # gradeable notes = sorted(visible+hidden) — matches chordsToProblems()
        notes = sorted(chords[0]["visible"] + chords[0]["hidden"])
        self.assertEqual(notes, [60, 64, 67])
```

Run: `python -m pytest apps/exercises/tests/test_chordal_umto.py::TestRoundTripEquivalence -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/exercises/umto_factory.py lab/views.py apps/exercises/tests/test_chordal_umto.py
git commit -m "feat(umto): backend wrapper loads legacy chord[] rows through chordal UMTO path"
```

---

## Task 11: Documentation

**Files:**
- Modify: `docs/UMTO_GUIDE.md`

- [ ] **Step 1: Add a "Chordal score-kind" section**

Document, with the exact field names shipped in Tasks 1–3:
- `Metadata.score_kind: "voices" | "chordal"` (default `"voices"`).
- `UMTO.chords: ChordEvent[]` (offset, duration, visible, hidden, optional spelling; input order preserved; spelling length must equal visible+hidden).
- Analysis stays in canonical `analysis[]`, correlated by `offset`.
- Frontend: `type` remains `umto_chorale`, selected by `score_kind`; chordal exercises populate `problems` for playback.
- Creation path: `build_chordal_umto_payload` / `save_chordal_umto_exercise`.
- Legacy rows load via `legacy_chord_row_to_chordal_payload` (runtime read, no DB rewrite).
- Note: transpose for chordal UMTO is Spec B.

- [ ] **Step 2: Commit**

```bash
git add docs/UMTO_GUIDE.md
git commit -m "docs: document chordal UMTO score-kind in UMTO_GUIDE"
```

---

## Full regression gate (run before declaring Spec A done)

- [ ] Python: `python -m pytest apps/exercises/tests/ -v` — all pass, including `test_chordal_umto.py` and untouched `test_umto_factory.py`.
- [ ] JS: `node lab/static/js/src/models/chordal_problems_logic.test.js` — all pass.
- [ ] Frontend build succeeds.
- [ ] Spec correctness bar tests 1–9 each map to a passing test above.

Spec B (MusicXML→chordal converter + Teacher Workbench UX) begins only after this gate is green.
