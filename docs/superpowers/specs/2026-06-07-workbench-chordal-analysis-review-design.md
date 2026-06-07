# Teacher Workbench Chordal Analysis Review Design

## Status

Approved for implementation on 2026-06-07.

## Context

The MusicXML UMTO router now stores one-part, explicit-chord, and other
vertical sources as chordal UMTO. Chordal imports already preserve the source
as `score.umto.chords[]`, but their `score.umto.analysis[]` is empty and the
Teacher Workbench blocks Roman numeral, figured-bass, analysis-match, and
pitch-identification projections for chordal imports.

Teachers need a review surface before those imported chordal sources become
student-facing analysis exercises. Analyzer output is useful, but it must be
editable and explicitly reviewed because MusicXML spelling, imported key
analysis, and vertical reductions can be musically ambiguous.

## Goal

When chordal MusicXML is imported:

- populate `score.umto.analysis[]` with analyzer-generated labels aligned to
  `score.umto.chords[]`;
- show teachers a Workbench review/editor per chord onset;
- persist teacher edits back into canonical UMTO;
- allow chordal Roman numeral, figured-bass, analysis-match, and
  pitch-identification projections only after the source analysis is reviewed;
- build those projections from chordal `chords[] + analysis[]`, not the
  voices-only projection factory.

## Analyzer Source Policy

HarmonyLab analyzer logic is the source of truth for student-facing labels.
music21 is a fallback and parsing helper, not the primary answer source.

### Figured Bass

Use `apps.exercises.utils.figured_bass.compute_figured_bass()` as canonical.
It already implements HarmonyLab's Kellner abbreviation behavior and the
9-vs-2 context hook used by Bach phrase imports.

For chordal MusicXML, the importer should build a per-offset next-pitch context
when enough sequential source material exists. If no context is available,
`compute_figured_bass()` still emits the deterministic no-context figure.

### Roman Numerals

Prefer `apps.exercises.utils.legacy_roman.legacy_roman_from_pitches()`, which
mirrors the browser analyzer's major/minor Roman lookup tables. The importer
uses the imported HarmonyLab key to choose tonic and mode.

If the HarmonyLab table returns no normalized label, fall back to
`music21.roman.romanNumeralFromChord()` and store that fallback label. The
review UI does not hide fallback labels; the review gate is what prevents them
from becoming student answer keys without teacher confirmation.

## UMTO Persistence

Analysis remains in the canonical top-level UMTO field:

```json
{
  "offset": 0.0,
  "content": {
    "roman_numeral": "I",
    "raw_roman_numeral": "I",
    "local_key": "jC_",
    "raw_figured_bass": "8/5/3",
    "figured_bass": "5/3"
  },
  "unit_tags": [],
  "is_target": true
}
```

The Exercise payload must keep these fields synchronized:

- `data["score"]["umto"]["analysis"]`
- `data["analysis"]`

Review state is stored in UMTO metadata as
`metadata.analysis_review_status`, with values:

- `generated` — analyzer output exists but has not been reviewed;
- `reviewed` — teacher saved the review editor;
- `none` — no analysis is available.

The preferred implementation is an explicit optional field on `Metadata`
because review state is stable product state.

## Import Flow

`import_musicxml` keeps the existing representation routing.

For chordal route:

1. Build `ChordEvent` dicts from MusicXML.
2. Build analyzer-generated `AnalysisSlice` dicts at matching offsets.
3. Save the chordal UMTO payload with `analysis_review_status="generated"`
   when at least one slice has a label, otherwise `"none"`.

Voices-kind imports are unchanged.

## Workbench Review API

Add two authenticated Workbench endpoints.

### Fetch Review

`GET /dashboard/api/workbench/chordal-analysis/<exercise_id>/`

Requirements:

- exercise must belong to the current user;
- exercise must be UMTO and `score_kind="chordal"`;
- response pairs each chord event with the analysis slice at the same offset;
- includes review status.

Response shape:

