# Student Progress Dashboard, Built Toward LTI — Design Spec

**Date:** 2026-07-02
**Status:** Draft — awaiting product owner review, not authorized for implementation
**Feature scope:** Student-facing aggregate progress view + the LTI groundwork it depends on.

---

## What exists today vs. what's being asked for

Today a student has:
- `/s/` home — course panels + curriculum browser
  (`apps/student/views.py` `HomeView`, `student/home.html`).
- `/s/courses/<pk>/` — one course's assignment list with per-playlist
  progress (`CourseDetailView`,
  `docs/superpowers/specs/2026-06-14-student-course-experience-design.md`).
- `/s/units/<unit_n>/` — one unit's skill-grouped mastery view
  (`UnitProgressView`, `2026-04-25-student-progress-tracking-design.md`).

There is **no single page showing a student's progress across all courses**
— that was explicitly deferred as future phase in the 2026-04-25 spec.
There is **no LTI code anywhere in the repo** (verified: zero matches for
"LTI", "lti1p3", "pylti", "IMS", "outcome service", "grade passback",
"LineItem" repo-wide).

This spec treats those as one problem: if a "student dashboard" is going to
be launched from an LMS (Canvas, Moodle, etc.) via LTI, its data shape and
auth model need to be decided now, because retrofitting LTI onto a
dashboard built only for direct HarmonyLab login typically means reworking
identity resolution and iframe/cookie behavior after the fact.

---

## Part A — LTI groundwork (prerequisite, decide first)

### Why this has to come before the dashboard, not after

1. **Identity.** An LTI launch arrives with an `sub` claim (opaque per-platform
   user id) and a `deployment_id`, not a HarmonyLab username/password. The
   dashboard's URL and auth decorators need to already assume "a request may
   arrive pre-authenticated via LTI launch, not just Django session login"
   or every view built in Part B has to be revisited.
2. **Framing.** LTI launches typically render HarmonyLab inside an iframe on
   the LMS's domain. That requires `SameSite=None; Secure` session cookies
   and a `Content-Security-Policy: frame-ancestors` allowlist instead of
   the default same-origin framing posture — a global settings change, not
   a per-view one.
3. **Grading passback direction.** LTI Advantage's Assignment and Grade
   Services (AGS) push grades **from tool to platform** (HarmonyLab →
   Canvas gradebook), keyed by a `LineItem` resource per assignment. Which
   HarmonyLab entity maps to a "LineItem" (a `Course`? a `PlaylistCourseOrdered`
   row?) has to be decided before the dashboard's progress-percent
   computation is wired to anything gradable.

### Recommended approach: use `pylti1p3`, don't hand-roll the protocol

Per AGENTS.md's "use existing package before writing new code" rule, and
because LTI 1.3 involves OIDC third-party login, JWT-signed launches, JWKS
key rotation, and the AGS/NRPS/Deep-Linking sub-services — this is exactly
the kind of protocol surface that should not be reimplemented.
[`pylti1p3`](https://github.com/dmitry-viskov/pylti1p3) is the standard
Python library (Django-compatible, framework helpers included) and is the
one most existing Django LTI integrations use.

### New app: `apps/lti` (new, isolated)

```
apps/lti/
  models.py       # LtiPlatform (issuer, client_id, deployment_ids, JWKS URL,
                   #   auth/token endpoints — one row per LMS instance a
                   #   teacher connects), LtiUserLink (user FK, platform FK,
                   #   sub, unique_together) , LtiLineItem (maps a
                   #   PlaylistCourseOrdered -> platform line item id)
  views.py        # OIDC login init, launch (POST from platform), JWKS endpoint
  urls.py         # /lti/login/, /lti/launch/, /lti/jwks/
  services.py     # grade passback: given a PCO + user + score, POST an AGS
                   # result to the platform's line item
```

This does **not** touch `lab/views.py` (forbidden by AGENTS.md), does not
touch playlist/assignment models beyond adding the mapping table above, and
does not require the Assignment Slot Foundation work that is currently
not authorized — `LtiLineItem` maps onto the *existing* `PlaylistCourseOrdered`
row, nothing new on the assignment side.

### Identity resolution

On launch: look up `LtiUserLink` by `(platform, sub)`.
- If found → log in as the linked Django `User`.
- If not found → the platform's launch claims typically include
  `email`/`name`. Match-or-create a `User` (mirroring however the app
  already handles first-login provisioning, if any — needs a lookup at
  implementation time; not yet confirmed in this pass) and create the
  `LtiUserLink`.
- Role claim (`https://purl.imsglobal.org/spec/lti/claim/roles`) maps
  Instructor → teacher-side landing, Learner → student-side landing. This
  determines whether the launch redirects into `/s/...` or `/teacher/...`
  (Part C of the teacher dashboard spec) — **not** a new third UI.

### Grading passback scope for v1

Recommend passing back **one score per `PlaylistCourseOrdered`** (i.e. one
LMS gradebook column per assignment, matching how Canvas/Moodle
assignments normally work), using the same `progress_pct` /
`last_score_pct` already computed by `_playlist_stats()`
(`apps/student/unit_progress.py:199-289`) for `CourseDetailView`. No new
scoring logic — reuse what `course_detail.html` already renders.

---

## Part B — The aggregate student dashboard itself

### New page: `/s/progress/` (name TBD — could also live at `/s/` if the
existing home page is judged to already serve this role; product owner
call)

