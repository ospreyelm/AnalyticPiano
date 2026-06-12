# Teacher Experience Meta-Plan

> **Purpose:** Break the current product priorities into smaller specs/plans that can be executed safely. This is a plan-of-plans, not a direct implementation plan.

**Source priorities:** `CLAUDE.md`, `AGENTS.md`, and `docs/teacher_experience_launch_followups.md`.

**Operating rule for all child plans:** Ask Avner explicit questions whenever the work touches UI direction, generation efficiency, musical pedagogy, grading tolerance, or official-content policy. Do not silently choose those details.

---

## Guiding Principles

- Keep new teacher workflows inside `/teacher/...`; avoid routing ordinary users back into legacy `/dashboard/...`.
- Treat `/teacher/play/` as the center of authoring, generation, import, review, and save-as-official workflows.
- Prefer small, independently deployable plans over one large rewrite.
- Preserve UMTO as the only sanctioned path for new Exercise rows.
- Separate product decisions from engineering tasks. If a choice is musical, visual, or pedagogical, ask first.

---

## Recommended Execution Order

### Phase 0: Stabilize Launch Surface

Goal: finish the rollout polish found during production testing.

Child plans:

1. `teacher-course-roster-and-join-links`
   - Add create/attach group controls to the teacher course detail page.
   - Show join code and copyable join URL directly in the roster panel.
   - Add explicit student join success state.

2. `student-course-home`
   - Add a course-focused section above the full curriculum.
   - Show assigned course, next due work, open/locked states, and progress.
   - Keep the full curriculum available below.

3. `teacher-course-detail-links`
   - Add direct student-view links for course playlists/units.
   - Add "copy assignment link" per row.
   - Remove or relabel legacy dashboard escape hatches.

Question gates:

- UI: Ask what the preferred student home hierarchy should be: course-first, curriculum-first with course banner, or hybrid.
- Musical: Ask whether assigned work should hide non-course playlists or merely prioritize course playlists.
- Policy: Ask whether teachers can attach any public playlist or only factory/owned playlists.

---

### Phase 1: `/teacher/play/` Save and Official Content Flow

Goal: make the existing teacher play surface reliable for hand-authored content.

Child plans:

1. `teacher-play-save-dialog-smoke`
   - Verify and harden save with description, unit tags, and playlist creation.
   - Verify superuser sees and can use "Save as official".
   - Ensure saved official rows use `factory@monteverdi.app` and are public.

2. `teacher-play-authoring-metadata`
   - Improve unit/skill/mode tagging controls.
   - Make playlist selection/creation clear.
   - Expose factory vs. personal ownership state.

3. `teacher-play-official-content-audit`
   - Add preview of what will be saved: exercise type, UMTO mode, tags, playlist, transpositions.
   - Add validation and clear errors before write.

Question gates:

- UI: Ask how much metadata should be visible by default versus tucked into advanced controls.
- Musical: Ask which tags are required for a saved exercise to be pedagogically useful.
- Policy: Ask whether teachers who are not superusers can request official review or only save personal content.

---

### Phase 2: MusicXML Import in `/teacher/play/`

Goal: import MusicXML directly from the teacher authoring surface and convert it into useful UMTO exercises.

Child plans:

1. `teacher-play-musicxml-upload`
   - Add upload UI to `/teacher/play/`.
   - Parse and validate MusicXML server-side.
   - Return preview data without committing rows.

2. `musicxml-to-umto-preview`
   - Show imported score preview.
   - Let user choose measure range, key, meter, clef/staff distribution, and voices.
   - Surface parse warnings.

3. `musicxml-exercise-variant-save`
   - Save imported content as one or more exercise variants.
   - Support official save path for superusers.
   - Add tests for common MusicXML files and malformed files.

Question gates:

- UI: Ask what the upload flow should look like: modal inside play, separate import step, or side panel.
- Efficiency: Ask whether preview generation may be asynchronous for larger files.
- Musical: Ask how much key/meter/voice detection should be automatic versus manually confirmed.
- Musical: Ask which MusicXML sources are in scope first: chorales, keyboard reductions, single-line melodies, or arbitrary scores.

---

### Phase 3: Generation Wizard for Exercise Variants

Goal: generate a family of useful exercises from one source/option.

Child plans:

1. `generation-manifest-model`
   - Define a declarative object for a generation request:
     source, unit, skill targets, exercise types, modes, transpositions, playlist target, ownership.
   - Add dry-run output.

2. `generation-wizard-ui`
   - Build teacher/admin wizard for selecting:
     - source content
     - exercise types
     - modes
     - units/skills
     - transposition policy
     - target playlists
   - Show dry-run preview before writes.

