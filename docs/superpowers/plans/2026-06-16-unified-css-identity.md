# Unified CSS Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Monteverdi design system (deepen `tokens.css`, extract the
student exercise player's inline CSS into a shared `player-canvas.css`) and migrate
`/teacher/play/` from legacy `harmony.css` chrome to the teacher base template,
wrapping the same parchment exercise canvas students see, with a `.t-*`-styled save
panel.

**Architecture:** Two visual zones share one token foundation (`tokens.css`).
Zone 1 ("desk" — management surfaces) uses `teacher.css`/`student.css` `.t-*`/`.s-*`
components. Zone 2 ("instrument" — exercise canvas) uses a new `player-canvas.css`
extracted verbatim from `player.html`'s inline styles. `/teacher/play/` combines
both: teacher chrome wraps the Zone 2 canvas, with a Zone 1 save panel.

**Tech Stack:** Django templates, vanilla CSS (custom properties), RequireJS
(legacy JS boot, untouched), Django test client for view smoke tests.

**Spec:** [docs/superpowers/specs/2026-06-16-unified-css-identity-design.md](../specs/2026-06-16-unified-css-identity-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `apps/student/static/student/tokens.css` | Modify | Add 7 new design tokens |
| `apps/teacher/templates/teacher/base.html` | Modify | Add Google Fonts link; add `js_require`/`js_extra` blocks |
| `apps/student/static/student/player-canvas.css` | **Create** | Exercise canvas styling (parchment + piano), shared by student player and teacher play view |
| `apps/student/templates/student/player.html` | Modify | Remove inline `<style>`, link `player-canvas.css` |
| `lab/templates/play.html` | Modify | Extend `teacher/base.html`; RequireJS boot; play-specific layout CSS; restyled toolbar + save panel |
| `lab/tests/test_play_view.py` | **Create** | Smoke tests: status code, template used, key markup present |

---

## Task 1: Deepen `tokens.css`

**Files:**
- Modify: `apps/student/static/student/tokens.css`
- Test: `apps/student/tests/test_views.py` (existing file — add one assertion-light smoke test)

This is pure CSS addition. No automated CSS test framework exists in this repo, so
verification is: (a) the file parses as valid CSS (gated by visual smoke test in
Task 6), (b) a quick grep-based test confirming the new custom properties exist,
so a future refactor can't silently drop them.

- [ ] **Step 1: Add the new tokens**

Open `apps/student/static/student/tokens.css`. Current content ends at line 19
with the closing `}` of `:root`. Insert the new properties before that closing
brace:

```css
:root {
  --teal: #2a7e94;
  --teal-dark: #1f6070;
  --teal-pale: #e8f4f7;
  --teal-mid: #aacbd4;
  --surface: #f4f6f7;
  --surface-2: #ffffff;
  --border: #dde3e6;
  --text: #1a2224;
  --text-muted: #6c7c80;
  --success: #198754;
  --success-pale: #e8f5ee;
  --warning: #b45309;
  --warning-pale: #fef3c7;
  --danger: #dc3545;
  --radius: 5px;
  --font-ui: 'Nunito', sans-serif;
  --font-body: 'Montserrat', sans-serif;
  --teal-header: #1e5c6e;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --text-xs: 0.72rem;
  --text-sm: 0.82rem;
  --text-base: 0.9375rem;
  --text-lg: 1.05rem;
  --text-xl: 1.5rem;
}
```

Note `--surface` changes from `#f7f8f8` to `#f4f6f7` (per spec — slightly warmer).
All other existing lines are unchanged.

- [ ] **Step 2: Write a regression test for the token set**

Create a small test that loads the CSS file and asserts the new custom properties
are present as plain text. This catches accidental deletion in future edits — it
does not validate CSS semantics (no CSS parser is in the toolchain).

Add to `apps/student/tests/test_views.py` at the end of the file:

```python
class DesignTokensTests(TestCase):
    def test_tokens_css_defines_required_custom_properties(self):
        tokens_path = (
            Path(__file__).resolve().parents[1] / "static" / "student" / "tokens.css"
        )
        content = tokens_path.read_text()
        for prop in (
            "--teal-header:",
            "--font-mono:",
            "--text-xs:",
            "--text-sm:",
            "--text-base:",
            "--text-lg:",
            "--text-xl:",
            "--surface: #f4f6f7;",
        ):
            self.assertIn(prop, content, f"tokens.css missing {prop}")
```

`Path` and `TestCase` are already imported at the top of this file (`from pathlib
import Path`, `from django.test import ... TestCase ...`). If `TestCase` isn't
imported (only `TransactionTestCase` is), add it:

```python
from django.test import Client, TestCase, TransactionTestCase, override_settings
```

- [ ] **Step 3: Run the test to verify it fails before the CSS edit**

If you wrote the test before Step 1's edit, run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_views.DesignTokensTests -v 2
```

Expected: FAIL — `AssertionError: tokens.css missing --teal-header:` (or similar).

If you already completed Step 1 first, skip this — just confirm Step 4 passes.

- [ ] **Step 4: Run the test to verify it passes**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_views.DesignTokensTests -v 2
```

Expected: `OK` (1 test passed).

- [ ] **Step 5: Commit**

```bash
git add apps/student/static/student/tokens.css apps/student/tests/test_views.py
git commit -m "Deepen tokens.css with header, mono font, and type-scale tokens"
```

---

## Task 2: Patch `teacher/base.html` — fonts and JS blocks

**Files:**
- Modify: `apps/teacher/templates/teacher/base.html`
- Test: `apps/teacher/tests/test_views_db.py` (existing file — add template-content assertions)

- [ ] **Step 1: Add Google Fonts link and new template blocks**

Current `apps/teacher/templates/teacher/base.html` is:

```html
{# apps/teacher/templates/teacher/base.html #}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Monteverdi — Teacher{% endblock %}</title>
  {% load static %}
  <link href="{% static 'student/tokens.css' %}" rel="stylesheet">
  <link href="{% static 'teacher/teacher.css' %}" rel="stylesheet">
  {% block head_extra %}{% endblock %}
</head>
<body>
  <header class="t-header">
    <a class="t-header-brand" href="/">Monteverdi</a>
    {% if request.user.is_authenticated %}
      <nav class="t-header-nav" aria-label="Teacher navigation">
        <a class="t-nav-link {% if 'course' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="{% url 'teacher:course-list' %}">Courses</a>
        <a class="t-nav-link {% if 'library' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="{% url 'teacher:library-hub' %}">Library</a>
        <a class="t-nav-link {% if 'play' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="/teacher/play/">Play</a>
      </nav>
      <div class="t-header-user-area">
        <span class="t-header-user">{{ request.user.first_name|default:request.user.email }}</span>
        <a class="t-header-signout" href="/accounts/logout/">Sign out</a>
      </div>
    {% endif %}
  </header>
  <main class="t-main">
    {% block content %}{% endblock %}
  </main>
  {% block body_extra %}{% endblock %}
</body>
</html>
```

Replace it with:

```html
{# apps/teacher/templates/teacher/base.html #}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Monteverdi — Teacher{% endblock %}</title>
  {% load static %}
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
  <link href="{% static 'student/tokens.css' %}" rel="stylesheet">
  <link href="{% static 'teacher/teacher.css' %}" rel="stylesheet">
  {% block head_extra %}{% endblock %}
</head>
<body>
  <header class="t-header">
    <a class="t-header-brand" href="/">Monteverdi</a>
    {% if request.user.is_authenticated %}
      <nav class="t-header-nav" aria-label="Teacher navigation">
        <a class="t-nav-link {% if 'course' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="{% url 'teacher:course-list' %}">Courses</a>
        <a class="t-nav-link {% if 'library' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="{% url 'teacher:library-hub' %}">Library</a>
        <a class="t-nav-link {% if 'play' in request.resolver_match.url_name %}t-nav-link--active{% endif %}"
           href="/teacher/play/">Play</a>
      </nav>
      <div class="t-header-user-area">
        <span class="t-header-user">{{ request.user.first_name|default:request.user.email }}</span>
        <a class="t-header-signout" href="/accounts/logout/">Sign out</a>
      </div>
    {% endif %}
  </header>
  <main class="t-main">
    {% block content %}{% endblock %}
  </main>
  {% block body_extra %}{% endblock %}
  {% block js_require %}{% endblock %}
  {% block js_extra %}{% endblock %}
</body>
</html>
```

Two changes: the Google Fonts `<link>` in `<head>`, and the two new empty blocks
(`js_require`, `js_extra`) at the end of `<body>`, after `body_extra`. Existing
teacher pages (`course_list.html`, `library_hub.html`, `course_wizard.html`, etc.)
don't define these blocks, so they render as empty — zero behavior change for them.

- [ ] **Step 2: Write a test confirming the blocks and font link exist**

Add to `apps/teacher/tests/test_views_db.py`. First check the existing imports at
the top of the file (already shown above: `Client`, `reverse` from `django.urls`,
`User`, `ROLE_TEACHER`). Add a new test class:

```python
class TeacherBaseTemplateTests(TestCase):
    def test_course_list_response_includes_google_fonts_link(self):
        teacher = _make_teacher()
        client = Client()
        client.force_login(teacher)
        resp = client.get(reverse("teacher:course-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "fonts.googleapis.com/css2?family=Nunito")
```

This reuses the `_make_teacher` helper already defined near the top of
`test_views_db.py`. `TestCase` must be imported — check the existing import line;
if it only imports `TransactionTestCase` or similar, add `TestCase` to the import
from `django.test`.

- [ ] **Step 3: Run the test to verify it fails before the template edit**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.teacher.tests.test_views_db.TeacherBaseTemplateTests -v 2
```

Expected: FAIL (font link not found) if run before Step 1's edit.

- [ ] **Step 4: Run the test to verify it passes**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.teacher.tests.test_views_db.TeacherBaseTemplateTests -v 2
```

Expected: `OK`.

- [ ] **Step 5: Manually verify no regression on an existing teacher page**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.teacher.tests.test_views_db -v 2
```

Expected: all existing tests in this file still pass (the new blocks are additive
and empty by default, so nothing else should break).

- [ ] **Step 6: Commit**

```bash
git add apps/teacher/templates/teacher/base.html apps/teacher/tests/test_views_db.py
git commit -m "Add Google Fonts and JS boot blocks to teacher base template"
```

---

## Task 3: Extract `player-canvas.css`

**Files:**
- Create: `apps/student/static/student/player-canvas.css`
- Modify: `apps/student/templates/student/player.html`
- Test: `apps/student/tests/test_views.py` (existing — add assertions)

This is a pure refactor: move the inline `<style>` block out of `player.html`
verbatim into a new file, then link it. No visual change.

- [ ] **Step 1: Identify the exact inline style block to move**

In `apps/student/templates/student/player.html`, the inline block is:

```
{% block css_extra %}
  {% load static %}
  <link href="{% static 'student/student.css' %}" rel="stylesheet">
  <style>
    ... (all CSS rules) ...
  </style>
{% endblock %}
```

The block runs from the `/* ── Page shell ─────...` comment through the final
`.click-note-done-key { ... }` rule, immediately before `</style>`.

- [ ] **Step 2: Create `player-canvas.css` with the extracted content**

Create `apps/student/static/student/player-canvas.css`. Its content is the
**exact text** currently between `<style>` and `</style>` in `player.html`
(everything from the `/* ── Page shell ─────────────────────────────────────────── */`
comment through the closing rule for `.click-note-done-key`), with no
modifications. Prepend a one-line file banner comment:

```css
/* apps/student/static/student/player-canvas.css
   Exercise canvas — shared by the student player and the teacher /teacher/play/
   authoring view. Warm parchment body, dark piano, instruction panel. */

/* ── Page shell ─────────────────────────────────────────── */
body { background: #f7f8f8 !important; }

#container {
  opacity: 1 !important;
  background: transparent;
  margin: 0;
  padding: 0;
}

... (continue copying every rule verbatim from the current inline <style> block,
     ending with the .click-note-done-key rule) ...
```

Copy the full block from the current `player.html` source exactly — do not
paraphrase or reformat any rule. The table below (from the design spec) names the
major sections you should see represented in the copied content, as a checklist
to confirm nothing was dropped:

- `.s-player-wrap`, `.s-player-header`, `.s-back-btn`, `.s-player-title`
- `.s-settings-overlay`, `.s-settings-panel`, `.s-settings-*`
- `.s-player-input-hint`
- `#notifications`, `.notification`, `.notification.warning`
- `#staff-toolbar`, `.s-toolbar-btn`, `.s-toolbar-btn-primary`
- `#staff-area`, `#staffwrapper`
- `#s-answer-bar`, `#ident-progress-container`, `#ident-input-container`,
  `#identification-submit`, `#identification-actions`
- `#piano`, `#piano::before`, `.keyboard-wrapper`, `.qwerty-key-badge`
- `.click-note-input`, `.input-mode-btn`, `.accidental-palette`
- `#mainmenu`
- `.icon-btn-camera`, `#user-interaction-solicitation`
- `.harmony-ui`
- `.feedback-bubble`, `.feedback-inline`, `.click-note-done-key`

- [ ] **Step 3: Replace the inline style block in `player.html`**

Change the `{% block css_extra %}` in `apps/student/templates/student/player.html`
from containing the full `<style>...</style>` block to:

```html
{% block css_extra %}
  {% load static %}
  <link href="{% static 'student/student.css' %}" rel="stylesheet">
  <link href="{% static 'student/player-canvas.css' %}" rel="stylesheet">
{% endblock %}
```

Load order matters: `student.css` first, then `player-canvas.css` — this preserves
today's cascade where the inline (now extracted) `.s-player-header` rule overrides
the simpler `.s-player-header` defined in `student.css`.

- [ ] **Step 4: Write a regression test confirming the link tag and removed inline style**

Add to `apps/student/tests/test_views.py`, in the existing `PlayerViewTests` class
(or as a new small test class if you prefer not to touch the existing one — either
is fine, but reuse the existing class's `setUp` fixtures if adding there). As a
standalone class to avoid coupling to `PlayerViewTests`'s specific fixtures:

```python
class PlayerCanvasCssExtractionTests(TestCase):
    def test_player_canvas_css_file_exists_and_has_content(self):
        css_path = (
            Path(__file__).resolve().parents[1]
            / "static" / "student" / "player-canvas.css"
        )
        self.assertTrue(css_path.exists(), "player-canvas.css was not created")
        content = css_path.read_text()
        for selector in ("#piano", ".harmony-ui", "#staffwrapper", ".s-toolbar-btn"):
            self.assertIn(selector, content, f"player-canvas.css missing {selector}")

    def test_player_template_links_player_canvas_css_and_has_no_inline_style(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates" / "student" / "player.html"
        )
        content = template_path.read_text()
        self.assertIn("student/player-canvas.css", content)
        # The big inline <style> block should be gone; only small inline
        # <script> blocks remain in this template, so a literal "<style>"
        # tag should no longer be present.
        self.assertNotIn("<style>", content)
```

- [ ] **Step 5: Run the tests to verify they fail before Steps 2-3**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_views.PlayerCanvasCssExtractionTests -v 2
```

Expected: FAIL (file doesn't exist / inline `<style>` still present) if run before
the extraction.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_views.PlayerCanvasCssExtractionTests -v 2
```

Expected: `OK` (2 tests passed).

- [ ] **Step 7: Run the full existing player test suite to confirm no regression**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student.tests.test_views -v 2
```

Expected: all tests pass, including the pre-existing `PlayerViewTests` and
`StudentBasicViewTests` classes.

- [ ] **Step 8: Manual visual verification**

Run the dev server and load a student exercise (`/student/unit/1/...` or
equivalent player URL with a valid playlist param). Confirm:
- Warm parchment body renders
- Dark piano with red accent stripe renders
- Settings drawer opens/closes
- No visual difference from before the extraction

- [ ] **Step 9: Commit**

```bash
git add apps/student/static/student/player-canvas.css apps/student/templates/student/player.html apps/student/tests/test_views.py
git commit -m "Extract student player inline styles into player-canvas.css"
```

---

## Task 4: Migrate `play.html` template and RequireJS boot

**Files:**
- Modify: `lab/templates/play.html`
- Create: `lab/tests/test_play_view.py`

- [ ] **Step 1: Replace the template extension and add RequireJS boot blocks**

Current top and `js_extra` block of `lab/templates/play.html`:

```html
{% extends "__base.html" %}

{% block js_extra %}
<script>require(['app/main']);</script>
{% endblock %}

{% block content %}
...
{% endblock %}
```

Replace with:

```html
{% extends "teacher/base.html" %}
{% load static %}

{% block head_extra %}
<link href="{% static 'student/player-canvas.css' %}" rel="stylesheet">
<style>
@font-face { font-family: "Sebastian"; src: url("{% static 'fonts/Sebastian-FigBass-Modified.woff' %}") format("woff"); }
@font-face { font-family: "MainSerifs"; src: url("{% static 'fonts/Alegreya-Regular-Modified.woff' %}") format("woff"); }
@font-face { font-family: "JazzSerifs"; src: url("{% static 'fonts/Alegreya-Regular-Modified-v2.woff' %}") format("woff"); }

/* Play view: canvas + save panel side-by-side */
.harmony-ui {
  display: flex;
  flex-direction: row;
  gap: 0;
  align-items: stretch;
  padding: 0;
  border-radius: 12px;
  overflow: hidden;
}
#staff-area {
  flex: 1;
  min-width: 0;
  padding: 12px 12px 0;
}
#piano {
  margin: 6px 12px 12px;
}
#play-save-panel {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid var(--border);
  overflow-y: auto;
  padding: 20px;
}
</style>
{% endblock %}

