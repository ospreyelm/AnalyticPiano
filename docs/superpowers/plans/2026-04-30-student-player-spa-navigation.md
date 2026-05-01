# Student Player SPA Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make next, previous, and retry transitions in the student player update the exercise in place without a full page reload, while preserving the existing deep-link full-page entry path and student progression guards.

**Architecture:** Keep the existing lab-side exercise replacement mechanism in `music.js`, but give the student player its own JSON definition endpoint and stop forcing redirect-only navigation from `PlayerView`. The initial page load still comes from `PlayerView`; subsequent transitions fetch updated exercise payloads from `PlayerDefinitionView`, then refresh the student-specific page chrome from the returned payload.

**Tech Stack:** Django class-based views and tests, existing `generate_exercise_context()` backend payload builder, RequireJS AMD modules, jQuery AJAX, inline template JS in `player.html`, existing student player progression logic.

---

## File Map

| File | Role |
|------|------|
| `apps/student/views.py` | Add `PlayerDefinitionView`, remove forced redirect payload flag, add `playlistId` and `totalExercises`, and keep student-only navigation metadata aligned between HTML and JSON responses |
| `apps/student/urls.py` | Register `/units/<unit_num>/play/definition/` |
| `apps/student/tests/test_views.py` | Add regression coverage for JSON definition responses and updated initial player payload |
| `apps/student/templates/student/player.html` | Expose the student definition endpoint URL and add a small `refreshPlayerChrome()` helper for counter / banner refresh |
| `lab/static/js/src/components/music.js` | Reuse existing exercise swap flow, but target the student definition endpoint when present, honor JSON redirect payloads, and skip history rewriting for student transitions |
| `lab/static/js/src/components/exercise_score_card.js` | Make Try Again reuse the existing reload path instead of calling `window.location.reload()` |

---

## Task 1: Add backend regression tests for the student definition contract

**Files:**
- Modify: `apps/student/tests/test_views.py`
- Test: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write the failing tests for the new JSON endpoint**

Add the following tests near the existing `PlayerView` tests in `apps/student/tests/test_views.py`:

```python
    def test_player_definition_returns_json_for_current_step(self):
        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 1}),
            {"playlist": self.playlist.id, "exercise_num": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["exerciseNum"], 1)
        self.assertEqual(payload["playlistId"], self.playlist.id)
        self.assertEqual(payload["totalExercises"], self.playlist.exercise_count)
        self.assertFalse(payload["reviewMode"])
        self.assertNotIn("redirect", payload)

    def test_player_definition_returns_redirect_payload_for_skipped_step(self):
        second_exercise = Exercise.objects.create(
            _id=21014,
            description="Unit 1 note names 14",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23014,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )

        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 1}),
            {"playlist": self.playlist.id, "exercise_num": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "redirect": reverse("student:player", kwargs={"unit_num": 1})
                + f"?playlist={self.playlist.id}&exercise_num=1"
            },
        )

    def test_player_definition_returns_review_answers_in_review_mode(self):
        IdentificationAttempt.objects.create(
            user=self.student,
            playlist=self.playlist,
            exercise=self.exercise,
            answers={"0": "Student answer"},
            correct_answers={"0": "Answer key"},
            score={"correct": 1, "incorrect": 0, "unanswered": 0},
            is_page_submit=True,
            mode="submit",
        )

        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 1}),
            {"playlist": self.playlist.id, "exercise_num": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["reviewMode"])
        self.assertEqual(payload["reviewAnswers"], {"0": "Student answer"})
```

- [ ] **Step 2: Replace the old force-redirect assertion with payload assertions for the initial page**

In the existing `test_player_uses_force_redirect_for_student_navigation`, replace the old assertion with:

```python
    def test_player_embeds_playlist_id_and_total_exercises_without_force_redirect(self):
        second_exercise = Exercise.objects.create(
            _id=21003,
            description="Unit 1 note names 3",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23003,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'"playlistId": "{self.playlist.id}"'.encode(), response.content)
        self.assertIn(b'"totalExercises": 2', response.content)
        self.assertNotIn(b'"forceRedirect": true', response.content)
```

- [ ] **Step 3: Run the targeted tests to verify they fail**

Run:

