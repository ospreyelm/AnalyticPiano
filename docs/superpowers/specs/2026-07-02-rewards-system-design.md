# Rewards / Awards System — Design Spec

**Date:** 2026-07-02
**Status:** Draft — awaiting product owner review, not authorized for implementation
**Feature scope:** New student-facing gamification layer. New models required.

---

## What exists today

Nothing. Repo-wide search for badge/achievement/points/streak/leaderboard
gamification code returns no hits (the one "badge" match,
`apps/dashboard/tests/test_analysis_review_badge.py`, is an unrelated
teacher-editor "needs review" UI status pill — worth avoiding the word
"badge" for this feature's model names to keep grep unambiguous; this spec
uses **Award**).

What already exists and is directly reusable as *signal* for awards:
- `StudentSkillMastery` (`apps/exercises/models.py:403`) — level per skill,
  `practice_days` (per-skill distinct calendar dates), `mastered_at`.
- `record_attempt()` (`apps/exercises/mastery.py:126-200`) — the **single
  funnel point** every submission passes through today. Confirmed exactly
  two call sites: `apps/exercises/views.py:240` and `:299` (play-mode and
  identification-mode submit endpoints). This is the one place to hook
  award-checking logic without adding a second, parallel submission path.
- `canvas-confetti` (`lab/static/js/lib/canvas-confetti.js`) is already
  bundled and already wired to mastery level-ups in
  `exercise_score_card.js:87-101` — the celebratory-moment UI pattern this
  feature would extend already exists, it isn't a new capability to build.
- `feedback_catalog.js` / `docs/feedback_catalog.md` — AGENTS.md requires
  all student-facing messages route through `feedbackService.emit(id,
  opts)`. An award notification is student-facing feedback and must follow
  this system, not a bespoke toast.

---

## Data model (new)

Two models, following the same `(user, X)` shape as `StudentSkillMastery`:

```python
class AwardDefinition(models.Model):
    """A rule for earning an award. Authored by product/admin, not per-student."""
    key         = models.SlugField(unique=True)   # stable id, e.g. "unit_1_mastered"
    title       = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    icon        = models.CharField(max_length=40)  # references a static icon set, not free-form upload
    category    = models.CharField(max_length=20, choices=[
        ("mastery", "Skill Mastery"),
        ("streak", "Practice Streak"),
        ("milestone", "Milestone"),
    ])
    # Rule parameters are category-specific; kept as JSON rather than one
    # column per possible rule shape (mirrors skill_tags/tags JSONField
    # pattern already used elsewhere in apps/exercises/models.py)
    rule_params = JSONField(default=dict)
    active      = models.BooleanField(default=True)


class StudentAward(models.Model):
    """One earned instance. Unique per (user, award_definition)."""
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="awards")
    definition = models.ForeignKey(AwardDefinition, on_delete=models.CASCADE)
    earned_at  = models.DateTimeField(auto_now_add=True)
    # Denormalized context for display, avoids re-deriving "which skill/unit"
    # after the fact if taxonomy tags later change.
    context    = JSONField(default=dict, blank=True)  # e.g. {"skill_tag": "Note_Names"}

    class Meta:
        unique_together = ("user", "definition")
```

Rules live in `AwardDefinition` rows (data), not hardcoded Python
conditionals — new awards should be addable by inserting a row (or a
migration-time fixture), not by shipping new code per award. This mirrors
how `SkillPrerequisite` treats the mastery DAG as data rather than code.

### Award categories for v1

