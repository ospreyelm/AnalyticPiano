---
title: "SPA URL-parameter pinning via in-place render + history.replaceState, not server {redirect}"
date: 2026-07-07
category: docs/solutions/design-patterns
module: student-player
problem_type: design_pattern
component: service_object
severity: medium
applies_when:
  - "An AJAX endpoint returns a JSON {redirect} whose only purpose is to pin a URL parameter to a server-derived value"
  - "The redirect target is the same route with a different query/path parameter (not a genuine route change)"
  - "The client consuming the redirect is an SPA that would lose state on a full reload"
resolution_type: code_fix
tags: [spa-navigation, history-replacestate, redirect-pin, player, exercise-num, ajax]
---

# SPA URL-parameter pinning via in-place render + history.replaceState, not server {redirect}

## Context

The student player (`/s/units/<unit>/play/?playlist=<id>&exercise_num=<n>`) decouples `exercise_num` from the URL: the backend derives the served slot from DB history ("Navigation Pinning") so the URL always reflects the exercise actually being served. When a requested `exercise_num` didn't match the derived slot, `PlayerDefinitionView` returned `{"redirect": "...&exercise_num=<derived>"}` and the client did `window.location.href = data.redirect`.

That hard navigation destroyed the SPA: every advance that needed re-pinning — most visibly the auto-advance after the score card (`triggerNextExercise` → `goToNextExercise` → `NEXTEXERCISE` → `renderPristine("next")` → `loadDefinition`), and almost every advance on adaptive/dynamic playlists (where `resolve_adaptive_step` pins whenever requested_num ≠ derived slot, by design) — degraded into a full page reload.

A long-postponed TODO at `lab/static/js/src/components/music.js` already sketched the fix ("URL changes dynamically with exercise without refreshing") but was gated on `!window.PLAYER_DEFINITION_URL`, so it never ran for the student player.

## Guidance

When a JSON endpoint's redirect exists only to pin a URL parameter to a server-derived value (same route, different param), **do not redirect**. Serve the resolved resource's content in place and return the pinned URL as a field the client applies with `history.replaceState`.

Server (`apps/student/views.py`, `PlayerDefinitionView`):
```python
# Before: hard redirect, forces a full reload on the SPA client.
if state.should_redirect:
    return JsonResponse({"redirect": reverse(...) + f"?playlist=...&exercise_num={state.exercise_num}"})

# After: serve the derived-slot exercise in place + expose the pinned URL.
pinned_url = (
    reverse("student:player", kwargs={"unit_num": unit_num})
    + f"?playlist={playlist.id}&exercise_num={state.exercise_num}"
)
# ... build exercise_context for state.exercise_num ...
exercise_context["pinnedUrl"] = pinned_url
return JsonResponse(exercise_context)
```

Client (`lab/static/js/src/components/music.js`, `renderPristine` after `loadDefinition`):
```javascript
if (!!newData?.exerciseNum && window.PLAYER_DEFINITION_URL && newData.pinnedUrl) {
  if (newData.pinnedUrl !== window.location.pathname + window.location.search) {
    window.history.replaceState(null, "", newData.pinnedUrl);
  }
} else if (!!newData?.exerciseNum && !window.PLAYER_DEFINITION_URL) {
  // legacy /exercise/<id>/ path-based URL sync, unchanged
}
```

Keep a hard `{redirect}` only for **genuine route changes** (here: end-of-playlist / no-exercise → unit page), where a full navigation is the intended behavior. Keep the document-load 302 on the page view (`PlayerView`) for fresh URL loads and refresh-stability.

## Why This Matters

The pin-redirect pattern is correct about *what* the URL should be; it's wrong about *how* to get there. Executing a URL correction as `window.location.href` throws away the SPA — state, audio context, scroll position, and the in-progress render — and pays a full page load. `history.replaceState` corrects the URL without any of that cost, and serving the derived content in place lets the SPA render it directly.

The bug was silent for clean linear progression (next = next_pending, no redirect) and loud for adaptive playlists and skip-ahead/review jumps — exactly the "often not triggered, but when it is, refresh" symptom users reported.

## When to Apply

- Any AJAX endpoint returning `{redirect}` for a **same-route URL-parameter pin** consumed by an SPA client.
- Any place a server "fixes" a client-supplied URL parameter by redirecting to the canonical value, where the client could instead render the canonical resource in place.
- Does NOT apply to genuine route changes (different page) or non-SPA clients where a full reload is acceptable.

## Examples

Before (adaptive playlist, every advance reloaded):
```
click Next → loadDefinition(num=3) → 200 {"redirect": "...&exercise_num=1"} → window.location.href → full reload
```

After (in-place, no reload):
```
click Next → loadDefinition(num=3) → 200 {"exerciseNum":1, "pinnedUrl":"...&exercise_num=1", ...} → render slot 1 + history.replaceState
```

Verified locally: clicking Next fires the definition AJAX (13KB context), no second top-level document GET, URL pinned via `replaceState`. Regression test: `apps/student/tests/test_player_views.py::test_player_definition_serves_pinned_slot_in_place_for_skipped_step` asserts no `redirect` field, `exerciseNum` = derived slot, `pinnedUrl` present.

## Related

- PR #237 — the fix this learning captures.
- `docs/...` memory `project_adaptive_re_serve_loop.md` — the documented-but-unfixed adaptive re-serve / Navigation Pinning area this fix partially addresses (the reload symptom; the re-serve-same-exercise behavior is separate).
- Files: `apps/student/views.py` (`PlayerDefinitionView`), `lab/static/js/src/components/music.js` (`renderPristine` / `loadDefinition`), `apps/student/player_progression.py` (`resolve_requested_step`, `resolve_adaptive_step`).