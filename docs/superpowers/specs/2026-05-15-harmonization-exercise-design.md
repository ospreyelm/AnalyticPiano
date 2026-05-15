# Harmonization Exercise — Design Spec

**Date:** 2026-05-15  
**Status:** Approved  

---

## Overview

A new exercise mode (`HARMONIZATION`) in which the student is given a bass line with figured bass (or Roman numeral) labels and must realize the upper voices at the keyboard. The exercise is derived from existing Bach chorale UMTO data — no new score data is required. Grading is tiered: chord correctness first, then voice leading quality.

This is the inverse of `analysis_match` (which shows notes and asks for the label). Here, the label is shown and the student plays the notes.

---

## Scope

- New `InteractionMode.HARMONIZATION` in Python UMTO model
- New metadata fields: `visible_voices`, `max_voice_displacement`
- New JS problem builder: `buildUMTOHarmonizationProblems()`
- New JS grader method: `harmonizationMatch()`
- New JS voice leading post-pass: `scoreVoiceLeading()`
- New JS completion overlay: tier badge shown on exercise complete
- New Python management command option: generate harmonization exercises from existing UMTO chorales
- No new DB migrations (no new model fields beyond what UMTO metadata already carries as JSON)

---

## Data Model

### `InteractionMode` (Python, `apps/exercises/umto.py`)

```python
class InteractionMode(str, Enum):
    IDENTIFICATION     = "identification"
    PLAYBACK           = "playback"
    ANALYSIS_MATCH     = "analysis_match"
    SYMBOLIC_IDENTIFICATION = "symbolic_identification"
    HARMONIZATION      = "harmonization"        # NEW
```

### `Metadata` additions (Python, `apps/exercises/umto.py`)

```python
class Metadata(BaseModel):
    # ... existing fields ...
    visible_voices: List[str] = Field(default_factory=lambda: ["B"])
    # e.g. ["B"] = bass only shown; ["B","S"] = bass + soprano locked
    max_voice_displacement: int = 4
    # semitones per voice, Tymoczko threshold; calibrated per exercise/unit
```

`visible_voices` controls what is shown as notation and locked in grading:
- `"B"` always present — bass notehead visible, bass MIDI must match exactly
- `"S"` optional — soprano notehead visible, soprano MIDI must match exactly (pitch class)

### `GradingSlice` — unchanged

`target_midi_pitches` already holds the full 4-voice stack. The harmonization grader derives:

| Voice | Rule |
|-------|------|
| Bass | Exact MIDI match: `delivered_bass == min(target_midi_pitches)` |
| Soprano (if visible) | Exact MIDI match: `delivered_soprano == max(target_midi_pitches)` |
| Inner voices | PC match: `delivered_midi % 12 in {m % 12 for m in target if m != bass [and m != sop]}`, and `bass_midi < delivered_midi [< soprano_midi if shown]` |
| Count | `len(delivered) >= len(target)` for CORRECT; `len(delivered) < len(target)` → PARTIAL (incomplete chord, not wrong) |

Doubling (two voices on same pitch class, e.g. two Gs) is **not** a chord error — it is flagged only at the voice leading tier.

### `AnalysisSlice` — unchanged

`figured_bass`, `raw_figured_bass`, and `roman_numeral` are already present. Display label chosen at render time by `analysisType` (`"figured_bass"` or `"roman"`).

---

## Slot Boundaries

Each `GradingSlice` offset = one chord-bank slot. Slots are derived from UMTO analysis slices: every new onset (any voice moves) creates a new slot. This means:

- A bass holding C while soprano moves G→A = two slots with different soprano notes
- A V8-7 suspension = two consecutive slots on the same bass/RN
- Slot count matches `AnalysisSlice` count in the UMTO object

The student must play each slot explicitly (no auto-advance on repeated notes).

---

## Chord-Bank Flow

Harmonization uses the **chord-bank** flow (same as `analytical` / `figured_bass` types), not the chorale window flow. The student plays all notes of a chord simultaneously; the grader fires on each chord change; the chord bank advances automatically on CORRECT.

`isChorale()` returns `false` for `HARMONIZATION`. A new `isHarmonization()` method gates the harmonization grader path.

---

## Rendering

### Score display

Bass clef staff always rendered. If `visible_voices` includes `"S"`, a treble clef staff is rendered above. Noteheads for visible voices drawn normally (black). All other voices (A, T, and optionally S) rendered **transparent** — student must supply them.

Figured bass labels (or RN labels) rendered below the bass staff at each slot, using the existing analysis overlay pipeline. Label type follows `analysisType` field.

### Existing `vexflow_adapter.js` hook

The adapter already supports `isAnalysisMatch` to render noteheads transparent. A parallel `isHarmonization` flag will suppress inner-voice noteheads (and soprano if not in `visible_voices`).

