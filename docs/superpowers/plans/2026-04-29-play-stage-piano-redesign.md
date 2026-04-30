# Play Stage Piano Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the student Play-mode lower half into a darker, more premium performance stage with a larger, more dimensional piano and light-touch top-of-page visual harmonization.

**Architecture:** Keep the current student player template and Raphael-based keyboard renderer. Implement the redesign through focused CSS and rendering tweaks in the existing player template, `piano/key.js`, and `piano/keyboard.js`, while preserving current input behavior and keyboard geometry-driven label placement.

**Tech Stack:** Django templates, existing player CSS in `apps/student/templates/student/player.html`, AMD JavaScript modules, Raphael piano renderer, Node-based DOM-free smoke tests.

---

## File Map

- `apps/student/templates/student/player.html`
  - Owns Play-mode page-local CSS, top chrome styling, stage container styling, prompt presentation, and piano-area framing.
- `lab/static/js/src/components/piano/key.js`
  - Owns white/black key fill, stroke, height, and pressed-state rendering.
- `lab/static/js/src/components/piano/keyboard.js`
  - Owns keyboard container composition and QWERTY badge placement/rendering.
- `lab/static/js/src/components/input/computer_keyboard_ux_logic.js`
  - Existing pure helper for keyboard-mode defaults and special-key label mapping; extend only if necessary for badge text consistency.
- `lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`
  - Existing DOM-free smoke test for keyboard UX defaults; keep passing as a regression check.

### Task 1: Reframe the Play Screen Into a Localized Performance Stage

**Files:**
- Modify: `apps/student/templates/student/player.html`
- Test: `lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

- [ ] **Step 1: Add a failing visual-smoke expectation note to the plan workspace**

Create a local checklist note for the implementation pass describing the expected before/after differences so the manual verification has a concrete target:

```md
Expected after this task:
- top header feels less teal-forward and less Artusi-like
- lower piano area sits inside a darker stage shell
- instruction row visually belongs to the stage
- start prompt remains readable over the stage
```

- [ ] **Step 2: Run the existing keyboard smoke test before changing layout**

Run: `node /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

Expected:

```text
computer_keyboard_ux_logic:
  PASS: exercise default input mode is qwerty
  PASS: grave shortcut renders as a backtick badge
  PASS: letter shortcut remains uppercase

3 passed, 0 failed
```

- [ ] **Step 3: Update the page-local CSS to introduce upper-page harmonization and a stage shell**

Modify the existing `player.html` style block so the upper header/toolbar become more neutral and the piano region becomes a distinct dark surface. Add rules in the same local CSS section rather than creating a new stylesheet.

```css
.s-player-header {
  border-bottom: 1px solid color-mix(in srgb, var(--border) 72%, #6f6558 28%);
  background: linear-gradient(180deg, #fcfaf6 0%, #f3eee6 100%);
  box-shadow: 0 1px 0 rgba(255,255,255,0.7) inset;
}

.s-player-title,
.s-player-title a {
  color: #3a3128;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.s-toolbar-btn {
  border-color: #c8b9a6;
  background: linear-gradient(180deg, #fffdfa 0%, #f1ebe2 100%);
  color: #44372b;
  box-shadow: 0 1px 0 rgba(255,255,255,0.78) inset;
}

.s-toolbar-btn-primary {
  background: linear-gradient(180deg, #4d4338 0%, #332a22 100%);
  border-color: #2c241d;
  color: #f8f3ea;
}

.harmony-ui {
  background:
    radial-gradient(circle at 50% 12%, rgba(106, 83, 54, 0.12), transparent 42%),
    linear-gradient(180deg, #f7f1e8 0%, #efe8de 54%, #e9e2d8 100%);
  border-radius: 24px;
  padding: 0 0 22px;
}

#piano {
  position: relative;
  margin: 14px auto 0;
  padding: 18px 18px 26px;
  border-radius: 28px;
  background:
    linear-gradient(180deg, #2d2927 0%, #151312 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    0 26px 48px rgba(34, 24, 17, 0.24);
}

#piano::before {
  content: "";
  position: absolute;
  left: 18px;
  right: 18px;
  top: 14px;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, #7a1714 0%, #bc2f29 50%, #771511 100%);
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
}

#instruction-panel {
  color: #efe5d8;
}

#exercise-text {
  font-size: 0.94rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

#exercise-status {
  background: linear-gradient(180deg, #645246 0%, #47382f 100%) !important;
  color: #fbf4e9 !important;
  border: 1px solid rgba(255,255,255,0.08);
}
```

