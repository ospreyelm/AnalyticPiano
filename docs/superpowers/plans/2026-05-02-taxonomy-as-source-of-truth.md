# Taxonomy as Source of Truth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `music_theory_taxonomy.json` the single source of truth for which Roman numeral labels are valid at each curriculum unit, deleting all hardcoded `UNIT_ALLOWED_ANSWERS` dicts from Python and JS.

**Architecture:** The taxonomy JSON gains an `analysis.roman` object per unit (cumulative + new lists). `TaxonomyReader` exposes three new methods (`get_unit_analysis`, `get_cumulative_values`, `get_new_values`). Import code stores `raw_roman_numeral` (unfiltered music21 output) in the DB; `generate_exercise_context` in `lab/views.py` applies curriculum targeting at request time and adds an `analysisPolicy` object to the payload. The JS side removes `UNIT_ALLOWED_ANSWERS` and reads `analysisPolicy` from the payload for dropdown options; `is_target` on each slice (set server-side) drives which slots are gradeable.

**Tech Stack:** Python 3.10, Django 4.x, music21, Pydantic v2, RequireJS/AMD JS, `music_theory_taxonomy.json` (flat taxonomy file)

---

## File Map

| File | Action |
|------|--------|
| `music_theory_taxonomy.json` | Add `analysis.roman` per unit 9–18 |
| `music_theory_taxonomy_with_branches.json` | Same (kept in sync) |
| `apps/exercises/taxonomy_reader.py` | Add `get_unit_analysis`, `get_cumulative_values`, `get_new_values` |
| `apps/exercises/tests/test_taxonomy_reader.py` | Extend with new method tests |
| `apps/exercises/umto.py` | Add `raw_roman_numeral: Optional[str]` to `AnalysisLayer`; add `is_target: bool` to `AnalysisSlice` |
| `apps/exercises/management/commands/import_bach_phrases.py` | Delete `UNIT_ALLOWED_ANSWERS`; rewrite `_build_roman_analysis_overrides` to store `raw_roman_numeral`, not targeted label |
| `apps/exercises/management/commands/backfill_raw_roman_numeral.py` | New management command: re-run music21 on existing exercises lacking `raw_roman_numeral` |
| `apps/exercises/management/commands/create_unit_playlist.py` | Delete `UNIT_ALLOWED_ANSWERS` import + `_unit_new_chords`; use `TaxonomyReader`; updated ordering tuple |
| `apps/exercises/tests/test_create_unit_playlist.py` | Update/extend for new ordering behavior |
| `lab/views.py` | `generate_exercise_context`: derive unit from playlist tags; build `analysisPolicy`; set `is_target` on analysis slices |
| `lab/static/js/src/models/exercise_definition.js` | Delete `UNIT_ALLOWED_ANSWERS`; delete/no-op `applySkillFilter`; use `analysisPolicy` for dropdowns |

---

## Task 1: Add `analysis.roman` to both taxonomy JSON files

**Files:**
- Modify: `music_theory_taxonomy.json`
- Modify: `music_theory_taxonomy_with_branches.json`

This task is purely data authoring — no tests needed, but run the `TaxonomyReader` tests after to confirm JSON is valid.

- [ ] **Step 1: Author `analysis.roman` for units 9–18 in `music_theory_taxonomy.json`**

Open `music_theory_taxonomy.json`. For each unit 9–18, add an `"analysis"` key alongside the existing `"n"`, `"title"`, `"feat"`, `"tags"` keys. The `cumulative` list is derived from the existing `UNIT_ALLOWED_ANSWERS` in `import_bach_phrases.py` (lines 17–64). The `new` list is the delta vs the previous unit.

The `display` field uses Unicode superscripts where needed: `°` for diminished, `⁶` for sixth, `⁷` for seventh, `+` for augmented, `⁶₄` for 6/4. When `value == display` (e.g. `"I"`, `"V"`) you still include both fields for schema consistency.

Unit 9 block (add inside the unit 9 object):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",  "display": "I" },
      { "value": "i",  "display": "i" },
      { "value": "V",  "display": "V" },
      { "value": "V7", "display": "V⁷" }
    ],
    "new": [
      { "value": "I",  "display": "I" },
      { "value": "i",  "display": "i" },
      { "value": "V",  "display": "V" },
      { "value": "V7", "display": "V⁷" }
    ]
  }
}
```

Unit 10 (adds inversions):
```json
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
      { "value": "vii°6",  "display": "vii°⁶" }
    ],
    "new": [
      { "value": "I6",    "display": "I⁶" },
      { "value": "i6",    "display": "i⁶" },
      { "value": "V6",    "display": "V⁶" },
      { "value": "vii°6", "display": "vii°⁶" }
    ]
  }
}
```

Unit 11 (adds pre-dominants):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",     "display": "I" },
      { "value": "i",     "display": "i" },
      { "value": "V",     "display": "V" },
      { "value": "V7",    "display": "V⁷" },
      { "value": "I6",    "display": "I⁶" },
      { "value": "i6",    "display": "i⁶" },
      { "value": "V6",    "display": "V⁶" },
      { "value": "vii°6", "display": "vii°⁶" },
      { "value": "IV",    "display": "IV" },
      { "value": "iv",    "display": "iv" },
      { "value": "ii",    "display": "ii" },
      { "value": "ii6",   "display": "ii⁶" },
      { "value": "vi",    "display": "vi" },
      { "value": "VI",    "display": "VI" }
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
```

Unit 12 (adds second inversions):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",     "display": "I" },
      { "value": "i",     "display": "i" },
      { "value": "V",     "display": "V" },
      { "value": "V7",    "display": "V⁷" },
      { "value": "I6",    "display": "I⁶" },
      { "value": "i6",    "display": "i⁶" },
      { "value": "V6",    "display": "V⁶" },
      { "value": "vii°6", "display": "vii°⁶" },
      { "value": "IV",    "display": "IV" },
      { "value": "iv",    "display": "iv" },
      { "value": "ii",    "display": "ii" },
      { "value": "ii6",   "display": "ii⁶" },
      { "value": "vi",    "display": "vi" },
      { "value": "VI",    "display": "VI" },
      { "value": "I64",   "display": "I⁶₄" },
      { "value": "V64",   "display": "V⁶₄" }
    ],
    "new": [
      { "value": "I64", "display": "I⁶₄" },
      { "value": "V64", "display": "V⁶₄" }
    ]
  }
}
```

Unit 13 (adds rule-of-octave chords):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",     "display": "I" },
      { "value": "i",     "display": "i" },
      { "value": "V",     "display": "V" },
      { "value": "V7",    "display": "V⁷" },
      { "value": "I6",    "display": "I⁶" },
      { "value": "i6",    "display": "i⁶" },
      { "value": "V6",    "display": "V⁶" },
      { "value": "vii°6", "display": "vii°⁶" },
      { "value": "IV",    "display": "IV" },
      { "value": "iv",    "display": "iv" },
      { "value": "ii",    "display": "ii" },
      { "value": "ii6",   "display": "ii⁶" },
      { "value": "vi",    "display": "vi" },
      { "value": "VI",    "display": "VI" },
      { "value": "I64",   "display": "I⁶₄" },
      { "value": "V64",   "display": "V⁶₄" },
      { "value": "iii",   "display": "iii" },
      { "value": "III",   "display": "III" },
      { "value": "VII",   "display": "VII" }
    ],
    "new": [
      { "value": "iii", "display": "iii" },
      { "value": "III", "display": "III" },
      { "value": "VII", "display": "VII" }
    ]
  }
}
```

