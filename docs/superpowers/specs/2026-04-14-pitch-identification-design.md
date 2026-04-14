# Pitch Identification Exercise Type — Design Spec

_Date: 2026-04-14_
_Status: Approved_

---

## Overview

Six new `analysisType` values — `note_name`, `solfege`, `do_based_solfege`, `scale_degree`, `fixed_do`, `pitch_class` — extend the existing `chorale_identification` exercise type to support pitch identification exercises. No new exercise type is introduced; all existing rendering, grading, and UX machinery is reused unchanged.

These exercises show a **single note** at a time from a **single voice** of a CIR score. The student clicks a `?` slot below the staff and selects the correct label from a popup of 5 choices. This is the mirror image of the existing `matching` exercises — instead of seeing a label and playing the note, the student sees the note and picks the label.

---

## Analysis Types

| `analysisType` | Label shown | Source method |
|---|---|---|
| `note_name` | "C", "F♯", "B♭" | `analyzer.to_note_name([midi])` |
| `solfege` | "Do", "Re", "Mi"… (la-based for minor) | `analyzer.to_solfege([midi])` |
| `do_based_solfege` | "Do", "Re", "Mi"… (do-based for minor) | `analyzer.to_do_based_solfege([midi])` |
| `scale_degree` | "1", "b3", "#4"… | `analyzer.to_scale_degree([midi])` |
| `fixed_do` | "Do", "Re", "Mi"… (fixed, letter-based) | `analyzer.to_fixed_do([midi])` |
| `pitch_class` | "0"–"11" | `analyzer.to_pitch_class([midi]).toString()` |

---

## Data Format

```json
{
  "type": "chorale_identification",
  "analysisType": "note_name",
  "identMode": "practice",
  "score": { "meta": { "key": "G", "time": "4/4" }, "measures": [...] },
  "key": "jG_",
  "staffDistribution": "chorale",
  "introText": "Name each note in the soprano voice.",
  "reviewText": "Well done!"
}
```

The score stored in the DB contains **one voice only** — all other voices are stripped at import time. Each onset window has exactly one note. No new fields beyond `analysisType`.

`problems` are computed client-side by `parse()` as with all `chorale_identification` exercises — not stored in the DB.

---

## Label Computation

`computeWindowLabel()` in `exercise_definition.js` gains a new branch for pitch analysis types. All six types call directly into `analyze.js` — no Tonal.js needed (pitch labels are unambiguous from MIDI + key).

```javascript
function isPitchAnalysisType(analysisType) {
  return analysisType === "note_name" ||
         analysisType === "solfege" ||
         analysisType === "do_based_solfege" ||
         analysisType === "scale_degree" ||
         analysisType === "fixed_do" ||
         analysisType === "pitch_class";
}

// In computeWindowLabel():
if (isPitchAnalysisType(analysisType)) {
  var midi = midiStack[0];
  if (analysisType === "note_name")         return analyzer.to_note_name([midi]);
  if (analysisType === "solfege")           return analyzer.to_solfege([midi]);
  if (analysisType === "do_based_solfege")  return analyzer.to_do_based_solfege([midi]);
  if (analysisType === "scale_degree")      return analyzer.to_scale_degree([midi]);
  if (analysisType === "fixed_do")          return analyzer.to_fixed_do([midi]);
  if (analysisType === "pitch_class")       return analyzer.to_pitch_class([midi]).toString();
}
```

**Single-note safety net:** if `midiStack.length !== 1` when a pitch analysis type is active, `computeWindowLabel()` logs a `console.warn` and returns `""`. Real enforcement is at import time.

---

## Distractor Pools

`buildChoices()` gains new fallback cases. Real labels from other windows in the excerpt are sampled first; the fixed pool fills gaps only.

| `analysisType` | Fallback pool |
|---|---|
| `note_name` | `["C", "D", "E", "F", "G", "A", "B"]` |
| `solfege` / `do_based_solfege` / `fixed_do` | `["Do", "Re", "Mi", "Fa", "So", "La", "Ti"]` |
| `scale_degree` | `["1", "2", "3", "4", "5", "6", "7"]` |
| `pitch_class` | `["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]` |

---

## Dashboard Import UI

On the chorale exercise edit page, a new **"Duplicate as pitch identification"** button opens a modal dialog with:

- **Voices** — checkboxes: ☑ Soprano ☑ Alto ☑ Tenor ☑ Bass (all checked by default)
- **Analysis type** — dropdown: Note name / Solfege / Do-based solfege / Scale degree / Fixed Do / Pitch class (default: Note name)
- **Identification mode** — dropdown: Practice / Submit / Test (default: Practice)
- A **Create** button

Submitting creates one new `chorale_identification` exercise per checked voice. Each exercise gets:
- The CIR score stripped to that voice only
- `description`: e.g. `"BWV1.6 mm.1-4 – Soprano (note name)"`
- `analysisType`: the selected analysis type
- `identMode`: the selected mode
- `staffDistribution`: `"chorale"`
- `key`: inherited from the source exercise

### SATB → staff/voice index mapping

| Voice | Staff | Voice index |
|---|---|---|
| Soprano | treble | 0 |
| Alto | treble | 1 |
| Tenor | bass | 0 |
| Bass | bass | 1 |

