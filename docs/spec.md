# HarmonyLab Product Specification

*Written: 2026-04-02*

This document specifies the features needed to take HarmonyLab from its current state to a deployable, classroom-ready music theory platform. It is derived from an architectural review of the codebase and product planning discussions.

For the full strategic rationale behind these decisions, see [hosting_and_roadmap.md](hosting_and_roadmap.md).

---

## Product Vision

HarmonyLab is a music theory practice platform with MIDI grading, staff notation, and chorale analysis. The goal is to replace Artusi as the standard classroom tool for undergraduate music theory — with a richer exercise engine, a built-in content library, and a freemium model where anyone can practice for free but classroom features (enrollment, grading, progress tracking) require a subscription.

**Target users:**
- **Students** — practice exercises, complete assigned work, track progress
- **Teachers** — assign courses, track student completion, build or adopt content from the library
- **Self-learners** — free practice without a class context

**Competitive framing vs. Artusi:**
- Artusi's strength: large built-in content library, teachers don't have to build anything
- HarmonyLab's strength: more sophisticated exercise engine (MIDI, chorales, VexFlow notation)
- HarmonyLab's gap to close: build the content library, fix the classroom UX

---

## Current Tech Stack (Reference)

| Layer | Current | Notes |
|---|---|---|
| Backend | Django 5.2 LTS | Supported until April 2028 |
| Python | 3.12 | |
| Database | PostgreSQL | Good, keep |
| Frontend | jQuery + RequireJS + Bootstrap 4 | Dated but functional |
| Music notation | VexFlow | Core, keep |
| Audio | Tone.js | Core, keep |
| Static files | WhiteNoise | Good, keep |
| Hosting | Fly.io | Deployed; CI/CD via GitHub Actions |

---

## Data Model (Existing, No Changes Needed for Pilot)

```
User
  ├── managed_groups (Group.manager) → teacher role
  └── participant_groups (Group.members) → student role

Group
  ├── manager: User (teacher)
  ├── members: [User] (students)
  └── join_code: str  ← ADD THIS (see spec below)

Course
  ├── authored_by: User
  ├── visible_to: [Group]
  ├── playlists: [Playlist] (ordered)
  ├── timely_credit, tardy_credit, late_credit, tardy_threshold  ← already exists
  └── open: bool (broadcast to all connections)

Playlist
  └── exercises: [Exercise] (ordered)

Exercise
  └── data: JSON (exercise definition)

PerformanceData
  ├── user: User
  ├── playlist: Playlist
  ├── course: Course
  └── data: JSON (per-attempt records)
```

The classroom relationship, grading weights, and per-student performance data are fully modeled. What is missing is the UI to create, browse, and interact with this data.

---

## Phase 1 — Deployment ✅ COMPLETE

**Goal:** Get the app running on infrastructure the owner controls.

### 1.1 Hosting Migration ✅

Deployed to **Fly.io** (`monteverdi`, `ord` region). CI/CD via GitHub Actions (`fly-deploy.yml`) auto-deploys on push to `main`. `Dockerfile` and `fly.toml` are in the repo root. Estimated cost: ~$5–8/mo.

### 1.2 Django + Python Upgrade ✅

Upgraded to Django 5.2 LTS (supported until April 2028) + Python 3.12. All breaking dependencies updated (whitenoise ≥6.0, dj-database-url ≥2.0, psycopg2-binary ≥2.9, chardet ≥5.0).

---

## Phase 2 — College Pilot

**Goal:** Usable by a real class of students at the owner's college. No payment required yet.

### 2.1 Group Join Codes

**Problem:** Teachers currently add students to groups manually by email lookup. This doesn't scale to a class of 30 and creates friction for students who haven't used the app before.

**Solution:** Join codes — a short alphanumeric code a teacher shares (e.g. in a syllabus), which students enter to self-enroll.

**Data change:**
```python
# Group model — add one field
join_code = models.CharField(max_length=16, unique=True, blank=True, null=True)
```

**New views needed:**
- `POST /groups/join/` — accepts `join_code`, adds current user to the matching Group's members
- Auto-generate `join_code` on Group creation (e.g. `MUSIC201-F26`, or random 6-char code)
- Teacher can view/regenerate their group's join code on the group edit page

**Acceptance criteria:**
- Student registers, enters join code, is added to group, can see the teacher's assigned courses
- Teacher sees student in their group roster
- Invalid codes show a clear error message

---

### 2.2 Student "My Work" View

**Problem:** The current "Courses By Other Users" shows a flat list of all courses from anyone who has granted the student content access — enrolled courses and random shared content mixed together. Students can't distinguish assigned work from browsable content.

