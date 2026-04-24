# Student App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clean student-facing Django app at `/s/` that lets students complete Unit 1 pitch identification exercises with Khan Academy-style UX — auto-resume, skill mastery tracking, zero instructor chrome.

**Architecture:** New `apps/student/` Django app with its own URL namespace, views, and templates. Reuses all existing models (`Exercise`, `Playlist`, `Course`, `StudentSkillMastery`) and the existing lab exercise JS engine verbatim. A new `tag_unit_exercises` management command creates and tags the Unit 1 content.

**Tech Stack:** Django 4.x, Python 3.10+, PostgreSQL, RequireJS (existing lab JS), plain CSS (no framework)

---

## File Map

### New files
- `apps/student/__init__.py` — empty
- `apps/student/apps.py` — StudentConfig
- `apps/student/urls.py` — `/s/` namespace, 4 routes
- `apps/student/views.py` — StudentLoginView, HomeView, UnitView, PlayerView
- `apps/student/progress.py` — `get_unit_progress(user, unit_tags)` helper
- `apps/student/templates/student/base.html` — minimal chrome (name, back link)
- `apps/student/templates/student/login.html` — email+password form
- `apps/student/templates/student/home.html` — unit list + auto-resume card
- `apps/student/templates/student/unit.html` — skill rows with mastery state
- `apps/student/templates/student/player.html` — exercise player, no instructor chrome
- `apps/student/static/student/student.css` — clean minimal styles
- `apps/exercises/management/commands/tag_unit_exercises.py` — new management command
- `apps/student/tests/test_views.py` — view tests
- `apps/student/tests/test_progress.py` — progress logic tests

### Modified files
- `harmony/settings/common.py:131` — add `"apps.student"` to INSTALLED_APPS
- `harmony/urls.py` — add `path("s/", include("apps.student.urls"))`

---

## Task 1: Register the student app

**Files:**
- Create: `apps/student/__init__.py`
- Create: `apps/student/apps.py`
- Modify: `harmony/settings/common.py`
- Modify: `harmony/urls.py`

- [ ] **Step 1: Create the app package**

```bash
mkdir -p apps/student/templates/student apps/student/static/student apps/student/tests
touch apps/student/__init__.py apps/student/tests/__init__.py
```

- [ ] **Step 2: Create apps.py**

```python
# apps/student/apps.py
from django.apps import AppConfig


class StudentConfig(AppConfig):
    name = "apps.student"
    verbose_name = "Student"
```

- [ ] **Step 3: Register in INSTALLED_APPS**

In `harmony/settings/common.py`, add after `"apps.dashboard"`:
```python
"apps.student",
```

- [ ] **Step 4: Create urls.py with placeholder**

```python
# apps/student/urls.py
from django.urls import path
from . import views

app_name = "student"

urlpatterns = [
    path("login/", views.StudentLoginView.as_view(), name="login"),
    path("", views.HomeView.as_view(), name="home"),
    path("units/<int:unit_num>/", views.UnitView.as_view(), name="unit"),
    path("units/<int:unit_num>/play/", views.PlayerView.as_view(), name="player"),
]
```

- [ ] **Step 5: Mount in root urls.py**

In `harmony/urls.py`, add after the dashboard line:
```python
path("s/", include("apps.student.urls")),
```

- [ ] **Step 6: Create stub views.py so server starts**

```python
# apps/student/views.py
from django.http import HttpResponse
from django.views import View


class StudentLoginView(View):
    def get(self, request):
        return HttpResponse("login stub")


class HomeView(View):
    def get(self, request):
        return HttpResponse("home stub")


class UnitView(View):
    def get(self, request, unit_num):
        return HttpResponse(f"unit {unit_num} stub")


class PlayerView(View):
    def get(self, request, unit_num):
        return HttpResponse("player stub")
```

- [ ] **Step 7: Verify server starts**

```bash
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 8: Commit**

```bash
git add apps/student/ harmony/settings/common.py harmony/urls.py
git commit -m "feat(student): scaffold student app with stub views"
```

---

## Task 2: Progress helper

**Files:**
- Create: `apps/student/progress.py`
- Create: `apps/student/tests/test_progress.py`

The progress helper aggregates `StudentSkillMastery` records for a list of skill tags and returns structured data per skill. All views use this helper.

- [ ] **Step 1: Write failing tests**

```python
# apps/student/tests/test_progress.py
import pytest
from django.contrib.auth import get_user_model
from apps.exercises.models import StudentSkillMastery
from apps.student.progress import get_unit_progress

User = get_user_model()


@pytest.fixture
def student(db):
    return User.objects.create_user(
        username="student@test.com",
        email="student@test.com",
        password="testpass",
    )


def test_all_not_started_returns_zero_percent(student):
    tags = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
    result = get_unit_progress(student, tags)
    assert result["percent"] == 0
    assert result["mastered_count"] == 0
    assert len(result["skills"]) == 4
    for skill in result["skills"]:
        assert skill["level"] == "not_started"


def test_one_mastered_returns_25_percent(student):
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Note_Names",
        level=StudentSkillMastery.LEVEL_MASTERED,
    )
    tags = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
    result = get_unit_progress(student, tags)
    assert result["percent"] == 25
    assert result["mastered_count"] == 1


def test_skill_level_returned_for_each_tag(student):
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Ledger_Lines",
        level=StudentSkillMastery.LEVEL_PROFICIENT,
    )
    tags = ["Note_Names", "Ledger_Lines"]
    result = get_unit_progress(student, tags)
    levels = {s["tag"]: s["level"] for s in result["skills"]}
    assert levels["Ledger_Lines"] == "proficient"
    assert levels["Note_Names"] == "not_started"


