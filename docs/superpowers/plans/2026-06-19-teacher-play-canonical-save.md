# Teacher Play Canonical Save Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every `/teacher/play/` save automatically create or reuse one stable playlist per author, unit, and interaction mode, with no teacher-managed playlist destination.

**Architecture:** Add explicit canonical identity fields and a conditional database uniqueness constraint to `Playlist`, then centralize canonical naming, legacy adoption, visibility promotion, locking checks, and ordered appends in one service. Both composed-score and MusicXML save endpoints call that service; the frontend becomes a single-unit, single-mode classifier with a read-only destination preview and superuser defaults for Public and Official.

**Tech Stack:** Django models/migrations/services/tests, PostgreSQL conditional unique constraints and `ArrayField`, RequireJS/UMD JavaScript, Node-based logic tests, Django template tests.

---

## Working-State Note

The branch already contains uncommitted edits in:

- `apps/teacher/views_musicxml.py`
- `lab/static/js/src/components/ui/music_controls.js`
- `lab/templates/play.html`
- `lab/tests/test_add_exercise_view_metadata_db.py`
- `lab/views.py`

These edits began enforcing one unit and repairing the empty playlist renderer. Preserve useful one-unit validation, but replace playlist-picker, description-derived naming, and multi-mode behavior with this plan's canonical-save contract. Do not discard unrelated user changes.

### Task 1: Persist Canonical Playlist Identity

**Files:**
- Modify: `apps/exercises/models.py`
- Create: `apps/exercises/migrations/0069_playlist_teacher_play_identity.py`
- Create: `apps/exercises/tests/test_canonical_playlist_model.py`

- [ ] **Step 1: Write the failing model tests**

Create `apps/exercises/tests/test_canonical_playlist_model.py`:

```python
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.exercises.models import Playlist

User = get_user_model()


class CanonicalPlaylistIdentityTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="canonical@example.com",
            password="x",
        )

    def _create(self, **overrides):
        values = {
            "name": "Unit 11 — Exercises (Roman)",
            "authored_by": self.author,
            "playlist_family": Playlist.FAMILY_TEACHER_PLAY,
            "canonical_unit": 11,
            "canonical_mode": "roman",
            "skill_tags": ["unit:11"],
        }
        values.update(overrides)
        return Playlist.objects.create(**values)

    def test_same_author_unit_mode_and_family_is_unique(self):
        self._create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._create()

    def test_different_modes_are_allowed(self):
        self._create()
        second = self._create(
            name="Unit 11 — Exercises (Play)",
            canonical_mode="play",
        )
        self.assertEqual(second.canonical_mode, "play")

    def test_noncanonical_playlists_are_not_constrained(self):
        Playlist.objects.create(name="Drafts", authored_by=self.author)
        Playlist.objects.create(name="Drafts", authored_by=self.author)
        self.assertEqual(
            Playlist.objects.filter(name="Drafts", authored_by=self.author).count(),
            2,
        )
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_canonical_playlist_model
```

Expected: ERROR because `Playlist.FAMILY_TEACHER_PLAY` and the canonical identity fields do not exist.

- [ ] **Step 3: Add explicit identity fields and the conditional constraint**

In `apps/exercises/models.py`, add to `Playlist`:

```python
    FAMILY_TEACHER_PLAY = "teacher_play"
    PLAYLIST_FAMILY_CHOICES = (
        ("", "Unclassified"),
        (FAMILY_TEACHER_PLAY, "Teacher Play authored exercises"),
    )

    playlist_family = models.CharField(
        max_length=24,
        choices=PLAYLIST_FAMILY_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    canonical_unit = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    canonical_mode = models.CharField(
        max_length=20,
        blank=True,
        default="",
        db_index=True,
    )
```

Update `Playlist.Meta`:

```python
    class Meta:
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "authored_by",
                    "playlist_family",
                    "canonical_unit",
                    "canonical_mode",
                ],
                condition=models.Q(playlist_family="teacher_play"),
                name="uniq_teacher_play_author_unit_mode",
            ),
        ]
```

- [ ] **Step 4: Generate and inspect the migration**

Run:

```bash
rtk summary env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py makemigrations exercises
rtk read apps/exercises/migrations/0069_playlist_teacher_play_identity.py
```

Expected: migration `0069_playlist_teacher_play_identity.py` adds the three fields and `uniq_teacher_play_author_unit_mode`.

