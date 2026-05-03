# Figured Bass Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `mode:figures` and `mode:figures_unabbreviated` parallel curriculum tracks to HarmonyLab so students can identify figured bass symbols from Bach chorales, units 9–18.

**Architecture:** Each figured bass exercise is a separate Exercise row (Approach A). Import computes `raw_figured_bass` (unabbreviated stack) and `figured_bass` (abbreviated) at import time and stores them on `AnalysisLayer`. At request time, `generate_exercise_context` branches on the mode tag to build an `analysisPolicy` with `family="figured_bass"` and target slices accordingly. The JS layer already reads `slice.content.figured_bass`; only fallback lists and answer extraction need extension.

**Tech Stack:** Python/Django, music21, Pydantic (UMTO schema), JavaScript (exercise_definition.js), JSON (taxonomy), pytest

---

## File Map

| File | Change |
|------|--------|
| `apps/exercises/umto.py` | Add `raw_figured_bass` field to `AnalysisLayer` |
| `apps/exercises/utils/figured_bass.py` | **New** — Python figured bass calculator |
| `apps/exercises/tests/test_figured_bass.py` | **New** — unit tests for calculator |
| `apps/exercises/management/commands/import_bach_phrases.py` | Add `_build_figured_bass_overrides()`, route `mode:figures*` |
| `apps/exercises/management/commands/create_unit_playlist.py` | Add `figures_unabbreviated` to `--mode` choices |
| `music_theory_taxonomy.json` | Add `analysis.figured_bass` + `analysis.figured_bass_unabbreviated` for units 9–13; correct `analysis.roman` for units 10–13 |
| `lab/views.py` | Branch `generate_exercise_context` on mode tag; inject `analysisType` into payload |
| `apps/exercises/tests/test_generate_exercise_context.py` | Add figured bass policy tests |
| `lab/static/js/src/models/exercise_definition.js` | Add `figured_bass_unabbreviated` to answer extraction + buildChoices fallbacks |

---

## Task 1: Add `raw_figured_bass` to `AnalysisLayer`

**Files:**
- Modify: `apps/exercises/umto.py:53-58`
- Test: `apps/exercises/tests/test_umto_contract.py`

- [ ] **Step 1: Write failing test**

Open `apps/exercises/tests/test_umto_contract.py` and add:

```python
def test_analysis_layer_has_raw_figured_bass():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer()
    assert hasattr(layer, "raw_figured_bass")
    assert layer.raw_figured_bass is None

def test_analysis_layer_raw_figured_bass_stores_value():
    from apps.exercises.umto import AnalysisLayer
    layer = AnalysisLayer(raw_figured_bass="7/5/3", figured_bass="7")
    assert layer.raw_figured_bass == "7/5/3"
    assert layer.figured_bass == "7"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python manage.py test apps.exercises.tests.test_umto_contract --verbosity=2 2>&1 | tail -20
```

Expected: `AttributeError` or `ValidationError` on `raw_figured_bass`.

- [ ] **Step 3: Add the field**

In `apps/exercises/umto.py`, update `AnalysisLayer` (currently lines 53–58):

```python
class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None  # unfiltered music21 output; durable record
    raw_figured_bass: Optional[str] = None   # unabbreviated stack: "8/5/3", "7/5/3"
    figured_bass: Optional[str] = None       # abbreviated per Kellner: "", "7", "4/2"
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test apps.exercises.tests.test_umto_contract --verbosity=2 2>&1 | tail -20
```

Expected: PASS.

- [ ] **Step 5: Run full suite to check regressions**

```bash
python manage.py test apps.exercises --verbosity=1 2>&1 | tail -10
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/tests/test_umto_contract.py
git commit -m "feat: add raw_figured_bass field to AnalysisLayer"
```

---

## Task 2: Python figured bass calculator — `abbreviate_figured_bass`

**Files:**
- Create: `apps/exercises/utils/figured_bass.py`
- Create: `apps/exercises/tests/test_figured_bass.py`

- [ ] **Step 1: Write failing tests for abbreviation**

Create `apps/exercises/tests/test_figured_bass.py`:

```python
import pytest
from apps.exercises.utils.figured_bass import abbreviate_figured_bass


def test_root_position_triad():
    assert abbreviate_figured_bass("8/5/3") == ""

def test_root_position_triad_without_octave():
    assert abbreviate_figured_bass("5/3") == ""

def test_first_inversion_triad():
    assert abbreviate_figured_bass("6/3") == "6"

def test_first_inversion_triad_with_double():
    assert abbreviate_figured_bass("6/3/3") == "6"

def test_second_inversion_triad():
    assert abbreviate_figured_bass("6/4") == "6/4"

def test_root_position_seventh():
    assert abbreviate_figured_bass("7/5/3") == "7"

def test_first_inversion_seventh():
    assert abbreviate_figured_bass("6/5/3") == "6/5"

def test_second_inversion_seventh():
    assert abbreviate_figured_bass("6/4/3") == "4/3"

def test_third_inversion_seventh():
    assert abbreviate_figured_bass("6/4/2") == "4/2"

def test_five_four_three():
    assert abbreviate_figured_bass("5/4/3") == "5/4"

def test_nine():
    assert abbreviate_figured_bass("9/5/3") == "9"

def test_nine_seven():
    assert abbreviate_figured_bass("9/7/3") == "9/7"

def test_chromatic_prefix_preserved_on_abbreviated():
    # b6/5/3 → b6/5
    assert abbreviate_figured_bass("b6/5/3") == "b6/5"

def test_chromatic_prefix_on_third():
    # 8/5/#3 → # (just the accidental on the third, root position)
    assert abbreviate_figured_bass("8/5/#3") == "#"

def test_chromatic_prefix_flat_third():
    assert abbreviate_figured_bass("8/5/b3") == "b"

def test_unknown_stack_passthrough():
    # Unrecognized stacks pass through unabbreviated — no data loss
    assert abbreviate_figured_bass("9/8/6/4") == "9/8/6/4"

def test_empty_string_passthrough():
    assert abbreviate_figured_bass("") == ""
```

