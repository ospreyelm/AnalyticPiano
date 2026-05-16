# Harmonization Exercise - Design Spec

**Date:** 2026-05-15  
**Status:** Revised after pedagogical review

---

## Overview

Harmonization exercises train students to realize a bass with figures. The
canonical grading representation is always:

```text
bass + figures -> required intervals above bass -> required pitch classes
```

Roman numerals, Bach chorale analysis, generated drills, and future repertoire
sources are input formats. They must be normalized to bass+figures before
grading. The fundamental question is not "did the student reproduce Bach's
four-voice realization?" It is "did the student correctly decode the bass and
figures into the required sonority?"

The exercise is training-oriented. Students receive immediate feedback and only
advance from a slice after producing a valid sonority for that bass+figure
target. Attempts and errors are still recorded for grading and analytics, but
the interaction should help students find the sound in real time.

Figured bass should be treated as shorthand notation, not as a special-purpose
grading trick. Once a bass and figures are expanded into ordinary musical
intervals and notes, the rest of the system is just checking whether the
student produced the notation implied by that shorthand.

---

## Pedagogical Principles

1. **Bass+figures are canonical.** Every harmonization target reduces to a bass
   and one or more intervals above that bass.
2. **Roman numerals are not a grading layer.** They are normalized into
   bass+figures using key and inversion information.
3. **Source repertoire is not the answer key.** Bach chorales, Josquin motets,
   Bartok excerpts, and generated drills can all supply targets, but chord
   correctness is derived from the normalized bass+figure target.
4. **Pitch correctness comes before style.** Wrong pitch classes are wrong.
   Voice leading, spacing, doublings, and stylistic constraints are later
   quality layers.
5. **Held notes matter.** At each slice, the grader evaluates the complete
   active sonority, including held notes, not only newly attacked notes.
6. **Feedback is immediate.** A slice advances only when the active sonority is
   valid for the current target.
7. **Reuse existing theory machinery.** The app already contains much of the
   required theory logic in legacy figured-bass grading, generic interval
   analysis, UMTO analysis layers, music21 builders/analyzers, and hand-authored
   Bach chorale Roman analyses. Implementation should draw from these sources
   before adding new theory code.

---

## Initial Exercise Modes

### Basic Figured Bass

The student sees a bass line and figures. They play the bass plus upper notes.
The exercise may specify a flexible or strict voice count.

Example:

```text
Bass: C
Figure: 6
Expanded figure: 6/3
Required upper pitch classes in C major: E and A
```

Any realization with C in the bass and E/A above it is harmonically correct,
subject to the exercise's voice-count policy.

### Two-Part Interval Above Bass

The student sees a bass and one figure. They play exactly two voices: bass plus
the indicated interval above the bass.

Example:

```text
Bass: C
Figure: 6
Expected active sonority: C + A
Voice count policy: min=2, max=2
```

More advanced two-part "choose the best note" exercises are out of scope for
the first implementation.

### Soprano-Bass Chorale Realization

The student sees bass, soprano, and figures. They must play or hold the locked
outer voices exactly and supply valid inner voices.

This is the advanced traditional exercise: given soprano + bass + figures,
realize the middle of the texture. The harmonic target still comes from
bass+figures. The visible soprano is an additional locked-voice constraint, not
the source of the chord answer.

---

## Scope

- New `InteractionMode.HARMONIZATION` in Python UMTO model
- New harmonization metadata:
  - `harmonization_target_policy`
  - `locked_voices`
  - `voice_count_policy`
  - `chord_settle_ms`
  - `release_grace_ms`
  - `max_voice_displacement`
- New normalized JS target builder:
  - `buildUMTOHarmonizationProblems()`
  - `normalizeHarmonizationTarget()`
  - `deriveFiguresFromRoman()`
  - `deriveRequiredPcsFromBassFigures()`
- New JS active-sonority grader:
  - `harmonizationMatch()`
  - held-note state and debounced evaluation
- New JS voice-leading post-pass:
  - `scoreVoiceLeading()`
