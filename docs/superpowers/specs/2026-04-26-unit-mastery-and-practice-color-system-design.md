# Unit Mastery and Practice Color System — Design Spec

**Date:** 2026-04-26  
**Status:** Approved for specification, not yet implemented  
**Scope:** Student-facing unit progress model, Unit 1 first, designed to generalize to later units

---

## Problem

The current student Unit page conflates two different ideas:

1. **How much practice content has the student worked through?**
2. **How strong is the student's demonstrated mastery of the skill?**

This creates a poor student experience in Unit 1 because lanes are intentionally
long and scaffolded from very easy to harder. A student can complete many early
exercises and see almost no meaningful color change, while a strict Khan-style
"100% on one exercise => proficient" model would overstate mastery for music
fluency work.

The user explicitly wants:

- a **Khan-like clarity of feedback**
- more visible color movement inside long practice lanes
- a stronger pedagogical claim for mastery than "got a few easy exercises right"
- a model that can carry forward to other units, not just Unit 1

---

## Core Design

The unit page should use **two progress languages at once**:

1. **Top mastery bar** — low-frequency, high-meaning skill status
2. **Lane-row practice color** — high-frequency, motivational progress through recommended practice

These surfaces must not mean the same thing.

### Principle

- **Mastery** answers: "How well does the student know this skill?"
- **Practice progress** answers: "How much fluency-building work has the student completed?"

This keeps the student signal honest:

- row colors move often
- top mastery colors move less often
- later, harder material matters more than early easy material

---

## Top Mastery Bar

The top segmented bar is the canonical per-skill mastery display.

### Allowed states

- `not_started`
- `attempted`
- `proficient`
- `mastered`

### Visual mapping

- `not_started` → gray
- `attempted` → amber
- `proficient` → blue
- `mastered` → green

### Meaning

- `not_started`: the student has not yet established meaningful evidence on the skill
- `attempted`: the student has started the skill, but only on early or incomplete evidence
- `proficient`: the student has demonstrated success on sufficiently advanced skill-focused material
- `mastered`: the student has passed a mixed mastery challenge built from the hardest material in the unit

### Important non-goal

The top bar is **not** a completion meter for the lane inventory. A student can
be `proficient` without finishing every lane exercise, and can continue to see
recommended practice after turning blue or green.

---

## Lane Rows

Lane rows should communicate momentum and fluency-building.

They should keep:

- row names (`Identify`, `Play from Name`, `Play the Notes`)
- clef splits (`Treble`, `Bass`)
- `done / total`
- mini progress bars
- last score indicators where available

They should add a richer practice color scale so long lanes visibly evolve every
4-5 exercises rather than staying visually flat.

### Practice-color ladder

For a 36-exercise lane, prefer **5-6 clearly distinguishable visual bands**
rather than 10 subtly different hues. The goal is visible encouragement, not a
taxonomy of nearly indistinguishable color names.

Recommended conceptual progression:

- `0` → gray — `Not started`
- early band → pale yellow — `Started`
- early-middle band → amber/orange — `Improving`
- middle band → warm gold — `Building`
- late band → teal/blue — `Confident`
- final band → blue-green — `Fluent practice`

For 34-item lanes, use proportional thresholds rather than literal copied
cutoffs.

Granular movement should come from the row's mini-progress bar and count text,
while the row background/accent color should stay visually legible and stable.

### Meaning of lane colors

These row colors mean:

- the student is making visible progress
- the student is building fluency through repetition
- remaining items are still useful even after skill proficiency is reached

These row colors must **not** be interpreted as mastery states.

---

## Unit 1 Mastery Model

Unit 1 contains six canonical lanes:

- Identify Treble
- Identify Bass
- Play from Name Treble
- Play from Name Bass
- Play the Notes Treble
- Play the Notes Bass

The Unit 1 top bar should continue to show six segments, but the segment logic
must stop being tied to "done < total => attempted."

### Unit 1 interpretation

- lane rows = practice inventory and momentum
- top segments = mastery state

The current incorrect interpretation is:

- incomplete lane => orange forever

The new interpretation is:

- orange/blue/green come from mastery evidence
- row completion is still shown, but only as recommended-practice progress

---

## Promotion Rules

This spec deliberately does **not** copy Khan Academy's exact one-exercise
promotion rule, because Monteverdi lanes are intentionally scaffolded from easy
to hard. Early perfect scores should not claim terminal skill competence.

### Unit 1 promotion rule

- early/easy lane completions can establish `attempted`
- `proficient` requires success on later, sufficiently advanced lane material
- `mastered` requires a mastery challenge pass

### Difficulty-sensitive principle

The system should treat success on later-stage exercises as stronger evidence
than success on the first few easy items.

The implementation may achieve this either by:

- stage-index gating, or
- a designated "advanced tier" flag/range within each lane

But the semantic rule is fixed:

> A student should not become `proficient` merely by succeeding on a handful of
> intentionally easy entry exercises.

---

## Mastery Challenge

Unit mastery should be confirmed with a mixed challenge modeled after Khan's
course-level mastery challenge, but built from Monteverdi's own lane ordering.

### Unit 1 challenge structure

