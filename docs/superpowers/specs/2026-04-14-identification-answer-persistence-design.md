# Identification Answer Persistence & Bug Fixes — Design Spec

_Date: 2026-04-14_
_Status: Approved_

---

## Overview

Three related problems are addressed in this spec:

1. **MIDI bug** — identification exercises incorrectly respond to MIDI/keyboard input, triggering re-grading and auto-advance on every note played.
2. **Navigation state bug** — navigating to the next exercise carries the previous exercise's grader answers into the new one; navigating back loses the answers already given.
3. **Answer persistence** — student answers to identification exercises are never saved to the database, so teachers cannot see what students answered.

All three are fixed together because the navigation bug fix and the answer persistence share the same save/restore hook in `renderPristine`.

---

## Bug Fix 1: Block MIDI in Identification Exercises

### Root cause

`ExerciseContext.initListeners()` unconditionally binds two handlers to `inputChords` change events:

```javascript
this.inputChords.bind("change", this.triggerTimer);
this.inputChords.bind("change", this.grade);
```

When MIDI notes arrive, `MidiComponent` puts them into `inputChords`, firing `change`. For identification exercises, `grade()` calls `submitIdentPage({ fromGrade: true })`, which re-grades the page and — on a fully-correct last page — triggers `triggerNextExercise()`.

### Fix

Guard both bindings in `initListeners()`:

```javascript
initListeners: function () {
  // ... existing UI hide logic ...
  if (!this._isIdentificationExercise()) {
    this.inputChords.bind("change", this.triggerTimer);
    this.inputChords.bind("change", this.grade);
  }
},
```

The piano and MIDI device remain active (sound still plays) — only the grading pipeline is disconnected. No other changes needed.

**File:** `lab/static/js/src/models/exercise_context.js`

---

## Bug Fix 2: Fix Grader State on Exercise Navigation

### Root cause

`renderPristine(exerciseAction)` in `music.js` re-parses the new exercise definition but never resets `scex.grader.answers` or `scex._identPage`. The same `IdentificationGrader` instance persists across exercises, so:

- Loading the next exercise: new exercise's problems are graded against old answer indices → incorrect colours, phantom completions.
- Navigating back: the old answers were never saved → blank slate instead of previously-entered answers.

### Fix

Three new methods on `ExerciseContext`:

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

`_identStateCache` is initialised lazily as a plain object on the `ExerciseContext` instance.

**Hook in `renderPristine` (music.js)** — immediately before the AJAX fetch for new data:

```javascript
// Save current identification state before navigating away
if (scex._isIdentificationExercise && scex._isIdentificationExercise()) {
  scex.saveIdentState();
  scex.submitIdentificationAnswers({ is_page_submit: false });
}
```

After `scex.definition.exercise = scex.definition.parse(newData)` and related assignments:

```javascript
// Restore identification state for new exercise (from cache or server)
if (scex._isIdentificationExercise && scex._isIdentificationExercise()) {
  var newExerciseId = newData.exerciseId;
  scex.restoreIdentState(newExerciseId);
}
```

**Files:** `lab/static/js/src/models/exercise_context.js`, `lab/static/js/src/components/music.js`

---

## New Model: `IdentificationAttempt`

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
    # e.g. {"0": "I", "1": "ii", "2": "V7", "3": "I"}
    # keyed by absolute problem index (string, since JSON keys are strings)
    correctness = JSONField(default=dict)
    # e.g. {"0": true, "1": true, "2": false, "3": true}
    score = JSONField(default=dict)
    # e.g. {"correct": 3, "incorrect": 1, "unanswered": 0}
    correct_answers = JSONField(default=dict)
    # e.g. {"0": "I", "1": "ii", "2": "V7", "3": "I"}
    # snapshot of the correct answers at submission time, so the teacher view
    # does not need to re-parse the exercise definition
    is_page_submit = models.BooleanField(default=False)
    # True = explicit Submit/page-turn, False = navigate-away auto-save
    page_num = models.IntegerField(null=True, blank=True)
    # The page the student was on when this attempt was saved

    class Meta:
        verbose_name = "Identification Attempt"
        verbose_name_plural = "Identification Attempts"
        ordering = ["submitted_at"]

    def __str__(self):
        return f"User:{self.user} Exercise:{self.exercise_id} at {self.submitted_at}"
