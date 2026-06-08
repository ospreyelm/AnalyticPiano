# Chordal UMTO Staff Distribution Picker — Design Spec

Date: 2026-06-08

Status: Approved design. Implementation plan approved and committed.

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

The picker must persist the selected value into chordal UMTO metadata, and the chordal
UMTO renderer must honor the same staff distribution tokens exposed by the dashboard
choice set. It must not change SATB chorale UMTO behavior, and it must not introduce new
legacy exercise behavior.

## Scope

In scope:

- Detect chordal UMTO in `ExerciseForm`.
- Show the existing `staff_distribution` field only for chordal UMTO among UMTO chorales.
- Initialize the field from `data.score.umto.metadata.staffDistribution`, falling back to
  top-level `data.staffDistribution`, then `"keyboard"`.
- Save the selected value to `data.score.umto.metadata.staffDistribution`.
- Mirror the value to top-level `data.staffDistribution` for existing frontend payload
  compatibility.
- Update the chordal UMTO render conversion path so persisted dashboard choices have
  matching preview/student behavior.
- Keep SATB voices-kind chorale UMTO forced to `"chorale"` with the field hidden.
- Add focused form tests for chordal UMTO persistence and SATB regression.
- Add focused renderer/conversion tests for chordal UMTO staff distribution tokens.

Out of scope:

- Play-view session storage behavior.
- Legacy chord exercise behavior.
- Broader edit-exercise page refactoring.
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
separate change.

The chordal UMTO converter currently reads `score.umto.metadata.staffDistribution`, but
it does not yet give every dashboard token distinct behavior. This change must extend
that converter so the existing dashboard values behave consistently:

- `"keyboard"`, `"keyboardPlusLHBias"`, and `"keyboardPlusRHBias"` use keyboard-style
  grand-staff splitting, with the documented split bias where applicable.
- `"grandStaff"` uses grand-staff splitting without collapsing to a single staff.
- `"LH"` renders all chord tones on the lower staff.
- `"RH"` renders all chord tones on the upper staff.
- `"chorale"` remains reserved for SATB voices-kind chorale UMTO and should not be
  offered as a meaningful chordal layout unless the renderer contract is expanded later.

## Data Flow

1. Teacher opens a chordal UMTO exercise in the dashboard edit page.
2. `ExerciseForm.__init__()` detects chordal UMTO.
3. `staff_distribution` remains visible and initializes from UMTO metadata.
4. Teacher saves the form.
5. `ExerciseForm.save()` writes the selected value to:
   - `instance.data["score"]["umto"]["metadata"]["staffDistribution"]`
   - `instance.data["staffDistribution"]`
6. Preview/student render reads the persisted value through the chordal UMTO conversion
   path and applies the selected staff layout.

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

Expected renderer work in `lab/static/js/src/components/music/exercise_sheet.js`:

- Extend `_convertChordalUMTOToProcessedScore()` so the existing dashboard tokens produce
  the staff layout described above.
- Keep the stored `meta.staffDistribution` value intact in the processed score metadata.
- Do not change voices-kind UMTO conversion behavior.

## Tests

Add focused tests in the dashboard/form test area:

- Chordal UMTO edit form exposes `staff_distribution` and initializes from
  `score.umto.metadata.staffDistribution`.
- Saving a chordal UMTO exercise with a new value writes both metadata and top-level
  mirror.
- SATB voices-kind chorale UMTO still hides `staff_distribution` and forces
  top-level `staffDistribution` to `"chorale"`.
- Chordal UMTO conversion routes `"LH"` to bass-only and `"RH"` to treble-only.
- Chordal UMTO conversion keeps `"grandStaff"` / keyboard-family values on grand-staff
  rendering.

No legacy-specific test is required because legacy behavior is not part of this change.

## Risks

- `umto_chorale` is a shared frontend type. The implementation must branch by
  `metadata.score_kind`, not by top-level type alone.
- `ExerciseForm.save()` currently writes top-level `staffDistribution` before
  score-kind-specific handlers run. The chordal handler must run after that generic write
  and overwrite metadata/mirror consistently.
- The frontend has historical token aliases (`LH`/`RH` versus lower-level
  `bass`/`treble` handling). The implementation must normalize behavior without
  changing persisted dashboard tokens.
- The later edit-page refactor (#4) should preserve this score-kind-specific boundary
  instead of folding chordal UMTO back into the SATB chorale branch.