- [ ] **Step 5: Run migration checks and model tests**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_canonical_playlist_model
rtk summary env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py makemigrations --check
```

Expected: PASS; `makemigrations --check` reports no changes.

- [ ] **Step 6: Commit the identity schema**

```bash
rtk git add apps/exercises/models.py apps/exercises/migrations/0069_playlist_teacher_play_identity.py apps/exercises/tests/test_canonical_playlist_model.py
rtk git commit -m "feat: add canonical teacher playlist identity"
```

### Task 2: Build the Shared Canonical Playlist Service

**Files:**
- Replace: `apps/exercises/utils/playlist_naming.py`
- Create: `apps/exercises/services/canonical_playlist.py`
- Replace: `apps/exercises/tests/test_playlist_naming.py`
- Create: `apps/exercises/tests/test_canonical_playlist_service.py`

- [ ] **Step 1: Write failing canonical naming tests**

Replace `apps/exercises/tests/test_playlist_naming.py` with:

```python
from django.test import SimpleTestCase

from apps.exercises.utils.playlist_naming import (
    SUPPORTED_TEACHER_PLAY_MODES,
    build_canonical_playlist_name,
    canonical_mode_label,
)


class CanonicalPlaylistNamingTests(SimpleTestCase):
    def test_every_supported_mode_has_a_stable_name(self):
        expected = {
            "play": "Play",
            "roman": "Roman",
            "figures": "Figures",
            "identify": "Identify",
            "harmonization": "Harmonization",
        }
        self.assertEqual(SUPPORTED_TEACHER_PLAY_MODES, tuple(expected))
        for mode, label in expected.items():
            self.assertEqual(canonical_mode_label(mode), label)
            self.assertEqual(
                build_canonical_playlist_name(11, mode),
                f"Unit 11 — Exercises ({label})",
            )

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "Unsupported interaction mode"):
            build_canonical_playlist_name(11, "counterpoint")
```

- [ ] **Step 2: Run naming tests and verify RED**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_playlist_naming
```

Expected: ERROR because the canonical naming API does not exist.

- [ ] **Step 3: Implement the minimal stable naming API**

Replace `apps/exercises/utils/playlist_naming.py` with:

```python
SUPPORTED_TEACHER_PLAY_MODES = (
    "play",
    "roman",
    "figures",
    "identify",
    "harmonization",
)

_MODE_LABELS = {
    "play": "Play",
    "roman": "Roman",
    "figures": "Figures",
    "identify": "Identify",
    "harmonization": "Harmonization",
}


def canonical_mode_label(mode: str) -> str:
    try:
        return _MODE_LABELS[mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported interaction mode: {mode}") from exc


def build_canonical_playlist_name(unit: int, mode: str) -> str:
    return f"Unit {int(unit)} — Exercises ({canonical_mode_label(mode)})"
```

- [ ] **Step 4: Run naming tests and verify GREEN**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_playlist_naming
```

Expected: PASS.

- [ ] **Step 5: Write failing service tests for create, reuse, visibility, ownership, adoption, and locking**

Create `apps/exercises/tests/test_canonical_playlist_service.py` with test cases that call this public API:

```python
playlist = resolve_canonical_playlist(
    author=self.author,
    unit=11,
    mode="roman",
    is_public=True,
    is_official=False,
)
append_exercise_to_canonical_playlist(playlist, self.exercise)
```

Include these concrete assertions:

```python
def test_first_resolution_creates_canonical_playlist(self):
    playlist = self.resolve(unit=11, mode="roman")
    self.assertEqual(playlist.name, "Unit 11 — Exercises (Roman)")
    self.assertEqual(playlist.skill_tags, ["unit:11"])
    self.assertEqual(playlist.playlist_family, Playlist.FAMILY_TEACHER_PLAY)
    self.assertEqual(playlist.canonical_unit, 11)
    self.assertEqual(playlist.canonical_mode, "roman")

def test_repeat_resolution_reuses_same_playlist(self):
    first = self.resolve(unit=11, mode="roman")
    second = self.resolve(unit=11, mode="roman")
    self.assertEqual(second.pk, first.pk)

