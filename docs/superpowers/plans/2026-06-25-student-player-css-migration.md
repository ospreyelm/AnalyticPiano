# Student Player CSS Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the student player page (`/s/units/<str:unit_num>/play/`) to the modernized CSS architecture. This involves transitioning the template layout away from legacy `harmony.css` and unifying its canvas styles with the route-neutral `exercise-canvas.css`.

**Architecture:**
- Zone 1 ("desk" — management surfaces) uses `student/base.html` / `student.css`.
- Zone 2 ("instrument" — exercise canvas) uses `exercise-canvas.css`.
- Currently, student player (`player.html`) extends `__base.html` (which loads legacy `harmony.css`) and loads `player-canvas.css` (which contains legacy overrides/resets alongside canvas styles).
- To migrate, `player.html` will extend `student/base.html`, load `exercise-canvas.css`, and load a refactored `player-canvas.css` containing only student-specific layout and settings drawer styles.

**Tech Stack:** Django templates, vanilla CSS (custom properties), RequireJS, Django test client.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `apps/student/templates/student/player.html` | Modify | Extend `student/base.html`, load custom fonts, wire RequireJS boot blocks, link `exercise-canvas.css` and `player-canvas.css` |
| `apps/student/static/student/player-canvas.css` | Modify | Prune duplicated shared rules, add reset overrides to replace legacy `harmony.css` defaults |
| `apps/student/tests/test_design_css.py` | Modify | Update design CSS tests to assert correct stylesheet linkages and absence of `harmony.css` |

---

## Task 1: Rehearsal & De-duplication (Visual Safety)

- [ ] **Step 1: Wire in `exercise-canvas.css`**
  Add `<link href="{% static 'student/exercise-canvas.css' %}" rel="stylesheet">` in `player.html` right before the inclusion of `player-canvas.css`.
  
- [ ] **Step 2: Prune duplicates from `player-canvas.css`**
  Remove selectors and rules from `player-canvas.css` that are already defined in `exercise-canvas.css` (such as staff wrappers, canvas background, notifications, and click-note controllers).

- [ ] **Step 3: Verification**
  Run automated tests and verify visually in the browser that the student player interface is unaffected.

---

## Task 2: Base Shell Switch & harmony.css Removal

- [ ] **Step 1: Switch base layout template**
  Change the player template to extend `student/base.html` instead of `__base.html`.

- [ ] **Step 2: Configure RequireJS boot and parameters**
  Copy the RequireJS scripts and custom JSON parameters mapping from `__base.html` into a `{% block js_require %}` block in `player.html`.

- [ ] **Step 3: Declare Font-Face definitions**
  Declare custom music fonts (`Sebastian`, `MainSerifs`, `JazzSerifs`) inside a `<style>` block in the template head or inside `player-canvas.css`.

- [ ] **Step 4: Include notification template**
  Ensure `{% include "_notifications.html" %}` is loaded within the content area.

- [ ] **Step 5: Apply layout and form overrides**
  Resolve any alignment gaps on buttons or menus caused by the omission of `harmony.css` / `pure.css` defaults by adding targeted rules to `player-canvas.css`.

---

## Task 3: Test Updates & Automated Verification

- [ ] **Step 1: Update design tests**
  Modify tests in `apps/student/tests/test_design_css.py` to assert that `harmony.css` is not linked, and that `exercise-canvas.css` is correctly loaded.

- [ ] **Step 2: Verify test suite**
  Execute Django tests to ensure no regressions:
  ```bash
  python manage.py test apps.student
  ```