- New completion overlay:
  - tier badge and feedback after final accepted slice
- New Python management command:
  - generate harmonization exercises from existing UMTO sources
- No Django model migration: new fields live in UMTO JSON metadata and submitted
  performance JSON

---

## Data Model

### `InteractionMode` (`apps/exercises/umto.py`)

```python
class InteractionMode(str, Enum):
    IDENTIFICATION = "identification"
    PLAYBACK = "playback"
    ANALYSIS_MATCH = "analysis_match"
    SYMBOLIC_IDENTIFICATION = "symbolic_identification"
    HARMONIZATION = "harmonization"
```

### Metadata Additions

```python
class VoiceCountPolicy(BaseModel):
    expected: Optional[int] = None
    min: int = 3
    max: Optional[int] = 4

class HarmonizationTargetPolicy(BaseModel):
    source: Literal["figured_bass", "roman", "analysis_slice"] = "figured_bass"
    written_spelling_required: bool = False
    midi_uses_pitch_class: bool = True

class Metadata(BaseModel):
    # existing fields...
    locked_voices: List[str] = Field(default_factory=lambda: ["B"])
    voice_count_policy: VoiceCountPolicy = Field(default_factory=VoiceCountPolicy)
    harmonization_target_policy: HarmonizationTargetPolicy = Field(
        default_factory=HarmonizationTargetPolicy
    )
    chord_settle_ms: int = 150
    release_grace_ms: int = 120
    max_voice_displacement: int = 4
```

`locked_voices` means the voice is visible and must be included correctly:

- `"B"` is normally locked and must be played.
- `"S"` may be locked for soprano-bass chorale realization.

For MIDI exercises:

- Bass is exact MIDI when displayed.
- Locked soprano is exact MIDI when displayed.
- Unlocked upper voices are graded by pitch class.

For future written-entry exercises:

- Spelling may matter. `F#` and `Gb` can be distinct if the exercise enables
  `written_spelling_required`.

---

## Canonical Harmonization Target

Every rendered prompt is normalized to a deterministic target:

```javascript
{
  offset: 2.0,
  bassMidi: 41,
  bassPc: 5,
  bassSpelling: "F",
  figures: ["3", "6"],
  requiredUpperPcs: [9, 2],
  allowedPcs: [5, 9, 2],
  lockedVoices: {
    B: { midi: 41, pc: 5, spelling: "F" },
    S: { midi: 62, pc: 2, spelling: "D" }
  },
  voiceCountPolicy: { expected: 4, min: 3, max: 4 },
  source: {
    kind: "roman",
    label: "ii6",
    key: "C"
  }
}
```

The grader consumes this normalized target. It does not directly grade Roman
numerals, source labels, or Bach's exact realization.

---

## Figures And Interval Expansion

Figures are generic intervals above the bass.

Common shorthands are encoded, but the general mechanism is the same for all
interval stacks:

| Input | Expanded |
|-------|----------|
| blank | `5/3` |
| `6` | `6/3` |
| `6/4` | `6/4` |
| `7` | `7/5/3` |
| `6/5` | `6/5/3` |
| `4/3` | `6/4/3` |
| `4/2` or `2` | `6/4/2` |
| `9/7/5/3` | `9/7/5/3` |
| `8/5/3` | `8/5/3` |

Any arbitrary stack is valid as long as each token can be interpreted as a
generic interval with optional accidental.

Accidental rules:

- The key/local key supplies the default diatonic spelling.
- A sharp, flat, or natural next to a number alters that numbered interval.
- A sharp, flat, or natural with no number means altered third.

Examples:

```text
#6  -> raised sixth above the bass
b5  -> lowered fifth above the bass
#   -> raised third above the bass
n   -> natural third above the bass
```

---

## Roman Numeral Normalization

Roman numerals are optional prompt syntax. They normalize to bass+figures before
grading.

Example in C major:

```text
Prompt: ii6
Roman layer: D minor triad in first inversion
Normalized bass: F
Normalized figure: 6/3
Required upper pitch classes: A and D
```

