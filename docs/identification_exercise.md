# Identification Exercise Type

An identification exercise shows the student a set of notated chords and asks them to label each one by clicking a question-mark placeholder below the staff and selecting from a list of choices. No MIDI input is used.

---

## JSON Data Format

```json
{
  "type": "identification",
  "identMode": "submit",
  "key": "jC_",
  "staffDistribution": "keyboard",
  "chord": [
    {
      "notes": [60, 64, 67],
      "answer": "I",
      "choices": ["I", "ii", "IV", "V"]
    },
    {
      "notes": [62, 65, 69],
      "answer": "ii",
      "choices": ["I", "ii", "IV", "V"]
    }
  ]
}
```

### Top-level fields

| Field              | Type   | Default    | Description                                                  |
|--------------------|--------|------------|--------------------------------------------------------------|
| `type`             | string | —          | Must be `"identification"`.                                  |
| `identMode`        | string | `"submit"` | Feedback mode — see below.                                   |
| `key`              | string | `"jC_"`    | Key signature code (same format as other exercise types).    |
| `staffDistribution`| string | `"keyboard"` | Staff layout (same choices as chord exercises).            |

### Per-chord fields (`chord` array)

Each entry in `chord` represents one problem (one notated chord with a question mark below it).

| Field     | Type     | Required | Description                                              |
|-----------|----------|----------|----------------------------------------------------------|
| `notes`   | int[]    | yes      | MIDI pitches to display. All notes are shown (no hidden).|
| `answer`  | string   | yes      | The single correct label.                                |
| `choices` | string[] | yes      | All options shown in the popup (should include the answer). |

---

## Feedback Modes (`identMode`)

| Value      | Behaviour                                                                                     |
|------------|-----------------------------------------------------------------------------------------------|
| `"submit"` | Student picks all answers, then clicks **Submit**. Correct (green ✓) / wrong (red ✗) revealed only after Submit. |
| `"practice"` | Correct/incorrect shown immediately after each selection (green or red). Exercise auto-completes if all correct. |
| `"test"`   | Answers are locked after selecting — no colour feedback shown at all. Exercise auto-submits silently once every slot is answered. |

---

## UX Behaviour

- A grey **?** label is drawn below the bass staff for each chord, at the same x/y position as Roman numeral annotations (`bass.getStartX() + 8`, `bass.getBottomY() + 18`).
- The cursor changes to a pointer only when hovering over a label zone (the 60 px strip below the bottom of each bass staff column).
- Clicking inside that zone opens a small popup listing the available choices.
- After selection the label turns dark; after grading it turns green (correct) or red (incorrect) with a ✓ or ✗ below it.
- In **test** mode, once a slot is answered subsequent clicks on it are ignored.
- Analysis overlays (Roman numerals, figured bass, chord symbols) are always hidden for identification exercises — the overlay would give away the answers.

---

## Admin

In the Django admin, open an exercise whose `data.type` is `"identification"`. The form:

- Hides the "Assessment method" radio group (type is fixed).
- Hides fields that don't apply: rhythm, visibility pattern, time signature, semibreves per line, staff distribution.
- Shows an **Identification settings** fieldset with:
  - **Feedback mode** (`identMode`) — RadioSelect with submit / practice / test options.

To create a new identification exercise, edit the JSON `data` field directly (the raw editor at the bottom of the change form), set `type` to `"identification"`, and save. The form will then detect the type and show the Identification settings fieldset on subsequent edits.

---

## Key Files

| File | Role |
|------|------|
| [lab/static/js/src/models/identification_grader.js](../lab/static/js/src/models/identification_grader.js) | Stores answers, grades against `problem.answer` per slot |
| [lab/static/js/src/components/music/exercise_sheet.js](../lab/static/js/src/components/music/exercise_sheet.js) | `initIdentificationMode`, `_showIdentPopup`, `drawIdentificationLabels`, `onSubmitIdentification` |
| [lab/static/js/src/models/exercise_definition.js](../lab/static/js/src/models/exercise_definition.js) | `isIdentification()`, `getIdentMode()`, chord normalisation for identification type |
| [lab/static/js/src/models/exercise_context.js](../lab/static/js/src/models/exercise_context.js) | Bypasses chord-bank advancement; treats result from grader as flawless pass |
| [apps/exercises/forms.py](../apps/exercises/forms.py) | `_detect_identification`, `_configure_identification_fields`, `_store_identification_settings` |
| [apps/exercises/admin.py](../apps/exercises/admin.py) | Injects "Identification settings" fieldset when `data.type == "identification"` |

---

## Data Flow

```
Exercise.data (Django DB)
    ↓  served as JSON to the browser
ExerciseDefinition.parse()
    → normalises each chord entry: all notes go to visible[], hidden=[]
    → copies answer and choices onto the problem object
    → reads identMode
    ↓
ExerciseSheet.initIdentificationMode()
    → attaches click + mousemove handlers to canvas
    → shows/hides #identification-actions Submit button based on mode
    ↓
Student clicks label zone → _showIdentPopup()
    → IdentificationGrader.setAnswer(index, choice)
    → mode branch: practice (grade + render), test (render + auto-submit), submit (render)
    ↓
onSubmitIdentification() / auto-submit
    → IdentificationGrader.grade(definition) → {result, score, problems[]}
    → exerciseContext.graded = graded
    → render() → drawIdentificationLabels() colours labels + draws ✓/✗
    → if result === "correct": setTimeout → exerciseContext.grade() → advance/complete
```

---

## Grading Logic (`IdentificationGrader.grade`)

- Iterates over `definition.getProblems()`.
- For each problem, compares `answers[i]` (student choice) against `problem.answer`.
- `correct: true` → green ✓; `correct: false` → red ✗; `correct: null` → not yet answered.
- `result`:
  - `"correct"` — all slots answered and all correct
  - `"incorrect"` — all slots answered but at least one wrong
  - `"partial"` — some slots still unanswered
- `score`: `0` correct, `1` partial, `2` incorrect.

In **test** mode, `exerciseContext.graded` is never set before submission, so `drawIdentificationLabels` never renders colour feedback regardless of the grader's output.
