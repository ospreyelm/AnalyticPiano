# HarmonyLab Pitch Identification Limits - Search Results

## Summary

**The limitation to 4 measures/windows is introduced at IMPORT time, not at runtime.** Identification exercises inherit the measure range from their source exercise through the shared score data.

## Key Findings

### 1. **WHERE LIMITS ARE APPLIED**

#### Import Time (Django Backend)
**File:** [`apps/exercises/management/commands/import_chorale.py`](apps/exercises/management/commands/import_chorale.py) (lines 36-37, 88)

```python
parser.add_argument('--start', type=int, default=0, help='Start measure (0-indexed)')
parser.add_argument('--end', type=int, default=4, help='End measure (exclusive)')
...
excerpt_measures = measures[start_measure:end_measure]
```

The excerpt is sliced at import time:
- Default range: `--start=0 --end=4` → **4 measures only**
- Both `chorale` (play) and `chorale_identification` (identify) exercises store this pre-sliced excerpt

#### Duplication (Django Backend)
**File:** [`apps/exercises/management/commands/duplicate_chorale_as_identification.py`](apps/exercises/management/commands/duplicate_chorale_as_identification.py) (line 43)

```python
score = copy.deepcopy(source_data.get("score", {}))
```

When duplicating a chorale as identification, the new exercise gets a **copy of the source's score**, which is already sliced to 4 measures (if that's how the source was imported).

### 2. **FRONTEND BUILD PROCESS (NO LIMITING)**

#### `buildChoraleIdentificationProblems()`
**File:** [`lab/static/js/src/models/exercise_definition.js`](lab/static/js/src/models/exercise_definition.js) (lines 301-334)

```javascript
function buildChoraleIdentificationProblems(exercise) {
  var score = exercise.score || {};
  var timeline = ScoreTimeline && ScoreTimeline.buildTimeline
    ? ScoreTimeline.buildTimeline(score)  // ← NO options passed
    : [];
  var windows = buildAnalysisWindows(timeline);
  
  // Creates ONE problem per window (onset)
  return _.map(windows, function (window, idx) {
    return {
      windowIndex: idx,
      onset: window.onset,
      answer: answer,
      choices: buildChoices(answer, labels, analysisType, compoundIntervals),
    };
  });
}
```

**Key point:** `buildTimeline()` is called with **no options**, so it processes the ENTIRE score passed to it. If the score contains 4 measures, 4 measures worth of problems are generated. If it contained 8 measures, 8 measures would be generated.

#### `ScoreTimeline.buildTimeline()`
**File:** [`lab/static/js/src/components/music/score_timeline.js`](lab/static/js/src/components/music/score_timeline.js) (lines 39-56)

```javascript
function buildTimeline(score, opts) {
  opts = opts || {};
  var timeline = [];
  
  var totalMeasures = score.measures.length;
  var startMeasure = Math.max(0, opts.startMeasure || 0);
  var maxMeasures = opts.maxMeasures != null ? opts.maxMeasures : totalMeasures;
  var endMeasure = Math.min(totalMeasures, startMeasure + maxMeasures);
  // ... builds timeline for measures [startMeasure, endMeasure)
}
```

The timeline builder DOES support `{ startMeasure, maxMeasures }` options, but **`buildChoraleIdentificationProblems()` never uses them**.

### 3. **RENDERING (4-MEASURE VIEW LIMIT - VISUAL ONLY)**

#### Exercise Sheet Setup
**File:** [`lab/static/js/src/components/music/exercise_sheet.js`](lab/static/js/src/components/music/exercise_sheet.js) (lines 455-463)

```javascript
initChoraleMode: function () {
  var maxMeasures = 4;
  this._chorale = { maxMeasures: maxMeasures, startMeasure: 0 };
  // ...
}
```

This hardcoded 4 is a **rendering/viewport limit**, not a data limit. It's used when calling `VexflowAdapter.render()`:

