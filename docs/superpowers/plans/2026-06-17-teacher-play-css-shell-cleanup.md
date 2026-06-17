# Teacher Play CSS Shell Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair `/teacher/play/` as a coherent Monteverdi teacher authoring workspace by removing visible legacy lab chrome, scoping teacher play layout into `teacher-play.css`, and starting the shared exercise-canvas CSS extraction without destabilizing the student player.

**Architecture:** Keep the current functional student player stable. Add a full-width teacher workspace variant to `teacher/base.html`, move teacher-play layout out of inline CSS into a scoped `teacher-play.css`, preserve legacy AMD mount points explicitly, and introduce a route-neutral `exercise-canvas.css` that `/teacher/play/` consumes first. Student `harmony.css` removal is intentionally deferred.

**Tech Stack:** Django templates, Django `TestCase` smoke tests, vanilla CSS custom properties, RequireJS legacy front-end boot, existing AMD exercise components.

**Spec:** `docs/superpowers/specs/2026-06-17-teacher-play-css-shell-cleanup-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `apps/teacher/templates/teacher/base.html` | Modify | Add `main_class` block so selected teacher pages can opt out of the narrow `.t-main` container |
| `apps/teacher/static/teacher/teacher.css` | Modify | Add `.t-main--workspace` and reusable `.u-hidden` utility |
| `apps/teacher/static/teacher/teacher-play.css` | Create | Teacher `/teacher/play/` workspace layout, toolbar, save panel, hidden legacy mounts |
| `apps/student/static/student/exercise-canvas.css` | Create | Route-neutral exercise canvas rules used by teacher play first |
| `lab/templates/play.html` | Modify | Remove visible legacy header/menu partials, load scoped CSS, preserve required AMD mount points |
| `lab/tests/test_play_view.py` | Modify | Add regression coverage for CSS links, removed legacy chrome, required JS hooks/mounts |

---

## Task 1: Update Teacher Play Smoke Tests First

**Files:**
- Modify: `lab/tests/test_play_view.py`

This task defines the desired behavior before changing templates.

- [ ] **Step 1: Replace the current CSS/chrome tests**

Open `lab/tests/test_play_view.py`. Replace the test methods from
`test_play_view_loads_player_canvas_css` through
`test_play_view_save_panel_preserves_js_hooks` with this block:

```python
    def test_play_view_loads_scoped_teacher_and_canvas_css(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "student/exercise-canvas.css")
        self.assertContains(resp, "teacher/teacher-play.css")
        self.assertNotContains(resp, "student/player-canvas.css")

    def test_play_view_boots_requirejs(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "require.js")
        self.assertContains(resp, "require(['app/main']);")

    def test_play_view_does_not_load_harmony_css(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertNotContains(resp, "css/harmony.css")

    def test_play_view_loads_notation_fonts(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "Sebastian-FigBass-Modified.woff")

    def test_play_view_uses_workspace_main_class(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'class="t-main t-main--workspace"')
        self.assertContains(resp, 'class="t-play-workspace js-fade-in fade"')

    def test_play_view_does_not_render_legacy_lab_header_menu(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertNotContains(resp, "Dashboard")
        self.assertNotContains(resp, "New Play View")
        self.assertNotContains(resp, "DISPLAY OPTIONS")
        self.assertNotContains(resp, "_header_music.html")

    def test_play_view_preserves_required_legacy_mount_points(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'id="mainmenu"')
        self.assertContains(resp, 'class="js-keysignature-widget"')
        self.assertContains(resp, 'class="js-notation-opts-widget"')
        self.assertContains(resp, 'class="js-keyboardsize settings-inline"')
        self.assertContains(resp, 'class="js-octaveadjustment settings-inline"')
        self.assertContains(resp, 'class="js-keyboardshortcuts settings-inline"')

    def test_play_view_toolbar_preserves_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'js-btn-upload-json')
        self.assertContains(resp, 'js-btn-pristine')
        self.assertContains(resp, 'js-btn-import-musicxml')
        self.assertContains(resp, 'id="musicxml-upload-input"')
        self.assertContains(resp, 'id="play-meter-select"')

    def test_play_view_audio_controls_preserve_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'id="mute-toggle"')
        self.assertContains(resp, 'id="volume"')
        self.assertContains(resp, 'id="midi-switch"')

    def test_play_view_save_panel_uses_t_classes(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 't-card-title')
        self.assertContains(resp, 't-btn t-btn-primary')

    def test_play_view_save_panel_preserves_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'id="play-save-description"')
        self.assertContains(resp, 'id="play-save-submit"')
        self.assertContains(resp, 'id="play-save-create-transpositions"')
        self.assertContains(resp, 'name="modes"')
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected result before implementation: failures for missing `student/exercise-canvas.css`,
missing `teacher/teacher-play.css`, still-present `student/player-canvas.css`, missing
workspace main class, and visible legacy menu text.

