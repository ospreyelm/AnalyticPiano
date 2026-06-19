# Assignment Slot Foundation (Phase 1)

## Status and relationship to other documents

This is Phase 1 of
[2026-06-19-individualized-assignment-recipes-design.md](2026-06-19-individualized-assignment-recipes-design.md)
("the roadmap"), split out after a second Codex review round so the
implementation-ready piece isn't entangled with the roadmap's larger,
separately-prioritized sub-projects (quota feasibility solver, taxonomy
metadata rebuild). **No quotas, no taxonomy contract, no recipe editor.** This
document alone is sufficient for an implementation plan.

It also supersedes the bounded-adaptive portion of
[2026-06-18-playlist-selection-mode-design.md](2026-06-18-playlist-selection-mode-design.md)
— that document's orphan-exercise fix remains separate, valid, independent
work.

## Problem (the part this phase actually fixes)

Verified across three rounds of review on the prior spec:

- `get_adaptive_exercise_for_view` never threads `exercise_num` through to
  `get_next_exercise`, so navigation pinning silently evaluates slot 1 for
  every request.
- Pinning validity additionally requires `ExercisePlaylistOrdered` linkage,
  which the scoped/dynamic pool mode doesn't use — pinning is effectively
  disabled for the one mode meant to matter most.
- The `PerformanceData` lookup used for pinning ignores `course`, despite
  `(user, playlist, course)` being the actual uniqueness constraint — a
  `MultipleObjectsReturned` crash risk.
- Three call sites (`PlayerDefinitionView`, `_submit_exercise_performance`,
  `identification_answers_view`) resolve "what exercise is at this slot" with
  zero adaptive awareness, including one that can return a hard `400` on score
  submission.
- A cap on adaptive serving (as the superseded spec proposed) is bypassable by
  direct URL, because nothing actually blocks resolution server-side — only
  navigation links were hideable.

All of these are symptoms of the same root cause: adaptive serving
**recomputes** "what exercise is at position N" on every request instead of
**persisting** it once decided. Phase 1 fixes this by construction: once a
slot is created, "what's at position N" becomes a row lookup, not a
recomputation. Every bug above stops being reachable, not just patched at each
call site.

## Goals

- Persist served-exercise identity per student per slot, immutably, the first
  time it's resolved.
- Make submission grade the stored slot, never rerun selection.
- Let a teacher convert an existing unbounded adaptive playlist into a
  bounded, individualized course by setting one number — closing the original
  "teacher can't build a reasonably-sized course from the mastery pool" gap —
  without needing the full recipe editor.
- Retire the blind legacy call sites by redirecting them to the modern player,
  instead of auditing and patching each one.

## Non-goals

- No coverage quotas, no `eligible_elements`, no per-musical-element targeting.
  Selection within a section still uses today's mastery/weak-skill-targeting
  logic (ported, not redesigned), just persisted into a slot.
- No taxonomy metadata rebuild (`assignable_element`, `concept_family`,
  aliases). Not needed — sections reference existing `skill_tags`/complexity
  directly, the same fields `get_next_exercise` already filters on today.
- No recipe editor UI. The only new teacher-facing control is a single
  "exercise count" field on an existing adaptive playlist (see Migration).
- No feasibility validation, no "Generate missing exercises." Nothing in this
  phase can become infeasible — there's no quota to fail.
- No product rename (Playlist stays Playlist in the database and most UI).
- Does not touch `Playlist.is_adaptive`/`is_dynamic` write sites — those
  remain exactly as they are today; this phase adds new tables, it doesn't
  modify the existing boolean-flag system. (The roadmap doc's note on
  retaining the prior audit's findings applies if/when that flag cleanup is
  separately revisited.)

## Domain model

```text
Course
  -> PlaylistCourseOrdered
    -> Playlist
      -> AssignmentSection (one per playlist, Phase 1)
        -> StudentAssignment (per student)
          -> StudentAssignmentSlot (per position)
```

### `AssignmentSection` (Phase 1 — minimal)