def test_resume_skill_is_first_non_mastered(student):
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Note_Names",
        level=StudentSkillMastery.LEVEL_MASTERED,
    )
    tags = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
    result = get_unit_progress(student, tags)
    assert result["resume_tag"] == "Ledger_Lines"


def test_resume_skill_is_none_when_all_mastered(student):
    tags = ["Note_Names", "Ledger_Lines"]
    for tag in tags:
        StudentSkillMastery.objects.create(
            user=student,
            skill_tag=tag,
            level=StudentSkillMastery.LEVEL_MASTERED,
        )
    result = get_unit_progress(student, tags)
    assert result["resume_tag"] is None
    assert result["percent"] == 100
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest apps/student/tests/test_progress.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` — `progress.py` doesn't exist yet.

- [ ] **Step 3: Implement progress.py**

```python
# apps/student/progress.py
from apps.exercises.models import StudentSkillMastery


def get_unit_progress(user, skill_tags: list[str]) -> dict:
    """
    Returns mastery summary for a list of skill tags for a given user.

    Returns:
        {
            "percent": int (0-100),
            "mastered_count": int,
            "resume_tag": str | None,  # first non-mastered tag
            "skills": [
                {"tag": str, "level": str},  # level matches LEVEL_* constants
                ...
            ]
        }
    """
    mastery_map = {
        m.skill_tag: m.level
        for m in StudentSkillMastery.objects.filter(user=user, skill_tag__in=skill_tags)
    }

    skills = []
    mastered_count = 0
    resume_tag = None

    for tag in skill_tags:
        level = mastery_map.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED)
        skills.append({"tag": tag, "level": level})
        if level == StudentSkillMastery.LEVEL_MASTERED:
            mastered_count += 1
        elif resume_tag is None:
            resume_tag = tag

    total = len(skill_tags)
    percent = int(mastered_count / total * 100) if total else 0

    return {
        "percent": percent,
        "mastered_count": mastered_count,
        "resume_tag": resume_tag,
        "skills": skills,
    }
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest apps/student/tests/test_progress.py -v
```
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/student/progress.py apps/student/tests/test_progress.py
git commit -m "feat(student): add get_unit_progress helper with tests"
```

---

## Task 3: Student login view

**Files:**
- Modify: `apps/student/views.py`
- Create: `apps/student/templates/student/base.html`
- Create: `apps/student/templates/student/login.html`
- Create: `apps/student/static/student/student.css`
- Create: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write failing test**

```python
# apps/student/tests/test_views.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def student(db):
    return User.objects.create_user(
        username="sarah@test.com",
        email="sarah@test.com",
        password="testpass123",
        is_staff=False,
    )


@pytest.fixture
def instructor(db):
    return User.objects.create_user(
        username="prof@test.com",
        email="prof@test.com",
        password="testpass123",
        is_staff=True,
    )


def test_login_get_returns_200(client):
    url = reverse("student:login")
    response = client.get(url)
    assert response.status_code == 200


def test_login_post_valid_redirects_to_home(client, student):
    url = reverse("student:login")
    response = client.post(url, {"email": "sarah@test.com", "password": "testpass123"})
    assert response.status_code == 302
    assert response["Location"] == reverse("student:home")


def test_login_post_invalid_rerenders_form(client, db):
    url = reverse("student:login")
    response = client.post(url, {"email": "nobody@test.com", "password": "wrong"})
    assert response.status_code == 200
    assert b"form" in response.content.lower()


def test_home_redirects_unauthenticated_to_student_login(client):
    url = reverse("student:home")
    response = client.get(url)
    assert response.status_code == 302
    assert "/s/login/" in response["Location"]


def test_home_redirects_instructor_to_dashboard(client, instructor):
    client.force_login(instructor)
    url = reverse("student:home")
    response = client.get(url)
    assert response.status_code == 302
    assert "/dashboard/" in response["Location"]
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest apps/student/tests/test_views.py -v
```
Expected: failures — views return stub `HttpResponse`, not real responses.

- [ ] **Step 3: Create base.html**