### Played note feedback

Played notes turn black as the student builds the chord (same as existing chord-bank feedback). Wrong-pitch notes turn red.

---

## Grading

### Chord tier (per slot, JS — `exercise_grader.js`)

New method `harmonizationMatch(expected, delivered, options)`:

```
options = {
  showSoprano: bool,
  bassMidi: int,        // min(expected)
  sopMidi: int,         // max(expected), only if showSoprano
}
```

Logic:
1. **Bass check** (exact): `sort(delivered)[0] === bassMidi` → INCORRECT if wrong
2. **Soprano check** (exact, if shown): `sort(delivered)[-1] === sopMidi` → INCORRECT if wrong
3. **Register check**: all upper voices `> bassMidi` (and `< sopMidi` if shown) → INCORRECT if violated
4. **PC completeness**: `{d%12 for d in delivered[1:]} ⊇ {e%12 for e in expected[1:]}` → INCORRECT if missing PCs; INCORRECT if extra PCs
5. **Count**: `len(delivered) >= len(expected)` → PARTIAL if short (PCs correct but incomplete)
6. → CORRECT

### Voice leading post-pass (JS — new `voice_leading.js` module)

Runs **once at exercise completion** over the full sequence of played chords. Returns a `VLScore` object.

#### Smoothness: `bestMapping(prevUpper, curUpper)`

Exhaustive permutation bijection (≤4 voices, ≤24 permutations — negligible cost). Pads shorter array by repeating nearest note to handle voice count changes.

Returns:
- `maxDisp`: maximum semitone displacement of any single voice pair
- `totalDisp`: sum of all displacements

A voice count change (4→3→4 voices) is handled gracefully — the missing voice is absorbed by the nearest mapping.

#### Parallels: `checkParallels(prevFull, curFull)`

For each pair of voices (6 pairs in 4-voice texture), checks consecutive chords:
- Interval at chord N: `|v_i - v_j| % 12`
- Interval at chord N+1: same formula
- **Parallel** if both intervals are P5 (7 semitones) or P8 (0 semitones), AND both voices actually move (not a unison repetition)
- Only **perfect** intervals flagged (no parallel thirds/sixths)

#### Doubled leading tone: `checkDoubledLT(chord, key)`

Leading tone PC = raised 7th of key. Flag if that PC appears in more than one voice of the chord.

#### `VLScore` object

```javascript
{
  smoothOK: bool,          // all inter-chord max displacements <= max_voice_displacement
  noParallels: bool,       // no parallel P5/P8 found
  noDoubledLT: bool,       // no doubled leading tone
  details: [               // one entry per consecutive chord pair
    {
      slotPair: [i, i+1],
      maxDisp: 4,
      totalDisp: 9,
      parallels: [],        // e.g. ["P5 v1↔v3"]
      doubledLT: false,
    }
  ]
}
```

### Grading tiers

| Tier | Chord correctness | `smoothOK` | `noParallels` | `noDoubledLT` | Score |
|------|---|---|---|---|---|
| Attempting | any chord wrong | — | — | — | < 60% |
| Developing | all correct | ✗ | any | any | 60–79% |
| Proficient | all correct | ✓ | ✓ | ✗ | 80–89% |
| Excellent | all correct | ✓ | ✓ | ✓ | 90–100% |

Note: parallel errors → Developing regardless of smoothness. Doubled LT alone (with smooth VL, no parallels) → Proficient not Developing. This matches standard pedagogical weighting.

### Score submission

Tier maps to numeric score: Attempting=50, Developing=70, Proficient=85, Excellent=95. Submitted via existing `submitExerciseReport()`. VL detail stored in `performanceData.vl_score` for analytics.

---

## Worked Example

**Key:** G major. **Mode:** bass only shown. **`max_voice_displacement`:** 4. **Leading tone:** F# (PC 6).

