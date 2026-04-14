---
name: AI-Optimized Documentation System
description: Design for making CLAUDE.md and docs/ serve as reliable AI context — preventing "rebuild what exists" errors and reducing re-explanation overhead at session start
type: project
date: 2026-04-14
---

# AI-Optimized Documentation System

## Problem

When starting a new conversation, Claude:
1. Has no knowledge of what features exist — wastes time re-explaining
2. Makes confident wrong assumptions about exercise types — leads to rebuilding things that already exist
3. Doesn't know which features are done vs. planned — suggests implementing completed work

The exercise type confusion is the highest-risk failure: `identification`, `chorale_identification`, `chorale`, `matching` all look related but have fundamentally different graders, data shapes, and interaction models.

## What Already Exists (Don't Rebuild)

| File | Status | Quality |
|---|---|---|
| `docs/architecture.md` | On master | Strong — data model, request flow, key encoding |
| `docs/exercise_types.md` | On master | Strong — all 8 types, graders, paging, analysisType variants |
| `docs/README.md` | On master | Good index |
| `CLAUDE.md` | On master | Deep but chorale-focused and stale |
| `docs/plan.md` | On master | Has ✅/[ ] status but buried in implementation detail |

## What's Missing

### 1. CLAUDE.md doesn't point to the docs

A fresh Claude loads CLAUDE.md automatically but won't know to read `docs/architecture.md` or `docs/exercise_types.md`. These are the most important files for preventing wrong assumptions.

**Fix:** Add a "Read These First" section at the top of CLAUDE.md that explicitly directs Claude to the two key docs before doing any work.

### 2. No feature status quick-lookup

Feature status is buried in `plan.md` among implementation checklists. A Claude that skims plan.md might miss that interval identification paging is fully implemented, or that curriculum-generation was abandoned.

**Fix:** New `docs/feature-status.md` — a clean table of every significant feature with status (Done / Planned / Abandoned) and one-line description. No implementation detail.

### 3. No confusion index

Common wrong assumptions are undocumented. The most dangerous ones are about exercise types (e.g. thinking `identification` uses a different grader than `chorale_identification`, or that paging only exists for chorale types).

**Fix:** "Don't Get This Wrong" section in `docs/feature-status.md` — a short table of the most common AI mistakes and the correct fact.

### 4. CLAUDE.md is stale

Still describes itself as the chorale-only guide. Doesn't reference the broader exercise system documentation added in April 2026.

**Fix:** Update CLAUDE.md header/overview to reflect current scope and point to new docs.

## Design

### File 1: Update `CLAUDE.md`

Add at the very top (before the existing content):

```markdown
## Before You Start — Read These First

Before making any changes to this codebase, read:
1. **[docs/architecture.md](docs/architecture.md)** — data model, request flow, key encoding, non-obvious patterns
2. **[docs/exercise_types.md](docs/exercise_types.md)** — all 8 exercise types, graders, paging, what each one is NOT
3. **[docs/feature-status.md](docs/feature-status.md)** — what's done, what's planned, what was abandoned

The rest of CLAUDE.md covers the chorale exercise system in depth.
```

### File 2: New `docs/feature-status.md`

Three sections:

**Section A — Feature Status Table**

| Feature | Status | Notes |
|---|---|---|
| `matching` / `analytical` / `figured_bass` exercise types | Done | Core original types |
| `chorale` play exercise | Done | See CLAUDE.md for full architecture |
| `identification` exercise (click to label) | Done | No paging yet on master |
| `chorale_identification` (roman_numeral, figured_bass) | Done | Paging: 4/page |
| `chorale_identification` interval types (interval_specific, interval_generic) | Done | Tonal.js authoritative source |
| Identification paging for `identification` type | **Not yet on master** | Implemented on feature/music21_builder, needs merge |
| Smart playlist transposition (shorter interval, tritone prefers down) | Done | `apps/exercises/utils/transpose.py` |
| Recurring assignments | Done | Per-period progress tracking |
| Group join codes | Done | |
| Student "My Work" view | Done | |
| Public content library | Done | |
| Course clone | Done | |
| Teacher gradebook with CSV export | Done | |
| Curriculum generation (programmatic) | **Abandoned** | Do not revisit |
| Exercise audit view (2.19) | Planned | |
| Streamlined exercise creation (2.20) | Planned | |
| Visual feedback for wrong chorale notes (red) | Planned | See chorale_future_improvements.md |
| Chorale mode variations (play-soprano, play-bass, etc.) | Planned | |
| "Explain this" button | Planned | |

**Section B — Don't Get This Wrong**

| Wrong assumption | Correct fact |
|---|---|
| `identification` and `chorale_identification` use different graders | Both use `IdentificationGrader` — same grader, extended with `pageOffset` |
| Paging only works for `chorale_identification` | On master: only `chorale_identification` has paging. `identification` paging is implemented on feature/music21_builder, not yet merged. |
| `chorale` and `chorale_identification` are the same type | They are not — `chorale` is MIDI play, `chorale_identification` is click-to-label |
| Curriculum generation was deferred | It was attempted and **abandoned** — do not revisit or build on it |
| The `key` field only affects display | It controls note spelling (enharmonic) — wrong key = wrong accidentals on staff |
| Transposition creates duplicate Exercise rows | No — transposed copies are virtual, generated on the fly with IDs like `EA00DD+16` |
| `identification` exercises use a `chord` array like `matching` | Yes, but each chord also has `answer` and `choices` keys |
| `chorale_identification` uses a `chord` array | No — it uses a `score` key with CIR JSON, same as `chorale` |

**Section C — Key Files Quick Reference**

The 10 files Claude most often needs to touch, with one-line purpose each.

## Implementation

1. Create `docs/feature-status.md` on master
2. Edit `CLAUDE.md` — add "Read These First" block at top
3. Commit both as one doc commit on master

## Success Criteria

In a fresh conversation with no prior context, Claude should:
- Read the three key docs before doing any exercise-type work
- Not suggest implementing anything in the "Done" list
- Not suggest revisiting curriculum generation
- Correctly distinguish `chorale` from `chorale_identification`
- Know that both identification types have paging