```html
{# apps/student/templates/student/base.html #}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}HarmonyLab{% endblock %}</title>
  {% load static %}
  <link href="{% static 'student/student.css' %}" rel="stylesheet">
</head>
<body>
  <header class="s-header">
    <span class="s-header-brand">HarmonyLab</span>
    {% if request.user.is_authenticated %}
      <span class="s-header-user">{{ request.user.first_name|default:request.user.email }}</span>
    {% endif %}
  </header>
  <main class="s-main">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 4: Create login.html**

```html
{# apps/student/templates/student/login.html #}
{% extends "student/base.html" %}
{% block title %}Sign In — HarmonyLab{% endblock %}
{% block content %}
<div class="s-login-wrap">
  <h1 class="s-login-title">Sign in</h1>
  <form method="post" class="s-form">
    {% csrf_token %}
    {% if form.errors %}
      <div class="s-form-error">{{ form.non_field_errors }}</div>
    {% endif %}
    <label class="s-label" for="id_email">Email</label>
    <input class="s-input" type="email" name="email" id="id_email" autofocus required>
    <label class="s-label" for="id_password">Password</label>
    <input class="s-input" type="password" name="password" id="id_password" required>
    <button class="s-btn-primary" type="submit">Sign in</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Create student.css with minimal styles**

```css
/* apps/student/static/student/student.css */
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #222; background: #fff; }

/* Header */
.s-header { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1.25rem; border-bottom: 1px solid #eee; }
.s-header-brand { font-weight: 700; font-size: 1rem; }
.s-header-user { font-size: 0.8rem; color: #888; }

/* Main */
.s-main { max-width: 600px; margin: 0 auto; padding: 1.5rem 1rem; }

/* Login */
.s-login-wrap { max-width: 360px; margin: 3rem auto; }
.s-login-title { font-size: 1.4rem; margin-bottom: 1.5rem; }

/* Form */
.s-form { display: flex; flex-direction: column; gap: 0.6rem; }
.s-label { font-size: 0.85rem; font-weight: 600; }
.s-input { padding: 0.55rem 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-size: 0.95rem; width: 100%; }
.s-input:focus { outline: 2px solid #4A90D9; border-color: transparent; }
.s-form-error { background: #fde8e8; border: 1px solid #f5c6c6; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.85rem; color: #c0392b; }

/* Buttons */
.s-btn-primary { background: #4A90D9; color: white; border: none; border-radius: 6px; padding: 0.6rem 1.25rem; font-size: 0.95rem; cursor: pointer; margin-top: 0.5rem; }
.s-btn-primary:hover { background: #357abd; }
.s-btn-secondary { background: white; color: #555; border: 1px solid #ddd; border-radius: 6px; padding: 0.4rem 0.9rem; font-size: 0.8rem; cursor: pointer; }

/* Back link */
.s-back { color: #4A90D9; font-size: 0.8rem; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
.s-back:hover { text-decoration: underline; }

/* Unit card / resume card */
.s-resume-card { background: #4A90D9; color: white; border-radius: 8px; padding: 1rem 1.25rem; cursor: pointer; margin-bottom: 1.5rem; text-decoration: none; display: block; }
.s-resume-card:hover { background: #357abd; }
.s-resume-label { font-size: 0.72rem; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.25rem; }
.s-resume-title { font-weight: 600; font-size: 0.95rem; }
.s-resume-progress { background: rgba(255,255,255,0.3); height: 4px; border-radius: 2px; margin-top: 0.75rem; }
.s-resume-progress-bar { background: white; height: 4px; border-radius: 2px; }
.s-resume-meta { font-size: 0.75rem; opacity: 0.85; margin-top: 0.4rem; }

/* Unit list */
.s-section-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; color: #888; margin-bottom: 0.5rem; }
.s-unit-card { border: 1px solid #eee; border-radius: 8px; padding: 0.85rem 1rem; margin-bottom: 0.5rem; text-decoration: none; display: block; color: inherit; }
.s-unit-card.active { border-color: #4A90D9; }
.s-unit-card.locked { opacity: 0.5; pointer-events: none; }
.s-unit-card-row { display: flex; justify-content: space-between; align-items: center; }
.s-unit-title { font-weight: 600; font-size: 0.9rem; }
.s-unit-pct { font-size: 0.75rem; color: #4A90D9; }
.s-progress-bar-track { background: #e0e0e0; height: 4px; border-radius: 2px; margin-top: 0.5rem; }
.s-progress-bar-fill { background: #4A90D9; height: 4px; border-radius: 2px; }

/* Skill rows */
.s-skill-row { border: 1px solid #eee; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.75rem; }
.s-skill-row.mastered { border-color: #c8ebc8; }
.s-skill-row.in-progress { border-color: #ffe082; background: #fffdf0; }
.s-skill-dot { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; flex-shrink: 0; }
.s-skill-dot.mastered { background: #4CAF50; color: white; }
.s-skill-dot.in-progress { background: #FF9800; color: white; }
.s-skill-dot.not-started { background: #e0e0e0; color: #999; }
.s-skill-info { flex: 1; }
.s-skill-name { font-weight: 600; font-size: 0.85rem; }
.s-skill-level { font-size: 0.75rem; }
.s-skill-level.mastered { color: #4CAF50; }
.s-skill-level.in-progress { color: #FF9800; }
.s-skill-level.not-started { color: #aaa; }

/* Player */
.s-player-header { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #eee; margin-bottom: 0.75rem; }
.s-player-pos { font-size: 0.75rem; color: #888; }
.s-player-instruction { background: #f0f7ff; border: 1px solid #dce8f5; border-radius: 6px; padding: 0.6rem 0.85rem; font-size: 0.85rem; margin-bottom: 0.75rem; }
.s-player-dots { display: flex; gap: 4px; justify-content: center; padding: 0.5rem 0; }
.s-dot { width: 8px; height: 8px; border-radius: 50%; background: #e0e0e0; }
.s-dot.done { background: #4CAF50; }
.s-dot.current { background: #4A90D9; }

@media (max-width: 600px) {
  .s-main { padding: 1rem 0.75rem; }
}
```

- [ ] **Step 6: Implement StudentLoginView in views.py**

```python
# apps/student/views.py
from django.contrib.auth import authenticate, login as django_login
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View

from apps.accounts.forms import CustomAuthenticationForm


class StudentLoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse("student:home"))
        form = CustomAuthenticationForm()
        return render(request, "student/login.html", {"form": form})

    def post(self, request):
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user = authenticate(username=email, password=password)
            if user is not None:
                django_login(request, user)
                return redirect(reverse("student:home"))
        return render(request, "student/login.html", {"form": form})


def _require_student(view_func):
    """Decorator: redirect unauthenticated → login, instructor → dashboard."""
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('student:login')}?next={request.path}")
        if request.user.is_staff:
            return HttpResponseRedirect("/dashboard/")
        return view_func(self, request, *args, **kwargs)
    return wrapper


class HomeView(View):
    def get(self, request):
        return HttpResponse("home stub")


class UnitView(View):
    def get(self, request, unit_num):
        return HttpResponse(f"unit {unit_num} stub")


class PlayerView(View):
    def get(self, request, unit_num):
        return HttpResponse("player stub")
```

Add the missing import at top of views.py:
```python
from django.http import HttpResponse, HttpResponseRedirect
```

- [ ] **Step 7: Run login tests**

```bash
pytest apps/student/tests/test_views.py::test_login_get_returns_200 apps/student/tests/test_views.py::test_login_post_valid_redirects_to_home apps/student/tests/test_views.py::test_login_post_invalid_rerenders_form apps/student/tests/test_views.py::test_home_redirects_unauthenticated_to_student_login apps/student/tests/test_views.py::test_home_redirects_instructor_to_dashboard -v
```
Expected: all 5 pass. (HomeView/UnitView/PlayerView tests will fail — that's fine, they're next.)

- [ ] **Step 8: Commit**

```bash
git add apps/student/
git commit -m "feat(student): student login view, base template, and CSS"
```

---

## Task 4: HomeView

**Files:**
- Modify: `apps/student/views.py`
- Create: `apps/student/templates/student/home.html`

Unit 1 tags are hardcoded for the pilot. The taxonomy JSON is read once to get unit metadata. Progress is computed via `get_unit_progress`.

- [ ] **Step 1: Write failing tests**

Add to `apps/student/tests/test_views.py`:

```python
def test_home_returns_200_for_student(client, student):
    client.force_login(student)
    url = reverse("student:home")
    response = client.get(url)
    assert response.status_code == 200


def test_home_context_has_units(client, student):
    client.force_login(student)
    url = reverse("student:home")
    response = client.get(url)
    assert "units" in response.context
    assert len(response.context["units"]) >= 1


def test_home_context_has_resume_url_when_in_progress(client, student, db):
    from apps.exercises.models import StudentSkillMastery, Playlist
    # create a playlist for Note_Names so resume_url can be constructed
    # (actual playlist creation tested in Task 9; here we just verify context key exists)
    client.force_login(student)
    url = reverse("student:home")
    response = client.get(url)
    assert "resume_url" in response.context  # may be None if no playlists
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest apps/student/tests/test_views.py::test_home_returns_200_for_student -v
```
Expected: fail — HomeView still returns stub HttpResponse.

- [ ] **Step 3: Implement HomeView**

Replace the HomeView stub in `apps/student/views.py`:

```python
import json
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent / "music_theory_taxonomy_with_branches.json"

# Unit 1 skill tags (fixed for pilot)
UNIT_1_TAGS = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]

def _load_unit_meta(unit_num: int) -> dict:
    """Return title/feat for a unit from taxonomy JSON."""
    with open(TAXONOMY_PATH) as f:
        taxonomy = json.load(f)
    for branch in taxonomy:
        for tier in branch.get("tiers", []):
            for unit in tier.get("units", []):
                if str(unit["n"]) == str(unit_num):
                    return unit
    return {}


class HomeView(View):
    @_require_student
    def get(self, request):
        from apps.student.progress import get_unit_progress

        unit_meta = _load_unit_meta(1)
        unit1_progress = get_unit_progress(request.user, UNIT_1_TAGS)

        # Build resume URL: find playlist for resume_tag
        resume_url = None
        resume_playlist_id = _get_playlist_id_for_tag(unit1_progress["resume_tag"]) if unit1_progress["resume_tag"] else None
        if resume_playlist_id:
            resume_url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={resume_playlist_id}"

        units = [
            {
                "num": 1,
                "title": unit_meta.get("title", "Pitch & Staff Notation"),
                "feat": unit_meta.get("feat", ""),
                "percent": unit1_progress["percent"],
                "mastered_count": unit1_progress["mastered_count"],
                "total_skills": len(UNIT_1_TAGS),
                "locked": False,
                "url": reverse("student:unit", kwargs={"unit_num": 1}),
            },
            {
                "num": 2,
                "title": "Rhythm & Meter",
                "feat": "Simple & compound, ties, dots",
                "percent": 0,
                "mastered_count": 0,
                "total_skills": 0,
                "locked": True,
                "url": None,
            },
        ]

        return render(request, "student/home.html", {
            "units": units,
            "resume_url": resume_url,
            "resume_skill": unit1_progress["resume_tag"],
            "unit1_progress": unit1_progress,
        })
```

Add helper (before HomeView class):
```python
from apps.exercises.models import Playlist

# Tag → primary playlist ID mapping (populated by tag_unit_exercises command)
# Keys are skill tags; values are playlist IDs (string like "P1A2B3").
# This dict is loaded lazily from DB.
def _get_playlist_id_for_tag(tag: str) -> str | None:
    """Return the primary playlist ID for a Unit 1 skill tag."""
    playlist = (
        Playlist.objects.filter(tags__contains=[f"unit:1"], tags__contains=[tag])
        .order_by("name")
        .first()
    )
    return playlist.id if playlist else None
```

- [ ] **Step 4: Create home.html**

```html
{# apps/student/templates/student/home.html #}
{% extends "student/base.html" %}
{% block title %}HarmonyLab{% endblock %}
{% block content %}

{% if resume_url %}
  <a class="s-resume-card" href="{{ resume_url }}">
    <div class="s-resume-label">Pick up where you left off</div>
    <div class="s-resume-title">Unit 1 · {{ resume_skill|default:"Note Names" }}</div>
    <div class="s-resume-progress">
      <div class="s-resume-progress-bar" style="width: {{ unit1_progress.percent }}%"></div>
    </div>
    <div class="s-resume-meta">{{ unit1_progress.mastered_count }} of 4 skills mastered</div>
  </a>
{% endif %}

<div class="s-section-label">Your Units</div>

{% for unit in units %}
  {% if unit.locked %}
    <div class="s-unit-card locked">
      <div class="s-unit-card-row">
        <span class="s-unit-title" style="color:#999">Unit {{ unit.num }} · {{ unit.title }}</span>
        <span style="font-size:0.8rem;color:#ccc">🔒</span>
      </div>
    </div>
  {% else %}
    <a class="s-unit-card active" href="{{ unit.url }}">
      <div class="s-unit-card-row">
        <span class="s-unit-title">Unit {{ unit.num }} · {{ unit.title }}</span>
        <span class="s-unit-pct">{% if unit.percent == 0 %}Start here →{% else %}{{ unit.percent }}%{% endif %}</span>
      </div>
      {% if unit.percent > 0 %}
        <div class="s-progress-bar-track">
          <div class="s-progress-bar-fill" style="width: {{ unit.percent }}%"></div>
        </div>
      {% endif %}
    </a>
  {% endif %}
{% endfor %}

{% endblock %}
```

- [ ] **Step 5: Run home tests**

```bash
pytest apps/student/tests/test_views.py::test_home_returns_200_for_student apps/student/tests/test_views.py::test_home_context_has_units -v
```
Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add apps/student/views.py apps/student/templates/student/home.html
git commit -m "feat(student): HomeView with unit list and auto-resume card"
```

---

## Task 5: UnitView

**Files:**
- Modify: `apps/student/views.py`
- Create: `apps/student/templates/student/unit.html`

- [ ] **Step 1: Write failing tests**

Add to `apps/student/tests/test_views.py`:

```python
def test_unit_view_returns_200_for_student(client, student):
    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 1})
    response = client.get(url)
    assert response.status_code == 200


