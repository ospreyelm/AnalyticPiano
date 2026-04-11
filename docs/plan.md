# HarmonyLab Development Plan

_Last updated: 2026-04-10_

Actionable steps in order. Check off as completed.

---

## Current state (2026-04-10)

- App runs locally. Hosting not yet deployed (Phase 1 still pending).
- Pilot with college approaching — teacher onboarding is the critical path.
- **The real blocker is content.** A starter curriculum needs to exist in the public library before teachers can onboard. But creating content is painful because the tooling is missing — exercises are hard to browse, creation takes 3 pages, and transposition is broken. Fix the tools first (2.19–2.21), then create content (2.12).
- Recurring assignments (2.14) is fully implemented and merged.
- Chorale identification is fully implemented and merged: a chorale can now be turned into a guided Roman numeral or figured-bass identification exercise from import flow or dashboard duplication.
- The `curriculum-generation` branch (programmatic exercise generation) was attempted and abandoned — do not revisit.

**Next session priorities (in order):**
1. ~~**2.21** — Smart transposition~~ ✅ done
2. **2.19** — Exercise audit view (can't manage what you can't see)
3. **2.20** — Streamlined creation flow (reduce 3 pages → 1)
4. **2.12** — Start building content once tools are in place

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

### 2.11a Chorale identification exercise flow ✅ IMPLEMENTED (2026-04-10)

A companion to the chorale-play type: the score is fully displayed and the student identifies each onset-window chord by selecting the correct Roman numeral or figured-bass label.

- [x] Add `chorale_identification` as a first-class exercise type; reuse `IdentificationGrader` without modifying `analyze.js`, `identification_grader.js`, or `score_timeline.js`
- [x] Client-side problem generation: extract onset windows from the chorale score and compute Roman numeral / figured-bass labels via the existing `Analyze` utility
- [x] Render the full chorale score with all notes black; overlay clickable label slots aligned to onset columns
- [x] Support creation via `import_chorale --mode identify` and via a dashboard "Save, Duplicate as Identification" button on any chorale exercise
- [x] Wire backend: new exercise type recognised in `forms.py`, `admin.py`, and `exercise_definition.js`
- [x] Django test for the duplication command; cherry-picked into `master` as commit `896114de`

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

**Explanation logic generation (new — tied to 2.13):**
- [ ] Each generated exercise spec should include an `explanation` block alongside the exercise JSON containing: `summary` (one-sentence string), `steps` (ordered array of strings), and optional `highlights` (MIDI note lists or staff note IDs to emphasize)
- [ ] Add an optional explanation template / DSL field to YAML curriculum specs so authors can define explanation patterns (e.g., `interval_quality_steps`, `triad_inversion_steps`) that the generator expands per-problem — this ensures explanations scale with generated content without hand-authoring each one
- [ ] `generate_curriculum` command writes explanation blocks into Exercise JSON when a template is defined in the spec

### 2.13 "Explain this" button (student rationale panel)

After a student attempts an exercise problem (correct or incorrect), they can tap/click **"Explain this"** to see a step-by-step rationale for why the answer is correct, using the same vocabulary the app uses elsewhere (semitone counts, scale degrees, chord quality/inversion logic, set-class normal form, figured-bass realization steps, etc.).

**UI:**
- [ ] Add "Explain this" button near the correctness feedback area in `exercise.html` / exercise player; hidden until at least one attempt has been made on the current problem
- [ ] Optionally show a small `?` icon beside the displayed correct answer as a secondary affordance
- [ ] Render explanation in a lightweight popover / expandable panel (not a blocking modal) containing: `summary` (one sentence), `steps` (bullet list), and optional note/chord highlights on the staff or piano

**Explanation data contract:**
- [ ] Define a shared `ExplanationBlock` shape: `{ summary: string, steps: string[], highlights?: number[] }` used by all exercise types
- [ ] Create `lab/static/js/src/utils/explanation_renderer.js` — takes an `ExplanationBlock` and mounts the popover/panel UI; handles show/hide/animation
- [ ] Create `lab/static/js/src/explanations/` directory with one module per exercise type (below); each exports a `buildExplanation(problem, answer) → ExplanationBlock` function

**Explanation logic — incremental rollout:**
- [ ] `explanations/interval.js` — spell note names, compute generic interval number (staff distance), count semitones, determine quality (major/minor/perfect/aug/dim)
- [ ] `explanations/triad.js` — identify root via stacking thirds, determine quality from interval pattern, determine inversion from bass note
- [ ] `explanations/seventh_chord.js` — extend triad logic to four-note stacks, add seventh quality
- [ ] `explanations/pc_set.js` — show normal form / prime form derivation steps; include interval-class vector if curriculum uses it
- [ ] `explanations/figured_bass.js` — show chord tones implied by figures, key context, and why a given realization matches
- [ ] `explanations/identification.js` — wrap the above per problem type for the `identification` exercise type (2.11)

