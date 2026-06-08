# Chordal UMTO Staff Distribution Picker — Design Spec

Date: 2026-06-08

Status: Approved design. Implementation plan pending.

---

## Problem

Chordal UMTO exercises can render in multiple staff layouts because
`exercise_sheet.js` already honors `score.umto.metadata.staffDistribution` when
converting `umto.chords[]` into a processed score. Teachers currently cannot persist
that setting from the dashboard edit page.

The dashboard form has a generic `staff_distribution` field, but the current chorale
branch treats every `umto_chorale` row as SATB chorale material and forces
`staffDistribution = "chorale"`. That is correct for voices-kind chorale UMTO, but wrong
for chordal UMTO, where the same `umto_chorale` frontend type represents vertical chord
events rather than S/A/T/B voices.

## Goal

Add a dashboard-only `staffDistribution` picker for chordal UMTO exercises.

The picker must persist the selected value into chordal UMTO metadata so the existing
renderer uses it on preview/student playback. It must not change SATB chorale UMTO
behavior, and it must not introduce new legacy exercise behavior.

## Scope

In scope:

- Detect chordal UMTO in `ExerciseForm`.
- Show the existing `staff_distribution` field only for chordal UMTO among UMTO chorales.
- Initialize the field from `data.score.umto.metadata.staffDistribution`, falling back to
  top-level `data.staffDistribution`, then `"keyboard"`.
- Save the selected value to `data.score.umto.metadata.staffDistribution`.
- Mirror the value to top-level `data.staffDistribution` for existing frontend payload
  compatibility.
- Keep SATB voices-kind chorale UMTO forced to `"chorale"` with the field hidden.
- Add focused form tests for chordal UMTO persistence and SATB regression.

Out of scope:

- Play-view session storage behavior.
- Legacy chord exercise behavior.
- Broader edit-exercise page refactoring.
- Renderer changes.
- New staff distribution option names or labels.

## Decisions

### Chordal UMTO Only

The picker applies only when all of these are true:

- `data["isUMTO"] is True`
- `data["type"] == "umto_chorale"`
- `data["score"]["umto"]["metadata"]["score_kind"] == "chordal"`

Voices-kind / SATB chorale UMTO must keep the current forced chorale layout. The
existing S/A/T/B chorale branch is intentionally preserved.

### Form Owns Initialization and Persistence

`apps/exercises/forms.py` remains the right boundary for this change because it already
owns dashboard edit initialization, visibility rules, and writes back exercise JSON.
The dashboard view and template should not need score-kind-specific logic for this field.

### Metadata Is Authoritative

For chordal UMTO, `score.umto.metadata.staffDistribution` is the canonical persisted
value. The top-level `data.staffDistribution` mirror remains for compatibility with
existing frontend payload conventions and table/list display code.

### Existing Choice Set

Use the current `DISTRIBUTION_CHOICES` values. The implementation should not invent
new tokens such as `"grand"` unless the renderer and model contract are updated in a
separate change. The current renderer already consumes existing dashboard values such as
`"keyboard"`, `"grandStaff"`, `"LH"`, and `"RH"`.

## Data Flow

1. Teacher opens a chordal UMTO exercise in the dashboard edit page.
2. `ExerciseForm.__init__()` detects chordal UMTO.
3. `staff_distribution` remains visible and initializes from UMTO metadata.
4. Teacher saves the form.
5. `ExerciseForm.save()` writes the selected value to:
   - `instance.data["score"]["umto"]["metadata"]["staffDistribution"]`
   - `instance.data["staffDistribution"]`
6. Preview/student render reads the persisted value through the existing frontend
   rendering path.

For SATB chorale UMTO, the existing `_configure_chorale_fields()` /
`_store_chorale_settings()` behavior continues to hide the field and force
`data["staffDistribution"] = "chorale"`.

## Implementation Shape

Expected helper methods in `apps/exercises/forms.py`:

- `_detect_chordal_umto()` returns `True` only for chordal UMTO rows.
- `_get_chordal_umto_metadata()` safely returns the nested metadata dict or `{}`.
- `_configure_chordal_umto_fields()` leaves `staff_distribution` visible and sets its
  initial value.
- `_store_chordal_umto_settings(instance)` writes the selected distribution to metadata
  and the top-level mirror.

The chorale configuration flow should branch early:

- chordal UMTO: configure chordal staff distribution and skip SATB chorale-only voice
  settings.
- other chorale UMTO / legacy chorale: keep existing chorale behavior.

## Tests

Add focused tests in the dashboard/form test area:

- Chordal UMTO edit form exposes `staff_distribution` and initializes from
  `score.umto.metadata.staffDistribution`.
- Saving a chordal UMTO exercise with a new value writes both metadata and top-level
  mirror.
- SATB voices-kind chorale UMTO still hides `staff_distribution` and forces
  top-level `staffDistribution` to `"chorale"`.

No legacy-specific test is required because legacy behavior is not part of this change.

## Risks

- `umto_chorale` is a shared frontend type. The implementation must branch by
  `metadata.score_kind`, not by top-level type alone.
- `ExerciseForm.save()` currently writes top-level `staffDistribution` before
  score-kind-specific handlers run. The chordal handler must run after that generic write
  and overwrite metadata/mirror consistently.
- The later edit-page refactor (#4) should preserve this score-kind-specific boundary
  instead of folding chordal UMTO back into the SATB chorale branch.
