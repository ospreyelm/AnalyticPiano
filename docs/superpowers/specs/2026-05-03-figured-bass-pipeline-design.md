# Figured Bass Pipeline — Design Spec

**Date:** 2026-05-03  
**Branch:** `docs/taxonomy-source-of-truth-viz`  
**Status:** Historical — superseded in part by current implementation,
[docs/FIGURED_BASS.md](../../FIGURED_BASS.md), and
[docs/music-theory-canon.md](../../music-theory-canon.md)

> **Stale-theory warning:** Early versions of this spec incorrectly state that
> every tritone receives a `+` marker. Current HarmonyLab figured-bass canon
> distinguishes augmented fourths (`4+`) from diminished fifths (`5°`).

---

## Overview

Add a `mode:figures` parallel curriculum track to HarmonyLab alongside the existing `mode:roman` track. Same Bach chorale corpus, units 9–18, but students identify figured bass instead of Roman numerals. A second `mode:figures_unabbreviated` variant shows the complete interval stack (e.g. `7/5/3`) before abbreviation conventions are introduced.

This is **Approach A** — a thin parallel track where each exercise stores only the analysis relevant to its mode. **Approach B** (every exercise stores both Roman numeral and figured bass analysis, enabling cross-validation) is the documented upgrade path once both tracks are proven independently.

---

## Figured Bass Theory (ground rules)

Figured bass = generic interval numbers above the bass note, with accidentals only where the pitch deviates from the diatonic key.

**Chromatic prefix rules:**
- Pitch matches diatonic scale of the key → no prefix
- Pitch raised from diatonic → `#`
- Pitch lowered from diatonic → `b`
- A tritone is labeled by generic interval: augmented fourth → `4+`;
  diminished fifth → `5°`.

Use quality symbols where HarmonyLab figured-bass canon requires them, such as
`+` for augmented intervals and `°` for diminished intervals.

**Abbreviation rules (Kellner 1732):**

| Unabbreviated (nums only) | Abbreviated |
|---------------------------|-------------|
| `8/5/3`                   | `` (nothing) |
| `6/3` or `6/3/3`          | `6`         |
| `8/6/4` or `6/4`          | `6/4`       |
| `7/5/3`                   | `7`         |
| `6/5/3`                   | `6/5`       |
| `6/4/3`                   | `4/3`       |
| `6/4/2`                   | `4/2`       |
| `5/4/3`                   | `5/4`       |
| `9/5/3`                   | `9`         |
| `9/7/3`                   | `9/7`       |

Chromatic prefixes are preserved on the abbreviated form: `b6/5`, `#4/3`, `4+/2`, etc. Unrecognized stacks pass through unabbreviated (safe fallback — never lose data).

**Suspension figures** — multi-beat figures spanning two chords are stored as a single slice value with a dash separator. The figure is attached to the onset of the dissonance, not the resolution:

| Figure | Meaning |
|--------|---------|
| `4-3`  | `8/5/4` resolving to `8/5/3` |
| `7-6`  | `8/7/3` resolving to `8/6/3` |
| `9-8`  | `9/5/3` resolving to `8/5/3` |
| `4+/3` | augmented sixth (aug. 6) |
| `6/4+` | augmented second above bass (aug. 2) |

The Python calculator detects these by comparing consecutive chords at adjacent offsets — if the interval resolves by step, emit the suspension figure as a single token on the first offset's slice.

---

## Architecture: Approach A (current sprint)

Each `mode:figures` exercise is a **separate Exercise row** from `mode:roman` — same chorale source, different analysis content. `mode:figures` exercises store figured bass fields; `mode:roman` exercises store Roman numeral fields. No cross-population.

### Upgrade path to Approach B

Approach B: every exercise (both modes) stores `raw_roman_numeral`, `raw_figured_bass`, and `figured_bass` — enabling cross-validation between analysis systems. The figured bass suffix is the same as the Roman numeral suffix (V⁶₅ = figure `6/5`), so independently-computed figures can confirm or correct ambiguous Roman numeral labels (especially suspensions and non-standard sonorities where `romanNumeralFromChord()` is unreliable). Implement B as a separate spec once Approach A is end-to-end verified.

---

## Section 1: Data Model

### `AnalysisLayer` schema (`apps/exercises/umto.py`)

Add one new field:

```python
raw_figured_bass: Optional[str] = None  # unabbreviated stack: "8/5/3", "7/5/3", "6/4/2"
figured_bass: Optional[str] = None      # abbreviated per Kellner: "", "7", "4/2"
```

`figured_bass` already exists in the schema (always `null` today). `raw_figured_bass` is new. Both populated at import time for `mode:figures` and `mode:figures_unabbreviated` exercises only (Approach A).

No Django migration required — UMTO data lives in a JSON field.

