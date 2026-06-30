# HarmonyLab Feature Status

_Last updated: 2026-04-14_

**Purpose:** Authoritative reference for AI assistants. Read this before implementing anything — to avoid rebuilding what already exists or revisiting what was abandoned.

---

## Feature Status

| Feature | Status | Notes |
|---|---|---|
| `matching` / `analytical` / `analytical_pcs` exercise types | Done | Core original types, stable |
| `figured_bass` / `figured_bass_pcs` exercise types | Done | Core original types, stable |
| `chorale` play exercise | Done | MIDI play through Bach chorale score, onset windows. See `CLAUDE.md` |
| `identification` exercise (click-to-label, static chords) | Done | 3 feedback modes: practice / submit / test. Paging not yet on master — see below |
| `chorale_identification` — roman_numeral, figured_bass | Done | Paging: 4/page, slide animation, colors preserved on back-navigation |
| `chorale_identification` — interval_specific, interval_generic | Done | Tonal.js authoritative source, `analyze.js` cross-check, `compoundIntervals` flag |
| Identification paging for `identification` type | **Not yet on master** | Implemented on `feature/music21_builder` — needs merge into master |
| Smart playlist transposition | Done | Picks shorter interval direction, tritone prefers down. `apps/exercises/utils/transpose.py` |
| Recurring assignments | Done | Per-period progress tracking, student My Work view, gradebook columns |
| Group join codes | Done | |
| Student "My Work" view | Done | Default post-login for students |
| Public content library `/library/` | Done | Filter by type and tag |
| Course clone | Done | Deep-clone; exercises referenced not duplicated |
| Content tagging | Done | `tags` on Exercise and Playlist; wired to library filter |
| Teacher gradebook with CSV export | Done | On-time / tardy / late status |
| Due date UI | Done | Per-playlist date picker; shown in gradebook and student view |
| Roman numeral experimental mode | Done | Abbreviated figures, secondary-dominant split layout |
| MusicXML admin import | Done | Accessible via Django admin only |
| Curriculum generation (programmatic) | **Abandoned** | `voicing.py`, `templates.py`, `music21_builder.py` all tried and produced unusable output. `curriculum-generation` branch abandoned. Do not revisit. |
| Exercise audit view | Planned | 2.19 — priority before more content creation |
| Streamlined exercise creation flow | Planned | 2.20 — reduce 3 pages to 1 |
| MusicXML import dashboard UI | Planned | 2.13 — currently admin-only |
| Visual feedback for wrong chorale notes (red) | Planned | See `docs/chorale_future_improvements.md` Feature 2 |
| Chorale mode variations (play-soprano, play-bass, etc.) | Planned | See `docs/chorale_future_improvements.md` Feature 4 |
| "Explain this" button | Planned | 2.13 in plan.md |
| LTI integration (Moodle) | Planned | Requirements TBD May 2026 |
| Course scheduling wizard | Planned | Depends on content (2.12) and recurring (2.14) |
| Counterpoint checking | Planned | Parallel fifths, octaves, doubled leading tones |
| Curriculum assembly tool | Planned | Bird's-eye course construction UI |

---

## Don't Get This Wrong

Common AI mistakes and the correct facts:

| Wrong assumption | Correct fact |
|---|---|
| `identification` and `chorale_identification` use different graders | Both use `IdentificationGrader` — same grader, `chorale_identification` adds `pageOffset` support |
| Paging only works for `chorale_identification` | `chorale_identification` has paging on master. `identification` paging exists on `feature/music21_builder` but not yet merged |
| `chorale` and `chorale_identification` are the same type | They are not — `chorale` is MIDI play, `chorale_identification` is click-to-label identification |
| Curriculum generation was deferred | It was **abandoned** after multiple failed attempts — do not revisit or build on it |
| The `key` field only affects display | It controls enharmonic note spelling — wrong key = wrong accidentals on staff (G## instead of A) |
| Transposition creates duplicate Exercise rows | No — transposed copies are virtual, generated on the fly with IDs like `EA00DD+16` |
| `identification` chord entries look like `matching` entries | Similar, but each chord also requires `answer` and `choices` keys |
| `chorale_identification` uses a `chord` array | No — it uses a `score` key with CIR JSON, same structure as `chorale` |
| Adding a new JS module only requires creating the file | Must also add a `paths` entry in `harmony/settings/requirejs.py` or the module 404s silently |
| `exercise_types.md` is up to date on identification paging | As of 2026-04-14 it says "not yet" for `identification` paging — that note is stale |
| Adaptive playlists support review / redo by editing the URL `exercise_num` | They do not — `exercise_num` is server-derived (PR #190); dedicated review mode and exercise redo for adaptive/dynamic playlists are **deferred** (see `docs/adaptive_learning.md` §3). Re-trusting the URL or relaxing `is_submitted` pinning reintroduces the re-serve loop |

---

## Key Files Quick Reference

| File | Purpose |
|---|---|
| `lab/static/js/src/models/exercise_definition.js` | Parses exercise JSON; `isChorale()`, `isIdentification()`, type checks |
| `lab/static/js/src/models/exercise_context.js` | Runtime state — current chord/window, paging, score tracking |
| `lab/static/js/src/components/music/exercise_sheet.js` | VexFlow rendering, label slots, page-turn animation |
| `lab/static/js/src/models/exercise_grader.js` | Grading for matching / analytical / figured_bass |
| `lab/static/js/src/models/chorale_grader.js` | Grading for `chorale` — onset window system |
| `lab/static/js/src/models/identification_grader.js` | Grading for `identification` and `chorale_identification` |
| `lab/static/js/src/components/music/score_timeline.js` | Builds flat timeline from CIR JSON score |
| `apps/exercises/management/commands/import_chorale.py` | Django command to import Bach chorale JSON as exercise |
| `apps/exercises/utils/transpose.py` | Playlist transposition — smart direction logic |
| `harmony/settings/requirejs.py` | RequireJS path registry — update when adding/moving JS files |
