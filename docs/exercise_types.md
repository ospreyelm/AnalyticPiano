# Exercise Types

HarmonyLab has two fundamental interaction modes:

| Mode | Student action | Examples |
|------|---------------|---------|
| **Play** | Sees notation/labels, plays matching notes on MIDI | `matching`, `analytical`, `figured_bass`, `chorale` |
| **Identify** | Sees notation, labels each item by clicking | `identification`, `chorale_identification`, `umto_chorale` (`mode: "identification"`) |

---

## Play types (student plays MIDI to match what is shown)

### `matching`

The original exercise type. Student sees notes on the staff (optionally with analysis overlays — solfege, note names, Roman numerals, chord symbols, etc.) and plays the corresponding notes on the keyboard or MIDI controller.

**Grading:** `ExerciseGrader.notesMatch()` — exact MIDI pitch match.

**Use cases:** Note reading, scale/mode drills, solfege reinforcement, chord voicing practice.

**Example JSON:**
```json
{
  "type": "matching",
  "staffDistribution": "keyboard",
  "key": "jC_",
  "analysis": {
    "enabled": true,
    "mode": { "do_based_solfege": true, "roman_numerals": true }
  },
  "chord": [
    { "rhythmValue": "w", "visible": [65], "hidden": [] },
    { "rhythmValue": "w", "visible": [67], "hidden": [] }
  ]
}
```

---

### `analytical`

Student sees a chord with analysis annotations and plays what the analysis implies (e.g. play the chord that matches the Roman numeral shown). Graded by comparing analysis labels rather than exact pitches.

**Grading:** `ExerciseGrader.analysisMatch()` — compares derived analysis labels.

---

### `analytical_pcs`

Same as `analytical` but graded using pitch-class sets (octave-independent matching).

**Grading:** `ExerciseGrader.analysisPcsMatch()`.

---

### `figured_bass`

Student sees a bass note with figured bass notation and plays the full chord it implies.

**Grading:** `ExerciseGrader.figuredBassMatch()` — checks that the played notes realize the figures above the bass.

---

### `figured_bass_pcs`

Same as `figured_bass` but pitch-class-based (octave-independent).

**Grading:** `ExerciseGrader.figuredBassPcsMatch()`.

---

### `harmonization`

Score-based figured-bass realization exercise. The student sees a bass line with figured bass (or Roman numeral) overlays on a grand staff. One or more voices are locked (typically the bass); the student plays the remaining upper voices to complete the sonority at each onset window.

**Interaction model:** Slice-by-slice — the exercise advances to the next slice only when the active sonority (held + attacked notes) satisfies the current target. Immediate feedback is given per slice; attempts and errors are recorded.

**Grading:** `HarmonizationGrader` — `harmonizationMatch()` in `harmonization_grader_logic.js`. At each slice, checks:
1. Locked voices are present (e.g. bass pitch class matches)
2. All played pitch classes are in the `allowedPcs` set (no illegal notes)
3. All `requiredUpperPcs` are covered
4. Voice count is within `[min, max]` from the exercise's `voiceCountPolicy`

**Overlay:** Controlled by `analysisType`:
- `"figured_bass"` → shows `thoroughbass` overlays (figures below the staff)
- `"roman"` → shows Roman numeral overlays

**Source:** Derived from any UMTO chorale exercise. Targets are pre-computed by `generate_harmonization` from the source exercise's `analysis` slices (bass + figured bass from each UMTO analysis slice). NCT (non-chord-tone) slices are skipped.

**Generation:**
```
python manage.py generate_harmonization --source <exercise_id> --author <email> \
  --locked-voices B --prompt figured_bass --min-voices 3 --max-voices 4 --public
```

**Key files:** `harmonization_grader_logic.js`, `harmonization_targets_logic.js`, `harmonization_realization_logic.js`, `apps/exercises/harmonization/targets.py`, `apps/exercises/management/commands/generate_harmonization.py`

---

### `chorale`

Score-based play exercise using Bach chorale CIR JSON. Student plays through the score note-by-note in onset windows. Requires exactly the voices specified; handles held/tied notes.

**Grading:** `ChoraleGrader` — onset-window matching, tracks per-window statistics.

