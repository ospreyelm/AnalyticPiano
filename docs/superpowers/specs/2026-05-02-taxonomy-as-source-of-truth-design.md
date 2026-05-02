# Taxonomy as Single Source of Truth for Harmonic Analysis

**Date:** 2026-05-02  
**Status:** Approved for implementation

---

## Problem

Three independent sources of truth currently define which Roman numerals are valid at each curriculum unit:

1. `UNIT_ALLOWED_ANSWERS` dict in `import_bach_phrases.py` (Python, ~50 lines)
2. `UNIT_ALLOWED_ANSWERS` dict in `exercise_definition.js` (JS, identical copy)
3. `music_theory_taxonomy_with_branches.json` — has `feat` strings but no machine-readable answer lists

Every debugging session patches local errors with hardcoded values in one location without updating the others. The JS and Python dicts drift. Teachers have no way to adjust curriculum policy without editing source code.

The fix: taxonomy JSON is the single source of truth. Python and JS derive everything from it at runtime or request time. No hardcoded answer tables in application code.

---

## Core Design Principles

**Taxonomy defines curriculum policy.** Which chords are permitted and which are new at each unit.

**Analysis code defines musical interpretation.** music21 produces raw labels; a normalization layer converts them to canonical tokens; a targeting layer applies curriculum policy. These are three distinct steps.

**Raw analysis is the durable record.** The database stores what the music objectively analyzes as. Unit-targeted labels are derived at request time from raw + current taxonomy policy. Taxonomy edits update targeting behavior without requiring reimport.

**Exercise payload carries resolved policy to the browser.** The server sends an explicit `analysisPolicy` object. The frontend renders what the payload says; it does not reconstruct curriculum logic or parse unit tags.

**One framework for all analysis families.** Roman numerals now. Figured bass, chord symbols, intervals, scale degrees, solfege later. The taxonomy shape and payload structure must not hardcode Roman-numeral-specific concepts.

---

## Section 1: Taxonomy Data Model

### Schema

Each unit in `music_theory_taxonomy_with_branches.json` (and `music_theory_taxonomy.json`) gains an `analysis` object keyed by analysis family:

```json
{
  "n": "11",
  "title": "Pre-dominants",
  "feat": "IV, ii, ii⁶, vi",
  "tags": ["diatonic_predominant", "Diatonic_Predominant"],
  "analysis": {
    "roman": {
      "cumulative": [
        { "value": "I",      "display": "I" },
        { "value": "i",      "display": "i" },
        { "value": "V",      "display": "V" },
        { "value": "V7",     "display": "V⁷" },
        { "value": "I6",     "display": "I⁶" },
        { "value": "i6",     "display": "i⁶" },
        { "value": "V6",     "display": "V⁶" },
        { "value": "vii°6",  "display": "vii°⁶" },
        { "value": "IV",     "display": "IV" },
        { "value": "iv",     "display": "iv" },
        { "value": "ii",     "display": "ii" },
        { "value": "ii6",    "display": "ii⁶" },
        { "value": "vi",     "display": "vi" },
        { "value": "VI",     "display": "VI" }
      ],
      "new": [
        { "value": "IV",  "display": "IV" },
        { "value": "iv",  "display": "iv" },
        { "value": "ii",  "display": "ii" },
        { "value": "ii6", "display": "ii⁶" },
        { "value": "vi",  "display": "vi" },
        { "value": "VI",  "display": "VI" }
      ]
    }
  }
}
```

### Field semantics

- **`analysis`** — keyed by family name (`roman`, `figured_bass`, `interval`, etc.). Absent families are omitted; units with no analysis exercises omit `analysis` entirely.
- **`cumulative`** — all values a student may encounter in this unit's exercises. Used as the acceptance filter during analysis import and as the frontend allowlist.
- **`new`** — values pedagogically introduced at this unit (delta from previous unit). Used as the minimum inclusion requirement for playlist selection.
- **`value`** — machine-readable canonical token matching music21 output symbols (ASCII). Authoritative.
- **`display`** — Unicode presentation string for UI rendering. Presentation-only; non-authoritative.

### Validation rules (enforced by `TaxonomyReader`)

- `new` must be a subset of `cumulative`
- `value` entries must be unique within a family
- `display` is informational; validation does not enforce display consistency

### Coverage

`analysis.roman` is authored for units 9–18. Units 1–8 (pitch, rhythm, intervals) and modulation units (19–20) omit `analysis.roman`. Future families (`figured_bass`, `interval`, `scale_degree`, `solfege`) are added per unit when those exercise types are built.

---

## Section 2: TaxonomyReader Extensions

`apps/exercises/taxonomy_reader.py` gains two new methods:

