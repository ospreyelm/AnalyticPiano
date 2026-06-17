# Unified CSS Identity — Design Spec

**Date:** 2026-06-16
**Priorities:** CLAUDE.md #6 (unified CSS identity) and #7 (apply to /teacher/play/)

---

## Goal

Complete the Monteverdi design system and apply it consistently across teacher and
student surfaces. Specifically:

1. Deepen `tokens.css` to cover all remaining gaps.
2. Extract the student exercise player's inline styles into a shared
   `player-canvas.css` file.
3. Migrate `/teacher/play/` from the legacy `harmony.css` chrome to the teacher
   base template, with the parchment canvas aesthetic and a `.t-*`-styled save panel.

---

## Design Decision: Two Zones, One System

Monteverdi has two visually distinct surface types. Both zones share `tokens.css`
as a token foundation; they are not merged into a single color scheme.

### Zone 1 — Management surfaces

Applies to: teacher courses/library/wizard, student home/unit pages, login.

- Token base: `tokens.css`
- Component libraries: `teacher.css` (`.t-*`) and `student.css` (`.s-*`)
- Palette: teal `#2a7e94`, header `#1e5c6e`, surface `#f4f6f7`, white cards
- Fonts: Nunito (UI) + Montserrat (body)

### Zone 2 — Exercise canvas

Applies to: the music staff, piano keyboard, and instruction panel — wherever a
student *plays* an exercise.

- Stylesheet: `player-canvas.css` (extracted from `player.html` inline styles)
- Palette: warm parchment body (`#fbf7ef → #f1e8db`), dark leather piano
  (`#241c17 → #15100d`), red accent stripe on piano
- Amber pill toolbar buttons, dark instruction panel

**Rationale:** The two zones serve different mental modes — "at the desk"
(management) vs. "at the instrument" (exercise canvas). The visual shift is
intentional and semantically meaningful, not a consistency problem to fix.
This pattern is standard in professional music tools (Ableton, Sibelius, Logic).

**`/teacher/play/` combines both zones:** teacher chrome (Zone 1 header/nav) wraps
the Zone 2 canvas. The save panel is Zone 1. This means teachers see the exact
exercise aesthetic that students play with — no visual surprise between authoring
and playing.

---

## Phase 1 — Deepen `tokens.css`

**File:** `apps/student/static/student/tokens.css`

Add the following tokens (nothing removed, all additive):

```css
/* Header — slightly darker than --teal, used in teacher/base.html */
--teal-header: #1e5c6e;

/* Mono font — currently missing, needed in save panel tag/code fields */
--font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;

/* Explicit type scale — replaces ad-hoc px/rem values scattered in components */
--text-xs:   0.72rem;
--text-sm:   0.82rem;
--text-base: 0.9375rem;
--text-lg:   1.05rem;
--text-xl:   1.5rem;

/* Surface — slightly warmer/deeper than current #f7f8f8 */
--surface: #f4f6f7;
```

`teacher.css` and `student.css` both import `tokens.css` unchanged and pick up
new vars automatically. Existing components that hardcode equivalent values are
migrated to vars as a follow-up cleanup pass, not part of this spec.

---

## Phase 2 — Extract `player-canvas.css`

**New file:** `apps/student/static/student/player-canvas.css`

**Source:** The inline `<style>` block in `apps/student/templates/student/player.html`.
Move the entire block verbatim into the new file.

**Scope of extraction** (representative, not exhaustive):

| Selector / rule | Description |
|---|---|
| `.harmony-ui` | Warm parchment exercise card |
| `#piano`, `#piano::before` | Dark leather keyboard + red stripe |
| `#staffwrapper` | White score area |
| `.s-player-header` (inline override) | Warm parchment top bar |
| `.s-toolbar-btn`, `.s-toolbar-btn-primary` | Amber pill nav buttons |
| `#instruction-panel`, `#exercise-text` | Dark instruction block |
| `.notification`, `.notification.warning` | Notification cards |
| `.s-settings-*` | Settings drawer overlay |
| Click-note-input, QWERTY badge, feedback styles | Interactive overlays |

**`player.html` after extraction:**
- Remove inline `<style>` block.
- Add `<link href="{% static 'student/player-canvas.css' %}" rel="stylesheet">` in
  `{% block css_extra %}`, after `student.css`.
