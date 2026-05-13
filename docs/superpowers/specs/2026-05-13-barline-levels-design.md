# Barline Exercise Levels — Design Spec
**Date:** 2026-05-13
**Status:** Approved for implementation

---

## Overview

Extend the Unit 2 "Add Barlines" system from a single flat playlist of identical manual exercises to 8 levelled playlists sourced from the music21 corpus (ryansMammoth, oneills1850, essenFolksong). Difficulty increases along three axes: meter simplicity → compound → derived; rhythmic vocabulary (beat → division → subdivision); and phrase length (2 bars → 2–4 bars).

---

## Level Taxonomy

Levels are assigned by the **smallest note value present** in the phrase. A phrase qualifies for the lowest level whose ceiling it fits.

| Level | Meter family | Allowed meters | Smallest value ≤ | Phrase length | Source |
|-------|-------------|----------------|-------------------|---------------|--------|
| 1 | Simple | 3/4, 4/4 | quarter | 2 bars | corpus |
| 2 | Simple | 2/4, 3/4, 4/4 | eighth | 2 bars | corpus |
| 3 | Simple | 2/4, 3/4, 4/4 | sixteenth | 2–4 bars | corpus |
| 4 | Compound | 6/8, 9/8, 12/8 | dotted quarter | 2 bars | corpus |
| 5 | Compound | 6/8, 9/8, 12/8 | eighth | 2–4 bars | corpus |
| 6 | Compound | 6/8, 9/8, 12/8 | sixteenth | 2–4 bars | corpus |
| 7 | Derived simple | 2/2, 3/2, 4/2 | eighth | 2–4 bars | derived ×2 from L2+L3 |
| 8 | Derived compound | 6/4, 9/4, 12/4 | eighth | 2–4 bars | derived ×2 from L5+L6 |

**Level 8 ceiling clarification:** Doubling L5/L6 source phrases (which contain sixteenths and dotted eighths) produces eighths and dotted quarters — not sixteenths. So L8's smallest value ceiling is **eighth** (in 6/4 notation), which is still harder than L7 due to compound meter.

**Meter mapping for derived levels:**
- 2/4 → 2/2, 3/4 → 3/2, 4/4 → 4/2 (double all durations)
- 6/8 → 6/4, 9/8 → 9/4, 12/8 → 12/4 (double all durations)

**Duration overflow rule:** If doubling a source note would exceed a whole note (e.g., a half note doubling to a breve), that phrase is rejected. The valid duration upscale map is:
- 16th → 8th, dotted 16th → dotted 8th, 8th → quarter, dotted 8th → dotted quarter
- quarter → half, dotted quarter → dotted half, half → whole
- Anything that would exceed whole: **reject phrase**

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

### 1. `apps/exercises/utils/barline_exercise_builder.py` (extended)

**Pre-step required:** extend `SIMPLE_METERS` and `COMPOUND_METERS` to include derived meters:

```python
SIMPLE_METERS = {
    "2/4": (2, Fraction(1, 1)),
    "3/4": (3, Fraction(1, 1)),
    "4/4": (4, Fraction(1, 1)),
    "2/2": (2, Fraction(2, 1)),   # new
    "3/2": (3, Fraction(2, 1)),   # new
    "4/2": (4, Fraction(2, 1)),   # new
}
COMPOUND_METERS = {
    "6/8":  (2, Fraction(3, 2)),
    "9/8":  (3, Fraction(3, 2)),
    "12/8": (4, Fraction(3, 2)),
    "6/4":  (2, Fraction(3, 1)),  # new
    "9/4":  (3, Fraction(3, 1)),  # new
    "12/4": (4, Fraction(3, 1)),  # new
}
```

No other changes to `build_barline_payload` — the rest of the builder is meter-agnostic.

### 2. `apps/exercises/utils/corpus_filter.py` (new)

Responsibilities:
- Discover and parse abc/krn corpus files via music21
- Extract N-bar phrases (4-bar preferred, 2-bar fallback) from monophonic parts
- Classify each phrase: `(level: int, time_signature: str, notes: list[dict], measures: int)`
- Apply all phrase validity rules
- Generate derived-meter variants by doubling durations (L7, L8), rejecting overflow
- Yield phrases deduplicated by fingerprint (within a single run; DB-level dedup is handled by the command)

