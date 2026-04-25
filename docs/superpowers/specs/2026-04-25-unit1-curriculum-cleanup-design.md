# Unit 1 Curriculum Cleanup — Design Spec

**Date:** 2026-04-25  
**Status:** Approved in conversation — ready for implementation planning  
**Feature scope:** Unit 1 content cleanup plus Unit 1 student-page restructuring

---

## Overview

Unit 1 currently exposes too much database shape to students:

- duplicate playlists surface as separate rows
- redundant concepts appear as separate cards (`Pitch Reading`, `Clefs`, `Ledger Lines`)
- the page reads like a raw taxonomy/playlist join instead of a deliberate curriculum

This spec replaces the current Unit 1 student experience with a **curated six-lane structure** and aligns the underlying content mapping to that structure.

The user explicitly chose to treat Unit 1 as a **clean reset**:

- no progress migration
- no attempt to preserve old duplicate-lane structure
- no need to keep redundant category cards for compatibility

---

## Goals

- Make Unit 1 read like a coherent beginner curriculum.
- Remove duplicate and redundant student-facing playlists from Unit 1.
- Present Unit 1 as six canonical lanes only.
- Keep stronger students free to skip ahead without hard gates.
- Separate this curriculum cleanup from future teacher/dashboard tooling work.

## Non-Goals

- No generalized curriculum-builder or teacher-management tool in this phase.
- No cross-unit taxonomy redesign.
- No progress migration from old Unit 1 data.
- No forced prerequisite locking between treble and bass.
- No extended-range, enharmonics, or separate clef cards in Unit 1.

## Preconditions / Blockers

The following must be resolved before implementation begins:

1. **Canonical playlist IDs must be identified from the actual database.**
   The six Unit 1 lanes cannot be implemented against placeholder playlist references.
2. **The old Unit 1 seeding path must be updated or retired in the same project.**
   Otherwise the deprecated Unit 1 structure can be silently reintroduced in dev or CI.
3. **The canonical student entry surface for Unit 1 must be explicit.**
   Both existing student Unit 1 surfaces cannot continue to diverge.

---

## Curriculum Decisions

The following decisions were made in conversation and are fixed for this spec.

### Unit 1 top-level structure

Unit 1 should be organized by **activity type**, not by concept labels like `Pitch Reading` or by clef progression at the top level.

Student-facing cards:

1. `Identify`
2. `Play from Name`
3. `Play the Notes`

### Rows inside each card

Each card contains exactly two rows:

1. `Treble`
2. `Bass`

This yields **six canonical student-facing lanes** total.

### Removed from Unit 1

The following should not appear as separate student-facing Unit 1 categories:

- `Pitch Reading`
- `Clefs`
- `Ledger Lines`
- `Enharmonics`
- `Extended Range`

Interpretation:
- clef learning is already embedded in treble/bass note-reading work
- ledger-line work should be deferred rather than split into a fake parallel category
- enharmonics belong later, not in this introductory note-reading unit
- extended range is explicitly out of Unit 1

### Sequence policy

- Students should see both `Treble` and `Bass` from the start.
- `Treble` should appear first and read as the default path.
- `Bass` should be visible but secondary.
- No hard lock is required in this phase.

---

## Canonical Unit 1 Structure

The student-facing Unit 1 page should render exactly this structure:

### Identify
- Treble
- Bass

### Play from Name
- Treble
- Bass

### Play the Notes
- Treble
- Bass

Each row maps to one canonical playlist behind the scenes.

The page should not expose duplicate playlists, variant suffix clutter, or raw skill-tag groupings.

---

## Content/Data Policy

## Section 1: Canonical playlist mapping

Unit 1 needs an explicit mapping from the six student-facing lanes to six canonical playlists.

Example shape:

```python
UNIT1_CANONICAL_LANES = {
    "identify_treble": {"label": "Treble", "playlist_id": "..."},
    "identify_bass": {"label": "Bass", "playlist_id": "..."},
    "play_from_name_treble": {"label": "Treble", "playlist_id": "..."},
    "play_from_name_bass": {"label": "Bass", "playlist_id": "..."},
    "play_the_notes_treble": {"label": "Treble", "playlist_id": "..."},
    "play_the_notes_bass": {"label": "Bass", "playlist_id": "..."},
}
```