```python
TaxonomyReader.get_unit_analysis(unit_n: str, family: str) -> dict | None
# Returns {"cumulative": [...], "new": [...]} or None if not defined.

TaxonomyReader.get_cumulative_values(unit_n: str, family: str) -> set[str]
# Returns set of "value" strings from cumulative list.

TaxonomyReader.get_new_values(unit_n: str, family: str) -> set[str]
# Returns set of "value" strings from new list.
```

These are the **only** interfaces application code uses to access curriculum policy. No other code reads `analysis` directly from the JSON.

Both taxonomy files (`music_theory_taxonomy.json` and `music_theory_taxonomy_with_branches.json`) are updated identically.

---

## Section 3: Analysis Pipeline (Python, import time)

### Three distinct steps

**Step 1 — Raw label (music21)**  
`roman_analyzer.get_raw(chord, key)` → raw music21 figure string, e.g. `"V/V"`, `"bVII"`, `"ii6"`

**Step 2 — Normalization**  
`roman_normalizer.to_canonical(raw)` → canonical token matching taxonomy `value` symbols. Handles only music21 *spelling variants of the same token* — e.g. `viio7` → `vii°7` (formatting), `Ger+6` → `Ger⁺⁶` (symbol). **Chromatic alterations are preserved:** `bVII`, `bVI`, `bIII` survive normalization unchanged. Collapsing `bVII` to `VII` is a curriculum decision, not a spelling fix, and belongs only in the targeting step. This is a pure function with no curriculum knowledge.

**Step 3 — Targeting (context-aware disambiguation)**  
`roman_targeting.resolve(canonical, chord_index, chord_sequence, unit_n)` → final targeted value or `None`.

Targeting logic:
- If canonical is unambiguously in `cumulative` → return it
- If canonical is a secondary-function label (contains `/`) AND its diatonic equivalent is also in `cumulative` → run escalating-context disambiguation:
  1. Check 1 chord ahead: if resolves to secondary target → keep secondary label
  2. Check 2 chords ahead → same
  3. Check to phrase boundary (next cadence) → same
  4. If none resolve → use the diatonic label (the one in `cumulative`)
- If final label is not in `cumulative` → return `None` (not a target slot)

### Storage schema (UMTO analysis slice)

```json
{
  "onset_beats": 1.0,
  "unit_tags": [11],
  "content": {
    "roman_numeral": null,
    "raw_roman_numeral": "V/V",
    "pop_symbol": null,
    "figured_bass": null,
    "functional_label": null
  },
  "is_target": false
}
```

- `raw_roman_numeral` — always stored; music21 output after normalization; durable record
- `roman_numeral` — targeted value (in `cumulative`) or `null` if out of scope; **computed at request time, not stored**
- `is_target` — boolean, derived at request time from `roman_numeral != null`

> **Important:** `roman_numeral` in the stored slice is removed. The field exists only in the request-time payload. The stored record contains only `raw_roman_numeral`. This keeps the DB as a stable musical record independent of curriculum policy.

### Deletion

`UNIT_ALLOWED_ANSWERS` dict in `import_bach_phrases.py` is deleted. The function `_build_roman_analysis_overrides` is rewritten to use `TaxonomyReader.get_cumulative_values(unit_n, "roman")`.

---

## Section 4: Exercise Payload (server → browser)

`generate_exercise_context()` in `lab/views.py` resolves the unit from the playlist's `skill_tags`, loads analysis policy from `TaxonomyReader`, applies targeting to raw analysis slices, and adds to the context:

```python
"analysisPolicy": {
    "family": "roman",
    "unit": 11,
    "mode": "targeted_slots",           # or "all_chords_in_scope" for performance
    "allowedValues": ["I", "i", "V", ...],   # from cumulative
    "newValues": ["IV", "iv", "ii", ...],    # from new
    "displayMap": {                          # only entries where display != value
        "V7":    "V⁷",
        "I6":    "I⁶",
        "i6":    "i⁶",
        "V6":    "V⁶",
        "vii°6": "vii°⁶",
        "ii6":   "ii⁶"
    }
}
```

The analysis slices in the payload have `roman_numeral` populated (targeted value or `null`) and `is_target` set, derived at request time.

### Selection modes

**`targeted_slots`** (identification/analysis exercises): out-of-scope chords become `null` slots — hidden from the student, not gradeable. Phrases may contain out-of-scope harmony that is simply not presented.

**`all_chords_in_scope`** (performance/play exercises): phrase is only included in a playlist if every harmonic event is in `cumulative`. Enforced at playlist-build time, not request time.

---

## Section 5: Frontend (JS)

### Deletions

- `UNIT_ALLOWED_ANSWERS` dict in `exercise_definition.js` — deleted
- All unit-tag parsing logic in `applySkillFilter()` used to reconstruct answer lists — deleted

### New behavior