- [ ] **Step 2: Run to confirm failure**

```bash
python manage.py test apps.exercises.tests.test_figured_bass --verbosity=2 2>&1 | tail -20
```

Expected: `ModuleNotFoundError` — file doesn't exist yet.

- [ ] **Step 3: Create `apps/exercises/utils/figured_bass.py` with `abbreviate_figured_bass`**

```python
"""
Figured bass calculator utilities.

compute_figured_bass() — derives raw and abbreviated figured bass from a music21
chord + key at import time.

abbreviate_figured_bass() — applies Kellner (1732) abbreviation rules to a raw
interval stack string (e.g. "7/5/3" → "7").
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Abbreviation table: maps frozenset of numeric parts → abbreviated form.
# Chromatic prefixes on individual intervals are stripped for matching, then
# reattached to the abbreviated output.
# ---------------------------------------------------------------------------

# Each entry: (sorted-descending tuple of nums without prefixes, abbreviated form).
# Chromatic prefixes are reattached after lookup by matching interval numbers.
# Empty string means "nothing" (root-position triad convention).
_ABBREV_TABLE = [
    # Root-position triads
    (("8", "5", "3"), ""),
    (("5", "3"),      ""),
    # Chromatic root-position triad: only an accidental (on the 3rd or 5th)
    # handled separately below
    # First-inversion triad
    (("6", "3", "3"), "6"),
    (("6", "3"),      "6"),
    # Second-inversion triad
    (("8", "6", "4"), "6/4"),
    (("6", "4"),      "6/4"),
    # Root-position seventh
    (("8", "7", "5", "3"), "7"),
    (("7", "5", "3"),      "7"),
    # First-inversion seventh
    (("6", "5", "3"), "6/5"),
    # Second-inversion seventh
    (("6", "4", "3"), "4/3"),
    # Third-inversion seventh
    (("6", "4", "2"), "4/2"),
    # 5/4 suspension resolution chord
    (("8", "5", "4"), "5/4"),
    (("5", "4", "3"), "5/4"),
    # Ninth chords
    (("9", "5", "3"), "9"),
    (("9", "7", "3"), "9/7"),
]

_ABBREV_MAP = {k: v for k, v in _ABBREV_TABLE}


def _split_interval(token: str) -> tuple[str, str]:
    """Split a token like 'b6', '#4', '4+', '3' into (prefix, num_str)."""
    m = re.match(r'^([#b+]*)(\d+)([+]?)$', token)
    if not m:
        return "", token
    prefix = m.group(1) + m.group(3)
    return prefix, m.group(2)


def abbreviate_figured_bass(raw: str) -> str:
    """Apply Kellner abbreviation rules to a raw stack string.

    Input: descending interval stack, e.g. "7/5/3", "b6/5/3", "8/5/#3"
    Output: abbreviated form, e.g. "7", "b6/5", "#"

    Unrecognized stacks pass through unchanged.
    """
    if not raw:
        return raw

    tokens = [t.strip() for t in raw.split("/")]
    prefixes = []
    nums = []
    for tok in tokens:
        prefix, num = _split_interval(tok)
        prefixes.append(prefix)
        nums.append(num)

    key = tuple(nums)

    # Special case: root-position triad with a chromatic 3rd or 5th
    # "8/5/#3" → "#", "8/#5/3" → "#5" (just the altered interval)
    if key in (("8", "5", "3"), ("5", "3")):
        # Find any non-empty prefix
        altered = [(prefixes[i], nums[i]) for i in range(len(nums))
                   if prefixes[i] and nums[i] != "8"]
        if altered:
            # Return just the accidental(s) on the non-octave altered interval
            return "".join(p + n for p, n in altered if p)
        return ""

    abbreviated = _ABBREV_MAP.get(key)
    if abbreviated is None:
        # Unknown pattern — pass through unabbreviated
        return raw

    if abbreviated == "":
        return ""

    # Reattach prefixes: match each number in the abbreviated form back to its
    # original prefix from the full stack.
    abbrev_tokens = abbreviated.split("/")
    result_tokens = []
    for abbrev_tok in abbrev_tokens:
        _, abbrev_num = _split_interval(abbrev_tok)
        # Find the prefix for this number in the original stack
        original_prefix = ""
        for i, num in enumerate(nums):
            if num == abbrev_num:
                original_prefix = prefixes[i]
                break
        result_tokens.append(original_prefix + abbrev_tok)
    return "/".join(result_tokens)
```

- [ ] **Step 4: Run abbreviation tests**

```bash
python manage.py test apps.exercises.tests.test_figured_bass --verbosity=2 2>&1 | tail -30
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/figured_bass.py apps/exercises/tests/test_figured_bass.py
git commit -m "feat: add abbreviate_figured_bass with Kellner abbreviation rules"
```

---

## Task 3: Python figured bass calculator — `compute_figured_bass`

**Files:**
- Modify: `apps/exercises/utils/figured_bass.py`
- Modify: `apps/exercises/tests/test_figured_bass.py`

- [ ] **Step 1: Add failing tests for `compute_figured_bass`**

Append to `apps/exercises/tests/test_figured_bass.py`:

