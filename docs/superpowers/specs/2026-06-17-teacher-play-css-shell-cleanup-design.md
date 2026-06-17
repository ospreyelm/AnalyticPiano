# Teacher Play CSS Shell Cleanup - Design Spec

**Date:** 2026-06-17
**Status:** Design spec
**Priority alignment:** Teacher `/teacher/play/` usability, unified CSS identity, teacher app continuity.

Related documents:

- `docs/superpowers/specs/2026-06-16-unified-css-identity-design.md`
- `docs/superpowers/plans/2026-06-16-unified-css-identity.md`
- `docs/superpowers/specs/2026-06-08-teacher-play-authoring-design.md`
- `docs/redundancy_analysis_report.md`

---

## Goal

Make `/teacher/play/` look and behave like a coherent Monteverdi teacher
authoring workspace without destabilizing the currently functional student
exercise player.

This is a follow-up to the unified CSS identity work. The June 16 plan moved the
student player styling into `student/player-canvas.css` and migrated
`lab/templates/play.html` onto `teacher/base.html`. The remaining problem is that
`/teacher/play/` still composes incompatible visual systems:

1. It uses the new teacher header from `apps/teacher/templates/teacher/base.html`.
2. It includes old lab header/menu partials from `lab/templates/_header_music.html`,
   `lab/templates/_menu_music.html`, and `lab/templates/_menu_piano.html`.
3. It imports broad student player CSS that includes student chrome and global
   selectors, then overrides layout in an inline `<style>` block.

The result is the current screenshot failure: raw bullet-list controls above a
partly modern parchment exercise canvas.

---

## Non-goals

- Do not redesign the student player first.
- Do not remove `harmony.css` from the student player in this phase.
- Do not refactor AMD exercise components or remove `MutationObserver` DOM surgery
  in `student/player.html` as part of this phase.
- Do not alter authoring behavior, MusicXML save behavior, analysis generation,
  MIDI handling, or exercise grading.
- Do not make `/teacher/play/` depend on dashboard templates or send teachers back
  to `/dashboard/...`.

---

## Current State

### Teacher app shell

`apps/teacher/templates/teacher/base.html` provides:

- Teacher header/nav.
- `student/tokens.css` and `teacher/teacher.css`.
- `js_require` and `js_extra` blocks for RequireJS pages.

Problem: its default `.t-main` is a narrow management-page container. The
authoring workspace needs a full-width mode.

### Student player

`apps/student/templates/student/player.html` still extends `lab/templates/__base.html`,
which loads `lab/static/css/harmony.css`. It then loads:

- `student/student.css`
- `student/player-canvas.css`

This is functional and visually stronger than teacher play. It should remain the
reference for exercise-canvas look and density.

Risk: the student player still depends on legacy DOM IDs and CSS reset behavior
from `harmony.css`. Removing `harmony.css` now would be a broad regression
project.

### Teacher play view

`lab/templates/play.html` currently:

- Extends `teacher/base.html`.
- Loads `student/player-canvas.css`.
- Defines additional inline CSS for `.harmony-ui`, `#staff-area`, `#piano`, and
  `#play-save-panel`.
- Includes `_header_music.html`, `_menu_music.html`, `_menu_piano.html`, and
  `_notifications.html`.

Problem: the old header/menu partials expect `harmony.css`; the teacher shell no
longer loads it. They render as browser-default lists and controls.

---

## Design Decision

Fix `/teacher/play/` first, then use that work to make the later student
`harmony.css` removal smaller and safer.

The teacher play view should not be a student player page with a save panel glued
onto it. It should be a teacher authoring workspace with:

- Teacher app chrome.
- A shared exercise canvas.
- A teacher-specific authoring toolbar.
- A teacher-specific right-side save/metadata inspector.
- Hidden or relocated legacy JS mount points where old AMD components still need
  IDs.

The student player remains stable until the shared exercise-canvas layer is
cleanly separated from route chrome.

---

## Target CSS Architecture

### 1. Shared tokens

Keep using `student/tokens.css` for now to avoid path churn. A later neutral move
to `design/tokens.css` is desirable but not required for this phase.

Required rule for this phase:

- New teacher play CSS must use existing token names where available.
- New hard-coded colors are allowed only for exercise-canvas art direction already
  present in `player-canvas.css` (parchment, piano, staff, feedback).

### 2. Shared exercise canvas CSS