{% block js_require %}
<script src="{% static 'js/lib/require.js' %}"></script>
<script>requirejs.config({ enforceDefine: true, waitSeconds: 0 });</script>
{% autoescape off %}
<script>requirejs.config({{ requirejs.config_json }});</script>
<script>window.appStaticUrl = '{% static '' %}';</script>
{% if requirejs.debug %}<script>requirejs.config({'urlArgs': 't='+(new Date().getTime())});</script>{% endif %}
{% endautoescape %}
{% endblock %}

{% block js_extra %}
<script>require(['app/main']);</script>
{% endblock %}

{% block content %}
...
{% endblock %}
```

The `{% block content %}` body is addressed in the next two steps (toolbar and
save panel) — leave the rest of the content block (the `staffwrapper`, `piano`
div, footer includes, and font-preload divs at the bottom) unchanged for now.

`PlayView` in `lab/views.py` already extends `RequirejsTemplateView`, which
supplies `requirejs.config_json` and `requirejs.debug` in the template context —
no Python changes needed.

- [ ] **Step 2: Write a smoke test for the migrated template**

Create `lab/tests/test_play_view.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PlayViewTeacherChromeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="play@example.com", password="x")
        self.client.force_login(self.user)

    def test_play_view_returns_200(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertEqual(resp.status_code, 200)

    def test_play_view_uses_teacher_chrome(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 't-header')
        self.assertContains(resp, 'Monteverdi')

    def test_play_view_loads_player_canvas_css(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "student/player-canvas.css")

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
```

`lab/urls.py` declares `app_name = "lab"` and `path("teacher/play/",
PlayView.as_view(), name="play")`, so `reverse("lab:play")` (as used above) is
correct — no adjustment needed.

- [ ] **Step 3: Run the tests to verify they fail before Step 1's edit**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected: FAIL on `test_play_view_uses_teacher_chrome`, `test_play_view_loads_player_canvas_css`,
`test_play_view_does_not_load_harmony_css` (these depend on Step 1's template
change — if you already made the edit, this step just confirms the edit is correct
by checking which assertions would have failed).

- [ ] **Step 4: Run the tests to verify they pass**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected: `OK` (6 tests passed).

- [ ] **Step 5: Commit**

```bash
git add lab/templates/play.html lab/tests/test_play_view.py
git commit -m "Migrate /teacher/play/ to teacher base template with RequireJS boot"
```

---

## Task 5: Restyle play toolbar and save panel

**Files:**
- Modify: `lab/templates/play.html`
- Modify: `lab/tests/test_play_view.py`

- [ ] **Step 1: Restyle the toolbar**

In `lab/templates/play.html`, the current toolbar (inside `{% block content %}`,
within `#staff-toolbar`) is:

```html
<div id="staff-toolbar">
    <a class="icon-btn icon-btn-right icon-btn-camera js-btn-screenshot" href="#" target="_blank" title="Screenshot &ndash; works in some browsers" alt="Screenshot"> </a>
    <a class="save-icon js-btn-upload-json" title="Create exercise" alt="Upload JSON"> </a>
    <div id="save-feedback" class="feedback-inline" aria-live="polite"></div>
    <!-- <a class="download-icon js-btn-download-json" alt="Download JSON"> </a> -->
    <a class="refresh-icon js-btn-pristine" title="Reload sheet music" alt="Reload sheet music"> </a>
    <a class="musicxml-icon js-btn-import-musicxml" title="Import MusicXML" alt="Import MusicXML" href="#"> </a>
    <input type="file" id="musicxml-upload-input" accept=".xml,.musicxml,.mxl" style="display:none;" />
    <label for="play-meter-select" style="font-size:12px;margin-left:10px;vertical-align:middle;">Meter:</label>
    <select id="play-meter-select" title="Set meter (auto-suggests barlines)" style="font-size:12px;padding:2px 4px;vertical-align:middle;border:1px solid #bbb;border-radius:3px;">
        <option value="">Free</option>
        <option value="2/4">2/4</option>
        <option value="3/4">3/4</option>
        <option value="4/4">4/4</option>
        <option value="6/8">6/8</option>
    </select>
</div>
```

Replace with:

```html
<div id="staff-toolbar">
    <button type="button" class="t-btn t-btn-ghost t-btn-sm js-btn-upload-json" title="Create exercise">Save</button>
    <div id="save-feedback" class="feedback-inline" aria-live="polite"></div>
    <button type="button" class="t-btn t-btn-ghost t-btn-sm js-btn-pristine" title="Reload sheet music">&#8635; Reload</button>
    <button type="button" class="t-btn t-btn-ghost t-btn-sm js-btn-import-musicxml" title="Import MusicXML">Import MusicXML</button>
    <input type="file" id="musicxml-upload-input" accept=".xml,.musicxml,.mxl" style="display:none;" />
    <label for="play-meter-select" class="t-label" style="display:inline-block;margin-left:10px;vertical-align:middle;">Meter:</label>
    <select id="play-meter-select" class="t-input" title="Set meter (auto-suggests barlines)" style="display:inline-block;width:auto;font-size:0.8rem;padding:4px 8px;vertical-align:middle;">
        <option value="">Free</option>
        <option value="2/4">2/4</option>
        <option value="3/4">3/4</option>
        <option value="4/4">4/4</option>
        <option value="6/8">6/8</option>
    </select>
</div>
```

Notes:
- The `js-btn-screenshot` anchor and its `icon-btn-camera` class are removed
  entirely — `player-canvas.css` already hides `.icon-btn-camera` via
  `display: none !important`, so this control is dead weight; removing the
  markup is cleaner than keeping a hidden element. If `app/main`'s JS errors on
  a missing `.js-btn-screenshot` element, this would surface in Task 5 Step 4's
  manual test — if so, keep the anchor but add `style="display:none"` instead of
  removing it. Try removing it first.
- All `js-btn-*` classes are preserved exactly — JS event binding is unaffected.
- The commented-out download-icon anchor is removed (it was already inert).

- [ ] **Step 2: Restyle the save panel**

Locate the save panel `<aside id="play-save-panel" ...>` block in `play.html`
(spans from `<aside id="play-save-panel"` through its closing `</aside>`,
immediately before `<div id="piano"></div>`).

Apply these class substitutions throughout the block (find-and-replace within
the aside only — do not change any `id`, `name`, `value`, or `data-*` attribute):

| Find | Replace with |
|---|---|
| `class="play-save-dialog-title"` | `class="play-save-dialog-title t-card-title"` |
| `class="play-save-field"` (each occurrence) | `class="play-save-field t-form-row"` |
| `class="play-save-field play-save-field-wide"` | `class="play-save-field play-save-field-wide t-form-row"` |
| `class="play-save-input"` (each occurrence) | `class="play-save-input t-input"` |
| `class="play-save-select"` (each occurrence) | `class="play-save-select t-input"` |
| `class="play-save-checkbox"` (each occurrence) | `class="play-save-checkbox t-check-row"` |
| `class="play-save-btn play-save-btn-primary"` | `class="play-save-btn play-save-btn-primary t-btn t-btn-primary"` |

Each `<label>` directly preceding an input/select inside the panel (e.g.
`<label for="play-save-description">Description <span class="play-save-required">*</span></label>`)
gets `class="t-label"` added:

```html
<label for="play-save-description" class="t-label">Description <span class="play-save-required">*</span></label>
```

Apply this to every `<label for="play-save-...">` in the panel (there are 7:
description, unit, modes group label, tags, playlist, new-playlist-name, key-set).

Keep all existing `play-save-*` classes alongside the new `.t-*` classes — JS
selects elements by `play-save-*` class names in several places (e.g.
`#play-save-create-transpositions`, `.play-save-checkboxes-group`), so removing
those classes would break JS. Only **add** `.t-*` classes; never remove the
original `play-save-*` ones.

- [ ] **Step 3: Add toolbar/save-panel assertions to the test file**

Add to `lab/tests/test_play_view.py`, inside `PlayViewTeacherChromeTests`:

```python
    def test_play_view_toolbar_uses_t_btn_classes(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 't-btn t-btn-ghost t-btn-sm js-btn-upload-json')
        self.assertContains(resp, 'js-btn-pristine')
        self.assertContains(resp, 'js-btn-import-musicxml')

    def test_play_view_save_panel_uses_t_classes(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 't-card-title')
        self.assertContains(resp, 't-btn t-btn-primary')

    def test_play_view_save_panel_preserves_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        # Original IDs/names JS depends on must survive the restyle.
        self.assertContains(resp, 'id="play-save-description"')
        self.assertContains(resp, 'id="play-save-submit"')
        self.assertContains(resp, 'id="play-save-create-transpositions"')
        self.assertContains(resp, 'name="modes"')
```

(Use the same `reverse(...)` call you confirmed works in Task 4 Step 3.)

- [ ] **Step 4: Run the tests to verify they fail before Steps 1-2**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected: `test_play_view_toolbar_uses_t_btn_classes` and
`test_play_view_save_panel_uses_t_classes` FAIL if run before Steps 1-2; the
preserved-JS-hooks test should already PASS since those ids exist today.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput lab.tests.test_play_view -v 2
```

Expected: `OK` (9 tests total passed across the file).

- [ ] **Step 6: Commit**

```bash
git add lab/templates/play.html lab/tests/test_play_view.py
git commit -m "Restyle /teacher/play/ toolbar and save panel with .t-* components"
```

---

## Task 6: Manual end-to-end verification

**Files:** none (manual QA pass — no code changes expected unless a bug is found)

- [ ] **Step 1: Run the full test suite for all touched apps**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.student apps.teacher lab -v 1
```

Expected: `OK`, zero failures, zero errors.

- [ ] **Step 2: Start the dev server**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py runserver
```

- [ ] **Step 3: Verify `/teacher/play/` in a browser**

Log in as a teacher user and visit `/teacher/play/`. Confirm:
- Teal teacher header/nav renders at top; "Play" nav link is highlighted active
- Nunito/Montserrat fonts render (not a system-font fallback — compare letterforms
  against `/teacher/courses/`)
- Music staff canvas loads and renders (RequireJS booted correctly — check browser
  console for `require` errors)
- Clicking/typing notes on the staff or piano works
- Piano renders with dark leather + red accent stripe, matching the student player
- Toolbar buttons (Save, Reload, Import MusicXML) are visible, styled as `.t-btn`,
  and clickable
- Meter `<select>` works
- Save panel on the right renders with white background, `.t-*` styled inputs
- Filling in description + unit + clicking Save successfully creates an exercise
  (check for the existing success feedback message)
- If logged in as superuser, "Save as official" checkbox row appears
- Clicking "Import MusicXML" opens the file picker and the MusicXML options panel
  appears after selecting a valid file

- [ ] **Step 4: Verify the student player is visually unchanged**

Visit a student exercise player page (e.g. via `/student/...` unit/playlist flow).
Confirm parchment body, dark piano, settings drawer, and toolbar all look identical
to before this work (compare against a screenshot taken before Task 3, if available,
or against `git show <commit-before-task-3>:apps/student/templates/student/player.html`
rendered separately if in doubt).

- [ ] **Step 5: Verify other teacher pages are unaffected**

Visit `/teacher/courses/` and `/teacher/library/`. Confirm fonts and layout are
unchanged from before this work (the new `js_require`/`js_extra` blocks are empty
on these pages and should have zero visible effect).

- [ ] **Step 6: Note any bugs found**

If any manual check fails, fix the specific issue in the relevant template/CSS
file from Tasks 1-5, re-run that task's automated tests, and re-commit with a
message describing the fix (e.g. `git commit -m "Fix musicxml-upload-input focus
trap in restyled play toolbar"`). Do not bundle unrelated changes into this fix.

---

## Self-Review Notes

**Spec coverage:**
- Phase 1 (tokens.css) → Task 1 ✓
- Phase 2 (player-canvas.css extraction) → Task 3 ✓
- Phase 3a (teacher/base.html JS blocks) → Task 2 ✓
- Phase 3b (Google Fonts) → Task 2 ✓
- Phase 3c (play.html template + RequireJS boot + layout CSS) → Task 4 ✓
- Phase 3d (toolbar restyle) → Task 5 Step 1 ✓
- Phase 3e (save panel restyle) → Task 5 Step 2 ✓
- Testing section of spec → Tasks 1-6 automated tests + Task 6 manual checklist ✓

**Out of scope confirmed unchanged:** no task touches `harmony.css` itself, no
task reskins `.s-player-header` to teal, no task adds transposition features, no
dark mode work.