```python
from apps.exercises.utils.figured_bass import compute_figured_bass


def _make_chord(pitches_str: str, key_str: str):
    """Helper: build music21 chord + key from strings like 'A3 C#4 E4 A4', 'A'."""
    from music21 import chord as m21chord, key as m21key
    pitches = pitches_str.split()
    c = m21chord.Chord(pitches)
    k = m21key.Key(key_str)
    return c, k


def test_root_position_A_major():
    # A3 C#4 E4 A4 in A major — all diatonic, root position
    c, k = _make_chord("A3 C#4 E4 A4", "A")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "8/5/3"
    assert abbrev == ""


def test_root_position_C_major():
    # C4 E4 G4 C5 in C major
    c, k = _make_chord("C4 E4 G4 C5", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "8/5/3"
    assert abbrev == ""


def test_first_inversion_C_major():
    # E3 G3 C4 E4 in C major — first inversion triad
    c, k = _make_chord("E3 G3 C4 E4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "6" in raw
    assert "3" in raw
    assert abbrev == "6"


def test_dominant_seventh_C_major():
    # G3 B3 D4 F4 in C major — root position V7
    c, k = _make_chord("G3 B3 D4 F4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "7/5/3"
    assert abbrev == "7"


def test_chromatic_raised_pitch():
    # In C major, G#4 above E3 — G# is raised from diatonic G
    c, k = _make_chord("E3 G#4 C5", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "#" in raw  # some interval has # prefix


def test_chromatic_lowered_pitch():
    # In C major, Bb4 above C4 — Bb is lowered from diatonic B
    c, k = _make_chord("C4 E4 G4 Bb4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "b" in raw  # b7 present


def test_tritone_marker():
    # F3 B3 in C major — B above F is a tritone (aug 4th), F is diatonic
    c, k = _make_chord("F3 B3 D4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "4+" in raw or "#4" in raw  # tritone above F is augmented 4th
```

- [ ] **Step 2: Run to confirm failure**

```bash
python manage.py test apps.exercises.tests.test_figured_bass.test_root_position_A_major --verbosity=2 2>&1 | tail -10
```

Expected: `ImportError` — `compute_figured_bass` not yet defined.

- [ ] **Step 3: Add `compute_figured_bass` to `apps/exercises/utils/figured_bass.py`**

Append after `abbreviate_figured_bass`:

```python
def compute_figured_bass(chord_element, key) -> tuple[str, str]:
    """Compute raw and abbreviated figured bass from a music21 chord + key.

    Returns (raw_figured_bass, figured_bass).
    raw_figured_bass: descending interval stack, e.g. "8/5/3", "7/5/3"
    figured_bass: Kellner-abbreviated form, e.g. "", "7", "4/2"

    Chromatic prefix rules:
    - Pitch diatonic to key → no prefix
    - Pitch raised from diatonic → #
    - Pitch lowered from diatonic → b
    - Tritone interval (6 semitones, aug4/dim5) above bass → + marker

    Suspensions (multi-beat) are NOT detected here; that requires look-ahead
    over consecutive slices — handled in _build_figured_bass_overrides().
    """
    from music21 import interval as m21interval

    bass = chord_element.bass()
    if bass is None:
        return "", ""

    # Build set of diatonic pitch names in the key (e.g. {"C", "D", "E", "F", "G", "A", "B"})
    diatonic_names = {p.name for p in key.pitches}  # e.g. "C", "C#", "Bb" etc.
    # Also track letter+accidental pairs for chromatic comparison
    diatonic_step_alter = {(p.step, p.alter) for p in key.pitches}

    intervals = {}  # num_str → prefix (last write wins for duplicates)

    for pitch in chord_element.pitches:
        if pitch == bass:
            continue
        itv = m21interval.Interval(bass, pitch)
        directed = itv.generic.directed  # e.g. 3, 5, 8, -3 ...
        generic = abs(directed)

        # Collapse compound intervals: 9→2, 10→3, etc., but keep octave as 8
        if generic > 8:
            generic = generic - 7
        if generic == 1:
            generic = 8  # unison above bass = octave

        num_str = str(generic)

        # Determine chromatic prefix
        semitones = abs(itv.semitones) % 12
        if semitones == 0 and generic != 8:
            semitones = 12  # true octave

        # Tritone check (6 semitones = aug4 or dim5)
        is_tritone = (semitones == 6)

        # Check diatonicism: compare pitch step + alter to key
        pitch_in_diatonic = (pitch.step, pitch.alter) in diatonic_step_alter

        if is_tritone:
            prefix = "4+" if num_str == "4" else (
                "#" + num_str if not pitch_in_diatonic and pitch.alter > 0 else num_str + "+"
            )
            # Simpler: always mark tritone with + on the interval number
            prefix = "+"
            intervals[num_str] = "+" + num_str  # e.g. "+4" stored as token
            # Use conventional notation: append + after number
            intervals[num_str] = num_str + "+"
        elif pitch_in_diatonic:
            intervals[num_str] = num_str
        else:
            # Determine direction of alteration from diatonic
            # Find the diatonic pitch with the same step
            diatonic_alter = next(
                (a for (s, a) in diatonic_step_alter if s == pitch.step), 0
            )
            if pitch.alter > diatonic_alter:
                intervals[num_str] = "#" + num_str
            else:
                intervals[num_str] = "b" + num_str

    if not intervals:
        return "", ""

    # Sort descending by numeric value
    def _num(token):
        m = re.search(r'\d+', token)
        return int(m.group()) if m else 0

    sorted_tokens = sorted(intervals.values(), key=_num, reverse=True)
    raw = "/".join(sorted_tokens)
    abbreviated = abbreviate_figured_bass(raw)
    return raw, abbreviated
```

- [ ] **Step 4: Run compute tests**

```bash
python manage.py test apps.exercises.tests.test_figured_bass --verbosity=2 2>&1 | tail -30
```

