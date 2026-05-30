# Roman From Clausulae — page_title Titling + Units 10–14 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `generate_roman_from_clausulae` from unit-9 simple cadences to units 10/11/12/14 via engine compound/double cadences with music21-derived Roman numerals and automatic unit-binning, title both clausulae generators from the Compendium `page_title` vocabulary, and make the per-unit answer table a taxonomy-derived artifact shared by JS and Python.

**Architecture:** A taxonomy-derived `unit_allowed_answers` artifact becomes the single source of truth for per-unit RN answer sets (consumed by both `exercise_definition.js` and the generator). The generator enumerates engine cadences, realizes them through shared realization helpers, derives Roman numerals through a new VoiceEvent→music21 converter, bins each exercise into the lowest covering unit, gives it a page_title-based student title (stored in `metadata.source`) plus a short hashed `description` for idempotency, and writes one idempotent playlist per populated unit. Unit 13 (Rule of the Octave) **and double cadences** are explicitly out of scope (deferred); this round uses **simple + compound** cadence families only.

**Title fields (important):** the student-facing title is the long page_title string, stored in UMTO `metadata.source` (no length limit; renders as `introText`). The Django `Exercise.description` field is `max_length=60` and is the idempotency key (`description + author`), so it gets a **short hashed key**, not the page_title.

**Tech Stack:** Python 3.13, Django management commands, `music21`, the sibling `clausulae-project` engine (already `pip install -e`-available), RequireJS/AMD frontend.

**Spec:** [docs/superpowers/specs/2026-05-30-roman-from-clausulae-units-10-14-design.md](../specs/2026-05-30-roman-from-clausulae-units-10-14-design.md)

**Test command (all Python tasks):**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest <path> -q
```
The worktree's `.python-version` is already `system` (Python 3.13). No DB is required by any test below.

---

## File Structure

**Create:**
- `apps/exercises/unit_allowed_answers.py` — taxonomy+overrides → per-unit RN set loader (single source of merge logic).
- `apps/exercises/data/unit_allowed_answers.overrides.json` — checked-in `null`/override entries (units 19–20).
- `apps/exercises/management/commands/build_unit_allowed_answers.py` — emits the generated AMD module from the loader.
- `lab/static/js/src/config/unit_allowed_answers.js` — **generated** AMD module (do not hand-edit).
- `apps/exercises/clausulae_titles.py` — `(family, n_voices)→page_title` map, compound-4v figure detector, long student title + short hashed description.
- `apps/exercises/clausulae_realize.py` — shared realization helpers (promoted from b1): `_DUR_*`, `_realize_events`, `_compound_events`.
- `apps/exercises/utils/voice_events_music21.py` — VoiceEvent→music21 `Score` converter.
- `apps/exercises/roman_derivation.py` — music21 RN derivation + normalization + binning.
- `apps/exercises/tests/test_unit_allowed_answers.py`
- `apps/exercises/tests/test_clausulae_titles.py`
- `apps/exercises/tests/test_voice_events_music21.py`
- `apps/exercises/tests/test_roman_derivation.py`
- `apps/exercises/tests/test_roman_from_clausulae_units.py`

**Modify:**
- `apps/exercises/utils/music21_builder.py:163` — fix `_pitch_to_midi` missing `return`.
- `lab/static/js/src/models/exercise_definition.js:15-90` — replace inline `UNIT_ALLOWED_ANSWERS` with the AMD import.
- `apps/exercises/management/commands/generate_clausulae_b1.py` — import realization from the shared module; titles from the shared map (B2/B3/B4/B11/B12 only — **not** B1).
- `apps/exercises/management/commands/generate_roman_from_clausulae.py` — pools (simple+compound), binning, titles, derived RNs, per-unit playlists.
- `CLAUDE.md`, `AGENTS.md` — mark Blocker 1 resolved.
- `docs/management_commands.md` — update the generator entry.

**Deferred (out of scope, like unit 13):** double cadences (`enumerate_double_3voice`/`enumerate_double_4voice`) — their realization (5-position quintuples) is unbuilt. Fast-follow if the bin histogram shows units 10/11/14 underpopulated by simple+compound alone.

---

## Task 1: Taxonomy-derived answer-table loader

**Files:**
- Create: `apps/exercises/data/unit_allowed_answers.overrides.json`
- Create: `apps/exercises/unit_allowed_answers.py`
- Test: `apps/exercises/tests/test_unit_allowed_answers.py`

- [ ] **Step 1: Create the overrides file**

`apps/exercises/data/unit_allowed_answers.overrides.json`:
```json
{
  "19": null,
  "20": null
}
```

- [ ] **Step 2: Write the failing test**

`apps/exercises/tests/test_unit_allowed_answers.py`:
```python
from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers


def test_unit_9_matches_taxonomy_cumulative():
    table = compute_unit_allowed_answers()
    assert table[9] == ["I", "i", "V", "V7"]


def test_unit_14_includes_diatonic_sevenths():
    table = compute_unit_allowed_answers()
    assert "ii7" in table[14]
    assert "vii°7" in table[14]
    # cumulative: unit 14 is a superset of unit 12
    assert set(table[12]).issubset(set(table[14]))


def test_override_units_are_null_passthrough():
    table = compute_unit_allowed_answers()
    assert table[19] is None
    assert table[20] is None


def test_all_taxonomy_units_present():
    table = compute_unit_allowed_answers()
    for n in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18):
        assert isinstance(table[n], list) and table[n], f"unit {n} missing"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_unit_allowed_answers.py -q`
Expected: FAIL with `ModuleNotFoundError: apps.exercises.unit_allowed_answers`

- [ ] **Step 4: Implement the loader**

`apps/exercises/unit_allowed_answers.py`:
```python
"""Single source of truth for per-unit Roman-numeral answer sets.

Derived from music_theory_taxonomy_with_branches.json (analysis.roman.cumulative),
with a checked-in overrides file for units the taxonomy does not enumerate
(e.g. modulation units 19-20, which are null pass-through).
"""
from __future__ import annotations

import json
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TAXONOMY_PATH = os.path.join(_REPO_ROOT, "music_theory_taxonomy_with_branches.json")
_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "data", "unit_allowed_answers.overrides.json")