```bash
python manage.py test apps.student.tests.test_views.PlayerViewTests -v 2
```

Expected:

- Django raises `NoReverseMatch` for `student:player-definition`
- the updated page-payload test fails because `playlistId` / `totalExercises` are missing
- the old payload still contains `"forceRedirect": true`

- [ ] **Step 4: Commit the failing test baseline**

```bash
git add apps/student/tests/test_views.py
git commit -m "test: add student player SPA navigation regression coverage"
```

---

## Task 2: Implement `PlayerDefinitionView` and align the initial player payload

**Files:**
- Modify: `apps/student/views.py`
- Modify: `apps/student/urls.py`
- Test: `apps/student/tests/test_views.py`

- [ ] **Step 1: Add a narrow helper to avoid duplicating student-player context assembly**

In `apps/student/views.py`, extract the student-only payload shaping from `PlayerView.get()` into a small module-level helper. Keep it narrow; do not move generic lab context building out of `generate_exercise_context()`.

Add a helper with this shape above `PlayerView`:

```python
def _build_student_player_context(request, unit_num: int, playlist: Playlist, exercise_num: int):
    playlist_tags = (playlist.tags or []) + (playlist.skill_tags or [])
    if "unit:1" not in playlist_tags:
        raise Http404("Playlist not part of Unit 1.")

    playlist_course = (
        PlaylistCourseOrdered.objects.filter(playlist=playlist)
        .select_related("course")
        .order_by("order", "_id")
        .first()
    )
    course = playlist_course.course if playlist_course else None

    if exercise_num > playlist.exercise_count:
        return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

    state = resolve_requested_step(request.user, playlist, exercise_num)
    if state.should_redirect:
        return redirect(
            reverse("student:player", kwargs={"unit_num": unit_num})
            + f"?playlist={playlist.id}&exercise_num={state.exercise_num}"
        )

    resolved_num = state.exercise_num
    exercise = playlist.get_exercise_obj_by_num(resolved_num)
    if not exercise:
        return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

    exercise_context = generate_exercise_context(
        resolved_num,
        exercise,
        request.user,
        playlist,
        course,
    )

    return {
        "exercise_context": exercise_context,
        "exercise_num": resolved_num,
        "course": course,
        "state": state,
    }
```

Important: the helper may return either an `HttpResponseRedirect` or a dict. This keeps `PlayerView` and `PlayerDefinitionView` behavior aligned without introducing a large cross-app refactor.

Immediately after the `generate_exercise_context(...)` call, move the existing review-mode answer merge, completed-step lookup, next/previous calculation, and `disableComputerKeyboardInput` logic from `PlayerView.get()` into this helper unchanged. The point of the helper is only to share the current student-specific payload shaping between HTML and JSON responses.

- [ ] **Step 2: Add the new payload fields and remove forced redirect behavior**

When finalizing `exercise_context` inside the helper, add:

```python
exercise_context["playlistId"] = playlist.id
exercise_context["totalExercises"] = playlist.exercise_count
exercise_context["disableComputerKeyboardInput"] = _disable_computer_keyboard_input(
    exercise_context, playlist, exercise
)
```

Delete the old line:

```python
exercise_context["forceRedirect"] = True
```

Keep the existing student-only navigation fields intact:

```python
exercise_context["reviewMode"] = state.mode == "review"
exercise_context["playerMode"] = state.mode
exercise_context["nextExercise"] = ...
exercise_context["nextExerciseNum"] = ...
exercise_context["nextExerciseId"] = ...
exercise_context["previousExercise"] = ...
exercise_context["previousExerciseNum"] = ...
exercise_context["previousExerciseId"] = ...
```

- [ ] **Step 3: Add `PlayerDefinitionView`**

In `apps/student/views.py`, add:

```python
class PlayerDefinitionView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        if not playlist_id:
            raise Http404("Playlist ID is required.")

        playlist = get_object_or_404(Playlist, id=playlist_id)

        try:
            exercise_num = int(request.GET.get("exercise_num", 1))
        except (TypeError, ValueError):
            raise Http404("Invalid exercise number.")

        if exercise_num < 1:
            raise Http404("Invalid exercise number.")

        result = _build_student_player_context(request, unit_num, playlist, exercise_num)
        if isinstance(result, HttpResponseRedirect):
            return JsonResponse({"redirect": result.url})

        return JsonResponse(result["exercise_context"])
```

