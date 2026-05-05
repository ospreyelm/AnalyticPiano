# Unit 2 Meter Questions Design

**Date:** 2026-05-04
**Status:** Draft, pending implementation plan
**Author:** avnerdorman + Codex (brainstorming)

## Purpose

Define a clean first exercise family for Unit 2 meter concepts, based on multiple-choice symbolic questions about time signatures and meter labels. Preserve room for later notation-reading and notation-repair exercises without forcing all three families into one shared representation.

## Sources

- [reference-htmls/unit2/meter-reference-heim.html](../../reference-htmls/unit2/meter-reference-heim.html)
- [reference-htmls/unit2/meter-signatures.html](../../reference-htmls/unit2/meter-signatures.html)
- Existing visual examples in [things-from-artusi/understanding-meter](../../things-from-artusi/understanding-meter)

## Goals

- Teach the two conceptual axes separately before combining them:
  - division structure: `simple` vs `compound`
  - metrical structure: `duple`, `triple`, `quadruple`
- Support multiple-choice concept questions that decode numeric time signatures such as `3/2`, `6/4`, `9/4`, `12/16`.
- Sequence questions from isolated properties to full synthesis.
- Keep the first implementation strictly numeric, with no `C` or cut-time symbols.
- Reserve a distinct second family for notation-reading questions.

## Non-Goals

- Implementing notation-reading questions in the first phase.
- Implementing beaming repair or barline repair interactions in the first phase.
- Covering irregular meters such as `5/8`, `7/8`, `10/8`.
- Using text input, free response, or multi-select answers.
- Designing around common time `C` or cut time `¢` in Phase 1.

## Pedagogical Model

The lesson material defines meter along two independent dimensions:

1. **Division structure**
   - `simple`: each beat divides into 2 division-level parts
   - `compound`: each beat divides into 3 division-level parts

2. **Metrical structure**
   - `duple`: 2 beats per measure
   - `triple`: 3 beats per measure
   - `quadruple`: 4 beats per measure

Students should practice these dimensions separately before answering combined labels such as `simple triple` or `compound duple`.

## Canonical Rules

These rules are the source of truth for every symbolic question.

### Denominator note mapping

When this spec says `note(n)`, it means the standard time-signature denominator mapping:

- `note(1) = whole`
- `note(2) = half`
- `note(4) = quarter`
- `note(8) = eighth`
- `note(16) = sixteenth`

So multiplying the denominator by 2 gives the **next smaller** note value, not the next larger one.

### Simple meter

- Top number = number of beats per measure
- Bottom number = note value at the beat level
- Division level = half of the beat
- `beat_count = top_number`
- `beat_value = note(bottom_number)`
- `division_count = top_number * 2`
- `division_value = next_smaller_note(beat_value)` = note(`bottom_number * 2`)

Examples:
- `2/4` = simple duple, quarter-note beat
- `3/2` = simple triple, half-note beat
- `4/8` = simple quadruple, eighth-note beat
- `3/2` has `division_value = note(2 * 2) = note(4) = quarter`

### Compound meter

- Top number = number of division-level units per measure
- Bottom number = note value at the division level
- Beat count = top number divided by 3
- Beat value = dotted form of the bottom-number note value
- `division_count = top_number`
- `division_value = note(bottom_number)`
- `beat_count = top_number / 3`
- `beat_value = dotted(note(bottom_number))`

Examples:
- `6/8` = compound duple, dotted-quarter beat
- `6/2` = compound duple, dotted-whole beat
- `9/4` = compound triple, dotted-half beat
- `12/16` = compound quadruple, dotted-eighth beat

## Scope

The design defines three families, but only the first is fully specified for implementation.

### Phase 1: Symbolic concept questions

- Prompt is symbolic text only.
- Answers are multiple choice only.
- Questions cover separate conceptual axes first, then combined synthesis.

### Phase 2: Notation-reading questions

- Prompt is a notated excerpt.
- Student infers meter properties from beaming, bar lines, and note grouping.
- Still multiple choice in first implementation of that family.
- Deferred from this implementation.

### Phase 3: Notation-repair questions

- Student identifies or fixes unclear/wrong beaming or bar lines.
- Requires a different interaction model from recognition drills.
- Explicitly deferred.

## Recommended Architecture

Use one abstract **symbolic meter question** family with subtype-driven behavior rather than separate data models for each concept drill.

Reasoning:

- The first-phase drills all share the same structure:
  - a symbolic prompt
  - a finite set of multiple-choice answers
  - one correct answer
  - explanation/metadata
- The important variation is the cognitive task, not the storage shape.
- A single family keeps authoring and sequencing uniform.

The notation-reading family should be a separate exercise family later because its prompt is a musical excerpt rather than symbolic text.

## Canonical Reference Dataset

