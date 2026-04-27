# QWERTY Keyboard Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When QWERTY input mode is active, show styled keycap badge overlays on each piano key indicating the keyboard shortcut that triggers that note.

**Architecture:** A `<div class="qwerty-labels">` container is absolutely positioned over the Raphael SVG canvas inside `.keyboard`. One `<div class="qwerty-key-badge">` per mapped key, positioned using the same layout data already computed per key. The overlay is shown/hidden by subscribing to the existing `EVENTS.BROADCAST.INPUT_MODE` event (value `"qwerty"` = show, anything else = hide). Labels rebuild automatically when keyboard size/octave changes because `piano.js` already destroys and recreates the entire `KeyboardComponent` on those events.

**Tech Stack:** jQuery, Lodash, RequireJS (AMD), Raphael SVG, existing HarmonyLab event bus

---

### Task 1: Add CSS for label overlay

**Files:**
- Modify: `lab/static/css/harmony.css`

This task adds all styles needed. The `.keyboard` div currently has no `position` set (defaults to `static`) — adding `position: relative` makes it the anchor for the absolute overlay.

- [ ] **Step 1: Find the `.keyboard > svg` rule in harmony.css**

Open `lab/static/css/harmony.css` and find the block around line 807:
```css
.keyboard > svg {
  margin: auto;
}
```

- [ ] **Step 2: Add `position: relative` to `.keyboard`**

Insert immediately before `.keyboard > svg`:
```css
.keyboard {
  position: relative;
}
```

- [ ] **Step 3: Append QWERTY label styles at end of file**

At the very end of `lab/static/css/harmony.css`, add:
```css
/*--------------------------------------------------*/
/* QWERTY key label overlay                         */

.qwerty-labels {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  display: none;
}

.qwerty-key-badge {
  position: absolute;
  font-family: monospace;
  font-size: 9px;
  font-weight: 600;
  text-align: center;
  border-radius: 3px;
  line-height: 1;
  padding: 2px 0;
  background: rgba(0, 0, 0, 0.13);
  border: 1px solid #aaa;
  color: #444;
}

.qwerty-key-badge.black {
  font-size: 8px;
  background: rgba(255, 255, 255, 0.10);
  border-color: #666;
  color: #bbb;
}
```

- [ ] **Step 4: Commit**

```bash
git add lab/static/css/harmony.css
git commit -m "style: add QWERTY key label overlay CSS"
```

---

### Task 2: Add `renderQwertyLabels()` to KeyboardComponent

**Files:**
- Modify: `lab/static/js/src/components/piano/keyboard.js`

The keyboard renders via Raphael SVG. After all key rects are drawn, we build a parallel HTML overlay. Key position data comes from each `KeyComponent` instance in `this.keyComponents`.

**How the reverse note→key map works:**

`keyboard_shortcuts.js` has a `keyMap` where each entry is `{ key: { msg: 'toggleNote', data: N } }` where `N` is a MIDI offset **relative to noteAnchor = 48**. So actual MIDI = `48 + N`. We invert this to get `noteNumber → keyLabel`.

- [ ] **Step 1: Add `Config` to keyboard.js dependencies**

`keyboard.js` currently starts with:
```javascript
define([
  "jquery",
  "lodash",
  "raphael",
  "app/models/keyboard_generator",
  "app/components/events",
  "app/components/component",
  "./key",
], function (
  $,
  _,
  Raphael,
  KeyboardGenerator,
  EVENTS,
  Component,
  KeyComponent
) {
```

Change to:
```javascript
define([
  "jquery",
  "lodash",
  "raphael",
  "app/config",
  "app/models/keyboard_generator",
  "app/components/events",
  "app/components/component",
  "./key",
], function (
  $,
  _,
  Raphael,
  Config,
  KeyboardGenerator,
  EVENTS,
  Component,
  KeyComponent
) {
```

- [ ] **Step 2: Add `renderQwertyLabels()` method to KeyboardComponent prototype**

In `keyboard.js`, locate the `render` method (around line 261). After the closing brace of `render`, add the following three methods inside the `_.extend(KeyboardComponent.prototype, { ... })` block — before the `destroy` method:

