# Roman From Clausulae Preservation Notes

Date: 2026-05-26

## Purpose

Capture the useful decisions and lessons from the exploratory `standard_exercises_from_clausulae` work before deleting that worktree or abandoning the XML-derived corpus path.

The key correction is that student-facing exercises should not be built by importing the Clausulae compendium XML examples into a new reduced CIR corpus. That path produced musically meaningless student exercises. The replacement direction is a new exercise type, `roman_from_clausulae`, generated through the same working path that already creates Clausulae exercises, with Roman numeral targets added on top.

## What To Preserve

### Exercise Identity

Create a distinct exercise type:

```text
roman_from_clausulae
```

This should be separate from Branch B Clausulae exercise identity and separate from Bach/Riemenschneider chorale identification.

### Generation Strategy

Use the existing Clausulae generator/rendering path as the source of the score.

Do not use the compendium XML-to-derived-CIR path for student-facing exercises. The source XML files may remain useful for separate Clausulae validation work, but they should not drive these Roman numeral student exercises.

The desired pipeline is:

1. Generate the cadence/progression with the same logic used by working Clausulae exercises.
2. Keep the generated score payload/rendering intact.
3. Add Roman numeral analysis slices at the relevant offsets.
4. Mark those slices as student targets.
5. Save the result as a UMTO exercise whose exercise identity is `roman_from_clausulae`.
6. Create idempotent per-unit playlists from those generated exercises.

### Student-Facing Naming

Avoid Clausulae terminology in student-facing titles where possible. Use the musical skill or progression type instead.

Good examples:

```text
3-part authentic cadence in C major
4-part authentic cadence in G minor
3-part half cadence in F major
```

Avoid titles that make these look like Branch B Clausulae materials or source XML snippets.

### Stable Tags

Preserve the naming discipline from the exploratory work so agents and commands do not confuse these with Branch B materials.

Useful tags:

```text
exercise_type:roman_from_clausulae
corpus:standard_exercises_from_clausulae
unit:9
mode:roman
voices:3
voices:4
Cadence_Perfect_Authentic
Diatonic_Triads
Dominant_Seventh
```

The `corpus:standard_exercises_from_clausulae` tag remains useful as a broad namespace for standard HarmonyLab material sourced from Clausulae generation. The concrete exercise type should be `roman_from_clausulae`.

### Roman Numeral Targets

The student identification UI needs targeted analysis slices. The exploratory work confirmed that non-target analysis data can render as passive labels or produce no `?` buttons.

Roman numeral slices should include:

```json
{
  "offset": 0.0,
  "content": {
    "roman_numeral": "I",
    "raw_roman_numeral": "I"
  },
  "unit_tags": [9],
  "is_target": true
}
```

For simple generated authentic cadences, the initial useful pattern is:

```text
0.0 -> I
2.0 -> V
4.0 -> I
```

More complex generated progressions can add additional slices once the simple cadence path is verified in the student app.

### Idempotent Commands

The replacement implementation should still have an operational command that can regenerate material without creating duplicates.

Desired shape:

```bash
python manage.py generate_roman_from_clausulae \
  --unit 9 \
  --author admin@example.com \
  --voices 3 \
  --public \
  --overwrite
```

The command should be able to:

- Generate exercises.
- Update or replace prior generated rows for the same unit/mode/voice configuration.
- Create or update a unit playlist.
- Keep Branch B Clausulae materials untouched.

### Test Patterns

Useful test ideas from the exploratory work:

- Generated exercises carry the expected namespace tags.
- The command is idempotent.
- Playlists are created with deterministic ordering.
- Analysis slices have `is_target: true`.
- Student payloads advertise Roman numeral analysis, not Clausulae analysis.

These tests should not be treated as sufficient verification. The student player must be manually/browser verified because the abandoned XML-derived path passed tests while producing unusable exercises.

## What To Discard

The following exploratory pieces should not be carried forward as the production path:

- Building a derived corpus from `/clausulae-project/compendium/examples`.
- Importing those derived JSON files into student exercises.
- The MusicXML compendium parsing command as a student-exercise generator.
- The CIR chord-expansion workaround for this use case.
- Derived files under `data/corpus/standard_exercises_from_clausulae/`.
- Student exercises titled by source measure numbers such as `m033-034`.

## Tonal Sonority Filter (Baroque / Classical / Early Romantic)

Clausulae are valid contrapuntal constructs on their own terms. When used to
generate *tonal-music exercises* (Roman numeral identification, harmonization
practice), some clausula combinations produce sonorities that are structurally
correct as counterpoint but **pedagogically misleading as tonal chords**.

The following filter is implemented in
`clausulae/constraints.py: tonal_sonority_ok()` and applied in
`generate_roman_from_clausulae.py: _tonal_valid()`.

### The Rule

Scale degrees in Z₇: **0 = Do, 2 = Mi, 4 = Sol**

```
Let ANT = { triple[0] for each voice }   — first-position (opening tonic)
Let ULT = { triple[2] for each voice }   — last-position (closing tonic)

KEEP combo if:
  (1)  2 ∈ ANT
       First sonority must contain the third (Mi).
       Bare octaves or octave+fifth at the opening chord are not complete
       tonic sonorities in common-practice tonal music.

  (2)  NOT (4 ∈ ULT AND 2 ∉ ULT)
       Final sonority may not be bare fifth/octave (Sol without Mi).
       {0} alone, {0,2}, {0,2,4} are all acceptable closings.
       {0,4} — Sol without Mi — is the disallowed shape.
```

### Why ANT and ULT Only?

PEN (the dominant passing moment) is intentionally incomplete in many clausulae
and is excluded from this check — an open dominant sonority at the penultimate
position is normal contrapuntal practice.

### Not Enforced by Default

This filter is **opt-in**. The clausulae engine itself does not apply it — it
would reject valid counterpoint that happens to lack a third. Apply it only when
the target context is tonal-music pedagogy where incomplete sonorities at
structural positions would mislead students.

## Verification Standard

For `roman_from_clausulae`, passing tests is not enough. Before considering the implementation successful:

1. Generate one exercise.
2. Open it in the student app.
3. Confirm the score is musically meaningful and matches the working Clausulae render.
4. Confirm Roman numeral `?` targets appear at the intended offsets.
5. Confirm the student can answer and complete the exercise.

Only after this smoke test should the generator be expanded to bulk Unit 9-18 material.

