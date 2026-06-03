---
run_id: a3f82c1d
date: 2026-05-28
frame: assumption-breaking and reframing
topic: Improvement ideas for Monteverdi Music
status: complete
---

# Assumption-Breaking Ideas — Monteverdi Music

**Frame:** What is being treated as fixed that is actually a choice? Reframe one level up or sideways.

**Grounding context:**
- Codebase: Django/Python backend, RequireJS/VexFlow/Tone.js frontend, MIDI grading engine
- Key constraints: Sep 2026 pilot hard deadline; MIDI-only input; UMTO is canonical exercise representation
- Inert systems: skill tag adaptive engine (data captured, not acted on); `problems[]` array (captured, not surfaced); per-attempt timing (captured, not displayed)
- Competitor framing: Artusi/Harmonia use notation-entry UI; Monteverdi Music's MIDI input is differentiator and limitation

**Topic axes:**
1. mastery feedback loop
2. exercise corpus & curriculum sequencing
3. student-facing UX
4. teacher & course management
5. grading infrastructure

---

## Ideas

### 1. Flip the Exercise-Generation Pipeline: Let Students Generate the Next Exercise From Their Own Error Data

**summary:** The current assumption is that instructors or management commands pre-generate every exercise. But the `problems` array from `ChoraleGrader` already records exactly which onset windows a student failed. Reframing: the grader output is not just a score — it is a spec for the student's next exercise. A lightweight generator could slice the chorale at the failed windows, package those measures as a new micro-exercise, and serve it immediately. Students who struggle at measures 3-4 always practice measures 3-4 next, not measures 1-2 again.

**axis:** mastery feedback loop

**basis:** `direct:` `lab/static/js/src/models/chorale_grader.js` captures `problems[]` per-window with `count.correct`/`count.incorrect` on every completion. `docs/adaptive_learning.md` describes the adaptive serving algorithm but it operates at the skill-tag granularity (whole exercises), not intra-exercise window granularity. The gap between what the grader captures and what the adaptive engine acts on is documented but unaddressed.

**why_it_matters:** Every current retry sends the student back to measure 1 even if they only failed measure 4. This is pedagogically wasteful and is the kind of precision that MIDI-graded practice uniquely enables — a human teacher could never slice exercises this finely at scale.

**meeting_test:** Requires deciding whether the exercise corpus is static (pre-generated) or dynamic (partially runtime-generated), which affects UMTO conformance, storage, and the Sep 2026 pilot scope — warrants team discussion.

---

### 2. Reframe Teacher Onboarding: Ship a "Clone a Semester" Course Template, Not a Course Builder

**summary:** The current assumption is that instructors need a course-builder UI to configure their curriculum. But the actual bottleneck before the Sep 2026 pilot is that a teacher arriving at Monteverdi Music has nothing to assign. The reframe: ship one canonical undergraduate theory curriculum as a pre-built course — Unit 1 through Unit 11, playlists filled, due dates templated relative to a semester start date. The instructor inputs one date (first day of class) and gets a fully-populated course. Course builder becomes a customization path, not the entry path.

**axis:** teacher & course management

**basis:** `direct:` `docs/hosting_and_roadmap.md` §4 identifies "no built-in library" as "the most important content gap to close before the pilot" and notes "teachers don't have to build anything; they assign from a library" as the Artusi advantage. `docs/feature-status.md` shows the exercise corpus is growing (Bach, Clausulae, Units 1-11); the missing piece is not exercises but a pre-assembled course container. `external:` Artusi's teacher onboarding model: teachers adopt and adapt a library course rather than build from scratch (cited in `docs/hosting_and_roadmap.md`).

**why_it_matters:** A teacher who spends 3 hours configuring a course before seeing any student value is a teacher who doesn't pilot the product. The template collapses time-to-first-value from hours to minutes and repositions Monteverdi Music from "tool" to "ready-to-teach curriculum."

**meeting_test:** This is a product positioning decision as much as an engineering one — it affects what "done" means for the Sep 2026 deadline and how the pilot is measured.

---

### 3. MIDI Is a Feature, Not a Prerequisite: Add Click-to-Play Note Input Directly on the Score