**Public API:**
```python
def iter_phrases(levels: list[int] | None = None) -> Iterator[PhraseResult]:
    """Yield PhraseResult(level, time_signature, notes, measures, source_path, fingerprint)"""
```

`notes` entries match `build_barline_payload` format: `{"pitch": "B4", "duration": "q", "dots": 0}`. Pitch is preserved from corpus (for future pitch-reading crossover) but rendered as rhythm-only by default (`pitch_mode="rhythm_only"`).

### 3. `apps/exercises/umto_factory.py` — `save_umto_barline_exercise` (extended)

Add optional `complexity` parameter (currently hardcoded to `2`):

```python
def save_umto_barline_exercise(
    *, description, author, payload, is_public=True, overwrite=False, complexity=2
) -> Exercise:
```

Command passes `complexity=level` (1–8) per exercise.

### 4. `apps/exercises/management/commands/generate_unit2_barline_exercises.py` (extended)

New arguments:
```
--source  choices: manual (existing), corpus (new)  [essen/kern remain as errors — no change]
--level   int 1-8, or omitted to generate all levels
--limit   max phrases per level (default: unlimited)
--dry-run print counts without saving
```

Behaviour with `--source corpus`:
1. Call `corpus_filter.iter_phrases(levels=[...])`
2. Collect all phrases per level into memory
3. For each phrase: description = `"Unit 2 barline L{level} {fingerprint[:12]}"`, call `build_barline_payload(...)` then `save_umto_barline_exercise(..., overwrite=True, complexity=level)`
4. Create/update one playlist per level: `"Unit 2 — Add Barlines, Level {N}"`
   - `skill_tags`: `["unit:2", "unit:2_rhythm", "unit:2_L{N}"]`
   - `is_dynamic=False`, `is_adaptive=True`
5. **Rebuild playlist links**: delete all existing `ExercisePlaylistOrdered` for the playlist, then re-insert the full discovered set ordered by `(source_path, phrase_offset)` — alphabetical by source, then by position within source. This is deterministic and stable across re-runs.
6. Mark `order=1` exercise as `is_adaptive_entry=True`; all others `is_adaptive_entry=False`

### 5. Playlist structure

8 playlists, one per level. Each playlist:
- Named `"Unit 2 — Add Barlines, Level {N}"`
- `is_adaptive=True` — adaptive engine serves exercises within the level based on student mastery
- Exercises ordered by `(source_path, phrase_offset)` — stable across re-runs
- First exercise (`order=1`) marked `is_adaptive_entry=True` as entry point for new students
- Existing manual playlist (`"Unit 2 — Add Barlines"`) left untouched

---

## Deduplication Strategy

**Canonical dedupe key:** `description = "Unit 2 barline L{level} {fingerprint[:12]}"`, unique per phrase per level.

**Fingerprint:** `sha256(time_sig + "|" + ",".join(f"{n['duration']}.{n['dots']}" for n in notes))` — rhythm-only, pitch-agnostic.

**Command flow (idempotent):**
1. `iter_phrases` yields all valid phrases (deduped within the run by fingerprint set)
2. `save_umto_barline_exercise(..., overwrite=True)` upserts by description+author — creates on first run, updates data on re-run
3. Playlist `ExercisePlaylistOrdered` links are fully rebuilt from the discovered set each run (delete-then-reinsert) — ensures playlist membership stays consistent even if phrases are added/removed

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
    ↓ build_barline_payload()   [after builder extended for derived meters]
barline payload dict
    ↓ save_umto_barline_exercise(complexity=level)
Exercise row (DB)
    ↓ ExercisePlaylistOrdered (delete-then-reinsert, order=1 marked adaptive_entry)
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
- Cross-level adaptive progression (student auto-promoted from L1→L2 when L1 mastered)
- Transposition of corpus phrases

---

## Testing

- **Unit tests for `corpus_filter.py`**: validity rules (each rule independently), deduplication, derived-meter doubling, overflow rejection, ending condition, level assignment (smallest value → correct level)
- **Unit tests for `barline_exercise_builder.py`**: derived meter payloads (2/2, 3/2, 4/2, 6/4) produce correct `beat_count` and `correct_barline_positions`
- **Integration test for command**: `--dry-run --source corpus` prints nonzero counts — guarded by `@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="music21 corpus not present")` to avoid CI flakiness
- **Regression**: existing `test_barline_exercise_builder.py` and `test_generate_unit2_barline_exercises.py` (manual source) pass unchanged
