# Interval Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `interval_generic` and `interval_specific` analysisType values to the existing `chorale_identification` exercise type, with Tonal.js as authoritative label source and `analyze.js` as a cross-check, plus a `compoundIntervals` boolean flag and admin UI.

**Architecture:** Extend `computeWindowLabel()` in `exercise_definition.js` with a dual-path interval branch (analyze.js + Tonal.js, always use Tonal, warn on mismatch); add `step`/`alter` to `ScoreTimeline` events so Tonal can compute spelled intervals; add `compoundIntervals` support throughout; wire admin fieldset and import command.

**Tech Stack:** RequireJS AMD modules, Tonal.js UMD bundle, Django admin forms, Python management commands.

---

## File Structure

- Modify: `lab/static/js/src/components/music/score_timeline.js`
  Adds `step` and `alter` to every timeline event (read-through from `item.pitch`).

- Modify: `lab/static/js/src/models/exercise_definition.js`
  Adds interval branch to `computeWindowLabel()`, Tonal.js dual-path, `compoundIntervals` support, updated `buildChoices()` fallback pools, `compoundIntervals` read in `parse()`.

- Add: `lab/static/js/lib/tonal.min.js`
  Tonal.js UMD bundle dropped into the existing lib directory.

- Modify: `harmony/settings/requirejs.py`
  Adds `tonal` path entry so RequireJS can load the bundle.

- Modify: `apps/exercises/management/commands/import_chorale.py`
  Adds `interval_generic`/`interval_specific` to `--analysis` choices, adds `--compound` flag, adds 2-voice validation, writes `compoundIntervals` to exercise data.

- Modify: `apps/exercises/forms.py`
  Adds `compound_intervals` checkbox field, `INTERVAL_ONLY_FIELDS`, `_detect_interval()`, `_configure_interval_fields()`, `_store_interval_settings()`.

- Modify: `apps/exercises/admin.py`
  Injects "Interval settings" fieldset when `analysisType` is an interval type.

---

### Task 1: Add `step` and `alter` to ScoreTimeline events

**Files:**
- Modify: `lab/static/js/src/components/music/score_timeline.js`

- [ ] **Step 1: Update note event push for `kind === 'note'` to include `step` and `alter`**

In `score_timeline.js`, line 102, change:
```javascript
timeline.push({ id: id++, onset: globalOnset, duration: durToTicks(item.duration), midi: pitchToMidi(item.pitch), staff: staffName, voiceIndex: vIdx, measureIndex: m, itemIndex: it, headIndex: 0 });
```
to:
```javascript
timeline.push({ id: id++, onset: globalOnset, duration: durToTicks(item.duration), midi: pitchToMidi(item.pitch), step: item.pitch.step, alter: item.pitch.alter || 0, staff: staffName, voiceIndex: vIdx, measureIndex: m, itemIndex: it, headIndex: 0 });
```

- [ ] **Step 2: Update note event push for `kind === 'chord'` to include `step` and `alter`**

In `score_timeline.js`, line 105, change:
```javascript
timeline.push({ id: id++, onset: globalOnset, duration: durToTicks(item.duration), midi: pitchToMidi(item.notes[h].pitch), staff: staffName, voiceIndex: vIdx, measureIndex: m, itemIndex: it, headIndex: h });
```
to:
```javascript
timeline.push({ id: id++, onset: globalOnset, duration: durToTicks(item.duration), midi: pitchToMidi(item.notes[h].pitch), step: item.notes[h].pitch.step, alter: item.notes[h].pitch.alter || 0, staff: staffName, voiceIndex: vIdx, measureIndex: m, itemIndex: it, headIndex: h });
```

- [ ] **Step 3: Verify existing chorale exercises still work**

Run: `./manage.py check`
Expected: `System check identified no issues (0 silenced).`

Open a chorale exercise in the browser. Confirm it loads and plays correctly — the `step`/`alter` additions are additive and should not affect existing behaviour.

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/score_timeline.js
git commit -m "feat: add step and alter fields to score timeline events"
```

---

### Task 2: Bundle Tonal.js and register with RequireJS

**Files:**
- Add: `lab/static/js/lib/tonal.min.js`
- Modify: `harmony/settings/requirejs.py`

- [ ] **Step 1: Download the Tonal.js UMD bundle**

Run:
```bash
curl -L "https://cdn.jsdelivr.net/npm/tonal@6/build/tonal.min.js" \
  -o lab/static/js/lib/tonal.min.js