After normalization, the grader does not care that the source label was `ii6`.
It grades `F + 6/3`.

---

## Slot Boundaries And Active Sonorities

Each harmonization slice has:

- an offset
- a normalized bass+figure target
- optional locked voices
- a voice-count policy

Slots are derived from UMTO analysis/grading offsets or authored drill offsets.
Every change of harmonic target creates a new slot, including cases where only
one voice moves.

The grader evaluates the complete active sonority at the current slot:

```text
Slot 1 active sonority: G B D G
Student holds B D G and moves bass G -> F
Slot 2 active sonority: F B D G
```

Slot 2 is graded as `F B D G`, even though only the bass was newly attacked.

This is the main advantage over the legacy figured-bass model: voices may move
independently and have different durations.

---

## MIDI Timing Model

MIDI chord entry is naturally asynchronous. Notes that are intended as one
sonority may arrive tens of milliseconds apart.

The harmonization grader maintains held-note state and uses debounced
evaluation:

```javascript
timing = {
  chordSettleMs: 150,
  releaseGraceMs: 120
}
```

Rules:

1. Any note-on or note-off updates the held-note state.
2. A note event schedules grading after `chordSettleMs`.
3. Additional note activity resets the timer.
4. Tiny release/re-attack gaps are tolerated by `releaseGraceMs`.
5. When the timer expires, the current active sonority is graded.

During the settle window, incomplete sonorities are not counted as wrong. After
the settle window:

- missing required tones keep the student on the slice
- illegal pitch classes are wrong and increment attempt/error data
- valid sonorities advance the slice

---

## Advancement Model

Harmonization advances only after a valid sonority for the current slice.

Loop:

1. Current slice exposes bass+figure target.
2. Student plays or holds notes.
3. The held-note state settles.
4. `harmonizationMatch()` grades the active sonority.
5. If invalid, the UI shows immediate feedback and stays on the slice.
6. If valid, accepted notes turn black, the sonority is recorded, and the
   exercise advances to the next slice.
7. At completion, voice-leading/style scoring runs over accepted sonorities.

This preserves the legacy figured-bass training behavior while supporting
polyphonic motion.

---

## Chord-Level Grading

### Inputs

```javascript
harmonizationMatch(target, activeMidi, options)
```

`target` is the normalized harmonization target. `activeMidi` is the currently
held sonority after the settle window.

### Gates

#### 1. Locked Voice Gate

- Bass must be present and exact MIDI when locked.
- Soprano must be present and exact MIDI when locked.
- Future written-entry modes may require exact spelling.

#### 2. Harmonic Pitch-Class Gate

- Required upper pitch classes derived from the figures must be present.
- Bass pitch class must be present.
- No unlicensed pitch classes may be sounding.
- Doublings of licensed pitch classes are allowed.

#### 3. Voice Count Gate

Voice count is independent of harmonic pitch correctness.

Examples:

| Context | Policy |
|---------|--------|
| Four-part chorale, flexible | `{ expected: 4, min: 3, max: 4 }` |
| Strict four-part writing | `{ expected: 4, min: 4, max: 4 }` |
| Two-part interval drill | `{ expected: 2, min: 2, max: 2 }` |
| Open keyboard realization | `{ expected: null, min: 2, max: null }` |

Voice count counts distinct sounding MIDI notes, not pitch classes. Doublings
therefore count as additional voices.

### Result States

```javascript
{
  state: "correct" | "partial" | "incorrect",
  reasons: [
    "missing_required_pc",
    "illegal_pc",
    "wrong_bass",
    "wrong_locked_soprano",
    "too_few_voices",
    "too_many_voices"
  ],
  accepted: false,
  activeMidi: [41, 45, 50, 62],
  target: HarmonizationTarget
}
```

In practice mode:

- `partial` means the sonority is not complete enough to advance.
- `incorrect` means an illegal or locked-voice error occurred.
- Only `correct` advances.

On submit/analytics:

- repeated partial attempts and incorrect attempts are both recorded
- the final accepted sonority is stored for the voice-leading pass

---

## Rendering

### Score Display

The bass staff is always shown for standard harmonization. If `"S"` is in
`locked_voices`, a treble staff is rendered above with soprano noteheads.

Unlocked voices are hidden or transparent. They may appear as black noteheads
only after the student supplies an accepted sonority.

Figures or Roman-numeral prompts are displayed according to exercise
configuration, but all prompts are normalized to bass+figures for grading.

### Feedback

- Correct/accepted notes turn black.
- Illegal notes can turn red or be shown in an error overlay.
- Missing required notes should be treated as "not there yet" rather than as a
  punitive error while the student is still searching.
- Attempt counts still record how many settled sonorities were needed before
  success.

---

## Voice-Leading And Style Layer

Voice-leading scoring runs only after every slice has an accepted sonority.

It does not determine fundamental chord correctness. It produces feedback and a
quality tier.

### `scoreVoiceLeading()`

```javascript
scoreVoiceLeading(acceptedSonorities, options)
```

Inputs:

- accepted active MIDI sonority per slice
- locked voice information
- voice-count policy
- `max_voice_displacement`
- key/local key for doubled leading-tone checks

Checks:

- smoothness / maximum voice displacement
- parallel perfect fifths/octaves
- doubled leading tone
- optional future style checks

Parallel detection must use stable voice mapping, not raw sorted-pitch indexes.
The implementation can reuse the same best-mapping result used for smoothness,
while respecting locked bass and soprano identities when present.

### Tiers

| Tier | Harmonic decoding | Voice-leading/style | Score |
|------|-------------------|---------------------|-------|
| Attempting | not all slices accepted | not evaluated | 50 |
| Developing | all slices accepted | major VL/style issues | 70 |
| Proficient | all slices accepted | mostly clean, minor issues | 85 |
| Excellent | all slices accepted | all checks pass | 95 |

The exact tier thresholds can evolve, but harmonic decoding remains the gate.

---

## Source Material

### Bach UMTO Sources

Bach chorale UMTO data can generate harmonization exercises by extracting:

- bass voice
- optional soprano locked voice
- analysis slice figures / Roman labels
- local key
- offset grid
- a reference realization

The reference realization is useful for display, analytics, and optional style
comparison. It is not the primary chord answer key.

### Non-Bach Sources

The same model supports generated drills, Renaissance counterpoint, modern
repertoire, or hand-authored exercises because all targets reduce to
bass+figures.

Non-chorale and synthetic material should enter the system through the same
normalization layer. Likely source paths:

- MusicXML files imported directly by the app
- music21 corpus sources, including non-Bach corpora that music21 can parse
- downloaded symbolic corpora that music21 can import or convert
- hand-authored generated drills stored directly as bass+figure targets

For MusicXML/corpus imports, the importer should first produce UMTO-like voices,
offsets, key/local-key context, and analysis/figure data. Harmonization target
generation then proceeds exactly as it does for Bach chorales:

```text
imported score -> voices + offsets + key/local key + figures -> bass+figure targets
```

This keeps source ingestion separate from grading. A Bach chorale, a Josquin
motet, a Bartok excerpt, a MusicXML classroom exercise, and a synthetic drill
all become the same kind of harmonization exercise once normalized.

---

## Existing Theory Sources To Reuse

The implementation should not start from a blank theory model. HarmonyLab
already has several layers that can supply or verify parts of the
bass+figures-to-notes pipeline:

- legacy figured-bass grading already treats figures as intervals above a bass
- existing generic interval logic can help derive interval names and pitch
  relationships
- UMTO analysis slices already carry Roman numerals, figured bass,
  raw figured bass, local key, offsets, and voice data
- music21 import and analysis code can parse or derive symbolic score data from
  multiple corpora and MusicXML sources
- hand-authored Bach chorale Roman analyses provide a trusted source for Bach
  examples