Introduce a route-neutral stylesheet:

`apps/student/static/student/exercise-canvas.css`

Responsibility:

- Staff wrapper and canvas sizing.
- Parchment exercise surface.
- Piano shell and keyboard visual treatment.
- Feedback bubbles and inline feedback.
- Click-note controls and QWERTY badges.
- Shared notification styling needed inside exercise surfaces.

Not responsible for:

- Student top bar.
- Student settings drawer.
- Student answer bar.
- Teacher save panel.
- Teacher authoring toolbar.
- Route-level page shell.

This can initially be extracted from `student/player-canvas.css` without changing
student markup. The first consumer should be `/teacher/play/`; student migration
can follow after visual verification.

### 3. Student player CSS

Keep:

`apps/student/static/student/player-canvas.css`

Responsibility after extraction:

- Student top bar.
- Student settings drawer.
- Student answer bar.
- Student-only player controls.
- Student-specific relocation overrides.

During this phase, the student template may continue to load both
`harmony.css` and `player-canvas.css`.

### 4. Teacher play CSS

Create:

`apps/teacher/static/teacher/teacher-play.css`

Responsibility:

- Full-width teacher workspace layout.
- Authoring toolbar layout.
- Save/metadata inspector.
- Display options / meter / MusicXML controls.
- Hidden legacy mount points.
- Responsive behavior for desktop, tablet, and narrow screens.

This file should be scoped by a page class such as `.t-play-workspace` to avoid
global ID leakage into other pages that also use `#staff-area`, `#piano`, or
`.harmony-ui`.

---

## Target Template Structure

### `teacher/base.html`

Add a body/main variant hook:

```html
<main class="t-main {% block main_class %}{% endblock %}">
  {% block content %}{% endblock %}
</main>
```

Default teacher pages keep the current narrow `.t-main` behavior. `play.html`
sets:

```html
{% block main_class %}t-main--workspace{% endblock %}
```

`teacher.css` adds:

```css
.t-main--workspace {
  max-width: none;
  padding: 0;
}
```

### `lab/templates/play.html`

The target structure:

```html
<div id="container" class="t-play-workspace js-fade-in fade" style="opacity: 0;">
  <section class="t-play-topbar" aria-label="Authoring controls">
    <div class="t-play-toolbar">
      <button class="t-btn t-btn-ghost t-btn-sm js-btn-upload-json">Save</button>
      <button class="t-btn t-btn-ghost t-btn-sm js-btn-pristine">Reload</button>
      <button class="t-btn t-btn-ghost t-btn-sm js-btn-import-musicxml">Import MusicXML</button>
      <input type="file" id="musicxml-upload-input" accept=".xml,.musicxml,.mxl" class="u-hidden">
      <label for="play-meter-select" class="t-label t-play-inline-label">Meter</label>
      <select id="play-meter-select" class="t-input t-play-meter-select"></select>
      <div id="save-feedback" class="feedback-inline" aria-live="polite"></div>
    </div>
    <div id="play-view-settings-mount" class="t-play-settings-mount"></div>
  </section>

  <div id="legacy-play-mounts" class="t-play-hidden-mounts" aria-hidden="true">
    <div id="mainmenu"></div>
    <div class="js-keysignature-widget"></div>
    <div class="js-notation-opts-widget"></div>
    <div class="js-keyboardsize settings-inline"></div>
    <div class="js-octaveadjustment settings-inline"></div>
    <div class="js-keyboardshortcuts settings-inline"></div>
  </div>

  {% include "_notifications.html" %}

  <div class="harmony-ui t-play-stage">
    <div id="staff-area" class="t-play-staff-area">
      <div id="staff-toolbar" class="t-play-staff-toolbar"></div>
      <div id="staffwrapper">
        <div id="user-interaction-solicitation">CLICK TO START AUDIO</div>
        <canvas id="staff"></canvas>
      </div>
    </div>

    <aside id="play-save-panel" class="play-save-panel t-play-save-panel"></aside>
    <div id="piano"></div>
  </div>
</div>
```

The exact save panel fields can stay as they are. The important change is that
legacy header/menu partials are not visibly included.

---

## Legacy Mount Point Strategy

Do not delete old mount points blindly. Several RequireJS widgets still query by
fixed selectors. The cleanup should handle them explicitly:

