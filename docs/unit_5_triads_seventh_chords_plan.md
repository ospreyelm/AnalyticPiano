# Unit 5: Triads & Seventh Chords — Curriculum Plan

_Branch: Core Sequence, Tier 1 — Fundamentals_

**Taxonomy entry:** Triad quality, seventh chord quality, chord symbol notation
**Tags:** `unit:5_triad_quality`, `unit:5_seventh_chord_quality`

---

## Design decisions

- **Labels:** Chord symbol quality names (major, minor, diminished, augmented; dominant 7, major 7, minor 7, half-dim 7, diminished 7) — not figured bass.
- **Inversions:** Root position only. No inversion identification in Unit 5.
- **Content source:** Synthetic — generated programmatically via `generation/music21_builder.py`. No Bach corpus or MusicXML file needed.
- **Exercise type:** `identification` (UMTO-wrapped). Student sees a notated chord on a keyboard staff and selects its quality from a multiple-choice popup.
- **Voicing:** `keyboard_4voice` — bass note in bass clef (MIDI ~45–57), upper voices in treble clef (MIDI ~60–76), root doubled in soprano for triads.

---

## Lane 1 — Triad Quality Identification

**Command:**
```
python manage.py generate_unit5 --type triads --author <email> --public
```

**Staged difficulty — number of answer choices grows:**

| Stage | Choices | Active qualities | Root pool (≤N acc) | Exercises |
|-------|---------|-----------------|-------------------|-----------|
| 1 | major, minor | major, minor | ≤3 acc (7 roots) | 12 |
| 2 | major, minor, diminished | + diminished | ≤5 acc (11 roots) | 12 |
| 3 | major, minor, diminished, augmented | + augmented | all 12 roots | 12 |

Each playlist draws exercises in round-robin order (qualities cycle, roots cycle), so every quality appears roughly equally and roots are varied.

**Playlist names:** `Unit 5 — Triad Quality: Stage {1|2|3}`
**Tags:** `unit:5`, `unit:5_triad_quality`, `unit:5_L{stage}`

---

## Lane 2 — Seventh Chord Quality Identification

**Command:**
```
python manage.py generate_unit5 --type sevenths --author <email> --public
```

**Staged difficulty:**

| Stage | Choices | Active qualities | Root pool (≤N acc) | Exercises |
|-------|---------|-----------------|-------------------|-----------|
| 1 | dominant 7, major 7 | dominant, major7 | ≤3 acc (7 roots) | 12 |
| 2 | + minor 7 | + minor7 | ≤5 acc (11 roots) | 12 |
| 3 | + half-dim 7 | + half_dim | ≤7 acc (all roots) | 12 |
| 4 | + diminished 7 | + dim7 | all 12 roots | 12 |

**Playlist names:** `Unit 5 — Seventh Chord Quality: Stage {1|2|3|4}`
**Tags:** `unit:5`, `unit:5_seventh_chord_quality`, `unit:5_L{stage}`

---

## Rebuild sequence

```bash
# Generate both lanes at once
python manage.py generate_unit5 --type both --author <email> --public --overwrite

# Or separately
python manage.py generate_unit5 --type triads --author <email> --public --overwrite
python manage.py generate_unit5 --type sevenths --author <email> --public --overwrite
```

---

## Root pool

All roots ordered by accidental count:

| Root | HL key string | Accidentals |
|------|--------------|-------------|
| C | `jC_` | 0 |
| G | `jG_` | 1 |
| F | `jF_` | 1 |
| D | `jD_` | 2 |
| Bb | `jBb` | 2 |
| A | `jA_` | 3 |
| Eb | `jEb` | 3 |
| E | `jE_` | 4 |
| Ab | `jAb` | 4 |
| B | `jB_` | 5 |
| Db | `jDb` | 5 |
| F# | `jF#` | 6 |

The display key for each chord is determined by `spelling_key_for_pitches()` rather than the root key, so enharmonic spellings (e.g. Eb in a C minor chord) render correctly.

---

## Course structure

```
Course: "Unit 5: Triads & Seventh Chords"
  Playlist: "Unit 5 — Triad Quality: Stage 1"
  Playlist: "Unit 5 — Triad Quality: Stage 2"
  Playlist: "Unit 5 — Triad Quality: Stage 3"
  Playlist: "Unit 5 — Seventh Chord Quality: Stage 1"
  Playlist: "Unit 5 — Seventh Chord Quality: Stage 2"
  Playlist: "Unit 5 — Seventh Chord Quality: Stage 3"
  Playlist: "Unit 5 — Seventh Chord Quality: Stage 4"
```

---

## Key files

- `apps/exercises/management/commands/generate_unit5.py`
- `apps/exercises/generation/music21_builder.py` — `triad()`, `seventh_chord()`, `spelling_key_for_pitches()`
- `apps/exercises/umto_factory.py` — `save_umto_chord_id_exercise()`

---

## What is NOT built in Unit 5

| Concept | Gap | Notes |
|---------|-----|-------|
| Inversion identification | Not built | Figured bass branch (Unit A1–A3) covers inversions |
| Play the chord (MIDI) | Not built | Could add `matching` lane for chord playback |
| Chord spelling (write it) | No construct exercise type | Out of scope |
| Diatonic context (I, ii, V…) | Unit 9 | Diatonic triads in key context belong to Unit 9 |

---

## Reference

- [Exercise types](exercise_types.md) — `identification` type reference
- `apps/exercises/generation/music21_builder.py` — `QUALITY_INTERVALS`, `LABEL_MAP`
- `apps/exercises/skill_graph.py` — `unit:5_triad_quality`, `unit:5_seventh_chord_quality`
