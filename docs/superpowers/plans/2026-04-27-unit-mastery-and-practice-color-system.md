# Unit Mastery And Practice Color System Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` before starting implementation.

**Goal**
Implement the approved Unit 1 mastery/practice redesign so the student unit page separates `mastery state` from `recommended practice progress`, adds challenge-ready curricular metadata at the lane-placement level, and establishes architecture that can generalize to later units.

**Architecture**
- Curricular sequencing metadata lives on `ExercisePlaylistOrdered`, not in UMTO.
- Unit 1 curriculum helpers in `apps/student/unit1_curriculum.py` remain the canonical mapping layer for the six Unit 1 lanes and will grow challenge-group metadata.
- Mastery state is computed from explicit evidence rules, not `done < total`.
- Lane rows remain playlist-driven and expose fluency/progress bands plus challenge entry points.
- Mastery challenge attempts must be distinguishable from ordinary practice attempts end-to-end.

**Tech Stack**
- Django models, migrations, views, templates, and tests
- Existing Unit 1 generation command and playlist wiring
- Existing `StudentSkillMastery`, `PerformanceData`, and `IdentificationAttempt` persistence paths
- Existing student unit progress UI in `apps/student/templates/student/unit_progress.html`

## Phase 1 — Curricular metadata foundation

**Files**
- `apps/exercises/models.py`
- `apps/exercises/migrations/`
- `apps/dashboard/views/playlists.py`
- `apps/dashboard/views/library.py`
- `apps/student/tests/test_unit1_curriculum.py`
- `apps/student/tests/test_unit1_curriculum_integration.py`

### Tasks
- [ ] Add placement-level metadata to `ExercisePlaylistOrdered` for Unit 1 sequencing semantics.
- [ ] Keep this metadata curricular, narrow, and playlist-placement specific. Recommended shape:
  - `difficulty_tier = models.PositiveSmallIntegerField(default=1)`
  - `is_mastery_challenge_source = models.BooleanField(default=False)`
- [ ] Add migration with safe defaults for existing rows.
- [ ] Update any playlist-copying codepaths so placement metadata survives duplication where appropriate.
- [ ] Add or update tests proving the new fields round-trip correctly and do not break existing playlist wiring.

### Notes
- Do not store this in UMTO payloads.
- Do not make challenge eligibility implicit from `order`.
- If later units need richer semantics, extend this model rather than smuggling logic into descriptions.

### Acceptance
- `ExercisePlaylistOrdered` can express “advanced tier” and “challenge source” explicitly.
- Existing Unit 1 playlist resolution tests still pass.

## Phase 2 — Unit 1 generation and curriculum mapping

**Files**
- `apps/exercises/management/commands/generate_unit1.py`
- `apps/exercises/management/commands/rebuild_unit1_playlists.py`
- `apps/student/unit1_curriculum.py`
- `apps/exercises/tests/` or `apps/student/tests/` for generator-facing coverage

### Tasks
- [ ] Update Unit 1 playlist wiring so each placement gets explicit `difficulty_tier`.
- [ ] Mark the terminal challenge-eligible slice of each lane with `is_mastery_challenge_source=True`.
- [ ] Base the challenge slice on curriculum semantics, not raw “last two by position” assumptions in downstream code.
- [ ] Extend `apps/student/unit1_curriculum.py` with canonical challenge group metadata:
  - Treble group: identify treble, play-from-name treble, play-the-notes treble
  - Bass group: identify bass, play-from-name bass, play-the-notes bass
- [ ] Add helper accessors for:
  - lane playlist IDs
  - challenge group definitions
  - challenge-source exercises for a lane/group
- [ ] Add tests proving generator output marks advanced/challenge rows as expected and that curriculum helpers expose stable challenge groups.

### Notes
- Keep the current lane naming compatibility logic in `UNIT1_CANONICAL_LANES`.
- Prefer deterministic metadata assignment in generation so rebuilds are idempotent.

### Acceptance
- Freshly generated Unit 1 playlists carry explicit advanced/challenge metadata.
- Curriculum code can answer “which exercises belong in the Treble Mastery Challenge?” without consulting descriptions or order-only heuristics.

## Phase 3 — Attempt typing and challenge persistence contract

**Files**
- `apps/exercises/views.py`
- `apps/exercises/models.py`
- `apps/exercises/tests/test_submission_views.py`
- `lab/static/js/src/models/exercise_context.js`
- grader or submission-related JS files as needed

