# Phase 3: Curation Workbench — Implementation Plan (SUPERSEDED)

> **⚠️ SUPERSEDED** — This monolithic plan was split into 6 focused plans after a Codex review identified blocking issues. Use the split plans instead:
> - [3A: Analysis Metadata Foundation](2026-06-13-phase3a-analysis-metadata-foundation.md)
> - [3B: Official Review Workflow](2026-06-13-phase3b-official-review-workflow.md)
> - [3C: Library Hub + Browse](2026-06-13-phase3c-library-hub-browse.md)
> - [3D: Playlist + Exercise Editors](2026-06-13-phase3d-playlist-exercise-editors.md)
> - [3E: Course Detail Replacement](2026-06-13-phase3e-course-detail-replacement.md)
> - [3F: VexFlow Thumbnails](2026-06-13-phase3f-vexflow-thumbnails.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy dashboard teacher workflows with modern `/teacher/library/` pages: content library, playlist/exercise editors, course settings/activity tabs, and an official-content review queue.

**Architecture:** New `apps/teacher/views_library.py` holds all library views (function-based, `@teacher_required`). Templates extend `teacher/base.html`. A new migration adds `official_review_status` to `Exercise` and `Playlist`. AnalysisLayer gets 7 new optional analytics fields; the JS save path and Python import path both compute them.

**Tech Stack:** Django 4.x, function-based views, `@teacher_required` decorator, Pydantic (`AnalysisLayer`), existing `analyze.js` exports, music21 for Python path, VexFlow for score thumbnails (lazy via Intersection Observer).

**Run tests with:**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests -v 2
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests -v 2
```

---

## File map

| File | Action | Purpose |
|---|---|---|
| `apps/exercises/umto.py` | Modify | Add 7 new optional fields to `AnalysisLayer` |
| `apps/exercises/migrations/NNNN_official_review_status.py` | Create | Add `official_review_status` to Exercise + Playlist |
| `apps/exercises/models.py` | Modify | Add `official_review_status` CharField to Exercise + Playlist |
| `apps/exercises/utils/umto_import_router.py` | Modify | Expand `build_chordal_analysis_slices` with set-class fields |
| `lab/static/js/src/components/music/play_save_logic.js` | Modify | Accept `deterministicFieldsArr` 5th arg, merge into slice content |
| `lab/static/js/src/components/music/play_sheet.js` | Modify | Compute `deterministicFieldsArr` before calling `buildAnalysisSlices`; add `analysisType` to save payload |
| `lab/views.py` | Modify | Read `exercise.data.get("analysisType")` before heuristic (~line 505) |
| `apps/teacher/views_library.py` | Create | All library hub, playlist/exercise editor, review, preview views |
| `apps/teacher/urls.py` | Modify | Register `/library/` routes |
| `apps/teacher/templates/teacher/base.html` | Modify | Add Library nav link |
| `apps/teacher/templates/teacher/library_hub.html` | Create | 3-tab library hub |
| `apps/teacher/templates/teacher/playlist_editor.html` | Create | Playlist editor |
| `apps/teacher/templates/teacher/exercise_editor.html` | Create | Exercise editor |
| `apps/teacher/templates/teacher/course_detail.html` | Modify | Add Settings + Activity tabs; remove dashboard escape hatches |
| `apps/teacher/views.py` | Modify | Add settings/activity tab data; remove dashboard URL construction |
| `apps/exercises/management/commands/backfill_analysis_layer.py` | Create | Backfill command |
| `apps/teacher/tests/test_library_views.py` | Create | Tests for all library views |

---

## Task 1: AnalysisLayer model expansion

**Files:**
- Modify: `apps/exercises/umto.py:75-83`

- [ ] **Add 7 new optional fields to `AnalysisLayer`**

In `apps/exercises/umto.py`, change:
```python
class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None
    local_key: Optional[str] = None
    raw_figured_bass: Optional[str] = None
    figured_bass: Optional[str] = None
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None
    scale_degrees: Optional[List[Dict[str, Any]]] = None
```
to:
```python
class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None
    local_key: Optional[str] = None
    raw_figured_bass: Optional[str] = None
    figured_bass: Optional[str] = None
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None
    scale_degrees: Optional[List[Dict[str, Any]]] = None
    # Analytics fields — computed at save time, not read by identification grader
    set_class_prime: Optional[str] = None
    set_class_forte: Optional[str] = None
    set_class_normal: Optional[str] = None
    set_class_set: Optional[str] = None
    spacing: Optional[str] = None
    interval_specific: Optional[str] = None
    interval_generic: Optional[str] = None
```

- [ ] **Regenerate UMTO schema**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py make_umto_schema
```
Expected: `apps/exercises/umto_schema.json` updated with new fields.

- [ ] **Run existing UMTO tests to confirm backward compat**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_chordal_umto -v 2
```
Expected: all pass (new fields are optional, default None).

- [ ] **Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_schema.json
git commit -m "feat: add 7 analytics fields to AnalysisLayer (set_class, spacing, intervals)"
```

---

## Task 2: `analysisType` serving boundary fix

**Files:**
- Modify: `lab/views.py:504-505`

- [ ] **Write failing test**

In `apps/teacher/tests/test_library_views.py` (create file):
```python
"""Tests for library views — Phase 3."""
import json
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Exercise, Playlist


def _make_teacher(**kw):
    defaults = dict(email="teacher@t.com", password="pass", role=ROLE_TEACHER)
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def _make_superuser(**kw):
    defaults = dict(email="super@t.com", password="pass")
    defaults.update(kw)
    return User.objects.create_superuser(**defaults)


def _make_playlist(author, name="Test Playlist"):
    pl = Playlist.objects.create(name=name, authored_by=author)
    return pl
```

Then add a test for the `analysisType` fix — this requires a fixture exercise. Skip the unit test for now (the fix is trivial and covered by the exercise editor integration test in Task 9). Mark the file created.

- [ ] **Apply the fix in `lab/views.py`**

Find the block around line 504:
```python
            # Inject analysisType into the top-level payload for the frontend
            exercise_context["analysisType"] = _family
```

Replace with:
```python
            # Inject analysisType — prefer explicit stored value over heuristic
            _stored_at = exercise.data.get("analysisType") if isinstance(exercise.data, dict) else None
            exercise_context["analysisType"] = _stored_at or _family
```

- [ ] **Run existing lab tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput lab -v 2
```
Expected: all pass.

- [ ] **Commit**

```bash
git add lab/views.py apps/teacher/tests/test_library_views.py
git commit -m "fix: prefer stored exercise.data.analysisType over complexity heuristic"
```

---

## Task 3: JS `buildAnalysisSlices` expansion

**Files:**
- Modify: `lab/static/js/src/components/music/play_save_logic.js`
- Modify: `lab/static/js/src/components/music/play_sheet.js:1239-1270`

- [ ] **Update `buildAnalysisSlices` to accept and merge `deterministicFieldsArr`**

In `play_save_logic.js`, change:
```javascript
function buildAnalysisSlices(offsets, slots, labels, overrides) {
  if (!slots || !slots.below) return [];
  var key = BELOW_CONTENT_KEY[slots.below];
  if (!key) return [];
  var out = [];
  for (var i = 0; i < offsets.length; i++) {
    var ov = overrides && overrides[i] && typeof overrides[i].below !== "undefined"
      ? overrides[i].below : null;
    var value = ov !== null ? ov : (labels[i] != null ? labels[i] : "");
    var content = {}; content[key] = value;
    out.push({ offset: offsets[i], content: content, is_target: true, unit_tags: [] });
  }
  return out;
}
```
to:
```javascript
function buildAnalysisSlices(offsets, slots, labels, overrides, deterministicFieldsArr) {
  if (!slots || !slots.below) return [];
  var key = BELOW_CONTENT_KEY[slots.below];
  if (!key) return [];
  var out = [];
  for (var i = 0; i < offsets.length; i++) {
    var ov = overrides && overrides[i] && typeof overrides[i].below !== "undefined"
      ? overrides[i].below : null;
    var value = ov !== null ? ov : (labels[i] != null ? labels[i] : "");
    var content = {}; content[key] = value;
    if (deterministicFieldsArr && deterministicFieldsArr[i]) {
      Object.assign(content, deterministicFieldsArr[i]);
    }
    out.push({ offset: offsets[i], content: content, is_target: true, unit_tags: [] });
  }
  return out;
}
```

- [ ] **Compute `deterministicFieldsArr` in `play_sheet.js` before calling `buildAnalysisSlices`**

In `play_sheet.js`, the block starting at line ~1239 computes `labels`. After the `labels` loop (after line ~1250, before the `buildChordRows` call), add:

```javascript
      // Compute analytics fields for each chord using the existing analyzer.
      var deterministicFieldsArr = notes.map(function(chord) {
        var midis = chord.visible || [];
        var fields = {};
        try { fields.set_class_set    = analyzer.to_set_class_set(midis)    || null; } catch(e) {}
        try { fields.set_class_normal = analyzer.to_set_class_normal(midis) || null; } catch(e) {}
        try { fields.set_class_prime  = analyzer.to_set_class_prime(midis)  || null; } catch(e) {}
        try { fields.set_class_forte  = analyzer.to_set_class_forte(midis)  || null; } catch(e) {}
        try { fields.spacing          = analyzer.to_spacing(midis)          || null; } catch(e) {}
        if (midis.length === 2) {
          try {
            var ivl = analyzer.to_interval(midis);
            fields.interval_specific = (ivl && ivl.name)  || null;
            fields.interval_generic  = (ivl && String(ivl.size)) || null;
          } catch(e) {}
        }
        return fields;
      });
```

Then update the `buildAnalysisSlices` call:
```javascript
      var analysisSlices = PlaySaveLogic.buildAnalysisSlices(
        offsets, slots, labels, tokenOverridesArr, deterministicFieldsArr);
```

- [ ] **Add `analysisType` to the save payload in `play_sheet.js`**

In the `json_data` object (around line 1256), add `analysisType`:
```javascript
      var json_data = {
        keySignature: this.keySignature.signatureSpec,
        key: this.keySignature.key,
        type: "matching",
        staffDistribution: this.parentComponent.staffDistributionConfig.staffDistribution,
        introText: "",
        reviewText: "",
        analyzeConfig: slots,
        display: display,
        highlight: this.parentComponent.highlightConfig,
        chord: chordRows,
        meter: this._meter,
        barline_offsets: this._barlineOffsets.slice(),
        analysisSlices: slots.below ? analysisSlices : null,
        analysisType: slots.below === "thoroughbass" ? "figured_bass" : "roman",
      };
```

- [ ] **Smoke-test in browser**

Load `/teacher/play/`, add a few chords, click Save. Open DevTools → Network → find the save POST to `/lab/exercises/add/`. Confirm request payload includes `analysisType` and that `analysisSlices[0].content` contains `set_class_prime` (or similar) alongside `roman_numeral`.

- [ ] **Commit**

```bash
git add lab/static/js/src/components/music/play_save_logic.js \
        lab/static/js/src/components/music/play_sheet.js
git commit -m "feat: compute analytics fields (set_class, spacing) in buildAnalysisSlices at save time"
```

---

## Task 4: Python `build_chordal_analysis_slices` expansion

**Files:**
- Modify: `apps/exercises/utils/umto_import_router.py:129-178`

- [ ] **Write failing test**

In `apps/exercises/tests/test_umto_import_router.py` (create or add to existing):
```python
from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices

def test_build_chordal_analysis_slices_has_set_class():
    chords = [
        {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
        {"offset": 1.0, "duration": 1.0, "visible": [62, 65, 69], "hidden": []},
    ]
    slices = build_chordal_analysis_slices(chords, harmony_key="C")
    assert len(slices) == 2
    content = slices[0]["content"]
    assert "set_class_prime" in content
    assert content["set_class_prime"] is not None
    assert "set_class_forte" in content
    assert "spacing" in content
```

- [ ] **Run test to confirm it fails**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_umto_import_router.test_build_chordal_analysis_slices_has_set_class -v 2
```
Expected: FAIL — `KeyError: 'set_class_prime'`.

- [ ] **Expand `build_chordal_analysis_slices` in `umto_import_router.py`**

Change the `analysis.append(...)` block (lines 166-177) from:
```python
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
```
to:
```python
        # Compute set-class analytics via music21
        sc_prime = sc_forte = sc_normal = sc_set = spacing_val = None
        try:
            sc_prime  = chord_obj.primeFormString
            sc_forte  = chord_obj.forteClassTnI
            sc_normal = str(chord_obj.normalOrder)
            sc_set    = "{" + ",".join(str(p.name) for p in chord_obj.pitches) + "}"
        except Exception:
            pass
        # Spacing: close (+) vs open (°) for 4-voice chords
        if len(pitches) == 4:
            sorted_midi = sorted(p.midi for p in chord_obj.pitches)
            sat = sorted_midi[1:]
            uv_span = sat[-1] - sat[0]
            pcs = sorted(set(m % 12 for m in sat))
            if len(pcs) == 3 and uv_span < 12:
                spacing_val = "+"
            elif len(pcs) == 3:
                spacing_val = "°"

        analysis.append({
            "offset": float(chord_event.get("offset", 0.0)),
            "content": {
                "roman_numeral": roman_label,
                "raw_roman_numeral": raw_roman,
                "local_key": harmony_key,
                "raw_figured_bass": raw_fb,
                "figured_bass": figured_bass,
                "set_class_prime":  sc_prime,
                "set_class_forte":  sc_forte,
                "set_class_normal": sc_normal,
                "set_class_set":    sc_set,
                "spacing":          spacing_val,
                "interval_specific": None,
                "interval_generic":  None,
            },
            "unit_tags": [],
            "is_target": True,
        })
```

- [ ] **Run test to confirm it passes**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_umto_import_router -v 2
```
Expected: PASS.

- [ ] **Commit**

```bash
git add apps/exercises/utils/umto_import_router.py \
        apps/exercises/tests/test_umto_import_router.py
git commit -m "feat: expand build_chordal_analysis_slices with set_class and spacing analytics"
```

---

## Task 5: `official_review_status` model field + migration

**Files:**
- Modify: `apps/exercises/models.py` (Exercise class ~line 142, Playlist class ~line 594)
- Create: migration file (auto-generated)

- [ ] **Add `official_review_status` to `Exercise` model**

After the `is_official` field (~line 142) in the `Exercise` class, add:
```python
    REVIEW_STATUS_CHOICES = [
        ("none", "none"),
        ("pending", "pending"),
        ("approved", "approved"),
        ("rejected", "rejected"),
    ]
    official_review_status = models.CharField(
        max_length=16,
        choices=REVIEW_STATUS_CHOICES,
        default="none",
        db_index=True,
    )
```

- [ ] **Add `official_review_status` to `Playlist` model**

After `is_official` in the `Playlist` class (~line 594), add the same field:
```python
    official_review_status = models.CharField(
        max_length=16,
        choices=[("none","none"),("pending","pending"),("approved","approved"),("rejected","rejected")],
        default="none",
        db_index=True,
    )
```

- [ ] **Generate and apply migration**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py makemigrations exercises --name official_review_status
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py migrate
```
Expected: migration created and applied with no errors.

- [ ] **Write model test**

In `apps/exercises/tests/test_official_review_status.py`:
```python
from django.test import TestCase
from apps.accounts.models import User
from apps.exercises.models import Exercise, Playlist


def _make_user():
    return User.objects.create_user(email="u@t.com", password="x")


class OfficialReviewStatusTest(TestCase):
    def setUp(self):
        self.user = _make_user()

    def test_exercise_default_none(self):
        ex = Exercise.objects.create(
            description="Test",
            data={"type": "test"},
            authored_by=self.user,
        )
        self.assertEqual(ex.official_review_status, "none")

    def test_playlist_default_none(self):
        pl = Playlist.objects.create(name="Test", authored_by=self.user)
        self.assertEqual(pl.official_review_status, "none")

    def test_can_set_pending(self):
        pl = Playlist.objects.create(name="Test", authored_by=self.user)
        pl.official_review_status = "pending"
        pl.save()
        pl.refresh_from_db()
        self.assertEqual(pl.official_review_status, "pending")
```

- [ ] **Run test**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_official_review_status -v 2
```
Expected: PASS.

- [ ] **Commit**

```bash
git add apps/exercises/models.py apps/exercises/migrations/ \
        apps/exercises/tests/test_official_review_status.py
git commit -m "feat: add official_review_status field to Exercise and Playlist"
```

---

## Task 6: Library views scaffold, URLs, nav link

**Files:**
- Create: `apps/teacher/views_library.py`
- Modify: `apps/teacher/urls.py`
- Modify: `apps/teacher/templates/teacher/base.html`

- [ ] **Create `apps/teacher/views_library.py` with stub views**

```python
"""Library hub and content editor views for the teacher app."""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.teacher.decorators import teacher_required

logger = logging.getLogger(__name__)


@teacher_required
def library_hub_view(request):
    """GET /teacher/library/ — three-tab library hub."""
    tab = request.GET.get("tab", "playlists")
    unit = request.GET.get("unit", "")
    official_filter = request.GET.get("official", "")

    # --- Playlists tab ---
    pl_qs = Playlist.objects.filter(
        Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)
    ).order_by("-updated")
    if unit:
        pl_qs = pl_qs.filter(skill_tags__contains=[f"unit:{unit}"])
    if official_filter == "official":
        pl_qs = pl_qs.filter(is_official=True)
    elif official_filter == "personal":
        pl_qs = pl_qs.filter(authored_by=request.user)
    playlists = list(pl_qs.annotate(exercise_count=Count("exercises"))[:200])

    # --- Exercises tab ---
    ex_qs = Exercise.objects.filter(
        Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)
    ).order_by("-updated")
    if unit:
        ex_qs = ex_qs.filter(skill_tags__contains=[f"unit:{unit}"])
    if official_filter == "official":
        ex_qs = ex_qs.filter(is_official=True)
    elif official_filter == "personal":
        ex_qs = ex_qs.filter(authored_by=request.user)
    exercises = list(ex_qs[:200])

    # --- Official tab (superuser only) ---
    pending_playlists = []
    pending_exercises = []
    if request.user.is_superuser:
        pending_playlists = list(
            Playlist.objects.filter(official_review_status="pending").order_by("-updated")
        )
        pending_exercises = list(
            Exercise.objects.filter(official_review_status="pending").order_by("-updated")
        )

    return render(request, "teacher/library_hub.html", {
        "tab": tab,
        "playlists": playlists,
        "exercises": exercises,
        "pending_playlists": pending_playlists,
        "pending_exercises": pending_exercises,
        "unit_filter": unit,
        "official_filter": official_filter,
    })


