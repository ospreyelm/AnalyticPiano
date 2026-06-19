# Teacher Access Redirection & Composed Save Transposition Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centrally enforce teacher-role access on `/teacher/` (clean redirect for GETs, 403 JSON with `redirectUrl` for AJAX/POST) and let the manual play editor save endpoint generate transposed copies, matching MusicXML save behavior.

## User Review Required

> [!IMPORTANT]
> **Centrally Enforced Redirect/API Response Policy:**
> - To prevent misleading AJAX errors (such as the generic "Failed to preview MusicXML" error which occurs when an AJAX POST gets redirected to HTML pages), we enforce a central middleware on all requests starting with `/teacher/`.
> - Non-teacher/non-superuser authenticated users (students) requesting GET pages under `/teacher/` will be cleanly redirected to `/s/`.
> - Non-teacher/non-superuser authenticated users making API/POST requests to `/teacher/` will receive a `403 Forbidden` JSON response containing the `redirectUrl`.
> - A global jQuery AJAX error handler is added to `apps/teacher/templates/teacher/base.html` so that any AJAX request hitting a 403 containing `redirectUrl` will automatically trigger a browser redirect.

> [!NOTE]
> **Composed Exercise Transposition Support:**
> - The manual play editor save endpoint `/exercises/add/` (`AddExerciseView`) now supports the `createTranspositions` and `keySet` fields in the JSON payload, matching the behavior of the MusicXML save endpoint.
> - When checked, it calls `generate_transposed_copies` within the save transaction to generate transposed variants in the target playlist.

## File Map

- Create `apps/teacher/middleware.py`: `TeacherAccessMiddleware`.
- Create `apps/teacher/tests/test_access_middleware.py`: middleware contract tests.
- Modify `harmony/settings/common.py`: register the middleware after `AuthenticationMiddleware`.
- Modify `apps/teacher/templates/teacher/base.html`: global jQuery `ajaxError` redirect handler.
- Modify `lab/static/js/src/components/ui/music_controls.js`: send `createTranspositions`/`keySet` in the save payload.
- Modify `lab/views.py`: `AddExerciseView.post` reads those fields and calls `generate_transposed_copies` inside the save transaction; also normalizes the source `key` via `apps.exercises.utils.transpose.normalize_key`.
- Modify `apps/teacher/tests/test_views_db.py`: assert 403 JSON (not bare 302) for non-teacher POST.
- Modify `lab/tests/test_add_exercise_view_db.py`: cover transposition generation on save.
- Modify `lab/tests/test_play_view.py`: test user now has `role="teacher"` so the new middleware doesn't block the view under test.
- Modify `apps/exercises/tests/test_play_save_chordal_umto.py`: payloads need `skillTags`/`mode` to satisfy unrelated canonical-playlist routing validation that landed on this branch; adaptive-playlist test rewritten to assert the now-enforced rejection of `playlistName`/`playlistId`.

### Task 1: Central Teacher Access Middleware

**Files:**
- Create: `apps/teacher/middleware.py`
- Create: `apps/teacher/tests/test_access_middleware.py`
- Modify: `harmony/settings/common.py`

- [x] **Step 1: Write middleware contract tests** — anonymous passes through to login redirect; authenticated student GET → 302 to `student:home`; authenticated student POST → 403 JSON with `redirectUrl`; teacher/superuser GET → 200.
- [x] **Step 2: Implement `TeacherAccessMiddleware`** — gate all `/teacher/` paths; allow anonymous through for `@teacher_required`/login-redirect decorators to handle; redirect GET, JSON 403 otherwise.
- [x] **Step 3: Register middleware** in `MIDDLEWARE` immediately after `AuthenticationMiddleware`.
- [x] **Step 4: Run tests green** — `apps.teacher.tests.test_access_middleware`.

### Task 2: Global AJAX Redirect Handler

**Files:**
- Modify: `apps/teacher/templates/teacher/base.html`

- [x] **Step 1: Add global jQuery `ajaxError` listener** before `</body>` — waits for `window.jQuery` to be available, then on any 403 response with a `redirectUrl` in the JSON body, navigates the browser there.

### Task 3: Composed Save Transposition Support

**Files:**
- Modify: `lab/static/js/src/components/ui/music_controls.js`
- Modify: `lab/views.py`
- Modify: `lab/tests/test_add_exercise_view_db.py`

- [x] **Step 1: Send `createTranspositions`/`keySet` from the manual play save dialog** — reuse the existing `#play-save-create-transpositions` checkbox and `_getSelectedKeySet()` helper already used by the batch-generation path; append both fields to the `/exercises/add/` JSON payload.
- [x] **Step 2: Extend `AddExerciseView.post`** — extract `createTranspositions` (bool) and `keySet` (array or comma-separated string) from the payload; normalize the source `key` via `normalize_key`; after the source exercise is appended to its canonical playlist, call `generate_transposed_copies(source_exercise=exercise, key_set=key_set, playlist=playlist, author=author, is_official=save_as_official, overwrite=False)` inside the same transaction when `createTranspositions and key_set`.
- [x] **Step 3: Add regression test** — `test_saves_with_transpositions_generated` posts with `createTranspositions=True, keySet=["G", "F"]` and asserts the source plus both transposed exercises land in the canonical unit playlist.

### Task 4: Verification

- [x] **Step 1:** `python manage.py test apps.teacher.tests.test_access_middleware apps.teacher.tests.test_views_db lab.tests.test_add_exercise_view_db lab.tests.test_play_view apps.exercises.tests.test_play_save_chordal_umto --settings=harmony.settings.local` — 68 tests, OK.
- [x] **Step 2:** `python manage.py test apps.teacher.tests.test_musicxml_import_views lab.tests --settings=harmony.settings.local` — 67 tests, OK.
- [ ] **Step 3:** Manual verification in browser per the plan's verification checklist (student redirect on `/teacher/play/`, 403 JSON + redirect on AJAX POST, transposition checkbox produces transposed exercises in the playlist).

## Notes

- `teacher_required`-decorated views still run their own per-view check; the middleware is a second, centralized layer so misconfigured or future views can't accidentally skip the redirect/403 contract.
- This work was picked up mid-flight in the `.worktrees/navigation-contract` worktree (branch `codex/navigation-contract`) after the prior session ran out of credits; all listed implementation steps were already present as uncommitted changes and have been verified against the test suite rather than re-implemented.