**summary:** The current assumption is that MIDI keyboard input is the interaction model. In practice, WebMIDI requires Chrome/Edge and physical hardware, blocking every Safari/Firefox/iOS user. The reframe: clicking a note head in the rendered VexFlow score should trigger the same `noteOn` event that a MIDI keypress sends. This is not a "mouse piano" — it is direct manipulation of the score notation the student is already looking at. MIDI remains for students who have it; click input becomes the universal fallback.

**axis:** student-facing UX

**basis:** `direct:` `docs/hosting_and_roadmap.md` §4 lists "clickable staff notation — click a note head to play it" as the highest-leverage near-term feature and explicitly calls it "buildable on top of VexFlow + the existing grader infrastructure without rearchitecting." `docs/lms_student_ux_assessment.md` §7 flags "MIDI keyboard input requires dedicated hardware" as a likely mobile/accessibility gap. `reasoned:` The grader infrastructure is already decoupled from input device — `ChoraleGrader.noteOn(midi)` takes a MIDI integer, not a device event. Any click handler that resolves a VexFlow note head to its MIDI pitch can call the same method.

**why_it_matters:** Browser/hardware gating is an adoption ceiling, not a design choice. Removing it expands the addressable classroom from "students who own MIDI controllers" to "all students" — and is the single change most likely to determine whether the Sep 2026 pilot is viable.

**meeting_test:** Whether this ships before the Sep 2026 pilot is a scope/priority decision that the whole team needs to align on.

---

### 4. Grade Style, Not Just Correctness: Add a Voice-Leading Rule Checker as a Second Grading Layer

**summary:** The current assumption is that grading means "did the student play the right pitches." But a student can play all correct pitches in a harmonization exercise while writing parallel fifths, doubling the leading tone, or making a large leap in an inner voice. The reframe: correctness is the floor, not the ceiling. A second-pass style checker — triggered after the pitch grader passes — could flag voice-leading violations on the completed response and display them as warnings without blocking completion. This is the difference between "you played the right notes" and "you realized the figured bass with good voice leading."

**axis:** grading infrastructure

**basis:** `direct:` `docs/feature-status.md` lists "Counterpoint checking — parallel fifths, octaves, doubled leading tones" as Planned. `apps/exercises/management/commands/generate_harmonization_from_clausulae.py` generates harmonization exercises that lock the bass and require the student to realize upper voices — exactly the context where voice-leading violations occur. `external:` Harmonia (competitor) grades both pitch correctness and voice-leading rules simultaneously. Monteverdi Music's onset-window data structure makes inter-onset voice-leading checks (parallel motion requires comparing two consecutive windows) more natural than static chord-entry systems.

**why_it_matters:** The Sep 2026 counterpoint class pilot requires this. Students who pass the pitch grader but fail voice-leading rules are getting false confidence; the teaching value collapses if the tool doesn't catch what the instructor would catch.

**meeting_test:** This gates the counterpoint class use case entirely — the Sep 2026 pilot is at risk without it.

---

### 5. The Skill Map Is Invisible to the Person Who Assigns Work: Surface It to Instructors as a Class Heatmap

**summary:** The current assumption is that skill-tag data is a student-facing adaptive engine concern. Reframe one level up: the skill map is the most actionable data the instructor has, and it should be their primary view. An instructor teaching 30 students who all show `Secondary_Dominant` at `attempted` level can make a targeted pedagogical decision before the next class. Today that signal lives in the database and nowhere on screen. A class-level skill heatmap — one row per skill, one column per student, color-coded by mastery level — turns unread analytics into a teaching instrument.

**axis:** teacher & course management

**basis:** `direct:` `docs/adaptive_learning.md` §4 describes the Visual Skill Map as the "student's primary progress dashboard" — framed as student-facing only. The skill tag system (26+ tags, GIN-indexed on `Exercise.skill_tags`, mastery level tracked per-student) is fully built but not surfaced to instructors. `docs/lms_student_ux_assessment.md` §8 notes the gradebook shows only pass/fail per playlist, not concept-level breakdown. `external:` Duolingo for Schools shows a class skill heatmap as its primary teacher view — teachers navigate directly to "who needs help with X" rather than browsing per-student histories.

