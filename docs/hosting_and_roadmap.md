# HarmonyLab: Hosting, Modernization & Product Roadmap

*Written: 2026-04-02*

---

## Background

HarmonyLab has been hosted on Heroku by a collaborator. With that collaboration becoming unreliable, self-hosting is the logical next step. This document covers:

1. Hosting options and migration plan
2. What deployment actually requires
3. LMS assessment and modernization strategy
4. Product direction: mouse/keyboard input, course library, monetization

---

## 1. Hosting: Fly.io vs Heroku

### Cost Comparison

| Factor | Heroku | Fly.io |
|---|---|---|
| Free tier | None (removed 2022) | Yes (shared CPU, 256MB RAM) |
| Cheapest paid compute | ~$7/mo (Eco dyno) | ~$2–5/mo |
| Postgres | $5–9/mo (mini) | $3/mo (1GB shared) |
| Static files | WhiteNoise works | WhiteNoise works |
| SSL | Included | Included |
| Deployment method | Git push + Procfile | Needs Dockerfile |
| Django support | Mature, documented | Well-supported |
| **Estimated total** | **~$12–16/mo** | **~$5–8/mo** |

### Recommendation

**Fly.io is the better long-term choice** — roughly half the cost, more control, and no vendor lock-in. The tradeoff is a one-time setup cost: writing a Dockerfile and `fly.toml` config (each ~40 lines).

**If speed matters most right now**, Heroku is the path of least resistance. The existing `Procfile` and `harmony/settings/heroku.py` mean deploying to a new Heroku account is a few commands.

---

## 2. What Deployment Requires

### Current State

The app is already Heroku-ready:
- `Procfile` runs migrations, creates the cache table, and starts gunicorn:
  ```
  release: python manage.py migrate && python manage.py createcachetable
  web: gunicorn harmony.wsgi:application --log-file -
  ```
- `harmony/settings/heroku.py` handles production config
- WhiteNoise serves static files (no S3/CDN needed)
- Sentry integration for error tracking

### Heroku (Fastest Path)

1. Create new Heroku app + Postgres addon
2. Set environment variables:
   - `SECRET_KEY`
   - `DJANGO_SETTINGS_MODULE=harmony.settings.heroku`
   - `ALLOWED_HOSTS` (JSON list of your domain)
   - `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` (Gmail SMTP for password reset)
   - `SENTRY_DSN` (optional)
3. `git push heroku master` — migrations run automatically

### Fly.io (Cheaper Path)

Same env vars, plus:
1. Write a `Dockerfile` (Python 3.10, install Pipfile deps, run gunicorn)
2. Write `fly.toml` (app name, region, port, health check)
   - Use the `[deploy] release_command` field to run migrations and `createcachetable` — this is the Fly.io equivalent of Heroku's `release` dyno
3. Create Fly Postgres cluster: `fly postgres create`
4. `fly deploy`

### One-Time Tasks Either Way

- Transfer the PostgreSQL database from the old host (pg_dump / pg_restore)
- Update DNS to point your domain at the new host
- Verify email sending works (password reset flow)
- Test MIDI input in Chrome/Edge after deploy

---

## 3. LMS Assessment

### What the App Is

HarmonyLab is not a traditional LMS — it is a **music theory practice platform with instructor features**. The exercise engine (MIDI grading, VexFlow notation, chorale analysis) is genuinely sophisticated and is the core differentiator. No off-the-shelf LMS (Moodle, Canvas, Open edX) does what this does.

### What Feels Dated

| Area | Current State | Modern Standard |
|---|---|---|
| Module system | RequireJS (2013) | ES modules / Vite |
| Frontend interaction | jQuery + full page reloads | React/Vue SPA or htmx |
| CSS framework | Bootstrap 4 (EOL) | Bootstrap 5 or Tailwind |
| Django version | 2.2 (EOL, no security updates) | 5.2 LTS (supported until April 2028) |
| Auth options | Email/password only | + Google/SSO |
| Student dashboard | None | Progress, completion, streaks |
| Mobile support | None (WebMIDI is desktop-only) | Responsive UI at minimum |
| Teacher UI | Admin panel only | Purpose-built course builder |

### Modernization Options