```javascript
    renderQwertyLabels: function () {
      // Remove any existing label overlay
      this.keyboardEl.find('.qwerty-labels').remove();

      // Build reverse map: noteNumber -> shortcut key string
      var keyMap = Config.get('keyboardShortcuts.keyMap');
      var NOTE_ANCHOR = 48;
      var noteToKey = {};
      _.each(keyMap, function (val, key) {
        if (val.msg === 'toggleNote') {
          noteToKey[NOTE_ANCHOR + val.data] = key;
        }
      });

      var layout = this.layout;
      var labelsEl = $('<div class="qwerty-labels"></div>');

      _.each(this.keyComponents, function (keyComponent) {
        var label = noteToKey[keyComponent.noteNumber];
        if (!label) { return; }

        var offsetX = keyComponent.calculateOffsetX();
        var isWhite = keyComponent.isWhite;
        var badgeWidth, badgeLeft, badgeBottom, badgeHeight;

        if (isWhite) {
          badgeLeft   = offsetX + 2;
          badgeWidth  = layout.keyWidth - 4;
          badgeBottom = 6;
          badgeHeight = 16;
        } else {
          var blackWidth = layout.keyWidth / 2;
          badgeLeft   = offsetX + 1;
          badgeWidth  = blackWidth - 2;
          badgeBottom = 6;
          badgeHeight = 14;
        }

        var badge = $('<div></div>')
          .addClass('qwerty-key-badge')
          .toggleClass('black', !isWhite)
          .text(label)
          .css({
            left:   badgeLeft + 'px',
            bottom: badgeBottom + 'px',
            width:  badgeWidth + 'px',
            height: badgeHeight + 'px'
          });

        labelsEl.append(badge);
      });

      this.keyboardEl.append(labelsEl);
      this._labelsEl = labelsEl;
    },

    showQwertyLabels: function () {
      if (this._labelsEl) {
        this._labelsEl.show();
      }
    },

    hideQwertyLabels: function () {
      if (this._labelsEl) {
        this._labelsEl.hide();
      }
    },
```

- [ ] **Step 3: Call `renderQwertyLabels()` at end of `render()`**

Find the `render` method:
```javascript
    render: function () {
      var width = this.layout.width;
      var height = this.layout.height;
      var keyWidth = this.layout.keyWidth;
      var paper = this.paper;

      // render keyboard container
      paper.rect(0, 0, width, height).attr("stroke-width", 0);

      // render keys
      _.invoke(this.keyComponents, "render", paper, keyWidth, width, height);

      return this;
    },
```

Change to:
```javascript
    render: function () {
      var width = this.layout.width;
      var height = this.layout.height;
      var keyWidth = this.layout.keyWidth;
      var paper = this.paper;

      // render keyboard container
      paper.rect(0, 0, width, height).attr("stroke-width", 0);

      // render keys
      _.invoke(this.keyComponents, "render", paper, keyWidth, width, height);

      this.renderQwertyLabels();

      return this;
    },
```

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/piano/keyboard.js
git commit -m "feat: render QWERTY key label overlay on keyboard"
```

---

### Task 3: Wire INPUT_MODE event to show/hide labels

**Files:**
- Modify: `lab/static/js/src/components/piano/keyboard.js`

The `EVENTS.BROADCAST.INPUT_MODE` event fires with value `"qwerty"` when QWERTY mode is activated and `"notename"` when switched away. We subscribe in `initListeners` and unsubscribe in `removeListeners`.

- [ ] **Step 1: Add `onInputModeChange` handler and bind it**

In `keyboard.js`, find `initComponent`:
```javascript
    initComponent: function () {
      // ...existing code...
      _.bindAll(this, [
        "onPedalChange",
        "onNoteChange",
        "onClearNotes",
        "triggerNoteChange",
      ]);

      this.initListeners();
    },
```

Change the `_.bindAll` call to include the new handler:
```javascript
      _.bindAll(this, [
        "onPedalChange",
        "onNoteChange",
        "onClearNotes",
        "triggerNoteChange",
        "onInputModeChange",
      ]);
```

- [ ] **Step 2: Add subscription in `initListeners`**

Find:
```javascript
    initListeners: function () {
      this.subscribe(EVENTS.BROADCAST.NOTE, this.onNoteChange);
      this.subscribe(EVENTS.BROADCAST.CLEAR_NOTES, this.onClearNotes);
      this.subscribe(EVENTS.BROADCAST.PEDAL, this.onPedalChange);
      this.bind("key", this.triggerNoteChange);
    },
```

Change to:
```javascript
    initListeners: function () {
      this.subscribe(EVENTS.BROADCAST.NOTE, this.onNoteChange);
      this.subscribe(EVENTS.BROADCAST.CLEAR_NOTES, this.onClearNotes);
      this.subscribe(EVENTS.BROADCAST.PEDAL, this.onPedalChange);
      this.subscribe(EVENTS.BROADCAST.INPUT_MODE, this.onInputModeChange);
      this.bind("key", this.triggerNoteChange);
    },
```

- [ ] **Step 3: Add unsubscription in `removeListeners`**

Find:
```javascript
    removeListeners: function () {
      this.unsubscribe(EVENTS.BROADCAST.NOTE, this.onNoteChange);
      this.unsubscribe(EVENTS.BROADCAST.CLEAR_NOTES, this.onClearNotes);
      this.unsubscribe(EVENTS.BROADCAST.PEDAL, this.onPedalChange);
      this.unbind("key", this.triggerNoteChange);
    },
