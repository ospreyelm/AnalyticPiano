# Student Progress Tracking — Design Spec

**Date:** 2026-04-25  
**Status:** Approved — ready for implementation planning  
**Feature scope:** Student-facing only (teacher gradebook is a future phase)

---

## Overview

Two connected features delivered as a single cohesive system:

1. **Per-exercise score card** — a slide-up overlay shown at exercise completion, displaying score percentage, "N of M correct," the student's current mastery tier for the skill, and a level-up notification if the tier changed.
2. **Unit progress page** — a skill-grouped view of a curriculum unit, with a segmented mastery-tier bar at the top and expandable skill cards showing per-playlist completion counts below.

The two surfaces are visually connected: the score card includes a miniature version of the unit segmented bar so students can see the exercise's effect on the bigger picture immediately.

---

## Architecture

Three layers, no new database models:

```
Unit (from music_theory_taxonomy.json)
  └── Playlist (Playlist model, is_adaptive=True, is_dynamic=True)
        └── Exercise (Exercise model, served adaptively via get_next_exercise())
```

**New Python modules:**
- `apps/exercises/taxonomy_reader.py` — stateless utility for reading the taxonomy JSON
- `apps/student/unit_progress.py` — service that computes unit progress data for the template (replaces/extends existing `progress.py`)

**Modified files:**
- `apps/exercises/mastery.py` — `record_attempt()` gains a return value
- `apps/exercises/views.py` — submit endpoint includes mastery changes in response
- `lab/static/js/src/models/exercise_context.js` — score fields added to submission payload
- `lab/static/js/src/components/exercise_score_card.js` — new component (new file)
- `apps/student/views.py` — new `UnitProgressView`
- `apps/student/urls.py` — new URL route
- `apps/student/templates/student/unit_progress.html` — new template

**No migrations required.** All changes are either new Python modules, new JS, or additions to existing JSON fields.

---

## Section 1: Score Storage

### Problem
`PerformanceData.data[]` stores `error_tally` (integer error count) but not the denominator. "4 of 5 correct" cannot be displayed reliably without also storing the total.

### Solution
At exercise submission time, the JavaScript grader includes two additional fields in the report payload:

| Field | Type | Description |
|---|---|---|
| `score_numerator` | int | Items answered correctly |
| `score_denominator` | int | Total items attempted |

These are passed through `PerformanceData.submit()` into `pd.data[]` as-is (no schema change — it is a JSONField). Old entries without these fields display as "—" instead of a percentage.

### Score Computation per Exercise Type

| Exercise type | numerator | denominator |
|---|---|---|
| `matching`, `analytical`, `figured_bass` | chords matched | total chords |
| `chorale` | onset windows hit correctly | total onset windows |
| `identification` | correct slots | total slots |
| `chorale_identification` | correct slots (all pages combined) | total slots (all pages) |

### Score → Display Label Mapping (presentation only)

| Score % | Display label |
|---|---|
| 100% | Mastered |
| 80–99% | Proficient |
| 60–79% | Familiar |
| 40–59% | Attempted |
| < 40% | Needs Practice |

This mapping is for the score card display label only. Actual mastery tier is always computed by `compute_mastery_level()` from `recent_history`, not from a single exercise score.

---

## Section 2: TaxonomyReader Utility

**File:** `apps/exercises/taxonomy_reader.py`

A stateless class (~60 lines) that reads `music_theory_taxonomy.json` once and caches it in memory.

```python
class TaxonomyReader:
    # Lazily loaded, cached at class level
    _data: list | None = None

    @classmethod
    def _load(cls) -> list: ...

    @classmethod
    def get_all_units(cls) -> list[dict]:
        """Returns all unit dicts across all tiers."""

    @classmethod
    def get_unit(cls, unit_n: str) -> dict | None:
        """Returns a single unit by its 'n' key (e.g. '1', '9')."""

    @classmethod
    def get_unit_for_tag(cls, skill_tag: str) -> dict | None:
        """Returns the unit that contains this skill_tag, or None."""

    @classmethod
    def get_tier_for_unit(cls, unit_n: str) -> dict | None:
        """Returns the tier dict containing the given unit."""
```

