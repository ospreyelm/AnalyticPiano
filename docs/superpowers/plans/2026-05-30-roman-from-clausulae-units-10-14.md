# Roman From Clausulae — page_title Titling + Units 10–14 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `generate_roman_from_clausulae` from unit-9 simple cadences to units 10/11/12/14 via engine compound/double cadences with music21-derived Roman numerals and automatic unit-binning, title both clausulae generators from the Compendium `page_title` vocabulary, and make the per-unit answer table a taxonomy-derived artifact shared by JS and Python.

**Architecture:** A taxonomy-derived `unit_allowed_answers` artifact becomes the single source of truth for per-unit RN answer sets (consumed by both `exercise_definition.js` and the generator). The generator enumerates engine cadences, realizes them, derives Roman numerals through a new VoiceEvent→music21 converter, bins each exercise into the lowest covering unit, titles it from a shared `(family, n_voices)→page_title` map, and writes one idempotent playlist per populated unit. Unit 13 (Rule of the Octave) is explicitly out of scope (deferred to a separate spike).

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
- `apps/exercises/clausulae_titles.py` — `(family, n_voices)→page_title` map + compound-4v figure detector.
- `apps/exercises/utils/voice_events_music21.py` — VoiceEvent→music21 `Score` converter.
- `apps/exercises/roman_derivation.py` — music21 RN derivation + normalization to answer vocabulary.
- `apps/exercises/tests/test_unit_allowed_answers.py`
- `apps/exercises/tests/test_clausulae_titles.py`
- `apps/exercises/tests/test_voice_events_music21.py`
- `apps/exercises/tests/test_roman_derivation.py`
- `apps/exercises/tests/test_roman_from_clausulae_units.py`

**Modify:**
- `apps/exercises/utils/music21_builder.py:163` — fix `_pitch_to_midi` missing `return`.
- `lab/static/js/src/models/exercise_definition.js:15-90` — replace inline `UNIT_ALLOWED_ANSWERS` with the AMD import.
- `apps/exercises/management/commands/generate_roman_from_clausulae.py` — pools, binning, titles, derived RNs, per-unit playlists.
- `apps/exercises/management/commands/generate_clausulae_b1.py` — titles from the shared map.
- `CLAUDE.md`, `AGENTS.md` — mark Blocker 1 resolved.
- `docs/management_commands.md` — update the generator entry.

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
import re
import subprocess
import sys
from pathlib import Path

_GENERATED_JS = Path(__file__).resolve().parents[3] / "lab/static/js/src/config/unit_allowed_answers.js"


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
        cwd=_GENERATED_JS.resolve().parents[4],
        check=True,
        env={**__import__("os").environ, "DJANGO_SETTINGS_MODULE": "harmony.settings.local"},
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

## Task 4: Clausula → page_title map (incl. compound-4v figure)

**Files:**
- Create: `apps/exercises/clausulae_titles.py`
- Test: `apps/exercises/tests/test_clausulae_titles.py`

- [ ] **Step 1: Write the failing test**

`apps/exercises/tests/test_clausulae_titles.py`:
```python
from apps.exercises.clausulae_titles import page_title, exercise_title


def test_simple_three_voices():
    assert page_title("simple", 3) == "Simple Cadences in Three Voices"


def test_compound_two_and_three():
    assert page_title("compound", 2) == "Compound Cadences in Two Voices"
    assert page_title("compound", 3) == "Compound Cadences in Three Voices"


def test_double_four_voices():
    assert page_title("double", 4) == "Double Cadences in Four Voices"


def test_compound_four_voice_figure_variants():
    # Generic intervals of the two upper voices above the bass at the penult.
    assert page_title("compound", 4, upper_figures={5, 4}) == "Compound Cadences with 5/4 in Four Voices"
    assert page_title("compound", 4, upper_figures={6, 5}) == "Compound Cadences with 6/5 in Four Voices"
    assert page_title("compound", 4, upper_figures={6, 4}) == "Compound Cadences with 6/4 in Four Voices"


def test_compound_four_voice_default_when_unknown():
    # Unrecognised figure set falls back to the 6/4 title (documented default).
    assert page_title("compound", 4, upper_figures={2, 7}) == "Compound Cadences with 6/4 in Four Voices"


def test_exercise_title_appends_key_and_fingerprint():
    title = exercise_title("simple", 3, key="C", fingerprint="D:D-Ti-D B:D-Sol-D")
    assert title == "Simple Cadences in Three Voices — C major [D:D-Ti-D B:D-Sol-D]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_clausulae_titles.py -q`
