# Unit 1: Note Reading (Bach Corpus)

This document describes the automated generation of Unit 1 (Note Name Identification) exercises from the Bach Riemenschneider chorale corpus.

## Objective
Provide a massive library of progressive note-reading exercises using authentic SATB literature. The curriculum moves from a handful of "anchor" notes in simple keys to a full diatonic range across all common key signatures.

---

## Technical Implementation

### 1. Data Foundation
The exercises are derived from the Bach chorale corpus via `music21`.
- **Importer**: `python manage.py import_music21_corpus`
- **Diatonicality**: Every note in the generated CIR JSON includes an `is_diatonic` flag. This is calculated by comparing the note's pitch and alteration against the `k.pitches` of the chorale's key signature.
- **Strictness**: To prevent confusing students in the first unit, **only strictly diatonic passages** are used. Any measure containing a chromatic accidental (e.g., a Bb in D major) is automatically discarded by the generator.

### 2. Stage Categorization
Exercises are grouped into 4 progressive stages based on their note range (Steps and Octaves):

| Stage | Note Set (Steps & Octaves) |
|---|---|
| **1** | {C4, G4, C5, G5} |
| **2** | Stage 1 + {B3, D4, F4, A4, B4, D5, F5, A5} |
| **3** | Stage 2 + {E4, E5, B5, C6} |
| **4** | Stage 3 + {A3} |

*Note: Bass clef exercises use the exact mirror of these sets around Middle C.*

### 3. Generation & Sorting Logic
Command: `python manage.py generate_unit1 --author <email> --clef both --lanes both --max-per-playlist 36 --max-per-stage 12`

The generator uses a **sliding window** of 2 measures across the entire corpus:
1. **Filtering**: If a window contains any `is_diatonic: false` note, it is **skipped**.
2. **Categorization**: The window is assigned the lowest Stage (1-4) that contains all of its pitches. If it exceeds Stage 4, it is skipped.
3. **Complexity Score**: A `complexity` integer is calculated: `(Stage * 10) + NumAccidentals`.
   - Example: Stage 2 in C Major = **20**
   - Example: Stage 2 in D Major = **22**
4. **Interleaving**: The final playlist is sorted primarily by `complexity`. This ensures students start with Stage 1 in C major, then Stage 1 in G/F major, before moving to Stage 2 in C major.

### 4. Playlist Caps
- Default per-playlist cap: **36**
- Default per-stage cap: **12**
- Suggested hard ceiling for pilot runtime: **48** per playlist

These caps keep exercise payload size predictable while preserving stage variety.

### 5. Curriculum Wiring
The command automatically creates/updates:
- **Identify playlists**: `"Unit 1 - Note Names (Treble)"` and `"Unit 1 - Note Names (Bass)"`.
- **Matching playlists**: `"Unit 1 - Note Names (Treble Play)"` and `"Unit 1 - Note Names (Bass Play)"`.
- **Tags**: Exercises and playlists are tagged for `unit:1`, `Note_Names`, clef-specific tags, and matching-lane enharmonic aggregation tags.
- **Course**: The playlists are attached to the `"Unit 1: Pitch & Staff Notation"` course.

### 6. Rebuild Utility
- Command: `python manage.py rebuild_unit1_playlists --author <email>`
- Purpose: rebuild `ExercisePlaylistOrdered` rows deterministically from existing Unit 1 exercises without re-reading corpus files.

---

## Reference
- **Generation Command**: [generate_unit1.py](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/exercises/management/commands/generate_unit1.py)
- **Diatonicality Logic**: [music21_builder.py](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/exercises/utils/music21_builder.py)
- **Unit 9 Strategy**: [unit_9_bach_import_strategy.md](unit_9_bach_import_strategy.md) (for comparison)
