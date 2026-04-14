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

The SATB → staff/voice mapping assumes standard ordering, which holds for all Bach chorales in the corpus. Non-standard source scores are rejected at the validation step below.

Given a CIR score and a voice name, `strip_to_voice()`:
1. Identifies the target staff name and voice index from `VOICE_MAP`
2. Builds a new score preserving all measure-level fields (e.g. `number`) and replacing only the `staves` slice with the single extracted voice
3. Calls `validate_pitch_voice()` on the result — raises `ValueError` if any window has zero notes or more than one note

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
            raise ValueError(
                f"Voice '{voice_name}' not found in measure "
                f"{measure.get('number', '?')} — expected index {voice_idx}, "
                f"but only {len(voices)} voice(s) present"
            )
        # Preserve all measure-level fields; replace only staves
        new_measure = dict(measure)
        new_measure["staves"] = {
            staff_name: {"voices": [voices[voice_idx]]}
        }
        new_measures.append(new_measure)
    new_score = dict(score)
    new_score["measures"] = new_measures
    validate_pitch_voice(new_score, voice_name)
    return new_score


def validate_pitch_voice(score, voice_name):
    """Raise ValueError if any window has zero or more than one note."""
    for measure in score.get("measures", []):
        for staff_name, stave in measure.get("staves", {}).items():
            for v_idx, voice in enumerate(stave.get("voices", [])):
                for item in voice.get("items", []):
                    kind = item.get("kind")
                    if kind == "chord":
                        raise ValueError(
                            f"Voice '{voice_name}' measure "
                            f"{measure.get('number', '?')} contains a chord "
                            f"— pitch identification requires single notes only"
                        )
                    # rests are silently skipped: they produce no onset window
                    # and are safe to include (ScoreTimeline ignores them)
```

**Rests** — rest items are left in place. `ScoreTimeline.buildTimeline()` already skips rests when building onset windows, so rest-containing measures produce no problem slot and do not break the exercise. Rejecting them would exclude valid musical excerpts unnecessarily.

**Non-standard voice ordering** — `VOICE_MAP` is validated implicitly: if the requested voice index doesn't exist in a measure, `strip_to_voice()` raises immediately with a clear error message shown in the dashboard.

### Backend POST action

`validate_pitch_voice()` and `strip_to_voice()` are the **single canonical validator** used by both the dashboard POST action and the CLI import command. No separate validation paths.

New action `duplicate-as-pitch-identification` in `apps/dashboard/views/exercises.py`:
1. Reads `voices[]`, `analysisType`, `identMode` from POST data
2. For each selected voice, calls `strip_to_voice(score, voice)` — this validates and strips atomically
3. If `strip_to_voice()` raises `ValueError` for any voice, aborts all creates and returns an error message in the UI (no partial saves)
4. Saves one `Exercise` per voice and redirects to the exercise list

---

## Admin

`apps/exercises/forms.py` — no changes required. Pitch identification exercises have `type: "chorale_identification"`, so `_detect_chorale_identification()` already returns `true` for them. The existing **Identification settings** fieldset (feedback mode) is already shown. No additional fieldset is needed — pitch types have no extra configuration beyond what all identification types share.

`apps/exercises/management/commands/import_chorale.py` — the `--analysis` argument gains six new choices for CLI use: `note_name`, `solfege`, `do_based_solfege`, `scale_degree`, `fixed_do`, `pitch_class`. A `--voice` argument (`soprano`/`alto`/`tenor`/`bass`) is also required when a pitch analysis type is used.

When a pitch analysis type is used with `--mode identify`, the command calls the shared `strip_to_voice(score, voice_name)` and `validate_pitch_voice()` helpers (same functions as the dashboard action — extracted to a shared module so there is a single enforcement path). `ValueError` is re-raised as `CommandError`.

---

## Files Touched

| File | Change |
|---|---|
| `lab/static/js/src/models/exercise_definition.js` | Add `isPitchAnalysisType()`, new branch in `computeWindowLabel()`, new fallback pools in `buildChoices()` |
| `apps/exercises/pitch_voice_utils.py` | New module: shared `strip_to_voice()` + `validate_pitch_voice()` helpers used by both dashboard and CLI |
| `apps/dashboard/views/exercises.py` | New `duplicate-as-pitch-identification` POST action (calls `pitch_voice_utils`) |
| `apps/dashboard/templates/dashboard/edit-exercise.html` | "Duplicate as pitch identification" button + modal dialog |
| `apps/exercises/management/commands/import_chorale.py` | Add 6 new `--analysis` choices + `--voice` arg; call shared `pitch_voice_utils` |
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

## Acceptance Checks

| Scenario | Expected behaviour |
|---|---|
| Source score has correct SATB ordering | Strip succeeds; exercise created with one note per window |
| Source score measure is missing the requested voice index | `strip_to_voice()` raises `ValueError`; dashboard shows error; no exercises saved |
| Source voice contains a chord item | `validate_pitch_voice()` raises `ValueError`; dashboard shows error |
| Source voice contains a rest | Rest passes through; `ScoreTimeline` skips it; no problem slot generated |
| Student selects correct pitch label | Problem marked correct; green ✓ shown (per `identMode`) |
| Student selects wrong pitch label | Problem marked incorrect; red ✗ shown (per `identMode`) |
| All 4 voices selected in dialog | 4 separate exercises created; each has one voice in its score |
| `computeWindowLabel()` receives `midiStack.length !== 1` | `console.warn` fires; label returns `""` (safety net only; should not occur in practice) |

---

## Out of Scope

- A "pitch identification" entry point separate from the chorale duplicate flow — deferred
- `helmholtz` and `scientific_pitch` analysis types — `analyze.js` has these methods but they require note-with-octave string input, not a MIDI integer; deferred
- UI distinction between pitch analysis types and other types in label rendering — all use same font/position
