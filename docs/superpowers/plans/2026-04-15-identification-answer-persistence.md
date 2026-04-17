# Identification Answer Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two MIDI/navigation bugs in identification exercises and persist student answers to the database with a teacher-facing view.

**Architecture:** Three independent concerns tackled in sequence: (1) guard MIDI bindings in `exercise_context.js`, (2) save/restore grader state on navigation via new methods + `renderPristine` hooks in `music.js`, (3) new `IdentificationAttempt` Django model + two AJAX endpoints + teacher view. The frontend submits on page-complete and on navigate-away; the backend stores all attempts (no uniqueness constraint).

**Tech Stack:** Django (models, views, migrations, JSONField), vanilla JS (jQuery AJAX, Backbone-style objects), Django templates (Bootstrap), django-tables2 (course activity table).

---

## File Map

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_context.js` | Guard MIDI bindings; add `saveIdentState`, `restoreIdentState`, `_restoreIdentStateFromServer`, `submitIdentificationAnswers` |
| `lab/static/js/src/components/music.js` | Add save/restore/submit hooks in `renderPristine` |
| `apps/exercises/models.py` | Add `IdentificationAttempt` model at end of file |
| `apps/exercises/migrations/0056_identificationattempt.py` | Generated migration (via `makemigrations`) |
| `apps/exercises/views.py` | Add `submit_identification_answers` (POST+GET) view |
| `lab/urls.py` | Wire `ajax/identification-answers/` |
| `apps/dashboard/views/courses.py` | Add `identification_answers_view` + `course_has_identification_exercises` helper |
| `apps/dashboard/urls.py` | Add `courses/<course_id>/identification-answers/<int:student_id>/` pattern |
| `apps/dashboard/templates/dashboard/identification-answers.html` | New template |
| `apps/dashboard/templates/dashboard/course-activity.html` | Add per-student link |

---

## Task 1: Block MIDI Input in Identification Exercises

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:131-141`

### Context

`initListeners` at line 131 unconditionally binds `triggerTimer` and `grade` to `inputChords` change events. When MIDI notes arrive they fire `grade()`, which calls `submitIdentPage({ fromGrade: true })`, which re-grades and auto-advances. The guard `_isIdentificationExercise()` already exists at line 652.

- [ ] **Step 1: Read the current initListeners block**

Read `lab/static/js/src/models/exercise_context.js` lines 131–141 to confirm the exact text.

- [ ] **Step 2: Apply the guard**

In `lab/static/js/src/models/exercise_context.js`, replace:

```javascript
    initListeners: function () {
      let testing =
        window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false;
      if (true || testing) {
        // using .remove() in the following lines hampers the staff distribution (analysis too?)
        $(".js-play-view-controls").hide();
        $("#mainmenu").hide();
      }
      this.inputChords.bind("change", this.triggerTimer);
      this.inputChords.bind("change", this.grade);
    },
```

with:

```javascript
    initListeners: function () {
      let testing =
        window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false;
      if (true || testing) {
        // using .remove() in the following lines hampers the staff distribution (analysis too?)
        $(".js-play-view-controls").hide();
        $("#mainmenu").hide();
      }
      if (!this._isIdentificationExercise()) {
        this.inputChords.bind("change", this.triggerTimer);
        this.inputChords.bind("change", this.grade);
      }
    },
```

- [ ] **Step 3: Verify in browser**

Open an identification exercise (e.g. a pitch identification exercise). Press keys on the MIDI controller or keyboard. Confirm:
- Sound still plays (MIDI is NOT disabled).
- The grader does NOT trigger (no auto-advance, no re-grading, no incorrect flash).

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "fix: block MIDI input grading in identification exercises"
```

---

## Task 2: Add `saveIdentState` / `restoreIdentState` / `_restoreIdentStateFromServer` to ExerciseContext

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

### Context

These three methods are the foundation for Bug Fix 2. They will be called from `renderPristine` in Task 3. Add them as new properties on the `ExerciseContext` object, right after `submitExerciseReport` or near other ident-related helpers. The `_identStateCache` is a plain object keyed by `exerciseId`; it lives on the `ExerciseContext` instance.

Existing methods for reference:
- `_isIdentificationExercise()` — line 652, returns bool
- `this.grader.answers` — the grader's answer map
- `this._identPage` — current page index
- `this.grader.reset()` — resets grader state
- `this.updateDisplayChords()` — refreshes display
- `this.trigger("graded")` — fires graded event

- [ ] **Step 1: Find the insertion point**

Search for `submitExerciseReport` in `exercise_context.js`. Add the three new methods immediately after the closing `},` of `submitExerciseReport`.

- [ ] **Step 2: Insert the three new methods**

After `submitExerciseReport`'s closing `},`, add:

```javascript
    saveIdentState: function () {
      if (!this._isIdentificationExercise()) return;
      var exerciseId = this.definition.exercise.exerciseId;
      if (!exerciseId) return;
      if (!this._identStateCache) this._identStateCache = {};
      this._identStateCache[exerciseId] = {
        answers: _.clone(this.grader.answers),
        identPage: this._identPage
      };
    },

    restoreIdentState: function (exerciseId) {
      if (!this._isIdentificationExercise()) return;
      var cached = this._identStateCache && this._identStateCache[exerciseId];
      if (cached) {
        this.grader.answers = _.clone(cached.answers);
        this._identPage = cached.identPage;
      } else {
        // Try server fallback (async, fires after render)
        this._restoreIdentStateFromServer(exerciseId);
        // Reset immediately so the page shows clean while the fetch runs
        this.grader.reset();
        this._identPage = 0;
      }
    },

    _restoreIdentStateFromServer: function (exerciseId) {
      var self = this;
      // Set a restoring flag so any input that arrives before the response
      // is ignored rather than graded against a blank state.
      this.grader._restoring = true;
      $.ajax({
        type: "GET",
        url: "/ajax/identification-answers/",
        data: { exercise_id: exerciseId },
        dataType: "json",
        timeout: 5000,
        success: function (data) {
          self.grader._restoring = false;
          if (data && data.answers && Object.keys(data.answers).length > 0) {
            self.grader.answers = data.answers;
            self._identPage = data.page_num || 0;
            self.updateDisplayChords();
            self.trigger("graded");
          }
        },
        error: function (jqXHR, textStatus, errorThrown) {
          self.grader._restoring = false;
          console.log("Identification state restore failed:", textStatus, errorThrown);
        }
      });
    },