def _walk_units(node):
    """Yield every dict that looks like a unit (has 'n' and dict 'analysis')."""
    if isinstance(node, dict):
        if "n" in node and isinstance(node.get("analysis"), dict):
            yield node
        for value in node.values():
            yield from _walk_units(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_units(item)


def compute_unit_allowed_answers() -> dict:
    """Return {unit_int: [rn, ...] | None} merged from taxonomy then overrides."""
    with open(_TAXONOMY_PATH) as fh:
        taxonomy = json.load(fh)

    table: dict = {}
    for unit in _walk_units(taxonomy):
        roman = unit["analysis"].get("roman")
        if not isinstance(roman, dict):
            continue
        cumulative = roman.get("cumulative")
        if not cumulative:
            continue
        try:
            n = int(str(unit["n"]).strip())
        except (TypeError, ValueError):
            continue
        table[n] = [entry["value"] for entry in cumulative]

    with open(_OVERRIDES_PATH) as fh:
        overrides = json.load(fh)
    for key, value in overrides.items():
        table[int(key)] = value  # overrides win (including explicit null)

    return table
```

- [ ] **Step 5: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_unit_allowed_answers.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/unit_allowed_answers.py apps/exercises/data/unit_allowed_answers.overrides.json apps/exercises/tests/test_unit_allowed_answers.py
git commit -m "feat: taxonomy-derived per-unit RN answer-table loader"
```

---

## Task 2: Build command emits the generated AMD module

**Files:**
- Create: `apps/exercises/management/commands/build_unit_allowed_answers.py`
- Create (generated): `lab/static/js/src/config/unit_allowed_answers.js`
- Test: `apps/exercises/tests/test_unit_allowed_answers.py` (append)

- [ ] **Step 1: Write the failing test (append to the existing file)**

Append to `apps/exercises/tests/test_unit_allowed_answers.py`:
```python
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# test file: apps/exercises/tests/test_unit_allowed_answers.py → repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATED_JS = _REPO_ROOT / "lab/static/js/src/config/unit_allowed_answers.js"


def _parse_generated_js():
    """Extract the JSON object literal embedded in the generated AMD module."""
    text = _GENERATED_JS.read_text()
    match = re.search(r"return\s+(\{.*\});\s*\}\);\s*$", text, re.DOTALL)
    assert match, "generated module does not match expected AMD shape"
    return json.loads(match.group(1))


def test_generated_js_matches_loader():
    # Regenerate, then compare to the loader output.
    subprocess.run(
        [sys.executable, "manage.py", "build_unit_allowed_answers"],
        cwd=_REPO_ROOT,
        check=True,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "harmony.settings.local"},
    )
    from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers
    expected = {str(k): v for k, v in compute_unit_allowed_answers().items()}
    assert _parse_generated_js() == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_unit_allowed_answers.py::test_generated_js_matches_loader -q`
Expected: FAIL — `build_unit_allowed_answers` command does not exist (CommandError / nonzero exit).

- [ ] **Step 3: Implement the build command**

`apps/exercises/management/commands/build_unit_allowed_answers.py`:
```python
"""Generate lab/static/js/src/config/unit_allowed_answers.js from the taxonomy.

The emitted AMD module is the frontend's view of the per-unit RN answer table.
It is generated — never hand-edit it. Re-run after taxonomy or override changes.
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers

_OUT_PATH = os.path.join(
    settings.BASE_DIR, "lab", "static", "js", "src", "config", "unit_allowed_answers.js"
)


class Command(BaseCommand):
    help = "Generate the AMD unit_allowed_answers.js module from the taxonomy."

    def handle(self, *args, **options):
        table = {str(k): v for k, v in sorted(compute_unit_allowed_answers().items())}
        body = json.dumps(table, indent=2, ensure_ascii=False)
        module = (
            "// GENERATED by `manage.py build_unit_allowed_answers` — do not edit.\n"
            "// Source of truth: music_theory_taxonomy_with_branches.json\n"
            "define([], function () {\n"
            f"  return {body};\n"
            "});\n"
        )
        with open(_OUT_PATH, "w") as fh:
            fh.write(module)
        self.stdout.write(self.style.SUCCESS(f"Wrote {_OUT_PATH}"))
```

If `settings.BASE_DIR` does not point at the repo root in `harmony.settings.local`, replace `_OUT_PATH` with a path computed relative to this file (`os.path.join(os.path.dirname(__file__), "../../../../../lab/static/js/src/config/unit_allowed_answers.js")` then `os.path.abspath`). Verify with the next step.

- [ ] **Step 4: Run the command and the test**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py build_unit_allowed_answers
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_unit_allowed_answers.py -q
```
Expected: command prints `Wrote .../unit_allowed_answers.js`; tests PASS (5 passed). Confirm the file exists and begins with the `// GENERATED` banner and `define([], function () {`.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/build_unit_allowed_answers.py lab/static/js/src/config/unit_allowed_answers.js apps/exercises/tests/test_unit_allowed_answers.py
git commit -m "feat: build command emits generated unit_allowed_answers.js"
```

---

## Task 3: Wire exercise_definition.js to the generated module

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js:1-90`

- [ ] **Step 1: Add the AMD dependency**

In `lab/static/js/src/models/exercise_definition.js`, change the `define` header (lines 1-10) to add the module. Before:
```javascript
define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
  "app/models/key_context_logic",
  "app/models/input_method_logic",
  "tonal",
], function (_, Config, ScoreTimeline, Analyze, KeySignature, KeyContext, InputMethodLogic, Tonal) {
```
After:
```javascript
define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
  "app/models/key_context_logic",
  "app/models/input_method_logic",
  "app/config/unit_allowed_answers",
  "tonal",
], function (_, Config, ScoreTimeline, Analyze, KeySignature, KeyContext, InputMethodLogic, UNIT_ALLOWED_ANSWERS_RAW, Tonal) {
```

- [ ] **Step 2: Replace the inline literal**

Delete the entire inline `var UNIT_ALLOWED_ANSWERS = { ... };` block (lines 15-90) and replace with:
```javascript
  // Per-unit allowed Roman-numeral answers. Source of truth is
  // music_theory_taxonomy_with_branches.json; this module is generated by
  // `manage.py build_unit_allowed_answers`. Keys arrive as strings.
  var UNIT_ALLOWED_ANSWERS = _.mapKeys(UNIT_ALLOWED_ANSWERS_RAW, function (v, k) {
    return parseInt(k, 10);
  });
```
`applySkillFilter` already does `UNIT_ALLOWED_ANSWERS.hasOwnProperty(unitNum)` and `UNIT_ALLOWED_ANSWERS[unitNum]` with integer `unitNum`; `_.mapKeys` to integer keys preserves that contract. The `null` entries (19, 20) survive as `null` and keep the existing pass-through behavior.

- [ ] **Step 3: Sanity-check the JS parses**

Run: `node -e "require('fs').readFileSync('lab/static/js/src/models/exercise_definition.js','utf8'); console.log('readable')"`
Expected: prints `readable` (this only confirms the file is intact; full AMD wiring is verified in the browser smoke test, Task 11).

Grep to confirm the inline literal is gone:
Run: `grep -c "Unit 9: Tonic & dominant" lab/static/js/src/models/exercise_definition.js`
Expected: `0`

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "refactor: exercise_definition.js consumes generated unit_allowed_answers"
```

---

## Task 4: page_title map + student title + short description

**Files:**
- Create: `apps/exercises/clausulae_titles.py`
- Test: `apps/exercises/tests/test_clausulae_titles.py`

Two title outputs: `student_title()` is the long page_title-based string for UMTO
`metadata.source` (no length limit). `short_description()` is the ≤60-char DB
idempotency key (`Exercise.description` is `max_length=60`).

- [ ] **Step 1: Write the failing test**

`apps/exercises/tests/test_clausulae_titles.py`:
```python
import pytest

from apps.exercises.clausulae_titles import page_title, student_title, short_description


def test_simple_three_voices():
    assert page_title("simple", 3) == "Simple Cadences in Three Voices"


def test_compound_two_and_three():
    assert page_title("compound", 2) == "Compound Cadences in Two Voices"
    assert page_title("compound", 3) == "Compound Cadences in Three Voices"


def test_double_four_voices():
    assert page_title("double", 4) == "Double Cadences in Four Voices"


def test_compound_four_voice_figure_variants():
    assert page_title("compound", 4, upper_figures={5, 4}) == "Compound Cadences with 5/4 in Four Voices"
    assert page_title("compound", 4, upper_figures={6, 5}) == "Compound Cadences with 6/5 in Four Voices"
    assert page_title("compound", 4, upper_figures={6, 4}) == "Compound Cadences with 6/4 in Four Voices"


def test_compound_four_voice_default_when_unknown():
    assert page_title("compound", 4, upper_figures={2, 7}) == "Compound Cadences with 6/4 in Four Voices"


def test_student_title_is_page_title_plus_key():
    assert student_title("simple", 3, key="C") == "Simple Cadences in Three Voices in C major"


def test_short_description_fits_60_and_is_unique():
    # Even the longest page_title family must yield a <=60 char description.
    d1 = short_description("compound", 4, key="Bb", unit=12, fingerprint="D:D-Ti-D A:S-Fa-M T:M-Re-D B:D-Sol-D")
    d2 = short_description("compound", 4, key="Bb", unit=12, fingerprint="D:D-Ti-D A:S-La-S T:M-Re-M B:D-Sol-D")
    assert len(d1) <= 60
    assert d1 != d2  # different fingerprints -> different keys
    assert d1.startswith("RfC u12 compound 4v Bb ")


def test_short_description_is_stable():
    args = dict(key="C", unit=9, fingerprint="D:D-Ti-D B:D-Sol-D")
    assert short_description("simple", 3, **args) == short_description("simple", 3, **args)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_clausulae_titles.py -q`
Expected: FAIL — `ModuleNotFoundError: apps.exercises.clausulae_titles`

- [ ] **Step 3: Implement the map + titles**

`apps/exercises/clausulae_titles.py`:
```python
"""Clausulae cadence families -> Compendium page_title strings + title helpers.

Titles use the musical-type vocabulary from the Galant Compendium so student
exercises read as harmony, not Clausulae jargon (per the lessons spec).

- student_title(): long, human-facing; stored in UMTO metadata.source (no limit).
- short_description(): <=60-char stable key for Exercise.description (idempotency).
"""
from __future__ import annotations

import hashlib

_BASE = {
    ("simple", 2): "Simple Cadences in Two Voices",
    ("simple", 3): "Simple Cadences in Three Voices",
    ("simple", 4): "Simple Cadences in Four Voices",
    ("compound", 2): "Compound Cadences in Two Voices",
    ("compound", 3): "Compound Cadences in Three Voices",
    ("double", 3): "Double Cadences in Three Voices",
    ("double", 4): "Double Cadences in Four Voices",
}

_COMPOUND_4V_BY_FIGURE = {
    frozenset({5, 4}): "Compound Cadences with 5/4 in Four Voices",
    frozenset({6, 5}): "Compound Cadences with 6/5 in Four Voices",
    frozenset({6, 4}): "Compound Cadences with 6/4 in Four Voices",
}
_COMPOUND_4V_DEFAULT = "Compound Cadences with 6/4 in Four Voices"


def page_title(family: str, n_voices: int, upper_figures: set | None = None) -> str:
    if family == "compound" and n_voices == 4:
        if upper_figures is not None:
            return _COMPOUND_4V_BY_FIGURE.get(frozenset(upper_figures), _COMPOUND_4V_DEFAULT)
        return _COMPOUND_4V_DEFAULT
    try:
        return _BASE[(family, n_voices)]
    except KeyError as exc:
        raise KeyError(f"No page_title for family={family!r} n_voices={n_voices}") from exc


def student_title(family: str, n_voices: int, *, key: str,
                  upper_figures: set | None = None) -> str:
    """Long student-facing title for metadata.source."""
    return f"{page_title(family, n_voices, upper_figures=upper_figures)} in {key} major"


def short_description(family: str, n_voices: int, *, key: str, unit: int,
                      fingerprint: str) -> str:
    """<=60-char stable idempotency key. Prefix is human-scannable; hash ensures
    uniqueness per voice combination."""
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:8]
    desc = f"RfC u{unit} {family} {n_voices}v {key} {digest}"
    assert len(desc) <= 60, f"description too long ({len(desc)}): {desc!r}"
    return desc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_clausulae_titles.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/clausulae_titles.py apps/exercises/tests/test_clausulae_titles.py
