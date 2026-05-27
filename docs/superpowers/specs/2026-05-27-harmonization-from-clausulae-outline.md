# Unit 9 Harmonization From Clausulae Outline

Date: 2026-05-27

## Scope

This document outlines the architecture for generating Unit 9 harmonization
exercises from the Clausulae engine. It is an outline only; no implementation
has been done.

The intended student experience is:

- The student sees a melody in the soprano voice.
- The student supplies the missing voices by playing MIDI.
- Grading checks whether the played notes match the target voicing.

## Current UMTO Shape

A harmonization exercise is a UMTO payload with frontend wrapper fields:

```json
{
  "isUMTO": true,
  "type": "umto_chorale",
  "mode": "harmonization",
  "analysisType": "roman",
  "score": {
    "umto": {
      "metadata": {
        "mode": "harmonization",
        "clef": "keyboard",
        "locked_voices": ["S"],
        "voice_count_policy": { "expected": 4, "min": 4, "max": 4 },
        "harmonization_target_policy": {
          "source": "analysis_slice",
          "written_spelling_required": false,
          "midi_uses_pitch_class": false
        }
      },
      "voices": { "S": [], "A": [], "T": [], "B": [] },
      "analysis": [],
      "grading": []
    }
  },
  "harmonizationTargets": []
}
```

Relevant contracts:

- `apps/exercises/umto.py`
- `apps/exercises/harmonization/targets.py`
- `lab/static/js/src/models/harmonization_grader_logic.js`

## Given Voices vs. Student-Supplied Voices

The frontend currently uses `metadata.locked_voices`.

In rendering, non-locked SATB voices are hidden in harmonization mode. Therefore
`locked_voices=["S"]` means soprano is shown and alto, tenor, and bass are
hidden.

In grading, the current target format is more limited:

- `lockedVoices.S` is enforced exactly by MIDI if present.
- `lockedVoices.B` is enforced by pitch class if present.
- Other required notes are checked by pitch class through `requiredUpperPcs`.
- Current targets are generated from figured bass over bass attacks.

This means the existing figured-bass harmonization path assumes bass is either
visible/locked or at least structurally known. It does not currently enforce
"student must play this exact hidden bass MIDI note" unless the target shape or
grader is extended.

## Clausulae Combos As Target Voicings

Clausulae combos can serve as the target voicing.

For 3 voices, the existing Clausulae slot assignment maps:

- `Discant -> S`
- `Tenor` or `Alto -> A`
- `Bass -> B`

So a 3-voice Unit 9 harmonization exercise can show `S` and hide `A` and `B`.
There is no tenor in that payload.

However, if the exercise is described as SATB and the student is expected to
supply alto, tenor, and bass, it should use 4-voice Clausulae combos:

- `Discant -> S`
- `Alto -> A`
- `Tenor -> T`
- `Bass -> B`

Architectural decision: use 4-voice combos for SATB harmonization. Optionally
support 3-voice exercises as "soprano plus two missing voices," but do not label
them SATB.

## HarmonizationTargetPolicy

Current model:

```python
class HarmonizationTargetPolicy(BaseModel):
    source: Literal["figured_bass", "roman", "analysis_slice"] = "figured_bass"
    written_spelling_required: bool = False
    midi_uses_pitch_class: bool = True
```

Today this policy is mostly metadata. The actual target builder ignores
`source` and always derives targets from analysis figures plus bass attacks.

For Clausulae melody harmonization, the policy should be extended or paired
with a new target shape. Recommended direction:

```python
source: "target_voicing"
midi_uses_pitch_class: False
```

Proposed target payload:

```json
{
  "offset": 0.0,
  "givenVoices": { "S": { "midi": 72, "pc": 0 } },
  "requiredVoices": {
    "A": { "midi": 64, "pc": 4 },
    "T": { "midi": 55, "pc": 7 },
    "B": { "midi": 48, "pc": 0 }
  },
  "requiredMidiPitches": [48, 55, 64, 72],
  "studentTargetMidiPitches": [48, 55, 64]
}
```

The JavaScript grader should check the hidden target MIDI pitches exactly when
`midi_uses_pitch_class=false`. Without this, the system only checks chord
membership by pitch class and may accept wrong voicings or octaves.

## Proposed Management Command

Proposed command:

```bash
python manage.py generate_harmonization_from_clausulae \
  --unit 9 \
  --author admin@example.com \
  --voices 4 \
  --public \
  --overwrite
```

Core flow:

1. Reuse the score-building machinery from
   `generate_roman_from_clausulae.py`, including `_realize_events`,
   `_assign_slots`, and `_tonal_valid`.
2. Enumerate `enumerate_simple(n_voices=4, require_bass=True)`.
3. Require `Discant` so soprano exists.
4. Apply `clausulae/constraints.py:tonal_sonority_ok()` or the equivalent
   `_tonal_valid`.
5. Deduplicate by slot fingerprint.
6. Realize voice events into UMTO `voices`.
7. Set `metadata.mode = InteractionMode.HARMONIZATION`.
8. Set `metadata.locked_voices = ["S"]`.
9. Set `voice_count_policy = {"expected": 4, "min": 4, "max": 4}`.
10. Build `grading` from all voices at ANT/PEN/ULT offsets.
11. Build `harmonizationTargets` from the actual Clausulae voicing, not
    figured-bass derivation.
12. Save idempotently with tags and playlist.

Suggested tags:

```text
exercise_type:harmonization_from_clausulae
corpus:standard_exercises_from_clausulae
unit:9
mode:harmonization
voices:4
Cadence_Perfect_Authentic
Diatonic_Triads
```

## Tonal Filter

Apply the existing tonal sonority filter for student-facing tonal exercises:

- `clausulae/constraints.py: tonal_sonority_ok()`

The rule:

```text
KEEP if:
  2 in ANT
  and NOT (4 in ULT and 2 not in ULT)
```

Scale degrees are in Z7:

- `0 = Do`
- `2 = Mi`
- `4 = Sol`

## Key Architectural Decision

Do not force this through `build_targets_from_umto()` as-is. That function is
figured-bass-oriented and bass-attack-oriented. Clausulae harmonization is
target-voicing-oriented.

Best path: add a new target builder for exact voicing harmonization, probably
alongside `apps/exercises/harmonization/targets.py`, and make the frontend
grader honor exact MIDI targets when the policy says so. This keeps existing
figured-bass harmonization behavior intact while supporting the Unit 9
melody-completion use case correctly.

## Verification Expectations

Before expanding this generator beyond a small smoke set:

1. Generate one exercise.
2. Open it in the student app.
3. Confirm the soprano is visible and the student-supplied voices are hidden.
4. Confirm the MIDI grader accepts the exact target voicing.
5. Confirm wrong octaves or wrong hidden bass notes are rejected when exact MIDI
   matching is required.
6. Confirm the exercise completes and records harmonization report data.