Unit 14 (adds diatonic seventh chords):
```json
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
      { "value": "VI",     "display": "VI" },
      { "value": "I64",    "display": "I⁶₄" },
      { "value": "V64",    "display": "V⁶₄" },
      { "value": "iii",    "display": "iii" },
      { "value": "III",    "display": "III" },
      { "value": "VII",    "display": "VII" },
      { "value": "ii7",    "display": "ii⁷" },
      { "value": "ii°7",   "display": "ii°⁷" },
      { "value": "IV7",    "display": "IV⁷" },
      { "value": "vi7",    "display": "vi⁷" },
      { "value": "iii7",   "display": "iii⁷" },
      { "value": "vii°7",  "display": "vii°⁷" },
      { "value": "viio7",  "display": "vii°⁷" }
    ],
    "new": [
      { "value": "ii7",   "display": "ii⁷" },
      { "value": "ii°7",  "display": "ii°⁷" },
      { "value": "IV7",   "display": "IV⁷" },
      { "value": "vi7",   "display": "vi⁷" },
      { "value": "iii7",  "display": "iii⁷" },
      { "value": "vii°7", "display": "vii°⁷" },
      { "value": "viio7", "display": "vii°⁷" }
    ]
  }
}
```

Unit 15 (sequences — same cumulative as 14, no new chord types):
```json
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
      { "value": "VI",     "display": "VI" },
      { "value": "I64",    "display": "I⁶₄" },
      { "value": "V64",    "display": "V⁶₄" },
      { "value": "iii",    "display": "iii" },
      { "value": "III",    "display": "III" },
      { "value": "VII",    "display": "VII" },
      { "value": "ii7",    "display": "ii⁷" },
      { "value": "ii°7",   "display": "ii°⁷" },
      { "value": "IV7",    "display": "IV⁷" },
      { "value": "vi7",    "display": "vi⁷" },
      { "value": "iii7",   "display": "iii⁷" },
      { "value": "vii°7",  "display": "vii°⁷" },
      { "value": "viio7",  "display": "vii°⁷" }
    ],
    "new": []
  }
}
```

