# Unit 2: Rhythm & Meter — Curriculum Plan

_Branch: Core Sequence, Tier 1 — Fundamentals_

**Taxonomy entry:** Simple & compound meter, ties, dots
**Tags:** `rhythm`, `meter_simple`, `meter_compound`

---

## Status: Partially implemented

Two exercise types are live with generation commands. A third lane (rhythm dictation / MIDI clapping) is not yet buildable with existing exercise types.

---

## What exists

### Lane 1 — Add Barlines

Student sees a measure of noteheads with a time signature but no barlines, and must place them correctly.

**Command:**
```
python manage.py generate_unit2_barline_exercises --author <email> --source corpus --grouped --public
```

**Sources:**
- `--source corpus` — derived from Bach chorale corpus via `apps/exercises/utils/corpus_filter.py`
- `--source manual` — generates a fixed sequence of quarter-note beats for a given meter (seed/testing use)

**8 internal level playlists** (not student-facing, tagged `unit:2_L{n}`):

| Level | Meters | Notes |
|---|---|---|
| 1–3 | Simple (2/4, 3/4, 4/4) | Increasing rhythmic variety |
| 5–6 | Compound (6/8, 9/8, 12/8) | Dotted-quarter beats |
| 7–8 | Half-note meters (2/2, 3/2) | Cut time and triple |

**3 student-facing grouped playlists** (built with `--grouped` after corpus run):

| Playlist name | Levels | Tags |
|---|---|---|
| `Unit 2 — Add Barlines: Simple Meters` | 1, 2, 3 | `unit:2`, `unit:2_rhythm`, `unit:2_meter_simple` |
| `Unit 2 — Add Barlines: Compound Meters` | 5, 6 | `unit:2`, `unit:2_rhythm`, `unit:2_meter_compound` |
| `Unit 2 — Add Barlines: Half-note Meters` | 7, 8 | `unit:2`, `unit:2_rhythm`, `unit:2_meter_half_note` |

All grouped playlists are adaptive (`is_adaptive=True`). Level playlists are internal source pools.

**Filters applied at generation time:**
- Syncopation that crosses a barline boundary → skipped (position ambiguous)
- Notes that VexFlow cannot beam cleanly → skipped

**Key files:**
- `apps/exercises/utils/barline_exercise_builder.py` — builds exercise payload
- `apps/exercises/utils/corpus_filter.py` — iterates Bach phrases by level

---

### Lane 2 — Symbolic Meter Questions

Student sees a time signature and must identify its properties from multiple-choice menus (beat grouping, division type, beat value, full meter name).

**Command:**
```
python manage.py generate_unit2_meter_exercises --author <email> --public
```

**Source:** Curated manifest at `apps/exercises/data/unit2_symbolic_drill_manifest.json`

**Playlist:** `Unit 2 — Symbolic Meter Questions`
**Tags:** `unit:2`, `unit:2_rhythm`, `unit:2_meter_simple`, `unit:2_meter_compound`

**Question types per problem** (from `apps/exercises/symbolic_meter_questions.py`):
- Beat grouping: duple / triple / quadruple
- Division type: simple / compound
- Beat value: note name (quarter, dotted quarter, half, etc.)
- Full meter name: e.g. "compound triple"

**Reference data** (`apps/exercises/data/unit2_meter_reference.json`) — generated once by:
```
python manage.py generate_unit2_meter_reference
```
This file is pre-generated and committed; re-run only if meter label logic changes.

---

## Rebuild sequence

Run these in order after a fresh database load:

```bash
# 1. Generate corpus-level playlists (levels 1–8)
python manage.py generate_unit2_barline_exercises --author <email> --source corpus --public

# 2. Assemble student-facing grouped playlists from level pools
python manage.py generate_unit2_barline_exercises --author <email> --grouped --public

# 3. Generate symbolic meter questions from manifest
python manage.py generate_unit2_meter_exercises --author <email> --public
```

---

## Course structure

```
Course: "Unit 2: Rhythm & Meter"
  Playlist: "Unit 2 — Add Barlines: Simple Meters"      ← adaptive
  Playlist: "Unit 2 — Add Barlines: Compound Meters"    ← adaptive
  Playlist: "Unit 2 — Add Barlines: Half-note Meters"   ← adaptive
  Playlist: "Unit 2 — Symbolic Meter Questions"
```

---

## What is NOT yet built

| Concept | Gap | Notes |
|---|---|---|
| Rhythm performance (MIDI/clap) | No exercise type for rhythm input | Would require a new input mode; out of scope |
| Minor scale meter exposure | Not applicable | Meter is mode-independent |
| Ties & dots drill | Not yet implemented | Could be hand-authored as `identification` exercises; e.g. "which note value equals a dotted quarter?" |
| Subdivision dictation | No exercise type | Out of scope |

Taxonomy also lists **ties** and **dots** as Unit 2 features. Those are currently covered only within the barline exercises (incidentally). A dedicated identification-type drill could be hand-authored if needed.

---

## Reference

- [Exercise types](exercise_types.md) — exercise type reference
- `apps/exercises/management/commands/generate_unit2_barline_exercises.py`
- `apps/exercises/management/commands/generate_unit2_meter_exercises.py`
- `apps/exercises/utils/barline_exercise_builder.py`
- `apps/exercises/symbolic_meter_questions.py`