**Key files:** `chorale_grader.js`, `score_timeline.js`

**See also:** `CLAUDE.md` for full architecture and troubleshooting.

---

### `umto_chorale` (UMTO playback mode)

UMTO-format score-based play exercise. Used for Unit 3 scale exercises (and any other UMTO exercise with `mode: "playback"`). Student sees a grand staff and plays through it note-by-note in onset windows using `ChoraleGrader`.

**Grading:** `ChoraleGrader` — same onset-window engine as `chorale`.

**UMTO metadata fields relevant to playback:**

| Field | Values | Notes |
|---|---|---|
| `mode` | `"playback"` | Selects ChoraleGrader path |
| `clef` | `"keyboard"` | Grand staff (treble + bass) |
| `hand_mode` | `"both"` \| `"rh"` \| `"lh"` | _(planned)_ Which hand(s) student must play |

**`hand_mode` (planned — not yet implemented):** Controls which staff the grader requires. `"rh"` = treble only, `"lh"` = bass only, `"both"` = all notes (default). Teacher sets default via `--hand-mode` flag on `generate_unit3_scale_exercises`; student can override per-session via a RH/LH/Both toggle in the instruction bar. Spec: [`docs/superpowers/specs/2026-05-21-hand-mode-selector-design.md`](superpowers/specs/2026-05-21-hand-mode-selector-design.md).

**Generation:**
```bash
python manage.py generate_unit3_scale_exercises --author <email> --mode both --public
```

**Key files:** `chorale_grader.js`, `score_timeline.js`, `exercise_definition.js`, `generate_unit3_scale_exercises.py`

---

## Identify types (student labels notation by clicking)

### `identification`

Static chord identification. Student sees a set of notated chords on the staff. Each chord has a `?` label below it. Student clicks the label and selects the correct answer from a popup list. No MIDI input required.

**Analysis overlays are hidden** (they would give away answers).

**`identMode` variants:**

| Value | Behaviour |
|-------|-----------|
| `"practice"` | Correct/incorrect shown immediately after each selection |
| `"submit"` | All answers first, then Submit button reveals results |
| `"test"` | Slots lock after answering; no colour feedback shown |

**Grading:** `IdentificationGrader` — compares `answers[i]` against `problem.answer` per slot.

**Example JSON:**
```json
{
  "type": "identification",
  "identMode": "practice",
  "key": "jC_",
  "staffDistribution": "keyboard",
  "chord": [
    { "notes": [60, 64, 67], "answer": "I",  "choices": ["I", "ii", "IV", "V"] },
    { "notes": [62, 65, 69], "answer": "ii", "choices": ["I", "ii", "IV", "V"] }
  ]
}
```

**Paging:** Implemented on the `feature/music21_builder` branch but not yet merged to master. `chorale_identification` has paging on master. The paging infrastructure in `exerciseContext` is type-agnostic and would enable it for `identification` once merged.

---

### `chorale_identification`

Score-based identification exercise using Bach chorale CIR JSON. Student sees measures of a chorale and labels each onset window (chord position) by clicking a `?` below the staff and selecting from a popup.

**Current runtime note:** new score-based identification content is increasingly emitted as `type: "umto_chorale"` with `mode: "identification"`. The frontend treats that UMTO shape as the modern equivalent of `chorale_identification`. Legacy `chorale_identification` rows are still supported.

**Paging:** Exercises are split into pages of 4 problems each by default. `display.maxMeasures` can override this for synthetic worksheets that should remain on a single page. Students navigate with Next/Previous; a slide animation signals the page turn. Page indicator shown in the instruction text box.

**`analysisType` controls what is being identified:**

| `analysisType` | What student labels | Answer format | Example |
|----------------|-------------------|---------------|---------|
| `"roman_numeral"` | Chord function | Roman numeral | `"V7"` |
| `"figured_bass"` | Bass inversion figures | Figured bass | `"6/4"` |
| `"interval_specific"` | Interval quality + size | Quality-first | `"m3"`, `"M6"`, `"P5"` |
| `"interval_generic"` | Interval size only | Number | `"3"`, `"6"`, `"8"` |

**`compoundIntervals`** (boolean, default `false`): when `false`, intervals larger than an octave are simplified (a 10th becomes a 3rd). When `true`, compound intervals are shown as-is.