No Django imports. Importable in tests without database setup.

---

## Section 3: UnitProgressView Service

**File:** `apps/student/unit_progress.py`

One main function returns a single dict used by the template. This replaces the simpler `get_unit_progress()` in `progress.py` (which can remain for backward compatibility).

```python
def get_unit_progress_data(user, unit_n: str) -> dict:
    """
    Returns all data needed to render the unit progress page.

    {
      "unit": {"n": "1", "title": "Pitch & Staff Notation", "feat": "...", "tags": [...]},
      "tier": {"label": "Tier 1 — Fundamentals & pitch reading", "badge": "T1"},
      "bar_segments": [
        {"tag": "Note_Names", "label": "Note Names", "level": "proficient"},
        {"tag": "Ledger_Lines", "label": "Ledger Lines", "level": "not_started"},
        ...
      ],
      "skill_cards": [
        {
          "tag": "Note_Names",
          "label": "Note Names",
          "level": "proficient",
          "playlists": [
            {
              "id": "PA01BC",
              "name": "Play the Notes (Treble)",
              "done": 16,
              "total": 36,
              "last_score_pct": 80,    # None if no score_numerator stored yet
              "url": "/student/playlist/PA01BC/?exercise_num=17"
            }
          ]
        },
        ...
      ]
    }
    """
```

**Playlist matching:** Playlists are matched to a skill card when `playlist.skill_tags` and the unit's `tags` share at least one element (set intersection). Only playlists accessible to the student's course are included.

**Completion count (`done`):** Derived from `PerformanceData.data[]` — count of entries for exercises in that playlist.

**Last score:** Most recent entry with `score_numerator` present, computed as `round(score_numerator / score_denominator * 100)`.

---

## Section 4: Mastery Level-Up Notifications

**Modified:** `apps/exercises/mastery.py` — `record_attempt()`

```python
# Before: returns None
# After:
def record_attempt(user_id: int, exercise, correct: bool) -> dict:
    """
    Returns a dict of skill-level changes, e.g.:
    {"Note_Names": {"old": "familiar", "new": "proficient"}}
    Empty dict if no levels changed.
    """
```

**Modified:** `apps/exercises/views.py` (submit endpoint)

The JSON response gains a `mastery_changes` key:

```json
{
  "status": "ok",
  "mastery_changes": {
    "Note_Names": {"old": "familiar", "new": "proficient"}
  }
}
```

---

## Section 5: Exercise Score Card (JavaScript)

**File:** `lab/static/js/src/components/exercise_score_card.js`

A self-contained module that:
1. Hooks into the existing `submitExerciseReport()` response in `exercise_context.js`
2. Reads `score_numerator`, `score_denominator`, and `mastery_changes` from the server response
3. Renders a slide-up overlay panel at the bottom of the exercise player

### Score Card Anatomy

```
┌─────────────────────────────────────────────┐
│  EXERCISE COMPLETE                           │  ← muted uppercase label
│                                             │
│  [Level up banner — shown only if tier      │  ← blue banner: "Level up!
│   changed. Gold if Mastered.]               │    Familiar → Proficient"
│                                             │
│  ◯ 80%    4 of 5 correct                   │  ← circular arc indicator
│           Skill: Note Names · Ex 8/36       │
│           [PROFICIENT]                      │  ← mastery tier badge
│                                             │
│  UNIT 1 · PITCH & STAFF NOTATION           │  ← mini unit bar
│  [■■□□]  1 of 4 skills proficient          │  ← segmented bar snippet
│                                             │
│  [  Try Again  ]  [  Next Exercise →  ]    │  ← two-button row
└─────────────────────────────────────────────┘
```