git commit -m "feat: page_title map, long student title, short hashed description"
```

---

## Task 5: Fix `_pitch_to_midi` + VoiceEvent→music21 converter

**Files:**
- Modify: `apps/exercises/utils/music21_builder.py:163`
- Create: `apps/exercises/utils/voice_events_music21.py`
- Test: `apps/exercises/tests/test_voice_events_music21.py`

- [ ] **Step 1: Fix the missing return in `_pitch_to_midi`**

In `apps/exercises/utils/music21_builder.py`, the function computes `midi` but never returns it. Change (line 163 area):
```python
    semitone = step_semitones.get(step, 0)
    midi = (octave + 1) * 12 + semitone + alter
```
to:
```python
    semitone = step_semitones.get(step, 0)
    midi = (octave + 1) * 12 + semitone + alter
    return midi
```

- [ ] **Step 2: Write the failing test**

`apps/exercises/tests/test_voice_events_music21.py`:
```python
import pytest

from apps.exercises.umto import Pitch, VoiceEvent, Voices

m21 = pytest.importorskip("music21")


def _satb_c_major_triad():
    """One onset: C3/E4/G4/C5 (a C-major sonority across SATB)."""
    return Voices(
        S=[VoiceEvent(kind="note", pitch=Pitch(step="C", alter=0, octave=5, midi=72),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
        A=[VoiceEvent(kind="note", pitch=Pitch(step="G", alter=0, octave=4, midi=67),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
        T=[VoiceEvent(kind="note", pitch=Pitch(step="E", alter=0, octave=4, midi=64),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
        B=[VoiceEvent(kind="note", pitch=Pitch(step="C", alter=0, octave=3, midi=48),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
    )


def test_converter_preserves_midi_pitches():
    from apps.exercises.utils.voice_events_music21 import score_from_voices
    score = score_from_voices(_satb_c_major_triad())
    midis = sorted(n.pitch.midi for n in score.recurse().notes)
    assert midis == [48, 64, 67, 72]


def test_converter_chordifies_to_one_vertical():
    from apps.exercises.utils.voice_events_music21 import score_from_voices
    score = score_from_voices(_satb_c_major_triad())
    chords = list(score.chordify().recurse().getElementsByClass("Chord"))
    assert len(chords) == 1
    assert sorted(p.midi for p in chords[0].pitches) == [48, 64, 67, 72]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_voice_events_music21.py -q`
Expected: FAIL — `ModuleNotFoundError: apps.exercises.utils.voice_events_music21`

- [ ] **Step 4: Implement the converter**

`apps/exercises/utils/voice_events_music21.py`:
```python
"""Build a music21 Score from UMTO VoiceEvent lists.

The generated VoiceEvents already carry MIDI in `pitch.midi`, so this converter
does not depend on the (separately fixed) music21_builder._pitch_to_midi helper.
One music21 Part per non-empty SATB voice; rests for `kind == "rest"`.
"""
from __future__ import annotations

from music21 import note, stream


def _append_event(part, event):
    ql = float(event.duration)
    if event.kind == "rest" or event.pitch is None:
        part.append(note.Rest(quarterLength=ql))
        return
    n = note.Note(midi=event.pitch.midi, quarterLength=ql)
    part.append(n)


def score_from_voices(voices) -> "stream.Score":
    score = stream.Score()
    for voice_id in ("S", "A", "T", "B"):
        events = getattr(voices, voice_id, None) or []
        if not events:
            continue
        part = stream.Part(id=voice_id)
        for event in events:
            _append_event(part, event)
        score.insert(0, part)
    return score
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_voice_events_music21.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/utils/music21_builder.py apps/exercises/utils/voice_events_music21.py apps/exercises/tests/test_voice_events_music21.py
git commit -m "fix: _pitch_to_midi return + add VoiceEvent->music21 converter"
```

---

## Task 6: Roman-numeral derivation + normalization

**Files:**
- Create: `apps/exercises/roman_derivation.py`
- Test: `apps/exercises/tests/test_roman_derivation.py`

The answer vocabulary uses the degree sign `°` (e.g. `vii°6`, `ii°7`). music21's `RomanNumeral.figure` uses `o` for diminished (e.g. `viio6`) and figured-bass inversion suffixes (`6`, `64`, `65`, ...). Normalize `o → °` and keep the figure suffix; binning later rejects any figure not present in a unit's set.

- [ ] **Step 1: Write the failing test**

`apps/exercises/tests/test_roman_derivation.py`:
```python
import pytest

from apps.exercises.umto import Pitch, VoiceEvent, Voices

pytest.importorskip("music21")


def _ivi_cadence_c_major():
    """Three onsets in C major: I (C/E/G), V (B/D/G), I (C/E/G) — SAB, half/half/whole."""
    def ev(step, octave, midi, ql):
        return VoiceEvent(kind="note", pitch=Pitch(step=step, alter=0, octave=octave, midi=midi),
                          duration=ql, duration_type="h" if ql == 2.0 else "w", dots=0, is_target=True)
    return Voices(
        S=[ev("G", 4, 67, 2.0), ev("G", 4, 67, 2.0), ev("G", 4, 67, 4.0)],
        A=[ev("E", 4, 64, 2.0), ev("D", 4, 62, 2.0), ev("E", 4, 64, 4.0)],
        T=[],
        B=[ev("C", 3, 48, 2.0), ev("G", 2, 43, 2.0), ev("C", 3, 48, 4.0)],
    )


def test_derive_simple_authentic_cadence():
    from apps.exercises.roman_derivation import derive_cadence
    verticals = derive_cadence(_ivi_cadence_c_major(), key="C")
    assert [v["rn"] for v in verticals] == ["I", "V", "I"]
    # offsets are actual sounding offsets (half/half/whole)
    assert [v["offset"] for v in verticals] == [0.0, 2.0, 4.0]
    # grading MIDI comes from the chordified vertical at each offset, not a position index
    assert verticals[0]["midi"] == [48, 64, 67]   # C3 E4 G4
    assert verticals[1]["midi"] == [43, 62, 67]   # G2 D4 G4


def test_normalize_diminished_uses_degree_sign():
    from apps.exercises.roman_derivation import normalize_figure
    assert normalize_figure("viio6") == "vii°6"
    assert normalize_figure("ii") == "ii"
    assert normalize_figure("V7") == "V7"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_derivation.py -q`
Expected: FAIL — `ModuleNotFoundError: apps.exercises.roman_derivation`

- [ ] **Step 3: Implement derivation + normalization**

`apps/exercises/roman_derivation.py`:
```python
"""Derive Roman numerals + grading pitches for a generated cadence via music21.

Chordify the SATB Score and, at each vertical, run romanNumeralFromChord and
collect the sounding MIDI pitches. Both the analysis offset and the grading MIDI
come from the SAME chordified vertical, so they stay aligned for any rhythm
(simple, compound, held notes, rests) — no position-index assumptions.
"""
from __future__ import annotations

from music21 import key as m21key
from music21 import roman

from apps.exercises.utils.voice_events_music21 import score_from_voices


def normalize_figure(figure: str) -> str:
    """music21 figure -> answer-vocabulary string (e.g. 'viio6' -> 'vii°6')."""
    return figure.replace("o", "°")


def derive_cadence(voices, *, key: str) -> list[dict]:
    """Return [{"offset": float, "rn": str, "midi": [int, ...]}, ...] per vertical."""
    score = score_from_voices(voices)
    tonal_key = m21key.Key(key)
    chordified = score.chordify()
    result: list[dict] = []
    for chord in chordified.recurse().getElementsByClass("Chord"):
        rn = roman.romanNumeralFromChord(chord, tonal_key)
        result.append({
            "offset": float(chord.offset),
            "rn": normalize_figure(rn.figure),
            "midi": sorted(p.midi for p in chord.pitches),
        })
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_derivation.py -q`
Expected: PASS (2 passed). If `derive_simple_authentic_cadence` returns something other than `["I","V","I"]` (music21 spelling differences), adjust `normalize_figure` minimally to cover the observed token and re-run — do not broaden beyond what the test requires. If `chord.offset` for the chordified verticals is not the expected sounding offset, inspect `score.chordify().flatten()` offsets and adjust the assertion to the real values before proceeding.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/roman_derivation.py apps/exercises/tests/test_roman_derivation.py
git commit -m "feat: music21 Roman-numeral derivation + answer-vocab normalization"
```

---

## Task 7: Binning helper

**Files:**
- Create: in `apps/exercises/roman_derivation.py` (append `bin_unit`)
- Test: `apps/exercises/tests/test_roman_derivation.py` (append)

- [ ] **Step 1: Write the failing test (append)**

Append to `apps/exercises/tests/test_roman_derivation.py`:
```python
def test_bin_unit_lowest_cover():
    from apps.exercises.roman_derivation import bin_unit
    table = {
        9: ["I", "i", "V", "V7"],
        10: ["I", "i", "V", "V7", "I6", "V6", "vii°6"],
        12: ["I", "i", "V", "V7", "I6", "V6", "vii°6", "I64", "V64"],
        14: ["I", "i", "V", "V7", "I6", "V6", "vii°6", "I64", "V64", "ii7"],
    }
    candidates = [9, 10, 12, 14]
    assert bin_unit({"I", "V"}, table, candidates) == 9
    assert bin_unit({"I", "V6", "I6"}, table, candidates) == 10
    assert bin_unit({"I", "I64", "V"}, table, candidates) == 12
    assert bin_unit({"I", "ii7"}, table, candidates) == 14
    assert bin_unit({"I", "N6"}, table, candidates) is None  # uncovered -> reject
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_derivation.py::test_bin_unit_lowest_cover -q`
Expected: FAIL — `cannot import name 'bin_unit'`

- [ ] **Step 3: Implement `bin_unit` (append to `roman_derivation.py`)**

```python
def bin_unit(rn_set, table: dict, candidate_units) -> int | None:
    """Lowest candidate unit whose allowed-answer set covers rn_set, else None.

    Unit 13 is intentionally excluded from candidate_units (deferred); since
    unit 14 is a superset of 13, RNs needing 13-only chords land in 14.
    """
    needed = set(rn_set)
    for unit in sorted(candidate_units):
        allowed = table.get(unit)
        if allowed is None:
            continue
        if needed.issubset(set(allowed)):
            return unit
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_derivation.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/roman_derivation.py apps/exercises/tests/test_roman_derivation.py
git commit -m "feat: lowest-covering-unit binning helper"
```

---

## Task 8: `build_binned_payload` — derived RNs, binning, titles, per-unit answers

**Files:**
- Modify: `apps/exercises/management/commands/generate_roman_from_clausulae.py`
- Test: `apps/exercises/tests/test_roman_from_clausulae_units.py`

This task adds the per-exercise payload builder that replaces the hardcoded `_CADENCE_RN` / `_RN_CHOICES_MAJOR` / `_build_identification_payload` path with derived RNs and binning. Keep the existing `_tonal_valid`, `_save_exercise`, and `_build_playlist` helpers (pool wiring + realization come in Task 9).

- [ ] **Step 1: Write the failing test (pure helpers, no DB, no clausulae lib)**

`apps/exercises/tests/test_roman_from_clausulae_units.py`:
```python
import pytest

from apps.exercises.umto import Pitch, VoiceEvent, Voices

pytest.importorskip("music21")


def _ivi_voices():
    def ev(step, octave, midi, ql, dt):
        return VoiceEvent(kind="note", pitch=Pitch(step=step, alter=0, octave=octave, midi=midi),
                          duration=ql, duration_type=dt, dots=0, is_target=True)
    return Voices(
        S=[ev("G", 4, 67, 2.0, "h"), ev("G", 4, 67, 2.0, "h"), ev("G", 4, 67, 4.0, "w")],
        A=[ev("E", 4, 64, 2.0, "h"), ev("D", 4, 62, 2.0, "h"), ev("E", 4, 64, 4.0, "w")],
        T=[],
        B=[ev("C", 3, 48, 2.0, "h"), ev("G", 2, 43, 2.0, "h"), ev("C", 3, 48, 4.0, "w")],
    )


def test_build_payload_bins_simple_cadence_to_unit_9():
    from apps.exercises.management.commands.generate_roman_from_clausulae import (
        build_binned_payload,
    )
    result = build_binned_payload(_ivi_voices(), key="C", family="simple", n_voices=3,
                                   fingerprint="D:D-Ti-D B:D-Sol-D")
    assert result is not None
    payload, unit, derived = result
    assert unit == 9
    assert derived == ["I", "V", "I"]
    assert payload["analysisType"] == "roman"
    assert payload["allowed_answers"] == ["I", "i", "V", "V7"]
    # one is_target analysis slice per derived RN
    targets = [s for s in payload["score"]["umto"]["analysis"] if s["is_target"]]
    assert len(targets) == 3
    # student-facing title lives in metadata.source (no length limit)
    assert payload["score"]["umto"]["metadata"]["source"] == "Simple Cadences in Three Voices in C major"
    # DB description is the short hashed key, <=60 chars
    assert payload["description"].startswith("RfC u9 simple 3v C ")
    assert len(payload["description"]) <= 60
```

(Confirm the payload key paths: inspect one existing exercise via
`DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py dump_exercise <id>`. If
`payload["score"]["umto"]["analysis"]` / `["metadata"]["source"]` differ, adjust the
assertions to the real shape before implementing.)

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_from_clausulae_units.py -q`
Expected: FAIL — `cannot import name 'build_binned_payload'`

- [ ] **Step 3: Add `build_binned_payload` to the command module**

Add to `apps/exercises/management/commands/generate_roman_from_clausulae.py` (module level), reusing existing imports plus the new helpers:
```python
from apps.exercises.clausulae_titles import student_title, short_description
from apps.exercises.roman_derivation import derive_cadence, bin_unit
from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers

_CANDIDATE_UNITS = [9, 10, 11, 12, 14]  # unit 13 (ROO) + double cadences deferred
_UNIT_TABLE = compute_unit_allowed_answers()


def build_binned_payload(voices, *, key, family, n_voices, fingerprint, upper_figures=None):
    """Return (payload, unit, derived_rns) or None if no unit covers the RNs."""
    verticals = derive_cadence(voices, key=key)          # [{offset, rn, midi}, ...]
    rn_list = [v["rn"] for v in verticals]
    unit = bin_unit(set(rn_list), _UNIT_TABLE, _CANDIDATE_UNITS)
    if unit is None:
        return None

    analysis = [
        AnalysisSlice(
            offset=v["offset"],
            content=AnalysisLayer(roman_numeral=v["rn"], raw_roman_numeral=v["rn"]),
            unit_tags=[unit],
            is_target=True,
        )
        for v in verticals
    ]
    # Grading aligned to the SAME verticals (offset-aware; correct for any rhythm).
    grading = [
        GradingSlice(offset=v["offset"], target_midi_pitches=v["midi"])
        for v in verticals
    ]
    vids = {vid for vid in ("S", "A", "T", "B") if getattr(voices, vid)}

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=student_title(family, n_voices, key=key, upper_figures=upper_figures),
            key=HL_KEY.get(key, "jC_"),
            meter="2/2",
            clef=_staff_dist(vids),
            complexity_score=unit,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="dropdown",
            unit=unit,
        ),
        voices=voices,
        analysis=analysis,
        grading=grading,
    )

    payload = umto.to_frontend_payload(unit=unit, analysis_type="roman")
    payload["analysisType"] = "roman"
    payload["identMode"] = "practice"
    payload["allowed_answers"] = list(_UNIT_TABLE[unit])
    payload["display"] = {
        "showNotation": True,
        "hideKeyLabel": False,
        "showScaleDegrees": False,
        "maxMeasures": 2,
    }
    payload["inputModeFixed"] = "dropdown"
    payload["description"] = short_description(
        family, n_voices, key=key, unit=unit, fingerprint=fingerprint
    )
    return payload, unit, rn_list
```
Note: this replaces the old `_build_identification_payload` (delete it and its hardcoded `_CADENCE_RN`/`_RN_CHOICES_MAJOR`). `GradingSlice` is already imported by the command. `Voices` is accepted directly by `UMTO(voices=...)`. The old `_grading_slices` helper is no longer used by this command — grading now comes from `derive_cadence` verticals; remove `_grading_slices` if nothing else references it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_from_clausulae_units.py -q`
Expected: PASS (1 passed). Fix the `payload["score"]["umto"]["analysis"]` key path in the test if step 1's note revealed a different shape.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_roman_from_clausulae.py apps/exercises/tests/test_roman_from_clausulae_units.py
git commit -m "feat: build_binned_payload — derived RNs, binning, page_title, per-unit answers"
```

---

## Task 9: Shared realization module + simple/compound pools

**Files:**
- Create: `apps/exercises/clausulae_realize.py`
- Modify: `apps/exercises/management/commands/generate_roman_from_clausulae.py`
- Test: `apps/exercises/tests/test_clausulae_realize.py`

Compound realization already exists in `generate_clausulae_b1.py` (`_realize_events`, `_compound_events`, `_DUR_COMPOUND_*`, `_OCTAVE`, `_m21_note_to_pitch`). Promote those into a shared module so both generators use one implementation, and add `voices_from_combo()` that maps an enumerator tuple to a UMTO `Voices` for the families in scope. **Double cadences are out of scope this round** (no realization exists for the 5-position quintuples) — `voices_from_combo` raises for them.

- [ ] **Step 1: Write the failing test**

`apps/exercises/tests/test_clausulae_realize.py`:
```python
import os
import sys

import pytest

# clausulae lib lives in the sibling repo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../clausulae-project")))
pytest.importorskip("clausulae.generate")

from clausulae.generate import enumerate_simple, enumerate_compound_3voice  # noqa: E402
from apps.exercises.clausulae_realize import voices_from_combo  # noqa: E402
from apps.exercises.umto import Voices  # noqa: E402


def test_simple_3voice_combo_realizes_to_voices():
    combo = next(c for c in enumerate_simple(n_voices=3, require_bass=True)
                 if any(name == "Discant" for name, _, _ in c))
    voices = voices_from_combo(combo, key="C", family="simple", n_voices=3)
    assert isinstance(voices, Voices)
    assert voices.S and voices.B           # discant + bass present
    assert len(voices.S) == 3              # ANT/PEN/ULT


def test_compound_3voice_combo_has_late_voice_rest():
    combo = next((b, e, l, pi) for b, e, l, pi in
                 enumerate_compound_3voice(require_discant=True, require_bass=True)
                 if l[0] == "Discant")
    voices = voices_from_combo(combo, key="C", family="compound", n_voices=3)
    # τ=1 (Discant=S) starts with a quarter rest
    assert voices.S[0].kind == "rest"


def test_double_family_raises():
    with pytest.raises(NotImplementedError):
        voices_from_combo(("x",), key="C", family="double", n_voices=3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_clausulae_realize.py -q`
Expected: FAIL — `ModuleNotFoundError: apps.exercises.clausulae_realize`

- [ ] **Step 3: Implement the shared module**

Copy the realization primitives **verbatim** from `generate_clausulae_b1.py` (so behavior is identical), then add `voices_from_combo`. `apps/exercises/clausulae_realize.py`:
```python
"""Shared clausulae realization — promoted from generate_clausulae_b1.

One implementation of the simple/compound voice realization, consumed by both
generate_clausulae_b1 and generate_roman_from_clausulae. Double-cadence
realization is not implemented (out of scope).
"""
from __future__ import annotations

import os
import sys

_CLAUSULAE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "clausulae-project")
)
if _CLAUSULAE_ROOT not in sys.path:
    sys.path.insert(0, _CLAUSULAE_ROOT)

from clausulae.realize import key_realize  # noqa: E402

from apps.exercises.umto import Pitch, VoiceEvent, Voices  # noqa: E402

_OCTAVE = {"S": 5, "A": 4, "T": 4, "B": 3}
_DUR_SIMPLE = [("h", 2.0), ("h", 2.0), ("w", 4.0)]
_DUR_COMPOUND_EARLY = [("h", 2.0), ("h", 2.0), ("w", 4.0)]
_DUR_COMPOUND_LATE = [("h", 2.0), ("q", 1.0), ("w", 4.0)]


def _m21_note_to_pitch(n) -> Pitch:
    p = n.pitch
    alter_map = {None: 0, "sharp": 1, "flat": -1, "double-sharp": 2, "double-flat": -2}
    alter = alter_map.get(p.accidental.name if p.accidental else None, 0)
    return Pitch(step=p.step, alter=alter, octave=p.octave, midi=p.midi)


def realize_events(triple, key: str, voice_id: str, dur_scheme=None) -> list:
    notes = key_realize(triple, key, octave=_OCTAVE[voice_id])
    scheme = dur_scheme or _DUR_SIMPLE
    return [
        VoiceEvent(kind="note", pitch=_m21_note_to_pitch(n), duration=ql,
                   duration_type=dt, dots=0, is_target=True)
        for n, (dt, ql) in zip(notes, scheme)
    ]


def compound_events(triple, key: str, vid: str, tau: int) -> list:
    if tau == 0:
        return realize_events(triple, key, vid, dur_scheme=_DUR_COMPOUND_EARLY)
    rest = VoiceEvent(kind="rest", duration=1.0, duration_type="q", dots=0, is_target=False)
    return [rest] + realize_events(triple, key, vid, dur_scheme=_DUR_COMPOUND_LATE)


def _voices(vmap: dict) -> Voices:
    return Voices(S=vmap.get("S", []), A=vmap.get("A", []),
                  T=vmap.get("T", []), B=vmap.get("B", []))


def voices_from_combo(combo, *, key: str, family: str, n_voices: int) -> Voices:
    """Map an enumerator tuple to a UMTO Voices object (simple or compound)."""
    if family == "simple":
        # combo: iterable of (name, idx, triple); map Discant->S, Bass->B, others->A/T
        vid_for = {"Discant": "S", "Bass": "B"}
        used = set()
        vmap: dict = {}
        for name, _idx, triple in combo:
            vid = vid_for.get(name) or next(v for v in ("A", "T") if v not in used)
            used.add(vid)
            vmap[vid] = realize_events(triple, key, vid)
        return _voices(vmap)

    if family == "compound" and n_voices == 3:
        # combo: (c_bass, c_early, c_late, pi); mirrors generate_clausulae_b1 B12 3v
        c_bass, c_early, c_late, _pi = combo
        vmap = {
            "B": compound_events(c_bass[2], key, "B", tau=0),
            "A": compound_events(c_early[2], key, "A", tau=0),
            "S": compound_events(c_late[2], key, "S", tau=1),
        }
        return _voices(vmap)

    if family == "compound" and n_voices == 4:
        # combo: (c_bass, c_u1, c_u2, c_late); mirrors B12 4v slot mapping
        c_bass, c_u1, c_u2, c_late = combo
        vmap = {
            "B": compound_events(c_bass[2], key, "B", tau=0),
            "T": compound_events(c_u1[2], key, "T", tau=0),
            "A": compound_events(c_u2[2], key, "A", tau=0),
            "S": compound_events(c_late[2], key, "S", tau=1),
        }
        return _voices(vmap)

    raise NotImplementedError(f"voices_from_combo: family={family!r} n_voices={n_voices}")
```
(If `enumerate_compound_*` tuple ordering differs from the b1 usage at `generate_clausulae_b1.py:565-628`, match b1 exactly — b1 is the working reference. Confirm with the print snippet in Step 5.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_clausulae_realize.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Confirm enumerator tuple shapes (one-time check before wiring the command)**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -c "
import sys, os
sys.path.insert(0, os.path.abspath('../clausulae-project'))
from clausulae.generate import enumerate_compound_3voice, enumerate_compound_4voice
for fn in (enumerate_compound_3voice, enumerate_compound_4voice):
    items = list(fn(require_discant=True, require_bass=True))
    print(fn.__name__, 'n=', len(items), 'first=', items[0] if items else None)
"
```
Confirm the tuple arity/order matches `voices_from_combo` (and b1 lines 565/604). Fix `voices_from_combo` if they differ, re-run Step 4.

- [ ] **Step 6: Wire pools + binning + per-unit playlists into the command**

In `generate_roman_from_clausulae.py`:
1. Replace the local realization helpers with imports from the shared module:
   `from apps.exercises.clausulae_realize import voices_from_combo`. Remove the now-duplicate local `_realize_events`/`_OCTAVE`/`_m21_note_to_pitch`/`_DUR_SIMPLE` if present.
2. Add the in-scope enumerator imports to the guarded clausulae import block:
   ```python
   from clausulae.generate import (
       enumerate_simple, enumerate_compound_3voice, enumerate_compound_4voice,
   )
   ```
3. Pool selector + family matrix (simple + compound only; double deferred):
   ```python
   FAMILY_VOICES = [("simple", 3), ("simple", 4),
                    ("compound", 3), ("compound", 4)]

   def _combos_for(family, n_voices):
       if family == "simple":
           return [c for c in enumerate_simple(n_voices=n_voices, require_bass=True)
                   if any(name == "Discant" for name, _, _ in c)]
       if family == "compound" and n_voices == 3:
           return [c for c in enumerate_compound_3voice(require_discant=True, require_bass=True)
                   if c[2][0] == "Discant"]
       if family == "compound" and n_voices == 4:
           return list(enumerate_compound_4voice(require_discant=True, require_bass=True))
       return []
   ```
4. Add the compound-4v figure helper (generic interval of upper voices above bass at the penult):
   ```python
   _STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}

   def _diatonic(p):
       return p.octave * 7 + _STEP_INDEX[p.step]

   def _upper_figures_at(voices, idx):
       figs = set()
       bass = voices.B[idx].pitch if idx < len(voices.B) and voices.B[idx].pitch else None
       if bass is None:
           return figs
       for vid in ("S", "A"):
           seq = getattr(voices, vid)
           if idx < len(seq) and seq[idx].pitch:
               figs.add((_diatonic(seq[idx].pitch) - _diatonic(bass)) % 7 + 1)
       return figs
   ```
   For compound-4v, the penult onset index is the second-to-last attack. Compound τ=1 voices begin with a rest, so use the bass (τ=0, no rest) timeline: `penult_idx = len(voices.B) - 2`.
5. `_make_exercises(family, n_voices, author, options, ...)` returns `dict[int, list[Exercise]]`:
   ```python
   def _make_exercises(family, n_voices, author, options, stdout, style):
       by_unit, rejected = {}, 0
       for key in TARGET_KEYS:
           for combo in _combos_for(family, n_voices):
               if family == "simple" and not _tonal_valid(combo):
                   continue
               voices = voices_from_combo(combo, key=key, family=family, n_voices=n_voices)
               upper = (_upper_figures_at(voices, len(voices.B) - 2)
                        if family == "compound" and n_voices == 4 else None)
               fingerprint = repr(combo)  # hashed into description; just needs to be unique
               built = build_binned_payload(voices, key=key, family=family,
                                            n_voices=n_voices, fingerprint=fingerprint,
                                            upper_figures=upper)
               if built is None:
                   rejected += 1
                   continue
               payload, unit, _rns = built
               skill_tags = [
                   "exercise_type:roman_from_clausulae",
                   "corpus:standard_exercises_from_clausulae",
                   f"unit:{unit}", "mode:roman", f"voices:{n_voices}",
                   f"family:{family}",
               ]
               ex = _save_exercise(author=author, description=payload["description"],
                                   payload=payload, skill_tags=skill_tags,
                                   complexity=unit, is_public=options["public"],
                                   overwrite=options["overwrite"])
               by_unit.setdefault(unit, []).append(ex)
               stdout.write(f"  [{unit}] {payload['description']}")
       stdout.write(style.WARNING(f"  rejected (no covering unit): {rejected}"))
       return by_unit
   ```
   **Skill tags are static** (namespace + `unit:N` + `family` + `voices`) — no nondeterministic `analyze_chunk_skills` call. (Spec note: harmony-skill tags beyond `unit:N` are dropped here for determinism.)
6. Rewrite `handle` to iterate the matrix, honor an optional `--unit` filter, build per-unit playlists, and print the histogram:
   ```python
   by_unit = {}
   for family, n_voices in FAMILY_VOICES:
       part = _make_exercises(family, n_voices, author, options, self.stdout, self.style)
       for unit, exs in part.items():
           by_unit.setdefault(unit, []).extend(exs)
   if options["unit"] is not None:
       by_unit = {options["unit"]: by_unit.get(options["unit"], [])}
   for unit in sorted(by_unit):
       _build_playlist(author=author,
                       playlist_name=f"Unit {unit} — Roman Numerals from Clausulae",
                       exercises=by_unit[unit],
                       skill_tags=["exercise_type:roman_from_clausulae", f"unit:{unit}"],
                       is_public=options["public"])
   self.stdout.write(self.style.MIGRATE_HEADING("Bin histogram:"))
   for unit in sorted(by_unit):
       self.stdout.write(f"  unit {unit}: {len(by_unit[unit])} exercises")
   self.stdout.write(self.style.WARNING(
       "\n⚠  Verify ONE exercise per populated unit in the student app before bulk use."))
   ```

- [ ] **Step 7: Change `--unit` to an optional filter (default None)**

In `add_arguments`, change the `--unit` argument from `default=9` to `default=None` and update its help to "Optional: restrict output to a single bin unit (default: all bins)." Delete the old `--voices` argument if the new family matrix supersedes it (it does — voice counts are driven by `FAMILY_VOICES`).

- [ ] **Step 8: Smoke-run the command**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py generate_roman_from_clausulae --author admin@example.com --overwrite 2>&1 | tail -40
```
Expected: a bin histogram across units in {9,10,11,12,14} plus a rejected count. **Record the histogram.** If units 10/11/14 are empty, flag it (spec top risk — likely needs double cadences, the deferred follow-up) and report before continuing. Re-run once; row/playlist counts identical (idempotent).

- [ ] **Step 9: Update the legacy test + run the suite**

The legacy `apps/exercises/tests/test_roman_from_clausulae.py` asserts the removed `_build_identification_payload` / `_CADENCE_RN` / `_RN_CHOICES_MAJOR`. Rewrite its cases to target `build_binned_payload` (the unit-9 I/V/I case) so coverage is preserved, not deleted.

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/ -q`
Expected: PASS (all app tests green).

- [ ] **Step 10: Commit**

```bash
git add apps/exercises/clausulae_realize.py apps/exercises/management/commands/generate_roman_from_clausulae.py apps/exercises/tests/
git commit -m "feat: shared realization module + simple/compound pools, binning, playlists, histogram"
```

---

## Task 10: Branch B — use shared realization + page_title student titles

**Files:**
- Modify: `apps/exercises/management/commands/generate_clausulae_b1.py`

Branch B keeps its identity, tags, payload, and pedagogy. Two changes: (a) import the realization primitives from the shared module instead of defining them locally (DRY); (b) set the **student-facing title** (`metadata.source`) from the page_title vocabulary for the cadence sections. The DB `desc` strings (`B1 — …`, `B2 — …`) stay as the short idempotency keys — do **not** rename them (they already fit 60 chars and keep idempotency stable). Branch B is playback/scale-degree, not roman — do **not** add roman analysis.

- [ ] **Step 1: Import realization from the shared module**

Replace b1's local `_realize_events`, `_compound_events`, `_DUR_SIMPLE`, `_DUR_COMPOUND_EARLY`, `_DUR_COMPOUND_LATE`, `_OCTAVE`, `_m21_note_to_pitch` definitions with:
```python
from apps.exercises.clausulae_realize import (
    realize_events as _realize_events,
    compound_events as _compound_events,
    _DUR_SIMPLE, _DUR_COMPOUND_EARLY, _DUR_COMPOUND_LATE, _OCTAVE,
)
```
Keep every call site unchanged (the aliases preserve the local names). This is a pure dedup — behavior identical.

- [ ] **Step 2: Set page_title student titles for the cadence sections (B2/B3/B4/B11/B12)**

In `_build_umto` (or wherever b1 sets `metadata.source`), set the student-facing source from `student_title()` for these sections. Map:
- B2 → `("simple", 2)`, B3 → `("simple", 3)`, B4 → `("simple", 4)`
- B11 → `("compound", 2)`, B12 3v → `("compound", 3)`, B12 4v → `("compound", 4)` with `upper_figures` from the realized voices.

Import: `from apps.exercises.clausulae_titles import student_title`. **Leave B1 unchanged** — it is single-clausula-by-voice, not a cadence, and has no `("…", 1)` page_title (calling `page_title` for it would raise `KeyError`). B1 keeps its existing title.

- [ ] **Step 3: Smoke-run Branch B and confirm idempotency**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py generate_clausulae_b1 --author admin@example.com --overwrite 2>&1 | tail -20
```
Expected: command succeeds; B2–B12 exercises now carry page_title-based `metadata.source` (visible as introText in the app); B1 unchanged. Re-run once more; row counts identical (idempotent — DB `desc` keys unchanged).

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/management/commands/generate_clausulae_b1.py
git commit -m "refactor: Branch B uses shared realization + page_title student titles"
```

---

## Task 11: Browser verification (spec-mandated, manual)

**Files:** none (verification only)

- [ ] **Step 1: Regenerate the JS module and start the app**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py build_unit_allowed_answers
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py runserver
```

- [ ] **Step 2: Smoke-test one exercise per populated unit (10, 11, 12, 14 — whichever the histogram populated)**

For each: open the exercise in the student app and confirm:
- Score renders and is musically coherent (matches a working clausulae render).
- One `?` slot per analyzed onset, at the correct offsets.
- The per-unit answer pool appears in the dropdown (and is filtered by unit, not the full diatonic set).
- A student can answer and complete the exercise.

- [ ] **Step 3: Record results**

Note any unit whose exercise fails the smoke test. A failure here blocks bulk use even with green tests (per the lessons spec). Report findings before proceeding to bulk generation.

---

## Task 12: Documentation

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md`, `docs/management_commands.md`

- [ ] **Step 1: Mark Blocker 1 resolved in CLAUDE.md and AGENTS.md**

In both files, in the "HIGH PRIORITY: Multi-Unit Playlist System" section, replace the Blocker 1 subsection's "Fix needed" instructions with a short resolved note:
```markdown
### Blocker 1: RESOLVED (2026-05-30)

`applySkillFilter` now uses the `UNIT_ALLOWED_ANSWERS` map (units 9–20),
generated from `music_theory_taxonomy_with_branches.json` via
`manage.py build_unit_allowed_answers` and consumed by both
`exercise_definition.js` and `generate_roman_from_clausulae`. The old generic
`startsWith` path is gone. Blocker 2 (create_unit_playlist) is unchanged.
```

- [ ] **Step 2: Update `docs/management_commands.md`**

Update the `generate_roman_from_clausulae` entry: document the family pool (**simple + compound, 3v/4v; double cadences deferred**), music21 RN derivation, generate-and-bin into units {9,10,11,12,14}, page_title student titles (in `metadata.source`) + short hashed `description`, per-unit playlists, and the printed bin histogram. Note unit 13 (ROO) and double cadences as deferred follow-ups. Add a one-line entry for the new `build_unit_allowed_answers` command under the appropriate category, and register it in `apps/exercises/management/commands/list_exercise_generators.py` `CATALOG` if it belongs there (it is a build tool, not an exercise generator — only add if the file documents build commands too; otherwise skip).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md AGENTS.md docs/management_commands.md
git commit -m "docs: Blocker 1 resolved + document binning generator and build command"
```

---

## Self-Review Notes

- **Spec coverage:** §1 answer table → Tasks 1–3; §2 title map → Tasks 4, 10; §3 converter + derivation → Tasks 5, 6; §4 generate-and-bin generator → Tasks 7 (bin), 8 (payload), 9 (pools/playlists/histogram); §6 docs → Task 12; §7 verification → Tasks 9 (histogram) + 11 (browser). Unit 13 (§0) intentionally absent — deferred.
- **Title fields (addresses description length):** student-facing page_title → UMTO `metadata.source` (no limit); `Exercise.description` (`max_length=60`, idempotency key) → short hashed key via `short_description()`. Tested in Task 4.
- **Deferred this round (like unit 13):** double cadences. Engine has the enumerators but realization (5-position quintuples) is unbuilt; `voices_from_combo` raises for them. Fast-follow if the Task 9 histogram shows units 10/11/14 underpopulated by simple+compound.
- **DRY:** compound realization is promoted to the shared `clausulae_realize.py` (Task 9) and consumed by both generators (Task 10) — no duplicated/divergent realization.
- **Out of scope (per spec):** no compendium content sourcing, no `applySkillFilter` logic change, no grading-engine/UMTO-schema change, no clausulae-project changes.
- **Known adaptation points flagged inline (not placeholders):** enumerator tuple shapes (Task 9 Step 5 prints them, matched against b1's working usage), the `payload["score"]["umto"]` key paths for `analysis`/`metadata.source` (Task 8 Step 1 verifies via `dump_exercise`), `normalize_figure` coverage and chordified offsets (Task 6 Step 4 adjusts to observed music21 output), and `settings.BASE_DIR` (Task 2 Step 3 has a relative-path fallback). Each has a concrete command to resolve it before coding.
