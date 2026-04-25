# Monteverdi Branding And Identification Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch failed identification submits into a true correction flow by forcing `Practice` mode, and rename visible student-facing branding to `Monteverdi` without changing internal identifiers or the repository name.

**Architecture:** Keep the interaction change entirely in the existing identification frontend flow by modifying the failed-submit branch in `ExerciseContext` and letting `ExerciseSheet` re-render the existing mode toggle and submit controls. Keep branding scoped to student templates and visible page titles only, so the rename stays student-facing and does not spill into infrastructure or internal naming.

**Tech Stack:** Django templates, Django test client, RequireJS/Backbone-style frontend JS, Node-based JS checks, Python bytecode compile checks

---

## File Structure

### Identification recovery

- `lab/static/js/src/models/exercise_context.js`
  - Owns identification page submission, grading state, `sessionMode`, and `errorTally`.
- `lab/static/js/src/components/music/exercise_sheet.js`
  - Owns the rendered mode toggle, submit button visibility, and identification UI refresh.

### Student-facing branding

- `apps/student/templates/student/base.html`
  - Global student layout and default title/header brand.
- `apps/student/templates/student/home.html`
  - Student home page title.
- `apps/student/templates/student/unit.html`
  - Unit page title.
- `apps/student/templates/student/login.html`
  - Student login page title.
- `apps/student/templates/student/player.html`
  - Student player header if any visible product-name string appears there.

### Tests and verification

- `apps/student/tests/test_views.py`
  - Existing student page response/content tests; extend for visible branding assertions.
- `apps/exercises/tests/test_submission_views.py`
  - Existing completion payload tests; extend only if backend-visible response changes are needed.

---

### Task 1: Force Practice Mode After Failed Identification Submit

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:994-1080`
- Modify: `lab/static/js/src/components/music/exercise_sheet.js:735-764`
- Test: manual browser verification on student identification flow

- [ ] **Step 1: Write the failing behavior down in comments next to the submit branch**

Add a short orienting comment in `submitIdentPage()` before the failed-submit branch so the implementation intent is explicit:

```javascript
      // A failed submit should stop behaving like a final-check state.
      // Switch into practice mode so the student corrects with immediate feedback.
```

- [ ] **Step 2: Implement the mode switch in the failed-submit branch**

Update the `else` branch in `submitIdentPage()` so failed submit attempts force practice mode before the UI refresh fires:

```javascript
      } else {
        this.done = false;
        this.sealed = false;
        this.state =
          graded.result === this.grader.STATE.INCORRECT
            ? ExerciseContext.STATE.INCORRECT
            : ExerciseContext.STATE.WAITING;

        if ((options && options.mode) === "submit") {
          this.sessionMode = "practice";
          if (this.exercise && this.exercise.exerciseSheet) {
            this.exercise.exerciseSheet._currentMode = "practice";
          }
        }

        if (graded.result === this.grader.STATE.INCORRECT) {
          this.flawless = false;
          this.errorTally += 1;
        }
        if (this.exercise && typeof this.exercise.trigger === "function") {
          this.exercise.trigger("change");
        }
        this.trigger("graded");
      }
```

Implementation note: if `this.exercise.exerciseSheet` is not available in this codepath, keep the `sessionMode` change here and do the full UI sync in the sheet render task below rather than inventing a new coupling.

- [ ] **Step 3: Make the sheet re-read the active mode from context during render**

In `renderModeToggle()` or the nearest render/setup path in `exercise_sheet.js`, make sure `_currentMode` is refreshed from `exerciseContext.sessionMode` before the buttons are drawn:

```javascript
      this._currentMode = this.exerciseContext.sessionMode || this._currentMode || "submit";
```

Place this before the toggle buttons are marked active so the UI reflects the forced switch immediately after failed submit.

- [ ] **Step 4: Make submit-button visibility follow the refreshed mode**

Keep the existing submit button logic, but bind it to the refreshed `_currentMode` so the button hides once the flow switches to `practice`:

```javascript
      if (this._currentMode === "submit") {
        $('#identification-submit').show();
      } else {
        $('#identification-submit').hide();
      }
```

If this logic already exists, collapse it into one place used by both initial setup and re-render rather than duplicating it.

- [ ] **Step 5: Run targeted syntax checks**

Run:

```bash
node --check lab/static/js/src/models/exercise_context.js
node --check lab/static/js/src/components/music/exercise_sheet.js
```

Expected: both commands exit successfully with no output.

- [ ] **Step 6: Manually verify the interaction**

Use the existing student URL pattern with a Unit 1 identification exercise and verify:

1. Start in `Submit` mode.
2. Enter at least one wrong answer.
3. Press `Submit`.
4. Confirm the segmented control switches to `Practice`.
5. Confirm the old failed-submit feel is gone and corrections get immediate feedback.

Expected: the UI no longer remains in a misleading `Submit` state after a failed submit.

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "Force practice mode after failed identification submit"
```

---

### Task 2: Rename Visible Student Branding To Monteverdi