- [ ] **Step 4: Move the instruction/prompt spacing so the stage reads as one unit**

Adjust the same template CSS so the instruction block and prompt visually sit within the piano stage instead of floating between unrelated surfaces.

```css
.s-control-bar {
  margin-top: 4px;
  padding: 0 12px 0;
}

#exercise-status-and-tempo {
  gap: 10px;
  margin-bottom: 8px;
}

#user-interaction-solicitation {
  bottom: 18px;
  background: rgba(242, 233, 220, 0.96);
  color: #4a3b30;
  border-color: rgba(120, 97, 77, 0.34);
  box-shadow:
    0 10px 30px rgba(14, 10, 8, 0.28),
    inset 0 1px 0 rgba(255,255,255,0.85);
}
```

- [ ] **Step 5: Reload the target student-player page and verify the stage composition manually**

Open and verify:

`http://127.0.0.1:8000/s/units/1/play/?playlist=PA00AU&exercise_num=4`

Expected:

```text
- top section still behaves the same
- header/buttons are visually warmer and less teal-heavy
- piano region now reads as a single dark stage
- instruction/status area visually belongs to the stage
- start prompt remains readable before first interaction
```

- [ ] **Step 6: Commit the stage-shell pass**

```bash
git add apps/student/templates/student/player.html
git commit -m "feat: add premium stage framing to play mode"
```

### Task 2: Give the Piano Keys More Depth and Presence

**Files:**
- Modify: `lab/static/js/src/components/piano/key.js`
- Test: `lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

- [ ] **Step 1: Run the existing smoke test before touching the renderer**

Run: `node /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

Expected:

```text
3 passed, 0 failed
```

- [ ] **Step 2: Adjust the core key color constants to warmer, more dimensional values**

Update the renderer constants near the top of `key.js`:

```javascript
var COLOR_BLACK_KEYUP = "90-#3a322d:0-#1f1a18:48-#14110f:100";
var COLOR_WHITE_KEYUP = "90-#fffdf8:0-#f7f1e7:58-#ebe1d2:100";
var COLOR_KEYDN = "90-#ccbca8:0-#af9b84:100";
var COLOR_KEYSUSTAIN = "#b7aa98";
```

- [ ] **Step 3: Increase black-key height and refine white/black key strokes**

Modify the renderers so black keys feel taller and both key types gain cleaner depth cues:

```javascript
el.attr({
  stroke: "#9d8e7f",
  "stroke-width": 0.6,
  fill: COLOR_WHITE_KEYUP,
  r: 2.5
});
```

```javascript
calculateHeight: function (keyboardHeight) {
  return 0.72 * keyboardHeight;
},
```

```javascript
el.attr({
  fill: COLOR_BLACK_KEYUP,
  stroke: "#070606",
  "stroke-width": 1,
  r: 2.5
});
```

- [ ] **Step 4: Give the keyboard more vertical presence without changing behavior**

In the same file, preserve the note behavior but ensure the pressed/released states remain readable with the new palette. The implementation should continue to rely on `press()`, `release()`, and `updateColor()` without branching changes.

```javascript
press: function () {
  this.state = STATE_KEYDN;
  this.updateColor();
},

release: function () {
  switch (this.sustain) {
    case SUSTAIN_ON:
      this.setColor(STATE_KEYUP, COLOR_KEYSUSTAIN);
      break;
    case SUSTAIN_OFF:
      this.revertColor(STATE_KEYUP);
      break;
    default:
      this.revertColor(STATE_KEYUP);
  }

  this.state = STATE_KEYUP;
  this.updateColor();
},
```

- [ ] **Step 5: Reload the target page and confirm the keys read as more 3D**

Open and verify:

`http://127.0.0.1:8000/s/units/1/play/?playlist=PA00AU&exercise_num=4`

Expected:

```text
- white keys feel warmer and less flat
- black keys feel taller and more sculpted
- pressed keys still read clearly
- mouse and keyboard interaction still animate key states
```

- [ ] **Step 6: Commit the key-depth pass**