```

**Location:** `apps/exercises/models.py`

A migration is required. No changes to `PerformanceData`.

---

## New Endpoints

### `POST /ajax/identification-answers/`

Creates one `IdentificationAttempt` row. Only fires when `performing_course` is set and the grader has at least one answer.

**Payload:**
```json
{
  "course_ID": "AB12C",
  "playlist_ID": "XY34Z",
  "exercise_num": 3,
  "answers": { "0": "I", "1": "ii", "2": "V7" },
  "correctness": { "0": true, "1": true, "2": false },
  "score": { "correct": 2, "incorrect": 1, "unanswered": 1 },
  "correct_answers": { "0": "I", "1": "ii", "2": "V7", "3": "I" },
  "page_num": 0,
  "is_page_submit": true
}
```

**Response:** HTTP 201 on success. HTTP 400 with a JSON error message if `course_ID`, `playlist_ID`, or `exercise_num` are invalid.

**CSRF:** The endpoint uses `@csrf_exempt` (same pattern as `submit_exercise_performance`). Authentication is enforced via `@login_required`.

**Lookup logic** (same as `submit_exercise_performance`):
```python
course_id = Course.objects.get(id=data_course_id)._id
playlist_id = Playlist.objects.get(id=data_playlist_id)._id
exercise_id = Playlist.objects.filter(id=data_playlist_id).first()
    .get_exercise_obj_by_num(int(data_exercise_num)).id
```

**Location:** `apps/exercises/views.py`, URL in `lab/urls.py`

---

### `GET /ajax/identification-answers/`

Returns the most recent `IdentificationAttempt` for the current user and a given exercise. Used for server-fallback restore on back-navigation after a page reload.

**Query params:** `exercise_id=<exercise_id_string>`

**Response:**
```json
{
  "answers": { "0": "I", "1": "ii" },
  "correctness": { "0": true, "1": true },
  "score": { "correct": 2, "incorrect": 0, "unanswered": 2 },
  "page_num": 0,
  "submitted_at": "2026-04-14 10:23:45"
}
```

Returns `{}` (empty object) if no attempt exists.

---

## Frontend: `submitIdentificationAnswers`

New method on `ExerciseContext`:

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
      if (isCorrect) correct++; else incorrect++;
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
    exercise_num: parseInt(listEntry.id.split("/")[1]),
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

**Trigger points:**

1. **Submit button / auto-advance on page completion** — in `ExerciseContext.submitIdentPage()`, immediately after `this.submitExerciseReport()` and before `this.goToIdentPage()` or `this.triggerNextExercise()`. This ensures answers are saved before any navigation occurs:

```javascript
// Inside submitIdentPage, in the graded.result === CORRECT branch:
if (this.sealed != true) {
  this.submitExerciseReport();
  this.submitIdentificationAnswers({ is_page_submit: true });  // NEW — after report, before navigation
}
```

2. **Navigate away** — in `renderPristine` (music.js), as described in Bug Fix 2 above, before loading new data.

---

## Teacher View

### URL

```
GET /dashboard/courses/<course_id>/identification-answers/<int:student_id>/
```

Added to `apps/dashboard/urls.py`.

### View logic (`apps/dashboard/views/courses.py` or new `identification.py`)

```python
def identification_answers_view(request, course_id, student_id):
    course = get_object_or_404(Course, id=course_id)
    if request.user != course.authored_by:
        raise PermissionDenied
    student = get_object_or_404(User, id=student_id)

    attempts = IdentificationAttempt.objects.filter(
        user=student, course=course
    ).select_related("exercise").order_by("submitted_at")

    # Group by exercise, most recent first within each group
    from collections import defaultdict
    by_exercise = defaultdict(list)
    for attempt in attempts:
        by_exercise[attempt.exercise_id].append(attempt)

    # For each exercise, build display data: most recent attempt + history
    exercises_data = []
    for exercise_id, exercise_attempts in by_exercise.items():
        latest = exercise_attempts[-1]
        exercise = latest.exercise
        exercises_data.append({
            "exercise": exercise,
            "latest": latest,
            "history": exercise_attempts[:-1],
            # correct_answers stored in the attempt at submission time —
            # no need to re-parse the exercise definition
        })

    return render(request, "dashboard/identification-answers.html", {
        "course": course,
        "student": student,
        "exercises_data": exercises_data,
    })
