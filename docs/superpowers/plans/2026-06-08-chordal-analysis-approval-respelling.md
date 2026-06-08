# Chordal Analysis Approval, Editing & Respelling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers (1) approve generated analysis at save time, (2) edit analysis when it's wrong, and (3) respell notes — with chordal exercises finally rendering correct, key-aware, override-able note spelling.

**Architecture:** Chordal UMTO exercises store chords as MIDI integers plus an optional positional `spelling: List[str]` field (already in the schema, format `"C#4"`/`"Eb4"`). Today both the Python measure builder and the JS runtime converter rebuild pitches from a hardcoded sharp table, ignoring key and ignoring stored spelling — so the VexFlow renderer (which trusts CIR `pitch.step/alter`, no snap-spelling) always shows sharps. We fix the converters to spell key-aware by default and honor stored spelling as an override, capture spelling at Play-save, add a soft "needs review" approval gate, and extend the existing review panel with a live notation preview and a respelling editor. The voices/chorale path already does all this correctly and is our reference pattern.

**Tech Stack:** Django + Pydantic (UMTO models), music21 (analysis), RequireJS/Backbone-style JS, VexFlow rendering, Jasmine/Jest-style JS tests + Django `TestCase`.

---

## Background: why this works the way it does

Read these before starting — they are load-bearing facts established during investigation:

- **Renderer trusts CIR pitch, does not snap-spell.** `itemToTickable` in `lab/static/js/src/components/music/rendering/vexflow_adapter.js:816-820` builds the VexFlow key straight from `item.pitch.step` + `item.pitch.alter` + `item.pitch.octave`. The snap-spelling in `stave_note_factory.js` belongs to the *Play/notater* renderer, not the exercise (VexFlowAdapter) renderer. So whatever the converter puts in `pitch.step/alter` is exactly what renders.
- **Chordal render source is the JS runtime converter, not the stored Python measures.** For chorale-like scores, `exercise_sheet.js:1831` re-converts `score.umto` via `_convertUMTOToProcessedScore` → `_convertChordalUMTOToProcessedScore` (`exercise_sheet.js:2983`) every render. The Python `_chordal_to_measures` output is a secondary/fallback copy. **Phase 1 fixes JS first** for that reason; Python is brought to parity in Phase 2.
- **Spelling string convention already exists.** `apps/exercises/utils/umto_import_router.py:102` `_pitch_spelling` = `pitch.nameWithOctave.replace("-", "b")` → e.g. `"C#4"`, `"Eb4"`, `"Cb5"`. `_pitches_for_chord_event` (same file, line 115) already *prefers* `chord_event["spelling"]` when present, so the analysis/figured-bass layer is already spelling-aware. We reuse this exact string format everywhere.
- **`ChordEvent.spelling` is positional: visible pitches first, then hidden.** Validated length == `len(visible) + len(hidden)` in `apps/exercises/umto.py:59`.
- **Key-aware spelling table (JS).** `KeySignature.keyToSpelling(key)` (`lab/static/js/src/models/key_signature.js:530`) returns the 12-element name array for a key, same table the analyzer uses (`this.spelling[key][pc]`). Keys are in HarmonyLab format (e.g. `"jC_"`, `"iA_"`).
- **Review infra already exists.** `api_chordal_analysis_review` GET/POST (`apps/dashboard/views/api_workbench.py:112`), the `analysis_review_status` metadata field (`none`/`generated`/`reviewed`), the workbench review panel (`apps/dashboard/templates/dashboard/workbench.html:112`), and the "Review/Edit Analysis" link (`apps/dashboard/templates/dashboard/edit-exercise.html:55`). The POST currently rewrites `analysis` only — it does **not** accept spelling yet.

## Testing conventions (READ — repo-specific)

- **JS unit tests are plain Node CommonJS scripts**, run with `node path/to/file.test.js`, using a hand-rolled `eq()` harness (see `lab/static/js/src/models/chordal_problems_logic.test.js`). There is **no** jasmine/jest/karma. Do **not** use `describe/it/expect` or RequireJS `define([...])` in tests.
- **Testable JS modules use the UMD wrapper** so they load in both Node and the browser:
  ```javascript
  (function (root, factory) {
    if (typeof module === "object" && module.exports) module.exports = factory();
    else if (typeof define === "function" && define.amd) define([], factory);
  })(this, function () {
    // ... return { ... };
  });
  ```
  `chordal_spelling.js` MUST use this wrapper so its `.test.js` can `require` it.
- **AMD-only browser modules** (`exercise_sheet.js`, `vexflow_adapter.js`, `key_signature.js`, `play_sheet.js`) are **not** node-unit-tested in this repo. Strategy: push all pure logic into the node-tested `chordal_spelling.js`; keep the AMD edits to thin wiring, and verify wiring by **manual browser check** (load the exercise/Play view and look). Tasks that touch AMD modules say so explicitly.
- **Python tests:** `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 manage.py test <dotted.path>` (creates the test DB). `pytest` works for pure modules with no DB, but the Django runner is the safe default.

## Approval gate decision

**Soft gate** (chosen). After save the teacher is routed into the review panel and a "needs review" badge appears in exercise lists. Nothing blocks playlist-add or student-serving. A hard block is explicitly out of scope for this plan.

## File map