def test_public_resolution_promotes_but_private_resolution_does_not_demote(self):
    playlist = self.resolve(is_public=False)
    self.assertFalse(playlist.is_public)
    self.resolve(is_public=True)
    playlist.refresh_from_db()
    self.assertTrue(playlist.is_public)
    self.resolve(is_public=False)
    playlist.refresh_from_db()
    self.assertTrue(playlist.is_public)

def test_different_authors_get_different_playlists(self):
    first = self.resolve(author=self.author)
    second = self.resolve(author=self.other_author)
    self.assertNotEqual(first.pk, second.pk)

def test_exact_legacy_row_is_adopted(self):
    legacy = Playlist.objects.create(
        name="Unit 11 — Exercises (Roman)",
        authored_by=self.author,
        skill_tags=["unit:11"],
    )
    resolved = self.resolve(unit=11, mode="roman")
    self.assertEqual(resolved.pk, legacy.pk)
    self.assertEqual(resolved.playlist_family, Playlist.FAMILY_TEACHER_PLAY)

def test_ambiguous_legacy_rows_raise(self):
    for _ in range(2):
        Playlist.objects.create(
            name="Unit 11 — Exercises (Roman)",
            authored_by=self.author,
            skill_tags=["unit:11"],
        )
    with self.assertRaisesMessage(ValueError, "Multiple legacy playlists"):
        self.resolve(unit=11, mode="roman")

def test_corpus_playlist_is_not_reused(self):
    corpus = Playlist.objects.create(
        name="Unit 11 — Cadences (roman)",
        authored_by=self.author,
        skill_tags=["unit:11"],
    )
    resolved = self.resolve(unit=11, mode="roman")
    self.assertNotEqual(resolved.pk, corpus.pk)

def test_locked_playlist_rejects_append(self):
    playlist = self.resolve()
    playlist.locked = True
    playlist.save(update_fields=["locked"])
    with self.assertRaisesMessage(ValueError, "locked"):
        append_exercise_to_canonical_playlist(playlist, self.exercise)

def test_append_uses_next_order(self):
    playlist = self.resolve()
    append_exercise_to_canonical_playlist(playlist, self.exercise)
    append_exercise_to_canonical_playlist(playlist, self.other_exercise)
    self.assertEqual(
        list(
            ExercisePlaylistOrdered.objects.filter(playlist=playlist)
            .order_by("order")
            .values_list("order", flat=True)
        ),
        [1, 2],
    )
```

Create the append fixtures in `setUp()` through the shared sanctioned test helper:

```python
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

self.exercise = make_umto_exercise(
    self.author,
    description="First canonical service exercise",
    unit=11,
)
self.other_exercise = make_umto_exercise(
    self.author,
    description="Second canonical service exercise",
    unit=11,
)
```

- [ ] **Step 6: Run service tests and verify RED**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_canonical_playlist_service
```

Expected: ERROR because `canonical_playlist.py` does not exist.

- [ ] **Step 7: Implement the shared service**

Create `apps/exercises/services/canonical_playlist.py` with:

```python
from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.utils.playlist_naming import build_canonical_playlist_name


def resolve_canonical_playlist(
    *,
    author,
    unit: int,
    mode: str,
    is_public: bool,
    is_official: bool,
) -> Playlist:
    unit = int(unit)
    name = build_canonical_playlist_name(unit, mode)
    identity = {
        "authored_by": author,
        "playlist_family": Playlist.FAMILY_TEACHER_PLAY,
        "canonical_unit": unit,
        "canonical_mode": mode,
    }

    with transaction.atomic():
        playlist = Playlist.objects.select_for_update().filter(**identity).first()
        if playlist is None:
            legacy = list(
                Playlist.objects.select_for_update().filter(
                    authored_by=author,
                    name=name,
                    playlist_family="",
                )
            )
            if len(legacy) > 1:
                raise ValueError(f"Multiple legacy playlists match {name}.")
            if legacy:
                playlist = legacy[0]
                if playlist.skill_tags != [f"unit:{unit}"]:
                    raise ValueError(f"Legacy playlist {name} has contradictory unit tags.")
                for field, value in identity.items():
                    if field != "authored_by":
                        setattr(playlist, field, value)
                playlist.is_official = playlist.is_official or is_official
                playlist.is_public = playlist.is_public or is_public
                playlist.save()
            else:
                try:
                    with transaction.atomic():
                        playlist = Playlist.objects.create(
                            name=name,
                            skill_tags=[f"unit:{unit}"],
                            is_public=is_public,
                            is_official=is_official,
                            **identity,
                        )
                except IntegrityError:
                    playlist = Playlist.objects.select_for_update().get(**identity)

        changed = []
        if is_public and not playlist.is_public:
            playlist.is_public = True
            changed.append("is_public")
        if is_official and not playlist.is_official:
            playlist.is_official = True
            changed.append("is_official")
        if changed:
            playlist.save(update_fields=changed)
        return playlist


def append_exercise_to_canonical_playlist(playlist: Playlist, exercise) -> None:
    with transaction.atomic():
        locked_playlist = Playlist.objects.select_for_update().get(pk=playlist.pk)
        if locked_playlist.has_been_performed:
            raise ValueError("Canonical playlist is locked because it has been performed.")
        next_order = (
            ExercisePlaylistOrdered.objects.filter(playlist=locked_playlist)
            .aggregate(max_order=Max("order"))["max_order"]
            or 0
        ) + 1
        ExercisePlaylistOrdered.objects.create(
            playlist=locked_playlist,
            exercise=exercise,
            order=next_order,
        )
```

