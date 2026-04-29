# Text Input Mode for Pitch Identification Exercises

**Date:** 2026-04-29  
**Status:** Approved  
**Scope:** Unit 1 identification exercises (applicable to all UMTO identification exercises)

---

## Background

Unit 1 pitch identification exercises currently require students to click a `?` slot below each note and select from a dropdown of 5 choices. For students with prior music training this is slow and patronising — they can recall note names without scaffolding. A text input mode lets these students type answers space-separated, dramatically reducing interaction friction.

The dropdown mode is kept as the default and remains appropriate for true beginners who benefit from recognition scaffolding.

---

## Goals

- Let students type space-separated note names instead of using dropdowns
- Persist the student's input mode preference across exercises (localStorage)
- Let teachers set a default input mode per exercise
- Reuse existing slot feedback rendering — no new visual language

---

## Non-Goals

- Replacing the dropdown mode
- Per-note inline text boxes (too close to the current UX, no speed benefit)
- Requiring a backend change for preference storage

---

## Design

### 1. Data Model

Add an optional `input_mode` field to the UMTO `Metadata` Pydantic model:

```python
input_mode: Literal["dropdown", "text"] = "dropdown"
```

Stored at `Exercise.data["umto"]["metadata"]["input_mode"]`. Default `"dropdown"` means all existing exercises are unaffected. The field is included in `umto_schema.json` (auto-regenerated via `python manage.py make_umto_schema`).

### 2. Student Preference & Toggle

**localStorage key:** `harmonylab.identInputMode` → `"dropdown"` or `"text"`

**Priority:** student localStorage preference > exercise `input_mode` default.

On exercise load, `exercise_sheet.js` reads localStorage and uses it to decide which input component to instantiate. If no localStorage value exists, falls back to the exercise's `input_mode` field.

**Toggle UI:** Segmented two-button control (`🖱 Click` / `⌨ Type`) rendered below the answer slot area and above the Practice/Submit toggle by `exercise_sheet.js`. Switching:
1. Writes new value to localStorage
2. Destroys current input component
3. Re-instantiates the appropriate component in-place
4. Does **not** reset answers already given or reload the exercise

### 3. `TextInputComponent`

**New file:** `lab/static/js/src/components/input/text_input.js`

Mirrors the external interface of `LabelInputComponent`:
- `render()` — creates the fused input+button pill DOM element
- `updatePositions(staves, canvasEl)` — no-op (text input is not position-dependent)
- `onAnswer(problemIndex, value)` callback — same signature as `LabelInputComponent`
- `destroy()` — removes DOM elements, unbinds events

**DOM structure:**

```html
<div class="text-id-input">
  <div class="text-id-pill">
    <input type="text" class="text-id-field" placeholder="e.g. C D E F G" />
    <button class="text-id-check">Check ↵</button>
  </div>
  <div class="text-id-hint">Space-separated · Bb and F# ok</div>
</div>
```

**Parser** (`_parseTokens(str)`):
- Split on whitespace
- Normalise to title case: `c` → `C`, `bb` → `Bb`, `f#` → `F#`
- Accept: natural names `C D E F G A B`, sharps `C# D# F# G# A#`, flats `Cb Db Eb Gb Ab Bb`
- Reject unrecognised tokens silently (don't fire `onAnswer`, don't advance index)

**Practice mode** (`feedbackMode === "practice"`):
- On every `input` event, re-parse all tokens
- For each newly-completed token (index N where token[N] !== previous token[N]): fire `onAnswer(N, value)`
- "Completed" = student has typed a space after the token, OR the token count equals the expected problem count (handles final token with no trailing space)

**Submit mode** (`feedbackMode === "submit"`):
- Suppress `onAnswer` calls during typing
- On Check button click (or Enter keypress): parse all tokens, fire `onAnswer(i, value)` for each in sequence

### 4. Score Slot Feedback

No new rendering code. The existing `drawIdentificationLabels` path in `exercise_sheet.js` already handles:
- Grey `?` for unanswered slots
- Green label + ✓ for correct answers (practice)
- Green/red label + ✓/✗ for graded answers (submit after check)

`TextInputComponent` feeds answers via the same `onAnswer` callback as `LabelInputComponent` → same grader path → same visual output.

### 5. Teacher Controls

**`generate_unit1` management command:**

```bash
python manage.py generate_unit1 --lane identification --input-mode text
```

New `--input-mode` flag (`dropdown` | `text`, default `dropdown`). Sets `metadata.input_mode` on all generated identification exercises.

**Dashboard exercise edit page:**

Add `Input mode` field to the existing UMTO metadata edit section:

```html
<select name="input_mode">
  <option value="dropdown">Dropdown (click)</option>
  <option value="text">Text (type)</option>
</select>
```

Saves via the existing exercise update view. No new endpoint needed.

---

## File Changelist

| File | Change |
|------|--------|
| `apps/exercises/umto.py` | Add `input_mode` field to `Metadata` |
| `apps/exercises/umto_schema.json` | Regenerate |
| `apps/exercises/management/commands/generate_unit1.py` | Add `--input-mode` flag |
| `apps/dashboard/templates/dashboard/edit-exercise.html` | Add input mode select |
| `lab/static/js/src/components/input/text_input.js` | New component |
| `lab/static/js/src/components/input/label_input.js` | Add `destroy()` method (required for component swap) |
| `lab/static/js/src/components/app/exercise.js` | Wire up toggle, pass inputMode to sheet |
| `lab/static/js/src/components/music/exercise_sheet.js` | Read inputMode, render toggle, swap components |
| `lab/static/js/src/models/exercise_definition.js` | Expose `getInputMode()` helper |

---

## Token Parser Reference

| Student types | Normalised | Valid |
|--------------|------------|-------|
| `c` | `C` | ✓ |
| `bb` | `Bb` | ✓ |
| `BB` | `Bb` | ✓ |
| `f#` | `F#` | ✓ |
| `F#` | `F#` | ✓ |
| `bbb` | — | ✗ (rejected silently) |
| `H` | — | ✗ (rejected silently) |

---

## Interaction Flow

```
Exercise loads
  → read localStorage("harmonylab.identInputMode")
  → fallback to exercise.input_mode
  → instantiate TextInputComponent or LabelInputComponent
  → render toggle below slots

Student clicks toggle
  → write localStorage
  → destroy current component
  → instantiate other component
  → answers preserved (grader state unchanged)

Student types in text box (practice)
  → on each space-separated token completion
  → onAnswer(i, token) fires
  → grader updates
  → slot renders green ✓

Student types in text box (submit)
  → no feedback until Check click
  → Check: parse all tokens, fire onAnswer for each
  → grader grades all at once
  → slots render green ✓ / red ✗
```

---

## Testing

- Unit tests for `_parseTokens`: case normalisation, accidentals, rejected tokens, empty input
- Integration test: `TextInputComponent` fires `onAnswer` in correct order for practice and submit modes
- Integration test: toggle preserves grader state (answers not lost on switch)
- Integration test: `input_mode` field round-trips through UMTO save/load
- Manual: verify score slot colours match dropdown mode in both practice and submit feedback paths