**Wiring:**
- [ ] Wire `explanation_renderer.js` into `exercise_context.js`: after `grade()` resolves, read `problem.explanation` (static, from exercise JSON) or call the appropriate `buildExplanation()` function (dynamic); expose result to the renderer
- [ ] Support both static (explanation baked into exercise JSON by the curriculum generator — see 2.12) and dynamic (computed client-side) explanation sources; static takes precedence when present

**Telemetry (optional but recommended for pilot):**
- [ ] Log `explanation_opened` event with: exercise type, problem index, whether the student's answer was correct, attempt count at time of open
- [ ] Use event data to evaluate whether explanation usage correlates with improved second-attempt accuracy

### 2.10 MusicXML import for teachers

Currently `import_musicxml` is only accessible via the Django admin panel (`/analytic-piano-app-admin/exercises/exercise/`). Needs a dashboard UI for teachers once a teacher/student role distinction exists (see 3.1).

- [ ] Add `POST /dashboard/exercises/import-musicxml/` view (teacher-only once roles exist)
- [ ] Upload form: file field + title + measure range (start/end) + public checkbox
- [ ] Wire to existing `import_musicxml` management command logic (extract into a reusable function in `apps/exercises/utils/`)
- [ ] Add "Import MusicXML" button to exercises list page
- [ ] Guard with role check once 3.1 is complete; for now, any logged-in user can use it

### 2.14 Recurring assignments ✅ IMPLEMENTED

Full recurring playlist system with per-period progress tracking, student My Work view, and teacher gradebook columns. All done.

### 2.15 UI/UX polish

- [ ] Audit dashboard pages for highest-impact visual pain points
- [ ] Update global styles: typography, colour, spacing, card/table treatments
- [ ] Polish student My Work and teacher gradebook views
- [ ] Verify responsive on tablet (likely in-class device)

### 2.16 LTI integration (Moodle)

_Requirements TBD — confirm with college May 2026._

- [ ] Confirm scope (SSO only vs. grade passback vs. roster sync)
- [ ] Choose LTI version (1.1 vs. 1.3) based on college Moodle version
- [ ] Spec and implement once confirmed

### 2.17 Course scheduling wizard

_Depends on 2.12 (content) and 2.14 (recurring). Needs spec session._

A wizard that takes a course and distributes its exercises into scheduled sessions: teacher picks weekday pattern + max exercises/session + start date; wizard creates `PlaylistCourseOrdered` entries with due dates.

- [ ] Spec wizard flow
- [ ] Auto-split logic: divide exercises into sessions in curriculum order
- [ ] Wizard UI: course → schedule → exercises/session → preview → confirm
- [ ] Allow preview and adjustment before committing

### 2.18 Counterpoint checking

Alerting and grading parallel fifths, parallel octaves, and doubled leading tones.

- [ ] Spec detection rules and grading behaviour
- [ ] Implement

### 2.19 Exercise audit view ⚠️ DO THIS BEFORE MORE CONTENT CREATION

Teachers cannot manage 400+ exercises — the current list shows ~50 at a time with no filtering.

- [ ] Add `/dashboard/exercises/audit/` — paginated table of all exercises by current user
- [ ] Columns: ID, description, key, type, tags, playlist count, locked, created date
- [ ] Filter by type, tag, key; full-text search on description
- [ ] Inline quick-edit for description and tags (no page reload)
- [ ] Bulk-tag action
- [ ] Links to exercise editor and preview from each row
- [ ] find a way to allow a teacher to work on a single course or single playlist not seeing all the exercises but only the ones that already belong to those courses or playlists.

### 2.20 Streamlined exercise creation flow

Currently 3 pages: (1) MIDI input, (2) save/type form, (3) preview. Friction kills content velocity.

- [ ] After saving from play/MIDI page, land on exercise editor with notes pre-populated — skip the middle confirm page
- [ ] Type, analysis settings, description all editable on the same page as the staff preview
- [ ] "Save and create another" action that resets input without navigating away
- [ ] Side-by-side layout: staff preview left, settings panel right

### 2.21 Smart playlist transposition ✅ DONE

Transposition always goes up — C→Bb shifts up a major 7th instead of down a major 2nd. Exercises end up in wrong registers.

- [x] Find where transposition interval is computed (`apps/exercises/utils/transpose.py`)
- [x] For each target key, pick the direction that results in the smaller interval (≤ 6 semitones)
- [x] Tritone (exactly 6 semitones): prefer down
- [x] Tests: C→F = +5 (up P4), C→Bb = −2 (down M2), C→F# = −6 (down tritone), C→G = −5 (down P4)
- [x] All 12×12 key pairs verified: no vector exceeds 6 semitones

### 2.22 Curriculum assembly tool

_Needs spec session before implementation._

No bird's-eye view of a course under construction. Everything is separate edit pages.

- [ ] Spec the UI
- [ ] Course outline page: available playlists/exercises left, course structure right
- [ ] Drag-and-drop reordering of playlists in course and exercises in playlist
- [ ] Inline new-playlist creation
- [ ] Transposition settings visible + editable per playlist inline
- [ ] Publish/unpublish from this view

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