Expected: all pass. Adjust `compute_figured_bass` logic if any fail — the tritone and chromatic logic may need tuning against the actual test assertions.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/figured_bass.py apps/exercises/tests/test_figured_bass.py
git commit -m "feat: add compute_figured_bass with pitch-vs-key chromatic prefix logic"
```

---

## Task 4: `_build_figured_bass_overrides` in import pipeline

**Files:**
- Modify: `apps/exercises/management/commands/import_bach_phrases.py:26-71`, `:82`, `:311-320`
- Modify: `apps/exercises/management/commands/create_unit_playlist.py:110`
- Test: `apps/exercises/tests/test_import_bach_phrases.py`

- [ ] **Step 1: Write failing test**

Open `apps/exercises/tests/test_import_bach_phrases.py` and add a test for the new builder function:

```python
def test_build_figured_bass_overrides_returns_slices(self):
    """_build_figured_bass_overrides produces slices with raw_figured_bass populated."""
    from apps.exercises.management.commands.import_bach_phrases import (
        _build_figured_bass_overrides,
    )
    from music21 import corpus, key as m21key
    from music21.corpus import chorales

    iterator = chorales.Iterator(1, 1, numberingSystem="riemenschneider")
    score = list(iterator)[0]
    chorded = score.chordify()
    global_key = score.analyze("key")

    result = _build_figured_bass_overrides(chorded, global_key)
    assert len(result) > 0
    first = result[0]
    assert "offset" in first
    assert "raw_figured_bass" in first["content"]
    assert "figured_bass" in first["content"]
    assert first["content"]["roman_numeral"] is None
    assert first["content"]["raw_roman_numeral"] is None
    # raw_figured_bass is a non-empty string
    assert isinstance(first["content"]["raw_figured_bass"], str)
    assert len(first["content"]["raw_figured_bass"]) > 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
python manage.py test apps.exercises.tests.test_import_bach_phrases --verbosity=2 -k "figured_bass_overrides" 2>&1 | tail -15
```

Expected: `ImportError` — `_build_figured_bass_overrides` not defined.

- [ ] **Step 3: Add `_build_figured_bass_overrides` to `import_bach_phrases.py`**

Add this function after `_build_roman_analysis_overrides` (around line 71):

```python
def _build_figured_bass_overrides(phrase_score, global_key) -> list:
    """Analyze a phrase and return UMTO analysis_overrides with figured bass.

    Stores raw_figured_bass (unabbreviated stack) and figured_bass (Kellner-
    abbreviated). roman_numeral and raw_roman_numeral are left null — this
    function is only called for mode:figures and mode:figures_unabbreviated.
    Targeting (curriculum filtering) happens at request time in
    generate_exercise_context; nothing is filtered here.
    """
    from music21 import chord
    from apps.exercises.utils.figured_bass import compute_figured_bass

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
                raw_fb, abbrev_fb = compute_figured_bass(element, global_key)
            except Exception:
                raw_fb, abbrev_fb = None, None

            overrides.append({
                "offset": abs_offset,
                "content": {
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "raw_figured_bass": raw_fb,
                    "figured_bass": abbrev_fb,
                    "pop_symbol": None,
                    "functional_label": None,
                },
            })

    return overrides
```

- [ ] **Step 4: Update the call site routing (around line 311–320)**

Replace:
```python
            # Build roman numeral analysis for label-entry modes
            analysis_overrides = None
            if mode in ('roman', 'figures', 'matching'):
                try:
                    analysis_overrides = _build_roman_analysis_overrides(
                        phrase_score, m21_key, unit_nums
                    )
                    self.stdout.write(f"  Built {len(analysis_overrides)} analysis slices")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Analysis overrides failed: {e}"))
```

With:
```python
            # Build analysis overrides based on mode
            analysis_overrides = None
            if mode in ('roman', 'matching'):
                try:
                    analysis_overrides = _build_roman_analysis_overrides(
                        phrase_score, m21_key, unit_nums
                    )
                    self.stdout.write(f"  Built {len(analysis_overrides)} roman analysis slices")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Roman analysis overrides failed: {e}"))
            elif mode in ('figures', 'figures_unabbreviated'):
                try:
                    analysis_overrides = _build_figured_bass_overrides(
                        phrase_score, m21_key
                    )
                    self.stdout.write(f"  Built {len(analysis_overrides)} figured bass slices")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Figured bass overrides failed: {e}"))
```

- [ ] **Step 5: Add `figures_unabbreviated` to `--mode` choices in both commands**

In `import_bach_phrases.py` line 82, change:
```python
        parser.add_argument('--mode', type=str, choices=['play', 'roman', 'figures', 'matching'], default='play', help='Exercise mode')
```
To:
```python
        parser.add_argument('--mode', type=str, choices=['play', 'roman', 'figures', 'figures_unabbreviated', 'matching'], default='play', help='Exercise mode')
```

In `create_unit_playlist.py` line 110, change:
```python
                            choices=["roman", "play", "figures", "matching"], default="roman")
```
To:
```python
                            choices=["roman", "play", "figures", "figures_unabbreviated", "matching"], default="roman")
```

- [ ] **Step 6: Run tests**

```bash
python manage.py test apps.exercises.tests.test_import_bach_phrases --verbosity=2 -k "figured_bass" 2>&1 | tail -20
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/exercises/management/commands/import_bach_phrases.py \
        apps/exercises/management/commands/create_unit_playlist.py \
        apps/exercises/tests/test_import_bach_phrases.py