@teacher_required
def exercise_preview_view(request, exercise_id):
    """GET /teacher/library/exercises/<id>/preview/ — return score_data for VexFlow thumbnail."""
    ex = get_object_or_404(Exercise, id=exercise_id)
    if not (ex.is_public or ex.is_official or ex.authored_by_id == request.user.pk):
        raise Http404
    score_data = None
    if isinstance(ex.data, dict):
        score_data = ex.data.get("score")
    return JsonResponse({"score_data": score_data})


@teacher_required
def playlist_detail_view(request, playlist_id):
    """GET /teacher/library/playlists/<id>/ — playlist editor."""
    pl = get_object_or_404(
        Playlist,
        id=playlist_id,
    )
    if not (pl.is_official or pl.is_public or pl.authored_by_id == request.user.pk):
        raise Http404
    epo_qs = (
        ExercisePlaylistOrdered.objects.filter(playlist=pl)
        .select_related("exercise")
        .order_by("order")
    )
    exercises = [
        {
            "id": epo.exercise.id,
            "description": epo.exercise.description or "",
            "complexity": epo.exercise.complexity,
            "skill_tags": epo.exercise.skill_tags or [],
            "is_official": epo.exercise.is_official,
            "epo_id": epo.pk,
            "order": epo.order,
        }
        for epo in epo_qs
    ]
    return render(request, "teacher/playlist_editor.html", {
        "playlist": pl,
        "exercises_json": json.dumps(exercises),
        "can_edit": pl.authored_by_id == request.user.pk or request.user.is_superuser,
    })