To avoid classification drift and generator bugs, implementation should use a canonical reference dataset rather than recomputing meter facts ad hoc in multiple places.

**Recommendation:** add a checked-in JSON file for the allowed Phase 1 numeric signatures, for example:

- `apps/exercises/data/unit2_meter_reference.json`

Each entry should fully encode the derived properties needed by every symbolic subtype.

### Proposed entry shape

```json
{
  "time_signature": "6/4",
  "numerator": 6,
  "denominator": 4,
  "division_type": "compound",
  "grouping": "duple",
  "full_meter": "compound duple",
  "beat_count": 2,
  "division_count": 6,
  "beat_value": "dotted half",
  "division_value": "quarter"
}
```

### Why this dataset should exist

- one source of truth for all allowed signatures
- no duplicated formula logic across generator, validator, and tests
- easy fixture-based review by humans
- deterministic support for `meter_to_ts`
- easier authoring of explanations and distractors

The formulas in this spec still define correctness, but the implementation should materialize the approved results into JSON and treat that file as canonical for Phase 1 content generation.

Field naming rule:

- use `grouping`, `beat_value`, and `division_value` as the canonical fields
- do not duplicate them with aliases such as `number_of_beats`, `beat_level`, or `division_level`
- if the UI wants friendlier labels, derive them at render time rather than storing parallel fields in the dataset

## Reference Dataset Generation

The canonical JSON dataset should be generated by a Python script, not authored by hand.

### Recommended files

- generator script: `apps/exercises/management/commands/generate_unit2_meter_reference.py` or `scripts/generate_unit2_meter_reference.py`
- generated dataset: `apps/exercises/data/unit2_meter_reference.json`

### Generation strategy

1. Explicitly enumerate the allowed Phase 1 numeric signatures from this spec.
2. For each signature, construct a `music21.meter.TimeSignature`.
3. Read the required meter facts from `music21`.
4. Normalize those facts into the canonical vocabulary of this spec.
5. Validate each normalized entry against the canonical rules in this spec.
6. Write the final checked-in JSON file.

### Required `music21` properties

The generator should use `music21` as a computation and validation backend for common meter facts, including:

- `TimeSignature.classification`
- `TimeSignature.beatCount`
- `TimeSignature.beatCountName`
- `TimeSignature.beatDivisionCount`
- `TimeSignature.beatDivisionCountName`
- `TimeSignature.beatDuration`
- `TimeSignature.beatDivisionDurations`

### Normalization rules

- normalize classification strings to lowercase spec vocabulary:
  - `Simple Triple` -> `simple triple`
  - `Compound Duple` -> `compound duple`
- derive:
  - `division_type` from normalized classification or `beatDivisionCountName`
  - `grouping` from normalized classification or `beatCountName`
- convert `music21` durations into canonical labels using a fixed tested mapping

### Quarter-length label mapping

The generator must use a fixed quarter-length-to-label mapping for all values produced by the allowed signature set:

- `0.25 -> sixteenth`
- `0.5 -> eighth`
- `0.75 -> dotted eighth`
- `1.0 -> quarter`
- `1.5 -> dotted quarter`
- `2.0 -> half`
- `3.0 -> dotted half`
- `4.0 -> whole`
- `6.0 -> dotted whole`

This mapper should be tested independently because an error here corrupts the entire reference dataset.

### Validation rule

The generator must validate every produced entry against the formulas in this spec before writing output, and exit with an error if any entry fails validation.

### Runtime rule

The application should consume the generated JSON dataset at runtime. `music21` should not be required for serving Phase 1 symbolic meter questions.

## Symbolic Question JSON Shape

Phase 1 should use a concrete question object shape rather than leaving the renderer or authoring layer to invent one.

```json
{
  "family": "unit2_symbolic_meter",
  "subtype": "ts_to_full_meter",
  "prompt": {
    "kind": "time_signature",
    "text": "6/4"
  },
  "choices": [
    "simple triple",
    "compound duple",
    "compound triple",
    "simple sextuple"
  ],
  "correct_index": 1,
  "answer": "compound duple",
  "source_signature": "6/4",
  "explanation": "6/4 is compound because each beat divides into three quarter notes; 6 divisions make 2 beats, so it is duple.",
  "tags": [
    "unit:2",
    "unit:2_meter_compound"
  ]
}
```

### Required fields

- `family`
- `subtype`
- `prompt`
- `choices`
- `correct_index`
- `answer`
- `source_signature`
- `explanation`
- `tags`

### Field rules

- `family` is fixed to `unit2_symbolic_meter`
- `choices` must contain exactly 4 entries in Phase 1
- `answer` is the canonical truth source
- `correct_index` must agree with `answer` in stored order and must be recomputed if choices are shuffled for display
- `source_signature` is the canonical numeric signature that generated the item
- `explanation` is required in the content model even if the first UI does not display it
- `tags` are generated from subtype plus reference-dataset classification, not authored manually per item

