# Barline Exercise Levels — Design Spec
**Date:** 2026-05-13
**Status:** Approved for implementation

---

## Overview

Extend the Unit 2 "Add Barlines" system from a single flat playlist of identical manual exercises to 8 levelled playlists sourced from the music21 corpus (ryansMammoth, oneills1850, essenFolksong). Difficulty increases along three axes: meter simplicity → compound → derived; rhythmic vocabulary (beat → division → subdivision); and phrase length (2 bars → 2–4 bars).

---

## Level Taxonomy

Levels are assigned by the **smallest note value present** in the phrase (less prescriptive than requiring exact vocabulary). A phrase qualifies for the lowest level whose ceiling it fits.

| Level | Meter family | Allowed meters | Smallest value ≤ | Phrase length | Source |
|-------|-------------|----------------|-------------------|---------------|--------|
| 1 | Simple | 3/4, 4/4 | quarter | 2 bars | corpus |
| 2 | Simple | 2/4, 3/4, 4/4 | eighth | 2 bars | corpus |
| 3 | Simple | 2/4, 3/4, 4/4 | sixteenth (+ dotted eighth, dotted quarter) | 2–4 bars | corpus |
| 4 | Compound | 6/8, 9/8, 12/8 | dotted quarter | 2 bars | corpus |
| 5 | Compound | 6/8, 9/8, 12/8 | eighth | 2–4 bars | corpus |
| 6 | Compound | 6/8, 9/8, 12/8 | sixteenth (+ dotted eighth) | 2–4 bars | corpus |
| 7 | Derived simple | 2/2, 3/2, 4/2 | eighth (after doubling) | 2–4 bars | derived ×2 from L2+L3 |
| 8 | Derived compound | 6/4, 9/4, 12/4 | sixteenth (after doubling) | 2–4 bars | derived ×2 from L5+L6 |

**Meter mapping for derived levels:**
- 2/4 → 2/2, 3/4 → 3/2, 4/4 → 4/2 (double all durations)
- 6/8 → 6/4, 9/8 → 9/4, 12/8 → 12/4 (double all durations)

---

## Phrase Validity Rules

A phrase extracted from the corpus is accepted only if ALL of the following hold:

1. **Meter matches** the level's allowed set
2. **Smallest note value** ≤ the level ceiling (assigned to lowest matching level)
3. **Duration sum** exactly fills N complete measures (no pickup bar handling initially)
4. **Ending condition**: `duration(notes[-1]) >= duration(notes[-2])` — last note at least as long as preceding note (musical sense of ending)
5. **No rests** — rests are a separate pedagogical concern not yet supported by the barline renderer
6. **No ties across barlines** — would make correct_barline_positions ambiguous
7. **Phrase length**: 2 bars for levels 1, 2, 4; 2 or 4 bars for levels 3, 5, 6, 7, 8 (try 4-bar slice first, fall back to 2)

---

## Components

### 1. `apps/exercises/utils/corpus_filter.py` (new)

Responsibilities:
- Discover and parse abc/krn corpus files via music21
- Extract N-bar phrases (4-bar preferred, 2-bar fallback) from monophonic parts
- Classify each phrase: `(level: int, time_signature: str, notes: list[dict], measures: int)`
- Apply all phrase validity rules
- Generate derived-meter variants by doubling durations (L7, L8)
- Deduplicate by `sha256(time_sig + json(note_sequence))` — skip already-seen fingerprints

**Public API:**
```python
def iter_phrases(levels: list[int] | None = None) -> Iterator[PhraseResult]:
    """Yield PhraseResult(level, time_signature, notes, measures, source_path, fingerprint)"""
```

`notes` entries match `build_barline_payload` format: `{"pitch": "B4", "duration": "q", "dots": 0}`. Pitch is preserved from corpus (for future pitch-reading crossover) but rendered as rhythm-only by default (`pitch_mode="rhythm_only"`).

### 2. `apps/exercises/management/commands/generate_unit2_barline_exercises.py` (extended)

