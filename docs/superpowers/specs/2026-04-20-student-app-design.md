# Student App Design

**Date:** 2026-04-20
**Scope:** Unit 1 pilot — pitch identification exercises, student-facing app

---

## Overview

A new student-facing Django app (`apps/student/`) that exposes Unit 1 (Pitch & Staff Notation) exercises with Khan Academy-style UX: auto-resume, skill-level mastery tracking, and no instructor chrome. The existing exercise engine (VexFlow, piano, grading JS) is reused unchanged. All existing models are reused unchanged.

Target audience: high school through graduate students. Piloting with one student (daughter) then college students.

---

## Goals

- Student never sees the dashboard or instructor tooling
- Clear unit/skill progress at a glance
- Auto-resume to lowest point of friction
- Skill mastery (not raw exercise count) drives progress %
- Unit 1 fully playable end-to-end: exercises created, tagged, linked to playlist

---

## Non-Goals (this spec)

- Unit 2+ (rhythm, meter) — deferred
- React/SPA rewrite — deferred
- Monetization / multi-tenant — deferred
- Instructor assignment flow — existing dashboard handles this
- Mobile-native — responsive CSS is sufficient for pilot

---

## Architecture

### New Django App: `apps/student/`

```
apps/student/
  __init__.py
  apps.py
  urls.py           # /s/ namespace
  views.py          # HomeView, UnitView, PlayerView
  progress.py       # unit progress aggregation logic
  templates/
    student/
      base.html     # minimal chrome: name, back link only
      home.html     # unit list + auto-resume card
      unit.html     # skill breakdown with mastery states
      player.html   # exercise player (clean wrapper)
  static/
    student/
      student.css   # clean, minimal styles
```

Registered in `settings.py` as `student`. Mounted at `/s/` in root `urls.py`.

### URL Structure

| URL | View | Purpose |
|-----|------|---------|
| `/s/` | `HomeView` | Unit list + auto-resume |
| `/s/units/<unit_num>/` | `UnitView` | Skill breakdown |
| `/s/units/<unit_num>/play/` | `PlayerView` | Exercise player |
| `/s/login/` | `StudentLoginView` (custom) | Student login → redirects to `/s/` |

### Reused (unchanged)

- `Exercise`, `Playlist`, `Course` models
- `StudentSkillMastery` model — drives mastery state per skill tag
- `PerformanceData` model — stores submission history
- Lab JS engine (`lab/static/js/src/`) — embedded in `player.html` via existing script includes
- `music_theory_taxonomy_with_branches.json` — source of unit/skill definitions

---

## Unit 1 Content

### Skills (from taxonomy)

Unit 1 "Pitch & Staff Notation" contains 4 mastery skills. Note Names is a single mastery tag with two content tracks (treble and bass), and each track now has two modes: identify and matching-playback. Progress math uses 4 as the denominator.

| Mastery skill | Tag | Voices / content | Exercise type |
|---------------|-----|-----------------|--------------|
| Note Names | `Note_Names` | soprano (treble) + bass voice (bass staff) — two playlists | pitch identification |
| Ledger Lines | `Ledger_Lines` | soprano | pitch identification |
| Clefs | `clefs` | soprano + bass | pitch identification |
| Enharmonics | `enharmonic` | soprano | pitch identification |

UnitView displays 4 skill rows. Note Names row links to treble playlist first; bass playlist is surfaced as a sub-track ("Also practice: Bass Staff") after treble mastery is reached.

### Exercise Creation

Unit 1 exercises are pitch identification exercises (`analysisType: note_name`). They do not yet exist in the DB and must be created as part of this work.

Each skill gets its own playlist (or two playlists for Note Names). All playlists are linked to a Unit 1 Course. Content generation matrix:

| Playlist | Tag | Voice arg | Clef |
|----------|-----|-----------|------|
| Unit 1 — Note Names (Treble) | `Note_Names` | `--voice soprano` | treble |
| Unit 1 — Note Names (Bass) | `Note_Names` | `--voice bass` | bass |
| Unit 1 — Note Names (Treble Play) | `Note_Names` + `enharmonic` path | `--voice soprano` | treble |
| Unit 1 — Note Names (Bass Play) | `Note_Names` + `enharmonic` path | `--voice bass` | bass |
| Unit 1 — Ledger Lines | `Ledger_Lines` | `--voice soprano` | treble |
| Unit 1 — Clefs (Treble) | `clefs` | `--voice soprano` | treble |
| Unit 1 — Clefs (Bass) | `clefs` | `--voice bass` | bass |
| Unit 1 — Enharmonics | `enharmonic` | `--voice soprano` | treble |

Operational cap defaults for Unit 1 generator:
- `--max-per-playlist 36` (recommended default)
- `--max-per-stage 12` (recommended default)
- hard ceiling guideline: 48 exercises per playlist

Neither `--skill-tags` nor `--playlist-name` exist in `import_chorale.py`. Both are new work. The creation process is:

```bash
# Step 1: import exercises (existing command — creates a Playlist automatically)
python manage.py import_chorale <file> --mode identify --analysis note_name --voice <voice>

# Step 2: tag exercises and link playlist to Unit 1 course
python manage.py tag_unit_exercises --playlist <playlist_id> --tags unit:1,<Tag> --course "Unit 1"
```

`tag_unit_exercises` is a new management command to be written as part of this work. It sets `skill_tags` on all exercises in the playlist and links the playlist to the Unit 1 course via `PlaylistCourseOrdered`.

### Note: `applySkillFilter` is non-blocking for Unit 1

`applySkillFilter` in `exercise_definition.js` skips filtering entirely for non-roman analysis types (line: `if ((analysisType || 'roman') !== 'roman') return problems;`). Since all Unit 1 exercises use `analysisType: note_name`, the broken generic path is never hit. No fix needed for this pilot. The CLAUDE.md blocker applies only to roman numeral exercises in other units.

---

## Data Model for Units

Units are not DB entities. A unit is represented as:

1. One **Playlist per content track** (6 total — see content matrix above), each tagged `skill_tags: ['unit:1', '<Tag>']`
2. A **Course** titled "Unit 1: Pitch & Staff Notation" grouping all 6 playlists
3. `StudentSkillMastery` records per student per skill tag (4 tags) — aggregated to compute unit % complete

Unit % = `(count of tags where level == 'mastered') / 4 * 100`

Unit number → skill tags mapping is derived from `music_theory_taxonomy_with_branches.json`.

---

## Views

### HomeView (`/s/`)

- Requires login (`LoginRequiredMixin`)
- Redirects instructors (staff users) to `/dashboard/`
- Loads all units from taxonomy JSON (initially Unit 1 only, rest locked)
- For each unit: computes % mastered from `StudentSkillMastery` for that unit's skill tags
- Determines "current unit" = first unit with mastery < 100%
- Determines "current skill" = first unmastered skill in current unit
- Context: `units`, `current_unit`, `resume_url`

### UnitView (`/s/units/<unit_num>/`)

- Loads skill list for the unit from taxonomy JSON
- For each skill: fetches `StudentSkillMastery` record for current user
- Maps mastery level → display state: `not_started`, `attempted`, `familiar`, `proficient`, `mastered`
- "Continue →" links to `PlayerView` for the first non-mastered skill
- "Practice" links to `PlayerView` for already-mastered skills

### PlayerView (`/s/units/<unit_num>/play/`)

- Accepts `?playlist=<playlist_id>` query param — explicit playlist ID, not tag (avoids ambiguity when multiple playlists share a tag e.g. Note Names Treble vs Bass)
- Loads the playlist by ID
- Renders `player.html` — embeds existing lab exercise JS
- No instructor chrome: no key selector, no display options, no screenshot, no MIDI toggle tabs
- Back link → `UnitView`
- Exercise position shown as "X of Y" and progress dots

