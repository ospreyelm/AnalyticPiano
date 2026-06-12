# Teacher Experience Meta-Plan

> **Purpose:** Break the current product priorities into small, executable
> phases. This is a plan-of-plans, not a direct implementation plan.

**Source priorities:** `CLAUDE.md`, `AGENTS.md`, and
`docs/teacher_experience_launch_followups.md`.

**Settled decisions:** read
[docs/superpowers/specs/2026-06-12-teacher-experience-decisions.md](../specs/2026-06-12-teacher-experience-decisions.md)
(the "decisions doc") before writing any child doc. Decisions D1–D6 are
settled — do not re-ask them. Open questions live there too, each owned by
exactly one phase.

**Operating rule for all child plans:** Ask Avner only when the work involves
musical pedagogy, official-content policy, or visual identity. Default UI
follows existing teacher-app conventions; do not gate on routine UI choices.

**Why this order differs from the CLAUDE.md priority list:** the CLAUDE.md
list is product priority; this plan is execution order. Per decision D1, the
curation bottleneck is producing content (generation, transpositions, import),
so those come before the curation workbench, even though the launch followups
doc lists the backend editor first. Navigation quick wins stay first because
they are small and unblock student-facing use immediately.

---

## Guiding Principles

- Keep new teacher workflows inside `/teacher/...`; avoid routing ordinary
  users back into legacy `/dashboard/...`.
- Treat `/teacher/play/` as the center of authoring, generation, import,
  review, and save-as-official workflows.
- Prefer small, independently deployable phases over one large rewrite.
- Preserve UMTO as the only sanctioned path for new Exercise rows.
- Wrap existing backend machinery (management commands, save endpoints)
  rather than re-planning it.

---

## Execution Order

### Phase 0: Launch Navigation Fixes

Goal: finish the rollout polish found during production testing. Quick wins
for navigation (goal: app easy to navigate for students and teachers).

Child plans:

1. `teacher-course-roster-and-join-links`
   - Add create/attach group controls to the teacher course detail page.
   - Show join code and copyable join URL directly in the roster panel.
   - Add explicit student join success state.

2. `student-course-home`
   - Course-first home per decision D4: assigned course, next due work,
     open/locked states, progress, direct links on top.
   - Keep the full curriculum available below as exploration.

3. `teacher-course-detail-links`
   - Add direct student-view links for course playlists/units.
   - Add "copy assignment link" per row.
   - Remove or relabel legacy dashboard escape hatches.

Open question owned here: Q8 (hide vs. prioritize non-course playlists).

Executor tiers: specs Tier 3; implementation Tier 2; copy/label fixes Tier 1.

---

### Phase 0.5: Official-Content Field

Goal: replace factory-account inference with an explicit field (decision D3).

Single child plan: `official-content-field`
- Add `is_official` (or status) to Exercise and Playlist.
- Backfill from `authored_by=factory@monteverdi.app`.
- Switch `generate_factory_library --report`, the course wizard, and any
  official-content filters to the field.
- Keep factory ownership as a convention, not the source of truth.

Tiny migration; unblocks filtering in every later phase.

Executor tiers: implementation Tier 2; doc updates Tier 1.

---

### Phase 1: Generation & Transposition Wizard

Goal: generate a family of useful exercises (types, modes, transpositions,
playlists) from one source, from the UI.

**Existing assets — wrap, do not re-plan:** `generate_bach_unit_matrix`,
`create_unit_playlist`, `generate_transpositions`, `generate_factory_library`,
and the approved plan
[2026-06-02-efficient-bach-generation.md](2026-06-02-efficient-bach-generation.md)
(CLAUDE.md marks it IMPLEMENT NEXT — execute it as the prerequisite for the
bulk-generation side of this phase). The save-as-official backend already
exists in `lab/views.py` (`saveAsOfficial` + superuser check), so save-flow
work here is verification/hardening, not construction.

Child plans:

1. `wire-play-save-transpositions` (first; unblocks play-in curation)
   - Extract `generate_transpositions` core into a service function.
   - Call it from the save endpoint (`lab/views.py` AddExercise flow) when the
     transpose option is checked, writing transposed UMTO copies into the
     target playlist (decision D2).
   - Fix the mangled "Auto-ne" checkbox label/payload in
     `target_selector.js`; replace the no-op `_onTargetChosen` logging in
     `music_controls.js` with the real call.
   - Smoke tests: save with description + unit tag + new playlist +
     transpositions; superuser sees and uses "Save as official"; official rows
     use the factory account and are public.

2. `generation-manifest-model`
   - Declarative object for a generation request: source, unit, skill
     targets, exercise types, modes, transpositions, playlist target,
     ownership.
   - Dry-run output. Executes by calling existing command logic, idempotently.

3. `generation-wizard-ui`
   - Teacher/admin wizard for selecting source content, exercise types,
     modes, units/skills, transposition policy, target playlists.
   - Dry-run preview before writes. Synchronous for small jobs first;
     background jobs only where measured to be slow.

4. `generation-results-review`
   - Show generated exercises with preview links.
   - Bulk accept, reject, retag, or regenerate.

Open questions owned here: Q3 (transposition sets by unit), Q7 (default
variant bundles).

Executor tiers: manifest/wizard design Tier 3; implementation Tier 2;
docs/tests scaffolds Tier 1.

---

### Phase 2: MusicXML Import in `/teacher/play/`

Goal: import MusicXML directly from the teacher authoring surface and convert
it into useful UMTO exercises.

Child plans:

1. `teacher-play-musicxml-upload`
   - Upload UI in `/teacher/play/`; server-side parse and validation;
     preview data returned without committing rows.

2. `musicxml-to-umto-preview`
   - Imported score preview; choose measure range, key, meter, clef/staff
     distribution, voices; surface parse warnings.

3. `musicxml-exercise-variant-save`
   - Save imported content as one or more exercise variants through the
     Phase 1 manifest path (including transpositions and official save).
   - Tests for common and malformed MusicXML files.

Open question owned here: Q2 (v1 scope: chorales, keyboard reductions,
single-line melodies, arbitrary scores).

Executor tiers: conversion design Tier 3; plumbing Tier 2; test fixtures
Tier 1.

---

### Phase 3: Curation Workbench

Goal: replace common legacy dashboard work with modern teacher-app pages,
simplified by the Phase 0.5 official field.

Child plans:

1. `teacher-content-library`
   - Browse exercises/playlists/courses inside `/teacher/...`.
   - Filter by unit, mode, owner, official/personal, exercise type, tags.

2. `teacher-playlist-editor`
   - Edit playlist title, tags, official state, visibility, order,
     membership. Add/remove/reorder exercises. Preview as student.

3. `teacher-exercise-editor`
   - Edit description, tags, unit/mode metadata, visibility, ownership.
   - Safe links to score/analysis review; no raw JSON editing for normal
     users.

4. `teacher-official-content-tools`
   - Promote existing public content to official; audit coverage by
     unit/author; retag and reassign official playlists safely.

Open questions owned here: Q1 (non-superuser official review), Q6 (which
legacy dashboard functions survive).

Executor tiers: editor specs Tier 3; CRUD implementation Tier 2; audits and
inventories Tier 1.

---

### Phase 4: MIDI Play Grading Reform

Goal: make MIDI play exercises grade like theory learning, not performance
assessment. Builds on the chord-race debounce + flat-threshold work from
PR #83 and the progressive-threshold/listen-credit roadmap.

Child plans:

1. `midi-play-grading-audit`
   - Catalog current graders and exercise types that use MIDI input.
   - Identify harsh penalty paths: timing, extra notes, re-attacks, releases,
     octave mistakes, correction attempts.