Unit 16 (adds secondary/applied chords):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",        "display": "I" },
      { "value": "i",        "display": "i" },
      { "value": "V",        "display": "V" },
      { "value": "V7",       "display": "V⁷" },
      { "value": "I6",       "display": "I⁶" },
      { "value": "i6",       "display": "i⁶" },
      { "value": "V6",       "display": "V⁶" },
      { "value": "vii°6",    "display": "vii°⁶" },
      { "value": "IV",       "display": "IV" },
      { "value": "iv",       "display": "iv" },
      { "value": "ii",       "display": "ii" },
      { "value": "ii6",      "display": "ii⁶" },
      { "value": "vi",       "display": "vi" },
      { "value": "VI",       "display": "VI" },
      { "value": "I64",      "display": "I⁶₄" },
      { "value": "V64",      "display": "V⁶₄" },
      { "value": "iii",      "display": "iii" },
      { "value": "III",      "display": "III" },
      { "value": "VII",      "display": "VII" },
      { "value": "ii7",      "display": "ii⁷" },
      { "value": "ii°7",     "display": "ii°⁷" },
      { "value": "IV7",      "display": "IV⁷" },
      { "value": "vi7",      "display": "vi⁷" },
      { "value": "iii7",     "display": "iii⁷" },
      { "value": "vii°7",    "display": "vii°⁷" },
      { "value": "viio7",    "display": "vii°⁷" },
      { "value": "V/ii",     "display": "V/ii" },
      { "value": "V7/ii",    "display": "V⁷/ii" },
      { "value": "V/IV",     "display": "V/IV" },
      { "value": "V7/IV",    "display": "V⁷/IV" },
      { "value": "V/V",      "display": "V/V" },
      { "value": "V7/V",     "display": "V⁷/V" },
      { "value": "V/vi",     "display": "V/vi" },
      { "value": "V7/vi",    "display": "V⁷/vi" },
      { "value": "V/III",    "display": "V/III" },
      { "value": "V7/III",   "display": "V⁷/III" },
      { "value": "vii°/ii",  "display": "vii°/ii" },
      { "value": "vii°7/ii", "display": "vii°⁷/ii" },
      { "value": "vii°/V",   "display": "vii°/V" },
      { "value": "vii°7/V",  "display": "vii°⁷/V" },
      { "value": "vii°/vi",  "display": "vii°/vi" },
      { "value": "vii°7/vi", "display": "vii°⁷/vi" },
      { "value": "vii°/IV",  "display": "vii°/IV" },
      { "value": "vii°7/IV", "display": "vii°⁷/IV" }
    ],
    "new": [
      { "value": "V/ii",     "display": "V/ii" },
      { "value": "V7/ii",    "display": "V⁷/ii" },
      { "value": "V/IV",     "display": "V/IV" },
      { "value": "V7/IV",    "display": "V⁷/IV" },
      { "value": "V/V",      "display": "V/V" },
      { "value": "V7/V",     "display": "V⁷/V" },
      { "value": "V/vi",     "display": "V/vi" },
      { "value": "V7/vi",    "display": "V⁷/vi" },
      { "value": "V/III",    "display": "V/III" },
      { "value": "V7/III",   "display": "V⁷/III" },
      { "value": "vii°/ii",  "display": "vii°/ii" },
      { "value": "vii°7/ii", "display": "vii°⁷/ii" },
      { "value": "vii°/V",   "display": "vii°/V" },
      { "value": "vii°7/V",  "display": "vii°⁷/V" },
      { "value": "vii°/vi",  "display": "vii°/vi" },
      { "value": "vii°7/vi", "display": "vii°⁷/vi" },
      { "value": "vii°/IV",  "display": "vii°/IV" },
      { "value": "vii°7/IV", "display": "vii°⁷/IV" }
    ]
  }
}
```

Unit 17 (adds modal mixture: bVI, bVII, bIII, ii°, ii°6):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",        "display": "I" },
      { "value": "i",        "display": "i" },
      { "value": "V",        "display": "V" },
      { "value": "V7",       "display": "V⁷" },
      { "value": "I6",       "display": "I⁶" },
      { "value": "i6",       "display": "i⁶" },
      { "value": "V6",       "display": "V⁶" },
      { "value": "vii°6",    "display": "vii°⁶" },
      { "value": "IV",       "display": "IV" },
      { "value": "iv",       "display": "iv" },
      { "value": "ii",       "display": "ii" },
      { "value": "ii6",      "display": "ii⁶" },
      { "value": "vi",       "display": "vi" },
      { "value": "VI",       "display": "VI" },
      { "value": "I64",      "display": "I⁶₄" },
      { "value": "V64",      "display": "V⁶₄" },
      { "value": "iii",      "display": "iii" },
      { "value": "III",      "display": "III" },
      { "value": "VII",      "display": "VII" },
      { "value": "ii7",      "display": "ii⁷" },
      { "value": "ii°7",     "display": "ii°⁷" },
      { "value": "IV7",      "display": "IV⁷" },
      { "value": "vi7",      "display": "vi⁷" },
      { "value": "iii7",     "display": "iii⁷" },
      { "value": "vii°7",    "display": "vii°⁷" },
      { "value": "viio7",    "display": "vii°⁷" },
      { "value": "V/ii",     "display": "V/ii" },
      { "value": "V7/ii",    "display": "V⁷/ii" },
      { "value": "V/IV",     "display": "V/IV" },
      { "value": "V7/IV",    "display": "V⁷/IV" },
      { "value": "V/V",      "display": "V/V" },
      { "value": "V7/V",     "display": "V⁷/V" },
      { "value": "V/vi",     "display": "V/vi" },
      { "value": "V7/vi",    "display": "V⁷/vi" },
      { "value": "V/III",    "display": "V/III" },
      { "value": "V7/III",   "display": "V⁷/III" },
      { "value": "vii°/ii",  "display": "vii°/ii" },
      { "value": "vii°7/ii", "display": "vii°⁷/ii" },
      { "value": "vii°/V",   "display": "vii°/V" },
      { "value": "vii°7/V",  "display": "vii°⁷/V" },
      { "value": "vii°/vi",  "display": "vii°/vi" },
      { "value": "vii°7/vi", "display": "vii°⁷/vi" },
      { "value": "vii°/IV",  "display": "vii°/IV" },
      { "value": "vii°7/IV", "display": "vii°⁷/IV" },
      { "value": "bVI",      "display": "♭VI" },
      { "value": "bVII",     "display": "♭VII" },
      { "value": "bIII",     "display": "♭III" },
      { "value": "ii°",      "display": "ii°" },
      { "value": "ii°6",     "display": "ii°⁶" }
    ],
    "new": [
      { "value": "bVI",  "display": "♭VI" },
      { "value": "bVII", "display": "♭VII" },
      { "value": "bIII", "display": "♭III" },
      { "value": "ii°",  "display": "ii°" },
      { "value": "ii°6", "display": "ii°⁶" }
    ]
  }
}
```

Unit 18 (adds Neapolitan + augmented sixths):
```json
"analysis": {
  "roman": {
    "cumulative": [
      { "value": "I",        "display": "I" },
      { "value": "i",        "display": "i" },
      { "value": "V",        "display": "V" },
      { "value": "V7",       "display": "V⁷" },
      { "value": "I6",       "display": "I⁶" },
      { "value": "i6",       "display": "i⁶" },
      { "value": "V6",       "display": "V⁶" },
      { "value": "vii°6",    "display": "vii°⁶" },
      { "value": "IV",       "display": "IV" },
      { "value": "iv",       "display": "iv" },
      { "value": "ii",       "display": "ii" },
      { "value": "ii6",      "display": "ii⁶" },
      { "value": "vi",       "display": "vi" },
      { "value": "VI",       "display": "VI" },
      { "value": "I64",      "display": "I⁶₄" },
      { "value": "V64",      "display": "V⁶₄" },
      { "value": "iii",      "display": "iii" },
      { "value": "III",      "display": "III" },
      { "value": "VII",      "display": "VII" },
      { "value": "ii7",      "display": "ii⁷" },
      { "value": "ii°7",     "display": "ii°⁷" },
      { "value": "IV7",      "display": "IV⁷" },
      { "value": "vi7",      "display": "vi⁷" },
      { "value": "iii7",     "display": "iii⁷" },
      { "value": "vii°7",    "display": "vii°⁷" },
      { "value": "viio7",    "display": "vii°⁷" },
      { "value": "V/ii",     "display": "V/ii" },
      { "value": "V7/ii",    "display": "V⁷/ii" },
      { "value": "V/IV",     "display": "V/IV" },
      { "value": "V7/IV",    "display": "V⁷/IV" },
      { "value": "V/V",      "display": "V/V" },
      { "value": "V7/V",     "display": "V⁷/V" },
      { "value": "V/vi",     "display": "V/vi" },
      { "value": "V7/vi",    "display": "V⁷/vi" },
      { "value": "V/III",    "display": "V/III" },
      { "value": "V7/III",   "display": "V⁷/III" },
      { "value": "vii°/ii",  "display": "vii°/ii" },
      { "value": "vii°7/ii", "display": "vii°⁷/ii" },
      { "value": "vii°/V",   "display": "vii°/V" },
      { "value": "vii°7/V",  "display": "vii°⁷/V" },
      { "value": "vii°/vi",  "display": "vii°/vi" },
      { "value": "vii°7/vi", "display": "vii°⁷/vi" },
      { "value": "vii°/IV",  "display": "vii°/IV" },
      { "value": "vii°7/IV", "display": "vii°⁷/IV" },
      { "value": "bVI",      "display": "♭VI" },
      { "value": "bVII",     "display": "♭VII" },
      { "value": "bIII",     "display": "♭III" },
      { "value": "ii°",      "display": "ii°" },
      { "value": "ii°6",     "display": "ii°⁶" },
      { "value": "N6",       "display": "N⁶" },
      { "value": "It+6",     "display": "It⁺⁶" },
      { "value": "Ger+6",    "display": "Ger⁺⁶" },
      { "value": "Fr+6",     "display": "Fr⁺⁶" }
    ],
    "new": [
      { "value": "N6",   "display": "N⁶" },
      { "value": "It+6", "display": "It⁺⁶" },
      { "value": "Ger+6","display": "Ger⁺⁶" },
      { "value": "Fr+6", "display": "Fr⁺⁶" }
    ]
  }
}
```