git commit -m "feat: add _build_figured_bass_overrides and route mode:figures in import pipeline"
```

---

## Task 5: Update taxonomy JSON — figured bass entries + RN corrections

**Files:**
- Modify: `music_theory_taxonomy.json` (units 9–13)

This task is hand-authoring. No code, no tests — the taxonomy is validated by `test_taxonomy_reader.py` additions below.

- [ ] **Step 1: Add `analysis.figured_bass` and `analysis.figured_bass_unabbreviated` for unit 9**

Find unit `"n": "9"` in `music_theory_taxonomy.json`. Its `analysis` currently has only `"roman"`. Add alongside it:

```json
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
```

- [ ] **Step 2: Add figured bass entries for unit 10 + correct roman**

Unit 10 `analysis.figured_bass`:
```json
"figured_bass": {
  "cumulative": [
    {"value": "",    "display": "5/3"},
    {"value": "7",   "display": "7"},
    {"value": "6",   "display": "6"},
    {"value": "6/5", "display": "6/5"}
  ],
  "new": [
    {"value": "6",   "display": "6"},
    {"value": "6/5", "display": "6/5"}
  ]
},
"figured_bass_unabbreviated": {
  "cumulative": [
    {"value": "8/5/3", "display": "8/5/3"},
    {"value": "7/5/3", "display": "7/5/3"},
    {"value": "6/3",   "display": "6/3"},
    {"value": "6/5/3", "display": "6/5/3"}
  ],
  "new": [
    {"value": "6/3",   "display": "6/3"},
    {"value": "6/5/3", "display": "6/5/3"}
  ]
}
```

Unit 10 `analysis.roman.cumulative` and `new` — add `V65`:
```json
{"value": "V65", "display": "V⁶₅"}
```
Add to both `cumulative` and `new` arrays.

- [ ] **Step 3: Add figured bass entries for unit 11 + correct roman**

Unit 11 `analysis.figured_bass` — no new figures (pre-dominants use `""` and `6` already in cumulative):
```json
"figured_bass": {
  "cumulative": [
    {"value": "",    "display": "5/3"},
    {"value": "7",   "display": "7"},
    {"value": "6",   "display": "6"},
    {"value": "6/5", "display": "6/5"}
  ],
  "new": []
},
"figured_bass_unabbreviated": {
  "cumulative": [
    {"value": "8/5/3", "display": "8/5/3"},
    {"value": "7/5/3", "display": "7/5/3"},
    {"value": "6/3",   "display": "6/3"},
    {"value": "6/5/3", "display": "6/5/3"}
  ],
  "new": []
}
```

Unit 11 `analysis.roman` — add `ii65`, `ii7` to both `cumulative` and `new`:
```json
{"value": "ii65",  "display": "ii⁶₅"},
{"value": "ii7",   "display": "ii⁷"}
```

- [ ] **Step 4: Add figured bass entries for unit 12 + correct roman**

Unit 12 `analysis.figured_bass`:
```json
"figured_bass": {
  "cumulative": [
    {"value": "",    "display": "5/3"},
    {"value": "7",   "display": "7"},
    {"value": "6",   "display": "6"},
    {"value": "6/5", "display": "6/5"},
    {"value": "6/4", "display": "6/4"},
    {"value": "4/3", "display": "4/3"},
    {"value": "4/2", "display": "4/2"}
  ],
  "new": [
    {"value": "6/4", "display": "6/4"},
    {"value": "4/3", "display": "4/3"},
    {"value": "4/2", "display": "4/2"}
  ]
},
"figured_bass_unabbreviated": {
  "cumulative": [
    {"value": "8/5/3", "display": "8/5/3"},
    {"value": "7/5/3", "display": "7/5/3"},
    {"value": "6/3",   "display": "6/3"},
    {"value": "6/5/3", "display": "6/5/3"},
    {"value": "6/4",   "display": "6/4"},
    {"value": "6/4/3", "display": "6/4/3"},
    {"value": "6/4/2", "display": "6/4/2"}
  ],
  "new": [
    {"value": "6/4",   "display": "6/4"},
    {"value": "6/4/3", "display": "6/4/3"},
    {"value": "6/4/2", "display": "6/4/2"}
  ]
}
```

Unit 12 `analysis.roman` — add to `cumulative` and `new`:
```json
{"value": "Cad64", "display": "Cad⁶₄"},
{"value": "V43",   "display": "V⁴₃"},
{"value": "V42",   "display": "V⁴₂"}
```

- [ ] **Step 5: Add figured bass entries for unit 13 + correct roman**

Unit 13 `analysis.figured_bass` — adds `#6/4/3` for the Rule of the Octave chromatic figure:
```json
"figured_bass": {
  "cumulative": [
    {"value": "",       "display": "5/3"},
    {"value": "7",      "display": "7"},
    {"value": "6",      "display": "6"},
    {"value": "6/5",    "display": "6/5"},
    {"value": "6/4",    "display": "6/4"},
    {"value": "4/3",    "display": "4/3"},
    {"value": "4/2",    "display": "4/2"},
    {"value": "#6/4/3", "display": "#6/4/3"}
  ],
  "new": [
    {"value": "#6/4/3", "display": "#6/4/3"}
  ]
},
"figured_bass_unabbreviated": {
  "cumulative": [
    {"value": "8/5/3",   "display": "8/5/3"},
    {"value": "7/5/3",   "display": "7/5/3"},
    {"value": "6/3",     "display": "6/3"},
    {"value": "6/5/3",   "display": "6/5/3"},
    {"value": "6/4",     "display": "6/4"},
    {"value": "6/4/3",   "display": "6/4/3"},
    {"value": "6/4/2",   "display": "6/4/2"},
    {"value": "#6/4/3",  "display": "#6/4/3"}
  ],
  "new": [
    {"value": "#6/4/3",  "display": "#6/4/3"}
  ]
}
```

Unit 13 `analysis.roman` — add to `cumulative` and `new`:
```json
{"value": "V43/V", "display": "V⁴₃/V"}
```