| File | Responsibility | Phases |
|---|---|---|
| `lab/static/js/src/components/music/exercise_sheet.js` | `_convertChordalUMTOToProcessedScore`: key-aware + spelling-honoring pitch build | 1, 2 |
| `lab/static/js/src/components/music/chordal_spelling.js` *(new)* | Pure helpers: `spelledPitchFromName`, `pitchFromSpellingString`, `keyAwarePitch` | 1, 2 |
| `apps/exercises/umto_factory.py` | `_chordal_to_measures` honor spelling; `save_chordal_umto_exercise` accept+store spelling | 2, 3 |
| `apps/exercises/chordal_spelling.py` *(new)* | Python `spelling_str_to_cir_pitch` parser | 2 |
| `lab/static/js/src/components/music/play_sheet.js` | `dataForSave`: capture spelling array from analyzer | 3 |
| `lab/views.py` | `AddExerciseView`: pass spelling through; return `reviewStatus` | 3, 4 |
| `apps/dashboard/views/exercises.py` | surface `analysis_review_status` to edit page + lists | 4 |
| `apps/dashboard/views/api_workbench.py` | review POST accept `spelling`; validate length | 6 |
| `apps/dashboard/templates/dashboard/edit-exercise.html` | "needs review" badge | 4 |
| `apps/dashboard/templates/dashboard/workbench.html` | live notation preview + respelling editor in review panel | 5, 6 |

---

## Phase 1 — Key-aware default spelling for chordal render

Removes the always-sharp bug. After this phase, a B♭ in F major renders as B♭ (not A♯) with no stored spelling needed. JS only (the render path).

### Task 1.1: Create pure spelling helper module (JS, UMD + Node test)

**Files:**
- Create: `lab/static/js/src/components/music/chordal_spelling.js`
- Test: `lab/static/js/src/components/music/chordal_spelling.test.js`

This module holds ALL the pure spelling logic so it is node-testable. It also exposes `resolveChordPitches`, used by the AMD converter in Task 1.2/2.1 (which stays a thin wrapper).

- [ ] **Step 1: Write the failing test** (plain Node CommonJS, `eq()` harness — copy the style from `chordal_problems_logic.test.js`)