**Interval computation:** Tonal.js is the authoritative source (uses note spellings from CIR JSON, not semitone counts). `analyze.js` is used as a cross-check with `console.warn` on mismatch.

**Requires exactly 2 voices** for interval types. Enforced at import time.

**Example JSON:**
```json
{
  "type": "umto_chorale",
  "mode": "identification",
  "analysisType": "interval_specific",
  "compoundIntervals": false,
  "identMode": "practice",
  "score": { ... }
}
```

**Unit 4 synthetic worksheets:** `generate_unit4` creates score-backed interval worksheets in this UMTO identification shape. They render one interval per measure, use treble-only notation, hide the no-accidental key label for this synthetic content, and place `?` slots under each notated interval column. Defaults are six one-page worksheets per lane/stage, with eight prompts per worksheet. Unit 4 also uses `display.noteXShift` to keep sparse whole-note intervals, accidentals, and labels visually centered in their measures. Text-input mode accepts interval numbers for generic intervals and case-sensitive quality+number tokens for specific intervals, such as `M2`, `m2`, `P4`, `A4`, and `d5`.

**Grading:** `IdentificationGrader` — same grader as `identification`, extended with `pageOffset` support so absolute answer indices work across pages.

**Key files:** `exercise_definition.js` (`computeWindowLabel`, `buildChoices`), `identification_grader.js`, `exercise_context.js` (paging state), `exercise_sheet.js` (popup, label drawing, page-turn animation).

---

## Shared infrastructure

### `IdentificationGrader`

Used by both `identification` and `chorale_identification`. Stores answers as `{ absoluteIndex: label }`. Signature:

```javascript
grade(definition, visibleProblems, pageOffset)
```

- `visibleProblems` — the current page's slice of problems (pass from `exerciseContext.getVisibleProblems()`)
- `pageOffset` — absolute index of the first visible problem (pass from `exerciseContext.getIdentPageOffset()`)

### Paging (`exerciseContext`)

Paging state lives on `exerciseContext`, not on the grader or definition:

| Method | Description |
|--------|-------------|
| `getIdentPage()` | Current 0-based page number |
| `getIdentPageSize()` | Problems per page (default 4) |
| `getIdentPageOffset()` | `page * pageSize` — absolute index of first visible problem |
| `getTotalIdentPages()` | `ceil(totalProblems / pageSize)` |
| `getVisibleProblems()` | Slice of problems for current page |
| `goToIdentPage(n)` | Navigate to page n; triggers slide animation + delayed re-render |
| `submitIdentPage(options)` | Grade current page; advance if `fromUI=true` and not last page |

Currently wired for score-based identification exercises (`chorale_identification` and `umto_chorale` with `mode: "identification"`). The same methods would work for static `identification` by simply enabling them.

---

## All exercise types at a glance

| Type | Input | Grader | Paging | Notes |
|------|-------|--------|--------|-------|
| `matching` | MIDI | `ExerciseGrader.notesMatch` | No | Original app type |
| `analytical` | MIDI | `ExerciseGrader.analysisMatch` | No | |
| `analytical_pcs` | MIDI | `ExerciseGrader.analysisPcsMatch` | No | |
| `figured_bass` | MIDI | `ExerciseGrader.figuredBassMatch` | No | |
| `figured_bass_pcs` | MIDI | `ExerciseGrader.figuredBassPcsMatch` | No | |
| `harmonization` | MIDI | `HarmonizationGrader` | No | Slice-by-slice FB realization, locked voices |
| `chorale` | MIDI | `ChoraleGrader` | No | Score-based, onset windows |
| `umto_chorale` (playback) | MIDI | `ChoraleGrader` | No | UMTO scale exercises; hand_mode selector planned |
| `identification` | Click | `IdentificationGrader` | On feature branch | Static chords |
| `chorale_identification` | Click | `IdentificationGrader` | Yes (4/page) | Score-based, analysisType variants |
| `umto_chorale` (`mode: "identification"`) | Click | `IdentificationGrader` | Yes (4/page) | Modern UMTO form of score-based identification; used by Unit 4 synthetic interval worksheets |