```python
class AssignmentSection(models.Model):
    assignment = models.ForeignKey(
        Playlist, related_name="assignment_sections", on_delete=models.CASCADE,
    )
    order = models.PositiveSmallIntegerField(default=1)
    source_mode = models.CharField(
        max_length=24,
        choices=(("fixed", "Fixed exercises"), ("individualized", "Individualized selection")),
    )
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    # Mirrors today's get_next_exercise filtering — no taxonomy contract needed.
    exercise_types = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    required_tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    excluded_tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    min_complexity = models.PositiveSmallIntegerField(null=True, blank=True)
    max_complexity = models.PositiveSmallIntegerField(null=True, blank=True)
    allowed_keys = ArrayField(models.CharField(max_length=16), default=list, blank=True)
```

Constraints: unique `(assignment, order)`; `quantity >= 1`;
`min_complexity <= max_complexity` when both set. No quota fields exist in
Phase 1 — adding `coverage_quotas`/`eligible_elements` is additive in Phase 2,
not a migration of this table's meaning.

### `AssignmentSectionExercise` (fixed section membership)

```python
class AssignmentSectionExercise(models.Model):
    section = models.ForeignKey(AssignmentSection, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField()
```

Constraint: unique `(section, order)`. For the first migration, each existing
fixed playlist's compatibility section reads `ExercisePlaylistOrdered`
directly rather than copying rows — no bulk data copy required.

### `StudentAssignment`