```javascript
// lab/static/js/src/components/music/chordal_spelling.test.js
// Run: node lab/static/js/src/components/music/chordal_spelling.test.js
"use strict";
var S = require("./chordal_spelling");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + " got " + JSON.stringify(actual) + " want " + JSON.stringify(expected)); fail++; }
}

// spelledPitchFromName(name, midi)
eq("c#4 from midi 61", S.spelledPitchFromName("c#", 61), { step: "C", alter: 1, octave: 4 });
eq("eb4 from midi 63", S.spelledPitchFromName("eb", 63), { step: "E", alter: -1, octave: 4 });
eq("cb wraps up (B3->Cb4)", S.spelledPitchFromName("cb", 59), { step: "C", alter: -1, octave: 4 });
eq("b# wraps down (C4->B#3)", S.spelledPitchFromName("b#", 60), { step: "B", alter: 1, octave: 3 });

// pitchFromSpellingString(str)
eq("parse C#4", S.pitchFromSpellingString("C#4"), { step: "C", alter: 1, octave: 4 });
eq("parse Eb4", S.pitchFromSpellingString("Eb4"), { step: "E", alter: -1, octave: 4 });
eq("parse Cb5", S.pitchFromSpellingString("Cb5"), { step: "C", alter: -1, octave: 5 });
eq("parse F##3", S.pitchFromSpellingString("F##3"), { step: "F", alter: 2, octave: 3 });
eq("parse junk -> null", S.pitchFromSpellingString("nope"), null);

// keyAwarePitch(midi, spellingTable) — F major table: pc10 -> "bb"
var fMajor = ["c","c#","d","eb","e","f","f#","g","g#","a","bb","b"];
eq("Bb in F major (midi 70)", S.keyAwarePitch(70, fMajor), { step: "B", alter: -1, octave: 4 });
eq("no table -> sharps (midi 70)", S.keyAwarePitch(70, null), { step: "A", alter: 1, octave: 4 });

// resolveChordPitches(chord, spellingTable) -> { <midi>: {step,alter,octave} }
// Explicit per-note spelling overrides the key-aware default.
eq("override wins",
   S.resolveChordPitches({ visible: [70], hidden: [], spelling: ["A#4"] }, fMajor),
   { 70: { step: "A", alter: 1, octave: 4 } });
eq("no spelling -> key-aware",
   S.resolveChordPitches({ visible: [70], hidden: [] }, fMajor),
   { 70: { step: "B", alter: -1, octave: 4 } });

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] **Step 2: Run test, verify it fails**

Run: `node lab/static/js/src/components/music/chordal_spelling.test.js`
Expected: FAIL — `Cannot find module './chordal_spelling'`.

- [ ] **Step 3: Implement the module (UMD wrapper)**

```javascript
// lab/static/js/src/components/music/chordal_spelling.js
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else if (typeof define === "function" && define.amd) define([], factory);
})(this, function () {
  var STEP_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

  // name: letter + accidentals, e.g. "c#", "eb", "cb", "b#", "f##". No octave.
  // midi: the sounding MIDI number, used to resolve the octave.
  function spelledPitchFromName(name, midi) {
    var lower = String(name).trim().toLowerCase();
    var step = lower.charAt(0).toUpperCase();
    var alter = 0;
    for (var i = 1; i < lower.length; i++) {
      var ch = lower.charAt(i);
      if (ch === "#") alter += 1;
      else if (ch === "b" || ch === "♭") alter -= 1;
      else if (ch === "x") alter += 2; // double-sharp shorthand
    }
    var pc = ((midi % 12) + 12) % 12;
    var naturalPc = STEP_PC[step];
    var octave = Math.floor(midi / 12) - 1;
    // Resolve enharmonic octave wrap (Cb sounds as B below it; B# sounds as C above it).
    if (pc - naturalPc > 6) octave += 1;       // e.g. Cb4: step C (pc 0) sounding B3 (pc 11)
    else if (naturalPc - pc > 6) octave -= 1;  // e.g. B#3: step B (pc 11) sounding C4 (pc 0)
    return { step: step, alter: alter, octave: octave };
  }

  // Scientific pitch string -> {step, alter, octave}. e.g. "C#4", "Eb4", "Cb5".
  function pitchFromSpellingString(str) {
    var m = /^([A-Ga-g])([#b♭♯x]*)(-?\d+)$/.exec(String(str).trim());
    if (!m) return null;
    var step = m[1].toUpperCase();
    var alter = 0;
    for (var i = 0; i < m[2].length; i++) {
      var ch = m[2].charAt(i);
      if (ch === "#" || ch === "♯") alter += 1;
      else if (ch === "b" || ch === "♭") alter -= 1;
      else if (ch === "x") alter += 2;
    }
    return { step: step, alter: alter, octave: parseInt(m[3], 10) };
  }

  // Key-aware spelling for a bare MIDI number using a key's 12-name table
  // (from KeySignature.keyToSpelling). Falls back to sharps if table missing.
  function keyAwarePitch(midi, spellingTable) {
    var pc = ((midi % 12) + 12) % 12;
    if (spellingTable && spellingTable[pc]) {
      return spelledPitchFromName(spellingTable[pc], midi);
    }
    var sharp = [["C",0],["C",1],["D",0],["D",1],["E",0],["F",0],
                 ["F",1],["G",0],["G",1],["A",0],["A",1],["B",0]][pc];
    return { step: sharp[0], alter: sharp[1], octave: Math.floor(midi / 12) - 1 };
  }

  // For one chord, return { midi: {step,alter,octave} } honoring explicit
  // positional spelling (visible then hidden) first, key-aware default otherwise.
  function resolveChordPitches(chord, spellingTable) {
    var out = {};
    var visible = chord.visible || [];
    var hidden = chord.hidden || [];
    var allMidis = visible.concat(hidden);
    var spelling = chord.spelling || null;
    var byMidi = {};
    if (spelling) {
      for (var i = 0; i < allMidis.length && i < spelling.length; i++) {
        var parsed = pitchFromSpellingString(spelling[i]);
        if (parsed) byMidi[allMidis[i]] = parsed;
      }
    }
    for (var j = 0; j < allMidis.length; j++) {
      var m = allMidis[j];
      out[m] = byMidi[m] || keyAwarePitch(m, spellingTable);
    }
    return out;
  }

  return {
    spelledPitchFromName: spelledPitchFromName,
    pitchFromSpellingString: pitchFromSpellingString,
    keyAwarePitch: keyAwarePitch,
    resolveChordPitches: resolveChordPitches,
  };
});
```

- [ ] **Step 4: Run test, verify PASS**

Run: `node lab/static/js/src/components/music/chordal_spelling.test.js`
Expected: `13 passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/chordal_spelling.js lab/static/js/src/components/music/chordal_spelling.test.js
git commit -m "feat(chordal): add key-aware + override-aware pitch spelling helpers"
```

### Task 1.2: Wire key-aware spelling into the chordal converter (AMD wiring — manual verify)

This edits an AMD-only browser module, so there is no node unit test; the logic it relies on is already covered by Task 1.1. Verify by manual browser check.

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js` — `_convertChordalUMTOToProcessedScore` (~2983-3048) and the module's `define([...])` header.

- [ ] **Step 1: Add the dependency**

In the `define([...], function (...) {})` header of `exercise_sheet.js`, add the module path for `chordal_spelling` (match the existing relative-path style used for sibling `music/` modules) and bind it to `ChordalSpelling`. Confirm whether `KeySignature` is already imported there; if not, add it too.

- [ ] **Step 2: Replace the hardcoded `midiToPitch` with key-aware spelling**

Replace the hardcoded `midiToPitch` (~2989-2994) with a key-table lookup. Leave the rest of the chord loop untouched for now (Task 2.1 swaps the loop to use `resolveChordPitches`):

```javascript
var spellingTable = null;
try { spellingTable = KeySignature.keyToSpelling(meta.key); } catch (e) { spellingTable = null; }
var midiToPitch = function (m) {
  return ChordalSpelling.keyAwarePitch(m, spellingTable);
};
```

- [ ] **Step 3: Manual browser verification (B♭ case)**

Build/serve the app, create or open a chordal exercise in an F-major key containing a B♭, and confirm it renders as B♭ (not A♯). If a quick build is unavailable, at minimum confirm `KeySignature.keyToSpelling("jF_")` returns a 12-element array whose index 10 is a flat name (`"bb"`), by reading `KEY_MAP` in `lab/static/js/src/models/key_signature.js`.

- [ ] **Step 4: Regression check (C major)**

Open the existing C-major chordal exercise (the screenshot one). Notes still render as naturals; Roman numerals still stack (Phase-0 fix in place).

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(chordal): render notes with key-aware spelling instead of forced sharps"
```

---

## Phase 2 — Honor explicit per-chord spelling override

When `chords[i].spelling` is present, it wins over the key-aware default (both JS render and Python measures). This is the data path the respelling UI (Phase 6) and capture (Phase 3) write to.

### Task 2.1: JS converter prefers stored spelling (AMD wiring — manual verify)

The override logic itself (`resolveChordPitches`) is already node-tested in Task 1.1. This task is the thin AMD wiring inside the converter; verify by manual browser check.

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js` (`_convertChordalUMTOToProcessedScore`, the `_.each(umto.chords, ...)` loop ~3004-3023)

- [ ] **Step 1: Confirm the helper covers the override case**

Re-run Task 1.1's test and confirm these two assertions pass (already in the file):
```
node lab/static/js/src/components/music/chordal_spelling.test.js
# "override wins" and "no spelling -> key-aware" both PASS
```
This is the behavior the converter must delegate to.

- [ ] **Step 2: Swap the chord loop to use `resolveChordPitches`**

Replace the per-chord pitch construction so each MIDI is mapped through the resolved map (override-aware), instead of calling `midiToPitch` directly:

```javascript
_.each(umto.chords, function (c) {
  var midis = (c.visible || []).slice();
  var resolved = ChordalSpelling.resolveChordPitches(c, spellingTable); // {midi: {step,alter,octave}}
  var dur = { type: durType(Number(c.duration)), dots: 0 };
  var routed = ChordalUMTOStaffDistribution.routeChordMidis(midis, dist);
  var hi = routed.treble, lo = routed.bass;
  var mkItem = function (ms) {
    var pitches = ms.map(function (m) { return resolved[m] || midiToPitch(m); });
    if (pitches.length > 1) {
      return { kind: "chord", notes: pitches.map(function (p) { return { pitch: p }; }), duration: dur };
    }
    if (pitches.length === 1) return { kind: "note", pitch: pitches[0], duration: dur };
    return { kind: "rest", duration: dur };
  };
  trebleItems.push(mkItem(hi));
  bassItems.push(mkItem(lo));
});
```

`spellingTable` and `midiToPitch` remain from Task 1.2 (the `midiToPitch` fallback covers any MIDI not in `resolved`, which should not happen but is defensive).

- [ ] **Step 3: Manual browser verification**

Open a chordal exercise whose stored `chords[i].spelling` forces an enharmonic (e.g. midi 70 spelled `"A#4"` in F major) and confirm it renders A♯, while a chord without `spelling` still renders the key-aware default (B♭). You can hand-edit one exercise's stored `spelling` via the review API or a shell once Phase 6 lands; before then, temporarily inject `spelling` into a test umto in the browser console calling `sheet._convertChordalUMTOToProcessedScore(umto)`.

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(chordal): honor explicit per-chord spelling override in render"
```

### Task 2.2: Python spelling-string parser

**Files:**
- Create: `apps/exercises/chordal_spelling.py`
- Test: `apps/exercises/tests/test_chordal_spelling.py`

- [ ] **Step 1: Write the failing test**

```python
from apps.exercises.chordal_spelling import spelling_str_to_cir_pitch

def test_sharp_with_octave():
    assert spelling_str_to_cir_pitch("C#4") == {"step": "C", "alter": 1, "octave": 4}

def test_flat():
    assert spelling_str_to_cir_pitch("Eb4") == {"step": "E", "alter": -1, "octave": 4}

def test_cb_keeps_letter():
    assert spelling_str_to_cir_pitch("Cb5") == {"step": "C", "alter": -1, "octave": 5}

def test_double_sharp():
    assert spelling_str_to_cir_pitch("F##3") == {"step": "F", "alter": 2, "octave": 3}

def test_invalid_returns_none():
    assert spelling_str_to_cir_pitch("nonsense") is None
```

- [ ] **Step 2: Run test, verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 -m pytest apps/exercises/tests/test_chordal_spelling.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the parser**

```python
# apps/exercises/chordal_spelling.py
import re

_PITCH_RE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")

def spelling_str_to_cir_pitch(s: str) -> dict | None:
    """Parse a scientific pitch string ("C#4", "Eb4", "Cb5") to a CIR pitch dict.

    Spelling strings use "b" for flat and "#" for sharp, matching
    apps/exercises/utils/umto_import_router._pitch_spelling.
    """
    if not s:
        return None
    m = _PITCH_RE.match(str(s).strip())
    if not m:
        return None
    step = m.group(1).upper()
    acc = m.group(2)
    alter = acc.count("#") - acc.count("b")
    return {"step": step, "alter": alter, "octave": int(m.group(3))}
```

- [ ] **Step 4: Run test, verify PASS**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 -m pytest apps/exercises/tests/test_chordal_spelling.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/chordal_spelling.py apps/exercises/tests/test_chordal_spelling.py
git commit -m "feat(chordal): add Python spelling-string parser"
```

### Task 2.3: `_chordal_to_measures` honors stored spelling

**Files:**
- Modify: `apps/exercises/umto_factory.py` (`_chordal_to_measures` ~436-462, `_staff_item`/`_append_chord_item`)
- Test: `apps/exercises/tests/test_chordal_to_measures_spelling.py`

- [ ] **Step 1: Write the failing test**

```python
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.ci")
django.setup()
from apps.exercises.umto_factory import _chordal_to_measures

def _all_pitches(measures):
    out = []
    for m in measures:
        for staff in m["staves"].values():
            for voice in staff["voices"]:
                for item in voice["items"]:
                    if item.get("kind") == "note":
                        out.append((item["pitch"]["step"], item["pitch"]["alter"]))
                    elif item.get("kind") == "chord":
                        for n in item["notes"]:
                            out.append((n["pitch"]["step"], n["pitch"]["alter"]))
    return out

def test_honors_stored_spelling():
    chords = [{"offset": 0.0, "duration": 4.0, "visible": [70], "hidden": [],
               "spelling": ["Bb4"]}]
    measures = _chordal_to_measures(chords, "4/4")
    assert ("B", -1) in _all_pitches(measures)
    assert ("A", 1) not in _all_pitches(measures)
```

- [ ] **Step 2: Run test, verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 -m pytest apps/exercises/tests/test_chordal_to_measures_spelling.py -q`
Expected: FAIL — `_midi_to_cir_pitch` returns `("A", 1)` for midi 70.

- [ ] **Step 3: Thread spelling through `_staff_item`**

Build a positional MIDI→pitch map per chord and pass it into `_staff_item`. In `_append_chord_item(c)` compute:

```python
from apps.exercises.chordal_spelling import spelling_str_to_cir_pitch

def _spell_map(c):
    spelling = c.get("spelling") or []
    if not spelling:
        return {}
    all_midis = list(c.get("visible") or []) + list(c.get("hidden") or [])
    out = {}
    for midi, s in zip(all_midis, spelling):
        parsed = spelling_str_to_cir_pitch(s)
        if parsed:
            out[midi] = parsed
    return out
```

Change `_staff_item(midis, duration)` to accept the map and prefer it:

```python
def _staff_item(midis, duration, spell_map):
    pitches = [spell_map.get(m) or _midi_to_cir_pitch(m) for m in midis]
    ...
```

And in `_append_chord_item`, compute `sm = _spell_map(c)` and pass it to both `_staff_item(treble, duration, sm)` and `_staff_item(bass, duration, sm)`.

- [ ] **Step 4: Run test, verify PASS**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 -m pytest apps/exercises/tests/test_chordal_to_measures_spelling.py -q`
Expected: PASS.

- [ ] **Step 5: Run the existing chordal save suite for regressions**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 manage.py test apps.exercises.tests.test_play_save_chordal_umto -v1`
Expected: OK (7 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_to_measures_spelling.py
git commit -m "feat(chordal): _chordal_to_measures honors stored spelling"
```

---

## Phase 3 — Capture spelling at Play-save

Auto-fill `chords[].spelling` from the spelling the Play view already computes, so most exercises get correct enharmonics with zero manual respelling.

### Task 3.1: Build spelling array in `dataForSave`

**Files:**
- Modify: `lab/static/js/src/components/music/play_sheet.js:675-713` (`dataForSave`)

Context: the Play sheet has an analyzer available via the same path the notater uses. `Analyze.getNoteName(midi, chordMidis)` returns the contextual name like `"c#"`/`"eb"` (lowercase, no octave). Combine with `ChordalSpelling.spelledPitchFromName` to get octave, then format a scientific string. Confirm how this component reaches an `Analyze` instance (grep `getAnalyzer`/`_makeAnalyzer` in the play render path); if none is directly held, instantiate one from `this.keySignature` exactly as `stave_note_factory._makeAnalyzer` does.

- [ ] **Step 1: Write the failing test**

```javascript
// Stub analyzer.getNoteName to return key-correct names; assert spelling strings.
// Chord visible [70] in F major should serialize spelling ["Bb4"].
var sheet = makePlaySheetWithKey("jF_");
sheet._analyzerForSave = { getNoteName: function (m) { return "bb"; } };
var data = sheet.dataForSave(); // with one chord [70]
expect(data.chord[0].spelling).toEqual(["Bb4"]);
```

- [ ] **Step 2: Run test, verify it fails**

Expected: FAIL — `dataForSave` does not emit `spelling`.

- [ ] **Step 3: Emit spelling per chord**

In the chord-building loop, after computing `visible`, add:

```javascript
var analyzer = this._analyzerForSave || this._makeAnalyzerForSave();
var spelling = visible.concat(hidden).map(function (midi) {
  var name = analyzer.getNoteName(midi, visible); // e.g. "bb", "c#"
  var p = ChordalSpelling.spelledPitchFromName(name, midi);
  var acc = p.alter === 1 ? "#" : p.alter === -1 ? "b"
          : p.alter === 2 ? "##" : p.alter === -2 ? "bb" : "";
  return p.step + acc + p.octave; // "Bb4"
});
chords.unshift({ rhythmValue: "w", visible: visible, hidden: hidden,
                 unison_idx: unison_idx, spelling: spelling });
```

Add `_makeAnalyzerForSave` mirroring `stave_note_factory._makeAnalyzer` (build from `this.keySignature`). Add `chordal_spelling` and `Analyze` to the module's `define([...])`.

- [ ] **Step 4: Run test, verify PASS**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/play_sheet.js lab/static/js/src/components/music/*.test.js
git commit -m "feat(play): capture note spelling into chordal save payload"
```

### Task 3.2: Persist spelling through the save path

**Files:**
- Modify: `apps/exercises/umto_factory.py` (`save_chordal_umto_exercise` normalizer ~718-751; `build_chordal_umto_payload` chord pass-through)
- Test: `apps/exercises/tests/test_play_save_chordal_umto.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to the existing test class a case posting a chord with `spelling` and asserting it round-trips into `umto.chords[i].spelling`.

```python
def test_spelling_is_persisted(self):
    payload = {
        "key": "jF_", "meter": "4/4", "staffDistribution": "keyboard",
        "chord": [
            {"visible": [70, 74, 77], "hidden": [], "rhythmValue": "w",
             "spelling": ["Bb4", "D5", "F5"]},
        ],
    }
    self.client.force_login(self.user)
    resp = self.client.post(self.add_url, {"data": json.dumps(payload)})
    self.assertEqual(resp.status_code, 201)
    ex = Exercise.objects.get(id=resp.json()["id"])
    chords = ex.data["score"]["umto"]["chords"]
    self.assertEqual(chords[0]["spelling"], ["Bb4", "D5", "F5"])
```

- [ ] **Step 2: Run test, verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 manage.py test apps.exercises.tests.test_play_save_chordal_umto.PlayViewSaveChordalUMTOTests.test_spelling_is_persisted -v2`
Expected: FAIL — normalizer drops `spelling`.

- [ ] **Step 3: Carry spelling through the normalizer**

In `save_chordal_umto_exercise`, when building `normalized_chords`, capture spelling and validate length:

```python
spelling = list(c.get("spelling")) if isinstance(c, dict) and c.get("spelling") else None
if spelling is not None and len(spelling) != len(visible) + len(hidden):
    spelling = None  # ignore malformed; key-aware default will apply
normalized_chords.append({
    "offset": off, "duration": dur, "visible": visible,
    "hidden": hidden, **({"spelling": spelling} if spelling else {}),
})
```

Confirm `build_chordal_umto_payload` constructs `ChordEvent(**chord)` (or equivalent) so the `spelling` key reaches the pydantic model; if it whitelists fields, add `spelling` to the passthrough.

- [ ] **Step 4: Run test, verify PASS**

Run the same command.
Expected: PASS.

- [ ] **Step 5: Run full chordal save suite**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.ci python3 manage.py test apps.exercises.tests.test_play_save_chordal_umto -v1`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_play_save_chordal_umto.py
git commit -m "feat(chordal): persist captured spelling through save"
```

---

## Phase 4 — Soft approval gate at save

Route the teacher into review after save and surface a "needs review" badge. No blocking.

### Task 4.1: Return review status + review URL from save

**Files:**
- Modify: `lab/views.py:900-943` (`AddExerciseView.post`)
- Test: `apps/exercises/tests/test_play_save_chordal_umto.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
def test_save_returns_review_status_and_url(self):
    payload = {"key": "jC_", "meter": "4/4", "staffDistribution": "keyboard",
               "chord": [{"visible": [60, 64, 67], "hidden": [], "rhythmValue": "w"}]}
    self.client.force_login(self.user)
    resp = self.client.post(self.add_url, {"data": json.dumps(payload)})
    body = resp.json()
    self.assertEqual(resp.status_code, 201)
    self.assertEqual(body["reviewStatus"], "generated")
    self.assertIn("/dashboard/", body["reviewUrl"])
```

- [ ] **Step 2: Run test, verify it fails**

Expected: FAIL — response only has `{"id": ...}`.

- [ ] **Step 3: Add status + URL to the JSON response**

```python
from django.urls import reverse
review_status = (
    exercise.data.get("score", {}).get("umto", {})
    .get("metadata", {}).get("analysis_review_status", "none")
)
review_url = reverse("dashboard:workbench") + f"?review={exercise.id}"
return JsonResponse(status=201, data={
    "id": exercise.id,
    "reviewStatus": review_status,
    "reviewUrl": review_url,
})
```

- [ ] **Step 4: Run test, verify PASS**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lab/views.py apps/exercises/tests/test_play_save_chordal_umto.py
git commit -m "feat(play): return review status and review URL on chordal save"
```

### Task 4.2: Play UI routes into review after save

**Files:**
- Modify: the JS that handles the save success response (grep for the `fetch`/`$.ajax` POSTing to the add URL in `play_sheet.js`/parent component; it currently reads `id`).

- [ ] **Step 1: Implement the redirect/prompt**

On `201`, if `reviewStatus === "generated"`, show a non-blocking toast "Analysis generated — review it" with a button that opens `reviewUrl` in a new tab. (Keep it soft: do not force navigation.) Use the existing `feedbackService.emit` channel per repo convention — add a catalog entry (see docs requirement below).

- [ ] **Step 2: Manual verification**

Save a chordal exercise from Play view → toast appears → clicking opens the review panel for that exercise.

- [ ] **Step 3: Docs — feedback catalog**

Add the new message to `lab/static/js/src/config/feedback_catalog.js` and a row in `docs/feedback_catalog.md` (required by CLAUDE.md for student-facing/feedback messages; this is teacher-facing but routes through the same service — add it for consistency).

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/play_sheet.js lab/static/js/src/config/feedback_catalog.js docs/feedback_catalog.md
git commit -m "feat(play): soft-route teacher into analysis review after save"
```

### Task 4.3: "Needs review" badge in edit page + lists

**Files:**
- Modify: `apps/dashboard/views/exercises.py` (the context that renders edit-exercise; `analysis_review_status` is already reachable — see `_analysis_review_status` in `api_workbench.py:194` for the accessor)
- Modify: `apps/dashboard/templates/dashboard/edit-exercise.html:55` area

- [ ] **Step 1: Write the failing test**

```python
def test_edit_page_shows_needs_review_badge(self):
    # create a chordal exercise with analysis_review_status="generated"
    ...
    resp = self.client.get(reverse("dashboard:edit-exercise", args=[ex.id]))
    self.assertContains(resp, "Needs review")
```

- [ ] **Step 2: Run test, verify it fails**

Expected: FAIL — no badge.

- [ ] **Step 3: Add status to context + template badge**

In the view, add `"analysis_review_status": _analysis_review_status(exercise)` to the context. In the template, near the "Review/Edit Analysis" link:

```html
{% if analysis_review_status == "generated" %}
  <span class="badge badge-warning">Needs review</span>
{% elif analysis_review_status == "reviewed" %}
  <span class="badge badge-success">Reviewed</span>
{% endif %}
```

- [ ] **Step 4: Run test, verify PASS**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/views/exercises.py apps/dashboard/templates/dashboard/edit-exercise.html apps/dashboard/tests/
git commit -m "feat(dashboard): surface analysis review status badge"
```

---

## Phase 5 — Live notation preview in the review panel

Upgrade the existing text-only review panel to render the actual stacked notation (notes + Roman/figured) so the teacher edits against what students see. Benefits Phases 2 and 6.

### Task 5.1: Render a read-only VexFlow preview from review rows

**Files:**
- Modify: `apps/dashboard/templates/dashboard/workbench.html` (`openAnalysisReview` ~429-458; add a `<div id="analysisReviewNotation">` to the panel ~118)

- [ ] **Step 1: Add the preview container**

Insert above `#analysisReviewRows`:

```html
<div id="analysisReviewNotation" class="review-notation" style="min-height:160px;"></div>
```

- [ ] **Step 2: Render via the existing VexFlowAdapter**

In `openAnalysisReview`, after fetching review data, build a minimal chordal `umto` from the returned `rows` (each row has `visible`/`hidden`/`spelling`/`content.roman_numeral`) and call `VexFlowAdapter.render` with `analyzeConfig.mode.roman_numerals = true` and `analysisRenderer: "adapter"`, reusing the same stored-roman path the exercise uses (so the preview matches the exercise exactly, including the braced-figure stacking from the Phase-0 fix). Confirm the workbench page can load the RequireJS `VexFlowAdapter` module; if not, expose a small render entry point.

- [ ] **Step 3: Manual verification**

Open review for the C-major exercise → preview shows notes with stacked `V⁶₅` / `V⁴₃`, matching the exercise view.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/templates/dashboard/workbench.html
git commit -m "feat(review): live notation preview in analysis review panel"
```

### Task 5.2: Re-render preview on edit

- [ ] **Step 1:** Wire `input` events on the roman/figure fields to re-run the preview render (debounced ~200ms).
- [ ] **Step 2:** Manual verification — typing `V7` updates the preview live.
- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/templates/dashboard/workbench.html
git commit -m "feat(review): live-update notation preview while editing analysis"
```

---

## Phase 6 — Respelling editor

Per-note enharmonic override in the review panel, persisted to `chords[].spelling`, honored by Phases 1–2.

### Task 6.1: Review POST accepts and validates spelling

**Files:**
- Modify: `apps/dashboard/views/api_workbench.py:152-191` (POST branch of `api_chordal_analysis_review`)
- Test: `apps/dashboard/tests/test_chordal_analysis_review.py` (extend or create)

- [ ] **Step 1: Write the failing test**

```python
def test_post_persists_spelling(self):
    # exercise with one chord [70] at offset 0
    resp = self.client.post(
        reverse("dashboard:api-chordal-analysis-review", args=[ex.id]),
        data=json.dumps({"rows": [
            {"offset": 0.0, "content": {"roman_numeral": "V{z5}"},
             "spelling": ["A#4"]}
        ]}),
        content_type="application/json",
    )
    self.assertEqual(resp.status_code, 200)
    ex.refresh_from_db()
    chords = ex.data["score"]["umto"]["chords"]
    self.assertEqual(chords[0]["spelling"], ["A#4"])
```

- [ ] **Step 2: Run test, verify it fails**

Expected: FAIL — POST writes only `analysis`, not `chords[].spelling`.

- [ ] **Step 3: Apply spelling to the matching chord on POST**

In the POST loop, after validating offset, when a row carries `spelling`, find the chord at that offset and set its spelling after length-validating against `visible + hidden`:

```python
spelling = row.get("spelling")
if spelling is not None:
    for chord in chords:
        if round(float(chord.get("offset", 0.0)), 6) == offset:
            expected = len(chord.get("visible", [])) + len(chord.get("hidden", []))
            if len(spelling) != expected:
                return JsonResponse(
                    {"error": f"spelling length {len(spelling)} != {expected} at offset {offset}"},
                    status=400)
            chord["spelling"] = spelling
            break
```

Write `umto["chords"] = chords` alongside the existing `umto["analysis"] = new_analysis` before `exercise.save()`. Keep `analysis_review_status = "reviewed"`.

- [ ] **Step 4: Run test, verify PASS**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/views/api_workbench.py apps/dashboard/tests/test_chordal_analysis_review.py
git commit -m "feat(review): persist per-chord respelling via review API"
```

### Task 6.2: Respelling UI controls

**Files:**
- Modify: `apps/dashboard/templates/dashboard/workbench.html` (`openAnalysisReview` row template ~445-453; `saveAnalysisReview` ~465-473)

- [ ] **Step 1: Render a per-note enharmonic toggle**

For each row, render the chord's notes from `row.spelling` (or computed default) with a small control per note offering the two enharmonic options (e.g. `A#`/`Bb`) computed from the note's pitch class. Selecting one updates an in-memory spelling array for that row and re-renders the Phase-5 preview.

- [ ] **Step 2: Include spelling in the POST body**

In `saveAnalysisReview`, add `spelling` to each row object alongside `offset` and `content`:

```javascript
return { offset: parseFloat(row.dataset.offset), content: content,
         spelling: readSpellingArray(row) };
```

- [ ] **Step 3: Manual verification**

Open a chordal exercise with a chromatic chord → flip a note's enharmonic → preview updates → Save Review → reopen exercise in Play/exercise view → respelling persists and renders.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/templates/dashboard/workbench.html
git commit -m "feat(review): per-note respelling editor"
```

### Task 6.3: Token-aware figure picker for Roman-numeral override

So a teacher correcting a mislabeled chord can insert stacked figures (6/5, 4/3, …) without knowing the Sebastian brace codes (`{z5}`, `{r3}`). The picker inserts the correct brace token into the focused `roman_numeral` field at the cursor.

**Files:**
- Modify: `apps/dashboard/templates/dashboard/workbench.html` (review panel; `openAnalysisReview` row template ~445-453)

Reference — canonical figure→token map (from `FIGURE_TOKEN_MAP` in `lab/static/js/src/models/exercise_definition.js:122`, using the z/u/r series so it renders stacked and round-trips through `stripFiguredBassTokens`):

| Button label | Inserted token |
|---|---|
| 6 | `{z}` |
| 6/4 | `{z4}` |
| 6/5 | `{z5}` |
| 7 | `{u}` |
| 4/3 | `{r3}` |
| 4/2 | `{r2}` |
| 4 | `{r}` |

- [ ] **Step 1: Render the picker row**

Add a single shared figure toolbar inside the review panel header (above `#analysisReviewRows`), plus track which `roman_numeral` input is focused:

```html
<div id="figurePicker" class="figure-picker">
  <span class="figure-picker-label">Insert figure:</span>
  <button type="button" data-token="{z}">6</button>
  <button type="button" data-token="{z4}">6/4</button>
  <button type="button" data-token="{z5}">6/5</button>
  <button type="button" data-token="{u}">7</button>
  <button type="button" data-token="{r3}">4/3</button>
  <button type="button" data-token="{r2}">4/2</button>
  <button type="button" data-token="{r}">4</button>
</div>
```

- [ ] **Step 2: Wire focus tracking + insertion**

```javascript
var activeRomanInput = null;

// Delegate: remember the last-focused roman_numeral input.
document.getElementById('analysisReviewRows').addEventListener('focusin', function (e) {
  if (e.target.matches('input[data-field="roman_numeral"]')) {
    activeRomanInput = e.target;
  }
});

document.getElementById('figurePicker').addEventListener('click', function (e) {
  var btn = e.target.closest('button[data-token]');
  if (!btn || !activeRomanInput) return;
  var token = btn.dataset.token;
  var el = activeRomanInput;
  var start = el.selectionStart != null ? el.selectionStart : el.value.length;
  var end = el.selectionEnd != null ? el.selectionEnd : el.value.length;
  el.value = el.value.slice(0, start) + token + el.value.slice(end);
  var caret = start + token.length;
  el.focus();
  el.setSelectionRange(caret, caret);
  el.dispatchEvent(new Event('input', { bubbles: true })); // triggers Phase-5 preview refresh
});
```

- [ ] **Step 3: Manual verification**

Open review → focus a `roman_numeral` field → type `V` → click `6/5` → field reads `V{z5}` → Phase-5 preview shows stacked `V⁶₅` → Save Review → exercise renders the stacked override.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/templates/dashboard/workbench.html
git commit -m "feat(review): token-aware figure picker for roman-numeral overrides"
```

---

## Docs to update (CLAUDE.md requirements)

- [ ] `docs/exercise_types.md` — note chordal exercises now carry key-aware + override-able spelling and a review/approval status. (No new exercise *type*, but behavior changed.)
- [ ] `docs/feedback_catalog.md` + `feedback_catalog.js` — the save→review toast (Task 4.2).
- [ ] If any new management command is added for backfilling spelling on existing chordal exercises (optional, not in scope above), follow the management-command docs rule.

## Out of scope (explicit)

- Hard approval gate (blocking serve/playlist on unreviewed). Soft only.
- Backfilling spelling onto already-saved chordal exercises (they render key-aware after Phase 1 regardless; explicit overrides only matter going forward). A backfill command can be a follow-up.
- Voices/chorale path changes — already correct.

## Self-review notes

- Spelling string format is identical everywhere: scientific pitch, `#`/`b`, e.g. `"Bb4"` — matching `_pitch_spelling`. JS `pitchFromSpellingString` and Python `spelling_str_to_cir_pitch` parse the same grammar.
- Positional ordering (visible then hidden) is consistent between capture (3.1/3.2), schema validation (`umto.py:59`), JS honor (2.1), Python honor (2.3), and review POST validation (6.1).
- Phase 1 is the only phase required to fix the current always-sharp display bug; Phases 2–6 are additive and independently shippable.
