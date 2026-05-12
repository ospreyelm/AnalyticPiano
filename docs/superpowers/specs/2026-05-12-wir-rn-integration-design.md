# When in Rome RN Integration — Design

**Date:** 2026-05-12
**Status:** Design — ready for implementation planning
**Author:** avnerdorman

---

## Summary

Replace music21's `romanNumeralFromChord()` as the source of `roman_numeral` in `AnalysisSlice` objects with human-annotated labels from the When in Rome (WiR) corpus. WiR covers all 371 Riemenschneider chorales with beat-level RN labels by human analysts. music21 RN output is preserved in `raw_roman_numeral` for audit/comparison. No UMTO schema changes required.

---

## Motivation

music21's RN analysis has two systematic problems:

1. **NCT pollution** — `chordify()` verticalises passing tones and suspensions into fake chords, producing labels like `I742`, `IV42` that have no harmonic meaning.
2. **Global key only** — no modulation or tonicisation detection; a secondary dominant in D minor gets labelled as if the piece never left G major.

WiR solves both: human analysts simply don't label NCT beats, and they write explicit key changes (`d:`, `D:`) when tonicisation occurs. The result is harmonically correct, NCT-free labelling for every chorale we teach.

Figured bass is computed independently (bass + intervals, no RN reasoning) and is unaffected by this change.

---

## Decisions

| Question | Decision |
|---|---|
| What fills `roman_numeral`? | WiR label |
| What fills `raw_roman_numeral`? | music21 output (preserved for audit) |
| New schema field for WiR? | No — `roman_numeral` was always intended for the curated label |
| Missing WiR entry at import? | `CommandError` — abort, no silent fallback |
| NCT slices (WiR has no label)? | `roman_numeral=None`; FB still populated |
| Variant readings? | Stored in JSON, not used at import time (future use) |

---

## Scope

**In scope:**
- One-time WiR corpus download and JSON conversion
- `bwv_to_riemenschneider.json` mapping (auto-derived from WiR `.txt` headers)
- `apps/exercises/utils/wir_corpus.py` lookup module
- Changes to `_build_roman_analysis_overrides()` in `import_bach_phrases.py`
- Tests for corpus module and conversion parser

**Out of scope:**
- WiR integration for non-chorale exercises
- Using WiR variant readings at runtime
- Dropping `raw_roman_numeral` from schema (deferred — do after WiR is proven in production)
- Merging RN and FB override builders into a single pass (Approach 3 — future work)

---

## Data Layer

### WiR corpus JSON

**Location:** `data/when_in_rome/chorales.json`

Keyed by Riemenschneider number (string). Built once by `scripts/convert_wir_corpus.py` from the downloaded WiR `.txt` files.

```json
{
  "1": {
    "title": "Aus meines Herzens Grunde",
    "bwv": "269",
    "time_signature": "3/4",
    "labels": [
      {"measure": 0, "beat": 3.0, "label": "I"},
      {"measure": 1, "beat": 1.0, "label": "I"},
      {"measure": 1, "beat": 2.0, "label": "IV6"},
      {"measure": 1, "beat": 3.0, "label": "V6"},
      ...
    ]
  }
}
```

Variant readings stored as optional field on label objects:
```json
{"measure": 11, "beat": 2.0, "label": "iii6", "variant": "I6/4"}
```

### BWV → Riemenschneider map

**Location:** `data/when_in_rome/bwv_to_riemenschneider.json`

Flat object `{"269": 1, "253": 2, ...}`. Auto-derived from the `BWV:` header line in each WiR `.txt` file by the conversion script. No hand-curation.

### WiR corpus source

Download from `https://github.com/MarkGotham/When-in-Rome`, directory `Corpus/Bach_Chorales/`. 371 `.txt` files in RomanText format. License: CC BY-SA.

---

## Conversion Script

**Location:** `scripts/convert_wir_corpus.py`

One-time script. Not part of the regular import pipeline. Run once after downloading WiR, commit the resulting JSON.

**Responsibilities:**
- Parse all 371 `.txt` files using the WiR parser (same logic as `rn_comparison_r1.html`, battle-tested)
- Extract `BWV:`, `Title:`, `Time Signature:` from headers
- Build label list: `{measure, beat, label}` per chord event
- Store variant readings on the label object
- Write `chorales.json` and `bwv_to_riemenschneider.json`

**Parser rules (from `rn_comparison_r1.html`):**
- Beat markers: `/^b\d/` — only `b` followed by digit(s), never confused with `bVI`, `bvii`
- Key-change tokens: `/^[A-Ga-g][#b-]?:$/` — skipped (context only, not a label)
- Repeat barlines `||`, `:||`, `|` — skipped
- `Note:`, `Composer:`, `BWV:`, etc. header lines — skipped
- Variant lines (`m11var1`) — stored as `variant` field, not as main label

---

## Lookup Module

**File:** `apps/exercises/utils/wir_corpus.py`

Loaded once at module level (JSON read on first import).