@teacher_required
@require_POST
def playlist_save_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/save/ — update playlist metadata."""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if "name" in body:
        pl.name = str(body["name"])[:64]
    if "skill_tags" in body and isinstance(body["skill_tags"], list):
        pl.skill_tags = [str(t)[:64] for t in body["skill_tags"]]
    if "is_public" in body:
        pl.is_public = bool(body["is_public"])
    pl.save()
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def playlist_reorder_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/reorder/ — reorder exercises in playlist."""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
        order = body["order"]  # list of EPO primary keys in new order
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "order list required"}, status=400)
    for idx, epo_pk in enumerate(order):
        ExercisePlaylistOrdered.objects.filter(pk=epo_pk, playlist=pl).update(order=idx)
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def playlist_add_exercise_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/add-exercise/ — add exercise to playlist."""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
        exercise_id = body["exerciseId"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "exerciseId required"}, status=400)
    ex = get_object_or_404(Exercise, id=exercise_id)
    if not (ex.is_public or ex.is_official or ex.authored_by_id == request.user.pk):
        return JsonResponse({"error": "Access denied"}, status=403)
    next_order = ExercisePlaylistOrdered.objects.filter(playlist=pl).count()
    epo = ExercisePlaylistOrdered.objects.create(
        playlist=pl, exercise=ex, order=next_order
    )
    return JsonResponse({"ok": True, "epoId": epo.pk})


@teacher_required
@require_POST
def playlist_remove_exercise_view(request, playlist_id, epo_id):
    """POST /teacher/library/playlists/<id>/remove-exercise/<epo_id>/ — remove exercise."""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    epo = get_object_or_404(ExercisePlaylistOrdered, pk=epo_id, playlist=pl)
    epo.delete()
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def playlist_submit_review_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/submit-review/ — submit for official review."""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    if not pl.is_public:
        return JsonResponse({"error": "Playlist must be public before submitting for review."}, status=400)
    if pl.official_review_status in ("pending", "approved"):
        return JsonResponse({"error": f"Already {pl.official_review_status}."}, status=400)
    pl.official_review_status = "pending"
    pl.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True, "status": "pending"})


@teacher_required
@require_POST
def playlist_approve_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/approve/ — superuser approve."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    pl = get_object_or_404(Playlist, id=playlist_id)
    from apps.accounts.models import User
    try:
        factory = User.objects.get(email="factory@monteverdi.app")
    except User.DoesNotExist:
        factory = request.user
    pl.official_review_status = "approved"
    pl.is_official = True
    pl.authored_by = factory
    pl.save(update_fields=["official_review_status", "is_official", "authored_by"])
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def playlist_reject_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/reject/ — superuser reject."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    pl = get_object_or_404(Playlist, id=playlist_id)
    pl.official_review_status = "none"
    pl.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True})


@teacher_required
def exercise_detail_view(request, exercise_id):
    """GET /teacher/library/exercises/<id>/ — exercise editor."""
    ex = get_object_or_404(Exercise, id=exercise_id)
    if not (ex.is_public or ex.is_official or ex.authored_by_id == request.user.pk):
        raise Http404
    in_playlists = list(
        Playlist.objects.filter(exercises=ex).values("id", "name")[:20]
    )
    # Editable only by author or superuser
    can_edit = ex.authored_by_id == request.user.pk or request.user.is_superuser
    umto_meta = {}
    if isinstance(ex.data, dict):
        score = ex.data.get("score", {})
        umto = score.get("umto", {}) if isinstance(score, dict) else {}
        meta = umto.get("metadata", {}) if isinstance(umto, dict) else {}
        umto_meta = {
            "key": meta.get("key", ""),
            "meter": meta.get("meter", ""),
            "mode": meta.get("mode", ""),
            "score_kind": meta.get("score_kind", ""),
            "analysis_review_status": meta.get("analysis_review_status", "none"),
            "complexity_score": meta.get("complexity_score", 1),
        }
    return render(request, "teacher/exercise_editor.html", {
        "exercise": ex,
        "umto_meta": umto_meta,
        "in_playlists": in_playlists,
        "can_edit": can_edit,
        "analysis_type": ex.data.get("analysisType", "roman") if isinstance(ex.data, dict) else "roman",
    })


@teacher_required
@require_POST
def exercise_save_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/save/ — update exercise metadata."""
    ex = get_object_or_404(Exercise, id=exercise_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if "description" in body:
        ex.description = str(body["description"])[:60]
    if "skill_tags" in body and isinstance(body["skill_tags"], list):
        ex.skill_tags = [str(t)[:64] for t in body["skill_tags"]]
    if "complexity" in body:
        try:
            ex.complexity = max(1, min(20, int(body["complexity"])))
        except (ValueError, TypeError):
            pass
    if "is_public" in body:
        ex.is_public = bool(body["is_public"])
    if "analysisType" in body and isinstance(ex.data, dict):
        ex.data = {**ex.data, "analysisType": str(body["analysisType"])}
    ex.save()
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def exercise_submit_review_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/submit-review/ — submit for official review."""
    ex = get_object_or_404(Exercise, id=exercise_id, authored_by=request.user)
    if not ex.is_public:
        return JsonResponse({"error": "Exercise must be public before submitting for review."}, status=400)
    if ex.official_review_status in ("pending", "approved"):
        return JsonResponse({"error": f"Already {ex.official_review_status}."}, status=400)
    ex.official_review_status = "pending"
    ex.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True, "status": "pending"})


@teacher_required
@require_POST
def exercise_approve_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/approve/ — superuser approve."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    ex = get_object_or_404(Exercise, id=exercise_id)
    from apps.accounts.models import User
    try:
        factory = User.objects.get(email="factory@monteverdi.app")
    except User.DoesNotExist:
        factory = request.user
    ex.official_review_status = "approved"
    ex.is_official = True
    ex.authored_by = factory
    ex.save(update_fields=["official_review_status", "is_official", "authored_by"])
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def exercise_reject_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/reject/ — superuser reject."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    ex = get_object_or_404(Exercise, id=exercise_id)
    ex.official_review_status = "none"
    ex.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True})


@teacher_required
def exercises_search_view(request):
    """GET /teacher/library/exercises/search/ — JSON search for add-exercise modal."""
    q = request.GET.get("q", "").strip()
    unit = request.GET.get("unit", "").strip()
    qs = Exercise.objects.filter(
        Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)
    )
    if q:
        qs = qs.filter(description__icontains=q)
    if unit:
        qs = qs.filter(skill_tags__contains=[f"unit:{unit}"])
    results = [
        {"id": ex.id, "description": ex.description or "", "complexity": ex.complexity,
         "is_official": ex.is_official}
        for ex in qs[:50]
    ]
    return JsonResponse({"results": results})
```

- [ ] **Register URLs in `apps/teacher/urls.py`**

Add these imports at the top:
```python
from apps.teacher.views_library import (
    library_hub_view,
    exercise_preview_view,
    playlist_detail_view,
    playlist_save_view,
    playlist_reorder_view,
    playlist_add_exercise_view,
    playlist_remove_exercise_view,
    playlist_submit_review_view,
    playlist_approve_view,
    playlist_reject_view,
    exercise_detail_view,
    exercise_save_view,
    exercise_submit_review_view,
    exercise_approve_view,
    exercise_reject_view,
    exercises_search_view,
)
```

Add URL patterns to `urlpatterns`:
```python
    path("library/", library_hub_view, name="library-hub"),
    path("library/playlists/", library_hub_view, name="library-playlists"),
    path("library/playlists/<str:playlist_id>/", playlist_detail_view, name="playlist-detail"),
    path("library/playlists/<str:playlist_id>/save/", playlist_save_view, name="playlist-save"),
    path("library/playlists/<str:playlist_id>/reorder/", playlist_reorder_view, name="playlist-reorder"),
    path("library/playlists/<str:playlist_id>/add-exercise/", playlist_add_exercise_view, name="playlist-add-exercise"),
    path("library/playlists/<str:playlist_id>/remove-exercise/<int:epo_id>/", playlist_remove_exercise_view, name="playlist-remove-exercise"),
    path("library/playlists/<str:playlist_id>/submit-review/", playlist_submit_review_view, name="playlist-submit-review"),
    path("library/playlists/<str:playlist_id>/approve/", playlist_approve_view, name="playlist-approve"),
    path("library/playlists/<str:playlist_id>/reject/", playlist_reject_view, name="playlist-reject"),
    path("library/exercises/", library_hub_view, name="library-exercises"),
    path("library/exercises/search/", exercises_search_view, name="exercises-search"),
    path("library/exercises/<str:exercise_id>/", exercise_detail_view, name="exercise-detail"),
    path("library/exercises/<str:exercise_id>/preview/", exercise_preview_view, name="exercise-preview"),
    path("library/exercises/<str:exercise_id>/save/", exercise_save_view, name="exercise-save"),
    path("library/exercises/<str:exercise_id>/submit-review/", exercise_submit_review_view, name="exercise-submit-review"),
    path("library/exercises/<str:exercise_id>/approve/", exercise_approve_view, name="exercise-approve"),
    path("library/exercises/<str:exercise_id>/reject/", exercise_reject_view, name="exercise-reject"),
    path("library/official/", library_hub_view, name="library-official"),