```
Expected: file created at `lab/static/js/lib/tonal.min.js`, non-zero size.

Verify: `wc -c lab/static/js/lib/tonal.min.js` — should be > 50000 bytes.

- [ ] **Step 2: Confirm UMD export name**

Run:
```bash
node -e "const T = require('./lab/static/js/lib/tonal.min.js'); console.log(Object.keys(T).slice(0,10));"
```
Expected output includes `Interval` and `Note`.

- [ ] **Step 3: Register tonal path in requirejs.py**

In `harmony/settings/requirejs.py`, inside `configure()`, after the line:
```python
"paths": {
    "app": os.path.join(STATIC_URL, "js", "src"),
},
```
change to:
```python
"paths": {
    "app": os.path.join(STATIC_URL, "js", "src"),
    "tonal": os.path.join(STATIC_URL, "js", "lib", "tonal.min"),
},
```

- [ ] **Step 4: Add RequireJS shim for Tonal (it uses a global, not AMD)**

In `harmony/settings/requirejs.py`, add a `shim` entry alongside `paths`:
```python
REQUIREJS_CONFIG = {
    "baseUrl": os.path.join(STATIC_URL, "js", "lib"),
    "paths": {
        "app": os.path.join(STATIC_URL, "js", "src"),
        "tonal": os.path.join(STATIC_URL, "js", "lib", "tonal.min"),
    },
    "shim": {
        "tonal": {"exports": "Tonal"},
    },
    "config": {},
}
```

- [ ] **Step 5: Verify Django starts cleanly**

Run: `./manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/lib/tonal.min.js harmony/settings/requirejs.py
git commit -m "feat: bundle Tonal.js and register with RequireJS"
```

---

### Task 3: Add interval label computation to `exercise_definition.js`

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`

- [ ] **Step 1: Add `tonal` to the RequireJS define dependency array**

At the top of `exercise_definition.js`, the current define line is:
```javascript
define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
], function (_, Config, ScoreTimeline, Analyze, KeySignature) {
```
Change to:
```javascript
define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
  "tonal",
], function (_, Config, ScoreTimeline, Analyze, KeySignature, Tonal) {
```

- [ ] **Step 2: Add `midiEventToTonalName` helper after the existing `expandFiguredBassToken` helper**

After the closing brace of `expandFiguredBassToken` (around line 80), add:
```javascript
  function midiEventToTonalName(event) {
    var alterStr = "";
    if (event.alter > 0) {
      alterStr = new Array(event.alter + 1).join("#");
    } else if (event.alter < 0) {
      alterStr = new Array(-event.alter + 1).join("b");
    }
    var octave = Math.floor(event.midi / 12) - 1;
    return event.step.toUpperCase() + alterStr + octave;
    // e.g. { step: "F", alter: 1, midi: 66 } → "F#4"
  }

  function tonalIntervalToHarmonyLabFormat(itvl) {
    // Tonal returns number-first: "3m", "5P", "4A". HarmonyLab uses quality-first: "m3", "P5", "A4".
    var num = String(Tonal.Interval.num(itvl));
    var quality = Tonal.Interval.quality(itvl);
    return quality + num;
  }

  function computeIntervalViaTonal(lowerEvent, upperEvent, analysisType, compoundIntervals) {
    if (!lowerEvent || !upperEvent) return "";
    try {
      var lowerName = midiEventToTonalName(lowerEvent);
      var upperName = midiEventToTonalName(upperEvent);
      var raw = Tonal.Interval.distance(lowerName, upperName);
      if (!raw) return "";
      var itvl = compoundIntervals ? raw : Tonal.Interval.simplify(raw);
      if (analysisType === "interval_generic") {
        return String(Math.abs(Tonal.Interval.num(itvl)));
      }
      return tonalIntervalToHarmonyLabFormat(itvl);
    } catch (_err) {
      return "";
    }
  }
```