```python
class StudentAssignment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course_assignment = models.ForeignKey(
        PlaylistCourseOrdered, null=True, blank=True, on_delete=models.CASCADE,
    )
    assignment = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

This is the non-null, unambiguous owner `PerformanceData`'s
`(user, playlist, course)` lookup never had — fixes the `MultipleObjectsReturned`
risk by construction, since a `StudentAssignment` row *is* the
(student, playlist, course) identity, looked up once, not re-derived per
request.

Validation: `course_assignment.playlist_id == assignment_id` when present.
Uniqueness: one active `StudentAssignment` per `(student, course_assignment)`,
and per `(student, assignment)` when `course_assignment` is null.

### `StudentAssignmentSlot`

```python
class StudentAssignmentSlot(models.Model):
    student_assignment = models.ForeignKey(StudentAssignment, related_name="slots", on_delete=models.CASCADE)
    section = models.ForeignKey(AssignmentSection, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField()

    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    variant = models.JSONField(default=dict, blank=True)  # e.g. {"key": "G"} for transposition

    mastery_snapshot = models.JSONField(default=dict, blank=True)
    served_at = models.DateTimeField(auto_now_add=True)
```

Uniqueness: `(student_assignment, section, position)`. Once created,
`exercise`/`variant`/`section`/`position` are immutable — no code path updates
them after creation.

### `AssignmentSelectionIncident`

```python
class AssignmentSelectionIncident(models.Model):
    student_assignment = models.ForeignKey(StudentAssignment, on_delete=models.CASCADE)
    section = models.ForeignKey(AssignmentSection, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

Recorded when no candidate exists at runtime (exercise pool emptied/retagged
after the playlist was set up). A blocked position has no slot — a slot only
ever represents a successfully resolved exercise.

## Just-in-time selection (no quotas)

Selection occurs when a student first opens an unserved slot:

1. Resolve `StudentAssignment` (create if first visit), section, position.
2. Atomically claim the slot (`select_for_update` or insert-and-retry; a
   losing concurrent request reloads the winning row instead of re-selecting).
3. If the slot exists, return it unchanged — no recomputation, ever.
4. Build the candidate pool: `exercise_types`, `required_tags`/`excluded_tags`,
   complexity range, key/transposition policy, visibility — the same filters
   `get_next_exercise` already applies today, just evaluated once per slot
   instead of once per request.
5. Rank by: target the student's weakest eligible skill → avoid repeating
   recent content → match complexity progression → deterministic tie-break.
   (This is today's `mastery.py:score_exercise` logic, ported — not
   redesigned. No quota-feasibility step exists in Phase 1.)
6. If no candidate exists, record an `AssignmentSelectionIncident`, show a
   neutral "temporarily unavailable" message, do not generate synchronously.
7. Persist the slot with mastery snapshot. Return it to the player.

Determinism (for the rare retry/recovery case, not the primary identity
mechanism — persistence is): seed on
`student_assignment_id + section_id + position`.

## Navigation, submission, and grading

The modern player loads a `StudentAssignmentSlot` ID. Submission endpoints:

- accept `slotId`, not `playlistId` + `exercise_num`;
- authorize it against the current student;
- grade the slot's stored `exercise`/`variant`;
- reject a request whose claimed exercise doesn't match the slot;
- create the attempt referencing the slot;
- **never call the selector to figure out what the student answered** — this
  is the direct fix for the confirmed `_submit_exercise_performance` 400
  landmine and the broken pinning-based "stability" the old design depended
  on.

The next slot is resolved only on navigation to it — completing slot N
doesn't pre-resolve N+1.

`assignmentTotal` shown to the student is `section.quantity` (a real number,
always — no `None`/unbounded case exists in Phase 1, because every Phase 1
section has an explicit teacher-supplied quantity by construction).

Legacy student delivery routes (`PlaylistView`, `PlayerDefinitionView`'s old
resolution path, etc.) become redirects to the modern slot-based player rather
than being individually patched for adaptive-awareness — this is why the
prior spec's "patch every blind call site" approach kept growing scope, and
this phase avoids repeating it.

## Migration

### Existing fixed playlists — automatic

One implicit fixed `AssignmentSection` per playlist:
`quantity = current served exercise count`, `source_mode = "fixed"`,
membership read live from `ExercisePlaylistOrdered` (no copy). Materialized
lazily on first serve or edit, not via bulk migration.

### Existing adaptive playlists — explicit only, never inferred

**Verified: no current adaptive playlist has any notion of an intended
count** (0 of 58 locally) — there is nothing to infer a `quantity` from. Per
the roadmap's corrected migration policy:

- **Default: every existing adaptive playlist stays on the legacy
  compatibility path, unbounded, exactly as today.** No section is created
  for it automatically.
- **Conversion is a single explicit teacher action:** the teacher sets one
  `quantity` field on the playlist (not a full recipe — `exercise_types`/tags
  default from the playlist's existing `skill_tags`/`tags`). This creates one
  `individualized` `AssignmentSection` with that quantity. From that point,
  the playlist serves through the slot system, bounded, with all the bugs
  above fixed.
- This minimal action is the entire Phase 1 teacher-facing UI surface beyond
  what already exists — not a recipe editor, just one number.

### Existing progress

Do not fabricate historical slot identities from ambiguous adaptive
`PerformanceData`. Fixed-playlist history maps by ordered position. Adaptive
history with a reliably recorded position and exercise ID may backfill a
historical slot; ambiguous rows stay as legacy history, shown separately. Any
attempt after slot rollout always references a slot — no new ambiguous rows
are created going forward.

## Permissions

- A student loads only slots belonging to their own `StudentAssignment`.
- Slot selection only considers exercises visible per existing
  `is_public`/`authored_by`/`content_permits` rules — no new visibility model.
- Exercise deletion is blocked while referenced by a slot.

## Testing strategy

- Model: section/slot uniqueness, slot immutability, `StudentAssignment`
  uniqueness with/without `course_assignment`.
- Selection: same slot always returns the same exercise on repeat access
  (fixes the slot-1 pinning bug); different students may get different
  exercises; later slots use updated mastery; deterministic tie-breaking.
- Submission: succeeds for an individualized exercise with zero
  `ExercisePlaylistOrdered` linkage (the confirmed 400 regression); slot/
  exercise mismatch rejected; unauthorized slot rejected; submission never
  invokes the selector.
- Concurrency: two simultaneous requests for the same slot return one slot;
  the losing request reloads rather than re-selecting.
- Migration: fixed playlist becomes an implicit fixed section automatically;
  adaptive playlist stays unbounded/legacy until a teacher explicitly sets a
  quantity; setting a quantity creates exactly one individualized section.
- Cap correctness: a direct URL request for a position beyond
  `section.quantity` 404s/redirects — verifies the cap is enforced before
  resolution, not just hidden from navigation links (the confirmed
  direct-URL-bypass gap in the superseded design).

## Open questions deferred to implementation planning

- Exact redirect mechanics for each legacy route (`PlaylistView`,
  `PlayerDefinitionView`, etc.) — 301 vs 302, and whether any need a
  transition period before becoming hard redirects.
- Whether `mastery_snapshot`/`selector_version`-equivalent fields are needed
  in Phase 1 for debugging, or can wait for the roadmap's full observability
  section in a later phase.
- Where the "set quantity to convert" control lives in the teacher UI for
  Phase 1 (a minimal addition to the existing playlist edit screen is assumed,
  not specified here).
