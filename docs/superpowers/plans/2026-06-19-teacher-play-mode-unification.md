# Teacher Play exercise-mode unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the manual `/teacher/play/` exercise editor so its 7 exercise-type
options (`play, play_figures, roman, figures, figures_unabbreviated,
matching, harmonization`) produce the correct `InteractionMode` and
`analysisType`, matching what the Bach matrix generator already does
correctly — instead of `"roman"`/`"figures"` silently falling back to
always-visible static labels.

**Architecture:** Extract the mode → `(InteractionMode, analysis_type,
display)` mapping that already works in `import_bach_phrases.py` into one
shared, tested resolver function. Both `import_bach_phrases.py` (Bach
corpus pipeline) and `lab/views.py` `AddExerciseView` (manual editor) call
the same function, so the two pipelines can never drift apart again. Add
the missing `analysisType` field to the chordal exercise payload builder,
which today never sets it (silently defaulting to `"roman"` on the
frontend regardless of what the teacher picked).

**Tech Stack:** Django 5.2, Python, pydantic (UMTO models), vanilla JS/jQuery
(play.html save dialog).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-19-teacher-play-mode-unification-design.md`
- Scope is the manual editor only. The batch wizard's HTML doesn't exist in
  any template (`#batch-wizard-overlay` is referenced only in JS, guarded by
  `if (!overlay.length) { return; }`) — it is unreachable dead code and out
  of scope for this plan.
- No retroactive fix for exercises already saved with the old broken
  `"roman"` semantics — only future saves are affected.
- `import_bach_phrases.py`'s existing test suite
  (`apps/exercises/tests/test_import_bach_phrases.py`) must pass unchanged
  after the resolver extraction — it is the regression guard that the
  refactor is behavior-preserving.

---

### Task 1: Shared mode resolver

**Files:**
- Create: `apps/exercises/utils/teacher_play_modes.py`
- Test: `apps/exercises/tests/test_teacher_play_modes.py`

**Interfaces:**
- Produces: `resolve_mode(mode: str) -> dict` with keys `"interaction_mode"`
  (an `apps.exercises.umto.InteractionMode` member), `"analysis_type"` (str),
  `"display"` (`Optional[dict]`). Tasks 2 and 5 both import and call this.

- [ ] **Step 1: Write the failing tests**

```python
# apps/exercises/tests/test_teacher_play_modes.py
from unittest import TestCase

from apps.exercises.umto import InteractionMode
from apps.exercises.utils.teacher_play_modes import resolve_mode


class ResolveModeTests(TestCase):
    def test_play_is_playback_with_roman_analysis_type_and_no_display(self):
        result = resolve_mode("play")
        self.assertEqual(result["interaction_mode"], InteractionMode.PLAYBACK)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])

    def test_play_figures_is_playback_with_figured_bass_display_overlay(self):
        result = resolve_mode("play_figures")
        self.assertEqual(result["interaction_mode"], InteractionMode.PLAYBACK)
        self.assertEqual(result["analysis_type"], "figured_bass")
        self.assertEqual(
            result["display"],
            {
                "showFigures": True,
                "figureStyle": "figures_abbrev",
                "analysisRenderer": "notater",
            },
        )

    def test_roman_is_identification_with_roman_analysis_type(self):
        result = resolve_mode("roman")
        self.assertEqual(result["interaction_mode"], InteractionMode.IDENTIFICATION)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])

    def test_figures_is_identification_with_figured_bass_analysis_type(self):
        result = resolve_mode("figures")
        self.assertEqual(result["interaction_mode"], InteractionMode.IDENTIFICATION)
        self.assertEqual(result["analysis_type"], "figured_bass")
        self.assertIsNone(result["display"])

    def test_figures_unabbreviated_uses_unabbreviated_analysis_type(self):
        result = resolve_mode("figures_unabbreviated")
        self.assertEqual(result["interaction_mode"], InteractionMode.IDENTIFICATION)
        self.assertEqual(result["analysis_type"], "figured_bass_unabbreviated")
        self.assertIsNone(result["display"])

    def test_matching_is_analysis_match_with_roman_analysis_type(self):
        result = resolve_mode("matching")
        self.assertEqual(result["interaction_mode"], InteractionMode.ANALYSIS_MATCH)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])

    def test_harmonization_is_harmonization_mode_with_roman_analysis_type(self):
        result = resolve_mode("harmonization")
        self.assertEqual(result["interaction_mode"], InteractionMode.HARMONIZATION)
        self.assertEqual(result["analysis_type"], "roman")
        self.assertIsNone(result["display"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.exercises.tests.test_teacher_play_modes --settings=harmony.settings.local -v 2`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'apps.exercises.utils.teacher_play_modes'`

- [ ] **Step 3: Write the implementation**

```python
# apps/exercises/utils/teacher_play_modes.py
from typing import Optional, TypedDict