**why_it_matters:** The teacher is the buyer. "Save grading time and see what your students know" is the value proposition. A pass/fail gradebook does the first; it does not do the second. A class skill heatmap does both and creates a qualitative step-change in teacher ROI.

**meeting_test:** This directly impacts the buyer persona's willingness to adopt before the pilot — could be the single teacher-facing feature that closes the first paying classroom.

---

### 6. Exercises Are One-Way — Add an "Explain This Chord" Layer So the Score Argues Back

**summary:** The current assumption is that exercises are problems with answers: the student guesses, the grader confirms. But in music theory pedagogy, understanding why V7 resolves to I is more durable than knowing that it does. The reframe: each `chorale_identification` slice with a known Roman numeral analysis (already stored in the UMTO `analysis` field) could surface a short text explanation when the student clicks a "Why?" button on any labeled chord. The explanation is pre-computable from the UMTO analysis slices — no LLM required. "This is V7/IV because the bass is on the fourth scale degree and the figured bass indicates a dominant seventh quality."

**axis:** student-facing UX

**basis:** `direct:` `docs/feature-status.md` lists "'Explain this' button" as Planned (item 2.13). UMTO exercises store `analysis` slices with Roman numeral, figured bass, and key data — the raw material for explanations is already present in every exercise payload. `reasoned:` The explanation can be templated from structured data: `"This is {RN} because the bass is {bass_pitch} (scale degree {scale_degree}) and the chord quality is {quality}."` No AI generation needed for a first version; slot-filling is deterministic from existing analysis fields.

**why_it_matters:** "Explain this" closes the feedback loop that currently only goes as far as "correct/incorrect." Students who understand harmonic logic can transfer it to novel contexts; students who memorize answers cannot. This is a pedagogical differentiator against Artusi, which grades but does not explain.

**meeting_test:** Achievable before the Sep 2026 pilot; the question is scope (template-based vs. richer explanation) — worth a team discussion to set the right bar.

---

### 7. Replace Exercise-Count Progress With Fluency-Rate: Notes Correct Per Minute at Target Accuracy

**summary:** The current assumption is that "exercises completed" and "skill tags at mastered level" are the right progress metrics. But a student who completes a chorale exercise in 45 minutes with 20 retries has not demonstrated fluency — they have demonstrated persistence. The reframe: fluency in music theory performance is a rate, not a binary. The chorale grader already records completion time (`endTimer()`) and error counts. Displaying "average notes correct per minute over last 3 attempts" makes practice quality visible in a way that completion count obscures. A student improving from 12 notes/minute to 24 notes/minute is gaining fluency even if they haven't yet "passed."

**axis:** mastery feedback loop

**basis:** `direct:` `docs/grading_pipeline.md` §CIR pipeline confirms `startTimer` fires on first note, `endTimer()` on completion — timing data is already captured per attempt. `docs/adaptive_learning.md` §2 describes a mastery decay model (exponential decay by time since last practice) but uses no fluency-rate signal — the decay parameter is time-based, not performance-speed-based. `external:` CBM (Curriculum-Based Measurement), a standard K-12 fluency assessment framework, uses rate metrics (correct responses per minute) rather than binary pass/fail as the primary progress indicator. ABA "precision teaching" research demonstrates that rate-based metrics predict retention and transfer more reliably than accuracy-only scores.

**why_it_matters:** The mastery engine exists but is inert — the data shape that feeds it is too coarse. Adding a fluency-rate dimension would make the adaptive engine act in a more pedagogically grounded way, while also giving students a concrete, improving number to work toward rather than a binary unlock/not-unlocked status.

**meeting_test:** This reframes what "mastery" means in the database and the UI — downstream implications for the adaptive serving algorithm and the teacher-facing skill heatmap make it a team-level conversation.

---

## Axis Coverage

| Axis | Ideas |
|------|-------|
| mastery feedback loop | 1, 7 |
| student-facing UX | 3, 6 |
| teacher & course management | 2, 5 |
| grading infrastructure | 4 |
| exercise corpus & curriculum sequencing | — (no direct survivor; Ideas 1 and 2 touch it tangentially) |