def test_unit_view_404_for_unknown_unit(client, student):
    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 99})
    response = client.get(url)
    assert response.status_code == 404


def test_unit_view_context_has_skills(client, student):
    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 1})
    response = client.get(url)
    assert "skills" in response.context
    assert len(response.context["skills"]) == 4


def test_unit_view_skill_mastery_state_shown(client, student, db):
    from apps.exercises.models import StudentSkillMastery
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Note_Names",
        level=StudentSkillMastery.LEVEL_MASTERED,
    )
    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 1})
    response = client.get(url)
    skill_map = {s["tag"]: s for s in response.context["skills"]}
    assert skill_map["Note_Names"]["level"] == "mastered"
    assert skill_map["Ledger_Lines"]["level"] == "not_started"
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest apps/student/tests/test_views.py::test_unit_view_returns_200_for_student -v
```
Expected: fail — UnitView still returns stub.

- [ ] **Step 3: Define UNIT_SKILLS config and implement UnitView**

Add constant after `UNIT_1_TAGS` in `apps/student/views.py`:

```python
# Maps unit_num → ordered list of skill definitions for that unit
UNIT_SKILLS = {
    1: [
        {
            "tag": "Note_Names",
            "label": "Note Names",
            "description": "Treble & bass staff note names",
            "primary_voice": "soprano",
        },
        {
            "tag": "Ledger_Lines",
            "label": "Ledger Lines",
            "description": "Notes above and below the staff",
            "primary_voice": "soprano",
        },
        {
            "tag": "clefs",
            "label": "Clefs",
            "description": "Treble and bass clef reading",
            "primary_voice": "soprano",
        },
        {
            "tag": "enharmonic",
            "label": "Enharmonics",
            "description": "Equivalent pitches with different names",
            "primary_voice": "soprano",
        },
    ]
}
```

Replace the UnitView stub:

```python
from django.http import Http404


