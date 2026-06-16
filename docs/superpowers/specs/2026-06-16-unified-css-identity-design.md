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

**Source:** The inline `<style>` block in `apps/student/templates/student/player.html`
(currently ~800 lines). Move the entire block verbatim into the new file.

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

### Template

**File:** `lab/templates/play.html`

| Before | After |
|---|---|
| `{% extends "__base.html" %}` | `{% extends "teacher/base.html" %}` |
| Imports `harmony.css` (via `__base.html`) | Imports `tokens.css` + `teacher.css` (via teacher base) |
| No teacher header/nav | Teacher header/nav included automatically |

**`{% block head_extra %}`** adds:
1. `player-canvas.css` — warm parchment canvas + dark piano
2. Notation font `<style>` block for `Sebastian`, `MainSerifs`, `JazzSerifs`
   (previously pulled in via `harmony.css`; now declared explicitly since
   `harmony.css` is no longer loaded)

### Canvas area

`#staff-area`, `#piano`, `.harmony-ui`, `#staffwrapper` — **HTML unchanged**.
`player-canvas.css` styles them identically to the student player. No JS changes.

The play-view toolbar (`#staff-toolbar`) keeps its existing icons and controls;
`player-canvas.css` provides the `.s-toolbar-btn` amber pill styling.

### Save panel (`#play-save-panel`)

Restyled with `.t-*` classes. The element IDs and `name` attributes that JS
targets are preserved exactly — only visual classes change.

| Element | Before (ad-hoc) | After (`.t-*`) |
|---|---|---|
| Panel container | `play-save-panel` custom CSS | white sidebar, `border-left: 1px solid var(--border)` |
| Section heading | `.play-save-dialog-title` | `class="t-card-title"` |
| Field wrapper | `.play-save-field` | `class="t-form-row"` |
| Labels | `<label>` unstyled | `class="t-label"` |
| Text inputs | `.play-save-input` | `class="t-input"` |
| Select elements | `.play-save-select` | `class="t-input"` |
| Checkbox rows | `.play-save-checkbox` | `class="t-check-row"` |
| Save button | `.play-save-btn-primary` | `class="t-btn t-btn-primary"` |
| Feedback div | `.feedback-inline` | unchanged (JS depends on it) |

**Panel width:** fixed `280px` right sidebar, flex row with canvas. Same layout
footprint as today.

### `harmony.css` removal

`harmony.css` is no longer loaded in `play.html`. Its remaining useful rules
(notation font declarations, body reset) are replaced by:
- Font declarations moved to an explicit `<style>` block in `{% block head_extra %}`
- Body/reset covered by `tokens.css` + browser defaults

No other pages are affected; `harmony.css` continues to load via `__base.html`
for the student exercise player until a future cleanup pass.

### Teacher nav active state

"Play" nav link already receives `t-nav-link--active` via the existing conditional
in `teacher/base.html`:
```html
{% if 'play' in request.resolver_match.url_name %}t-nav-link--active{% endif %}
```
No change needed.

---

## File changes summary

| File | Change |
|---|---|
| `apps/student/static/student/tokens.css` | Add 7 new tokens |
| `apps/student/static/student/player-canvas.css` | **New file** — extracted from player.html |
| `apps/student/templates/student/player.html` | Remove inline `<style>`, add `<link>` to player-canvas.css |
| `lab/templates/play.html` | Extend teacher/base.html; import player-canvas.css; restyle save panel |

No backend changes. No JS changes. No model changes.

---

## Testing

**Phase 1 (tokens):** Visual smoke-test teacher app (course list, library, wizard).
Verify no regression. No automated tests needed — purely additive CSS.

**Phase 2 (extraction):** Load student player page; confirm visual is pixel-identical
to before. Test play exercise, identification exercise, QWERTY mode, settings drawer.

**Phase 3 (play.html):** Load `/teacher/play/`. Verify:
- Teacher header/nav visible; "Play" link active
- Canvas renders with warm parchment + dark piano (identical to student player)
- Save panel fields, checkboxes, selects all function
- Save button posts correctly (JS targets preserved by id/name)
- Superuser sees "Save as official" row
- MusicXML import panel appears on import

---

## Out of scope

- Migrating `harmony.css` out of `__base.html` globally
- Reskinning the student player top bar (`.s-player-header`) to teal
- Adding new save-panel features (transpositions wiring is Phase 1 of the
  generation wizard, a separate plan)
- Dark mode
