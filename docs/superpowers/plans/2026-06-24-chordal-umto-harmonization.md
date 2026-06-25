# Chordal UMTO Harmonization Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs so that chordal UMTO exercises can be assigned and delivered in harmonization mode via teacher/play.

**Architecture:** Backend `build_targets_from_umto` currently reads bass from `voices.B`, which is always empty for `score_kind="chordal"`. Add a chordal dispatch path that reads from `chords[]` instead. Frontend `exercise_definition.js` early-returns inside the chordal block before harmonization logic can run; add harmonization handling before that return.

**Tech Stack:** Python/Django (targets.py), vanilla JS (exercise_definition.js), pytest

---

## Files Modified

| File | Change |
|------|--------|
| `apps/exercises/harmonization/targets.py` | Add `_CHROMATIC_NAMES`, `_chord_bass_payload()`, `_build_targets_from_chordal_umto()`, dispatch in `build_targets_from_umto` |
| `apps/exercises/tests/test_harmonization_targets.py` | Add chordal-path tests |
| `lab/static/js/src/models/exercise_definition.js` | Add harmonization block before early return at line 992 |

---

## Background: Data shapes

**ChordEvent dict** (serialized from `ChordEvent` Pydantic model, `umto.py:51`):
```python
{
    "offset": 0.0,       # quarter-lengths from start
    "duration": 1.0,     # quarter-lengths
    "visible": [48, 52, 55],  # MIDI pitches sounding (list of int)
    "hidden": [],
    "spelling": ["C", "E", "G"]  # Optional; positional: visible then hidden; may be None
}
```
Bass = `min(visible)`. `spelling[index_of_bass_in_visible]` when spelling is present.

**AnalysisSlice dict** (same format used by existing voices path — `_analysis_for_target_offset` works unchanged for chordal).

**generate_harmonization command** (`apps/exercises/management/commands/generate_harmonization.py`):
- Run: `python manage.py generate_harmonization --source <exercise_id> --author <email>`
- Calls `build_targets_from_umto(umto)` → saves result as `data["harmonizationTargets"]`
- After Bug 1 is fixed, this command will work for chordal source exercises.

---

## Task 1: Backend — chordal path in build_targets_from_umto

**Files:**
- Modify: `apps/exercises/harmonization/targets.py`
- Test: `apps/exercises/tests/test_harmonization_targets.py`

### Step 1.1: Write the failing tests

Add to `apps/exercises/tests/test_harmonization_targets.py`:

```python
# --- Chordal UMTO tests ---

def _chordal_umto(chords, analysis, *, key="C", locked_voices=None, voice_count_policy=None):
    """Helper: build a minimal chordal UMTO dict for testing."""
    return {
        "metadata": {
            "key": key,
            "score_kind": "chordal",
            "locked_voices": locked_voices or ["B"],
            "voice_count_policy": voice_count_policy or {"expected": 4, "min": 3, "max": 4},
        },
        "voices": {"S": [], "A": [], "T": [], "B": []},
        "chords": chords,
        "analysis": analysis,
        "grading": [],
    }


def _analysis_slice(offset, *, local_key="C", figured_bass="5/3", raw_figured_bass="5/3"):
    return {
        "offset": offset,
        "content": {
            "figured_bass": figured_bass,
            "raw_figured_bass": raw_figured_bass,
            "local_key": local_key,
            "roman_numeral": None,
            "raw_roman_numeral": None,
            "pop_symbol": None,
            "functional_label": None,
        },
    }


def test_chordal_umto_produces_targets_from_chords():
    # C major triad in root position: C3=48 is bass, E3=52 and G3=55 are upper
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": [], "spelling": ["C", "E", "G"]}],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    t = targets[0]
    assert t["bassMidi"] == 48
    assert t["bassPc"] == 0
    assert t["bassSpelling"] == "C"
    assert t["lockedVoices"]["B"]["midi"] == 48
    assert t["lockedVoices"]["B"]["pc"] == 0
    assert 7 in t["allowedPcs"]   # G
    assert 4 in t["allowedPcs"]   # E
    assert t["voiceCountPolicy"] == {"expected": 4, "min": 3, "max": 4}


def test_chordal_umto_bass_is_lowest_midi():
    # G2=43 lowest; E3=52 and G3=55 above; spelling has bass at correct index
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [52, 43, 55], "hidden": [], "spelling": ["E", "G", "G"]}],
        analysis=[_analysis_slice(0.0, local_key="G", figured_bass="6/3", raw_figured_bass="6/3")],
        key="G",
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    # bass is 43 (G2), spelling index 1 → "G"
    assert targets[0]["bassMidi"] == 43
    assert targets[0]["bassPc"] == 7
    assert targets[0]["bassSpelling"] == "G"


def test_chordal_umto_spelling_fallback_when_none():
    # No spelling provided — should fall back to chromatic MIDI name
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": []}],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["bassSpelling"] == "C"   # MIDI 48 % 12 = 0 → "C"


def test_chordal_umto_skips_chord_with_no_matching_analysis():
    # Two chords, only one has a matching analysis slice
    umto = _chordal_umto(
        chords=[
            {"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": [], "spelling": ["C", "E", "G"]},
            {"offset": 1.0, "duration": 1.0, "visible": [43, 47, 50], "hidden": [], "spelling": ["G", "B", "D"]},
        ],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
        # No analysis slice for offset 1.0
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["offset"] == 0.0


def test_chordal_umto_skips_empty_chord():
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [], "hidden": []}],
        analysis=[_analysis_slice(0.0)],
    )
    targets = build_targets_from_umto(umto)
    assert targets == []


def test_chordal_umto_single_note_chord_bass_only():
    # Only 1 visible note = bass only, no upper voices required
    umto = _chordal_umto(
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [48], "hidden": [], "spelling": ["C"]}],
        analysis=[_analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3")],
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 1
    assert targets[0]["bassMidi"] == 48
    assert targets[0]["lockedVoices"]["B"]["midi"] == 48


def test_chordal_umto_multiple_chords_produce_multiple_targets():
    umto = _chordal_umto(
        chords=[
            {"offset": 0.0, "duration": 1.0, "visible": [48, 52, 55], "hidden": [], "spelling": ["C", "E", "G"]},
            {"offset": 1.0, "duration": 1.0, "visible": [43, 47, 50], "hidden": [], "spelling": ["G", "B", "D"]},
        ],
        analysis=[
            _analysis_slice(0.0, local_key="C", figured_bass="5/3", raw_figured_bass="5/3"),
            _analysis_slice(1.0, local_key="G", figured_bass="5/3", raw_figured_bass="5/3"),
        ],
        key="C",
    )
    targets = build_targets_from_umto(umto)
    assert len(targets) == 2
    assert targets[0]["bassMidi"] == 48
    assert targets[1]["bassMidi"] == 43
```

- [ ] **Step 1.1: Add the tests above to `apps/exercises/tests/test_harmonization_targets.py`** (after the existing `test_local_key_overrides_metadata_key` test at line 274)

- [ ] **Step 1.2: Run tests to confirm they all fail**

```bash
python manage.py test apps.exercises.tests.test_harmonization_targets --settings=harmony.settings.local -v 2 2>&1 | grep -E "(FAIL|ERROR|test_chordal)"
```

Expected: all 7 new `test_chordal_*` tests FAIL (targets returns [] for chordal UMTO).

- [ ] **Step 1.3: Implement the chordal path in targets.py**

Add the following to `apps/exercises/harmonization/targets.py`. Insert `_CHROMATIC_NAMES` and `_chord_bass_payload` before `build_targets_from_umto` (around line 138). Add `_build_targets_from_chordal_umto` after them.