- [ ] **Step 3: Commit the failing test only if working in TDD-sized commits**

```bash
git add lab/tests/test_play_view.py
git commit -m "test: capture target teacher play shell behavior"
```

If the branch convention prefers one commit for the whole visual shell change, skip this
commit and keep the test staged later with implementation.

---

## Task 2: Add Full-Width Teacher Workspace Hook

**Files:**
- Modify: `apps/teacher/templates/teacher/base.html`
- Modify: `apps/teacher/static/teacher/teacher.css`

- [ ] **Step 1: Add the `main_class` block**

In `apps/teacher/templates/teacher/base.html`, replace:

```html
  <main class="t-main">
    {% block content %}{% endblock %}
  </main>
```

with:

```html
  <main class="t-main {% block main_class %}{% endblock %}">
    {% block content %}{% endblock %}
  </main>
```

Do not move the existing `body_extra`, `js_require`, or `js_extra` blocks.

- [ ] **Step 2: Add workspace and hidden utility CSS**

In `apps/teacher/static/teacher/teacher.css`, after the existing `.t-main` rule, add:

```css
.t-main--workspace {
  max-width: none;
  padding: 0;
}

.u-hidden {
  display: none !important;
}
```

This keeps ordinary teacher management pages constrained and gives `/teacher/play/`
a page-level escape hatch.

- [ ] **Step 3: Run existing teacher base tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.teacher.tests.test_views_db.TeacherBaseTemplateTests apps.teacher.tests.test_views_db.UrlResolutionTests -v 2
```

Expected: all selected tests pass.

---

## Task 3: Create Scoped Teacher Play CSS

**Files:**
- Create: `apps/teacher/static/teacher/teacher-play.css`

- [ ] **Step 1: Create `teacher-play.css`**

Create `apps/teacher/static/teacher/teacher-play.css` with this content:

```css
/* Teacher Play workspace.
   Route-specific layer for /teacher/play/. Keep selectors scoped to
   .t-play-workspace except where legacy AMD components require fixed IDs. */

.t-play-workspace {
  min-height: calc(100vh - 52px);
  background: var(--surface);
  color: var(--text);
}

.t-play-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}

.t-play-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.t-play-inline-label {
  display: inline-flex;
  align-items: center;
  margin: 0 0 0 4px;
  white-space: nowrap;
}

.t-play-meter-select {
  width: auto;
  min-width: 92px;
  padding: 5px 9px;
  font-size: var(--text-sm);
}

.t-play-audio-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.t-play-control-btn {
  min-height: 32px;
  padding: 5px 10px;
  white-space: nowrap;
}

.t-play-hidden-mounts {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}

.t-play-stage {
  width: calc(100% - 24px);
  max-width: none;
  margin: 10px auto 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
  grid-template-areas:
    "staff save"
    "piano save";
  gap: 12px;
  align-items: stretch;
  padding: 14px 12px 16px;
  box-sizing: border-box;
  border: 1px solid rgba(125, 101, 74, 0.14);
  border-radius: 24px;
  background: linear-gradient(180deg, #fbf7ef 0%, #f1e8db 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78), 0 18px 40px rgba(38, 27, 17, 0.08);
}

.t-play-stage #staff-area {
  grid-area: staff;
  min-width: 0;
  padding: 0;
}

.t-play-stage #piano {
  grid-area: piano;
  min-width: 0;
}

.t-play-save-panel {
  grid-area: save;
  min-width: 0;
  max-height: calc(100vh - 118px);
  overflow-y: auto;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(38, 27, 17, 0.08);
}

.t-play-save-panel .play-save-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}

.t-play-save-panel .play-save-field {
  margin-bottom: 0;
}

.t-play-save-panel .play-save-options {
  display: grid;
  gap: 8px;
}

.t-play-save-panel .play-save-actions {
  display: flex;
  justify-content: flex-start;
  margin-top: 14px;
}

.t-play-musicxml-options {
  border-top: 1px solid var(--border);
  padding-top: 10px;
  margin-top: 5px;
}

.t-play-musicxml-title {
  font-size: var(--text-sm);
  margin: 0 0 8px;
  color: var(--text);
  font-weight: 700;
  font-family: var(--font-ui);
}