### Taxonomy JSON (`music_theory_taxonomy.json`)

Each unit 9–18 gains two new analysis families alongside `analysis.roman`:

```json
"analysis": {
  "roman": { "cumulative": [...], "new": [...] },
  "figured_bass": {
    "cumulative": [
      {"value": "",  "display": "5/3"},
      {"value": "7", "display": "7"}
    ],
    "new": [
      {"value": "",  "display": "5/3"},
      {"value": "7", "display": "7"}
    ]
  },
  "figured_bass_unabbreviated": {
    "cumulative": [
      {"value": "8/5/3", "display": "8/5/3"},
      {"value": "7/5/3", "display": "7/5/3"}
    ],
    "new": [
      {"value": "8/5/3", "display": "8/5/3"},
      {"value": "7/5/3", "display": "7/5/3"}
    ]
  }
}
```

`value=""` for root-position triads (abbreviated form is nothing); `display="5/3"` ensures dropdowns never show a blank option.

**Proposed unit mapping for `figured_bass` family (to be hand-authored):**

| Unit | Title | New figures | Notes |
|------|-------|-------------|-------|
| 9  | Tonic & dominant | `""`, `7` | Root position triads + dom7 |
| 10 | First inversions | `6`, `6/5` | `6` = first inversion triad; `6/5` = first inversion V7 |
| 11 | Pre-dominants | *(none)* | Pre-dominant RNs (ii, IV, ii6) use figures already in cumulative (`""`, `6`) |
| 12 | Second inversions | `6/4`, `4/3`, `4/2` | All three second-position seventh inversions + cadential 6/4 |
| 13 | Rule of the Octave | `#6/4/3` | Chromatic figure for raised scale degree in Rule of Octave context |
| 14–18 | Chromaticism | `b6`, `#4`, `4+`, `b6/5`, suspension figures (`4-3`, `7-6`, `9-8`) | Units 14–18 TBD in detail |

**Parallel RN taxonomy corrections** (units 10–13 need updating alongside figured bass):

| Unit | RN additions needed |
|------|---------------------|
| 10 | Add `V65` (`V6/5`) — first inversion dominant seventh |
| 11 | Add `ii65` (`ii6/5`), `ii7` — pre-dominant seventh chords |
| 12 | Add `Cad64` (cadential 6/4), `V43` (`V4/3`), `V42` (`V4/2`) |
| 13 | Add `V43/V` (`V4/3` of V) — secondary dominant in Rule of Octave |

`figured_bass_unabbreviated` entries mirror the same units but use raw stacks as values.

`TaxonomyReader` requires no code changes — `get_cumulative_values(unit_n, "figured_bass")` works for any family name.

---

## Section 2: Python Figured Bass Calculator

### New file: `apps/exercises/utils/figured_bass.py`

```python
def compute_figured_bass(chord_element, key) -> tuple[str, str]:
    """
    Returns (raw_figured_bass, figured_bass).
    raw_figured_bass: complete stack descending, e.g. "8/5/3", "7/5/3", "6/4/2"
    figured_bass: abbreviated per Kellner, e.g. "", "7", "4/2"
    """

def abbreviate_figured_bass(raw: str) -> str:
    """Apply Kellner abbreviation rules to a raw stack string."""
```

### `compute_figured_bass` algorithm

1. Get bass pitch: `chord_element.bass()`
2. Get key's diatonic pitch classes from `key.pitches`
3. For each upper pitch in chord:
   - Compute generic interval number: `music21.interval.Interval(bass, upper).generic.directed`
   - Reduce to within octave + handle octave (8) specially
   - Compare upper pitch letter+accidental to diatonic scale:
     - Diatonic match → no prefix
     - Raised → `#`
     - Lowered → `b`
   - Check tritone: if semitone distance is 6, use the generic interval to
     choose `+` for augmented fourth or `°` for diminished fifth
4. Deduplicate intervals (same number may appear multiple times in 4-voice chords)
5. Sort descending by number
6. `raw_figured_bass` = join with `/`
7. `figured_bass` = `abbreviate_figured_bass(raw_figured_bass)`

### `abbreviate_figured_bass` algorithm

Strip prefixes, match numeric pattern against lookup table, reattach prefixes to abbreviated form. Unrecognized patterns pass through unchanged.

---

## Section 3: Import Pipeline

### `apps/exercises/management/commands/import_bach_phrases.py`

New function alongside `_build_roman_analysis_overrides`:

```python
def _build_figured_bass_overrides(phrase_score, global_key) -> list:
    """Analyze phrase and return UMTO analysis_overrides with figured bass.
    Stores raw_figured_bass (unabbreviated) and figured_bass (abbreviated).
    Targeting happens at request time in generate_exercise_context.
    """
```