**Files:**
- Modify: `apps/student/templates/student/base.html`
- Modify: `apps/student/templates/student/home.html`
- Modify: `apps/student/templates/student/unit.html`
- Modify: `apps/student/templates/student/login.html`
- Inspect/modify if needed: `apps/student/templates/student/player.html`
- Test: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write the failing template assertions**

Add focused content assertions to `apps/student/tests/test_views.py` for the pages that render student-facing branding:

```python
    def test_student_pages_use_monteverdi_branding(self):
        self.client.force_login(self.student)

        for url in [
            reverse("student:home"),
            reverse("student:unit", kwargs={"unit_num": 1}),
            reverse("student:login"),
        ]:
            response = self.client.get(url)
            self.assertContains(response, "Monteverdi")
            self.assertNotContains(response, "HarmonyLab")
```

If unauthenticated access is required for `student:login`, keep that request outside the authenticated loop.

- [ ] **Step 2: Update the global student layout**

In `apps/student/templates/student/base.html`, change the default title and visible brand:

```html
  <title>{% block title %}Monteverdi{% endblock %}</title>
  ...
  <span class="s-header-brand">Monteverdi</span>
```

- [ ] **Step 3: Update page-specific student titles**

In each page template, replace old visible app-name titles with `Monteverdi`:

```html
{% block title %}Monteverdi{% endblock %}
```

and:

```html
{% block title %}Unit {{ unit_num }} — Monteverdi{% endblock %}
```

and:

```html
{% block title %}Sign In — Monteverdi{% endblock %}
```

Only change visible titles and student-facing strings. Do not rename route names, template paths, or internal identifiers.

- [ ] **Step 4: Search for remaining student-visible old branding**

Run:

```bash
rg -n "HarmonyLab|Harmony Lab" apps/student/templates apps/student/views.py
```

Expected: no remaining old product-name strings that are visible to students, or a short reviewed list of intentionally internal references.

- [ ] **Step 5: Run the targeted Django student view tests**

Run:

```bash
python manage.py test apps.student.tests.test_views -v 2
```

Expected: PASS. If local DB access blocks this in the current environment, record that and at minimum run the template-content assertions manually in-browser.

- [ ] **Step 6: Commit**

```bash
git add apps/student/templates/student/base.html apps/student/templates/student/home.html apps/student/templates/student/unit.html apps/student/templates/student/login.html apps/student/tests/test_views.py
git commit -m "Rename student-facing branding to Monteverdi"
```

---

### Task 3: Final Verification Sweep

**Files:**
- Inspect: `lab/static/js/src/models/exercise_context.js`
- Inspect: `lab/static/js/src/components/music/exercise_sheet.js`
- Inspect: `apps/student/templates/student/base.html`
- Inspect: `apps/student/templates/student/home.html`
- Inspect: `apps/student/templates/student/unit.html`
- Inspect: `apps/student/templates/student/login.html`

- [ ] **Step 1: Run frontend checks together**

Run:

```bash
node --check lab/static/js/src/models/exercise_context.js
node --check lab/static/js/src/components/music/exercise_sheet.js
```

Expected: both pass with no output.

- [ ] **Step 2: Run the existing score-card regression test**

Run:

```bash
node lab/static/js/src/components/exercise_score_card.test.js
```

Expected: all tests pass. This confirms the earlier corrected/mastered distinction still works after the flow change.

- [ ] **Step 3: Manual browser verification**

Verify all of the following in the student app:

1. Failed identification submit forces `Practice` mode.
2. Correcting answers in that state gives immediate feedback.
3. Final completion still shows the result card.
4. Student-facing pages show `Monteverdi`.

Expected: no student-facing `HarmonyLab` branding remains on the verified pages, and the identification flow no longer leaves students in a misleading failed-submit state.

- [ ] **Step 4: Commit verification-safe cleanup if needed**

If the verification pass required tiny follow-up fixes, commit them explicitly:

```bash
git add lab/static/js/src/models/exercise_context.js lab/static/js/src/components/music/exercise_sheet.js apps/student/templates/student/base.html apps/student/templates/student/home.html apps/student/templates/student/unit.html apps/student/templates/student/login.html apps/student/tests/test_views.py
git commit -m "Polish Monteverdi student flow verification fixes"
```

If no cleanup was needed, skip this step.

---

## Self-Review

### Spec coverage

- Identification failed-submit recovery: covered by Task 1.
- Copy and mode alignment: covered by Task 1.
- Student-facing rename to `Monteverdi`: covered by Task 2.
- Explicitly keeping repo/internal naming unchanged: preserved throughout; no task touches repo or internal naming.
- Verification requirements: covered by Task 3.

### Placeholder scan

- No `TODO`/`TBD` placeholders left in tasks.
- Each command is concrete.
- Code changes are shown inline where behavior changes.

### Type consistency

- Uses existing `sessionMode`, `_currentMode`, `ExerciseContext.STATE`, and `submitIdentPage()` names already present in the codebase.
- Branding tasks only touch templates and tests; no conflicting renamed identifiers introduced.