**Option A: Incremental improvement (recommended)**
- Upgrade Django to 5.2 LTS (current LTS, supported until April 2028) — critical for security
- Replace RequireJS with Vite — big developer experience improvement
- Add a modern student dashboard (progress bars, completion rates, history)
- Add htmx for partial-page updates without a full SPA rewrite
- Keep the Django backend — correct choice for this domain

**Option B: Frontend rewrite with React or Vue**
- Replace Django templates with a React SPA
- Django becomes a REST API (Django REST Framework)
- Much larger effort (months, not weeks)
- The music engine (VexFlow, Tone.js, graders) would carry over unchanged
- Enables mobile and richer interactivity long-term

**Option C: Adopt an existing LMS**
- Not viable. Canvas/Moodle/Open edX don't support custom MIDI exercises.
- The exercise engine is the entire product.

### Recommendation

Start with **Option A**. The Django upgrade alone (2.2 → 5.2) removes a meaningful security risk and unlocks modern Django features. Then layer in UX improvements. Reserve a full SPA rewrite for a later phase when the course library and user base justify it.

**Note on the Django upgrade:** The jump from 2.2 to 5.2 spans three major versions and will require updating several pinned dependencies that have had breaking changes:

| Package | Pinned version | Issue |
|---|---|---|
| `whitenoise` | 5.1.0 | Known issues with Django 4+; upgrade to 6.x |
| `dj-database-url` | 0.5.0 | API changed significantly in 1.x |
| `psycopg2-binary` | 2.8.6 | Update to 2.9.x |
| `pytz` | 2020.1 | Superseded by Python 3.9+ built-in `zoneinfo` |
| `chardet` | 3.0.4 | Very old; may have transitive conflicts |

Factor this dependency chain into the effort estimate — the actual upgrade is closer to **1–2 weeks** than a few days. Python 3.10 security support also ends October 2026, so a Python upgrade (3.10 → 3.12) is worth bundling with the Django upgrade.

---

## 4. Product Direction

### Mouse & Keyboard Input

The exercises currently accept MIDI keyboard input. Gaps to fill for non-MIDI users:

- **Clickable staff notation** — click a note head in the score to "play" it
- **On-screen piano keyboard** — click keys with a mouse
- **Computer keyboard note entry** — letter keys for pitch (A–G), numbers for octave, like Sibelius/Finale
- **All three are buildable** on top of VexFlow + the existing grader infrastructure without rearchitecting

This is the highest-leverage near-term feature — it removes the MIDI hardware requirement and opens the app to all students, not just those with MIDI controllers.

### Built-in Exercise Library (The Real Artusi Advantage)

Artusi's actual competitive strength is not its exercise engine — it's that students open it and there is already a full semester of structured work ready to go. Teachers don't have to build anything; they assign from a library.

HarmonyLab currently has no built-in library. All content is user-created. A teacher starting fresh has to build every exercise, playlist, and course themselves.

**This is the most important content gap to close before the pilot.**

#### What the library needs to contain

A standard undergraduate theory sequence (2 semesters) would cover:

| Unit | Exercise Types | Notes |
|---|---|---|
| Intervals | Identify and notate intervals | All qualities, all sizes |
| Scales & modes | Identify and complete scales | Major, minor, modal |
| Triads | Build and identify triads | All qualities, root position + inversions |
| Seventh chords | Build and identify 7ths | All types |
| Voice leading basics | 4-part SATB writing | Already strong (chorale grader) |
| Roman numeral analysis | Identify chords in context | Already exists |
| Secondary dominants | Tonicization | Extension of existing analysis |
| Species counterpoint | 1st–4th species | Not yet implemented |
| Harmonic dictation | Hear → identify progression | Not yet implemented |
| Melodic dictation | Hear → notate melody | Not yet implemented |

The top half of this table (intervals through Roman numerals) is buildable now using existing exercise types. The bottom half requires new exercise type development.

**The author's advantage:** Building this library is a content task, not an engineering task. A music theory teacher can create dozens of exercises per hour once the workflow is smooth. The priority is making that creation workflow fast and then populating the library.

#### How the library should be structured

**For teachers:**
- A dedicated **Content Library** page — browse all public courses, playlists, and exercises
- Filter by topic (intervals, triads, voice leading…), difficulty, exercise type
- One-click "Copy to my courses" — clone a public course and customize it
- This is the model Artusi uses: teachers adopt and adapt, not build from scratch