Expected: FAIL — `ModuleNotFoundError: apps.exercises.clausulae_titles`

- [ ] **Step 3: Implement the map**

`apps/exercises/clausulae_titles.py`:
```python
"""Map clausulae cadence families to Compendium page_title strings.

Titles use the musical-type vocabulary from the Galant Compendium so student
exercises read as harmony, not Clausulae jargon (per the lessons spec). 4-voice
compound cadences split into three figured-bass variants; we pick the variant
from the generic intervals of the two upper voices above the bass at the
penultimate onset.
"""
from __future__ import annotations

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


def exercise_title(family: str, n_voices: int, *, key: str, fingerprint: str,
                   upper_figures: set | None = None) -> str:
    base = page_title(family, n_voices, upper_figures=upper_figures)
    return f"{base} — {key} major [{fingerprint}]"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_clausulae_titles.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/clausulae_titles.py apps/exercises/tests/test_clausulae_titles.py
git commit -m "feat: clausula->page_title map with compound-4v figure detection"
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
    from apps.exercises.roman_derivation import derive_roman_numerals
    slices = derive_roman_numerals(_ivi_cadence_c_major(), key="C")
    figures = [rn for _offset, rn in slices]
    assert figures == ["I", "V", "I"]


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
"""Derive Roman numerals for a generated cadence via music21.

Chordify the SATB Score, run romanNumeralFromChord at each vertical, and
normalize music21's figure to the answer vocabulary (degree sign for diminished).
"""
from __future__ import annotations

from music21 import key as m21key
from music21 import roman

from apps.exercises.utils.voice_events_music21 import score_from_voices


def normalize_figure(figure: str) -> str:
    """music21 figure -> answer-vocabulary string (e.g. 'viio6' -> 'vii°6')."""
    return figure.replace("o", "°")


def derive_roman_numerals(voices, *, key: str) -> list[tuple[float, str]]:
    """Return [(offset, normalized_figure), ...] for each chordified vertical."""
    score = score_from_voices(voices)
    tonal_key = m21key.Key(key)
    chordified = score.chordify()
    result: list[tuple[float, str]] = []
    for chord in chordified.recurse().getElementsByClass("Chord"):
        rn = roman.romanNumeralFromChord(chord, tonal_key)
        result.append((float(chord.offset), normalize_figure(rn.figure)))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_derivation.py -q`
Expected: PASS (2 passed). If `derive_simple_authentic_cadence` returns something other than `["I","V","I"]` (music21 spelling differences), adjust `normalize_figure` minimally to cover the observed token and re-run — do not broaden beyond what the test requires.

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

## Task 8: Generator refactor — pools, derivation, binning, titles, playlists

**Files:**
- Modify: `apps/exercises/management/commands/generate_roman_from_clausulae.py`
- Test: `apps/exercises/tests/test_roman_from_clausulae_units.py`

This task replaces the hardcoded `_CADENCE_RN` / `_RN_CHOICES_MAJOR` path with derived RNs and binning, and broadens the enumerator pool. Keep the existing `_tonal_valid`, `_assign_slots`, `_combo_label`, `_realize_events`, `_save_exercise`, and `_build_playlist` helpers.

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
                                   fingerprint="test")
    assert result is not None
    payload, unit, derived = result
    assert unit == 9
    assert derived == ["I", "V", "I"]
    assert payload["analysisType"] == "roman"
    assert payload["allowed_answers"] == ["I", "i", "V", "V7"]
    # one is_target analysis slice per derived RN
    targets = [s for s in payload["score"]["umto"]["analysis"] if s["is_target"]]
    assert len(targets) == 3
    assert payload["description"].startswith("Simple Cadences in Three Voices — C major [test]")
```

(Confirm the payload's analysis path: inspect one existing exercise via
`DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py dump_exercise <id>` if the
`payload["score"]["umto"]["analysis"]` key path differs, and adjust the assertion to match the real shape before implementing.)

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_from_clausulae_units.py -q`
Expected: FAIL — `cannot import name 'build_binned_payload'`

