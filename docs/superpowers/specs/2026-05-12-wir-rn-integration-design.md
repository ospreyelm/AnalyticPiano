# When in Rome RN Integration — Design

**Date:** 2026-05-12
**Status:** Design — ready for implementation planning
**Author:** avnerdorman

---

## Summary

Replace music21's `romanNumeralFromChord()` as the source of `roman_numeral` in `AnalysisSlice` objects with human-annotated labels from the When in Rome (WiR) corpus. WiR covers all 371 Riemenschneider chorales with beat-level RN labels by human analysts. music21 RN output is preserved in `raw_roman_numeral` for audit/comparison. No UMTO schema changes required except adding `local_key` to `AnalysisLayer`.

---

## Motivation

music21's RN analysis has two systematic problems:

1. **NCT pollution** — `chordify()` verticalises passing tones and suspensions into fake chords, producing labels like `I742`, `IV42` that have no harmonic meaning.
2. **Global key only** — no modulation or tonicisation detection; a secondary dominant in D minor gets labelled as if the piece never left G major.

WiR solves both: human analysts simply don't label NCT beats, and they write explicit key changes (`d:`, `D:`) when tonicisation occurs. The result is harmonically correct, NCT-free labelling for every chorale we teach.

Figured bass is computed independently (bass + intervals, no RN reasoning) and is unaffected by this change.

**Pedagogical value of omitting NCT slices:** NCT beats are shown in the score (student sees full musical context) but no analysis slot is rendered. Only harmonically meaningful beats get slots. Student learns implicitly which notes are structural vs. decorative, without being told explicitly. The human analyst already made that judgment call.

---

## Decisions

| Question | Decision |
|---|---|
| What fills `roman_numeral`? | WiR label (e.g. `"V6"`, `"i"`) |
| What fills `local_key`? | Active key from WiR at that offset (e.g. `"d"`, `"G"`) |
| What fills `raw_roman_numeral`? | music21 output (preserved for audit) |
| New schema field for WiR? | Yes — `local_key: Optional[str]` added to `AnalysisLayer` |
| Missing WiR entry (unknown BWV)? | `CommandError` — hard abort, no exercise created |
| NCT slices (no WiR label at beat)? | Slice omitted entirely from overrides list |
| `--riemenschneider N` provided? | Use directly — no map lookup needed |
| BWV → Riemenschneider map? | Only used when loading by BWV; auto-derived from WiR headers |
| Cantata movements (e.g. bwv1.6)? | Not in WiR's 371 — blocked by `CommandError` |
| Variant readings? | Stored in JSON, not used at import time (future use) |
| Existing `try/except` around override builder? | Removed for roman/matching modes — hard fail only |

---

## Scope

**In scope:**
- One-time WiR corpus download and JSON conversion
- `bwv_to_riemenschneider.json` mapping (auto-derived from WiR `.txt` headers)
- `apps/exercises/utils/wir_corpus.py` lookup module
- `local_key` field added to `AnalysisLayer` in `umto.py`
- Changes to `_build_roman_analysis_overrides()` in `import_bach_phrases.py`
- Remove `try/except` swallow for roman/matching modes in import command
- `data/when_in_rome/README.md` with provenance, license, citation
- Tests for corpus module and conversion parser

**Out of scope:**
- WiR integration for non-chorale exercises
- Using WiR variant readings at runtime
- Dropping `raw_roman_numeral` from schema (deferred — after WiR proven in production)
- Merging RN and FB override builders into a single pass (future work)
- NCT detection / labelling (separate future work)

---

## Data Layer

### WiR corpus JSON

**Location:** `data/when_in_rome/chorales.json`

Keyed by Riemenschneider number (string). Built once by `scripts/convert_wir_corpus.py`.

```json
{
  "1": {
    "title": "Aus meines Herzens Grunde",
    "bwv": "269",
    "time_signature": "3/4",
    "labels": [
      {"measure": 0, "beat": 3.0, "label": "I",    "local_key": "G"},
      {"measure": 1, "beat": 1.0, "label": "I",    "local_key": "G"},
      {"measure": 1, "beat": 2.0, "label": "IV6",  "local_key": "G"},
      {"measure": 1, "beat": 3.0, "label": "V6",   "local_key": "G"}
    ]
  }
}
```

`local_key` is tracked as a running state across the parse: starts as the global key from the header, updates whenever a key-change token (e.g. `d:`) is encountered. Every label object carries the active key at its beat.

Variant readings stored as optional field:
```json
{"measure": 11, "beat": 2.0, "label": "iii6", "local_key": "G", "variant": "I6/4"}
```

### BWV → Riemenschneider map

**Location:** `data/when_in_rome/bwv_to_riemenschneider.json`