### Design Rules (no emoji)
- No emoji anywhere. Level-up banner uses a text arrow (→) and color only.
- "MASTERED" (not "⭐ MASTERED!") — gold background, dark amber text.
- "Level up! Familiar → Proficient in Note Names" — clean sentence, blue banner.
- When the skill is mastered and a next skill exists, the primary button changes to "Start [Next Skill] →" in green.
- In `test` mode (identMode = "test"), the overlay is suppressed entirely — no score shown.

### State Variants

| Condition | Banner | Circle color | Badge | CTA |
|---|---|---|---|---|
| Normal completion | None | Blue | Tier name | "Next Exercise →" |
| Level up (not mastered) | Blue "Level up! X → Y" | Blue | New tier | "Next Exercise →" |
| Mastered | Gold "You've mastered [Skill]" | Green | "MASTERED" | "Start [Next Skill] →" |
| Low score (< 60%) | None | Amber | "Needs Practice" | "Try Again" (primary) |
| test mode | Not shown | — | — | — |

---

## Section 6: Unit Progress Page

**URL:** `/student/units/<unit_n>/`  
**View:** `apps/student/views.py` → `UnitProgressView`  
**Template:** `apps/student/templates/student/unit_progress.html`

### Page Structure

```
← Back to Course

UNIT 1 · PITCH & STAFF NOTATION
T1 | Tier 1 — Fundamentals & pitch reading

[■■■□]  segmented mastery bar (one segment per skill)
  Note Names: Proficient | Ledger Lines: Familiar | Clefs: Not Started | ...

─────────────────────────────────────────────

Note Names                          PROFICIENT
  Play the Notes (Treble)   ━━━━━━━━░░░░  16/36 · Last: 80%
  Play the Notes (Bass)     ░░░░░░░░░░░░   0/36
  Identify the Notes        ━━━━━━░░░░░░  22/36 · Last: 73%

Ledger Lines                        FAMILIAR
  Play Ledger Lines (Treble) ━━░░░░░░░░░░  8/36

Clefs (Treble & Bass)               NOT STARTED
  Play Treble Clef           ░░░░░░░░░░░░   0/36
  [coming soon...]

Enharmonics                         NOT STARTED
  ...
```

### Segmented Bar Details
- One segment per skill tag in the unit, equal width
- Colors: green (mastered), blue (proficient), amber (familiar), light gray (not started)
- On hover/tap: tooltip shows the skill name and tier
- No animation on initial load (static render); future: animate on first visit

### Navigation
- "← Back to Course" links to the parent Course page
- Each playlist row is a clickable link to the exercise player, resuming at the next uncompleted exercise
- "Coming soon" placeholder shown for skills in the taxonomy that have no matching playlists yet

---

## Section 7: URL and Navigation Wiring

**New URL** in `apps/student/urls.py`:
```python
path("units/<str:unit_n>/", UnitProgressView.as_view(), name="unit-progress"),
```

**Entry points to the unit page:**
- From the Course page: each playlist row gains a "Unit Progress" link (or the unit heading becomes clickable)
- From the exercise score card: when mastered, the "Start [Next Skill] →" button links to the unit progress page, not directly to a playlist

---

## Out of Scope (Future Phase)

- Teacher gradebook view (class-wide mastery dashboard)
- Decay / "review due" indicators on the unit page
- Mastery Challenges (cross-skill adaptive quizzes confirming mastery)
- UnitDefinition as a database model (teacher-configurable unit structures)
- Email notifications on level-up
- PDF transcript export

---

## Implementation Order

1. `taxonomy_reader.py` — pure Python, fully testable, no dependencies
2. `unit_progress.py` — depends on taxonomy_reader + existing models
3. `record_attempt()` return value — small change, add tests
4. Submit endpoint — add `mastery_changes` to response + pass through `score_numerator/denominator`
5. JS graders — add score fields to `submitExerciseReport()` payload
6. `exercise_score_card.js` — new JS component
7. Unit progress template + view — wires everything together
8. URL routing + course page links
