# HarmonyLab Development Plan

_Last updated: 2026-04-02_

Actionable steps in order. Check off as completed.

---

## Phase 1 — Get Running

> **Sequencing note:** Upgrade Django locally first, then deploy the upgraded version
> once to new hosting. One migration instead of two.

### 1.1 Upgrade Django + Python (locally)

- [x] Upgrade Python 3.10 → 3.12
- [x] Upgrade dependencies with breaking changes:
  - [x] `whitenoise` 5.1.0 → 6.x
  - [x] `dj-database-url` 0.5.0 → 2.x
  - [x] `psycopg2-binary` 2.8.6 → 2.9.x
  - [x] Replace `pytz` with `zoneinfo` (built into Python 3.9+)
  - [x] Update `chardet`
- [x] Upgrade Django 2.2 → 3.2 (step 1), verify locally, fix breakage
- [x] Upgrade Django 3.2 → 4.2 (step 2), verify locally, fix breakage
- [x] Upgrade Django 4.2 → 5.2 LTS (step 3), verify locally, fix breakage
- [ ] Verify all pages work end-to-end locally

### 1.2 Deploy upgraded version to new hosting

- [ ] Choose hosting: Heroku (fastest) or Fly.io (cheaper, ~$5–8/mo vs ~$12–16/mo)
- [ ] **If Heroku:**
  - [ ] Create new Heroku app
  - [ ] Add Postgres addon
  - [ ] Set env vars: `SECRET_KEY`, `DJANGO_SETTINGS_MODULE=harmony.settings.heroku`, `ALLOWED_HOSTS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `SENTRY_DSN`
  - [ ] `git push heroku master`
- [ ] **If Fly.io:**
  - [ ] Write `Dockerfile`
  - [ ] Write `fly.toml` (include `[deploy] release_command` for migrations + createcachetable)
  - [ ] `fly postgres create`
  - [ ] Set same env vars
  - [ ] `fly deploy`
- [ ] Transfer existing database: `pg_dump` old host → `pg_restore` new host
- [ ] Update DNS to new host
- [ ] Verify password reset email works
- [ ] Verify MIDI input works in Chrome/Edge

---

## Phase 2 — College Pilot

### 2.1 Group join codes

- [x] Add `join_code` field to `Group` model
- [x] Auto-generate code on Group creation
- [x] Add join code display to group edit page (teacher sees/copies code)
- [x] Add `POST /groups/join/` view (student submits code → added to group)
- [x] Add join code entry UI for students (on dashboard or registration flow)

### 2.2 Student "My Work" view

- [ ] Create new view showing only courses student is enrolled in via Group membership
- [ ] Show completion status per playlist (not started / in progress / complete)
- [ ] Show due dates if set
- [ ] Link directly to playlist player
- [ ] Set as default post-login destination for students (replace "Courses By Other Users")

### 2.3 Public content library

- [ ] Create `/library/` page listing all `is_public` courses, playlists, exercises
- [ ] Add topic filter (uses tags from 2.5)
- [ ] Add type filter (course / playlist / exercise)
- [ ] Make browsable without needing to be connected to the author

### 2.4 Course clone / copy

- [ ] Create `POST /library/clone-course/<course_id>/` view
- [ ] Deep-clone Course + PlaylistCourseOrdered entries
- [ ] Set `authored_by = request.user`, `is_public = False` on clone
- [ ] Exercises referenced (not cloned)
- [ ] Redirect to cloned course edit page

### 2.5 Content tagging

- [ ] Add `tags = ArrayField(...)` to `Exercise` and `Playlist` models
- [ ] Add tag selector to exercise and playlist edit forms
- [ ] Wire tags to library filter

### 2.6 Teacher gradebook polish

- [ ] Add score/grade column alongside completion in `course_activity_view`
- [ ] Show on-time / tardy / late status using existing `timely_credit` fields
- [ ] Add CSV export

### 2.7 Due date UI

- [ ] Add `due_date` field to `PlaylistCourseOrdered` if not present
- [ ] Add date picker to course edit form (one per playlist)
- [ ] Show due dates on student "My Work" view
- [ ] Show timely/tardy/late status in gradebook

### 2.8 Mouse & keyboard input

- [ ] **On-screen piano keyboard** — SVG/HTML piano, fires `noteOn`/`noteOff` identical to MIDI
- [ ] **Computer keyboard note entry** — letter keys for pitch (A–G), number for octave
- [ ] Show on-screen keyboard when no MIDI device detected (or as permanent toggle)

### 2.9 Build content library (content task)

- [ ] Intervals — identification (3 playlists, ~20 exercises each)
- [ ] Intervals — notation (2 playlists)
- [ ] Triads — identification (4 playlists)
- [ ] Triads — notation (2 playlists)
- [ ] Seventh chords — identification (3 playlists)
- [ ] Seventh chords — notation (2 playlists)
- [ ] Roman numeral analysis (4 playlists)
- [ ] Voice leading — SATB basics (3 playlists)
- [ ] Tag all content, mark as `is_public`

---

## Phase 3 — Monetization

_Start after pilot validates the product._

### 3.1 Role field + teacher verification

- [ ] Add `role` field to `User` model (`TextChoices`: `student` / `teacher`)
- [ ] Add role selector to registration form
- [ ] Require `.edu` email for teacher registration
- [ ] Add manual approval path for non-.edu teacher requests

### 3.2 Email verification

- [ ] New accounts create with `is_active=False`
- [ ] Send verification email with signed token on registration
- [ ] Verification link sets `is_active=True`

### 3.3 Stripe integration

- [ ] Add `stripe_subscription_id` and `subscription_status` to `User`
- [ ] Wire Stripe Checkout into the group join flow (student pays before enrolling)
- [ ] Handle payment success webhook → enroll student
- [ ] Add subscription management page (cancel, update card)
- [ ] Teachers bypass payment check entirely

### 3.4 Access control

- [ ] Add subscription check decorator/mixin
- [ ] Gate: joining a group, submitting performance in course context, gradebook access
- [ ] Free (no gate): library browsing, solo practice, creating own content

---

## Phase 4 — Growth

_Prioritize based on pilot feedback._

- [ ] Species counterpoint exercise type
- [ ] Harmonic dictation exercise type
- [ ] Melodic dictation exercise type
- [ ] Frontend: replace RequireJS with Vite
- [ ] Frontend: Bootstrap 4 → 5 (or Tailwind)
- [ ] Frontend: add htmx for partial-page updates
- [ ] React/Vue SPA rewrite (only if mobile or richer UI is required)

---

## Reference

- [spec.md](spec.md) — Full feature specifications with acceptance criteria
- [hosting_and_roadmap.md](hosting_and_roadmap.md) — Strategic rationale and background
