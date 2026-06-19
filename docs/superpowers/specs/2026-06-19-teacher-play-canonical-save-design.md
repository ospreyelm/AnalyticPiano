# Teacher Play Canonical Save Design

**Date:** 2026-06-19  
**Status:** Implemented

### Implementation Note (2026-06-19)
- Canonical identity migration `0069_playlist_teacher_play_identity.py` adds fields and unique constraint.
- Shared authoring-oriented resolution service: `apps/exercises/services/canonical_playlist.py`.
- Endpoint routing integration: `lab/views.py` (composed exercises) and `apps/teacher/views_musicxml.py` (MusicXML import).
- Front-end single-unit/single-mode configuration form in `lab/static/js/src/components/ui/music_controls.js` and `lab/templates/play.html`.

## Goal

Make `/teacher/play/` a safe, fast authoring tool for creating curriculum
materials. Teachers should classify an exercise, not manage playlist structure.
The application chooses the correct destination automatically.

This contract applies to both exercises composed in `/teacher/play/` and
MusicXML imported there.

## Save Form

The primary form contains:

1. Exercise description.
2. Exactly one unit.
3. Exactly one interaction mode.
4. A read-only destination preview.
5. A Save button whose label includes the selected mode when useful.

There is no playlist picker, new-playlist name field, or destination override.

Additional skill tags and transposition controls remain under Advanced options.
MusicXML-only range and complexity controls remain available when a MusicXML
file is active.

Superusers see `Public` and `Official` checkboxes. Both default to checked but
remain editable. Non-superusers cannot request official content.

## Canonical Playlist Contract

Each save author has at most one manually authored exercise playlist for each
unit and interaction mode.

The stable display name is:

```text
Unit {N} — Exercises ({Mode})
```

Examples:

```text
Unit 11 — Exercises (Play)
Unit 11 — Exercises (Roman)
Unit 11 — Exercises (Figures)
```

The playlist name never incorporates an exercise description. A new exercise
description therefore does not create a new playlist.

Canonical identity consists of:

- save author;
- unit;
- interaction mode;
- the manually authored exercise namespace.

For an official save, the save author is the configured factory user. For a
non-official save, the save author is the requesting user. This keeps personal
and official material separate even when unit and mode match.

The implementation must not reuse Bach/corpus playlists or other playlist
families merely because their names end with the same mode.

## Destination Resolution

After one unit and one mode are selected, the interface shows:

```text
Will save to: Unit {N} — Exercises ({Mode})
```

On save, the backend independently resolves the destination:

1. Validate exactly one known `unit:N` tag.
2. Validate exactly one supported interaction mode.
3. Resolve the save author from the `Official` choice.
4. Find that author's canonical manually authored playlist for the unit and
   mode.
5. Reuse it when found.
6. Otherwise create it with the canonical name, unit tag, mode identity, and
   requested visibility/official metadata.
7. Append the new exercise in the next playlist order.

Resolution must be idempotent under repeated saves. Database lookup and
creation must be transaction-safe so concurrent saves do not produce duplicate
canonical playlists.

If a legacy playlist already has the exact canonical name, author, unit tag,
and mode, it may be adopted. Ambiguous or contradictory legacy rows must cause
a clear error rather than arbitrary reuse.

## Visibility and Official Status

`Public` controls the saved exercise and its canonical playlist.

- When creating a playlist, apply the requested public value.
- When reusing a playlist, a public save may promote it to public.
- A later private save must not make an existing public playlist private.

`Official` controls authorship and official status.

- Only superusers may submit `Official=true`.
- Official exercises and playlists are authored by the configured factory user.
- Official and personal canonical playlists are distinct destinations.
- Reusing an official playlist must not depend on the requesting superuser's
  personal ownership.

## Interaction Modes

The save form uses a single-select control, not checkboxes. Supported modes are
the modes already accepted by the authoring pipeline:

- Play
- Roman
- Figures
- Identify
- Harmonization

One save creates one exercise in one canonical playlist. Creating multiple
mode variants is performed as separate explicit saves, avoiding hidden fan-out
and making the destination unambiguous.

## Validation and Errors

The client disables Save and presents a direct inline message when:

- description is empty;
- no unit is selected;
- no mode is selected;
- transpositions are enabled without a key set;
- authoring metadata cannot be loaded.

The backend repeats all authoritative validation. It rejects:

- zero or multiple unit tags;
- zero or multiple modes;
- unknown units or unsupported modes;
- official saves from non-superusers;
- missing factory user for official saves;
- contradictory canonical playlist metadata;
- locked canonical playlists that cannot accept exercises.

No error path silently falls back to an arbitrary playlist or creates a
description-derived playlist.

## Shared Implementation Boundary

Canonical naming and destination resolution belong in one backend service used
by both:

- `lab.views.AddExerciseView`;
- `apps.teacher.views_musicxml.import_musicxml_save_view`.

The frontend may compute the same display label for immediate feedback, but the
backend service is authoritative. The two save paths must not carry separate
playlist-matching algorithms.

## Test Contract

Tests are written before implementation changes and cover:

1. Canonical name generation for every supported mode.
2. Exactly one unit and one mode are required.
3. First save creates the canonical playlist.
4. Later saves for the same author, unit, and mode reuse it.
5. Different descriptions do not create additional playlists.
6. Different modes create different playlists.
7. Different units create different playlists.
8. Personal and official saves resolve to different authors and playlists.
9. Superuser saves default to public and official in the UI.
10. Public reuse promotes visibility without later downgrading it.
11. MusicXML and composed saves resolve destinations identically.
12. Corpus playlists and contradictory legacy playlists are not reused.
13. The save form has no playlist picker or playlist-name input.
14. Concurrent or repeated resolution cannot create duplicate canonical
    playlists.

## Out of Scope

- Bulk generation workflows.
- Editing or reorganizing playlists after save.
- Migrating every historical manually authored playlist.
- Automatically splitting one save into several interaction modes.
- Allowing a destination override from `/teacher/play/`.
