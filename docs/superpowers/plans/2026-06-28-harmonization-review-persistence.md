# Harmonization Review Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In review mode, render the student's saved harmonization answer (read from existing `PerformanceData`) as pure display, instead of the bare exercise.

**Architecture:** The student's accepted sonorities are already persisted in `PerformanceData.data`. A new model method selects the most-complete pass; both review-mode view branches embed it as `reviewHarmonizationSonorities` in the exercise context (mirroring `reviewAnswers`); the frontend restores it into `acceptedHarmonizationSonorities` and renders via the existing realization path, with input/grading disabled.

**Tech Stack:** Django (Python), pytest + Django test runner, vanilla JS (ESM via Vite), jQuery.

**Spec:** `docs/superpowers/specs/2026-06-28-harmonization-review-persistence-design.md`

---

## Setup notes (read before starting)

- **Interpreter:** this checkout pins `.python-version` to 3.10.18, which may not be installed. If `python` errors with a pyenv message, run `pyenv local system` in the worktree first (do not commit the resulting `.python-version` change).
- **Branch:** work on a dedicated branch off the current `migration/requirejs-to-vite-master` (e.g. `git switch -c feat/harmonization-review-persistence`).
- **Test commands used below:**
  - Model (pytest): `pytest apps/exercises/tests/test_performance_data_harmonization.py -v`
  - View (Django runner): `python manage.py test apps.student.tests.test_player_views --settings=harmony.settings.local`

---

## File Structure

- **Modify** `apps/exercises/models.py` — add `PerformanceData.get_best_harmonization_pass`.
- **Create** `apps/exercises/tests/test_performance_data_harmonization.py` — model unit tests.
- **Modify** `apps/student/views.py` — embed `reviewHarmonizationSonorities` in both review branches; add `is_harmonization_review` template context.
- **Modify** `apps/student/tests/test_player_views.py` — view tests.
- **Modify** `lab/static/js/src/components/app/exercise.js` — restore sonorities + set display-only flag.
- **Modify** `lab/static/js/src/models/exercise_context.js` — guard `gradeHarmonizationMidiSet` when display-only.
- **Modify** `apps/student/templates/student/player.html` — banner copy (static + JS) + body flag for hiding controls.
- **Modify** `apps/student/static/student/exercise-canvas.css` — hide note-entry controls in harmonization review.

---

## Task 1: Model — `get_best_harmonization_pass`

**Files:**
- Modify: `apps/exercises/models.py` (class `PerformanceData`, after `get_exercise_first_pass` ~line 1486)
- Test: `apps/exercises/tests/test_performance_data_harmonization.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `apps/exercises/tests/test_performance_data_harmonization.py`:

```python
from django.test import SimpleTestCase

from apps.exercises.models import PerformanceData


def _son(n):
    """n accepted sonorities, minimal shape used by the renderer."""
    return [{"midi": [60 + i], "targetIndex": i, "ts": i} for i in range(n)]


