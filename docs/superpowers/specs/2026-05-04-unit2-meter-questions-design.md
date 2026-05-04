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

### Simple meter

- Top number = number of beats per measure
- Bottom number = note value at the beat level
- Division level = half of the beat

Examples:
- `2/4` = simple duple, quarter-note beat
- `3/2` = simple triple, half-note beat
- `4/8` = simple quadruple, eighth-note beat

### Compound meter

- Top number = number of division-level units per measure
- Bottom number = note value at the division level
- Beat count = top number divided by 3
- Beat value = dotted form of the bottom-number note value

Examples:
- `6/8` = compound duple, dotted-quarter beat
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

- `whole`
- `half`
- `quarter`
- `eighth`
- `sixteenth`
- dotted forms as needed:
  - `dotted whole`
  - `dotted half`
  - `dotted quarter`
  - `dotted eighth`

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
  - Example: `3/4` -> `3 divisions` instead of `6`

### Distractor design rule

Each wrong option should correspond to a plausible parsing error, not to a random impossible answer.

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

## Open Implementation Questions

These are implementation questions, not unresolved design questions.

- how symbolic prompts and note-value labels should be rendered in the existing exercise UI
- whether explanations appear after each attempt or only in author tooling
- how progression levels and drill selection map onto existing HarmonyLab exercise types
- whether a single frontend renderer can cover all symbolic subtypes with only prompt/choice configuration

## Recommendation

Proceed with implementation planning for Phase 1 only:

- one symbolic multiple-choice meter-question family
- subtype-driven question generation and evaluation
- strictly numeric signatures
- separate-axis questions first, combined questions later

Then design Phase 2 notation-reading as a separate family once the symbolic model is working and pedagogically validated.