- [ ] **Step 6: Validate JSON is well-formed**

```bash
python3 -c "import json; json.load(open('music_theory_taxonomy.json')); print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Write taxonomy reader tests**

Add to `apps/exercises/tests/test_taxonomy_reader.py`:

```python
def test_figured_bass_unit9_cumulative():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_cumulative_values("9", "figured_bass")
    assert "" in vals
    assert "7" in vals

def test_figured_bass_unit9_new():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_new_values("9", "figured_bass")
    assert "" in vals
    assert "7" in vals

def test_figured_bass_unit10_new_adds_6_and_65():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_new_values("10", "figured_bass")
    assert "6" in vals
    assert "6/5" in vals

def test_figured_bass_unit11_new_is_empty():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_new_values("11", "figured_bass")
    assert len(vals) == 0

def test_figured_bass_unit12_new_adds_inversions():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_new_values("12", "figured_bass")
    assert "6/4" in vals
    assert "4/3" in vals
    assert "4/2" in vals

def test_roman_unit10_includes_V65():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_cumulative_values("10", "roman")
    assert "V65" in vals

def test_roman_unit11_includes_ii65_and_ii7():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_cumulative_values("11", "roman")
    assert "ii65" in vals
    assert "ii7" in vals

def test_roman_unit12_includes_cad64_V43_V42():
    from apps.exercises.taxonomy_reader import TaxonomyReader
    vals = TaxonomyReader.get_cumulative_values("12", "roman")
    assert "Cad64" in vals
    assert "V43" in vals
    assert "V42" in vals
```

- [ ] **Step 8: Run taxonomy tests**

```bash
python manage.py test apps.exercises.tests.test_taxonomy_reader --verbosity=2 2>&1 | tail -20
```

Expected: all pass. Fix any JSON entry errors until they do.

- [ ] **Step 9: Commit**

```bash
git add music_theory_taxonomy.json apps/exercises/tests/test_taxonomy_reader.py
git commit -m "feat: add figured_bass taxonomy entries units 9-13 and correct roman entries 10-13"
```

---

## Task 6: `generate_exercise_context` — figured bass policy branch

**Files:**
- Modify: `lab/views.py:325-389`
- Test: `apps/exercises/tests/test_generate_exercise_context.py`

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generate_exercise_context.py`:

```python
    def _make_figured_bass_exercise_data(self, raw_fb_list):
        """Build exercise data with raw_figured_bass slices instead of roman numerals."""
        slices = []
        for i, raw_fb in enumerate(raw_fb_list):
            slices.append({
                "offset": float(i),
                "content": {
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "raw_figured_bass": raw_fb,
                    "figured_bass": None,
                    "pop_symbol": None,
                    "functional_label": None,
                },
                "is_target": False,
            })
        return {
            "isUMTO": False,
            "type": "test",
            "key": "jC_",
            "keySignature": "",
            "analysisType": "figured_bass",
            "score": {
                "meta": {"key": "jC_", "time": "4/4"},
                "measures": [],
                "umto": {
                    "metadata": {
                        "exercise_id": "TEST_FB",
                        "source": "test",
                        "key": "C",
                        "meter": "4/4",
                        "complexity_score": 9,
                        "mode": "identification",
                    },
                    "voices": {"S": [], "A": [], "T": [], "B": []},
                    "analysis": slices,
                    "grading": [],
                },
            },
            "complexity_score": 9,
        }

    def _run_figures_context(self, raw_fb_list, unit_n="9"):
        from apps.exercises.models import Exercise, Playlist
        from lab.views import generate_exercise_context

        ex = MagicMock(spec=Exercise)
        ex.data = self._make_figured_bass_exercise_data(raw_fb_list)
        ex.skill_tags = [f"unit:{unit_n}", "mode:figures"]
        ex.id = "TEST_FB"
        ex.complexity = 9
        ex.is_public = True

        pl = MagicMock(spec=Playlist)
        pl.skill_tags = [f"unit:{unit_n}", "mode:figures"]
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
        pl.id = "PLTEST_FB"
        pl.min_complexity = 1
        pl.max_complexity = 12

        return generate_exercise_context(
            exercise_num=1,
            exercise=ex,
            user=MagicMock(id=1),
            playlist=pl,
            course=None,
        )

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_figures_mode_returns_figured_bass_family(self, mock_reader, mock_perf):
        self._make_mocks({"", "7"}, {"", "7"}, mock_reader, mock_perf)
        ctx = self._run_figures_context(["8/5/3", "7/5/3"], unit_n="9")
        policy = ctx["analysisPolicy"]
        self.assertIsNotNone(policy)
        self.assertEqual(policy["family"], "figured_bass")

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_figures_mode_targets_slices_by_raw_figured_bass(self, mock_reader, mock_perf):
        self._make_mocks({"", "7"}, {"", "7"}, mock_reader, mock_perf)
        ctx = self._run_figures_context(["8/5/3", "9/5/3"], unit_n="9")
        slices = ctx["score"]["umto"]["analysis"]
        # "8/5/3" abbreviates to "" — in cumulative → is_target True
        self.assertTrue(slices[0]["is_target"])
        # "9/5/3" abbreviates to "9" — not in cumulative {"", "7"} → is_target False
        self.assertFalse(slices[1]["is_target"])

    @patch("lab.views.PerformanceData")
    @patch("lab.views.TaxonomyReader")
    def test_figures_mode_injects_analysis_type(self, mock_reader, mock_perf):
        self._make_mocks({"", "7"}, {"", "7"}, mock_reader, mock_perf)
        ctx = self._run_figures_context(["8/5/3"], unit_n="9")
        self.assertEqual(ctx.get("analysisType"), "figured_bass")
```

