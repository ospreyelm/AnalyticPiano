# Individualized Assignment Recipes and Immutable Student Slots

## Status and relationship to prior work

This design supersedes the bounded-adaptive portions of
`2026-06-18-playlist-selection-mode-design.md`.

The earlier design tried to make `Playlist` represent both:

- a fixed ordered collection of exercises; and
- an adaptive exercise pool with a hard serving limit.

Further design discussion established a clearer product model:

- a **bounded assignment** is a teacher-authored recipe with an explicit number
  and distribution of exercises;
- exercises are selected individually for each student just in time;
- once a concrete exercise is served, its assignment slot is immutable; and
- open-ended adaptive practice is a separate **drill/practice** concept, not an
  unbounded assignment.

The orphan-exercise fix from the earlier spec remains valid independent work:
teacher-authored exercises should not become unreachable merely because no
assignment was chosen. It should be implemented separately and must not force
every saved exercise into an assignment recipe.

This document is an architecture design, not an implementation plan. The rollout
is intentionally incremental so the current `Playlist` database model and
course relationships remain operational while the new concepts are introduced.

## Problem

HarmonyLab's `Playlist` began as an ordered sequence of MIDI exercises. It now
serves several unrelated responsibilities:

- reusable exercise collection;
- ordered assignment;
- adaptive exercise pool;
- serving and transposition policy;
- course placement and schedule;
- progress namespace;
- public or official content package; and
- implicit completion definition.

The `is_adaptive` and `is_dynamic` booleans are symptoms of that overload.
Adding `selection_mode` and `target_length` would make the states more explicit,
but it would not give teachers the authoring model they actually need.

A teacher should be able to ask for work such as:

> Six harmonic-analysis exercises: include at least two secondary dominants,
> one chord with the 3rd in the bass, and one chord with the 5th in the bass.

The software should:

1. verify that the exercise library can satisfy the request;
2. offer to generate missing content when it cannot;
3. choose exercises individually using each student's current mastery;
4. preserve the teacher's section order and coverage promises;
5. permanently record each concrete exercise when it is first served; and
6. use that recorded identity for navigation, grading, review, and analytics.

The current adaptive implementation instead reruns selection from a playlist
pool and attempts to infer slot identity from performance history. That creates
course ambiguity, unstable selection, submission failures for unlinked pool
items, and no reliable way to enforce assignment-wide coverage.

## Goals

- Make **Assignment** the product concept teachers and students use.
- Let teachers define ordered sections by exercise type, quantity, musical
  elements, quotas, complexity, key, mode, source, and other supported
  constraints.
- Make individualized selection the default for recipe-based sections.
- Select each concrete exercise just in time using current student mastery.
- Record every served exercise in an immutable, student-specific slot.
- Guarantee the minimum coverage promised by each assignment section.
- Validate recipe feasibility before publication.
- Offer generation of missing exercises from the feasibility report.
- Preserve fixed ordered assignments and existing playlist data.
- Introduce the architecture incrementally without a destructive rename or
  immediate replacement of every playlist-related table.
- Establish the modern student player as the only long-term delivery surface.

## Non-goals

- Do not rename the `Playlist` database table in the first phase.
- Do not rewrite every course, gradebook, and recurring-assignment feature in
  one release.
- Do not generate exercises synchronously during a student request.
- Do not silently relax teacher-authored quotas or constraints.
- Do not make every taxonomy tag selectable as an assignment element.
- Do not use assignment slots for endless drills; drills require a separate
  completion and progress model.
- Do not extend legacy student rendering routes. They should become
  compatibility redirects and then be removed.
- Do not change UMTO's role as the only sanctioned representation for new
  exercises.

## Product vocabulary

### Assignment

A bounded, scheduled, gradable body of student work.

In the initial rollout, an existing `Playlist` row can back an Assignment in
the product UI. The internal class and table may remain named `Playlist` until
the migration is mature.

### Assignment section

An ordered recipe block inside an assignment.

Examples:

- four harmonic-analysis exercises;
- two figured-bass realization exercises;
- three cadence-identification exercises.

Sections are completed in teacher-defined order. Selection is personalized
within each section.

