# Branch-Unit Canonical Playlist Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers save exercises against Branch A–D units (e.g. `B17`) from `/teacher/play/`, not just the numbered core units (1–20ish).

**Architecture:** The "canonical teacher-play playlist" system (`Playlist.canonical_unit` + `canonical_mode`, one playlist per author/unit/mode, auto-created/deduped by `resolve_canonical_playlist`) currently forces the unit through `int()` at three points and stores it in a `PositiveSmallIntegerField`, so any non-numeric unit token (`"B17"`) throws or 400s before a playlist can be created. Everywhere else in the codebase — `TaxonomyReader.get_unit()`, the `unit:` skill-tag convention, the legacy `_unit_prefix()` naming helper, and the client-side JS — already treats unit identifiers as opaque strings and already works correctly for branch units (confirmed: 104 existing exercises are tagged `unit:B1` etc., and the `/teacher/play/` unit picker and "Will save to" preview already render `B17` correctly). The fix widens `canonical_unit` to a string-typed column and removes the three `int()` casts, bringing the canonical-playlist path in line with the string-based convention the rest of the codebase already uses. No client-side (JS) changes are needed.

**Tech Stack:** Django 5.2, PostgreSQL, Python.

**Blast radius (confirmed via grep before writing this plan):** exactly 3 non-test `.py` files touch `Playlist.canonical_unit`, and exactly 2 view functions do the premature `int()` cast on a unit token. This is a narrow, well-contained change.

---

### Task 1: Widen `Playlist.canonical_unit` from integer to string

**Files:**
- Modify: `apps/exercises/models.py:570-574`
- Create: `apps/exercises/migrations/0070_canonical_unit_to_charfield.py`
- Test: `apps/exercises/tests/test_canonical_playlist_model.py`

- [ ] **Step 1: Write the failing test**

Add this test to `apps/exercises/tests/test_canonical_playlist_model.py` (it needs `Playlist.FAMILY_TEACHER_PLAY` alongside the existing constants already imported in that file):

```python
    def test_canonical_unit_accepts_branch_unit_token(self):
        playlist = Playlist.objects.create(
            name="Teacher Play Branch B17",
            authored_by=self.teacher,
            playlist_family=Playlist.FAMILY_TEACHER_PLAY,
            canonical_unit="B17",
            canonical_mode="figures",
        )
        playlist.refresh_from_db()
        self.assertEqual(playlist.canonical_unit, "B17")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_canonical_playlist_model.CanonicalPlaylistIdentityTests.test_canonical_unit_accepts_branch_unit_token -v 2`