- [ ] **Step 3: Add interval branch to `computeWindowLabel()`**

`computeWindowLabel` currently starts with:
```javascript
  function computeWindowLabel(midiStack, analysisType, analyzer) {
    if (!midiStack || midiStack.length < 2 || !analyzer) {
      return "";
    }
    try {
      if (analysisType === "figured_bass") {
```

Change the signature and add the interval branch before the existing `figured_bass` branch:
```javascript
  function computeWindowLabel(midiStack, analysisType, analyzer, compoundIntervals, windowEvents) {
    if (!midiStack || midiStack.length < 2 || !analyzer) {
      return "";
    }
    try {
      if (analysisType === "interval_generic" || analysisType === "interval_specific") {
        var lowerMidi = midiStack[0];
        var upperMidi = midiStack[midiStack.length - 1];
        // Find the matching events for lower and upper notes (by midi value)
        var lowerEvent = _.find(windowEvents || [], function(e) { return e.midi === lowerMidi; });
        var upperEvent = _.find(windowEvents || [], function(e) { return e.midi === upperMidi; });

        // analyze.js path
        var analyzeLabel = "";
        try {
          var result = analyzer.to_interval([lowerMidi, upperMidi]);
          if (result && result.name) {
            analyzeLabel = analysisType === "interval_generic" ? result.size : result.name;
            analyzeLabel = normalizeAnalysisLabel(analyzeLabel);
          }
        } catch (_e) { analyzeLabel = ""; }

        // Tonal.js path (authoritative)
        var tonalLabel = computeIntervalViaTonal(lowerEvent, upperEvent, analysisType, compoundIntervals);
        tonalLabel = normalizeAnalysisLabel(tonalLabel);

        if (analyzeLabel && analyzeLabel !== tonalLabel) {
          console.warn("[interval] analyze/tonal mismatch:", analyzeLabel, "vs", tonalLabel, "midi:", lowerMidi, upperMidi);
        }
        return tonalLabel || analyzeLabel;
      }
      if (analysisType === "figured_bass") {
```

- [ ] **Step 4: Pass `compoundIntervals` and `windowEvents` through `buildAnalysisWindows` and `buildChoraleIdentificationProblems`**

`buildAnalysisWindows` currently returns `{ onset, events, midiStack }` per window. The events are already on the window object. Update `buildChoraleIdentificationProblems` to pass them through to `computeWindowLabel`:

Find the line in `buildChoraleIdentificationProblems`:
```javascript
    var labels = _.map(windows, function (window) {
      return computeWindowLabel(window.midiStack, analysisType, analyzer);
    });
```
Change to:
```javascript
    var compoundIntervals = exercise.compoundIntervals || false;
    var labels = _.map(windows, function (window) {
      return computeWindowLabel(window.midiStack, analysisType, analyzer, compoundIntervals, window.events);
    });
```

- [ ] **Step 5: Update `buildChoices()` fallback pools for interval types**

Find the existing fallback assignment in `buildChoices`:
```javascript
    var fallbacks = analysisType === "figured_bass"
      ? ["5/3", "6", "6/4", "6/5", "7"]
      : ["I", "ii", "IV", "V", "vi"];
```
Replace with:
```javascript
    var fallbacks = analysisType === "figured_bass"
      ? ["5/3", "6", "6/4", "6/5", "7"]
      : analysisType === "interval_generic"
      ? ["2", "3", "4", "5", "6", "7", "8"]
      : analysisType === "interval_specific"
      ? ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8"]
      : ["I", "ii", "IV", "V", "vi"];
```

- [ ] **Step 6: Read `compoundIntervals` in the `chorale_identification` branch of `parse()`**

In `parse()`, inside the `if (definition.type === "chorale_identification")` block, after the line:
```javascript
        exercise.analysisType = definition.analysisType || "roman";
```
add:
```javascript
        exercise.compoundIntervals = definition.compoundIntervals || false;
```

- [ ] **Step 7: Smoke test in the browser**

Import a 2-voice exercise with interval analysis (see Task 5 Step 1 for the command) and open it in the browser. Open DevTools console. Confirm:
- Labels appear under each onset window
- `[interval] analyze/tonal mismatch` warnings appear for any mismatches (informational only)
- No JS errors