```

### Template: `dashboard/identification-answers.html`

For each exercise: a table with columns **#**, **Correct Answer**, **Student Answer**, **Result** (✓/✗/–). Above the table: exercise title, score summary (e.g. "8 / 12 correct"), timestamp of latest attempt. Below the table: a `<details>` element containing the full attempt history (same table format, one per attempt).

A link to this view is added per student row in `course_activity_view` — only rendered when the course contains at least one identification exercise. Detection logic:

```python
PITCH_ANALYSIS_TYPES = {
    "note_name", "solfege", "do_based_solfege",
    "scale_degree", "fixed_do", "pitch_class",
    "interval_generic", "interval_specific",
    "roman", "figured_bass",  # all chorale_identification types
}

def course_has_identification_exercises(course):
    return course.exercise_set.filter(
        data__type="chorale_identification"
    ).exists()
```

This is a single DB query using the JSONField lookup `data__type`. If `data__type` is not indexed, it falls back to a Python-level check — acceptable for the teacher view which is not performance-critical.

---

## Data Flow

```
Student clicks popup choice
    → grader.setAnswer(absoluteIndex, choice)
    → render() (label goes dark in submit mode)

Student clicks Submit / page auto-advances
    → submitIdentPage({ fromUI: true / fromGrade: false })
        → submitExerciseReport()            [existing — timing/errors]
        → submitIdentificationAnswers({ is_page_submit: true })  [NEW]
        → goToIdentPage(next) or triggerNextExercise()

Student clicks Next Exercise (or prev)
    → renderPristine("next" / "previous")
        → scex.saveIdentState()             [NEW — writes to _identStateCache]
        → scex.submitIdentificationAnswers({ is_page_submit: false })  [NEW]
        → fetch new exercise definition
        → scex.restoreIdentState(newExerciseId)  [NEW — from cache or server]
        → render()

Teacher opens identification-answers view
    → query IdentificationAttempt for (student, course)
    → group by exercise, show most recent + history
```

---

## Files Touched

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_context.js` | Guard MIDI bindings; add `saveIdentState`, `restoreIdentState`, `_restoreIdentStateFromServer`, `submitIdentificationAnswers` |
| `lab/static/js/src/components/music.js` | Add save/restore hooks in `renderPristine` |
| `lab/static/js/src/components/music/exercise_sheet.js` | Call `submitIdentificationAnswers({ is_page_submit: true })` on page submit |
| `apps/exercises/models.py` | Add `IdentificationAttempt` model |
| `apps/exercises/migrations/XXXX_add_identification_attempt.py` | New migration |
| `apps/exercises/views.py` | Add `submit_identification_answers` (POST) and `get_identification_answers` (GET) views |
| `lab/urls.py` | Wire new AJAX endpoints |
| `apps/dashboard/views/courses.py` (or new `identification.py`) | Add `identification_answers_view` |
| `apps/dashboard/urls.py` | Add new URL pattern |
| `apps/dashboard/templates/dashboard/identification-answers.html` | New template |
| `apps/dashboard/templates/dashboard/course-activity.html` | Add per-student link to identification answers |

### Files NOT touched

- `apps/exercises/models.py` (`PerformanceData`) — no changes
- `lab/static/js/src/models/identification_grader.js` — used as-is; the `_restoring` flag is set externally on the grader instance by `_restoreIdentStateFromServer`, no changes to the grader class itself
- `lab/static/js/src/models/exercise_definition.js` — no changes

---

## Known Limitations

- The server-fallback restore (`_restoreIdentStateFromServer`) is async: the page renders blank for a brief moment before answers appear. This is acceptable since it only occurs after a hard page reload, not normal navigation.
- `IdentificationAttempt` has no unique constraint — multiple rows can exist for the same (user, exercise, course, page_num). This is intentional: all attempts are preserved. The teacher view always shows the latest by `submitted_at`.
- Correct answers are snapshotted at submission time in `correct_answers`. If an exercise is edited after attempts are saved, the teacher view will show the original correct answers that the student was tested against, not the new ones. This is the correct behaviour.
- The teacher view loads all attempts for a student in a course in a single query. For courses with many identification exercises, consider adding pagination or a date-range filter in a future version.
- The `_restoring` flag on the grader instance blocks input during async server restore. Any MIDI input during this window (unlikely but possible) is silently dropped. This is acceptable since identification exercises don't respond to MIDI anyway (Bug Fix 1).

---

## Out of Scope

- LTI / external LMS integration — separate project
- Showing identification answer detail in the existing `playlist_performance_view` — deferred
- Admin interface for `IdentificationAttempt` — deferred
- Aggregated class-level answer statistics (e.g. "60% of students chose ii for problem 3") — deferred
