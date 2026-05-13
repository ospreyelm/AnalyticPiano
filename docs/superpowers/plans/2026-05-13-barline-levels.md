# Barline Exercise Levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate 8 levelled playlists of barline exercises sourced from the music21 ABC/krn folk corpus, with difficulty increasing by meter family, rhythmic vocabulary, and phrase length.

**Architecture:** A new `corpus_filter.py` util parses music21 corpus files and yields `PhraseResult` objects; the existing management command gains a `--source corpus` mode that calls the filter, upserts exercises via `save_umto_barline_exercise`, and rebuilds one playlist per level. Two existing files need small extensions: `barline_exercise_builder.py` gains derived meters (2/2, 3/2 etc.) and `umto_factory.save_umto_barline_exercise` gains a `complexity` param.

**Tech Stack:** Python, Django management commands, music21 ABC/krn parser, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `apps/exercises/utils/barline_exercise_builder.py` | Modify | Add derived meter entries to `SIMPLE_METERS` / `COMPOUND_METERS` |
| `apps/exercises/umto_factory.py` | Modify | Add `complexity` param to `save_umto_barline_exercise` |
| `apps/exercises/utils/corpus_filter.py` | Create | Parse corpus, extract phrases, classify by level, yield `PhraseResult` |
| `apps/exercises/management/commands/generate_unit2_barline_exercises.py` | Modify | Add `--source corpus`, `--level`, `--limit`, `--dry-run` args + corpus flow |
| `apps/exercises/tests/test_barline_exercise_builder.py` | Modify | Add tests for derived meter payloads |
| `apps/exercises/tests/test_corpus_filter.py` | Create | Unit tests for all filter rules and level assignment |
| `apps/exercises/tests/test_generate_unit2_barline_exercises.py` | Modify | Add corpus source tests (with mocked iter_phrases) |

---

## Task 1: Extend builder for derived meters

**Files:**
- Modify: `apps/exercises/utils/barline_exercise_builder.py`
- Test: `apps/exercises/tests/test_barline_exercise_builder.py`

- [ ] **Step 1: Write failing tests for derived meters**

Add to `apps/exercises/tests/test_barline_exercise_builder.py`:

