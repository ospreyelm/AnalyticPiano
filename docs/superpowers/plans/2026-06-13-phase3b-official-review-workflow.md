# Phase 3B: Official Review Workflow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent spec:** [docs/superpowers/plans/2026-06-13-phase3-curation-workbench.md](2026-06-13-phase3-curation-workbench.md)

**Goal:** Add `official_review_status` to Exercise and Playlist; give teachers a submit-for-review endpoint; give superusers approve/reject endpoints that reassign authorship to the factory account.

**Architecture:** One migration adds `official_review_status = CharField(choices=[none/pending/approved/rejected], default="none")` to both models. Six new POST-only views in a new `apps/teacher/views_library.py` file (three for Exercise, three for Playlist). Factory account resolved via `settings.FACTORY_USER_EMAIL` + `get_or_create`. The superuser-only `/teacher/library/official/` view (built in Plan C) returns 403 for non-superusers — this plan wires the permission contract tested here.

**Tech Stack:** Django 4.x, `@teacher_required` decorator, `request.user.is_superuser` check, `django.conf.settings`.

**Run tests with:**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_official_review_status apps.teacher.tests.test_review_workflow -v 2
```

---

## File map

| File | Action |
|---|---|
| `apps/exercises/models.py` | Add `official_review_status` to `Exercise` and `Playlist` |
| `apps/exercises/migrations/NNNN_official_review_status.py` | Auto-generated migration |
| `apps/exercises/tests/test_official_review_status.py` | New — model field tests |
| `apps/teacher/views_library.py` | Create with submit/approve/reject views |
| `apps/teacher/urls.py` | Register review endpoints |
| `apps/teacher/tests/test_review_workflow.py` | New — permission + transition tests |

---

## Task 1: Model field + migration

**Files:**
- Modify: `apps/exercises/models.py`
- Create: migration (auto-generated)

- [ ] **Write failing model test**

Create `apps/exercises/tests/test_official_review_status.py`:

```python
"""Tests for official_review_status on Exercise and Playlist."""
from django.test import TestCase

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_playlist(author, name="P"):
    return Playlist.objects.create(name=name, authored_by=author)


def _make_exercise(author):
    return save_chordal_umto_exercise(
        description="Test",
        author=author,
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []}],
        key="C", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        source="test", skill_tags=[], complexity=1, is_public=False,
    )


class OfficialReviewStatusModelTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()

    def test_playlist_defaults_to_none(self):
        pl = _make_playlist(self.teacher)
        self.assertEqual(pl.official_review_status, "none")

    def test_exercise_defaults_to_none(self):
        ex = _make_exercise(self.teacher)
        self.assertEqual(ex.official_review_status, "none")

    def test_can_set_pending(self):
        pl = _make_playlist(self.teacher)
        pl.official_review_status = "pending"
        pl.save(update_fields=["official_review_status"])
        pl.refresh_from_db()
        self.assertEqual(pl.official_review_status, "pending")

    def test_can_set_approved(self):
        ex = _make_exercise(self.teacher)
        ex.official_review_status = "approved"
        ex.save(update_fields=["official_review_status"])
        ex.refresh_from_db()
        self.assertEqual(ex.official_review_status, "approved")

    def test_invalid_status_raises(self):
        pl = _make_playlist(self.teacher)
        pl.official_review_status = "unknown"
        with self.assertRaises(Exception):
            pl.full_clean()
```

- [ ] **Run test to confirm it fails**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_official_review_status -v 2
```
Expected: FAIL — field doesn't exist yet.

- [ ] **Add `official_review_status` to `Exercise` in `apps/exercises/models.py`**

Find the `Exercise` class. After the `is_official` field, add:

```python
    REVIEW_NONE     = "none"
    REVIEW_PENDING  = "pending"
    REVIEW_APPROVED = "approved"
    REVIEW_REJECTED = "rejected"
    REVIEW_STATUS_CHOICES = [
        (REVIEW_NONE,     "none"),
        (REVIEW_PENDING,  "pending"),
        (REVIEW_APPROVED, "approved"),
        (REVIEW_REJECTED, "rejected"),
    ]
    official_review_status = models.CharField(
        max_length=16,
        choices=REVIEW_STATUS_CHOICES,
        default=REVIEW_NONE,
        db_index=True,
    )
```

- [ ] **Add the same field to `Playlist` in `apps/exercises/models.py`**

Find the `Playlist` class. After its `is_official` field, add:

```python
    official_review_status = models.CharField(
        max_length=16,
        choices=Exercise.REVIEW_STATUS_CHOICES,
        default=Exercise.REVIEW_NONE,
        db_index=True,
    )
```