from apps.exercises.umto import InteractionMode


class ModeResolution(TypedDict):
    interaction_mode: InteractionMode
    analysis_type: str
    display: Optional[dict]


def resolve_mode(mode: str) -> ModeResolution:
    """Map a teacher-play mode string to its InteractionMode, analysis_type,
    and any mode-driven display overrides.

    Single source of truth, shared by import_bach_phrases.py (Bach corpus
    pipeline) and lab/views.py AddExerciseView (manual editor), so the two
    pipelines can't drift into different meanings for the same mode string.
    """
    if mode in ("play", "play_figures"):
        interaction_mode = InteractionMode.PLAYBACK
    elif mode == "matching":
        interaction_mode = InteractionMode.ANALYSIS_MATCH
    elif mode == "harmonization":
        interaction_mode = InteractionMode.HARMONIZATION
    else:  # roman, figures, figures_unabbreviated
        interaction_mode = InteractionMode.IDENTIFICATION

    display: Optional[dict] = None
    if mode == "figures":
        analysis_type = "figured_bass"
    elif mode == "figures_unabbreviated":
        analysis_type = "figured_bass_unabbreviated"
    elif mode == "play_figures":
        analysis_type = "figured_bass"
        display = {
            "showFigures": True,
            "figureStyle": "figures_abbrev",
            "analysisRenderer": "notater",
        }
    else:
        analysis_type = "roman"

    return {
        "interaction_mode": interaction_mode,
        "analysis_type": analysis_type,
        "display": display,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.exercises.tests.test_teacher_play_modes --settings=harmony.settings.local -v 2`
Expected: `OK` (7 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/teacher_play_modes.py apps/exercises/tests/test_teacher_play_modes.py
git commit -m "feat: add shared teacher-play mode resolver"
```

---

### Task 2: Refactor import_bach_phrases.py to use the shared resolver

**Files:**
- Modify: `apps/exercises/management/commands/import_bach_phrases.py:682-739`

**Interfaces:**
- Consumes: `resolve_mode(mode: str) -> dict` from Task 1.

- [ ] **Step 1: Run the existing test suite to capture the current baseline**

Run: `python manage.py test apps.exercises.tests.test_import_bach_phrases --settings=harmony.settings.local -v 2`
Expected: `OK` (all tests pass — this is the pre-refactor baseline)

- [ ] **Step 2: Replace the inline mode-mapping logic**

In `apps/exercises/management/commands/import_bach_phrases.py`, find this
block (currently lines 682-739):

```python
                # 4. Map to UMTO Interaction Mode
                # `roman` and `figures` are label-entry exercises (show prompts/slots),
                # while `matching` is the inverse mode (label shown, play the pitch).
                if mode in ('play', 'play_figures'):
                    umto_mode = InteractionMode.PLAYBACK
                elif mode == 'matching':
                    umto_mode = InteractionMode.ANALYSIS_MATCH
                else:
                    umto_mode = InteractionMode.IDENTIFICATION
                
                # 5. Build Intro Text
                if mode == 'figures':
                    intro_text = f"Provide the Figured Bass for this phrase from Bach (BWV {bwv_display}, mm. {start_m}-{end_m})."
                elif mode == 'matching' or mode == 'roman':
                    intro_text = f"Analyze the Roman Numerals for this phrase from Bach (BWV {bwv_display}, mm. {start_m}-{end_m})."
                else:
                    intro_text = f"Play all four voices of this Bach phrase (BWV {bwv_display}, mm. {start_m}-{end_m})."
```

and the later block (currently around line 726-737):

```python
                display = None
                if mode == 'figures':
                    analysis_type = 'figured_bass'
                elif mode == 'figures_unabbreviated':
                    analysis_type = 'figured_bass_unabbreviated'
                elif mode == 'play_figures':
                    analysis_type = 'figured_bass'
                    display = {
                        "showFigures": True,
                        "figureStyle": "figures_abbrev",
                        "analysisRenderer": "notater",
                    }
                else:
                    analysis_type = 'roman'
```

Replace both with:

```python
                # 4. Map to UMTO Interaction Mode / analysis_type / display via
                # the shared resolver (also used by the manual editor in lab/views.py).
                from apps.exercises.utils.teacher_play_modes import resolve_mode
                resolved = resolve_mode(mode)
                umto_mode = resolved["interaction_mode"]
                analysis_type = resolved["analysis_type"]
                display = resolved["display"]

                # 5. Build Intro Text
                if mode == 'figures':
                    intro_text = f"Provide the Figured Bass for this phrase from Bach (BWV {bwv_display}, mm. {start_m}-{end_m})."
                elif mode == 'matching' or mode == 'roman':
                    intro_text = f"Analyze the Roman Numerals for this phrase from Bach (BWV {bwv_display}, mm. {start_m}-{end_m})."
                else:
                    intro_text = f"Play all four voices of this Bach phrase (BWV {bwv_display}, mm. {start_m}-{end_m})."
```

(The two original `if mode == 'figures': analysis_type = ...` blocks
collapse into the single `resolved = resolve_mode(mode)` call placed where
the first block used to be; delete the now-redundant second block entirely.)

- [ ] **Step 3: Run the existing test suite again to confirm zero behavior change**

Run: `python manage.py test apps.exercises.tests.test_import_bach_phrases --settings=harmony.settings.local -v 2`
Expected: `OK` (same test count, same results as Step 1 — this proves the
extraction is behavior-preserving)

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/management/commands/import_bach_phrases.py
git commit -m "refactor: import_bach_phrases uses shared teacher-play mode resolver"
```

---

### Task 3: Wire `analysisType` through the chordal exercise payload

**Files:**
- Modify: `apps/exercises/umto_factory.py:668-728` (`build_chordal_umto_payload`)
- Modify: `apps/exercises/umto_factory.py:850-870` (`save_chordal_umto_exercise` signature)
- Modify: `apps/exercises/umto_factory.py:932-936` (`save_chordal_umto_exercise` call into `build_chordal_umto_payload`)
- Test: `apps/exercises/tests/test_umto_factory.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: `build_chordal_umto_payload(..., analysis_type: Optional[str] =
  None)` and `save_chordal_umto_exercise(..., analysis_type: Optional[str] =
  None)`. Both default to `"roman"` when not passed. Task 5 passes
  `analysis_type` explicitly.

- [ ] **Step 1: Write the failing test**

```python
# Append to apps/exercises/tests/test_umto_factory.py
from apps.exercises.umto_factory import build_chordal_umto_payload


class ChordalAnalysisTypeTests(TestCase):
    def _chords(self):
        return [
            {"offset": float(i), "duration": 1.0, "visible": [60, 64, 67], "hidden": []}
            for i in range(4)
        ]

    def test_build_chordal_umto_payload_defaults_analysis_type_to_roman(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="test",
            key="C",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            chords=self._chords(),
        )
        self.assertEqual(payload["analysisType"], "roman")

    def test_build_chordal_umto_payload_sets_explicit_analysis_type(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="test",
            key="C",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            chords=self._chords(),
            analysis_type="figured_bass",
        )
        self.assertEqual(payload["analysisType"], "figured_bass")
```

`apps/exercises/tests/test_umto_factory.py` already imports `TestCase` from
`unittest` at the top of the file (line 1: `from unittest import
TestCase`). `build_chordal_umto_payload` needs no database, so this new
`ChordalAnalysisTypeTests` class can use that same `TestCase` — no new
import needed for it. The `from apps.exercises.umto_factory import
build_chordal_umto_payload` line shown at the top of the Step 1 code block
above is a second, separate import statement from the same module as the
file's existing `from apps.exercises.umto_factory import
(NonUMTOExerciseError, _to_music21_key, build_umto_payload,
save_umto_exercise)` — both are valid Python and can coexist; no need to
merge them.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_umto_factory.ChordalAnalysisTypeTests --settings=harmony.settings.local -v 2`
Expected: FAIL with `TypeError: build_chordal_umto_payload() got an unexpected keyword argument 'analysis_type'`

- [ ] **Step 3: Implement — add the parameter and thread it through**

In `apps/exercises/umto_factory.py`, modify `build_chordal_umto_payload`'s
signature (around line 668-683):

```python
def build_chordal_umto_payload(
    *,
    exercise_id: str,
    source: str,
    key: str,
    meter: str,
    clef: str,
    complexity_score: int,
    mode: InteractionMode,
    chords: list,
    analysis: Optional[list] = None,
    unit: Optional[int] = None,
    input_mode: Literal["dropdown", "text"] = "dropdown",
    analysis_review_status: Literal["none", "generated", "reviewed"] = "none",
    barline_offsets: Optional[list] = None,
    analysis_type: Optional[str] = None,
) -> dict:
```

and the returned dict (around line 713-727), add the new key:

```python
    return {
        "type": "umto_chorale",
        "isUMTO": True,
        "mode": mode.value if hasattr(mode, "value") else mode,
        "analysisType": analysis_type or "roman",
        "key": key,
        "meter": meter,
        "clef": clef,
        "complexity_score": complexity_score,
        "score": {
            "meta": {"key": key, "time": meter, "clef": clef},
            "measures": _chordal_to_measures(chords, meter, barline_offsets or []),
            "umto": umto_json,
        },
        "analysis": umto_json["analysis"],
        "grading": [],
    }
```

Then modify `save_chordal_umto_exercise`'s signature (around line 850-870)
to add the same parameter:

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
    analyze_config: Optional[dict] = None,
    display: Optional[dict] = None,
    mode: "InteractionMode" = None,
    analysis_type: Optional[str] = None,
) -> Exercise:
```

and its call into `build_chordal_umto_payload` (around line 932-942), add
the new argument:

```python
    try:
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source=source,
            key=key,
            meter=meter,
            clef=clef,
            complexity_score=complexity,
            mode=mode if mode is not None else InteractionMode.PLAYBACK,
            chords=normalized_chords,
            analysis=analysis_slices,
            unit=None,
            input_mode="dropdown",
            analysis_review_status=review_status,
            barline_offsets=barline_offsets or [],
            analysis_type=analysis_type,
        )
    except Exception as e:
        raise NonUMTOExerciseError(f"Failed to build chordal UMTO payload: {e}") from e
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.exercises.tests.test_umto_factory.ChordalAnalysisTypeTests --settings=harmony.settings.local -v 2`
Expected: `OK` (2 tests)

- [ ] **Step 5: Run the full umto_factory test suite to confirm no regression**

Run: `python manage.py test apps.exercises.tests.test_umto_factory --settings=harmony.settings.local -v 2`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/umto_factory.py apps/exercises/tests/test_umto_factory.py
git commit -m "feat: wire analysisType through chordal exercise payload"
```

