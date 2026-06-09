# Teacher Play Authoring — Phase A Backend Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the chordal-UMTO backend contract for ABC-style Play authoring — explicit barlines drive saved render, durations come from a closed palette, metered exercises are validated as exact contiguous tilings, free mode (`meter=None`) saves anything, and the Play save/review endpoint persists teacher-reviewed analysis.

**Architecture:** Extend the existing chordal-UMTO factory (`apps/exercises/umto_factory.py`) and schema (`apps/exercises/umto.py`). A single shared rhythm validator backs both the create/save path and the review/update endpoint, so UI and agent writes obey one rule. `_chordal_to_measures` splits `score.measures` at explicit teacher barline offsets instead of by meter accumulation. This is the contract layer; the in-Play click-first UI (Plan 2) consumes it.

**Tech Stack:** Python, Django, Pydantic (UMTO models), Django test runner.

**Scope:** Backend only. The in-Play RequireJS/VexFlow authoring UI and analysis-slot persistence are **Plan 2**. This plan produces working, independently-tested backend software.

**Spec:** `docs/superpowers/specs/2026-06-08-teacher-play-authoring-design.md`

---

## File Structure

- **`apps/exercises/umto.py`** — chordal `Metadata`: add `barline_offsets`, make `meter` optional. Pure schema.
- **`apps/exercises/umto_factory.py`** — palette constant + `_is_palette_duration`, the shared `validate_chordal_rhythm`, `_chordal_to_measures` barline splitting, and the `save_chordal_umto_exercise` / `build_chordal_umto_payload` wiring (remove auto-stretch, thread barlines + reviewed analysis).
- **`apps/dashboard/views/api_workbench.py`** — extend `api_chordal_analysis_review` POST with duration/meter/barline ops + validation.
- **`apps/exercises/tests/test_chordal_authoring_backend.py`** (new) — schema, palette, validator, measure-splitting, save-path tests.
- **`apps/exercises/tests/test_play_save_chordal_umto.py`** (existing) — extend for no-auto-stretch + reviewed analysis.

---

## Task 1: Schema — optional meter + explicit barline offsets

**Files:**
- Modify: `apps/exercises/umto.py:127` (the `Metadata` class)
- Test: `apps/exercises/tests/test_chordal_authoring_backend.py`

- [ ] **Step 1: Write the failing test**

Create `apps/exercises/tests/test_chordal_authoring_backend.py`:

```python
from apps.exercises.umto import Metadata, InteractionMode


def _base_metadata_kwargs(**overrides):
    kwargs = dict(
        exercise_id="TEMP",
        source="Play view chordal exercise",
        key="C major",
        clef="keyboard",
        complexity_score=1,
        mode=InteractionMode.PLAYBACK,
        score_kind="chordal",
    )
    kwargs.update(overrides)
    return kwargs


def test_metadata_meter_optional_defaults_none():
    md = Metadata(**_base_metadata_kwargs())
    assert md.meter is None


def test_metadata_accepts_explicit_meter():
    md = Metadata(**_base_metadata_kwargs(meter="3/4"))
    assert md.meter == "3/4"


def test_metadata_barline_offsets_defaults_empty():
    md = Metadata(**_base_metadata_kwargs())
    assert md.barline_offsets == []


def test_metadata_round_trips_barline_offsets():
    md = Metadata(**_base_metadata_kwargs(meter="4/4", barline_offsets=[4.0, 8.0]))
    dumped = md.model_dump(mode="json")
    again = Metadata(**dumped)
    assert again.barline_offsets == [4.0, 8.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: FAIL — `test_metadata_meter_optional_defaults_none` errors because `meter` is a required field; `barline_offsets` tests fail with unexpected-keyword / attribute errors.

- [ ] **Step 3: Edit the `Metadata` model**

In `apps/exercises/umto.py`, change the `meter` line and add `barline_offsets` directly after it:

```python
    meter: Optional[str] = None # e.g. "4/4", "3/4"; None = free/open (no time signature)
    barline_offsets: List[float] = Field(default_factory=list)  # explicit chordal barlines (quarter-lengths, on chord onsets, excludes 0.0 and stream end)