Note: `Exercise.REVIEW_STATUS_CHOICES` is reused. If `Playlist` is defined before `Exercise` in the file, define the choices on `Playlist` instead and reference from `Exercise`.

- [ ] **Generate and apply migration**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py makemigrations exercises --name official_review_status
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py migrate
```
Expected: migration created and applied cleanly.

- [ ] **Run model tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_official_review_status -v 2
```
Expected: all pass.

- [ ] **Commit**

```bash
git add apps/exercises/models.py apps/exercises/migrations/ \
        apps/exercises/tests/test_official_review_status.py
git commit -m "feat: add official_review_status field to Exercise and Playlist"
```

---

## Task 2: Submit/approve/reject views

**Files:**
- Create: `apps/teacher/views_library.py`
- Modify: `apps/teacher/urls.py`

- [ ] **Write failing tests**

Create `apps/teacher/tests/test_review_workflow.py`:

```python
"""Tests for submit/approve/reject review endpoints."""
import json
from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Exercise, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_superuser(email="su@t.com"):
    return User.objects.create_superuser(email=email, password="x")


def _make_playlist(author, public=False):
    pl = Playlist.objects.create(name="PL", authored_by=author, is_public=public)
    return pl


def _make_exercise(author, public=False):
    ex = save_chordal_umto_exercise(
        description="Ex",
        author=author,
        chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []}],
        key="C", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        source="test", skill_tags=[], complexity=1, is_public=public,
    )
    return ex


class PlaylistReviewTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="t@t.com", password="x")
        self.pl = _make_playlist(self.teacher, public=False)

    def test_submit_requires_public(self):
        url = reverse("teacher:playlist-submit-review", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.official_review_status, "none")

    def test_submit_sets_pending(self):
        self.pl.is_public = True
        self.pl.save()
        url = reverse("teacher:playlist-submit-review", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.official_review_status, "pending")

    def test_double_submit_rejected(self):
        self.pl.is_public = True
        self.pl.official_review_status = "pending"
        self.pl.save()
        url = reverse("teacher:playlist-submit-review", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)

    def test_approve_requires_superuser(self):
        url = reverse("teacher:playlist-approve", args=[self.pl.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_approve_by_superuser_marks_official(self):
        su = _make_superuser()
        c = Client()
        c.login(email="su@t.com", password="x")
        url = reverse("teacher:playlist-approve", args=[self.pl.id])
        resp = c.post(url)
        self.assertEqual(resp.status_code, 200)
        self.pl.refresh_from_db()
        self.assertTrue(self.pl.is_official)
        self.assertEqual(self.pl.official_review_status, "approved")

    def test_approve_assigns_factory_account(self):
        su = _make_superuser()
        c = Client()
        c.login(email="su@t.com", password="x")
        c.post(reverse("teacher:playlist-approve", args=[self.pl.id]))
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.authored_by.email, settings.FACTORY_USER_EMAIL)

    def test_reject_by_superuser_resets_status(self):
        self.pl.official_review_status = "pending"
        self.pl.save()
        su = _make_superuser()
        c = Client()
        c.login(email="su@t.com", password="x")
        resp = c.post(reverse("teacher:playlist-reject", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 200)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.official_review_status, "none")

    def test_other_teacher_cannot_submit_others_playlist(self):
        other = _make_teacher(email="other@t.com")
        self.pl.is_public = True
        self.pl.save()
        c = Client()
        c.login(email="other@t.com", password="x")
        url = reverse("teacher:playlist-submit-review", args=[self.pl.id])
        resp = c.post(url)
        # 404 — authored_by check hides the object
        self.assertEqual(resp.status_code, 404)


class ExerciseReviewTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.client = Client()
        self.client.login(email="t@t.com", password="x")
        self.ex = _make_exercise(self.teacher, public=False)

    def test_submit_requires_public(self):
        url = reverse("teacher:exercise-submit-review", args=[self.ex.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)

    def test_submit_sets_pending(self):
        self.ex.is_public = True
        self.ex.save(update_fields=["is_public"])
        resp = self.client.post(reverse("teacher:exercise-submit-review", args=[self.ex.id]))
        self.assertEqual(resp.status_code, 200)
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.official_review_status, "pending")

    def test_approve_assigns_factory_and_marks_official(self):
        su = _make_superuser()
        c = Client()
        c.login(email="su@t.com", password="x")
        c.post(reverse("teacher:exercise-approve", args=[self.ex.id]))
        self.ex.refresh_from_db()
        self.assertTrue(self.ex.is_official)
        self.assertEqual(self.ex.authored_by.email, settings.FACTORY_USER_EMAIL)
```