```javascript
VexFlowAdapter.render(score, this.vexRenderer, {
  width: canvas.width,
  height: canvas.height,
  maxMeasures: (this._chorale && this._chorale.maxMeasures) || 4,  // line 782
  startMeasure: startMeasure,
  // ...
});
```

This only affects what's displayed on screen - all 4+ measures can still be rendered by paging.

### 4. **THE EXCERPT FIELD (UNUSED)**

Both `chorale` and `chorale_identification` exercises store an `excerpt` object in exercise.data:

**File:** [`apps/exercises/management/commands/import_chorale.py`](apps/exercises/management/commands/import_chorale.py) (lines 215-217)

```python
"excerpt": {
    "startMeasure": start_measure,      # e.g., 0
    "endMeasure": end_measure           # e.g., 4
}
```

**Current Status:** This field is **stored but never used** in the JavaScript frontend:

- **NOT accessed** in `exercise_definition.js` when parsing chorale_identification
- **NOT passed** to `ScoreTimeline.buildTimeline()`
- **NOT used** to limit problems generation

### 5. **COMPLETE DATA FLOW**

```
import_chorale --start=0 --end=4 --mode=play
    ↓
Exercise.data = {
  "type": "chorale",
  "score": {
    "measures": [m0, m1, m2, m3]  ← 4 measures ONLY
  },
  "excerpt": { "startMeasure": 0, "endMeasure": 4 }
}
    ↓
duplicate_chorale_as_identification(exercise_id)
    ↓
score_copy = copy.deepcopy(source.data['score'])
Exercise.data = {
  "type": "chorale_identification",
  "score": score_copy  ← Still 4 measures!
}
    ↓
ExerciseDefinition.parse(data)
    → buildChoraleIdentificationProblems(exercise)
        → ScoreTimeline.buildTimeline(exercise.score)
            → Builds timeline from ALL 4 measures
        → buildAnalysisWindows(timeline)
        → Returns problems array with 4 windows
```

## The Problem

**The 4-measure limit is a data constraint, not a code constraint:**

1. **At import:** `import_chorale.py` defaults to `--end=4`, slicing measures before saving
2. **At duplication:** `duplicate_chorale_as_identification.py` copies the pre-sliced score
3. **At problem building:** `buildChoraleIdentificationProblems()` creates one problem per onset in whatever measures are present

**The `excerpt` metadata is stored but unused** — it could theoretically be used to regenerate problems for the full original chorale, but it's not implemented.

## Code Locations Summary

| Component | File | Line(s) | What it Does |
|-----------|------|---------|--------------|
| Import default | `import_chorale.py` | 36-37 | `--end` defaults to 4 |
| Import slicing | `import_chorale.py` | 88 | `excerpt_measures = measures[start_measure:end_measure]` |
| Problem building | `exercise_definition.js` | 303-304 | Calls `buildTimeline(score)` with NO options |
| Timeline builder | `score_timeline.js` | 39-56 | Supports `{maxMeasures}` but not used for identification |
| Duplication | `duplicate_chorale_as_identification.py` | 43 | `score = copy.deepcopy(source_data.get("score", {}))` |
| Excerpt metadata | `import_chorale.py` | 215-217 | Stored but **not used** |
| Rendering limit | `exercise_sheet.js` | 462 | Hardcoded `maxMeasures = 4` for viewport only |

## Where to Fix

**To allow exercises with more problems:**

1. **Option A (Recommended):** Modify `duplicate_chorale_as_identification.py` to accept `--start` and `--end` options and re-slice the score, OR store/preserve the original full score and use `excerpt` metadata
2. **Option B:** Modify `buildChoraleIdentificationProblems()` to accept and pass through `{ startMeasure, maxMeasures }` options to `buildTimeline()`
3. **Option C:** Modify `import_chorale.py` to use a higher default `--end` value (currently hardcoded to 4)