- [ ] **Step 2: Mirror the same changes in `music_theory_taxonomy_with_branches.json`**

The two taxonomy files must stay identical on the `analysis` field. Copy-paste the same blocks. Both files share the same unit structure; use the same unit `n` values to locate each unit object.

- [ ] **Step 3: Verify JSON is parseable**

```bash
python -c "import json; json.load(open('music_theory_taxonomy.json')); print('OK')"
python -c "import json; json.load(open('music_theory_taxonomy_with_branches.json')); print('OK')"
```

Expected: `OK` on each line.

- [ ] **Step 4: Run existing TaxonomyReader tests**

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1
python -m pytest apps/exercises/tests/test_taxonomy_reader.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add music_theory_taxonomy.json music_theory_taxonomy_with_branches.json
git commit -m "data: add analysis.roman cumulative/new lists to taxonomy units 9-18"
```

---

## Task 2: Extend `TaxonomyReader` with analysis query methods

**Files:**
- Modify: `apps/exercises/taxonomy_reader.py`
- Modify: `apps/exercises/tests/test_taxonomy_reader.py`

- [ ] **Step 1: Write failing tests**

In `apps/exercises/tests/test_taxonomy_reader.py`, add after the existing test class:

```python
class TaxonomyReaderAnalysisTestCase(unittest.TestCase):
    def test_get_unit_analysis_returns_dict_for_unit_with_analysis(self):
        result = TaxonomyReader.get_unit_analysis("11", "roman")
        self.assertIsNotNone(result)
        self.assertIn("cumulative", result)
        self.assertIn("new", result)
        self.assertIsInstance(result["cumulative"], list)
        self.assertIsInstance(result["new"], list)

    def test_get_unit_analysis_returns_none_for_unit_without_analysis(self):
        # Unit 1 has no roman analysis
        result = TaxonomyReader.get_unit_analysis("1", "roman")
        self.assertIsNone(result)

    def test_get_unit_analysis_returns_none_for_unknown_family(self):
        result = TaxonomyReader.get_unit_analysis("11", "figured_bass")
        self.assertIsNone(result)

    def test_get_cumulative_values_returns_set_of_strings(self):
        result = TaxonomyReader.get_cumulative_values("11", "roman")
        self.assertIsInstance(result, set)
        self.assertIn("IV", result)
        self.assertIn("I", result)
        self.assertIn("V7", result)

    def test_get_cumulative_values_returns_empty_for_no_analysis(self):
        result = TaxonomyReader.get_cumulative_values("1", "roman")
        self.assertEqual(result, set())

    def test_get_new_values_returns_delta(self):
        result = TaxonomyReader.get_new_values("11", "roman")
        self.assertIn("IV", result)
        self.assertIn("ii", result)
        # Unit 9 chords are NOT in new for unit 11
        self.assertNotIn("I", result)
        self.assertNotIn("V", result)

    def test_get_new_values_returns_empty_for_no_analysis(self):
        result = TaxonomyReader.get_new_values("1", "roman")
        self.assertEqual(result, set())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/exercises/tests/test_taxonomy_reader.py::TaxonomyReaderAnalysisTestCase -v
```

Expected: FAIL with `AttributeError: type object 'TaxonomyReader' has no attribute 'get_unit_analysis'`

- [ ] **Step 3: Implement the three new methods in `TaxonomyReader`**

In `apps/exercises/taxonomy_reader.py`, append after `get_skill_label`:

```python
    @classmethod
    def get_unit_analysis(cls, unit_n: str, family: str) -> dict | None:
        """Returns {"cumulative": [...], "new": [...]} for the given unit and analysis family, or None."""
        unit = cls.get_unit(unit_n)
        if unit is None:
            return None
        return unit.get("analysis", {}).get(family)

    @classmethod
    def get_cumulative_values(cls, unit_n: str, family: str) -> set[str]:
        """Returns the set of 'value' strings from the cumulative list for this unit/family."""
        analysis = cls.get_unit_analysis(unit_n, family)
        if analysis is None:
            return set()
        return {entry["value"] for entry in analysis.get("cumulative", [])}

    @classmethod
    def get_new_values(cls, unit_n: str, family: str) -> set[str]:
        """Returns the set of 'value' strings from the new list for this unit/family."""
        analysis = cls.get_unit_analysis(unit_n, family)
        if analysis is None:
            return set()
        return {entry["value"] for entry in analysis.get("new", [])}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest apps/exercises/tests/test_taxonomy_reader.py -v
```

Expected: all 12 tests PASS (5 old + 7 new).

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/taxonomy_reader.py apps/exercises/tests/test_taxonomy_reader.py
git commit -m "feat: add get_unit_analysis, get_cumulative_values, get_new_values to TaxonomyReader"
```

---

## Task 3: Add `raw_roman_numeral` and `is_target` to the UMTO data model

**Files:**
- Modify: `apps/exercises/umto.py`
- Modify: `apps/exercises/umto_schema.json` (auto-regenerated)

`AnalysisLayer` gains `raw_roman_numeral`; `AnalysisSlice` gains `is_target`. Both are optional/defaulted so existing data remains valid.

- [ ] **Step 1: Write a failing test for the new fields**

In `apps/exercises/tests/test_umto_contract.py`, append:

```python
def test_analysis_layer_has_raw_roman_numeral():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer(roman_numeral="V", raw_roman_numeral="V/V")
    assert layer.raw_roman_numeral == "V/V"

def test_analysis_layer_raw_roman_numeral_defaults_none():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer()
    assert layer.raw_roman_numeral is None

def test_analysis_slice_has_is_target():
    from apps.exercises.umto import AnalysisSlice, AnalysisLayer
    sl = AnalysisSlice(offset=0.0, content=AnalysisLayer())
    assert sl.is_target is False  # default

def test_analysis_slice_is_target_can_be_set():
    from apps.exercises.umto import AnalysisSlice, AnalysisLayer
    sl = AnalysisSlice(offset=0.0, content=AnalysisLayer(roman_numeral="I"), is_target=True)
    assert sl.is_target is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/exercises/tests/test_umto_contract.py -v -k "raw_roman_numeral or is_target"
```

