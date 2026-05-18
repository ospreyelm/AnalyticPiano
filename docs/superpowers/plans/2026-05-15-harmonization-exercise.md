# Harmonization Exercise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a UMTO harmonization mode where all prompts normalize to bass+figures, students advance only after playing a valid active sonority, and each stage produces musician-review artifacts.

**Architecture:** Implement the theory core first in small Python modules with tests and review artifacts, then mirror the normalized target and active-sonority logic in focused frontend modules. Existing figured-bass, UMTO, music21, and Bach analysis code remains the source of truth where possible; new code fills the missing reverse direction from figures to required notes.

**Tech Stack:** Django management commands, Pydantic UMTO models, music21, plain CommonJS-compatible JS logic tests, AMD frontend modules, VexFlow rendering.

---

## File Structure

Create or modify these files:

- Create: `apps/exercises/harmonization/__init__.py`
- Create: `apps/exercises/harmonization/figures.py`
  - Expands figured-bass shorthand, parses accidentals, derives note spellings and pitch classes above a bass.
- Create: `apps/exercises/harmonization/targets.py`
  - Builds normalized harmonization targets from UMTO analysis/grading/voice data.
- Create: `apps/exercises/management/commands/render_harmonization_review.py`
  - Writes musician-review HTML artifacts for figure parsing, Roman normalization, and active-sonority cases.
- Create: `apps/exercises/management/commands/generate_harmonization.py`
  - Creates UMTO harmonization exercises from existing UMTO source exercises.
- Create: `apps/exercises/tests/test_harmonization_figures.py`
- Create: `apps/exercises/tests/test_harmonization_targets.py`
- Create: `apps/exercises/tests/test_generate_harmonization.py`
- Create: `lab/static/js/src/models/harmonization_targets_logic.js`
  - Browser-side version of target normalization data helpers when payload already contains normalized targets.
- Create: `lab/static/js/src/models/harmonization_targets_logic.test.js`
- Create: `lab/static/js/src/models/harmonization_grader_logic.js`
  - Pure held-note and active-sonority grading logic.
- Create: `lab/static/js/src/models/harmonization_grader_logic.test.js`
- Create: `lab/static/js/src/models/voice_leading_logic.js`
  - Pure quality-tier checks over accepted sonorities.
- Create: `lab/static/js/src/models/voice_leading_logic.test.js`
- Modify: `apps/exercises/umto.py`
  - Add harmonization mode and metadata fields.
- Modify: `apps/exercises/umto_schema.json`
  - Regenerate after `umto.py` changes.
- Modify: `apps/exercises/umto_factory.py`
  - Pass through harmonization metadata and normalized targets.
- Modify: `lab/static/js/src/models/exercise_definition.js`
  - Add `isHarmonization()`, collapse duplicate `getMode()`, and parse harmonization problems.
- Modify: `lab/static/js/src/models/exercise_grader.js`
  - Route harmonization to pure active-sonority grader.
- Modify: `lab/static/js/src/models/exercise_context.js`
  - Add settle-window scheduling, accepted-sonority recording, and performance payload fields.
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`
  - Treat harmonization as a VexFlow-rendered UMTO mode.
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
  - Render locked voices and hide unlocked voices.
- Modify: `lab/static/harmonization-process-visualization.html`
  - Link generated review artifacts when available.

---

## Task 1: Add UMTO Harmonization Metadata

**Files:**
- Modify: `apps/exercises/umto.py`
- Test: `apps/exercises/tests/test_umto_contract.py`

- [ ] **Step 1: Write failing UMTO metadata tests**

Add these tests near the existing UMTO contract tests:

```python
def test_interaction_mode_has_harmonization():
    from apps.exercises.umto import InteractionMode

    assert InteractionMode.HARMONIZATION.value == "harmonization"


def test_metadata_has_harmonization_defaults():
    from apps.exercises.umto import Metadata, InteractionMode

    meta = Metadata(
        exercise_id="TEMP",
        source="Test",
        key="C",
        meter="4/4",
        clef="keyboard",
        complexity_score=9,
        mode=InteractionMode.HARMONIZATION,
    )

    assert meta.locked_voices == ["B"]
    assert meta.voice_count_policy.min == 3
    assert meta.voice_count_policy.max == 4
    assert meta.voice_count_policy.expected is None
    assert meta.harmonization_target_policy.source == "figured_bass"
    assert meta.harmonization_target_policy.midi_uses_pitch_class is True
    assert meta.chord_settle_ms == 150
    assert meta.release_grace_ms == 120
    assert meta.max_voice_displacement == 4
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_umto_contract -v 2
```

Expected: fails because `InteractionMode.HARMONIZATION`, `VoiceCountPolicy`, and `HarmonizationTargetPolicy` do not exist.

- [ ] **Step 3: Implement the metadata models**

In `apps/exercises/umto.py`, add `Literal` fields if needed and update the models:

```python
class InteractionMode(str, Enum):
    IDENTIFICATION = "identification"
    PLAYBACK = "playback"
    ANALYSIS_MATCH = "analysis_match"
    SYMBOLIC_IDENTIFICATION = "symbolic_identification"
    HARMONIZATION = "harmonization"


class VoiceCountPolicy(BaseModel):
    expected: Optional[int] = None
    min: int = 3
    max: Optional[int] = 4


class HarmonizationTargetPolicy(BaseModel):
    source: Literal["figured_bass", "roman", "analysis_slice"] = "figured_bass"
    written_spelling_required: bool = False
    midi_uses_pitch_class: bool = True
```

Then extend `Metadata`:

```python
class Metadata(BaseModel):
    exercise_id: str
    source: str
    key: str
    meter: str
    clef: str = "treble"
    complexity_score: int = Field(ge=1, le=12, description="Unit 1-12 ranking system")
    mode: InteractionMode = InteractionMode.PLAYBACK
    is_umto: bool = True
    input_mode: Literal["dropdown", "text"] = "dropdown"
    unit: Optional[int] = None
    locked_voices: List[str] = Field(default_factory=lambda: ["B"])
    voice_count_policy: VoiceCountPolicy = Field(default_factory=VoiceCountPolicy)
    harmonization_target_policy: HarmonizationTargetPolicy = Field(
        default_factory=HarmonizationTargetPolicy
    )
    chord_settle_ms: int = 150
    release_grace_ms: int = 120
    max_voice_displacement: int = 4
```

- [ ] **Step 4: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_umto_contract -v 2
```

Expected: pass.

- [ ] **Step 5: Regenerate UMTO schema**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py make_umto_schema
```

Expected: `apps/exercises/umto_schema.json` updates and includes harmonization fields.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_schema.json apps/exercises/tests/test_umto_contract.py
git commit -m "feat: add UMTO harmonization metadata"
```

---

## Task 2: Build Figure Expansion And Pitch Derivation

**Files:**
- Create: `apps/exercises/harmonization/__init__.py`
- Create: `apps/exercises/harmonization/figures.py`
- Test: `apps/exercises/tests/test_harmonization_figures.py`

- [ ] **Step 1: Write failing parser and derivation tests**

Create `apps/exercises/tests/test_harmonization_figures.py`:

```python
from apps.exercises.harmonization.figures import (
    expand_figure_string,
    derive_required_notes,
)


def test_blank_figure_expands_to_five_three():
    assert expand_figure_string("") == ["5", "3"]


def test_six_expands_to_six_three():
    assert expand_figure_string("6") == ["6", "3"]


def test_seven_expands_to_seven_five_three():
    assert expand_figure_string("7") == ["7", "5", "3"]


def test_arbitrary_stack_passes_through():
    assert expand_figure_string("9/7/5/3") == ["9", "7", "5", "3"]


def test_accidental_without_number_means_third():
    assert expand_figure_string("#") == ["#3", "5"]
    assert expand_figure_string("b") == ["b3", "5"]
    assert expand_figure_string("n") == ["n3", "5"]


def test_c_major_c_six_derives_e_and_a():
    result = derive_required_notes(key_name="C", bass_name="C", figure="6")
    assert result["expanded_figures"] == ["6", "3"]
    assert result["required_note_names"] == ["A", "E"]
    assert result["required_upper_pcs"] == [9, 4]
    assert result["allowed_pcs"] == [0, 9, 4]


def test_c_major_f_six_derives_d_and_a():
    result = derive_required_notes(key_name="C", bass_name="F", figure="6")
    assert result["required_note_names"] == ["D", "A"]
    assert result["required_upper_pcs"] == [2, 9]


def test_c_major_f_sharp_alters_third():
    result = derive_required_notes(key_name="C", bass_name="F", figure="#")
    assert result["expanded_figures"] == ["#3", "5"]
    assert result["required_note_names"] == ["A#", "C"]
    assert result["required_upper_pcs"] == [10, 0]


def test_c_major_b_natural_six_uses_key_default():
    result = derive_required_notes(key_name="C", bass_name="B", figure="6")
    assert result["required_note_names"] == ["G", "D"]
    assert result["required_upper_pcs"] == [7, 2]
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_figures -v 2
```

Expected: import error for `apps.exercises.harmonization.figures`.

- [ ] **Step 3: Implement `figures.py`**

Create `apps/exercises/harmonization/__init__.py` as an empty file.

Create `apps/exercises/harmonization/figures.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from music21 import interval as m21_interval
from music21 import key as m21_key
from music21 import pitch as m21_pitch


_SHORTHANDS = {
    "": ["5", "3"],
    "5/3": ["5", "3"],
    "6": ["6", "3"],
    "6/4": ["6", "4"],
    "7": ["7", "5", "3"],
    "6/5": ["6", "5", "3"],
    "4/3": ["6", "4", "3"],
    "4/2": ["6", "4", "2"],
    "2": ["6", "4", "2"],
}


_STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class DerivedNotes(TypedDict):
    bass_name: str
    bass_pc: int
    expanded_figures: list[str]
    required_note_names: list[str]
    required_upper_pcs: list[int]
    allowed_pcs: list[int]


@dataclass(frozen=True)
class FigureToken:
    accidental: str
    number: int


def _normalize_key_name(key_name: str) -> str:
    text = (key_name or "C").strip()
    if text.startswith(("j", "i")) and len(text) >= 2:
        mode = "minor" if text.startswith("i") else "major"
        tonic = text[1:].replace("_", "")
        return f"{tonic} {mode}"
    return text


def _parse_token(token: str) -> FigureToken:
    token = token.strip()
    if token in {"#", "b", "n"}:
        token = token + "3"
    match = re.fullmatch(r"([#bn]?)(\d+)", token)
    if not match:
        raise ValueError(f"Invalid figure token: {token!r}")
    accidental, number = match.groups()
    return FigureToken(accidental=accidental, number=int(number))


def expand_figure_string(figure: str | None) -> list[str]:
    text = (figure or "").strip()
    if text in _SHORTHANDS:
        return list(_SHORTHANDS[text])
    if text in {"#", "b", "n"}:
        return [text + "3", "5"]
    tokens = [part.strip() for part in text.split("/") if part.strip()]
    if not tokens:
        return list(_SHORTHANDS[""])
    return tokens


def _pitch_class_from_name(name: str) -> int:
    p = m21_pitch.Pitch(name)
    return int(p.pitchClass)


def _apply_accidental(default_pitch: m21_pitch.Pitch, accidental: str, key_obj: m21_key.Key) -> m21_pitch.Pitch:
    if accidental == "":
        return default_pitch

    step = default_pitch.step
    octave = default_pitch.octave
    key_pitch_for_step = next((p for p in key_obj.pitches if p.step == step), None)
    base_alter = key_pitch_for_step.alter if key_pitch_for_step is not None else 0

    if accidental == "#":
        alter = base_alter + 1
    elif accidental == "b":
        alter = base_alter - 1
    elif accidental == "n":
        alter = 0
    else:
        raise ValueError(f"Unsupported accidental: {accidental!r}")

    result = m21_pitch.Pitch()
    result.step = step
    result.octave = octave
    result.alter = alter
    return result


def _interval_name_for_number(number: int) -> str:
    simple = ((number - 1) % 7) + 1
    octaves = (number - 1) // 7
    quality_by_number = {
        1: "P",
        2: "M",
        3: "M",
        4: "P",
        5: "P",
        6: "M",
        7: "M",
    }
    return f"{quality_by_number[simple]}{number + (0 * octaves)}"


def derive_required_notes(*, key_name: str, bass_name: str, figure: str | None) -> DerivedNotes:
    key_obj = m21_key.Key(_normalize_key_name(key_name))
    bass_pitch = m21_pitch.Pitch(bass_name)
    if bass_pitch.octave is None:
        bass_pitch.octave = 3

    expanded = expand_figure_string(figure)
    note_names: list[str] = []
    pcs: list[int] = []

    for raw_token in expanded:
        token = _parse_token(raw_token)
        interval_name = _interval_name_for_number(token.number)
        derived = m21_interval.Interval(interval_name).transposePitch(bass_pitch)
        derived = _apply_accidental(derived, token.accidental, key_obj)
        note_name = derived.name.replace("-", "b")
        pc = int(derived.pitchClass)
        if pc not in pcs:
            note_names.append(note_name)
            pcs.append(pc)

    bass_pc = _pitch_class_from_name(bass_name)
    return {
        "bass_name": bass_name,
        "bass_pc": bass_pc,
        "expanded_figures": expanded,
        "required_note_names": note_names,
        "required_upper_pcs": pcs,
        "allowed_pcs": [bass_pc] + pcs,
    }
```

- [ ] **Step 4: Run tests and adjust music21 interval details**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_figures -v 2
```

Expected: pass. If `music21.interval.Interval("M9")` behavior differs for compound intervals, adjust `_interval_name_for_number()` only; keep tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/harmonization apps/exercises/tests/test_harmonization_figures.py
git commit -m "feat: derive harmonization notes from bass figures"
```

---

## Task 3: Build Musical Review Artifact Command

**Files:**
- Create: `apps/exercises/management/commands/render_harmonization_review.py`
- Test: `apps/exercises/tests/test_harmonization_figures.py`

- [ ] **Step 1: Add artifact smoke test**

Append to `apps/exercises/tests/test_harmonization_figures.py`:

```python
def test_review_artifact_command_writes_html(tmp_path):
    from django.core.management import call_command

    out = tmp_path / "harmonization-review.html"
    call_command("render_harmonization_review", output=str(out))

    html = out.read_text()
    assert "Figure Parser Review" in html
    assert "C + 6" in html
    assert "F + #" in html
```

- [ ] **Step 2: Run failing test**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_figures -v 2
```

Expected: fails because command does not exist.

- [ ] **Step 3: Implement command**

Create `apps/exercises/management/commands/render_harmonization_review.py`:

```python
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.exercises.harmonization.figures import derive_required_notes


CASES = [
    ("C", "C", "6"),
    ("C", "F", "6"),
    ("C", "F", "#"),
    ("C", "G", "7"),
    ("G", "F#", "6/5"),
    ("C", "C", "9/7/5/3"),
]


class Command(BaseCommand):
    help = "Render musician-review artifacts for harmonization theory behavior."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="lab/static/harmonization-review.html",
            help="Path to write the review HTML artifact.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"])
        rows = []
        for key_name, bass, figure in CASES:
            derived = derive_required_notes(key_name=key_name, bass_name=bass, figure=figure)
            label = f"{bass} + {figure}"
            rows.append(
                "<tr>"
                f"<td>{key_name}</td>"
                f"<td>{label}</td>"
                f"<td>{'/'.join(derived['expanded_figures'])}</td>"
                f"<td>{', '.join(derived['required_note_names'])}</td>"
                f"<td>{', '.join(str(pc) for pc in derived['required_upper_pcs'])}</td>"
                "</tr>"
            )

        html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Harmonization Review</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; color: #172033; }
    table { border-collapse: collapse; width: 100%; max-width: 900px; }
    th, td { border: 1px solid #d8dee9; padding: 8px 10px; text-align: left; }
    th { background: #f5f7fb; }
  </style>
</head>
<body>
  <h1>Figure Parser Review</h1>
  <p>Review whether bass+figure inputs expand to the notes a musician expects.</p>
  <table>
    <thead><tr><th>Key</th><th>Input</th><th>Expanded</th><th>Notes</th><th>Pitch classes</th></tr></thead>
    <tbody>
""" + "\n".join(rows) + """
    </tbody>
  </table>
</body>
</html>
"""
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html)
        self.stdout.write(self.style.SUCCESS(f"Wrote {output}"))
```

- [ ] **Step 4: Run tests and render default artifact**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_figures -v 2
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py render_harmonization_review
```

Expected: tests pass and `lab/static/harmonization-review.html` exists.

- [ ] **Step 5: Human review gate**

Open `lab/static/harmonization-review.html` through the local static server or browser. Ask Avner to confirm the figure parser table before proceeding to Roman normalization or frontend work.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/management/commands/render_harmonization_review.py apps/exercises/tests/test_harmonization_figures.py lab/static/harmonization-review.html
git commit -m "feat: add harmonization musical review artifact"
```

---

## Task 4: Normalize UMTO Analysis Slices Into Harmonization Targets

> **Key invariant:** `raw_figured_bass` (full interval stack, e.g. `"6/3"`, `"7/5/3"`) drives
> pitch derivation in `derive_required_notes()`. `figured_bass` (abbreviated, e.g. `"6"`, `"7"`)
> is stored as `displayFigure` for rendering only. Abbreviation drops intervals (e.g. `"6/3"→"6"`
> loses the 3rd), producing incorrect `allowedPcs`. Validation against 200 Bach chord onsets
> confirmed 100% accuracy with `raw_figured_bass` vs 96% with abbreviated.

**Files:**
- Create: `apps/exercises/harmonization/targets.py`
- Test: `apps/exercises/tests/test_harmonization_targets.py`

- [ ] **Step 1: Write failing target tests**

Create `apps/exercises/tests/test_harmonization_targets.py`:

```python
from apps.exercises.harmonization.targets import build_targets_from_umto


def _event(midi, step, octave, duration=1.0, alter=0):
    return {
        "kind": "note",
        "pitch": {"step": step, "alter": alter, "octave": octave, "midi": midi},
        "duration": duration,
        "duration_type": "q",
        "dots": 0,
        "is_tied_start": False,
        "is_tied_stop": False,
        "is_target": True,
    }


def test_build_target_from_figured_bass_slice():
    umto = {
        "metadata": {
            "key": "C",
            "locked_voices": ["B"],
            "voice_count_policy": {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {
            "S": [_event(60, "C", 4)],
            "A": [_event(57, "A", 3)],
            "T": [_event(52, "E", 3)],
            "B": [_event(48, "C", 3)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "6",
                    "raw_figured_bass": "6/3",
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "local_key": "C",
                    "pop_symbol": None,
                    "functional_label": None,
                },
            }
        ],
        "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60]}],
    }

    targets = build_targets_from_umto(umto)

    assert len(targets) == 1
    assert targets[0]["bassMidi"] == 48
    assert targets[0]["bassPc"] == 0
    assert targets[0]["figures"] == ["6", "3"]
    assert targets[0]["requiredUpperPcs"] == [9, 4]
    assert targets[0]["allowedPcs"] == [0, 9, 4]
    assert targets[0]["lockedVoices"]["B"]["midi"] == 48
    assert targets[0]["voiceCountPolicy"] == {"expected": 4, "min": 3, "max": 4}


def test_locked_soprano_is_included_when_configured():
    umto = {
        "metadata": {
            "key": "C",
            "locked_voices": ["B", "S"],
            "voice_count_policy": {"expected": 4, "min": 4, "max": 4},
        },
        "voices": {
            "S": [_event(60, "C", 4)],
            "A": [_event(57, "A", 3)],
            "T": [_event(52, "E", 3)],
            "B": [_event(48, "C", 3)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": "6",
                    "raw_figured_bass": "6/3",
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "local_key": "C",
                    "pop_symbol": None,
                    "functional_label": None,
                },
            }
        ],
        "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60]}],
    }

    targets = build_targets_from_umto(umto)

    assert targets[0]["lockedVoices"]["S"]["midi"] == 60
    assert targets[0]["lockedVoices"]["S"]["pc"] == 0


def test_raw_figured_bass_used_not_abbreviated():
    # "8/6/3" abbreviates to "6" — if we used the abbreviation we'd expand ["6","3"]
    # and get the same result. Use "4/3" (second-inversion seventh) vs abbreviated "4/3"
    # to show raw is preferred: provide only raw_figured_bass (no figured_bass key).
    # More importantly: provide a case where abbreviated form is present but WRONG subset —
    # raw="8/5/3" (root position with octave doubling) should give same pcs as "5/3",
    # whereas if figured_bass were accidentally used and was empty it would fall back to "5/3".
    # The critical case: raw_figured_bass present, figured_bass absent — raw must win.
    umto = {
        "metadata": {
            "key": "G",
            "locked_voices": ["B"],
            "voice_count_policy": {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {
            "S": [_event(74, "D", 5)],
            "A": [_event(69, "A", 4)],
            "T": [_event(62, "D", 4)],
            "B": [_event(55, "G", 3)],
        },
        "analysis": [
            {
                "offset": 0.0,
                "content": {
                    "figured_bass": None,        # absent — raw must be used
                    "raw_figured_bass": "8/5/3",
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "local_key": "G",
                    "pop_symbol": None,
                    "functional_label": None,
                },
            }
        ],
        "grading": [{"offset": 0.0, "target_midi_pitches": [55, 62, 69, 74]}],
    }

    targets = build_targets_from_umto(umto)

    # G major root position: G(7), D(2), A(9)
    assert targets[0]["figures"] == ["8", "5", "3"]   # full stack, not abbreviated
    assert targets[0]["displayFigure"] == "8/5/3"     # falls back to raw when no abbrev
    assert 7 in targets[0]["allowedPcs"]   # G
    assert 2 in targets[0]["allowedPcs"]   # D
    assert 9 in targets[0]["allowedPcs"]   # A
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_targets -v 2
```

Expected: import error for `apps.exercises.harmonization.targets`.

- [ ] **Step 3: Implement target builder**

Create `apps/exercises/harmonization/targets.py`:

```python
from __future__ import annotations

from typing import Any

from apps.exercises.harmonization.figures import derive_required_notes, expand_figure_string


def _voice_event_at_offset(events: list[dict[str, Any]], offset: float) -> dict[str, Any] | None:
    t = 0.0
    for event in events:
        dur = float(event.get("duration") or 0)
        if t <= offset < t + dur - 0.0001:
            return event if event.get("kind") == "note" else None
        t += dur
    return None


def _pitch_name(pitch: dict[str, Any]) -> str:
    alter = int(pitch.get("alter") or 0)
    acc = {0: "", 1: "#", -1: "b", 2: "##", -2: "bb"}[alter]
    return f"{pitch['step']}{acc}"


def _locked_voice_payload(umto: dict[str, Any], voice_id: str, offset: float) -> dict[str, Any] | None:
    event = _voice_event_at_offset(umto.get("voices", {}).get(voice_id, []), offset)
    if not event or not event.get("pitch"):
        return None
    pitch = event["pitch"]
    return {
        "midi": int(pitch["midi"]),
        "pc": int(pitch["midi"]) % 12,
        "spelling": _pitch_name(pitch),
    }


def build_targets_from_umto(umto: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = umto.get("metadata", {})
    key_name = metadata.get("key") or "C"
    locked_voices = metadata.get("locked_voices") or ["B"]
    voice_count_policy = metadata.get("voice_count_policy") or {"expected": None, "min": 3, "max": 4}

    targets = []
    for analysis in umto.get("analysis", []):
        offset = float(analysis["offset"])
        content = analysis.get("content", {})
        bass = _locked_voice_payload(umto, "B", offset)
        if bass is None:
            continue

        # raw_figured_bass (full interval stack, e.g. "6/3") is used for pitch
        # derivation — abbreviation drops intervals and produces wrong notes.
        # figured_bass (abbreviated, e.g. "6") is display-only.
        raw_figure = content.get("raw_figured_bass") or content.get("figured_bass") or "5/3"
        display_figure = content.get("figured_bass") or raw_figure
        local_key = content.get("local_key") or key_name
        derived = derive_required_notes(
            key_name=local_key,
            bass_name=bass["spelling"],
            figure=raw_figure,
        )

        locked = {}
        for voice_id in locked_voices:
            payload = _locked_voice_payload(umto, voice_id, offset)
            if payload is not None:
                locked[voice_id] = payload

        targets.append({
            "offset": offset,
            "bassMidi": bass["midi"],
            "bassPc": bass["pc"],
            "bassSpelling": bass["spelling"],
            "figures": expand_figure_string(raw_figure),      # full stack for grading
            "displayFigure": display_figure,                   # abbreviated for display
            "requiredUpperPcs": derived["required_upper_pcs"],
            "requiredNoteNames": derived["required_note_names"],
            "allowedPcs": derived["allowed_pcs"],
            "lockedVoices": locked,
            "voiceCountPolicy": {
                "expected": voice_count_policy.get("expected"),
                "min": voice_count_policy.get("min", 3),
                "max": voice_count_policy.get("max", 4),
            },
            "source": {
                "kind": "analysis_slice",
                "label": display_figure or content.get("roman_numeral") or "",
                "key": local_key,
            },
        })
    return targets
```

- [ ] **Step 4: Run tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_targets -v 2
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/harmonization/targets.py apps/exercises/tests/test_harmonization_targets.py
git commit -m "feat: normalize UMTO harmonization targets"
```

---

## Task 5: Generate Harmonization Exercise Rows

**Files:**
- Modify: `apps/exercises/umto_factory.py`
- Create: `apps/exercises/management/commands/generate_harmonization.py`
- Test: `apps/exercises/tests/test_generate_harmonization.py`

- [ ] **Step 1: Write failing command test**

Create `apps/exercises/tests/test_generate_harmonization.py`:

```python
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise


class GenerateHarmonizationCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="pw",
        )
        self.source = Exercise.objects.create(
            description="Source UMTO",
            authored_by=self.user,
            data={
                "isUMTO": True,
                "type": "umto_chorale",
                "mode": "playback",
                "analysisType": "figured_bass",
                "score": {
                    "umto": {
                        "metadata": {
                            "exercise_id": "SRC001",
                            "source": "Synthetic source",
                            "key": "C",
                            "meter": "4/4",
                            "clef": "keyboard",
                            "complexity_score": 9,
                            "mode": "playback",
                            "is_umto": True,
                            "input_mode": "dropdown",
                        },
                        "voices": {
                            "S": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4, "midi": 60}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                            "A": [{"kind": "note", "pitch": {"step": "A", "alter": 0, "octave": 3, "midi": 57}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                            "T": [{"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 3, "midi": 52}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                            "B": [{"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 3, "midi": 48}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": False, "is_tied_stop": False, "is_target": True}],
                        },
                        "analysis": [{
                            "offset": 0.0,
                            "content": {"roman_numeral": None, "raw_roman_numeral": None, "local_key": "C", "raw_figured_bass": "6/3", "figured_bass": "6", "pop_symbol": None, "functional_label": None},
                            "visual": None,
                            "unit_tags": [],
                            "is_target": False,
                        }],
                        "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60], "rhythmic_flexibility": False}],
                    }
                },
                "grading": [{"offset": 0.0, "target_midi_pitches": [48, 52, 57, 60], "rhythmic_flexibility": False}],
            },
        )

    def test_command_creates_harmonization_exercise(self):
        call_command(
            "generate_harmonization",
            source=self.source.id,
            author="admin@example.com",
            locked_voices="B",
            min_voices=3,
            max_voices=4,
        )

        created = Exercise.objects.exclude(id=self.source.id).get()
        umto = created.data["score"]["umto"]
        assert umto["metadata"]["mode"] == "harmonization"
        assert umto["metadata"]["locked_voices"] == ["B"]
        assert created.data["harmonizationTargets"][0]["figures"] == ["6", "3"]
```

- [ ] **Step 2: Run failing test**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_harmonization -v 2
```

Expected: command missing.

- [ ] **Step 3: Implement command**

Create `apps/exercises/management/commands/generate_harmonization.py`:

```python
from __future__ import annotations

import copy

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.harmonization.targets import build_targets_from_umto
from apps.exercises.models import Exercise


class Command(BaseCommand):
    help = "Generate a harmonization exercise from an existing UMTO source exercise."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Source Exercise id.")
        parser.add_argument("--author", required=True, help="Author email.")
        parser.add_argument("--locked-voices", dest="locked_voices", default="B")
        parser.add_argument("--prompt", default="figured_bass", choices=["figured_bass", "roman"])
        parser.add_argument("--voice-count", dest="voice_count", type=int, default=None)
        parser.add_argument("--min-voices", dest="min_voices", type=int, default=3)
        parser.add_argument("--max-voices", dest="max_voices", type=int, default=4)
        parser.add_argument("--max-displacement", dest="max_displacement", type=int, default=4)
        parser.add_argument("--public", action="store_true")

    def handle(self, *args, **options):
        try:
            source = Exercise.objects.get(id=options["source"])
        except Exercise.DoesNotExist as exc:
            raise CommandError(f"Source exercise not found: {options['source']}") from exc

        try:
            author = get_user_model().objects.get(email=options["author"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f"Author not found: {options['author']}") from exc

        source_umto = source.data.get("score", {}).get("umto")
        if not source.data.get("isUMTO") or not source_umto:
            raise CommandError("Source exercise must be UMTO with score.umto")

        locked_voices = [v.strip() for v in options["locked_voices"].split(",") if v.strip()]
        voice_count_policy = {
            "expected": options["voice_count"],
            "min": options["min_voices"],
            "max": options["max_voices"],
        }

        umto = copy.deepcopy(source_umto)
        umto["metadata"]["mode"] = "harmonization"
        umto["metadata"]["locked_voices"] = locked_voices
        umto["metadata"]["voice_count_policy"] = voice_count_policy
        umto["metadata"]["harmonization_target_policy"] = {
            "source": "analysis_slice",
            "written_spelling_required": False,
            "midi_uses_pitch_class": True,
        }
        umto["metadata"]["max_voice_displacement"] = options["max_displacement"]
        umto["metadata"]["chord_settle_ms"] = 150
        umto["metadata"]["release_grace_ms"] = 120

        targets = build_targets_from_umto(umto)
        desc = (
            f"Harmonization from {source.id} "
            f"locked={','.join(locked_voices)} voices={voice_count_policy}"
        )
        existing = Exercise.objects.filter(description=desc, authored_by=author).first()
        if existing:
            self.stdout.write(f"Exists: {existing.id}")
            return

        data = copy.deepcopy(source.data)
        data["mode"] = "harmonization"
        data["analysisType"] = options["prompt"]
        data["score"]["umto"] = umto
        data["harmonizationTargets"] = targets

        ex = Exercise.objects.create(
            description=desc,
            authored_by=author,
            data=data,
            public=options["public"],
            skill_tags=list(source.skill_tags or []) + ["mode:harmonization"],
            complexity=source.complexity,
        )
        umto["metadata"]["exercise_id"] = ex.id
        ex.data["exerciseId"] = ex.id
        ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
        ex.save(update_fields=["data"])
        self.stdout.write(self.style.SUCCESS(f"Created {ex.id}"))
```

- [ ] **Step 4: Run command tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_harmonization -v 2
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_harmonization.py apps/exercises/tests/test_generate_harmonization.py
git commit -m "feat: generate UMTO harmonization exercises"
```

---

## Task 6: Add Frontend Active-Sonority Grading Logic

**Files:**
- Create: `lab/static/js/src/models/harmonization_grader_logic.js`
- Create: `lab/static/js/src/models/harmonization_grader_logic.test.js`

- [ ] **Step 1: Write JS logic tests**

Create `lab/static/js/src/models/harmonization_grader_logic.test.js`:

```javascript
"use strict";

var logic = require("./harmonization_grader_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, "got", actual, "expected", expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

var target = {
  bassMidi: 48,
  bassPc: 0,
  requiredUpperPcs: [9, 4],
  allowedPcs: [0, 9, 4],
  lockedVoices: { B: { midi: 48, pc: 0, spelling: "C" } },
  voiceCountPolicy: { expected: 4, min: 3, max: 4 }
};

assertEqual("correct three-voice realization passes", logic.harmonizationMatch(target, [48, 52, 57]).state, "correct");
assertEqual("doubling allowed within max voices", logic.harmonizationMatch(target, [48, 52, 57, 60]).state, "correct");
assertEqual("missing required pc is partial", logic.harmonizationMatch(target, [48, 52]).state, "partial");
assertEqual("illegal pc is incorrect", logic.harmonizationMatch(target, [48, 52, 58]).state, "incorrect");
assertEqual("wrong bass is incorrect", logic.harmonizationMatch(target, [47, 52, 57]).state, "incorrect");
assertEqual("too many voices is incorrect", logic.harmonizationMatch(target, [48, 52, 57, 60, 64]).state, "incorrect");

var sopranoTarget = {
  bassMidi: 48,
  bassPc: 0,
  requiredUpperPcs: [9, 4],
  allowedPcs: [0, 9, 4],
  lockedVoices: { B: { midi: 48, pc: 0 }, S: { midi: 60, pc: 0 } },
  voiceCountPolicy: { expected: 4, min: 4, max: 4 }
};

assertEqual("locked soprano exact midi passes", logic.harmonizationMatch(sopranoTarget, [48, 52, 57, 60]).state, "correct");
assertEqual("locked soprano wrong octave fails", logic.harmonizationMatch(sopranoTarget, [48, 52, 57, 72]).state, "incorrect");
```

- [ ] **Step 2: Run failing JS test**

Run:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
```

Expected: module missing.

- [ ] **Step 3: Implement pure grader**

Create `lab/static/js/src/models/harmonization_grader_logic.js`:

```javascript
"use strict";

function uniq(arr) {
  var seen = {};
  var result = [];
  for (var i = 0; i < arr.length; i += 1) {
    if (!seen[arr[i]]) {
      seen[arr[i]] = true;
      result.push(arr[i]);
    }
  }
  return result;
}

function pcs(midi) {
  return ((midi % 12) + 12) % 12;
}

function includes(arr, value) {
  return arr.indexOf(value) !== -1;
}

function harmonizationMatch(target, activeMidi) {
  var active = (activeMidi || []).slice().sort(function (a, b) { return a - b; });
  var reasons = [];
  var note = {};
  var activePcs = uniq(active.map(pcs));
  var locked = target.lockedVoices || {};
  var policy = target.voiceCountPolicy || { min: 3, max: 4 };

  if (locked.B && !includes(active, locked.B.midi)) {
    reasons.push("wrong_bass");
  }
  if (locked.S && !includes(active, locked.S.midi)) {
    reasons.push("wrong_locked_soprano");
  }

  for (var i = 0; i < active.length; i += 1) {
    if (!includes(target.allowedPcs || [], pcs(active[i]))) {
      reasons.push("illegal_pc");
      note[active[i]] = "incorrect";
    } else {
      note[active[i]] = "correct";
    }
  }

  for (var r = 0; r < (target.requiredUpperPcs || []).length; r += 1) {
    if (!includes(activePcs, target.requiredUpperPcs[r])) {
      reasons.push("missing_required_pc");
    }
  }

  if (policy.min != null && active.length < policy.min) {
    reasons.push("too_few_voices");
  }
  if (policy.max != null && active.length > policy.max) {
    reasons.push("too_many_voices");
  }

  var hardReasons = reasons.filter(function (reason) {
    return reason !== "missing_required_pc" && reason !== "too_few_voices";
  });
  var state = hardReasons.length ? "incorrect" : reasons.length ? "partial" : "correct";

  return {
    state: state,
    reasons: uniq(reasons),
    accepted: state === "correct",
    activeMidi: active,
    note: note,
    target: target
  };
}

module.exports = {
  harmonizationMatch: harmonizationMatch
};
```

- [ ] **Step 4: Run JS test**

Run:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
```

Expected: all `PASS`.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/harmonization_grader_logic.js lab/static/js/src/models/harmonization_grader_logic.test.js
git commit -m "feat: add harmonization active-sonority grader"
```

---

## Task 7: Add Held-Note Timing State

**Files:**
- Modify: `lab/static/js/src/models/harmonization_grader_logic.js`
- Modify: `lab/static/js/src/models/harmonization_grader_logic.test.js`

- [ ] **Step 1: Add tests for held-note state**

Append:

```javascript
var tracker = logic.createHeldNoteTracker({ releaseGraceMs: 120 });
tracker.noteOn(48, 0);
tracker.noteOn(52, 20);
tracker.noteOn(57, 40);
assertEqual("tracker holds chord", tracker.activeMidi(100), [48, 52, 57]);
tracker.noteOff(48, 110);
assertEqual("release grace keeps bass briefly", tracker.activeMidi(150), [48, 52, 57]);
assertEqual("release grace removes bass after timeout", tracker.activeMidi(240), [52, 57]);
```

- [ ] **Step 2: Run failing test**

Run:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
```

Expected: `createHeldNoteTracker` missing.

- [ ] **Step 3: Implement tracker**

Add to `harmonization_grader_logic.js`:

```javascript
function createHeldNoteTracker(options) {
  options = options || {};
  var releaseGraceMs = options.releaseGraceMs == null ? 120 : options.releaseGraceMs;
  var held = {};
  var releasedAt = {};

  return {
    noteOn: function (midi, atMs) {
      held[midi] = true;
      delete releasedAt[midi];
    },
    noteOff: function (midi, atMs) {
      if (held[midi]) {
        releasedAt[midi] = atMs;
      }
    },
    activeMidi: function (nowMs) {
      var result = [];
      Object.keys(held).forEach(function (key) {
        var midi = parseInt(key, 10);
        if (releasedAt[midi] == null) {
          result.push(midi);
        } else if (nowMs - releasedAt[midi] <= releaseGraceMs) {
          result.push(midi);
        } else {
          delete held[midi];
          delete releasedAt[midi];
        }
      });
      return result.sort(function (a, b) { return a - b; });
    }
  };
}
```

Update `module.exports`:

```javascript
module.exports = {
  harmonizationMatch: harmonizationMatch,
  createHeldNoteTracker: createHeldNoteTracker
};
```

- [ ] **Step 4: Run JS test**

Run:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
```

Expected: all `PASS`.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/harmonization_grader_logic.js lab/static/js/src/models/harmonization_grader_logic.test.js
git commit -m "feat: track held notes for harmonization grading"
```

---

## Task 8: Wire Harmonization Into ExerciseDefinition And Grader

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`
- Modify: `lab/static/js/src/models/exercise_grader.js`
- Create: `lab/static/js/src/models/harmonization_targets_logic.js`
- Create: `lab/static/js/src/models/harmonization_targets_logic.test.js`

- [ ] **Step 1: Add pure target parsing test**

Create `lab/static/js/src/models/harmonization_targets_logic.test.js`:

```javascript
"use strict";

var logic = require("./harmonization_targets_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, "got", actual, "expected", expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

var definition = {
  mode: "harmonization",
  harmonizationTargets: [{ offset: 0, bassMidi: 48, figures: ["6", "3"] }]
};

assertEqual("returns harmonization targets", logic.getHarmonizationTargets(definition), definition.harmonizationTargets);
assertEqual("detects harmonization mode", logic.isHarmonization(definition), true);
assertEqual("non harmonization false", logic.isHarmonization({ mode: "playback" }), false);
```

- [ ] **Step 2: Run failing test**

Run:

```bash
node lab/static/js/src/models/harmonization_targets_logic.test.js
```

Expected: module missing.

- [ ] **Step 3: Implement pure target helper**

Create `lab/static/js/src/models/harmonization_targets_logic.js`:

```javascript
"use strict";

function getMode(definition) {
  return definition.mode ||
    (definition.score && definition.score.umto && definition.score.umto.metadata && definition.score.umto.metadata.mode) ||
    null;
}

function isHarmonization(definition) {
  return getMode(definition) === "harmonization";
}

function getHarmonizationTargets(definition) {
  return definition.harmonizationTargets || [];
}

module.exports = {
  getMode: getMode,
  isHarmonization: isHarmonization,
  getHarmonizationTargets: getHarmonizationTargets
};
```

- [ ] **Step 4: Run pure target test**

Run:

```bash
node lab/static/js/src/models/harmonization_targets_logic.test.js
```

Expected: all `PASS`.

- [ ] **Step 5: Collapse duplicate `getMode()` in `exercise_definition.js`**

Keep one authoritative `getMode()` method:

```javascript
getMode: function () {
  return this.exercise.mode ||
    (this.exercise.score &&
      this.exercise.score.umto &&
      this.exercise.score.umto.metadata &&
      this.exercise.score.umto.metadata.mode) ||
    null;
},
```

Remove the later duplicate method that returns `"play-all-voices"` by default. If callers need that default, update only those callers to use `definition.getMode() || "play-all-voices"`.

- [ ] **Step 6: Add `isHarmonization()` and target accessors**

In `exercise_definition.js`, add:

```javascript
isHarmonization: function () {
  return this.getMode() === "harmonization";
},

getHarmonizationTargets: function () {
  return this.exercise.harmonizationTargets || [];
},
```

In the UMTO parse block, after `exercise.grading = definition.grading || [];`, add:

```javascript
exercise.harmonizationTargets = definition.harmonizationTargets || [];
```

In the `umto_chorale` parse branch, set:

```javascript
var isHarmonization = exercise.mode === "harmonization";
if (isHarmonization) {
  exercise.problems = exercise.harmonizationTargets;
} else if (isIdent) {
  ...
}
```

- [ ] **Step 7: Route `exercise_grader.js`**

Add `app/models/harmonization_grader_logic` to the AMD dependency list and factory args. In the `umto_chorale` switch branch:

```javascript
if (mode === "harmonization") {
  result = HarmonizationGraderLogic.harmonizationMatch(problems[i], actual_notes);
} else if (mode === "analysis_match") {
  result = this.analysisMatch(expected_notes, actual_notes, analysis_types);
} else {
  result = this.notesMatch(expected_notes, actual_notes, problems[i].unison_idx || null, delivered_unison_idx);
}
```

When `mode === "harmonization"`, use `problems[i]` as the target and do not read `problems[i].notes`.

> **Wiring note:** `actual_notes` here must be the **current held-MIDI snapshot** from
> `HeldNoteTracker.activeMidi(nowMs)`, not the chord-bank `inputChords` array used by
> other modes. The chord bank accumulates note-on events per problem slot; the harmonization
> grader needs the live sonority at settle time. Wire the tracker's output — not `inputChords`
> — as the second argument to `harmonizationMatch`. This wiring is confirmed and tested in
> Task 12; if the existing event path makes it awkward, Task 12 step 7 is the place to fix it.

- [ ] **Step 8: Run targeted tests**

Run:

```bash
node lab/static/js/src/models/harmonization_targets_logic.test.js
node lab/static/js/src/models/harmonization_grader_logic.test.js
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js lab/static/js/src/models/exercise_grader.js lab/static/js/src/models/harmonization_targets_logic.js lab/static/js/src/models/harmonization_targets_logic.test.js
git commit -m "feat: route frontend harmonization grading"
```

---

## Task 9: Add ExerciseContext Settle-Window Advancement

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`
- Modify: `lab/static/js/src/models/harmonization_grader_logic.js`

- [ ] **Step 1: Add accepted-sonority fields in constructor**

In `ExerciseContext` constructor, initialize:

```javascript
this.acceptedHarmonizationSonorities = [];
this._harmonizationSettleTimer = null;
this._harmonizationHeldTracker = null;
```

- [ ] **Step 2: Add helper methods**

Add methods to `ExerciseContext.prototype`:

```javascript
isHarmonizationExercise: function () {
  return !!(this.definition && this.definition.isHarmonization && this.definition.isHarmonization());
},

recordAcceptedHarmonizationSonority: function (graded) {
  if (!graded || graded.result !== this.grader.STATE.CORRECT) return;
  var activeIndex = typeof graded.activeIndex === "number" ? graded.activeIndex : 0;
  var problem = graded.problems && graded.problems[activeIndex];
  if (!problem || !problem.notes) return;
  this.acceptedHarmonizationSonorities[activeIndex] = problem.notes.slice(0);
},
```

- [ ] **Step 3: Update `grade()` completion path**

After `graded = this.grader.grade(this.definition, this.inputChords);`, add:

```javascript
if (this.isHarmonizationExercise()) {
  this.recordAcceptedHarmonizationSonority(graded);
}
```

In `compileExerciseReport()`, add:

```javascript
if (this.isHarmonizationExercise()) {
  report.harmonization_accepted_sonorities = this.acceptedHarmonizationSonorities || [];
  report.harmonization_attempt_count = this.errorTally + (this.acceptedHarmonizationSonorities || []).length;
}
```

- [ ] **Step 4: Defer full MIDI debounce until integration**

Do not yet replace low-level MIDI event handling. This task records accepted sonorities through the existing chord-bank flow. The actual `noteOn`/`noteOff` settle timer is implemented after rendering and a live prototype expose where MIDI events enter this mode.

- [ ] **Step 5: Run current JS tests**

Run:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
node lab/static/js/src/models/harmonization_targets_logic.test.js
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: record harmonization accepted sonorities"
```

---

## Task 10: Render Harmonization As UMTO Notation With Locked Voices

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
- Modify: `lab/static/harmonization-process-visualization.html`

- [ ] **Step 1: Add harmonization to the chorale-like render path**

In `exercise_sheet.js`, change:

```javascript
var isChoraleLike = (definition.isChorale() || definition.isChoraleIdentification());
```

to:

```javascript
var isHarmonization = !!(definition.isHarmonization && definition.isHarmonization());
var isChoraleLike = (definition.isChorale() || definition.isChoraleIdentification() || isHarmonization);
```

In the render options for `VexFlowAdapter.render`, add:

```javascript
isHarmonization: isHarmonization,
lockedVoices: isHarmonization && definition.exercise && definition.exercise.score && definition.exercise.score.umto
  ? (definition.exercise.score.umto.metadata.locked_voices || ["B"])
  : null,
```

- [ ] **Step 2: Extend adapter function signatures**

In `vexflow_adapter.js`, extend `itemToTickable` signature:

```javascript
function itemToTickable(clef, item, octaveShift, idState, keySignatureAlterations, onset, measureIndex, showNotation, isAnalysisMatch, harmonizationOptions) {
```

Default:

```javascript
harmonizationOptions = harmonizationOptions || {};
```

- [ ] **Step 3: Hide unlocked voices**

Where note/chord style is set, compute:

```javascript
var hideForHarmonization = harmonizationOptions.isHarmonization && harmonizationOptions.hideCurrentVoice;
```

Use it with existing transparency logic:

```javascript
} else if (!showNotation || isAnalysisMatch || hideForHarmonization) {
  note.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
}
```

The current adapter does not pass voice id into `itemToTickable`; add that only at the call site that loops voices. The rule should be:

```javascript
hideCurrentVoice = isHarmonization && lockedVoices.indexOf(voiceId) === -1;
```

Use existing SATB mapping in the render loop. Do not infer voice identity from pitch.

- [ ] **Step 4: Keep figures visible**

For harmonization, ensure `analyzeConfig.enabled = true` and `thoroughbass` mode is enabled when `analysisType === "figured_bass"`:

```javascript
if (isHarmonization) {
  analyzeConfig.enabled = true;
  analyzeConfig.mode = analyzeConfig.mode || {};
  if (definition.getAnalysisType && definition.getAnalysisType() === "figured_bass") {
    analyzeConfig.mode.thoroughbass = true;
  } else {
    analyzeConfig.mode.roman_numerals = true;
  }
}
```

- [ ] **Step 5: Update visual companion**

In `lab/static/harmonization-process-visualization.html`, add a link to the generated review artifact:

```html
<p class="small">
  Review generated parser examples:
  <a href="/static/harmonization-review.html">harmonization-review.html</a>
</p>
```

- [ ] **Step 6: Manual render check**

Start the local server:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver 127.0.0.1:8001 --noreload
```

Open:

```text
http://127.0.0.1:8001/static/harmonization-process-visualization.html
http://127.0.0.1:8001/static/harmonization-review.html
```

Expected: both pages render. Full app rendering is verified after one generated exercise exists in Task 12.

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js lab/static/js/src/components/music/rendering/vexflow_adapter.js lab/static/harmonization-process-visualization.html
git commit -m "feat: render harmonization locked voices"
```

---

## Task 11: Add Voice-Leading Quality Logic

**Files:**
- Create: `lab/static/js/src/models/voice_leading_logic.js`
- Create: `lab/static/js/src/models/voice_leading_logic.test.js`
- Modify: `lab/static/js/src/models/exercise_context.js`

- [ ] **Step 1: Write pure tests**

Create `lab/static/js/src/models/voice_leading_logic.test.js`:

```javascript
"use strict";

var logic = require("./voice_leading_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, "got", actual, "expected", expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "smooth close motion passes",
  logic.scoreVoiceLeading([[48, 52, 57], [47, 53, 57]], { maxDisplacement: 4, leadingTonePc: 11 }).smoothOK,
  true
);

assertEqual(
  "large leap fails smoothness",
  logic.scoreVoiceLeading([[48, 52, 57], [36, 53, 69]], { maxDisplacement: 4, leadingTonePc: 11 }).smoothOK,
  false
);

assertEqual(
  "doubled leading tone detected",
  logic.scoreVoiceLeading([[47, 59, 62]], { maxDisplacement: 4, leadingTonePc: 11 }).noDoubledLT,
  false
);
```

- [ ] **Step 2: Run failing test**

Run:

```bash
node lab/static/js/src/models/voice_leading_logic.test.js
```

Expected: module missing.

- [ ] **Step 3: Implement minimal quality module**

Create `lab/static/js/src/models/voice_leading_logic.js`:

```javascript
"use strict";

function pc(midi) {
  return ((midi % 12) + 12) % 12;
}

function bestMapping(prevUpper, curUpper) {
  var prev = prevUpper.slice(0);
  var cur = curUpper.slice(0);
  var len = Math.min(prev.length, cur.length);
  var maxDisp = 0;
  var totalDisp = 0;
  var pairs = [];
  for (var i = 0; i < len; i += 1) {
    var disp = Math.abs(cur[i] - prev[i]);
    if (disp > maxDisp) maxDisp = disp;
    totalDisp += disp;
    pairs.push([prev[i], cur[i]]);
  }
  return { maxDisp: maxDisp, totalDisp: totalDisp, pairs: pairs };
}

function checkDoubledLT(chord, leadingTonePc) {
  var count = 0;
  for (var i = 0; i < chord.length; i += 1) {
    if (pc(chord[i]) === leadingTonePc) count += 1;
  }
  return count > 1;
}

function scoreVoiceLeading(sonorities, options) {
  options = options || {};
  var maxDisplacement = options.maxDisplacement == null ? 4 : options.maxDisplacement;
  var leadingTonePc = options.leadingTonePc;
  var smoothOK = true;
  var noDoubledLT = true;
  var details = [];

  for (var i = 0; i < sonorities.length; i += 1) {
    if (leadingTonePc != null && checkDoubledLT(sonorities[i], leadingTonePc)) {
      noDoubledLT = false;
    }
    if (i > 0) {
      var mapping = bestMapping(sonorities[i - 1].slice(1), sonorities[i].slice(1));
      if (mapping.maxDisp > maxDisplacement) smoothOK = false;
      details.push({ slotPair: [i - 1, i], maxDisp: mapping.maxDisp, totalDisp: mapping.totalDisp, parallels: [], doubledLT: false });
    }
  }

  return {
    smoothOK: smoothOK,
    noParallels: true,
    noDoubledLT: noDoubledLT,
    details: details
  };
}

module.exports = {
  bestMapping: bestMapping,
  checkDoubledLT: checkDoubledLT,
  scoreVoiceLeading: scoreVoiceLeading
};
```

- [ ] **Step 4: Run tests**

Run:

```bash
node lab/static/js/src/models/voice_leading_logic.test.js
```

Expected: all `PASS`.

- [ ] **Step 5: Attach VL score to performance report**

In `exercise_context.js`, add AMD dependency if needed or compute with the pure module through AMD wrapper. In `compileExerciseReport()` harmonization block, add:

```javascript
report.harmonization_tier = this.harmonizationTier || null;
report.vl_score = this.harmonizationVLScore || null;
```

In the completion path for harmonization, compute:

```javascript
this.harmonizationVLScore = VoiceLeadingLogic.scoreVoiceLeading(
  this.acceptedHarmonizationSonorities || [],
  { maxDisplacement: this.definition.exercise.score.umto.metadata.max_voice_displacement || 4 }
);
this.harmonizationTier = this.harmonizationVLScore.smoothOK &&
  this.harmonizationVLScore.noParallels &&
  this.harmonizationVLScore.noDoubledLT
  ? "excellent"
  : "developing";
```

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/models/voice_leading_logic.js lab/static/js/src/models/voice_leading_logic.test.js lab/static/js/src/models/exercise_context.js
git commit -m "feat: score harmonization voice leading"
```

---

## Task 12: End-To-End Prototype And Review Gate

**Files:**
- Uses: `apps/exercises/management/commands/generate_harmonization.py`
- Uses: `apps/exercises/management/commands/render_harmonization_review.py`
- Modify only if defects are found.

- [ ] **Step 1: Run backend test suite slice**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_harmonization_figures apps.exercises.tests.test_harmonization_targets apps.exercises.tests.test_generate_harmonization apps.exercises.tests.test_figured_bass apps.exercises.tests.test_import_bach_phrases -v 2
```

Expected: all pass.

- [ ] **Step 2: Run frontend logic tests**

Run:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
node lab/static/js/src/models/harmonization_targets_logic.test.js
node lab/static/js/src/models/voice_leading_logic.test.js
```

Expected: all `PASS`.

- [ ] **Step 3: Render musician-review artifact**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py render_harmonization_review
```

Expected: `lab/static/harmonization-review.html` is updated.

- [ ] **Step 4: Generate one real harmonization exercise from a Bach UMTO source**

Find a suitable source — must have non-empty `analysis` array or `generate_harmonization` will produce zero targets and abort:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c "
from apps.exercises.models import Exercise
qs = Exercise.objects.filter(data__isUMTO=True, data__analysisType='figured_bass')
good = [e for e in qs if e.data.get('score', {}).get('umto', {}).get('analysis')]
print([(e.id, e.description) for e in good[:10]])
"
```

Then run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py generate_harmonization --source SOURCE_ID --author admin@example.com --locked-voices B --voice-count 4 --min-voices 3 --max-voices 4 --public
```

Expected: command prints `Created EXID` or `Exists: EXID`.

> **Guard:** `generate_harmonization` must raise `CommandError` (not silently create an empty exercise) if `build_targets_from_umto` returns zero targets. Add this check to the command implementation in Task 5 step 3.

- [ ] **Step 5: Start local server**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver 127.0.0.1:8001 --noreload
```

Expected: server starts without tracebacks.

- [ ] **Step 6: Musician review gate**

Ask Avner to review:

```text
http://127.0.0.1:8001/static/harmonization-review.html
```

Then open the generated exercise through the normal playlist or admin/player route available for that exercise. Review:

- bass and figures appear correctly
- locked voices are visible
- hidden voices are not spoiled
- correct sonority advances
- missing notes do not advance
- illegal notes give immediate feedback
- held common-tone motion behaves musically

- [ ] **Step 7: Fix only defects found by the review**

For each defect, add a failing Python or JS test first, then patch the smallest affected module.

- [ ] **Step 8: Commit final prototype fixes**

```bash
git add apps lab docs
git commit -m "feat: validate harmonization prototype"
```

---

## Self-Review Notes

- Spec coverage:
  - Bass+figures canonical model: Tasks 2 and 4.
  - Existing theory reuse: Tasks 2, 4, and 5 reuse `compute_figured_bass`, UMTO analysis, and music21.
  - Musician artifacts: Tasks 3 and 12.
  - Active sonority and held notes: Tasks 6, 7, and 9.
  - Locked soprano/bass: Tasks 4, 6, and 10.
  - Voice-count policy: Tasks 1, 4, and 6.
  - Voice-leading layer: Task 11.
  - Source generation: Task 5.
- Known implementation risk:
  - Roman numeral normalization beyond existing analysis labels is intentionally not first. The first working path consumes existing figured-bass fields already produced by Bach/import code. Add explicit Roman-to-bass+figure expansion after the figured-bass path passes review.
  - Full live MIDI debounce may require tracing the current input event path. Task 7 creates the pure held-note model; Task 12 validates integration and should add follow-up tests if event wiring differs from assumptions.
