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

The exact playlist IDs may live in Python config, a helper module, or another explicit curated structure, but the key point is this:

**Unit 1 must stop being inferred from “all playlists that overlap a tag.”**

Instead, the student surface should use one curated source of truth.

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

---

## Student Page Design

## Section 1: Unit 1 becomes curated

Unit 1 should not use the current generic “skill cards from taxonomy tags + all overlapping playlists” rendering model.

Instead, Unit 1 should render a curated structure tailored to the six-lane curriculum above.

This can be implemented as:

- a Unit 1 special-case data builder in the student service layer, or
- a curated Unit 1 view-model generator used only for Unit 1

The generic multi-tag system can remain for other units for now.

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
- possibly `apps/student/templates/student/unit.html` if that surface is still used
- new helper module for curated Unit 1 lane mapping
- tests for student unit rendering

No migration is required by this spec.

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