### Tasks
- [ ] Add explicit attempt typing through the submission path. Recommended values:
  - `practice`
  - `mastery_challenge`
- [ ] Ensure this type is captured in stored performance data or associated submission rows in a way analytics and mastery code can query later.
- [ ] Update the frontend submission payload so ordinary lane work sends `practice` and challenge flows send `mastery_challenge`.
- [ ] Preserve existing score numerator/denominator behavior introduced in the recent mastery fix.
- [ ] Add tests showing attempt type is persisted and available in the server-side response/persistence path.

### Notes
- The goal here is not only UI behavior. It is future auditability.
- Do not leave challenge attempts indistinguishable from routine practice completions.

### Acceptance
- A completed submission can be reliably identified as practice or mastery challenge in backend logic.

## Phase 4 — Mastery evidence service

**Files**
- `apps/student/unit_progress.py`
- `apps/exercises/mastery.py`
- `apps/student/tests/test_unit_progress.py`
- `apps/exercises/tests/` as needed for shared evidence helpers

### Tasks
- [ ] Extract or add a small service/helper layer that computes Unit 1 mastery evidence from:
  - lane completion history
  - score quality
  - placement metadata (`difficulty_tier`, `is_mastery_challenge_source`)
  - attempt type (`practice` vs `mastery_challenge`)
- [ ] Replace the current `_playlist_progress_level()` shortcut for Unit 1.
- [ ] Implement the approved Unit 1 state semantics:
  - `not_started`: no meaningful evidence
  - `attempted`: started, but no advanced success yet
  - `proficient`: success on sufficiently advanced lane material
  - `mastered`: successful mastery challenge pass
- [ ] Make proficiency depend on advanced-tier evidence, not merely early easy wins.
- [ ] Make mastery challenge evaluation strict: `6/6` correct => `mastered`, otherwise remain `proficient`.
- [ ] Keep the challenge retry policy uncooldowned; failure should not block retry.
- [ ] Add focused tests covering:
  - early easy completions stay `attempted`
  - advanced-tier success promotes to `proficient`
  - challenge pass promotes to `mastered`
  - challenge miss does not incorrectly demote or promote

### Notes
- Keep this evidence logic factored so later units can reuse the pattern with different groupings.
- Avoid tying the top bar directly to row completion counts.

### Acceptance
- Unit 1 bar segments are derived from mastery evidence rather than playlist completion.

## Phase 5 — Lane progress bands and recommended-practice messaging

**Files**
- `apps/student/unit_progress.py`
- `apps/student/templates/student/unit_progress.html`
- `apps/student/tests/test_views.py`
- `apps/student/tests/test_unit_progress.py`

### Tasks
- [ ] Add row-level practice band computation for long lanes using a small number of clearly distinguishable bands.
- [ ] Keep the row mini-progress bar for fine-grained movement.
- [ ] Add student-facing copy/state that treats post-proficiency remaining items as `recommended practice`, not implied failure.
- [ ] Return richer row objects from `get_unit_progress_data()` including:
  - progress band token
  - mastery state
  - whether the lane is already proficient/mastered
  - optional recommended-practice label
- [ ] Update the template to visually separate:
  - top mastery meaning
  - row practice meaning
- [ ] Keep the existing `done / total` and `Last: N%` indicators, but stop using them as the only color source.
- [ ] Add regression tests for the rendered Unit 1 page state.

### Notes
- Aim for about 5–6 stable visual bands, not 10 subtle hues.
- The row color system is motivational, not canonical mastery.

### Acceptance
- A student who has completed meaningful practice sees visible row progression before mastery.
- A student who has become proficient still sees unfinished row work framed as recommended practice.

## Phase 6 — Mastery challenge unlock and serving

**Files**
- `apps/student/unit1_curriculum.py`
- `apps/student/views.py`
- `apps/student/player_progression.py`
- `apps/exercises/mastery.py`
- `apps/student/tests/test_player_progression.py`
- `apps/student/tests/test_views.py`

### Tasks
- [ ] Define challenge unlock rules for the two Unit 1 challenge groups:
  - Treble challenge unlocks when all three treble skills are `proficient`
  - Bass challenge unlocks when all three bass skills are `proficient`
- [ ] Decide and implement the concrete serving shape for challenge entry:
  - dedicated pseudo-playlist/playlist
  - or a challenge-specific player route/context