```python
def test_simple_derived_meter_2_2(self):
    payload = build_barline_payload(
        time_signature="2/2",
        clef="treble",
        notes=[
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
        ],
        measures=2,
        show_time_signature=True,
        pitch_mode="rhythm_only",
        source="test",
    )
    self.assertEqual(payload["type"], "umto_barline_placement")
    self.assertEqual(payload["beat_count"], 4)
    self.assertEqual(payload["correct_barline_positions"], [1])

def test_simple_derived_meter_3_2(self):
    payload = build_barline_payload(
        time_signature="3/2",
        clef="treble",
        notes=[
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
        ],
        measures=2,
        show_time_signature=True,
        pitch_mode="rhythm_only",
        source="test",
    )
    self.assertEqual(payload["beat_count"], 6)
    self.assertEqual(payload["correct_barline_positions"], [2])

def test_compound_derived_meter_6_4(self):
    payload = build_barline_payload(
        time_signature="6/4",
        clef="treble",
        notes=[
            {"pitch": "B4", "duration": "q", "dots": 1},
            {"pitch": "B4", "duration": "q", "dots": 1},
            {"pitch": "B4", "duration": "q", "dots": 1},
            {"pitch": "B4", "duration": "q", "dots": 1},
        ],
        measures=2,
        show_time_signature=True,
        pitch_mode="rhythm_only",
        source="test",
    )
    self.assertEqual(payload["beat_count"], 4)
    self.assertEqual(payload["correct_barline_positions"], [1])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 manage.py test apps.exercises.tests.test_barline_exercise_builder -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: FAIL — `ValueError: Unsupported time signature: 2/2`

- [ ] **Step 3: Add derived meters to builder**

In `apps/exercises/utils/barline_exercise_builder.py`, replace the `SIMPLE_METERS` and `COMPOUND_METERS` dicts:

```python
SIMPLE_METERS = {
    "2/4": (2, Fraction(1, 1)),
    "3/4": (3, Fraction(1, 1)),
    "4/4": (4, Fraction(1, 1)),
    "2/2": (2, Fraction(2, 1)),
    "3/2": (3, Fraction(2, 1)),
    "4/2": (4, Fraction(2, 1)),
}
COMPOUND_METERS = {
    "6/8":  (2, Fraction(3, 2)),
    "9/8":  (3, Fraction(3, 2)),
    "12/8": (4, Fraction(3, 2)),
    "6/4":  (2, Fraction(3, 1)),
    "9/4":  (3, Fraction(3, 1)),
    "12/4": (4, Fraction(3, 1)),
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_barline_exercise_builder -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/barline_exercise_builder.py apps/exercises/tests/test_barline_exercise_builder.py
git commit -m "feat: add derived meter support to barline exercise builder (2/2, 3/2, 4/2, 6/4, 9/4, 12/4)"
```

---

## Task 2: Add `complexity` param to `save_umto_barline_exercise`

**Files:**
- Modify: `apps/exercises/umto_factory.py:483-522`
- Test: `apps/exercises/tests/test_barline_exercise_save.py`

- [ ] **Step 1: Write failing test**

Open `apps/exercises/tests/test_barline_exercise_save.py` and add:

```python
def test_save_umto_barline_exercise_uses_provided_complexity(self):
    from apps.exercises.umto_factory import save_umto_barline_exercise
    from apps.exercises.utils.barline_exercise_builder import build_barline_payload
    user = get_user_model().objects.create_user(email="barline-complexity@test.com", password="pw")
    payload = build_barline_payload(
        time_signature="3/4",
        clef="treble",
        notes=[
            {"pitch": "B4", "duration": "q", "dots": 0},
            {"pitch": "B4", "duration": "q", "dots": 0},
            {"pitch": "B4", "duration": "h", "dots": 0},
        ],
        measures=1,
        show_time_signature=True,
        pitch_mode="rhythm_only",
        source="test",
    )
    ex = save_umto_barline_exercise(
        description="complexity test",
        author=user,
        payload=payload,
        complexity=5,
    )
    self.assertEqual(ex.complexity, 5)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 manage.py test apps.exercises.tests.test_barline_exercise_save -v 2 2>&1 | grep -E "FAIL|ERROR|OK|TypeError"
```

Expected: FAIL — `TypeError: save_umto_barline_exercise() got an unexpected keyword argument 'complexity'`

- [ ] **Step 3: Add complexity param**

In `apps/exercises/umto_factory.py`, replace the `save_umto_barline_exercise` signature and body hardcoded `complexity=2` references:

```python
def save_umto_barline_exercise(
    *,
    description: str,
    author,
    payload: dict,
    is_public: bool = True,
    overwrite: bool = False,
    complexity: int = 2,
) -> Exercise:
    data = dict(payload)
    data["type"] = "umto_barline_placement"
    data["isUMTO"] = True
    data["mode"] = InteractionMode.IDENTIFICATION.value

    skill_tags = list(data.get("tags") or ["unit:2", "unit:2_rhythm"])
    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

    if ex is None:
        ex = Exercise(
            description=description,
            data=data,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags,
            complexity=complexity,
        )
    else:
        ex.data = data
        ex.skill_tags = skill_tags
        ex.complexity = complexity
        ex.is_public = is_public

    if ex._state.adding:
        ex.save()
    else:
        ex.save(update_fields=["data", "skill_tags", "complexity", "is_public"])
    ex.data["exerciseId"] = ex.id
    ex.save(update_fields=["data"])
    return ex
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 manage.py test apps.exercises.tests.test_barline_exercise_save -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Run all barline tests to confirm no regression**

```bash
python3 manage.py test apps.exercises.tests.test_barline_exercise_builder apps.exercises.tests.test_barline_exercise_save apps.exercises.tests.test_generate_unit2_barline_exercises -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_barline_exercise_save.py
git commit -m "feat: add complexity param to save_umto_barline_exercise (default=2)"
```

---

## Task 3: Create `corpus_filter.py` — phrase extraction and level classification

**Files:**
- Create: `apps/exercises/utils/corpus_filter.py`
- Create: `apps/exercises/tests/test_corpus_filter.py`

This is the core module. Build and test rule by rule.

### 3a: Data structures and level classification

- [ ] **Step 1: Write failing tests for level assignment**

Create `apps/exercises/tests/test_corpus_filter.py`:

```python
from django.test import SimpleTestCase
from apps.exercises.utils.corpus_filter import assign_level, SMALLEST_VALUE_ORDER


class CorpusFilterLevelAssignmentTests(SimpleTestCase):
    """assign_level returns the lowest matching level, or None if no level matches."""

    def test_simple_quarter_only_is_level_1(self):
        # 3/4, smallest = quarter → L1
        self.assertEqual(assign_level("3/4", "q"), 1)

    def test_simple_quarter_in_44_is_level_1(self):
        self.assertEqual(assign_level("4/4", "q"), 1)

    def test_simple_24_quarter_only_is_level_2_not_1(self):
        # 2/4 not in L1 meters, falls to L2
        self.assertEqual(assign_level("2/4", "q"), 2)

    def test_simple_eighth_is_level_2(self):
        self.assertEqual(assign_level("3/4", "8"), 2)

    def test_simple_sixteenth_is_level_3(self):
        self.assertEqual(assign_level("4/4", "16"), 3)

    def test_compound_dotted_quarter_is_level_4(self):
        # 6/8, smallest = dotted quarter (q+dot) → L4
        self.assertEqual(assign_level("6/8", "q", dots=1), 4)

    def test_compound_eighth_is_level_5(self):
        self.assertEqual(assign_level("6/8", "8"), 5)

    def test_compound_sixteenth_is_level_6(self):
        self.assertEqual(assign_level("9/8", "16"), 6)

    def test_derived_simple_half_is_level_7(self):
        self.assertEqual(assign_level("3/2", "h"), 7)

    def test_derived_compound_quarter_is_level_8(self):
        self.assertEqual(assign_level("6/4", "q"), 8)

    def test_unsupported_meter_returns_none(self):
        self.assertIsNone(assign_level("5/4", "q"))

    def test_whole_note_in_simple_is_level_1(self):
        self.assertEqual(assign_level("4/4", "w"), 1)
```

- [ ] **Step 2: Run to verify all fail**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter -v 2 2>&1 | grep -E "FAIL|ERROR|ImportError|OK"
```

Expected: FAIL — `ImportError: cannot import name 'assign_level'`

- [ ] **Step 3: Implement assign_level**

Create `apps/exercises/utils/corpus_filter.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator

# Duration ordering: smaller index = shorter = harder
SMALLEST_VALUE_ORDER = ["16", "8", "q", "h", "w"]  # ascending duration

# Dotted durations are represented as (duration, dots).
# A dotted quarter (q,1) is between q and h in length.
# For level assignment we compare raw duration type only (dots irrelevant to ceiling).

# Level definitions: (meter_set, smallest_ceiling_duration, smallest_ceiling_dots)
# A phrase qualifies for a level if:
#   - its time_signature is in meter_set
#   - its smallest note value is >= ceiling (i.e. not shorter than ceiling)
# We assign to the LOWEST matching level.

_LEVEL_DEFS = [
    # level, meters, smallest_dur_ceiling, ceiling_dots
    (1, {"3/4", "4/4"},               "q",  0),
    (2, {"2/4", "3/4", "4/4"},        "8",  0),
    (3, {"2/4", "3/4", "4/4"},        "16", 0),
    (4, {"6/8", "9/8", "12/8"},       "q",  1),  # dotted quarter = compound beat
    (5, {"6/8", "9/8", "12/8"},       "8",  0),
    (6, {"6/8", "9/8", "12/8"},       "16", 0),
    (7, {"2/2", "3/2", "4/2"},        "8",  0),
    (8, {"6/4", "9/4", "12/4"},       "8",  0),
]

# Fraction of a whole note for each duration type
_DUR_FRACTION = {
    "w":  Fraction(1, 1),
    "h":  Fraction(1, 2),
    "q":  Fraction(1, 4),
    "8":  Fraction(1, 8),
    "16": Fraction(1, 16),
}


def _dur_value(duration: str, dots: int = 0) -> Fraction:
    """Return fractional whole-note value for a duration+dots."""
    base = _DUR_FRACTION[duration]
    total = base
    add = base
    for _ in range(dots):
        add /= 2
        total += add
    return total


def assign_level(time_signature: str, smallest_dur: str, dots: int = 0) -> int | None:
    """Return the lowest level number this phrase qualifies for, or None."""
    phrase_smallest = _dur_value(smallest_dur, dots)
    for level, meters, ceiling_dur, ceiling_dots in _LEVEL_DEFS:
        if time_signature not in meters:
            continue
        ceiling = _dur_value(ceiling_dur, ceiling_dots)
        if phrase_smallest >= ceiling:
            return level
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/corpus_filter.py apps/exercises/tests/test_corpus_filter.py
git commit -m "feat: corpus_filter assign_level — level taxonomy and classification"
```

### 3b: Phrase validity rules

- [ ] **Step 1: Write failing tests for validity rules**

Add to `apps/exercises/tests/test_corpus_filter.py`:

```python
from apps.exercises.utils.corpus_filter import is_valid_phrase


class CorpusFilterValidityTests(SimpleTestCase):
    def _notes(self, *specs):
        """specs: list of (duration, dots) tuples."""
        return [{"pitch": "B4", "duration": d, "dots": dot} for d, dot in specs]

    def test_valid_phrase_passes(self):
        # 3/4, 2 bars, all quarters, last >= second-to-last
        notes = self._notes(("q", 0), ("q", 0), ("q", 0), ("q", 0), ("q", 0), ("h", 0))
        self.assertTrue(is_valid_phrase("3/4", notes, measures=2))

    def test_last_note_shorter_than_preceding_fails(self):
        notes = self._notes(("h", 0), ("q", 0), ("q", 0), ("q", 0), ("q", 0), ("8", 0))
        self.assertFalse(is_valid_phrase("3/4", notes, measures=2))

    def test_wrong_total_duration_fails(self):
        # Only 1.5 bars of 3/4 instead of 2
        notes = self._notes(("q", 0), ("q", 0), ("q", 0), ("q", 0))
        self.assertFalse(is_valid_phrase("3/4", notes, measures=2))

    def test_single_note_phrase_is_valid(self):
        # Edge: only one note — ending condition vacuously true
        notes = self._notes(("h", 0), ("h", 0))
        self.assertTrue(is_valid_phrase("2/2", notes, measures=1))

    def test_compound_meter_valid(self):
        # 6/8, 1 bar: dotted quarter + dotted quarter = 1 bar
        notes = self._notes(("q", 1), ("q", 1))
        # But last >= second-to-last (both equal), and total fills 1 bar
        self.assertTrue(is_valid_phrase("6/8", notes, measures=1))

    def test_unsupported_meter_fails(self):
        notes = self._notes(("q", 0), ("q", 0))
        self.assertFalse(is_valid_phrase("5/4", notes, measures=1))
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter.CorpusFilterValidityTests -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: FAIL — `ImportError: cannot import name 'is_valid_phrase'`

- [ ] **Step 3: Implement is_valid_phrase**

Add to `apps/exercises/utils/corpus_filter.py` (after `assign_level`):

```python
from apps.exercises.utils.barline_exercise_builder import meter_info, duration_quarters


def _total_bars_quarters(time_signature: str, measures: int) -> Fraction:
    beats_per_measure, beat_quarters = meter_info(time_signature)
    return Fraction(measures * beats_per_measure) * beat_quarters


def is_valid_phrase(time_signature: str, notes: list[dict], measures: int) -> bool:
    """Return True if notes satisfy all phrase validity rules."""
    # Rule: supported meter
    try:
        beats_per_measure, beat_quarters = meter_info(time_signature)
    except ValueError:
        return False

    # Rule: duration sum exactly fills measures
    expected = _total_bars_quarters(time_signature, measures)
    actual = sum(
        duration_quarters(n["duration"], n.get("dots", 0)) for n in notes
    )
    if actual != expected:
        return False

    # Rule: ending condition — last note >= preceding note (skip if only 1 note)
    if len(notes) >= 2:
        last = duration_quarters(notes[-1]["duration"], notes[-1].get("dots", 0))
        prev = duration_quarters(notes[-2]["duration"], notes[-2].get("dots", 0))
        if last < prev:
            return False

    return True
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/corpus_filter.py apps/exercises/tests/test_corpus_filter.py
git commit -m "feat: corpus_filter is_valid_phrase — duration, ending, and meter rules"
```

### 3c: Duration doubling for derived meters

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_corpus_filter.py`:

```python
from apps.exercises.utils.corpus_filter import double_durations


class CorpusFilterDoublingTests(SimpleTestCase):
    def test_eighth_becomes_quarter(self):
        notes = [{"pitch": "B4", "duration": "8", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "q", "dots": 0}])

    def test_dotted_eighth_becomes_dotted_quarter(self):
        notes = [{"pitch": "B4", "duration": "8", "dots": 1}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "q", "dots": 1}])

    def test_sixteenth_becomes_eighth(self):
        notes = [{"pitch": "B4", "duration": "16", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "8", "dots": 0}])

    def test_quarter_becomes_half(self):
        notes = [{"pitch": "B4", "duration": "q", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "h", "dots": 0}])

    def test_dotted_quarter_becomes_dotted_half(self):
        notes = [{"pitch": "B4", "duration": "q", "dots": 1}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "h", "dots": 1}])

    def test_half_becomes_whole(self):
        notes = [{"pitch": "B4", "duration": "h", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "w", "dots": 0}])

    def test_whole_note_raises_overflow(self):
        notes = [{"pitch": "B4", "duration": "w", "dots": 0}]
        with self.assertRaises(ValueError):
            double_durations(notes)

    def test_dotted_half_raises_overflow(self):
        notes = [{"pitch": "B4", "duration": "h", "dots": 1}]
        with self.assertRaises(ValueError):
            double_durations(notes)

    def test_multiple_notes_all_doubled(self):
        notes = [
            {"pitch": "B4", "duration": "8", "dots": 0},
            {"pitch": "C5", "duration": "q", "dots": 0},
        ]
        result = double_durations(notes)
        self.assertEqual(result[0]["duration"], "q")
        self.assertEqual(result[1]["duration"], "h")
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter.CorpusFilterDoublingTests -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: FAIL — `ImportError: cannot import name 'double_durations'`

