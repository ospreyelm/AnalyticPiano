# MusicXML UMTO Router Design

## Status

Approved for implementation on 2026-06-07.

## Context

Spec A made chordal UMTO a first-class score kind. Spec B must not treat every
MusicXML upload as chordal: a stable multi-part source should remain a regular
voices-kind UMTO exercise, while homophonic, chord-on-staff, ragged, monophonic,
and legacy chord-bank material should use chordal UMTO.

The repository already has a voices-kind MusicXML path in
`apps/exercises/management/commands/import_musicxml.py`, but it routes every file
through one music21-to-CIR conversion. The repository also has
`exercises_2026-04-03.csv`, which contains legacy `data.chord` rows that are a
narrow, real-world test corpus for the chordal UMTO path.

## Goal

Add a backend representation router for imported music material:

- stable 2-, 3-, or 4-part MusicXML -> voices-kind UMTO;
- chord-on-staff, homophonic, ragged, or monophonic MusicXML -> chordal UMTO;
- legacy CSV `data.chord` rows -> chordal UMTO import/validation path.

## Non-Goals

- No silent rewrite of existing DB rows.
- No new frontend exercise type.
- No native chordal transposition UI beyond preserving source spelling in the
  chordal payload.
- No Workbench redesign in this slice; Workbench should later call the same
  backend router.

## Routing Rules

### Legacy CSV

Rows are parsed as CSV with a JSON `data` column. A row is importable when
`data.chord` is a non-empty list. The importer converts each row through the
Spec A chordal wrapper and can validate/dry-run without writing.

### MusicXML

The classifier returns a route plus evidence.

Use `voices` when:

- the parsed score has 2, 3, or 4 parts;
- each part has note/rest content;
- no part contains explicit chord events;
- part count is stable across measures enough for the existing voices-kind UMTO
  pipeline to preserve the source as independent lines.

Use `chordal` when:

- the parsed score has one part;
- any part contains explicit `music21.chord.Chord` events;
- the source has ragged or verticality-oriented material that should be stored
  as onset windows instead of forced into SATB voices.

## Chordal Conversion

Chordal MusicXML conversion groups sounding note/chord attacks by absolute
quarter-length offset. Each group becomes a UMTO `ChordEvent`:

- `offset`: absolute quarter-length from excerpt start;
- `duration`: shortest positive duration in the group;
- `visible`: MIDI pitches in source order;
- `hidden`: empty for Spec B imports;
- `spelling`: source pitch spellings for future transpose support.

The existing `build_chordal_umto_payload()` generates `score.measures`, so the
frontend timeline and analysis-window alignment stay on the Spec A W1 path.

## Acceptance Tests

1. A stable 4-part music21 score classifies as `voices`.
2. A stable 2-part music21 score classifies as `voices`.
3. A one-part score with chord events classifies as `chordal`.
4. A one-part monophonic score classifies as `chordal`.
5. Chordal conversion preserves offsets, durations, MIDI values, and spellings.
6. Legacy CSV parsing finds real `data.chord` rows and converts them to chordal
   UMTO without writing by default.
7. `import_musicxml` uses the classifier: voices route keeps the existing
   voices-kind factory path, chordal route uses `build_chordal_umto_payload`.

