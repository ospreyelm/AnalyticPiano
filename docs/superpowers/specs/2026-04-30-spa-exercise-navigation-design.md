# SPA-Like Exercise Navigation Design

**Date:** 2026-04-30  
**Status:** Approved  
**Branch:** student player

---

## Problem

Student player does a full page reload on every next/previous exercise transition. `PlayerView` sets `exercise_context["forceRedirect"] = True`, which causes JS to do `window.location.href = ...` instead of using the existing AJAX path. The AJAX infrastructure already exists in `music.js` but uses `playlist_name` + `exercise_id` params that don't match the student player's `playlist_id` + `exercise_num` scheme.

---

## Goal

Next/previous/retry transitions in the student player feel instant — no full page reload. URL stays fixed at the initial exercise (no `history.pushState`). Deep-linking and back/forward work via the existing full-page load path.

---

## Approach: Extract context builder, add JSON endpoint

Pull `PlayerView.get()`'s body into a shared function. `PlayerView` calls it and renders the template. A new `PlayerDefinitionView` calls it and returns JSON. JS sends AJAX requests to the new endpoint instead of doing `window.location.href`.

---

## Backend

### `build_player_exercise_context(request, unit_num, playlist, exercise_num)`

Extract from `PlayerView.get()` into a module-level function in `apps/student/views.py`.

Returns either:
- A `dict` — the full exercise context (same fields currently embedded in the page)
- An `HttpResponseRedirect` — when `resolve_requested_step` returns `should_redirect=True`

Add two new fields to the returned dict:
- `totalExercises` (integer) — `playlist.exercise_count`
- `playlistId` (string) — `playlist.id` — needed by JS to construct AJAX params

The `unit:1` tag validation currently in `PlayerView.get()` must be preserved inside `build_player_exercise_context` (raise `Http404` if tag absent), so `PlayerDefinitionView` also enforces it.

### `PlayerView` (unchanged behavior)

Calls `build_player_exercise_context`. If result is a redirect, returns it. Otherwise renders `student/player.html` with the context. Remove `exercise_context["forceRedirect"] = True`.

### `PlayerDefinitionView` (new)

```python
class PlayerDefinitionView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        exercise_num = int(request.GET.get("exercise_num", 1))
        playlist = get_object_or_404(Playlist, id=playlist_id)
        result = build_player_exercise_context(request, unit_num, playlist, exercise_num)
        if isinstance(result, HttpResponseRedirect):
            return JsonResponse({"redirect": result.url})
        return JsonResponse(result)
```

### New URL

```python
# apps/student/urls.py
path("units/<int:unit_num>/play/definition/", PlayerDefinitionView.as_view(), name="player-definition")
```

---

## Frontend

### Embed endpoint URL + unit_num in player.html

Add to `player.html` template (small script block):

```html
<script>
  window.PLAYER_DEFINITION_URL = "{% url 'student:player-definition' unit_num=unit_num %}";
</script>
```

### Remove forceRedirect

With `forceRedirect` gone from the context, `music.js` falls through to the AJAX branch for next/prev automatically. No JS flag removal needed — the branch is already `if (forceRedirect) redirect; else ajax`.

### Fix param mismatch in music.js

All four AJAX calls in `music.js` (reload, next, previous, first) currently send:
```javascript
url: "definition",
data: { playlist_name: ..., exercise_id: ..., exercise_num: ... }
```

Change to:
```javascript
url: window.PLAYER_DEFINITION_URL,
data: { playlist: setdef.settings.definition.playlistId, exercise_num: ... }
```

