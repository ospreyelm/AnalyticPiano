# Teacher Workbench Chordal Analysis Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate, review, persist, and project editable chordal UMTO analysis from Teacher Workbench.

**Architecture:** Keep chordal analysis canonical in `score.umto.analysis[]`, using HarmonyLab's figured-bass and Roman analyzer helpers as the primary label source and music21 only as fallback. Add small backend helpers for analysis generation/review/projection, expose two Workbench API endpoints, and keep the Workbench UI as a compact editor around existing recent-import rows.

**Tech Stack:** Django, Django TestCase, music21, Pydantic UMTO models, vanilla JavaScript in the existing Workbench template.

---

## File Structure

- Modify: `apps/exercises/umto.py` — add explicit `Metadata.analysis_review_status`.
- Modify: `apps/exercises/umto_factory.py` — let chordal payload builder accept review status and keep top-level `analysis` synchronized.
- Modify: `apps/exercises/utils/umto_import_router.py` — add HarmonyLab-first chordal analysis generation.
- Modify: `apps/exercises/management/commands/import_musicxml.py` — populate chordal analysis during import.
- Modify: `apps/exercises/tests/test_umto_import_router.py` — analyzer/import tests.
- Modify: `apps/dashboard/views/api_workbench.py` — review fetch/save APIs and reviewed chordal projection.
- Modify: `apps/dashboard/urls.py` — route review API endpoint.
- Modify: `apps/dashboard/templates/dashboard/workbench.html` — review button/editor and projection enablement.
- Modify: `apps/dashboard/tests/test_workbench_router_wiring.py` — review/projection API coverage.
- Modify: `docs/UMTO_GUIDE.md` — document chordal analysis review status and projections.

## Task 1: UMTO Review Status Contract

**Files:**
- Modify: `apps/exercises/umto.py`
- Modify: `apps/exercises/umto_factory.py`
- Test: `apps/exercises/tests/test_umto_contract.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `apps/exercises/tests/test_umto_contract.py`:

```python
from apps.exercises.umto import Metadata, InteractionMode
from apps.exercises.umto_factory import build_chordal_umto_payload


def test_metadata_accepts_analysis_review_status():
    meta = Metadata(
        exercise_id="TEMP",
        source="Chordal import",
        key="jC_",
        meter="4/4",
        complexity_score=1,
        mode=InteractionMode.PLAYBACK,
        score_kind="chordal",
        analysis_review_status="generated",
    )

    assert meta.analysis_review_status == "generated"