```python
_CHROMATIC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _chord_bass_payload(chord: dict[str, Any]) -> dict[str, Any] | None:
    """Derive bass payload from a ChordEvent dict (chordal UMTO).

    Bass is the lowest MIDI in visible[]. spelling (when present) is positional
    over visible+hidden, so spelling[visible.index(bass_midi)] names the bass.
    """
    visible = chord.get("visible") or []
    if not visible:
        return None
    bass_midi = min(visible)
    spelling_list = chord.get("spelling")
    if spelling_list:
        bass_idx = visible.index(bass_midi)
        name = (
            spelling_list[bass_idx]
            if bass_idx < len(spelling_list)
            else _CHROMATIC_NAMES[bass_midi % 12]
        )
    else:
        name = _CHROMATIC_NAMES[bass_midi % 12]
    return {
        "midi": bass_midi,
        "pc": bass_midi % 12,
        "spelling": name,
    }


def _build_targets_from_chordal_umto(umto: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = umto.get("metadata", {})
    key_name = metadata.get("key") or "C"
    locked_voices: list[str] = metadata.get("locked_voices") or ["B"]
    vcp = metadata.get("voice_count_policy") or {}
    voice_count_policy = {
        "expected": vcp.get("expected"),
        "min": vcp.get("min", 3),
        "max": vcp.get("max", 4),
    }

    chords = umto.get("chords") or []
    analyses = list(umto.get("analysis", []))
    grading_pcs_by_offset = _grading_pcs_by_offset(umto)
    used_analysis_indexes: set[int] = set()
    targets = []

    for chord in chords:
        offset = round(float(chord.get("offset", 0)), 5)
        bass = _chord_bass_payload(chord)
        if bass is None:
            continue

        analysis_idx, analysis = _analysis_for_target_offset(
            analyses=analyses,
            used_analysis_indexes=used_analysis_indexes,
            offset=offset,
            key_name=key_name,
            bass=bass,
            grading_pcs=grading_pcs_by_offset.get(offset, set()),
        )
        if analysis_idx is None or analysis is None:
            continue
        used_analysis_indexes.add(analysis_idx)

        content = analysis.get("content", {})
        raw_figure = content.get("raw_figured_bass") or content.get("figured_bass") or "5/3"
        display_figure = content.get("figured_bass") or raw_figure
        local_key = content.get("local_key") or key_name

        derived = derive_required_notes(
            key_name=local_key,
            bass_name=bass["spelling"],
            figure=raw_figure,
        )

        locked: dict[str, Any] = {}
        if "B" in locked_voices:
            locked["B"] = bass

        targets.append({
            "offset": offset,
            "bassMidi": bass["midi"],
            "bassPc": bass["pc"],
            "bassSpelling": bass["spelling"],
            "figures": expand_figure_string(raw_figure),
            "displayFigure": display_figure,
            "requiredUpperPcs": derived["required_upper_pcs"],
            "requiredNoteNames": derived["required_note_names"],
            "allowedPcs": derived["allowed_pcs"],
            "lockedVoices": locked,
            "voiceCountPolicy": voice_count_policy,
            "source": {
                "kind": "analysis_slice",
                "label": display_figure or content.get("roman_numeral") or "",
                "key": local_key,
            },
        })

    return targets
```

Then add the dispatch at the top of `build_targets_from_umto`, right after `metadata = umto.get("metadata", {})`:

```python
def build_targets_from_umto(umto: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = umto.get("metadata", {})
    if metadata.get("score_kind") == "chordal":
        return _build_targets_from_chordal_umto(umto)

    key_name = metadata.get("key") or "C"
    # ... rest of existing function unchanged
```

- [ ] **Step 1.4: Run tests to confirm they all pass**

```bash
python manage.py test apps.exercises.tests.test_harmonization_targets --settings=harmony.settings.local -v 2
```

Expected: All tests pass (existing 6 + new 7 = 13 total).

- [ ] **Step 1.5: Commit**

```bash
git add apps/exercises/harmonization/targets.py apps/exercises/tests/test_harmonization_targets.py
git commit -m "fix(harmonization): add chordal path to build_targets_from_umto

Chordal UMTO stores note data in chords[] not voices.B.
Detect score_kind=chordal and dispatch to _build_targets_from_chordal_umto,
which derives bass from min(chord.visible) and matches analysis slices
by offset. Chords with no matching slice are skipped (not an error)."
```

---

## Task 2: Frontend — harmonization handling inside chordal block

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js` lines 987–992

### Context

Current code at lines 986–992 (after the `if (chordalIsIdent)` block closes):

```javascript
            exercise.complexity_score = definition.complexity_score || 0;
            exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
            exercise.playlistTags = definition.playlistTags || [];
            exercise.playlistSkillTags = definition.playlistSkillTags || [];
            exercise.skill_tags = definition.skillTags || [];
            return exercise;  // ← harmonizationTargets never read for chordal
```

The non-chordal harmonization path (lines 994–1006) that correctly reads `definition.harmonizationTargets` is never reached for chordal UMTO exercises.

- [ ] **Step 2.1: Apply the fix**

In `lab/static/js/src/models/exercise_definition.js`, replace the block at lines 987–992:

Find this exact string:
```javascript
            exercise.complexity_score = definition.complexity_score || 0;
            exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
            exercise.playlistTags = definition.playlistTags || [];
            exercise.playlistSkillTags = definition.playlistSkillTags || [];
            exercise.skill_tags = definition.skillTags || [];
            return exercise;