Make sure `JsonResponse` is imported from `django.http`.

- [ ] **Step 4: Simplify `PlayerView` to use the helper**

Replace the duplicated payload-building code in `PlayerView.get()` with:

```python
        result = _build_student_player_context(request, unit_num, playlist, exercise_num)
        if isinstance(result, HttpResponseRedirect):
            return result

        exercise_context = result["exercise_context"]
        state = result["state"]
        resolved_num = result["exercise_num"]

        rj_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)
        rj_context.set_app_module("app/components/app/exercise")
        rj_context.set_module_params("app/components/app/exercise", exercise_context)

        context = {
            "unit_num": unit_num,
            "playlist": playlist,
            "exercise_num": resolved_num,
            "total_exercises": playlist.exercise_count,
            "is_review_mode": state.mode == "review",
            "disable_computer_keyboard_input": exercise_context["disableComputerKeyboardInput"],
        }
```

This keeps the initial deep-link render path unchanged except for the removal of forced redirect navigation.

- [ ] **Step 5: Register the route**

In `apps/student/urls.py`, add:

```python
    path("units/<int:unit_num>/play/definition/", views.PlayerDefinitionView.as_view(), name="player-definition"),
```

Place it immediately after the existing `student:player` route.

- [ ] **Step 6: Run the backend regression tests**

Run:

```bash
python manage.py test apps.student.tests.test_views.PlayerViewTests -v 2
```

Expected:

- the three new JSON-endpoint tests pass
- the updated payload test passes
- existing `PlayerViewTests` around review mode, next/prev metadata, and keyboard-disable behavior still pass

- [ ] **Step 7: Commit**

```bash
git add apps/student/views.py apps/student/urls.py apps/student/tests/test_views.py
git commit -m "feat: add student player definition endpoint"
```

---

## Task 3: Expose student-player endpoint and chrome refresh hooks in `player.html`

**Files:**
- Modify: `apps/student/templates/student/player.html`
- Modify: `apps/student/tests/test_views.py`
- Test: `apps/student/tests/test_views.py`

- [ ] **Step 1: Add a page-level regression test for the new template hooks**

Add this test to `apps/student/tests/test_views.py`:

```python
    def test_player_page_exposes_definition_endpoint_and_chrome_hooks(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            reverse("student:player-definition", kwargs={"unit_num": 1}).encode(),
            response.content,
        )
        self.assertIn(b"window.PLAYER_DEFINITION_URL", response.content)
        self.assertIn(b"window.refreshPlayerChrome", response.content)
```

- [ ] **Step 2: Run the template regression test to verify it fails**

Run:

```bash
python manage.py test apps.student.tests.test_views.PlayerViewTests.test_player_page_exposes_definition_endpoint_and_chrome_hooks -v 2
```

Expected: the test fails because the endpoint URL and helper are not yet present in the template.

- [ ] **Step 3: Add `PLAYER_DEFINITION_URL` and `refreshPlayerChrome()`**

In `apps/student/templates/student/player.html`, inside `{% block js_extra %}`, add before the existing `window.addEventListener('load', ...)` block:

```html
  <script>
    window.PLAYER_DEFINITION_URL = "{% url 'student:player-definition' unit_num=unit_num %}";
    window.refreshPlayerChrome = function (newData) {
      var cur = document.getElementById('js-player-current');
      var tot = document.getElementById('js-player-total');
      if (cur && newData && newData.exerciseNum != null) {
        cur.innerText = String(newData.exerciseNum);
      }
      if (tot && newData && newData.totalExercises != null) {
        tot.innerText = String(newData.totalExercises);
      }

      var hints = document.querySelectorAll('.s-player-input-hint[data-player-hint]');
      hints.forEach(function (node) { node.remove(); });

      var toolbar = document.querySelector('.s-player-wrap');
      if (!toolbar || !newData) return;

      if (newData.disableComputerKeyboardInput) {
        var midiHint = document.createElement('div');
        midiHint.className = 's-player-input-hint';
        midiHint.setAttribute('data-player-hint', 'midi');
        midiHint.innerText = 'Play using your MIDI keyboard or click the piano below. Any octave works.';
        toolbar.insertBefore(midiHint, document.querySelector('.harmony-ui'));
      }

      if (newData.reviewMode) {
        var reviewHint = document.createElement('div');
        reviewHint.className = 's-player-input-hint';
        reviewHint.setAttribute('data-player-hint', 'review');
        reviewHint.innerText = 'Review mode — your result is preserved, practice freely.';
        toolbar.insertBefore(reviewHint, document.querySelector('.harmony-ui'));
      }
    };
  </script>
```