- [ ] **Step 3: Implement double_durations**

Add to `apps/exercises/utils/corpus_filter.py`:

```python
_DOUBLE_MAP = {
    "16": "8",
    "8":  "q",
    "q":  "h",
    "h":  "w",
}


def double_durations(notes: list[dict]) -> list[dict]:
    """Return new notes list with all durations doubled. Raises ValueError on overflow."""
    result = []
    for n in notes:
        dur = n["duration"]
        dots = n.get("dots", 0)
        if dur not in _DOUBLE_MAP:
            raise ValueError(f"Cannot double duration '{dur}': would exceed whole note")
        # dotted whole would exceed a whole — reject
        new_dur = _DOUBLE_MAP[dur]
        if new_dur == "w" and dots > 0:
            raise ValueError(f"Cannot double dotted {dur}: would exceed whole note")
        result.append({**n, "duration": new_dur, "dots": dots})
    return result
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/corpus_filter.py apps/exercises/tests/test_corpus_filter.py
git commit -m "feat: corpus_filter double_durations — derived meter note doubling with overflow guard"
```

### 3d: Fingerprinting and deduplication

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_corpus_filter.py`:

```python
from apps.exercises.utils.corpus_filter import phrase_fingerprint


class CorpusFilterFingerprintTests(SimpleTestCase):
    def _notes(self, *specs):
        return [{"pitch": p, "duration": d, "dots": dot} for p, d, dot in specs]

    def test_same_rhythm_different_pitch_same_fingerprint(self):
        n1 = self._notes(("B4", "q", 0), ("C5", "h", 0))
        n2 = self._notes(("G4", "q", 0), ("A4", "h", 0))
        self.assertEqual(phrase_fingerprint("3/4", n1), phrase_fingerprint("3/4", n2))

    def test_different_rhythm_different_fingerprint(self):
        n1 = self._notes(("B4", "q", 0), ("B4", "h", 0))
        n2 = self._notes(("B4", "h", 0), ("B4", "q", 0))
        self.assertNotEqual(phrase_fingerprint("3/4", n1), phrase_fingerprint("3/4", n2))

    def test_different_meter_different_fingerprint(self):
        n1 = self._notes(("B4", "q", 0), ("B4", "q", 0))
        self.assertNotEqual(phrase_fingerprint("3/4", n1), phrase_fingerprint("4/4", n1))

    def test_fingerprint_is_12_char_hex(self):
        n = self._notes(("B4", "q", 0))
        fp = phrase_fingerprint("3/4", n)
        self.assertEqual(len(fp), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter.CorpusFilterFingerprintTests -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: FAIL

- [ ] **Step 3: Implement phrase_fingerprint**

Add to `apps/exercises/utils/corpus_filter.py`:

```python
def phrase_fingerprint(time_signature: str, notes: list[dict]) -> str:
    """12-char hex fingerprint of rhythm only (pitch-agnostic)."""
    rhythm = ",".join(f"{n['duration']}.{n.get('dots', 0)}" for n in notes)
    raw = f"{time_signature}|{rhythm}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/corpus_filter.py apps/exercises/tests/test_corpus_filter.py
git commit -m "feat: corpus_filter phrase_fingerprint — rhythm-only deduplication hash"
```

### 3e: Music21 corpus parsing and iter_phrases

- [ ] **Step 1: Write tests with synthetic music21-like data**

Add to `apps/exercises/tests/test_corpus_filter.py`:

```python
from unittest.mock import patch, MagicMock
from fractions import Fraction as F
from apps.exercises.utils.corpus_filter import iter_phrases, PhraseResult


def _make_m21_note(dur_type, dots=0, pitch_name="B", pitch_octave=4):
    """Build a minimal mock music21 note."""
    n = MagicMock()
    n.isNote = True
    n.isRest = False
    n.tie = None
    n.duration.type = dur_type
    n.duration.dots = dots
    n.duration.quarterLength = float(
        {"whole": 4, "half": 2, "quarter": 1, "eighth": 0.5, "16th": 0.25}[dur_type]
        * (1.5 ** dots)
    )
    n.pitch.step = pitch_name
    n.pitch.octave = pitch_octave
    n.pitch.accidental = None
    return n


def _make_m21_stream(notes, time_sig_str="3/4"):
    """Build a mock music21 flat stream."""
    stream = MagicMock()
    num, den = map(int, time_sig_str.split("/"))
    ts = MagicMock()
    ts.numerator = num
    ts.denominator = den
    stream.recurse.return_value.getElementsByClass.return_value = [ts]
    stream.flatten.return_value.notesAndRests = notes
    return stream


class CorpusFilterIterPhrasesTests(SimpleTestCase):
    @patch("apps.exercises.utils.corpus_filter._iter_corpus_streams")
    def test_yields_valid_level1_phrase(self, mock_streams):
        # 3/4, 2 bars of quarters ending on half — should be L1
        notes = [
            _make_m21_note("quarter"), _make_m21_note("quarter"), _make_m21_note("quarter"),
            _make_m21_note("quarter"), _make_m21_note("quarter"), _make_m21_note("half"),
        ]
        mock_streams.return_value = [("fake/path.abc", _make_m21_stream(notes, "3/4"))]

        results = list(iter_phrases(levels=[1]))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].level, 1)
        self.assertEqual(results[0].time_signature, "3/4")
        self.assertEqual(len(results[0].notes), 6)
        self.assertEqual(results[0].measures, 2)

    @patch("apps.exercises.utils.corpus_filter._iter_corpus_streams")
    def test_skips_phrase_with_rest(self, mock_streams):
        rest = MagicMock()
        rest.isNote = False
        rest.isRest = True
        notes = [
            _make_m21_note("quarter"), rest, _make_m21_note("quarter"),
            _make_m21_note("quarter"), _make_m21_note("quarter"), _make_m21_note("half"),
        ]
        mock_streams.return_value = [("fake/path.abc", _make_m21_stream(notes, "3/4"))]
        results = list(iter_phrases(levels=[1]))
        self.assertEqual(results, [])

    @patch("apps.exercises.utils.corpus_filter._iter_corpus_streams")
    def test_deduplicates_identical_rhythm(self, mock_streams):
        notes = [
            _make_m21_note("quarter"), _make_m21_note("quarter"), _make_m21_note("half"),
            _make_m21_note("quarter"), _make_m21_note("quarter"), _make_m21_note("half"),
        ]
        # Provide same stream twice — should yield only one phrase
        stream = _make_m21_stream(notes, "3/4")
        mock_streams.return_value = [("a.abc", stream), ("b.abc", stream)]
        results = list(iter_phrases(levels=[1]))
        self.assertEqual(len(results), 1)

    @patch("apps.exercises.utils.corpus_filter._iter_corpus_streams")
    def test_yields_derived_level7_from_simple_source(self, mock_streams):
        # 3/4 phrase with eighths — L2 source, doubled → 3/2 L7
        notes = [
            _make_m21_note("quarter"), _make_m21_note("eighth"), _make_m21_note("eighth"),
            _make_m21_note("quarter"), _make_m21_note("quarter"), _make_m21_note("half"),
        ]
        mock_streams.return_value = [("fake/path.abc", _make_m21_stream(notes, "3/4"))]
        results = list(iter_phrases(levels=[7]))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].level, 7)
        self.assertEqual(results[0].time_signature, "3/2")
        # All durations doubled: quarter→half, eighth→quarter, half→whole
        dur_types = [n["duration"] for n in results[0].notes]
        self.assertEqual(dur_types, ["h", "q", "q", "h", "h", "w"])
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter.CorpusFilterIterPhrasesTests -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: FAIL

- [ ] **Step 3: Implement PhraseResult, _iter_corpus_streams, and iter_phrases**

Add to `apps/exercises/utils/corpus_filter.py`:

```python
# music21 duration type name → our duration code
_M21_DUR_TYPE = {
    "whole":    "w",
    "half":     "h",
    "quarter":  "q",
    "eighth":   "8",
    "16th":     "16",
}

# Derived meter mapping: source_time_sig → derived_time_sig
_DERIVE_METER = {
    "2/4": "2/2", "3/4": "3/2", "4/4": "4/2",
    "6/8": "6/4", "9/8": "9/4", "12/8": "12/4",
}

# Levels that use derived meters (generated by doubling source phrases)
_DERIVED_LEVELS = {7, 8}
# Source levels to derive L7 from (simple), L8 from (compound)
_L7_SOURCES = {2, 3}
_L8_SOURCES = {5, 6}


@dataclass
class PhraseResult:
    level: int
    time_signature: str
    notes: list[dict]
    measures: int
    source_path: str
    phrase_offset: int  # index of first note in the source stream
    fingerprint: str


def _iter_corpus_streams(collections=("ryansMammoth", "oneills1850", "essenFolksong")):
    """Yield (path_str, music21_stream) for each tune in the corpus."""
    from music21 import corpus, converter, stream as m21stream

    for path in corpus.getPaths():
        path_str = str(path)
        if not any(c in path_str for c in collections):
            continue
        try:
            parsed = converter.parse(path_str)
        except Exception:
            continue
        if isinstance(parsed, m21stream.Opus):
            for score in parsed.scores:
                yield path_str, score
        else:
            yield path_str, parsed


def _extract_notes_from_stream(stream) -> tuple[str | None, list[dict]]:
    """Extract (time_signature_str, notes_list) from a music21 stream. Returns (None, []) on failure."""
    try:
        ts_list = list(stream.recurse().getElementsByClass("TimeSignature"))
        if not ts_list:
            return None, []
        ts = ts_list[0]
        time_sig = f"{ts.numerator}/{ts.denominator}"
        notes_and_rests = list(stream.flatten().notesAndRests)
        notes = []
        for elem in notes_and_rests:
            if elem.isRest:
                return None, []  # Rule: no rests
            if not elem.isNote:
                continue
            if elem.tie and elem.tie.type in ("stop", "continue"):
                return None, []  # Rule: no ties (simplified — reject any tied note)
            dur_type = elem.duration.type
            if dur_type not in _M21_DUR_TYPE:
                return None, []
            dots = elem.duration.dots
            pitch_step = elem.pitch.step
            acc = elem.pitch.accidental
            alter = int(acc.alter) if acc else 0
            octave = elem.pitch.octave
            pitch_name = pitch_step + ("#" if alter > 0 else "b" if alter < 0 else "") + str(octave)
            notes.append({"pitch": pitch_name, "duration": _M21_DUR_TYPE[dur_type], "dots": dots})
        return time_sig, notes
    except Exception:
        return None, []


def _slice_phrases(notes: list[dict], time_signature: str, prefer_bars: int, fallback_bars: int) -> list[tuple[list[dict], int]]:
    """
    Slice notes into phrases of prefer_bars measures, falling back to fallback_bars.
    Returns list of (phrase_notes, phrase_offset).
    """
    from apps.exercises.utils.barline_exercise_builder import meter_info, duration_quarters
    try:
        beats_per_measure, beat_quarters = meter_info(time_signature)
    except ValueError:
        return []

    bar_quarters = Fraction(beats_per_measure) * beat_quarters
    results = []

    for target_bars in (prefer_bars, fallback_bars):
        target_quarters = bar_quarters * target_bars
        i = 0
        while i < len(notes):
            accumulated = Fraction(0)
            j = i
            phrase = []
            while j < len(notes) and accumulated < target_quarters:
                n = notes[j]
                accumulated += duration_quarters(n["duration"], n.get("dots", 0))
                phrase.append(n)
                j += 1
            if accumulated == target_quarters and len(phrase) > 0:
                results.append((phrase, i))
                i = j
            else:
                i += 1  # no clean slice starting here

    return results


def iter_phrases(levels: list[int] | None = None) -> Iterator[PhraseResult]:
    """
    Yield PhraseResult for each valid phrase extracted from the music21 corpus.
    Deduplicates by rhythm fingerprint within the run.
    If levels is None, yields all levels 1-8.
    """
    target_levels = set(levels) if levels is not None else set(range(1, 9))
    source_levels = target_levels - _DERIVED_LEVELS
    need_l7_sources = bool(target_levels & {7})
    need_l8_sources = bool(target_levels & {8})

    seen_fingerprints: set[str] = set()

    def _emit(level, time_sig, notes, measures, source_path, offset) -> PhraseResult | None:
        fp = phrase_fingerprint(time_sig, notes)
        if fp in seen_fingerprints:
            return None
        if not is_valid_phrase(time_sig, notes, measures):
            return None
        seen_fingerprints.add(fp)
        return PhraseResult(
            level=level,
            time_signature=time_sig,
            notes=notes,
            measures=measures,
            source_path=source_path,
            phrase_offset=offset,
            fingerprint=fp,
        )

    for source_path, stream in _iter_corpus_streams():
        time_sig, all_notes = _extract_notes_from_stream(stream)
        if not time_sig or not all_notes:
            continue

        # Determine smallest note value for level assignment
        from fractions import Fraction
        smallest_val = min(
            _dur_value(n["duration"], n.get("dots", 0)) for n in all_notes
        )
        # Find duration type for smallest_val (ignore dots for ceiling check)
        # Map back from Fraction to duration string
        smallest_dur = min(
            _DUR_FRACTION, key=lambda d: abs(_DUR_FRACTION[d] - smallest_val)
        )
        smallest_dots = 1 if smallest_val < _DUR_FRACTION[smallest_dur] else 0

        direct_level = assign_level(time_sig, smallest_dur, smallest_dots)

        # Direct (non-derived) phrases
        if direct_level in source_levels:
            prefer = 4 if direct_level in {3, 5, 6} else 2
            fallback = 2
            for phrase, offset in _slice_phrases(all_notes, time_sig, prefer, fallback):
                result = _emit(direct_level, time_sig, phrase, len(phrase) // 1 or 2, source_path, offset)
                # Recalculate actual measures for this phrase
                from apps.exercises.utils.barline_exercise_builder import meter_info, duration_quarters
                beats_per_measure, beat_quarters = meter_info(time_sig)
                bar_q = Fraction(beats_per_measure) * beat_quarters
                phrase_q = sum(duration_quarters(n["duration"], n.get("dots", 0)) for n in phrase)
                measures = int(phrase_q / bar_q)
                result = _emit(direct_level, time_sig, phrase, measures, source_path, offset)
                if result:
                    yield result

        # Derived phrases (L7 from simple, L8 from compound)
        derived_target = None
        derived_ts = _DERIVE_METER.get(time_sig)
        if derived_ts:
            if need_l7_sources and direct_level in _L7_SOURCES:
                derived_target = 7
            elif need_l8_sources and direct_level in _L8_SOURCES:
                derived_target = 8

        if derived_target and derived_ts:
            try:
                doubled = double_durations(all_notes)
            except ValueError:
                continue
            prefer = 4
            for phrase, offset in _slice_phrases(doubled, derived_ts, prefer, 2):
                from apps.exercises.utils.barline_exercise_builder import meter_info, duration_quarters
                beats_per_measure, beat_quarters = meter_info(derived_ts)
                bar_q = Fraction(beats_per_measure) * beat_quarters
                phrase_q = sum(duration_quarters(n["duration"], n.get("dots", 0)) for n in phrase)
                measures = int(phrase_q / bar_q)
                result = _emit(derived_target, derived_ts, phrase, measures, source_path, offset)
                if result:
                    yield result
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/corpus_filter.py apps/exercises/tests/test_corpus_filter.py
git commit -m "feat: corpus_filter iter_phrases — music21 ABC/krn parsing, slicing, derivation"
```

---

## Task 4: Extend management command with `--source corpus`

**Files:**
- Modify: `apps/exercises/management/commands/generate_unit2_barline_exercises.py`
- Modify: `apps/exercises/tests/test_generate_unit2_barline_exercises.py`

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generate_unit2_barline_exercises.py`:

```python
from unittest.mock import patch
from apps.exercises.utils.corpus_filter import PhraseResult


def _fake_phrase(level, time_sig, measures, fingerprint, source_path="a.abc", offset=0):
    from apps.exercises.utils.barline_exercise_builder import meter_info
    beats_per_measure, beat_quarters = meter_info(time_sig)
    from fractions import Fraction
    bar_beats = beats_per_measure * measures
    notes = [{"pitch": "B4", "duration": "q", "dots": 0}] * bar_beats
    # Adjust for compound: use dotted quarters
    if "8" in time_sig:
        notes = [{"pitch": "B4", "duration": "q", "dots": 1}] * (beats_per_measure * measures)
    return PhraseResult(
        level=level,
        time_signature=time_sig,
        notes=notes,
        measures=measures,
        source_path=source_path,
        phrase_offset=offset,
        fingerprint=fingerprint,
    )


class GenerateUnit2BarlineCorpusTests(TestCase):
    def _create_user(self, email="corpus-seed@example.com"):
        return get_user_model().objects.create_user(email=email, password="pw")

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_creates_level_playlist(self, mock_iter):
        user = self._create_user()
        mock_iter.return_value = iter([
            _fake_phrase(1, "3/4", 2, "aabbcc112233"),
        ])
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            source="corpus",
            level=1,
            public=True,
        )
        playlist = Playlist.objects.get(
            name="Unit 2 — Add Barlines, Level 1",
            authored_by=user,
        )
        self.assertTrue(playlist.is_adaptive)
        self.assertIn("unit:2_L1", playlist.skill_tags)
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, order=1)
        self.assertEqual(link.exercise.complexity, 1)
        self.assertTrue(link.is_adaptive_entry)

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_dry_run_does_not_save(self, mock_iter):
        user = self._create_user("dry-run@example.com")
        mock_iter.return_value = iter([
            _fake_phrase(1, "3/4", 2, "dryrun000001"),
        ])
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            source="corpus",
            dry_run=True,
        )
        self.assertFalse(
            Playlist.objects.filter(name__startswith="Unit 2 — Add Barlines, Level").exists()
        )

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_idempotent_rerun(self, mock_iter):
        user = self._create_user("idempotent@example.com")
        phrase = _fake_phrase(1, "3/4", 2, "idempotent01")
        mock_iter.side_effect = [iter([phrase]), iter([phrase])]
        call_command("generate_unit2_barline_exercises", author=user.email, source="corpus", level=1)
        call_command("generate_unit2_barline_exercises", author=user.email, source="corpus", level=1)
        self.assertEqual(Exercise.objects.filter(description__startswith="Unit 2 barline L1").count(), 1)

    @patch("apps.exercises.management.commands.generate_unit2_barline_exercises.iter_phrases")
    def test_corpus_source_limit_restricts_count(self, mock_iter):
        user = self._create_user("limit@example.com")
        mock_iter.return_value = iter([
            _fake_phrase(1, "3/4", 2, f"limit{i:06d}") for i in range(5)
        ])
        call_command(
            "generate_unit2_barline_exercises",
            author=user.email,
            source="corpus",
            level=1,
            limit=2,
        )
        self.assertEqual(
            ExercisePlaylistOrdered.objects.filter(
                playlist__name="Unit 2 — Add Barlines, Level 1"
            ).count(),
            2,
        )
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 manage.py test apps.exercises.tests.test_generate_unit2_barline_exercises -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: FAIL — `unrecognized arguments: --source corpus`

- [ ] **Step 3: Extend the management command**

Replace `apps/exercises/management/commands/generate_unit2_barline_exercises.py` with:

```python
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_umto_barline_exercise
from apps.exercises.utils.barline_exercise_builder import build_barline_payload
from apps.exercises.utils.corpus_filter import iter_phrases

PLAYLIST_NAME = "Unit 2 — Add Barlines"
PLAYLIST_SKILL_TAGS = [
    "unit:2",
    "unit:2_rhythm",
    "unit:2_meter_simple",
    "unit:2_meter_compound",
]

SIMPLE_METERS = {"2/4", "3/4", "4/4"}
COMPOUND_METER_BEATS = {
    "6/8": 2,
    "9/8": 3,
    "12/8": 4,
}


def _manual_notes(meter, measures):
    if measures < 1:
        raise CommandError("--measures must be at least 1")
    if meter in SIMPLE_METERS:
        beats = int(meter.split("/")[0]) * measures
        return [{"pitch": "B4", "duration": "q", "dots": 0} for _ in range(beats)]
    if meter in COMPOUND_METER_BEATS:
        beats = COMPOUND_METER_BEATS[meter] * measures
        return [{"pitch": "B4", "duration": "q", "dots": 1} for _ in range(beats)]
    raise CommandError(f"Unsupported meter: {meter}")


def _level_playlist_name(level: int) -> str:
    return f"Unit 2 — Add Barlines, Level {level}"


def _level_skill_tags(level: int) -> list[str]:
    return ["unit:2", "unit:2_rhythm", f"unit:2_L{level}"]


class Command(BaseCommand):
    help = "Create Unit 2 add-barlines exercises"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")
        # manual-only args
        parser.add_argument("--count", type=int, default=1)
        parser.add_argument("--meter", default="3/4")
        parser.add_argument("--measures", type=int, default=2)
        parser.add_argument("--pitch-mode", default="rhythm_only")
        parser.add_argument(
            "--source",
            choices=["manual", "corpus", "essen", "kern"],
            default="manual",
        )
        # corpus-only args
        parser.add_argument("--level", type=int, default=None,
                            help="Level 1-8; omit for all levels")
        parser.add_argument("--limit", type=int, default=None,
                            help="Max phrases per level (default: unlimited)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print counts without saving")

    def handle(self, *args, **options):
        source = options["source"]

        if source in ("essen", "kern"):
            raise CommandError(
                "Essen/Kern import is not implemented yet; "
                "use --source manual or --source corpus"
            )

        user_model = get_user_model()
        try:
            author = user_model.objects.get(email=options["author"])
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        if source == "corpus":
            self._handle_corpus(author, options)
        else:
            self._handle_manual(author, options)

    def _handle_manual(self, author, options):
        if options["count"] < 1:
            raise CommandError("--count must be at least 1")

        notes = _manual_notes(options["meter"], options["measures"])

        playlist, created = Playlist.objects.get_or_create(
            name=PLAYLIST_NAME,
            authored_by=author,
            defaults=dict(
                is_dynamic=False,
                is_adaptive=False,
                is_public=options["public"],
                skill_tags=list(PLAYLIST_SKILL_TAGS),
            ),
        )
        if not created:
            playlist.is_dynamic = False
            playlist.is_adaptive = False
            if options["public"]:
                playlist.is_public = True
            merged_skill_tags = list(playlist.skill_tags or [])
            for tag in PLAYLIST_SKILL_TAGS:
                if tag not in merged_skill_tags:
                    merged_skill_tags.append(tag)
            playlist.skill_tags = merged_skill_tags
            playlist.save()

        exercise_is_public = playlist.is_public
        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        for index in range(options["count"]):
            payload = build_barline_payload(
                time_signature=options["meter"],
                clef="treble",
                notes=list(notes),
                measures=options["measures"],
                show_time_signature=index % 2 == 0,
                pitch_mode=options["pitch_mode"],
                source="Unit 2 add barlines manual seed",
                tags=list(PLAYLIST_SKILL_TAGS),
            )
            exercise = save_umto_barline_exercise(
                description=f"Unit 2 add barlines {options['meter']} #{index + 1}",
                author=author,
                payload=payload,
                is_public=exercise_is_public,
                overwrite=True,
            )
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist,
                exercise=exercise,
                order=index + 1,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {options['count']} barline exercise(s) in '{playlist.name}'"
            )
        )

    def _handle_corpus(self, author, options):
        is_public = options["public"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        target_levels = [options["level"]] if options["level"] else list(range(1, 9))

        # Group phrases by level; collect sorted by (source_path, phrase_offset)
        from collections import defaultdict
        by_level: dict[int, list] = defaultdict(list)
        seen_per_level: dict[int, set] = defaultdict(set)

        for phrase in iter_phrases(levels=target_levels):
            level = phrase.level
            if limit and len(by_level[level]) >= limit:
                continue
            if phrase.fingerprint in seen_per_level[level]:
                continue
            seen_per_level[level].add(phrase.fingerprint)
            by_level[level].append(phrase)

        # Sort each level by (source_path, phrase_offset) for stable ordering
        for level in by_level:
            by_level[level].sort(key=lambda p: (p.source_path, p.phrase_offset))

        if dry_run:
            for level in sorted(by_level):
                self.stdout.write(f"Level {level}: {len(by_level[level])} phrase(s) (dry run)")
            return

        for level in sorted(by_level):
            phrases = by_level[level]
            skill_tags = _level_skill_tags(level)
            playlist_name = _level_playlist_name(level)

            playlist, _ = Playlist.objects.get_or_create(
                name=playlist_name,
                authored_by=author,
                defaults=dict(
                    is_dynamic=False,
                    is_adaptive=True,
                    is_public=is_public,
                    skill_tags=skill_tags,
                ),
            )
            playlist.is_dynamic = False
            playlist.is_adaptive = True
            playlist.skill_tags = skill_tags
            if is_public:
                playlist.is_public = True
            playlist.save()

            # Upsert all exercises
            exercises = []
            for phrase in phrases:
                description = f"Unit 2 barline L{level} {phrase.fingerprint}"
                payload = build_barline_payload(
                    time_signature=phrase.time_signature,
                    clef="treble",
                    notes=phrase.notes,
                    measures=phrase.measures,
                    show_time_signature=True,
                    pitch_mode="rhythm_only",
                    source=phrase.source_path,
                    tags=skill_tags,
                )
                ex = save_umto_barline_exercise(
                    description=description,
                    author=author,
                    payload=payload,
                    is_public=is_public,
                    overwrite=True,
                    complexity=level,
                )
                exercises.append(ex)

            # Rebuild playlist links (delete-then-reinsert for idempotency)
            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for order, ex in enumerate(exercises, 1):
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=order,
                    is_adaptive_entry=(order == 1),
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Level {level}: {len(exercises)} exercise(s) in '{playlist_name}'"
                )
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 manage.py test apps.exercises.tests.test_generate_unit2_barline_exercises -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 5: Run all barline tests**