- [ ] Build challenge composition from the explicit lane-placement metadata, interleaving 2 prompts from each of the 3 lanes.
- [ ] Ensure challenge prompts are the hardest tier already flagged in curricular sequencing.
- [ ] Add challenge status and CTA data to the Unit 1 progress payload/template.
- [ ] Add tests for:
  - locked vs unlocked challenge visibility
  - correct 6-prompt composition
  - interleaving instead of grouped-by-lane serving

### Notes
- This phase is where the plan may branch slightly depending on whether challenge serving reuses existing playlist mechanics or introduces a lightweight challenge wrapper.
- Keep challenge selection deterministic enough for tests.

### Acceptance
- Unit 1 progress page can show and launch Treble/Bass mastery challenges only when unlocked.

## Phase 7 — Challenge input robustness

**Files**
- `lab/static/js/src/models/exercise_context.js`
- player/grader UI files implicated by play and identification challenge submission
- `apps/student/templates/student/player.html`
- JS/frontend tests if present; otherwise Django/regression coverage plus manual checklist

### Tasks
- [ ] Audit challenge submission flows for accidental-input failure modes, especially MIDI-based play exercises.
- [ ] Add guardrails so a stray note or accidental submission is not disproportionately punitive. Examples:
  - explicit “submit challenge” confirmation state where relevant
  - clear/reset affordance before final grading
  - challenge-mode messaging that distinguishes active answering from finalized submission
- [ ] Keep the challenge pass threshold strict at `6/6`, while improving input robustness instead of weakening scoring.
- [ ] Add regression coverage where feasible and a manual QA checklist where automated coverage is weak.

### Acceptance
- Strict mastery scoring remains intact without making accidental input the dominant failure mode.

## Phase 8 — Generalization and documentation closeout

**Files**
- `docs/adaptive_learning.md`
- `docs/architecture.md`
- implementation notes or follow-on specs if needed

### Tasks
- [ ] Verify implementation still matches the already-updated global docs.
- [ ] Add any final architecture notes discovered during implementation:
  - how other units should mark advanced/challenge placements
  - where attempt typing is persisted
  - how mastery evidence services should be extended
- [ ] Leave Unit 1-specific constants in a location that can be copied forward intentionally rather than spreading hardcoded challenge rules across templates and views.

### Acceptance
- The codebase has one coherent story for mastery vs practice progression and a clear extension path to later units.

## Suggested implementation order

1. Land the `ExercisePlaylistOrdered` metadata model changes first.
2. Teach `generate_unit1` and curriculum helpers to populate and expose the metadata.
3. Add attempt typing before challenge logic depends on it.
4. Replace Unit 1 top-bar computation with mastery evidence rules.
5. Update the Unit 1 UI for row bands and recommended-practice messaging.
6. Add challenge unlock/serving.
7. Add challenge input robustness.
8. Run a final docs and regression pass.

## TDD and verification

Run targeted tests after each phase rather than waiting until the end.

Recommended command clusters:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.student.tests.test_unit1_curriculum apps.student.tests.test_unit1_curriculum_integration -v 2
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.student.tests.test_unit_progress apps.student.tests.test_views -v 2
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_submission_views apps.student.tests.test_player_progression -v 2
```

For generator changes, use a dry-run or fixture-backed regeneration path before touching curated playlists:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py generate_unit1 --author <author-email> --clef both --lanes all --dry-run
```

Expected verification outcomes:
- metadata fields persist correctly on playlist placements
- Unit 1 bar segments stop mirroring `done < total`
- row progress visibly advances before mastery
- challenge unlock and scoring rules behave deterministically

## Open implementation choices to resolve during coding

- Whether mastery challenge serving should be represented as dedicated playlists or a lightweight challenge wrapper built from lane metadata.
- Whether advanced-tier proficiency should require one successful advanced completion or a slightly stronger threshold across advanced-tier items. The approved design requires advanced evidence, but the exact threshold can be finalized in code review if tests and pedagogy suggest adjustment.
- Whether challenge attempts should persist in `PerformanceData` only, or also in a dedicated challenge-attempt model if analytics needs quickly outgrow the current structures.

## Execution options

1. **Subagent-Driven (recommended)**  
   Use `superpowers:subagent-driven-development` to split model/migration work, mastery-service work, and UI/challenge work into disjoint slices.

2. **Inline Execution**  
   Implement phase-by-phase in this branch, running the targeted test cluster after each phase before moving on.