Use the existing hint copy exactly so manual behavior stays consistent with the first page load.

- [ ] **Step 4: Mark the server-rendered hint banners for cleanup**

Change the two server-rendered hint blocks from:

```html
      <div class="s-player-input-hint">
```

to:

```html
      <div class="s-player-input-hint" data-player-hint="midi">
```

and:

```html
      <div class="s-player-input-hint" data-player-hint="review">
```

This lets `refreshPlayerChrome()` replace them cleanly after each AJAX transition.

- [ ] **Step 5: Remove the polling-based header sync**

Delete the `setInterval(...)` block that reads `#exercise-info` every 500ms. The AJAX loader will now call `refreshPlayerChrome(newData)` directly after each transition.

- [ ] **Step 6: Re-run the page-level regression test**

Run:

```bash
python manage.py test apps.student.tests.test_views.PlayerViewTests.test_player_page_exposes_definition_endpoint_and_chrome_hooks -v 2
```

Expected: the test passes.

- [ ] **Step 7: Commit**

```bash
git add apps/student/templates/student/player.html apps/student/tests/test_views.py
git commit -m "feat: expose student player SPA chrome hooks"
```

---

## Task 4: Wire `music.js` and Retry to the student AJAX endpoint

**Files:**
- Modify: `lab/static/js/src/components/music.js`
- Modify: `lab/static/js/src/components/exercise_score_card.js`
- Test: `apps/student/tests/test_views.py`

- [ ] **Step 1: Add a small request helper inside `renderPristine()`**

In `lab/static/js/src/components/music.js`, inside `renderPristine()`, add a tiny local helper before the `if (exerciseAction === "reload")` branch:

```javascript
        function loadDefinition(targetExerciseNum, targetExerciseId) {
          var requestUrl = window.PLAYER_DEFINITION_URL || "definition";
          var requestData;

          if (window.PLAYER_DEFINITION_URL) {
            requestData = {
              playlist: setdef.settings.definition.playlistId,
              exercise_num: targetExerciseNum,
            };
          } else {
            requestData = {
              playlist_name: setdef.settings.definition.playlistName,
              exercise_id: targetExerciseId,
              exercise_num: targetExerciseNum,
            };
          }

          $.ajax({
            type: "GET",
            url: requestUrl,
            async: false,
            data: requestData,
            dataType: "json",
            success: function (data) {
              if (data.redirect) {
                window.location.href = data.redirect;
                return;
              }
              newData = data;
            },
          });
        }
```

This keeps non-student lab flows on the existing relative `definition` URL and only switches request shape when the student template defines `window.PLAYER_DEFINITION_URL`.

- [ ] **Step 2: Replace the repeated student reload branches with the helper**

Change the four AJAX branches in `renderPristine()` to call:

```javascript
loadDefinition(
  setdef.settings.definition.exerciseNum,
  setdef.settings.definition.exerciseId
);
loadDefinition(
  setdef.settings.definition.nextExerciseNum,
  setdef.settings.definition.nextExerciseId
);
loadDefinition(
  setdef.settings.definition.previousExerciseNum,
  setdef.settings.definition.previousExerciseId
);
loadDefinition(1, setdef.settings.definition.firstExerciseId);
```

Also delete the old `if (setdef.settings.definition.forceRedirect) window.location.href = ...` branches.

- [ ] **Step 3: Skip the history rewrite for the student player**

Change:

```javascript
        if (!!newData?.exerciseNum) {
          const newPath = location.pathname.split("/").slice(0, -2);
          newPath.push(newData.exerciseNum);
          newPath.push("");
          window.history.replaceState("", "", newPath.join("/"));
        }
```

to:

```javascript
        if (!!newData?.exerciseNum && !window.PLAYER_DEFINITION_URL) {
          const newPath = location.pathname.split("/").slice(0, -2);
          newPath.push(newData.exerciseNum);
          newPath.push("");
          window.history.replaceState("", "", newPath.join("/"));
        }
```

This preserves the existing lab behavior while keeping the student URL fixed.

- [ ] **Step 4: Refresh student page chrome after successful AJAX loads**

After `newData` has been applied to the exercise definition, add:

```javascript
          if (window.refreshPlayerChrome) {
            window.refreshPlayerChrome(newData);
          }
```

Place it after `scex.settings.definition.settings.definition = newData;` and before `sheetComponent.renderExerciseInfo();`.

- [ ] **Step 5: Make Retry reuse `renderPristine("reload")` instead of hard reloading**

In `lab/static/js/src/components/exercise_score_card.js`, replace:

```javascript
        if (window.location) window.location.reload();
```

with:

```javascript
        var resetLink = document.querySelector('.js-btn-pristine');
        if (resetLink) {
          resetLink.click();
        }
```

This reuses the existing toolbar reset behavior without adding a new event constant or a wider event-system change.

- [ ] **Step 6: Run the backend regressions again**

Run:

```bash
python manage.py test apps.student.tests.test_views.PlayerViewTests -v 2
```

Expected: all `PlayerViewTests` still pass. This is a contract check that the HTML payload and JSON endpoint still match what the template and client code expect.

- [ ] **Step 7: Perform the manual SPA verification pass**

Run the app locally, sign in as a student, and verify this checklist in the browser:

```text
1. Open /student/units/1/play/?playlist=<playlist_id>&exercise_num=1
2. Click Next: exercise changes without full page reload
3. Click Previous: exercise changes without full page reload
4. Click Reset/Try Again: current exercise reloads without full page reload
5. Confirm the URL stays fixed during AJAX transitions
6. Confirm the counter in the header updates on each transition
7. Confirm review-mode banner appears/disappears correctly
8. Confirm MIDI-only hint appears/disappears correctly
9. Confirm a skipped-step request still redirects to the allowed step
10. Confirm an identification exercise preserves current-page autosave before moving away
11. Confirm a chorale exercise resets correctly after transition
```

Expected: all eleven checks succeed. If any fail, fix them before moving on.

- [ ] **Step 8: Commit**

```bash
git add lab/static/js/src/components/music.js lab/static/js/src/components/exercise_score_card.js
git commit -m "feat: enable SPA navigation in student player"
```

---

## Task 5: Final verification pass

**Files:**
- Test only

- [ ] **Step 1: Run the focused Django test module**

```bash
python manage.py test apps.student.tests.test_views -v 2
```

Expected: `OK` with all `PlayerViewTests` and related student view regressions green.

- [ ] **Step 2: Re-run the manual SPA checklist after the final build state**

Repeat the checklist from Task 4, Step 7 after the final code is in place.

Expected: no regressions from the last commit.

- [ ] **Step 3: Commit any final follow-up fixes**

```bash
git add apps/student/views.py apps/student/urls.py apps/student/tests/test_views.py apps/student/templates/student/player.html lab/static/js/src/components/music.js lab/static/js/src/components/exercise_score_card.js
git commit -m "test: verify student player SPA navigation"
```

---

## Self-Review

- Spec coverage:
  - student JSON endpoint: covered in Tasks 1-2
  - `playlistId` and `totalExercises`: covered in Tasks 1-2
  - template endpoint exposure and chrome refresh: covered in Task 3
  - `music.js` AJAX target / redirect handling / no history rewrite: covered in Task 4
  - Retry via AJAX reload path: covered in Task 4
  - deep-link initial render path preserved: covered by keeping `PlayerView` and validating with existing page tests
- Placeholder scan:
  - no `TODO`, `TBD`, or “similar to above” references remain
  - all code steps include concrete snippets or exact replacement instructions
- Type consistency:
  - route name is consistently `student:player-definition`
  - payload fields are consistently `playlistId`, `totalExercises`, `reviewMode`, and `disableComputerKeyboardInput`
  - the frontend hook names are consistently `window.PLAYER_DEFINITION_URL` and `window.refreshPlayerChrome`
