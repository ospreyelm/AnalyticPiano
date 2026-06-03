---
date: 2026-05-28
topic: monteverdi-open-ideation
focus: open-ended
mode: repo-grounded
---

# Ideation: Monteverdi Music — Open Ideation

## Grounding Context

**Project shape:** Python/Django backend + JavaScript/VexFlow frontend. Django apps: accounts, dashboard, exercises, student. Frontend in lab/. Music corpus in data/, clausulae/, compendium/.

**Strategy approach:** Win by combining broad importable corpus (Bach, Handel, Clausulae, Partimenti) with automated real-time grading so instructors build curriculum without writing exercises from scratch; students get instant feedback.

**Active tracks:** Exercise corpus, Grading infrastructure, Adaptive engine, Teacher tools.

**Milestone:** Pilot with live class — fall 2026 semester (2026-09-01).

**Key gaps:**
- `record_attempt()` never called after submission → mastery engine inert
- Skill tag vocabulary drift (`unit:9_Dominant_Seventh` vs `Dominant_Seventh`) → adaptive queries silently broken
- `applySkillFilter` JS hardcoded for Unit 9 only → multi-unit playlists broken
- No `create_unit_playlist` command → each new unit requires bespoke scripting
- Student progress UX (score card, unit progress page) designed but not built
- No MIDI fallback for Safari/Firefox/iOS
- LMS integration absent; competitors (Artusi, Flat, Harmonia) all have Canvas/Google Classroom

**Competitor signals:**
- Artusi and Harmonia: notation-entry only, no MIDI — MIDI input is a genuine differentiator
- Adaptive sequencing: claimed by all, implemented by none at onset-window granularity
- LMS integration: near-universal among competitors; university procurement requirement
- Gradescope per-step breakdown: documented driver of instructor adoption

## Topic Axes

1. mastery feedback loop
2. exercise corpus & curriculum sequencing
3. student-facing UX
4. teacher & course management
5. grading infrastructure

## Ranked Ideas

### 1. Wire the Mastery Submission Hook
**Description:** `record_attempt()` is fully implemented in `apps/exercises/mastery.py` (5-level DAG, decay algorithm, prerequisite unlock) but is never called from `PerformanceData` or `IdentificationAttempt` save. One hook activates the entire adaptive engine, skill unlock DAG, and mastery decay system simultaneously.
**Axis:** mastery feedback loop
**Basis:** `direct:` `apps/exercises/mastery.py` — `record_attempt()` exists but has no callers in the submission path. `docs/feature-status.md` explicitly flags this as the critical wiring gap.
**Rationale:** Single highest-leverage fix in the codebase. Every adaptive feature (sequencing, error routing, progress display) is inert until this runs. Skill tag vocabulary drift (`unit:9_Dominant_Seventh` vs `Dominant_Seventh`) must be reconciled simultaneously.
**Downsides:** Prefixed-tag drift means some exercises will still be silently skipped by `record_attempt` until tag normalization is also fixed.
**Confidence:** 95%
**Complexity:** Low
**Status:** Explored

### 2. Taxonomy JSON as Single Source of Truth for Curriculum Policy
**Description:** `exercise_definition.js:14-89` has `UNIT_ALLOWED_ANSWERS` hardcoded for units 9-18. `skill_graph.py:155` has `MASTERY_TAGS` declared independently. `music_theory_taxonomy_with_branches.json` exists at root but neither file reads from it. A build-time or runtime derivation from the JSON eliminates three-way drift that recurs with every new unit.
**Axis:** exercise corpus & curriculum sequencing
**Basis:** `direct:` `lab/static/js/src/models/exercise_definition.js:14-89`; `apps/exercises/skill_graph.py:155`; `music_theory_taxonomy_with_branches.json` at repo root.
**Rationale:** Curriculum correctness becomes structural rather than disciplinary. Every future unit import costs zero additional cross-file maintenance.
**Downsides:** Requires architecture decision on code-gen vs. runtime read. Changes UNIT_ALLOWED_ANSWERS from static to derived.
**Confidence:** 92%
**Complexity:** Medium
**Status:** Unexplored

### 3. Per-Window Error Overlay on Post-Exercise Score Sheet
**Description:** After a chorale exercise completes, show each onset window highlighted green/red on the VexFlow score with the Roman numeral label for that window. The `problems[]` array in `chorale_grader.js` already captures this data; it's a rendering decision, not a new data collection problem.
**Axis:** student-facing UX
**Basis:** `direct:` `lab/static/js/src/models/chorale_grader.js` `problems[]` array (CLAUDE.md Feature 3). LMS assessment rated learning value 2/5. `external:` Gradescope per-rubric-item breakdown as documented driver of instructor adoption.
**Rationale:** The data already flows. Exposing it turns binary pass/fail into a diagnostic that instructors can show to students and demonstrate platform value over Artusi/Harmonia.
**Downsides:** Requires `problems[]` to be serialized into `PerformanceData` (currently not happening). VexFlow overlay design needs care.
**Confidence:** 88%
**Complexity:** Low-Medium
**Status:** Unexplored