There are two challenges:

- `Treble Mastery Challenge`
- `Bass Mastery Challenge`

Each challenge contains **6 prompts total**:

- 2 challenge-eligible exercises from lane 1
- 2 challenge-eligible exercises from lane 2
- 2 challenge-eligible exercises from lane 3

For treble:

- 2 challenge-eligible exercises from Identify Treble
- 2 challenge-eligible exercises from Play from Name Treble
- 2 challenge-eligible exercises from Play the Notes Treble

For bass:

- 2 challenge-eligible exercises from Identify Bass
- 2 challenge-eligible exercises from Play from Name Bass
- 2 challenge-eligible exercises from Play the Notes Bass

### Challenge ordering

Prompts should be **interleaved**, not grouped by lane.

### Why this design

- no separate challenge authoring burden
- challenge difficulty is transparently aligned to curriculum structure
- green means success on the hardest built-in material

### Selection rule

The curriculum rule remains:

> the mastery challenge should use the hardest tier of each lane

But the implementation must **not** infer this from raw playlist position such
as "the last two items in the ordered lane."

Instead, challenge membership should be expressed in the lane / playlist
sequencing layer through explicit curricular metadata attached to the exercise's
placement in that lane.

Examples of acceptable implementation shapes:

- a placement-level `challenge_eligible=True` flag
- a placement-level difficulty tier whose terminal tier is challenge-eligible
- a lane mapping module that explicitly names the challenge slice for each lane

Examples of unacceptable implementation shapes:

- "take the final two ordered rows" without metadata
- storing challenge eligibility in the UMTO exercise payload itself

Challenge eligibility is curricular, not canonical exercise semantics.

---

## Mastery Challenge Unlock Rule

### Unit 1

Unlock the challenge only when the relevant skill group is already
`proficient`.

Recommended interpretation:

- `Treble Mastery Challenge` unlocks when the three treble-related skills are `proficient`
- `Bass Mastery Challenge` unlocks when the three bass-related skills are `proficient`

This keeps `mastered` meaningfully above ordinary lane completion.

---

## Mastery Challenge Scoring

Recommended first-version rule:

- `6/6` correct => all relevant skills become `mastered`
- `<6/6` => no promotion to `mastered`
- no cooldown; challenge may be retried immediately

### Why strict scoring

The row colors already provide frequent encouragement. The mastery challenge
should be demanding because green is a high-meaning signal.

### Why no cooldown

Monteverdi is practice-heavy. Students should be allowed to continue working
without artificial scarcity.

### Input robustness requirement

Because mastery challenges are strict and because some Monteverdi exercises
depend on live MIDI input, the challenge UX must protect students from
accidental or stray input.

The spec does not mandate an exact UI, but the first implementation must ensure
that:

- accidental inputs do not prematurely finalize a challenge outcome
- the student can clearly tell what the system has registered
- challenge grading is robust enough that hardware noise does not make green
  feel arbitrary

---

## Recommended Practice After Proficiency

After a student becomes `proficient`, the remaining lane items should be framed
as **recommended practice**, not unfinished required work.

### Student-facing meaning

- blue means "you can do this"
- green means "you can do this in the hardest mixed review"
- remaining row items mean "keep building fluency"

This distinction is essential for music pedagogy, where automaticity matters.

---

## Generalization to Later Units

This model is intended to be global.

### Global rule

For every unit:

- unit page top segments represent mastery state
- lane rows represent practice-volume / fluency-building progress
- mastery challenge is built from the hardest tier of the unit's related lanes

### Recommended challenge pattern

Each future mastery challenge should:

- mix multiple related lanes/skills
- use the hardest authored tier of those lanes
- remain retryable without cooldown

### Authoring implication

Future units should be authored with:

- clear easy → medium → hard lane progression
- identifiable terminal exercises suitable for challenge use

The challenge should not need a separate pedagogical content stream if lane
ordering is already meaningful.

---

## Data / System Implications

This spec is behavioral, but it implies a few architecture constraints:

- lane progress thresholds must be derived from playlist length
- the system needs a durable way to know which exercises are challenge-eligible
  within a lane's hardest tier
- top mastery state must no longer be derived from `done < total`
- challenge results must be stored separately enough to distinguish:
  - ordinary lane work
  - mastery-challenge confirmation
- attempt records and analytics must be able to distinguish at least:
  - `practice`
  - `mastery_challenge`

The exact implementation shape is deferred to planning.

---

## Non-Goals

- No redesign of the existing Unit 1 six-lane curriculum structure
- No change to UMTO as canonical exercise representation
- No requirement that all units look exactly like Unit 1 visually
- No mandatory cooldown or scarcity mechanic
- No strict clone of Khan Academy's one-exercise promotion rule

---

## Summary

Monteverdi should borrow Khan Academy's clarity, not its exact promotion math.

The final model is:

- **top bar** = mastery
- **rows** = recommended practice progress
- **advanced lane success** = proficient
- **hard mixed challenge** = mastered
- **remaining items after blue/green** = useful fluency work, not failure

This better fits a music curriculum where scaffolded repetition and fluency are
core pedagogical goals.
