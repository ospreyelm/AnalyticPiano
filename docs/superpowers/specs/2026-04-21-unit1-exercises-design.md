# Unit 1 Exercise Content Design

**Date:** 2026-04-21
**Status:** Draft

---

## Overview

Unit 1 ("Pitch & Staff Notation") exercises use the existing `chorale_identification` + `note_name` analysis type. Students see a single soprano (or bass) voice extracted from a Bach chorale and identify each note by clicking a `?` slot and selecting from 5 choices.

Exercises are ordered using the **Dandelot method**: anchor notes first, neighbors added progressively, with spaced repetition interleaving across stages. All content comes from the Riemenschneider Bach chorale corpus (371 chorales), filtered to excerpts whose note set fits each stage.

---

## Display Approach

**Single voice only** — no other voices shown. The score shows one staff (treble or bass) with the extracted voice. This keeps Unit 1 focused and uncluttered for beginners.

Each exercise is ~8–12 notes (~2 measures). Short exercises → fast feedback loop → lower frustration for beginners.

---

## Dandelot Stage Map

### Treble Clef (gamut A3–C6)

| Stage | New notes introduced | Cumulative count |
|-------|----------------------|-----------------|
| 1 | C4, G4, C5, G5 | 4 |
| 2 | B3, D4, F4, A4, B4, D5, F5, A5 | 12 |
| 3 | E4, E5, B5, C6 | 16 |
| 4 | A3 (low ledger line) | 17 |
| 5 | Accidentals on any note above | chromatic |

Stage map derived from `dandelot-emulator-treble.xml` (Opusmodus-generated file in repo root).

### Bass Clef (gamut F2–D5, anchors F2, C3, F3, C4)

Bass stages are derived algorithmically by mirroring the treble Dandelot structure around middle C (C4). Each treble note maps to its bass mirror: interval from C4 is inverted. This is computed in `generate_unit1` — not hardcoded — so it stays in sync if the treble map is ever adjusted.

| Stage | New notes introduced |
|-------|----------------------|
| 1 | F2, C3, F3, C4 (anchors — mirror of G4, C4, G5, C5) |
| 2 | G2, E3, A3, B3, G3, E4, A2, B2 (neighbors — mirror of treble Stage 2) |
| 3 | D3, D2, A2 (fill — mirror of treble Stage 3 E/B notes) |
| 4 | D5 (high ledger line extreme) |
| 5 | Accidentals |

The exact derived set will be logged by `generate_unit1 --dry-run` for review before first real run.

---

## Interleaving / Spaced Repetition Order

Exercises within the playlist are sorted using a pre-computed interleave sequence across stages. Pattern:

```
[1, 1, 2, 1, 2, 1, 3, 2, 1, 3, 2, 3, 4, 3, 2, 4, 3, 4, 5, 4, 5, ...]
```

- Early in the playlist: mostly Stage 1, occasional Stage 2 peek
- Mid playlist: Stage 1 reviews interspersed as new stages introduced
- Later: all stages rotating, Stage 5 (accidentals) appearing last

**Algorithm — weighted round-robin:** Stage K gets weight `6 - K` (Stage 1 = 5 slots, Stage 2 = 4, Stage 3 = 3, Stage 4 = 2, Stage 5 = 1 per cycle). Each cycle exhausts one exercise from each bucket proportional to its weight. Buckets are drained in ascending stage order within each cycle slot. When a bucket empties, remaining cycles skip it.

Sort key computed at generation time and stored as `ExercisePlaylistOrdered.order`. Playlist order is fixed (not dynamically recomputed at serve time).

Within each stage bucket, exercises are sorted by Riemenschneider number (ascending) before interleaving.

---

## New Commands

### 1. `import_music21_corpus`

One-time bulk import of Riemenschneider chorales to local CIR JSON.

```bash
python manage.py import_music21_corpus \
  --riemenschneider 1-371 \
  --output-dir data/corpus/bach/ \
  --dry-run
```

**Algorithm:**
1. Call `music21.corpus.getBachChorales()` → Riemenschneider set (~371 paths)
2. For each: `music21.corpus.parse(path)` → music21 `Score`
3. Convert via new `score_to_cir(score)` function in `music21_builder.py`
4. Write to `data/corpus/bach/<bwv_id>.json`
5. Skip if file already exists (idempotent)
6. Log written / skipped / failed counts

**`score_to_cir(score)` — reverse path in `music21_builder.py`:**