```bash
python3 manage.py test apps.exercises.tests.test_barline_exercise_builder apps.exercises.tests.test_barline_exercise_save apps.exercises.tests.test_corpus_filter apps.exercises.tests.test_generate_unit2_barline_exercises -v 2 2>&1 | grep -E "FAIL|ERROR|OK"
```

Expected: OK

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/management/commands/generate_unit2_barline_exercises.py \
        apps/exercises/tests/test_generate_unit2_barline_exercises.py
git commit -m "feat: generate_unit2_barline_exercises --source corpus — 8 levelled playlists from music21 folk corpus"
```

---

## Task 5: Smoke test against live corpus

This is an optional integration test to verify the real corpus yields phrases. It is guarded so it won't run in CI unless the env var is set.

- [ ] **Step 1: Add guarded smoke test**

Add to `apps/exercises/tests/test_corpus_filter.py`:

```python
import os
import pytest


@pytest.mark.skipif(
    not os.environ.get("HARMONYLAB_CORPUS_SMOKE"),
    reason="Set HARMONYLAB_CORPUS_SMOKE=1 to run live corpus test",
)
class CorpusFilterSmokeTests(SimpleTestCase):
    def test_live_corpus_yields_phrases_for_all_direct_levels(self):
        from apps.exercises.utils.corpus_filter import iter_phrases
        from collections import Counter
        counts = Counter()
        for phrase in iter_phrases(levels=[1, 2, 3, 4, 5, 6]):
            counts[phrase.level] += 1
            if all(counts[l] >= 5 for l in [1, 2, 4, 5]):
                break
        for level in [1, 2, 4, 5]:
            self.assertGreater(counts[level], 0, f"Level {level} yielded no phrases")