### Assignment slot

One immutable position in one student's assignment.

The slot stores the exact exercise and variant selected for that student.
Navigation and submission reference the slot rather than independently rerunning
the adaptive selector.

### Exercise set

An optional reusable curated collection of exercises. Existing fixed playlists
can eventually become exercise sets or fixed assignment sections. An exercise
set is content; it is not itself a schedule, grade, or student-progress record.

### Drill or practice

Open-ended, mastery-driven work without a fixed quantity. Existing genuinely
endless adaptive playlists migrate here rather than becoming assignments.

## Core domain model

The long-term conceptual hierarchy is:

```text
Course
  -> Assignment
    -> AssignmentSection
      -> StudentAssignmentSlot
        -> Exercise
          -> Submission / Attempt
```

The incremental first phase keeps current course placement:

```text
Course
  -> PlaylistCourseOrdered
    -> Playlist presented as Assignment
      -> AssignmentSection
        -> StudentAssignmentSlot
```

### `AssignmentSection`

Proposed fields:

```python
class AssignmentSection(models.Model):
    assignment = models.ForeignKey(
        Playlist,
        related_name="assignment_sections",
        on_delete=models.CASCADE,
    )
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=128, blank=True)
    instructions = models.TextField(blank=True)

    source_mode = models.CharField(
        max_length=24,
        choices=(
            ("fixed", "Fixed exercises"),
            ("individualized", "Individualized selection"),
        ),
        default="individualized",
    )
    quantity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )

    exercise_types = ArrayField(
        models.CharField(max_length=64),
        default=list,
    )
    eligible_elements = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )
    coverage_quotas = models.JSONField(default=dict, blank=True)

    min_complexity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    max_complexity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    allowed_keys = ArrayField(
        models.CharField(max_length=16),
        default=list,
        blank=True,
    )
    required_tags = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )
    excluded_tags = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )

    selector_config = models.JSONField(default=dict, blank=True)
    published_recipe_snapshot = models.JSONField(null=True, blank=True)
```

The exact storage split between typed columns and `selector_config` belongs in
the implementation plan. Stable, commonly queried constraints should be typed.
Rare generator-specific parameters may remain validated JSON.

Constraints:

- unique `(assignment, order)`;
- `quantity >= 1`;
- every quota key must also appear in `eligible_elements`;
- every quota value is an integer `>= 1`;
- each quota value must be `<= quantity`;
- `min_complexity <= max_complexity` when both are set;
- only taxonomy elements applicable to the selected exercise types may be used;
- published sections are edited by creating a new recipe revision, not mutating
  the snapshot used by active students.

### Fixed section membership

Fixed sections need explicit ordered membership rather than overloading the
assignment-wide `ExercisePlaylistOrdered` relation:

```python
class AssignmentSectionExercise(models.Model):
    section = models.ForeignKey(AssignmentSection, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField()
```

Constraint: unique `(section, order)`.

For the first migration, each existing playlist gets one materialized
compatibility section. Its fixed membership may continue reading the existing
`ExercisePlaylistOrdered` relation without immediately copying every exercise
relationship. New fixed sections use the explicit section relation.

### `StudentAssignmentSlot`

Proposed fields:

```python
class StudentAssignmentSlot(models.Model):
    student_assignment = models.ForeignKey(
        "StudentAssignment",
        related_name="slots",
        on_delete=models.CASCADE,
    )
    section = models.ForeignKey(AssignmentSection, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField()

    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    variant = models.JSONField(default=dict, blank=True)
    credited_elements = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )

    selection_rationale = models.JSONField(default=dict, blank=True)
    selector_version = models.CharField(max_length=32)
    mastery_snapshot = models.JSONField(default=dict, blank=True)
    recipe_snapshot = models.JSONField(default=dict)

    served_at = models.DateTimeField(auto_now_add=True)
```

Required uniqueness:

```text
student_assignment + section + position
```

Once created, these fields are immutable:

- student assignment;
- section;
- position;
- exercise;
- variant;
- credited elements;
- recipe snapshot; and
- selector version.