```json
{
  "exerciseId": "EA123",
  "description": "Chordal upload",
  "scoreKind": "chordal",
  "reviewStatus": "generated",
  "rows": [
    {
      "offset": 0.0,
      "duration": 1.0,
      "visible": [60, 64, 67],
      "hidden": [],
      "spelling": ["C4", "E4", "G4"],
      "content": {
        "roman_numeral": "I",
        "raw_roman_numeral": "I",
        "local_key": "jC_",
        "raw_figured_bass": "8/5/3",
        "figured_bass": "5/3"
      }
    }
  ]
}
```

### Save Review

`POST /dashboard/api/workbench/chordal-analysis/<exercise_id>/`

Payload:

```json
{
  "rows": [
    {
      "offset": 0.0,
      "content": {
        "roman_numeral": "I",
        "raw_roman_numeral": "I",
        "local_key": "jC_",
        "raw_figured_bass": "8/5/3",
        "figured_bass": "5/3"
      }
    }
  ]
}
```

Validation:

- offsets must match existing chord offsets;
- each row is validated through `AnalysisSlice`;
- unknown content keys are rejected by Pydantic or dropped only if existing
  schema behavior already drops them consistently;
- save marks `analysis_review_status="reviewed"`.

## Workbench UI

Keep the current single-page Workbench structure. Add a compact review action
for chordal imports:

- recent imports display a review status badge;
- chordal rows expose a "Review" button;
- clicking opens an inline editor panel or modal with one row per chord onset;
- teachers can edit Roman numeral, figured bass, raw figured bass, and local
  key;
- saving refreshes recent imports and enables reviewed chordal projections.

This is an operational editor, not a redesign. The table must be readable and
responsive enough for existing Workbench use, but no broader dashboard layout
change is part of this project.

## Chordal Projection Rules

Exact Match:

- allowed for chordal imports regardless of review status;
- clones chordal UMTO as playback, same as the current behavior.

Roman numeral:

- requires every selected chordal source to be reviewed;
- clones chordal UMTO;
- sets mode to `IDENTIFICATION`;
- sets `analysisType="roman"`;
- uses reviewed `analysis[].content.roman_numeral` as the student-facing answer
  source.

Figured bass:

- requires review;
- clones chordal UMTO;
- sets mode to `IDENTIFICATION`;
- sets `analysisType="figured_bass"`;
- uses reviewed `analysis[].content.figured_bass` as the answer source.

Analysis match:

- requires review;
- clones chordal UMTO;
- sets mode to `ANALYSIS_MATCH`;
- keeps chordal `chords[]` and reviewed analysis labels;
- hides or deemphasizes notation only through existing display flags if those
  flags already exist.

Pitch identification:

- requires review;
- clones chordal UMTO;
- sets mode to `IDENTIFICATION`;
- sets `analysisType="note_name"` unless the API later accepts a more specific
  pitch-analysis type;
- derives pitch choices from `chords[].spelling` when present and MIDI fallback
  otherwise.

Mixed selections:

- if any selected source is chordal and any selected source is voices-kind, the
  API rejects the request with a clear error. Mixing projection factories in one
  request would make partial failure and response semantics ambiguous.

## Non-Goals

- No new student runtime engine.
- No bulk auto-review.
- No source DB migration for existing chordal imports; they can be re-saved
  through the editor or handled by a future backfill command.
- No frontend port of the analyzer.
- No attempt to solve non-chord-tone Roman analysis automatically; teacher
  review is the control point.

## Acceptance Tests

1. Chordal MusicXML import populates `analysis[]` with HarmonyLab figured bass.
2. Chordal MusicXML import prefers HarmonyLab Roman table labels over music21.
3. Chordal MusicXML import falls back to music21 Roman labels when HarmonyLab
   returns no label.
4. Recent Workbench imports expose `analysisReviewStatus`.
5. Review fetch returns chord rows paired with analysis content.
6. Review save validates offsets, persists analysis in both UMTO and top-level
   payload fields, and marks the source reviewed.
7. Chordal Roman/figured-bass/analysis-match/pitch-identification projection
   rejects unreviewed sources.
8. Reviewed chordal Roman projection creates a chordal UMTO identification
   exercise without calling the voices-only factory.
9. Mixed voices/chordal projection requests are rejected.
10. Exact Match chordal projection remains allowed without review.