```bash
git add lab/static/js/src/components/piano/key.js
git commit -m "feat: deepen piano key rendering in play mode"
```

### Task 3: Enlarge the Keyboard Presentation and Clean the QWERTY Labels

**Files:**
- Modify: `lab/static/js/src/components/piano/keyboard.js`
- Modify: `apps/student/templates/student/player.html`
- Test: `lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

- [ ] **Step 1: Run the keyboard smoke test before adjusting badge geometry**

Run: `node /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

Expected:

```text
3 passed, 0 failed
```

- [ ] **Step 2: Increase the default keyboard footprint in the renderer**

Update layout defaults near the top of `keyboard.js` so the keyboard has more height and slightly more width budget:

```javascript
defaultHeight: 144,
defaultSmallHeight: 96,
defaultKeyWidth: 32,
```

Retain the existing responsive shrink behavior in `getLayout()` so narrower screens still scale down.

- [ ] **Step 3: Tighten QWERTY badge styling and placement**

Modify `renderQwertyLabels()` in `keyboard.js` to reduce clutter and embed the labels more cleanly:

```javascript
var LABEL_NUDGE_X = 1.5;
```

```javascript
if (isWhite) {
  badgeHeight = 14;
  badgeWidth  = Math.max(layout.keyWidth - 8, 10);
  badgeLeft   = offsetX + 4 + LABEL_NUDGE_X;
  badgeTop    = keyH - badgeHeight - 10;
} else {
  var blackKeyH = 0.72 * keyH;
  var blackWidth = layout.keyWidth / 2;
  badgeHeight = 13;
  badgeWidth  = Math.max(blackWidth - 3, 8);
  badgeLeft   = offsetX + 1.5 + LABEL_NUDGE_X;
  badgeTop    = blackKeyH - badgeHeight - 8;
}
```

- [ ] **Step 4: Update the page-local badge CSS to match the premium piano**

In `player.html`, refine the local keyboard badge CSS:

```css
.qwerty-key-badge {
  font-size: 8px;
  font-weight: 700;
  border-radius: 4px;
  line-height: 14px;
  background: linear-gradient(180deg, rgba(244, 238, 229, 0.98) 0%, rgba(225, 214, 197, 0.98) 100%);
  border: 1px solid rgba(113, 95, 77, 0.36);
  color: #5a4a3c;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.75),
    0 1px 2px rgba(0,0,0,0.16);
}

.qwerty-key-badge.black {
  font-size: 8px;
  line-height: 13px;
  background: linear-gradient(180deg, rgba(73, 68, 66, 0.94) 0%, rgba(39, 35, 33, 0.96) 100%);
  border-color: rgba(255,255,255,0.08);
  color: #f2e8db;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    0 1px 2px rgba(0,0,0,0.34);
}
```

- [ ] **Step 5: Verify the full experience on the target page**

Open and verify:

`http://127.0.0.1:8000/s/units/1/play/?playlist=PA00AU&exercise_num=4`

Expected:

```text
- piano is visibly larger and more substantial
- labels are clean and aligned
- backtick badge remains correct
- start prompt disappears on first interaction
- qwerty remains the visible default
- mouse, qwerty, and MIDI still work
```

- [ ] **Step 6: Re-run the smoke test after all keyboard changes**

Run: `node /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/components/input/computer_keyboard_ux_logic.test.js`

Expected:

```text
3 passed, 0 failed
```

- [ ] **Step 7: Commit the size-and-label pass**

```bash
git add apps/student/templates/student/player.html lab/static/js/src/components/piano/keyboard.js
git commit -m "feat: enlarge play-mode piano and refine key labels"
```

## Self-Review

Spec coverage:

- Stage container and dark localized performance surface: Task 1
- Upper-page harmonization: Task 1
- Instruction/status integration: Task 1
- Key depth and premium rendering: Task 2
- Larger presentation and cleaner labels: Task 3
- Behavior preservation and regression verification: Tasks 1-3 smoke checks and manual checks

Placeholder scan:

- No `TBD`, `TODO`, or deferred implementation markers remain.
- Every task lists exact files and exact commands.

Type consistency:

- Keyboard smoke test path is consistent across all tasks.
- Renderer files and template files match the spec file map.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-play-stage-piano-redesign.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