- [ ] **Step 8: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat: add interval label computation with Tonal.js dual-path"
```

---

### Task 4: Backend — `import_chorale.py` interval support

**Files:**
- Modify: `apps/exercises/management/commands/import_chorale.py`

- [ ] **Step 1: Add `interval_generic` and `interval_specific` to `--analysis` choices and add `--compound` flag**

In `add_arguments`, change:
```python
        parser.add_argument('--analysis', choices=['roman', 'figured_bass'], default='roman', help='Analysis label type for identify mode')
```
to:
```python
        parser.add_argument('--analysis', choices=['roman', 'figured_bass', 'interval_generic', 'interval_specific'], default='roman', help='Analysis label type for identify mode')
        parser.add_argument('--compound', action='store_true', default=False, help='Allow compound intervals (default: reduce to within octave). Only applies to interval analysis types.')
```

- [ ] **Step 2: Add 2-voice validation helper and call it for interval types**

After the `corpus_path` loading block (around line 55), add this helper and call:
```python
        def count_voices(measures):
            if not measures:
                return 0
            first = measures[0].get('staves', {})
            return sum(len(stave.get('voices', [])) for stave in first.values())

        compound = options['compound']

        if analysis_type in ('interval_generic', 'interval_specific'):
            voice_count = count_voices(excerpt_measures)
            if voice_count != 2:
                raise CommandError(
                    f'Interval identification requires exactly 2 voices; '
                    f'found {voice_count} in {corpus_file}.'
                )
```

Place this block just after `excerpt_measures` is assigned (after the `if not excerpt_measures:` check).

- [ ] **Step 3: Write `compoundIntervals` into the identify exercise data and update `introText`**

Inside the `if mode == 'identify':` block, change:
```python
            exercise_data = {
                "type": "chorale_identification",
                "identMode": "submit",
                "analysisType": analysis_type,
                "score": {
                    "meta": meta,
                    "measures": excerpt_measures
                },
                "introText": f"Label the {analysis_label} for {bwv}, measures {start_measure+1}–{end_measure}.",
                "reviewText": f"Well done! You labeled all chords for {bwv}, measures {start_measure+1}–{end_measure}.",
                "key": meta.get("key", "C"),
                "staffDistribution": "chorale"
            }
```
to:
```python
            if analysis_type == 'roman':
                analysis_label = 'Roman numerals'
            elif analysis_type == 'figured_bass':
                analysis_label = 'figured bass'
            elif analysis_type == 'interval_generic':
                analysis_label = 'generic intervals'
            else:
                analysis_label = 'specific intervals'

            if analysis_type in ('interval_generic', 'interval_specific'):
                intro = f"Identify the {analysis_label} in this two-voice excerpt of {bwv}, measures {start_measure+1}–{end_measure}."
            else:
                intro = f"Label the {analysis_label} for {bwv}, measures {start_measure+1}–{end_measure}."

            exercise_data = {
                "type": "chorale_identification",
                "identMode": "submit",
                "analysisType": analysis_type,
                "compoundIntervals": compound,
                "score": {
                    "meta": meta,
                    "measures": excerpt_measures
                },
                "introText": intro,
                "reviewText": f"Well done! You completed {bwv}, measures {start_measure+1}–{end_measure}.",
                "key": meta.get("key", "C"),
                "staffDistribution": "chorale"
            }
```

Also remove the now-redundant `analysis_label` line that was there before (the `analysis_label = 'Roman numerals' if analysis_type == 'roman' else 'figured bass'` line).

- [ ] **Step 4: Verify command works end-to-end**

First find a 2-voice CIR file in the corpus:
```bash
python3 -c "
import json, glob, sys
for f in sorted(glob.glob('data/corpus/bach/*.json')):
    d = json.load(open(f))
    m = d.get('score',{}).get('measures',[{}])[0]
    total = sum(len(s.get('voices',[])) for s in m.get('staves',{}).values())
    if total == 2:
        print(f, total, 'voices'); sys.exit(0)
