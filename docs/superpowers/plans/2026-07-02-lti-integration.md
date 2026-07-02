# LTI Integration (Part A) — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-07-02-student-dashboard-lti-design.md` (Part A + revision)
**Date:** 2026-07-02
**Branch:** `claude/dashboards-rewards-system-4yvqqx` (continue on current branch)

---

## Phase 0 — External prerequisites (blocking for go-live, not for scaffolding)

Not code — a checklist of what has to come from outside the repo before
any `LtiPlatform` row can serve a real student. Phases 1–6 below can be
built and fully unit-tested against fake/mock platform config without
these; they gate turning a specific institution's connection on, not the
code itself.

### Tasks

- [ ] Confirm with the college's Moodle admin: issuer URL, client ID,
      deployment ID(s), JWKS URL, OIDC auth endpoint, token endpoint —
      the values a `LtiPlatform` row needs.
- [ ] Confirm with the Moodle admin what privacy level the tool will be
      registered under (does she plan to release `name`/`email`, or
      configure it anonymous/`sub`-only?) — this doesn't change the code
      (Phase 4 already assumes the strict case), but it changes what a
      teacher will actually see on the class progress dashboard, worth
      knowing ahead of the demo.
- [ ] Confirm who signs the data-sharing/FERPA agreement on the
      HarmonyLab-operator side and get a target date — `agreement_signed_at`
      (Phase 2) stays null, and the platform stays unusable for real
      course data, until this exists.
- [ ] Decide the redirect URIs / tool registration details Moodle will
      need from us (login init URL, launch URL, JWKS URL — these come
      from Phase 3's routes, so this step happens after Phase 3, not
      before).

### Acceptance
A filled-in `LtiPlatform` row's worth of real values exists somewhere
(even just notes), plus a known agreement-signing owner and target date.

---

## Phase 1 — App skeleton + dependency

**Files:** `apps/lti/` *(new)*, `requirements.txt`/`Pipfile`, `harmony/settings/*`

### Tasks

- [ ] Add `pylti1p3` to `Pipfile` (and regenerate `Pipfile.lock`)
- [ ] Create `apps/lti/` as a standard Django app: `__init__.py`,
      `apps.py`, `models.py`, `views.py`, `urls.py`, `services.py`,
      `migrations/`, `tests/`
- [ ] Register `apps.lti` in `INSTALLED_APPS`
- [ ] Wire `apps/lti/urls.py` into the project's root `urls.py` under
      `/lti/`

### Acceptance
`python manage.py check` passes with the new app installed and empty.

---

## Phase 2 — Models

**File:** `apps/lti/models.py`

### Tasks

- [ ] `LtiPlatform`: `name` (display, e.g. "Example College Moodle"),
      `issuer`, `client_id`, `deployment_ids` (`ArrayField` — a platform
      can have more than one deployment), `auth_login_url`,
      `auth_token_url`, `jwks_url` (or a stored public key set, per
      `pylti1p3`'s registration format), `agreement_signed_at`
      (nullable `DateTimeField`), `is_active` (bool, default `False`)
- [ ] `LtiUserLink`: `user` FK, `platform` FK, `sub` (`CharField`),
      `unique_together = ("platform", "sub")`
- [ ] `LtiLineItem`: `pco` FK to `PlaylistCourseOrdered`, `platform` FK,
      `line_item_id` (the platform-side resource id/URL returned when the
      line item is created or discovered)
- [ ] Migration
- [ ] Admin registration (`apps/lti/admin.py`) for `LtiPlatform` only —
      this is the only place a superuser sets `agreement_signed_at` and
      flips `is_active`; not exposed to teachers
- [ ] Tests: `unique_together` enforcement on `LtiUserLink`;
      `LtiPlatform.deployment_ids` accepts multiple ids

### Acceptance
`python manage.py test apps.lti.tests.test_models` passes. Migration
applies cleanly on a fresh DB.

---

## Phase 3 — OIDC login + launch + JWKS endpoints

**Files:** `apps/lti/views.py`, `apps/lti/urls.py`

### Tasks

- [ ] Implement `apps/lti/services.py::ToolConfig` — adapts
      `LtiPlatform` rows into the registration format `pylti1p3`'s
      Django tool config expects (`pylti1p3.tool_config.ToolConfDjango`
      or a custom `ToolConfAbstract` subclass reading from the DB
      instead of a static JSON file, since platforms are added at
      runtime via Phase 2's admin, not deploy-time config)
- [ ] `GET/POST /lti/login/` — OIDC third-party login init, per
      `pylti1p3`'s Django example (`OIDCLogin`)
- [ ] `POST /lti/launch/` — the signed launch; verifies the JWT via
      `pylti1p3`, extracts claims, hands off to Phase 4's identity
      resolution, then redirects into `/s/...` or `/teacher/...`
      per role
- [ ] `GET /lti/jwks/` — serves HarmonyLab's own public JWKS (tool-side
      keys `pylti1p3` needs for signing AGS/deep-linking requests back
      to the platform)
- [ ] Reject launches for a platform with `is_active=False` or
      `agreement_signed_at is None` with a clear error page (this is the
      code-level safety net from the spec — not just relying on nobody
      registering a platform early)
- [ ] Tests using `pylti1p3`'s test/mock launch helpers (or hand-built
      signed JWTs against a locally-generated test keypair) against a
      fake `LtiPlatform` row — no real Moodle connection needed for this
      phase