The exact playlist IDs must be resolved from the live/dev database before implementation starts. They may then live in Python config, a helper module, or another explicit curated structure, but the key point is this:

**Unit 1 must stop being inferred from “all playlists that overlap a tag.”**

Instead, the student surface should use one curated source of truth.

### Required discovery step

Before writing implementation code:

- query the current Unit 1 playlists from the database
- determine the six canonical playlists
- record those exact playlist IDs in either:
  - this spec,
  - a companion seed/curation script, or
  - the final canonical mapping module

Implementation must not proceed with `...` placeholders.

## Section 2: Duplicate handling

When multiple existing playlists represent the same pedagogical lane:

- choose one canonical playlist
- do not show the others to students on the Unit 1 page
- duplicates may remain in the database temporarily, but they are retired from the student-facing Unit 1 experience

This is a visibility and curriculum decision, not necessarily an immediate destructive data cleanup.

## Section 3: Existing progress

Existing Unit 1 progress may be discarded.

Reason:
- there is no meaningful live student data to preserve
- the current Unit 1 structure is being treated as pre-production curriculum scaffolding

This allows implementation to avoid migration logic entirely.

## Section 4: Seeder policy

The existing Unit 1 seeding command must be updated or retired as part of this project.

Reason:
- the current seeder creates the old four-tag structure (`Note_Names`, `Ledger_Lines`, `clefs`, `enharmonic`)
- that structure is explicitly being retired by this spec

Affected file:
- `apps/student/management/commands/seed_unit1_content.py`

Allowed outcomes:

1. update the seeder to emit the six canonical Unit 1 lanes, or
2. retire/disable the seeder if it is no longer authoritative

It must not remain capable of silently recreating the deprecated student-facing Unit 1 structure.

---

## Student Page Design

## Section 1: Unit 1 becomes curated

Unit 1 should not use the current generic “skill cards from taxonomy tags + all overlapping playlists” rendering model.

Instead, Unit 1 should render a curated structure tailored to the six-lane curriculum above.

This can be implemented as:

- a Unit 1 special-case data builder in the student service layer, or
- a curated Unit 1 view-model generator used only for Unit 1

The generic multi-tag system can remain for other units for now.

## Section 1A: Canonical entry surface

Implementation must explicitly choose the canonical Unit 1 student entry path and align the other surface to it.

Current parallel surfaces:

- `apps/student/views.py` `UnitView` using `student/unit.html`
- `apps/student/views.py` `UnitProgressView` using `student/unit_progress.html`

Decision required in implementation:

- either `UnitProgressView` becomes the canonical Unit 1 curriculum surface and `UnitView` redirects/alignment-shims to it
- or `UnitView` becomes canonical and `UnitProgressView` is aligned to the same curated data

This project must not leave one Unit 1 route curated and the other route tag-derived.

## Section 2: Card layout

The page should show three cards:

1. `Identify`
2. `Play from Name`
3. `Play the Notes`

Each card contains:

- `Treble`
- `Bass`

Each row should include:

- row label (`Treble` or `Bass`)
- progress indicator/count for that canonical playlist
- last score if available
- direct resume/start link

## Section 3: Visual emphasis

- `Treble` is listed before `Bass` in every card.
- `Bass` is not hidden or locked.
- The page should imply an intended order through layout, not enforcement.

---

## Architecture Impact

### Existing problem areas

Current Unit 1 rendering is split across two parallel student surfaces:

- `apps/student/views.py` `UnitView`
- `apps/student/unit_progress.py` and `apps/student/templates/student/unit_progress.html`

The current system groups content by taxonomy tags and all intersecting playlists. That is exactly what causes the clutter and redundancy.

### Proposed architecture

Introduce a curated Unit 1 source of truth in the student layer.

Likely pieces:

- a dedicated Unit 1 curriculum mapping module or helper
- a Unit 1-specific view-model builder
- template rendering that consumes three activity cards, each with two rows

The generic taxonomy-driven behavior can remain for other units.

### Files likely affected

Potential implementation files:

- `apps/student/unit_progress.py`
- `apps/student/views.py`
- `apps/student/templates/student/unit_progress.html`
- `apps/student/templates/student/unit.html`
- `apps/student/management/commands/seed_unit1_content.py`
- new helper module for curated Unit 1 lane mapping
- tests for student unit rendering

No migration is required by this spec.

### Legacy cleanup items that must be addressed explicitly

Implementation should review and either remove or stop relying on the following old Unit 1 structures:

- `UNIT_1_TAGS` in `apps/student/views.py`
- `skill_display_names` entries for retired Unit 1 categories in `apps/student/views.py`
- the `enharmonic` label compatibility override in `apps/student/views.py`
- HomeView resume selection logic in `apps/student/views.py` that currently uses `_get_playlists_for_tag(...)` and the retiring Unit 1 tag flow

These are part of the deprecated tag/category model and should not survive unnoticed into the curated Unit 1 implementation.

### Resume flow requirement

If Unit 1 still exposes a resume button or resume URL from `HomeView`, that flow must be updated to use the canonical Unit 1 lane mapping rather than `_get_playlists_for_tag(...)` / `UNIT_1_TAGS`.

Implementation must not leave HomeView resuming students into a non-canonical or duplicate Unit 1 playlist through the old tag-overlap path.

### Tag continuity

Canonical Unit 1 playlists should retain the `unit:1` tag (or equivalent existing unit tag contract) so existing unit-scoped player logic continues to recognize them correctly.

---

## Implementation Strategy

This project has two coupled parts and should be implemented together.

### Part 1: Content cleanup

- identify the six canonical playlists
- define explicit lane mapping
- retire duplicate playlists from the student-facing Unit 1 view

### Part 2: Student rendering cleanup

- stop rendering Unit 1 from raw overlapping tag groups
- render the three curated activity cards instead

The key constraint is that **the student page and the content mapping must be updated together**. Doing only one side would preserve confusion.

---

## Testing

### Curriculum/data checks

- confirm exactly six student-facing Unit 1 lanes are rendered
- confirm each lane maps to one canonical playlist
- confirm duplicate playlists do not appear on the Unit 1 page
- confirm the canonical playlists are the six explicitly selected DB rows, not name-based guesses

### Student UI checks

- Unit 1 renders three cards only:
  - `Identify`
  - `Play from Name`
  - `Play the Notes`
- each card renders exactly:
  - `Treble`
  - `Bass`
- no `Pitch Reading`, `Clefs`, `Ledger Lines`, `Enharmonics`, or `Extended Range` cards appear

### Progress checks

- each row resumes into the canonical playlist
- done/total counts still render correctly
- last-score display still works if a score exists

### Required automated test coverage

Implementation should add or extend tests in concrete existing files, not rely on manual checks alone.

Primary targets:

- `apps/student/tests/test_unit_progress.py`
  - verify the curated Unit 1 view-model returns exactly three cards and six rows
  - verify retired categories do not appear
- `apps/student/tests/test_unit1_curriculum_integration.py`
  - verify the student-facing Unit 1 page renders the curated structure end-to-end
- `apps/student/tests/test_views.py`
  - verify whichever Unit 1 route remains canonical responds with the curated structure

If implementation introduces a new Unit 1 curation helper/module, add focused unit tests for the canonical lane mapping there as well.

---

## Risks

### Risk 1: Hidden dependency on generic tag grouping

The current student surfaces may assume that every unit is tag-driven and generic.

**Mitigation:** keep the Unit 1 curation isolated to Unit 1 only, rather than trying to generalize prematurely.

### Risk 2: Canonical playlist choice ambiguity

There may be multiple similarly named Unit 1 playlists and unclear ownership of which one should survive.

**Mitigation:** make the canonical mapping explicit in code and verify against actual playlist IDs, not names alone.

### Risk 3: Partial cleanup

If the curated rendering is added but old generic Unit 1 surfaces still link to cluttered content, students may still encounter the messy version.

**Mitigation:** identify the actual student entry path for Unit 1 and make that path authoritative.

---

## Follow-Up Work

After this cleanup, the next logical project is teacher/tooling support shaped by the cleaned curriculum:

- better canonical-playlist management
- duplicate detection/retirement tools
- easier unit-lane editing
- broader curriculum authoring UX

Those tools should be built **after** Unit 1 is structurally correct, not before.