Keep the final implementation this small; do not add a generic playlist repository.

- [ ] **Step 8: Run service tests and the model constraint tests**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_playlist_naming apps.exercises.tests.test_canonical_playlist_service apps.exercises.tests.test_canonical_playlist_model
```

Expected: PASS.

- [ ] **Step 9: Commit the shared service**

```bash
rtk git add apps/exercises/utils/playlist_naming.py apps/exercises/services/canonical_playlist.py apps/exercises/tests/test_playlist_naming.py apps/exercises/tests/test_canonical_playlist_service.py
rtk git commit -m "feat: resolve canonical teacher playlists"
```

### Task 3: Route Composed Exercise Saves Through the Service

**Files:**
- Modify: `lab/views.py`
- Modify: `lab/tests/test_add_exercise_view_metadata_db.py`
- Modify: `lab/tests/test_add_exercise_view_db.py`

- [ ] **Step 1: Rewrite endpoint tests for one mode and automatic destinations**

In `lab/tests/test_add_exercise_view_metadata_db.py`, make `_post()` default to:

```python
payload.setdefault("skillTags", ["unit:11"])
payload.setdefault("mode", "roman")
payload.pop("playlistId", None)
payload.pop("playlistName", None)
payload.pop("modes", None)
```

Add or update tests:

```python
def test_save_creates_canonical_playlist_without_playlist_payload(self):
    response = self._post({"chord": self._chords(), "description": "First"})
    self.assertEqual(response.status_code, 201, response.content)
    playlist = Playlist.objects.get(id=response.json()["playlistId"])
    self.assertEqual(playlist.name, "Unit 11 — Exercises (Roman)")

def test_different_descriptions_reuse_one_playlist(self):
    first = self._post({"chord": self._chords(), "description": "First"})
    second = self._post({"chord": self._chords(), "description": "Second"})
    self.assertEqual(first.json()["playlistId"], second.json()["playlistId"])
    self.assertEqual(
        Playlist.objects.filter(
            authored_by=self.user,
            playlist_family=Playlist.FAMILY_TEACHER_PLAY,
            canonical_unit=11,
            canonical_mode="roman",
        ).count(),
        1,
    )

def test_different_modes_use_different_playlists(self):
    roman = self._post({"chord": self._chords(), "mode": "roman"})
    play = self._post({"chord": self._chords(), "mode": "play"})
    self.assertNotEqual(roman.json()["playlistId"], play.json()["playlistId"])

def test_multiple_modes_are_rejected(self):
    response = self._post({
        "chord": self._chords(),
        "modes": ["play", "roman"],
    })
    self.assertEqual(response.status_code, 400)
    self.assertIn("exactly one", response.json()["error"].lower())

def test_playlist_override_fields_are_rejected(self):
    response = self._post({
        "chord": self._chords(),
        "playlistId": "PA0001",
    })
    self.assertEqual(response.status_code, 400)
    self.assertIn("automatic", response.json()["error"].lower())
```

Retain the existing zero/multiple-unit tests and official/factory-user tests.

- [ ] **Step 2: Run endpoint tests and verify RED**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test lab.tests.test_add_exercise_view_metadata_db lab.tests.test_add_exercise_view_db
```