print('no 2-voice file found')
"
```

If no 2-voice file exists, test the error path with a 4-voice file:
```bash
./manage.py import_chorale data/corpus/bach/bwv1.6.json \
  --author=admin@example.com --start=0 --end=2 \
  --mode identify --analysis interval_specific
```
Expected: `CommandError: Interval identification requires exactly 2 voices; found 4 in bwv1.6.json.`

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/import_chorale.py
git commit -m "feat: add interval analysis types and --compound flag to import_chorale"
```

---

### Task 5: Admin — "Interval settings" fieldset

**Files:**
- Modify: `apps/exercises/forms.py`
- Modify: `apps/exercises/admin.py`

- [ ] **Step 1: Add `compound_intervals` field and interval helpers to `ExerciseForm`**

In `apps/exercises/forms.py`, after the `ident_mode` field definition (around line 485), add:
```python
    # ---- Interval-only fields ----
    compound_intervals = forms.BooleanField(
        required=False,
        label="Allow compound intervals",
        help_text="When checked, intervals larger than an octave are labeled as compound (10th, 12th, etc.). Default: reduce to within the octave.",
        initial=False,
    )
```

Add `"compound_intervals"` to `field_order` after `"ident_mode"`:
```python
        "ident_mode",
        "compound_intervals",
    ]
```

After `IDENT_ONLY_FIELDS = ["ident_mode"]` (line 925), add:
```python
    INTERVAL_ANALYSIS_TYPES = ("interval_generic", "interval_specific")

    INTERVAL_ONLY_FIELDS = ["compound_intervals"]
```

After `_store_identification_settings` (line 973), add:
```python
    def _detect_interval(self):
        data = {}
        if self.instance and getattr(self.instance, "data", None):
            data = self.instance.data
        return data.get("analysisType") in self.INTERVAL_ANALYSIS_TYPES

    def _configure_interval_fields(self):
        if not self._detect_interval():
            for field in self.INTERVAL_ONLY_FIELDS:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
            return
        if self.instance and getattr(self.instance, "data", None):
            compound = self.instance.data.get("compoundIntervals", False)
            if "compound_intervals" in self.fields:
                self.fields["compound_intervals"].initial = compound

    def _store_interval_settings(self, instance):
        instance.data["compoundIntervals"] = bool(self.cleaned_data.get("compound_intervals", False))
```

- [ ] **Step 2: Call the new interval helpers in `__init__` and `save`**

In `__init__`, after `self._configure_identification_fields()`:
```python
        self._configure_interval_fields()
```

In `save`, after `if self._is_identification: self._store_identification_settings(instance)`:
```python
            if self._detect_interval():
                self._store_interval_settings(instance)
```

- [ ] **Step 3: Add "Interval settings" fieldset to admin**

In `apps/exercises/admin.py`, in `get_fieldsets`, after the existing `if identification:` block (around line 213), add:
```python
        interval = False
        if obj and isinstance(getattr(obj, "data", None), dict):
            interval = obj.data.get("analysisType") in ("interval_generic", "interval_specific")
        elif request.method == "POST":
            # POST data doesn't carry analysisType directly; rely on obj for existing records
            pass
        if interval:
            base_fieldsets.append(
                (
                    "Interval settings",
                    {"fields": tuple(ExerciseForm.INTERVAL_ONLY_FIELDS)},
                )
            )
```

- [ ] **Step 4: Run Django system check**

Run: `./manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Manually verify admin fieldset**

1. Create a `chorale_identification` exercise with `analysisType: "interval_specific"` via the JSON editor in Django admin.
2. Save, then reopen the exercise.
3. Confirm "Interval settings" fieldset appears with the "Allow compound intervals" checkbox.
4. Confirm "Identification settings" fieldset (feedback mode) also appears.
5. Check the box, save again, reopen — confirm `compoundIntervals: true` is in the exercise's JSON data.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/forms.py apps/exercises/admin.py
git commit -m "feat: add Interval settings admin fieldset with compound intervals checkbox"
```

---

### Task 6: End-to-End Verification

**Files:** No changes — verification only.

- [ ] **Step 1: Verify Django check and run existing tests**

