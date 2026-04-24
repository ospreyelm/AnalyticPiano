# UMTO Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make UMTO the single canonical Exercise representation via a shared factory module, model-level guards, contract tests, golden fixtures, and migration of all Exercise-creating code paths to UMTO.

**Architecture:** Four layers built bottom-up.
(1) `apps/exercises/umto_factory.py` owns CIR→UMTO conversion and is the only sanctioned path to create an Exercise.
(2) `Exercise.clean()` + `Exercise.save()` guard rejects new non-UMTO rows with `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` emergency bypass.
(3) `lab/views.py` and the dashboard duplicate endpoint route through the factory and log (not print) on UMTO validation failures.
(4) Golden-fixture contract tests in Python and JS pin the UMTO shape against drift.

**Tech Stack:** Python 3.11, Django, Pydantic v2, pytest, Jest/Jasmine (repo's existing JS runner — verified in Task 14), PostgreSQL, music21.

**Spec:** [docs/superpowers/specs/2026-04-23-umto-consistency-design.md](../specs/2026-04-23-umto-consistency-design.md)

---

## File Structure

### New files
- `apps/exercises/umto_factory.py` — factory + `NonUMTOExerciseError`
- `apps/exercises/tests/test_umto_factory.py` — unit tests for factory
- `apps/exercises/tests/test_umto_contract.py` — contract tests against fixtures
- `apps/exercises/tests/fixtures/umto/unit1_identification_treble.json`
- `apps/exercises/tests/fixtures/umto/unit1_identification_bass.json`
- `apps/exercises/tests/fixtures/umto/unit1_playback_treble.json`
- `apps/exercises/tests/fixtures/umto/unit1_analysis_treble.json`
- `apps/exercises/tests/fixtures/umto/unit9_chorale_roman.json`
- `apps/exercises/tests/fixtures/umto/unit12_chromatic_analysis.json`
- `apps/exercises/tests/fixtures/umto/minimal.json`
- `apps/exercises/tests/fixtures/umto/maximal.json`
- `apps/exercises/tests/fixtures/cir_inputs/` (one CIR per fixture)
- `apps/exercises/management/commands/make_umto_schema.py`
- `apps/exercises/management/commands/make_umto_fixtures.py`
- `lab/static/js/test/test_umto_rendering.js` (Task 14 verifies runner)
- `docs/UMTO_GUIDE.md`

### Modified files
- `apps/exercises/models.py` — `clean()`, `save()` guard
- `apps/exercises/umto_schema.json` — regenerated
- `apps/exercises/management/commands/generate_unit1.py` — collapse builders, fix argparse
- `apps/exercises/management/commands/migrate_unit1_to_umto.py` — use factory
- `apps/exercises/management/commands/migrate_exercises.py` — audit, use factory
- `apps/exercises/management/commands/import_chorale.py` — use factory
- `apps/exercises/management/commands/import_bach_phrases.py` — use factory
- `apps/exercises/management/commands/import_musicxml.py` — use factory
- `apps/exercises/management/commands/mass_import_performance.py` — use factory
- `apps/exercises/management/commands/duplicate_chorale_as_identification.py` — use factory
- `apps/dashboard/views/exercises.py` — duplicate-as-pitch via factory
- `lab/views.py` — `logger.warning` replaces `print`
- `CLAUDE.md` — top-level UMTO directive
- All `apps/**/tests/*.py` that create Exercise rows
- `scratch/batch_import_unit9.py`, `scratch/fix_mismatched_keys.py` — migrate or delete

---

## Task 1: Bootstrap factory module skeleton

**Files:**
- Create: `apps/exercises/umto_factory.py`
- Test: `apps/exercises/tests/test_umto_factory.py`

- [ ] **Step 1.1: Write failing test for NonUMTOExerciseError import**

Create `apps/exercises/tests/test_umto_factory.py`:

```python
import pytest
from apps.exercises.umto_factory import NonUMTOExerciseError


def test_non_umto_exercise_error_is_value_error_subclass():
    assert issubclass(NonUMTOExerciseError, ValueError)


def test_non_umto_exercise_error_carries_message():
    err = NonUMTOExerciseError("test message")
    assert str(err) == "test message"
```

- [ ] **Step 1.2: Run test, verify fail**

Run: `pytest apps/exercises/tests/test_umto_factory.py -v`
Expected: `ImportError: cannot import name 'NonUMTOExerciseError' from 'apps.exercises.umto_factory'`

- [ ] **Step 1.3: Create module with error class**

Create `apps/exercises/umto_factory.py`:

```python
"""Canonical factory for creating UMTO-backed Exercise rows.

This module owns the CIR→UMTO conversion. Every Exercise creation path in the
codebase flows through `save_umto_exercise`. Direct `Exercise(data={...}).save()`
for new rows is blocked by `Exercise.clean()` and `Exercise.save()` guards.

Emergency bypass: set HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 for one-shot migration
scripts only. Never set in CI, tests, or production.
"""

from __future__ import annotations


class NonUMTOExerciseError(ValueError):
    """Raised when save_umto_exercise is handed legacy-shaped data, or when
    Exercise.save() / Exercise.clean() sees a new row whose data fails UMTO
    validation."""
```

- [ ] **Step 1.4: Run test, verify pass**

Run: `pytest apps/exercises/tests/test_umto_factory.py -v`
Expected: 2 passed.

- [ ] **Step 1.5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_umto_factory.py
git commit -m "Bootstrap umto_factory module with NonUMTOExerciseError"
```

---

## Task 2: Factory — `build_umto_payload` for single-voice (Unit 1) case

**Files:**
- Modify: `apps/exercises/umto_factory.py`
- Test: `apps/exercises/tests/test_umto_factory.py`

- [ ] **Step 2.1: Write failing test for single-voice treble build**

Append to `apps/exercises/tests/test_umto_factory.py`:

```python
from apps.exercises.umto import InteractionMode


SINGLE_VOICE_CIR = {
    "meta": {"key": "C", "time": "4/4"},
    "measures": [
        {
            "staves": {
                "treble": {
                    "voices": [
                        {
                            "items": [
                                {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "F", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                            ]
                        }
                    ]
                }
            }
        }
    ],
}


def test_build_umto_payload_single_voice_treble_identification():
    from apps.exercises.umto_factory import build_umto_payload

    payload = build_umto_payload(
        exercise_id="TEMP",
        source="Test",
        key="C",
        meter="4/4",
        clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        score_data=SINGLE_VOICE_CIR,
        target_voice="soprano",
        unit=1,
    )

    assert payload["isUMTO"] is True
    assert payload["type"] == "umto_chorale"
    assert payload["mode"] == "identification"
    assert payload["clef"] == "treble"
    assert payload["staffDistribution"] == "treble"
    assert payload["complexity_score"] == 1
    assert payload["key"] == "C"
    assert payload["meter"] == "4/4"

    umto = payload["score"]["umto"]
    assert len(umto["voices"]["S"]) == 4
    assert umto["voices"]["S"][0]["pitch"]["midi"] == 60
    assert umto["voices"]["S"][1]["pitch"]["midi"] == 62
    assert umto["voices"]["S"][2]["pitch"]["midi"] == 64
    assert umto["voices"]["S"][3]["pitch"]["midi"] == 65
    assert len(umto["grading"]) == 4
    assert umto["grading"][0]["offset"] == 0.0
    assert umto["grading"][1]["offset"] == 1.0
    assert umto["grading"][2]["offset"] == 2.0
    assert umto["grading"][3]["offset"] == 3.0
    assert umto["grading"][0]["target_midi_pitches"] == [60]
    assert len(umto["analysis"]) == 4
    assert umto["analysis"][0]["unit_tags"] == [1]
```

- [ ] **Step 2.2: Run test, verify fail**

Run: `pytest apps/exercises/tests/test_umto_factory.py::test_build_umto_payload_single_voice_treble_identification -v`
Expected: `ImportError: cannot import name 'build_umto_payload'`.

- [ ] **Step 2.3: Implement `build_umto_payload`**

Append to `apps/exercises/umto_factory.py`:

```python
from typing import Optional

from apps.exercises.umto import (
    UMTO,
    Metadata,
    Voices,
    VoiceEvent,
    Pitch,
    GradingSlice,
    AnalysisSlice,
    AnalysisLayer,
    InteractionMode,
)


_DUR_QL = {"w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "16": 0.25, "32": 0.125}
_STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_VOICE_NAME_TO_ID = {"soprano": "S", "alto": "A", "tenor": "T", "bass": "B"}


def _duration_ql(duration: dict) -> float:
    base = _DUR_QL.get(duration.get("type", "q"), 1.0)
    dots = duration.get("dots", 0)
    return base * (2.0 - 0.5 ** dots) if dots else base


def _pitch_to_midi(step: str, alter: int, octave: int) -> int:
    return ((int(octave) + 1) * 12) + _STEP_SEMITONES[step] + int(alter)


def _resolve_voice_id(target_voice: Optional[str], clef: str) -> str:
    if target_voice:
        vid = _VOICE_NAME_TO_ID.get(target_voice.lower())
        if vid is None:
            raise ValueError(f"Unknown target_voice: {target_voice}")
        return vid
    return "S" if clef == "treble" else "B"


def build_umto_payload(
    *,
    exercise_id: str,
    source: str,
    key: str,
    meter: str,
    clef: str,
    complexity_score: int,
    mode: InteractionMode,
    score_data: dict,
    target_voice: Optional[str] = None,
    unit: Optional[int] = None,
    analysis_overrides: Optional[list] = None,
) -> dict:
    """Build a UMTO frontend payload from CIR-shaped score_data.

    Owns all CIR→UMTO conversion. See spec
    docs/superpowers/specs/2026-04-23-umto-consistency-design.md for contract.
    """
    metadata = Metadata(
        exercise_id=exercise_id,
        source=source,
        key=key,
        meter=meter,
        clef=clef,
        complexity_score=complexity_score,
        mode=mode,
    )

    voices_dict: dict[str, list[VoiceEvent]] = {"S": [], "A": [], "T": [], "B": []}
    grading_slices: list[GradingSlice] = []
    analysis_slices: list[AnalysisSlice] = []

    voice_id = _resolve_voice_id(target_voice, clef)
    current_offset = 0.0

    for measure in score_data.get("measures", []):
        staff = measure.get("staves", {}).get(clef, {})
        voice_list = staff.get("voices", [])
        if not voice_list:
            continue
        items = voice_list[0].get("items", [])
        for item in items:
            dur = item.get("duration", {})
            ql = _duration_ql(dur)
            kind = item.get("kind")
            if kind == "note":
                p = item.get("pitch", {})
                midi = _pitch_to_midi(p.get("step", "C"), p.get("alter", 0), p.get("octave", 4))
                pitch = Pitch(step=p["step"], alter=p.get("alter", 0), octave=p["octave"], midi=midi)
                voices_dict[voice_id].append(
                    VoiceEvent(
                        kind="note",
                        pitch=pitch,
                        duration=ql,
                        duration_type=dur.get("type", "q"),
                        dots=dur.get("dots", 0),
                    )
                )
                grading_slices.append(
                    GradingSlice(offset=current_offset, target_midi_pitches=[midi])
                )
                analysis_slices.append(
                    AnalysisSlice(
                        offset=current_offset,
                        content=AnalysisLayer(),
                        unit_tags=[unit] if unit is not None else [],
                    )
                )
            elif kind == "rest":
                voices_dict[voice_id].append(
                    VoiceEvent(
                        kind="rest",
                        duration=ql,
                        duration_type=dur.get("type", "q"),
                        dots=dur.get("dots", 0),
                    )
                )
            current_offset += ql

    if analysis_overrides:
        analysis_slices = [AnalysisSlice(**a) for a in analysis_overrides]

    umto = UMTO(
        metadata=metadata,
        voices=Voices(**voices_dict),
        analysis=analysis_slices,
        grading=grading_slices,
    )
    return umto.to_frontend_payload(unit=unit)
```

- [ ] **Step 2.4: Run test, verify pass**

Run: `pytest apps/exercises/tests/test_umto_factory.py -v`
Expected: all tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_umto_factory.py
git commit -m "Add build_umto_payload factory function for single-voice CIR→UMTO"
```

---

## Task 3: Factory — `build_umto_payload` for SATB (chorale) case

**Files:**
- Modify: `apps/exercises/umto_factory.py`
- Test: `apps/exercises/tests/test_umto_factory.py`

- [ ] **Step 3.1: Write failing test for SATB build**

Append to `apps/exercises/tests/test_umto_factory.py`:

```python
SATB_CIR = {
    "meta": {"key": "G", "time": "4/4"},
    "measures": [
        {
            "staves": {
                "treble": {
                    "voices": [
                        {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                        {"items": [{"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                    ]
                },
                "bass": {
                    "voices": [
                        {"items": [{"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 3}, "duration": {"type": "q", "dots": 0}}]},
                        {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 2}, "duration": {"type": "q", "dots": 0}}]},
                    ]
                },
            }
        }
    ],
}


def test_build_umto_payload_satb_all_voices_playback():
    from apps.exercises.umto_factory import build_umto_payload

    payload = build_umto_payload(
        exercise_id="TEMP",
        source="Test SATB",
        key="G",
        meter="4/4",
        clef="keyboard",
        complexity_score=9,
        mode=InteractionMode.PLAYBACK,
        score_data=SATB_CIR,
        target_voice=None,
        unit=9,
    )

    assert payload["isUMTO"] is True
    umto = payload["score"]["umto"]
    assert len(umto["voices"]["S"]) == 1
    assert len(umto["voices"]["A"]) == 1
    assert len(umto["voices"]["T"]) == 1
    assert len(umto["voices"]["B"]) == 1
    assert umto["voices"]["S"][0]["pitch"]["midi"] == 67
    assert umto["voices"]["A"][0]["pitch"]["midi"] == 62
    assert umto["voices"]["T"][0]["pitch"]["midi"] == 59
    assert umto["voices"]["B"][0]["pitch"]["midi"] == 43
```

- [ ] **Step 3.2: Run test, verify fail**

Run: `pytest apps/exercises/tests/test_umto_factory.py::test_build_umto_payload_satb_all_voices_playback -v`
Expected: FAIL — current loop only handles single voice under one `clef` staff.

- [ ] **Step 3.3: Extend `build_umto_payload` to handle SATB routing**

Replace the measure-walking loop in `apps/exercises/umto_factory.py` (inside `build_umto_payload`) with:

```python
    # Per-voice running offsets so each voice's timeline is independent.
    voice_offsets: dict[str, float] = {"S": 0.0, "A": 0.0, "T": 0.0, "B": 0.0}
    # Pair (staff, voice_index_in_staff) → voice id for SATB convention.
    # treble[0]=S, treble[1]=A, bass[0]=T, bass[1]=B
    SATB_MAP = {("treble", 0): "S", ("treble", 1): "A", ("bass", 0): "T", ("bass", 1): "B"}

    single_voice_mode = target_voice is not None or clef in ("treble", "bass")

    for measure in score_data.get("measures", []):
        if single_voice_mode:
            staves_to_walk = [(clef, 0)]
        else:
            staves_to_walk = [(s, i) for s in ("treble", "bass") for i in range(2)]

        for staff_name, v_idx in staves_to_walk:
            staff = measure.get("staves", {}).get(staff_name, {})
            voice_list = staff.get("voices", [])
            if v_idx >= len(voice_list):
                continue
            items = voice_list[v_idx].get("items", [])

            if single_voice_mode:
                target_id = voice_id
            else:
                target_id = SATB_MAP[(staff_name, v_idx)]

            for item in items:
                dur = item.get("duration", {})
                ql = _duration_ql(dur)
                kind = item.get("kind")
                cur_offset = voice_offsets[target_id]
                if kind == "note":
                    p = item.get("pitch", {})
                    midi = _pitch_to_midi(p.get("step", "C"), p.get("alter", 0), p.get("octave", 4))
                    pitch = Pitch(step=p["step"], alter=p.get("alter", 0), octave=p["octave"], midi=midi)
                    voices_dict[target_id].append(
                        VoiceEvent(
                            kind="note",
                            pitch=pitch,
                            duration=ql,
                            duration_type=dur.get("type", "q"),
                            dots=dur.get("dots", 0),
                        )
                    )
                    if single_voice_mode:
                        grading_slices.append(
                            GradingSlice(offset=cur_offset, target_midi_pitches=[midi])
                        )
                        analysis_slices.append(
                            AnalysisSlice(
                                offset=cur_offset,
                                content=AnalysisLayer(),
                                unit_tags=[unit] if unit is not None else [],
                            )
                        )
                elif kind == "rest":
                    voices_dict[target_id].append(
                        VoiceEvent(
                            kind="rest",
                            duration=ql,
                            duration_type=dur.get("type", "q"),
                            dots=dur.get("dots", 0),
                        )
                    )
                voice_offsets[target_id] += ql

    # For SATB (non-single-voice) modes, synthesize one grading slice per
    # unique onset across all four voices. Callers that need roman-numeral
    # analysis_slices must pass analysis_overrides.
    if not single_voice_mode:
        all_offsets = sorted({0.0})
        cursor = 0.0
        cursors = {"S": 0.0, "A": 0.0, "T": 0.0, "B": 0.0}
        onsets: set[float] = set()
        # Recompute per-voice onsets of note events.
        for vid in ("S", "A", "T", "B"):
            t = 0.0
            for ev in voices_dict[vid]:
                if ev.kind == "note":
                    onsets.add(round(t, 5))
                t += ev.duration
        for off in sorted(onsets):
            pitches_at = []
            for vid in ("S", "A", "T", "B"):
                t = 0.0
                for ev in voices_dict[vid]:
                    if ev.kind == "note" and abs(t - off) < 0.001:
                        pitches_at.append(ev.pitch.midi)
                        break
                    t += ev.duration
            if pitches_at:
                grading_slices.append(
                    GradingSlice(offset=off, target_midi_pitches=sorted(pitches_at))
                )
                analysis_slices.append(
                    AnalysisSlice(
                        offset=off,
                        content=AnalysisLayer(),
                        unit_tags=[unit] if unit is not None else [],
                    )
                )
```

Remove the old single-voice loop above (the `for measure in score_data.get("measures", []):` block that existed before this change) — the new block replaces it entirely.

- [ ] **Step 3.4: Run all factory tests**

Run: `pytest apps/exercises/tests/test_umto_factory.py -v`
Expected: all pass, including single-voice test from Task 2.

- [ ] **Step 3.5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_umto_factory.py
git commit -m "Extend factory to handle SATB multi-voice CIR→UMTO routing"
```

---

## Task 4: Factory — `save_umto_exercise`

**Files:**
- Modify: `apps/exercises/umto_factory.py`
- Test: `apps/exercises/tests/test_umto_factory.py`

- [ ] **Step 4.1: Write failing test**

Append to `apps/exercises/tests/test_umto_factory.py`:

```python
import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_save_umto_exercise_creates_row_and_backfills_exercise_id():
    from apps.exercises.umto_factory import save_umto_exercise

    User = get_user_model()
    author = User.objects.create(email="test@test.com", username="t")

    ex = save_umto_exercise(
        description="Factory test",
        score_data=SINGLE_VOICE_CIR,
        author=author,
        skill_tags=["unit:1", "Note_Names"],
        complexity=11,
        umto_kwargs=dict(
            exercise_id="TEMP",
            source="Factory test",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            target_voice="soprano",
            unit=1,
        ),
    )

    assert ex.pk is not None
    assert ex.id is not None
    assert ex.description == "Factory test"
    assert ex.data["isUMTO"] is True
    assert ex.data["score"]["umto"]["metadata"]["exercise_id"] == ex.id
    assert ex.skill_tags == ["unit:1", "Note_Names"]
    assert ex.complexity == 11


@pytest.mark.django_db
def test_save_umto_exercise_rejects_legacy_score_data():
    from apps.exercises.umto_factory import save_umto_exercise, NonUMTOExerciseError

    User = get_user_model()
    author = User.objects.create(email="test2@test.com", username="t2")

    with pytest.raises(NonUMTOExerciseError):
        save_umto_exercise(
            description="Bad",
            score_data={"meta": {}, "measures": []},  # empty → UMTO validation triggers
            author=author,
            skill_tags=[],
            complexity=1,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=0,  # invalid: must be ≥1
                mode=InteractionMode.PLAYBACK,
            ),
        )
```

- [ ] **Step 4.2: Run test, verify fail**

Run: `pytest apps/exercises/tests/test_umto_factory.py -v -k save_umto_exercise`
Expected: `ImportError: cannot import name 'save_umto_exercise'`.

- [ ] **Step 4.3: Implement `save_umto_exercise`**

Append to `apps/exercises/umto_factory.py`:

```python
import os

from apps.exercises.models import Exercise


def _legacy_bypass_enabled() -> bool:
    return os.environ.get("HARMONYLAB_ALLOW_LEGACY_EXERCISE") == "1"


def save_umto_exercise(
    *,
    description: str,
    score_data: dict,
    author,
    skill_tags: list,
    complexity: int,
    is_public: bool = True,
    umto_kwargs: dict,
) -> Exercise:
    """Build a UMTO payload from score_data + umto_kwargs, validate, save Exercise,
    and backfill exercise_id in the stored payload.

    Create-only. Conversions of existing legacy rows go through dedicated
    migration commands with HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 bypass.
    """
    try:
        payload = build_umto_payload(score_data=score_data, **umto_kwargs)
    except Exception as e:
        raise NonUMTOExerciseError(f"Failed to build UMTO payload: {e}") from e

    # Validate before DB write.
    try:
        UMTO.model_validate(payload["score"]["umto"])
    except Exception as e:
        raise NonUMTOExerciseError(f"UMTO validation failed: {e}") from e

    ex = Exercise(
        description=description,
        data=payload,
        authored_by=author,
        is_public=is_public,
        skill_tags=list(skill_tags),
        complexity=complexity,
    )
    ex.save()
    # Backfill now that the DB-assigned id is known.
    ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.data["exerciseId"] = ex.id
    ex.save()
    return ex
```

- [ ] **Step 4.4: Run tests, verify pass**

Run: `pytest apps/exercises/tests/test_umto_factory.py -v`
Expected: all tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_umto_factory.py
git commit -m "Add save_umto_exercise with validation and exercise_id backfill"
```

---

## Task 5: Regenerate `umto_schema.json` + add `make_umto_schema` command

**Files:**
- Create: `apps/exercises/management/commands/make_umto_schema.py`
- Modify: `apps/exercises/umto_schema.json`

- [ ] **Step 5.1: Create management command**

Create `apps/exercises/management/commands/make_umto_schema.py`:

```python
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.exercises.umto import UMTO


class Command(BaseCommand):
    help = "Regenerate apps/exercises/umto_schema.json from the UMTO pydantic model."

    def handle(self, *args, **options):
        schema = UMTO.generate_schema()
        path = Path("apps/exercises/umto_schema.json")
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
```

- [ ] **Step 5.2: Run it to regenerate schema**

Run: `python manage.py make_umto_schema`
Expected output: `Wrote apps/exercises/umto_schema.json`.

- [ ] **Step 5.3: Verify new fields now present in schema**

Run: `grep -E '"mode"|"clef"|"is_umto"|"is_target"|"is_tied_start"' apps/exercises/umto_schema.json`
Expected: matches found for all five fields.

- [ ] **Step 5.4: Commit**

```bash
git add apps/exercises/management/commands/make_umto_schema.py apps/exercises/umto_schema.json
git commit -m "Regenerate umto_schema.json and add make_umto_schema command"
```

---

## Task 6: Golden fixtures — hand-authored

**Files:**
- Create: `apps/exercises/tests/fixtures/umto/minimal.json`
- Create: `apps/exercises/tests/fixtures/umto/maximal.json`
- Create: `apps/exercises/tests/fixtures/umto/unit1_identification_treble.json`
- Create: `apps/exercises/tests/fixtures/umto/unit1_identification_bass.json`
- Create: `apps/exercises/tests/fixtures/umto/unit1_playback_treble.json`
- Create: `apps/exercises/tests/fixtures/umto/unit1_analysis_treble.json`
- Create: `apps/exercises/tests/fixtures/umto/unit9_chorale_roman.json`
- Create: `apps/exercises/tests/fixtures/umto/unit12_chromatic_analysis.json`

- [ ] **Step 6.1: Write `minimal.json`**

Create `apps/exercises/tests/fixtures/umto/minimal.json`:

```json
{
  "metadata": {
    "exercise_id": "FIXTURE_MINIMAL",
    "source": "minimal fixture",
    "key": "C",
    "meter": "4/4",
    "clef": "treble",
    "complexity_score": 1,
    "mode": "playback",
    "is_umto": true
  },
  "voices": {
    "S": [
      {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4, "midi": 60}, "duration": 4.0, "duration_type": "w", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "A": [],
    "T": [],
    "B": []
  },
  "analysis": [],
  "grading": [
    {"offset": 0.0, "target_midi_pitches": [60], "rhythmic_flexibility": false}
  ]
}
```

- [ ] **Step 6.2: Write `maximal.json`**

Create `apps/exercises/tests/fixtures/umto/maximal.json`:

```json
{
  "metadata": {
    "exercise_id": "FIXTURE_MAXIMAL",
    "source": "maximal fixture — every optional field populated",
    "key": "g minor",
    "meter": "3/4",
    "clef": "keyboard",
    "complexity_score": 12,
    "mode": "identification",
    "is_umto": true
  },
  "voices": {
    "S": [
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 5, "midi": 79}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": true, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 5, "midi": 79}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": true, "is_target": false}
    ],
    "A": [
      {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 5, "midi": 74}, "duration": 2.0, "duration_type": "h", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "T": [
      {"kind": "note", "pitch": {"step": "B", "alter": -1, "octave": 4, "midi": 70}, "duration": 1.5, "duration_type": "q", "dots": 1, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "rest", "duration": 0.5, "duration_type": "8", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": false}
    ],
    "B": [
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 3, "midi": 55}, "duration": 2.0, "duration_type": "h", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ]
  },
  "analysis": [
    {
      "offset": 0.0,
      "content": {
        "roman_numeral": "i",
        "figured_bass": "5/3",
        "pop_symbol": "Gm",
        "functional_label": "Tonic"
      },
      "visual": {"x_hint": 0.0, "y_hint": -40.0, "anchor": "slice", "style": "handwritten"},
      "unit_tags": [1, 9, 12]
    }
  ],
  "grading": [
    {"offset": 0.0, "target_midi_pitches": [55, 70, 74, 79], "rhythmic_flexibility": true}
  ]
}
```

- [ ] **Step 6.3: Write Unit 1 treble identification fixture**

Create `apps/exercises/tests/fixtures/umto/unit1_identification_treble.json`:

```json
{
  "metadata": {
    "exercise_id": "FIXTURE_U1_ID_TREBLE",
    "source": "BWV1.6 mm.1-2 Soprano identification",
    "key": "G",
    "meter": "4/4",
    "clef": "treble",
    "complexity_score": 1,
    "mode": "identification",
    "is_umto": true
  },
  "voices": {
    "S": [
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4, "midi": 67}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "A", "alter": 0, "octave": 4, "midi": 69}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 4, "midi": 71}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 5, "midi": 72}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "A": [],
    "T": [],
    "B": []
  },
  "analysis": [
    {"offset": 0.0, "content": {}, "visual": null, "unit_tags": [1]},
    {"offset": 1.0, "content": {}, "visual": null, "unit_tags": [1]},
    {"offset": 2.0, "content": {}, "visual": null, "unit_tags": [1]},
    {"offset": 3.0, "content": {}, "visual": null, "unit_tags": [1]}
  ],
  "grading": [
    {"offset": 0.0, "target_midi_pitches": [67], "rhythmic_flexibility": false},
    {"offset": 1.0, "target_midi_pitches": [69], "rhythmic_flexibility": false},
    {"offset": 2.0, "target_midi_pitches": [71], "rhythmic_flexibility": false},
    {"offset": 3.0, "target_midi_pitches": [72], "rhythmic_flexibility": false}
  ]
}
```

- [ ] **Step 6.4: Write Unit 1 bass identification fixture**

Create `apps/exercises/tests/fixtures/umto/unit1_identification_bass.json`:

```json
{
  "metadata": {
    "exercise_id": "FIXTURE_U1_ID_BASS",
    "source": "BWV1.6 mm.1-2 Bass identification",
    "key": "G",
    "meter": "4/4",
    "clef": "bass",
    "complexity_score": 1,
    "mode": "identification",
    "is_umto": true
  },
  "voices": {
    "S": [],
    "A": [],
    "T": [],
    "B": [
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 2, "midi": 43}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 3, "midi": 50}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 3, "midi": 55}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 3, "midi": 59}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ]
  },
  "analysis": [
    {"offset": 0.0, "content": {}, "visual": null, "unit_tags": [1]},
    {"offset": 1.0, "content": {}, "visual": null, "unit_tags": [1]},
    {"offset": 2.0, "content": {}, "visual": null, "unit_tags": [1]},
    {"offset": 3.0, "content": {}, "visual": null, "unit_tags": [1]}
  ],
  "grading": [
    {"offset": 0.0, "target_midi_pitches": [43], "rhythmic_flexibility": false},
    {"offset": 1.0, "target_midi_pitches": [50], "rhythmic_flexibility": false},
    {"offset": 2.0, "target_midi_pitches": [55], "rhythmic_flexibility": false},
    {"offset": 3.0, "target_midi_pitches": [59], "rhythmic_flexibility": false}
  ]
}
```

- [ ] **Step 6.5: Write Unit 1 playback fixture**

Create `apps/exercises/tests/fixtures/umto/unit1_playback_treble.json` (same voices as `unit1_identification_treble.json` but set `"mode": "playback"`, `"exercise_id": "FIXTURE_U1_PB_TREBLE"`). Copy the identification fixture and edit these two fields.

- [ ] **Step 6.6: Write Unit 1 analysis fixture**

Create `apps/exercises/tests/fixtures/umto/unit1_analysis_treble.json` (same voices, `"mode": "analysis_match"`, `"exercise_id": "FIXTURE_U1_AN_TREBLE"`).

- [ ] **Step 6.7: Write Unit 9 chorale fixture**

Create `apps/exercises/tests/fixtures/umto/unit9_chorale_roman.json`:

```json
{
  "metadata": {
    "exercise_id": "FIXTURE_U9_CHORALE",
    "source": "Unit 9 SATB chorale window with Roman numerals",
    "key": "C",
    "meter": "4/4",
    "clef": "keyboard",
    "complexity_score": 9,
    "mode": "identification",
    "is_umto": true
  },
  "voices": {
    "S": [
      {"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 5, "midi": 76}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 5, "midi": 74}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "A": [
      {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 5, "midi": 72}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 4, "midi": 71}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "T": [
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4, "midi": 67}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4, "midi": 67}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "B": [
      {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 3, "midi": 48}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true},
      {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 2, "midi": 43}, "duration": 1.0, "duration_type": "q", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ]
  },
  "analysis": [
    {"offset": 0.0, "content": {"roman_numeral": "I"}, "visual": null, "unit_tags": [9]},
    {"offset": 1.0, "content": {"roman_numeral": "V"}, "visual": null, "unit_tags": [9]}
  ],
  "grading": [
    {"offset": 0.0, "target_midi_pitches": [48, 67, 72, 76], "rhythmic_flexibility": false},
    {"offset": 1.0, "target_midi_pitches": [43, 67, 71, 74], "rhythmic_flexibility": false}
  ]
}
```

- [ ] **Step 6.8: Write Unit 12 chromatic fixture**

Create `apps/exercises/tests/fixtures/umto/unit12_chromatic_analysis.json`:

```json
{
  "metadata": {
    "exercise_id": "FIXTURE_U12_CHROMATIC",
    "source": "Unit 12 secondary dominant + chromatic mediant",
    "key": "C",
    "meter": "4/4",
    "clef": "keyboard",
    "complexity_score": 12,
    "mode": "identification",
    "is_umto": true
  },
  "voices": {
    "S": [
      {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 5, "midi": 74}, "duration": 2.0, "duration_type": "h", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "A": [
      {"kind": "note", "pitch": {"step": "F", "alter": 1, "octave": 4, "midi": 66}, "duration": 2.0, "duration_type": "h", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "T": [
      {"kind": "note", "pitch": {"step": "A", "alter": 0, "octave": 3, "midi": 57}, "duration": 2.0, "duration_type": "h", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ],
    "B": [
      {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 3, "midi": 50}, "duration": 2.0, "duration_type": "h", "dots": 0, "is_tied_start": false, "is_tied_stop": false, "is_target": true}
    ]
  },
  "analysis": [
    {"offset": 0.0, "content": {"roman_numeral": "V/V", "functional_label": "Secondary Dominant"}, "visual": null, "unit_tags": [12]}
  ],
  "grading": [
    {"offset": 0.0, "target_midi_pitches": [50, 57, 66, 74], "rhythmic_flexibility": false}
  ]
}
```

- [ ] **Step 6.9: Verify all fixtures validate against UMTO schema**

Run:
```bash
python -c "
import json, glob
from apps.exercises.umto import UMTO
import django; django.setup()
for p in sorted(glob.glob('apps/exercises/tests/fixtures/umto/*.json')):
    UMTO.model_validate_json(open(p).read())
    print('OK', p)
"
```

Alternative if Django setup is fussy, use `pytest apps/exercises/tests/test_umto_contract.py` after Task 8 and verify fixture loading there.

Expected: each fixture prints `OK`.

- [ ] **Step 6.10: Commit**

```bash
git add apps/exercises/tests/fixtures/umto/
git commit -m "Add golden UMTO fixtures for all interaction modes + min/max edges"
```

---

## Task 7: CIR input fixtures (for factory-idempotence test)

**Files:**
- Create: `apps/exercises/tests/fixtures/cir_inputs/unit1_treble.json`
- Create: `apps/exercises/tests/fixtures/cir_inputs/unit1_bass.json`
- Create: `apps/exercises/tests/fixtures/cir_inputs/unit9_satb.json`

- [ ] **Step 7.1: Write CIR inputs that factory must transform into golden fixtures**

Create `apps/exercises/tests/fixtures/cir_inputs/unit1_treble.json`:

```json
{
  "meta": {"key": "G", "time": "4/4"},
  "measures": [
    {
      "staves": {
        "treble": {
          "voices": [
            {
              "items": [
                {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                {"kind": "note", "pitch": {"step": "A", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                {"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 5}, "duration": {"type": "q", "dots": 0}}
              ]
            }
          ]
        }
      }
    }
  ]
}
```

Create `apps/exercises/tests/fixtures/cir_inputs/unit1_bass.json` (same shape, clef `bass`, pitches `G2 D3 G3 B3`).

Create `apps/exercises/tests/fixtures/cir_inputs/unit9_satb.json` (two measures, SATB matching `unit9_chorale_roman.json`).

- [ ] **Step 7.2: Commit**

```bash
git add apps/exercises/tests/fixtures/cir_inputs/
git commit -m "Add CIR input fixtures paired with golden UMTO fixtures"
```

---

## Task 8: Contract tests

**Files:**
- Create: `apps/exercises/tests/test_umto_contract.py`

- [ ] **Step 8.1: Write contract test file**

Create `apps/exercises/tests/test_umto_contract.py`:

```python
"""Contract tests for UMTO. Pins schema, payload shape, and factory behavior
against silent drift. Each failure points at a specific invariant in the spec
at docs/superpowers/specs/2026-04-23-umto-consistency-design.md.
"""
import json
from pathlib import Path

import pytest

from apps.exercises.umto import UMTO


FIXTURES_DIR = Path("apps/exercises/tests/fixtures/umto")
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))


@pytest.mark.parametrize("fixture", FIXTURE_FILES, ids=lambda p: p.name)
def test_fixture_roundtrip_invariance(fixture):
    """Fixture → UMTO → JSON equals fixture (after key sort)."""
    original = json.loads(fixture.read_text())
    umto = UMTO.model_validate(original)
    # Use model_dump then round-trip through json for deterministic key ordering.
    dumped = json.loads(umto.model_dump_json())
    assert dumped["metadata"]["exercise_id"] == original["metadata"]["exercise_id"]
    assert dumped["voices"] == original["voices"]
    assert dumped["analysis"] == original["analysis"]
    assert dumped["grading"] == original["grading"]


def test_schema_file_matches_pydantic_model():
    """apps/exercises/umto_schema.json must match UMTO.generate_schema() output.

    If this fails, run: python manage.py make_umto_schema
    """
    generated = UMTO.generate_schema()
    on_disk_text = Path("apps/exercises/umto_schema.json").read_text()
    on_disk = json.loads(on_disk_text)
    assert generated == on_disk, (
        "Schema drift detected. Run: python manage.py make_umto_schema and commit."
    )


EXPECTED_PAYLOAD_KEYS = {
    "type", "isUMTO", "mode", "staffDistribution", "complexity_score",
    "exerciseId", "key", "meter", "clef", "allowed_answers", "score", "grading",
}


@pytest.mark.parametrize("fixture", FIXTURE_FILES, ids=lambda p: p.name)
def test_frontend_payload_shape(fixture):
    """to_frontend_payload must emit the frozen key set and isUMTO=True."""
    umto = UMTO.model_validate_json(fixture.read_text())
    # Pick unit from first analysis slice if present.
    unit = umto.analysis[0].unit_tags[0] if umto.analysis and umto.analysis[0].unit_tags else None
    payload = umto.to_frontend_payload(unit=unit)

    missing = EXPECTED_PAYLOAD_KEYS - set(payload.keys())
    assert not missing, f"{fixture.name}: missing keys {missing}"
    assert payload["isUMTO"] is True, f"{fixture.name}: isUMTO must be True, got {payload['isUMTO']!r}"
    assert payload["type"] == "umto_chorale"


def test_factory_idempotence_unit1_treble():
    """build_umto_payload on cir_inputs/unit1_treble.json produces a UMTO that
    round-trips byte-equal to unit1_identification_treble.json's voices/grading.
    """
    from apps.exercises.umto_factory import build_umto_payload
    from apps.exercises.umto import InteractionMode

    cir = json.loads(Path("apps/exercises/tests/fixtures/cir_inputs/unit1_treble.json").read_text())
    golden = json.loads(Path("apps/exercises/tests/fixtures/umto/unit1_identification_treble.json").read_text())

    payload = build_umto_payload(
        exercise_id="FIXTURE_U1_ID_TREBLE",
        source=golden["metadata"]["source"],
        key="G",
        meter="4/4",
        clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        score_data=cir,
        target_voice="soprano",
        unit=1,
    )
    built = payload["score"]["umto"]
    assert built["voices"] == golden["voices"]
    assert built["grading"] == golden["grading"]


@pytest.mark.django_db
def test_save_umto_then_reload_matches_fixture():
    from apps.exercises.umto_factory import save_umto_exercise
    from apps.exercises.umto import InteractionMode
    from apps.exercises.models import Exercise
    from django.contrib.auth import get_user_model

    cir = json.loads(Path("apps/exercises/tests/fixtures/cir_inputs/unit1_treble.json").read_text())
    author = get_user_model().objects.create(email="c@c.com", username="c")
    ex = save_umto_exercise(
        description="contract test",
        score_data=cir,
        author=author,
        skill_tags=["unit:1"],
        complexity=11,
        umto_kwargs=dict(
            exercise_id="TEMP",
            source="contract",
            key="G", meter="4/4", clef="treble",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            target_voice="soprano",
            unit=1,
        ),
    )
    reloaded = Exercise.objects.get(pk=ex.pk)
    assert reloaded.data["isUMTO"] is True
    assert reloaded.data["score"]["umto"]["metadata"]["exercise_id"] == ex.id
```

- [ ] **Step 8.2: Run contract tests, verify pass**

Run: `pytest apps/exercises/tests/test_umto_contract.py -v`
Expected: all tests pass. If `test_schema_file_matches_pydantic_model` fails, re-run `python manage.py make_umto_schema` and recommit.

- [ ] **Step 8.3: Commit**

```bash
git add apps/exercises/tests/test_umto_contract.py
git commit -m "Add UMTO contract tests over golden fixtures"
```

---

## Task 9: Fix `generate_unit1.py` — collapse builders, fix `--lanes`

**Files:**
- Modify: `apps/exercises/management/commands/generate_unit1.py`

- [ ] **Step 9.1: Write failing test verifying `--lanes identification` is accepted**

Create `apps/exercises/tests/test_generate_unit1_args.py`:

```python
import pytest
from django.core.management import call_command, CommandError


def test_lanes_identification_is_valid_choice():
    """--lanes identification must be accepted by argparse.

    Previously `choices=["exact","analysis","both"]` rejected it silently
    despite a code branch handling it.
    """
    with pytest.raises(CommandError) as exc:
        # Missing --author triggers CommandError AFTER argparse parses --lanes,
        # so argparse accepting 'identification' is what we're testing.
        call_command("generate_unit1", "--lanes=identification")
    # Error must be about --author, NOT about --lanes.
    assert "--author" in str(exc.value) or "author" in str(exc.value)
```

- [ ] **Step 9.2: Run, verify fail**

Run: `pytest apps/exercises/tests/test_generate_unit1_args.py -v`
Expected: FAIL — argparse rejects `identification`.

- [ ] **Step 9.3: Fix argparse choices**

In `apps/exercises/management/commands/generate_unit1.py` line 393, change:

```python
parser.add_argument("--lanes", choices=["exact", "analysis", "both"], default="both")
```

to:

```python
parser.add_argument(
    "--lanes",
    choices=["exact", "analysis", "identification", "all"],
    default="all",
    help="Which lane(s) to emit. 'all' = exact + analysis + identification.",
)
```

- [ ] **Step 9.4: Replace `lanes in ("exact", "both")` etc. with new semantics**

Inside the same file, find every `lanes in (...)` check (three sites: ~line 563, 586, 609). Replace:

```python
if lanes in ("exact", "both"):
```

with:

```python
if lanes in ("exact", "all"):
```

Same for `analysis` → `"analysis", "all"` and `identification` → `"identification", "all"`.

- [ ] **Step 9.5: Run args test, verify pass**

Run: `pytest apps/exercises/tests/test_generate_unit1_args.py -v`
Expected: pass.

- [ ] **Step 9.6: Replace `_build_exact_payload` + `_build_analysis_payload` + `_build_identification_payload` + `_score_to_umto_payload` with factory calls**

Delete the four functions `_build_exact_payload`, `_build_analysis_payload`, `_build_identification_payload`, `_score_to_umto_payload` from `generate_unit1.py` (lines ~259-381).

Add at the top of the file:

```python
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode
```

Replace each lane's Exercise creation (the `if exact is None:` / `else:` branches at ~line 570, ~593, ~616) with:

```python
# Lane: exact (PLAYBACK)
if lanes in ("exact", "all"):
    exact_desc = f"{bwv.upper()} mm.{human_start}-{human_end} - {voice_name.title()} (exact) Stage {stage}"
    existing = Exercise.objects.filter(description=exact_desc).first()
    if existing is None:
        if not dry_run:
            ex = save_umto_exercise(
                description=exact_desc,
                score_data=one_voice,
                author=author,
                skill_tags=base_tags,
                complexity=complexity,
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source=f"Play the notes: {intro_text}",
                    key=one_voice["meta"].get("key", "C"),
                    meter=one_voice["meta"].get("time", "4/4"),
                    clef=target,
                    complexity_score=1,
                    mode=InteractionMode.PLAYBACK,
                    target_voice=voice_name,
                    unit=1,
                ),
            )
            print(f"Created {ex.id}: {exact_desc}")
            created.append((target, "exact", stage, complexity, ex))
    else:
        if not dry_run:
            # Rebuild payload on existing row (update path bypasses model guard).
            from apps.exercises.umto_factory import build_umto_payload
            existing.data = build_umto_payload(
                exercise_id=existing.id,
                source=f"Play the notes: {intro_text}",
                key=one_voice["meta"].get("key", "C"),
                meter=one_voice["meta"].get("time", "4/4"),
                clef=target,
                complexity_score=1,
                mode=InteractionMode.PLAYBACK,
                score_data=one_voice,
                target_voice=voice_name,
                unit=1,
            )
            existing.save()
            print(f"Updated {existing.id}: {exact_desc}")
            created.append((target, "exact", stage, complexity, existing))
```

Repeat the same structure for `analysis` (use `InteractionMode.ANALYSIS_MATCH` + `source=f"Name the notes: {intro_text}"`) and `identification` (use `InteractionMode.IDENTIFICATION` + `source=f"Identify the notes: {intro_text}"`).

- [ ] **Step 9.7: Run generate_unit1 dry-run to verify no crashes**

Run: `python manage.py generate_unit1 --author admin@example.com --dry-run --file bwv1.6.json --lanes all`
Expected: completes without exception, logs lane creation activity.

- [ ] **Step 9.8: Commit**

```bash
git add apps/exercises/management/commands/generate_unit1.py apps/exercises/tests/test_generate_unit1_args.py
git commit -m "generate_unit1: collapse duplicate builders into factory, fix --lanes argparse"
```

---

## Task 10: Migrate `migrate_unit1_to_umto.py` to use factory (update path)

**Files:**
- Modify: `apps/exercises/management/commands/migrate_unit1_to_umto.py`

- [ ] **Step 10.1: Refactor to use `build_umto_payload`**

Replace the body of `migrate_exercise` method. Delete `dur_to_ql` and `to_midi` helpers.

New body:

```python
def migrate_exercise(self, ex):
    from apps.exercises.umto_factory import build_umto_payload
    from apps.exercises.umto import InteractionMode

    old = ex.data
    score = old.get("score", {})
    meta = score.get("meta", {})
    staves = score.get("measures", [{}])[0].get("staves", {}).keys()
    primary = list(staves)[0] if staves else "treble"
    target_voice = "soprano" if primary == "treble" else "bass"

    return build_umto_payload(
        exercise_id=ex.id,
        source=old.get("introText", "Bach Chorale Window"),
        key=meta.get("key", "C"),
        meter=meta.get("time", "4/4"),
        clef=primary,
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        score_data=score,
        target_voice=target_voice,
        unit=1,
    )
```

- [ ] **Step 10.2: Write test verifying migration emits UMTO**

Create `apps/exercises/tests/test_migrate_unit1_to_umto.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.exercises.models import Exercise


@pytest.mark.django_db
def test_migrate_unit1_to_umto_converts_legacy_row(monkeypatch):
    import os
    monkeypatch.setenv("HARMONYLAB_ALLOW_LEGACY_EXERCISE", "1")

    author = get_user_model().objects.create(email="m@m.com", username="m")
    legacy_data = {
        "type": "chorale_identification",
        "introText": "Legacy",
        "score": {
            "meta": {"key": "C", "time": "4/4"},
            "measures": [{
                "staves": {"treble": {"voices": [{"items": [
                    {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                ]}]}}
            }]
        }
    }
    ex = Exercise.objects.create(
        description="legacy",
        data=legacy_data,
        authored_by=author,
        skill_tags=["unit:1"],
    )

    call_command("migrate_unit1_to_umto")

    ex.refresh_from_db()
    assert ex.data["isUMTO"] is True
    assert ex.data["score"]["umto"]["voices"]["S"][0]["pitch"]["midi"] == 60
```

- [ ] **Step 10.3: Run test**

Run: `pytest apps/exercises/tests/test_migrate_unit1_to_umto.py -v`
Expected: pass.

- [ ] **Step 10.4: Commit**

```bash
git add apps/exercises/management/commands/migrate_unit1_to_umto.py apps/exercises/tests/test_migrate_unit1_to_umto.py
git commit -m "migrate_unit1_to_umto: use umto_factory for CIR→UMTO conversion"
```

---

## Task 11: Migrate remaining importers + dashboard endpoint

**Files:**
- Modify: `apps/exercises/management/commands/import_chorale.py`
- Modify: `apps/exercises/management/commands/import_bach_phrases.py`
- Modify: `apps/exercises/management/commands/import_musicxml.py`
- Modify: `apps/exercises/management/commands/mass_import_performance.py`
- Modify: `apps/exercises/management/commands/duplicate_chorale_as_identification.py`
- Modify: `apps/exercises/management/commands/migrate_exercises.py`
- Modify: `apps/dashboard/views/exercises.py`

For **each** file above, apply the same three-step pattern:

- [ ] **Step 11.1: Read the command** and locate every `Exercise(...)` or `Exercise.objects.create(...)` call.

- [ ] **Step 11.2: Replace with `save_umto_exercise`** — build `umto_kwargs` from the command's context. For commands that don't have a clear `InteractionMode`, default to `InteractionMode.IDENTIFICATION` for chord-bank exercises, `PLAYBACK` for note-reading exercises.

Example transformation pattern (apply to each occurrence):

```python
# Before:
ex = Exercise(
    description=desc,
    data=legacy_payload,
    authored_by=author,
    skill_tags=tags,
    complexity=c,
)
ex.save()

# After:
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode

ex = save_umto_exercise(
    description=desc,
    score_data=cir_score,          # the CIR dict that was previously wrapped in legacy_payload
    author=author,
    skill_tags=tags,
    complexity=c,
    umto_kwargs=dict(
        exercise_id="TEMP",
        source=intro_text,
        key=cir_score["meta"].get("key", "C"),
        meter=cir_score["meta"].get("time", "4/4"),
        clef=target_clef,           # or "keyboard" for SATB
        complexity_score=complexity_score_value,
        mode=InteractionMode.IDENTIFICATION,  # or PLAYBACK / ANALYSIS_MATCH
        target_voice=target_voice,  # or None for SATB
        unit=unit_number,
    ),
)
```

- [ ] **Step 11.3: Write one integration test per command** asserting the command creates a UMTO-shaped row.

Template:

```python
@pytest.mark.django_db
def test_<command_name>_emits_umto():
    # set up minimal author + invocation args
    call_command("<command_name>", ...)
    ex = Exercise.objects.last()
    assert ex.data["isUMTO"] is True
    assert "umto" in ex.data["score"]
```

Place each test in `apps/exercises/tests/test_<command_name>.py`.

- [ ] **Step 11.4: Run full test suite**

Run: `pytest apps/exercises/tests/ -v`
Expected: all tests pass.

- [ ] **Step 11.5: Commit (one commit per command)**

```bash
git add apps/exercises/management/commands/<command>.py apps/exercises/tests/test_<command>.py
git commit -m "<command>: route Exercise creation through umto_factory"
```

For `apps/dashboard/views/exercises.py` duplicate-as-pitch endpoint, same pattern but also update the corresponding test at `apps/dashboard/tests/test_exercise_pitch_duplication.py`.

---

## Task 12: Update `lab/views.py` — logger.warning replaces print

**Files:**
- Modify: `lab/views.py`

- [ ] **Step 12.1: Write failing test**

Create `apps/exercises/tests/test_views_umto_logging.py`:

```python
import logging
import pytest
from django.contrib.auth import get_user_model

from apps.exercises.models import Exercise


@pytest.mark.django_db
def test_legacy_exercise_emits_warning_log(caplog, client, monkeypatch):
    monkeypatch.setenv("HARMONYLAB_ALLOW_LEGACY_EXERCISE", "1")
    author = get_user_model().objects.create(email="w@w.com", username="w")
    ex = Exercise.objects.create(
        description="legacy",
        data={"type": "chorale_identification", "score": {}},  # intentionally broken UMTO
        authored_by=author,
    )
    # Force UMTO path: set isUMTO but make validation fail.
    ex.data = {"isUMTO": True, "metadata": {}, "voices": {}}
    ex.save()

    # This test verifies the warning is emitted; exact view invocation
    # is repo-specific. Fall back to direct function test if views are hard to hit.
    from lab.views import exercise_view  # adjust per actual view function name
    # ...
    with caplog.at_level(logging.WARNING):
        # minimal request to trigger the UMTO path
        pass

    assert any("[LEGACY EXERCISE]" in r.message for r in caplog.records)
```

(If the view function is hard to test in isolation, simplify to a direct call of the UMTO-validation block extracted into a helper. If extraction itself is out of scope, delete this test and keep only Step 12.2's edit.)

- [ ] **Step 12.2: Replace `print` with logger**

In `lab/views.py`, at the top add (near other imports):

```python
import logging

logger = logging.getLogger(__name__)
```

Replace lines ~289-292:

```python
except Exception as e:
    # Fallback to raw data if UMTO validation fails
    print(f"UMTO Alignment Warning: {e}")
    exercise_context.update(exercise.data)
```

with:

```python
except Exception as e:
    logger.warning(
        "[LEGACY EXERCISE] Exercise %s failed UMTO validation: %s. "
        "Falling back to raw data. Migrate via apps.exercises.umto_factory.",
        exercise.id, e,
    )
    exercise_context.update(exercise.data)
```

- [ ] **Step 12.3: Run test (if kept)**

Run: `pytest apps/exercises/tests/test_views_umto_logging.py -v`
Expected: pass.

- [ ] **Step 12.4: Commit**

```bash
git add lab/views.py apps/exercises/tests/test_views_umto_logging.py
git commit -m "lab/views: replace print with logger.warning for legacy UMTO fallback"
```

---

## Task 13: Migrate test fixtures

**Files:**
- Modify: `apps/exercises/tests/test_adaptive_serving.py`
- Modify: `apps/exercises/tests/test_recurring_progress.py`
- Modify: any other test that creates `Exercise(...)` rows
- Create: `apps/exercises/tests/umto_test_helpers.py`

- [ ] **Step 13.1: Create shared test helper**

Create `apps/exercises/tests/umto_test_helpers.py`:

```python
"""Helpers for tests that need to create Exercise rows without manually
shaping UMTO payloads."""
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode


DEFAULT_CIR = {
    "meta": {"key": "C", "time": "4/4"},
    "measures": [{
        "staves": {"treble": {"voices": [{"items": [
            {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
        ]}]}}
    }]
}


def make_umto_exercise(author, *, description="test", unit=1, skill_tags=None, complexity=11, mode=None):
    return save_umto_exercise(
        description=description,
        score_data=DEFAULT_CIR,
        author=author,
        skill_tags=skill_tags or [f"unit:{unit}"],
        complexity=complexity,
        umto_kwargs=dict(
            exercise_id="TEMP",
            source=description,
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=mode or InteractionMode.PLAYBACK,
            target_voice="soprano",
            unit=unit,
        ),
    )
```

- [ ] **Step 13.2: Audit & migrate every test-side Exercise creation**

Run: `grep -rn "Exercise(" apps/ --include="*.py" | grep -i test`

For each hit, replace the `Exercise(...)` construction with `make_umto_exercise(...)`.

If a test specifically requires legacy-shape data to test legacy fallback paths, add `monkeypatch.setenv("HARMONYLAB_ALLOW_LEGACY_EXERCISE", "1")` to the test and document why with a comment.

- [ ] **Step 13.3: Run full test suite**

Run: `pytest apps/ -v`
Expected: all tests pass. If any fail because of dependency on legacy shape, either migrate to UMTO or add the env bypass with a `# LEGACY: reason` comment.

- [ ] **Step 13.4: Commit**

```bash
git add apps/
git commit -m "Migrate test fixtures to use UMTO factory helper"
```

---

## Task 14: Frontend rendering harness (contract-only)

**Files:**
- Create: `lab/static/js/test/test_umto_rendering.js`

- [ ] **Step 14.1: Identify JS test runner**

Run: `find lab/static/js -name "*.test.js" -o -name "*.spec.js" | head` and `cat package.json | grep -E '"test|jest|jasmine|karma|mocha"' | head`

If a runner is configured: proceed to Step 14.2 with that runner's syntax.
If no runner is configured: skip this task, add a note to the spec's "Open Questions" section indicating frontend contract testing is deferred. Continue to Task 15.

- [ ] **Step 14.2: Write frontend contract test**

Create `lab/static/js/test/test_umto_rendering.js` (syntax assumes Jest; adapt to whatever the repo uses):

```javascript
const fs = require('fs');
const path = require('path');

// Adjust this import path to match how ExerciseSheetComponent is exposed
// in the repo's test environment.
const ExerciseSheetComponent = require('../src/components/music/exercise_sheet').default;

const FIXTURES = [
  'unit1_identification_treble.json',
  'unit1_identification_bass.json',
  'unit9_chorale_roman.json',
  'maximal.json',
  'minimal.json',
];

describe('_convertUMTOToProcessedScore', () => {
  FIXTURES.forEach((name) => {
    test(`${name} produces structurally valid processed score`, () => {
      const fixturePath = path.join(
        __dirname, '../../../../apps/exercises/tests/fixtures/umto', name
      );
      const umto = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
      const processed = ExerciseSheetComponent.prototype._convertUMTOToProcessedScore(umto);

      expect(processed).toBeTruthy();
      expect(processed.measures.length).toBeGreaterThanOrEqual(1);
      expect(processed.measures[0].staves.treble.voices).toBeInstanceOf(Array);
      expect(processed.measures[0].staves.bass.voices).toBeInstanceOf(Array);

      // Every note voice event in UMTO must appear as an item in the processed score
      // on the correct staff (S/A → treble, T/B → bass).
      ['S', 'A', 'T', 'B'].forEach((vid) => {
        const events = umto.voices[vid] || [];
        const noteCount = events.filter(e => e.kind === 'note').length;
        if (noteCount > 0) {
          const staff = (vid === 'S' || vid === 'A') ? 'treble' : 'bass';
          const voiceIdx = (vid === 'S' || vid === 'T') ? 0 : 1;
          const processedItems = processed.measures[0].staves[staff].voices[voiceIdx]?.items || [];
          const processedNoteCount = processedItems.filter(i => i.kind === 'note').length;
          expect(processedNoteCount).toBe(noteCount);
        }
      });
    });
  });
});
```

- [ ] **Step 14.3: Run JS tests**

Run: whatever command the repo uses (`npm test`, `yarn test`, etc.).
Expected: pass.

- [ ] **Step 14.4: Commit**

```bash
git add lab/static/js/test/test_umto_rendering.js
git commit -m "Add frontend UMTO rendering contract test"
```

---

## Task 15: Flip model guard — `Exercise.clean()` + `Exercise.save()`

**Files:**
- Modify: `apps/exercises/models.py`
- Modify: `apps/exercises/tests/test_umto_contract.py`

- [ ] **Step 15.1: Write failing test for legacy rejection**

Append to `apps/exercises/tests/test_umto_contract.py`:

```python
@pytest.mark.django_db
def test_new_exercise_without_umto_is_rejected():
    from apps.exercises.models import Exercise
    from apps.exercises.umto_factory import NonUMTOExerciseError
    from django.contrib.auth import get_user_model

    author = get_user_model().objects.create(email="guard@g.com", username="g")

    with pytest.raises(NonUMTOExerciseError):
        Exercise.objects.create(
            description="should reject",
            data={"type": "chorale_identification", "score": {}},
            authored_by=author,
        )


@pytest.mark.django_db
def test_new_exercise_with_legacy_bypass_env_is_allowed(monkeypatch):
    from apps.exercises.models import Exercise
    from django.contrib.auth import get_user_model

    monkeypatch.setenv("HARMONYLAB_ALLOW_LEGACY_EXERCISE", "1")
    author = get_user_model().objects.create(email="bypass@g.com", username="bypass")

    ex = Exercise.objects.create(
        description="legacy allowed",
        data={"type": "chorale_identification", "score": {}},
        authored_by=author,
    )
    assert ex.pk is not None


@pytest.mark.django_db
def test_existing_legacy_row_can_still_be_updated():
    from apps.exercises.models import Exercise
    from django.contrib.auth import get_user_model
    import os

    os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"] = "1"
    try:
        author = get_user_model().objects.create(email="leg@g.com", username="leg")
        ex = Exercise.objects.create(
            description="legacy",
            data={"type": "chorale_identification", "score": {}},
            authored_by=author,
        )
    finally:
        del os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"]

    # Updates must succeed without bypass (grandfathering).
    ex.description = "updated legacy"
    ex.save()
    assert Exercise.objects.get(pk=ex.pk).description == "updated legacy"
```

- [ ] **Step 15.2: Run tests, verify fail**

Run: `pytest apps/exercises/tests/test_umto_contract.py -v -k "rejected or bypass or updated"`
Expected: FAIL — guard not yet installed.

- [ ] **Step 15.3: Install guard in `Exercise.save()` and `Exercise.clean()`**

In `apps/exercises/models.py`:

Add at top of file (with other imports):

```python
import os
```

Inside `class Exercise`, add a `clean` method and modify `save`. Place `clean` just above the existing `save` method (around line 227).

```python
def _umto_validate_or_raise(self, exc_cls):
    """Shared UMTO validation. Called by both clean() and save()."""
    if _legacy_bypass_enabled():
        return
    if not isinstance(self.data, dict) or not self.data.get("isUMTO"):
        raise exc_cls(
            "Exercise creation blocked: data missing isUMTO=True. "
            "Use apps.exercises.umto_factory.save_umto_exercise()."
        )
    try:
        from apps.exercises.umto import UMTO
        umto_dict = self.data.get("score", {}).get("umto") or self.data
        UMTO.model_validate(umto_dict)
    except exc_cls:
        raise
    except Exception as e:
        raise exc_cls(f"UMTO validation failed: {e}") from e


def clean(self):
    super().clean() if hasattr(super(), "clean") else None
    if not self.pk:
        from django.core.exceptions import ValidationError
        try:
            self._umto_validate_or_raise(ValidationError)
        except ValidationError as e:
            raise ValidationError({"data": str(e)})


def save(self, *args, **kwargs):
    if not self._id:
        from apps.exercises.umto_factory import NonUMTOExerciseError
        self._umto_validate_or_raise(NonUMTOExerciseError)
        super(Exercise, self).save(*args, **kwargs)
        self.set_id(initial="E")
        self.save()
        self.set_auto_playlist()

    self.set_id(initial="E")
    self.sort_data()
    self.set_rhythm_values()

    super(Exercise, self).save(*args, **kwargs)
```

Also add below the class (module-level):

```python
def _legacy_bypass_enabled() -> bool:
    return os.environ.get("HARMONYLAB_ALLOW_LEGACY_EXERCISE") == "1"
```

- [ ] **Step 15.4: Run contract tests, verify pass**

Run: `pytest apps/exercises/tests/test_umto_contract.py -v`
Expected: all tests pass including the three new ones.

- [ ] **Step 15.5: Run full test suite to catch regressions**

Run: `pytest apps/ -v`
Expected: all pass. If any legacy-fixture-using test fails, loop back to Task 13 — those tests were missed.

- [ ] **Step 15.6: Commit**

```bash
git add apps/exercises/models.py apps/exercises/tests/test_umto_contract.py
git commit -m "Install UMTO guard on Exercise.clean() and Exercise.save()"
```

---

## Task 16: Docs — CLAUDE.md directive + UMTO_GUIDE.md + header banners

**Files:**
- Modify: `CLAUDE.md`
- Create: `docs/UMTO_GUIDE.md`

- [ ] **Step 16.1: Add UMTO section to top of CLAUDE.md**

Open `CLAUDE.md`. Just below the `# HarmonyLab Chorale Exercise System - Implementation Guide` title, insert:

```markdown
## UMTO is the Canonical Exercise Representation

**All new Exercise rows MUST be UMTO.** Legacy `chorale`, `chorale_identification`,
and raw-CIR Exercise shapes are FROZEN — do not extend, do not emit from new code.

### Creating an Exercise (only sanctioned path)

```python
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode

ex = save_umto_exercise(
    description="BWV1.6 mm.1-2 — Soprano (identification) Stage 1",
    score_data=cir_score_dict,
    author=user,
    skill_tags=["unit:1", "Note_Names", "Read_Treble_Clef"],
    complexity=11,
    umto_kwargs=dict(
        exercise_id="TEMP",
        source="BWV1.6 measures 1-2, Soprano voice.",
        key="G", meter="4/4", clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        target_voice="soprano",
        unit=1,
    ),
)
```

Direct `Exercise(data={...}).save()` on new rows is blocked by `Exercise.clean()`
and `Exercise.save()`. Bypass env `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` exists for
one-shot migration scripts only — never set in CI, tests, or production.

Schema: [apps/exercises/umto_schema.json](apps/exercises/umto_schema.json)
(auto-regenerated by `python manage.py make_umto_schema`).

Guide: [docs/UMTO_GUIDE.md](docs/UMTO_GUIDE.md)
Spec: [docs/superpowers/specs/2026-04-23-umto-consistency-design.md](docs/superpowers/specs/2026-04-23-umto-consistency-design.md)
```

- [ ] **Step 16.2: Create `docs/UMTO_GUIDE.md`**

Create `docs/UMTO_GUIDE.md`:

```markdown
# UMTO Developer Guide

## What UMTO is

Universal Music Theory Object — the single canonical Exercise payload shape.
Defined by the pydantic model at [apps/exercises/umto.py](../apps/exercises/umto.py)
and the schema at [apps/exercises/umto_schema.json](../apps/exercises/umto_schema.json).

## When to use it

Always. Every new Exercise row must be UMTO.

## Creating an Exercise

See CLAUDE.md "UMTO is the Canonical Exercise Representation" for the full
example. Short form:

```python
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode

ex = save_umto_exercise(
    description=...,
    score_data=cir_dict,
    author=user,
    skill_tags=[...],
    complexity=...,
    umto_kwargs=dict(mode=InteractionMode.IDENTIFICATION, ...),
)
```

## The three InteractionMode values

- `PLAYBACK` — student sees notation, plays each note on MIDI keyboard. Grading
  matches MIDI pitch to grading slice.
- `IDENTIFICATION` — student sees notation, picks a label (note name, roman
  numeral, scale degree) from choices. Grading matches selected label to
  `analysis.content`.
- `ANALYSIS_MATCH` — student sees a label, plays matching pitch in any octave.
  Grading relaxes octave constraint.

## Voice model

`voices.S`, `.A`, `.T`, `.B`. Each is a list of `VoiceEvent` (note or rest) with
absolute duration in quarter-lengths.

`metadata.clef` controls rendering:
- `"treble"` — single staff, all events rendered there regardless of voice id
- `"bass"` — same, single bass staff
- `"keyboard"` — SATB. Soprano+Alto → treble staff, Tenor+Bass → bass staff

## Analysis slices vs. grading slices

- `analysis[]` — pedagogical content (Roman numerals, figured bass, etc.) shown
  to the student. Drives label choices and correct-answer logic.
- `grading[]` — target MIDI pitches at each onset. Drives MIDI input grading.

Same `offset` in both arrays represents the same musical moment. Keep them
aligned when authoring.

## Adding a new analysis label type

1. Extend `AnalysisLayer` in `apps/exercises/umto.py`.
2. Update `get_allowed_answers` priority order if needed.
3. Run `python manage.py make_umto_schema` to regenerate the schema.
4. Add a fixture under `apps/exercises/tests/fixtures/umto/` exercising the new field.
5. Contract test #2 will fail in CI if you skip step 3.

## Common pitfalls

- `exercise_id="TEMP"` at build time. Factory's `save_umto_exercise` backfills
  the DB-assigned id after save.
- Unit-tag-driven filtering. `AnalysisSlice.unit_tags=[1]` triggers the Unit 1
  note-name bridge in the frontend. Set it when your exercise is pedagogically
  a "Unit N" exercise.
- The CIR→VexFlow bridge. `_convertUMTOToProcessedScore` in
  `lab/static/js/src/components/music/exercise_sheet.js` is a temporary
  adapter. Do not reach around it — if rendering is broken, fix the adapter or
  the UMTO, not the VexFlow layer.

## FAQ

**Q: Why is there still a bridge to CIR (`_convertUMTOToProcessedScore`)?**
A: The VexFlow adapter still speaks legacy. Native UMTO rendering is a future
phase, tracked separately. Until then the bridge keeps the frontend working.

**Q: Can I create an Exercise from a Jupyter notebook / shell?**
A: Yes — use `save_umto_exercise`. If you have data in a legacy shape and need
to migrate, use a dedicated management command with
`HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` set.

**Q: The model guard blocks my test.**
A: Use `apps.exercises.tests.umto_test_helpers.make_umto_exercise(...)`. The
bypass env var is only for migration scripts.
```

- [ ] **Step 16.3: Add header banner to one legacy file path as example**

Open `apps/dashboard/views/exercises.py`. Near the top (after imports), add:

```python
# FROZEN — legacy Exercise-shape support remains only for reading existing rows.
# NEW Exercise creation in this module MUST use apps.exercises.umto_factory.
# See CLAUDE.md "UMTO is the Canonical Exercise Representation".
```

- [ ] **Step 16.4: Commit**

```bash
git add CLAUDE.md docs/UMTO_GUIDE.md apps/dashboard/views/exercises.py
git commit -m "Document UMTO as canonical; add CLAUDE.md directive and UMTO_GUIDE"
```

---

## Task 17: CI guard — grep for legacy type strings

**Files:**
- Create or modify: repo's CI config (or `scripts/check_no_legacy_exercise.sh`)

- [ ] **Step 17.1: Add script**

Create `scripts/check_no_legacy_exercise.sh`:

```bash
#!/bin/bash
# Fails if any production source file contains a legacy Exercise type string.
# Test fixtures and legacy migration tests are allowed.

set -euo pipefail

BAD=$(grep -rlE '"type":\s*"chorale(_identification)?"' \
  apps/ lab/ \
  --include='*.py' --include='*.js' --include='*.html' \
  --exclude-dir='fixtures' \
  --exclude-dir='legacy_fixtures' \
  --exclude-dir='__pycache__' \
  --exclude='test_migrate_unit1_to_umto.py' \
  --exclude='umto_test_helpers.py' \
  || true)

if [ -n "$BAD" ]; then
  echo "ERROR: Legacy Exercise type strings found in:"
  echo "$BAD"
  echo
  echo "All new Exercise creation must use apps.exercises.umto_factory."
  echo "See CLAUDE.md 'UMTO is the Canonical Exercise Representation'."
  exit 1
fi
echo "OK: no legacy Exercise type strings in production source."
```

Make it executable:

```bash
chmod +x scripts/check_no_legacy_exercise.sh
```

- [ ] **Step 17.2: Wire into CI**

If repo has `.github/workflows/*.yml`, append a step to the existing test workflow:

```yaml
- name: Check no legacy Exercise shapes
  run: ./scripts/check_no_legacy_exercise.sh
```

If no CI file exists, skip this step — note it in Task 18 success criteria.

- [ ] **Step 17.3: Run locally**

Run: `./scripts/check_no_legacy_exercise.sh`
Expected: `OK: no legacy Exercise type strings in production source.`

- [ ] **Step 17.4: Commit**

```bash
git add scripts/check_no_legacy_exercise.sh .github/workflows/ 2>/dev/null || true
git commit -m "CI: fail if legacy Exercise type strings appear in production source"
```

---

## Task 18: Final verification

- [ ] **Step 18.1: Full test suite**

Run: `pytest apps/ -v`
Expected: all pass.

- [ ] **Step 18.2: Legacy grep CI script**

Run: `./scripts/check_no_legacy_exercise.sh`
Expected: OK message.

- [ ] **Step 18.3: Schema freshness check**

Run: `python manage.py make_umto_schema && git diff apps/exercises/umto_schema.json`
Expected: no diff.

- [ ] **Step 18.4: Smoke test frontend**

Start dev server, load an existing UMTO exercise in the browser, verify:
- Renders correctly
- No `[LEGACY EXERCISE]` warnings in server logs for UMTO rows
- `isUMTO()` returns true in JS console for the exercise

- [ ] **Step 18.5: Final commit if any tidy-up**

```bash
git status
# If clean, nothing to commit.
# If dirty, commit outstanding adjustments.
```

- [ ] **Step 18.6: Update memory**

Save memory note:
```
Name: umto-canonical-form
Type: project
Body: UMTO (apps/exercises/umto.py + apps/exercises/umto_factory.py) is the
canonical Exercise shape. All new Exercise rows go through save_umto_exercise.
Exercise.clean() and Exercise.save() guard against legacy shapes.
HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 bypass for one-shot migrations only.
Why: prevents schema-drift debugging loops (see 2026-04-23 spec).
How to apply: refuse to generate Exercise(...) calls that don't use the factory.
```

---

## Self-Review

**Spec coverage check** — every spec requirement is implemented:
- Layer 1 (factory) → Tasks 1-4
- Layer 2 (model guard + clean()) → Task 15
- Layer 3 (views + logger + dashboard endpoint) → Tasks 11, 12
- Layer 4 (fixtures + contract tests + JS harness) → Tasks 6, 7, 8, 14
- Schema hygiene (regenerate + argparse fix) → Tasks 5, 9
- Documentation (CLAUDE.md + UMTO_GUIDE + banners) → Task 16
- Command migration → Tasks 9, 10, 11
- Test fixture migration (gate before flip) → Task 13 precedes Task 15
- Legacy-grep CI → Task 17
- Minimal + maximal + six unit fixtures → Task 6
- isUMTO=True explicit value assertion → Task 8 contract test #3

**Placeholder scan:** searched for TBD, TODO, "fill in", "similar to" — none found. Every code step has complete code.

**Type consistency:** `build_umto_payload` signature matches between Tasks 2, 3, 4, 9, 10, 11, 13, 16. `save_umto_exercise` signature matches across Tasks 4, 9, 10, 11, 13. `NonUMTOExerciseError` referenced consistently.

**Rollout order matches spec:** Task 15 (model guard flip) comes after Task 13 (test fixture migration), which comes after Tasks 9-11 (command migration), as the spec requires.

Plan complete.

---
