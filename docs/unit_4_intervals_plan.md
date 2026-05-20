# Unit 4: Intervals — Curriculum Plan

_Branch: Core Sequence, Tier 1 — Fundamentals_

**Taxonomy entry:** Quality, inversion, consonance/dissonance
**Tags:** `interval_quality`, `interval_inversion`, `Interval_Generic`, `Interval_Specific`, `Interval_Compound`

---

## What exists in the engine today

| Capability | Exercise type | Status |
|---|---|---|
| Click-to-label generic interval (2nd, 3rd…) | `chorale_identification`, `interval_generic` | Done |
| Click-to-label specific interval (M3, P5…) | `chorale_identification`, `interval_specific` | Done |
| Compound interval flag | `compoundIntervals: true` on above | Done |
| Play two notated notes on MIDI | `matching` | Done |
| `unit:4` tagging | tags field | Done |

---

## Proposed lanes

| Lane | Exercise type | Description |
|---|---|---|
| **Identify (Generic)** | `chorale_identification`, `interval_generic` | See 2-voice excerpt, pick generic size (2nd, 3rd…) |
| **Identify (Specific)** | `chorale_identification`, `interval_specific` | See 2-voice excerpt, pick quality+size (M3, P5…) |
| **Play the Interval** | `matching` | See 2 notated notes, play both on MIDI |
| **Compound Intervals** *(phase 2)* | `chorale_identification`, `interval_specific`, `compoundIntervals: true` | Same but with 9ths/10ths from wide voice pairs |

---

## Content source & generation approach

- **Source:** Bach chorale corpus (`/data/corpus/bach/`)
- **Method:** Sliding window of 1–2 measures across 2-voice extractions
- **Voice pairs by width:**

| Voice pair | Typical intervals | Lane |
|---|---|---|
| Soprano–Alto | 3rds, 6ths (close) | Generic + Specific |
| Soprano–Tenor | 6ths, 10ths (medium) | Specific + Compound |
| Soprano–Bass | 10ths–15ths (wide) | Compound |

- **Filter:** Diatonic only — reuse `is_diatonic` flag from Unit 1 logic. Discard any window containing a chromatic alteration.
- `chorale_identification` enforces exactly 2 voices at import time.

---

## Staging (complexity order)

| Stage | Intervals | Rationale |
|---|---|---|
| 1 | P1, P8, P5 | Perfect consonances — easiest to hear |
| 2 | M3, m3, M6, m6 | Imperfect consonances |
| 3 | M2, m2, M7, m7 | Dissonances |
| 4 | A4/d5 | Tritone — most ambiguous |

Complexity score: `(Stage × 10) + NumAccidentals` — same formula as Unit 1.

---

## New management command

```
python manage.py generate_unit4 --author <email> --voice-pair soprano-alto --max-per-stage 12
```

**Modeled on `generate_unit1.py`.** Key differences:
- Outputs 2-voice CIR JSON (not full SATB)
- Creates `chorale_identification` exercises (not `matching`)
- Voice pair is a parameter: `soprano-alto` | `soprano-tenor` | `soprano-bass`
- Sets `analysisType` to `interval_generic` or `interval_specific` depending on lane flag

### Implementation sketch

```python
# apps/exercises/management/commands/generate_unit4.py

for chorale in load_corpus():
    windows = sliding_window(chorale, voices=[top_voice, bottom_voice], size=2)
    for window in windows:
        if not all_diatonic(window):
            continue
        interval = compute_interval(window)  # via Tonal.js mapping or music21
        stage = classify_stage(interval)
        complexity = stage * 10 + count_accidentals(window)
        exercises.append(build_chorale_identification(window, analysis_type, complexity))

exercises.sort(key=lambda e: e.complexity)
create_playlist(exercises[:max_per_stage * 4], name=f"Unit 4 — {lane_name}")
```

---

## Playlist & course structure

```
Course: "Unit 4: Intervals"
  Playlist: "Unit 4 — Generic Intervals (Soprano–Alto)"     ← interval_generic
  Playlist: "Unit 4 — Specific Intervals (Soprano–Alto)"    ← interval_specific
  Playlist: "Unit 4 — Play Intervals"                       ← matching
  Playlist: "Unit 4 — Compound Intervals"                   ← phase 2, compoundIntervals: true
```

Per-playlist cap: **36 exercises** (matches Unit 1 convention). Default per-stage cap: **12**.

---

## Tags to apply

| Tag | Applies to |
|---|---|
| `unit:4` | All exercises and playlists |
| `Interval_Generic` | Generic identification lane |
| `Interval_Specific` | Specific identification lane |
| `interval_quality` | Specific identification lane |
| `interval_inversion` | *(phase 2 — inversion drill lane)* |
| `Interval_Compound` | Compound interval lane |

---

## What is NOT buildable with existing exercise types

| Concept | Gap | Path forward |
|---|---|---|
| Interval inversion drill | No paired-question type | Hand-author a small `identification` exercise set with inverted interval answer choices (e.g. "M3 inverts to __": m6, M6, m3, P5) |
| Consonance/dissonance classification | Technically possible via `identification` | Small hand-authored set; answer choices: "perfect consonance / imperfect consonance / dissonance" |
| Write an interval above/below a given note | No construct-mode exercise type | Out of scope — new exercise type required |

---

## Reference

- [Unit 1 strategy](unit_1_note_reading_strategy.md) — generation pattern this follows
- [Exercise types](exercise_types.md) — `chorale_identification` interval modes
- [generate_unit1.py](../apps/exercises/management/commands/generate_unit1.py) — template for new command
