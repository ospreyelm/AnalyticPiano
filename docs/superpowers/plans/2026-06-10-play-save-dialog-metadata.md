# Play Save Dialog — Exercise Metadata, Playlist Assignment, Save-as-Official

**Goal:** The `/teacher/play/` click-first editor saves a fully described exercise:
description, unit/skill tags, public flag, playlist assignment — and (creator-only)
directly into the factory library. Today `AddExerciseView` hardcodes
`description="Play view chordal exercise"`, `is_public=False`, no tags, no playlist.

**Scope:** Backend contract on `AddExerciseView` (lab/views.py) + one small
authoring-meta GET endpoint; frontend save dialog in
`lab/static/js/src/components/ui/music_controls.js` + `lab/templates/play.html`.
Builds on completed plans `2026-06-09-teacher-play-authoring-{backend,frontend}.md`.

**Roadmap context:** Phase 4 of the production roadmap
(`~/.claude/plans/have-old-dashboard-...md`), pulled forward because the editor is
the curriculum creator's factory-content authoring tool (curated units in the
Phase 1 factory manifest).

## Backend contract (Task 1 — Codex)

`POST /exercises/add/` accepts NEW OPTIONAL fields in the JSON `data` payload
(all optional → fully backward compatible; existing tests in
`lab/tests/test_add_exercise_view_db.py` must stay green unchanged):

- `description`: str, ≤60 chars (Exercise.description max). Default stays
  `"Play view chordal exercise"`.
- `skillTags`: list[str]. Sanitize: strings matching `^[A-Za-z0-9:_#/-]{1,40}$`,
  max 20. Tags starting `unit:` must reference a unit number present in the
  taxonomy (`TaxonomyReader`); invalid → 400 with JSON error body.
- `isPublic`: bool. Default false.
- `playlistId` OR `playlistName` (mutually exclusive; both → 400):
  - `playlistId`: append exercise to existing playlist. Must be
    `authored_by == request.user` (or factory user when `saveAsOfficial`) and
    not performed-locked; else 400 with reason.
  - `playlistName`: get_or_create playlist by (name, author), append at next
    `order` via ExercisePlaylistOrdered.
- `saveAsOfficial`: bool. Only honored when `request.user.is_superuser`;
  otherwise 403. Effect: exercise (and any created playlist) authored by the
  factory user (`settings.FACTORY_USER_EMAIL`), `is_public=True` forced.

Response gains: `"playlistId"`, `"playlistName"` when assignment happened.

Also:
- `GET /exercises/authoring-meta/` (login required) returns
  `{units: [{n, title}], playlists: [{id, name, locked}], isSuperuser: bool}`.
  Units from `TaxonomyReader`; playlists = user's own (+ factory's when
  superuser), annotated with performed-lock state.
- Remove `csrf_exempt` from `AddExerciseView`; add `ensure_csrf_cookie` to
  `PlayView.get` so the JS can send `X-CSRFToken` from the cookie.

## Frontend (Task 2 — Sonnet)

Replace the bare upload branch in `music_controls.js` (~line 566) with a save
dialog (markup in `play.html`): description input, unit dropdown, tag chips,
playlist select (existing) / name input (new), is_public checkbox,
save-as-official checkbox (rendered only when `isSuperuser`). Fetch
`/exercises/authoring-meta/` on dialog open. Send `X-CSRFToken` header.
Surface backend 400 reasons via `feedbackService` (new catalog entries:
`play.save.invalid_tags`, `play.save.playlist_locked`, `play.save.forbidden_official`).

## Feedback catalog & docs

- Add the three feedback ids to `lab/static/js/src/config/feedback_catalog.js`
  and rows to `docs/feedback_catalog.md`.
- Update `docs/exercise_types.md` only if behavior of saved types changes (it
  does not — metadata only).

## Tasks

- [x] Task 1: backend contract + authoring-meta endpoint + CSRF (Codex, TDD;
      new tests in `lab/tests/test_add_exercise_view_metadata_db.py`)
- [x] Task 2: save dialog frontend (Sonnet) + feedback catalog entries
- [x] Task 3: orchestrator review + full suite (20/20 lab AddExercise tests
      green; 12 full-suite failures verified pre-existing on master e2bb6573).
      Live-browser smoke deferred: the dev server at :8000 serves the main
      checkout, not this worktree — smoke after merge or by running runserver
      from the worktree.
