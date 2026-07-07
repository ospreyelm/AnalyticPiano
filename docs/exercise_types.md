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

**`analysisType` storage:** saved UMTO chordal exercises store the selected type
at `exercise.data["analysisType"]`. `lab.views._resolve_analysis_type()` reads
that persisted value first and falls back to the legacy complexity heuristic only
for older rows without the key.

**Source:** Derived from any UMTO chorale exercise, or generated directly from standard Clausulae cadences. Targets are pre-computed from the exercise's `analysis` slices (bass + figured bass from each UMTO analysis slice). NCT (non-chord-tone) slices are skipped for chorale-derived material.

**`input_style: "per_voice"` (SATB voice-completion variant, planned — not yet implemented):** A second `input_style` for this same `harmonization` mode/pipeline — not a new exercise type, mode, or grader. The source is a full SATB `score_kind="voices"` UMTO (not the bass-plus-figures `chordal` shape above); three of the four voices are locked/given and the student completes the one missing voice by clicking notes on the staff. Grading reuses the existing chord-onset analysis-match path (`ExerciseContext.gradeHarmonizationMidiSet` → `harmonization_runtime_grader.js` → `harmonizationMatch`) unmodified — see "Grading" above.

Milestone-1 constraints (so they don't need to be re-derived from code):
- Bass is always among the locked voices — bass is never the missing voice.
- Exactly one voice is missing per exercise (soprano, alto, or tenor).
- Eligible sources are homophonic: the missing voice has exactly one attack per bass onset, 1:1 with the bass-onset grid — no ties, rests, or passing tones between onsets. Sources with rhythmic independence in the candidate missing voice (e.g. passing tones, suspensions) are ineligible; generation must fail loudly rather than silently tolerate the gap.
- Click-based note entry only; physical/on-screen piano input for this variant is out of scope for milestone 1.
- No voice-leading, register, or voice-crossing grading — correctness is harmonic (chord-tone) only, matching the grading semantics above.

`input_style` is stored on `score.umto.metadata.input_style` (alongside `locked_voices`/`voice_count_policy`), not as a new top-level `Exercise.data` field, and is mirrored as skill tag `input_style:per_voice` for queryability. Absent/default `input_style` means the existing chord-entry shape described above (unchanged).

See [`docs/plans/2026-07-06-001-feat-satb-voice-completion-harmonization-plan.md`](plans/2026-07-06-001-feat-satb-voice-completion-harmonization-plan.md) for the full plan.

**Generation:**
```
python manage.py generate_harmonization --source <exercise_id> --author <email> \
  --locked-voices B --prompt figured_bass --min-voices 3 --max-voices 4 --public

python manage.py generate_harmonization_from_clausulae --unit 9 --author <email> \
  --voices 3 --public --overwrite

python manage.py generate_harmonization_from_clausulae --unit 10 --author <email> \
  --voices 3 --public --overwrite
```

**Key files:** `harmonization_grader_logic.js`, `harmonization_targets_logic.js`, `harmonization_realization_logic.js`, `apps/exercises/harmonization/targets.py`, `apps/exercises/management/commands/generate_harmonization.py`, `apps/exercises/management/commands/generate_harmonization_from_clausulae.py`

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

### Chordal Play-saved exercises (`score_kind: "chordal"`) — spelling & analysis review

Exercises saved from the Teacher Play view are `umto_chorale` rows with `score_kind: "chordal"` (chords stored as flat verticalities in `umto.chords[]`, split across staves at render time).

**Note spelling.** Chords store MIDI in `visible`/`hidden` plus an optional positional `spelling` array (visible then hidden) in scientific form (`"Bb4"`, `"C#5"`). Rendering resolves each note's spelling in this order:
1. explicit `chords[i].spelling` (teacher override), else
2. key-aware default from the exercise key (`KeySignature.keyToSpelling`), else
3. sharp fallback (only for malformed/missing keys).

The renderer (`vexflow_adapter.itemToTickable`) trusts CIR `pitch.step/alter` and does not snap-spell, so the converter (`exercise_sheet._convertChordalUMTOToProcessedScore` and Python `_chordal_to_measures`) is the single source of spelling. Both share the helpers in `lab/static/js/src/components/music/chordal_spelling.js` (JS) and `apps/exercises/chordal_spelling.py` (Python). On save, `play_sheet.dataForSave` captures the analyzer's contextual spelling into `spelling` so exercises match what the teacher saw.

**Roman-numeral figures** in chordal analysis slices use the braced legacy format (`V{r3}`, `V{z5}`) so figures render stacked and round-trip through `stripFiguredBassTokens` for answers; the brace-stripped form is kept as `raw_roman_numeral`.

**Click-first authoring (Teacher Play Authoring, Phase B).** Authoring happens in place on the Play canvas — "if you see it, you can click it to change it." Clicking a banked chord opens a micro-toolbar (`play_authoring_toolbar.js`): a closed **duration palette** (quarter-lengths `{4, 3, 2, 1.5, 1, 0.75, 0.5, 0.25}`, default quarter), **Respell**, and below-zone **token correction** (Roman numeral / figured bass). Clicking the gap between two chords places/removes a **barline** at that chord's onset. Selection-scoped keyboard accelerators (`1`–`4` set duration, `R` respell, `Esc` deselect) fire only while a chord is selected; note-entry is suspended whenever a text field is focused, so neither collides with the QWERTY note-entry overlay.

**Rhythm & meter (ABC-style).** `ChordEvent.duration` is a per-chord quarter-length from the closed palette; `metadata.barline_offsets` is the explicit sorted/unique list of teacher-placed barlines (on chord onsets, excluding `0.0` and the stream end). The **meter is the mode switch**:
- **Free / open mode** (`meter: null`, default) — any rhythm saves; the saved score is one running measure with no time-signature glyph; no metric validation.
- **Metered mode** (a time signature is set) — barlines auto-suggest at meter boundaries (teacher then edits), and Save is **gated**: every bar must be an exact contiguous tiling summing to the meter, else Save is blocked with specific feedback ("Bar 3 has 5 beats, expected 4"). The same validator runs client-side (`chordal_barlines_logic.checkRhythm`) and server-side (`umto_factory.validate_chordal_rhythm`). The saved render splits `score.measures` at exactly the placed barlines.

**Analysis slots.** Two zones (above / below the staff), at most one analysis type each, persisted as `analyzeConfig: {above, below}` on the exercise data (`analysis_slots.js` owns the type→zone rules). Below-zone harmonic labels (Roman numerals / figured bass) are serialized as reviewed analysis slices; above-zone pitch labels (note names / scale degrees) are key-relative and recomputed at render.

**Save = approval (no soft-gate bounce).** A Play Save persists the in-place analysis directly and stamps `analysis_review_status = "reviewed"` (or `"none"` when no analysis slot is active — a pure `PLAYBACK` exercise). There is **no** redirect to the workbench and **no** `window.alert`; feedback routes through `feedbackService`. After save, a post-save **target selector** emits the seam contract `{ exerciseId, targetIntent: "library" | "assign", sectionId?, autoTranspose }` (v1 wires `library`; `assign`/curriculum are Threads 2/3). The legacy `generated → workbench review` path (`api_chordal_analysis_review`) survives only for bulk MusicXML imports that never pass through Play, and an agent retains full parity via the review API payload.

**Key files:** `play_sheet.js` (`dataForSave`, authoring state), `play_save_logic.js`, `chordal_barlines_logic.js`, `analysis_slots.js`, `play_authoring_toolbar.js`, `target_selector.js`, `music_controls.js` (Save→reviewed), `shortcuts.js` + `note_entry_gate_logic.js`, `chordal_spelling.js`/`chordal_spelling.py`, `exercise_sheet.js`, `umto_factory.py` (`save_chordal_umto_exercise`, `validate_chordal_rhythm`, `_chordal_to_measures`), `lab/views.py` (`AddExerciseView`), `api_workbench.py`.

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

**Unit 4 synthetic worksheets:** `generate_unit4` creates score-backed interval worksheets in this UMTO identification shape. They render one interval per measure, use treble-only notation, hide the no-accidental key label for this synthetic content, and place `?` slots under each notated interval column. Defaults are twenty-four one-page worksheets per lane/stage, with eight prompts per worksheet. Student player serving is deterministic but personalized: each Unit 4 interval playlist shuffles that fixed worksheet bank into a stable per-student order, then exposes only the first six worksheets from that per-student order. Different students therefore get different stable six-sheet assignments without on-the-fly exercise generation. Unit 4 also uses `display.noteXShift` to keep sparse whole-note intervals, accidentals, and labels visually centered in their measures. Text-input mode accepts interval numbers for generic intervals and case-sensitive quality+number tokens for specific intervals, such as `M2`, `m2`, `P4`, `A4`, and `d5`.

**Grading:** `IdentificationGrader` — same grader as `identification`, extended with `pageOffset` support so absolute answer indices work across pages.

**Key files:** `exercise_definition.js` (`computeWindowLabel`, `buildChoices`), `identification_grader.js`, `exercise_context.js` (paging state), `exercise_sheet.js` (popup, label drawing, page-turn animation).

---

### `roman_from_compendium` (UMTO identification — Galant compendium)

Roman-numeral identification exercises sourced from a checked-in curated subset of the Galant compendium cadence pages (`apps/exercises/data/galant_compendium_cadences.json`). Each compendium page describes a named cadence type; curated, music-professor-vetted RN templates (`apps/exercises/compendium_templates.py`) supply the answer labels — music21 is **not** used to auto-derive labels (auto-derivation produces suspension/passing-tone noise). Exercises with misaligned or degenerate notes are skipped at import time.

**Source:** vendored `index.json`-shape notes (not raw MusicXML); note durations are trimmed to the next onset for correct inversion rendering. music21 + `m21_to_cir` build the CIR score; `save_umto_exercise` saves the UMTO row. `COMPENDIUM_INDEX=/path/to/index.json` can override the checked-in source for local regeneration/debugging.

**Corpus tag:** `corpus:galant_compendium`

**Exercise identity tag:** `exercise_type:roman_from_compendium`

**Curriculum coverage:** units 9, 10, 12, 14, 17 (345 exercises across multiple transposition keys).

**Cadential six-four:** labeled `Cad64` (not `I6/4`) to match pedagogical convention and unit answer-set vocabulary.

**Per-unit answer sets:** derived from `music_theory_taxonomy_with_branches.json` via `manage.py build_unit_allowed_answers`, with inverted-seventh additions (`ii65`, `iiø65` → unit 14; `Cad64` → unit 12) from `apps/exercises/data/unit_allowed_answers.additions.json`.

**`analysisType`:** `"roman"` — student clicks a `?` slot and selects from a dropdown.

**Interaction mode:** UMTO `"identification"` — rendered by the same paged identification engine as `chorale_identification`.

**Generation:**
```bash
python manage.py import_compendium_cadences --unit 9 --author admin@example.com --public
python manage.py import_compendium_cadences --all-units --author admin@example.com --public --overwrite
```

**Key files:** `apps/exercises/data/galant_compendium_cadences.json`, `apps/exercises/compendium_templates.py`, `apps/exercises/unit_allowed_answers.py`, `apps/exercises/data/unit_allowed_answers.additions.json`, `apps/exercises/management/commands/import_compendium_cadences.py`

**See also:** `docs/superpowers/specs/2026-05-26-roman-from-clausulae-lessons.md` (§ 2026-05-31 Update) for the sanctioned-override note explaining why this path is allowed despite the earlier compendium ban.

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
| `harmonization` | MIDI (Click for planned `input_style: per_voice` SATB variant) | `HarmonizationGrader` | No | Slice-by-slice FB realization, locked voices |
| `chorale` | MIDI | `ChoraleGrader` | No | Score-based, onset windows |
| `umto_chorale` (playback) | MIDI | `ChoraleGrader` | No | UMTO scale exercises; hand_mode selector planned |
| `umto_chorale` (chordal, Play-authored) | MIDI | `ChoraleGrader` | No | Click-first Play authoring; per-chord palette durations + explicit barlines; free (`meter:null`) or metered (validated); Save = `reviewed` |
| `identification` | Click | `IdentificationGrader` | On feature branch | Static chords |
| `chorale_identification` | Click | `IdentificationGrader` | Yes (4/page) | Score-based, analysisType variants |
| `umto_chorale` (`mode: "identification"`) | Click | `IdentificationGrader` | Yes (4/page) | Modern UMTO form of score-based identification; used by Unit 4 synthetic interval worksheets |
| `roman_from_compendium` | Click (dropdown) | `IdentificationGrader` | Yes (4/page) | Galant compendium cadences; curated RN templates; units 9/10/12/14/17; `Cad64` label |