```

Change to:
```javascript
    removeListeners: function () {
      this.unsubscribe(EVENTS.BROADCAST.NOTE, this.onNoteChange);
      this.unsubscribe(EVENTS.BROADCAST.CLEAR_NOTES, this.onClearNotes);
      this.unsubscribe(EVENTS.BROADCAST.PEDAL, this.onPedalChange);
      this.unsubscribe(EVENTS.BROADCAST.INPUT_MODE, this.onInputModeChange);
      this.unbind("key", this.triggerNoteChange);
    },
```

- [ ] **Step 4: Add `onInputModeChange` method**

Inside the `_.extend(KeyboardComponent.prototype, { ... })` block, add this method (e.g. after `onPedalChange`):

```javascript
    onInputModeChange: function (mode) {
      if (mode === 'qwerty') {
        this.showQwertyLabels();
      } else {
        this.hideQwertyLabels();
      }
    },
```

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/piano/keyboard.js
git commit -m "feat: show/hide QWERTY labels on INPUT_MODE event"
```

---

### Task 4: Manual verification

There are no unit tests for the piano keyboard rendering (it's a Raphael SVG UI component with no test harness in this codebase). Verify manually in the browser.

- [ ] **Step 1: Start the dev server**

```bash
python manage.py runserver
```

Open `http://localhost:8000` in a browser.

- [ ] **Step 2: Verify labels hidden by default**

Load the exercise page. The keyboard should show **no** QWERTY badges. Open browser DevTools → Elements, confirm `.qwerty-labels` exists in the DOM but has `display: none`.

- [ ] **Step 3: Switch to QWERTY mode**

Click the QWERTY toggle in the input mode selector (below the keyboard). Confirm:
- `.qwerty-labels` becomes visible (`display: block` or `display: ''`)
- Each key with a shortcut shows a small badge at its bottom
- White key badges: dark text on faint background with border
- Black key badges: light text on faint dark background

- [ ] **Step 4: Verify badge positions**

Check a few specific keys:
- `Q` badge on the A below middle C (MIDI 45 = 48+(-3)... wait — check against actual keymap: `q: { msg: 'toggleNote', data: 45 }` → MIDI = 48+45 = 93? No.

**Important:** Re-read the keyMap. `data` values in `keyboard_shortcuts.js` are the raw offset added to `noteAnchor = 48`. E.g. `q: { data: 45 }` → MIDI 48+45 = 93? That can't be right for A3. Actually re-check — the comment says "relative to C one octave below middle C = MIDI 48" but `noteAnchor` in `shortcuts.js` is set to `48` as the default. So `q: { data: 45 }` → 48+45 = 93 = A5. But that seems high.

**Actually check the real values:** `e: { data: 48 }` — if noteAnchor=48 then MIDI=96 which is way too high. The comment in keyboard_shortcuts.js says "Maps a key to an integer relative to the C one octave below middle C (MIDI note number 48)" but `noteAnchor: 0` in the config. `shortcuts.js` hardcodes `noteAnchor = 48` only as a fallback if config doesn't have it. The config has `noteAnchor: 0`, so the component uses 0 from config... but wait: `shortcuts.js` line 47-50 reads:

```javascript
this.noteAnchor = 48;
if (SHORTS.hasOwnProperty("noteAnchor")) {
  this.noteAnchor = SHORTS.noteAnchor;  // → 0 from config
}
```

So `noteAnchor = 0` and `e: { data: 48 }` → MIDI 48 = C3. That makes sense. So `NOTE_ANCHOR` in `renderQwertyLabels` must be `0`, not `48`.

- [ ] **Step 5: Fix NOTE_ANCHOR if needed**

In `keyboard.js` `renderQwertyLabels()`, the constant was written as `var NOTE_ANCHOR = 48`. **Change it to `0`**:

```javascript
      var NOTE_ANCHOR = 0;
```

Then verify: `e: { data: 48 }` → noteToKey[0+48] = noteToKey[48] = `'e'`. MIDI 48 = C3. The keyboard's 49-key layout starts at MIDI 36 (C2), so C3 exists and should show `E` badge. Confirm in browser.

- [ ] **Step 6: Switch back to Note Name mode**

Click the Note Name toggle. Confirm all badges disappear.

- [ ] **Step 7: Resize keyboard**

Change keyboard size (e.g. from 49 to 61 keys via the toolbar). Confirm:
- Keyboard redraws at new size
- QWERTY badges still absent (mode is Note Name after step 6)
- Switch back to QWERTY — badges appear at correct positions for new key width

- [ ] **Step 8: Commit fix if NOTE_ANCHOR was wrong**

```bash
git add lab/static/js/src/components/piano/keyboard.js
git commit -m "fix: use noteAnchor=0 for QWERTY label reverse map"
```

---

### Task 5: Final cleanup commit

- [ ] **Step 1: Check for any console errors**

Open browser DevTools → Console. Play the keyboard in QWERTY mode. Confirm no JS errors.

- [ ] **Step 2: Final commit**

```bash
git add -p  # review any remaining changes
git commit -m "feat: QWERTY keyboard label overlay complete"
```
