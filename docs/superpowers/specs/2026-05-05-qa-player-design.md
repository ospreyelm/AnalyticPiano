# Q&A Player Design

**Date:** 2026-05-05
**Status:** Draft
**Author:** avnerdorman + Claude

## Purpose

Replace the broken symbolic meter exercise rendering path with a dedicated, lightweight Q&A player. The existing exercise shell (AMD/RequireJS, ExerciseContext, ChoraleGrader, MIDI wiring) was built for MIDI-driven chorale playback and extended incrementally to handle identification-mode exercises. Unit 2 symbolic meter questions stretch that extension past its natural limit — blank renders and broken navigation are symptoms of accidental complexity, not missing features.

This spec defines a clean, minimal Q&A player that handles any `umto_symbolic_meter` exercise (and future Q&A exercise types) without MIDI, without the chorale grader stack, and without the RequireJS module system.

## Scope

- Fix Unit 2 symbolic meter exercise rendering and navigation (immediate goal)
- Establish a reliable Q&A path reusable for future Q&A-type units
- Support both flashcard mode (one question at a time) and quiz mode (all questions, explicit submit)
- Wire results to the existing mastery/progress backend — no backend changes needed

## Non-Goals

- Replacing the existing MIDI/chorale/identification exercise shell for any other exercise type
- Building a general-purpose LMS quiz engine
- Spaced repetition scheduling
- Phase 2 notation-reading questions (those need a different renderer and are out of scope here)

## Architecture

### Routing: Template branch at Django level

Detection happens in the Django template layer, not in JavaScript. The existing `/s/units/N/play/` view already injects the exercise config into the page. Add a branch:

```
/s/units/2/play/?playlist=PA01DY&exercise_num=1
    ↓
Django view (existing, no changes to view logic)
    ├── exercise.type == "umto_symbolic_meter"
    │       → qa_player.html  → qa_player.js
    └── everything else
            → exercise.html   → existing AMD app (unchanged)
```

The new template extends the existing base (`lab/base.html`) and reuses the same header, navigation, and breadcrumb. The only difference is the content region: instead of `#staff-area` / `#staffwrapper` / piano / MIDI controls, it renders a single `<div id="qa-root"></div>` and bootstraps `qa_player.js`.

**Why this is safe:** the existing exercise shell is not touched. No risk of regression on any MIDI, chorale, or identification exercise.

### Data injection

Same injection point as today:

```html
<script>
  window.__EXERCISE_CONFIG__ = {{ exercise_config_json|safe }};
</script>
```

The `qa_player.js` reads `window.__EXERCISE_CONFIG__` on load. No XHR, no async data fetch — the problems are already in the page.

## Frontend Module: `qa_player.js`

**Location:** `lab/static/js/src/qa_player.js`

Single standalone ES module. No RequireJS, no AMD, no external framework. Approximately 250 lines.

### State

Plain immutable-style state object, recreated on each update and passed to render:

```javascript
{
  exerciseId: string,          // from config.id
  problems: Problem[],         // from config.problems
  mode: "flashcard" | "quiz",  // from config.inputMode, default "flashcard"
  answers: { [index]: string },// user's selected answers
  revealed: { [index]: bool }, // flashcard: which problems have been graded
  page: number,                // flashcard: current problem index (0-based)
  submitted: boolean,          // quiz: true after explicit submit
  nextExerciseUrl: string|null // from config.nextExercise
}
```

### Render

Two render functions share a root container (`#qa-root`):

```
renderFlashcard(state, dispatch) → DOM
renderQuiz(state, dispatch)      → DOM
```

Both are full re-renders into `#qa-root` (innerHTML replacement). No virtual DOM, no diffing — the content is small enough that full re-render is instant and correct.

### Dispatch

Single `dispatch(action)` function updates state and calls render:

```javascript
dispatch({ type: "SELECT_ANSWER", index: 0, answer: "triple" })
dispatch({ type: "SUBMIT_QUIZ" })
dispatch({ type: "NEXT_PAGE" })
dispatch({ type: "RESTORE", savedState: {...} })
```

### Flashcard mode behavior

- Shows one problem at a time.
- User clicks a choice → answer recorded, problem graded immediately.
  - Correct: brief green highlight, auto-advance after 800ms.
  - Incorrect: red highlight on chosen answer, correct answer shown, "Next" button appears (no auto-advance on wrong).
- Progress indicator: "3 / 10" top-right of card.
- Last problem correct → save results → redirect to `nextExerciseUrl`.

### Quiz mode behavior

- Shows all problems as a scrollable list of cards.
- User can answer in any order.
- "Submit" button (fixed/sticky bottom) enabled only when all problems answered.
- After submit: inline correct/incorrect feedback on each card. "Next Exercise" button appears.
- Clicking "Next Exercise" → save results → redirect to `nextExerciseUrl`.

### Answer checking

Pure function, no side effects:

```javascript
function checkAnswer(problem, chosen) {
  return chosen === problem.answer;
}
```

### Prompt rendering

Reuses `SymbolicMeterRenderingLogic` (already at `lab/static/js/src/models/symbolic_meter_rendering_logic.js`) for time signature display. Import directly as an ES module (the existing file uses AMD `define` — either convert it to ES module export, or inline the ~30-line logic into `qa_player.js` to avoid the AMD dependency).

