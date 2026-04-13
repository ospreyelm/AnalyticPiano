# Interval Identification Exercise Type — Design Spec

_Date: 2026-04-11_
_Status: Approved_

---

## Overview

Two new `analysisType` values — `interval_generic` and `interval_specific` — extend the existing `chorale_identification` exercise type to support interval identification exercises. No new exercise type is introduced; all existing rendering, grading, and UX machinery is reused unchanged.

- `interval_generic` — labels are interval sizes without quality: `"2"`, `"3"`, `"5"`, `"8"` etc.
- `interval_specific` — labels include quality: `"m3"`, `"M3"`, `"P5"`, `"A4"`, `"d7"` etc.

These exercises require exactly 2 voices in the score. This is enforced at import time only — no runtime check.

---

## Data Format

Extends `chorale_identification` with one new optional field. Example:

```json
{
  "type": "chorale_identification",
  "identMode": "submit",
  "analysisType": "interval_specific",
  "compoundIntervals": false,
  "score": { "meta": { "key": "C", "time": "4/4" }, "measures": [...] },
  "key": "jC_",
  "staffDistribution": "chorale",
  "introText": "Identify the intervals in this two-voice excerpt.",
  "reviewText": "Well done! You identified all intervals correctly."
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `compoundIntervals` | boolean | `false` | When `false`, intervals larger than an octave are reduced (a 10th → 3rd). When `true`, compound intervals are labeled as-is (10th, 12th, etc.). Only meaningful for `interval_generic` and `interval_specific` analysis types. |

`problems` are computed client-side by `parse()` as with existing `chorale_identification` — not stored in the DB.

---

## Interval Label Computation

### Dual-path approach

For `interval_generic` and `interval_specific`, the label at each window is computed using **both** `analyze.js` and Tonal.js, then compared:

```javascript
var analyzeLabel = computeIntervalViaAnalyze(midiStack, analysisType, analyzer);
var tonalLabel   = computeIntervalViaTonal(midiStack, analysisType, cirEvents);

if (analyzeLabel && analyzeLabel === tonalLabel) {
  return analyzeLabel;           // agreement — use it
} else {
  if (analyzeLabel !== tonalLabel) {
    console.warn(
      "[interval] analyze/tonal mismatch:",
      analyzeLabel, "vs", tonalLabel,
      "midi:", midiStack
    );
  }
  return tonalLabel;             // always trust Tonal.js result
}
```

This comparison runs on every exercise load. The `console.warn` output shows exactly where `analyze.js` is wrong, making it easy to improve over time. Once confidence in `analyze.js` is established, the fallback can be removed.

### analyze.js path

Calls the existing `analyzer.to_interval([lower, upper])` where `lower` and `upper` are the lowest and highest MIDI notes in `midiStack` (already sorted). Returns `.size` for generic, `.name` for specific. May return `""` for chromatic/augmented/diminished intervals when the dyad context is insufficient for enharmonic resolution.

### Tonal.js path

Uses the CIR note spelling (step + alter) stored in the score events, available via `ScoreTimeline` timeline events. Each timeline event has a `step` and `alter` field (e.g. `{ step: "F", alter: 1 }` for F#). These are used to construct Tonal note names (e.g. `"F#4"`), then:

```javascript
var raw = Tonal.Interval.distance(lowerNoteName, upperNoteName);
// Tonal returns number-first format: "3m", "5P", "4A", "5d"

// Apply compound reduction unless compoundIntervals is true
var itvl = compoundIntervals ? raw : Tonal.Interval.simplify(raw);
// e.g. "10m" → "3m" when compoundIntervals=false; stays "10m" when true

// Reformat to quality-first (HarmonyLab convention: "m3", "P5", "A4", "d5")
function tonalToHarmonyLabFormat(itvl) {
  var num = Tonal.Interval.num(itvl).toString();
  var quality = Tonal.Interval.quality(itvl);
  return quality + num;  // e.g. "3m" → "m3", "5P" → "P5"
}

// For interval_specific:
var label = tonalToHarmonyLabFormat(itvl);
// e.g. "m3", "P5", "A4", "d7", "m10" (if compoundIntervals=true)

