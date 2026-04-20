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
| `/s/login/` | Django `LoginView` with student template | Student login |

### Reused (unchanged)

- `Exercise`, `Playlist`, `Course` models
- `StudentSkillMastery` model — drives mastery state per skill tag
- `PerformanceData` model — stores submission history
- Lab JS engine (`lab/static/js/src/`) — embedded in `player.html` via existing script includes
- `music_theory_taxonomy_with_branches.json` — source of unit/skill definitions

---

## Unit 1 Content

### Skills (from taxonomy)

Unit 1 "Pitch & Staff Notation" contains 5 skills, each mapped to a skill tag:

| Skill | Tag | Exercise type |
|-------|-----|--------------|
| Note Names — Treble Staff | `Note_Names` | pitch identification |
| Note Names — Bass Staff | `Note_Names` | pitch identification |
| Ledger Lines | `Ledger_Lines` | pitch identification |
| Clefs | `clefs` | pitch identification |
| Enharmonics | `enharmonic` | pitch identification |

### Exercise Creation

Unit 1 exercises are pitch identification exercises (`analysisType: note_name`). They do not yet exist in the DB and must be created as part of this work.

Creation path: `python manage.py import_chorale` with `--mode identify --analysis note_name --voice soprano` for single-voice pitch ID exercises, tagged with the relevant skill tags.

Each skill gets its own playlist. All 5 playlists are linked to a Unit 1 course (or a single Unit 1 playlist with skill-tagged exercises — see Data Model section).

### Blocker: `applySkillFilter`

The existing `applySkillFilter` generic path in `exercise_definition.js` is broken for most units (documented in CLAUDE.md). Unit 1 skill tags (`Note_Names`, `Ledger_Lines`, `clefs`, `enharmonic`) must be added to the `UNIT_ALLOWED_ANSWERS` map before exercise filtering will work. **Fix this before creating exercises.**

---

## Data Model for Units

Units are not DB entities. A unit is represented as:

1. One **Playlist per skill** (e.g. "Unit 1 — Note Names Treble"), tagged `skill_tags: ['unit:1', 'Note_Names']`
2. A **Course** titled "Unit 1: Pitch & Staff Notation" grouping all 5 skill playlists
3. `StudentSkillMastery` records per student per skill tag — aggregated to compute unit % complete

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

- Accepts `?skill=<tag>` query param to select which skill's playlist to load
- Loads the playlist for that skill
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
4. Student clicks → `UnitView` — sees 5 skills, all "Not started"
5. Clicks "Start" on first skill → `PlayerView`

### Returning visit

1. Student logs in → `/s/`
2. Auto-resume card: "Pick up where you left off — Unit 1 · Ledger Lines, 4 of 10 skills practiced"
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

Unit % complete = `(mastered_skills / total_unit_skills) * 100`

Mastery state per skill comes from `StudentSkillMastery.level`:
- `not_started` → empty circle, gray
- `attempted` / `familiar` → half circle, orange (shown as "Proficient — keep practicing")
- `proficient` → half circle, orange
- `mastered` → checkmark, green

Mastery computation logic is unchanged (existing `mastery.py`).

---

## Auth & Roles

- Student login: `/s/login/` — standard Django auth, student template
- Instructors (Django `is_staff=True`) hitting `/s/` → redirect to `/dashboard/`
- No new user model needed for pilot — distinguish by `is_staff` flag
- Students are created by admin (you) — no self-registration for pilot

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