def test_chordal_payload_stores_review_status_and_top_level_analysis():
    analysis = [{
        "offset": 0.0,
        "content": {
            "roman_numeral": "I",
            "raw_roman_numeral": "I",
            "local_key": "jC_",
            "raw_figured_bass": "8/5/3",
            "figured_bass": "5/3",
        },
        "is_target": True,
    }]

    payload = build_chordal_umto_payload(
        exercise_id="TEMP",
        source="Chordal import",
        key="jC_",
        meter="4/4",
        clef="keyboard",
        complexity_score=1,
        mode=InteractionMode.PLAYBACK,
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
        analysis=analysis,
        analysis_review_status="generated",
    )

    metadata = payload["score"]["umto"]["metadata"]
    assert metadata["analysis_review_status"] == "generated"
    assert payload["analysis"] == payload["score"]["umto"]["analysis"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_contract -v 2`

Expected: failure because `Metadata` and `build_chordal_umto_payload()` do not accept `analysis_review_status`.

- [ ] **Step 3: Implement the contract**

In `apps/exercises/umto.py`, add the field to `Metadata`:

```python
analysis_review_status: Literal["none", "generated", "reviewed"] = "none"
```

In `apps/exercises/umto_factory.py`, update `build_chordal_umto_payload()`:

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
) -> dict:
```

Pass the value into `Metadata(...)`:

```python
analysis_review_status=analysis_review_status,
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_contract -v 2`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_factory.py apps/exercises/tests/test_umto_contract.py
git commit -m "feat: add chordal analysis review status"
```

## Task 2: HarmonyLab-First Chordal Analysis Generation

**Files:**
- Modify: `apps/exercises/utils/umto_import_router.py`
- Modify: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write the failing tests**

Add imports:

```python
from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices
```

Add tests:

```python
class ChordalAnalysisGenerationTests(unittest.TestCase):
    def test_build_chordal_analysis_uses_harmonylab_figured_bass(self):
        chords = [{
            "offset": 0.0,
            "duration": 1.0,
            "visible": [60, 64, 67],
            "spelling": ["C4", "E4", "G4"],
        }]

        analysis = build_chordal_analysis_slices(chords, harmony_key="jC_")

        self.assertEqual(analysis[0]["offset"], 0.0)
        self.assertEqual(analysis[0]["content"]["raw_figured_bass"], "8/5/3")
        self.assertEqual(analysis[0]["content"]["figured_bass"], "5/3")

    def test_build_chordal_analysis_prefers_legacy_roman_table(self):
        chords = [{
            "offset": 0.0,
            "duration": 1.0,
            "visible": [60, 64, 67],
            "spelling": ["C4", "E4", "G4"],
        }]

        analysis = build_chordal_analysis_slices(chords, harmony_key="jC_")

        self.assertEqual(analysis[0]["content"]["roman_numeral"], "I")
        self.assertEqual(analysis[0]["content"]["local_key"], "jC_")

    def test_build_chordal_analysis_falls_back_to_music21_roman(self):
        chords = [{
            "offset": 0.0,
            "duration": 1.0,
            "visible": [61, 64, 68],
            "spelling": ["C#4", "E4", "G#4"],
        }]

        with patch("apps.exercises.utils.umto_import_router.legacy_roman_from_pitches") as legacy:
            legacy.return_value.normalized_label = ""
            legacy.return_value.label = ""
            analysis = build_chordal_analysis_slices(chords, harmony_key="jC_")

        self.assertTrue(analysis[0]["content"]["roman_numeral"])
        self.assertEqual(analysis[0]["content"]["local_key"], "jC_")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_import_router -v 2`

Expected: failure because `build_chordal_analysis_slices` does not exist.

- [ ] **Step 3: Implement analysis generation**

In `apps/exercises/utils/umto_import_router.py`, add helpers:

```python
from music21 import chord as m21_chord
from music21 import key as m21_key
from music21 import pitch as m21_pitch
from music21 import roman as m21_roman

from apps.exercises.utils.figured_bass import compute_figured_bass
from apps.exercises.utils.legacy_roman import legacy_roman_from_pitches
```

Add key conversion:

```python
def _harmony_key_to_tonic_mode(harmony_key: str) -> tuple[str, str]:
    text = (harmony_key or "jC_").strip()
    if text and text[0] in {"i", "j"}:
        tonic = text[1:].replace("_", "").replace("b", "-") or "C"
        mode = "minor" if text[0] == "i" else "major"
        return tonic, mode
    return text.replace("b", "-") or "C", "major"
```

Add chord construction and slice generation:

```python
def _pitches_for_chord_event(chord_event: dict) -> list:
    spellings = chord_event.get("spelling") or []
    if spellings:
        return [m21_pitch.Pitch(str(name).replace("b", "-")) for name in spellings]
    return [m21_pitch.Pitch(midi=int(midi)) for midi in chord_event.get("visible", []) + chord_event.get("hidden", [])]


def build_chordal_analysis_slices(chords: list[dict], *, harmony_key: str) -> list[dict]:
    tonic, mode = _harmony_key_to_tonic_mode(harmony_key)
    tonal_key = m21_key.Key(tonic, mode)
    analysis = []
    for chord_event in chords:
        pitches = _pitches_for_chord_event(chord_event)
        if not pitches:
            continue
        chord_obj = m21_chord.Chord(pitches)
        raw_fb, figured_bass = compute_figured_bass(chord_obj, tonal_key)
        legacy = legacy_roman_from_pitches(sorted(chord_obj.pitches, key=lambda p: p.midi), tonic.replace("-", "b"), mode)
        roman_label = legacy.normalized_label
        raw_roman = legacy.label or legacy.normalized_label
        if not roman_label:
            try:
                rn = m21_roman.romanNumeralFromChord(chord_obj, tonal_key)
                roman_label = rn.figure
                raw_roman = rn.figure
            except Exception:
                roman_label = None
                raw_roman = raw_roman or None
        analysis.append({
            "offset": float(chord_event.get("offset", 0.0)),
            "content": {
                "roman_numeral": roman_label,
                "raw_roman_numeral": raw_roman,
                "local_key": harmony_key,
                "raw_figured_bass": raw_fb,
                "figured_bass": figured_bass,
            },
            "unit_tags": [],
            "is_target": True,
        })
    return analysis
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_import_router -v 2`

Expected: all router tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/utils/umto_import_router.py apps/exercises/tests/test_umto_import_router.py
git commit -m "feat: generate chordal import analysis"
```

## Task 3: MusicXML Import Stores Generated Analysis

**Files:**
- Modify: `apps/exercises/management/commands/import_musicxml.py`
- Modify: `apps/exercises/tests/test_umto_import_router.py`

- [ ] **Step 1: Write the failing test**

In `ImportMusicXMLRoutingTests`, update the chordal payload test:

```python
    def test_build_import_payload_for_score_builds_chordal_payload_with_generated_analysis(self):
        score = stream.Score()
        part = stream.Part()
        measure = stream.Measure(number=1)
        measure.append(chord.Chord(["C4", "E4", "G4"], quarterLength=1.0))
        part.append(measure)
        score.append(part)

        result = _build_import_payload_for_score(
            score,
            title="chords",
            harmony_key="jC_",
            start_measure=0,
            end_measure=None,
            complexity=1,
        )

        umto = result.payload["score"]["umto"]
        self.assertEqual(umto["metadata"]["score_kind"], "chordal")
        self.assertEqual(umto["metadata"]["analysis_review_status"], "generated")
        self.assertEqual(umto["analysis"][0]["content"]["roman_numeral"], "I")
        self.assertEqual(umto["analysis"][0]["content"]["figured_bass"], "5/3")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_import_router.ImportMusicXMLRoutingTests -v 2`

Expected: failure because chordal import still passes `analysis=[]` and no review status.

- [ ] **Step 3: Implement import integration**

In `apps/exercises/management/commands/import_musicxml.py`, import `build_chordal_analysis_slices` and update the chordal route:

```python
analysis = build_chordal_analysis_slices(chords, harmony_key=harmony_key)
review_status = "generated" if analysis else "none"
payload = build_chordal_umto_payload(
    exercise_id="TEMP",
    source=f"Play {title}.",
    key=harmony_key,
    meter=meter,
    clef="keyboard",
    complexity_score=complexity,
    mode=InteractionMode.PLAYBACK,
    chords=chords,
    analysis=analysis,
    analysis_review_status=review_status,
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_import_router.ImportMusicXMLRoutingTests -v 2`

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/import_musicxml.py apps/exercises/tests/test_umto_import_router.py
git commit -m "feat: store generated chordal analysis on import"
```

## Task 4: Workbench Review Fetch and Save APIs

**Files:**
- Modify: `apps/dashboard/views/api_workbench.py`
- Modify: `apps/dashboard/urls.py`
- Modify: `apps/dashboard/tests/test_workbench_router_wiring.py`

- [ ] **Step 1: Write failing API tests**

Add tests:

```python
    def test_chordal_analysis_review_fetch_returns_rows(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "spelling": ["C4", "E4", "G4"]}],
            analysis=[{"offset": 0.0, "content": {"roman_numeral": "I", "figured_bass": "5/3"}, "is_target": True}],
            analysis_review_status="generated",
        )
        chordal = Exercise.objects.create(description="Chordal upload", data=payload, authored_by=self.user, complexity=1)

        response = self.client.get(reverse("dashboard:api-chordal-analysis-review", args=[chordal.id]))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["reviewStatus"], "generated")
        self.assertEqual(body["rows"][0]["visible"], [60, 64, 67])
        self.assertEqual(body["rows"][0]["content"]["roman_numeral"], "I")

    def test_chordal_analysis_review_save_persists_reviewed_analysis(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis_review_status="generated",
        )
        chordal = Exercise.objects.create(description="Chordal upload", data=payload, authored_by=self.user, complexity=1)

        response = self.client.post(
            reverse("dashboard:api-chordal-analysis-review", args=[chordal.id]),
            data=json.dumps({"rows": [{"offset": 0.0, "content": {"roman_numeral": "I6", "figured_bass": "6"}}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        chordal.refresh_from_db()
        umto = chordal.data["score"]["umto"]
        self.assertEqual(umto["metadata"]["analysis_review_status"], "reviewed")
        self.assertEqual(umto["analysis"][0]["content"]["roman_numeral"], "I6")
        self.assertEqual(chordal.data["analysis"], umto["analysis"])

    def test_chordal_analysis_review_save_rejects_unknown_offsets(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
        )
        chordal = Exercise.objects.create(description="Chordal upload", data=payload, authored_by=self.user, complexity=1)

        response = self.client.post(
            reverse("dashboard:api-chordal-analysis-review", args=[chordal.id]),
            data=json.dumps({"rows": [{"offset": 1.0, "content": {"roman_numeral": "V"}}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("offset", response.json()["error"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring -v 2`

Expected: failure because URL/view does not exist.

- [ ] **Step 3: Implement fetch/save views**

In `apps/dashboard/views/api_workbench.py`, import `AnalysisSlice` and add helpers:

```python
from apps.exercises.umto import AnalysisSlice, InteractionMode
```

Add view:

```python
@login_required
@csrf_exempt
def api_chordal_analysis_review(request, exercise_id):
    try:
        exercise = Exercise.objects.get(id=exercise_id, authored_by=request.user)
    except Exercise.DoesNotExist:
        return JsonResponse({"error": "Exercise not found"}, status=404)
    if _score_kind(exercise) != "chordal":
        return JsonResponse({"error": "Analysis review is only available for chordal UMTO imports."}, status=400)

    data = _copy.deepcopy(exercise.data or {})
    umto = data.get("score", {}).get("umto", {})
    metadata = umto.get("metadata", {})
    chords = umto.get("chords", [])

    if request.method == "GET":
        analysis_by_offset = {round(float(a.get("offset", 0.0)), 6): a for a in umto.get("analysis", [])}
        rows = []
        for chord in chords:
            offset = round(float(chord.get("offset", 0.0)), 6)
            rows.append({
                "offset": offset,
                "duration": chord.get("duration"),
                "visible": chord.get("visible", []),
                "hidden": chord.get("hidden", []),
                "spelling": chord.get("spelling", []),
                "content": (analysis_by_offset.get(offset) or {}).get("content", {}),
            })
        return JsonResponse({
            "exerciseId": exercise.id,
            "description": exercise.description,
            "scoreKind": "chordal",
            "reviewStatus": metadata.get("analysis_review_status", "none"),
            "rows": rows,
        })

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json.loads(request.body or "{}")
    valid_offsets = {round(float(c.get("offset", 0.0)), 6) for c in chords}
    new_analysis = []
    for row in payload.get("rows", []):
        offset = round(float(row.get("offset", 0.0)), 6)
        if offset not in valid_offsets:
            return JsonResponse({"error": f"Unknown chord offset: {offset}"}, status=400)
        slice_data = {
            "offset": offset,
            "content": row.get("content", {}),
            "unit_tags": row.get("unit_tags", []),
            "is_target": True,
        }
        new_analysis.append(AnalysisSlice(**slice_data).model_dump(mode="json"))

    metadata["analysis_review_status"] = "reviewed"
    umto["analysis"] = new_analysis
    data["analysis"] = new_analysis
    exercise.data = data
    exercise.save(update_fields=["data"])
    return JsonResponse({"status": "success", "reviewStatus": "reviewed", "analysis": new_analysis})
```

In `apps/dashboard/urls.py`, import the view and add:

```python
path("api/workbench/chordal-analysis/<str:exercise_id>/", api_chordal_analysis_review, name="api-chordal-analysis-review"),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring -v 2`

Expected: all Workbench tests pass or fail only on projection behavior covered by later tasks.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/views/api_workbench.py apps/dashboard/urls.py apps/dashboard/tests/test_workbench_router_wiring.py
git commit -m "feat: add chordal analysis review API"
```

## Task 5: Reviewed Chordal Projection Backend

**Files:**
- Modify: `apps/dashboard/views/api_workbench.py`
- Modify: `apps/dashboard/tests/test_workbench_router_wiring.py`

- [ ] **Step 1: Write failing projection tests**

Replace the existing chordal unsupported-projection test with:

```python
    def test_chordal_import_rejects_unreviewed_analysis_projection(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis=[{"offset": 0.0, "content": {"roman_numeral": "I"}, "is_target": True}],
            analysis_review_status="generated",
        )
        chordal = Exercise.objects.create(description="Chordal upload", data=payload, authored_by=self.user, complexity=1)

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({"source_ids": [chordal.id], "target_type": "roman_numeral"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("review", response.json()["error"].lower())
```

Add reviewed projection and mixed-selection tests:

```python
    def test_reviewed_chordal_roman_projection_creates_identification_clone(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis=[{"offset": 0.0, "content": {"roman_numeral": "I", "figured_bass": "5/3"}, "is_target": True}],
            analysis_review_status="reviewed",
        )
        chordal = Exercise.objects.create(description="Chordal upload", data=payload, authored_by=self.user, complexity=1)

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({"source_ids": [chordal.id], "target_type": "roman_numeral"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        created = Exercise.objects.get(id=response.json()["created_exercises"][0])
        self.assertEqual(created.data["score"]["umto"]["metadata"]["score_kind"], "chordal")
        self.assertEqual(created.data["score"]["umto"]["metadata"]["mode"], "identification")
        self.assertEqual(created.data["analysisType"], "roman")
        self.assertEqual(created.data["score"]["umto"]["analysis"][0]["content"]["roman_numeral"], "I")

    def test_mixed_chordal_and_voices_projection_is_rejected(self):
        voices = make_umto_exercise(self.user, description="Voices", complexity=3, mode=InteractionMode.PLAYBACK)
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Chordal upload",
            key="jC_",
            meter="4/4",
            clef="keyboard",
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis_review_status="reviewed",
        )
        chordal = Exercise.objects.create(description="Chordal upload", data=payload, authored_by=self.user, complexity=1)

        response = self.client.post(
            reverse("dashboard:api-multiply-projection"),
            data=json.dumps({"source_ids": [voices.id, chordal.id], "target_type": "roman_numeral"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("mixed", response.json()["error"].lower())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring -v 2`

Expected: failure because chordal analysis projection is still blocked or not review-gated.

- [ ] **Step 3: Implement projection helpers**

In `apps/dashboard/views/api_workbench.py`, add:

```python
CHORDAL_ANALYSIS_TARGETS = {"roman_numeral", "figured_bass", "analysis_match", "identification"}


def _analysis_review_status(exercise):
    return (
        (exercise.data or {})
        .get("score", {})
        .get("umto", {})
        .get("metadata", {})
        .get("analysis_review_status", "none")
    )


def _clone_chordal_projection(base_ex, author, target_type):
    data = _copy.deepcopy(base_ex.data)
    metadata = data["score"]["umto"]["metadata"]
    metadata["exercise_id"] = "TEMP"
    if target_type == "analysis_match":
        mode = InteractionMode.ANALYSIS_MATCH
    else:
        mode = InteractionMode.IDENTIFICATION if target_type != "exact_match" else InteractionMode.PLAYBACK
    metadata["mode"] = mode.value
    data["mode"] = mode.value
    analysis_type_map = {
        "roman_numeral": "roman",
        "figured_bass": "figured_bass",
        "analysis_match": "roman",
        "identification": "note_name",
        "exact_match": data.get("analysisType", "roman"),
    }
    data["analysisType"] = analysis_type_map[target_type]
    suffix = f" ({target_type})"
    description = f"{(base_ex.description or base_ex.id)[:60 - len(suffix)]}{suffix}"
    new_ex = Exercise(
        description=description,
        data=data,
        authored_by=author,
        skill_tags=base_ex.skill_tags,
        complexity=base_ex.complexity,
        is_public=False,
        time_signature=metadata.get("meter", ""),
    )
    new_ex.save()
    new_ex.data["score"]["umto"]["metadata"]["exercise_id"] = new_ex.id
    new_ex.save(update_fields=["data"])
    return new_ex
```

Update `api_multiply_projection()` after loading `source_exercises`:

```python
chordal_sources = [ex for ex in source_exercises if _score_kind(ex) == "chordal"]
voices_sources = [ex for ex in source_exercises if _score_kind(ex) != "chordal"]
if chordal_sources and voices_sources:
    return JsonResponse({"error": "Mixed chordal and voices projections must be run separately."}, status=400)
if chordal_sources and target_type in CHORDAL_ANALYSIS_TARGETS:
    unreviewed = [ex.id for ex in chordal_sources if _analysis_review_status(ex) != "reviewed"]
    if unreviewed:
        return JsonResponse({"error": "Chordal analysis projections require reviewed analysis."}, status=400)
```

In the transaction loop, route chordal sources through `_clone_chordal_projection(...)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring -v 2`

Expected: all Workbench router tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/views/api_workbench.py apps/dashboard/tests/test_workbench_router_wiring.py
git commit -m "feat: project reviewed chordal analysis"
```

## Task 6: Workbench UI Review Editor

**Files:**
- Modify: `apps/dashboard/templates/dashboard/workbench.html`
- Modify: `apps/dashboard/tests/test_workbench_router_wiring.py`

- [ ] **Step 1: Write a template smoke test**

Add a test that asserts the Workbench includes the review endpoint hook and editor container:

```python
    def test_workbench_template_includes_chordal_review_editor(self):
        response = self.client.get(reverse("dashboard:workbench"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "analysisReviewPanel")
        self.assertContains(response, "openAnalysisReview")
        self.assertContains(response, "api/workbench/chordal-analysis")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring.WorkbenchRouterWiringTests.test_workbench_template_includes_chordal_review_editor -v 2`

Expected: failure because the template does not contain review UI.

- [ ] **Step 3: Implement template UI**

In `apps/dashboard/templates/dashboard/workbench.html`, add a panel below the grid:

```html
<div class="card analysis-review-panel" id="analysisReviewPanel" style="display: none;">
    <div class="card-header">
        <h3 id="analysisReviewTitle">Analysis Review</h3>
        <button class="btn btn-secondary" onclick="closeAnalysisReview()">Close</button>
    </div>
    <div class="card-body">
        <div id="analysisReviewRows"></div>
        <button class="btn btn-primary" onclick="saveAnalysisReview()" id="saveAnalysisReviewBtn">Save Review</button>
    </div>
</div>
```

In recent import rendering, include review status and a review button for chordal rows:

```javascript
const reviewStatus = item.analysisReviewStatus || 'none';
const reviewButton = scoreKind === 'chordal'
    ? `<button class="btn btn-secondary btn-small" onclick="openAnalysisReview('${item.id}')">Review</button>`
    : '';
```

Add functions:

```javascript
let activeReviewExerciseId = null;

window.openAnalysisReview = function(exerciseId) {
    activeReviewExerciseId = exerciseId;
    fetch(`/dashboard/api/workbench/chordal-analysis/${exerciseId}/`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('analysisReviewPanel').style.display = 'block';
            document.getElementById('analysisReviewTitle').textContent = `Analysis Review: ${data.description}`;
            const rows = data.rows.map(row => {
                const content = row.content || {};
                return `
                    <div class="analysis-review-row" data-offset="${row.offset}">
                        <div class="analysis-review-chord">${(row.spelling && row.spelling.length ? row.spelling : row.visible).join(' ')}</div>
                        <input data-field="roman_numeral" value="${content.roman_numeral || ''}" placeholder="Roman">
                        <input data-field="figured_bass" value="${content.figured_bass || ''}" placeholder="Figure">
                        <input data-field="raw_figured_bass" value="${content.raw_figured_bass || ''}" placeholder="Raw figure">
                        <input data-field="local_key" value="${content.local_key || ''}" placeholder="Local key">
                    </div>
                `;
            }).join('');
            document.getElementById('analysisReviewRows').innerHTML = rows;
        });
};

window.closeAnalysisReview = function() {
    activeReviewExerciseId = null;
    document.getElementById('analysisReviewPanel').style.display = 'none';
};

window.saveAnalysisReview = function() {
    if (!activeReviewExerciseId) return;
    const rows = Array.from(document.querySelectorAll('.analysis-review-row')).map(row => {
        const content = {};
        row.querySelectorAll('input[data-field]').forEach(input => {
            content[input.dataset.field] = input.value || null;
        });
        return {offset: parseFloat(row.dataset.offset), content};
    });
    fetch(`/dashboard/api/workbench/chordal-analysis/${activeReviewExerciseId}/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
        body: JSON.stringify({rows})
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert('Analysis review saved.', 'success');
            closeAnalysisReview();
            fetchImports();
        } else {
            showAlert(data.error || 'Failed to save analysis review.', 'error');
        }
    });
};
```

- [ ] **Step 4: Run the smoke test**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring.WorkbenchRouterWiringTests.test_workbench_template_includes_chordal_review_editor -v 2`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/templates/dashboard/workbench.html apps/dashboard/tests/test_workbench_router_wiring.py
git commit -m "feat: add chordal analysis review editor"
```

## Task 7: Recent Imports and Projection Button State

**Files:**
- Modify: `apps/dashboard/views/api_workbench.py`
- Modify: `apps/dashboard/templates/dashboard/workbench.html`
- Modify: `apps/dashboard/tests/test_workbench_router_wiring.py`

- [ ] **Step 1: Write failing tests**

Extend `test_recent_imports_exposes_umto_score_kind`:

```python
self.assertEqual(by_description["Chordal upload"]["analysisReviewStatus"], "none")
```

Add a reviewed chordal import in that test and assert:

```python
self.assertEqual(by_description["Reviewed chordal"]["analysisReviewStatus"], "reviewed")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring.WorkbenchRouterWiringTests.test_recent_imports_exposes_umto_score_kind -v 2`

Expected: failure because the API does not expose `analysisReviewStatus`.

- [ ] **Step 3: Expose status and update button logic**

In `api_recent_imports`, add:

```python
"analysisReviewStatus": metadata.get("analysis_review_status", "none"),
```

In `updateStatus()` in the template, allow chordal analysis buttons only when all selected chordal rows are reviewed and no selected voices rows are mixed with chordal rows:

```javascript
const selectedItems = Array.from(selectedIds).map(id => importMetaById[id]).filter(Boolean);
const hasChordal = selectedItems.some(item => item.scoreKind === 'chordal');
const hasVoices = selectedItems.some(item => item.scoreKind !== 'chordal');
const allChordalReviewed = selectedItems
    .filter(item => item.scoreKind === 'chordal')
    .every(item => item.analysisReviewStatus === 'reviewed');
actionBtns.forEach(btn => {
    if (!selectedItems.length || (hasChordal && hasVoices)) {
        btn.disabled = true;
    } else if (hasChordal) {
        btn.disabled = btn.id !== 'btn-exact' && !allChordalReviewed;
    } else {
        btn.disabled = false;
    }
});
```

- [ ] **Step 4: Run Workbench tests**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.dashboard.tests.test_workbench_router_wiring -v 2`

Expected: all Workbench tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/views/api_workbench.py apps/dashboard/templates/dashboard/workbench.html apps/dashboard/tests/test_workbench_router_wiring.py
git commit -m "feat: expose chordal analysis review state"
```

## Task 8: Documentation and Verification

**Files:**
- Modify: `docs/UMTO_GUIDE.md`

- [ ] **Step 1: Update UMTO guide**

Add a subsection under chordal UMTO documenting:

```markdown
### Chordal Analysis Review

Chordal imports may include analyzer-generated `analysis[]` slices aligned by
offset to `chords[]`. `metadata.analysis_review_status` records whether those
labels are `none`, `generated`, or `reviewed`.

Workbench analysis projections from chordal imports require `reviewed` status.
Exact Match playback can be cloned before review because it does not expose
analysis labels as answer keys.

Generated labels use HarmonyLab analyzer logic first:

- `compute_figured_bass()` for raw and abbreviated figured bass;
- `legacy_roman_from_pitches()` for Roman labels matching the browser analyzer;
- music21 Roman analysis only as fallback when HarmonyLab has no table label.
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_umto_contract apps.exercises.tests.test_umto_import_router apps.dashboard.tests.test_workbench_router_wiring -v 2
```

Expected: all focused tests pass.

- [ ] **Step 3: Run Django check**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py check
```

Expected: system check reports no issues.

- [ ] **Step 4: Commit**

```bash
git add docs/UMTO_GUIDE.md
git commit -m "docs: document chordal analysis review"
```

## Self-Review Checklist

- Spec coverage: Tasks cover import analysis generation, review persistence,
  Workbench UI, reviewed projection, mixed selection rejection, and docs.
- Placeholder scan: No task contains unresolved placeholder language.
- Type consistency: Review status values are `none`, `generated`, and
  `reviewed` across schema, API, UI, and tests.