class GetBestHarmonizationPassTests(SimpleTestCase):
    def _pd(self, data):
        # Unsaved instance; method only reads self.data, no DB needed.
        return PerformanceData(data=data)

    def test_picks_most_complete_pass(self):
        pd = self._pd([
            {"id": "ABC123", "harmonization_accepted_sonorities": _son(1)},
            {"id": "ABC123", "harmonization_accepted_sonorities": _son(3)},
            {"id": "ABC123", "harmonization_accepted_sonorities": _son(2)},
        ])
        self.assertEqual(len(pd.get_best_harmonization_pass("ABC123")), 3)

    def test_tie_prefers_most_recent(self):
        pd = self._pd([
            {"id": "ABC123", "harmonization_accepted_sonorities": [{"midi": [1], "targetIndex": 0}]},
            {"id": "ABC123", "harmonization_accepted_sonorities": [{"midi": [2], "targetIndex": 0}]},
        ])
        self.assertEqual(pd.get_best_harmonization_pass("ABC123")[0]["midi"], [2])

    def test_ignores_other_exercise_ids(self):
        pd = self._pd([
            {"id": "ZZZ999", "harmonization_accepted_sonorities": _son(3)},
        ])
        self.assertIsNone(pd.get_best_harmonization_pass("ABC123"))

    def test_matches_transposed_variant_by_base_id(self):
        pd = self._pd([
            {"id": "ABC123_T05", "harmonization_accepted_sonorities": _son(2)},
        ])
        self.assertEqual(len(pd.get_best_harmonization_pass("ABC123")), 2)

    def test_no_sonorities_returns_none(self):
        pd = self._pd([
            {"id": "ABC123"},
            {"id": "ABC123", "harmonization_accepted_sonorities": []},
        ])
        self.assertIsNone(pd.get_best_harmonization_pass("ABC123"))

    def test_empty_data_returns_none(self):
        self.assertIsNone(self._pd([]).get_best_harmonization_pass("ABC123"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/exercises/tests/test_performance_data_harmonization.py -v`
Expected: FAIL — `AttributeError: 'PerformanceData' object has no attribute 'get_best_harmonization_pass'`

- [ ] **Step 3: Implement the method**

In `apps/exercises/models.py`, inside `class PerformanceData`, add after `get_exercise_first_pass`:

```python
    def get_best_harmonization_pass(self, exercise_id):
        """Return the harmonization_accepted_sonorities list from the most
        complete stored pass for this exercise, or None.

        Most complete = greatest number of accepted sonorities. Ties resolve to
        the most recent pass (self.data is append-ordered). Matches transposed
        variants via the 6-char base id, consistent with exercise_id[0:6] usage
        elsewhere in this model.
        """
        base = (exercise_id or "")[:6]
        best = None
        best_len = 0
        for entry in self.data:
            if entry.get("id", "")[:6] != base:
                continue
            sonorities = entry.get("harmonization_accepted_sonorities")
            if not sonorities:
                continue
            if len(sonorities) >= best_len:  # >= => later (more recent) wins ties
                best_len = len(sonorities)
                best = sonorities
        return best
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/exercises/tests/test_performance_data_harmonization.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/models.py apps/exercises/tests/test_performance_data_harmonization.py
git commit -m "feat(harmonization): add PerformanceData.get_best_harmonization_pass"
```

---

## Task 2: View — embed `reviewHarmonizationSonorities` + template flag

Two review-mode branches set `reviewAnswers` today and both must also embed the
harmonization sonorities: the HTML player view (~line 975) and the
player-definition JSON endpoint (~line 1169). Harmonization is detected via
`exercise_context.get("mode") == "harmonization"` (the canonical check, also used
in `apps/exercises/services/exercise_context.py:238`).

**Files:**
- Modify: `apps/student/views.py` (~975 HTML branch, ~1169 JSON branch, and the
  template render context that sets `is_review_mode` ~1086/1111)
- Test: `apps/student/tests/test_player_views.py`

- [ ] **Step 1: Write the failing view tests**

Add to `apps/student/tests/test_player_views.py` (new methods inside the existing
`PlayerViewTests` class; follow the existing harmonization/umto fixture helpers
already imported there — `make_umto_exercise`, `InteractionMode`). Build a
harmonization exercise, create a `PerformanceData` row with a stored pass, hit
the player-definition endpoint, and assert the payload carries the sonorities:

```python
    def test_player_definition_includes_harmonization_sonorities_in_review(self):
        # Arrange: a harmonization exercise served in this playlist, with a
        # completed PerformanceData pass for this student.
        exercise, playlist = self._make_harmonization_exercise_in_playlist()
        sonorities = [{"midi": [60, 64, 67], "targetIndex": 0, "ts": 1}]
        PerformanceData.objects.create(
            user=self.student,
            playlist=playlist,
            course=None,
            data=[{
                "id": exercise.id,
                "harmonization_accepted_sonorities": sonorities,
                "error_tally": 0,
                "performed_at": "2026-06-28 00:00:00",
            }],
        )
        self._complete_exercise_for_review(self.student, playlist, exercise)

        self.client.force_login(self.student)
        resp = self.client.get(self._player_definition_url(playlist, 1))
        payload = json.loads(resp.content)

        self.assertTrue(payload["reviewMode"])
        self.assertEqual(payload["reviewHarmonizationSonorities"], sonorities)

    def test_player_definition_omits_sonorities_for_non_harmonization(self):
        exercise, playlist = self._make_identification_exercise_in_playlist()
        self._complete_exercise_for_review(self.student, playlist, exercise)
        self.client.force_login(self.student)
        resp = self.client.get(self._player_definition_url(playlist, 1))
        payload = json.loads(resp.content)
        self.assertNotIn("reviewHarmonizationSonorities", payload)
```

> NOTE: `_make_harmonization_exercise_in_playlist`,
> `_make_identification_exercise_in_playlist`, `_complete_exercise_for_review`,
> and `_player_definition_url` — reuse or lightly adapt the existing setup
> helpers already used by `test_player_review_mode_uses_submitted_identification_answers`
> and `test_player_definition_includes_review_answers_in_review_mode` in this
> file (they already build umto exercises, playlists, and put the student into
> review mode). If a harmonization-specific builder does not exist, build one
> with `make_umto_exercise(..., mode=InteractionMode.HARMONIZATION)` matching the
> existing identification builder, asserting `payload["mode"] == "harmonization"`
> as a sanity check inside the harmonization test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.student.tests.test_player_views.PlayerViewTests.test_player_definition_includes_harmonization_sonorities_in_review --settings=harmony.settings.local`
Expected: FAIL — `KeyError: 'reviewHarmonizationSonorities'`

- [ ] **Step 3: Add a shared helper for the embed**

In `apps/student/views.py`, add a module-level helper near the other private
helpers (top of file, after `resolve_course_for_playlist`):

```python
def _attach_harmonization_review(exercise_context, user, playlist, course, exercise):
    """Embed the student's best stored harmonization pass for review mode.

    No-op unless the exercise is a harmonization exercise and a pass exists.
    """
    if exercise_context.get("mode") != "harmonization":
        return
    pd = (
        PerformanceData.objects.filter(user=user, playlist=playlist, course=course)
        .first()
    )
    if not pd:
        return
    sonorities = pd.get_best_harmonization_pass(exercise.id)
    if sonorities:
        exercise_context["reviewHarmonizationSonorities"] = sonorities
```

- [ ] **Step 4: Call the helper in both review branches**

In the **HTML player view** review branch (the `if state.mode == "review":` block
around line 975, after the `reviewAnswers` assignment) add:

```python
            _attach_harmonization_review(
                exercise_context, request.user, playlist, course, exercise
            )
```

In the **player-definition JSON** review branch (the `if state.mode == "review":`
block around line 1169, after its `reviewAnswers` assignment) add the identical
call:

```python
            _attach_harmonization_review(
                exercise_context, request.user, playlist, course, exercise
            )
```

- [ ] **Step 5: Add the template context flag (for banner copy in Task 4)**

In the HTML player view, where the render context dict is built (the dict that
already includes `"is_review_mode": state.mode == "review"`, ~line 1086/1111),
add a sibling key:

```python
            "is_harmonization_review": (
                state.mode == "review"
                and exercise_context.get("mode") == "harmonization"
            ),
```

- [ ] **Step 6: Run the view tests to verify they pass**

Run: `python manage.py test apps.student.tests.test_player_views --settings=harmony.settings.local`
Expected: PASS (new tests pass; existing review tests still pass)

- [ ] **Step 7: Commit**

```bash
git add apps/student/views.py apps/student/tests/test_player_views.py
git commit -m "feat(harmonization): embed saved sonorities in review payload"
```

---

## Task 3: Frontend — restore sonorities + display-only guard

`definition.reviewHarmonizationSonorities` now flows to the frontend the same way
`definition.reviewMode`/`reviewAnswers` already do (`exercise.js:164`). Restore it
into the existing render path and block grading.

**Files:**
- Modify: `lab/static/js/src/components/app/exercise.js` (~line 163, identification
  review block)
- Modify: `lab/static/js/src/models/exercise_context.js` (`gradeHarmonizationMidiSet` ~line 363)

- [ ] **Step 1: Restore in `exercise.js`**

In `lab/static/js/src/components/app/exercise.js`, immediately after the existing
identification review block (the `if (models.exerciseContext._isIdentificationExercise ...)`
block ending ~line 169), add:

```javascript
    if (
      definition.reviewMode &&
      definition.reviewHarmonizationSonorities &&
      models.exerciseContext._isHarmonizationExercise &&
      models.exerciseContext._isHarmonizationExercise()
    ) {
      models.exerciseContext.acceptedHarmonizationSonorities = _.cloneDeep(
        definition.reviewHarmonizationSonorities
      );
      models.exerciseContext._harmonizationPointer =
        models.exerciseContext.acceptedHarmonizationSonorities.length;
      models.exerciseContext._reviewDisplayOnly = true;
    }
```

- [ ] **Step 2: Guard grading in `exercise_context.js`**

In `lab/static/js/src/models/exercise_context.js`, make `gradeHarmonizationMidiSet`
inert in display-only review. Change (line ~363):

```javascript
    gradeHarmonizationMidiSet: function (activeMidi) {
      this._harmonizationActiveMidiOverride = activeMidi || [];
```

to:

```javascript
    gradeHarmonizationMidiSet: function (activeMidi) {
      if (this._reviewDisplayOnly) return;
      this._harmonizationActiveMidiOverride = activeMidi || [];
```

- [ ] **Step 3: Initialize the flag in the constructor**

In `exercise_context.js`, near the other harmonization fields in the constructor
(~line 97-103), add an initializer so the property always exists:

```javascript
    this._reviewDisplayOnly = false;
```

- [ ] **Step 4: Manual verification (no JS unit harness for this DOM glue)**

Rebuild is automatic under the Vite dev server (HMR); otherwise `npm run build`.
Then:
1. Complete a harmonization exercise (Unit 9, playlist `PA03SM`, exercise 1) so a
   `PerformanceData` pass is saved.
2. Reload the exercise in review mode.
3. Expected: the staff now renders your saved upper-voice chords (not the bare
   exercise). Confirm in console there is no error and
   `acceptedHarmonizationSonorities` is populated.
4. Press Enter / click Lock chord — expected: nothing grades, notes do NOT change
   (guard active). (Control hiding comes in Task 4.)

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/app/exercise.js lab/static/js/src/models/exercise_context.js
git commit -m "feat(harmonization): restore saved sonorities in review (display-only)"
```

---

## Task 4: Hide note-entry controls + banner copy

Pure-display review should not show note-entry controls, and the banner copy
should reflect display-only.

**Files:**
- Modify: `apps/student/templates/student/player.html` (static banner ~line 105,
  body flag, JS banner ~line 222)
- Modify: `apps/student/static/student/exercise-canvas.css`
- Modify: `lab/static/js/src/components/app/exercise.js` (apply body class)

- [ ] **Step 1: Static banner copy + body flag (template)**

In `apps/student/templates/student/player.html`, replace the static review hint
(~line 103-107):

```django
    {% if is_review_mode %}
      <div class="s-player-input-hint" data-player-hint="review">
        Review mode — your result is preserved, practice freely.
      </div>
    {% endif %}
```

with:

```django
    {% if is_review_mode %}
      <div class="s-player-input-hint" data-player-hint="review">
        {% if is_harmonization_review %}Review mode — showing your saved result.{% else %}Review mode — your result is preserved, practice freely.{% endif %}
      </div>
    {% endif %}
```

- [ ] **Step 2: JS banner copy (template inline script)**

In the same file, in `refreshPlayerChrome` (~line 218-224), the review hint is set
unconditionally. Make it respect a harmonization flag carried on `newData`.
Replace (~line 222):

```javascript
        reviewHint.innerText = 'Review mode — your result is preserved, practice freely.';
```

with:

```javascript
        reviewHint.innerText = newData.harmonizationReview
          ? 'Review mode — showing your saved result.'
          : 'Review mode — your result is preserved, practice freely.';
```

> NOTE: `newData` is the player-chrome refresh payload used on in-app navigation.
> If it does not already carry a harmonization flag, set
> `newData.harmonizationReview = !!(newData.reviewMode && newData.reviewHarmonizationSonorities)`
> at the point `refreshPlayerChrome` is called, or derive it from the definition
> there. Confirm the payload shape during implementation; the initial page load
> uses the static template banner from Step 1, so this only affects later nav.

- [ ] **Step 3: Apply a body class for CSS hiding (exercise.js)**

In `lab/static/js/src/components/app/exercise.js`, in the same block added in
Task 3 Step 1 (after setting `_reviewDisplayOnly = true`), add:

```javascript
      var harmonyUiEl = document.querySelector(".harmony-ui");
      if (harmonyUiEl) {
        harmonyUiEl.classList.add("harmonization-review-display");
      }
```

- [ ] **Step 4: CSS to hide note-entry controls (exercise-canvas.css)**

Append to `apps/student/static/student/exercise-canvas.css`:

```css
/*
 * Harmonization review is pure display: hide note-entry controls (accidental
 * palette, Clear, Lock chord, and the MIDI/Click source toggle). Navigation
 * (Previous/Reset/Next), playback, and the score remain visible.
 */
.harmonization-review-display .click-note-input,
.harmonization-review-display #ident-input-toggle-container {
  display: none !important;
}
```

- [ ] **Step 5: Manual verification**

1. Reload a completed harmonization exercise in review.
2. Expected: saved answer renders; accidental palette + Clear + Lock chord +
   source toggle are hidden; Previous/Reset/Next/Play remain; banner reads
   "Review mode — showing your saved result."
3. Adjust the CSS selectors in Step 4 if any note-entry control is still visible
   or any needed control got hidden (inspect the live DOM to confirm class names;
   `.click-note-input` is built in `click_note.js:_buildEl`).

- [ ] **Step 6: Commit**

```bash
git add apps/student/templates/student/player.html apps/student/static/student/exercise-canvas.css lab/static/js/src/components/app/exercise.js
git commit -m "feat(harmonization): display-only review chrome (hide controls, banner copy)"
```

---

## Final verification

- [ ] **Step 1: Run all touched test suites**

```bash
pytest apps/exercises/tests/test_performance_data_harmonization.py -v
python manage.py test apps.student.tests.test_player_views --settings=harmony.settings.local
npm run lint
```
Expected: all green.

- [ ] **Step 2: Full manual QA pass**

1. Fresh harmonization attempt still works (play, lock chords, complete, save).
2. Reopen in review → saved answer renders, controls hidden, banner updated.
3. Reopen a harmonization exercise with NO prior pass → bare exercise renders, no
   error, no `reviewHarmonizationSonorities` in payload.
4. Identification review still restores answers (regression check).

- [ ] **Step 3: Confirm clean diff and final commit state**

```bash
git status
git log --oneline -5
```