- [ ] **Step 3: Add `build_binned_payload` to the command module**

Add to `apps/exercises/management/commands/generate_roman_from_clausulae.py` (module level), reusing existing imports plus the new helpers:
```python
from apps.exercises.clausulae_titles import exercise_title
from apps.exercises.roman_derivation import derive_roman_numerals, bin_unit
from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers

_CANDIDATE_UNITS = [9, 10, 11, 12, 14]  # unit 13 (ROO) deferred — see spec §0
_UNIT_TABLE = compute_unit_allowed_answers()


def build_binned_payload(voices, *, key, family, n_voices, fingerprint, upper_figures=None):
    """Return (payload, unit, derived_rns) or None if no unit covers the RNs."""
    derived = derive_roman_numerals(voices, key=key)
    rn_list = [rn for _off, rn in derived]
    unit = bin_unit(set(rn_list), _UNIT_TABLE, _CANDIDATE_UNITS)
    if unit is None:
        return None

    offsets = [off for off, _rn in derived]
    analysis = [
        AnalysisSlice(
            offset=off,
            content=AnalysisLayer(roman_numeral=rn, raw_roman_numeral=rn),
            unit_tags=[unit],
            is_target=True,
        )
        for off, rn in derived
    ]
    vids = {vid for vid in ("S", "A", "T", "B") if getattr(voices, vid)}
    description = exercise_title(family, n_voices, key=key, fingerprint=fingerprint,
                                 upper_figures=upper_figures)

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=description,
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
        grading=_grading_slices(
            {vid: getattr(voices, vid) for vid in ("S", "A", "T", "B") if getattr(voices, vid)},
            offsets,
        ),
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
    payload["description"] = description
    return payload, unit, rn_list
```
Note: `_grading_slices` currently takes `voice_events_by_id: dict` and `offsets`. The dict comprehension above matches its existing signature. `Voices` is accepted directly by `UMTO(voices=...)` as in the existing builder.

- [ ] **Step 4: Run the test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_from_clausulae_units.py -q`
Expected: PASS (1 passed). Fix the `payload["score"]["umto"]["analysis"]` key path in the test if step 1's note revealed a different shape.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_roman_from_clausulae.py apps/exercises/tests/test_roman_from_clausulae_units.py
git commit -m "feat: build_binned_payload — derived RNs, binning, page_title, per-unit answers"
```

---

## Task 9: Wire the new pools + per-unit playlists + histogram into the command

**Files:**
- Modify: `apps/exercises/management/commands/generate_roman_from_clausulae.py` (`_make_exercises`, `handle`)

- [ ] **Step 1: Broaden the enumerator pool in `_make_exercises`**

Replace the single `enumerate_simple(...)` loop in `_make_exercises` with a per-family loop. At the top of the command module add to the clausulae import block:
```python
    from clausulae.generate import (
        enumerate_simple,
        enumerate_compound_3voice,
        enumerate_compound_4voice,
        enumerate_double_3voice,
        enumerate_double_4voice,
    )
```
Define the pool selector (module level):
```python
def _combos_for(family: str, n_voices: int):
    if family == "simple":
        return enumerate_simple(n_voices=n_voices, require_bass=True)
    if family == "compound" and n_voices == 3:
        return enumerate_compound_3voice(require_discant=True, require_bass=True)
    if family == "compound" and n_voices == 4:
        return enumerate_compound_4voice(require_discant=True, require_bass=True)
    if family == "double" and n_voices == 3:
        return enumerate_double_3voice()
    if family == "double" and n_voices == 4:
        return enumerate_double_4voice()
    return []
```
**Tuple shapes differ per enumerator.** Before writing the realize/slot logic, print one tuple from each to confirm its arity and ordering:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -c "
import sys, os
sys.path.insert(0, os.path.abspath('../clausulae-project'))
from clausulae.generate import enumerate_compound_3voice, enumerate_compound_4voice, enumerate_double_3voice, enumerate_double_4voice
for fn in (enumerate_compound_3voice, enumerate_compound_4voice, enumerate_double_3voice, enumerate_double_4voice):
    items = list(fn()) if fn.__name__.startswith('enumerate_double') else list(fn(require_discant=True, require_bass=True))
    print(fn.__name__, 'n=', len(items), 'first=', items[0] if items else None)
