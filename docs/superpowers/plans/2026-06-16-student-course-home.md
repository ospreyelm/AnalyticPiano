# student-course-home

**Phase 0, item 2** of the teacher experience meta-plan
([2026-06-12-teacher-experience-meta-plan.md](2026-06-12-teacher-experience-meta-plan.md)).

Settled decisions D4 (course-first home) and Q8 (prioritize, not hide) already
implemented at a structural level — enrolled students see course panels above the
collapsible full curriculum. This plan closes the remaining gaps:

1. Course panels on the home page lack a direct "Next up →" link; students must
   click through to the course detail page to find their next assignment.
2. After joining a course, the success banner names the group but provides no
   direct path to the first assigned work.

---

## Design

### What determines "next up"

First open, published PCO for the course, sorted by `due_date ASC` (nulls last),
then by `order ASC`. A PCO is "open" when:
- `publish_date` is null or in the past (published)
- The student has not completed it (`pco_pct < 100`)

### Play URL

Use `_playlist_stats(playlist, raw_by_pk[playlist.pk])["url"]` — already
computes `next_exercise_num` (first incomplete exercise index) and builds the
correct player URL. This is already called in `_build_course_panels()`, so no
extra DB hit.

### Fallback behavior (differs by call site)

- **`_build_course_panels()`**: if no open PCO exists (all complete or all
  upcoming), `next_url` is `None` and the row is not rendered.
- **`JoinCourseView.post()`**: if no published open PCO found, or if the PCO's
  playlist has no `unit:N` tag, **skip storing** `next_assignment_url` in session.
  The banner then shows only the group name, as before. This site never falls
  back to a course detail URL because the banner link is optional; falling back
  would be confusing ("Start: view your course" makes no sense as button text).
  `_build_course_panels()` always has a course detail URL available so it can
  fall back cleanly there.

### HTML structure — no nested anchors

The current `.s-course-panel` in `home.html` is an `<a>` element. Adding a
"Next up" `<a>` inside it would be invalid HTML. The fix: change the card
container from `<a>` to `<div>`, and add two explicit links:

```
<div class="s-course-panel">
  <div class="s-course-panel-header"> ... title + progress % ... </div>
  [optional] <a class="s-course-next" href="{{ panel.next_url }}"> Next up ... </a>
  <div class="s-course-panel-footer">
    ... open/due counts ...
    <a href="{% url 'student:course-detail' pk=panel.course_pk %}">View course →</a>
  </div>
</div>
```

The existing hover/transition styles on `.s-course-panel` apply to the `div`
unchanged.

### CSS — no new inline styles

`home.html` already has a large inline `<style>` block with all course-panel
and next-up rules. New styles go into `apps/student/static/student/student.css`
using existing design tokens. The inline block is not removed wholesale (scope
creep), but no additional rules are added inline.

### Session keys added by JoinCourseView

- `joined_course` — group name (existing)
- `next_assignment_url` — player URL from `_playlist_stats()["url"]` (new, optional)
- `next_assignment_name` — playlist name (new, optional)

All three are popped by `HomeView.get()` in one pass.

---

## Implementation tasks

- [ ] **[Tier 2]** `_build_course_panels()` — after existing `pco_pct` computation,
  track the best "next up" candidate per course:
  - Collect open (published, `pco_pct < 100`) PCOs
  - Sort by `(due_date is None, due_date, pco.order)`
  - Winner's `next_url = stats["url"]` (already computed; no extra DB hit)
  - `next_name = pl.name`, `next_due_label = _unit_date_labels({"due": pco.due_date, ...})`
  - If no open PCO, `next_url = None`

- [ ] **[Tier 2]** `JoinCourseView.post()` — after `group.members.add(request.user)`:
  - Query `PlaylistCourseOrdered.objects.filter(course__visible_to=group)` ordered
    by `due_date ASC NULLS LAST, order ASC`
  - Pick first PCO where `publish_date` is null or in the past
  - Compute URL via `_playlist_stats_by_id(request.user, pco.playlist.id)["url"]`
    (accepts one playlist; acceptable since this is a single post-action, not a
    bulk home render)
  - If found: store `next_assignment_url` and `next_assignment_name` in session
  - If not found or no published PCO: skip (banner shows only group name)

- [ ] **[Tier 2]** `HomeView.get()` — pop `next_assignment_url` and
  `next_assignment_name` alongside existing `joined_course` pop; add both to context

- [ ] **[Tier 2]** `home.html` — restructure course panel from `<a>` to `<div>`;
  add separate "View course →" link in footer; add "Next up →" `<a>` row between
  header and footer (only when `panel.next_url`)

- [ ] **[Tier 2]** `home.html` — join banner: add `<a>` with `next_assignment_name`
  (only when `next_assignment_url` in context); no new inline styles — put any new
  banner-link rule in `student.css`

- [ ] **[Tier 1]** `apps/student/static/student/student.css` — add any new rules
  needed for the banner link and next-up row; use existing `--teal`, `--border`,
  `--surface-2` tokens

- [ ] **[Tier 1]** Tests (`test_home_course_panels.py` or extend `test_course_connection.py`):
  - `_build_course_panels` returns `next_url` pointing to the earliest-due open PCO
  - `_build_course_panels` returns `next_url=None` when all PCOs are complete
  - `_build_course_panels` returns `next_url=None` when all PCOs are upcoming
  - `_build_course_panels` sorts by due date (null last) over order
  - `JoinCourseView.post()` stores `next_assignment_url` in session when a
    published open PCO exists
  - `JoinCourseView.post()` omits `next_assignment_url` when no published PCO
  - `HomeView.get()` pops all three session keys; context contains expected values
  - Partially completed playlist: `next_url` points to first incomplete exercise
    (not exercise 1)

- [ ] **[Tier 1]** Update `docs/teacher_experience_launch_followups.md` — mark item 4
  (course-focused student home section) and UX polish item 3 (join success) resolved

---

## Out of scope

- Removing the existing large inline `<style>` block from `home.html` (CSS identity
  work belongs in Phase 5)
- Course detail page changes (already shows open/upcoming/completed sections)
- Multiple enrolled courses: each panel independently shows its own next-up row
- Students with no enrolled course: unchanged (resume card + curriculum as today)
