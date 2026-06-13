# Phase 3C: Library Hub + Browse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent spec:** [docs/superpowers/plans/2026-06-13-phase3-curation-workbench.md](2026-06-13-phase3-curation-workbench.md)

**Prerequisite:** Plan 3B must be merged first (`official_review_status` field must exist on Exercise and Playlist, and `views_library.py` must exist to extend).

**Goal:** Add `/teacher/library/` as a three-tab browse surface (Playlists, Exercises, Official). Regular teachers see Playlists and Exercises tabs; the Official tab is superuser-only (403 for others). Also adds the header nav link and the exercise-preview JSON endpoint.

**Architecture:** `library_hub_view` and `exercise_preview_view` added to existing `apps/teacher/views_library.py`. Three HTML templates using `.t-*` CSS classes. New CSS rules appended to `apps/teacher/static/teacher/teacher.css`. The Official tab route (`?tab=official`) returns HTTP 403 if `request.user.is_superuser` is False — it does not silently return an empty list.

**Tech Stack:** Django 4.x, function-based views, `@teacher_required`, existing `.t-*` CSS classes.

**Run tests with:**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_hub -v 2
```

---

## File map

| File | Action |
|---|---|
| `apps/teacher/views_library.py` | Add `library_hub_view`, `exercise_preview_view`, `exercises_search_view` |
| `apps/teacher/urls.py` | Register hub + preview + search routes |
| `apps/teacher/templates/teacher/base.html` | Add Library nav link |
| `apps/teacher/templates/teacher/library_hub.html` | Create |
| `apps/teacher/static/teacher/teacher.css` | Add tab, table, filter-bar styles |
| `apps/teacher/tests/test_library_hub.py` | New |

---

## Task 1: Hub and preview views

**Files:**
- Modify: `apps/teacher/views_library.py` (add to existing file from Plan 3B)
- Modify: `apps/teacher/urls.py`

- [ ] **Write failing tests**

Create `apps/teacher/tests/test_library_hub.py`:

```python
"""Tests for the library hub, preview, and search views."""
import json
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Exercise, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_superuser(email="su@t.com"):
    return User.objects.create_superuser(email=email, password="x")


def _make_playlist(author, name="PL", public=False):
    return Playlist.objects.create(name=name, authored_by=author, is_public=public)


def _make_exercise(author, public=False):
    return save_chordal_umto_exercise(
        description="Ex", author=author,
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []}],
        key="C", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        source="test", skill_tags=[], complexity=1, is_public=public,
    )


class LibraryHubAccessTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_anonymous_redirected(self):
        c = Client()
        resp = c.get(reverse("teacher:library-hub"))
        self.assertIn(resp.status_code, [302, 403])

    def test_teacher_gets_200_playlists_tab(self):
        resp = self.client.get(reverse("teacher:library-hub"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "playlists")

    def test_teacher_gets_200_exercises_tab(self):
        resp = self.client.get(reverse("teacher:library-hub") + "?tab=exercises")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "exercises")

    def test_official_tab_403_for_regular_teacher(self):
        resp = self.client.get(reverse("teacher:library-hub") + "?tab=official")
        self.assertEqual(resp.status_code, 403)

    def test_official_tab_200_for_superuser(self):
        su = _make_superuser()
        c = Client()
        c.login(email="su@t.com", password="x")
        resp = c.get(reverse("teacher:library-hub") + "?tab=official")
        self.assertEqual(resp.status_code, 200)

    def test_own_playlist_appears_in_list(self):
        pl = _make_playlist(self.teacher, "My PL")
        resp = self.client.get(reverse("teacher:library-hub") + "?tab=playlists")
        self.assertIn(pl, resp.context["playlists"])

    def test_public_playlist_from_another_teacher_appears(self):
        other = _make_teacher(email="o@t.com")
        pl = _make_playlist(other, "Public PL", public=True)
        resp = self.client.get(reverse("teacher:library-hub") + "?tab=playlists")
        self.assertIn(pl, resp.context["playlists"])

    def test_private_other_teacher_playlist_hidden(self):
        other = _make_teacher(email="o2@t.com")
        pl = _make_playlist(other, "Private PL", public=False)
        resp = self.client.get(reverse("teacher:library-hub") + "?tab=playlists")
        self.assertNotIn(pl, resp.context["playlists"])

    def test_pending_shows_in_official_tab_for_superuser(self):
        pl = _make_playlist(self.teacher, "Pending PL", public=True)
        pl.official_review_status = "pending"
        pl.save()
        su = _make_superuser()
        c = Client()
        c.login(email="su@t.com", password="x")
        resp = c.get(reverse("teacher:library-hub") + "?tab=official")
        self.assertIn(pl, resp.context["pending_playlists"])


class ExercisePreviewTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="t@t.com", password="x")
        self.ex = _make_exercise(self.teacher)

    def test_preview_returns_score_data(self):
        url = reverse("teacher:exercise-preview", args=[self.ex.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertIn("score_data", body)

    def test_preview_private_other_exercise_404(self):
        other = _make_teacher(email="o@t.com")
        ex2 = _make_exercise(other, public=False)
        url = reverse("teacher:exercise-preview", args=[ex2.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


class ExercisesSearchTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_search_returns_own_exercise(self):
        ex = _make_exercise(self.teacher)
        ex.description = "Unique name XYZ"
        ex.save(update_fields=["description"])
        url = reverse("teacher:exercises-search") + "?q=Unique+name+XYZ"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in json.loads(resp.content)["results"]]
        self.assertIn(ex.id, ids)
```

- [ ] **Run tests to confirm they fail**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_hub -v 2
```
Expected: FAIL — `NoReverseMatch` for `teacher:library-hub`.

- [ ] **Add hub/preview/search views to `apps/teacher/views_library.py`**

Append to the bottom of the existing `views_library.py` (from Plan 3B):

```python
# ── Library hub ────────────────────────────────────────────────────────────────

from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render


@teacher_required
def library_hub_view(request):
    """GET /teacher/library/?tab=[playlists|exercises|official]"""
    tab = request.GET.get("tab", "playlists")

    if tab == "official" and not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Superuser access required.")

    unit_filter    = request.GET.get("unit", "").strip()
    official_filter = request.GET.get("official", "").strip()

    # ── Playlists ──
    pl_qs = Playlist.objects.filter(
        Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)
    ).order_by("-updated")
    if unit_filter:
        pl_qs = pl_qs.filter(skill_tags__contains=[f"unit:{unit_filter}"])
    if official_filter == "official":
        pl_qs = pl_qs.filter(is_official=True)
    elif official_filter == "personal":
        pl_qs = pl_qs.filter(authored_by=request.user)
    playlists = list(pl_qs.annotate(exercise_count=Count("exercises"))[:200])

    # ── Exercises ──
    ex_qs = Exercise.objects.filter(
        Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)
    ).order_by("-updated")
    if unit_filter:
        ex_qs = ex_qs.filter(skill_tags__contains=[f"unit:{unit_filter}"])
    if official_filter == "official":
        ex_qs = ex_qs.filter(is_official=True)
    elif official_filter == "personal":
        ex_qs = ex_qs.filter(authored_by=request.user)
    exercises = list(ex_qs[:200])

    # ── Official tab (superuser only) ──
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
        "tab":              tab,
        "playlists":        playlists,
        "exercises":        exercises,
        "pending_playlists": pending_playlists,
        "pending_exercises": pending_exercises,
        "unit_filter":      unit_filter,
        "official_filter":  official_filter,
    })


# ── Exercise preview endpoint ──────────────────────────────────────────────────

@teacher_required
def exercise_preview_view(request, exercise_id):
    """GET /teacher/library/exercises/<id>/preview/ → {score_data: ...}"""
    ex = get_object_or_404(Exercise, id=exercise_id)
    if not (ex.is_public or ex.is_official or ex.authored_by_id == request.user.pk):
        raise Http404
    score_data = ex.data.get("score") if isinstance(ex.data, dict) else None
    return JsonResponse({"score_data": score_data})


# ── Exercise search (for add-exercise modal in playlist editor) ────────────────

@teacher_required
def exercises_search_view(request):
    """GET /teacher/library/exercises/search/?q=&unit= → {results: [...]}"""
    q    = request.GET.get("q", "").strip()
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

- [ ] **Register new URLs in `apps/teacher/urls.py`**

Add to imports at the top:
```python
from apps.teacher.views_library import (
    # already imported from 3B: submit/approve/reject views
    library_hub_view,
    exercise_preview_view,
    exercises_search_view,
)
```

Add to `urlpatterns`:
```python
    path("library/",                                         library_hub_view,       name="library-hub"),
    path("library/playlists/",                               library_hub_view,       name="library-playlists"),
    path("library/exercises/",                               library_hub_view,       name="library-exercises"),
    path("library/official/",                                library_hub_view,       name="library-official"),
    path("library/exercises/search/",                        exercises_search_view,  name="exercises-search"),
    path("library/exercises/<str:exercise_id>/preview/",     exercise_preview_view,  name="exercise-preview"),
```

- [ ] **Run tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_hub -v 2
```
Expected: FAIL — templates not created yet.

- [ ] **Commit views + URLs (tests will pass once templates exist)**

```bash
git add apps/teacher/views_library.py apps/teacher/urls.py
git commit -m "feat: add library_hub_view, exercise_preview_view, exercises_search_view"
```

---

## Task 2: CSS additions

**Files:**
- Modify: `apps/teacher/static/teacher/teacher.css`

- [ ] **Append new rule blocks to `teacher.css`**

```css
/* ── Library nav ─────────────────────────────────────────────────── */
.t-header-nav { display: flex; gap: 4px; }
.t-nav-link {
  font-family: var(--font-ui);
  font-size: 0.875rem;
  color: rgba(255,255,255,0.75);
  text-decoration: none;
  padding: 6px 14px;
  border-radius: 4px;
}
.t-nav-link:hover, .t-nav-link--active {
  background: rgba(255,255,255,0.18);
  color: #fff;
  font-weight: 700;
}

/* ── Tabs ─────────────────────────────────────────────────────────── */
.t-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border);
  margin-bottom: 18px;
}
.t-tab {
  font-family: var(--font-ui);
  font-size: 0.875rem;
  font-weight: 600;
  padding: 9px 18px;
  color: var(--text-muted);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}
.t-tab--active, .t-tab:hover { color: var(--teal); border-bottom-color: var(--teal); }

/* ── Badge ────────────────────────────────────────────────────────── */
.t-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 700;
  border-radius: 10px;
  padding: 1px 7px;
  margin-left: 5px;
}
.t-badge--warn { background: #fef3c7; color: #b45309; }

/* ── Filter bar ───────────────────────────────────────────────────── */
.t-filter-bar { display: flex; gap: 8px; margin-bottom: 14px; align-items: center; }

/* ── Data table ───────────────────────────────────────────────────── */
.t-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface-2, #fff);
  border: 1px solid var(--border);
  border-radius: var(--radius, 5px);
  font-size: 0.82rem;
}
.t-table th {
  font-family: var(--font-ui);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--text-muted);
  padding: 8px 12px;
  text-align: left;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.t-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); }
.t-table tr:last-child td { border-bottom: none; }
.t-table tr:hover td { background: #f0f6f8; }

/* ── Submission cards (official tab) ──────────────────────────────── */
.t-section-title {
  font-family: var(--font-ui);
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: .05em;
  margin-bottom: 10px;
}
.t-submission-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius, 5px);
  padding: 14px 16px;
  margin-bottom: 10px;
}
.t-submission-actions { display: flex; gap: 6px; flex-shrink: 0; }
.t-btn-success { background: #198754; color: #fff; }
.t-btn-danger  { background: #dc3545; color: #fff; }
.t-mono { font-family: monospace; font-size: 0.75rem; color: var(--text-muted); }
.t-muted { color: var(--text-muted); font-size: 0.82rem; }
```

- [ ] **Commit**

```bash
git add apps/teacher/static/teacher/teacher.css
git commit -m "feat: add tab, table, badge, and submission-card CSS for library hub"
```

---

## Task 3: Header nav link

**Files:**
- Modify: `apps/teacher/templates/teacher/base.html`

- [ ] **Add nav links between brand and user area**

In `base.html`, find:
```html
    <a class="t-header-brand" href="/">Monteverdi</a>
    {% if request.user.is_authenticated %}
      <div class="t-header-user-area">
```

Replace with:
```html
    <a class="t-header-brand" href="/">Monteverdi</a>
    {% if request.user.is_authenticated %}
      <nav class="t-header-nav">
        <a class="t-nav-link {% if 'course' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="{% url 'teacher:course-list' %}">Courses</a>
        <a class="t-nav-link {% if 'library' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="{% url 'teacher:library-hub' %}">Library</a>
        <a class="t-nav-link {% if 'play' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="/teacher/play/">Play</a>
      </nav>
      <div class="t-header-user-area">
```

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/base.html
git commit -m "feat: add Courses/Library/Play nav links to teacher header"
```

---

## Task 4: Library hub template

**Files:**
- Create: `apps/teacher/templates/teacher/library_hub.html`

- [ ] **Create the template**

```django
{# apps/teacher/templates/teacher/library_hub.html #}
{% extends "teacher/base.html" %}

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

{% if tab != 'official' %}
<form class="t-filter-bar" method="get">
  <input type="hidden" name="tab" value="{{ tab }}">
  <input class="t-input t-input-sm" type="text" name="unit"
         value="{{ unit_filter }}" placeholder="Unit (e.g. 9)">
  <select class="t-input t-input-sm" name="official">
    <option value="">All</option>
    <option value="official"  {% if official_filter == 'official'  %}selected{% endif %}>Official only</option>
    <option value="personal"  {% if official_filter == 'personal'  %}selected{% endif %}>Mine only</option>
  </select>
  <button class="t-btn t-btn-ghost t-btn-sm" type="submit">Filter</button>
</form>
{% endif %}

{# ── Playlists ─────────────────────────────────────────────────────── #}
{% if tab == 'playlists' %}
<table class="t-table">
  <thead><tr>
    <th>Name</th><th>Tags</th><th>Exercises</th><th>Official</th><th>Updated</th>
  </tr></thead>
  <tbody>
  {% for pl in playlists %}
  <tr>
    <td><a class="t-link" href="{% url 'teacher:playlist-detail' pl.id %}">{{ pl.name }}</a></td>
    <td class="t-mono">{{ pl.skill_tags|join:", " }}</td>
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

{# ── Exercises ─────────────────────────────────────────────────────── #}
{% if tab == 'exercises' %}
<table class="t-table">
  <thead><tr>
    <th>Description</th><th>Unit</th><th>Complexity</th><th>Official</th><th>Updated</th>
  </tr></thead>
  <tbody>
  {% for ex in exercises %}
  <tr>
    <td><a class="t-link" href="{% url 'teacher:exercise-detail' ex.id %}">{{ ex.description|default:"(no description)" }}</a></td>
    <td class="t-mono">{{ ex.skill_tags|join:", " }}</td>
    <td>{{ ex.complexity }}</td>
    <td>{% if ex.is_official %}✓{% endif %}</td>
    <td>{{ ex.updated|date:"Y-m-d" }}</td>
  </tr>
  {% empty %}
  <tr><td colspan="5" style="color:var(--text-muted);padding:16px;">No exercises found.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}

{# ── Official (superuser) ──────────────────────────────────────────── #}
{% if tab == 'official' %}
<h2 class="t-section-title">Pending review</h2>

{% for pl in pending_playlists %}
<div class="t-submission-card">
  <div>
    <strong>{{ pl.name }}</strong>
    <span class="t-mono">{{ pl.id }}</span><br>
    <span class="t-muted">Playlist · {{ pl.authored_by.email }} · {{ pl.updated|date:"Y-m-d" }}</span>
  </div>
  <div class="t-submission-actions">
    <form method="post" action="{% url 'teacher:playlist-approve' pl.id %}">
      {% csrf_token %}<button class="t-btn t-btn-sm t-btn-success">✓ Approve</button>
    </form>
    <form method="post" action="{% url 'teacher:playlist-reject' pl.id %}">
      {% csrf_token %}<button class="t-btn t-btn-sm t-btn-danger">✗ Reject</button>
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
    <span class="t-muted">Exercise · {{ ex.authored_by.email }} · {{ ex.updated|date:"Y-m-d" }}</span>
  </div>
  <div class="t-submission-actions">
    <form method="post" action="{% url 'teacher:exercise-approve' ex.id %}">
      {% csrf_token %}<button class="t-btn t-btn-sm t-btn-success">✓ Approve</button>
    </form>
    <form method="post" action="{% url 'teacher:exercise-reject' ex.id %}">
      {% csrf_token %}<button class="t-btn t-btn-sm t-btn-danger">✗ Reject</button>
    </form>
  </div>
</div>
{% empty %}
<p class="t-muted">No pending exercise submissions.</p>
{% endfor %}
{% endif %}

{% endblock %}
```

- [ ] **Run all hub tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_library_hub -v 2
```
Expected: all pass.

- [ ] **Browser smoke test**

1. `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver`
2. Visit `/teacher/library/` — confirm Playlists tab loads, table shows own playlists
3. Click Exercises tab — table loads
4. Visit `/teacher/library/?tab=official` as a non-superuser — confirm 403 page

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/library_hub.html
git commit -m "feat: library hub template (Playlists / Exercises / Official tabs)"
```

---

## Self-review checklist

- [ ] `?tab=official` returns 403 for teacher, 200 for superuser
- [ ] Private exercise/playlist from another teacher not visible in browse
- [ ] Public playlist from another teacher IS visible
- [ ] `exercise-preview` returns 404 for inaccessible private exercise
- [ ] Nav active state highlights correctly for library routes
- [ ] Filter by unit narrows results