Flat object `{"269": 1, "253": 2, ...}`. Auto-derived from `BWV:` header in each `.txt` file. No hand-curation. Used only when importing by BWV — `--riemenschneider N` bypasses it entirely.

### Provenance file

**Location:** `data/when_in_rome/README.md`

Must contain: source URL, commit SHA of downloaded WiR repo, license (CC BY-SA), citation per WiR README requirements, and date of conversion.

### WiR corpus source

`https://github.com/MarkGotham/When-in-Rome`, directory `Corpus/Bach_Chorales/`. 371 `.txt` files in RomanText format. License: CC BY-SA.

---

## Conversion Script

**Location:** `scripts/convert_wir_corpus.py`

One-time script. Not part of regular import pipeline. Run once after downloading WiR, commit resulting JSON.

**Responsibilities:**
- Parse all 371 `.txt` files
- Extract `BWV:`, `Title:`, `Time Signature:` from header lines
- Track running `local_key` state across each file, updating on key-change tokens
- Build label list: `{measure, beat, label, local_key}` per harmonic event
- Store variant readings on label objects
- Write `chorales.json` and `bwv_to_riemenschneider.json`
- Validate output: exactly 371 chorales, no duplicate Riemenschneider keys, labels sorted by (measure, beat)

**Parser rules (fully specified):**

| Pattern | Action |
|---|---|
| Lines matching `^(Note\|Composer\|BWV\|Title\|Analyst\|Proofreader\|Time Signature\|Form):` | Skip (header) |
| Lines matching `^m(\d+)(var\d+)?\s+(.*)` | Parse as measure line |
| Token matching `/^b\d/` | Beat marker — update `curBeat` (e.g. `b2.5` → 2.5) |
| Token matching `/^[A-Ga-g][#b-]?:$/` | Key-change token — update `local_key`, do not emit label |
| Token `\|\|`, `:\|\|`, `\|` | Repeat barline — skip |
| Any other token | RN label at current `(measure, curBeat)` |
| Line with `var\d+` suffix | Store as `variant` field on the matching main label at same `(measure, curBeat)`. If no main label exists at that position, create a label object with `label: null, variant: "..."`. |
| `curBeat` default per measure line | 1.0 |

---

## Schema Change

**File:** `apps/exercises/umto.py`

Add one field to `AnalysisLayer`:

```python
class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None
    local_key: Optional[str] = None          # NEW: active key at this slice, e.g. "G", "d"
    raw_figured_bass: Optional[str] = None
    figured_bass: Optional[str] = None
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None
```

No migration — `Optional` with default `None`, backward compatible with all existing exercises.

---

## Lookup Module

**File:** `apps/exercises/utils/wir_corpus.py`

Loaded once at module level (JSON read on first import).

```python
def lookup(riemenschneider: int, measure: int, beat: float) -> dict | None:
    """Return {label, local_key} for exact (measure, beat) match.
    Returns None if chorale unknown or no label at this exact offset.
    Beat comparison uses abs(stored_beat - beat) < 1e-6 to handle float imprecision."""

def has_chorale(riemenschneider: int) -> bool:
    """Return True if WiR corpus contains data for this Riemenschneider number."""

def bwv_to_riemenschneider(bwv: str) -> int | None:
    """Return Riemenschneider number for a BWV string, or None if not found."""
```

**Lookup semantics: exact match only.** No "closest at or before" fallback. A beat not present in WiR returns `None` — that beat is an NCT and the slice is omitted. Float comparison uses `abs(stored_beat - beat) < 1e-6` throughout.

---

## Import Pipeline Changes

**File:** `apps/exercises/management/commands/import_bach_phrases.py`

### Remove `try/except` swallow

The existing `try/except` around `_build_roman_analysis_overrides()` that logs a warning and continues must be removed for `roman` and `matching` modes. If WiR lookup fails, the command aborts with `CommandError`. No exercise is created.

### `_build_roman_analysis_overrides()` signature change

Add `riemenschneider: int` parameter (either from `--riemenschneider` arg directly, or derived via `bwv_to_riemenschneider(bwv)`).

### Early abort on unknown chorale

```python
# riemenschneider is already known at this point (from --riemenschneider arg or BWV lookup)
if not wir_corpus.has_chorale(riemenschneider):
    raise CommandError(
        f"Riemenschneider {riemenschneider} not found in When in Rome corpus. "
        f"Only standalone chorales (1–371) are supported in roman mode."
    )
```

### RN lookup per slice — omit NCT slices