```

- [ ] **Step 3: Verify no syntax errors**

Run:
```bash
node --check lab/static/js/src/models/exercise_context.js
```
Expected: no output (no errors).

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: add saveIdentState/restoreIdentState methods to ExerciseContext"
```

---

## Task 3: Add `submitIdentificationAnswers` to ExerciseContext

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

### Context

This method is called in two places:
1. From `renderPristine` in music.js (navigate-away auto-save) — Task 4.
2. Inside `submitIdentPage` after `submitExerciseReport` — Task 5.

`this.definition.getProblems()` returns all problems (line 552 of exercise_definition.js).
`this.definition.getExerciseList()` returns the list of exercises (line 429).
`listEntry.id` is a string like `"XY34Z/3"` — `split("/")[0]` is the playlist ID, `split("/")[1]` is the exercise number.
`this.definition.exercise.performing_course` is the courseId (set at line 840 of exercise_definition.js).

- [ ] **Step 1: Add `submitIdentificationAnswers` after `_restoreIdentStateFromServer`**

Add immediately after `_restoreIdentStateFromServer`'s closing `},`:

```javascript
    submitIdentificationAnswers: function (options) {
      var isPageSubmit = options && options.is_page_submit === true;
      if (!this._isIdentificationExercise()) return;
      if (!this.definition.exercise.performing_course) return;

      var grader = this.grader;
      if (!grader.answers || Object.keys(grader.answers).length === 0) return;

      // Compute correctness and score from current grader state
      var allProblems = this.definition.getProblems();
      var answers = grader.answers;
      var correctness = {};
      var correct = 0, incorrect = 0, unanswered = 0;

      for (var i = 0; i < allProblems.length; i++) {
        if (answers.hasOwnProperty(String(i))) {
          var isCorrect = answers[String(i)] === allProblems[i].answer;
          correctness[String(i)] = isCorrect;
          if (isCorrect) { correct++; } else { incorrect++; }
        } else {
          unanswered++;
        }
      }

      var idx = this.definition.getExerciseList().reduce(function (sel, cur, index) {
        return sel < 0 && cur.selected ? index : sel;
      }, -1);
      if (idx < 0) return;
      var listEntry = this.definition.getExerciseList()[idx];

      // Build correct_answers snapshot from problem definitions
      var correct_answers = {};
      for (var j = 0; j < allProblems.length; j++) {
        correct_answers[String(j)] = allProblems[j].answer;
      }

      var payload = {
        course_ID: this.definition.exercise.performing_course,
        playlist_ID: listEntry.id.split("/")[0],
        exercise_num: parseInt(listEntry.id.split("/")[1], 10),
        answers: answers,
        correctness: correctness,
        score: { correct: correct, incorrect: incorrect, unanswered: unanswered },
        correct_answers: correct_answers,
        page_num: this._identPage,
        is_page_submit: isPageSubmit
      };

      $.ajax({
        type: "POST",
        url: "/ajax/identification-answers/",
        data: { data: JSON.stringify(payload) },
        dataType: "text"
      }).done(function () {
        console.log("Identification answers saved");
      }).fail(function (jqXHR, textStatus, errorThrown) {
        console.log("Identification answers save failed", textStatus, errorThrown);
      });
    },
```

- [ ] **Step 2: Verify no syntax errors**

```bash
node --check lab/static/js/src/models/exercise_context.js
```
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: add submitIdentificationAnswers method to ExerciseContext"
```

---

## Task 4: Hook `renderPristine` in music.js (Bug Fix 2 navigation + auto-save)

**Files:**
- Modify: `lab/static/js/src/components/music.js:177-381`

### Context

`renderPristine` is at line 177 in music.js. The structure is:
1. Lines 177–287: fetch `newData` for the requested action (reload/next/previous/first).
2. Lines 289–374: apply `newData` to `scex` — `scex.definition.exercise = scex.definition.parse(newData)` is at line 309.
3. Lines 377–380: `sheetComponent.render()`.

We need two insertions:
- **Before the fetch** (after line 184 where `scex` is assigned): save state + submit answers for the current exercise.
- **After `scex.definition.exercise = scex.definition.parse(newData)` block** (after the `if (Object.keys(newData).length)` block, around line 359): restore state for the new exercise.

The `if (Object.keys(newData).length)` block ends with `this.trigger("change");` at ~line 359 followed by `}`.

- [ ] **Step 1: Read lines 183-190 of music.js to find the exact insertion point for save**

Read `lab/static/js/src/components/music.js` lines 183–195 to confirm `scex` assignment location.

- [ ] **Step 2: Insert save + submit before the fetch**

After the line `let setdef = scex.settings.definition;` (line 185) and before `let newData = {};` (line 189), insert:

```javascript
        // Save current identification state before navigating away
        if (scex._isIdentificationExercise && scex._isIdentificationExercise()) {
          scex.saveIdentState();
          scex.submitIdentificationAnswers({ is_page_submit: false });
        }