| Legacy selector | Current source | Target |
|---|---|---|
| `#mainmenu` | `_menu.html` | Hidden mount in `play.html`, or visible teacher settings drawer later |
| `.js-keysignature-widget` | `_header_music.html` | Move into teacher topbar or hidden mount if not needed |
| `.js-notation-opts-widget` | `_menu_music.html` | Hidden mount initially |
| `.js-keyboardsize` | `_menu_music.html` | Hidden mount initially |
| `.js-octaveadjustment` | `_menu_music.html` | Hidden mount initially |
| `.js-keyboardshortcuts` | `_menu_music.html` | Hidden mount initially |
| `#mute-toggle` | `_header.html` | Teacher toolbar/settings control |
| `#volume` | `_header.html` | Teacher toolbar/settings control |
| `#midi-switch` | `_header.html` | Teacher toolbar/settings control |

Initial version may keep MIDI/audio controls in a compact toolbar. If the JS
requires these exact IDs, preserve the IDs and change only their surrounding
markup/classes.

---

## Responsive Behavior

Desktop:

- Full-width teacher chrome.
- Top authoring toolbar at the top of the workspace.
- Staff and save panel side by side.
- Piano below the staff and spanning the available stage width.

Tablet:

- Toolbar wraps across two rows.
- Save panel remains right-side until it would crowd the staff.

Narrow screens:

- Stage becomes single column.
- Save panel moves below the staff/piano or becomes a collapsible inspector.
- All buttons and selects keep at least 44px touch target height.
- No horizontal page scroll except intentional staff/piano internal scroll.

---

## Verification Requirements

Run after implementation:

1. Django template smoke check:
   - `/teacher/play/` returns 200.
   - Response includes `teacher/teacher-play.css`.
   - Response does not include visible legacy `_header.html` text such as
     `Dashboard`, `New Play View`, or `DISPLAY OPTIONS`.
   - Response still includes required JS mount IDs.

2. Browser checks:
   - `/teacher/play/` desktop screenshot: no bullet lists, no browser-default
     buttons above the stage, toolbar is coherent.
   - `/teacher/play/` narrow screenshot: save panel and staff do not overlap.
   - Student player screenshot before/after: no visual regression.

3. Static scan:
   - `lab/templates/play.html` contains no inline `<style>` block.
   - `lab/templates/play.html` contains no includes for `_header_music.html`,
     `_menu_music.html`, or `_menu_piano.html`.
   - New CSS selectors are scoped by `.t-play-workspace` or `.t-play-*` except
     where overriding shared canvas IDs is unavoidable.

---

## Phasing

### Phase 1: Teacher play shell repair

- Add `main_class` support to teacher base.
- Add `t-main--workspace` to `teacher.css`.
- Create `teacher-play.css`.
- Stop visibly including old lab header/menu partials in `play.html`.
- Preserve required JS mount points inside hidden or teacher-styled containers.
- Move inline play CSS into `teacher-play.css`.

This phase should fix the visible screenshot problem.

### Phase 2: Shared exercise-canvas extraction

- Extract route-neutral rules from `student/player-canvas.css` into
  `exercise-canvas.css`.
- Load `exercise-canvas.css` before `teacher-play.css` on `/teacher/play/`.
- Keep student loading unchanged unless screenshot verification is already in
  place.

This phase reduces teacher dependence on broad student CSS.

### Phase 3: Student player migration rehearsal

- Load `exercise-canvas.css` before `player-canvas.css` in student player.
- Remove duplicated shared rules from `player-canvas.css`.
- Keep `harmony.css` loaded.
- Verify no visual or interaction regression.

This phase prepares the student route for eventual legacy CSS removal.

### Phase 4: Student `harmony.css` removal

Only after Phase 3 passes visual and interaction checks:

- Add any missing reset/font/icon dependencies explicitly.
- Remove `harmony.css` from the student player route.
- Verify staff, piano, answer bar, settings drawer, notifications, and
  identification modes.

This is intentionally last because the student player is functional today.

---

## Open Questions

1. Should teacher play expose display options immediately in the topbar, or hide
   them in a compact settings drawer like the student player?
2. Should the save panel stay permanently visible on desktop, or become a
   collapsible inspector once MusicXML import options grow?
3. Should shared tokens be moved to a neutral static path now, or deferred until
   after teacher play is visually stable?

Recommended defaults:

- Put the common display controls in the topbar for now.
- Keep save panel visible on desktop.
- Defer token path relocation.