---

### Task 4: Expand SUPPORTED_TEACHER_PLAY_MODES to 7 modes

**Files:**
- Modify: `apps/exercises/utils/playlist_naming.py:3-20`
- Modify: `apps/exercises/tests/test_playlist_naming.py:14-20`

**Interfaces:**
- Consumes: nothing.
- Produces: `SUPPORTED_TEACHER_PLAY_MODES` now `("play", "play_figures",
  "roman", "figures", "figures_unabbreviated", "matching",
  "harmonization")`. Task 5 imports this indirectly via
  `AddExerciseView._single_mode`, which already imports
  `SUPPORTED_TEACHER_PLAY_MODES` from this module.

- [ ] **Step 1: Update the failing-first test**

Modify `apps/exercises/tests/test_playlist_naming.py`'s
`test_every_supported_mode_has_a_stable_name` (currently lines 14-28):

```python
    def test_every_supported_mode_has_a_stable_name(self):
        expected = {
            "play": "Play",
            "play_figures": "Play + figures",
            "roman": "Roman",
            "figures": "Figures",
            "figures_unabbreviated": "Figures (unabbreviated)",
            "matching": "Matching",
            "harmonization": "Harmonization",
        }

        self.assertEqual(SUPPORTED_TEACHER_PLAY_MODES, tuple(expected))

        for mode, label in expected.items():
            self.assertEqual(canonical_mode_label(mode), label)
            self.assertEqual(
                build_canonical_playlist_name(11, mode),
                f"Unit 11 — Exercises ({label})",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.exercises.tests.test_playlist_naming --settings=harmony.settings.local -v 2`