2. `forgiving-play-grading-policy`
   - Define grading modes (theory forgiving default, strict practice,
     optional performance) and document tolerance choices.

3. `midi-play-grader-implementation`
   - Implement forgiving default; tests for extra notes, timing slop,
     re-attacks, corrected attempts, held notes.

4. `student-feedback-for-play`
   - Replace punitive messages with actionable feedback via
     `feedbackService.emit`; keep analytics useful.

Open question owned here: Q4 (what forgiving means per type — pedagogy,
Tier 4 with Avner).

Executor tiers: audit Tier 1; policy Tier 4/3; grader implementation Tier 2.

---

### Phase 5: CSS Identity + `/teacher/play/` Redesign

Goal: one modern Monteverdi visual identity, distinct from Artusi, applied
across teacher and student surfaces — and `/teacher/play/` moved onto it as
the primary authoring workspace. (Old Phases 6 and 7, merged.)

Child plans (two combined docs):

1. `monteverdi-design-system` (combined doc)
   - Inventory current teacher/student/dashboard/play styles (Tier 1 audit).
   - Define tokens: colors, typography, spacing, radii, shadows, controls,
     tables, cards, forms, states.
   - Consolidate teacher course/wizard/detail styles; align student surfaces.

2. `teacher-play-redesign` (combined doc)
   - Redesign page structure around source, score, controls, analysis, and
     save/generate actions, using the new identity.
   - Replace modal-only save with a save/publish panel: description, unit,
     mode, playlist, official ownership, validation.
   - First-class entry points: generation wizard, MusicXML import,
     transposition workflow.
   - Play-in authoring-loop polish: record → correct → tag → save →
     transpose → append-to-playlist ergonomics.

Open question owned here: Q5 (visual direction vs. Artusi — Tier 4 with
Avner).

Executor tiers: style inventory Tier 1; token/redesign specs Tier 3 (visual
decisions Tier 4); CSS implementation Tier 2.

---

## Child Doc Prompt Template

One reusable prompt; per decision D5 each phase produces ONE combined
spec+plan document.

```text
Read docs/superpowers/specs/2026-06-12-teacher-experience-decisions.md and
docs/superpowers/plans/2026-06-12-teacher-experience-meta-plan.md §Phase N.

Produce ONE combined spec+plan doc for Phase N at
docs/superpowers/plans/YYYY-MM-DD-<phase-name>.md: a short design section
(why, data shapes, decisions taken) followed by checkbox implementation
tasks, each tagged with its executor tier (see decisions doc D6).

Settled decisions D1–D6 are not open for discussion. Ask Avner only the open
questions the meta-plan assigns to this phase, then record the answers in the
decisions doc. Do not implement yet.
```

## Cost Routing

Per decision D6: every task defaults to the cheapest capable executor.
`gemini` (0.37.1) and `codex` (0.137.0) CLIs are installed.

- **Tier 1 — mechanical/bulk:** `gemini -m gemini-2.5-flash` or Codex CLI at
  low reasoning effort. Doc rewrites from explicit instructions,
  audits/inventories, label fixes, test scaffolds, backfill scripts.
- **Tier 2 — implementation against a complete spec:** Codex CLI default
  model, or `claude --model haiku`. The spec must remove all design judgment.
- **Tier 3 — combined spec+plan docs needing judgment:**
  `claude --model sonnet` or main session.
- **Tier 4 — pedagogy / visual identity / policy:** Avner + main session
  only. Never delegated.

Escalate a task's tier only when it demands judgment the lower tier lacks.
Review of delegated output happens in the dispatching session, not by another
expensive agent.

---

## Completion Definition

This meta-plan is complete when Avner can take one unit from source material
(Bach, clausulae, MusicXML, or played-in at `/teacher/play/`) to official,
transposed, playlist-ordered, student-visible content **entirely inside
`/teacher/...`** — no CLI, no legacy dashboard — and students who join a
course land on a course-first home with obvious next work.