**Solution:** A dedicated "My Work" page that shows only courses the student is actively enrolled in (via Group membership).

**New view:** `GET /dashboard/my-work/`

**Logic:**
```python
# Courses where student is in an assigned group
enrolled_courses = Course.objects.filter(
    visible_to__members=request.user
).distinct()
```

**Page structure:**
```
My Work
├── [Course Title]
│   ├── Status: 3/8 playlists complete
│   ├── [Playlist 1] ✓ Complete (2026-03-15)
│   ├── [Playlist 2] → In Progress
│   └── [Playlist 3] Due: 2026-04-10
└── [Course Title 2]
    └── ...
```

**Data source:** `PerformanceData` (already populated on exercise completion). Completion = at least one passing attempt recorded for each exercise in the playlist.

**Acceptance criteria:**
- Only shows courses the student is enrolled in via a Group
- Shows completion status per playlist (not started / in progress / complete)
- Shows due dates if set by teacher
- Links directly to the playlist player
- Replaces "Courses By Other Users" as the primary post-login destination for students

---

### 2.3 Public Content Library

**Problem:** HarmonyLab has no built-in content. A teacher starting fresh must build every exercise, playlist, and course themselves. This is the primary reason to use Artusi instead.

**Solution:** A browsable library of all `is_public` content, organized by topic and type.

**New view:** `GET /library/`

**Page structure:**
```
Content Library
├── Filter by: [Topic ▾] [Type ▾] [Level ▾]
├── Courses (3)
│   ├── Music Theory I — Intervals & Triads
│   │   by [author] · 8 playlists · Public
│   │   [Preview] [Copy to My Courses]
│   └── ...
├── Playlists (12)
│   └── ...
└── Exercises (47)
    └── ...
```

**Query:**
```python
Course.objects.filter(is_public=True).order_by('title')
Playlist.objects.filter(is_public=True).order_by('name')
Exercise.objects.filter(is_public=True).order_by('description')
```

**Filtering:** By topic tag (see 2.5), exercise type, difficulty level.

**Acceptance criteria:**
- Any logged-in user can browse the library
- Works without being connected to the content author
- Filtering by topic narrows results correctly
- "Copy to My Courses" clones the course (see 2.4)

---

### 2.4 Course Clone / Copy

**Problem:** Teachers can't easily adopt library content — they'd have to manually recreate every exercise and playlist.

**Solution:** One-click clone of a public course (or playlist) into the teacher's own account for customization.

**New view:** `POST /library/clone-course/<course_id>/`

