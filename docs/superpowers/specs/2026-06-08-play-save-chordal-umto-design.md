# Play View Save as Chordal UMTO — Design Spec

Date: 2026-06-08

Status: Approved design. Implementation plan pending.

---

## Problem

The legacy play view lets a teacher pedal-record a chord sequence and click "Save as
exercise." That POST still hits `lab.views.AddExerciseView`, which creates a raw
`Exercise()` from the submitted legacy `data.chord[]` payload.

New Exercise rows must be UMTO. Raw legacy exercise creation is blocked by
`Exercise.clean()` / `Exercise.save()` and is no longer an acceptable authoring path.
The play view save flow must persist the recorded chord sequence as chordal UMTO.

## Goal

Keep the play view authoring workflow zero-friction while changing the backend save path
to create a valid chordal UMTO exercise.

When a logged-in teacher uploads play-view JSON containing `chord[]`, the server should
save a private chordal UMTO exercise and return the new exercise id exactly as the
frontend already expects.

## Scope

In scope:

- Convert the posted play-view chord payload into `score.umto.metadata.score_kind =
  "chordal"` using the existing chordal UMTO data model.
- Persist new rows through a UMTO factory/helper, not direct `Exercise(data=...)`.
- Keep the existing `/exercises/add/` POST endpoint and JSON response shape
  `{ "id": "<exercise id>" }`.
- Preserve the chord sequence order and each chord's `visible` / `hidden` pitches.
- Preserve `staffDistribution` into chordal UMTO metadata and the top-level payload
  mirror.
- Use generated metadata so the current UI does not need a title/description prompt.
- Return clear 400 responses for malformed, empty, or non-chord payloads.
- Add backend tests for the save endpoint and helper behavior.

Out of scope:

- New play-view prompt UI.
- Legacy row creation.
- Migration of existing legacy chord rows.
- Identification / Roman / figured-bass save modes from the play view.
- Analytics, playlists, or auto-publication.
- Broader legacy view refactoring.

## Decisions

### Zero-Friction Metadata

The save flow should not prompt for title, tags, or description in this issue. New saved
play-view exercises use:

- `description`: `"Play view chordal exercise"`
- `source` / `introText`: `"Play the saved chord progression."`
- `mode`: `InteractionMode.PLAYBACK`
- `skill_tags`: `[]`
- `complexity`: `1`
- `is_public`: `False`

This keeps the original "author exercises on the fly" workflow intact and leaves richer
authoring metadata for a later dashboard/workbench enhancement.

### Backend Owns Conversion

The browser may keep posting the current legacy-shaped JSON. The conversion belongs on
the server because the server owns the canonical persistence contract and can validate
UMTO before writing a row.

The endpoint should reject unsupported payloads instead of silently saving legacy rows.

### New Save Helper

Add a small factory helper rather than teaching `AddExerciseView` all chordal UMTO
details directly.

Recommended helper:

`save_chordal_umto_exercise(description, author, chords, key, meter, clef,
staff_distribution, source, skill_tags, complexity, is_public)`

The helper should:

1. Normalize incoming legacy chord records into chordal `ChordEvent` dicts.
2. Call `build_chordal_umto_payload(...)`.
3. Copy `staffDistribution` into `payload["score"]["umto"]["metadata"]` and the
   top-level payload mirror.
4. Validate `UMTO.model_validate(payload["score"]["umto"])`.
5. Save an `Exercise` with UMTO data.
6. Backfill `metadata.exercise_id` and top-level `exerciseId` after the database id is
   assigned.

The existing `legacy_chord_row_to_chordal_payload()` remains a read-only wrapper for
serving old rows. It should not become the primary persistence helper unless it is
refactored to clearly separate "build payload" from "save new Exercise."

### Chord Sequence Semantics

The play view currently posts `chord[]` records like:

```json
{
  "rhythmValue": "w",
  "visible": [60, 64, 67],
  "hidden": [],
  "unison_idx": null
}
```

For this issue, each saved chord becomes one chordal UMTO event with:

- `offset`: sequential quarter-length offsets `0.0`, `1.0`, `2.0`, ...
- `duration`: `1.0`
- `visible`: the posted visible MIDI pitches, preserving order
- `hidden`: the posted hidden MIDI pitches, preserving order

This matches the existing runtime legacy wrapper behavior and avoids changing playback
or rendered spacing as part of the save-path fix.

### Endpoint Contract

`AddExerciseView.post()` should:

1. Require an authenticated user.
2. Parse `request.POST["data"]` as JSON.
3. Require a non-empty `chord` array.
4. Build and save a chordal UMTO exercise through the helper.
5. Return `201` with `{ "id": exercise.id }`.

Malformed JSON, `"null"`, missing `chord`, empty `chord`, or chords with no pitches
should return `400`. The endpoint should not fall back to direct raw `Exercise()` saves.

## Data Flow

1. Teacher records chords in the play view.
2. `PlaySheetComponent.dataForSave()` writes the current legacy-shaped JSON to
   `sessionStorage.current_state`.
3. `MusicControlsComponent.onClickSaveJSON("upload")` posts that JSON to
   `/exercises/add/`.
4. `AddExerciseView` parses and validates the JSON.
5. `save_chordal_umto_exercise()` persists a chordal UMTO row.
6. The existing AJAX success handler receives `{ id }` and opens the dashboard edit page.

## Tests

Add focused Django tests for:

- Posting a valid play-view chord payload creates an `Exercise` whose data is UMTO and
  whose `score.umto.metadata.score_kind` is `"chordal"`.
- The saved UMTO chord events preserve visible/hidden MIDI arrays and order.
- The saved metadata and top-level mirror preserve `staffDistribution`.
- The saved row is private, authored by the logged-in user, and has generated
  zero-friction metadata.
- Anonymous POST returns `400`.
- `"null"`, malformed JSON, missing `chord`, empty `chord`, and pitchless chord payloads
  return `400`.
- No test path relies on `HARMONYLAB_ALLOW_LEGACY_EXERCISE`.

Run nearby chordal UMTO tests to confirm the existing read-only wrapper still works.

## Risks

- The endpoint name is legacy, but the persistence behavior must now be canonical UMTO.
  Tests should assert `isUMTO` and `score_kind`, not just a successful response.
- The frontend still posts legacy-shaped JSON. Changing the frontend payload format is
  unnecessary for this issue and would increase risk.
- `Exercise.clean()` only blocks new legacy rows. A direct save may appear to work in
  some update paths; tests must cover creation through `/exercises/add/`.
- Future richer authoring metadata should build on the dashboard edit page opened after
  save, not block this backend conversion.
