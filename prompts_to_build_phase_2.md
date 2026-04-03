2.1 Group join codes

Please read `docs/plan.md` and `docs/spec.md` (section 2.1), then implement group join codes.

Add a `join_code` field to the `Group` model in `apps/accounts/models.py`, auto-generate it on Group creation, display it on the group edit page so a teacher can copy it, and add a view + UI for students to enter a code and be added to the group automatically.

Read the existing Group model and dashboard views before making changes.
2.2 Student "My Work" view

Please read `docs/plan.md` and `docs/spec.md` (section 2.2), then build the student "My Work" view.

Create a new dashboard view that shows only courses the logged-in student is enrolled in via Group membership (not all shared content). Show completion status per playlist using existing PerformanceData. This should replace "Courses By Other Users" as the default post-login destination.

Read the existing courses_by_others view and PerformanceData model before building.
2.3 Public content library

Please read `docs/plan.md` and `docs/spec.md` (section 2.3), then build the public content library page.

Create a `/library/` page that lists all is_public courses, playlists, and exercises. It should be browsable without needing a connection to the author. Add type filtering. Tag filtering can be stubbed out (tags come in step 2.5).

Read the existing dashboard list views and templates before building.
2.4 Course clone / copy

Please read `docs/plan.md` and `docs/spec.md` (section 2.4), then implement course cloning.

Add a "Copy to My Courses" action on the library page (from step 2.3) that deep-clones a public course and its playlist structure into the current user's account. Exercises should be referenced not duplicated. Set authored_by to the current user and is_public to False on the clone.

Read the Course, Playlist, and their through models before building.
2.5 Content tagging

Please read `docs/plan.md` and `docs/spec.md` (section 2.5), then add content tagging.

Add a `tags` ArrayField to the Exercise and Playlist models. Add a tag selector to their edit forms using a predefined vocabulary: intervals, scales, triads, seventh-chords, voice-leading, roman-numerals, secondary-dominants, counterpoint, harmonic-dictation, melodic-dictation, rhythm, sight-singing. Wire the tags to the library page filter from step 2.3.

Read the existing Exercise and Playlist models and their edit forms before building.
2.6 Teacher gradebook polish

Please read `docs/plan.md` and `docs/spec.md` (section 2.6), then improve the teacher gradebook.

The existing course_activity_view in apps/dashboard/views/courses.py already shows a completion table. Add score/grade alongside completion, show on-time/tardy/late status using the existing timely_credit/tardy_credit/late_credit fields on Course, and add CSV export.

Read the existing view and Course model carefully before modifying.
2.7 Due date UI

Please read `docs/plan.md` and `docs/spec.md` (section 2.7), then add due date UI.

Add a `due_date` DateTimeField to PlaylistCourseOrdered if not already present. Add a date picker per playlist to the course edit form. Show due dates on the student "My Work" view. Show timely/tardy/late status in the gradebook using the threshold fields that already exist on Course.

Read PlaylistCourseOrdered, the course edit form, and the Course model before building.
2.8 Mouse & keyboard input

Please read `docs/plan.md` and `docs/spec.md` (section 2.8), then add non-MIDI input methods.

Two inputs needed:
1. An on-screen SVG/HTML piano keyboard that fires noteOn/noteOff events identical to MIDI input — show it when no MIDI device is detected
2. Computer keyboard note entry: letter keys A–G for pitch, number keys for octave (like Sibelius), modifier keys for accidentals

The grader already listens to noteOn(midi)/noteOff(midi) — these inputs just need to fire those same events. Read lab/static/js/src/ to understand the existing MIDI input handling before building.