// For interval_generic:
var label = Tonal.Interval.num(itvl).toString();
// e.g. "3", "5", "4", "7", "10" (if compoundIntervals=true)
```

Tonal.js handles all diatonic and chromatic intervals correctly including augmented and diminished qualities, because it works from note spellings rather than semitone counts alone.

**Distractor pool for compound mode:** When `compoundIntervals` is `true`, the fixed fallback pool for `interval_specific` extends to include compound labels: `["m9", "M9", "m10", "M10", "P11", "P12", "m13", "M13", "m14", "M14"]`. The generic pool extends to `["9", "10", "11", "12", "13", "14", "15"]`. As before, distractors are sampled from other windows in the excerpt first.

### ScoreTimeline event shape

`ScoreTimeline.buildTimeline()` currently emits events with `midi` only — `step` and `alter` are not included. The Tonal.js path requires these fields to construct spelled note names. As part of this implementation, `score_timeline.js` will be updated to include `step` and `alter` on each event:

```javascript
// note event (current)
{ id, onset, duration, midi, staff, voiceIndex, measureIndex, itemIndex, headIndex }

// note event (after change)
{ id, onset, duration, midi, step, alter, staff, voiceIndex, measureIndex, itemIndex, headIndex }
```

`step` is the note letter (`"C"`, `"D"`, ..., `"B"`) and `alter` is the chromatic alteration integer (`-2`, `-1`, `0`, `1`, `2`). Both are already available in the CIR `item.pitch` object passed to `pitchToMidi()` — this is a read-through addition only, no logic changes to the timeline builder.

The Tonal.js path in `computeWindowLabel` then builds spelled note names from these fields:

```javascript
function midiEventToTonalName(event) {
  var alterStr = event.alter === 0 ? "" : event.alter > 0
    ? "#".repeat(event.alter) : "b".repeat(-event.alter);
  return event.step.toUpperCase() + alterStr + Math.floor(event.midi / 12) - 1;
  // e.g. { step: "F", alter: 1, midi: 66 } → "F#4"
}
```

---

## Distractor Pool

`buildChoices()` gains two new fallback cases:

```javascript
var fallbacks = analysisType === "figured_bass"
  ? ["5/3", "6", "6/4", "6/5", "7"]
  : analysisType === "interval_generic"
  ? ["2", "3", "4", "5", "6", "7", "8"]
  : analysisType === "interval_specific"
  ? ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8"]
  : ["I", "ii", "IV", "V", "vi"];
```

As with existing types, distractors are first sampled from other windows in the excerpt (real labels from the piece), with the fixed pool used only to fill gaps when the excerpt lacks variety.

---

## Backend: `import_chorale.py`

The `--analysis` argument gains two new choices:

```python
parser.add_argument(
  '--analysis',
  choices=['roman', 'figured_bass', 'interval_generic', 'interval_specific'],
  default='roman'
)
```

The `--analysis` argument gains two new choices and a `--compound` flag:

```python
parser.add_argument('--compound', action='store_true',
    help='Allow compound intervals (default: reduce to within octave)')
```

When `--mode identify` and `analysisType` is an interval type, the command validates that the score has exactly 2 voices and writes `compoundIntervals` into the exercise data:

```python
def count_voices(measures):
    if not measures:
        return 0
    first = measures[0].get('staves', {})
    return sum(len(stave.get('voices', [])) for stave in first.values())

if analysis_type in ('interval_generic', 'interval_specific'):
    if count_voices(excerpt_measures) != 2:
        raise CommandError(
            f'Interval identification requires exactly 2 voices; '
            f'found {count_voices(excerpt_measures)}.'
        )