**Logic:**
- Deep-clone the Course, all its PlaylistCourseOrdered entries, and all PlaylistExerciseOrdered entries
- Set `authored_by = request.user` on the cloned Course and Playlists
- Set `is_public = False` on cloned content by default (teacher's customized version is private)
- Exercises are shared by reference (not cloned) — they're the atomic units
- Redirect to the cloned course's edit page

**Acceptance criteria:**
- Teacher can clone any public course in one click
- Cloned course appears in teacher's course list, editable
- Original course is unchanged
- Cloned exercises are referenced, not duplicated

---

### 2.5 Content Tagging

**Problem:** Without tags, the library is a flat unsorted list. Browsing 50 exercises for "triads in root position" is unusable.

**Solution:** A simple tag system on exercises and playlists, with predefined topic tags.

**Data change:**
```python
# Exercise and Playlist models — add one field each
tags = ArrayField(models.CharField(max_length=32), default=list, blank=True)
```

**Predefined tags (controlled vocabulary):**
```
intervals, scales, triads, seventh-chords, voice-leading,
roman-numerals, secondary-dominants, counterpoint,
harmonic-dictation, melodic-dictation, rhythm, sight-singing
```

**UI:**
- Tag selector on exercise/playlist edit forms (multi-select, predefined list)
- Filter by tag on the library page
- Tags displayed as small labels on library cards

**Acceptance criteria:**
- Tags can be added/removed by the content author
- Library page filters correctly by tag
- Tags are visible in search results

---

### 2.6 Teacher Gradebook

**Problem:** The existing `course_activity_view` is teacher-only and partially functional, but the UI is basic and not student-facing.

**Solution:** Polish the existing view and ensure it shows what a teacher actually needs per assignment period.

**Existing view:** `apps/dashboard/views/courses.py:255` (`course_activity_view`)

**What exists:**
- Dynamic table with one column per playlist
- Shows completion status per student per playlist
- Filters by group

**What needs improvement:**
- Show score/grade alongside completion (currently shows pass date or "TO DO")
- Show due date status (timely / tardy / late) using existing `timely_credit` fields
- Export to CSV (for uploading to institution gradebook)
- Accessible without needing admin panel knowledge

**Acceptance criteria:**
- Teacher sees a table: rows = students, columns = playlists
- Each cell shows: complete/incomplete + score if complete + on-time/late status
- Export to CSV works
- Teacher can filter by group if they have multiple sections

---

### 2.7 Due Date UI

**Problem:** `Course` already has `timely_credit`, `tardy_credit`, `late_credit`, `tardy_threshold` fields, and `PlaylistCourseOrdered` likely has or needs `due_date`. The grading logic exists but there is no UI to set due dates.

**What needs to be built:**
- Date picker per playlist in the course edit form
- Due date visible to students on the "My Work" page
- Late/tardy status calculated and shown in the gradebook

**Data:** Add `due_date = DateTimeField(null=True, blank=True)` to `PlaylistCourseOrdered` if not already present.

**Acceptance criteria:**
- Teacher can set a due date for each playlist in a course
- Student sees due date on "My Work" page
- Gradebook shows timely/tardy/late status per submission

---

### 2.8 Mouse & Keyboard Input

**Problem:** WebMIDI only works in Chrome/Edge and requires a MIDI controller. This blocks students on Firefox, Safari, or without hardware.

**Solution:** Three complementary input methods, all usable without MIDI hardware.

#### 2.8a On-Screen Piano Keyboard

An SVG/HTML piano keyboard rendered below the staff. Clicking a key triggers `noteOn` / `noteOff` events identical to MIDI input.

**Implementation:** The grader already listens to `noteOn(midi)` / `noteOff(midi)` events. The on-screen keyboard just needs to fire those same events. No changes to the grader.

**Acceptance criteria:**
- Piano keyboard visible below staff when no MIDI device is detected (or always, as a toggle)
- Clicking a key registers the note in the grader identically to MIDI input
- Keyboard range matches the exercise's expected note range

#### 2.8b Computer Keyboard Note Entry

Letter keys for pitch, number keys for octave, like Sibelius/Finale entry.

**Key mapping:**
```
a b c d e f g  →  A B C D E F G (natural)
shift + above  →  sharp
ctrl + above   →  flat
1–8            →  octave number
```

**Implementation:** Key listener fires `noteOn` / `noteOff` via the same interface as MIDI.

**Acceptance criteria:**
- Pressing `c` + `4` plays middle C (MIDI 60)
- Accidentals work via modifier keys
- Does not conflict with browser shortcuts

#### 2.8c Clickable Staff Notation

Clicking a note head in the VexFlow-rendered score "plays" that note — useful for checking what a note sounds like, not for grading.

**Scope:** Read-only / audio preview only. Not a grading input method. Lower priority than 2.8a and 2.8b.

---

## Phase 3 — Monetization

**Goal:** Charge for classroom features after the pilot validates the product.

**Model:** Free for self-study. Paid for being in a class (student pays, teacher is free).

The paywall attaches to the **Group** — the classroom unit — not to content access.

### 3.1 User Role Field

Add a `role` field to `User` at registration time:

```python
class UserRole(models.TextChoices):
    STUDENT = 'student', 'Student'
    TEACHER = 'teacher', 'Teacher'

role = models.CharField(
    max_length=16,
    choices=UserRole.choices,
    default=UserRole.STUDENT
)
```

Registration form adds a "I am a teacher / I am a student" choice. Teachers must provide a `.edu` email address (one-line validation). Non-.edu teacher requests handled manually.

Do **not** use two booleans (`is_teacher`, `is_student`) — that's an anti-pattern (both=True is undefined).

### 3.2 Email Verification

Currently accounts activate immediately on registration. For paid accounts, email verification is required before activation.

**Flow:**
1. User registers → account created with `is_active=False`
2. Verification email sent with signed token link
3. User clicks link → `is_active=True`
4. User can now log in

Django's built-in `PasswordResetView` infrastructure handles token signing — reuse that pattern.

### 3.3 Stripe Integration

**What triggers payment:** A student using a join code to enter a teacher's group.

**Flow:**
1. Student enters join code
2. If Group has active subscription OR student already has active subscription → enroll
3. If not → redirect to Stripe Checkout (semester subscription, ~$15–25)
4. On payment success → enroll student in group

**Data change:**
```python
# Option A: subscription on Group (institution pays)
Group.stripe_subscription_id = CharField(...)

# Option B: subscription on User (student pays per-student)
User.stripe_subscription_id = CharField(...)
User.subscription_status = CharField(choices=['active', 'cancelled', 'past_due'])
```

Option B (student pays) is simpler to implement and matches the Artusi model.

**Library:** `dj-stripe` handles most of the Stripe/Django integration.

**Acceptance criteria:**
- Students can pay and enroll in one flow
- Teachers are never charged
- Subscription status is checked when accessing class features
- Students can cancel and manage their subscription

### 3.4 Access Control

A simple decorator/mixin that checks subscription status:

```python
@requires_active_subscription
def my_work_view(request):
    ...
```

Free actions (no check needed): browsing library, solo practice, creating own content.
Paid actions: joining a group, submitting performance data in a course context, accessing class gradebook.

---

## Phase 4 — Growth

These are not scheduled — they depend on what the pilot reveals.

### 4.1 New Exercise Types

| Type | Description | Depends on |
|---|---|---|
| Species counterpoint | Write 1st–4th species against a cantus firmus | New grader + exercise type |
| Harmonic dictation | Hear a progression → identify chords | Audio playback + new grader |
| Melodic dictation | Hear a melody → notate it | Audio playback + notation input |

Each is a significant engineering effort (2–3 weeks minimum). Build in the order that the content library needs them.

### 4.2 Frontend Modernization

- Replace RequireJS with Vite (build step, ES modules, hot reload)
- Replace Bootstrap 4 with Bootstrap 5 or Tailwind
- Add htmx for partial-page updates without a full SPA

This is infrastructure work with no user-visible feature. Do it when the developer experience becomes a bottleneck.

### 4.3 Full SPA Rewrite (Optional, Long-term)

- Replace Django templates with React or Vue
- Django becomes a REST API
- Enables mobile, richer interactivity
- The music engine (VexFlow, Tone.js, graders) carries over unchanged

Only pursue this if mobile access or more complex UI interactions are required and incremental improvements have hit their ceiling.

---

## Content Library — Build Plan

The content itself is a teacher's task, not an engineering task. Once the library infrastructure (Phase 2.3–2.5) is in place, exercises can be created at the rate of dozens per hour.

**Semester 1 content target (buildable with existing exercise types):**

| Unit | Playlists | Exercises each | Total |
|---|---|---|---|
| Intervals — identification | 3 (by size, by quality, mixed) | 20 | 60 |
| Intervals — notation | 2 | 20 | 40 |
| Triads — identification | 4 (by quality, by inversion, mixed) | 20 | 80 |
| Triads — notation | 2 | 20 | 40 |
| Seventh chords — identification | 3 | 20 | 60 |
| Seventh chords — notation | 2 | 20 | 40 |
| Roman numeral analysis | 4 (by key, by complexity) | 15 | 60 |
| Voice leading — SATB basics | 3 | 10 | 30 |
| **Total** | **~23 playlists** | | **~410 exercises** |

This is one semester's worth of content. Creating the exercise-building workflow efficiently first (fast forms, bulk import, duplication tools) will make populating this feasible.

---

## Summary: What to Build and When

| Phase | Feature | Effort | Blocked by |
|---|---|---|---|
| **1** | Deploy to new hosting | 1–2 days | Nothing |
| **1** | Django 2.2 → 5.2 + Python 3.10 → 3.12 | 1–2 weeks | Nothing |
| **2** | Group join codes | 1–2 days | Deployment |
| **2** | Student "My Work" view | 2–3 days | Deployment |
| **2** | Public library page | 2–3 days | Deployment |
| **2** | Course clone/copy | 1–2 days | Library page |
| **2** | Content tagging | 1–2 days | Library page |
| **2** | On-screen piano + keyboard input | 3–5 days | Deployment |
| **2** | Teacher gradebook polish | 3–5 days | Deployment |
| **2** | Due date UI | 2–3 days | Deployment |
| **2** | Build content library (content task) | Ongoing | Library page + tags |
| **3** | Role field + .edu check | 1 day | Pilot complete |
| **3** | Email verification | 1–2 days | Pilot complete |
| **3** | Stripe integration | 3–4 days | Role field |
| **3** | Subscription access control | 1 day | Stripe |
| **4** | New exercise types | 2–3 weeks each | Pilot feedback |
| **4** | Frontend modernization | Ongoing | — |

---

## Related Documents

- [hosting_and_roadmap.md](hosting_and_roadmap.md) — Strategic rationale and background
- [chorale_exercises_plan.md](chorale_exercises_plan.md) — Chorale exercise curriculum
- [chorale_future_improvements.md](chorale_future_improvements.md) — Pending chorale features
- [lms_student_ux_assessment.md](lms_student_ux_assessment.md) — Student UX assessment
- [grading_pipeline.md](grading_pipeline.md) — Grading architecture