Expected: FAIL because the endpoint still accepts multi-mode and playlist destination fields.

- [ ] **Step 3: Replace playlist parsing and multi-mode fan-out**

In `lab/views.py`:

1. Add `_single_mode(payload)` that rejects `modes`, requires one `mode`, and validates it against `SUPPORTED_TEACHER_PLAY_MODES`.
2. Add `_single_unit(skill_tags)` that returns the integer from the one validated `unit:N` tag.
3. Reject non-empty `playlistId` or `playlistName` with:

```python
raise ValueError("Playlist destination is automatic for teacher-play saves.")
```

4. Remove `_append_to_playlist()` and imports used only by it.
5. Replace the `for mode in selected_modes:` loop with one exercise creation using the validated `mode`.
6. Remove `effective_is_public = True if save_as_official else is_public`; the editable Public checkbox remains authoritative even for official saves.
7. After creating the exercise, call:

```python
playlist = resolve_canonical_playlist(
    author=author,
    unit=unit,
    mode=mode,
    is_public=is_public,
    is_official=save_as_official,
)
append_exercise_to_canonical_playlist(playlist, exercise)
```

8. Pass `is_public` to the exercise factory and return one `id`, `playlistId`, and `playlistName`. Preserve compatibility fields as `ids: [id]` and `playlists: [{"id": playlist.id, "name": playlist.name, "mode": mode}]`.

- [ ] **Step 4: Run endpoint tests and verify GREEN**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test lab.tests.test_add_exercise_view_metadata_db lab.tests.test_add_exercise_view_db
```

Expected: PASS.

- [ ] **Step 5: Commit composed-save integration**

```bash
rtk git add lab/views.py lab/tests/test_add_exercise_view_metadata_db.py lab/tests/test_add_exercise_view_db.py
rtk git commit -m "feat: auto-route composed exercises by unit and mode"
```

### Task 4: Route MusicXML Saves Through the Same Service

**Files:**
- Modify: `apps/teacher/views_musicxml.py`
- Modify: `apps/teacher/tests/test_musicxml_import_views.py`

- [ ] **Step 1: Write failing MusicXML parity tests**

Update MusicXML POST helpers to default to:

```python
"unit": "11",
"mode": "roman",
```

Remove default `playlist_id`, `playlist_name`, and multi-mode values. Add:

```python
def test_save_automatically_creates_canonical_playlist(self):
    response = self._post_save(description="Imported cadence")
    self.assertEqual(response.status_code, 201, response.content)
    playlist = Playlist.objects.get(id=response.json()["playlistId"])
    self.assertEqual(playlist.name, "Unit 11 — Exercises (Roman)")

def test_repeated_musicxml_saves_reuse_destination(self):
    first = self._post_save(description="First import")
    second = self._post_save(description="Second import")
    self.assertEqual(first.json()["playlistId"], second.json()["playlistId"])

def test_musicxml_and_composed_save_share_destination_identity(self):
    composed = self.client.post(
        "/exercises/add/",
        data={"data": json.dumps(self._composed_payload(unit=11, mode="roman"))},
    )
    imported = self._post_save(description="Imported")
    self.assertEqual(composed.json()["playlistId"], imported.json()["playlistId"])

def test_musicxml_rejects_multiple_modes(self):
    response = self._post_save(modes=["play", "roman"])
    self.assertEqual(response.status_code, 400)
    self.assertIn("exactly one", response.json()["error"].lower())
```

Keep the existing official-save assertions, changing expected playlist names to the canonical stable name.

- [ ] **Step 2: Run MusicXML tests and verify RED**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.teacher.tests.test_musicxml_import_views
```

Expected: FAIL because MusicXML still accepts explicit playlist targets and fans out multiple modes.

- [ ] **Step 3: Replace MusicXML playlist and mode handling**

In `apps/teacher/views_musicxml.py`:

1. Validate exactly one non-empty unit.
2. Read exactly one `mode`; reject `modes` containing zero or multiple values.
3. Reject `playlist_id` and `playlist_name`.
4. Remove `build_new_playlist_name`, `extract_playlist_mode`, direct `Playlist.objects.get_or_create`, and direct `ExercisePlaylistOrdered` ordering logic.
5. Create one exercise for the selected mode.
6. Remove the official-save override that forces `effective_is_public=True`; pass the submitted `is_public` to both exercise creation and playlist resolution.
7. Resolve and append using `resolve_canonical_playlist()` and `append_exercise_to_canonical_playlist()`.
8. Pass the resolved playlist to `generate_transposed_copies()` so transpositions remain in the same destination.