- [ ] **Step 2: Run to confirm failure**

```bash
python manage.py test apps.exercises.tests.test_generate_exercise_context --verbosity=2 -k "figures_mode" 2>&1 | tail -15
```

Expected: FAIL — policy family is `"roman"`, analysisType not in context.

- [ ] **Step 3: Refactor `generate_exercise_context` in `lab/views.py`**

Replace the block from line 325 (`# Build analysisPolicy`) through line 386 (end of cadential rewrite) with:

```python
    # Build analysisPolicy and apply targeting to raw analysis slices
    analysis_policy = None
    _unit_n_for_policy = unit_n  # may be None if no unit tag found

    # Detect analysis family from mode tag on exercise or playlist
    _all_tags = list(playlist.skill_tags or []) + list(exercise.skill_tags or []) if playlist else list(exercise.skill_tags or [])
    if "mode:figures_unabbreviated" in _all_tags:
        _family = "figured_bass_unabbreviated"
        _raw_field = "raw_figured_bass"
        _targeted_field = "raw_figured_bass"
        _analysis_type = "figured_bass_unabbreviated"
    elif "mode:figures" in _all_tags:
        _family = "figured_bass"
        _raw_field = "raw_figured_bass"
        _targeted_field = "figured_bass"
        _analysis_type = "figured_bass"
    else:
        _family = "roman"
        _raw_field = "raw_roman_numeral"
        _targeted_field = "roman_numeral"
        _analysis_type = None  # JS defaults to "roman" already

    if _unit_n_for_policy:
        _unit_analysis = TaxonomyReader.get_unit_analysis(_unit_n_for_policy, _family)
        if _unit_analysis:
            _cumulative = TaxonomyReader.get_cumulative_values(_unit_n_for_policy, _family)
            _new_vals = TaxonomyReader.get_new_values(_unit_n_for_policy, _family)

            # Build displayMap: only entries where display != value
            _display_map = {
                entry["value"]: entry["display"]
                for entry in _unit_analysis["cumulative"]
                if entry["display"] != entry["value"]
            }

            analysis_policy = {
                "family": _family,
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
                _raw = _sl.get("content", {}).get(_raw_field)
                # For figured_bass family, abbreviate the raw stack to compare with cumulative
                if _family == "figured_bass":
                    from apps.exercises.utils.figured_bass import abbreviate_figured_bass
                    _compare = abbreviate_figured_bass(_raw) if _raw else None
                else:
                    _compare = _raw
                if _compare is not None and _compare in _cumulative:
                    _sl["content"][_targeted_field] = _compare
                    _sl["is_target"] = True
                else:
                    _sl["content"][_targeted_field] = None
                    _sl["is_target"] = False

            # ── Cadential 6/4 contextual rewrite (Roman numerals only) ──
            if _family == "roman":
                _CAD64_SOURCES = {"I64", "i64"}
                _CAD64_TARGETS = {"V", "V7", "V65", "V43"}
                for _i in range(len(_slices) - 1):
                    _cur = _slices[_i]
                    _nxt = _slices[_i + 1]
                    _cur_rn = _cur.get("content", {}).get("roman_numeral")
                    _nxt_rn = _nxt.get("content", {}).get("roman_numeral")
                    if _cur_rn in _CAD64_SOURCES and _nxt_rn in _CAD64_TARGETS:
                        if "V64" in _cumulative:
                            _cur["content"]["roman_numeral"] = "V64"
                            _cur["is_target"] = True
                        else:
                            _cur["content"]["roman_numeral"] = None
                            _cur["is_target"] = False
```

Then in the `exercise_context.update({...})` block (currently line 387), add `"analysisType"` alongside `"analysisPolicy"`:

```python
    exercise_context.update(
        {
            "analysisPolicy": analysis_policy,
            "analysisType": _analysis_type,  # ADD THIS LINE
            "unit_n": unit_n,
            # ... rest unchanged
        }
    )
```

- [ ] **Step 4: Run all context tests**

```bash
python manage.py test apps.exercises.tests.test_generate_exercise_context --verbosity=2 2>&1 | tail -20
```

Expected: all pass including previous roman numeral tests.

- [ ] **Step 5: Commit**

```bash
git add lab/views.py apps/exercises/tests/test_generate_exercise_context.py
git commit -m "feat: branch generate_exercise_context on mode:figures for figured bass policy"
```

---

## Task 7: JS — answer extraction + buildChoices for `figured_bass_unabbreviated`

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js:447-450`, `:319-337`

No new JS test infrastructure is needed — verify manually via browser after import.

- [ ] **Step 1: Add `figured_bass_unabbreviated` to answer extraction**

In `exercise_definition.js` around line 447, the answer extraction block reads:

```javascript
      if (slice.content.roman_numeral) answer = stripFiguredBassTokens(slice.content.roman_numeral);
      else if (slice.content.pop_symbol) answer = slice.content.pop_symbol;
      else if (slice.content.figured_bass) answer = expandFiguredBassToken(slice.content.figured_bass);
      else if (slice.content.functional_label) answer = slice.content.functional_label;
```

Replace with:

```javascript
      if (analysisType === "figured_bass_unabbreviated" && slice.content.raw_figured_bass) {
        answer = slice.content.raw_figured_bass;
      } else if (slice.content.roman_numeral) {
        answer = stripFiguredBassTokens(slice.content.roman_numeral);
      } else if (slice.content.pop_symbol) {
        answer = slice.content.pop_symbol;
      } else if (slice.content.figured_bass) {
        answer = expandFiguredBassToken(slice.content.figured_bass);
      } else if (slice.content.functional_label) {
        answer = slice.content.functional_label;
      }
