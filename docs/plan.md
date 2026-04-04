# HarmonyLab Development Plan

_Last updated: 2026-04-03_

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

- [x] Create new view showing only courses student is enrolled in via Group membership
- [x] Show completion status per playlist (not started / in progress / complete)
- [x] Show due dates if set
- [x] Link directly to playlist player
- [x] Set as default post-login destination for students (replace "Courses By Other Users")

### 2.3 Public content library

- [x] Create `/library/` page listing all `is_public` courses, playlists, exercises
- [x] Add topic filter (uses tags from 2.5)
- [x] Add type filter (course / playlist / exercise)
- [x] Make browsable without needing to be connected to the author

### 2.4 Course clone / copy

- [x] Create `POST /library/clone-course/<course_id>/` view
- [x] Deep-clone Course + PlaylistCourseOrdered entries
- [x] Set `authored_by = request.user`, `is_public = False` on clone
- [x] Exercises referenced (not cloned)
- [x] Redirect to cloned course edit page

### 2.5 Content tagging

- [x] Add `tags = ArrayField(...)` to `Exercise` and `Playlist` models
- [x] Add tag selector to exercise and playlist edit forms
- [x] Wire tags to library filter

### 2.6 Teacher gradebook polish

- [x] Add score/grade column alongside completion in `course_activity_view`
- [x] Show on-time / tardy / late status using existing `timely_credit` fields
- [x] Add CSV export

### 2.7 Due date UI

- [x] Add `due_date` field to `PlaylistCourseOrdered` if not present
- [x] Add date picker to course edit form (one per playlist)
- [x] Show due dates on student "My Work" view
- [x] Show timely/tardy/late status in gradebook

### 2.8 Mouse & keyboard input

_Existing systems (no changes needed):_
- [x] **On-screen piano** — Raphael SVG piano always visible; mouse-click fires `noteOn`/`noteOff` via EVENTS bus
- [x] **QWERTY piano-layout** — `keyboard_shortcuts.js` maps QWERTY rows to octaves; wired in `exercise.js` and `play.js`

_Remaining work:_
- [ ] **QWERTY discoverability** — add visible help label / tooltip near keyboard so users know the layout exists
- [ ] **Note-name entry mode** — letter keys `a`–`g` = pitch name, `1`–`8` = octave, `UP`/`DOWN` arrows = sharp/flat; fires same `noteOn`/`noteOff` events; selectable alongside existing QWERTY mode

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

### 2.11 Identification exercise type

A new exercise type where **notes are shown on the staff and the student selects the correct analytical label** from a set of buttons — the reverse of `analytical`. No MIDI grading; the answer mechanism is a multiple-choice UI.

- [ ] Add `identification` to `ExerciseDefinition.TYPES` in `exercise_definition.js`; parse `answer` and `choices` per problem; all notes go to `visible`, nothing to `hidden`; analysis overlays off
- [ ] Create `lab/static/js/src/models/identification_grader.js` — tracks pointer, student selections, correct/incorrect state; `selectLabel(label)` advances through problems; `grade()` returns same shape as `ExerciseGrader.grade()`
- [ ] Create `lab/static/js/src/components/input/label_input.js` — renders per-problem choice buttons; dispatches `EVENTS.BROADCAST.LABEL_SELECTED`; shows correct (green) / incorrect (red flash) feedback
- [ ] Wire into `exercise_sheet.js`: new `initIdentificationMode()` renders notes fully visible, mounts `LabelInputComponent` below canvas, suppresses MIDI grading
- [ ] Wire into `exercise_context.js`: branch on `isIdentification()` to use `IdentificationGrader`; listen for `LABEL_SELECTED`
- [ ] Wire into `exercise.js`: instantiate `IdentificationGrader` in `getModels()` when type is `identification`
- [ ] Add `<div id="label-input"></div>` mount point to `exercise.html`; CSS for button states

**Exercise JSON shape:**
```json
{
  "type": "identification",
  "key": "jC_",
  "chord": [
    { "visible": [60,64,67], "hidden": [], "answer": "I",  "choices": ["I","ii","IV","V"] },
    { "visible": [62,65,69], "hidden": [], "answer": "ii", "choices": ["I","ii","IV","V"] }
  ]
}
```

### 2.12 Curriculum generation system

Template-based and MusicXML-based batch generation of exercises and playlists. Full spec in [docs/curriculum_generation_spec.md](curriculum_generation_spec.md).

**Path A — template-based management command:**
- [ ] Create `apps/exercises/generation/analysis_presets.py` — expand shorthand analysis dicts (e.g., `{roman_numerals: true}`) to full Exercise JSON `analysis.mode` objects
- [ ] Create `apps/exercises/generation/voicing.py` — voicing strategy functions (close, open, close_4voice, keyboard_4voice) that compute MIDI note lists from root + quality + inversion
- [ ] Create `apps/exercises/generation/templates.py` — template functions: `single_note`, `interval`, `diatonic_intervals`, `triad`, `diatonic_triads`, `seventh_chord`, `diatonic_sevenths`, `scale`, `roto`, `progression`, `chorale_excerpt`
- [ ] Create `apps/exercises/generation/spec_loader.py` — YAML spec parser and validator; expands key shorthands (`all_major`, `all_minor`, `all_12`, `common_major`, `common_minor`)
- [ ] Create `apps/exercises/management/commands/generate_curriculum.py` — drives spec_loader + templates, creates Exercise/Playlist/Course records, supports `--dry-run` and `--overwrite`
- [ ] Create `data/curriculum/theory1.yaml` — first real spec covering intervals, triads, 7th chords, ROTO, basic progressions; validate output matches CSV conventions

**Path B — MusicXML web import (batch):**
- [ ] Extract `import_musicxml` core logic into `apps/exercises/utils/musicxml.py`
- [ ] Add batch slicing: upload one file, specify measure ranges, generate multiple exercises
- [ ] Add playlist creation option to web import form
- [ ] Add analysis preset selector to web import form

**Path C — word question type:**
- [ ] Add `"question"` to `ExerciseDefinition.TYPES`; parse `question`, `choices`, `answer` fields; skip staff rendering
- [ ] Show question text + multiple-choice buttons (reuse `LabelInputComponent` from identification type); no VexFlow, no MIDI
- [ ] Hook into `IdentificationGrader` (one problem, no notes)

### 2.10 MusicXML import for teachers

Currently `import_musicxml` is only accessible via the Django admin panel (`/analytic-piano-app-admin/exercises/exercise/`). Needs a dashboard UI for teachers once a teacher/student role distinction exists (see 3.1).

- [ ] Add `POST /dashboard/exercises/import-musicxml/` view (teacher-only once roles exist)
- [ ] Upload form: file field + title + measure range (start/end) + public checkbox
- [ ] Wire to existing `import_musicxml` management command logic (extract into a reusable function in `apps/exercises/utils/`)
- [ ] Add "Import MusicXML" button to exercises list page
- [ ] Guard with role check once 3.1 is complete; for now, any logged-in user can use it

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