Expected: FAIL. `PositiveSmallIntegerField` rejects `"B17"` — either a `ValueError`/`DataError` on save, or (SQLite/loose backends) silent truncation to a number that then fails the `assertEqual`. On Postgres (this project's real backend) expect a `django.db.utils.DataError: invalid input syntax for type smallint: "B17"`.

- [ ] **Step 3: Change the field type**

In `apps/exercises/models.py`, replace:

```python
    canonical_unit = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
```

with:

```python
    canonical_unit = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        db_index=True,
    )
```

(`max_length=8` comfortably fits every existing unit token — `"1"`–`"99"`, `"B17"`, `"C4"`, `"D10"` — with headroom.)

- [ ] **Step 4: Generate and inspect the migration**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py makemigrations exercises -n canonical_unit_to_charfield`

Confirm the generated file `apps/exercises/migrations/0070_canonical_unit_to_charfield.py` contains a single `AlterField` on `canonical_unit`:

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exercises", "0069_playlist_teacher_play_identity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="playlist",
            name="canonical_unit",
            field=models.CharField(blank=True, db_index=True, max_length=8, null=True),
        ),
    ]
```

If Django generated anything else (e.g. it also touched the `CheckConstraint`/`UniqueConstraint` from migration 0069), that's fine — those constraints reference the field by name only and don't encode its type, so they don't need to change. Just confirm the constraint operations (if regenerated) are semantically identical to the ones in `0069_playlist_teacher_play_identity.py`.

- [ ] **Step 5: Apply the migration locally and run the test**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py migrate exercises`
Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_canonical_playlist_model.CanonicalPlaylistIdentityTests.test_canonical_unit_accepts_branch_unit_token -v 2`

Expected: PASS. (Django's test runner creates a fresh test DB and applies all migrations, so this also validates the migration runs cleanly from scratch, not just against your existing local DB.)

- [ ] **Step 6: Verify existing data survives the migration**

The only `canonical_unit` value in the current local DB is `13` (confirmed via `Playlist.objects.exclude(canonical_unit=None).values_list("canonical_unit", flat=True)` during investigation). After `manage.py migrate exercises`, confirm it became the string `"13"`, not `None` or corrupted:

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c "
from apps.exercises.models import Playlist
for p in Playlist.objects.exclude(canonical_unit=None):
    print(repr(p.canonical_unit))
"
```

Expected output: `'13'` (a string, not an int).

- [ ] **Step 7: Commit**

```bash
git add apps/exercises/models.py apps/exercises/migrations/0070_canonical_unit_to_charfield.py apps/exercises/tests/test_canonical_playlist_model.py
git commit -m "feat(exercises): widen Playlist.canonical_unit to support branch unit tokens like B17"
```

---

### Task 2: Stop forcing `resolve_canonical_playlist` and playlist naming through `int()`

**Files:**
- Modify: `apps/exercises/services/canonical_playlist.py:11-19`
- Modify: `apps/exercises/utils/playlist_naming.py:35-36`
- Test: `apps/exercises/tests/test_canonical_playlist_service.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/exercises/tests/test_canonical_playlist_service.py` (inside `CanonicalPlaylistServiceTests`, reusing the existing `self.resolve()` helper and `self.author`):

```python
    def test_branch_unit_token_creates_canonical_playlist(self):
        playlist = self.resolve(unit="B17", mode="figures", is_public=True)

        self.assertEqual(playlist.name, "Unit B17 — Exercises (Figures)")
        self.assertEqual(playlist.skill_tags, ["unit:B17"])
        self.assertEqual(playlist.playlist_family, Playlist.FAMILY_TEACHER_PLAY)
        self.assertEqual(playlist.canonical_unit, "B17")
        self.assertEqual(playlist.canonical_mode, "figures")

    def test_branch_unit_token_dedups_on_repeat_resolution(self):
        first = self.resolve(unit="B17", mode="figures")
        second = self.resolve(unit="B17", mode="figures")

        self.assertEqual(second.pk, first.pk)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_canonical_playlist_service.CanonicalPlaylistServiceTests.test_branch_unit_token_creates_canonical_playlist -v 2`

Expected: FAIL with `ValueError: invalid literal for int() with base 10: 'B17'`, raised from `resolve_canonical_playlist`'s `unit = int(unit)` line.

- [ ] **Step 3: Fix `resolve_canonical_playlist`**

In `apps/exercises/services/canonical_playlist.py`, replace:

```python
def resolve_canonical_playlist(
    *,
    author,
    unit: int,
    mode: str,
    is_public: bool,
    is_official: bool,
) -> Playlist:
    unit = int(unit)
    canonical_mode_label(mode)  # validates mode; raises ValueError for unsupported values
```

with:

```python
def resolve_canonical_playlist(
    *,
    author,
    unit: str,
    mode: str,
    is_public: bool,
    is_official: bool,
) -> Playlist:
    unit = str(unit)
    canonical_mode_label(mode)  # validates mode; raises ValueError for unsupported values
```

No other line in this function needs to change — `unit` is already only ever used as `f"unit:{unit}"`, `identity["canonical_unit"] = unit`, and passed straight into `build_canonical_playlist_name(unit, mode)`, all of which are string-safe once the premature `int()` cast is gone.

- [ ] **Step 4: Fix `build_canonical_playlist_name`**

In `apps/exercises/utils/playlist_naming.py`, replace:

```python
def build_canonical_playlist_name(unit: int, mode: str) -> str:
    return f"Unit {int(unit)} — Exercises ({canonical_mode_label(mode)})"
```

with:

```python
def build_canonical_playlist_name(unit: str, mode: str) -> str:
    return f"Unit {unit} — Exercises ({canonical_mode_label(mode)})"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_canonical_playlist_service.CanonicalPlaylistServiceTests -v 2`

Expected: PASS for the two new tests. Also expect two **pre-existing** failures at this point — `test_first_resolution_creates_canonical_playlist` and `test_exact_legacy_row_is_adopted` — because they assert `canonical_unit == 11` (int); that's fixed in Task 3, not this step. Confirm those are the *only* two failures (everything else in the file should still pass, since numeric unit tokens like `11`/`"11"` still resolve correctly, just now stored as strings).

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/services/canonical_playlist.py apps/exercises/utils/playlist_naming.py apps/exercises/tests/test_canonical_playlist_service.py
git commit -m "feat(exercises): make resolve_canonical_playlist and playlist naming string-native for unit tokens"
```

---

### Task 3: Update existing tests for the new string-typed `canonical_unit`

**Files:**
- Modify: `apps/exercises/tests/test_canonical_playlist_service.py:60,112`
- Modify: `apps/exercises/tests/test_canonical_playlist_model.py:26,36,45,53,75,83,89`
- Modify: `apps/teacher/tests/test_musicxml_import_views.py:234`
- Modify: `lab/tests/test_add_exercise_view_metadata_db.py:46,59`

This task has no new behavior to test — it's bringing pre-existing assertions in line with the type change from Task 1/2. Do it as a single mechanical pass, then run the full affected test suite once.

- [ ] **Step 1: Fix the two remaining int assertions in `test_canonical_playlist_service.py`**

Line 60, inside `test_first_resolution_creates_canonical_playlist`:

```python
        self.assertEqual(playlist.canonical_unit, 11)
```
→
```python
        self.assertEqual(playlist.canonical_unit, "11")
```

Line 112, inside `test_exact_legacy_row_is_adopted`:

```python
        self.assertEqual(resolved.canonical_unit, 11)
```
→
```python
        self.assertEqual(resolved.canonical_unit, "11")
```

- [ ] **Step 2: Fix the seven `canonical_unit=9` kwargs in `test_canonical_playlist_model.py`**

Replace every occurrence of `canonical_unit=9,` with `canonical_unit="9",` (lines 26, 36, 45, 53, 75, 83, 89 — 7 total). These are plain model-constructor kwargs; the column now stores strings, so pass a string to keep the tests honest about the real contract (Postgres would silently coerce an int here via an implicit assignment cast, which would mask a real regression if `resolve_canonical_playlist` or a caller ever passed a raw int again).

- [ ] **Step 3: Fix `test_musicxml_import_views.py`**

Line 234:

```python
        self.assertEqual(playlist.canonical_unit, 11)
```
→
```python
        self.assertEqual(playlist.canonical_unit, "11")
```

- [ ] **Step 4: Fix `test_add_exercise_view_metadata_db.py`**

Line 46:

```python
        self.assertEqual(playlist.canonical_unit, 11)
```
→
```python
        self.assertEqual(playlist.canonical_unit, "11")
```

Line 59:

```python
                canonical_unit=11,
```
→
```python
                canonical_unit="11",
```

- [ ] **Step 5: Run the full set of touched test files**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test \
  apps.exercises.tests.test_canonical_playlist_service \
  apps.exercises.tests.test_canonical_playlist_model \
  apps.teacher.tests.test_musicxml_import_views \
  lab.tests.test_add_exercise_view_metadata_db \
  -v 2
```

Expected: PASS, all tests in all four files, no failures or errors.

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/tests/test_canonical_playlist_service.py apps/exercises/tests/test_canonical_playlist_model.py apps/teacher/tests/test_musicxml_import_views.py lab/tests/test_add_exercise_view_metadata_db.py
git commit -m "test(exercises): update canonical_unit assertions for string-typed field"
```

---

### Task 4: Fix `AddExerciseView._single_unit` to return the string unit token

**Files:**
- Modify: `lab/views.py:562-568`
- Test: `lab/tests/test_add_exercise_view_metadata_db.py`

`AddExerciseView._skill_tags` (called before `_single_unit`, at `lab/views.py:526-544`) already validates the unit token against `TaxonomyReader.get_unit(unit_n)` and already accepts branch tokens — that part is correct today. The only bug is `_single_unit` casting the already-validated token to `int()` afterward.

- [ ] **Step 1: Write the failing test**

`lab/tests/test_add_exercise_view_metadata_db.py` already has a `self._post(payload)` helper (defined at line 27) that posts JSON to `/exercises/add/` with canonical-save defaults (`skillTags: ["unit:11"]`, `mode: "roman"`), and a `self._chords()` helper that returns a valid 4-chord `chord` payload. Successful saves return **201**, not 200 (see `test_save_creates_canonical_playlist_without_playlist_payload` at line 38 for the existing pattern this mirrors). Add this test to the `AddExerciseViewMetadataTests` class, in the "Canonical-save contract" section near line 47:

```python
    def test_branch_unit_token_creates_canonical_playlist(self):
        response = self._post({
            "chord": self._chords(),
            "skillTags": ["unit:B17"],
            "mode": "figures",
            "description": "Branch unit smoke test",
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        exercise = Exercise.objects.get(id=body["id"])
        self.assertIn("unit:B17", exercise.skill_tags)
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertEqual(playlist.canonical_unit, "B17")
        self.assertEqual(playlist.name, "Unit B17 — Exercises (Figures)")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test lab.tests.test_add_exercise_view_metadata_db.AddExerciseViewMetadataTests.test_branch_unit_token_creates_canonical_playlist -v 2`

Expected: FAIL with a 400 response whose `error` body is the raw `ValueError` text `invalid literal for int() with base 10: 'B17'` (caught and JSON-wrapped by the `except (NonUMTOExerciseError, ValueError, KeyError)` block in `AddExerciseView.post`), not the 201 the test expects.

- [ ] **Step 3: Fix `_single_unit`**

In `lab/views.py`, replace:

```python
    def _single_unit(self, skill_tags):
        """Return the integer unit number from the validated skill_tags list."""
        for tag in skill_tags:
            if tag.startswith("unit:"):
                return int(tag.split(":", 1)[1])
        raise ValueError("Exactly one unit tag is required.")
```

with:

```python
    def _single_unit(self, skill_tags):
        """Return the unit token (e.g. "11" or "B17") from the validated skill_tags list."""
        for tag in skill_tags:
            if tag.startswith("unit:"):
                return tag.split(":", 1)[1]
        raise ValueError("Exactly one unit tag is required.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test lab.tests.test_add_exercise_view_metadata_db -v 2`

Expected: PASS, all tests in the file including the new one.

- [ ] **Step 5: Commit**

```bash
git add lab/views.py lab/tests/test_add_exercise_view_metadata_db.py
git commit -m "fix(exercises): AddExerciseView accepts branch unit tokens, not just integers"
```

---

### Task 5: Fix `views_musicxml.py` unit validation

**Files:**
- Modify: `apps/teacher/views_musicxml.py:194-205`
- Test: `apps/teacher/tests/test_musicxml_import_views.py`

This endpoint currently validates the unit with a bare `int()` cast and **no taxonomy check at all** — a garbage numeric unit like `9999` would already sail through today. Fix both problems at once by validating against `TaxonomyReader.get_unit()`, matching the pattern `AddExerciseView._skill_tags` already uses.

- [ ] **Step 1: Write the failing tests**

`apps/teacher/tests/test_musicxml_import_views.py`'s `MusicXMLImportViewsTest` class already has a `self._post_save(extra=None, xml_data=None)` helper (line 132) that POSTs a valid multipart save request to `reverse("teacher:import-musicxml-save")` with canonical defaults (`unit: "11"`, `mode: "roman"`, a real generated MusicXML file), and accepts an `extra` dict to override any field. Successful saves return **201** (see `test_save_automatically_creates_canonical_playlist` at line 223 for the existing pattern). Add these two tests near it, in the "Canonical-save contract" section:

```python
    def test_save_accepts_branch_unit_token(self):
        """Branch units (e.g. B17) should save just like numeric units."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save({"unit": "B17", "mode": "figures"})
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        playlist = Playlist.objects.get(id=data["playlistId"])
        self.assertEqual(playlist.canonical_unit, "B17")
        self.assertEqual(playlist.name, "Unit B17 — Exercises (Figures)")

    def test_save_rejects_unknown_unit_token(self):
        """A unit token that isn't in the taxonomy should 400 with a clear message,
        not silently succeed or leak a raw ValueError."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save({"unit": "ZZZ99"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not reference a known unit", response.json()["error"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.teacher.tests.test_musicxml_import_views.MusicXMLImportViewsTest.test_save_accepts_branch_unit_token apps.teacher.tests.test_musicxml_import_views.MusicXMLImportViewsTest.test_save_rejects_unknown_unit_token -v 2`

Expected: `test_save_accepts_branch_unit_token` FAILs with a 400 whose body is `{"error": "Unit must be an integer."}`, not the 201 the test expects. `test_save_rejects_unknown_unit_token` currently PASSES for the wrong reason (`"ZZZ99"` hits the same `int()` `ValueError` path as any non-numeric string, regardless of whether it's a real taxonomy miss) — after Step 3 it should still pass, but for the *right* reason (an explicit `TaxonomyReader.get_unit()` miss). Note this in the PR description so a reviewer doesn't misread "still passing" as "nothing changed here."

- [ ] **Step 3: Fix the unit validation**

In `apps/teacher/views_musicxml.py`, add the import at the top of the file (near the other `apps.exercises` imports, e.g. next to `from apps.exercises.umto import InteractionMode`):

```python
from apps.exercises.taxonomy_reader import TaxonomyReader
```

Then replace:

```python
    try:
        unit = int(unit_tags[0])
    except ValueError:
        return JsonResponse({"error": "Unit must be an integer."}, status=400)

    skill_tags = [f"unit:{unit}"]
```

with:

```python
    unit = unit_tags[0]
    if TaxonomyReader.get_unit(unit) is None:
        return JsonResponse({"error": f"unit tag unit:{unit} does not reference a known unit."}, status=400)

    skill_tags = [f"unit:{unit}"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.teacher.tests.test_musicxml_import_views -v 2`

Expected: PASS, all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add apps/teacher/views_musicxml.py apps/teacher/tests/test_musicxml_import_views.py
git commit -m "fix(teacher): validate MusicXML save unit against taxonomy, accept branch unit tokens"
```

---

### Task 6: Manual end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full affected test surface once more, together**

Run:
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test \
  apps.exercises.tests.test_canonical_playlist_service \
  apps.exercises.tests.test_canonical_playlist_model \
  apps.teacher.tests.test_musicxml_import_views \
  lab.tests.test_add_exercise_view_metadata_db \
  -v 2
```
Expected: PASS, everything green.

- [ ] **Step 2: Start local servers**

See `.claude/skills/run-harmonylab/SKILL.md` in this repo for the exact commands (Django on `127.0.0.1:8123` + `vite --port 5173`). **Before starting Vite, run `lsof -i :5173 -sTCP:LISTEN` and confirm nothing is already listening** — a stale Vite process from a different worktree can silently squat the port and serve a different checkout's bundle, producing a false "it works" (this happened during the investigation that led to this plan; see memory `feedback_vite_port_squatter` if available in this environment).

- [ ] **Step 3: Manually save a Branch B exercise through the real UI**

Log in as a teacher, go to `/teacher/play/`, enter some chords (or import a MusicXML file), select **Unit B17 — Rule of...** and any interaction mode, click Save. Confirm:
- No "Can't save yet" error.
- Success feedback appears.
- `Playlist.objects.get(canonical_unit="B17", canonical_mode=<mode>, playlist_family="teacher_play")` exists and contains the new exercise (check via `manage.py shell`).

- [ ] **Step 4: Confirm numeric units still work (regression check)**

Repeat Step 3 with a normal numeric unit (e.g. Unit 11). Confirm it still saves correctly and `canonical_unit` is stored as `"11"` (string, not int — expected given Task 1).

- [ ] **Step 5: Report results**

No commit for this task — it's verification. If anything fails, return to the relevant earlier task rather than patching ad hoc.

---

## Notes for whoever executes this plan

- This plan intentionally does **not** touch any JavaScript. The client already sends unit tokens as opaque strings and already renders `"Unit B17 — Exercises (Figures)"` correctly in the save-panel preview — confirmed by inspecting the live page during investigation, before this plan was written. If Vite is serving a stale build, you'll see stale-looking behavior that has nothing to do with this plan — see Task 6 Step 2's warning.
- The 104 exercises already tagged `unit:B1` etc. in production were created through a separate bulk-import path (not `AddExerciseView` or `views_musicxml.py`) and are on legacy (`playlist_family=""`) playlists, not canonical ones. This plan does not migrate or touch that existing content — it only unblocks *new* branch-unit saves through `/teacher/play/` going forward.