Expected: FAIL with `TypeError` or `ValidationError` (fields don't exist yet).

- [ ] **Step 3: Add fields to the Pydantic models**

In `apps/exercises/umto.py`, update `AnalysisLayer` (around line 53):

```python
class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None  # unfiltered music21 output; durable record
    figured_bass: Optional[str] = None
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None
```

Update `AnalysisSlice` (around line 69):

```python
class AnalysisSlice(BaseModel):
    offset: float
    content: AnalysisLayer
    visual: Optional[VisualMetadata] = None
    unit_tags: List[int] = Field(default_factory=list)
    is_target: bool = False  # set at request time by targeting layer
```

- [ ] **Step 4: Regenerate the JSON schema**

```bash
python manage.py make_umto_schema
```

Expected: `apps/exercises/umto_schema.json` updated with `raw_roman_numeral` and `is_target` fields.

- [ ] **Step 5: Run the new tests**

```bash
python -m pytest apps/exercises/tests/test_umto_contract.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_schema.json
git commit -m "feat: add raw_roman_numeral to AnalysisLayer and is_target to AnalysisSlice"
```

---

## Task 4: Rewrite `_build_roman_analysis_overrides` to store raw labels

**Files:**
- Modify: `apps/exercises/management/commands/import_bach_phrases.py`

The goal: delete `UNIT_ALLOWED_ANSWERS`; store music21's raw figure in `raw_roman_numeral` (no filtering); set `roman_numeral` to `None` (targeting happens at request time).

- [ ] **Step 1: Write a failing test**

In `apps/exercises/tests/` create or append to a test file for import_bach_phrases. Check if `test_import_bach_phrases.py` exists; if not, create it:

```python
# apps/exercises/tests/test_import_bach_phrases.py
import unittest
from unittest.mock import patch, MagicMock


class BuildRomanAnalysisOverridesTestCase(unittest.TestCase):
    def _call(self, phrase_score, global_key, unit_tags):
        from apps.exercises.management.commands.import_bach_phrases import (
            _build_roman_analysis_overrides,
        )
        return _build_roman_analysis_overrides(phrase_score, global_key, unit_tags)

    def test_stores_raw_roman_numeral_not_targeted(self):
        """raw_roman_numeral is stored; roman_numeral is always None."""
        from music21 import stream, chord, key as m21key, meter
        s = stream.Score()
        part = stream.Part()
        m = stream.Measure()
        m.append(chord.Chord(["C4", "E4", "G4"]))
        part.append(m)
        s.append(part)
        global_key = m21key.Key("C")
        overrides = self._call(s, global_key, [9])
        self.assertTrue(len(overrides) > 0)
        first = overrides[0]
        self.assertIn("raw_roman_numeral", first["content"])
        self.assertIsNotNone(first["content"]["raw_roman_numeral"])
        # roman_numeral is always None — targeting happens at request time
        self.assertIsNone(first["content"]["roman_numeral"])

    def test_no_filter_applied_for_out_of_scope_chord(self):
        """A chord outside unit 9's scope still gets stored with its raw label."""
        from music21 import stream, chord, key as m21key
        s = stream.Score()
        part = stream.Part()
        m = stream.Measure()
        # ii chord — not in unit 9 cumulative, but must be stored raw
        m.append(chord.Chord(["D4", "F4", "A4"]))
        part.append(m)
        s.append(part)
        global_key = m21key.Key("C")
        overrides = self._call(s, global_key, [9])
        self.assertTrue(len(overrides) > 0)
        self.assertIsNotNone(overrides[0]["content"]["raw_roman_numeral"])
        self.assertIsNone(overrides[0]["content"]["roman_numeral"])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest apps/exercises/tests/test_import_bach_phrases.py -v
```

Expected: FAIL (currently `roman_numeral` is set to the filtered figure, not `None`).

- [ ] **Step 3: Rewrite `_build_roman_analysis_overrides`**

In `apps/exercises/management/commands/import_bach_phrases.py`, delete the entire `UNIT_ALLOWED_ANSWERS` dict (lines 16–64) and replace `_build_roman_analysis_overrides` (lines 75–129) with:

```python
def _build_roman_analysis_overrides(phrase_score, global_key, unit_tags: list) -> list:
    """Analyze a phrase and return UMTO analysis_overrides with raw Roman numerals.

    Stores the raw music21 figure in raw_roman_numeral. Targeting (curriculum
    filtering) happens at request time in generate_exercise_context; nothing is
    filtered here.
    """
    from music21.roman import romanNumeralFromChord

    chorded = phrase_score.chordify()
    measures = list(chorded.getElementsByClass('Measure'))
    if not measures:
        return []

    first_measure_offset = measures[0].offset
    overrides = []
    seen_offsets = set()

    for m in measures:
        measure_start = m.offset - first_measure_offset
        for element in m.flat.notes:
            if not isinstance(element, chord.Chord):
                continue
            abs_offset = round(measure_start + float(element.offset), 5)
            if abs_offset in seen_offsets:
                continue
            seen_offsets.add(abs_offset)
            try:
                rn = romanNumeralFromChord(element, global_key)
                raw_figure = rn.figure
            except Exception:
                raw_figure = None
            overrides.append({
                "offset": abs_offset,
                "content": {
                    "roman_numeral": None,   # derived at request time, never stored
                    "raw_roman_numeral": raw_figure if raw_figure else None,
                    "figured_bass": None,
                    "pop_symbol": None,
                    "functional_label": None,
                },
                "unit_tags": list(unit_tags),
            })

    return overrides
```

Also remove the import of `UNIT_ALLOWED_ANSWERS` from the top of the file (it no longer exists).

- [ ] **Step 4: Run the tests**

```bash
python -m pytest apps/exercises/tests/test_import_bach_phrases.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/import_bach_phrases.py \
        apps/exercises/tests/test_import_bach_phrases.py
git commit -m "feat: store raw_roman_numeral in import; remove UNIT_ALLOWED_ANSWERS from import_bach_phrases"
```

---

## Task 5: Backfill `raw_roman_numeral` on existing exercises

**Files:**
- Create: `apps/exercises/management/commands/backfill_raw_roman_numeral.py`

Existing exercises in the DB have `roman_numeral` populated in stored slices but no `raw_roman_numeral`. This command re-runs music21 on each such exercise and writes the raw figure.

- [ ] **Step 1: Create the management command**

```python
# apps/exercises/management/commands/backfill_raw_roman_numeral.py
from django.core.management.base import BaseCommand
from apps.exercises.models import Exercise


class Command(BaseCommand):
    help = "Backfill raw_roman_numeral on UMTO exercises that are missing it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print what would be changed without writing to DB."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        from music21 import stream as m21stream, chord as m21chord, key as m21key
        from music21.roman import romanNumeralFromChord

        exercises = Exercise.objects.filter(
            data__score__umto__isnull=False
        )
        updated = 0
        skipped = 0

        for ex in exercises:
            umto_data = ex.data.get("score", {}).get("umto", {})
            analysis = umto_data.get("analysis", [])
            if not analysis:
                skipped += 1
                continue

            # Check if any slice is missing raw_roman_numeral
            needs_backfill = any(
                sl.get("content", {}).get("raw_roman_numeral") is None
                for sl in analysis
            )
            if not needs_backfill:
                skipped += 1
                continue

            # Re-derive raw labels from the stored CIR score
            try:
                raw_overrides = self._derive_raw_labels(ex)
            except Exception as e:
                self.stderr.write(f"  ERROR {ex.id}: {e}")
                continue

            if not raw_overrides:
                skipped += 1
                continue

            # Merge raw_roman_numeral into existing slices by offset
            raw_by_offset = {round(r["offset"], 5): r["content"]["raw_roman_numeral"]
                             for r in raw_overrides}
            changed = False
            for sl in analysis:
                off = round(sl.get("offset", 0), 5)
                if off in raw_by_offset and sl["content"].get("raw_roman_numeral") is None:
                    sl["content"]["raw_roman_numeral"] = raw_by_offset[off]
                    changed = True

            if changed:
                if not dry_run:
                    ex.data["score"]["umto"]["analysis"] = analysis
                    ex.save(update_fields=["data"])
                updated += 1
                self.stdout.write(f"  {'[dry] ' if dry_run else ''}Updated {ex.id}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated: {updated}, skipped (no-op): {skipped}"
            )
        )

    def _derive_raw_labels(self, ex: "Exercise") -> list:
        """Re-run music21 roman numeral analysis on this exercise's score."""
        from music21 import stream as m21stream, chord as m21chord, key as m21key
        from music21.roman import romanNumeralFromChord

        score_data = ex.data.get("score", {})
        key_str = score_data.get("meta", {}).get("key", "C major")
        try:
            global_key = m21key.Key(key_str.split()[0])
        except Exception:
            global_key = m21key.Key("C")

        measures = score_data.get("measures", [])
        if not measures:
            return []

        # Build a minimal music21 score from the CIR measure data
        score = m21stream.Score()
        part = m21stream.Part()
        for mdata in measures:
            m = m21stream.Measure()
            staves = mdata.get("staves", {})
            for staff_name, staff in staves.items():
                for voice_list in staff.get("voices", []):
                    for item in voice_list.get("items", []):
                        if item.get("kind") == "note" and item.get("pitch"):
                            p = item["pitch"]
                            from music21 import note as m21note, pitch as m21pitch
                            mp = m21pitch.Pitch(
                                step=p["step"],
                                accidental=p.get("alter", 0),
                                octave=p.get("octave", 4),
                            )
                            n = m21note.Note()
                            n.pitch = mp
                            m.append(n)
            part.append(m)
        score.append(part)

        # Chordify and extract roman numerals
        chorded = score.chordify()
        result = []
        seen = set()
        offset_acc = 0.0
        for m in chorded.getElementsByClass("Measure"):
            for el in m.flat.notes:
                if not isinstance(el, m21chord.Chord):
                    continue
                abs_offset = round(offset_acc + float(el.offset), 5)
                if abs_offset in seen:
                    continue
                seen.add(abs_offset)
                try:
                    rn = romanNumeralFromChord(el, global_key)
                    raw = rn.figure
                except Exception:
                    raw = None
                result.append({
                    "offset": abs_offset,
                    "content": {"raw_roman_numeral": raw},
                })
            offset_acc += float(m.barDuration.quarterLength)
        return result
```

- [ ] **Step 2: Run a dry-run to verify it doesn't crash**

```bash
python manage.py backfill_raw_roman_numeral --dry-run
```

Expected: output listing exercises that would be updated, ending with `Done. Updated: N, skipped: M`. No errors.

- [ ] **Step 3: Run for real (after verifying dry-run)**

```bash
python manage.py backfill_raw_roman_numeral
```

Expected: same count of updated exercises, no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/management/commands/backfill_raw_roman_numeral.py
git commit -m "feat: add backfill_raw_roman_numeral management command for existing exercises"
```

---

## Task 6: Add targeting logic and `analysisPolicy` to `generate_exercise_context`

**Files:**
- Modify: `lab/views.py`

The server now resolves unit from **playlist** `skill_tags`, runs a lightweight targeting pass over raw analysis slices, sets `is_target` on each, and appends `analysisPolicy` to the exercise context.

- [ ] **Step 1: Write a failing test**

In `apps/exercises/tests/test_views_umto_logging.py` or a new file `apps/exercises/tests/test_generate_exercise_context.py`:

```python
# apps/exercises/tests/test_generate_exercise_context.py
import pytest
from unittest.mock import MagicMock, patch
from django.test import TestCase


class GenerateExerciseContextAnalysisPolicyTest(TestCase):
    def _make_exercise(self, raw_rn, unit_tags=None):
        """Minimal UMTO exercise dict with a single analysis slice."""
        return {
            "isUMTO": True,
            "metadata": {
                "exercise_id": "TEST01",
                "source": "test",
                "key": "C",
                "meter": "4/4",
                "complexity_score": 9,
                "mode": "identification",
            },
            "voices": {"S": [], "A": [], "T": [], "B": []},
            "analysis": [
                {
                    "offset": 0.0,
                    "content": {
                        "roman_numeral": None,
                        "raw_roman_numeral": raw_rn,
                        "figured_bass": None,
                        "pop_symbol": None,
                        "functional_label": None,
                    },
                    "unit_tags": unit_tags or [11],
                    "is_target": False,
                }
            ],
            "grading": [],
        }

    @patch("lab.views.TaxonomyReader")
    def test_analysis_policy_included_in_context(self, mock_reader):
        mock_reader.get_cumulative_values.return_value = {"I", "V", "IV"}
        mock_reader.get_new_values.return_value = {"IV"}
        mock_reader.get_unit_analysis.return_value = {
            "cumulative": [
                {"value": "I", "display": "I"},
                {"value": "V", "display": "V"},
                {"value": "IV", "display": "IV"},
            ],
            "new": [{"value": "IV", "display": "IV"}],
        }

        from apps.exercises.models import Exercise, Playlist
        ex = MagicMock(spec=Exercise)
        ex.data = self._make_exercise("I")
        ex.skill_tags = ["unit:11", "mode:roman"]
        ex.id = "TEST01"
        ex.complexity = 9

        pl = MagicMock(spec=Playlist)
        pl.skill_tags = ["unit:11", "mode:roman"]
        pl.is_adaptive = False
        pl.is_dynamic = False
        pl.tags = []
        pl.feedback_mode = ""
        pl.exercise_count = 1
        pl.prev_num.return_value = None
        pl.next_num.return_value = None
        pl.get_exercise_obj_by_num.return_value = None
        pl.get_exercise_url_by_num.return_value = None
        pl.exercise_list = [ex]
        pl.id = "PLTEST"
        pl.min_complexity = 1
        pl.max_complexity = 12

        from lab.views import generate_exercise_context
        ctx = generate_exercise_context(
            exercise_num=1,
            exercise=ex,
            user=MagicMock(id=1),
            playlist=pl,
            course=None,
        )

        self.assertIn("analysisPolicy", ctx)
        policy = ctx["analysisPolicy"]
        self.assertEqual(policy["family"], "roman")
        self.assertEqual(policy["unit"], 11)
        self.assertIn("allowedValues", policy)
        self.assertIn("newValues", policy)
        self.assertIn("displayMap", policy)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest apps/exercises/tests/test_generate_exercise_context.py -v
```

Expected: FAIL — `analysisPolicy` not in context.

- [ ] **Step 3: Implement targeting and `analysisPolicy` in `generate_exercise_context`**

In `lab/views.py`, after the `unit_n = None` / tag-loop block (around line 307), add the targeting + policy logic. Insert before the `exercise_context.update({...})` call at line 322:

```python
    # Build analysisPolicy and apply targeting to raw analysis slices
    from apps.exercises.taxonomy_reader import TaxonomyReader as _TR
    analysis_policy = None
    _unit_n_for_policy = unit_n  # may be None if no unit tag found

    if _unit_n_for_policy:
        _unit_analysis = _TR.get_unit_analysis(_unit_n_for_policy, "roman")
        if _unit_analysis:
            _cumulative = _TR.get_cumulative_values(_unit_n_for_policy, "roman")
            _new_vals = _TR.get_new_values(_unit_n_for_policy, "roman")

            # Build displayMap: only entries where display != value
            _display_map = {
                entry["value"]: entry["display"]
                for entry in _unit_analysis["cumulative"]
                if entry["display"] != entry["value"]
            }

            analysis_policy = {
                "family": "roman",
                "unit": int(_unit_n_for_policy),
                "mode": "targeted_slots",
                "allowedValues": sorted(_cumulative),
                "newValues": sorted(_new_vals),
                "displayMap": _display_map,
            }

            # Apply targeting: set is_target on each analysis slice in the payload
            _score = exercise_context.get("score", {})
            _umto_data = _score.get("umto", {}) if isinstance(_score, dict) else {}
            _slices = _umto_data.get("analysis", [])
            for _sl in _slices:
                _raw = _sl.get("content", {}).get("raw_roman_numeral")
                if _raw and _raw in _cumulative:
                    # In-scope: set roman_numeral to the raw value (no secondary-function
                    # disambiguation in this phase — that is a future enhancement)
                    _sl["content"]["roman_numeral"] = _raw
                    _sl["is_target"] = True
                else:
                    _sl["content"]["roman_numeral"] = None
                    _sl["is_target"] = False
```

Then add `"analysisPolicy": analysis_policy,` inside the `exercise_context.update({...})` dict (around line 322):

```python
    exercise_context.update(
        {
            "analysisPolicy": analysis_policy,
            "unit_n": unit_n,
            # ... rest of existing keys unchanged ...
        }
    )
```

- [ ] **Step 4: Run the test**

```bash
python -m pytest apps/exercises/tests/test_generate_exercise_context.py -v
```

Expected: PASS.

- [ ] **Step 5: Also run the full test suite to check for regressions**

```bash
python -m pytest apps/exercises/tests/ -v --tb=short 2>&1 | tail -30
```

Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add lab/views.py apps/exercises/tests/test_generate_exercise_context.py
git commit -m "feat: add analysisPolicy to exercise context and apply targeting to raw analysis slices"
```

---

## Task 7: Update `create_unit_playlist.py` to use `TaxonomyReader`

**Files:**
- Modify: `apps/exercises/management/commands/create_unit_playlist.py`
- Modify: `apps/exercises/tests/test_create_unit_playlist.py`

Delete `UNIT_ALLOWED_ANSWERS` import and `_unit_new_chords`; use `TaxonomyReader` for new-chord detection.

- [ ] **Step 1: Write a failing test**

In `apps/exercises/tests/test_create_unit_playlist.py`, add a test that checks `_has_new_chord` uses TaxonomyReader (not the old import):

```python
def test_has_new_chord_uses_taxonomy_not_import():
    """_has_new_chord must not import from import_bach_phrases."""
    import ast, inspect
    import apps.exercises.management.commands.create_unit_playlist as mod
    src = inspect.getsource(mod)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "import_bach_phrases" in node.module:
                for alias in node.names:
                    assert alias.name != "UNIT_ALLOWED_ANSWERS", (
                        "create_unit_playlist must not import UNIT_ALLOWED_ANSWERS from import_bach_phrases"
                    )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest apps/exercises/tests/test_create_unit_playlist.py::test_has_new_chord_uses_taxonomy_not_import -v
```

Expected: FAIL — the import is currently there.

- [ ] **Step 3: Rewrite `create_unit_playlist.py` — delete stale helpers and use `TaxonomyReader`**

Replace the top of `apps/exercises/management/commands/create_unit_playlist.py`:

**Delete** lines 8–16 (the `UNIT_ALLOWED_ANSWERS` import and `_unit_new_chords` function):
```python
# DELETE these lines:
from apps.exercises.management.commands.import_bach_phrases import UNIT_ALLOWED_ANSWERS

def _unit_new_chords(unit_num: int) -> set[str]:
    ...
```

**Replace** the `_has_new_chord` static method body inside `Command` (it now reads from TaxonomyReader via `raw_roman_numeral`):

The new top-of-file imports (keep existing imports, add `TaxonomyReader`):
```python
from apps.exercises.taxonomy_reader import TaxonomyReader
```

Rewrite `_has_new_chord` as a module-level function (remove from class or keep as `@staticmethod` — both work):

```python
def _unit_new_chords(unit_num: int) -> set[str]:
    """Chords introduced at this unit, from taxonomy."""
    return TaxonomyReader.get_new_values(str(unit_num), "roman")
```

Update `Command._has_new_chord` to use `raw_roman_numeral` if present, falling back to `roman_numeral`:

```python
@staticmethod
def _has_new_chord(ex: "Exercise", unit_num: int) -> bool:
    """Return True if exercise analysis contains at least one chord new to unit_num."""
    new_chords = _unit_new_chords(unit_num)
    if not new_chords:
        return True
    analysis = ex.data.get("score", {}).get("umto", {}).get("analysis", [])
    rns = set()
    for s in analysis:
        content = s.get("content", {})
        # Prefer raw_roman_numeral (unfiltered); fall back to roman_numeral for
        # exercises imported before the backfill.
        label = content.get("raw_roman_numeral") or content.get("roman_numeral")
        if label:
            rns.add(label)
    return bool(rns & new_chords)
```

- [ ] **Step 4: Run the tests**

```bash
python -m pytest apps/exercises/tests/test_create_unit_playlist.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/create_unit_playlist.py \
        apps/exercises/tests/test_create_unit_playlist.py
git commit -m "feat: create_unit_playlist uses TaxonomyReader instead of hardcoded UNIT_ALLOWED_ANSWERS"
```

---

## Task 8: Update JS — delete `UNIT_ALLOWED_ANSWERS`, read `analysisPolicy` for dropdowns

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`

The `UNIT_ALLOWED_ANSWERS` object (lines 14–91) and the unit-tag parsing logic inside `applySkillFilter` (lines 106–139) are deleted. The function is reduced to a no-op: `is_target` on each slice (set server-side in Task 6) already hides out-of-scope slots. Dropdown choices come from `analysisPolicy.allowedValues`.

- [ ] **Step 1: Delete `UNIT_ALLOWED_ANSWERS` and simplify `applySkillFilter`**

In `lab/static/js/src/models/exercise_definition.js`:

**Delete** lines 14–91 (the entire `var UNIT_ALLOWED_ANSWERS = { ... };` object).

**Replace** the `applySkillFilter` function (lines 93–140) with:

```javascript
  function applySkillFilter(problems, skillTags, analysisType, explicitAllowedAnswers) {
    // Targeting is applied server-side via is_target on each analysis slice.
    // explicitAllowedAnswers (from analysisPolicy.allowedValues) is used only
    // to populate dropdown choices, not to hide slots.
    // This function is now a pass-through — slot visibility is already resolved.
    if (explicitAllowedAnswers && explicitAllowedAnswers.length > 0) {
      return _.map(problems, function (p) {
        if (p.hidden) return p;
        if (explicitAllowedAnswers.indexOf(p.answer) === -1) {
          p = _.clone(p);
          p.hidden = true;
        }
        return p;
      });
    }
    return problems;
  }
```

> **Why keep the `explicitAllowedAnswers` branch?** The server sets `is_target = false` for out-of-scope slices, making their `hidden: true` in `rawProblems`. But `applySkillFilter` is still called with `explicitAllowedAnswers = analysisPolicy.allowedValues` as the dropdown population step — the branch that hides based on `allowedValues` catches any remaining slots whose `answer` is not in scope (belt-and-suspenders for the transition period while some exercises still have `roman_numeral` stored from before the backfill).

- [ ] **Step 2: Verify dropdown choices use `analysisPolicy.allowedValues`**

Search for where `allowed_answers` is passed into `applySkillFilter` and where dropdown `choices` are built. The call site is around line 610–640 in `exercise_definition.js`. The existing code already passes `exercise.allowed_answers` as `explicitAllowedAnswers`. After Task 6, `exercise.allowed_answers` will be populated from `analysisPolicy.allowedValues` via the server payload.

Check that `to_frontend_payload` in `umto.py` (`lab/views.py` path) still sets `allowed_answers`. Looking at `umto.py` line 189: `"allowed_answers": self.get_allowed_answers(unit)`. This is the pre-policy path; after Task 6, `analysisPolicy.allowedValues` is the authoritative source. For now, `allowed_answers` stays for backwards compatibility with non-UMTO exercises. No change needed here.

- [ ] **Step 3: Manual smoke test**

Open `http://127.0.0.1:8000/s/units/11/play/?playlist=<your-unit-11-playlist-id>&exercise_num=1` in a browser. Verify:
- Analysis slots show only pre-dominant and earlier chords
- Dropdown options match `analysisPolicy.allowedValues` in the page context (check DevTools → Network → the page response JSON or `window.__EXERCISE_CONTEXT__`)
- No JS errors in console

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat: remove UNIT_ALLOWED_ANSWERS from JS; applySkillFilter is now server-driven pass-through"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by task |
|---|---|
| §1 Taxonomy schema: `analysis.roman`, `cumulative`, `new`, `value`, `display` | Task 1 |
| §2 `TaxonomyReader` extensions: `get_unit_analysis`, `get_cumulative_values`, `get_new_values` | Task 2 |
| §3 `raw_roman_numeral` stored; `roman_numeral` null in DB | Task 3, 4 |
| §3 `_build_roman_analysis_overrides` rewritten | Task 4 |
| §3 Backfill command | Task 5 |
| §4 `analysisPolicy` payload from server | Task 6 |
| §4 `is_target` set at request time | Task 6 |
| §5 JS: delete `UNIT_ALLOWED_ANSWERS` | Task 8 |
| §5 JS: `applySkillFilter` reduced / server-driven | Task 8 |
| §5 JS: dropdown uses `analysisPolicy.allowedValues` | Task 8, checked |
| §6 `create_unit_playlist` uses `TaxonomyReader` | Task 7 |
| §6 `_has_new_chord` uses `raw_roman_numeral` | Task 7 |
| Migration backfill prerequisite | Task 5 |

**Notes on spec items deferred:**
- **Secondary-function escalating-context disambiguation** (spec §3 targeting step 2): Task 6 uses a simplified targeting pass (raw label in cumulative → keep; else null). The full disambiguation algorithm (check N chords ahead for resolution) is a follow-up. The spec marks this as the targeting layer but the implementation plan delivers a safe first version that is correct for all non-secondary-function labels. Secondary function labels (`V/V` etc.) will appear as `null` slots until the disambiguation logic is added in a future task.
- **`all_chords_in_scope` mode for performance playlists** (spec §4, §6): not yet implemented. Performance playlists currently use the existing behaviour. This is a separate task.
- **`displayMap` rendering in JS** (spec §5): `analysisPolicy.displayMap` is emitted by the server (Task 6) but JS rendering using it for dropdown labels is left for a follow-up. The existing display logic continues to work.