"
```
Adapt `_assign_slots` / realize to each tuple shape. The existing `_assign_slots` handles `(name, idx, triple)` tuples for simple; compound/double tuples are triple-of-triples per voice — map each voice's triple through `_realize_events`. Keep the realized result as a `Voices` object (S/A/T/B lists) so it feeds `build_binned_payload` directly.

- [ ] **Step 2: Rewrite `_make_exercises` to derive + bin + collect by unit**

`_make_exercises` returns `dict[int, list[Exercise]]` keyed by bin unit. For each family/key/combo: build `Voices`, compute `fingerprint = _combo_label(slots)` (fall back to `var{combo_idx}` when `len > 60`), compute `upper_figures` for compound-4v from the penult (see Step 3), call `build_binned_payload`; on `None` increment a rejected counter and log; else `_save_exercise` with skill_tags and append to `by_unit[unit]`.

Skill tags per exercise:
```python
skill_tags = [
    "exercise_type:roman_from_clausulae",
    "corpus:standard_exercises_from_clausulae",
    f"unit:{unit}",
    "mode:roman",
    f"voices:{n_voices}",
] + derived_harmony_tags  # from analyze_chunk_skills on the same Score, optional
```
(Reuse `apps.exercises.utils.skills_analyzer.analyze_chunk_skills` if convenient; if it adds noise, keep just the namespace + `unit:N` tags. Decide based on observed output — do not invent tags.)

- [ ] **Step 3: Compute `upper_figures` for compound-4v titles**

Add a helper that, for a 4-voice `Voices`, computes the generic intervals of the two upper voices above the bass at the penultimate derived offset:
```python
_STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


def _diatonic(p) -> int:
    return p.octave * 7 + _STEP_INDEX[p.step]


def _upper_figures_at(voices, offset_index: int) -> set:
    """Generic intervals (1..7) of A & S above B at the given onset index."""
    figs = set()
    bass = voices.B[offset_index].pitch if offset_index < len(voices.B) else None
    if bass is None:
        return figs
    for vid in ("S", "A"):
        seq = getattr(voices, vid)
        if offset_index < len(seq) and seq[offset_index].pitch:
            interval = (_diatonic(seq[offset_index].pitch) - _diatonic(bass)) % 7 + 1
            figs.add(interval)
    return figs
```
Pass `upper_figures=_upper_figures_at(voices, penult_index)` only when `family == "compound" and n_voices == 4`; the penult index is `len(offsets) - 2`.

- [ ] **Step 4: Rewrite `handle` to iterate families, build per-unit playlists, print histogram**

In `handle`, after resolving the author, loop over the family/voice matrix:
```python
FAMILY_VOICES = [("simple", 3), ("simple", 4),
                 ("compound", 3), ("compound", 4),
                 ("double", 3), ("double", 4)]
by_unit: dict[int, list] = {}
for family, n_voices in FAMILY_VOICES:
    part = _make_exercises(family, n_voices, author, options, self.stdout, self.style)
    for unit, exs in part.items():
        by_unit.setdefault(unit, []).extend(exs)
```
Respect an optional `--unit` filter: if provided, keep only that bin. Then one playlist per populated unit:
```python
for unit in sorted(by_unit):
    _build_playlist(
        author=author,
        playlist_name=f"Unit {unit} — Roman Numerals from Clausulae",
        exercises=by_unit[unit],
        skill_tags=["exercise_type:roman_from_clausulae", f"unit:{unit}"],
        is_public=options["public"],
    )
```
Print the **bin histogram** and rejected count:
```python
self.stdout.write(self.style.MIGRATE_HEADING("Bin histogram:"))
for unit in sorted(by_unit):
    self.stdout.write(f"  unit {unit}: {len(by_unit[unit])} exercises")
self.stdout.write(self.style.WARNING(
    "\n⚠  Verify ONE exercise per populated unit in the student app before bulk use."
))
```

- [ ] **Step 5: Smoke-run the command (writes to DB — use a scratch author or `--overwrite`)**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py generate_roman_from_clausulae --author admin@example.com --overwrite 2>&1 | tail -30
```
Expected: a bin histogram listing counts for units among {9,10,11,12,14}, plus a rejected count. **Record the histogram** — if units 10/11/14 are empty, flag it (top risk in the spec) and report before continuing.