class UnitView(View):
    @_require_student
    def get(self, request, unit_num):
        from apps.student.progress import get_unit_progress

        skill_defs = UNIT_SKILLS.get(unit_num)
        if skill_defs is None:
            raise Http404(f"Unit {unit_num} not found.")

        tags = [s["tag"] for s in skill_defs]
        progress = get_unit_progress(request.user, tags)
        level_map = {s["tag"]: s["level"] for s in progress["skills"]}

        skills = []
        for skill_def in skill_defs:
            tag = skill_def["tag"]
            level = level_map[tag]
            playlist_id = _get_playlist_id_for_tag(tag)
            play_url = (
                reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={playlist_id}"
                if playlist_id else None
            )
            skills.append({
                "tag": tag,
                "label": skill_def["label"],
                "description": skill_def["description"],
                "level": level,
                "play_url": play_url,
            })

        unit_meta = _load_unit_meta(unit_num)

        return render(request, "student/unit.html", {
            "unit_num": unit_num,
            "unit_title": unit_meta.get("title", f"Unit {unit_num}"),
            "skills": skills,
            "progress": progress,
        })
```

Add `Http404` to the existing import line:
```python
from django.http import Http404, HttpResponse, HttpResponseRedirect
```

- [ ] **Step 4: Create unit.html**

```html
{# apps/student/templates/student/unit.html #}
{% extends "student/base.html" %}
{% block title %}Unit {{ unit_num }} — HarmonyLab{% endblock %}
{% block content %}

<a class="s-back" href="{% url 'student:home' %}">← All Units</a>

<h1 style="font-size:1.1rem;font-weight:700;margin:0 0 0.25rem">Unit {{ unit_num }} · {{ unit_title }}</h1>
<p style="font-size:0.8rem;color:#888;margin:0 0 1rem">{{ progress.mastered_count }} of 4 skills mastered</p>

<div class="s-progress-bar-track" style="margin-bottom:1.5rem">
  <div class="s-progress-bar-fill" style="width:{{ progress.percent }}%"></div>
</div>

<div class="s-section-label">Skills</div>

{% for skill in skills %}
  {% if skill.level == "mastered" %}
    <div class="s-skill-row mastered">
      <div class="s-skill-dot mastered">✓</div>
      <div class="s-skill-info">
        <div class="s-skill-name">{{ skill.label }}</div>
        <div class="s-skill-level mastered">Mastered</div>
      </div>
      {% if skill.play_url %}<a class="s-btn-secondary" href="{{ skill.play_url }}">Practice</a>{% endif %}
    </div>
  {% elif skill.level == "not_started" %}
    <div class="s-skill-row">
      <div class="s-skill-dot not-started">○</div>
      <div class="s-skill-info">
        <div class="s-skill-name">{{ skill.label }}</div>
        <div class="s-skill-level not-started">Not started</div>
      </div>
      {% if skill.play_url %}<a class="s-btn-primary" href="{{ skill.play_url }}">Start</a>{% endif %}
    </div>
  {% else %}
    <div class="s-skill-row in-progress">
      <div class="s-skill-dot in-progress">◑</div>
      <div class="s-skill-info">
        <div class="s-skill-name">{{ skill.label }}</div>
        <div class="s-skill-level in-progress">Keep practicing</div>
      </div>
      {% if skill.play_url %}<a class="s-btn-primary" href="{{ skill.play_url }}">Go →</a>{% endif %}
    </div>
  {% endif %}
{% endfor %}

{% endblock %}
```

- [ ] **Step 5: Run unit tests**

```bash
pytest apps/student/tests/test_views.py -k "unit_view" -v
```
Expected: all 4 unit tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/student/views.py apps/student/templates/student/unit.html
git commit -m "feat(student): UnitView with skill mastery breakdown"
```

---

## Task 6: PlayerView

**Files:**
- Modify: `apps/student/views.py`
- Create: `apps/student/templates/student/player.html`

The player template embeds the existing lab RequireJS exercise engine. It strips all instructor chrome and passes the same `lab_data` JSON the lab's `PlaylistView` provides — so the existing JS works without changes.

- [ ] **Step 1: Write failing tests**

Add to `apps/student/tests/test_views.py`:

```python
def test_player_view_404_without_playlist_param(client, student):
    client.force_login(student)
    url = reverse("student:player", kwargs={"unit_num": 1})
    response = client.get(url)
    assert response.status_code == 404


def test_player_view_404_with_bad_playlist_id(client, student):
    client.force_login(student)
    url = reverse("student:player", kwargs={"unit_num": 1}) + "?playlist=XXXXXX"
    response = client.get(url)
    assert response.status_code == 404
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest apps/student/tests/test_views.py::test_player_view_404_without_playlist_param -v
```
Expected: fail — PlayerView stub returns 200.

- [ ] **Step 3: Implement PlayerView**

Replace PlayerView stub in `apps/student/views.py`:

```python
from apps.exercises.models import Playlist
from lab.views import get_exercise_context  # reuse existing context builder


class PlayerView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        if not playlist_id:
            raise Http404("No playlist specified.")

        playlist = Playlist.objects.filter(id=playlist_id).first()
        if playlist is None:
            raise Http404(f"Playlist '{playlist_id}' not found.")

        exercise_num = int(request.GET.get("n", 1))
        total = playlist.exercises.count()

        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if exercise is None:
            raise Http404("Exercise not found in playlist.")

        exercise_context = get_exercise_context(
            request=request,
            playlist=playlist,
            exercise=exercise,
            exercise_num=exercise_num,
            course=None,
        )

        skill_tags = [t for t in (playlist.tags or []) if not t.startswith("unit:")]
        skill_label = skill_tags[0].replace("_", " ") if skill_tags else playlist.name

        return render(request, "student/player.html", {
            "exercise_context_json": exercise_context.as_json(),
            "exercise_num": exercise_num,
            "total_exercises": total,
            "playlist_id": playlist_id,
            "unit_num": unit_num,
            "skill_label": skill_label,
            "back_url": reverse("student:unit", kwargs={"unit_num": unit_num}),
            "requirejs": request.requirejs if hasattr(request, "requirejs") else None,
        })
```

- [ ] **Step 4: Find the correct exercise_context builder**

The lab uses `get_exercise_context` in `lab/views.py` (lines ~157-301). Check its exact signature:

```bash
grep -n "^def get_exercise_context\|^class.*ExerciseContext" lab/views.py
```

If the function signature differs from what's above, update the PlayerView import/call to match exactly.

- [ ] **Step 5: Create player.html**

```html
{# apps/student/templates/student/player.html #}
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ skill_label }} — HarmonyLab</title>
  <link href="{% static 'css/harmony.css' %}" rel="stylesheet">
  <link href="{% static 'css/ionicons-needed.css' %}" rel="stylesheet">
  <link href="{% static 'student/student.css' %}" rel="stylesheet">
  <style>
    /* Override lab chrome we don't want in student player */
    #menu, .menu-bar, .js-btn-screenshot, .startover-icon,
    #display-options, #key-widget, .audio-controls { display: none !important; }
    /* Tighten top padding since we removed the header rows */
    #container { padding-top: 0; }
  </style>
</head>
<body>
{% autoescape off %}
<div id="container" class="js-fade-in fade" style="opacity: 0;">

  <div class="s-player-header">
    <a class="s-back" href="{{ back_url }}">← {{ skill_label }}</a>
    <span class="s-player-pos">{{ exercise_num }} of {{ total_exercises }}</span>
  </div>

  <div id="staff-area" class="content-area">
    <div id="staffwrapper">
      <div id="user-interaction-solicitation">CLICK TO START AUDIO</div>
      <canvas id="staff"></canvas>
    </div>
    <div id="identification-actions" style="display: none; text-align: center; margin-top: 8px;">
      <button id="identification-submit" class="simple-button">Submit</button>
    </div>
    <div id="instruction-panel">
      <div class="instruction-panel">
        <div class="instruction-panel-content">
          <div class="instruction-panel-col instruction-panel-col1">
            <div id="exercise-info"></div>
            <div id="exercise-status-and-tempo"></div>
          </div>
          <div class="instruction-panel-col instruction-panel-col2">
            <div id="exercise-text"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div id="piano"></div>

  <div class="s-player-dots">
    {% for i in total_exercises|rjust:total_exercises %}
      {# template tag workaround — use range filter below #}
    {% endfor %}
  </div>

</div>
{% endautoescape %}

<script src="{% static 'js/lib/require.js' %}"></script>
<script>requirejs.config({ enforceDefine: true, waitSeconds: 0 });</script>
{% if requirejs %}<script>requirejs.config({{ requirejs.config_json }});</script>{% endif %}
<script>window.appStaticUrl = '{% static "" %}';</script>
<script>
  window.__exerciseContext = {{ exercise_context_json }};
</script>
<script>require(['app/main']);</script>
</body>
</html>
```

- [ ] **Step 6: Add progress dots via template tag**

The dots require a range loop. Django templates don't have `range`. Add a simple template tag:

```python
# apps/student/templatetags/__init__.py  (empty)
# apps/student/templatetags/student_tags.py
from django import template

register = template.Library()

@register.filter
def num_range(value):
    """Return range(value) for use in templates."""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)
```

Then in player.html replace the dots section with:
```html
{% load student_tags %}
<div class="s-player-dots">
  {% for i in total_exercises|num_range %}
    <div class="s-dot {% if forloop.counter == exercise_num %}current{% elif forloop.counter < exercise_num %}done{% endif %}"></div>
  {% endfor %}
</div>
```

Create the templatetags directory:
```bash
mkdir -p apps/student/templatetags
touch apps/student/templatetags/__init__.py
```

- [ ] **Step 7: Run player tests**

```bash
pytest apps/student/tests/test_views.py::test_player_view_404_without_playlist_param apps/student/tests/test_views.py::test_player_view_404_with_bad_playlist_id -v
```
Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add apps/student/
git commit -m "feat(student): PlayerView — clean exercise player wrapping existing JS engine"
```

---

## Task 7: tag_unit_exercises management command

**Files:**
- Create: `apps/exercises/management/commands/tag_unit_exercises.py`

This command tags all exercises in a named playlist and links the playlist to a named course via `PlaylistCourseOrdered`.

- [ ] **Step 1: Write the command**

```python
# apps/exercises/management/commands/tag_unit_exercises.py
from django.core.management import BaseCommand
from apps.exercises.models import Exercise, Playlist, Course, PlaylistCourseOrdered


class Command(BaseCommand):
    help = "Tag all exercises in a playlist with skill tags and link playlist to a course."

    def add_arguments(self, parser):
        parser.add_argument("--playlist", required=True, help="Playlist ID (e.g. P1A2B3)")
        parser.add_argument("--tags", required=True, help="Comma-separated tags (e.g. unit:1,Note_Names)")
        parser.add_argument("--course", required=True, help="Course title to link playlist to")
        parser.add_argument("--order", type=int, default=1, help="Order of this playlist in the course")

    def handle(self, *args, **options):
        playlist_id = options["playlist"]
        tags = [t.strip() for t in options["tags"].split(",") if t.strip()]
        course_title = options["course"]
        order = options["order"]

        playlist = Playlist.objects.filter(id=playlist_id).first()
        if playlist is None:
            self.stdout.write(self.style.ERROR(f"Playlist '{playlist_id}' not found."))
            return

        course = Course.objects.filter(title=course_title).first()
        if course is None:
            self.stdout.write(self.style.ERROR(
                f"Course '{course_title}' not found. Create it in the dashboard first."
            ))
            return

        # Tag playlist itself
        existing = set(playlist.tags or [])
        new_tags = existing | set(tags)
        playlist.tags = list(new_tags)
        playlist.save(update_fields=["tags"])
        self.stdout.write(f"  Playlist tags set to: {playlist.tags}")

        # Tag all exercises in playlist
        exercise_ids = list(
            playlist.exercises.values_list("_id", flat=True)
        )
        updated = Exercise.objects.filter(_id__in=exercise_ids).update(
            skill_tags=tags
        )
        self.stdout.write(f"  Tagged {updated} exercise(s) with {tags}")

        # Link playlist to course
        pco, created = PlaylistCourseOrdered.objects.get_or_create(
            playlist=playlist,
            course=course,
            defaults={"order": order, "authored_by": playlist.authored_by},
        )
        if not created:
            self.stdout.write(f"  Playlist already linked to course at order {pco.order}")
        else:
            self.stdout.write(f"  Linked playlist to course '{course_title}' at order {order}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. Playlist '{playlist.name}' ({playlist_id}) tagged and linked."
        ))