3. `generation-executor`
   - Execute the manifest idempotently.
   - Avoid repeated expensive music21 analysis.
   - Write UMTO rows and playlist memberships.

4. `generation-results-review`
   - Show generated exercises with preview links.
   - Allow bulk accept, reject, retag, or regenerate.

Question gates:

- Efficiency: Ask which generation paths are slow enough to require background jobs.
- Efficiency: Ask whether the first version may be synchronous for small jobs only.
- Musical: Ask which exercise variants should be generated together by default.
- Musical: Ask transposition defaults: all keys, selected keys, pedagogical key set, or no transpositions by default.
- UI: Ask whether this belongs inside `/teacher/play/` as a wizard panel or as a separate `/teacher/generate/` page linked from play.

---

### Phase 4: New Teacher Backend Editor

Goal: replace common legacy dashboard work with modern teacher-app pages.

Child plans:

1. `teacher-content-library`
   - Browse exercises/playlists/courses inside `/teacher/...`.
   - Filter by unit, mode, owner, official/personal, exercise type, and tags.

2. `teacher-playlist-editor`
   - Edit playlist title, tags, owner/official state, visibility, order, and membership.
   - Add/remove/reorder exercises.
   - Preview playlist as student.

3. `teacher-exercise-editor`
   - Edit description, tags, unit/mode metadata, visibility, ownership.
   - Provide safe links to score/analysis review.
   - Avoid raw JSON editing for normal users.

4. `teacher-official-content-tools`
   - Promote existing public content to factory.
   - Audit coverage by unit/author.
   - Retag and reassign official playlists safely.

Question gates:

- UI: Ask what editor density is desired: compact operational table, richer card layout, or split-pane inspector.
- Policy: Ask who can edit official factory content.
- Policy: Ask whether official content should be a real model field instead of inferred from factory ownership.

---

### Phase 5: MIDI Play Grading Reform

Goal: make MIDI play exercises grade like theory learning, not performance assessment.

Child plans:

1. `midi-play-grading-audit`
   - Catalog current graders and exercise types that use MIDI input.
   - Identify harsh penalty paths: timing, extra notes, re-attacks, releases, octave mistakes, correction attempts.

2. `forgiving-play-grading-policy`
   - Define grading modes:
     - theory forgiving
     - strict practice
     - optional performance mode
   - Document tolerance choices.

3. `midi-play-grader-implementation`
   - Implement forgiving default.
   - Add tests for extra notes, timing slop, re-attacks, corrected attempts, held notes.

4. `student-feedback-for-play`
   - Replace punitive messages with actionable feedback.
   - Keep analytics useful without failing students unnecessarily.

Question gates:

- Musical: Ask which errors should matter pedagogically: wrong pitch, wrong chord member, wrong register, missing voice, wrong inversion, wrong rhythm.
- Musical: Ask when extra notes should be ignored versus marked wrong.
- Musical: Ask whether octave equivalence should be allowed for some exercise types.
- UI: Ask how feedback should appear: inline note colors, small message, progress meter, or detailed post-attempt feedback.

---

### Phase 6: Unified Modern CSS Identity

Goal: create a coherent Monteverdi visual identity distinct from Artusi.

Child plans:

1. `monteverdi-design-system-audit`
   - Inventory current teacher, student, dashboard, and play styles.
   - Identify reusable tokens and conflicts.

2. `monteverdi-design-tokens`
   - Define colors, typography, spacing, radii, shadows, controls, tables, cards, forms, and states.
   - Avoid Artusi-like visual signatures.

3. `teacher-app-css-consolidation`
   - Move teacher course/wizard/detail styles into the unified system.
   - Remove one-off inline styles where practical.

4. `student-app-css-alignment`
   - Align student home/course elements with the same identity while keeping student surfaces clear and calm.

Question gates:

- UI: Ask for visual direction using concrete references or adjectives.
- UI: Ask what "not too much like Artusi" means in practice: colors, typography, spacing, icons, density, or all of these.
- UI: Ask whether the identity should feel more academic, studio/tool-like, modern SaaS, or conservatory.

---

### Phase 7: Redesign `/teacher/play/`

Goal: move `/teacher/play/` into the new layout and make it the primary authoring/generation workspace.

Child plans:

1. `teacher-play-layout-redesign`
   - Redesign page structure around source, score, controls, analysis, and save/generate actions.
   - Use the new CSS identity.

2. `teacher-play-save-panel`
   - Replace modal-only save flow with a clear save/publish panel.
   - Include description, unit, mode, playlist, official ownership, and validation.

