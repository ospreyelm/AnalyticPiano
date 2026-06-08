# Teacher Play Route — Design Spec (2026-06-07)

Backlog issue #1 of the chordal-UMTO backlog
(`docs/superpowers/plans/2026-06-07-chordal-umto-backlog.md`). Gates issue #2
(play view "Save as exercise" → UMTO).

## Problem

The legacy play view (`lab.views.PlayView`, the chord-pedal authoring surface and
the eventual chordal-UMTO save target) is unreachable. Clicking the "New Play
View" nav link leaves the user on the dashboard with no JS error; `/play/`
returns 200-then-302 server-side.

### Root cause (confirmed, no bisect needed)

Commit `e58a2fc7` (2026-04-26, "fix: route legacy / and /play paths to student
surface") added a **project-level** redirect in `harmony/urls.py`:

```python
path("", RedirectView.as_view(url="/s/"), name="root-redirect"),
path("play/", RedirectView.as_view(url="/s/"), name="play-redirect"),   # ← line 17
...
path("", include(lab.urls)),   # ← line 23, lab patterns live here
```

Django matches URL patterns top-down. `/play/` matches `play-redirect` (line 17)
**before** the `lab.urls` include (line 23) is ever consulted, so the request
302s to the student surface `/s/` and `PlayView` never runs.

`lab/urls.py` names **both** lab patterns `index`:

```python
path("", RedirectView.as_view(url="/play"), name="index"),
path("play/", PlayView.as_view(), name="index"),
```

`reverse("lab:index")` resolves to the last match → `/play/`. Every consumer of
`lab:index` therefore funnels into the dead `play-redirect`:

| Consumer | File | Effect |
|---|---|---|
| "New Play View" nav link | `lab/templates/_header.html:16` | → /play/ → /s/ (the reported symptom) |
| "Play View" dashboard link | `apps/dashboard/templates/dashboard/base.html:25` | → /play/ → /s/ |
| "Back to Dashboard" link | `lab/templates/skill_map.html:82` | → /play/ → /s/ |
| Post-login redirect | `apps/accounts/views.py:25` (`reverse_lazy("lab:index")`) | → /play/ → /s/ |

This is a deliberate-redirect side effect from `e58a2fc7`. It predates and is
unrelated to the chordal-UMTO work.

## Decisions

1. **`/s/` stays the student front door.** Do not touch the `/`→/s/ or
   `/play/`→/s/ project-level redirects. Old bookmarks and the login flow keep
   landing on the student surface.
2. **Legacy play view becomes a teacher tool at its own URL: `/teacher/play/`.**
   `/teacher/` is the intended future home for the entire dashboard; today's
   scope only puts PlayView there. No other surface moves.
3. **Minimal blast radius.** Retarget only the two teacher-facing nav links.
   Leave login redirect, skill_map back link, and the commented PlayView context
   untouched.
4. **No auth gate (parity).** PlayView stays ungated, matching the old `/play/`
   behavior. Auth/role gating is deferred to the future `/teacher/` dashboard
   migration.

## Changes

### 1. `lab/urls.py` — add a distinct teacher route + name

Add (existing `index` patterns stay as redirect anchors — not removed, to limit
blast radius):

```python
path("teacher/play/", PlayView.as_view(), name="play"),
```

- `reverse("lab:play")` → `/teacher/play/`.
- Reached via the `lab.urls` include (harmony/urls.py:23); no project-level
  `/teacher/` redirect exists to shadow it.

### 2. `lab/templates/_header.html:16` — retarget "New Play View"

```diff
-<li><a href="{% if home_url %}{{ home_url }}{% else %}{% url 'lab:index' %}{% endif %}">New Play View</a></li>
+<li><a href="{% if home_url %}{{ home_url }}{% else %}{% url 'lab:play' %}{% endif %}">New Play View</a></li>
```

### 3. `apps/dashboard/templates/dashboard/base.html:25` — retarget "Play View"

```diff
-<a href="{% if home_url %}{{ home_url }}{% else %}{% url 'lab:index' %}{% endif %}">Play View</a>
+<a href="{% if home_url %}{{ home_url }}{% else %}{% url 'lab:play' %}{% endif %}">Play View</a>
```

## Explicitly NOT changing

- `harmony/urls.py` project-level `/`→/s/ and `/play/`→/s/ redirects.
- `apps/accounts/views.py` post-login redirect (`lab:index`, lands /s/ — intended).
- `lab/templates/skill_map.html:82` back link.
- `lab/urls.py` existing `index` patterns.
- `lab/views.py` PlayView (no context changes, no auth gate).

## Verification

- `reverse("lab:play")` returns `/teacher/play/`.
- GET `/teacher/play/` (authenticated) returns 200 and renders `play.html` (the
  RequireJS play app `app/components/app/play`) — does **not** 302 to `/s/`.
- "New Play View" (header) and "Play View" (dashboard) links navigate to the
  play app, not the dashboard.
- `/play/` and `/` still redirect to `/s/` (unchanged front door).
- No new auth behavior: anonymous GET `/teacher/play/` behaves as before for
  the old `/play/` route.

## Future / out of scope

- Migrating the whole dashboard under `/teacher/` (and adding proper
  login/role gating there).
- Issue #2: the play view "Save as exercise" path emitting a chordal UMTO
  exercise — depends on this fix landing first.