```

- [ ] **Step 2: Check PlaylistCourseOrdered requires authored_by**

```bash
python manage.py shell -c "from apps.exercises.models import PlaylistCourseOrdered; print([f.name for f in PlaylistCourseOrdered._meta.fields])"
```

If `authored_by` is not a field, remove it from the `defaults` dict in the command above.

- [ ] **Step 3: Verify command loads**

```bash
python manage.py tag_unit_exercises --help
```
Expected: shows usage with `--playlist`, `--tags`, `--course`, `--order`.

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/management/commands/tag_unit_exercises.py
git commit -m "feat(exercises): tag_unit_exercises management command"
```

---

## Task 8: Create Unit 1 content

This task creates the Unit 1 Course and 6 playlists in the database. It is done interactively — not automated in tests. Run each import command, note the playlist ID from the output, then tag it.

**Prerequisite:** You need a Bach chorale JSON file with both treble and bass voices. Use `bwv1.6.json` as a starting point for all imports. Adjust `--start` and `--end` to get a reasonable number of exercises per skill.

- [ ] **Step 1: Create the Unit 1 course in the dashboard**

Navigate to `/dashboard/courses/` → Create course titled exactly:
```
Unit 1: Pitch & Staff Notation
```
Note the course ID (shown in the URL or course list).