3. `teacher-play-generation-panel`
   - Add generation wizard entry point.
   - Add MusicXML import entry point.
   - Add transposition workflow entry point.

4. `teacher-play-preview-and-review`
   - Preview generated variants before writing.
   - Link directly into the new backend editor.

Question gates:

- UI: Ask whether `/teacher/play/` should be score-first, workflow-first, or split-pane.
- Efficiency: Ask which actions must feel instant and which can run in background.
- Musical: Ask which analysis overlays and controls are essential while authoring.

---

## Prompt Series for Child Specs and Plans

Use these prompts one at a time. Each should produce a focused design spec first,
then an implementation plan only after approval.

### Prompt 1: Launch Stabilization

```text
Read CLAUDE.md, AGENTS.md, docs/teacher_experience_launch_followups.md, and docs/superpowers/plans/2026-06-12-teacher-experience-meta-plan.md.

Create a focused design spec for Phase 0: roster/group creation, join-code visibility, student join success, and course-focused student home entry points. Ask me questions whenever UI or student-course policy decisions arise. Do not implement yet.
```

### Prompt 2: `/teacher/play/` Save and Official Content

```text
Read the current teacher play/save code and the teacher experience meta-plan. Create a design spec for making /teacher/play/ save official and personal content reliably: description, unit tags, playlist creation, factory ownership, validation, and smoke tests. Ask me before choosing metadata defaults, official-content policy, or UI layout. Do not implement yet.
```

### Prompt 3: MusicXML Import in `/teacher/play/`

```text
Create a design spec for adding MusicXML import to /teacher/play/. Cover upload, parse, preview, measure/voice selection, UMTO conversion, error handling, and save-as-official. Ask me all musical questions about supported score types, automatic key/meter detection, voice handling, and default exercise variants. Do not implement yet.
```

### Prompt 4: Generation Wizard

```text
Create a design spec for a generation wizard that can produce multiple exercise types, modes, playlists, and transpositions from one source. Include a dry-run preview and efficient backend execution. Ask me before deciding default variants, transposition sets, background-job behavior, or how much UI complexity is acceptable. Do not implement yet.
```

### Prompt 5: Teacher Backend Editor

```text
Create a design spec for replacing the common legacy Dashboard workflows with teacher-app editors for courses, playlists, exercises, and official content. Ask me before deciding editor layout, permissions, official-content model, or which legacy features to omit in v1. Do not implement yet.
```

### Prompt 6: MIDI Play Grading

```text
Create a design spec for reforming MIDI play grading so it behaves like a theory-learning app rather than a performance app. Audit current graders first. Ask me musical questions about wrong notes, extra notes, rhythm, register, octave equivalence, re-attacks, held notes, and correction behavior. Do not implement yet.
```

### Prompt 7: Monteverdi CSS Identity

```text
Create a design spec for a unified Monteverdi CSS/design identity that is modern and beautiful but not too close to Artusi. Audit current teacher/student/play styles first. Ask me UI questions about desired personality, density, typography, colors, and what specifically to avoid from Artusi. Do not implement yet.
```

### Prompt 8: `/teacher/play/` Redesign

```text
Create a design spec for redesigning /teacher/play/ using the new CSS identity and making it the main authoring, MusicXML import, generation, transposition, preview, and save-as-official workspace. Ask me before deciding the page structure, score/control layout, and which authoring actions must be first-class. Do not implement yet.
```

---

## Cross-Phase Questions to Ask Early

Ask these before locking the child specs if the answer is not already clear:

1. Should official content remain inferred from `factory@monteverdi.app`, or should it become an explicit field?
2. Should non-superuser teachers be able to submit content for official review?
3. Should student course enrollment restrict visible curriculum, prioritize assigned work, or leave all curriculum visible?
4. What is the minimum useful MusicXML import scope for v1?
5. Which transposition sets are pedagogically appropriate by unit?
6. What does "forgiving MIDI grading" mean for each play exercise type?
7. What visual qualities make Monteverdi distinct from Artusi?
8. Which legacy dashboard functions are genuinely still needed by normal teachers?

---

## Completion Definition

This meta-plan is complete when:

- Each phase has a written design spec.
- Each approved design spec has a task-level implementation plan.
- `/teacher/play/` supports efficient authoring, MusicXML import, generation variants, transpositions, and official save paths.
- Normal teacher workflows no longer require legacy dashboard pages.
- Students who join a course see a complete, obvious course experience.
- MIDI play grading is pedagogically forgiving by default.
- Teacher, student, and play surfaces share one modern Monteverdi design identity.