```

- [ ] **Step 2: Update `allContentNull` check to include `raw_figured_bass`**

Around line 468:

```javascript
      var allContentNull = slice.content.roman_numeral === null &&
        slice.content.pop_symbol === null &&
        slice.content.figured_bass === null &&
        slice.content.functional_label === null;
```

Replace with:

```javascript
      var allContentNull = slice.content.roman_numeral === null &&
        slice.content.pop_symbol === null &&
        slice.content.figured_bass === null &&
        slice.content.raw_figured_bass === null &&
        slice.content.functional_label === null;
```

- [ ] **Step 3: Add `figured_bass_unabbreviated` fallbacks to `buildChoices`**

Around line 319, the fallbacks block starts:

```javascript
    var fallbacks = analysisType === "figured_bass"
      ? ["5/3", "6", "6/4", "6/5", "7"]
```

Replace with:

```javascript
    var fallbacks = analysisType === "figured_bass"
      ? ["", "6", "6/4", "7", "6/5", "4/3", "4/2"]
      : analysisType === "figured_bass_unabbreviated"
      ? ["8/5/3", "6/3", "6/4", "7/5/3", "6/5/3", "6/4/3", "6/4/2"]
```

(Leave the remaining `: analysisType === "note_name"` chain unchanged.)

- [ ] **Step 4: Add `figured_bass_unabbreviated` to `analysis.mode` detection**

Around line 923–926:

```javascript
        if (exercise.analysisType === "note_name") {
          exercise.analysis.mode.note_names = true;
        } else {
          exercise.analysis.mode.roman_numerals = true;
        }
```

Replace with:

```javascript
        if (exercise.analysisType === "note_name") {
          exercise.analysis.mode.note_names = true;
        } else if (exercise.analysisType === "figured_bass" || exercise.analysisType === "figured_bass_unabbreviated") {
          exercise.analysis.mode.roman_numerals = true;  // reuse roman slot rendering for now
        } else {
          exercise.analysis.mode.roman_numerals = true;
        }
```

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat: add figured_bass_unabbreviated answer extraction and buildChoices fallbacks"
```

---

## Task 8: End-to-end smoke test — import one unit 9 figured bass playlist

This task verifies the full pipeline works before declaring done.

- [ ] **Step 1: Import a single Riemenschneider chorale as `mode:figures`**

```bash
python manage.py import_bach_phrases \
  --riemenschneider 1 \
  --author avnerdorman@gmail.com \
  --mode figures \
  --extra-tags unit:9 mode:figures \
  --public \
  --dry-run
```

Expected: shows phrase ranges without error.

- [ ] **Step 2: Import for real**

```bash
python manage.py import_bach_phrases \
  --riemenschneider 1 \
  --author avnerdorman@gmail.com \
  --mode figures \
  --extra-tags unit:9 mode:figures \
  --public
```

Expected: `Created UMTO Exercise ...` for each phrase.

- [ ] **Step 3: Verify stored data**

```bash
python manage.py shell -c "
from apps.exercises.models import Exercise
import json
ex = Exercise.objects.filter(skill_tags__contains=['mode:figures']).first()
umto = ex.data.get('score',{}).get('umto',{})
slices = umto.get('analysis', [])
print('Exercise:', ex.description)
print('Skill tags:', ex.skill_tags)
print('Slices:', len(slices))
for s in slices[:4]:
    c = s.get('content', {})
    print('  offset:', s.get('offset'),
          'raw_fb:', c.get('raw_figured_bass'),
          'fb:', c.get('figured_bass'))
"
```

Expected: `raw_figured_bass` is populated (e.g. `"8/5/3"`), `figured_bass` is abbreviated (e.g. `""`), `raw_roman_numeral` is `None`.

- [ ] **Step 4: Create a unit 9 figures playlist**

```bash
python manage.py create_unit_playlist \
  --unit 9 \
  --riemenschneider 1-1 \
  --author avnerdorman@gmail.com \
  --mode figures \
  --public
```

Expected: `Playlist 'Unit 9 — Tonic & dominant (figures)' ... — created`.

- [ ] **Step 5: Load exercise in browser**

Start the dev server and navigate to the created playlist exercise. Open DevTools console.

Check:
- `[UMTO-DEBUG] parsed exercise` log shows `analysisType: "figured_bass"`
- Analysis slots appear with `?` placeholders
- Dropdown choices include figured bass values from `allowedValues` (e.g. `"5/3"`, `"7"`)
- `is_target` slices show slots; non-target slices are hidden

- [ ] **Step 6: Commit smoke test notes (optional)**

If any fixes were needed, commit them now with descriptive messages.

---

## Self-Review Checklist

After completing all tasks:

- [ ] `raw_figured_bass` field exists in `AnalysisLayer` and is nullable
- [ ] `abbreviate_figured_bass` handles all Kellner cases + chromatic prefixes + passthrough
- [ ] `compute_figured_bass` uses pitch-vs-key for chromatic prefix (no specifier logic)
- [ ] `_build_figured_bass_overrides` called for `mode in ('figures', 'figures_unabbreviated')`; roman builder NOT called for those modes
- [ ] `figures_unabbreviated` in `--mode` choices for both management commands
- [ ] Taxonomy JSON valid; units 9–13 have `analysis.figured_bass` and `analysis.figured_bass_unabbreviated`; units 10–13 `analysis.roman` corrected
- [ ] `generate_exercise_context` branches on mode tag; cadential rewrite guard is Roman-only
- [ ] `analysisType` injected into exercise context payload for figured bass modes
- [ ] JS answer extraction handles `figured_bass_unabbreviated` before other fields
- [ ] `allContentNull` check includes `raw_figured_bass`
- [ ] All Python tests pass: `python manage.py test apps.exercises --verbosity=1`