- [ ] **Step 6: Run the full Python test suite for the app**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_roman_from_clausulae.py apps/exercises/tests/test_roman_from_clausulae_units.py apps/exercises/tests/test_roman_derivation.py -q`
Expected: PASS. Note: the **legacy** `test_roman_from_clausulae.py` asserts the old `_CADENCE_RN`/`_RN_CHOICES_MAJOR` behavior and the hardcoded `_build_identification_payload`. If you removed that function, update those tests to target `build_binned_payload` (the unit-9 case reproduces I/V/I) rather than deleting coverage. Make that update in this step and keep both files green.

- [ ] **Step 7: Commit**

```bash
git add apps/exercises/management/commands/generate_roman_from_clausulae.py apps/exercises/tests/
git commit -m "feat: multi-family pools, per-unit binning + playlists, bin histogram"
```

---

## Task 10: Title `generate_clausulae_b1` from the shared map

**Files:**
- Modify: `apps/exercises/management/commands/generate_clausulae_b1.py`

Branch B keeps its identity, tags, and pedagogy; only the human-readable `desc` strings change to the page_title vocabulary. Branch B is playback/scale-degree, not roman — do **not** add roman analysis or change its payload.

- [ ] **Step 1: Map each B-section to a family/n_voices and retitle**

`generate_clausulae_b1.py` builds descriptions like `B1 — {clausula} ({sol}) in {key}`, `B2 — ... [{key}]`, `B3 — ...`, `B4 — ...`. For each section, replace the `desc = ...` line with `exercise_title(family, n_voices, key=key, fingerprint=<existing compact label>)`:
- B1 (single clausula, by voice) → keep `family="simple"`, `n_voices` = the section's voice count.
- B2 (2-voice) → `("simple", 2)`.
- B3 (3-voice) → `("simple", 3)`.
- B4 (4-voice) → `("simple", 4)`.
- B11/B12 (compound) → `("compound", n_voices)`; for 4-voice pass `upper_figures` via `_upper_figures_at` if the realized voices are available, else accept the documented 6/4 default.

Import at top: `from apps.exercises.clausulae_titles import exercise_title`. Keep the existing `_vpart`/solfège fingerprints as the `fingerprint` argument so descriptions stay unique and idempotency holds.

- [ ] **Step 2: Smoke-run Branch B and confirm titles + idempotency**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py generate_clausulae_b1 --author admin@example.com --overwrite 2>&1 | tail -20
```
Expected: descriptions now read e.g. `Simple Cadences in Three Voices — C major [D:... B:...]`. Re-run once more; counts identical (idempotent, no duplicate rows).

- [ ] **Step 3: Commit**

```bash
git add apps/exercises/management/commands/generate_clausulae_b1.py
git commit -m "feat: title Branch B clausulae from the shared page_title map"
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

Update the `generate_roman_from_clausulae` entry: document the family pool (simple/compound/double, 3v/4v), music21 RN derivation, generate-and-bin into units {9,10,11,12,14}, page_title titling, per-unit playlists, and the printed bin histogram. Add a one-line entry for the new `build_unit_allowed_answers` command under the appropriate category, and register it in `apps/exercises/management/commands/list_exercise_generators.py` `CATALOG` if it belongs there (it is a build tool, not an exercise generator — only add if the file documents build commands too; otherwise skip).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md AGENTS.md docs/management_commands.md
git commit -m "docs: Blocker 1 resolved + document binning generator and build command"
```

---

## Self-Review Notes

- **Spec coverage:** §1 answer table → Tasks 1–3; §2 title map → Tasks 4, 10; §3 converter + derivation → Tasks 5, 6; §4 generate-and-bin generator → Tasks 7–9; §6 docs → Task 12; §7 verification → Tasks 9 (histogram) + 11 (browser). Unit 13 (§0) is intentionally absent — deferred.
- **Out of scope (per spec):** no compendium content sourcing, no `applySkillFilter` logic change, no grading-engine/UMTO-schema change, no clausulae-project changes.
- **Known adaptation points flagged inline (not placeholders):** enumerator tuple shapes (Task 9 Step 1 prints them), the `payload["score"]["umto"]["analysis"]` key path (Task 8 Step 1 verifies via `dump_exercise`), and `normalize_figure` coverage (Task 6 Step 4 adjusts to observed music21 tokens). Each has a concrete command to resolve it before coding.