- [ ] **Step 4: Run MusicXML and composed endpoint tests**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.teacher.tests.test_musicxml_import_views lab.tests.test_add_exercise_view_metadata_db lab.tests.test_add_exercise_view_db
```

Expected: PASS.

- [ ] **Step 5: Commit MusicXML integration**

```bash
rtk git add apps/teacher/views_musicxml.py apps/teacher/tests/test_musicxml_import_views.py
rtk git commit -m "feat: auto-route MusicXML exercises by unit and mode"
```

### Task 5: Make the Save Panel a Single Explicit Classification Form

**Files:**
- Modify: `lab/templates/play.html`
- Modify: `lab/tests/test_play_view.py`
- Modify: `apps/teacher/static/teacher/teacher-play.css`

- [ ] **Step 1: Write failing template contract tests**

In `lab/tests/test_play_view.py`, replace the old `name="modes"` hook assertion and add:

```python
def test_save_panel_has_single_unit_and_mode_controls(self):
    resp = self.client.get(reverse("lab:play"))
    self.assertContains(resp, 'id="play-save-unit"')
    self.assertContains(resp, 'id="play-save-mode"')
    self.assertNotContains(resp, 'name="modes"')

def test_save_panel_has_read_only_destination(self):
    resp = self.client.get(reverse("lab:play"))
    self.assertContains(resp, 'id="play-save-destination"')
    self.assertContains(resp, "Will save to")

def test_save_panel_has_no_playlist_management_controls(self):
    resp = self.client.get(reverse("lab:play"))
    self.assertNotContains(resp, 'id="play-save-playlist"')
    self.assertNotContains(resp, 'id="play-save-new-playlist-name"')
    self.assertNotContains(resp, 'id="play-save-adaptive"')

def test_public_and_official_controls_exist(self):
    resp = self.client.get(reverse("lab:play"))
    self.assertContains(resp, 'id="play-save-public"')
    self.assertContains(resp, 'id="play-save-official"')
```

- [ ] **Step 2: Run template tests and verify RED**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test lab.tests.test_play_view
```

Expected: FAIL because the template still renders mode checkboxes and playlist controls.

- [ ] **Step 3: Replace the save-panel markup**

In `lab/templates/play.html`:

1. Keep one single-select `#play-save-unit` with an empty placeholder.
2. Replace mode checkboxes with:

```html
<label for="play-save-mode" class="t-label">
    Interaction mode <span class="play-save-required">*</span>
</label>
<select id="play-save-mode" name="mode" class="play-save-select t-input">
    <option value="">— Select mode —</option>
    <option value="play">Play</option>
    <option value="roman">Roman numerals</option>
    <option value="figures">Figured bass</option>
    <option value="identify">Identify</option>
    <option value="harmonization">Harmonization</option>
</select>
```

3. Remove target-playlist, new-playlist, and adaptive controls.
4. Add:

```html
<div class="play-save-field play-save-field-wide t-form-row">
    <span class="t-label">Destination</span>
    <div id="play-save-destination" class="t-play-save-destination" aria-live="polite">
        Select a unit and interaction mode.
    </div>
</div>
```

5. Keep Public and Official checkboxes in Advanced options. Do not hard-code `checked`; JavaScript sets superuser defaults after metadata loads.

- [ ] **Step 4: Add the smallest teacher-scoped destination style**

In `apps/teacher/static/teacher/teacher-play.css`, add:

```css
.t-play-save-destination {
  padding: 0.75rem 0.875rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 0.9rem;
}
```