Attempts and submissions reference `StudentAssignmentSlot`, not merely playlist
plus exercise number.

### Assignment instance or progress owner

The current `PerformanceData` uniqueness is `(user, playlist, course)`. Slots
need the same contextual distinction and should not infer it from loosely
related request parameters.

Required model:

```python
class StudentAssignment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course_assignment = models.ForeignKey(
        PlaylistCourseOrdered,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    assignment = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    recipe_version = models.CharField(max_length=64)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

This creates a non-null owner for every slot, removes nullable-course uniqueness
ambiguity, and provides a natural owner
for completion state, grade policy, restart behavior, and future reassignment.

Validation requires `course_assignment.playlist_id == assignment_id` when a
course assignment is present.

Required uniqueness:

- one active `StudentAssignment` per `(student, course_assignment)`; and
- one active standalone `StudentAssignment` per `(student, assignment)` when
  `course_assignment` is null.

Runtime selection failures are recorded in a separate
`AssignmentSelectionIncident` keyed to the student assignment, section, and
position. A blocked position is not represented by a partially populated slot;
a slot exists only after a concrete exercise has been selected.

## Taxonomy contract

`eligible_elements` and `coverage_quotas` use canonical taxonomy identifiers.
The taxonomy is the shared vocabulary for:

- exercise generation;
- exercise tagging;
- teacher assignment recipes;
- individualized selection;
- coverage reporting; and
- student mastery.

Not every taxonomy tag is an assignable musical element. Unit, mode, source,
workflow, and organizational tags remain filters or metadata.

Assignable taxonomy entries need metadata such as:

```json
{
  "tag": "Chord_Third_In_Bass",
  "label": "Chord with the 3rd in the bass",
  "aliases": ["first inversion"],
  "concept_family": "bass_chord_member",
  "assignable_element": true,
  "quota_eligible": true,
  "exercise_types": ["roman_analysis", "harmonic_analysis", "figured_bass"]
}
```

Agreed terminology:

```text
Root position
Chord with the 3rd in the bass
Chord with the 5th in the bass
Chord with the 7th in the bass
```

Canonical identifiers:

```text
Chord_Root_Position
Chord_Third_In_Bass
Chord_Fifth_In_Bass
Chord_Seventh_In_Bass
```

Conventional inversion terms remain searchable aliases and optional explanatory
help text, not the primary teacher-facing labels.

Existing tags such as `Inversions_First` and `Inversions_Second` should migrate
to the new identifiers. During migration, taxonomy lookup and exercise matching
may accept both identifiers, but new generation and authoring must emit only the
new canonical tags.

The assignable-element metadata must be generated or served from the taxonomy's
single source of truth. Do not add a separate Python and JavaScript allowlist.

## Assignment recipe semantics

Example:

```json
{
  "title": "Secondary dominants and bass chord members",
  "sections": [
    {
      "order": 1,
      "exercise_types": ["roman_analysis"],
      "quantity": 6,
      "eligible_elements": [
        "Secondary_Dominant",
        "Chord_Third_In_Bass",
        "Chord_Fifth_In_Bass"
      ],
      "coverage_quotas": {
        "Secondary_Dominant": 2,
        "Chord_Third_In_Bass": 1,
        "Chord_Fifth_In_Bass": 1
      },
      "min_complexity": 3,
      "max_complexity": 6
    },
    {
      "order": 2,
      "exercise_types": ["figured_bass"],
      "quantity": 2,
      "eligible_elements": ["Seventh_Chords"],
      "coverage_quotas": {
        "Seventh_Chords": 2
      }
    }
  ]
}
```

Sections are served in ascending `order`. A student cannot enter a later section
until every slot in the preceding section is complete, unless the assignment's
explicit navigation policy permits review or skipping.

Quotas are minimum exposure requirements, not exact counts. An exercise may
satisfy multiple quotas simultaneously. A secondary dominant with the 3rd in
the bass credits both elements.

After all quotas are satisfied, remaining positions are selected freely from
the eligible pool according to the student's needs and the section constraints.

## Publication and feasibility validation

Teachers may save incomplete assignment drafts. Publication requires a
feasibility report for every individualized section.

Validation checks:

1. all taxonomy identifiers exist and are assignable;
2. all identifiers apply to at least one selected exercise type;
3. all structural field constraints pass;
4. a non-empty candidate pool exists;
5. every quota has enough matching candidates;
6. the quotas are jointly satisfiable across the requested quantity;
7. the section can avoid prohibited immediate repetition where that policy is
   enabled; and
8. each requested key, mode, source, or complexity restriction has coverage.

Simple per-tag counts are insufficient because overlapping tags can make
individual quotas appear satisfiable while the combined assignment is not.
Publication validation must solve the same constrained-coverage problem used
by runtime selection.

The report includes:

- candidate count by exercise type;
- coverage count by eligible element;
- jointly feasible or infeasible status;
- the smallest unsatisfied constraint set;
- representative matching exercises;
- missing generation requirements; and
- actions:
  - **Generate missing exercises**;
  - revise recipe;
  - remove or lower a quota; or
  - broaden constraints.

Publication is blocked while any section is infeasible. Requirements are never
silently weakened.

### Generation integration

“Generate missing exercises” creates a declarative generation request using the
existing generation-manifest service rather than invoking ad hoc management
commands from the view.

The manifest must be extended to represent:

- assignment section;
- exercise type;
- required taxonomy elements;
- quantity or coverage deficit;
- keys and complexity;
- ownership and official-content policy;
- dry-run estimates; and
- idempotency key.

Generated exercises are normal UMTO exercises in the exercise library. They are
not permanently owned by one student's assignment slot and may satisfy future
assignments.

Generation is asynchronous when measured execution time exceeds the ordinary
request budget. Publication remains blocked until generation finishes and the
section passes validation.

## Quota allocation

For one section and student, define:

```text
Q(e) = teacher's minimum quota for element e
C(e) = number of already served slots credited to element e
R(e) = max(Q(e) - C(e), 0)
S    = number of unserved positions remaining, including the current position
```

Before selecting the current slot, the selector must choose a candidate such
that the remaining positions can still satisfy every `R(e)`.

An exercise credits every quota-eligible element that:

- is declared in the section's `eligible_elements`; and
- is present in the exercise's canonical skill tags or validated analysis
  metadata.

One exercise may reduce multiple remaining quotas.

### Feasibility-preserving selection

For each candidate:

1. apply the candidate's credited elements;
2. calculate the residual quotas;
3. determine whether the residual candidate pool can satisfy those quotas in
   `S - 1` positions;
4. discard the candidate if not; and
5. rank the remaining feasible candidates.

The feasibility solver may initially use a bounded backtracking or
integer-programming-style search because section quantities are expected to be
small. It must be deterministic and shared by publication validation and
runtime selection to prevent disagreement between the two.

The implementation plan must benchmark realistic candidate-pool sizes before
choosing the exact algorithm. It may precompute element bitmasks and cap the
runtime candidate subset after preserving all quota-relevant candidates.

## Just-in-time individualized selection

Selection occurs when the student first opens an unserved slot.

Algorithm:

1. Resolve the `StudentAssignment`, section, and position.
2. Lock or atomically claim the unique slot identity.
3. If the slot already exists, return it unchanged.
4. Verify that preceding required sections and positions permit access.
5. Load the published recipe snapshot.
6. Load previous slots and completed attempts for this assignment.
7. Calculate remaining section quotas.
8. Build candidates matching:
   - exercise type;
   - required and excluded tags;
   - eligible musical elements;
   - complexity;
   - key or transposition policy;
   - source and official-content policy;
   - visibility and authorization; and
   - any exercise-type-specific constraints.
9. Exclude candidates that:
   - were deleted or made inaccessible;
   - duplicate a prohibited recent exercise or musical fingerprint;
   - conflict with the student's already served assignment variants; or
   - make remaining quota fulfillment infeasible.
10. Rank feasible candidates.
11. Choose deterministically among equivalent candidates.
12. Persist the slot, credited elements, variant, recipe snapshot, mastery
    snapshot, rationale, and selector version.
13. Return the persisted slot to the player.

### Ranking order

Ranking priorities, in order:

1. preserve feasibility of every remaining quota;
2. target the student's weakest eligible skill;
3. satisfy the most urgent remaining quotas;
4. avoid repeating equivalent musical content;
5. match the desired complexity progression;
6. diversify key, source, and musical surface where configured; and
7. deterministic tie-breaking.

Feasibility is a hard constraint. Personalization preferences are ranking
signals and cannot override the teacher's coverage contract.

### Determinism

Tie-breaking seed:

```text
student_assignment_id + section_id + position + selector_version
```

The result is persisted immediately, so determinism is a recovery aid rather
than the primary identity mechanism.

### Atomicity and concurrency

Two simultaneous requests for the same slot must return the same slot.

The service runs in a transaction and relies on the unique slot constraint.
The implementation may use `select_for_update`, an insert-and-retry pattern, or
database-native upsert semantics. A losing request reloads the winning row.

Do not hold a database lock while running expensive generation or unbounded
candidate analysis.

## Runtime failure behavior

Publication validation reduces failures but cannot eliminate them. Exercises may
be unpublished, deleted, retagged, or made inaccessible after publication.

If no feasible candidate exists at runtime:

- do not weaken quotas;
- do not generate synchronously;
- persist an `AssignmentSelectionIncident`;
- show the student a neutral temporary-unavailability message;
- notify the teacher or administrator with the exact missing coverage;
- offer generation or recipe revision;
- preserve already served slots; and
- retry only the unserved blocked position after the issue is resolved.

Recipe edits do not replace already served slots. They create a new recipe
revision for future slots or a new assignment version, according to the
teacher's chosen remediation.

## Navigation, submission, and grading

The modern student player loads a `StudentAssignmentSlot` ID.

The player context contains:

```json
{
  "studentAssignmentId": 123,
  "slotId": 456,
  "sectionOrder": 1,
  "sectionPosition": 3,
  "assignmentPosition": 3,
  "assignmentTotal": 8,
  "exerciseId": "EX1234",
  "variant": {"key": "G"},
  "previousSlotUrl": "...",
  "nextSlotUrl": "..."
}
```

Submission endpoints:

- accept `slotId`;
- authorize it against the current student;
- grade the slot's stored exercise and variant;
- reject an exercise ID that does not match the slot;
- create an attempt referencing the slot; and
- never rerun selection to determine what the student supposedly answered.

The next slot is selected only when the student navigates to it. Completing the
current slot does not need to preselect the rest of the assignment.

Section order is preserved. Review navigation may revisit existing slots but
does not create replacements.

Assignment completion means every required slot has met the assignment's
completion policy. It does not require every underlying taxonomy skill to reach
global mastery.

## Teacher workflow

### Create assignment

The teacher:

1. creates or opens an Assignment;
2. adds ordered sections;
3. chooses an exercise type for each section;
4. chooses eligible musical elements from taxonomy-backed controls;
5. sets minimum coverage quotas;
6. optionally sets complexity, keys, modes, sources, and exclusions;
7. previews candidate coverage;
8. generates missing exercises or revises the recipe;
9. publishes when all sections are feasible; and
10. schedules the assignment in a course.

Teacher-facing controls use musical labels, not raw taxonomy tags.

Example:

```text
Harmonic analysis — 6 exercises