- Load order preserved: `student.css` → `player-canvas.css`. The `.s-player-header`
  override in `player-canvas.css` wins by cascade order, same as today.

**Visual result:** Zero change to the student player. Pure refactor.

---

## Phase 3 — Migrate `/teacher/play/`

### 3a. Patch `teacher/base.html` — add JS blocks

`teacher/base.html` currently has no RequireJS setup. `play.html` depends on
`require(['app/main'])` which only works when `require.js` is loaded and configured
(currently provided by `__base.html`'s `{% block js_require %}`).

**Fix:** Add two new template blocks to `teacher/base.html` inside `<body>`, just
before `{% block body_extra %}`:

```html
{% block js_require %}{% endblock %}
{% block js_extra %}{% endblock %}
```

This lets pages that extend `teacher/base.html` inject JS boot sequences. The
blocks are empty by default so existing teacher pages (`course_wizard.html`,
`library_hub.html`, etc.) are unaffected.

### 3b. Patch `teacher/base.html` — add Google Fonts

`teacher/base.html` loads `tokens.css` (which defines `--font-ui: 'Nunito'` and
`--font-body: 'Montserrat'`) but never loads the actual font files. `student.css`
loads them via `@import url(...)`, but teacher pages don't load `student.css`.
Result: teacher surfaces fall back to system fonts.

**Fix:** Add a Google Fonts `<link>` to `teacher/base.html`'s `<head>`:

```html
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
```

Place it before the `tokens.css` and `teacher.css` links. No change to
`student.css` (it keeps its own `@import` for student-only pages).

### 3c. Migrate `play.html`

**File:** `lab/templates/play.html`

**Template extension:**

```
{% extends "teacher/base.html" %}   {# was: __base.html #}
```

**`{% block js_require %}`** — copy the RequireJS boot from `__base.html` verbatim:

```html
{% block js_require %}
{% load static %}
<script src="{% static 'js/lib/require.js' %}"></script>
<script>requirejs.config({ enforceDefine: true, waitSeconds: 0 });</script>
{% autoescape off %}
<script>requirejs.config({{ requirejs.config_json }});</script>
<script>window.appStaticUrl = '{% static '' %}';</script>
{% if requirejs.debug %}<script>requirejs.config({'urlArgs': 't='+(new Date().getTime())});</script>{% endif %}
{% endautoescape %}
{% endblock %}
```

`PlayView` already extends `RequirejsTemplateView`, so `requirejs.config_json` is
available in context. No view change needed.

**`{% block js_extra %}`** retains the existing `require(['app/main'])` call:

```html
{% block js_extra %}
<script>require(['app/main']);</script>
{% endblock %}
```

**`{% block head_extra %}`** adds three things:

1. `player-canvas.css` — warm parchment canvas + dark piano aesthetic:
   ```html
   <link href="{% static 'student/player-canvas.css' %}" rel="stylesheet">
   ```

2. Notation font `@font-face` declarations for `Sebastian`, `MainSerifs`,
   `JazzSerifs` — previously loaded via `harmony.css`, now declared explicitly
   since `harmony.css` is no longer loaded:
   ```html
   <style>
   @font-face { font-family: "Sebastian"; src: url("{% static 'fonts/Sebastian-FigBass-Modified.woff' %}") format("woff"); }
   @font-face { font-family: "MainSerifs"; src: url("{% static 'fonts/Alegreya-Regular-Modified.woff' %}") format("woff"); }
   @font-face { font-family: "JazzSerifs"; src: url("{% static 'fonts/Alegreya-Regular-Modified-v2.woff' %}") format("woff"); }
   </style>
   ```

3. Play-specific layout CSS — overrides `.harmony-ui` for the two-column
   authoring layout (canvas left, save panel right). This is play-only and does
   not belong in `player-canvas.css` which must stay compatible with the
   single-column student player:
   ```html
   <style>
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
   ```

### 3d. Restyle play toolbar

The current `#staff-toolbar` in `play.html` uses icon-button classes from
`harmony.css` (`icon-btn`, `save-icon`, `refresh-icon`, `musicxml-icon`). Removing
`harmony.css` leaves these unstyled.

**Fix:** Replace the icon-button markup with `.t-btn t-btn-ghost` equivalents.
JS hooks target these buttons by class selectors (`js-btn-upload-json`,
`js-btn-pristine`, `js-btn-import-musicxml`) which are preserved on the new markup;
only the visual classes change.

```html
<!-- Before (harmony.css icon buttons) -->
<a class="save-icon js-btn-upload-json" title="Create exercise" ...> </a>
<a class="refresh-icon js-btn-pristine" title="Reload sheet music" ...> </a>
<a class="musicxml-icon js-btn-import-musicxml" ...> </a>

<!-- After (.t-btn equivalents, JS selectors preserved) -->
<button class="t-btn t-btn-ghost t-btn-sm js-btn-upload-json" title="Create exercise">Save</button>
<button class="t-btn t-btn-ghost t-btn-sm js-btn-pristine" title="Reload">↺ Reload</button>
<button class="t-btn t-btn-ghost t-btn-sm js-btn-import-musicxml" title="Import MusicXML">Import MusicXML</button>
```

The camera/screenshot icon-btn is already hidden by `player.html`'s
`.icon-btn-camera { display: none !important }` rule, which carries over in
`player-canvas.css`. It can be removed from the HTML entirely.

The meter `<select>` and its label remain unchanged.

### 3e. Restyle save panel (`#play-save-panel`)

Restyled with `.t-*` classes. The element IDs and `name` attributes that JS
targets are preserved exactly — only visual classes change.

| Element | Before (ad-hoc) | After (`.t-*`) |
|---|---|---|
| Panel container | `play-save-panel` custom CSS | Layout from 3c `<style>` block above |
| Section heading | `.play-save-dialog-title` | `class="t-card-title"` |
| Field wrapper | `.play-save-field` | `class="t-form-row"` |
| Labels | `<label>` unstyled | `class="t-label"` |
| Text inputs | `.play-save-input` | `class="t-input"` |
| Select elements | `.play-save-select` | `class="t-input"` |
| Checkbox rows | `.play-save-checkbox` | `class="t-check-row"` |
| Save button | `.play-save-btn-primary` | `class="t-btn t-btn-primary"` |
| Feedback div | `.feedback-inline` | unchanged (JS depends on it) |

### Teacher nav active state

"Play" nav link already receives `t-nav-link--active` via the existing conditional
in `teacher/base.html`. No change needed.

---

## File changes summary

| File | Change |
|---|---|
| `apps/student/static/student/tokens.css` | Add 7 new tokens |
| `apps/teacher/templates/teacher/base.html` | Add Google Fonts `<link>`; add `{% block js_require %}` and `{% block js_extra %}` |
| `apps/student/static/student/player-canvas.css` | **New file** — extracted from player.html inline `<style>` |
| `apps/student/templates/student/player.html` | Remove inline `<style>`, add `<link>` to player-canvas.css |
| `lab/templates/play.html` | Extend teacher/base.html; add RequireJS boot in js_require block; import player-canvas.css + fonts + play layout CSS; restyle toolbar + save panel |

No backend changes. No model changes. No changes to JS files.

---

## Testing

**Phase 1 (tokens):** Smoke-test teacher app (course list, library, wizard). No
visual regression expected — new tokens are additive.

**Phase 2 (extraction):** Load student player page. Confirm visual is identical to
before. Test play exercise, identification exercise, QWERTY mode, settings drawer,
click-note mode.

**Phase 3 (play.html):** Load `/teacher/play/`. Verify:
- Teacher header/nav visible; "Play" link active
- Nunito/Montserrat fonts render correctly (not falling back to system fonts)
- RequireJS boots: music canvas loads, staff renders, piano keyboard works
- Canvas renders with warm parchment + dark piano (identical to student player)
- Notation fonts (`Sebastian`, `MainSerifs`, `JazzSerifs`) load — verify by
  checking staff renders figured bass / Roman numeral annotations correctly
- Toolbar buttons (`Save`, `↺ Reload`, `Import MusicXML`) render and respond
- Save panel fields, checkboxes, selects, meter select all function
- Save button posts correctly (JS targets by id/name preserved)
- Superuser sees "Save as official" row
- MusicXML import panel appears after file selection

---

## Out of scope

- Migrating `harmony.css` out of `__base.html` globally
- Reskinning the student player top bar (`.s-player-header`) to teal
- Adding new save-panel features (transpositions wiring is the generation wizard plan)
- Dark mode
