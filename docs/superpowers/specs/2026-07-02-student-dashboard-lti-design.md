# Student Progress Dashboard, Built Toward LTI — Design Spec

**Date:** 2026-07-02 (revised same day — FERPA/multi-tenant framing added)
**Status:** Draft — awaiting product owner review, not authorized for implementation
**Feature scope:** Student-facing aggregate progress view + the LTI groundwork it depends on.

---

## Why LTI, specifically (revision note)

The product owner's college requires LTI for any tool used in graded
coursework, per their Moodle administrator — this is the FERPA "school
official" exception in practice: the institution can share education-record
PII with HarmonyLab without per-student consent only under a written
agreement, and the *technical* precondition their Moodle admin is imposing
is that provisioning and grade exchange go through LTI rather than
students self-registering with a HarmonyLab account. **The LTI integration
does not itself constitute FERPA compliance** — the signed agreement
between the college and whoever operates HarmonyLab is what does that.
LTI is the technical mechanism the college's admin wants because it keeps
provisioning under the institution's direct control (one of the school-
official exception's requirements) and lets HarmonyLab minimize the PII it
ever has to store. This revision changes two things from the original
draft below: identity resolution no longer assumes email/name will be
available (Part A), and the design is explicitly multi-tenant so a second
college or a high school can be onboarded later without code changes
(new section below).

This has a direct consequence for the existing direct-signup flow: for any
course whose data is subject to an institution's FERPA agreement, student
identity must come from that institution's LTI launch, not from a
self-registered HarmonyLab account. Direct signup can remain for
non-institutional use (independent learners, a teacher's own ungraded
practice course) — it just can't be the enrollment path for a course
covered by a college's data agreement. **Open question for product
owner:** should this be enforced in code (e.g. a `Course.requires_lti`
flag that blocks non-LTI login from accessing it) or left as an
operational/policy rule for now? This spec assumes policy-only for v1 and
flags the flag-based enforcement as a natural v2.

## Multi-tenancy: built for more than one institution from day one

The product owner asked whether this could help other colleges and high
schools later — yes, and the model below is already shaped for it, not as
an afterthought:

- `LtiPlatform` is **one row per institution's LMS instance** (its own
  issuer, client ID, deployment ID(s), JWKS URL). Two colleges, or a
  college and a high school, are just two rows — no schema change, no
  per-institution code branching.
- `LtiUserLink` is scoped `(platform, sub)`, not just `sub` — the same
  numeric `sub` value can (and will) collide across institutions, since
  each platform assigns its own opaque IDs independently. Keying on the
  pair is what makes multiple institutions safe to hold in one database
  without cross-contamination.
- The FERPA agreement is a **per-institution legal artifact**, not a
  per-feature one — each new college or high school needs its own signed
  data-sharing agreement with whoever operates HarmonyLab before their
  `LtiPlatform` row goes live. Recommend `LtiPlatform.agreement_signed_at`
  (nullable) as a field, and gate the launch flow so a platform with no
  signed-agreement date can be configured/tested but not used for a real
  course — a code-level safety net matching the legal requirement, not
  just a policy note in a doc somewhere.
- High schools bring one extra wrinkle worth flagging now rather than at
  onboarding time: many students are minors, which brings **COPPA** and/or
  state student-privacy laws (e.g. SOPIPA in California) into play
  alongside FERPA. Nothing in this spec's data model changes for that, but
  the DPA process for a K-12 institution is typically stricter and
  the "minimize what you store" posture below matters even more there.

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
                   #   auth/token endpoints, agreement_signed_at — one row
                   #   per institution's LMS instance), LtiUserLink (user FK,
                   #   platform FK, sub, unique_together=(platform, sub)),
                   #   LtiLineItem (maps a PlaylistCourseOrdered -> platform
                   #   line item id)
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

### Identity resolution — `sub` is the only identity claim we require

The Moodle admin's requirement means this has to work correctly under the
*strictest* privacy configuration the institution might choose (an
"anonymous" launch: `sub` and role only, no `name`, no `email`) — not just
the common case where names are released. Designing for the strict case
first and treating name/email as optional enrichment, rather than the
reverse, is what keeps this compliant regardless of how each institution's
LMS admin configures the tool.

On launch: look up `LtiUserLink` by `(platform, sub)`.
- If found → log in as the linked Django `User`.
- If not found → **create a `User` keyed only on `(platform, sub)`.** Do
  not require `email`/`name` claims to exist. If the launch happens to
  include `name` and/or `email` (the institution released them), store
  them on the `User` as-is; if not, leave those fields blank and use a
  non-identifying display label (e.g. `f"Student {sub_hash[:6]}"`, derived
  from a one-way hash of `sub`, not from `sub` itself, so it's not
  reversible to the platform's own ID) for anywhere the UI needs to show
  *something* for the row (teacher dashboard, roster).
- Registration/direct-login by email must not be able to "claim" or merge
  into an LTI-provisioned account — an LTI-only `User` has no usable
  password and no email to log in with directly, by design; this prevents
  an account-takeover path where someone signs up directly with a guessed
  or scraped email and inherits an LTI-linked student's data.
- Role claim (`https://purl.imsglobal.org/spec/lti/claim/roles`) maps
  Instructor → teacher-side landing, Learner → student-side landing. This
  determines whether the launch redirects into `/s/...` or `/teacher/...`
  (Part C of the teacher dashboard spec) — **not** a new third UI.

### Scope request at platform registration — ask for the minimum

When registering HarmonyLab with a college's Moodle (or a future
institution's Canvas), request only:
- Core launch (`sub`, role, deployment/context claims) — always required.
- AGS score-publish scope (to push grades back) — required for grade
  passback.

Do **not** request the NRPS (roster) scope or any profile/email scope by
default. Requesting only what's used means an institution reviewing the
registration request sees a minimal ask, which is both the compliant
posture and, practically, an easier approval to get from a cautious
Moodle/Canvas admin.

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
  `Group`/`visible_to` invite flow. Deliberately excluded here, not just
  deferred: NRPS is a PII-pull scope (names/emails for a whole class in one
  call), which cuts against the minimal-scope posture this revision adopts.
  Worth revisiting only if a specific institution's DPA explicitly permits
  it and the teacher dashboard has a concrete need for it.
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
| `apps/lti/migrations/` | `LtiPlatform` (incl. `agreement_signed_at`, nullable — launch flow refuses to serve real course data for a platform with no signed-agreement date), `LtiUserLink` (unique on `(platform, sub)`), `LtiLineItem` |

## Files to change (implementation-time, Part B)

| File | Change |
|---|---|
| `apps/student/views.py` | New `ProgressDashboardView` (or extend `HomeView`, pending product owner decision above) |
| `apps/student/urls.py` | New route |
| `apps/student/templates/student/progress_dashboard.html` | New template |
| `apps/student/unit_progress.py` | Possible small addition: a cross-unit variant of `_batch_skill_levels` scoped to "all tags across the student's enrolled courses" rather than one unit's tags |