These sources should be used as references and fallback layers, but the final
grading target should still be normalized to bass+figures. The app should
understand figured bass the way musicians do: as compact notation for ordinary
intervals above a bass.

---

## Musical Review Artifacts

Automated tests are required, but they are not enough for this feature. Musical
correctness should also be validated through human-readable artifacts that can
be reviewed by a musician before the next stage is implemented.

Required review artifacts:

1. **Figure parser table**
   - input: key, bass, figure
   - output: expanded intervals, note spellings, pitch classes
2. **Roman normalization table**
   - input: key, Roman numeral
   - output: bass, figure, required notes
3. **Active-sonority grading table**
   - input: target, held notes, voice-count policy
   - output: correct / partial / incorrect with reasons
4. **Rendered staff artifact**
   - shows bass, figures, optional locked soprano, hidden voices, and accepted
     notes on a staff
5. **End-to-end prototype exercise**
   - one real exercise in the app, preferably with MIDI, before broad content
     generation

Each development stage should have both automated tests and a review artifact.
The implementation plan should include these musician review checkpoints as
formal gates.

---

## Management Command

```bash
python manage.py generate_harmonization \
  --source EA88AI \
  --locked-voices B \
  --prompt figured_bass \
  --voice-count 4 \
  --min-voices 3 \
  --max-voices 4 \
  --max-displacement 4 \
  --author admin@example.com \
  --public
```

Soprano-bass realization:

```bash
python manage.py generate_harmonization \
  --source EA88AI \
  --locked-voices B,S \
  --prompt figured_bass \
  --voice-count 4 \
  --min-voices 4 \
  --max-voices 4 \
  --author admin@example.com \
  --public
```

Internally:

1. Load source exercise.
2. Validate source has UMTO voices and analysis.
3. Build normalized harmonization targets for each slot.
4. Store locked voices and voice-count policy in metadata.
5. Save via `save_umto_exercise()`.

Idempotency key:

```text
source exercise id + mode + locked voices + prompt type + voice count policy
```

---

## Files Changed

| File | Change |
|------|--------|
| `apps/exercises/umto.py` | Add `HARMONIZATION`; add harmonization metadata models |
| `apps/exercises/umto_factory.py` | Add harmonization save support |
| `apps/exercises/management/commands/generate_harmonization.py` | New command |
| `lab/static/js/src/models/exercise_definition.js` | Add `isHarmonization()`, target builder, and parse routing |
| `lab/static/js/src/models/exercise_grader.js` | Add active-sonority `harmonizationMatch()` |
| `lab/static/js/src/models/harmonization_targets.js` | New normalization module |
| `lab/static/js/src/models/voice_leading.js` | New quality scoring module |
| `lab/static/js/src/models/exercise_context.js` | Add settle-window grading and accepted-sonority recording |
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | Hide unlocked voices; show locked voices |
| `lab/static/js/src/components/app/exercise.js` | Show completion tier and feedback |

No Django database migration is required.

---

## Technical Risks To Resolve In Implementation Plan

1. `exercise_definition.js` currently defines `getMode()` twice. The
   implementation should collapse this into one authoritative method before
   adding `isHarmonization()`.
2. The current chorale renderer path depends on `isChoraleLike`. Harmonization
   needs an explicit render path that uses UMTO notation without invoking
   chorale playback grading.
3. Score submission currently sends numerator/denominator data. The plan must
   specify how tier score, attempt counts, accepted sonorities, and
   `vl_score` are attached to performance data.
4. Held-note state, settle windows, and release grace need focused JS tests
   because they are the behavioral core of the exercise.
5. Figure parsing must be test-driven. Accidentals, shorthand expansion, and
   local-key defaults are the highest-risk music-theory logic.

---

## What Is Not Changed

- Legacy figured-bass exercises remain unchanged.
- Existing chorale playback and chorale identification modes remain unchanged.
- `ChoraleGrader` is not reused as the harmonization grader, though the new
  grader may borrow its held-note concepts.
- UMTO remains the canonical exercise data container.