**For students:**
- A dedicated **My Work** page (replaces the current confusing "Courses By Other Users")
  - Shows only courses the student is enrolled in via their groups
  - Clear completion status per playlist
  - Due dates visible if set
- A **Free Practice** section — browse public exercises/playlists not tied to a course
  - Good for self-study, exam prep, exploration

#### Current browsing UX (and its problems)

The current system is connection/permission-based, not enrollment-based:

1. Teacher creates a Group → adds students manually by email → creates a Course → assigns Course to Group
2. Student sees it under "Courses By Other Users" — a flat list of all courses from anyone who's granted them content access, enrolled or not
3. There is **no public library page** — `is_public` content is accessible but not browsable
4. There is **no "My Assigned Work" view** — students can't distinguish "this was assigned to me" from "I can access this"
5. To find a teacher's course, a student must first manually add the teacher as a connection

This friction is acceptable in the current small-scale use but won't work for a class of 30 students who have never used the app.

#### What needs to be built

| Feature | What it does | Effort |
|---|---|---|
| **Public library page** | Browse all `is_public` courses/playlists/exercises, filter by topic | 2–3 days |
| **"My Work" student view** | Shows only courses assigned via groups; replaces "Courses By Others" | 2–3 days |
| **Copy/clone a public course** | Teacher clones a library course and customizes it | 1–2 days |
| **Join code enrollment** | Student enters code → added to teacher's group automatically (replaces manual email add) | 1–2 days |
| **Content tagging** | Tag exercises/playlists by topic (intervals, voice leading, etc.) for filtering | 1–2 days |

#### Artusi feature gap

| Feature | HarmonyLab Status | Gap |
|---|---|---|
| Chorale voice leading | Done (advanced) | None |
| Chord identification & Roman numerals | Done | None |
| Interval exercises | Exists | Library content needed |
| Triad/seventh chord exercises | Exists | Library content needed |
| Species counterpoint | Not implemented | New exercise type |
| Harmonic dictation | Not implemented | New exercise type |
| Melodic dictation | Not implemented | New exercise type |
| Public browsable library | Not implemented | Build browse UI |
| Student "My Work" dashboard | Not implemented | Build view |
| Teacher gradebook | Partial (course_activity view exists) | Polish UI |
| Payment / subscriptions | Not implemented | Phase 3 |

### User Roles: Teacher vs Student

The original design deliberately avoided separate teacher/student account types — all users share one model, keeping things fluid. This was a reasonable choice and the role distinction is already implicit in the data:

- A user who is `Group.manager` → is acting as a teacher
- A user who is a `Group.member` → is acting as a student
- `content_permits` / `performance_permits` → teacher grants student access

**Recommendation: don't add a separate model or role flag yet.** Use `Group.manager` as the teacher signal. If billing is added later, a single `role` field (`teacher` / `student`, set at registration) is the clean Django way — one field with `TextChoices`, not two booleans. Avoid `is_teacher + is_student` booleans (anti-pattern: what does both=True mean?).

### Monetization Model

The model mirrors Artusi's: **anyone can use the app for free; the paywall is around the classroom relationship**, not content access.

- Free tier: practice exercises, create playlists/courses, self-study
- Paid tier: joining a teacher's class, teacher seeing student performance data

This is clean because the billing attaches to the `Group` — the object that represents the classroom relationship. A `stripe_subscription_id` on `Group` (or a FK to a `Subscription` model) is all that's needed structurally. Exercise/Playlist/Course models don't need to change.

**Business model options:**
- **Per-student subscription** (~$15–25/semester) — matches Artusi pricing
- **Per-institution license** — flat fee for unlimited students at a school
- **Freemium** — free tier real and useful, paid tier for classroom features

**Teacher verification:** Require `.edu` email for teacher accounts at registration — one line of validation, matches how Artusi handles it. Not airtight but sufficient at early scale.

**Ongoing support costs** (realistic expectations):
- Disputed charges / forgotten subscriptions — small but real
- Non-.edu teacher requests (adjuncts, private teachers, international) — need a manual approval path
- Mid-semester cancellations — need a policy decision (lose access immediately? end of semester?)
- Institution deals — once you have traction, schools want one invoice for 30 students

