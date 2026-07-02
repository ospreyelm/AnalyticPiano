# Adaptive Playlist Skill-Level Display — Design Spec

**Date:** 2026-07-02
**Status:** Draft — awaiting product owner review, not authorized for implementation
**Feature scope:** Student-facing progress display only. No new models.

---

## Problem

The unit progress page (`apps/student/templates/student/unit_progress.html:87-89`)
renders every playlist row as `{{ row.done }}/{{ row.total }} completed`, with a
`widthratio` fill bar sized to that ratio. For a **static** playlist this is a
meaningful number: there is a fixed, finite exercise pool.

For an **adaptive** playlist (`Playlist.is_adaptive` / `is_dynamic=True`,
served through `get_next_exercise()` in `apps/exercises/mastery.py:259`), the
pool is not fixed — `total` is `len(served_exercise_ids)`
(`apps/student/unit_progress.py:285`), which is the count of exercises the
adaptive engine has *served so far in this session's history*, not a stable
denominator the student is working toward. A student who has been
practicing for weeks can show "8/8" (looks complete) right next to another
skill showing "3/40" (looks barely started), even though both reflect
equally healthy adaptive practice. The ratio does not describe skill level;
it describes serving history, which is an implementation detail of
`get_next_exercise()`, not a proficiency signal.

The proficiency signal the platform actually computes — per-skill mastery
level — already exists and is already used for playlist gating and the
segmented unit bar. It just isn't shown at the individual playlist-row
level, which is where students currently read a raw ratio.

---

## Current data available (no new models needed)

- `StudentSkillMastery.level` (`apps/exercises/models.py:403-448`): one of
  `not_started → attempted → familiar → proficient → mastered`, per
  `(user, skill_tag)`.
- `compute_mastery_level()` (`apps/exercises/mastery.py:23-62`): derives the
  level from a rolling 10-attempt boolean history plus distinct practice
  days.
- `_batch_skill_levels()` (`apps/student/unit_progress.py:41-68`): already
  resolves a mastery level per taxonomy skill tag, alias-expanded, and is
  used today to build `bar_segments` and `skill_cards[].level` — i.e. the
  unit-level segmented bar already shows exactly the signal we want at the
  playlist row.
- `_playlist_progress_level()` (`apps/student/unit_progress.py:336-351`)
  already exists as a *playlist-level* heuristic (not skill-tag-level) that
  approximates a level from `done`/`total`/`last_score_pct` for the
  Unit-1 lane cards. It is a reasonable model for "how do we phrase this for
  one playlist row" but it re-derives an approximation instead of reading
  the skill's actual `StudentSkillMastery.level` — worth reconciling (see
  Open Question below).

---

## Proposed change

**Adaptive/dynamic playlist rows** show the skill-tag mastery level instead
of (or alongside, muted) the done/total ratio. **Static playlist rows**
keep the done/total ratio — it is accurate there and the product owner has
not asked to change it.

### Row rendering rule

```
if playlist.is_adaptive or playlist.is_dynamic:
    show: mastery level badge (e.g. "PROFICIENT"), using the same 5-tier
          vocabulary and color mapping as the segmented bar
          (not_started=gray, attempted=amber-light, familiar=amber,
          proficient=blue, mastered=green — matching
          unit_progress.html's existing bar segment colors)
    optionally show: last_score_pct as secondary text ("Last: 80%"),
          which is already computed and already displayed today
else:
    show: existing done/total ratio + fill bar (unchanged)
```

This is a **template + one small service function** change:

- `apps/student/unit_progress.py`: extend `_playlist_stats()` (or add a
  thin wrapper) to attach `mastery_level` to the returned dict for
  adaptive/dynamic playlists, sourced from the skill card's already-computed
  `skill_levels` map (`_batch_skill_levels`) rather than recomputing.
  Concretely: pass `skill_levels` into `_playlist_stats` (or compute it once
  per unit and attach it when building `tag_to_playlists`), keyed by the
  playlist's `_playlist_primary_tag()`.
- `unit_progress.html`: branch on `playlist.is_adaptive` to render a
  mastery badge instead of the `widthratio` bar.

No changes to `mastery.py`, no migration, no changes to `get_next_exercise()`
selection logic — this is a display-layer change only.

### Multi-skill playlists

A playlist's `_playlist_primary_tag()` picks a single tag for skill-card
grouping today (`apps/student/unit_progress.py:133-139`). Reuse that same
primary tag to select which `StudentSkillMastery.level` to show — no new
aggregation rule needed, since the row is already filed under one skill
card by that same primary tag.

---

## Open question for product owner

`_playlist_progress_level()` (existing, used only for Unit-1 lane rows)
and `StudentSkillMastery.level` (the taxonomy-wide mastery signal) are two
different heuristics that could disagree for the same student/skill. This
spec proposes using `StudentSkillMastery.level` everywhere outside Unit-1
(consistent with the segmented bar the student already sees above the
rows), and leaving Unit-1's existing lane-specific logic untouched since it
has its own mastery model (`_compute_unit1_lane_mastery_level`,
`apps/student/unit_progress.py:421-482`) tied to lane challenges. Confirm
this is acceptable before implementation, since it means two different
"proficient" badges can theoretically be computed by two different
functions across the same page (Unit 1 vs. all other units) — that
divergence already exists today, this spec does not introduce it.

---

## Out of scope

- Changing `get_next_exercise()` selection/ranking logic.
- Changing what "mastered" means (`compute_mastery_level` thresholds).
- Score card (exercise-completion overlay) changes — already shows tier
  correctly per `2026-04-25-student-progress-tracking-design.md`.
- Static playlist display — unchanged.

---

## Files to change (implementation-time)

| File | Change |
|---|---|
| `apps/student/unit_progress.py` | Attach `mastery_level` to adaptive playlist stat dicts, sourced from existing `_batch_skill_levels` output |
| `apps/student/templates/student/unit_progress.html` | Branch rendering: mastery badge for adaptive/dynamic rows, existing ratio bar for static rows |
| `apps/student/tests/test_unit_progress.py` (or equivalent) | Add coverage: adaptive playlist row shows mastery badge; static playlist row unchanged |

No entry needed in `docs/exercise_types.md` (no new exercise type) or
`feedback_catalog.md` (no new student-facing feedback event).