`playlistId` must be present in the exercise context dict. Currently `playlistId` is not explicitly set — add it in `build_player_exercise_context` (it's `playlist.id`).

The `exercise_num` for each action:
- `reload`: `setdef.settings.definition.exerciseNum`
- `next`: `setdef.settings.definition.nextExerciseNum`
- `previous`: `setdef.settings.definition.previousExerciseNum`
- `first`: `1`

### Redirect handling

After each AJAX success callback, check:
```javascript
if (data.redirect) {
  window.location.href = data.redirect;
  return;
}
```

This covers the rare case where progression enforcement rejects the requested step.

### No URL update

URL stays fixed at the initial page load URL. No `history.pushState`. Deep-linking works via the full-page load path (`PlayerView`).

### Header counter update

`player.html` currently polls `#exercise-info` via `setInterval` to update `#js-player-current` / `#js-player-total`. After each AJAX load, update directly:

```javascript
var cur = document.getElementById('js-player-current');
var tot = document.getElementById('js-player-total');
if (cur) cur.textContent = newData.exerciseNum;
if (tot && newData.totalExercises) tot.textContent = newData.totalExercises;
```

The `setInterval` polling can be removed once this is in place.

### Hint banner updates

`is_review_mode` and `disable_computer_keyboard_input` banners are rendered server-side at page load. After AJAX transitions they must update from `newData`:

- `newData.reviewMode` → show/hide `.s-player-input-hint` review banner
- `newData.disableComputerKeyboardInput` → show/hide MIDI-only banner

Add a `refreshPlayerBanners(newData)` helper in `player.html`'s script block. Called after each successful AJAX load in `music.js`.

### Chorale grader reset

The existing AJAX transition code in `music.js` (lines ~317-350) updates `scex.definition` and `scex.settings.definition` with the new data. Verify that `exercise_sheet.js` re-calls `grader.initFromDefinition(definition)` when the definition changes — if not, call it explicitly after updating the definition object. If the chorale grader is not active for the new exercise, this is a no-op.

### Retry (Reset)

`exercise_score_card.js` line 356: replace `window.location.reload()` with a broadcast or direct call that triggers the `exerciseAction === "reload"` path in `music.js`. The reload AJAX path already exists and fetches the same exercise. With the param fix above it will use the new endpoint.

Simplest implementation: `exercise_score_card.js` fires `EVENTS.BROADCAST.RELOAD` (add this event constant), `music.js` listens and calls `onExerciseAction("reload")`.

---

## Testing

### Backend unit tests

- `build_player_exercise_context` — progression redirect case, review mode, normal progression
- `PlayerDefinitionView` — returns JSON with correct fields; returns `{"redirect": url}` when progression guard fires
- Existing `test_player_progression.py` unchanged

### Manual test checklist

- [ ] Next/prev through playlist — no page reload, exercise updates
- [ ] Retry (Reset) — same exercise reloads via AJAX, no page reload
- [ ] Review mode banner updates on transition between review and progression exercises
- [ ] `disable_computer_keyboard_input` banner updates on transition
- [ ] Header counter (`1/12`) updates correctly on each transition
- [ ] Chorale exercise: grader resets correctly on AJAX transition
- [ ] Identification exercise: answers saved before navigate, fresh state on new exercise
- [ ] End of playlist (no next): no crash, Next button inert
- [ ] Start of playlist (no prev): no crash, Previous button inert
- [ ] Progression guard: requesting skipped exercise via raw URL → full redirect still works
- [ ] Lab playlist view (non-student player) unaffected

---

## Files changed

| File | Change |
|------|--------|
| `apps/student/views.py` | Extract `build_player_exercise_context`; remove `forceRedirect`; add `PlayerDefinitionView` |
| `apps/student/urls.py` | Add `player-definition` URL |
| `apps/student/templates/student/player.html` | Embed `PLAYER_DEFINITION_URL`; add `refreshPlayerBanners`; update counter logic |
| `lab/static/js/src/components/music.js` | Fix AJAX params (url + playlist_id + exercise_num); add redirect handling |
| `lab/static/js/src/components/exercise_score_card.js` | Replace `window.location.reload()` with broadcast |
| `lab/static/js/src/models/exercise_context.js` | Add `RELOAD` event constant (if not present) |