### Voice stripping (Python)

Given a CIR score and a voice name, the stripping function:
1. Identifies the target staff name and voice index from the mapping above
2. Builds a new score with only that staff, containing only that voice
3. Validates that every measure window contains exactly one note (no chords, no rests-only windows) — raises an error if not

```python
VOICE_MAP = {
    "soprano": ("treble", 0),
    "alto":    ("treble", 1),
    "tenor":   ("bass",   0),
    "bass":    ("bass",   1),
}

def strip_to_voice(score, voice_name):
    staff_name, voice_idx = VOICE_MAP[voice_name]
    new_measures = []
    for measure in score.get("measures", []):
        stave = measure.get("staves", {}).get(staff_name, {})
        voices = stave.get("voices", [])
        if voice_idx >= len(voices):
            raise ValueError(f"Voice {voice_name} not found in measure")
        new_measures.append({
            "staves": {
                staff_name: {
                    "voices": [voices[voice_idx]]
                }
            }
        })
    new_score = dict(score)
    new_score["measures"] = new_measures
    return new_score
```

### Backend POST action

New action `duplicate-as-pitch-identification` in `apps/dashboard/views/exercises.py`:
1. Reads `voices[]`, `analysisType`, `identMode` from POST data
2. For each selected voice, calls `strip_to_voice(score, voice)`
3. Creates and saves one `Exercise` per voice
4. Redirects to the exercise list (or first created exercise)

---

## Admin

`apps/exercises/forms.py` — no changes required. Pitch identification exercises have `type: "chorale_identification"`, so `_detect_chorale_identification()` already returns `true` for them. The existing **Identification settings** fieldset (feedback mode) is already shown. No additional fieldset is needed — pitch types have no extra configuration beyond what all identification types share.

`apps/exercises/management/commands/import_chorale.py` — the `--analysis` argument gains six new choices for CLI use:
`note_name`, `solfege`, `do_based_solfege`, `scale_degree`, `fixed_do`, `pitch_class`.

When any pitch analysis type is used with `--mode identify`, the command validates that the score has exactly 1 voice after stripping, and raises `CommandError` otherwise.

---

## Files Touched

| File | Change |
|---|---|
| `lab/static/js/src/models/exercise_definition.js` | Add `isPitchAnalysisType()`, new branch in `computeWindowLabel()`, new fallback pools in `buildChoices()` |
| `apps/dashboard/views/exercises.py` | New `duplicate-as-pitch-identification` POST action + `strip_to_voice()` helper |
| `apps/dashboard/templates/dashboard/edit-exercise.html` | "Duplicate as pitch identification" button + modal dialog |
| `apps/exercises/management/commands/import_chorale.py` | Add 6 new `--analysis` choices; validate single-voice when pitch type |
| `apps/exercises/forms.py` | No changes needed — pitch types are `chorale_identification` records; existing detection already covers them |

### Files NOT touched

- `identification_grader.js` — used as-is
- `exercise_sheet.js` — no changes; pitch exercises use identical popup/label UX
- `exercise_context.js` — no changes; `isChoraleIdentification()` already handles these
- `score_timeline.js` — no changes; `step`/`alter` already present; pitch types only need `midi`
- `analyze.js` — consumed read-only

---

## Data Flow

```
Chorale exercise in dashboard
    → "Duplicate as pitch identification" button
    → Modal: select voices (S/A/T/B), analysisType, identMode
    → POST duplicate-as-pitch-identification
        → strip_to_voice(score, voice) × N voices
        → validate: 1 note per window
        → save N Exercise records (type: chorale_identification)
    ↓
Exercise.data (Django DB)
    ↓ served as JSON to the browser
ExerciseDefinition.parse()
    → isChoraleIdentification() = true
    → buildChoraleIdentificationProblems()
        → ScoreTimeline.buildTimeline() → single-voice events
        → buildAnalysisWindows() → midiStack = [midi] per window
        → computeWindowLabel(midiStack, analysisType, analyzer, ...)
            → isPitchAnalysisType() = true
            → analyzer.to_note_name/solfege/etc([midi]) → label
        → buildChoices(answer, allLabels, analysisType)
    → problems[] populated
    ↓
ExerciseSheet — identical to chorale_identification (popup, labels, grading, paging)
    ↓
IdentificationGrader.grade() → correct/incorrect/partial
```

---

## Known Limitations

- The single-note constraint is enforced at import time only. If a `chorale_identification` record with a pitch `analysisType` is manually edited in the DB to have multiple voices, `computeWindowLabel()` will `console.warn` and return `""` for multi-note windows.
- The `note_name` fallback distractor pool uses naturals only. For chromatic excerpts, real labels from other windows will typically provide accidentals, but in a diatonic excerpt the choices will look simpler than the actual note.

---

## Out of Scope

- A "pitch identification" entry point separate from the chorale duplicate flow — deferred
- `helmholtz` and `scientific_pitch` analysis types — `analyze.js` has these methods but they require note-with-octave string input, not a MIDI integer; deferred
- UI distinction between pitch analysis types and other types in label rendering — all use same font/position