```

(`Optional`, `List`, and `Field` are already imported in this module.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/tests/test_chordal_authoring_backend.py
git commit -m "feat(umto): optional meter + explicit barline_offsets on chordal Metadata"
```

---

## Task 2: Duration palette constant + check

**Files:**
- Modify: `apps/exercises/umto_factory.py` (add near `_QL_TO_DURATION`, ~line 82)
- Test: `apps/exercises/tests/test_chordal_authoring_backend.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/exercises/tests/test_chordal_authoring_backend.py`:

```python
from apps.exercises.umto_factory import CHORDAL_DURATION_PALETTE, _is_palette_duration


def test_palette_contains_the_eight_authoring_values():
    assert CHORDAL_DURATION_PALETTE == {4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25}


def test_is_palette_duration_accepts_palette_values():
    for ql in [4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25]:
        assert _is_palette_duration(ql) is True


def test_is_palette_duration_rejects_off_palette():
    # 0.375 (dotted-16) and 0.125 (32nd) render but are NOT in the authoring palette
    for ql in [0.375, 0.125, 1.25, 2.5, 0.0, 3.5]:
        assert _is_palette_duration(ql) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: FAIL — `ImportError: cannot import name 'CHORDAL_DURATION_PALETTE'`.

- [ ] **Step 3: Add the palette and check**

In `apps/exercises/umto_factory.py`, directly below the `_QL_TO_DURATION` dict (ends ~line 92), add:

```python
# Authoring palette: the closed set of note values the teacher may assign in Play.
# A subset of _QL_TO_DURATION (which also renders 0.375/0.125); tuplets are deferred.
CHORDAL_DURATION_PALETTE = {4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25}


def _is_palette_duration(ql: float) -> bool:
    try:
        return round(float(ql), 6) in CHORDAL_DURATION_PALETTE
    except (TypeError, ValueError):
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_authoring_backend.py
git commit -m "feat(umto): chordal duration authoring palette + check"
```

---

## Task 3: Shared rhythm validator

**Files:**
- Modify: `apps/exercises/umto_factory.py` (add after `_is_palette_duration`)
- Test: `apps/exercises/tests/test_chordal_authoring_backend.py`

The validator is the single rule both the save path (Task 5) and the endpoint (Task 6) call.

- [ ] **Step 1: Write the failing test**

Append to `apps/exercises/tests/test_chordal_authoring_backend.py`:

```python
from apps.exercises.umto_factory import validate_chordal_rhythm
from apps.exercises.models import NonUMTOExerciseError


def _ch(offset, duration, visible=(60,)):
    return {"offset": offset, "duration": duration, "visible": list(visible)}


def test_free_mode_skips_rhythm_validation_but_checks_palette():
    # meter None: any contiguity allowed, palette still enforced
    chords = [_ch(0.0, 1.0), _ch(1.0, 0.75), _ch(1.75, 0.25)]
    validate_chordal_rhythm(chords, meter=None, barline_offsets=[])  # no raise


def test_free_mode_rejects_off_palette_duration():
    chords = [_ch(0.0, 1.25)]
    try:
        validate_chordal_rhythm(chords, meter=None, barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "palette" in str(exc).lower()


def test_metered_exact_tiling_passes():
    # 4/4, two full bars of quarters; barline at 4.0
    chords = [_ch(float(i), 1.0) for i in range(8)]
    validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[4.0])  # no raise