- [ ] **Step 5: Run template tests and verify GREEN**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test lab.tests.test_play_view
```

Expected: PASS.

- [ ] **Step 6: Commit the markup contract**

```bash
rtk git add lab/templates/play.html lab/tests/test_play_view.py apps/teacher/static/teacher/teacher-play.css
rtk git commit -m "feat: simplify teacher play save form"
```

### Task 6: Implement Tested Client-Side Destination and Payload Logic

**Files:**
- Modify: `lab/static/js/src/components/music/play_save_logic.js`
- Modify: `lab/static/js/src/components/music/play_save_logic.test.js`
- Modify: `lab/static/js/src/components/ui/music_controls.js`

- [ ] **Step 1: Write failing pure-logic tests**

Append to `play_save_logic.test.js`:

```javascript
assertEqual(
  "canonical destination label",
  mod.canonicalDestinationLabel("11", "roman"),
  "Unit 11 — Exercises (Roman)"
);
assertEqual(
  "missing unit has no destination",
  mod.canonicalDestinationLabel("", "roman"),
  ""
);
assertEqual(
  "missing mode has no destination",
  mod.canonicalDestinationLabel("11", ""),
  ""
);
assertEqual(
  "single save payload",
  mod.buildCanonicalSaveFields({
    unit: "11",
    mode: "roman",
    isPublic: true,
    saveAsOfficial: true
  }),
  {
    skillTags: ["unit:11"],
    mode: "roman",
    isPublic: true,
    saveAsOfficial: true
  }
);
```

- [ ] **Step 2: Run Node tests and verify RED**

Run:

```bash
rtk test node lab/static/js/src/components/music/play_save_logic.test.js
```

Expected: FAIL because the two functions are undefined.

- [ ] **Step 3: Add pure canonical-save helpers**

Extend `play_save_logic.js` with:

```javascript
  var MODE_LABELS = {
    play: "Play",
    roman: "Roman",
    figures: "Figures",
    identify: "Identify",
    harmonization: "Harmonization"
  };

  function canonicalDestinationLabel(unit, mode) {
    if (!unit || !MODE_LABELS[mode]) return "";
    return "Unit " + unit + " — Exercises (" + MODE_LABELS[mode] + ")";
  }

  function buildCanonicalSaveFields(options) {
    return {
      skillTags: ["unit:" + options.unit],
      mode: options.mode,
      isPublic: !!options.isPublic,
      saveAsOfficial: !!options.saveAsOfficial
    };
  }
```

Export both functions in the returned object.

- [ ] **Step 4: Run Node tests and verify GREEN**

Run:

```bash
rtk test node lab/static/js/src/components/music/play_save_logic.test.js
```

Expected: all assertions pass.

- [ ] **Step 5: Wire the UI to the tested helpers**

In `music_controls.js`:

1. Add `app/components/music/play_save_logic` to the AMD dependency list and factory arguments.
2. Remove `_allPlaylists`, `_renderPlaylistOptions()`, playlist change handlers, and playlist-name/adaptive reset code.
3. Listen to `#play-save-unit` and `#play-save-mode`.
4. Add `_renderCanonicalDestination()`:

```javascript
var label = PlaySaveLogic.canonicalDestinationLabel(
  $("#play-save-unit").val(),
  $("#play-save-mode").val()
);
$("#play-save-destination").text(
  label ? "Will save to: " + label : "Select a unit and interaction mode."
);
```

5. On authoring metadata success:

```javascript
if (that._isSuperuser) {
  $("#play-save-public, #play-save-official").prop("checked", true);
  $("#play-save-official-row").show();
} else {
  $("#play-save-official").prop("checked", false);
  $("#play-save-official-row").hide();
}
```

6. Validation requires non-empty description, one unit, and one mode.
7. Both composed and MusicXML payload builders call `buildCanonicalSaveFields()` and send `mode`, not `modes`, `playlistId`, `playlistName`, or `isAdaptive`.
8. On save success, retain the selected unit and mode so repeated material creation stays fast; clear only description/file-specific transient state.

- [ ] **Step 6: Run logic, template, and endpoint tests**

Run:

```bash
rtk test node lab/static/js/src/components/music/play_save_logic.test.js
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test lab.tests.test_play_view lab.tests.test_add_exercise_view_metadata_db apps.teacher.tests.test_musicxml_import_views
```

Expected: PASS.

- [ ] **Step 7: Commit client behavior**

```bash
rtk git add lab/static/js/src/components/music/play_save_logic.js lab/static/js/src/components/music/play_save_logic.test.js lab/static/js/src/components/ui/music_controls.js
rtk git commit -m "feat: preview canonical teacher save destination"
```

### Task 7: Verify Official/Public Semantics and Full Regression Scope