```

- [ ] **Add Library nav link to `base.html`**

In `apps/teacher/templates/teacher/base.html`, change:
```html
  <header class="t-header">
    <a class="t-header-brand" href="/">Monteverdi</a>
    {% if request.user.is_authenticated %}
      <div class="t-header-user-area">
```
to:
```html
  <header class="t-header">
    <a class="t-header-brand" href="/">Monteverdi</a>
    {% if request.user.is_authenticated %}
      <nav class="t-header-nav">
        <a class="t-nav-link {% if request.resolver_match.app_name == 'teacher' and 'course' in request.resolver_match.url_name %}t-nav-link--active{% endif %}" href="/teacher/courses/">Courses</a>
        <a class="t-nav-link {% if request.resolver_match.app_name == 'teacher' and 'library' in request.resolver_match.url_name %}t-nav-link--active{% endif %}" href="/teacher/library/">Library</a>
        <a class="t-nav-link" href="/teacher/play/">Play</a>
      </nav>
      <div class="t-header-user-area">
```

Add to `apps/teacher/static/teacher/teacher.css` (at the end):
```css
.t-header-nav { display: flex; gap: 4px; }
.t-nav-link { font-family: var(--font-ui); font-size: 0.875rem; color: rgba(255,255,255,0.75); text-decoration: none; padding: 6px 14px; border-radius: 4px; }
.t-nav-link:hover, .t-nav-link--active { background: rgba(255,255,255,0.18); color: #fff; font-weight: 700; }
```

- [ ] **Write URL routing tests**

In `apps/teacher/tests/test_library_views.py`, add:
```python
from django.urls import reverse


class LibraryURLTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="teacher@t.com", password="pass")

    def test_library_hub_200(self):
        url = reverse("teacher:library-hub")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_library_official_requires_superuser(self):
        url = reverse("teacher:library-official")
        resp = self.client.get(url)
        # Regular teacher sees hub but pending_playlists/exercises empty
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["pending_playlists"], [])

    def test_library_official_superuser_sees_pending(self):
        su = _make_superuser()
        pl = _make_playlist(self.teacher, "Pending PL")
        pl.is_public = True
        pl.official_review_status = "pending"
        pl.save()

        c = Client()
        c.login(email="super@t.com", password="pass")
        resp = c.get(reverse("teacher:library-official"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(pl, resp.context["pending_playlists"])
```

- [ ] **Run URL tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_views.LibraryURLTest -v 2
```
Expected: PASS.

- [ ] **Commit**

```bash
git add apps/teacher/views_library.py apps/teacher/urls.py \
        apps/teacher/templates/teacher/base.html \
        apps/teacher/static/teacher/teacher.css \
        apps/teacher/tests/test_library_views.py
git commit -m "feat: add library views, URLs, and header nav link"
```

---

## Task 7: Library hub template

**Files:**
- Create: `apps/teacher/templates/teacher/library_hub.html`

- [ ] **Create the template**

```django
{# apps/teacher/templates/teacher/library_hub.html #}
{% extends "teacher/base.html" %}
{% load static %}

{% block title %}Library — Monteverdi{% endblock %}

{% block content %}
<div class="t-list-header">
  <h1 class="t-page-title">Library</h1>
</div>

<div class="t-tabs" role="tablist">
  <a class="t-tab {% if tab == 'playlists' %}t-tab--active{% endif %}"
     href="?tab=playlists">Playlists</a>
  <a class="t-tab {% if tab == 'exercises' %}t-tab--active{% endif %}"
     href="?tab=exercises">Exercises</a>
  {% if request.user.is_superuser %}
  <a class="t-tab {% if tab == 'official' %}t-tab--active{% endif %}"
     href="?tab=official">
    Official
    {% if pending_playlists or pending_exercises %}
    <span class="t-badge t-badge--warn">{{ pending_playlists|length|add:pending_exercises|length }}</span>
    {% endif %}
  </a>
  {% endif %}
</div>

{# ── Filter bar (playlists + exercises tabs) ─────────────────────── #}
{% if tab != 'official' %}
<form class="t-filter-bar" method="get">
  <input type="hidden" name="tab" value="{{ tab }}">
  <input class="t-input t-input-sm" type="text" name="unit" value="{{ unit_filter }}"
         placeholder="Unit (e.g. 9)">
  <select class="t-input t-input-sm" name="official">
    <option value="">All</option>
    <option value="official" {% if official_filter == 'official' %}selected{% endif %}>Official only</option>
    <option value="personal" {% if official_filter == 'personal' %}selected{% endif %}>Mine only</option>
  </select>
  <button class="t-btn t-btn-ghost t-btn-sm" type="submit">Filter</button>
</form>
{% endif %}

{# ── Playlists tab ────────────────────────────────────────────────── #}
{% if tab == 'playlists' %}
<table class="t-table">
  <thead><tr>
    <th>Name</th><th>Unit tags</th><th>Exercises</th><th>Official</th><th>Updated</th>
  </tr></thead>
  <tbody>
  {% for pl in playlists %}
  <tr>
    <td><a class="t-link" href="{% url 'teacher:playlist-detail' pl.id %}">{{ pl.name }}</a></td>
    <td>{{ pl.skill_tags|join:", " }}</td>
    <td>{{ pl.exercise_count }}</td>
    <td>{% if pl.is_official %}✓{% endif %}</td>
    <td>{{ pl.updated|date:"Y-m-d" }}</td>
  </tr>
  {% empty %}
  <tr><td colspan="5" style="color:var(--text-muted);padding:16px;">No playlists found.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}

{# ── Exercises tab ─────────────────────────────────────────────────── #}
{% if tab == 'exercises' %}
<table class="t-table">
  <thead><tr>
    <th>Description</th><th>Type</th><th>Unit</th><th>Complexity</th><th>Official</th><th>Updated</th>
  </tr></thead>
  <tbody>
  {% for ex in exercises %}
  <tr>
    <td><a class="t-link" href="{% url 'teacher:exercise-detail' ex.id %}">{{ ex.description|default:"(no description)" }}</a></td>
    <td style="font-size:0.75rem;color:var(--text-muted);">{{ ex.data.type|default:"" }}</td>
    <td>{{ ex.skill_tags|join:", " }}</td>
    <td>{{ ex.complexity }}</td>
    <td>{% if ex.is_official %}✓{% endif %}</td>
    <td>{{ ex.updated|date:"Y-m-d" }}</td>
  </tr>
  {% empty %}
  <tr><td colspan="6" style="color:var(--text-muted);padding:16px;">No exercises found.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}

{# ── Official tab (superuser) ─────────────────────────────────────── #}
{% if tab == 'official' and request.user.is_superuser %}
<section style="margin-bottom:24px;">
  <h2 class="t-section-title">Pending review</h2>
  {% for pl in pending_playlists %}
  <div class="t-submission-card">
    <div>
      <strong>{{ pl.name }}</strong>
      <span class="t-mono">{{ pl.id }}</span><br>
      <span class="t-muted">Playlist · by {{ pl.authored_by.email }} · {{ pl.updated|date:"Y-m-d" }}</span>
    </div>
    <div class="t-submission-actions">
      <form method="post" action="{% url 'teacher:playlist-approve' pl.id %}">
        {% csrf_token %}
        <button class="t-btn t-btn-sm t-btn-success">✓ Approve</button>
      </form>
      <form method="post" action="{% url 'teacher:playlist-reject' pl.id %}">
        {% csrf_token %}
        <button class="t-btn t-btn-sm t-btn-danger">✗ Reject</button>
      </form>
    </div>
  </div>
  {% empty %}
  <p class="t-muted">No pending playlist submissions.</p>
  {% endfor %}

  {% for ex in pending_exercises %}
  <div class="t-submission-card">
    <div>
      <strong>{{ ex.description|default:"(no description)" }}</strong>
      <span class="t-mono">{{ ex.id }}</span><br>
      <span class="t-muted">Exercise · by {{ ex.authored_by.email }} · {{ ex.updated|date:"Y-m-d" }}</span>
    </div>
    <div class="t-submission-actions">
      <form method="post" action="{% url 'teacher:exercise-approve' ex.id %}">
        {% csrf_token %}
        <button class="t-btn t-btn-sm t-btn-success">✓ Approve</button>
      </form>
      <form method="post" action="{% url 'teacher:exercise-reject' ex.id %}">
        {% csrf_token %}
        <button class="t-btn t-btn-sm t-btn-danger">✗ Reject</button>
      </form>
    </div>
  </div>
  {% empty %}
  <p class="t-muted">No pending exercise submissions.</p>
  {% endfor %}
</section>
{% endif %}
{% endblock %}
```

Add new CSS to `teacher.css`:
```css
.t-tabs { display: flex; gap: 0; border-bottom: 2px solid var(--border); margin-bottom: 18px; }
.t-tab { font-family: var(--font-ui); font-size: 0.875rem; font-weight: 600; padding: 9px 18px; color: var(--text-muted); text-decoration: none; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.t-tab--active, .t-tab:hover { color: var(--teal); border-bottom-color: var(--teal); }
.t-badge { display: inline-flex; align-items: center; justify-content: center; font-size: 0.68rem; font-weight: 700; border-radius: 10px; padding: 1px 7px; margin-left: 5px; }
.t-badge--warn { background: #fef3c7; color: #b45309; }
.t-filter-bar { display: flex; gap: 8px; margin-bottom: 14px; align-items: center; }
.t-table { width: 100%; border-collapse: collapse; background: var(--surface-2, #fff); border: 1px solid var(--border); border-radius: var(--radius, 5px); font-size: 0.82rem; }
.t-table th { font-family: var(--font-ui); font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted); padding: 8px 12px; text-align: left; background: var(--surface); border-bottom: 1px solid var(--border); }
.t-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); }
.t-table tr:last-child td { border-bottom: none; }
.t-table tr:hover td { background: #f0f6f8; }
.t-section-title { font-family: var(--font-ui); font-size: 0.82rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }
.t-submission-card { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; background: #fff; border: 1px solid var(--border); border-radius: var(--radius, 5px); padding: 14px 16px; margin-bottom: 10px; }
.t-submission-actions { display: flex; gap: 6px; flex-shrink: 0; }
.t-btn-success { background: #198754; color: #fff; }
.t-btn-danger  { background: #dc3545; color: #fff; }
.t-mono { font-family: monospace; font-size: 0.75rem; color: var(--text-muted); }
.t-muted { color: var(--text-muted); font-size: 0.82rem; }
```

- [ ] **Smoke test in browser**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver
```
Visit `http://localhost:8000/teacher/library/`. Confirm tabs render, filter bar shows, table populates.

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/library_hub.html \
        apps/teacher/static/teacher/teacher.css
git commit -m "feat: library hub template with Playlists, Exercises, Official tabs"
```

---

## Task 8: Playlist editor template

**Files:**
- Create: `apps/teacher/templates/teacher/playlist_editor.html`

- [ ] **Create the template**

```django
{# apps/teacher/templates/teacher/playlist_editor.html #}
{% extends "teacher/base.html" %}
{% load static %}

{% block title %}{{ playlist.name }} — Library — Monteverdi{% endblock %}

{% block head_extra %}
<script>
window.__PLAYLIST_DATA__ = {
  playlistId: "{{ playlist.id|escapejs }}",
  exercises: {{ exercises_json|safe }},
  canEdit: {{ can_edit|yesno:"true,false" }},
  csrfToken: "{{ csrf_token }}",
  saveUrl: "{% url 'teacher:playlist-save' playlist.id %}",
  reorderUrl: "{% url 'teacher:playlist-reorder' playlist.id %}",
  addExerciseUrl: "{% url 'teacher:playlist-add-exercise' playlist.id %}",
  searchUrl: "{% url 'teacher:exercises-search' %}",
  submitReviewUrl: "{% url 'teacher:playlist-submit-review' playlist.id %}",
};
</script>
{% endblock %}

{% block content %}
<div class="t-list-header">
  <div>
    <a class="t-link t-muted" href="/teacher/library/?tab=playlists">← Library</a>
    <h1 class="t-page-title" style="margin-top:4px;">{{ playlist.name }}</h1>
  </div>
</div>

<div class="t-detail-layout">

  <!-- Left: metadata sidebar -->
  <div class="t-detail-side" style="order:-1;">
    <div class="t-card" id="pl-meta-card">
      <div class="t-card-title">Playlist metadata</div>

      <label class="t-label">Name</label>
      <input class="t-input" type="text" id="pl-name" value="{{ playlist.name|escapejs }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Unit / skill tags (comma-separated)</label>
      <input class="t-input" type="text" id="pl-tags"
             value="{{ playlist.skill_tags|join:', ' }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Visibility</label>
      <select class="t-input" id="pl-visibility" {% if not can_edit %}disabled{% endif %}>
        <option value="public" {% if playlist.is_public %}selected{% endif %}>Public</option>
        <option value="private" {% if not playlist.is_public %}selected{% endif %}>Private</option>
      </select>

      <div style="margin-top:10px;">
        <span class="t-label">Official status</span>
        <span class="t-mono">
          {% if playlist.is_official %}Official{% else %}{{ playlist.official_review_status }}{% endif %}
        </span>
      </div>

      {% if can_edit %}
      <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;">
        <button class="t-btn t-btn-primary" id="btn-pl-save">Save</button>
        {% if not playlist.is_official and playlist.official_review_status != 'pending' %}
        <button class="t-btn t-btn-ghost" id="btn-submit-review"
                {% if not playlist.is_public %}disabled title="Make public first"{% endif %}>
          Submit for review
        </button>
        {% elif playlist.official_review_status == 'pending' %}
        <span class="t-muted">Submitted — awaiting review</span>
        {% endif %}
      </div>
      {% endif %}
    </div>
  </div>

  <!-- Right: exercise list -->
  <div class="t-detail-main">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <h2 class="t-section-title" style="margin:0;">Exercises ({{ playlist.exercises.count }})</h2>
      {% if can_edit %}
      <button class="t-btn t-btn-ghost t-btn-sm" id="btn-add-exercise">+ Add exercise</button>
      {% endif %}
    </div>

    <div id="exercise-list">
      <!-- populated by playlist_editor.js -->
    </div>
  </div>

</div>

<!-- Add exercise modal -->
<div id="add-exercise-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:100;align-items:center;justify-content:center;">
  <div style="background:#fff;border-radius:8px;padding:24px;min-width:360px;max-width:540px;width:90%;">
    <h3 style="margin-bottom:12px;font-family:var(--font-ui);">Add exercise</h3>
    <input class="t-input" type="text" id="modal-search-q" placeholder="Search by description…">
    <input class="t-input" type="text" id="modal-search-unit" placeholder="Unit (optional)" style="margin-top:8px;">
    <button class="t-btn t-btn-ghost t-btn-sm" id="btn-modal-search" style="margin-top:8px;">Search</button>
    <div id="modal-results" style="margin-top:12px;max-height:240px;overflow-y:auto;"></div>
    <button class="t-btn t-btn-ghost" id="btn-modal-close" style="margin-top:12px;">Close</button>
  </div>
</div>
{% endblock %}

{% block body_extra %}
<script>
(function() {
  var data = window.__PLAYLIST_DATA__;
  if (!data) return;

  // Render exercise list
  function renderList(exercises) {
    var el = document.getElementById("exercise-list");
    if (!exercises.length) {
      el.innerHTML = '<p class="t-muted">No exercises in this playlist.</p>';
      return;
    }
    el.innerHTML = exercises.map(function(ex, idx) {
      return '<div class="t-exercise-row" data-epo-id="' + ex.epo_id + '" data-idx="' + idx + '">' +
        '<span class="t-exercise-desc">' + (ex.description || "(no description)") + '</span>' +
        '<span class="t-mono" style="margin-left:8px;">' + ex.id + '</span>' +
        (data.canEdit
          ? '<button class="t-btn t-btn-sm t-btn-ghost" onclick="removeExercise(' + ex.epo_id + ')">Remove</button>'
          : '') +
      '</div>';
    }).join('');
  }
  renderList(data.exercises);

  // Save metadata
  document.getElementById("btn-pl-save") && document.getElementById("btn-pl-save").addEventListener("click", function() {
    var tags = document.getElementById("pl-tags").value.split(",").map(function(t){ return t.trim(); }).filter(Boolean);
    var isPublic = document.getElementById("pl-visibility").value === "public";
    fetch(data.saveUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": data.csrfToken},
      body: JSON.stringify({name: document.getElementById("pl-name").value, skill_tags: tags, is_public: isPublic}),
    }).then(function(r){ return r.json(); }).then(function(j){ if (j.ok) alert("Saved."); });
  });

  // Submit for review
  document.getElementById("btn-submit-review") && document.getElementById("btn-submit-review").addEventListener("click", function() {
    if (!confirm("Submit this playlist for official review?")) return;
    fetch(data.submitReviewUrl, {
      method: "POST",
      headers: {"X-CSRFToken": data.csrfToken},
    }).then(function(r){ return r.json(); }).then(function(j) {
      if (j.ok) { location.reload(); }
      else { alert(j.error); }
    });
  });

  // Add exercise modal
  var modal = document.getElementById("add-exercise-modal");
  document.getElementById("btn-add-exercise") && document.getElementById("btn-add-exercise").addEventListener("click", function() {
    modal.style.display = "flex";
  });
  document.getElementById("btn-modal-close").addEventListener("click", function() {
    modal.style.display = "none";
  });
  document.getElementById("btn-modal-search").addEventListener("click", function() {
    var q = document.getElementById("modal-search-q").value;
    var unit = document.getElementById("modal-search-unit").value;
    var url = data.searchUrl + "?q=" + encodeURIComponent(q) + "&unit=" + encodeURIComponent(unit);
    fetch(url).then(function(r){ return r.json(); }).then(function(j) {
      var el = document.getElementById("modal-results");
      if (!j.results.length) { el.innerHTML = '<p class="t-muted">No results.</p>'; return; }
      el.innerHTML = j.results.map(function(ex) {
        return '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">' +
          '<span>' + (ex.description || "(no description)") + ' <span class="t-mono">' + ex.id + '</span></span>' +
          '<button class="t-btn t-btn-sm t-btn-primary" onclick="addExercise(\'' + ex.id + '\')">Add</button>' +
        '</div>';
      }).join('');
    });
  });

  window.addExercise = function(exId) {
    fetch(data.addExerciseUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": data.csrfToken},
      body: JSON.stringify({exerciseId: exId}),
    }).then(function(r){ return r.json(); }).then(function(j) {
      if (j.ok) { location.reload(); }
      else { alert(j.error); }
    });
  };

  window.removeExercise = function(epoId) {
    if (!confirm("Remove this exercise from the playlist?")) return;
    var url = "/teacher/library/playlists/" + data.playlistId + "/remove-exercise/" + epoId + "/";
    fetch(url, {method: "POST", headers: {"X-CSRFToken": data.csrfToken}})
      .then(function(r){ return r.json(); })
      .then(function(j){ if (j.ok) location.reload(); });
  };
})();
</script>
{% endblock %}
```

Add CSS to `teacher.css`:
```css
.t-exercise-row { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 0.875rem; }
.t-exercise-desc { flex: 1; }
```

- [ ] **Write integration test**

In `apps/teacher/tests/test_library_views.py`, add:
```python
class PlaylistEditorTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.pl = _make_playlist(self.teacher, "My PL")
        self.client = Client()
        self.client.login(email="teacher@t.com", password="pass")

    def test_playlist_detail_200(self):
        url = reverse("teacher:playlist-detail", args=[self.pl.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My PL")

    def test_playlist_save(self):
        url = reverse("teacher:playlist-save", args=[self.pl.id])
        resp = self.client.post(url, json.dumps({"name": "New Name", "skill_tags": ["unit:9"], "is_public": False}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.name, "New Name")
        self.assertEqual(self.pl.skill_tags, ["unit:9"])

    def test_submit_review_requires_public(self):
        url = reverse("teacher:playlist-submit-review", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)

    def test_submit_review_sets_pending(self):
        self.pl.is_public = True
        self.pl.save()
        url = reverse("teacher:playlist-submit-review", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.official_review_status, "pending")

    def test_approve_requires_superuser(self):
        url = reverse("teacher:playlist-approve", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_approve_by_superuser(self):
        su = _make_superuser()
        c = Client()
        c.login(email="super@t.com", password="pass")
        url = reverse("teacher:playlist-approve", args=[self.pl.id])
        resp = c.post(url)
        self.assertEqual(resp.status_code, 200)
        self.pl.refresh_from_db()
        self.assertTrue(self.pl.is_official)
        self.assertEqual(self.pl.official_review_status, "approved")
```

- [ ] **Run tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_views.PlaylistEditorTest -v 2
```
Expected: PASS.

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/playlist_editor.html \
        apps/teacher/static/teacher/teacher.css \
        apps/teacher/tests/test_library_views.py
git commit -m "feat: playlist editor template with save, reorder, add/remove, submit-for-review"
```

---

## Task 9: Exercise editor template

**Files:**
- Create: `apps/teacher/templates/teacher/exercise_editor.html`

- [ ] **Create the template**

```django
{# apps/teacher/templates/teacher/exercise_editor.html #}
{% extends "teacher/base.html" %}
{% load static %}

{% block title %}{{ exercise.description|default:"Exercise" }} — Library — Monteverdi{% endblock %}

{% block head_extra %}
<script>
window.__EXERCISE_DATA__ = {
  exerciseId: "{{ exercise.id|escapejs }}",
  canEdit: {{ can_edit|yesno:"true,false" }},
  csrfToken: "{{ csrf_token }}",
  saveUrl: "{% url 'teacher:exercise-save' exercise.id %}",
  submitReviewUrl: "{% url 'teacher:exercise-submit-review' exercise.id %}",
  previewUrl: "{% url 'teacher:exercise-preview' exercise.id %}",
  isSuperuser: {{ request.user.is_superuser|yesno:"true,false" }},
  approveUrl: "{% url 'teacher:exercise-approve' exercise.id %}",
  rejectUrl: "{% url 'teacher:exercise-reject' exercise.id %}",
};
</script>
{% endblock %}

{% block content %}
<div class="t-list-header">
  <div>
    <a class="t-link t-muted" href="/teacher/library/?tab=exercises">← Library</a>
    <h1 class="t-page-title" style="margin-top:4px;">
      {{ exercise.description|default:"(no description)" }}
    </h1>
  </div>
</div>

<div class="t-detail-layout">

  <!-- Left: score preview + in-playlists -->
  <div class="t-detail-side" style="order:-1;">
    <div class="t-card">
      <div class="t-card-title">Score preview</div>
      <canvas id="score-preview-canvas" width="220" height="120"
              style="border:1px solid var(--border);border-radius:4px;width:100%;"></canvas>
      <p class="t-muted" style="margin-top:6px;">First 2 measures · VexFlow render</p>
    </div>

    <div class="t-card" style="margin-top:12px;">
      <div class="t-card-title">In playlists</div>
      {% for pl in in_playlists %}
      <div><a class="t-link" href="{% url 'teacher:playlist-detail' pl.id %}">{{ pl.name }}</a></div>
      {% empty %}
      <p class="t-muted">Not in any playlists.</p>
      {% endfor %}
    </div>

    {% if request.user.is_superuser %}
    <div class="t-card" style="margin-top:12px;">
      <div class="t-card-title">Admin</div>
      <a class="t-link" href="/dashboard/exercises/{{ exercise.pk }}/edit/" target="_blank">
        Edit raw JSON ↗
      </a>
    </div>
    {% endif %}
  </div>

  <!-- Right: metadata form -->
  <div class="t-detail-main">
    <div class="t-card">
      <div class="t-card-title">Metadata</div>

      <label class="t-label">Description</label>
      <input class="t-input" type="text" id="ex-description"
             value="{{ exercise.description|default:''|escapejs }}"
             maxlength="60" {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Unit / skill tags (comma-separated)</label>
      <input class="t-input" type="text" id="ex-tags"
             value="{{ exercise.skill_tags|join:', ' }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Complexity (1–20)</label>
      <input class="t-input" type="number" min="1" max="20" id="ex-complexity"
             value="{{ exercise.complexity }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Analysis type</label>
      <select class="t-input" id="ex-analysis-type" {% if not can_edit %}disabled{% endif %}>
        {% for token, label in analysis_type_choices %}
        <option value="{{ token }}" {% if token == analysis_type %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>

      <label class="t-label" style="margin-top:10px;">Visibility</label>
      <select class="t-input" id="ex-visibility" {% if not can_edit %}disabled{% endif %}>
        <option value="public" {% if exercise.is_public %}selected{% endif %}>Public</option>
        <option value="private" {% if not exercise.is_public %}selected{% endif %}>Private</option>
      </select>

      <div class="t-divider" style="height:1px;background:var(--border);margin:16px 0;"></div>

      <div class="t-card-title">Read-only properties</div>
      <table style="font-size:0.82rem;width:100%;">
        <tr><td class="t-muted" style="padding:3px 0;width:40%;">Exercise type</td>
            <td class="t-mono">{{ exercise.data.type|default:"—" }}</td></tr>
        <tr><td class="t-muted" style="padding:3px 0;">Key</td>
            <td>{{ umto_meta.key|default:"—" }}</td></tr>
        <tr><td class="t-muted" style="padding:3px 0;">Meter</td>
            <td>{{ umto_meta.meter|default:"—" }}</td></tr>
        <tr><td class="t-muted" style="padding:3px 0;">Analysis review</td>
            <td>{{ umto_meta.analysis_review_status|default:"none" }}</td></tr>
        <tr><td class="t-muted" style="padding:3px 0;">Official status</td>
            <td>
              {% if exercise.is_official %}Official
              {% else %}{{ exercise.official_review_status }}{% endif %}
            </td></tr>
      </table>

      {% if can_edit %}
      <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;">
        <button class="t-btn t-btn-primary" id="btn-ex-save">Save</button>
        {% if not exercise.is_official and exercise.official_review_status != 'pending' %}
        <button class="t-btn t-btn-ghost" id="btn-ex-submit-review"
                {% if not exercise.is_public %}disabled title="Make public first"{% endif %}>
          Submit for review
        </button>
        {% elif exercise.official_review_status == 'pending' %}
        <span class="t-muted">Submitted — awaiting review</span>
        {% endif %}
      </div>
      {% endif %}
    </div>
  </div>

</div>
{% endblock %}

{% block body_extra %}
<script>
(function() {
  var data = window.__EXERCISE_DATA__;

  // Save
  document.getElementById("btn-ex-save") && document.getElementById("btn-ex-save").addEventListener("click", function() {
    var tags = document.getElementById("ex-tags").value.split(",").map(function(t){ return t.trim(); }).filter(Boolean);
    fetch(data.saveUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": data.csrfToken},
      body: JSON.stringify({
        description: document.getElementById("ex-description").value,
        skill_tags: tags,
        complexity: parseInt(document.getElementById("ex-complexity").value, 10),
        is_public: document.getElementById("ex-visibility").value === "public",
        analysisType: document.getElementById("ex-analysis-type").value,
      }),
    }).then(function(r){ return r.json(); }).then(function(j){ if (j.ok) alert("Saved."); });
  });

  // Submit for review
  document.getElementById("btn-ex-submit-review") && document.getElementById("btn-ex-submit-review").addEventListener("click", function() {
    if (!confirm("Submit this exercise for official review?")) return;
    fetch(data.submitReviewUrl, {method:"POST", headers:{"X-CSRFToken": data.csrfToken}})
      .then(function(r){ return r.json(); })
      .then(function(j){ if (j.ok) location.reload(); else alert(j.error); });
  });

  // VexFlow thumbnail (placeholder — full VexFlow wiring is a follow-up)
  // The canvas is rendered when the score_data endpoint has VexFlow integration.
  // For now, fetch score_data and log it so the wiring point is clear.
  fetch(data.previewUrl)
    .then(function(r){ return r.json(); })
    .then(function(j){
      if (j.score_data) {
        var canvas = document.getElementById("score-preview-canvas");
        var ctx = canvas.getContext("2d");
        ctx.font = "11px sans-serif";
        ctx.fillStyle = "#6c7c80";
        ctx.fillText("Score preview — VexFlow wiring pending", 8, 64);
      }
    })
    .catch(function(){});
})();
</script>
{% endblock %}
```

- [ ] **Add `analysis_type_choices` to `exercise_detail_view` in `views_library.py`**

In `exercise_detail_view`, add to the render context:
```python
    ANALYSIS_TYPE_CHOICES = [
        ("roman", "Roman numeral"),
        ("figured_bass", "Figured bass"),
        ("figured_bass_unabbreviated", "Figured bass (unabbreviated)"),
        ("scale_degree", "Scale degree"),
        ("note_name", "Note name"),
        ("solfege", "Solfège"),
        ("do_based_solfege", "Do-based solfège"),
        ("fixed_do", "Fixed do"),
        ("pitch_class", "Pitch class"),
        ("set_class_prime", "Set class — prime form"),
        ("set_class_forte", "Set class — Forte label"),
        ("set_class_normal", "Set class — normal order"),
        ("set_class_set", "Set class — set notation"),
        ("spacing", "Spacing"),
        ("interval_generic", "Interval (generic)"),
        ("interval_specific", "Interval (specific)"),
    ]
    return render(request, "teacher/exercise_editor.html", {
        "exercise": ex,
        "umto_meta": umto_meta,
        "in_playlists": in_playlists,
        "can_edit": can_edit,
        "analysis_type": ex.data.get("analysisType", "roman") if isinstance(ex.data, dict) else "roman",
        "analysis_type_choices": ANALYSIS_TYPE_CHOICES,
    })
```

- [ ] **Write integration test**

In `apps/teacher/tests/test_library_views.py`, add:
```python
class ExerciseEditorTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="teacher@t.com", password="pass")
        self.ex = Exercise.objects.create(
            description="Test Ex",
            data={"type": "test", "isUMTO": False},
            authored_by=self.teacher,
        )

    def test_exercise_detail_200(self):
        url = reverse("teacher:exercise-detail", args=[self.ex.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test Ex")

    def test_exercise_save_updates_description(self):
        url = reverse("teacher:exercise-save", args=[self.ex.id])
        resp = self.client.post(url, json.dumps({"description": "Updated", "skill_tags": [], "complexity": 5, "is_public": False}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.description, "Updated")

    def test_exercise_save_stores_analysis_type(self):
        url = reverse("teacher:exercise-save", args=[self.ex.id])
        self.client.post(url, json.dumps({"description": "Test Ex", "skill_tags": [], "complexity": 1, "is_public": False, "analysisType": "figured_bass"}),
                         content_type="application/json")
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.data.get("analysisType"), "figured_bass")

    def test_exercise_preview_returns_score_data(self):
        self.ex.data = {"type": "test", "score": {"meta": {}, "measures": []}}
        self.ex.save()
        url = reverse("teacher:exercise-preview", args=[self.ex.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertIn("score_data", body)
```

- [ ] **Run tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_views.ExerciseEditorTest -v 2
```
Expected: PASS.

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/exercise_editor.html \
        apps/teacher/views_library.py \
        apps/teacher/tests/test_library_views.py
git commit -m "feat: exercise editor template with analysis_type dropdown, save, submit-for-review"
```

---

## Task 10: Course detail Settings + Activity tabs

**Files:**
- Modify: `apps/teacher/views.py` (course_detail_view)
- Modify: `apps/teacher/templates/teacher/course_detail.html`

- [ ] **Add Settings/Activity data + remove dashboard URLs from `course_detail_view`**

In `apps/teacher/views.py`, in `course_detail_view`, remove:
```python
    # Dashboard deep-link URLs
    from django.urls import reverse
    dashboard_edit_url = reverse("dashboard:edit-course", args=[course.id])
    dashboard_activity_url = reverse("dashboard:course-activity", args=[course.id])
```

And update the render context — remove `dashboard_edit_url` and `dashboard_activity_url`, add the current tab:
```python
    tab = request.GET.get("tab", "timeline")
    return render(
        request,
        "teacher/course_detail.html",
        {
            "course": course,
            "pco_rows_json": json.dumps(pco_rows),
            "groups_json": json.dumps(groups),
            "activity_json": json.dumps(course.performance_dict),
            "addable_playlists_json": json.dumps(addable_playlists),
            "tab": tab,
        },
    )
```

- [ ] **Update the `window.__COURSE_DATA__` block in `course_detail.html`**

Replace:
```html
  <script>
    window.__COURSE_DATA__ = {
      courseId: "{{ course.id|escapejs }}",
      pcoRows: {{ pco_rows_json|safe }},
      groups: {{ groups_json|safe }},
      activity: {{ activity_json|safe }},
      addablePlaylists: {{ addable_playlists_json|safe }},
      dashboardEditUrl: "{{ dashboard_edit_url|escapejs }}",
      dashboardActivityUrl: "{{ dashboard_activity_url|escapejs }}",
    };
  </script>
```
with:
```html
  <script>
    window.__COURSE_DATA__ = {
      courseId: "{{ course.id|escapejs }}",
      pcoRows: {{ pco_rows_json|safe }},
      groups: {{ groups_json|safe }},
      activity: {{ activity_json|safe }},
      addablePlaylists: {{ addable_playlists_json|safe }},
      csrfToken: "{{ csrf_token }}",
      settingsSaveUrl: "/teacher/courses/{{ course.id|escapejs }}/update-settings/",
    };
  </script>
```

- [ ] **Add tab nav and Settings/Activity panels to `course_detail.html`**

After the `t-list-header` div (after line ~36), insert:
```html
<div class="t-tabs" style="margin-bottom:18px;">
  <a class="t-tab {% if tab == 'timeline' %}t-tab--active{% endif %}"
     href="?tab=timeline">Timeline</a>
  <a class="t-tab {% if tab == 'settings' %}t-tab--active{% endif %}"
     href="?tab=settings">Settings</a>
  <a class="t-tab {% if tab == 'roster' %}t-tab--active{% endif %}"
     href="?tab=roster">Roster</a>
  <a class="t-tab {% if tab == 'activity' %}t-tab--active{% endif %}"
     href="?tab=activity">Activity</a>
</div>
```

Wrap the existing `t-detail-layout` div with `{% if tab == 'timeline' or tab == 'roster' %}...{% endif %}` (the current layout handles both timeline and roster columns).

After that block, add:
```html
{% if tab == 'settings' %}
<div style="max-width:520px;">
  <div class="t-card">
    <div class="t-card-title">Course settings</div>
    <label class="t-label">Title</label>
    <input class="t-input" type="text" id="settings-title" value="{{ course.title|escapejs }}">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;">
      <div>
        <label class="t-label">Start date</label>
        <input class="t-input" type="date" id="settings-start"
               value="{% if course.start_date %}{{ course.start_date|date:'Y-m-d' }}{% endif %}">
      </div>
      <div>
        <label class="t-label">End date</label>
        <input class="t-input" type="date" id="settings-end"
               value="{% if course.end_date %}{{ course.end_date|date:'Y-m-d' }}{% endif %}">
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-top:14px;">
      <button class="t-btn t-btn-primary" id="btn-settings-save">Save settings</button>
    </div>
  </div>
</div>
<script>
document.getElementById("btn-settings-save").addEventListener("click", function() {
  var data = window.__COURSE_DATA__;
  fetch(data.settingsSaveUrl, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRFToken": data.csrfToken},
    body: JSON.stringify({
      title: document.getElementById("settings-title").value,
      start_date: document.getElementById("settings-start").value || null,
      end_date: document.getElementById("settings-end").value || null,
    }),
  }).then(function(r){ return r.json(); }).then(function(j){
    if (j.ok) location.reload();
    else alert(j.error || "Save failed.");
  });
});
</script>
{% endif %}

{% if tab == 'activity' %}
<div>
  <div style="display:flex;gap:10px;align-items:center;margin-bottom:14px;">
    <label class="t-label" style="margin:0;white-space:nowrap;">Playlist:</label>
    <select class="t-input" id="activity-playlist-select" style="max-width:300px;">
      <option value="">All playlists</option>
      {% for pco_row in pco_rows_json_list %}
      <option value="{{ pco_row.playlistId }}">{{ pco_row.playlistName }}</option>
      {% endfor %}
    </select>
  </div>
  <div id="activity-table-container">
    <!-- populated by inline script from course.performance_dict -->
  </div>
  <p class="t-muted" style="margin-top:8px;">
    Progress = exercises attempted / total in playlist. Score = average.
  </p>
</div>
<script>
(function() {
  var activity = window.__COURSE_DATA__.activity || {};
  var container = document.getElementById("activity-table-container");
  var entries = Object.entries(activity);
  if (!entries.length) {
    container.innerHTML = '<p class="t-muted">No activity recorded yet.</p>';
    return;
  }
  var rows = entries.map(function(kv) {
    var name = kv[0];
    var val = kv[1];
    return '<tr><td>' + name + '</td>' +
      '<td>' + (val.pass_mark || "—") + '</td>' +
      '<td>' + (val.time_spent_minutes != null ? val.time_spent_minutes + " min" : "—") + '</td></tr>';
  }).join('');
  container.innerHTML = '<table class="t-table"><thead><tr><th>Student</th><th>Status</th><th>Time spent</th></tr></thead><tbody>' + rows + '</tbody></table>';
})();
</script>
{% endif %}
```

Remove the `<details class="t-legacy-section">` block at the bottom (line ~139-142).

- [ ] **Add `update-settings` URL + view**

In `apps/teacher/views.py`, add:
```python
@teacher_required
@require_POST
def course_settings_view(request, course_id):
    """POST /teacher/courses/<course_id>/update-settings/ — update title and dates."""
    from datetime import date
    course = get_object_or_404(Course, id=course_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if "title" in body:
        course.title = str(body["title"])[:200]
    if "start_date" in body:
        try:
            course.start_date = date.fromisoformat(body["start_date"]) if body["start_date"] else None
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid start_date"}, status=400)
    if "end_date" in body:
        try:
            course.end_date = date.fromisoformat(body["end_date"]) if body["end_date"] else None
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid end_date"}, status=400)
    if course.start_date and course.end_date and course.start_date >= course.end_date:
        return JsonResponse({"error": "start must be before end"}, status=400)
    course.save()
    return JsonResponse({"ok": True})
```

Add to imports at the top of `views.py`:
```python
from django.views.decorators.http import require_http_methods, require_POST
```
(already present — skip if duplicate).

Register in `urls.py`:
```python
from apps.teacher.views import course_settings_view
# in urlpatterns:
path("courses/<str:course_id>/update-settings/", course_settings_view, name="course-update-settings"),
```

- [ ] **Write tests**

In `apps/teacher/tests/test_views_db.py`, add:
```python
class CourseSettingsTabTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="teacher@example.com", password="pass")
        self.pl = _make_playlist(self.teacher)
        import json as _json
        resp = _post_create(self.client, {
            "title": "Course A", "units": [9], "startDate": "2026-09-01", "endDate": "2026-12-01"
        })
        self.course_id = _json.loads(resp.content)["courseId"]

    def test_settings_tab_200(self):
        resp = self.client.get(f"/teacher/courses/{self.course_id}/?tab=settings")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Course settings")

    def test_activity_tab_200(self):
        resp = self.client.get(f"/teacher/courses/{self.course_id}/?tab=activity")
        self.assertEqual(resp.status_code, 200)

    def test_update_settings(self):
        import json as _json
        resp = self.client.post(
            f"/teacher/courses/{self.course_id}/update-settings/",
            data=_json.dumps({"title": "Renamed", "start_date": "2026-09-01", "end_date": "2026-12-15"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        from apps.exercises.models import Course
        c = Course.objects.get(id=self.course_id)
        self.assertEqual(c.title, "Renamed")
```

- [ ] **Run tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_views_db.CourseSettingsTabTest -v 2
```
Expected: PASS.

- [ ] **Commit**

```bash
git add apps/teacher/views.py apps/teacher/urls.py \
        apps/teacher/templates/teacher/course_detail.html \
        apps/teacher/tests/test_views_db.py
git commit -m "feat: add Settings and Activity tabs to course detail; remove dashboard escape hatches"
```

---

## Task 11: Backfill management command

**Files:**
- Create: `apps/exercises/management/commands/backfill_analysis_layer.py`

- [ ] **Create the command**

```python
"""Backfill AnalysisLayer analytics fields on existing UMTO chordal exercises."""
from django.core.management.base import BaseCommand

from apps.exercises.models import Exercise
from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices


class Command(BaseCommand):
    help = "Populate set_class_*, spacing fields in AnalysisLayer for UMTO chordal exercises."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Overwrite existing analytics fields.")
        parser.add_argument("--dry-run", action="store_true", help="Print counts without writing.")

    def handle(self, *args, **options):
        overwrite = options["all"]
        dry_run = options["dry_run"]
        qs = Exercise.objects.filter(data__isUMTO=True)
        updated = skipped = errors = 0

        for ex in qs.iterator(chunk_size=100):
            data = ex.data
            if not isinstance(data, dict):
                continue
            score = data.get("score", {})
            umto = score.get("umto", {}) if isinstance(score, dict) else {}
            meta = umto.get("metadata", {}) if isinstance(umto, dict) else {}
            if meta.get("score_kind") != "chordal":
                continue

            analysis = umto.get("analysis", [])
            if not analysis:
                skipped += 1
                continue

            # Skip if already populated and not overwriting
            if not overwrite and analysis[0].get("content", {}).get("set_class_prime") is not None:
                skipped += 1
                continue

            chords = umto.get("chords", [])
            if not chords:
                skipped += 1
                continue

            key = meta.get("key", "C")
            try:
                new_slices = build_chordal_analysis_slices(chords, harmony_key=key)
            except Exception as e:
                self.stderr.write(f"Exercise {ex.id}: {e}")
                errors += 1
                continue

            # Merge analytics fields into existing slices (by index)
            for i, old_slice in enumerate(analysis):
                if i >= len(new_slices):
                    break
                new_content = new_slices[i].get("content", {})
                old_content = old_slice.get("content", old_slice.get("content", {}))
                for field in ("set_class_prime", "set_class_forte", "set_class_normal",
                              "set_class_set", "spacing", "interval_specific", "interval_generic"):
                    if overwrite or field not in old_content:
                        old_content[field] = new_content.get(field)

            if not dry_run:
                ex.data = data
                ex.save(update_fields=["data"])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. updated={updated}, skipped={skipped}, errors={errors}"
                + (" (dry run)" if dry_run else "")
            )
        )
```

- [ ] **Register in `list_exercise_generators.py`**

In `apps/exercises/management/commands/list_exercise_generators.py`, add to `CATALOG`:
```python
("backfill_analysis_layer", "Backfill set_class/spacing analytics into existing UMTO chordal exercises"),
```

- [ ] **Smoke-test the command**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py backfill_analysis_layer --dry-run
```
Expected: prints `Done. updated=N, skipped=M, errors=0 (dry run)`.

- [ ] **Update `docs/management_commands.md`**

Add under "Backfill / maintenance" section:
```
| `backfill_analysis_layer` | Populate `set_class_*`, `spacing` analytics fields on existing UMTO chordal exercises. Options: `--all` (overwrite), `--dry-run`. |
```

- [ ] **Commit**

```bash
git add apps/exercises/management/commands/backfill_analysis_layer.py \
        apps/exercises/management/commands/list_exercise_generators.py \
        docs/management_commands.md
git commit -m "feat: add backfill_analysis_layer management command"
```

---

## Task 12: Documentation updates

**Files:**
- Modify: `docs/exercise_types.md`
- Modify: `docs/UMTO_GUIDE.md`

- [ ] **Update `docs/exercise_types.md`**

Add a note to the UMTO chordal exercise entry:

> **analysisType storage (as of Phase 3):** The `analysisType` token for identification exercises is now stored explicitly as `exercise.data["analysisType"]` (top-level key in the UMTO wrapper dict, not inside `UMTO.metadata`). `lab/views.py` reads this value and injects it into the frontend payload; exercises without the key fall back to the complexity-score heuristic (`complexity_score == 1` → `"note_name"`, otherwise `"roman"`).
>
> **AnalysisLayer analytics fields (as of Phase 3):** `AnalysisSlice.content` now accepts 7 optional analytics fields (`set_class_prime`, `set_class_forte`, `set_class_normal`, `set_class_set`, `spacing`, `interval_specific`, `interval_generic`). These are populated at save time but are **not read by the identification grader** — the grader still live-computes them from MIDI. They are stored for search/filtering/analytics.

- [ ] **Update `docs/UMTO_GUIDE.md`**

Add to the AnalysisLayer section:

> **New analytics fields (Phase 3):**
> All fields are optional (`None` by default) and are computed at save time by `buildAnalysisSlices` (JS path) or `build_chordal_analysis_slices` (Python path).
>
> | Field | Type | Example | Source |
> |---|---|---|---|
> | `set_class_prime` | `str` | `"(0,1,4)"` | music21 `chord.primeFormString` / JS `to_set_class_prime` |
> | `set_class_forte` | `str` | `"3-11B"` | music21 `chord.forteClassTnI` / JS `to_set_class_forte` |
> | `set_class_normal` | `str` | `"[0,3,7]"` | music21 `chord.normalOrder` / JS `to_set_class_normal` |
> | `set_class_set` | `str` | `"{C,E,G}"` | music21 pitch names / JS `to_set_class_set` |
> | `spacing` | `str` | `"+"` or `"°"` | Computed from upper-voice span / JS `to_spacing` |
> | `interval_specific` | `str` | `"P5"` | JS `to_interval` (2-voice only) |
> | `interval_generic` | `str` | `"5"` | JS `to_interval` (2-voice only) |

- [ ] **Commit**

```bash
git add docs/exercise_types.md docs/UMTO_GUIDE.md
git commit -m "docs: document analysisType storage and new AnalysisLayer analytics fields"
```

---

## Self-review checklist

After all tasks are complete, run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests apps.exercises.tests -v 2
```

Verify:
- [ ] Library hub loads at `/teacher/library/` with all three tabs
- [ ] Playlist editor loads, save works, submit-for-review updates `official_review_status`
- [ ] Superuser can approve/reject from Official tab
- [ ] Exercise editor loads, `analysisType` dropdown saves to `exercise.data["analysisType"]`
- [ ] Course detail Settings tab saves title/dates
- [ ] Course detail Activity tab renders from `performance_dict`
- [ ] `dashboardEditUrl` / `dashboardActivityUrl` no longer appear in `course_detail.html`
- [ ] `backfill_analysis_layer --dry-run` completes without errors
- [ ] `make_umto_schema` produces a schema with all 7 new analytics fields