def test_metered_short_bar_blocks():
    # 4/4 but only 3 beats before the end -> last bar short
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0), _ch(2.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "bar" in str(exc).lower()


def test_metered_overfull_bar_blocks():
    # 4/4, a bar summing to 5 beats
    chords = [_ch(0.0, 2.0), _ch(2.0, 2.0), _ch(4.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass


def test_metered_barline_not_on_onset_blocks():
    chords = [_ch(0.0, 1.0), _ch(1.0, 1.0), _ch(2.0, 1.0), _ch(3.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[2.5])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError as exc:
        assert "onset" in str(exc).lower()


def test_metered_gap_blocks():
    # 4/4 with a hole: chord at 0 (q), then next at 2.0 leaving a gap at beat 2
    chords = [_ch(0.0, 1.0), _ch(2.0, 1.0), _ch(3.0, 1.0)]
    try:
        validate_chordal_rhythm(chords, meter="4/4", barline_offsets=[])
        assert False, "expected NonUMTOExerciseError"
    except NonUMTOExerciseError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: FAIL — `ImportError: cannot import name 'validate_chordal_rhythm'`.

- [ ] **Step 3: Implement the validator**

In `apps/exercises/umto_factory.py`, add after `_is_palette_duration`:

```python
def validate_chordal_rhythm(chords, meter, barline_offsets):
    """Validate chordal rhythm against the ABC-style authoring contract.

    Free mode (meter is None): only the duration palette is enforced.
    Metered mode: every bar (segments of [0] + sorted(barline_offsets) + [total])
    must be an EXACT CONTIGUOUS TILING — chords contiguous, first chord on the bar's
    start barline, durations summing to barLen — and every barline offset must
    coincide with a chord onset. Raises NonUMTOExerciseError on the first violation.
    """
    EPS = 1e-6

    # Palette applies in both modes.
    for c in chords:
        if not _is_palette_duration(c.get("duration")):
            raise NonUMTOExerciseError(
                f"Duration {c.get('duration')!r} at offset {c.get('offset')} "
                f"is not in the authoring palette {sorted(CHORDAL_DURATION_PALETTE)}."
            )

    if meter is None:
        return  # free/open mode: no metric validation

    if not chords:
        return

    bar_len = _meter_quarter_length(meter)
    ordered = sorted(chords, key=lambda c: round(float(c["offset"]), 6))
    onsets = {round(float(c["offset"]), 6) for c in ordered}

    # Every explicit barline must land on a chord onset.
    for b in barline_offsets:
        if round(float(b), 6) not in onsets:
            raise NonUMTOExerciseError(
                f"Barline at offset {b} does not coincide with a chord onset."
            )

    total = round(float(ordered[-1]["offset"]) + float(ordered[-1]["duration"]), 6)
    bounds = [0.0] + sorted(round(float(b), 6) for b in barline_offsets) + [total]

    for bar_idx in range(len(bounds) - 1):
        start, end = bounds[bar_idx], bounds[bar_idx + 1]
        bar_chords = [c for c in ordered
                      if start - EPS <= round(float(c["offset"]), 6) < end - EPS]
        beats = round(end - start, 6)
        if abs(beats - bar_len) > EPS:
            raise NonUMTOExerciseError(
                f"Bar {bar_idx + 1} spans {beats} beats, expected {bar_len}."
            )
        if not bar_chords:
            raise NonUMTOExerciseError(f"Bar {bar_idx + 1} is empty.")
        cursor = start
        for c in bar_chords:
            off = round(float(c["offset"]), 6)
            if abs(off - cursor) > EPS:
                raise NonUMTOExerciseError(
                    f"Bar {bar_idx + 1} has a gap/overlap at offset {off} "
                    f"(expected a chord at {round(cursor, 6)})."
                )
            cursor = round(cursor + float(c["duration"]), 6)
        if abs(cursor - end) > EPS:
            filled = round(cursor - start, 6)
            raise NonUMTOExerciseError(
                f"Bar {bar_idx + 1} has {filled} beats, expected {bar_len}."
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: PASS (all validator tests).

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_authoring_backend.py
git commit -m "feat(umto): shared chordal rhythm validator (palette + metered tiling)"
```

---

## Task 4: `_chordal_to_measures` splits at explicit barlines

**Files:**
- Modify: `apps/exercises/umto_factory.py:437` (`_chordal_to_measures`) and `:586` (its call in `build_chordal_umto_payload`) and the `build_chordal_umto_payload` signature (~`:533`)
- Test: `apps/exercises/tests/test_chordal_authoring_backend.py`

Today `_chordal_to_measures(chords, meter)` breaks measures when accumulated quarter-length reaches `beats`. We add an optional `barline_offsets`: when present, split at exactly those offsets (and never by meter accumulation); when absent, keep current behavior. Free mode (`meter=None`, no barlines) becomes a single measure.

- [ ] **Step 1: Write the failing test**

Append to `apps/exercises/tests/test_chordal_authoring_backend.py`:

```python
from apps.exercises.umto_factory import _chordal_to_measures


def test_measures_split_at_explicit_barlines():
    # 6 quarters, barlines at 2.0 and 4.0 -> 3 measures of 2 chords each
    chords = [_ch(float(i), 1.0) for i in range(6)]
    measures = _chordal_to_measures(chords, meter="2/4", barline_offsets=[2.0, 4.0])
    assert len(measures) == 3
    # each measure's treble voice holds 2 items
    for m in measures:
        assert len(m["staves"]["treble"]["voices"][0]["items"]) == 2


def test_free_mode_single_measure_when_no_barlines():
    chords = [_ch(0.0, 1.0), _ch(1.0, 0.5), _ch(1.5, 0.5)]
    measures = _chordal_to_measures(chords, meter=None, barline_offsets=[])
    assert len(measures) == 1
    assert len(measures[0]["staves"]["treble"]["voices"][0]["items"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: FAIL — `_chordal_to_measures()` got an unexpected keyword argument `barline_offsets`.

- [ ] **Step 3: Add barline splitting**

In `apps/exercises/umto_factory.py`, change the signature at line 437:

```python
def _chordal_to_measures(chords: list, meter, barline_offsets=None) -> list:
```

Find the main loop (after the helper defs, ~line 506) that currently reads:

```python
    measures = []
    current = _new_measure()
    used = 0.0
    cursor = 0.0
    for c in sorted(chords, key=lambda item: float(item.get("offset", 0.0))):
        offset = float(c.get("offset", cursor))
        if offset < cursor - 1e-6:
            raise ValueError("Chord offsets must be non-overlapping and monotonic")

        while cursor < offset - 1e-6:
            gap = min(offset - cursor, beats - used)
            _append_rest(gap)
            used += gap
            cursor += gap
            if abs(used - beats) < 1e-6 or used > beats:
                _finish_measure()

        if abs(used - beats) < 1e-6:
            _finish_measure()

        dur = float(c["duration"])
        _append_chord_item(c)
        used += dur
        cursor = offset + dur
        if abs(used - beats) < 1e-6 or used > beats:
            _finish_measure()
    if _any_items():
        measures.append(current)
    return measures
```

Replace that block with a barline-aware version (keep the existing helper closures above it untouched):

```python
    measures = []
    current = _new_measure()
    used = 0.0
    cursor = 0.0

    if barline_offsets:
        # Explicit teacher barlines: split at exactly these offsets.
        split_points = sorted(round(float(b), 6) for b in barline_offsets)
    else:
        split_points = []
    next_split = 0

    for c in sorted(chords, key=lambda item: float(item.get("offset", 0.0))):
        offset = float(c.get("offset", cursor))
        if offset < cursor - 1e-6:
            raise ValueError("Chord offsets must be non-overlapping and monotonic")

        # Fill any gap before this chord with rests (display-only rests).
        while cursor < offset - 1e-6:
            if split_points and next_split < len(split_points) \
                    and split_points[next_split] <= cursor + 1e-6:
                _finish_measure()
                next_split += 1
            limit = offset
            if split_points and next_split < len(split_points):
                limit = min(limit, split_points[next_split])
            if not split_points and beats:
                limit = min(limit, cursor + (beats - used))
            gap = limit - cursor
            if gap <= 1e-6:
                gap = offset - cursor
            _append_rest(gap)
            used += gap
            cursor += gap
            if split_points:
                if next_split < len(split_points) and abs(cursor - split_points[next_split]) < 1e-6:
                    _finish_measure()
                    next_split += 1
            elif beats and (abs(used - beats) < 1e-6 or used > beats):
                _finish_measure()

        # Start a new measure if we've reached the next barline.
        if split_points and next_split < len(split_points) \
                and abs(cursor - split_points[next_split]) < 1e-6:
            _finish_measure()
            next_split += 1
        elif not split_points and beats and abs(used - beats) < 1e-6:
            _finish_measure()

        dur = float(c["duration"])
        _append_chord_item(c)
        used += dur
        cursor = offset + dur

        if split_points:
            if next_split < len(split_points) and abs(cursor - split_points[next_split]) < 1e-6:
                _finish_measure()
                next_split += 1
        elif beats and (abs(used - beats) < 1e-6 or used > beats):
            _finish_measure()

    if _any_items():
        measures.append(current)
    return measures
```

Also handle `meter=None` in the `beats` setup at the top of the function. Find:

```python
    beats = _meter_quarter_length(meter)
```

Replace with:

```python
    beats = _meter_quarter_length(meter) if meter else 0.0
```

(When `meter` is None and there are no barlines, `beats == 0.0` disables meter-accumulation finishes, yielding a single measure.)

- [ ] **Step 4: Thread `barline_offsets` through `build_chordal_umto_payload`**

In `apps/exercises/umto_factory.py`, add a parameter to `build_chordal_umto_payload` (signature starts ~line 533). Add after `meter: str,`:

```python
    barline_offsets: Optional[list] = None,
```

Inside the function, the `Metadata(...)` construction must include barlines — add to the `Metadata(` kwargs:

```python
            barline_offsets=barline_offsets or [],
```

And change the measures call at line 586 from:

```python
            "measures": _chordal_to_measures(chords, meter),
```

to:

```python
            "measures": _chordal_to_measures(chords, meter, barline_offsets or []),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend -v 2`
Expected: PASS.

Run the existing chordal suite to confirm no regression (default behavior preserved when no barlines passed):

Run: `python manage.py test apps.exercises.tests.test_chordal_to_measures_spelling apps.exercises.tests.test_chordal_umto -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_authoring_backend.py
git commit -m "feat(umto): split chordal score.measures at explicit barlines; meter=None single measure"
```

---

## Task 5: `save_chordal_umto_exercise` — barlines, no auto-stretch, reviewed analysis, validation

**Files:**
- Modify: `apps/exercises/umto_factory.py:713` (`save_chordal_umto_exercise`)
- Test: `apps/exercises/tests/test_chordal_authoring_backend.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/exercises/tests/test_chordal_authoring_backend.py`:

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class SaveChordalAuthoringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="t@example.com", password="x"
        )

    def _chords(self):
        # Two 4/4 bars of quarters
        return [{"offset": float(i), "duration": 1.0, "visible": [60, 64, 67]}
                for i in range(8)]

    def test_no_auto_stretch_last_chord_keeps_duration(self):
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=self._chords(),
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
        )
        chords = ex.data["score"]["umto"]["chords"]
        assert chords[-1]["duration"] == 1.0  # NOT stretched to fill the bar

    def test_reviewed_analysis_sets_status_reviewed_without_regeneration(self):
        analysis = [{"offset": 0.0, "content": {"roman_numeral": "I"},
                     "unit_tags": [], "is_target": True}]
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=self._chords(),
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
            analysis=analysis,
        )
        md = ex.data["score"]["umto"]["metadata"]
        assert md["analysis_review_status"] == "reviewed"
        assert ex.data["score"]["umto"]["analysis"][0]["content"]["roman_numeral"] == "I"

    def test_no_analysis_slot_saves_playback_status_none(self):
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=self._chords(),
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
            analysis=[],
        )
        md = ex.data["score"]["umto"]["metadata"]
        assert md["analysis_review_status"] == "none"

    def test_invalid_metered_rhythm_rejected(self):
        from apps.exercises.models import NonUMTOExerciseError
        bad = [{"offset": 0.0, "duration": 1.0, "visible": [60]},
               {"offset": 1.0, "duration": 1.0, "visible": [60]},
               {"offset": 2.0, "duration": 1.0, "visible": [60]}]  # 3 beats in 4/4
        with self.assertRaises(NonUMTOExerciseError):
            save_chordal_umto_exercise(
                description="t", author=self.user, chords=bad,
                key="C major", meter="4/4", clef="keyboard",
                staff_distribution="keyboard",
            )

    def test_free_mode_saves_uneven_durations(self):
        chords = [{"offset": 0.0, "duration": 1.0, "visible": [60]},
                  {"offset": 1.0, "duration": 0.5, "visible": [62]}]
        ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=chords,
            key="C major", meter=None, clef="keyboard",
            staff_distribution="keyboard",
        )
        assert ex.data["score"]["umto"]["metadata"]["meter"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend.SaveChordalAuthoringTests -v 2`
Expected: FAIL — `save_chordal_umto_exercise()` got an unexpected keyword argument `barline_offsets`; and auto-stretch test fails because the last chord is stretched.

- [ ] **Step 3: Update the signature and body**

In `apps/exercises/umto_factory.py`, change the `save_chordal_umto_exercise` signature (line 713). Change `meter: str` to `meter: Optional[str] = None` and add three params:

```python
def save_chordal_umto_exercise(
    *,
    description: str,
    author,
    chords: list,
    key: str,
    meter: Optional[str] = None,
    clef: str,
    staff_distribution: str,
    source: str = "Play view chordal exercise",
    skill_tags: Optional[list] = None,
    complexity: int = 1,
    is_public: bool = False,
    overwrite: bool = False,
    auto_playlist: bool = True,
    barline_offsets: Optional[list] = None,
    analysis: Optional[list] = None,
) -> Exercise:
```

Change the `beats_per_measure` line near the top of the body (line ~732). Find:

```python
    beats_per_measure = _meter_quarter_length(meter)
```

Replace with:

```python
    beats_per_measure = _meter_quarter_length(meter) if meter else 0.0
```

**Remove the final-chord auto-stretch.** In the normalization loop, delete these lines (currently ~752-758):

```python
        # Adjust final chord's duration to fill the remainder of the final measure
        if idx == len(chords) - 1:
            remaining = beats_per_measure - (off % beats_per_measure)
            if abs(remaining) < 1e-5:
                dur = beats_per_measure
            else:
                dur = remaining
```

(The teacher's duration now stands; bar completeness is enforced by the validator instead.)

After the normalization loop builds `normalized_chords`, **add the rhythm validation call** (before the analysis block ~line 776):

```python
    validate_chordal_rhythm(normalized_chords, meter, barline_offsets or [])
```

Replace the analysis-generation block (currently ~776-784) so a caller-supplied `analysis` takes precedence over generation:

```python
    if analysis is not None:
        # Teacher-reviewed (Play) path: use supplied analysis verbatim.
        analysis_slices = analysis
        review_status = "reviewed" if analysis else "none"
    else:
        # Non-Play path (bulk import): auto-generate and mark generated.
        analysis_slices = []
        review_status = "none"
        try:
            from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices
            analysis_slices = build_chordal_analysis_slices(normalized_chords, harmony_key=key)
            if analysis_slices:
                review_status = "generated"
        except Exception as e:
            print(f"Warning: HarmonyLab analysis generation failed: {e}")
```

Finally, pass `barline_offsets` into the `build_chordal_umto_payload(...)` call (in the same function, ~line 787). Add the argument:

```python
            barline_offsets=barline_offsets or [],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend.SaveChordalAuthoringTests -v 2`
Expected: PASS.

- [ ] **Step 5: Guard against regression in the existing play-save suite**

Run: `python manage.py test apps.exercises.tests.test_play_save_chordal_umto -v 2`
Expected: PASS — but if any existing test asserted the old auto-stretch behavior (last chord stretched), update that assertion to expect the chord's authored duration. Search the file:

Run: `grep -n "stretch\|remaining\|beats_per_measure\|duration" apps/exercises/tests/test_play_save_chordal_umto.py`
Fix any test that encoded auto-stretch by changing the expected last-chord duration to the authored value.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_chordal_authoring_backend.py apps/exercises/tests/test_play_save_chordal_umto.py
git commit -m "feat(umto): save path takes barlines + reviewed analysis, drops auto-stretch, validates rhythm"
```

---

## Task 6: Endpoint — duration / meter / barline ops + validation

**Files:**
- Modify: `apps/dashboard/views/api_workbench.py:112` (`api_chordal_analysis_review`)
- Test: `apps/exercises/tests/test_chordal_authoring_backend.py`

Extend the review POST so the Play surface (and an agent) can update durations, meter, and barlines, validated by the shared `validate_chordal_rhythm`. Analysis-slot persistence is **deferred to Plan 2**.

- [ ] **Step 1: Write the failing test**

Append to `apps/exercises/tests/test_chordal_authoring_backend.py`:

```python
import json
from apps.exercises.models import Exercise


class ReviewEndpointRhythmTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="r@example.com", password="x")
        self.client.force_login(self.user)
        chords = [{"offset": float(i), "duration": 1.0, "visible": [60]} for i in range(8)]
        self.ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=chords,
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0],
            analysis=[],
        )

    def _url(self):
        return f"/dashboard/api/workbench/chordal-analysis/{self.ex.id}/"

    def test_post_updates_meter_and_barlines_when_valid(self):
        # Re-bar the same 8 quarters as 4 bars of 2/4
        body = {"meter": "2/4", "barline_offsets": [2.0, 4.0, 6.0], "rows": []}
        resp = self.client.post(self._url(), data=json.dumps(body),
                                content_type="application/json")
        assert resp.status_code == 200, resp.content
        self.ex.refresh_from_db()
        md = self.ex.data["score"]["umto"]["metadata"]
        assert md["meter"] == "2/4"
        assert md["barline_offsets"] == [2.0, 4.0, 6.0]

    def test_post_rejects_off_palette_duration(self):
        body = {"rows": [{"offset": 0.0, "duration": 1.25}]}
        resp = self.client.post(self._url(), data=json.dumps(body),
                                content_type="application/json")
        assert resp.status_code == 400
        assert "palette" in resp.json()["error"].lower()

    def test_post_rejects_invalid_metered_bars(self):
        # Move a barline off the grid so a bar is not barLen
        body = {"meter": "4/4", "barline_offsets": [3.0], "rows": []}
        resp = self.client.post(self._url(), data=json.dumps(body),
                                content_type="application/json")
        assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend.ReviewEndpointRhythmTests -v 2`
Expected: FAIL — endpoint ignores `meter`/`barline_offsets`/`duration` and returns 200 / does not persist them.

- [ ] **Step 3: Extend the POST handler**

In `apps/dashboard/views/api_workbench.py`, import the validator near the top (with the other `apps.exercises` imports):

```python
from apps.exercises.umto_factory import validate_chordal_rhythm, _is_palette_duration
```

In `api_chordal_analysis_review`, inside the POST branch, **after** `payload = json.loads(...)` and **before** the `metadata[...] = "reviewed"` write, apply duration/meter/barline updates and validate. Insert this block right after the `new_analysis` row loop completes (just before `metadata["analysis_review_status"] = "reviewed"`):

```python
    # Apply per-row duration edits (chords is the live list mutated below).
    for row in payload.get("rows", []):
        if "duration" not in row:
            continue
        dur = row["duration"]
        if not _is_palette_duration(dur):
            return JsonResponse(
                {"error": f"Duration {dur!r} is not in the authoring palette."},
                status=400)
        roff = round(float(row.get("offset", 0.0)), 6)
        for chord in chords:
            if round(float(chord.get("offset", 0.0)), 6) == roff:
                chord["duration"] = float(dur)
                break

    # Apply meter / barline updates (None meter = free mode).
    new_meter = payload.get("meter", metadata.get("meter"))
    new_barlines = payload.get("barline_offsets", metadata.get("barline_offsets", []))

    # Validate the resulting rhythm (raises -> 400).
    try:
        validate_chordal_rhythm(chords, new_meter, new_barlines or [])
    except NonUMTOExerciseError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    metadata["meter"] = new_meter
    metadata["barline_offsets"] = new_barlines or []
```

Add the import for the error type if not already present (top of file, with the exercises imports):

```python
from apps.exercises.models import NonUMTOExerciseError
```

Note: the existing handler already mutates `chords` and writes `umto["chords"] = chords` and `exercise.save(...)` after this block, so the duration/meter/barline mutations persist with the existing save. Confirm `metadata` is the same dict object that gets written back (it is — `metadata = umto.setdefault("metadata", {})` style reference earlier in the function).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.exercises.tests.test_chordal_authoring_backend.ReviewEndpointRhythmTests -v 2`
Expected: PASS.

- [ ] **Step 5: Guard against endpoint regression**

Run: `python manage.py test apps.dashboard -v 2`
Expected: PASS (existing review/projection tests still green).

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/views/api_workbench.py apps/exercises/tests/test_chordal_authoring_backend.py
git commit -m "feat(workbench): review endpoint accepts duration/meter/barline ops with shared validation"
```

---

## Task 7: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole exercises + dashboard test suite**

Run: `python manage.py test apps.exercises apps.dashboard -v 1`
Expected: PASS. If a pre-existing test encoded the old auto-stretch or required-meter behavior, fix the assertion to match the new contract (authored durations stand; chordal meter may be None) — do not reintroduce the old behavior.

- [ ] **Step 2: Commit any test fixups**

```bash
git add -A
git commit -m "test: align existing chordal tests with ABC authoring contract"
```

---

## Self-Review Notes (spec coverage)

- Duration palette (spec Decision a) → Tasks 2, 5, 6.
- `metadata.barline_offsets` field shape (spec Decision a) → Task 1.
- Explicit barlines drive `score.measures` (spec Decision a, Codex item 1) → Task 4.
- `meter: Optional = None` free mode (spec Decision a, Codex item 2) → Tasks 1, 4, 5.
- No-reflow duration semantics are a UI contract; the backend enforces only palette + tiling (gaps rejected in metered mode) → Tasks 3, 5. The `setChordDuration` offset-preservation is a **Plan 2 (UI)** concern; backend rejects the resulting invalid tiling.
- Metered exact-tiling validity + free-mode pass (spec Decision a) → Task 3.
- Remove final-chord auto-stretch (spec, Codex r1 item 2) → Task 5.
- Shared validator on save + endpoint (spec, Codex r1 item 3 / r2) → Tasks 3, 5, 6.
- Save = reviewed without regeneration; no-slot → none (spec Decision d, Codex r2 item 4) → Task 5.
- Endpoint duration/meter/barline ops + rejection tests (spec AC10) → Task 6. (Analysis-slot persistence deferred to Plan 2.)

**Deferred to Plan 2 (in-Play UI):** the click-first authoring surface, selection-scoped shortcuts, analysis-slot UI + `analyzeConfig {above, below}` persistence, barline auto-suggest UX, `dataForSave` changes, `music_controls` Save→reviewed wiring + `feedbackService`, ABC-style render path in `exercise_sheet.js`, post-save target selector, MusicXML-onto-canvas.