```

Replace with:
```javascript
            exercise.complexity_score = definition.complexity_score || 0;
            exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
            exercise.playlistTags = definition.playlistTags || [];
            exercise.playlistSkillTags = definition.playlistSkillTags || [];
            exercise.skill_tags = definition.skillTags || [];
            if (exercise.mode === "harmonization") {
              exercise.harmonizationTargets = definition.harmonizationTargets || [];
              exercise.problems = exercise.harmonizationTargets;
              exercise.analysis = { enabled: true, mode: {} };
              if (exercise.analysisType === "figured_bass") {
                exercise.analysis.mode.thoroughbass = true;
              } else {
                exercise.analysis.mode.roman_numerals = true;
              }
            }
            return exercise;
```

- [ ] **Step 2.2: Verify the fix doesn't break identification mode**

Search the file to confirm the `chordalIsIdent` block still handles identification before the new `if (exercise.mode === "harmonization")` — it does, because identification sets `exercise.problems` inside its own block (lines 937–985) and the new block only runs for `mode === "harmonization"`.

Quick grep check:
```bash
grep -n "chordalIsIdent\|harmonization\|return exercise" lab/static/js/src/models/exercise_definition.js | head -20
```

Expected output includes:
- Line ~928: `var chordalIsIdent = ...`
- Line ~929: `if (chordalIsIdent) {`
- Line ~986: closing `}`
- New lines: `if (exercise.mode === "harmonization") {`
- Line ~993+: `return exercise;`

- [ ] **Step 2.3: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "fix(exercise_definition): handle harmonization mode in chordal UMTO block

The chordal isChordalUMTO block returned early before
harmonizationTargets could be read. Add harmonization check
before the return so exercise.problems is populated from
definition.harmonizationTargets when mode === 'harmonization'."
```

---

## Task 3: End-to-end verification

This is manual — no automated test for the generate_harmonization command against a live DB.

- [ ] **Step 3.1: Find or create a chordal UMTO source exercise**

```bash
python manage.py shell --settings=harmony.settings.local -c "
from apps.exercises.models import Exercise
import json
qs = Exercise.objects.filter(data__type='umto_chorale')
for ex in qs[:20]:
    umto = ex.data.get('score', {}).get('umto', {})
    if umto.get('metadata', {}).get('score_kind') == 'chordal':
        print(ex.id, ex.description[:60])
"
```

- [ ] **Step 3.2: Run generate_harmonization on a chordal source**

```bash
python manage.py generate_harmonization \
  --source <source_exercise_id> \
  --author <your_email> \
  --settings=harmony.settings.local
```

Expected: `Created <new_exercise_id>` (previously raised `CommandError: produced zero targets`).

- [ ] **Step 3.3: Confirm harmonizationTargets written**

```bash
python manage.py shell --settings=harmony.settings.local -c "
from apps.exercises.models import Exercise
ex = Exercise.objects.get(id='<new_exercise_id>')
targets = ex.data.get('harmonizationTargets', [])
print(f'{len(targets)} targets')
if targets: print(targets[0])
"
```

Expected: `N targets` with at least 1 target showing bassMidi, figures, etc.

- [ ] **Step 3.4: Open exercise in teacher/play and set mode=harmonization**

Use the existing teacher/play UI or direct URL. Set exercise mode to "harmonization" in the playlist/exercise config. Load the exercise in the student player.

Expected: harmonization problems are shown (bass locked, upper voices to fill in). Previously: exercise loaded with empty problems because JS returned early.

---

## Self-Review Checklist

**Spec coverage:**
- [x] Bug 1 backend fix: `_build_targets_from_chordal_umto` added with dispatch in `build_targets_from_umto`
- [x] Edge cases: empty chords list, chord with no visible notes, chord with no matching analysis slice, single-note chord, spelling fallback
- [x] Bug 2 frontend fix: harmonization handling added before early return
- [x] Tests for chordal path: 7 new tests in `test_harmonization_targets.py`
- [x] E2E verification: `generate_harmonization` command + teacher/play smoke test
- [x] No scope creep: no new API endpoints, no save flow changes, no pipeline redesign

**Type consistency:** `_chord_bass_payload` returns `{midi: int, pc: int, spelling: str}` — same shape as `_locked_voice_payload`. `_build_targets_from_chordal_umto` uses `locked["B"] = bass` (same "B" key as existing targets). `_analysis_for_target_offset` is reused unchanged.

**Placeholder scan:** None found.