# In exercise_data:
"compoundIntervals": options['compound'],  # True if --compound flag passed
```

`introText` is adjusted for interval exercises:

```
"Identify the intervals in this two-voice excerpt of BWV1.6, measures 1–4."
```

No other backend changes. The `duplicate_chorale_as_identification` command passes `analysisType` and `compoundIntervals` through unchanged — callers are responsible for only using interval types on 2-voice source exercises.

---

## Frontend: Tonal.js Integration

### Bundling

Download the Tonal.js UMD bundle (`tonal.min.js`) and place it in `lab/static/js/lib/tonal.min.js`.

Add a `paths` entry in `harmony/settings/requirejs.py`:

```python
REQUIREJS_CONFIG["paths"]["tonal"] = os.path.join(STATIC_URL, "js", "lib", "tonal.min")
```

### Usage in `exercise_definition.js`

Add `"tonal"` to the RequireJS dependency list for `exercise_definition.js`. Tonal is only called from within `computeWindowLabel()` for interval analysis types — no other module is affected.

---

## Admin: "Interval settings" fieldset

A new **Interval settings** fieldset is shown in the Django admin exercise change form when `data.analysisType` is `interval_generic` or `interval_specific`. It contains a single checkbox:

- **Allow compound intervals** (`compoundIntervals`) — unchecked by default

This fieldset is separate from the existing **Identification settings** fieldset (feedback mode), which applies to all identification types regardless.

Changes required:
- `apps/exercises/forms.py` — detect interval analysis types, serialize/deserialize `compoundIntervals`
- `apps/exercises/admin.py` — inject "Interval settings" fieldset when analysis type is an interval type

---

## Files Touched

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_definition.js` | Add `interval_generic`/`interval_specific` branch in `computeWindowLabel()`; add Tonal.js dual-path comparison; pass `compoundIntervals` through `parse()`; update `buildChoices()` fallback pool |
| `lab/static/js/src/components/music/score_timeline.js` | Add `step` and `alter` fields to each timeline event (read from `item.pitch`, no logic change) |
| `lab/static/js/lib/tonal.min.js` | New file — Tonal.js UMD bundle |
| `harmony/settings/requirejs.py` | Add `tonal` path entry |
| `apps/exercises/management/commands/import_chorale.py` | Add `interval_generic`/`interval_specific` to `--analysis` choices; add `--compound` flag; add 2-voice validation; write `compoundIntervals` to exercise data |
| `apps/exercises/forms.py` | Detect interval analysis types; serialize/deserialize `compoundIntervals` checkbox |
| `apps/exercises/admin.py` | Inject "Interval settings" fieldset when `analysisType` is an interval type |

### Files NOT touched

- `analyze.js` — consumed read-only; no changes
- `identification_grader.js` — used as-is
- `exercise_sheet.js` — no changes; interval exercises use the same popup/label UX
- `exercise_context.js` — no changes; interval exercises are treated as `isChoraleIdentification()`

---

## Data Flow

```
import_chorale --mode identify --analysis interval_specific [--compound]
    → validate 2 voices
    → write chorale_identification record with analysisType: "interval_specific",
      compoundIntervals: false (or true if --compound)
    ↓
Exercise.data (Django DB)
    ↓ served as JSON to the browser
ExerciseDefinition.parse()
    → isChoraleIdentification() = true
    → reads compoundIntervals (default false)
    → buildChoraleIdentificationProblems()
        → ScoreTimeline.buildTimeline() → events with step/alter/midi
        → buildAnalysisWindows() → midiStack + lower/upper events per window
        → computeWindowLabel(midiStack, "interval_specific", analyzer, compoundIntervals, events)
            → analyze.js: to_interval([lower, upper]) → label or ""
            → Tonal.js: Interval.distance(lowerName, upperName)
                → simplify if !compoundIntervals
                → reformat to quality-first ("3m" → "m3")
            → compare, warn on mismatch, always return Tonal result
        → buildChoices(answer, allLabels, analysisType, compoundIntervals)
    → problems[] populated
    ↓
ExerciseSheet — identical to chorale_identification (popup, labels, grading)
    ↓
IdentificationGrader.grade() → correct/incorrect/partial
```

---

## Known Limitations

- The 2-voice constraint is enforced at import time only. If a `chorale_identification` record is manually edited in the DB to have more voices with an interval `analysisType`, `computeWindowLabel` will silently use the lowest and highest MIDI note of however many notes are sounding.
- Tonal.js is the authoritative source for interval labels until `analyze.js` is validated. The `console.warn` output is the mechanism for tracking discrepancies.

---

## Out of Scope

- Improving `analyze.js` interval logic — deferred, driven by `console.warn` output
- Removing the Tonal.js fallback — deferred until `analyze.js` is validated
- 2-voice constraint enforcement in `duplicate_chorale_as_identification` — deferred
- UI distinction between interval types and Roman numeral types in label rendering