```

- [ ] **Step 3: Read lines 356-376 to find exact insertion point for restore**

Read `lab/static/js/src/components/music.js` lines 356–380.

- [ ] **Step 4: Insert restore after definition parse block**

After the closing `}` of the `if (Object.keys(newData).length)` block (which ends with `this.trigger("change");`) and before `sheetComponent.renderExerciseInfo();`, insert:

```javascript
        // Restore identification state for new exercise (from cache or server)
        if (scex._isIdentificationExercise && scex._isIdentificationExercise()) {
          var newExerciseId = newData.exerciseId;
          scex.restoreIdentState(newExerciseId);
        }
```

- [ ] **Step 5: Verify no syntax errors**

```bash
node --check lab/static/js/src/components/music.js
```
Expected: no output.

- [ ] **Step 6: Verify in browser**

Open a playlist with multiple identification exercises:
1. Answer some questions on exercise 1.
2. Navigate to exercise 2 — answers should NOT appear on exercise 2 (fresh slate).
3. Navigate back to exercise 1 — previously entered answers should be restored.

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/components/music.js
git commit -m "fix: save/restore identification grader state on exercise navigation"
```

---

## Task 5: Call `submitIdentificationAnswers` on page submit in `submitIdentPage`

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:766-844`

### Context

`submitIdentPage` at line 766 has two `submitExerciseReport()` calls inside the `graded.result === CORRECT` branch:
- Line 807: when correct but not the last page (page advance).
- Line 815: when correct and it IS the last page (exercise complete).

We add `submitIdentificationAnswers({ is_page_submit: true })` immediately after EACH of those two `submitExerciseReport()` calls.

- [ ] **Step 1: Read submitIdentPage lines 798-827**

Read `lab/static/js/src/models/exercise_context.js` lines 798–827 to see exact code.

- [ ] **Step 2: Add call after first submitExerciseReport (non-last page)**

The block at ~lines 803-810 is:
```javascript
        if (!isLastPage) {
          this.done = false;
          this.endTimer();
          if (this.sealed != true) {
            this.submitExerciseReport();
          }
          graded.advancedPage = true;
          this.goToIdentPage(this._identPage + 1);
```

Replace it with:
```javascript
        if (!isLastPage) {
          this.done = false;
          this.endTimer();
          if (this.sealed != true) {
            this.submitExerciseReport();
            this.submitIdentificationAnswers({ is_page_submit: true });
          }
          graded.advancedPage = true;
          this.goToIdentPage(this._identPage + 1);
```

- [ ] **Step 3: Add call after second submitExerciseReport (last page / exercise complete)**

The block at ~lines 811-826 is:
```javascript
        } else {
          this.done = true;
          this.endTimer();
          if (this.sealed != true) {
            this.submitExerciseReport();
          }
          this.state = ExerciseContext.STATE.CORRECT;
          this.sealed = true;
```

Replace it with:
```javascript
        } else {
          this.done = true;
          this.endTimer();
          if (this.sealed != true) {
            this.submitExerciseReport();
            this.submitIdentificationAnswers({ is_page_submit: true });
          }
          this.state = ExerciseContext.STATE.CORRECT;
          this.sealed = true;
```

- [ ] **Step 4: Verify no syntax errors**

```bash
node --check lab/static/js/src/models/exercise_context.js
```
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: submit identification answers on page complete"
```

---

## Task 6: Add `IdentificationAttempt` Model and Migration

**Files:**
- Modify: `apps/exercises/models.py`
- Create: `apps/exercises/migrations/0056_identificationattempt.py` (generated)

### Context

The model references `User`, `Exercise`, `Course`, and `Playlist` — all already defined in `models.py`. `JSONField` is already imported at line 10. Add the class at the end of the file, after the existing `PerformanceData` class.

- [ ] **Step 1: Add `IdentificationAttempt` class to models.py**

At the end of `apps/exercises/models.py`, add:

```python
class IdentificationAttempt(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="identification_attempts"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name="identification_attempts"
    )
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="identification_attempts"
    )
    playlist = models.ForeignKey(
        Playlist, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="identification_attempts"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    answers = JSONField(default=dict)
    correctness = JSONField(default=dict)
    score = JSONField(default=dict)
    correct_answers = JSONField(default=dict)
    is_page_submit = models.BooleanField(default=False)
    page_num = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Identification Attempt"
        verbose_name_plural = "Identification Attempts"
        ordering = ["submitted_at"]

    def __str__(self):
        return f"User:{self.user} Exercise:{self.exercise_id} at {self.submitted_at}"
```

- [ ] **Step 2: Generate migration**

```bash
python manage.py makemigrations exercises --name add_identification_attempt
```

Expected output:
```
Migrations for 'exercises':
  apps/exercises/migrations/0056_add_identification_attempt.py
    - Create model IdentificationAttempt
```

- [ ] **Step 3: Run migration**

```bash
python manage.py migrate exercises
```

Expected: `Applying exercises.0056_add_identification_attempt... OK`

- [ ] **Step 4: Verify table in shell**

```bash
python manage.py shell -c "from apps.exercises.models import IdentificationAttempt; print(IdentificationAttempt.objects.count())"
```
Expected: `0`

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/models.py apps/exercises/migrations/
git commit -m "feat: add IdentificationAttempt model and migration"
```

---

## Task 7: Add POST/GET AJAX Views for Identification Answers

**Files:**
- Modify: `apps/exercises/views.py`
- Modify: `lab/urls.py`

### Context

Follow the same pattern as `submit_exercise_performance` (line 80–115 of views.py): `@login_required`, `@method_decorator(csrf_exempt)`, parse `request.POST.get("data")`, look up `course_id`, `playlist_id`, `exercise_id` by string-to-int conversion.

For the GET endpoint: look up the most recent `IdentificationAttempt` for `(request.user, exercise_id)` and return as JSON. Return `{}` if not found.

Both GET and POST are handled by the same view function, dispatching on `request.method`.

The `Exercise` model lookup: `exercise_id` in the payload is derived from `playlist.get_exercise_obj_by_num(exercise_num).id` — this is a string exercise ID (not integer). The GET endpoint receives `exercise_id` directly as a query param (not the course+playlist+num triple).

- [ ] **Step 1: Add imports needed**

Check `apps/exercises/views.py` for existing imports. Add `JsonResponse` if not present:

```python
from django.http import HttpResponse, JsonResponse
```

Also add at the top of views.py (after existing imports):
```python
from .models import PerformanceData, IdentificationAttempt
```

(Note: check whether `IdentificationAttempt` is already imported — it won't be since we just added it.)

- [ ] **Step 2: Add the view at the end of `apps/exercises/views.py`**

```python
@login_required
@csrf_exempt
def identification_answers_view(request):
    if request.method == "POST":
        data = json.loads(request.POST.get("data"))
        data_course_id = data["course_ID"]
        data_playlist_id = data["playlist_ID"]
        data_exercise_num = data["exercise_num"]

        try:
            course = Course.objects.get(id=data_course_id)
            playlist = Playlist.objects.get(id=data_playlist_id)
            exercise = playlist.get_exercise_obj_by_num(int(data_exercise_num))
        except (Course.DoesNotExist, Playlist.DoesNotExist, Exception) as e:
            return JsonResponse({"error": str(e)}, status=400)

        IdentificationAttempt.objects.create(
            user=request.user,
            exercise=exercise,
            course=course,
            playlist=playlist,
            answers=data.get("answers", {}),
            correctness=data.get("correctness", {}),
            score=data.get("score", {}),
            correct_answers=data.get("correct_answers", {}),
            page_num=data.get("page_num"),
            is_page_submit=data.get("is_page_submit", False),
        )
        return HttpResponse(status=201)

    elif request.method == "GET":
        exercise_id = request.GET.get("exercise_id")
        if not exercise_id:
            return JsonResponse({})
        attempt = (
            IdentificationAttempt.objects.filter(
                user=request.user,
                exercise_id=exercise_id,
            )
            .order_by("-submitted_at")
            .first()
        )
        if not attempt:
            return JsonResponse({})
        return JsonResponse({
            "answers": attempt.answers,
            "correctness": attempt.correctness,
            "score": attempt.score,
            "page_num": attempt.page_num,
            "submitted_at": attempt.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return HttpResponse(status=405)
```

- [ ] **Step 3: Check existing imports in views.py**

Read the top of `apps/exercises/views.py` to see what's already imported. Confirm `json`, `Course`, `Playlist`, `Exercise` are imported. If not, add them.

Currently imported in views.py: `json` (check), `Course`, `Playlist` (check these are imported from models). Add `IdentificationAttempt` to the models import line.

- [ ] **Step 4: Wire URL in lab/urls.py**

In `lab/urls.py`, add to the imports:
```python
from apps.exercises.views import (
    ...existing imports...,
    identification_answers_view,
)
```

Add to urlpatterns:
```python
path("ajax/identification-answers/", identification_answers_view, name="identification-answers"),
```

Place it near the `ajax/exercise-performance/` entry for consistency.

- [ ] **Step 5: Test POST endpoint manually**

```bash
python manage.py shell -c "
from apps.exercises.models import IdentificationAttempt
print('Model accessible:', IdentificationAttempt)
"
```

- [ ] **Step 6: Commit**

```bash
git add apps/exercises/views.py lab/urls.py
git commit -m "feat: add POST/GET AJAX endpoints for identification answers"
```

---

## Task 8: Teacher View — Backend

**Files:**
- Modify: `apps/dashboard/views/courses.py`
- Modify: `apps/dashboard/urls.py`

### Context

Add `identification_answers_view` to `courses.py`. Also add the `course_has_identification_exercises` helper used by the course-activity template.

The `course_activity_view` context dict is passed to `course-activity.html` which we modify in Task 9. We need to pass `course_has_identification_exercises(course)` to that template. Add it to the existing context dict in `course_activity_view`.

The URL is: `courses/<str:course_id>/identification-answers/<int:student_id>/`

- [ ] **Step 1: Add imports to `apps/dashboard/views/courses.py`**

Check existing imports. Add:
```python
from apps.exercises.models import IdentificationAttempt
```

- [ ] **Step 2: Add helper function and view to `apps/dashboard/views/courses.py`**

Near the top of the file (after imports), add:

```python
PITCH_ANALYSIS_TYPES = {
    "note_name", "solfege", "do_based_solfege",
    "scale_degree", "fixed_do", "pitch_class",
    "interval_generic", "interval_specific",
    "roman", "figured_bass",
}


def course_has_identification_exercises(course):
    return course.exercise_set.filter(
        data__type="chorale_identification"
    ).exists()
```

At the end of the file (or after `course_activity_view`), add:

```python
def identification_answers_view(request, course_id, student_id):
    from django.contrib.auth import get_user_model
    from collections import defaultdict
    User = get_user_model()

    course = get_object_or_404(Course, id=course_id)
    if request.user != course.authored_by:
        raise PermissionDenied

    student = get_object_or_404(User, id=student_id)

    attempts = IdentificationAttempt.objects.filter(
        user=student, course=course
    ).select_related("exercise").order_by("submitted_at")

    by_exercise = defaultdict(list)
    for attempt in attempts:
        by_exercise[attempt.exercise_id].append(attempt)

    exercises_data = []
    for exercise_id, exercise_attempts in by_exercise.items():
        latest = exercise_attempts[-1]
        exercises_data.append({
            "exercise": latest.exercise,
            "latest": latest,
            "history": exercise_attempts[:-1],
        })

    return render(request, "dashboard/identification-answers.html", {
        "course": course,
        "student": student,
        "exercises_data": exercises_data,
    })
```

- [ ] **Step 3: Inject `has_identification_exercises` into `course_activity_view` context**

Find the `render(...)` call at the bottom of `course_activity_view`. Add `"has_identification_exercises": course_has_identification_exercises(course)` to its context dict.

Read the end of `course_activity_view` to find the render call, then add the context key.

- [ ] **Step 4: Wire URL in `apps/dashboard/urls.py`**

Add import:
```python
from apps.dashboard.views.courses import (
    ...existing...,
    identification_answers_view as dashboard_identification_answers_view,
)
```

Add URL pattern after `course-activity`:
```python
path(
    "courses/<str:course_id>/identification-answers/<int:student_id>/",
    dashboard_identification_answers_view,
    name="course-identification-answers",
),
```

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/views/courses.py apps/dashboard/urls.py
git commit -m "feat: add identification answers teacher view"
```

---

## Task 9: Teacher View — Template

**Files:**
- Create: `apps/dashboard/templates/dashboard/identification-answers.html`
- Modify: `apps/dashboard/templates/dashboard/course-activity.html`

### Context

The `identification-answers.html` template receives `course`, `student`, `exercises_data` (list of dicts with `exercise`, `latest`, `history` keys). For each exercise: show a summary row (title, score, timestamp), then a table with per-problem rows.

Each `attempt.answers` is a dict like `{"0": "I", "1": "ii"}`. Each `attempt.correct_answers` is `{"0": "I", "1": "ii", "2": "V7"}`. Iterate over `correct_answers` keys to build the table. Use `attempt.answers.get(key, "–")` for the student answer. Compare to determine ✓/✗.

The `course-activity.html` link should only render when `has_identification_exercises` is True. The student's `id` is available as `row.performer.id`.

- [ ] **Step 1: Read `apps/dashboard/templates/dashboard/base-content-list.html` to understand `{% extends %}`**

Read the first 20 lines to confirm the block names.

- [ ] **Step 2: Create `identification-answers.html`**

Create `apps/dashboard/templates/dashboard/identification-answers.html`:

```html
{% extends "dashboard/base.html" %}
{% load static %}

{% block content %}
<div class="container mt-4">
  <h1>Identification Answers</h1>
  <p>
    Student: <strong>{{ student.get_full_name }}</strong> &mdash;
    Course: <strong>{{ course.title }}</strong>
  </p>
  <a href="{% url 'course-activity' course.id %}" class="btn btn-sm btn-outline-secondary mb-3">
    &larr; Back to Course Activity
  </a>

  {% if not exercises_data %}
    <p>No identification answers recorded for this student in this course.</p>
  {% endif %}

  {% for item in exercises_data %}
  <div class="card mb-4">
    <div class="card-header">
      <strong>{{ item.exercise.name }}</strong>
      &mdash;
      Score: {{ item.latest.score.correct }} / {{ item.latest.score.correct|add:item.latest.score.incorrect|add:item.latest.score.unanswered }} correct
      &mdash;
      Submitted: {{ item.latest.submitted_at|date:"Y-m-d H:i" }}
    </div>
    <div class="card-body p-0">
      <table class="table table-sm mb-0">
        <thead>
          <tr>
            <th>#</th>
            <th>Correct Answer</th>
            <th>Student Answer</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {% for key, correct_answer in item.latest.correct_answers.items %}
          {% with student_answer=item.latest.answers|dict_key:key %}
          <tr>
            <td>{{ key }}</td>
            <td>{{ correct_answer }}</td>
            <td>{% if student_answer %}{{ student_answer }}{% else %}&ndash;{% endif %}</td>
            <td>
              {% if not student_answer %}
                <span class="text-muted">&ndash;</span>
              {% elif student_answer == correct_answer %}
                <span class="text-success">&#10003;</span>
              {% else %}
                <span class="text-danger">&#10007;</span>
              {% endif %}
            </td>
          </tr>
          {% endwith %}
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% if item.history %}
    <div class="card-footer">
      <details>
        <summary>History ({{ item.history|length }} earlier attempt{{ item.history|length|pluralize }})</summary>
        {% for attempt in item.history %}
        <h6 class="mt-3">{{ attempt.submitted_at|date:"Y-m-d H:i" }} &mdash; {{ attempt.score.correct }} / {{ attempt.score.correct|add:attempt.score.incorrect|add:attempt.score.unanswered }} correct</h6>
        <table class="table table-sm">
          <thead>
            <tr><th>#</th><th>Correct</th><th>Student</th><th>Result</th></tr>
          </thead>
          <tbody>
            {% for key, correct_answer in attempt.correct_answers.items %}
            {% with student_answer=attempt.answers|dict_key:key %}
            <tr>
              <td>{{ key }}</td>
              <td>{{ correct_answer }}</td>
              <td>{% if student_answer %}{{ student_answer }}{% else %}&ndash;{% endif %}</td>
              <td>
                {% if not student_answer %}
                  <span class="text-muted">&ndash;</span>
                {% elif student_answer == correct_answer %}
                  <span class="text-success">&#10003;</span>
                {% else %}
                  <span class="text-danger">&#10007;</span>
                {% endif %}
              </td>
            </tr>
            {% endwith %}
            {% endfor %}
          </tbody>
        </table>
        {% endfor %}
      </details>
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endblock %}
```

**Note on `|dict_key`:** Django templates don't have a built-in `dict_key` filter. Use a templatetag or restructure the data in the view. The simplest fix is to pre-process in the view: convert each attempt's `correct_answers` to a list of `(key, correct, student, is_correct)` tuples. Update `identification_answers_view` to build this:

```python
def _build_rows(attempt):
    rows = []
    for key in sorted(attempt.correct_answers.keys(), key=lambda k: int(k)):
        correct = attempt.correct_answers[key]
        student = attempt.answers.get(key)
        rows.append({
            "key": key,
            "correct": correct,
            "student": student,
            "is_correct": student == correct if student is not None else None,
        })
    return rows

# In identification_answers_view, replace exercises_data construction:
exercises_data = []
for exercise_id, exercise_attempts in by_exercise.items():
    latest = exercise_attempts[-1]
    exercises_data.append({
        "exercise": latest.exercise,
        "latest": latest,
        "latest_rows": _build_rows(latest),
        "history": [
            {"attempt": a, "rows": _build_rows(a)}
            for a in exercise_attempts[:-1]
        ],
    })
```

Then update the template to use `item.latest_rows` and `h.rows` instead of `correct_answers.items` + `answers|dict_key`.

- [ ] **Step 3: Update `identification_answers_view` to use `_build_rows`**

In `apps/dashboard/views/courses.py`, update the view as described in Step 2 (add `_build_rows` helper and update `exercises_data` construction).

- [ ] **Step 4: Rewrite template to use pre-processed rows**

Rewrite `identification-answers.html` replacing the `|dict_key` approach with `item.latest_rows` and `h.rows`:

```html
{% extends "dashboard/base.html" %}
{% load static %}

{% block content %}
<div class="container mt-4">
  <h1>Identification Answers</h1>
  <p>
    Student: <strong>{{ student.get_full_name }}</strong> &mdash;
    Course: <strong>{{ course.title }}</strong>
  </p>
  <a href="{% url 'course-activity' course.id %}" class="btn btn-sm btn-outline-secondary mb-3">
    &larr; Back to Course Activity
  </a>

  {% if not exercises_data %}
    <p>No identification answers recorded for this student in this course.</p>
  {% endif %}

  {% for item in exercises_data %}
  <div class="card mb-4">
    <div class="card-header">
      <strong>{{ item.exercise.name }}</strong>
      &mdash;
      Score: {{ item.latest.score.correct }} / {{ item.latest.score.correct|add:item.latest.score.incorrect|add:item.latest.score.unanswered }} correct
      &mdash;
      Submitted: {{ item.latest.submitted_at|date:"Y-m-d H:i" }}
    </div>
    <div class="card-body p-0">
      <table class="table table-sm mb-0">
        <thead>
          <tr>
            <th>#</th>
            <th>Correct Answer</th>
            <th>Student Answer</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {% for row in item.latest_rows %}
          <tr>
            <td>{{ row.key }}</td>
            <td>{{ row.correct }}</td>
            <td>{% if row.student %}{{ row.student }}{% else %}&ndash;{% endif %}</td>
            <td>
              {% if row.is_correct is None %}
                <span class="text-muted">&ndash;</span>
              {% elif row.is_correct %}
                <span class="text-success">&#10003;</span>
              {% else %}
                <span class="text-danger">&#10007;</span>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% if item.history %}
    <div class="card-footer">
      <details>
        <summary>History ({{ item.history|length }} earlier attempt{{ item.history|length|pluralize }})</summary>
        {% for h in item.history %}
        <h6 class="mt-3">{{ h.attempt.submitted_at|date:"Y-m-d H:i" }} &mdash; {{ h.attempt.score.correct }} / {{ h.attempt.score.correct|add:h.attempt.score.incorrect|add:h.attempt.score.unanswered }} correct</h6>
        <table class="table table-sm">
          <thead>
            <tr><th>#</th><th>Correct</th><th>Student</th><th>Result</th></tr>
          </thead>
          <tbody>
            {% for row in h.rows %}
            <tr>
              <td>{{ row.key }}</td>
              <td>{{ row.correct }}</td>
              <td>{% if row.student %}{{ row.student }}{% else %}&ndash;{% endif %}</td>
              <td>
                {% if row.is_correct is None %}
                  <span class="text-muted">&ndash;</span>
                {% elif row.is_correct %}
                  <span class="text-success">&#10003;</span>
                {% else %}
                  <span class="text-danger">&#10007;</span>
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
        {% endfor %}
      </details>
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 5: Add link in `course-activity.html`**

Read `apps/dashboard/templates/dashboard/course-activity.html` to find where student rows are rendered. Look for `performer` or similar. 

Since this template only has 51 lines and uses a django-tables2 table (not a hand-rolled loop), the per-student link cannot easily be injected into the table itself. Add it as a separate section below the table (or above it), listing students with identification answers:

In `course-activity.html`, in the `{% block content %}` or equivalent area (add a new block if needed), add after the table:

```html
{% if has_identification_exercises %}
<div class="mt-4">
  <h5>Identification Answer Details</h5>
  <p>View per-student identification answers for this course:</p>
  <ul>
    {% for performer_data in table.data %}
    {% if performer_data.performer.id %}
    <li>
      <a href="{% url 'course-identification-answers' course.id performer_data.performer.id %}">
        {{ performer_data.performer.get_full_name }}
      </a>
    </li>
    {% endif %}
    {% endfor %}
  </ul>
</div>
{% endif %}
```

Read `apps/dashboard/templates/dashboard/course-activity.html` fully first to understand current block structure, then insert appropriately.

- [ ] **Step 6: Verify template renders**

Navigate to a course activity page in browser. Confirm no Django template errors.

Navigate to `/dashboard/courses/<course_id>/identification-answers/<student_id>/`. Confirm page loads (may show "No identification answers" if none yet recorded).

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/templates/dashboard/identification-answers.html \
        apps/dashboard/templates/dashboard/course-activity.html \
        apps/dashboard/views/courses.py
git commit -m "feat: add identification answers teacher view and template"
```

---

## Task 10: End-to-End Verification

- [ ] **Step 1: Run Django tests**

```bash
python manage.py test apps.exercises apps.dashboard
```

Expected: all tests pass (or pre-existing failures only).

- [ ] **Step 2: Full flow test in browser**

1. Log in as a student enrolled in a course with a pitch identification playlist.
2. Open the playlist's first identification exercise.
3. Answer 2–3 questions (click `?` slots and choose answers).
4. Press "Submit" / let page auto-advance. Open DevTools console → confirm "Identification answers saved".
5. Navigate to the next exercise via the Next button. Confirm the previous exercise's answers are NOT shown on the new exercise.
6. Navigate back. Confirm the answers are restored from the in-memory cache.
7. Reload the page (hard reload). Navigate to the exercise that had answers. Confirm the server-fallback restore kicks in (brief blank then answers appear).

- [ ] **Step 3: Teacher view test**

1. Log in as the course teacher.
2. Navigate to `/dashboard/courses/<course_id>/activity/`.
3. Confirm the "Identification Answer Details" section appears.
4. Click a student link. Confirm the detail view shows the submitted answers with correct/incorrect marks.

- [ ] **Step 4: MIDI non-interference test**

1. Open an identification exercise.
2. Connect a MIDI controller and play several notes.
3. Confirm: no grading fires, no auto-advance, no incorrect flash. Sound plays normally.

---

## Task 10: localStorage Fallback for Standalone (Non-Course) Exercise Browsing

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

### Context

When an identification exercise is browsed outside a playlist (standalone URL, e.g. `/lab/exercises/EX123/1/`), `forceRedirect = True` is set by the Django view (`lab/views.py:194`). This means Next/Previous navigation does `window.location.href = ...` — a full page reload — instead of the in-page AJAX `renderPristine`. As a result:

- The in-memory `_identStateCache` is wiped on every navigation.
- `submitIdentificationAnswers` returns early (no `performing_course`), so nothing is saved to the DB either.

The fix: use `localStorage` as a third persistence tier, below the in-memory cache and the server. On every answer change (or at navigate-away time), write answers to `localStorage`. On load, read from `localStorage` if no in-memory cache and no server data.

**Storage key:** `"identAnswers:" + exerciseId` — namespaced to avoid collisions.

**When to write:** In `saveIdentState`, after writing to `_identStateCache`, also write to `localStorage`.

**When to read:** In `restoreIdentState`, after the cache miss, before firing the server fallback, check `localStorage`. If found, restore immediately (synchronously) instead of hitting the server.

**TTL:** Store a `savedAt` timestamp alongside answers. Discard entries older than 7 days on read.

**When to clear:** After a successful server-save (`submitIdentificationAnswers` POST succeeds), remove the `localStorage` entry for that exerciseId — it's been promoted to the DB.

### Step 1: Extend `saveIdentState` to write to localStorage

In `lab/static/js/src/models/exercise_context.js`, find `saveIdentState` and after the `_identStateCache` write, add:

```javascript
    saveIdentState: function () {
      if (!this._isIdentificationExercise()) return;
      var exerciseId = this.definition.exercise.exerciseId;
      if (!exerciseId) return;
      if (!this._identStateCache) this._identStateCache = {};
      var state = {
        answers: _.clone(this.grader.answers),
        identPage: this._identPage
      };
      this._identStateCache[exerciseId] = state;
      // localStorage fallback for force-redirect (standalone) navigation
      try {
        localStorage.setItem("identAnswers:" + exerciseId, JSON.stringify({
          answers: state.answers,
          identPage: state.identPage,
          savedAt: Date.now()
        }));
      } catch (e) {
        // localStorage unavailable (private browsing, quota exceeded) — ignore
      }
    },
```

### Step 2: Extend `restoreIdentState` to read from localStorage before server fallback

Replace the `else` branch (no cache hit) in `restoreIdentState`:

```javascript
    restoreIdentState: function (exerciseId) {
      if (!this._isIdentificationExercise()) return;
      var cached = this._identStateCache && this._identStateCache[exerciseId];
      if (cached) {
        this.grader.answers = _.clone(cached.answers);
        this._identPage = cached.identPage;
      } else {
        // Check localStorage before hitting the server
        var local = this._readLocalIdentState(exerciseId);
        if (local) {
          this.grader.answers = local.answers;
          this._identPage = local.identPage || 0;
          // Also populate in-memory cache so subsequent same-session navigations are fast
          if (!this._identStateCache) this._identStateCache = {};
          this._identStateCache[exerciseId] = local;
        } else {
          // Try server fallback (async, fires after render)
          this._restoreIdentStateFromServer(exerciseId);
          // Reset immediately so the page shows clean while the fetch runs
          this.grader.reset();
          this._identPage = 0;
        }
      }
    },
```

### Step 3: Add `_readLocalIdentState` helper

Add immediately after `_restoreIdentStateFromServer`:

```javascript
    _readLocalIdentState: function (exerciseId) {
      try {
        var raw = localStorage.getItem("identAnswers:" + exerciseId);
        if (!raw) return null;
        var data = JSON.parse(raw);
        // Discard entries older than 7 days
        var sevenDays = 7 * 24 * 60 * 60 * 1000;
        if (!data.savedAt || Date.now() - data.savedAt > sevenDays) {
          localStorage.removeItem("identAnswers:" + exerciseId);
          return null;
        }
        return data;
      } catch (e) {
        return null;
      }
    },
```

### Step 4: Clear localStorage on successful server save

In `submitIdentificationAnswers`, in the `.done()` callback, after logging success, remove the localStorage entry:

```javascript
      $.ajax({
        type: "POST",
        url: "/ajax/identification-answers/",
        data: { data: JSON.stringify(payload) },
        dataType: "text"
      }).done(function () {
        console.log("Identification answers saved");
        try { localStorage.removeItem("identAnswers:" + payload.exercise_id); } catch (e) {}
      }).fail(function (jqXHR, textStatus, errorThrown) {
        console.log("Identification answers save failed", textStatus, errorThrown);
      });
```

Wait — `payload` doesn't have `exercise_id` as a key; the exercise is identified by `course_ID + playlist_ID + exercise_num`. Instead, capture `exerciseId` from `this.definition.exercise.exerciseId` before the AJAX call and use it in the closure:

```javascript
      var selfExerciseId = this.definition.exercise.exerciseId;
      $.ajax({
        type: "POST",
        url: "/ajax/identification-answers/",
        data: { data: JSON.stringify(payload) },
        dataType: "text"
      }).done(function () {
        console.log("Identification answers saved");
        try { localStorage.removeItem("identAnswers:" + selfExerciseId); } catch (e) {}
      }).fail(function (jqXHR, textStatus, errorThrown) {
        console.log("Identification answers save failed", textStatus, errorThrown);
      });
```

### Step 5: Verify no syntax errors

```bash
node --check lab/static/js/src/models/exercise_context.js
```

### Step 6: Test in browser

1. Open a standalone identification exercise (not in a playlist/course).
2. Answer 2-3 questions.
3. Click Next (full page redirect to next exercise).
4. Click Previous (full page redirect back).
5. Confirm answers from step 2 are restored.
6. Reload the page — confirm answers still appear.
7. Confirm answers disappear after 7 days (can test by manually setting `savedAt` to an old timestamp in DevTools).

### Step 7: Commit

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: localStorage fallback for identification answer persistence in standalone exercises"
```

---

## Self-Review Against Spec

| Spec requirement | Covered in task |
|---|---|
| Block MIDI bindings in `initListeners` | Task 1 |
| `saveIdentState` method | Task 2 |
| `restoreIdentState` method | Task 2 |
| `_restoreIdentStateFromServer` method with `_restoring` flag | Task 2 |
| Hook both methods in `renderPristine` | Task 4 |
| `submitIdentificationAnswers` method | Task 3 |
| Call on page submit (both last+non-last page) | Task 5 |
| Call on navigate-away in `renderPristine` | Task 4 |
| `IdentificationAttempt` model with all fields | Task 6 |
| Migration | Task 6 |
| `POST /ajax/identification-answers/` | Task 7 |
| `GET /ajax/identification-answers/?exercise_id=` | Task 7 |
| URL wired in `lab/urls.py` | Task 7 |
| `identification_answers_view` teacher view | Task 8 |
| `course_has_identification_exercises` helper | Task 8 |
| URL in `apps/dashboard/urls.py` | Task 8 |
| `identification-answers.html` template | Task 9 |
| Per-student link in `course-activity.html` | Task 9 |
| Inject `has_identification_exercises` into activity view context | Task 8 Step 3 |