```

- [ ] **Step 2: Verify smoke test skips normally**

```bash
python3 manage.py test apps.exercises.tests.test_corpus_filter.CorpusFilterSmokeTests -v 2 2>&1 | grep -E "skip|SKIP|OK"
```

Expected: skipped

- [ ] **Step 3: Run smoke test manually against live corpus**

```bash
HARMONYLAB_CORPUS_SMOKE=1 python3 manage.py test apps.exercises.tests.test_corpus_filter.CorpusFilterSmokeTests -v 2 2>&1 | grep -E "FAIL|ERROR|OK|Level"
```

Expected: OK with counts > 0 for levels 1, 2, 4, 5

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/tests/test_corpus_filter.py
git commit -m "test: add guarded smoke test for live corpus phrase extraction"
```

---

## Task 6: Generate the playlists

- [ ] **Step 1: Run the command against the live corpus (dry run first)**

```bash
python3 manage.py generate_unit2_barline_exercises \
  --author avnerdorman@gmail.com \
  --source corpus \
  --dry-run
```

Expected output: `Level N: X phrase(s) (dry run)` for each level with nonzero counts.

- [ ] **Step 2: Generate all levels**

```bash
python3 manage.py generate_unit2_barline_exercises \
  --author avnerdorman@gmail.com \
  --source corpus \
  --public
```

Expected: `Level N: X exercise(s) in 'Unit 2 — Add Barlines, Level N'` for each level.

- [ ] **Step 3: Verify in Django admin or shell**

```bash
python3 manage.py shell -c "
from apps.exercises.models import Playlist, ExercisePlaylistOrdered
for pl in Playlist.objects.filter(name__startswith='Unit 2 — Add Barlines, Level').order_by('name'):
    count = ExercisePlaylistOrdered.objects.filter(playlist=pl).count()
    print(f'{pl.name}: {count} exercises, adaptive={pl.is_adaptive}')
"
```

Expected: 8 playlists, each with > 0 exercises, `adaptive=True`.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "chore: generate Unit 2 barline level playlists from music21 corpus"
```