Include:
  Secondary dominants                  at least 2
  Chords with the 3rd in the bass      at least 1
  Chords with the 5th in the bass      at least 1

Complexity: 3-6
```

### Preview

Because student work is individualized, preview has two modes:

- **Coverage preview** shows the pool, counts, feasibility, and representative
  candidates.
- **Sample student preview** runs the selector against a chosen or synthetic
  mastery profile without creating real student slots.

The teacher does not need to inspect every student's concrete assignment before
publication.

## Student workflow

Students see:

- assignment title and instructions;
- ordered sections;
- a fixed total exercise count;
- current position and completion;
- due/open/locked state;
- concrete served exercises; and
- review of prior attempts.

Students do not see “adaptive playlist,” pool size, or quota machinery.
Personalization appears as an ordinary bounded assignment.

## Existing-data migration

### Existing fixed playlists

An existing non-adaptive ordered playlist behaves as one implicit fixed section:

```text
quantity = current served exercise count
source_mode = fixed
membership = existing ExercisePlaylistOrdered order
```

No immediate data copy is required. A later migration can materialize explicit
sections when a teacher edits or converts the assignment.

### Existing bounded adaptive playlists

If an adaptive playlist already has an intended finite count, migrate it to one
individualized section:

```text
quantity = intended count
exercise_types = inferred or explicitly reviewed
eligible_elements = current skill tags after taxonomy cleanup
coverage_quotas = {}
```

Empty quotas preserve current personalized targeting without promising a
specific distribution.

### Existing endless adaptive playlists

Migrate to Drill/Practice, not Assignment. Until the drill model exists, keep
them on the legacy compatibility path and label them as open-ended practice.

### Existing progress

Do not fabricate historical slot identities from ambiguous adaptive
`PerformanceData` unless the concrete exercise and position can be proven.

Migration rules:

- fixed playlist history may map by ordered position;
- adaptive history with reliable recorded position and exercise ID may create
  historical slots;
- ambiguous rows remain legacy history and are displayed separately;
- new attempts after slot rollout always reference a slot.

## Incremental rollout

### Phase 1: Slot foundation under existing playlists

- Add `StudentAssignment`, `AssignmentSection`, and `StudentAssignmentSlot`.
- Materialize one compatibility section for each existing playlist when it is
  first served or edited; no bulk migration is required.
- Fixed slots resolve from ordered membership.
- Adaptive slots use just-in-time selection and persist identity.
- Update modern player and submission endpoints to use slot IDs.
- Redirect legacy student delivery routes to the modern player.
- Keep teacher playlist CRUD and course scheduling intact.

This phase resolves the current adaptive identity and submission bugs without
requiring the full recipe editor.

### Phase 2: Assignment sections and recipes

- Expand compatibility sections into the full recipe model and editor.
- Add fixed section membership.
- Add taxonomy-backed recipe validation.
- Add section ordering, quantities, eligible elements, and quotas.
- Add teacher coverage preview.

### Phase 3: Missing-content generation

- Extend `GenerationManifest`.
- Add dry-run generation requirements from feasibility reports.
- Add “Generate missing exercises.”
- Revalidate and publish after generation.

### Phase 4: Product rename and course integration

- Change teacher/student language from Playlist to Assignment.
- Replace ordinary teacher playlist screens with assignment screens.
- Introduce a clearer course-assignment relation while preserving schedules,
  recurring policies, and gradebook references.
- Keep database compatibility aliases during migration.

### Phase 5: Separate content sets and drills

- Introduce reusable Exercise Sets.
- Introduce open-ended Drills/Practice.
- Migrate public collections and endless adaptive playlists.
- Remove assignment responsibilities from the legacy Playlist model.

### Phase 6: Legacy retirement

- Remove parallel legacy player views and templates after redirects have been
  stable and internal links have migrated.
- Remove obsolete playlist adaptive flags and inference code.
- Retire ambiguous performance-position logic.

## Compatibility with the earlier `selection_mode` spec

Do not implement `target_length` as the long-term bounded-assignment mechanism.
Section `quantity` and persisted slots replace it.

Do not remove the existing adaptive booleans merely to introduce
`selection_mode` before Phase 1 slots exist. That migration produces substantial
write-site churn without fixing assignment identity.

If an interim compatibility field is needed, it should distinguish legacy
behavior only and must not become the new recipe architecture.

Retain these findings from the prior audit:

- adaptive selection must receive the actual position;
- performance lookup must be course-aware;
- scoped/global pool selections cannot require playlist membership to validate
  a persisted identity;
- submission must not rediscover the served exercise;
- direct legacy routes must not bypass bounded assignment rules;
- MusicXML and ordinary save flows need the same orphan-content policy; and
- all old boolean write sites must eventually migrate.

## Permissions and content policy

- A student may load only slots belonging to their own assignment instance.
- A teacher may inspect slots only for courses they are authorized to manage.
- Slot selection uses only exercises visible to the assignment's content policy.
- Official assignments may require official exercises; teacher-owned assignments
  may permit owned, shared, or official exercises.
- Exercise deletion is blocked while referenced by a slot; unpublishing affects
  future selection but not already served work.
- Recipe snapshots and selection rationale are instructor-visible audit data,
  not student-facing mastery labels.

## Observability

Record:

- selector version;
- candidate count before and after each hard filter;
- remaining quotas;
- chosen exercise and credited elements;
- ranking factors;
- fallback or blocked reason;
- selection latency; and
- generation deficits.

Do not emit full exercise payloads or sensitive student data to ordinary logs.

Useful aggregate metrics:

- slot-selection success rate;
- selection-incident rate;
- median and p95 selection latency;
- candidate-pool coverage by taxonomy element;
- generation requests caused by infeasible recipes; and
- assignment completion by section and exercise type.

## Testing strategy

### Model and validation tests

- section ordering and uniqueness;
- slot uniqueness under concurrent requests;
- immutable slot identity;
- quota field validation;
- taxonomy applicability validation;
- recipe revision snapshots; and
- course and non-course assignment-instance identity.

### Feasibility tests

- disjoint quotas;
- overlapping quotas satisfied by one exercise;
- individually sufficient but jointly infeasible quotas;
- impossible quantity;
- filtered keys and complexity;
- canonical and migration-alias tags; and
- publication blocked with an actionable deficit report.

### Selection tests

- same slot always returns the same exercise;
- different students may receive different exercises;
- later slots use updated mastery;
- section order is preserved;
- every completed section satisfies minimum quotas;
- one exercise may credit multiple quotas;
- quota feasibility outranks weakness targeting;
- no immediate duplicate when alternatives exist;
- deterministic tie-breaking; and
- scoped/global exercises need not be linked through playlist membership.

### Submission tests

- submission succeeds for an individualized unlinked exercise;
- slot/exercise mismatch is rejected;
- unauthorized slot is rejected;
- transposed variant grades against the stored variant;
- review loads the original slot;
- course-specific attempts remain isolated; and
- submission never invokes the selector.

### Concurrency tests

- simultaneous requests create one slot;
- losing request returns the winning slot;
- retry after transaction failure remains stable; and
- selection-incident recovery preserves earlier slots.

### Migration and compatibility tests

- fixed playlist becomes an implicit fixed assignment section;
- bounded adaptive playlist becomes an individualized section;
- endless adaptive playlist remains open-ended practice;
- reliable historical progress maps safely;
- ambiguous history is preserved without invented slot identity;
- legacy URLs redirect to the modern slot route; and
- old course schedules and recurring assignments continue to work.

## Documentation impact

Implementation must update:

- teacher assignment authoring documentation;
- student assignment and review documentation;
- taxonomy metadata documentation;
- generation-manifest documentation;
- management command catalog if new commands are added;
- exercise type documentation when recipe applicability changes; and
- migration notes for legacy playlists and URLs.

## Decisions established by this design

- Product term: **Assignment**.
- Individualized selection is the default for recipe sections.
- Selection occurs just in time.
- Served slots are immutable.
- Sections remain in teacher-defined order.
- Teachers select exercise types and musical elements.
- Coverage is defined by minimum quotas across a section.
- One exercise may satisfy multiple quotas.
- Publication is blocked when the recipe is infeasible.
- Teachers may generate missing exercises or revise the recipe.
- Assignable elements come from taxonomy metadata.
- Primary terminology uses bass chord members:
  - root position;
  - chord with the 3rd in the bass;
  - chord with the 5th in the bass;
  - chord with the 7th in the bass.
- Conventional inversion terminology remains an alias.
- Endless practice is not an assignment.

## Open questions deferred to implementation planning

- Exact feasibility-solver implementation after candidate-pool benchmarks.
- Exact split between typed section columns and validated selector JSON.
- Recipe revision behavior when a teacher edits an assignment after some
  students have started.
- Initial exercise types supported by the recipe editor.
- Exact teacher-facing controls for quota entry and generation review.

These questions affect implementation sequencing and UI detail but do not change
the approved domain model.