None of these are engineering problems. The engineering is a one-time ~2-week effort; the support is operational.

**Implementation effort when ready:**
| Piece | Effort |
|---|---|
| Add `role` field + registration UI update | 1 day |
| Email verification before account activation | 1–2 days |
| `.edu` check for teacher registration | 2 hours |
| Stripe Checkout (one-time or subscription) | 2–3 days |
| Access control on Group join/view | 1 day |
| Subscription management page (cancel, update card) | 1–2 days |
| **Total** | **~2 weeks** |

### College Pilot (Before Monetizing)

The right sequence is: **pilot at your college first, charge later.** Running real students through the app will reveal what actually matters before building billing infrastructure.

#### What the data model already supports for a classroom

Inspecting the actual models, more is built than expected:

```
Group (manager=teacher, members=students)
  └── Course (visible_to → Groups)
        └── Playlist (ordered, with due dates commented out but schema present)
              └── Exercise

PerformanceData (user + playlist + course → every attempt recorded)
Course already has: timely_credit, tardy_credit, late_credit, tardy_threshold fields
```

The classroom relationship, grading weights, and per-student performance data are all modeled. What's missing is the **UI to use them**.

#### What needs to be built for the pilot

| Feature | What | Effort |
|---|---|---|
| **Join codes** | Teacher creates Group → gets a code (e.g. `MUSIC201-F26`); student enters code → auto-enrolled. Requires one `join_code` field on `Group` + one view. | 1–2 days |
| **Student dashboard** | "My courses, assignments, completion, scores" — the data is in `PerformanceData`, just needs a view and template | 3–5 days |
| **Teacher gradebook** | Class roster + completion/score per playlist per student — again, data exists, needs a view | 3–5 days |
| **Due date UI** | `Course` already has `timely_credit`, `tardy_credit`, `late_credit`, `tardy_threshold` fields. The UI for setting due dates per playlist is the missing piece. | 2–3 days |

**Total for a usable college pilot: ~2–3 weeks.** No structural changes to Exercise/Playlist/Course needed.

---

## Prioritized Next Steps

### Phase 1 — Get Running (Now)
| Priority | Task | Effort |
|---|---|---|
| Critical | Deploy to new hosting (Heroku fastest, Fly.io cheaper) | 1–2 days |
| Critical | Upgrade Django 2.2 → 5.2 LTS + Python 3.10 → 3.12 | 1–2 weeks |

### Phase 2 — College Pilot (Before charging anyone)
| Priority | Task | Effort |
|---|---|---|
| High | Group join codes for student self-enrollment | 1–2 days |
| High | "My Work" student view (assigned courses only, with completion) | 2–3 days |
| High | Public library page (browse/filter all `is_public` content) | 2–3 days |
| High | Copy/clone a public course (teacher adopts library content) | 1–2 days |
| High | Add on-screen piano / mouse input (removes MIDI hardware requirement) | 3–5 days |
| High | Teacher gradebook (roster + completion per playlist) | 3–5 days |
| Medium | Content tagging by topic (intervals, voice leading, etc.) | 1–2 days |
| Medium | Due date UI (model fields already exist) | 2–3 days |
| Content | Build core exercise library (intervals → Roman numerals) | Ongoing |

### Phase 3 — Monetization (After pilot validates the product)
| Priority | Task | Effort |
|---|---|---|
| High | Role field + `.edu` teacher verification at registration | 1 day |
| High | Email verification flow | 1–2 days |
| High | Stripe Checkout + subscription management | 3–4 days |
| High | Paywall on Group join (student side) | 1 day |

### Phase 4 — Growth
| Priority | Task | Effort |
|---|---|---|
| Medium | Expand exercise types (species counterpoint, harmonic dictation) | 2–3 weeks each |
| Medium | Frontend modernization (Vite/htmx) | Ongoing |
| Long-term | React/Vue SPA rewrite (if mobile or richer interactivity needed) | Months |

---

## Related Documents

- [chorale_exercises_plan.md](chorale_exercises_plan.md) — Chorale curriculum design
- [chorale_future_improvements.md](chorale_future_improvements.md) — Pending chorale features
- [lms_student_ux_assessment.md](lms_student_ux_assessment.md) — Student UX assessment
- [grading_pipeline.md](grading_pipeline.md) — Grading architecture