```python
def lookup_rn(riemenschneider: int, measure: int, beat: float) -> str | None:
    """Return WiR main label for closest beat at or before (measure, beat).
    Returns None if chorale unknown or no label covers this offset."""

def bwv_to_riemenschneider(bwv: str) -> int | None:
    """Return Riemenschneider number for a BWV string, or None if not found."""
```

**Lookup semantics:** within a measure, find the label whose beat is closest at or before the requested beat. This handles the case where chordify produces an offset that falls between two WiR label positions.

---

## Import Pipeline Changes

**File:** `apps/exercises/management/commands/import_bach_phrases.py`

### `_build_roman_analysis_overrides()` signature change

Add `bwv: str` parameter.

### Early abort

```python
r_num = bwv_to_riemenschneider(bwv)
if r_num is None:
    raise CommandError(
        f"BWV {bwv} has no Riemenschneider mapping — "
        f"cannot import in roman mode. "
        f"Only standalone chorales in the WiR corpus are supported."
    )
```

### RN lookup per slice

```python
wir_label = lookup_rn(r_num, element.measureNumber, float(element.beat))
# music21 RN preserved for audit
m21_figure = romanNumeralFromChord(element, global_key).figure

overrides.append({
    "offset": abs_offset,
    "roman_numeral": wir_label,       # None for NCT slices
    "raw_roman_numeral": m21_figure,  # always populated
    "raw_figured_bass": None,
    "figured_bass": None,
    ...
})
```

### NCT slices

`roman_numeral=None` for beats where WiR has no label. Slice is still emitted so figured bass can be attached. Frontend renders nothing for null RN (existing behaviour).

### `bwv` derivation

The import command already derives the BWV from the music21 corpus filename (e.g. `bwv269.xml` → `"269"`). Pass this through to `_build_roman_analysis_overrides()`.

---

## No Schema Changes

`AnalysisLayer` in `apps/exercises/umto.py` already has:
- `roman_numeral: Optional[str]` — WiR label (or None for NCT)
- `raw_roman_numeral: Optional[str]` — music21 output
- `raw_figured_bass: Optional[str]`
- `figured_bass: Optional[str]`

No migrations needed.

---

## Testing

### `apps/exercises/tests/test_wir_corpus.py`

Tests against the real `chorales.json` (not mocked — the data file is the contract):

| Test | Input | Expected |
|---|---|---|
| Anacrusis lookup | `lookup_rn(1, 0, 3.0)` | `"I"` |
| Mid-measure label | `lookup_rn(1, 1, 2.0)` | `"IV6"` |
| NCT beat | `lookup_rn(1, 3, 1.5)` | `None` |
| Unknown chorale | `lookup_rn(999, 1, 1.0)` | `None` |
| BWV lookup hit | `bwv_to_riemenschneider("269")` | `1` |
| BWV lookup miss | `bwv_to_riemenschneider("99999")` | `None` |

### `scripts/tests/test_convert_wir_corpus.py`

Parser unit tests (embedded WiR text, no filesystem):

- Anacrusis `m0 b3 G: I` → `measure=0, beat=3.0, label="I"`
- Half-beat `b2.5` parsed correctly
- Key-change token `G:` skipped
- Repeat barlines `||`, `:||` skipped
- `bVI` label not confused with beat marker
- Variant `m11var1` → stored as `variant` field

### `apps/exercises/tests/test_import_bach_phrases.py` (extend existing)

- Import R1 in `roman` mode → first `AnalysisSlice.content.roman_numeral == "I"`
- Import R1 → `AnalysisSlice.content.raw_roman_numeral` populated with music21 figure
- NCT slice (m3 b1.5) → `roman_numeral=None`, `figured_bass` still populated
- Import with unmapped BWV raises `CommandError`

---

## File Map

| File | Change |
|---|---|
| `scripts/convert_wir_corpus.py` | New — one-time conversion script |
| `scripts/tests/test_convert_wir_corpus.py` | New — parser unit tests |
| `data/when_in_rome/chorales.json` | New — generated by conversion script, checked in |
| `data/when_in_rome/bwv_to_riemenschneider.json` | New — generated by conversion script, checked in |
| `apps/exercises/utils/wir_corpus.py` | New — lookup module |
| `apps/exercises/tests/test_wir_corpus.py` | New — lookup tests |
| `apps/exercises/management/commands/import_bach_phrases.py` | Modified — `_build_roman_analysis_overrides()` uses WiR |

---

## Future Work (Out of Scope Here)

- **Approach 3:** Merge RN + FB builders into a single pass keyed on WiR label offsets (eliminates chordify for RN entirely)
- **Drop `raw_roman_numeral`:** Once WiR is proven in production, remove the music21 audit field via migration
- **Variant readings at runtime:** Expose `variant` field to let exercises show alternate analyst interpretations
- **Non-chorale WiR corpora:** WiR also covers Mozart, Beethoven, etc. — same architecture applies