---

## Student UX Flow

### First visit

1. Student logs in at `/s/login/`
2. Redirected to `/s/` — sees Unit 1 (active), Unit 2+ (locked)
3. Unit 1 shows "Start here →" — 0% mastery
4. Student clicks → `UnitView` — sees 4 mastery skills, all "Not started"
5. Clicks "Start" on first skill → `PlayerView`

### Returning visit

1. Student logs in → `/s/`
2. Auto-resume card: "Pick up where you left off — Unit 1 · Ledger Lines, 1 of 4 skills mastered"
3. One tap → `PlayerView` for that skill
4. Unit list below shows overall progress bar

### Exercise flow (pitch identification)

1. Staff shows a single note
2. Student clicks the note → popup appears with 5 answer options
3. Student selects an answer → instant feedback (green flash = correct, red = wrong + correct answer shown)
4. Auto-advance to next note
5. After last exercise in skill session: "Skill complete" screen with mastery level gained, button back to unit

---

## Player Chrome (what's removed vs. current lab)

**Removed:**
- Dashboard / Login / Play links in header
- Key signature selector
- Display Options menu
- Screenshot button
- MIDI toggle tabs (Piano / Keyboard / MIDI / Settings)
- Volume / Mute controls
- User badge with email

**Kept:**
- Staff / score (VexFlow, unchanged)
- Piano keyboard (existing engine, shown below staff)
- Exercise instruction text (above staff)
- Feedback display (correct/incorrect)
- Back link to unit page
- "X of Y" exercise counter
- Progress dots

---

## Progress & Mastery

Unit % complete (Unit 1) = `(count of {Note_Names, Ledger_Lines, clefs, enharmonic} where level == 'mastered') / 4 * 100`

For future units: `(mastered_skill_count / len(unit_skill_tags)) * 100` — denominator derived from taxonomy JSON at runtime.

Mastery state per skill comes from `StudentSkillMastery.level` (model constants: `LEVEL_NOT_STARTED`, `LEVEL_ATTEMPTED`, `LEVEL_FAMILIAR`, `LEVEL_PROFICIENT`, `LEVEL_MASTERED`):

| Level | Display | Color |
|-------|---------|-------|
| `not_started` (no record) | Empty circle | Gray |
| `attempted` | Half circle | Orange |
| `familiar` | Half circle | Orange |
| `proficient` | Half circle | Orange — "Keep practicing" |
| `mastered` | Checkmark | Green |

Mastery computation logic is unchanged (existing `mastery.py`).

---

## Auth & Roles

- Existing login at `/accounts/login/` redirects to `/dashboard/my-work/` — **not reused** for students
- New `StudentLoginView` in `apps/student/views.py`: same email+password form, but `success_url = '/s/'`; does not call existing `accounts.views.login`
- `HomeView`, `UnitView`, `PlayerView` all use `LoginRequiredMixin` with `login_url = '/s/login/'`
- Instructors (`is_staff=True`) hitting any `/s/` view → `HttpResponseRedirect('/dashboard/')`
- No new user model — pilot users created by admin via Django admin
- No self-registration for pilot

---

## Out of Scope Decisions

- **Naming / branding** — deferred; use "HarmonyLab" for pilot
- **Unit unlock logic** — Unit 2+ locked until Unit 1 reaches 100% mastery. Simple check in `HomeView`.
- **MIDI auto-detection** — existing engine handles this; no UI toggle needed in student player
- **Gamification** — no points/badges for pilot; mastery state is sufficient motivation signal

---

## Success Criteria for Pilot

1. Daughter can log in, navigate to Unit 1, complete pitch identification exercises, and see her mastery progress — without any confusion from instructor UI
2. College students can do the same from any device (deployed, responsive)
3. Mastery state persists across sessions
4. No regressions in existing dashboard or lab functionality
