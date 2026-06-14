# Phase 3D: Playlist + Exercise Editors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent spec:** [docs/superpowers/plans/2026-06-13-phase3-curation-workbench.md](2026-06-13-phase3-curation-workbench.md)

**Prerequisites:** Plans 3B (review workflow + `official_review_status`) and 3C (library hub URLs + CSS) must be merged first.

**Goal:** Add full playlist and exercise editing surfaces inside the teacher app. Playlist editor: metadata save, drag-reorder exercises, add/remove exercises via a search modal, submit-for-review button. Exercise editor: description/tags/complexity/visibility/analysisType metadata save, submit-for-review button, escape hatch link to raw JSON editor for superusers. No VexFlow thumbnails (Plan 3F).

**Architecture:** Playlist editor view + template at `/teacher/library/playlists/<id>/`. Exercise editor view + template at `/teacher/library/exercises/<id>/`. Mutation views (save, reorder, add-exercise, remove-exercise, exercise-save) are POST-only JSON endpoints. All logic appended to `apps/teacher/views_library.py`.

**Tech Stack:** Django 4.x, inline `<script>` blocks using `fetch()`, existing `.t-*` CSS classes.

**Run tests with:**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_playlist_editor apps.teacher.tests.test_exercise_editor -v 2
```

---

## File map

| File | Action |
|---|---|
| `apps/teacher/views_library.py` | Add playlist + exercise editor views |
| `apps/teacher/urls.py` | Register editor + mutation routes |
| `apps/teacher/templates/teacher/playlist_editor.html` | Create |
| `apps/teacher/templates/teacher/exercise_editor.html` | Create |
| `apps/teacher/static/teacher/teacher.css` | Add editor-specific styles |
| `apps/teacher/tests/test_playlist_editor.py` | New |
| `apps/teacher/tests/test_exercise_editor.py` | New |

---

## Task 1: Playlist editor views

**Files:**
- Modify: `apps/teacher/views_library.py`
- Modify: `apps/teacher/urls.py`

- [ ] **Write failing tests**

Create `apps/teacher/tests/test_playlist_editor.py`:

```python
"""Tests for the playlist editor views."""
import json
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_playlist(author, name="PL"):
    return Playlist.objects.create(name=name, authored_by=author)


def _make_exercise(author):
    return save_chordal_umto_exercise(
        description="Ex", author=author,
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []}],
        key="C", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        source="test", skill_tags=[], complexity=1, is_public=True,
    )


class PlaylistDetailTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.pl = _make_playlist(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_get_200(self):
        resp = self.client.get(reverse("teacher:playlist-detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PL")

    def test_other_teacher_private_playlist_404(self):
        other = _make_teacher(email="o@t.com")
        pl2 = _make_playlist(other)
        resp = self.client.get(reverse("teacher:playlist-detail", args=[pl2.id]))
        self.assertEqual(resp.status_code, 404)

    def test_public_playlist_readable_by_other_teacher(self):
        other = _make_teacher(email="o@t.com")
        pl2 = Playlist.objects.create(name="Pub", authored_by=other, is_public=True)
        resp = self.client.get(reverse("teacher:playlist-detail", args=[pl2.id]))
        self.assertEqual(resp.status_code, 200)


class PlaylistSaveTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.pl = _make_playlist(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def _post(self, payload):
        return self.client.post(
            reverse("teacher:playlist-save", args=[self.pl.id]),
            data=json.dumps(payload), content_type="application/json",
        )

    def test_save_updates_name(self):
        self._post({"name": "Renamed"})
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.name, "Renamed")

    def test_save_updates_skill_tags(self):
        self._post({"skill_tags": ["unit:9", "Cadence_PAC"]})
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.skill_tags, ["unit:9", "Cadence_PAC"])

    def test_save_trims_name_to_64_chars(self):
        self._post({"name": "x" * 100})
        self.pl.refresh_from_db()
        self.assertLessEqual(len(self.pl.name), 64)

    def test_other_teacher_cannot_save(self):
        other = _make_teacher(email="o@t.com")
        c = Client()
        c.login(email="o@t.com", password="x")
        resp = c.post(
            reverse("teacher:playlist-save", args=[self.pl.id]),
            data=json.dumps({"name": "Stolen"}), content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)


class PlaylistAddRemoveTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.pl = _make_playlist(self.teacher)
        self.ex = _make_exercise(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_add_exercise(self):
        resp = self.client.post(
            reverse("teacher:playlist-add-exercise", args=[self.pl.id]),
            data=json.dumps({"exerciseId": self.ex.id}), content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ExercisePlaylistOrdered.objects.filter(
            playlist=self.pl, exercise=self.ex
        ).exists())

    def test_remove_exercise(self):
        epo = ExercisePlaylistOrdered.objects.create(
            playlist=self.pl, exercise=self.ex, order=0
        )
        resp = self.client.post(
            reverse("teacher:playlist-remove-exercise", args=[self.pl.id, epo.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ExercisePlaylistOrdered.objects.filter(pk=epo.pk).exists())

    def test_reorder_exercises(self):
        ex2 = _make_exercise(self.teacher)
        epo1 = ExercisePlaylistOrdered.objects.create(playlist=self.pl, exercise=self.ex, order=0)
        epo2 = ExercisePlaylistOrdered.objects.create(playlist=self.pl, exercise=ex2, order=1)
        resp = self.client.post(
            reverse("teacher:playlist-reorder", args=[self.pl.id]),
            data=json.dumps({"order": [epo2.pk, epo1.pk]}), content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        epo1.refresh_from_db()
        epo2.refresh_from_db()
        self.assertEqual(epo2.order, 0)
        self.assertEqual(epo1.order, 1)
```

- [ ] **Run to confirm failure**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_playlist_editor -v 2
```
Expected: FAIL — `NoReverseMatch`.

- [ ] **Add playlist editor views to `apps/teacher/views_library.py`**

Append:

```python
# ── Playlist editor ────────────────────────────────────────────────────────────

from apps.exercises.models import ExercisePlaylistOrdered


@teacher_required
def playlist_detail_view(request, playlist_id):
    """GET /teacher/library/playlists/<id>/"""
    pl = get_object_or_404(
        Playlist,
        Q(id=playlist_id) & (Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True))
    )
    epo_qs = (
        ExercisePlaylistOrdered.objects.filter(playlist=pl)
        .select_related("exercise")
        .order_by("order")
    )
    exercises_data = [
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
        "exercises_json": json.dumps(exercises_data),
        "can_edit": pl.authored_by_id == request.user.pk or request.user.is_superuser,
        "review_status": pl.official_review_status,
    })


@teacher_required
@require_POST
def playlist_save_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/save/"""
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
    """POST /teacher/library/playlists/<id>/reorder/ — {order: [epo_pk, ...]}"""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
        order = body["order"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "order list required"}, status=400)
    for idx, epo_pk in enumerate(order):
        ExercisePlaylistOrdered.objects.filter(pk=epo_pk, playlist=pl).update(order=idx)
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def playlist_add_exercise_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/add-exercise/ — {exerciseId: str}"""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
        exercise_id = body["exerciseId"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "exerciseId required"}, status=400)
    ex = get_object_or_404(
        Exercise,
        Q(id=exercise_id) & (Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True))
    )
    next_order = ExercisePlaylistOrdered.objects.filter(playlist=pl).count()
    epo = ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex, order=next_order)
    return JsonResponse({"ok": True, "epoId": epo.pk})


@teacher_required
@require_POST
def playlist_remove_exercise_view(request, playlist_id, epo_id):
    """POST /teacher/library/playlists/<id>/remove-exercise/<epo_id>/"""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    epo = get_object_or_404(ExercisePlaylistOrdered, pk=epo_id, playlist=pl)
    epo.delete()
    return JsonResponse({"ok": True})
```

- [ ] **Register playlist editor URLs in `apps/teacher/urls.py`**

Add to imports:
```python
from apps.teacher.views_library import (
    # existing imports from 3B + 3C ...
    playlist_detail_view,
    playlist_save_view,
    playlist_reorder_view,
    playlist_add_exercise_view,
    playlist_remove_exercise_view,
)
```

Add to `urlpatterns`:
```python
    path("library/playlists/<str:playlist_id>/",                              playlist_detail_view,          name="playlist-detail"),
    path("library/playlists/<str:playlist_id>/save/",                         playlist_save_view,            name="playlist-save"),
    path("library/playlists/<str:playlist_id>/reorder/",                      playlist_reorder_view,         name="playlist-reorder"),
    path("library/playlists/<str:playlist_id>/add-exercise/",                 playlist_add_exercise_view,    name="playlist-add-exercise"),
    path("library/playlists/<str:playlist_id>/remove-exercise/<int:epo_id>/", playlist_remove_exercise_view, name="playlist-remove-exercise"),
```

- [ ] **Run playlist editor tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_playlist_editor -v 2
```
Expected: FAIL — templates not yet created. Views should be accessible; error should be `TemplateDoesNotExist`.

- [ ] **Commit views**

```bash
git add apps/teacher/views_library.py apps/teacher/urls.py
git commit -m "feat: playlist editor views (detail, save, reorder, add/remove exercise)"
```

---

## Task 2: Exercise editor views

**Files:**
- Modify: `apps/teacher/views_library.py`
- Modify: `apps/teacher/urls.py`

- [ ] **Write failing tests**

Create `apps/teacher/tests/test_exercise_editor.py`:

```python
"""Tests for the exercise editor views."""
import json
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Exercise, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_exercise(author, public=False):
    return save_chordal_umto_exercise(
        description="Ex", author=author,
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []}],
        key="C", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        source="test", skill_tags=[], complexity=1, is_public=public,
    )


class ExerciseDetailTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.ex = _make_exercise(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_get_200(self):
        resp = self.client.get(reverse("teacher:exercise-detail", args=[self.ex.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ex")

    def test_private_other_exercise_404(self):
        other = _make_teacher(email="o@t.com")
        ex2 = _make_exercise(other, public=False)
        resp = self.client.get(reverse("teacher:exercise-detail", args=[ex2.id]))
        self.assertEqual(resp.status_code, 404)

    def test_context_has_analysis_type_choices(self):
        resp = self.client.get(reverse("teacher:exercise-detail", args=[self.ex.id]))
        self.assertIn("analysis_type_choices", resp.context)
        tokens = [t for t, _ in resp.context["analysis_type_choices"]]
        self.assertIn("roman", tokens)
        self.assertIn("figured_bass", tokens)

    def test_can_edit_own_exercise(self):
        resp = self.client.get(reverse("teacher:exercise-detail", args=[self.ex.id]))
        self.assertTrue(resp.context["can_edit"])

    def test_cannot_edit_others_public_exercise(self):
        other = _make_teacher(email="o@t.com")
        ex2 = _make_exercise(other, public=True)
        resp = self.client.get(reverse("teacher:exercise-detail", args=[ex2.id]))
        self.assertFalse(resp.context["can_edit"])


class ExerciseSaveTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.ex = _make_exercise(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def _post(self, payload):
        return self.client.post(
            reverse("teacher:exercise-save", args=[self.ex.id]),
            data=json.dumps(payload), content_type="application/json",
        )

    def test_save_updates_description(self):
        self._post({"description": "Updated desc"})
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.description, "Updated desc")

    def test_save_trims_description_to_60_chars(self):
        self._post({"description": "x" * 100})
        self.ex.refresh_from_db()
        self.assertLessEqual(len(self.ex.description), 60)

    def test_save_updates_complexity(self):
        self._post({"complexity": 7})
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.complexity, 7)

    def test_save_clamps_complexity(self):
        self._post({"complexity": 99})
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.complexity, 20)

    def test_save_stores_analysis_type(self):
        self._post({"analysisType": "figured_bass"})
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.data.get("analysisType"), "figured_bass")

    def test_save_updates_skill_tags(self):
        self._post({"skill_tags": ["unit:9", "Cadence_PAC"]})
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.skill_tags, ["unit:9", "Cadence_PAC"])

    def test_other_teacher_cannot_save(self):
        other = _make_teacher(email="o@t.com")
        c = Client()
        c.login(email="o@t.com", password="x")
        resp = c.post(
            reverse("teacher:exercise-save", args=[self.ex.id]),
            data=json.dumps({"description": "Stolen"}), content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
```

- [ ] **Run to confirm failure**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_exercise_editor -v 2
```
Expected: FAIL — `NoReverseMatch`.

- [ ] **Add exercise editor views to `apps/teacher/views_library.py`**

Append:

```python
# ── Exercise editor ────────────────────────────────────────────────────────────

ANALYSIS_TYPE_CHOICES = [
    ("roman",                    "Roman numeral"),
    ("figured_bass",             "Figured bass"),
    ("figured_bass_unabbreviated", "Figured bass (unabbreviated)"),
    ("scale_degree",             "Scale degree"),
    ("note_name",                "Note name"),
    ("solfege",                  "Solfège"),
    ("do_based_solfege",         "Do-based solfège"),
    ("fixed_do",                 "Fixed do"),
    ("pitch_class",              "Pitch class"),
    ("set_class_prime",          "Set class — prime form"),
    ("set_class_forte",          "Set class — Forte label"),
    ("set_class_normal",         "Set class — normal order"),
    ("set_class_set",            "Set class — set notation"),
    ("spacing",                  "Spacing"),
    ("interval_generic",         "Interval (generic)"),
    ("interval_specific",        "Interval (specific)"),
]


@teacher_required
def exercise_detail_view(request, exercise_id):
    """GET /teacher/library/exercises/<id>/"""
    ex = get_object_or_404(
        Exercise,
        Q(id=exercise_id) & (Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True))
    )
    in_playlists = list(
        Playlist.objects.filter(exercises=ex).values("id", "name")[:20]
    )
    can_edit = ex.authored_by_id == request.user.pk or request.user.is_superuser
    analysis_type = ex.data.get("analysisType", "roman") if isinstance(ex.data, dict) else "roman"
    umto_meta = {}
    if isinstance(ex.data, dict):
        score = ex.data.get("score", {})
        umto_block = score.get("umto", {}) if isinstance(score, dict) else {}
        meta = umto_block.get("metadata", {}) if isinstance(umto_block, dict) else {}
        umto_meta = {
            "key":                     meta.get("key", ""),
            "meter":                   meta.get("meter", ""),
            "mode":                    meta.get("mode", ""),
            "score_kind":              meta.get("score_kind", ""),
            "analysis_review_status":  meta.get("analysis_review_status", "none"),
            "complexity_score":        meta.get("complexity_score", 1),
        }
    return render(request, "teacher/exercise_editor.html", {
        "exercise":              ex,
        "umto_meta":             umto_meta,
        "in_playlists":          in_playlists,
        "can_edit":              can_edit,
        "analysis_type":         analysis_type,
        "analysis_type_choices": ANALYSIS_TYPE_CHOICES,
        "review_status":         ex.official_review_status,
    })


@teacher_required
@require_POST
def exercise_save_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/save/"""
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
```

- [ ] **Register exercise editor URLs in `apps/teacher/urls.py`**

Add to imports:
```python
from apps.teacher.views_library import (
    # existing...
    exercise_detail_view,
    exercise_save_view,
)
```

Add to `urlpatterns`:
```python
    path("library/exercises/<str:exercise_id>/",       exercise_detail_view, name="exercise-detail"),
    path("library/exercises/<str:exercise_id>/save/",  exercise_save_view,   name="exercise-save"),
```

**Important:** The `exercises/search/` and `exercises/<id>/preview/` routes from Plan 3C must be listed BEFORE `exercises/<str:exercise_id>/` to avoid the string wildcard swallowing them. Verify ordering in `urls.py` after adding.

- [ ] **Run exercise editor tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_exercise_editor -v 2
```
Expected: FAIL — `TemplateDoesNotExist`. Views work; need templates.

- [ ] **Commit views**

```bash
git add apps/teacher/views_library.py apps/teacher/urls.py \
        apps/teacher/tests/test_exercise_editor.py \
        apps/teacher/tests/test_playlist_editor.py
git commit -m "feat: playlist and exercise editor views"
```

---

## Task 3: Playlist editor template

**Files:**
- Create: `apps/teacher/templates/teacher/playlist_editor.html`

- [ ] **Create the template**

```django
{# apps/teacher/templates/teacher/playlist_editor.html #}
{% extends "teacher/base.html" %}

{% block title %}{{ playlist.name }} — Library — Monteverdi{% endblock %}

{% block head_extra %}
<script>
window.__PL__ = {
  id:               "{{ playlist.id|escapejs }}",
  exercises:        {{ exercises_json|safe }},
  canEdit:          {{ can_edit|yesno:"true,false" }},
  reviewStatus:     "{{ review_status|escapejs }}",
  csrfToken:        "{{ csrf_token }}",
  saveUrl:          "{% url 'teacher:playlist-save' playlist.id %}",
  reorderUrl:       "{% url 'teacher:playlist-reorder' playlist.id %}",
  addExUrl:         "{% url 'teacher:playlist-add-exercise' playlist.id %}",
  searchUrl:        "{% url 'teacher:exercises-search' %}",
  submitReviewUrl:  "{% url 'teacher:playlist-submit-review' playlist.id %}",
};
</script>
{% endblock %}

{% block content %}
<div class="t-list-header">
  <div>
    <a class="t-link t-muted" href="{% url 'teacher:library-hub' %}?tab=playlists">← Library</a>
    <h1 class="t-page-title" style="margin-top:4px;">{{ playlist.name }}</h1>
  </div>
</div>

<div class="t-detail-layout">
  <!-- Metadata sidebar -->
  <div class="t-detail-side">
    <div class="t-card">
      <div class="t-card-title">Playlist metadata</div>

      <label class="t-label">Name</label>
      <input class="t-input" id="pl-name" type="text"
             value="{{ playlist.name|escapejs }}" maxlength="64"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Tags (comma-separated)</label>
      <input class="t-input" id="pl-tags" type="text"
             value="{{ playlist.skill_tags|join:', ' }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Visibility</label>
      <select class="t-input" id="pl-visibility" {% if not can_edit %}disabled{% endif %}>
        <option value="public"  {% if playlist.is_public  %}selected{% endif %}>Public</option>
        <option value="private" {% if not playlist.is_public %}selected{% endif %}>Private</option>
      </select>

      <div style="margin-top:8px;">
        <span class="t-label" style="display:inline;">Review status:</span>
        <span class="t-mono">{% if playlist.is_official %}official{% else %}{{ playlist.official_review_status }}{% endif %}</span>
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

  <!-- Exercise list -->
  <div class="t-detail-main">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <h2 class="t-section-title" style="margin:0;">Exercises</h2>
      {% if can_edit %}
      <button class="t-btn t-btn-ghost t-btn-sm" id="btn-add-exercise">+ Add exercise</button>
      {% endif %}
    </div>
    <div id="exercise-list"></div>
  </div>
</div>

<!-- Add exercise modal -->
<div id="add-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:200;align-items:center;justify-content:center;">
  <div style="background:#fff;border-radius:8px;padding:24px;width:90%;max-width:520px;">
    <h3 style="margin-bottom:12px;font-family:var(--font-ui);">Add exercise</h3>
    <input class="t-input" id="modal-q" type="text" placeholder="Search description…">
    <input class="t-input" id="modal-unit" type="text" placeholder="Unit (optional)" style="margin-top:8px;">
    <button class="t-btn t-btn-ghost t-btn-sm" id="btn-modal-search" style="margin-top:8px;">Search</button>
    <div id="modal-results" style="margin-top:12px;max-height:220px;overflow-y:auto;"></div>
    <button class="t-btn t-btn-ghost" id="btn-modal-close" style="margin-top:12px;">Close</button>
  </div>
</div>
{% endblock %}

{% block body_extra %}
<script>
(function() {
  var PL = window.__PL__;

  function renderList(exercises) {
    var el = document.getElementById("exercise-list");
    if (!exercises.length) {
      el.innerHTML = '<p class="t-muted">No exercises in this playlist.</p>';
      return;
    }
    el.innerHTML = '<table class="t-table"><thead><tr><th>#</th><th>Description</th><th>ID</th>' +
      (PL.canEdit ? '<th></th>' : '') + '</tr></thead><tbody>' +
      exercises.map(function(ex, i) {
        return '<tr><td>' + (i+1) + '</td>' +
          '<td>' + (ex.description || "(no description)") + '</td>' +
          '<td class="t-mono">' + ex.id + '</td>' +
          (PL.canEdit ? '<td><button class="t-btn t-btn-sm t-btn-ghost" onclick="removeEx(' + ex.epo_id + ')">Remove</button></td>' : '') +
          '</tr>';
      }).join('') + '</tbody></table>';
  }
  renderList(PL.exercises);

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": PL.csrfToken},
      body: JSON.stringify(body),
    }).then(function(r) { return r.json(); });
  }

  // Save metadata
  document.getElementById("btn-pl-save") && document.getElementById("btn-pl-save").addEventListener("click", function() {
    var tags = document.getElementById("pl-tags").value.split(",").map(function(t){ return t.trim(); }).filter(Boolean);
    post(PL.saveUrl, {
      name: document.getElementById("pl-name").value,
      skill_tags: tags,
      is_public: document.getElementById("pl-visibility").value === "public",
    }).then(function(j) { if (j.ok) location.reload(); else alert(j.error); });
  });

  // Submit for review
  document.getElementById("btn-submit-review") && document.getElementById("btn-submit-review").addEventListener("click", function() {
    if (!confirm("Submit for official review?")) return;
    post(PL.submitReviewUrl, {}).then(function(j) {
      if (j.ok) location.reload(); else alert(j.error);
    });
  });

  // Modal
  var modal = document.getElementById("add-modal");
  document.getElementById("btn-add-exercise") && document.getElementById("btn-add-exercise").addEventListener("click", function() {
    modal.style.display = "flex";
  });
  document.getElementById("btn-modal-close").addEventListener("click", function() {
    modal.style.display = "none";
  });
  document.getElementById("btn-modal-search").addEventListener("click", function() {
    var url = PL.searchUrl + "?q=" + encodeURIComponent(document.getElementById("modal-q").value) +
              "&unit=" + encodeURIComponent(document.getElementById("modal-unit").value);
    fetch(url).then(function(r){ return r.json(); }).then(function(j) {
      var el = document.getElementById("modal-results");
      if (!j.results.length) { el.innerHTML = '<p class="t-muted">No results.</p>'; return; }
      el.innerHTML = j.results.map(function(ex) {
        return '<div style="display:flex;justify-content:space-between;margin-bottom:6px;">' +
          '<span>' + (ex.description || "(no desc)") + ' <span class="t-mono">' + ex.id + '</span></span>' +
          '<button class="t-btn t-btn-sm t-btn-primary" onclick="addEx(\'' + ex.id + '\')">Add</button>' +
        '</div>';
      }).join('');
    });
  });

  window.addEx = function(exId) {
    post(PL.addExUrl, {exerciseId: exId}).then(function(j) {
      if (j.ok) location.reload(); else alert(j.error);
    });
  };

  window.removeEx = function(epoId) {
    if (!confirm("Remove from playlist?")) return;
    fetch("/teacher/library/playlists/" + PL.id + "/remove-exercise/" + epoId + "/",
      {method:"POST", headers:{"X-CSRFToken": PL.csrfToken}})
      .then(function(r){ return r.json(); })
      .then(function(j){ if (j.ok) location.reload(); });
  };
})();
</script>
{% endblock %}
```

- [ ] **Run playlist editor tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_playlist_editor -v 2
```
Expected: all pass.

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/playlist_editor.html
git commit -m "feat: playlist editor template"
```

---

## Task 4: Exercise editor template

**Files:**
- Create: `apps/teacher/templates/teacher/exercise_editor.html`

- [ ] **Create the template**

```django
{# apps/teacher/templates/teacher/exercise_editor.html #}
{% extends "teacher/base.html" %}

{% block title %}{{ exercise.description|default:"Exercise" }} — Library — Monteverdi{% endblock %}

{% block head_extra %}
<script>
window.__EX__ = {
  id:              "{{ exercise.id|escapejs }}",
  canEdit:         {{ can_edit|yesno:"true,false" }},
  csrfToken:       "{{ csrf_token }}",
  saveUrl:         "{% url 'teacher:exercise-save' exercise.id %}",
  submitReviewUrl: "{% url 'teacher:exercise-submit-review' exercise.id %}",
};
</script>
{% endblock %}

{% block content %}
<div class="t-list-header">
  <div>
    <a class="t-link t-muted" href="{% url 'teacher:library-hub' %}?tab=exercises">← Library</a>
    <h1 class="t-page-title" style="margin-top:4px;">
      {{ exercise.description|default:"(no description)" }}
    </h1>
  </div>
</div>

<div class="t-detail-layout">
  <!-- Sidebar: in-playlists + admin link -->
  <div class="t-detail-side">
    <div class="t-card">
      <div class="t-card-title">In playlists</div>
      {% for pl in in_playlists %}
      <div><a class="t-link" href="{% url 'teacher:playlist-detail' pl.id %}">{{ pl.name }}</a></div>
      {% empty %}
      <p class="t-muted">Not in any playlists.</p>
      {% endfor %}
    </div>

    {% if request.user.is_superuser %}
    <div class="t-card" style="margin-top:12px;">
      <div class="t-card-title">Admin escape hatch</div>
      <a class="t-link" href="/dashboard/exercises/{{ exercise.pk }}/edit/" target="_blank">
        Edit raw JSON ↗
      </a>
    </div>
    {% endif %}
  </div>

  <!-- Main: metadata form -->
  <div class="t-detail-main">
    <div class="t-card">
      <div class="t-card-title">Metadata</div>

      <label class="t-label">Description (max 60 chars)</label>
      <input class="t-input" id="ex-description" type="text" maxlength="60"
             value="{{ exercise.description|default:''|escapejs }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Tags (comma-separated)</label>
      <input class="t-input" id="ex-tags" type="text"
             value="{{ exercise.skill_tags|join:', ' }}"
             {% if not can_edit %}disabled{% endif %}>

      <label class="t-label" style="margin-top:10px;">Complexity (1–20)</label>
      <input class="t-input" id="ex-complexity" type="number" min="1" max="20"
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
        <option value="public"  {% if exercise.is_public  %}selected{% endif %}>Public</option>
        <option value="private" {% if not exercise.is_public %}selected{% endif %}>Private</option>
      </select>

      <hr style="border:none;border-top:1px solid var(--border);margin:16px 0;">
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
              {% if exercise.is_official %}official{% else %}{{ review_status }}{% endif %}
            </td></tr>
      </table>

      {% if can_edit %}
      <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;">
        <button class="t-btn t-btn-primary" id="btn-ex-save">Save</button>
        {% if not exercise.is_official and review_status != 'pending' %}
        <button class="t-btn t-btn-ghost" id="btn-ex-submit"
                {% if not exercise.is_public %}disabled title="Make public first"{% endif %}>
          Submit for review
        </button>
        {% elif review_status == 'pending' %}
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
  var EX = window.__EX__;

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": EX.csrfToken},
      body: JSON.stringify(body),
    }).then(function(r) { return r.json(); });
  }

  document.getElementById("btn-ex-save") && document.getElementById("btn-ex-save").addEventListener("click", function() {
    var tags = document.getElementById("ex-tags").value.split(",").map(function(t){ return t.trim(); }).filter(Boolean);
    post(EX.saveUrl, {
      description:  document.getElementById("ex-description").value,
      skill_tags:   tags,
      complexity:   parseInt(document.getElementById("ex-complexity").value, 10),
      is_public:    document.getElementById("ex-visibility").value === "public",
      analysisType: document.getElementById("ex-analysis-type").value,
    }).then(function(j) { if (j.ok) location.reload(); else alert(j.error); });
  });

  document.getElementById("btn-ex-submit") && document.getElementById("btn-ex-submit").addEventListener("click", function() {
    if (!confirm("Submit for official review?")) return;
    post(EX.submitReviewUrl, {}).then(function(j) {
      if (j.ok) location.reload(); else alert(j.error);
    });
  });
})();
</script>
{% endblock %}
```

- [ ] **Add editor card CSS to `teacher.css`**

```css
/* ── Detail layout ────────────────────────────────────────────────── */
.t-detail-layout { display: grid; grid-template-columns: 260px 1fr; gap: 20px; align-items: start; }
@media (max-width: 700px) { .t-detail-layout { grid-template-columns: 1fr; } }
.t-detail-side { display: flex; flex-direction: column; gap: 12px; }
.t-card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius, 5px); padding: 16px; }
.t-card-title { font-family: var(--font-ui); font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); margin-bottom: 10px; }
```

- [ ] **Run all editor tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_playlist_editor apps.teacher.tests.test_exercise_editor -v 2
```
Expected: all pass.

- [ ] **Browser smoke test**

1. Open `/teacher/library/?tab=playlists` — click a playlist → playlist editor loads
2. Edit name, click Save — page reloads with new name
3. Click "Add exercise" — modal opens, search works, exercise added to list
4. Open `/teacher/library/?tab=exercises` — click an exercise → exercise editor loads
5. Change analysisType dropdown, click Save — page reloads; verify `exercise.data.get("analysisType")` via shell:
   ```bash
   DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c \
     "from apps.exercises.models import Exercise; ex = Exercise.objects.order_by('-updated').first(); print(ex.data.get('analysisType'))"
   ```

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/exercise_editor.html \
        apps/teacher/static/teacher/teacher.css
git commit -m "feat: exercise editor template with analysisType dropdown and submit-for-review"
```

---

## Self-review checklist

- [ ] `exercises/search/` URL listed before `exercises/<str:exercise_id>/` in `urls.py`
- [ ] Teacher cannot save another teacher's exercise (404, not 403)
- [ ] analysisType roundtrip: set in dropdown → Save → reload → dropdown shows correct value
- [ ] "Submit for review" button disabled when playlist/exercise is private
- [ ] Superuser sees "Edit raw JSON ↗" escape hatch on exercise editor; regular teacher does not