**Aggregates across all of a student's enrolled courses:**
- Overall completion — reuse `overall_pct` pattern already computed per
  course in `CourseDetailView` (`2026-06-14-student-course-experience-design.md`),
  averaged again across courses.
- Skill mastery summary — reuse `_batch_skill_levels()` across the union of
  all unit tags the student's courses touch, rendered as a compact grid
  (mastered / proficient / familiar / attempted / not-started counts),
  not a full segmented bar per unit (that already exists per-unit at
  `/s/units/<n>/`).
- Recent activity — most recent `PerformanceData`/`IdentificationAttempt`
  rows across all courses, small list, "You practiced Note Names 2 hours
  ago."
- If the rewards system (separate spec,
  `2026-07-02-rewards-system-design.md`) is approved, badges earned appear
  here too — this page is the natural home for them.

### No new models required for Part B

Every number needed is already computed by existing services
(`_batch_playlist_data`, `_playlist_stats`, `_batch_skill_levels`). This is
an aggregation + new template, same pattern as `CourseDetailView`.

### LTI-launched vs. direct-login rendering

Same template, same view, same URL. The only difference: if the request
arrived via an LTI launch tied to a single course (the common case — a
Canvas assignment link launches into "this HarmonyLab course"), the page
should default to a single-course scoped view rather than the
all-courses aggregate, since that's what the instructor's LMS
"assignment" link implies. Concretely: honor an optional
`?course=<pk>` param that Part A's launch handler sets, and detect it in
`GET`, not through a special LTI-only branch.

---

## Out of scope for this spec

- Deep Linking (instructor picks a specific HarmonyLab assignment from
  inside the LMS's UI) — a Part A follow-on, not required for grade
  passback or dashboard viewing.
- Names and Role Provisioning Services (NRPS) roster sync — would let
  HarmonyLab pull a class roster from the LMS instead of using existing
  `Group`/`visible_to` invite flow. Worth revisiting once the teacher
  dashboard (separate spec) is built, since NRPS would change how
  `course.visible_to` groups get populated.
- Any change to `Course`, `Playlist`, `PlaylistCourseOrdered`,
  `ExercisePlaylistOrdered` beyond the additive `LtiLineItem` mapping
  table — no assignment-architecture changes, consistent with the current
  AGENTS.md hold on that work.

---

## Files to change (implementation-time, Part A)

| File | Change |
|---|---|
| `apps/lti/` | New app: models, views, urls, services (grade passback) |
| `requirements.txt` / `pyproject.toml` | Add `pylti1p3` |
| Django settings | `SameSite=None; Secure` cookie config scoped to LTI launch paths only; `frame-ancestors` CSP allowlist per connected `LtiPlatform` |
| `apps/lti/migrations/` | `LtiPlatform`, `LtiUserLink`, `LtiLineItem` |

## Files to change (implementation-time, Part B)

| File | Change |
|---|---|
| `apps/student/views.py` | New `ProgressDashboardView` (or extend `HomeView`, pending product owner decision above) |
| `apps/student/urls.py` | New route |
| `apps/student/templates/student/progress_dashboard.html` | New template |
| `apps/student/unit_progress.py` | Possible small addition: a cross-unit variant of `_batch_skill_levels` scoped to "all tags across the student's enrolled courses" rather than one unit's tags |