New arguments:
```
--source  choices: manual (existing), corpus (new)
--level   int 1-8, or omitted to generate all levels
--limit   max phrases per level (default: unlimited)
--dry-run print counts without saving
```

Behaviour with `--source corpus`:
1. Call `corpus_filter.iter_phrases(levels=[...])` 
2. For each phrase, call `build_barline_payload(...)` then `save_umto_barline_exercise(...)`
3. Create/update one playlist per level: `"Unit 2 — Add Barlines, Level N"`
   - `skill_tags`: `["unit:2", "unit:2_rhythm", "unit:2_L{N}"]`
   - `is_dynamic=False`, `is_adaptive=True`
   - `complexity` = level number (1–8)
4. Link all exercises to their level playlist via `ExercisePlaylistOrdered` (ordered by fingerprint for reproducibility)
5. Command is **idempotent**: re-running skips already-saved fingerprints (stored in exercise description or a dedupe field)

### 3. Playlist structure

8 playlists, one per level. Each playlist:
- Named `"Unit 2 — Add Barlines, Level {N}"`  
- `is_adaptive=True` — adaptive engine serves exercises within the level based on mastery
- Exercises ordered deterministically (alphabetical by source path + phrase offset) so order is stable across re-runs
- Existing manual playlist (`"Unit 2 — Add Barlines"`) left untouched

---

## Deduplication Strategy

Exercise description = `"Unit 2 barline L{level} {fingerprint[:12]}"` — unique per phrase. `save_umto_barline_exercise(..., overwrite=True)` matches on description+author, so re-runs update rather than duplicate.

Fingerprint = `sha256(time_sig + "|" + ",".join(f"{n['duration']}.{n['dots']}" for n in notes))` — rhythm only (pitch-agnostic so transposed variants don't create duplicates, though we don't transpose yet).

---

## Corpus Sources

Tried in order, all via `music21.corpus.getPaths()`:

1. `ryansMammoth` — 1059 abc files, 1 tune each, mix of jigs (6/8), reels (4/4), waltzes (3/4)
2. `oneills1850` — 39 abc files
3. `essenFolksong` — 31 abc files, each an Opus with ~300 scores

Expected yield per level (rough estimate before implementation):
- L1: ~200–400 phrases (quarters-only tunes are common)
- L2: ~500+ (most reels/jigs have eighth notes)
- L3: ~200 (sixteenth notes less common in folk)
- L4: ~100–200 (jigs with only dotted quarters)
- L5: ~400+ (jigs with eighth notes)
- L6: ~100 (compound + sixteenths)
- L7/L8: same count as L2+L3 / L5+L6 (derived)

---

## Data Flow

```
music21 corpus (abc/krn)
    ↓ corpus_filter.iter_phrases()
PhraseResult(level, time_sig, notes, measures, fingerprint)
    ↓ build_barline_payload()
barline payload dict
    ↓ save_umto_barline_exercise()
Exercise row (DB)
    ↓ ExercisePlaylistOrdered
Playlist "Unit 2 — Add Barlines, Level N"
    ↓ adaptive engine (mastery.py)
Student sees next exercise within their level
```

---

## Out of Scope

- Rests in barline exercises (separate feature)
- Ties across barlines
- Pickup bars (anacrusis)
- Beaming exercises
- Cross-level adaptive progression (student auto-promoted from L1→L2 when L1 mastered) — playlists are independent for now; curriculum sequencing handles promotion via separate unit playlists
- Transposition of corpus phrases

---

## Testing

- Unit tests for `corpus_filter.py`: validity rules, deduplication, derived-meter doubling, ending condition
- Unit tests for level assignment: phrase with given smallest value → correct level
- Integration test: `--dry-run` produces nonzero phrase counts for at least L1, L2, L4, L5
- Existing `test_barline_exercise_builder.py` and `test_generate_unit2_barline_exercises.py` must continue to pass (manual source path unchanged)