For `prompt.kind === "time_signature"`: render stacked numerals with the existing music font CSS classes.
For `prompt.kind === "meter_label"`: render as plain styled text (e.g. "compound duple").

### Persistence

On each answer selection, save state to localStorage:

```javascript
localStorage.setItem(`qa:${exerciseId}`, JSON.stringify({ answers, page, submitted }));
```

On page load, restore if key exists and is less than 7 days old. If exercise is already complete in saved state, redirect immediately to `nextExerciseUrl`.

### AJAX save (mastery wiring)

On exercise completion, POST to the existing endpoint:

```
POST /ajax/identification-answers/
```

Payload shape (matches what the existing system sends):

```javascript
{
  course_ID: config.courseId,
  playlist_ID: config.playlistId,
  exercise_num: config.exerciseNum,
  answers: { 0: "triple", 1: "compound", ... },
  correctness: { 0: true, 1: false, ... },
  score: {
    correct: N,
    incorrect: M,
    unanswered: 0
  },
  correct_answers: { 0: "triple", 1: "compound", ... },
  page_num: 0,
  is_page_submit: false,
  mode: "flashcard" | "quiz",
  attempt_type: "practice"
}
```

For mastery: `score.incorrect === 0 && score.unanswered === 0` → `correct = true` in `record_attempt()`. No backend changes required.

## Django Template: `qa_player.html`

**Location:** `lab/templates/lab/qa_player.html`

Extends `lab/base.html` (same base as `exercise.html`). Replaces the exercise content region only:

```html
{% extends "lab/base.html" %}
{% block content %}
<div id="qa-root"></div>
<script>
  window.__EXERCISE_CONFIG__ = {{ exercise_config_json|safe }};
</script>
<script type="module" src="{% static 'js/src/qa_player.js' %}"></script>
{% endblock %}
```

No piano container, no `#staffwrapper`, no MIDI script tags.

## CSS

New block in `harmony.css` (or `qa_player.css` if preferred). Approximately 80 lines.

### Flashcard layout

```
#qa-root
  .qa-flashcard
    .qa-progress          ("3 / 10", top-right)
    .qa-card
      .qa-prompt          (time signature or meter label, centered, min-height 80px)
      .qa-choices         (2-column grid, gap 12px)
        .qa-choice        (button, border 2px solid #ddd, border-radius 8px)
        .qa-choice.selected   (border-color #3b82f6)
        .qa-choice.correct    (background #dcfce7, border-color #16a34a)
        .qa-choice.incorrect  (background #fee2e2, border-color #dc2626)
    .qa-feedback          (hidden until answered)
    .qa-next-btn          (hidden until incorrect answer shown)
```

### Quiz layout

```
#qa-root
  .qa-quiz
    .qa-card (× N)        (same card anatomy as flashcard)
    .qa-submit-bar        (sticky bottom, full-width)
      .qa-submit-btn      (disabled until all answered)
  .qa-results-bar         (appears after submit)
    .qa-next-exercise-btn
```

### Shared

Reuse existing `.symbolic-meter-prompt` CSS classes for time signature display (already in `harmony.css`). Do not duplicate.

## Files Changed

| File | Action |
|------|--------|
| `lab/static/js/src/qa_player.js` | Create |
| `lab/templates/lab/qa_player.html` | Create |
| `lab/static/css/harmony.css` | Add Q&A layout CSS block |
| `lab/views.py` (exercise view, ~line 579) | Add template branch for `umto_symbolic_meter` |

No changes to:
- `exercise.js`, `exercise_context.js`, `exercise_definition.js` — existing shell untouched
- `symbolic_question_sheet.js` — can be deleted after new player is verified, or left in place
- Any backend/mastery code

## Mastery Integration

The mastery system consumes only:
- `correct` boolean (derived from `score.incorrect === 0`)
- `exercise.skill_tags` (already set on the UMTO exercise row at creation time)

Both are already handled by the existing `/ajax/identification-answers/` endpoint. The Q&A player's AJAX save payload is shape-compatible with what the endpoint expects. No backend work required.

## Mode Selection

`inputMode` field in the exercise config selects the mode:

- `"flashcard"` (default) → flashcard mode
- `"quiz"` → quiz mode

The existing `unit2_symbolic_drill_manifest.json` does not set `inputMode`, so all current exercises default to flashcard. Quiz mode can be enabled per-exercise or per-playlist by setting `inputMode: "quiz"` in the UMTO data at generation time.

## Future Q&A Exercise Types

Any future exercise type that:
- Has `problems[]` array with `prompt`, `choices`, `answer`
- Does not require MIDI input or notation rendering
- Uses `type: "umto_qa_*"` naming convention

...can be routed through the same `qa_player.html` + `qa_player.js` with no changes. The template branch in the Django view should match a prefix (`umto_symbolic_meter` now, or a broader `isQAType()` check later).

## Open Questions

None blocking implementation. The following are deferred decisions:

1. **`SymbolicMeterRenderingLogic` AMD→ES module conversion:** safest approach is to inline the ~30 lines directly into `qa_player.js` for now, avoiding the AMD dependency entirely. Can be extracted to a shared ES module later.
2. **`qa_player.css` vs `harmony.css`:** either works. Separate file is cleaner but requires a new `<link>` tag in the template.
3. **Score card / completion overlay:** the existing `ExerciseScoreCard` is an AMD component. The Q&A player should implement its own simple completion state (green banner or inline "Well done!" text) rather than reusing it.