- [ ] **Step 2: Import Note Names (Treble) playlist**

```bash
python manage.py import_chorale bwv1.6.json \
  --author your@email.com \
  --mode identify \
  --analysis note_name \
  --voice soprano \
  --start 0 --end 8 \
  --public
```
Note the exercise IDs printed. Then find the playlist ID:
```bash
python manage.py shell -c "from apps.exercises.models import Playlist; p = Playlist.objects.order_by('-created').first(); print(p.id, p.name)"
```
Rename via shell if needed:
```bash
python manage.py shell -c "from apps.exercises.models import Playlist; p = Playlist.objects.order_by('-created').first(); p.name = 'Unit 1 — Note Names (Treble)'; p.save()"
```

- [ ] **Step 3: Tag Note Names (Treble)**

```bash
python manage.py tag_unit_exercises \
  --playlist <PLAYLIST_ID> \
  --tags unit:1,Note_Names \
  --course "Unit 1: Pitch & Staff Notation" \
  --order 1
```

- [ ] **Step 4: Repeat for all 5 remaining playlists**

| Playlist name | `--voice` | `--tags` | `--order` |
|--------------|-----------|----------|-----------|
| Unit 1 — Note Names (Bass) | `bass` | `unit:1,Note_Names` | 2 |
| Unit 1 — Ledger Lines | `soprano` | `unit:1,Ledger_Lines` | 3 |
| Unit 1 — Clefs (Treble) | `soprano` | `unit:1,clefs` | 4 |
| Unit 1 — Clefs (Bass) | `bass` | `unit:1,clefs` | 5 |
| Unit 1 — Enharmonics | `soprano` | `unit:1,enharmonic` | 6 |