Storing `explanation` now avoids changing the question schema later.

### Tag derivation rules

- every question gets `unit:2`
- every question gets one subtype tag:
  - `unit:2_ts_to_grouping`
  - `unit:2_ts_to_division_type`
  - `unit:2_ts_to_beat_value`
  - `unit:2_ts_to_division_value`
  - `unit:2_ts_to_beat_count`
  - `unit:2_ts_to_division_count`
  - `unit:2_ts_to_full_meter`
  - `unit:2_meter_to_ts`
- prompt-derived classification tags may also be attached:
  - `unit:2_meter_simple` or `unit:2_meter_compound`
  - `unit:2_meter_duple`, `unit:2_meter_triple`, or `unit:2_meter_quadruple`

## Symbolic Question Subtypes

Phase 1 supports these subtypes.

### `ts_to_grouping`

Given a time signature, identify metrical structure only.

Example:
- Prompt: `3/4`
- Correct answer: `triple`

### `ts_to_division_type`

Given a time signature, identify division structure only.

Example:
- Prompt: `6/4`
- Correct answer: `compound`

### `ts_to_beat_value`

Given a time signature, identify the beat note value.

Examples:
- `3/2` -> `half`
- `6/8` -> `dotted quarter`
- `9/4` -> `dotted half`

### `ts_to_division_value`

Given a time signature, identify the division note value.

Examples:
- `3/2` -> `quarter`
- `6/8` -> `eighth`
- `12/4` -> `quarter`

For simple meter, the division value is the subdivision of the beat into two equal parts.

### `ts_to_beat_count`

Given a time signature, identify the number of beats per measure.

Examples:
- `4/2` -> `4`
- `6/8` -> `2`
- `12/16` -> `4`

### `ts_to_division_count`

Given a time signature, identify the number of division-level units per measure.

Examples:
- `3/4` -> `6`
- `6/8` -> `6`
- `9/4` -> `9`

### `ts_to_full_meter`

Given a time signature, identify the full combined label.

Examples:
- `3/2` -> `simple triple`
- `6/4` -> `compound duple`
- `12/8` -> `compound quadruple`

### `meter_to_ts`

Given a meter description, choose a valid time signature example.

Examples:
- `simple quadruple` -> `4/2`
- `compound triple` -> `9/8` or `9/4`

In multiple-choice form, only one option may satisfy the prompt.

Implementation rule:

- build the correct answer from one chosen reference-dataset entry
- build the three wrong answers from entries whose `full_meter` does not match the prompt

This guarantees that only one option is correct even though several signatures may share the same meter classification.

## Allowed Answer Vocabulary

Phase 1 answer vocabulary should be canonical and limited.

### Grouping labels

- `duple`
- `triple`
- `quadruple`

### Division labels

- `simple`
- `compound`

### Full meter labels

- `simple duple`
- `simple triple`
- `simple quadruple`
- `compound duple`
- `compound triple`
- `compound quadruple`

### Note-value labels

Numeric Phase 1 requires note-value names that may appear at beat or division level:

- `half`
- `quarter`
- `eighth`
- `sixteenth`
- dotted forms as needed:
  - `dotted whole`
  - `dotted half`
  - `dotted quarter`
  - `dotted eighth`

`whole` is excluded from the Phase 1 answer vocabulary because it is not produced by the allowed signature set defined below. `dotted whole` is required for compound `/2` signatures such as `6/2`, `9/2`, and `12/2`.

## Allowed Time Signatures

Phase 1 should include familiar and theoretically valid numeric signatures, not just the most common classroom subset.

Allowed examples include:

- Simple:
  - `2/2`, `2/4`, `2/8`, `2/16`
  - `3/2`, `3/4`, `3/8`, `3/16`
  - `4/2`, `4/4`, `4/8`, `4/16`
- Compound:
  - `6/2`, `6/4`, `6/8`, `6/16`
  - `9/2`, `9/4`, `9/8`, `9/16`
  - `12/2`, `12/4`, `12/8`, `12/16`

This avoids falsely teaching that compound meter only appears with `8` on the bottom.

## Question Fairness Rules

- Every multiple-choice question must have exactly one defensible correct answer.
- Questions may be challenging but should not rely on traps, exceptions, or historical notation quirks.
- Avoid prompts where multiple choices are all valid unless the prompt explicitly narrows the answer.
- Do not include irregular meters in Phase 1.
- Do not include symbolic aliases such as `C` or `¢` in Phase 1.

## Distractor Strategy

Distractors should target the actual misconception implied by the subtype.

### Common misconception categories

- Treat compound top numbers as beats instead of divisions.
  - Example: `6/8` -> `6 beats`
