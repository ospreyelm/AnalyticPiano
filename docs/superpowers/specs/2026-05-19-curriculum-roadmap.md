# HarmonyLab Curriculum Roadmap

**Date:** 2026-05-19
**Author:** Avner Dorman
**Goal:** Structured path from current state to fall 2026 counterpoint class + long-term platform vision.

See also: [Platform infrastructure roadmap](2026-04-29-platform-roadmap.md)

---

## Use Cases (Priority Order)

1. **Avner's daughter** — early units, now
2. **Fall 2026 counterpoint class** — partimento/clausulae, hard deadline ~Sept 2026
3. **Colleague's Theory III** — chromatic harmony (units 9–18 range), fall 2026
4. **Wide availability** — future

---

## Workstream Overview

| # | Workstream | Deadline | Status |
|---|-----------|----------|--------|
| 1 | Content: early units (1–8) | Now | Partly done; units 1–3 generated |
| 2 | Partimento/clausulae exercises | Sept 2026 | Not started |
| 3 | Teacher course builder | Sept 2026 | Not started |
| 4 | Chorale analysis browse mode | Fall 2026 | Not started |
| 5 | Voice-leading quality checks | 2027 | Not started |

---

## Workstream 1 — Early Units Content (Now)

**Goal:** Avner's daughter has a full early curriculum.

### What exists
- Unit 1: note names, play from name — done
- Unit 2: meter, barlines — done
- Unit 3: key signatures, major scales — done (just generated on prod)

### What to generate next
- **Unit 3 remaining:** minor scales, scale degrees, pitch class exercises (commands may already exist — check `generate_unit3_*`)
- **Units 4–8:** intervals, triads, basic diatonic harmony — need content + generation commands

### Approach
Run existing admin generators where commands exist. Write new `generate_unit4_*` etc. commands following the established pattern. Each unit needs:
1. Exercise generation command
2. Playlist creation (leveled where appropriate)
3. Taxonomy entry in `music_theory_taxonomy_with_branches.json`

---

## Workstream 2 — Partimento / Clausulae (Sept 2026)

**Goal:** Fall counterpoint class can practice clausulae patterns via MIDI keyboard.

### Pedagogy
- Clausulae = short cadential formulas (2–8 bars), 2–4 voices
- Student exercises: play full realization (all voices, chorale mode) OR play upper voices against locked bass + figures
- Grading: figures-based (any correct realization accepted), NOT against stored soprano/alto/tenor
- Figures either present in MusicXML `<figured-bass>` elements, or derived from intervals

### Two exercise modes
**Mode A — Full playback:** Full realization visible, student plays all voices. Existing chorale mode. No new code needed.

**Mode B — Bass locked:** Bass shown + figures shown, student plays upper voices as chords. Graded against figures via existing `harmonizationMatch` / `figuredBassMatch` logic.

### Source files
Avner's website has MusicXML files for clausulae exercises. Files include:
- Full realizations (2, 3, or 4 parts)
- Figured bass in MusicXML elements (or derivable)
- Bass in lowest part always

### What to build
1. **`import_partimento` management command** — parses MusicXML, extracts bass + figures + upper voices, creates UMTO exercise in appropriate mode
2. **Bass-locked UI flag** — in harmonization/chorale player, grey out bass staff, mark it as "given"
3. **Admin generator button** — "Import Partimento" section in exercise operations UI

### What NOT to build yet
- Voice-leading quality checks (parallels, LT doubling, spacing) — deferred to Workstream 5
- Written notation input — MIDI only for fall

### Open questions
- Does Mode B map cleanly onto existing harmonization exercise type, or need a new UMTO mode?
- How are clausulae grouped into playlists? By cadence type (clausula vera, tenorizans, basizans)? By number of voices?

---

## Workstream 3 — Teacher Course Builder (Sept 2026)

**Goal:** Teachers (Avner, colleagues) can assign playlists to students and track progress without touching the admin UI.

### Minimum viable for fall
- Teacher creates a Course, adds ordered playlists from existing library
- Students enroll in a Course, see only that course's content
- Teacher sees per-student progress (which playlists started/completed, last score)

### What exists
- `PlaylistCourseOrdered` model and `Course` model exist
- Student progress tracking exists (PerformanceData, IdentificationAttempt)
- Student unit view shows playlists

### What to build
- Teacher-facing course editor (HTMX, follows platform roadmap Phase 3 pattern)
- Student enrollment flow
- Teacher progress dashboard (table: student × playlist → completion %)

### Deferred
- Prebuilt course templates
- Automated adaptive sequencing within a course

---

## Workstream 4 — Chorale Analysis Browse Mode (Fall 2026)

**Goal:** Students open any Bach chorale, see RN or figured bass overlay, play along at their own pace.

### What exists
- Chorales in DB with RN and FB analysis computed
- Chorale playback mode fully working
- Analysis overlay rendering in VexFlow

### What to build
- "Browse chorales" view — searchable/filterable list of all chorales in DB
- Mode selector: play-along vs analysis-only (no grading)
- Analysis overlay toggle: Roman numerals / figured bass / both / none

---

## Workstream 5 — Voice-Leading Quality Checks (2027)

**Goal:** Grader detects and flags parallel fifths/octaves, doubled leading tone, poor spacing.

### Scope
- Applies to partimento Mode B and harmonization exercises
- Non-blocking feedback (shows after chord played, doesn't prevent advancement)
- Configurable per exercise (some exercises may allow parallel motion)

### Deferred because
- Not needed for fall class
- Requires defining rule set, edge cases, pedagogical calibration
- Significant implementation complexity

---

## Immediate Next Actions

1. **Check what unit 3 content is still missing on prod** — minor scales, scale degrees, pitch class
2. **Audit units 4–8** — does taxonomy define them? Do generation commands exist?
3. **Start Workstream 2 spec** — `import_partimento` command design, Mode B UI
4. **Start Workstream 3 spec** — minimal teacher course builder for fall