JS builds gradeable problem slots directly from analysis slices that have `is_target: true` in the payload. It does **not** re-filter slices against `analysisPolicy.allowedValues` — the server is the single authoritative pass for targeting. `applySkillFilter()` is deleted or reduced to a no-op for Roman numeral exercises.

`analysisPolicy.allowedValues` is used only to populate **dropdown options** for `?` slots (the list of choices a student picks from). It is not used to decide which slots are gradeable.

Dropdown rendering uses `analysisPolicy.displayMap` — if the value has an entry, show the display string; otherwise show the value as-is. No hardcoded display mappings in JS.

---

## Section 6: Playlist Selection and Ordering

### Selection (in `create_unit_playlist.py`)

Reads `new` and `cumulative` from `TaxonomyReader` — no import from `import_bach_phrases`.

Playlist selection uses the **targeting function** (same as request time), not raw values directly. A chord whose `raw_roman_numeral` is `V/V` but whose targeted value collapses to `V` is treated as containing `V` for both inclusion and ordering. This ensures playlist selection and browser behavior agree on what the exercise contains.

**Analysis exercises (`targeted_slots` mode):**
- Run targeting on each slice to get the targeted value
- Include phrase if at least one targeted value is in `new`
- Out-of-scope chords (targeted value = `None`) are permitted — they become hidden slots

**Performance exercises (`all_chords_in_scope` mode):**
- Run targeting on each slice
- Include phrase only if every targeted value is in `cumulative` (no `None` results)
- Additionally require at least one targeted value in `new` (unless `--no-chord-filter`)

### Ordering

```python
selected.sort(key=lambda ex: (
    _out_of_scope_ratio(ex, cumulative),    # ascending: fewer out-of-scope chords first
    -_new_value_event_count(ex, new_set),   # descending: more new-chord exposure first
    -_targetable_event_ratio(ex, cumulative), # descending: more relevant material first
    ex.complexity,                           # ascending: simpler first
    _extract_riem_phrase(ex.description or "") # deterministic tiebreaker
))
```

Where:
- `_out_of_scope_ratio` = out-of-scope events / total events (0.0 for performance mode, varies for analysis)
- `_new_value_event_count` = count of events (not distinct values) whose canonical label is in `new`
- `_targetable_event_ratio` = events in `cumulative` / total events

`UNIT_ALLOWED_ANSWERS` import from `import_bach_phrases` deleted. `_unit_new_chords()` deleted and replaced by `TaxonomyReader.get_new_values()`.

---

## Migration of Existing Exercises

Existing exercises in the DB have `roman_numeral` populated in stored slices but no `raw_roman_numeral`. The request-time targeting layer must derive targeted labels from `raw_roman_numeral`. For existing exercises that lack it:

- A backfill management command (`backfill_raw_roman_numeral`) re-runs music21 analysis on existing UMTO exercises and stores `raw_roman_numeral` in each slice, leaving `roman_numeral` in place temporarily
- Once `raw_roman_numeral` is present on all exercises, the request-time layer uses it and ignores any stored `roman_numeral`
- A follow-up migration can strip stored `roman_numeral` from all slices once the backfill is verified

The backfill is a prerequisite for the request-time targeting layer to work on existing exercises.

---

## What Is Not In This Spec

- **Synthetic exercise generation** — taxonomy shape does not block it, but no `generation` schema is authored now
- **Progression patterns** — future spec
- **Cached/versioned derived analysis** — future escape hatch if request-time targeting proves expensive or audit trail is needed
- **Figured bass, interval, solfege families** — taxonomy shape supports them; authoring and pipeline implementation are separate specs per family

---

## Files Changed

| File | Change |
|------|--------|
| `music_theory_taxonomy_with_branches.json` | Add `analysis.roman` per unit 9–18 |
| `music_theory_taxonomy.json` | Same |
| `apps/exercises/taxonomy_reader.py` | Add `get_unit_analysis`, `get_cumulative_values`, `get_new_values` |
| `apps/exercises/management/commands/import_bach_phrases.py` | Delete `UNIT_ALLOWED_ANSWERS`; rewrite `_build_roman_analysis_overrides`; store `raw_roman_numeral`, not targeted label |
| `apps/exercises/management/commands/create_unit_playlist.py` | Delete `UNIT_ALLOWED_ANSWERS` import and `_unit_new_chords`; use `TaxonomyReader`; new ordering tuple; `all_chords_in_scope` mode for performance |
| `lab/views.py` / `generate_exercise_context()` | Resolve unit from playlist tags; build `analysisPolicy`; derive targeted analysis at request time |
| `lab/static/js/src/models/exercise_definition.js` | Delete `UNIT_ALLOWED_ANSWERS`; rewrite `applySkillFilter` to use `analysisPolicy` |