.t-play-musicxml-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.t-play-compact-label {
  font-size: var(--text-xs);
  margin-bottom: 2px;
}

.t-play-compact-input {
  padding: 5px 7px;
}

@media (max-width: 1020px) {
  .t-play-stage {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "staff"
      "piano"
      "save";
  }

  .t-play-save-panel {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .t-play-topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .t-play-toolbar,
  .t-play-audio-controls {
    width: 100%;
  }

  .t-play-control-btn,
  .t-play-toolbar .t-btn,
  .t-play-meter-select {
    min-height: 44px;
  }

  .t-play-musicxml-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Commit CSS after template wiring passes**

Do not commit this file alone until Task 4 wires it into `play.html`; otherwise it is
dead CSS.

---

## Task 4: Rewrite `lab/templates/play.html` Shell

**Files:**
- Modify: `lab/templates/play.html`

This task removes visible legacy lab chrome while preserving the fixed selectors the
RequireJS modules still use.

- [ ] **Step 1: Update `head_extra`**

In `lab/templates/play.html`, replace the current `{% block head_extra %}` content with:

```html
{% block head_extra %}
<link href="{% static 'student/exercise-canvas.css' %}" rel="stylesheet">
<link href="{% static 'teacher/teacher-play.css' %}" rel="stylesheet">
<style>
@font-face { font-family: "Sebastian"; src: url("{% static 'fonts/Sebastian-FigBass-Modified.woff' %}") format("woff"); }
@font-face { font-family: "MainSerifs"; src: url("{% static 'fonts/Alegreya-Regular-Modified.woff' %}") format("woff"); }
@font-face { font-family: "JazzSerifs"; src: url("{% static 'fonts/Alegreya-Regular-Modified-v2.woff' %}") format("woff"); }
</style>
{% endblock %}
```

This keeps notation fonts inline temporarily because they are template-static URL
dependent. Do not include `student/player-canvas.css` on this route.

- [ ] **Step 2: Add workspace main class**

Add this block after `{% load static %}`:

```html
{% block main_class %}t-main--workspace{% endblock %}
```

- [ ] **Step 3: Replace the top of the content block**

In `{% block content %}`, replace:

```html
<div id="container" class="js-fade-in fade" style="opacity: 0;">
	{% include "_header_music.html" %}
	{% include "_menu_music.html" %}
	{% include "_menu_piano.html" %}
	{% include "_notifications.html" %}
	<div class="harmony-ui">
```

with:

```html
<div id="container" class="t-play-workspace js-fade-in fade" style="opacity: 0;">
	<section class="t-play-topbar" aria-label="Authoring controls">
		<div class="t-play-toolbar">
			<button type="button" class="t-btn t-btn-ghost t-btn-sm js-btn-upload-json" title="Create exercise">Save</button>
			<div id="save-feedback" class="feedback-inline" aria-live="polite"></div>
			<button type="button" class="t-btn t-btn-ghost t-btn-sm js-btn-pristine" title="Reload sheet music">&#8635; Reload</button>
			<button type="button" class="t-btn t-btn-ghost t-btn-sm js-btn-import-musicxml" title="Import MusicXML">Import MusicXML</button>
			<input type="file" id="musicxml-upload-input" accept=".xml,.musicxml,.mxl" class="u-hidden" />
			<label for="play-meter-select" class="t-label t-play-inline-label">Meter</label>
			<select id="play-meter-select" class="t-input t-play-meter-select" title="Set meter (auto-suggests barlines)">
				<option value="">Free</option>
				<option value="2/4">2/4</option>
				<option value="3/4">3/4</option>
				<option value="4/4">4/4</option>
				<option value="6/8">6/8</option>
			</select>
		</div>
		<div class="t-play-audio-controls" aria-label="Audio and MIDI controls">
			<button id="mute-toggle" type="button" class="t-btn t-btn-ghost t-btn-sm t-play-control-btn" title="Toggle mute">Mute</button>
			<button id="volume" type="button" class="t-btn t-btn-ghost t-btn-sm t-play-control-btn" title="Adjust volume">mf</button>
			<button id="midi-switch" type="button" class="t-btn t-btn-ghost t-btn-sm t-play-control-btn" title="Turn MIDI input on or off">MIDI</button>
		</div>
	</section>
	<div id="legacy-play-mounts" class="t-play-hidden-mounts" aria-hidden="true">
		<div id="mainmenu">
			<div class="js-keysignature-widget"></div>
			<div class="js-notation-opts-widget"></div>
			<div class="js-keyboardsize settings-inline"></div>
			<div class="js-octaveadjustment settings-inline"></div>
			<div class="js-keyboardshortcuts settings-inline"></div>
		</div>
	</div>
	{% include "_notifications.html" %}
	<div class="harmony-ui t-play-stage">
```

This removes the visible old partials but preserves the hooks those partials were
providing.

- [ ] **Step 4: Remove duplicated toolbar controls inside `#staff-area`**

Inside `<div id="staff-area" class="content-area">`, replace the full `#staff-toolbar`
contents with an empty mount:

```html
			<div id="staff-toolbar" class="t-play-staff-toolbar"></div>
```

The Save/Reload/MusicXML/Meter controls now live in the top authoring toolbar.

- [ ] **Step 5: Scope staff and save panel classes**

Change:

```html
			<div id="staff-area" class="content-area">
```

to:

```html
			<div id="staff-area" class="content-area t-play-staff-area">
```

Change:

```html
		<aside id="play-save-panel" class="play-save-panel" aria-labelledby="play-save-panel-title">
```

to:

```html
		<aside id="play-save-panel" class="play-save-panel t-play-save-panel" aria-labelledby="play-save-panel-title">
```

- [ ] **Step 6: Remove inline styles from MusicXML option block**

Replace the opening MusicXML block:

```html
				<div id="play-save-musicxml-options" class="play-save-field play-save-field-wide t-form-row" style="display:none; border-top: 1px solid #d9c9a9; padding-top: 10px; margin-top: 5px;">
					<h3 style="font-size: 13px; margin: 0 0 8px 0; color: #2d251d; font-weight: 700;">MusicXML Import Options</h3>
					<div style="display: flex; gap: 10px;">
```

with:

```html
				<div id="play-save-musicxml-options" class="play-save-field play-save-field-wide t-form-row t-play-musicxml-options u-hidden">
					<h3 class="t-play-musicxml-title">MusicXML Import Options</h3>
					<div class="t-play-musicxml-grid">
```

For each of the three inner option columns, replace:

```html
						<div style="flex: 1;">
```

with:

```html
						<div>
```

Replace the three labels' inline styles with:

```html
							<label for="musicxml-start-measure" class="t-label t-play-compact-label">Start Measure</label>
							<label for="musicxml-end-measure" class="t-label t-play-compact-label">End Measure</label>
							<label for="musicxml-complexity" class="t-label t-play-compact-label">Complexity</label>
```

Replace the three number inputs' inline style `style="padding: 4px 6px;"` by adding
`t-play-compact-input` to the class list:

```html
class="play-save-input t-input t-play-compact-input"
```

Important: JavaScript may currently set `style.display` on
`#play-save-musicxml-options`. If it only toggles inline display, the `u-hidden` class
would keep it hidden. During implementation, either update the JS toggle to remove/add
`u-hidden`, or keep `style="display:none;"` on this specific element and do not use
`u-hidden` there. Prefer updating the JS if the toggle location is clear; otherwise keep
`style="display:none;"` and leave this one inline display style until a JS cleanup pass.

- [ ] **Step 7: Run teacher play tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected: tests still fail only because `student/exercise-canvas.css` does not exist
yet. All legacy-chrome and workspace-class assertions should pass.

---

## Task 5: Create Initial `exercise-canvas.css`

**Files:**
- Create: `apps/student/static/student/exercise-canvas.css`

This is the first shared extraction. Keep it conservative: copy only the rules needed
for `/teacher/play/` to render the staff, piano, feedback, and notifications cleanly.
Do not edit `student/player-canvas.css` in this task.

- [ ] **Step 1: Create the shared canvas stylesheet**

Create `apps/student/static/student/exercise-canvas.css` with:

```css
/* Shared exercise canvas layer.
   Used by /teacher/play/ first. Student migration comes later. */

#container {
  opacity: 1 !important;
  background: transparent;
  margin: 0;
  padding: 0;
}

#notifications {
  display: block;
  width: 95vw;
  max-width: 900px;
  margin: 8px auto;
  text-align: left;
}

.notifications-wrapper {
  display: block;
}

.notification {
  position: relative;
  margin-bottom: 12px;
  border-radius: 16px;
  padding: 14px 18px;
  font-family: var(--font-body);
  font-size: 0.85rem;
  box-shadow: 0 4px 20px rgba(38, 27, 17, 0.05);
  border: 1px solid var(--border);
  background-color: var(--surface-2);
  color: var(--text);
  display: block;
  transition: all 200ms ease;
}

.notification.warning {
  background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
  border-color: rgba(217, 119, 6, 0.28);
  color: #78350f;
}

.notification.warning .title {
  color: #b45309;
  font-weight: 700;
  font-size: 0.9rem;
}

.notification .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(120, 53, 15, 0.18);
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.7);
  color: #78350f;
  transition: all 150ms ease;
  user-select: none;
}

#staff-area {
  width: 100%;
  max-width: none;
  margin: 0 auto;
  box-sizing: border-box;
  position: relative;
}

#staff-toolbar {
  margin: 8px auto;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  width: 100%;
}

#staffwrapper {
  position: relative;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 8px;
  height: 400px;
  overflow-x: auto;
  overflow-y: hidden;
}

#user-interaction-solicitation {
  position: absolute;
  left: 50%;
  top: 58px;
  transform: translateX(-50%);
  z-index: 5;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: min(960px, calc(100% - 48px));
  max-width: calc(100% - 48px);
  box-sizing: border-box;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: rgba(44, 38, 34, 0.13);
  font-family: var(--font-ui);
  font-size: clamp(2.5rem, 5.8vw, 6.5rem);
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0;
  text-align: center;
  text-transform: uppercase;
  pointer-events: none;
  white-space: nowrap;
}

#piano {
  width: 100%;
  max-width: none;
  margin: 6px auto 0;
  padding: 10px 8px;
  box-sizing: border-box;
  overflow-x: auto;
  position: relative;
  border-radius: 24px;
  background: linear-gradient(180deg, #241c17 0%, #15100d 100%);
  border: 1px solid rgba(0, 0, 0, 0.34);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    inset 0 -16px 24px rgba(255, 255, 255, 0.03),
    0 18px 34px rgba(0, 0, 0, 0.22);
}

#piano::before {
  content: "";
  position: absolute;
  left: 18px;
  right: 18px;
  top: 0;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(158, 46, 46, 0.2), rgba(187, 57, 57, 0.95), rgba(158, 46, 46, 0.2));
}

.keyboard-wrapper {
  margin: 0 auto !important;
}

.keyboard-input-mode {
  max-width: 100%;
}

.keyboard-area {
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.keyboard .qwerty-labels {
  z-index: 4;
}

.keyboard .qwerty-key-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 0 3px;
  border-radius: 7px;
  border: 1px solid rgba(115, 91, 64, 0.38);
  background: linear-gradient(180deg, rgba(251, 246, 238, 0.98) 0%, rgba(232, 220, 202, 0.98) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82), 0 1px 2px rgba(36, 26, 18, 0.14);
  color: #2e2217;
  font-family: var(--font-ui);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1;
  text-transform: uppercase;
  pointer-events: none;
  user-select: none;
  -webkit-font-smoothing: antialiased;
}

.keyboard .qwerty-key-badge.black {
  padding: 0 2px;
  border-color: rgba(255, 255, 255, 0.18);
  background: linear-gradient(180deg, rgba(71, 64, 59, 0.96) 0%, rgba(26, 22, 20, 0.96) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 2px 4px rgba(0, 0, 0, 0.28);
  color: rgba(255, 248, 238, 0.96);
}

.feedback-bubble {
  position: absolute;
  z-index: 1000;
  max-width: 280px;
  padding: 8px 12px;
  border-radius: 6px;
  background: #2b2f36;
  color: #fff;
  font-size: 13px;
  line-height: 1.35;
  box-shadow: 0 2px 10px rgba(0,0,0,.25);
  pointer-events: none;
}

.feedback-bubble--mistake {
  background: #8a3324;
}

.feedback-bubble--success {
  background: #2f6b3a;
}

.feedback-control-flash {
  animation: feedback-shake .4s ease;
}

@keyframes feedback-shake {
  0%,100% { transform: translateX(0); }
  25% { transform: translateX(-3px); }
  75% { transform: translateX(3px); }
}

.feedback-inline {
  font-size: 13px;
  color: #444;
  opacity: 0;
  transition: opacity .2s ease;
}

.feedback-inline.is-visible {
  opacity: 1;
}

.feedback-inline strong {
  color: #1f2937;
}
```

This is deliberately smaller than `player-canvas.css`. It avoids student topbar,
settings drawer, answer bar, and identification relocation rules.

- [ ] **Step 2: Run teacher play tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected: all tests pass.

---

## Task 6: Static Regression Scans

**Files:**
- No source changes expected unless scans find problems.

- [ ] **Step 1: Confirm no legacy partial includes remain in teacher play**

Run:

```bash
rg -n "_header_music|_menu_music|_menu_piano|student/player-canvas.css|<style>|style=" lab/templates/play.html
```

Expected:

- No `_header_music`, `_menu_music`, `_menu_piano`.
- No `student/player-canvas.css`.
- One `<style>` block remains only for notation `@font-face`.
- `style="opacity: 0;"` may remain on `#container` because existing JS fade-in expects it.
- If `#play-save-musicxml-options` still uses `style="display:none;"`, document that as a deliberate temporary compatibility exception.

- [ ] **Step 2: Confirm new CSS is scoped**

Run:

```bash
rg -n "^(#|body|\\.harmony-ui|\\.play-save|\\.notification|\\.feedback)" apps/teacher/static/teacher/teacher-play.css
```

Expected: no unscoped global selectors except selectors intentionally nested under
`.t-play-*`. If this command returns unscoped selectors, either scope them or move
route-neutral rules to `exercise-canvas.css`.

- [ ] **Step 3: Confirm student template is unchanged**

Run:

```bash
git diff -- apps/student/templates/student/player.html apps/student/static/student/player-canvas.css
```

Expected: no diff in this phase.

---

## Task 7: Browser Verification

**Files:**
- No source changes expected unless screenshots reveal layout regressions.

- [ ] **Step 1: Start local Django server**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py runserver 127.0.0.1:8001 --noreload
```

Expected: server starts without errors.

- [ ] **Step 2: Verify `/teacher/play/` visually**

Open:

```text
http://127.0.0.1:8001/teacher/play/
```

Check:

- Teacher nav is present once.
- No raw bullet list.
- No visible `Dashboard`, `New Play View`, or `DISPLAY OPTIONS` legacy row.
- Save/Reload/Import MusicXML/Meter/Mute/Volume/MIDI are in a coherent topbar.
- Staff area, save panel, and piano do not overlap.
- MusicXML import button still opens the file picker.
- Save panel scrolls internally when content is taller than the viewport.

- [ ] **Step 3: Verify narrow viewport**

At a narrow viewport around 390px wide, check:

- Toolbar wraps without text overflow.
- Touch targets are at least 44px tall.
- Staff and piano retain internal horizontal scroll.
- Save panel moves below the stage and does not overlap the staff.

- [ ] **Step 4: Verify student player is unchanged**

Open a known student player route such as:

```text
http://127.0.0.1:8001/s/units/9/play/?playlist=PA02PY&exercise_num=1
```

Check:

- Student topbar still matches the current good screenshot.
- Staff, instruction panel, and piano still render.
- Settings drawer opens.
- No teacher toolbar appears.

---

## Task 8: Final Test Run and Commit

**Files:**
- All changed files from Tasks 1-5.

- [ ] **Step 1: Run targeted Django tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view apps.teacher.tests.test_views_db.TeacherBaseTemplateTests apps.teacher.tests.test_views_db.UrlResolutionTests -v 2
```

Expected: all tests pass.

- [ ] **Step 2: Review diff**

Run:

```bash
git diff -- lab/templates/play.html lab/tests/test_play_view.py apps/teacher/templates/teacher/base.html apps/teacher/static/teacher/teacher.css apps/teacher/static/teacher/teacher-play.css apps/student/static/student/exercise-canvas.css
```

Expected:

- `play.html` no longer includes old lab header/menu partials.
- `play.html` loads `student/exercise-canvas.css` and `teacher/teacher-play.css`.
- Required JS IDs/classes are preserved.
- New CSS is scoped and route-specific.
- Student player files are untouched.

- [ ] **Step 3: Commit**

```bash
git add lab/templates/play.html lab/tests/test_play_view.py apps/teacher/templates/teacher/base.html apps/teacher/static/teacher/teacher.css apps/teacher/static/teacher/teacher-play.css apps/student/static/student/exercise-canvas.css
git commit -m "refactor(teacher-play): replace legacy chrome with scoped authoring shell"
```

---

## Deferred Follow-Up Plan

After this plan ships and screenshots are stable, write a smaller follow-up plan for:

1. Loading `exercise-canvas.css` in the student player before `player-canvas.css`.
2. Removing duplicated shared rules from `player-canvas.css`.
3. Keeping `harmony.css` loaded while verifying student behavior.
4. Only then removing `harmony.css` from the student route.

Do not combine that follow-up with this teacher shell repair.