| Slot | RN | Bass MIDI | Full chord | Expected upper PCs |
|------|----|-----------|------------|-------------------|
| 0 | I | G2=43 | 43,47,50,55 | {11=B, 2=D, 7=G} |
| 1 | V⁷ | D2=38 | 38,42,45,48 | {6=F#, 9=A, 0=C} |
| 2 | I⁶ | B1=35 | 35,38,43,47 | {2=D, 7=G, 11=B} |
| 3 | IV | C2=36 | 36,40,43,48 | {4=E, 7=G, 0=C} |

**Student plays chords correctly (exact expected MIDIs).**

VL post-pass, slot 0→1, upper voices `[47,50,55]` → `[42,45,48]`:

Best mapping (exhaustive): 47→48 (+1), 50→45 (−5), 55→42 (−13). Trying all permutations, best total is 47→42 (+5), 50→45 (−5), 55→48 (−7) → total=17, max=7. Max exceeds threshold of 4.

→ `smoothOK = false` → **Developing** (70–79%).

If student instead voices slot 0 as `[43,47,55,59]` (G2,B2,G3,B3), upper=`[47,55,59]`:

Best mapping to `[42,45,48]`: 47→48(+1), 55→45(−10), 59→42(−17) — still rough. V7 in root position after I in root position almost always requires a leap in some voice. This is musically correct behavior — the threshold is pedagogically intentional.

Parallel check slot 1→2 (student plays `[38,42,45,48]` → `[35,38,43,47]`):

Voice pairs: bass(38→35), upper1(42→43 +1), upper2(45→43 −2), upper3(48→47 −1). No pair moves in parallel P5 or P8. ✓

Doubled LT slot 1 (V⁷): upper PCs `{6,9,0}`. F# (PC 6) appears once. ✓

---

## Files Changed

| File | Change |
|------|--------|
| `apps/exercises/umto.py` | Add `HARMONIZATION` to `InteractionMode`; add `visible_voices`, `max_voice_displacement` to `Metadata` |
| `apps/exercises/umto_factory.py` | Add `harmonization` kwarg support to `save_umto_exercise()` |
| `apps/exercises/management/commands/generate_harmonization.py` | New command: derive harmonization exercise from existing UMTO chorale exercise ID |
| `lab/static/js/src/models/exercise_definition.js` | Add `buildUMTOHarmonizationProblems()`; add `isHarmonization()` method; wire into `parse()` switch |
| `lab/static/js/src/models/exercise_grader.js` | Add `harmonizationMatch()` method; route `umto_chorale + harmonization` to it |
| `lab/static/js/src/models/voice_leading.js` | New module: `bestMapping()`, `checkParallels()`, `checkDoubledLT()`, `scoreVoiceLeading()` |
| `lab/static/js/src/models/exercise_context.js` | On CORRECT for harmonization: run `scoreVoiceLeading()`, compute tier, submit with VL data |
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | Add `isHarmonization` flag: render inner voices (and optionally soprano) transparent |
| `lab/static/js/src/components/app/exercise.js` | Show tier badge overlay on harmonization completion |

No Django migrations required. No new URL patterns. No new templates.

---

## Management Command

```bash
python manage.py generate_harmonization \
  --source EA88AI \          # existing UMTO playback exercise to derive from
  --visible-voices B \       # "B" or "B,S"
  --analysis figured_bass \  # or "roman"
  --max-displacement 4 \
  --author admin@example.com \
  --public
```

Internally:
1. Load source exercise, validate it is UMTO with `voices` and `grading`
2. Clone UMTO object, set `metadata.mode = HARMONIZATION`
3. Set `metadata.visible_voices`, `metadata.max_voice_displacement`
4. Set `metadata.analysisType` from `--analysis`
5. Save via `save_umto_exercise()`

Idempotent: if an exercise with same source ID + mode + visible_voices exists, skip.

---

## Voice Leading Module Interface

`lab/static/js/src/models/voice_leading.js` — standalone, no RequireJS dependencies beyond lodash.

```javascript
define(['lodash'], function(_) {

  function bestMapping(fromUpper, toUpper) { ... }
  // Returns { maxDisp, totalDisp, pairs }

  function checkParallels(prevFull, curFull) { ... }
  // Returns array of strings e.g. ["P5 v1↔v3"]

  function checkDoubledLT(chord, leadingTonePC) { ... }
  // Returns bool

  function scoreVoiceLeading(chordSequence, options) { ... }
  // chordSequence: array of sorted MIDI arrays (one per slot, as played)
  // options: { maxDisplacement, leadingTonePC, showSoprano }
  // Returns VLScore object

  return { bestMapping, checkParallels, checkDoubledLT, scoreVoiceLeading };
});
```

This module is self-contained and testable independently of the exercise system.

---

## Spec Explorer

A standalone validation tool was built during brainstorming at:

`lab/static/harmonization-explorer.html` (served at `http://localhost:8000/static/harmonization-explorer.html`)

Implements the full grading logic (chord check + VL tiers) in browser JS. Used to validate the design before implementation. Can be used during development to test edge cases with arbitrary MIDI input.

---

## What Is Not Changed

- `ChoraleGrader` — not used by `HARMONIZATION` mode
- Existing `playback`, `identification`, `analysis_match` modes — unchanged
- `figuredBassMatch` / `figuredBassPcsMatch` — still used by legacy exercise types
- Python UMTO schema validation (`umto_schema.json`) — regenerated via `make_umto_schema` after `umto.py` changes
- Django Exercise model — `data` is JSON, no migration needed