music21 Bach chorales have 4 separate `Part` objects, not 2 staves. Map by part index using the same `VOICE_MAP` ordering as `pitch_voice_utils.py`:

| Part index | Voice | CIR stave | CIR voice index |
|------------|-------|-----------|-----------------|
| 0 | Soprano | treble | 0 |
| 1 | Alto | treble | 1 |
| 2 | Tenor | bass | 0 |
| 3 | Bass | bass | 1 |

| music21 object | CIR field |
|---------------|-----------|
| `score.parts[0,1]` | `staves.treble.voices[0,1]` |
| `score.parts[2,3]` | `staves.bass.voices[0,1]` |
| `note.Note` | `{kind:"note", pitch:{step,alter,octave}, duration:{type,dots}}` |
| `note.Rest` | `{kind:"rest", duration:{type,dots}}` |
| `note.Chord` | `{kind:"chord", pitches:[...]}` |
| Key/time sig | `meta.key`, `meta.time_signature` |

All 371 Riemenschneider chorales are SATB 4-part — no structural validation needed.

---

### 2. `generate_unit1`

Generates Unit 1 pitch identification exercises from the local corpus.

```bash
python manage.py generate_unit1 \
  --author admin@example.com \
  --clef treble           # treble | bass | both (default: both)
  --dry-run
```

**Algorithm:**
1. Load all CIR JSON files from `data/corpus/bach/`
2. For each chorale, extract target voice (soprano for treble, bass voice for bass clef)
3. Slide a 2-measure window (step=1 measure) across the voice
4. For each window:
   - Compute MIDI pitch set (excluding rests)
   - Skip if note count < 6 or > 14
   - Find highest stage whose **cumulative** note set contains all pitches in window
   - Skip if any pitch falls outside Stage 5 gamut
   - Skip if any item in the window is a chord (bass voice may have chords — `validate_pitch_voice()` enforces single-note constraint)
   - Call `strip_to_voice()` to produce single-voice CIR score
   - Create `Exercise`:
     - `type: "chorale_identification"`
     - `analysisType: "note_name"`
     - `skill_tags: ["unit:1", "Note_Names"]`
     - `complexity`: stage number (1–5)
     - `description`: e.g. `"BWV10.7 mm.3-4 – Soprano (note_name) Stage 1"` — 1-indexed measure numbers (score convention). This description is the **idempotency key**: `generate_unit1` skips creation if `Exercise.objects.filter(description=desc).exists()`. The format is deterministic so re-runs produce identical keys.
     - `is_public: True`
5. Compute interleaved sort order across all created exercises (see above)
6. Create or update `Playlist(name="Unit 1 — Note Names (Treble)", skill_tags=["unit:1","Note_Names"])`
7. Link exercises via `ExercisePlaylistOrdered` using computed sort order
8. Link playlist to Unit 1 `Course` via `PlaylistCourseOrdered` (create Course if absent)
9. Idempotent: skip exercise if description already exists

---

## Playlist & Course Wiring

| Playlist | Clef | Tags | Voice |
|----------|------|------|-------|
| Unit 1 — Note Names (Treble) | Treble | `unit:1`, `Note_Names` | soprano |
| Unit 1 — Note Names (Bass) | Bass | `unit:1`, `Note_Names` | bass |

Both playlists link to a single `Course` titled `"Unit 1: Pitch & Staff Notation"`.

`StudentSkillMastery` rows keyed on `Note_Names` — one row per student covers both playlists. Progress aggregation unchanged from student-app spec.

No new models required.

---

## Dependencies

| Dependency | Status |
|------------|--------|
| `strip_to_voice()` in `pitch_voice_utils.py` | Implemented |
| `chorale_identification` + `note_name` exercise type | Implemented |
| `StudentSkillMastery` model | Implemented (updates not yet wired) |
| `Course` / `Playlist` / `PlaylistCourseOrdered` models | Implemented |
| `music21_builder.py` forward path (CIR → music21) | Implemented |
| `score_to_cir()` reverse path (music21 → CIR) | **New work** |
| `import_music21_corpus` command | **New work** |
| `generate_unit1` command | **New work** |
| Mastery update hook on `IdentificationAttempt` | Planned (mastery-wiring spec) — not a blocker for content generation |

---

## Out of Scope

- Ledger Lines, Clefs, Enharmonics playlists (separate skills in Unit 1) — follow same pattern but deferred
- Bass clef stage note sets hardcoded — derived algorithmically at runtime by mirroring treble map
- Mastery gating between stages within playlist — mastery-wiring spec handles this
- Unit 2+ content generation