- [ ] **Run tests to confirm they fail**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_review_workflow -v 2
```
Expected: FAIL — URLs not registered yet.

- [ ] **Create `apps/teacher/views_library.py` with review views only**

```python
"""Teacher library views — Phase 3B: official review workflow."""
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.exercises.models import Exercise, Playlist
from apps.teacher.decorators import teacher_required

logger = logging.getLogger(__name__)


def _get_factory_user():
    """Return (or create) the factory account used for approved official content."""
    email = getattr(settings, "FACTORY_USER_EMAIL", "factory@monteverdi.app")
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={"is_active": True},
    )
    return user


# ── Playlist review ────────────────────────────────────────────────────────────

@teacher_required
@require_POST
def playlist_submit_review_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/submit-review/"""
    pl = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
    if not pl.is_public:
        return JsonResponse({"error": "Make the playlist public before submitting."}, status=400)
    if pl.official_review_status in ("pending", "approved"):
        return JsonResponse({"error": f"Already {pl.official_review_status}."}, status=400)
    pl.official_review_status = "pending"
    pl.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True, "status": "pending"})


@teacher_required
@require_POST
def playlist_approve_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/approve/ — superuser only."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    pl = get_object_or_404(Playlist, id=playlist_id)
    factory = _get_factory_user()
    pl.official_review_status = "approved"
    pl.is_official = True
    pl.authored_by = factory
    pl.save(update_fields=["official_review_status", "is_official", "authored_by"])
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def playlist_reject_view(request, playlist_id):
    """POST /teacher/library/playlists/<id>/reject/ — superuser only."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    pl = get_object_or_404(Playlist, id=playlist_id)
    pl.official_review_status = "none"
    pl.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True})


# ── Exercise review ────────────────────────────────────────────────────────────

@teacher_required
@require_POST
def exercise_submit_review_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/submit-review/"""
    ex = get_object_or_404(Exercise, id=exercise_id, authored_by=request.user)
    if not ex.is_public:
        return JsonResponse({"error": "Make the exercise public before submitting."}, status=400)
    if ex.official_review_status in ("pending", "approved"):
        return JsonResponse({"error": f"Already {ex.official_review_status}."}, status=400)
    ex.official_review_status = "pending"
    ex.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True, "status": "pending"})


@teacher_required
@require_POST
def exercise_approve_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/approve/ — superuser only."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    ex = get_object_or_404(Exercise, id=exercise_id)
    factory = _get_factory_user()
    ex.official_review_status = "approved"
    ex.is_official = True
    ex.authored_by = factory
    ex.save(update_fields=["official_review_status", "is_official", "authored_by"])
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def exercise_reject_view(request, exercise_id):
    """POST /teacher/library/exercises/<id>/reject/ — superuser only."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required."}, status=403)
    ex = get_object_or_404(Exercise, id=exercise_id)
    ex.official_review_status = "none"
    ex.save(update_fields=["official_review_status"])
    return JsonResponse({"ok": True})
```

- [ ] **Register URLs in `apps/teacher/urls.py`**

Add import at the top:
```python
from apps.teacher.views_library import (
    playlist_submit_review_view,
    playlist_approve_view,
    playlist_reject_view,
    exercise_submit_review_view,
    exercise_approve_view,
    exercise_reject_view,
)
```

Add to `urlpatterns`:
```python
    path("library/playlists/<str:playlist_id>/submit-review/", playlist_submit_review_view, name="playlist-submit-review"),
    path("library/playlists/<str:playlist_id>/approve/",       playlist_approve_view,        name="playlist-approve"),
    path("library/playlists/<str:playlist_id>/reject/",        playlist_reject_view,         name="playlist-reject"),
    path("library/exercises/<str:exercise_id>/submit-review/", exercise_submit_review_view,  name="exercise-submit-review"),
    path("library/exercises/<str:exercise_id>/approve/",       exercise_approve_view,        name="exercise-approve"),
    path("library/exercises/<str:exercise_id>/reject/",        exercise_reject_view,         name="exercise-reject"),
```

- [ ] **Run all review tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_review_workflow apps.exercises.tests.test_official_review_status -v 2
```
Expected: all pass.

- [ ] **Commit**

```bash
git add apps/teacher/views_library.py apps/teacher/urls.py \
        apps/teacher/tests/test_review_workflow.py
git commit -m "feat: submit/approve/reject review endpoints for playlists and exercises"
```

---

## Self-review checklist

- [ ] Non-superuser teacher gets 403 from approve/reject (not 404)
- [ ] `authored_by` after approval = `settings.FACTORY_USER_EMAIL` user
- [ ] Double-submit returns 400
- [ ] Teacher submitting another teacher's object gets 404 (authored_by filter)
- [ ] Migration is clean: `python manage.py migrate --run-syncdb` shows no drift