Run:
```bash
./manage.py check
./manage.py test apps.exercises -v 2
```
Expected: no errors, all existing tests pass.

- [ ] **Step 2: Verify 4-voice import rejection**

Run:
```bash
./manage.py import_chorale data/corpus/bach/bwv1.6.json \
  --author=admin@example.com --start=0 --end=2 \
  --mode identify --analysis interval_specific
```
Expected output contains: `Interval identification requires exactly 2 voices; found 4`

- [ ] **Step 3: Verify roman and figured_bass still work (no regression)**

Run:
```bash
./manage.py import_chorale data/corpus/bach/bwv1.6.json \
  --author=admin@example.com --start=0 --end=4 \
  --mode identify --analysis roman --public
```
Expected: `Successfully created exercise ...`

Open the exercise in the browser. Confirm Roman numeral popup works, no JS errors.

- [ ] **Step 4: Manually create an interval exercise via JSON editor and test in browser**

In Django admin, create a new Exercise with:
```json
{
  "type": "chorale_identification",
  "identMode": "practice",
  "analysisType": "interval_specific",
  "compoundIntervals": false,
  "key": "jC_",
  "staffDistribution": "chorale",
  "introText": "Identify the intervals.",
  "score": {
    "meta": { "key": "C", "time": "4/4" },
    "measures": [
      {
        "staves": {
          "treble": {
            "voices": [
              {
                "items": [
                  { "kind": "note", "pitch": { "step": "E", "alter": 0, "octave": 4 }, "duration": { "type": "q", "dots": 0 } },
                  { "kind": "note", "pitch": { "step": "G", "alter": 0, "octave": 4 }, "duration": { "type": "q", "dots": 0 } }
                ]
              }
            ]
          },
          "bass": {
            "voices": [
              {
                "items": [
                  { "kind": "note", "pitch": { "step": "C", "alter": 0, "octave": 3 }, "duration": { "type": "q", "dots": 0 } },
                  { "kind": "note", "pitch": { "step": "C", "alter": 0, "octave": 3 }, "duration": { "type": "q", "dots": 0 } }
                ]
              }
            ]
          }
        }
      }
    ]
  }
}
```

Open the exercise in the browser. Confirm:
- Score renders with 2 voices
- `?` slots appear below each onset
- Clicking a slot opens popup with 5 choices including `"m3"` (E4→G4) and `"M10"` or `"m3"` depending on voicing
- In DevTools console, check for `[interval] analyze/tonal mismatch` warnings (informational)
- Selecting the correct answer turns the label green

- [ ] **Step 5: Test compound intervals**

Edit the exercise data to set `"compoundIntervals": true`. Reload. Confirm intervals spanning more than an octave are now labeled with their full size (e.g. `"m10"` instead of `"m3"`).

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test: verify interval identification end-to-end"
```

---

## Self-Review

**Spec coverage:**
- ✓ `interval_generic` / `interval_specific` analysisType values — Task 3
- ✓ `compoundIntervals` field — Tasks 3, 4, 5
- ✓ Dual-path: analyze.js + Tonal.js, always use Tonal, warn on mismatch — Task 3
- ✓ `step`/`alter` on timeline events for Tonal — Task 1
- ✓ Tonal.js bundled, RequireJS path registered — Task 2
- ✓ Label format reformatted from Tonal number-first to quality-first — Task 3
- ✓ `Interval.simplify()` used for compound reduction — Task 3
- ✓ Distractor fallback pools for interval types — Task 3
- ✓ `--analysis interval_*` and `--compound` flag in import command — Task 4
- ✓ 2-voice validation at import time — Task 4
- ✓ "Interval settings" fieldset in admin (separate from "Identification settings") — Task 5
- ✓ `compoundIntervals` round-tripped through admin form save/load — Task 5

**Placeholder scan:** No TBD, TODO, or vague steps present.

**Type consistency:**
- `compoundIntervals` (camelCase) used consistently in JS and as the JSON key
- `compound_intervals` (snake_case) used consistently as the Django form field name
- `INTERVAL_ONLY_FIELDS`, `INTERVAL_ANALYSIS_TYPES` defined before use
- `computeIntervalViaTonal` defined before `computeWindowLabel` calls it