### 4. `create_unit_playlist` Management Command
**Description:** An idempotent Django management command (`--unit N --riemenschneider A-B --author email --mode roman|figures|play`) that reads the unit's allowed answers from the taxonomy JSON, runs `import_bach_phrases`, creates a `Playlist(skill_tags=['unit:N'])`, and links exercises. Replaces all one-off batch scripts.
**Axis:** exercise corpus & curriculum sequencing
**Basis:** `direct:` CLAUDE.md Blocker 2 documents this verbatim with the proposed CLI interface. `scratch/batch_import_unit9.py` is the one-off precedent. `apps/exercises/management/commands/import_bach_phrases.py` implements the underlying pipeline.
**Rationale:** Converts 12+ units needed for a semester into a single shell script. Compounds with every future corpus addition.
**Downsides:** Idempotency semantics need design. Mode selection per unit needs curriculum input.
**Confidence:** 95%
**Complexity:** Low
**Status:** Unexplored

### 5. Error-Class Adaptive Routing
**Description:** Connect wrong notes in a chorale window to a targeted follow-up drill. `problems[]` carries wrong MIDI note per window; `analysis.roman` in the CIR carries RN labels per chord position. A window → RN label → skill tag lookup routes students to a Dominant_Seventh drill after a V7 error, not a repeat of the whole chorale.
**Axis:** mastery feedback loop
**Basis:** `direct:` `chorale_grader.js problems[]` + `analysis.roman` in CIR structure. `external:` Duolingo error taxonomy routing (Settles et al. 2016) — no music theory platform implements this at onset-window granularity.
**Rationale:** The prerequisite data (wrong notes per window) already exists. This is the strongest competitive moat once built.
**Downsides:** Requires mastery hook (idea 1) first. Window-to-skill-tag mapping needs music theory design decision.
**Confidence:** 72%
**Complexity:** High
**Status:** Unexplored

### 6. Student Triage View for Instructors
**Description:** Priority-sorted instructor view: students who have been stuck on a skill for N+ days, approaching a deadline with <50% completion, or whose mastery is actively decaying appear at the top. Urgency score computed from existing DB fields — no new data collection.
**Axis:** teacher & course management
**Basis:** `reasoned:` Mastery decay timestamps, deadline proximity, and completion rate all in DB. New query and sort over existing data. `external:` ED triage model — urgency-ordered queue, highest-acuity first.
**Rationale:** Automated grading shifts the instructor's job to intervention. A priority queue makes that job tractable for a class of 30+.
**Downsides:** Urgency formula needs instructor validation. Short-term, mastery signals require hook (idea 1) to be wired.
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

### 7. MIDI Fallback / Notation-Click Input Mode
**Description:** When `navigator.requestMIDIAccess` is undefined (Safari, Firefox, iOS), activate `computer_keyboard_ux_logic.js` instead of showing a dead-end error. For harmonization exercises, wire a click-note-head path through `HarmonizationGrader`. Unlocks ~30% of browser users and all iOS devices.
**Axis:** grading infrastructure
**Basis:** `direct:` `lab/static/js/src/components/midi.js onWebMIDIError` shows dead-end error; `computer_keyboard_ux_logic.js` already imported and functional. `external:` Web MIDI browser compatibility 2026 — Safari/Firefox/iOS excluded. Artusi: 50k+ users with notation-entry only.
**Rationale:** Hardware gating is an adoption ceiling. The computer keyboard module already exists. This is a display branch change, not a new grading system.
**Downsides:** Computer keyboard is a degraded experience vs. MIDI controller. Click-to-harmonize UX needs design for chord entry.
**Confidence:** 90%
**Complexity:** Low-Medium
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|----------------|
| — | Spaced repetition "Review Due" surface | Depends on mastery hook (idea 1); Phase 2 follow-on |
| — | Fluency rate metric | Premature — adds dimension to mastery model before basic model is active |
| — | Per-window class heatmap | Absorbed into idea 6 (triage view) |
| — | Chess puzzle mode | Depends on aggregate error pipeline; Phase 2 after ideas 1+3 |
| — | Partimento predict-then-compare | High complexity; requires counterpoint checker first |
| — | Multi-key mastery confirmation gate | Changes mastery definition retroactively; worth a spec, not immediate implementation |
| — | LTI 1.3 grade passback | Already in backlog (feature-status.md "Requirements TBD May 2026"); not novel |
| — | UMTO REST API | Strategic framing of LTI; belongs in strategy discussion, not product improvement ideation |
| — | Instructor exercise builder (MusicXML UI) | On planned feature list (2.20); not novel enough to rank over blocking infra gaps |
| — | Transposition-based corpus multiplication | Infrastructure already works; curriculum policy decision, not a product idea |
| — | Self-directed skill tree | Requires mastery hook + progress UX; Phase 3 feature |
| — | Clone-a-semester template | Absorbed into `create_unit_playlist` as a preset config option |
| — | "Explain this chord" button | Valid 1-day feature from existing UMTO analysis field; below meeting-test floor |
| — | Chorale race / peer leaderboard | Valid engagement idea; targets primary metric cheaply; deferred — engagement features lower-priority than infra gaps pre-pilot |
| — | Post-session error replay | Strong; depends on problems[] serialization to PerformanceData being fixed first |
