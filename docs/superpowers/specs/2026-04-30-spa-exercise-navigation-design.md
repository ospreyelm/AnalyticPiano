# Minimal SPA Exercise Navigation for Student Player

**Date:** 2026-04-30  
**Status:** Revised / Minimal Scope  
**Branch:** student player

---

## Problem

The student player does a full page reload on next/previous/retry because `PlayerView` forces redirect behavior by setting `exercise_context["forceRedirect"] = True`.

The lab already has client-side exercise replacement logic in `music.js`. That logic does **not** need to be rebuilt. What is missing in the student player is a compatible JSON endpoint and a small amount of student-specific state refresh after the AJAX load.

---

## What We Can Reuse

### Reuse as-is

- `generate_exercise_context()` in `lab/views.py` already builds the core exercise payload the frontend expects.
- `music.js` already knows how to fetch a new definition and swap the active exercise without a full page reload.
- Existing exercise-sheet / grader reset behavior is already mostly in place and should continue to work after AJAX transitions.

### Student-specific additions that must remain

The student player adds behavior that the lab does not have:

- progression / review gating via `resolve_requested_step()`
- student-specific next / previous rules in review mode
- unit membership validation
- student-only banners and header state in `player.html`

So the right approach is:

- keep the existing lab-side AJAX replacement mechanism
- add a **student** definition endpoint that returns the same payload shape, but with student progression logic applied

---

## Non-Goal

Do **not** refactor the lab navigation system or preserve the old student full-reload behavior.

Do **not** extract a large shared `build_player_exercise_context()` helper unless it becomes necessary during implementation. That is optional cleanup, not part of the minimum change.

Do **not** treat this as an `exercise_id` vs `exercise_num` migration project. The existing playlist refresh flow already navigates primarily by `exercise_num`.

---

## Minimal Backend Change

### Add `PlayerDefinitionView`

Add a new JSON endpoint in `apps/student/views.py` that:

1. Reads `playlist` and `exercise_num` from query params.
2. Loads the playlist.
3. Enforces the same unit validation currently done in `PlayerView`.
4. Applies `resolve_requested_step()`.
5. If progression rules reject the requested step, returns:

```json
{ "redirect": "/student/units/1/play/?playlist=...&exercise_num=..." }
```

6. Otherwise builds the same exercise context currently produced by `PlayerView`, including:
   - `reviewMode`
   - `playerMode`
   - `reviewAnswers` when applicable
   - student-specific `nextExercise`, `nextExerciseNum`, `nextExerciseId`
   - student-specific `previousExercise`, `previousExerciseNum`, `previousExerciseId`
   - `disableComputerKeyboardInput`
7. Adds:
   - `playlistId`
   - `totalExercises`
8. Returns `JsonResponse(exercise_context)`.

### Keep `PlayerView`, but simplify it

`PlayerView` should continue rendering the initial full page load for deep links and back/forward behavior.

Minimum behavioral changes:

- stop setting `forceRedirect = True`
- add `playlistId` and `totalExercises` to the embedded definition payload
- keep all existing student progression/review logic for the initial render

### URL

Add:

```python
path("units/<int:unit_num>/play/definition/", PlayerDefinitionView.as_view(), name="player-definition")
```

---

## Minimal Frontend Change

### 1. Point AJAX reloads to the student endpoint

In `player.html`, expose the endpoint:

```html
<script>
  window.PLAYER_DEFINITION_URL = "{% url 'student:player-definition' unit_num=unit_num %}";
</script>
```

In `lab/static/js/src/components/music.js`, keep the existing AJAX replacement flow but change the request target and params for student player loads:

- URL: `window.PLAYER_DEFINITION_URL`
- params:

```javascript
data: {
  playlist: setdef.settings.definition.playlistId,
  exercise_num: targetExerciseNum,
}
```

The current `playlist_name` / `exercise_id` values should not be used for the student player endpoint.

### 2. Remove redirect-only branching for student navigation

Once `forceRedirect` is no longer injected by `PlayerView`, next/previous/reload can use the existing AJAX branch.

Add redirect handling for guarded cases:

```javascript
if (data.redirect) {
  window.location.href = data.redirect;
  return;
}
```

### 3. Do not update browser history

Keep the existing page URL fixed. No `pushState` or `replaceState` for student transitions.

The current history rewrite block in `music.js` should be disabled or bypassed for student-player AJAX transitions.

### 4. Update student-only shell state after AJAX load

After a successful AJAX transition, refresh the parts of `player.html` that are currently only correct on first render:

- header counter: `exerciseNum` / `totalExercises`
- review-mode hint banner
- MIDI-only / keyboard-disabled banner

A small helper in `player.html` is enough, e.g. `window.refreshPlayerChrome(newData)`.

### 5. Retry should use the same AJAX path

In `exercise_score_card.js`, replace `window.location.reload()` with the same internal reload path used elsewhere so retry reloads the same exercise without a full page refresh.

This can be done with a small broadcast event or a direct call into the existing reload behavior.

---

## Why This Is the Minimum

This keeps the existing exercise runtime intact and only replaces the missing integration points for the student player:

- a student-compatible definition endpoint
- removal of forced full redirects
- student shell refresh after definition swaps
- retry using AJAX instead of hard reload

Everything else in the earlier spec is optional cleanup.

---

## Optional Cleanup (Not Required for MVP)

These are reasonable follow-ups, but they should not block the first implementation:

- extract shared `PlayerView` context assembly into a helper
- unify lab and student definition endpoints behind a shared backend builder
- remove remaining assumptions in `music.js` that every environment has a relative `definition` URL
- split student-specific chrome refresh into a dedicated JS module

---

## Testing

### Backend

- `PlayerDefinitionView` returns JSON for a valid current step
- `PlayerDefinitionView` returns `{ "redirect": url }` when progression guard rejects the request
- `PlayerDefinitionView` includes `playlistId` and `totalExercises`
- existing student progression tests for initial page loads remain green

### Manual

- next / previous transitions update the exercise without full page reload
- retry reloads the current exercise without full page reload
- review-mode banner updates correctly between exercises
- keyboard-disabled banner updates correctly between exercises
- header counter updates correctly
- chorale exercise resets correctly on AJAX transition
- identification exercise saves state before navigation and restores correct new state after load
- direct deep link still works through the full page render path

---

## Files Changed

| File | Change |
|------|--------|
| `apps/student/views.py` | Add `PlayerDefinitionView`; stop forcing redirect-only navigation in `PlayerView`; include `playlistId` and `totalExercises` |
| `apps/student/urls.py` | Add `player-definition` route |
| `apps/student/templates/student/player.html` | Expose definition endpoint URL and add helper to refresh student-specific chrome |
| `lab/static/js/src/components/music.js` | Reuse existing AJAX swap flow, but target student endpoint, handle redirect payloads, and skip history rewrite for student player |
| `lab/static/js/src/components/exercise_score_card.js` | Retry via AJAX reload path instead of `window.location.reload()` |