Run `import_chorale` + rename shell command + `tag_unit_exercises` for each.

- [ ] **Step 5: Verify playlists appear in HomeView**

```bash
python manage.py shell -c "
from apps.exercises.models import Playlist
ps = Playlist.objects.filter(tags__contains=['unit:1'])
for p in ps: print(p.id, p.name, p.tags)
"
```
Expected: 6 playlists listed with `unit:1` in their tags.

- [ ] **Step 6: Verify HomeView shows resume card**

Start the dev server, log in as a non-staff user at `/s/`, confirm:
- Unit 1 card is active, Unit 2 is locked
- After practicing one exercise: auto-resume card appears

---

## Task 9: End-to-end smoke test

Manual verification before deploy.

- [ ] **Step 1: Full student flow test**

As a non-staff user:
1. Go to `/s/login/` — confirm instructor login page does NOT appear
2. Log in → confirm redirect to `/s/`
3. Click Unit 1 → confirm 4 skill rows, all "Not started"
4. Click "Start" on Note Names → confirm player loads with staff and piano
5. Complete one exercise → confirm note identifies and advances
6. Return to `/s/units/1/` → confirm Note Names shows "Attempted" or better
7. Return to `/s/` → confirm resume card appears

- [ ] **Step 2: Instructor redirect test**

Log in as `is_staff=True` user at `/s/` → confirm redirect to `/dashboard/`.

- [ ] **Step 3: Regression test — existing lab unaffected**

Navigate to `/playlists/<any_existing_playlist_id>/1/` → confirm existing lab exercise loads normally with all existing chrome intact.

- [ ] **Step 4: Run full test suite**

```bash
pytest apps/student/ -v
```
Expected: all tests pass.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(student): Unit 1 student app complete — pilot ready"
```

---

## Self-Review

**Spec coverage check:**
- ✅ New `apps/student/` Django app — Task 1
- ✅ `/s/` URL namespace — Task 1
- ✅ StudentLoginView with `success_url='/s/'` — Task 3
- ✅ Instructor redirect to `/dashboard/` — Task 3 (`_require_student`)
- ✅ HomeView: unit list + auto-resume — Task 4
- ✅ UnitView: 4 skill rows with mastery state — Task 5
- ✅ PlayerView: clean player, no instructor chrome — Task 6
- ✅ `?playlist=<id>` routing (not tag-based) — Task 6
- ✅ `get_unit_progress` helper with tests — Task 2
- ✅ Progress % = mastered / 4 — Task 2
- ✅ Mastery levels from `LEVEL_*` constants — Task 2, 5
- ✅ `tag_unit_exercises` command — Task 7
- ✅ Unit 1 content creation (6 playlists, 1 course) — Task 8
- ✅ No regressions in existing lab — Task 9
- ✅ `applySkillFilter` non-blocking for `note_name` — no action needed (confirmed in spec)

**Potential issues to watch:**
- `get_exercise_context` signature in `lab/views.py` — Task 6 Step 4 instructs a check before wiring
- `PlaylistCourseOrdered.authored_by` field existence — Task 7 Step 2 instructs a check
- `Playlist.tags` vs `skill_tags` — the spec uses `tags` (the `ArrayField` on the model); `skill_tags` is on `Exercise`. The `_get_playlist_id_for_tag` query uses `tags__contains` on Playlist — correct.