**Files:**
- Modify: `lab/tests/test_add_exercise_view_metadata_db.py`
- Modify: `apps/teacher/tests/test_musicxml_import_views.py`
- Modify: `docs/superpowers/specs/2026-06-19-teacher-play-canonical-save-design.md`

- [ ] **Step 1: Add explicit official/personal separation tests**

For both composed and MusicXML paths, assert:

```python
def test_official_and_personal_saves_use_distinct_destinations(self):
    personal = self.save_as_superuser(save_as_official=False)
    official = self.save_as_superuser(save_as_official=True)
    self.assertNotEqual(personal.json()["playlistId"], official.json()["playlistId"])

    personal_playlist = Playlist.objects.get(id=personal.json()["playlistId"])
    official_playlist = Playlist.objects.get(id=official.json()["playlistId"])
    self.assertEqual(personal_playlist.authored_by, self.superuser)
    self.assertEqual(official_playlist.authored_by.email, settings.FACTORY_USER_EMAIL)
    self.assertTrue(official_playlist.is_official)
    self.assertTrue(official_playlist.is_public)
```

The official request above explicitly submits Public=true. Also add a separate
official request with Public=false and assert that both the exercise and
playlist remain private, proving the editable checkbox is authoritative. Assert
a non-superuser receives 403 for `saveAsOfficial=true` or
`save_as_official=true`.

- [ ] **Step 2: Run focused tests and verify any missing behavior fails**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test lab.tests.test_add_exercise_view_metadata_db apps.teacher.tests.test_musicxml_import_views
```

Expected: PASS only when official/factory authorship, editable public status,
and public promotion are identical across both endpoints.

- [ ] **Step 3: Mark the approved spec implemented**

Change the spec header to:

```markdown
**Status:** Implemented
```

Add an implementation note listing:

- canonical identity migration `0069`;
- shared service `apps/exercises/services/canonical_playlist.py`;
- composed and MusicXML endpoint integration;
- single-unit/single-mode UI.

- [ ] **Step 4: Run the complete relevant suite**

Run:

```bash
rtk test env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_canonical_playlist_model apps.exercises.tests.test_playlist_naming apps.exercises.tests.test_canonical_playlist_service lab.tests.test_play_view lab.tests.test_add_exercise_view_metadata_db lab.tests.test_add_exercise_view_db apps.teacher.tests.test_musicxml_import_views
rtk test node lab/static/js/src/components/music/play_save_logic.test.js
rtk summary env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py check
rtk summary env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py makemigrations --check
rtk git diff --check
```

Expected: all tests pass, Django reports no issues or missing migrations, and `git diff --check` is silent.

- [ ] **Step 5: Perform browser verification on `/teacher/play/`**

Start the local server:

```bash
rtk summary env DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py runserver 127.0.0.1:8001 --noreload
```

Verify in the browser:

1. Save is disabled until description, one unit, and one mode are selected.
2. Destination preview updates to `Unit N — Exercises (Mode)`.
3. No playlist picker or playlist-name field appears.
4. A superuser sees Public and Official checked by default.
5. Unchecking either box changes the submitted result correctly.
6. Two differently described saves with the same unit/mode reuse one playlist.
7. Changing the mode changes the destination.
8. MusicXML preview/save follows the same rules.

- [ ] **Step 6: Commit verification documentation**

```bash
rtk git add lab/tests/test_add_exercise_view_metadata_db.py apps/teacher/tests/test_musicxml_import_views.py docs/superpowers/specs/2026-06-19-teacher-play-canonical-save-design.md
rtk git commit -m "test: verify canonical teacher save workflow"
```

### Task 8: Push the Branch and Update PR #134

**Files:**
- No code changes expected.

- [ ] **Step 1: Confirm branch state and commit history**

Run:

```bash
rtk git status
rtk git log -8 --oneline
```

Expected: clean worktree; commits are scoped in the order described above.

- [ ] **Step 2: Push the existing branch**

Run:

```bash
rtk git push origin claude/clever-antonelli-7dd62c
```

Expected: branch updates successfully.

- [ ] **Step 3: Verify the pull request target and checks**

Run:

```bash
rtk gh pr view 134 --repo avnerdorman/HarmonyLab
rtk gh pr checks 134 --repo avnerdorman/HarmonyLab
```

Expected: PR #134 targets `avnerdorman/HarmonyLab:master`; checks are visible and no repository is inferred from `upstream`.