Same structure as `_build_roman_analysis_overrides`: `chordify()`, iterate offsets, per-offset call `compute_figured_bass(chord, key)`, store both fields. `roman_numeral` and `raw_roman_numeral` left `null` on figured bass exercises.

Call site routing (replacing current unified call):

```python
if mode in ('roman', 'matching'):
    analysis_overrides = _build_roman_analysis_overrides(phrase_score, m21_key, unit_nums)
elif mode in ('figures', 'figures_unabbreviated'):
    analysis_overrides = _build_figured_bass_overrides(phrase_score, m21_key)
```

Both `figures` and `figures_unabbreviated` call the same function and produce identical stored data — the difference is only in which field is targeted at request time and which `analysisType` the JS uses.

`--mode` gains one new choice: `figures_unabbreviated` (joins existing `figures`).

`create_unit_playlist` needs `figures_unabbreviated` added to its `--mode` choices list (currently `["roman", "play", "figures", "matching"]`).

---

## Section 4: `generate_exercise_context` (`lab/views.py`)

Currently hardcoded to `family="roman"`. Add mode detection from exercise skill tags:

```python
if "mode:figures_unabbreviated" in skill_tags:
    family = "figured_bass_unabbreviated"
    raw_field = "raw_figured_bass"
    targeted_field = "raw_figured_bass"
elif "mode:figures" in skill_tags:
    family = "figured_bass"
    raw_field = "raw_figured_bass"
    targeted_field = "figured_bass"
else:
    family = "roman"
    raw_field = "raw_roman_numeral"
    targeted_field = "roman_numeral"
```

Targeting loop: check `slice["content"][raw_field] in cumulative` → write to `slice["content"][targeted_field]`, set `is_target`.

The cadential 6/4 contextual rewrite block is Roman-only — skip entirely for figured bass families.

`analysisPolicy` payload gains `"family"` key (`"figured_bass"` or `"figured_bass_unabbreviated"`) so JS knows which `analysisType` and field to read.

---

## Section 5: JS Changes (`lab/static/js/src/`)

### `models/exercise_definition.js`

**Answer extraction** — add branch before existing `roman_numeral` check:

```javascript
if (analysisType === "figured_bass_unabbreviated")
  answer = slice.content.raw_figured_bass;
else if (slice.content.roman_numeral) ...
else if (slice.content.figured_bass) ...
```

**`buildChoices` fallbacks:**

```javascript
var fallbacks = analysisType === "figured_bass"
  ? ["", "6", "6/4", "7", "6/5", "4/3", "4/2"]
  : analysisType === "figured_bass_unabbreviated"
  ? ["8/5/3", "6/3", "8/6/4", "7/5/3", "6/5/3", "6/4/3", "6/4/2"]
  : // ... existing roman fallbacks
```

**`displayMap`** from `analysisPolicy` maps `"" → "5/3"` — handled automatically by existing displayMap logic, no code change needed.

### `components/music/stave_notater.js`

For `mode:figures` exercises, draw `figured_bass` value below bass staff in same position as Roman numerals. Read field based on `analysisType` — no structural change, just field selection.

No VexFlow changes. No new JS files.

---

## Section 6: Testing

### `apps/exercises/tests/test_figured_bass.py` (new)

- `A3 C#4 E4 A4` in A major → raw=`8/5/3`, abbreviated=``
- Root position triad in C major: no accidentals → `8/5/3` → ``
- First inversion triad in G major: `6/3` → `6`
- Dominant seventh: `7/5/3` → `7`
- `6/5/3` → `6/5`, `6/4/3` → `4/3`, `6/4/2` → `4/2`
- Chromatic raised: `#3`, `#4` prefix
- Chromatic lowered: `b6`, `b3` prefix
- Natural tritone (e.g. B above F in C major): `4+`
- Unrecognized stack passthrough: no data loss

### `apps/exercises/tests/test_taxonomy_reader.py`

Assert `get_cumulative_values("9", "figured_bass")` returns `{"", "7"}` once taxonomy updated.

### `apps/exercises/tests/test_views_analysis_policy.py`

Assert `generate_exercise_context` returns `analysisPolicy["family"] == "figured_bass"` for `mode:figures` exercise.

---

## Future Work (Approach B)

Once Approach A is end-to-end verified:

1. Populate `raw_figured_bass` + `figured_bass` on all `mode:roman` exercises (backfill command)
2. Use figured bass suffix to cross-validate ambiguous `raw_roman_numeral` values — especially suspensions and passing chords where music21's `romanNumeralFromChord()` produces garbled output
3. Single import run produces exercises usable in both `mode:roman` and `mode:figures` playlists

## Future Work (rendering)

Flat string display in identification slots (`6/5`) is a stopgap. Upgrade path: HTML-stacked rendering (CSS flex-column) for both Roman numerals and figured bass slots. Applies to all analysis slot UI, not just figured bass.