Expected: FAIL — `AssertionError` on `SUPPORTED_TEACHER_PLAY_MODES` tuple mismatch (still the old 5-mode set)

- [ ] **Step 3: Implement**

In `apps/exercises/utils/playlist_naming.py`, replace lines 3-20:

```python
SUPPORTED_TEACHER_PLAY_MODES = (
    "play",
    "play_figures",
    "roman",
    "figures",
    "figures_unabbreviated",
    "matching",
    "harmonization",
)

_LEADING_UNIT_RE = re.compile(r"^Units?\s+\d", re.IGNORECASE)
_UNIT_TAG_RE = re.compile(r"^unit:(\w+)$")
_TRAILING_MODE_RE = re.compile(r"\(([a-z_]+)\)\s*$", re.IGNORECASE)

_MODE_LABELS = {
    "play": "Play",
    "play_figures": "Play + figures",
    "roman": "Roman",
    "figures": "Figures",
    "figures_unabbreviated": "Figures (unabbreviated)",
    "matching": "Matching",
    "harmonization": "Harmonization",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.exercises.tests.test_playlist_naming --settings=harmony.settings.local -v 2`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/playlist_naming.py apps/exercises/tests/test_playlist_naming.py
git commit -m "feat: expand teacher-play modes to 7, drop identify"
```

---

### Task 5: Fix AddExerciseView to use the shared resolver

**Files:**
- Modify: `lab/views.py:1047-1089`
- Modify: `lab/tests/test_add_exercise_view_db.py`

**Interfaces:**
- Consumes: `resolve_mode` from Task 1, `analysis_type` param on
  `save_chordal_umto_exercise` from Task 3, 7-mode
  `SUPPORTED_TEACHER_PLAY_MODES` from Task 4 (already imported by
  `_single_mode`, no change needed there).

- [ ] **Step 1: Write the failing tests**

Append to `lab/tests/test_add_exercise_view_db.py`:

```python
    def test_roman_mode_produces_identification_with_roman_analysis_type(self):
        from apps.exercises.models import Exercise
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:1"],
            "mode": "roman",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        ex = Exercise.objects.get(id=resp.json()["id"])
        self.assertEqual(ex.data["mode"], "identification")
        self.assertEqual(ex.data["analysisType"], "roman")
        self.assertNotEqual(ex.data.get("display", {}).get("showRomans"), True)

    def test_figures_mode_produces_identification_with_figured_bass_analysis_type(self):
        from apps.exercises.models import Exercise
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:1"],
            "mode": "figures",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        ex = Exercise.objects.get(id=resp.json()["id"])
        self.assertEqual(ex.data["mode"], "identification")
        self.assertEqual(ex.data["analysisType"], "figured_bass")

    def test_figures_unabbreviated_mode_produces_unabbreviated_analysis_type(self):
        from apps.exercises.models import Exercise
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:1"],
            "mode": "figures_unabbreviated",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        ex = Exercise.objects.get(id=resp.json()["id"])
        self.assertEqual(ex.data["mode"], "identification")
        self.assertEqual(ex.data["analysisType"], "figured_bass_unabbreviated")

    def test_matching_mode_produces_analysis_match(self):
        from apps.exercises.models import Exercise
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:1"],
            "mode": "matching",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        ex = Exercise.objects.get(id=resp.json()["id"])
        self.assertEqual(ex.data["mode"], "analysis_match")

    def test_play_figures_mode_produces_playback_with_figures_display_overlay(self):
        from apps.exercises.models import Exercise
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:1"],
            "mode": "play_figures",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        ex = Exercise.objects.get(id=resp.json()["id"])
        self.assertEqual(ex.data["mode"], "playback")
        self.assertEqual(ex.data["analysisType"], "figured_bass")
        self.assertEqual(ex.data["display"]["showFigures"], True)

    def test_identify_mode_is_no_longer_supported(self):
        payload = {
            "chord": self._chords(),
            "key": "C",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:1"],
            "mode": "identify",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("unsupported", resp.json()["error"].lower())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test lab.tests.test_add_exercise_view_db --settings=harmony.settings.local -v 2`
Expected: FAIL on the new `roman`/`figures`/`figures_unabbreviated` tests
(currently produce `"playback"` not `"identification"`, and
`ex.data["analysisType"]` is `None` not the expected string).
`test_identify_mode_is_no_longer_supported` currently PASSES already (not a
regression target — `"identify"` is still valid pre-fix, so skip asserting
on its current behavior; this test only becomes meaningful after Task 4 has
already landed, which it has by this point in the plan).

- [ ] **Step 3: Implement — replace `_mode_map` and the display force-block**

In `lab/views.py`, find this block (currently lines 1047-1065):

```python
            _mode_map = {
                "identify": InteractionMode.IDENTIFICATION,
                "harmonization": InteractionMode.HARMONIZATION,
            }

            import copy
            mode_display = copy.deepcopy(display or {})
            for flag in ["showRomans", "showFigures", "showChordLabels", "showScaleDegrees", "showNoteNames"]:
                if flag not in mode_display:
                    mode_display[flag] = False
            if mode == "roman":
                mode_display["showRomans"] = True
                mode_display["showFigures"] = False
            elif mode == "figures":
                mode_display["showFigures"] = True
                mode_display["showRomans"] = False
            elif mode in ("identify", "harmonization"):
                mode_display["showRomans"] = False
                mode_display["showFigures"] = False
```

Replace it with:

```python
            from apps.exercises.utils.teacher_play_modes import resolve_mode
            resolved = resolve_mode(mode)
            interaction_mode = resolved["interaction_mode"]
            analysis_type = resolved["analysis_type"]

            import copy
            mode_display = copy.deepcopy(display or {})
            for flag in ["showRomans", "showFigures", "showChordLabels", "showScaleDegrees", "showNoteNames"]:
                if flag not in mode_display:
                    mode_display[flag] = False
            if resolved["display"]:
                for flag, value in resolved["display"].items():
                    if flag not in (display or {}):
                        mode_display[flag] = value
```

Then find the `save_chordal_umto_exercise(...)` call (currently around
line 1073-1089) and change its `mode=` argument plus add `analysis_type=`:

```python
                exercise = save_chordal_umto_exercise(
                    description=description,
                    author=author,
                    chords=chords,
                    key=key,
                    meter=meter,
                    clef=clef,
                    staff_distribution=staff_distribution,
                    skill_tags=skill_tags,
                    is_public=is_public,
                    auto_playlist=False,
                    barline_offsets=barline_offsets,
                    analysis=analysis_slices,
                    analyze_config=analyze_config,
                    display=mode_display,
                    mode=interaction_mode,
                    analysis_type=analysis_type,
                )
```

(Only `mode=_mode_map.get(mode, InteractionMode.PLAYBACK)` →
`mode=interaction_mode` and the new `analysis_type=analysis_type` line
change here — everything else in the call is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test lab.tests.test_add_exercise_view_db --settings=harmony.settings.local -v 2`
Expected: `OK` (all tests, old and new)

- [ ] **Step 5: Run the full lab.tests suite to confirm no regression**

Run: `python manage.py test lab.tests --settings=harmony.settings.local -v 2`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add lab/views.py lab/tests/test_add_exercise_view_db.py
git commit -m "fix: AddExerciseView uses shared mode resolver, fixes roman/figures quiz UI"
```

---

### Task 6: Update the manual editor's mode picker UI

**Files:**
- Modify: `lab/templates/play.html:93-100`
- Modify: `lab/static/js/src/components/ui/music_controls.js:1616-1630`

**Interfaces:**
- Consumes: nothing (pure UI, backend already enforces the 7-mode set from
  Task 4 regardless of what the dropdown sends).

- [ ] **Step 1: Replace the `<select>` options**

In `lab/templates/play.html`, replace lines 93-100:

```html
					<select id="play-save-mode" name="mode" class="play-save-select t-input">
						<option value="">— Select mode —</option>
						<option value="play">Play</option>
						<option value="play_figures">Play + figures</option>
						<option value="roman">Roman numerals</option>
						<option value="figures">Figured bass</option>
						<option value="figures_unabbreviated">Figured bass (unabbreviated)</option>
						<option value="matching">Matching</option>
						<option value="harmonization">Harmonization</option>
					</select>
```

- [ ] **Step 2: Extend the MusicXML-route mode gating to the 3 new analysis modes**

There is no `"identify"`-specific toggle anywhere in this file (it was a
plain static `<option>` with no JS behavior). There IS a route-gating block
that disables/hides `roman`/`figures`/`harmonization` when an imported
MusicXML file isn't routed as `"chordal"` — `figures_unabbreviated`,
`matching`, and `play_figures` need the same treatment, since they depend
on the same chordal-specific analysis support.

In `lab/static/js/src/components/ui/music_controls.js`, find this block
(currently lines 1616-1630):

```javascript
            // Set mode restrictions
            var selectMode = $("#play-save-mode");
            if (data.route === "chordal") {
              selectMode.find("option[value='roman']").prop("disabled", false).show();
              selectMode.find("option[value='figures']").prop("disabled", false).show();
              selectMode.find("option[value='harmonization']").prop("disabled", false).show();
            } else {
              selectMode.find("option[value='roman']").prop("disabled", true).hide();
              selectMode.find("option[value='figures']").prop("disabled", true).hide();
              selectMode.find("option[value='harmonization']").prop("disabled", true).hide();
              var currentVal = selectMode.val();
              if (currentVal === "roman" || currentVal === "figures" || currentVal === "harmonization") {
                selectMode.val("play");
              }
            }
```

Replace it with:

```javascript
            // Set mode restrictions
            var selectMode = $("#play-save-mode");
            var chordalOnlyModes = ["roman", "figures", "figures_unabbreviated", "matching", "harmonization"];
            if (data.route === "chordal") {
              $.each(chordalOnlyModes, function (i, val) {
                selectMode.find("option[value='" + val + "']").prop("disabled", false).show();
              });
            } else {
              $.each(chordalOnlyModes, function (i, val) {
                selectMode.find("option[value='" + val + "']").prop("disabled", true).hide();
              });
              var currentVal = selectMode.val();
              if (chordalOnlyModes.indexOf(currentVal) !== -1) {
                selectMode.val("play");
              }
            }
```

- [ ] **Step 3: Manual smoke test**

This step has no automated test — UI-only change. Per the repo's
verification standard for Roman/identify exercises
(`docs/superpowers/specs/2026-05-26-roman-from-clausulae-lessons.md`):

1. Start the dev server, log in as a teacher, open `/teacher/play/`.
2. Compose a short chord progression (e.g. 4 chords).
3. Open the save dialog, confirm the "Interaction mode" dropdown shows
   exactly 7 options: Play, Play + figures, Roman numerals, Figured bass,
   Figured bass (unabbreviated), Matching, Harmonization.
4. Select "Roman numerals", fill in unit/description, save.
5. Open the saved exercise in the student app. Confirm `?` slots appear in
   place of the Roman numerals (not static always-visible labels), and that
   clicking one and answering correctly works.

- [ ] **Step 4: Commit**

```bash
git add lab/templates/play.html lab/static/js/src/components/ui/music_controls.js
git commit -m "feat: expand manual editor mode picker to 7 modes, drop identify"
```

---

### Task 7: Final regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full affected test surface**

```bash
python manage.py test apps.exercises.tests.test_teacher_play_modes apps.exercises.tests.test_import_bach_phrases apps.exercises.tests.test_umto_factory apps.exercises.tests.test_playlist_naming lab.tests.test_add_exercise_view_db lab.tests.test_play_view --settings=harmony.settings.local -v 2
```

Expected: `OK`, all tests across all six modules.

- [ ] **Step 2: Run the full apps.exercises and lab.tests suites for broader regression coverage**

```bash
python manage.py test apps.exercises lab.tests --settings=harmony.settings.local
```

Expected: `OK`.