### Acceptance
A scripted fake launch (test-only keypair + fake platform row) reaches
`/lti/launch/`, validates, and redirects correctly by role.

---

## Phase 4 — Identity resolution

**File:** `apps/lti/services.py` (or a sibling `identity.py` if
`services.py` grows past the file-length guideline)

### Tasks

- [ ] `resolve_user(launch_data) -> User`:
  - Look up `LtiUserLink` by `(platform, sub)`; return linked `User` if
    found.
  - Otherwise create a `User` with **no required email/name** — only a
    generated non-reversible display label (hash of `sub`, not `sub`
    itself) — then create the `LtiUserLink`.
  - If `name`/`email` claims are present in the launch (institution
    chose to release them), store them on the `User`; if absent, leave
    blank. Never treat their absence as an error.
  - Ensure the created `User` has no usable password (LTI-only account —
    confirms the "can't be claimed by direct signup" rule from the spec)
- [ ] `resolve_role(launch_data) -> "teacher" | "student"` from the LTI
      roles claim
- [ ] Tests: new anonymous-mode launch creates a `User` with blank
      name/email and a working `LtiUserLink`; a launch with name/email
      claims stores them; a second launch with the same `(platform, sub)`
      reuses the existing `User` rather than creating a duplicate; role
      claim correctly maps Instructor/Learner

### Acceptance
`python manage.py test apps.lti.tests.test_identity` passes, covering
both the anonymous and name-released launch shapes.

---

## Phase 5 — Framing settings (iframe/cookie posture)

**Files:** Django settings (`harmony/settings/*`), possibly new
middleware in `apps/lti/`

### Tasks

- [ ] Scope `SameSite=None; Secure` session cookies to LTI launch
      requests/sessions only — do not change the global cookie posture
      for direct-login sessions (a global change would weaken CSRF
      protection for everyone, not just LTI users)
- [ ] Add a `Content-Security-Policy: frame-ancestors` header, populated
      from the active `LtiPlatform.issuer` values, applied only to the
      views that are meant to be iframed (the LTI-launched dashboard
      views, not the whole site)
- [ ] Tests: a direct (non-LTI) request still gets the default
      same-origin framing posture; an LTI-launched response includes the
      correct `frame-ancestors` for that platform's issuer only

### Acceptance
Existing non-LTI views' cookie/framing behavior is unchanged (regression
check against current test suite). New tests confirm the LTI-scoped
behavior.

---

## Phase 6 — Grade passback (AGS)

**File:** `apps/lti/services.py`

### Tasks

- [ ] `ensure_line_item(pco) -> LtiLineItem` — creates or looks up the
      platform-side line item for a `PlaylistCourseOrdered`, via
      `pylti1p3`'s AGS service wrapper; stores the returned id in
      `LtiLineItem`
- [ ] `publish_score(user, pco)` — computes the same `progress_pct` /
      `last_score_pct` already used by `CourseDetailView`
      (`apps/student/unit_progress.py::_playlist_stats`) and POSTs it to
      the platform via AGS, keyed by the `LtiUserLink.sub` for that user
      (not by name/email — nothing PII-bearing goes in the grade POST)
- [ ] Decide and document the trigger point: on every submission via the
      existing `record_attempt()` funnel, or only when a student
      explicitly finishes an assignment — **flag as open question for
      product owner**, not decided by this plan
- [ ] Tests against a mocked AGS endpoint (no real Moodle needed):
      correct score computed, correct line item targeted, correct sub
      used as the recipient

### Acceptance
`python manage.py test apps.lti.tests.test_grade_passback` passes against
mocked platform responses.

---

## Phase 7 — Manual end-to-end check against a real Moodle (blocked on Phase 0)

Only runnable once Phase 0's external prerequisites are in hand.

### Tasks

- [ ] Register HarmonyLab as an external tool in the college's Moodle
      sandbox/test course using Phase 3's login/launch/JWKS URLs
- [ ] Create the corresponding `LtiPlatform` row (still
      `agreement_signed_at=None`, `is_active=False` if the agreement
      isn't signed yet — verify the launch is correctly refused)
- [ ] Once agreement is confirmed and the row is activated: launch from
      a real Moodle test course as a test student — confirm identity
      resolution, role redirect, and that the dashboard renders inside
      Moodle's iframe
- [ ] Submit an exercise, confirm a grade appears in the Moodle
      gradebook for that assignment
- [ ] Confirm: no student name/email appears anywhere in HarmonyLab's
      database for this test student if Moodle was configured anonymous
      (spot-check via `manage.py shell`, not just code review)

### Acceptance
A real Moodle-launched student can practice and see a grade land in
Moodle's gradebook, with the actual DB contents matching whatever privacy
level the Moodle admin configured.

---

## Out of Scope (this plan)

- Deep Linking
- NRPS roster sync (deliberately excluded per the spec revision, not just deferred)
- Part B (the aggregate student dashboard itself) — separate plan, once
  Part A is merged
- `Course.requires_lti` enforcement flag — spec flags this as a v2
  open question, not decided here