| Category | Example | Rule signal (already available) |
|---|---|---|
| Mastery | "Mastered Note Names" | `StudentSkillMastery.level == 'mastered'` transition (from `record_attempt()`'s existing `changes` dict) |
| Mastery | "Mastered a full unit" (all tags in one taxonomy unit at `mastered`) | `TaxonomyReader.get_unit()` tags ∩ mastered skill tags == unit tags |
| Streak | "3-day streak" / "7-day streak" | Needs a cross-skill practice-day signal — see Open Question 1 below, since `practice_days` today is stored **per skill tag**, not per student overall |
| Milestone | "First exercise completed" | `total_attempts` count across a user's `StudentSkillMastery` rows, or first `record_attempt()` call ever |
| Milestone | "100 exercises completed" | Sum of `total_attempts` across skill rows |

---

## Open Question 1: streaks need a new per-user daily-activity signal

`StudentSkillMastery.practice_days` (`apps/exercises/models.py:429`) is
scoped **per skill tag** — there is no existing "did this student practice
*anything* today" signal at the user level. Two options:

**Option A (recommended):** Add a lightweight `StudentActivityStreak`
model (`user` OneToOne, `current_streak`, `longest_streak`,
`last_active_date`), updated inside `record_attempt()` itself (one extra
write per submission, same transaction). This avoids scanning all of a
user's `StudentSkillMastery.practice_days` arrays or `PerformanceData`
timestamps to compute a streak on every dashboard page load.

**Option B:** Derive streaks on read from `MAX`/`DISTINCT` over
`PerformanceData.created` and `IdentificationAttempt.submitted_at` per
user. No new model, but recomputes from potentially large history on every
dashboard view — a cache or precomputed counter (Option A) is the more
scalable choice once class sizes grow, and the write-time cost is trivial
since it's colocated with a call that's already writing to the DB.

This spec recommends **Option A**. Needs product owner confirmation before
implementation since it's the one place this feature adds write load to
the hot submission path.

---

## Award-checking hook point

Single integration point: `record_attempt()` in `apps/exercises/mastery.py`
already returns a `changes` dict of skill-level transitions
(`{"Note_Names": {"old": "familiar", "new": "proficient"}}`). Extend the
same function (or a sibling called immediately after it from the same two
call sites) to:

1. Update `StudentActivityStreak` (if Option A).
2. Check `AwardDefinition` rows whose category matches what just changed
   (mastery transition → check mastery-category awards; any attempt →
   check streak/milestone-category awards).
3. Create `StudentAward` rows for newly-earned awards (idempotent via the
   `unique_together` constraint — `get_or_create`).
4. Return newly-earned awards alongside `mastery_changes` in the existing
   submit-endpoint JSON response (`apps/exercises/views.py:240,299`),
   so the frontend can trigger celebration UI in the same response it
   already handles level-ups in.

This keeps award-checking co-located with the one funnel point that
already handles mastery updates, rather than adding a second post-save
signal/hook elsewhere (avoids the "parallel logic in views vs. services"
anti-pattern AGENTS.md warns against).

---

## Frontend: celebration + display

**Celebration moment** (extends `exercise_score_card.js`, does not
replace it): when the submit response includes newly-earned awards, show
them in the same slide-up score card that already shows mastery level-ups
(`docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md`
Section 5), using the confetti trigger that already exists for
mastery-level-up (`exercise_score_card.js:87-101`) — no new animation
library, no new overlay component.

**Persistent display:** a new "Awards" section on the student progress
dashboard (`2026-07-02-student-dashboard-lti-design.md`, Part B) — a grid
of earned award icons with `earned_at` dates, plus (optional v2) locked/
grayed-out unearned awards to signal what's achievable.

**Feedback catalog compliance:** the award-earned notification text
("You earned: Note Names Mastered!") is a new entry in
`feedback_catalog.js` + `docs/feedback_catalog.md`
(category: `success`, surface: `anchored`, matching the existing
`exercise.grade.correct` pattern), emitted via `feedbackService.emit()` —
not a bespoke toast, per AGENTS.md's student-facing feedback rule.

---

## Open Question 2: teacher visibility

Should teachers see which awards their students have earned (on the
teacher class-progress dashboard,
`2026-07-02-teacher-dashboard-design.md`)? If yes, that's an additional
column/summary on that dashboard's per-student row — no new backend work
beyond a query already covered by `StudentAward`. Flagging as a scope
decision rather than assuming it.

---

## Out of scope for v1

- Points/leaderboards (ranking students against each other) — the product
  owner's framing was "shows students how they fare" and "awards for
  various things," which reads as individual achievement, not competitive
  ranking. Flag if competitive leaderboards are actually wanted — that's a
  materially different feature (needs privacy/opt-out consideration for
  minors, likely). Confirm before treating leaderboards as in scope.
- Custom/teacher-authored award definitions — v1 `AwardDefinition` rows are
  product/admin-authored, not a teacher-facing CMS.
- Physical/external reward redemption (e.g. printable certificates) — pure
  in-app display only.

---

## Files to change (implementation-time)

| File | Change |
|---|---|
| `apps/exercises/models.py` | New `AwardDefinition`, `StudentAward`, `StudentActivityStreak` models + migration |
| `apps/exercises/mastery.py` | `record_attempt()` (or a new sibling called alongside it) gains award-checking + streak update |
| `apps/exercises/views.py:240,299` | Submit endpoint response gains `new_awards` key alongside existing `mastery_changes` |
| `lab/static/js/src/config/feedback_catalog.js` | New award-earned entries |
| `docs/feedback_catalog.md` | Mirror the above |
| `lab/static/js/src/components/exercise_score_card.js` | Render newly-earned awards in the existing overlay |
| `apps/student/templates/student/progress_dashboard.html` | Awards grid (depends on the student dashboard spec being approved first) |
| Data migration or fixture | Seed initial `AwardDefinition` rows (mastery/streak/milestone set above) |