```python
result = wir_corpus.lookup(riemenschneider, element.measureNumber, float(element.beat))
if result is None:
    continue  # NCT beat — no WiR label — omit slice entirely

wir_label = result["label"]
local_key  = result["local_key"]

# music21 RN preserved for audit
m21_figure = romanNumeralFromChord(element, global_key).figure

overrides.append({
    "offset": abs_offset,
    "content": {
        "roman_numeral": wir_label,
        "local_key": local_key,
        "raw_roman_numeral": m21_figure,
        "raw_figured_bass": None,
        "figured_bass": None,
        "pop_symbol": None,
        "functional_label": None,
    },
    "unit_tags": list(unit_tags),
})
```

### `riemenschneider` derivation

- If `--riemenschneider N` provided: use directly (already the common case).
- If loading by BWV: derive via `bwv_to_riemenschneider(bwv)`. If not found: `CommandError`.

---

## No Frontend Changes Required

NCT slices are omitted entirely — no slice emitted, no null `roman_numeral` reaching the frontend. The fallback chain in `exercise_definition.js` line 471 is never triggered because roman-mode exercises don't populate `figured_bass` fields anyway (separate builder).

---

## Testing

### `apps/exercises/tests/test_wir_corpus.py`

Tests against the real `chorales.json`:

| Test | Input | Expected |
|---|---|---|
| Anacrusis lookup | `lookup(1, 0, 3.0)` | `{"label": "I", "local_key": "G"}` |
| Mid-measure label | `lookup(1, 1, 2.0)` | `{"label": "IV6", "local_key": "G"}` |
| NCT beat (exact miss) | `lookup(1, 3, 1.5)` | `None` |
| Unknown chorale | `lookup(999, 1, 1.0)` | `None` |
| BWV lookup hit | `bwv_to_riemenschneider("269")` | `1` |
| BWV lookup miss | `bwv_to_riemenschneider("99999")` | `None` |
| Key change in chorale | lookup at tonicised beat | `local_key` reflects modulation |

### `scripts/tests/test_convert_wir_corpus.py`

Parser unit tests (embedded WiR text, no filesystem):

- `m0 b3 G: I` → `{measure:0, beat:3.0, label:"I", local_key:"G"}`
- `b2.5` beat marker parsed correctly
- Key-change token `G:` skipped as label, updates `local_key`
- Key-change `d:` → subsequent labels carry `local_key: "d"`
- Repeat barlines `||`, `:||` skipped
- `bVI` not confused with beat marker (`/^b\d/` rule)
- `m11var1` → stored as `variant`, not main label
- Output: 371 chorales, sorted labels, no duplicate Riemenschneider keys

### `apps/exercises/tests/test_import_bach_phrases.py` (extend)

- Import R1 roman mode → first slice `roman_numeral="I"`, `local_key="G"`
- Import R1 → `raw_roman_numeral` populated with music21 figure
- NCT beat (m3 b1.5) → no `AnalysisSlice` emitted at that offset
- Import with unmapped BWV → `CommandError`
- Import with `--riemenschneider 999` (not in WiR) → `CommandError`
- Import a chorale with a tonicisation (e.g. Riemenschneider 10, which modulates) → slice at tonicised beat has `roman_numeral` set to WiR label and `local_key` reflecting the secondary key, not the global key

---

## File Map

| File | Change |
|---|---|
| `scripts/convert_wir_corpus.py` | New — one-time conversion script |
| `scripts/tests/test_convert_wir_corpus.py` | New — parser unit tests |
| `data/when_in_rome/chorales.json` | New — generated, checked in |
| `data/when_in_rome/bwv_to_riemenschneider.json` | New — generated, checked in |
| `data/when_in_rome/README.md` | New — provenance, license, citation |
| `apps/exercises/utils/wir_corpus.py` | New — lookup module |
| `apps/exercises/tests/test_wir_corpus.py` | New — lookup tests |
| `apps/exercises/umto.py` | Modified — add `local_key` to `AnalysisLayer` |
| `apps/exercises/umto_schema.json` | Regenerated — run `python manage.py make_umto_schema` after adding `local_key` |
| `apps/exercises/management/commands/import_bach_phrases.py` | Modified — WiR lookup, remove try/except swallow |

---

## Future Work (Out of Scope Here)

- **NCT detection / labelling:** Now that NCT slices are clearly identified (no WiR label), a future pass can mark them explicitly for visual distinction in the score
- **Approach 3:** Merge RN + FB builders into single pass keyed on WiR label offsets (eliminates chordify for RN entirely)
- **Drop `raw_roman_numeral`:** After WiR proven in production, remove music21 audit field via migration
- **Variant readings at runtime:** Expose `variant` field for alternate analyst interpretations
- **Non-chorale WiR corpora:** WiR covers Mozart, Beethoven, etc. — same architecture applies
