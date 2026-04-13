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

### 1.1 Upgrade Django + Python ✅ (locally done)

- [x] Upgrade Python 3.10 → 3.12
- [x] Upgrade Django 2.2 → 5.2 LTS (step-by-step: 2.2 → 3.2 → 4.2 → 5.2)
- [x] Upgrade all breaking dependencies (whitenoise, dj-database-url, psycopg2, pytz → zoneinfo, chardet)
- [ ] Verify all pages work end-to-end locally

### 1.2 Deploy to hosting

- [ ] Choose hosting: Heroku (fastest) or Fly.io (~$5–8/mo)
- [ ] **If Heroku:** create app, add Postgres addon, set env vars (`SECRET_KEY`, `DJANGO_SETTINGS_MODULE=harmony.settings.heroku`, `ALLOWED_HOSTS`, `EMAIL_HOST_*`, `SENTRY_DSN`), `git push heroku master`
- [ ] **If Fly.io:** write `Dockerfile` + `fly.toml`, `fly postgres create`, set same env vars, `fly deploy`
- [ ] Transfer existing database: `pg_dump` old host → `pg_restore` new host
- [ ] Update DNS, verify password reset email, verify MIDI in Chrome/Edge

---

## Phase 2 — College Pilot

### 2.1–2.7 ✅ Core pilot features (all complete)

Group join codes, student My Work view, public library, course clone, content tagging, gradebook polish, due date UI — all implemented.

### 2.8 Mouse & keyboard input

- [x] On-screen piano (mouse), QWERTY keyboard layout — both exist
- [ ] QWERTY discoverability — add visible help label/tooltip so users know the layout exists
- [ ] Note-name entry mode — letter keys `a`–`g` = pitch, `1`–`8` = octave, arrows = sharp/flat; same `noteOn`/`noteOff` events

### 2.11 Identification exercise type ✅ (almost — one task remaining)

- [x] `identification` type, `IdentificationGrader`, `LabelInputComponent`, wired into exercise context
- [ ] Add `<div id="label-input"></div>` mount point to `exercise.html` + CSS for button states

### 2.11a Chorale identification exercise flow ✅ IMPLEMENTED

- [x] Add `chorale_identification` as a first-class exercise type built on chorale onset windows
- [x] Generate Roman numeral or figured-bass prompts directly from the chorale score data
- [x] Reuse the identification grading flow without changing `analyze.js`, `identification_grader.js`, or `score_timeline.js`
- [x] Support creation through both `import_chorale` and a dashboard “Save, Duplicate as Identification” action on chorale exercises
- [x] Align score rendering, label hit zones, and feedback markers so the exercise is usable in the browser
- [x] Cover the duplication path with a Django test and verify the merged feature locally

### 2.12 Curriculum content ⚠️ KEY BLOCKER

**Blocker for teacher onboarding.** Until a starter curriculum exists in the public library, teachers cannot browse-and-clone a ready-made course.

> ❌ **Programmatic generation is off the table.** Attempts with voicing.py, templates.py, and music21_builder all produced unusable output (wrong spellings, wrong registers). The `curriculum-generation` branch is abandoned.

**Content will be created by:** hand-authoring in the exercise editor, MusicXML import, or manual curation. Fix the tools (2.19–2.21) before attempting this at scale.

**Content needed:**
- [ ] Intervals — matching + identification (common major keys)
- [ ] Triads — root position, inversions — matching + identification (all 12 keys via transposition)
- [ ] Seventh chords — dominant, major, minor, half-dim — matching + identification
- [ ] Diatonic triads + seventh chords in major keys — matching + analytical
- [ ] Scales — major, natural minor
- [ ] Rule of the Octave — ascending + descending
- [ ] ii–V–I progressions
- [ ] Tag all content, mark as `is_public`, assemble into one public course

**Path B — MusicXML web import (batch):**
- [ ] Extract `import_musicxml` core logic into `apps/exercises/utils/musicxml.py`
- [ ] Add batch slicing: upload one file, specify measure ranges, generate multiple exercises
- [ ] Add playlist creation option + analysis preset selector to web import form

**Path C — word question type:**
- [ ] Add `"question"` type: text prompt + multiple-choice buttons, no staff, no MIDI
- [ ] Reuse `LabelInputComponent`; hook into `IdentificationGrader`

### 2.13 MusicXML import for teachers

Currently only accessible via Django admin. Needs a dashboard UI.

- [ ] Add `POST /dashboard/exercises/import-musicxml/` view
- [ ] Upload form: file + title + measure range + public checkbox
- [ ] Extract management command logic into `apps/exercises/utils/musicxml.py`
- [ ] Add "Import MusicXML" button to exercises list page

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
- [ ] Add `role` field (`student` / `teacher`), role selector on registration, `.edu` gate + manual approval path

### 3.2 Email verification
- [ ] New accounts `is_active=False`; send signed verification link on registration; link sets `is_active=True`

### 3.3 Stripe integration
- [ ] `stripe_subscription_id` + `subscription_status` on User; Checkout in group join flow; payment success webhook → enroll; subscription management page

### 3.4 Access control
- [ ] Subscription check decorator; gate: group join, performance submission in course context, gradebook; free: library, solo practice, own content

---

## Phase 4 — Growth

_Prioritise based on pilot feedback._

- [ ] Species counterpoint exercise type
- [ ] Harmonic dictation exercise type
- [ ] Melodic dictation exercise type
- [ ] Frontend: replace RequireJS with Vite
- [ ] Frontend: Bootstrap 4 → 5 (or Tailwind)
- [ ] Frontend: add htmx for partial-page updates

---

## Reference

- [architecture.md](architecture.md) — How the app works (data model, request flow, frontend, grading)
- [spec.md](spec.md) — Full feature specifications with acceptance criteria
- [hosting_and_roadmap.md](hosting_and_roadmap.md) — Strategic rationale and background