- Treat compound bottom numbers as beat values instead of division values.
  - Example: `6/8` -> beat = `eighth`
- Ignore non-eighth compound signatures.
  - Example: `6/4` misread as six quarter-note beats
- Collapse the two axes.
  - Example: answer `triple` when the question requires `simple triple`
- Confuse beat count with division count.
  - Example: `3/4` -> `3 beats` when the question asks for division count and the correct answer is `6`

### Distractor design rule

Each wrong option should correspond to a plausible parsing error, not to a random impossible answer.

### Deterministic distractor algorithm

Implementation should not sample distractors from a loose global pool. It should generate them by subtype from the canonical reference dataset and fixed misconception transforms.

Recommended strategy:

1. derive the correct record from `unit2_meter_reference.json`
2. derive 1-2 misconception-based wrong answers specific to the subtype
3. fill any remaining slots from the valid answer vocabulary, excluding duplicates and the correct answer
4. validate that all 4 choices are unique and exactly one is correct

Subtype-specific rules:

- `ts_to_grouping`
  - distract from `duple`, `triple`, `quadruple`
- `ts_to_division_type`
  - distract from `simple`, `compound`
- `ts_to_beat_value`
  - include the signature's `division_value` as a high-value distractor for compound signatures
- `ts_to_division_value`
  - include the signature's `beat_value` as a high-value distractor when it is not identical in spelling
- `ts_to_beat_count`
  - include `numerator` as a high-value distractor for compound signatures
- `ts_to_division_count`
  - include `beat_count` as a high-value distractor
- `ts_to_full_meter`
  - vary one axis at a time when possible:
    - same division type, wrong grouping
    - wrong division type, same grouping
- `meter_to_ts`
  - choose all wrong answers from records whose `full_meter` differs from the prompt

## Difficulty Progression

Questions should be sequenced in this order:

1. Identify grouping only.
2. Identify division type only.
3. Identify beat value and division value.
4. Count beats and divisions correctly.
5. Synthesize the full meter label.
6. Reverse-map from meter label to a valid signature.

This preserves the agreed pedagogical progression: separate the conceptual axes first, then combine them.

## Deferred Notation-Reading Family

The notation-reading family is intentionally separate from the symbolic family.

### Why it is separate

- The prompt is a musical excerpt, not symbolic text.
- The inference depends on visible notation cues such as:
  - beaming
  - bar lines
  - note grouping
  - beat visibility
- The question metadata will need to describe excerpt-specific properties such as beat level and division level.

### Intended Phase 2 capabilities

- infer `simple` vs `compound` from notation
- infer `duple` / `triple` / `quadruple` from notation
- infer beat value from notation
- infer full meter from notation

All of those remain multiple choice at first.

## Deferred Repair Family

Repair drills are future work and should not shape the Phase 1 model.

Reason:

- recognition questions ask “what is this?”
- repair questions ask “how should this be rewritten or segmented so the meter is clear?”

Repair likely needs interactive click targets, selectable barline insertion points, or selectable beaming repairs. That interaction model is materially different from standard multiple choice.

## Content Authoring Guidance

When authoring Phase 1 questions:

- prefer concise prompts
- keep answer vocabulary consistent across questions
- use examples like `6/4`, `9/4`, and `12/16` regularly so the bank does not overfit to `6/8`, `9/8`, `12/8`
- make reverse-mapping questions explicit:
  - “Which of the following is an example of compound triple?”
  - not “What is the time signature for compound triple?” unless only one answer can be correct by construction

## Preconditions For Implementation Planning

These must be resolved in the implementation plan before coding starts.

- how symbolic prompts and note-value labels should be rendered in the existing exercise UI
- how progression levels and drill selection map onto existing HarmonyLab exercise types
- whether a single frontend renderer can cover all symbolic subtypes with only prompt/choice configuration; if not, split by renderer while keeping one backend content family
- whether Phase 1 questions are fully generated from the canonical reference dataset, hand-authored against that schema, or a hybrid

## Rendering Requirement

Numeric time signatures must be rendered with a proper music notation font, not a generic text font.

Preferred approach:

- use a SMuFL-compliant music font if available in the existing stack

Fallback:

- use another dedicated music font that renders stacked time-signature numerals clearly and consistently

Implications for implementation planning:

- the symbolic renderer must support stacked time-signature display such as `6/4`, `9/8`, and `12/16`
- font choice must be resolved before UI implementation begins
- the renderer should not rely on default serif or sans-serif fonts for music-symbol presentation

## Recommendation

Proceed with implementation planning for Phase 1 only:

- one symbolic multiple-choice meter-question family
- one canonical meter reference JSON dataset
- subtype-driven question generation and evaluation
- strictly numeric signatures
- separate-axis questions first, combined questions later

Then design Phase 2 notation-reading as a separate family once the symbolic model is working and pedagogically validated.
