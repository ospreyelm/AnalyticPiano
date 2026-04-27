# QWERTY Keyboard Labels Design

**Date:** 2026-04-26  
**Status:** Approved

## Goal

When QWERTY input mode is active, display styled keycap badges on each piano key showing the keyboard shortcut letter/number that triggers that note. Badges disappear when QWERTY mode is inactive.

## Behaviour

- Labels visible **only when QWERTY input mode is active** (i.e. `INPUT_MODE` event value is `"qwerty"`)
- Each key with a mapped shortcut shows one badge
- Badge content: key letter/number only (no note name)
- Labels rebuild automatically when keyboard size or octave changes

## Visual Design

- White key badges: subtle rounded rectangle, `background: rgba(0,0,0,0.13)`, `border: 1px solid #aaa`, dark text — positioned at bottom of key
- Black key badges: `background: rgba(255,255,255,0.10)`, `border: 1px solid #666`, light text — positioned near bottom of black key
- Font: monospace, bold, ~9px white keys / ~8px black keys
- Badge sits `2px` inset from key edges horizontally, `6px` from key bottom

## Architecture

### New: `.qwerty-labels` overlay div (inside `keyboard.js`)

- A `<div class="qwerty-labels">` is created inside the `.keyboard` div (which wraps the Raphael SVG)
- `position: absolute; top: 0; left: 0; pointer-events: none` — sits over SVG without blocking mouse events on keys
- One `<div class="qwerty-key-badge">` per key that has a shortcut mapping
- Hidden by default; shown/hidden via `INPUT_MODE` event

### Position math

Computed from layout data already present on each `KeyComponent`:

```
White key badge:
  left   = key.calculateOffsetX() + 2
  width  = layout.keyWidth - 4
  bottom = 6px
  height = ~16px

Black key badge:
  left   = key.calculateOffsetX() + 1
  width  = (layout.keyWidth / 2) - 2   // black key width = keyWidth/2
  bottom = 6px (from black key bottom = layout.height * 0.66)
  height = ~14px
```

### Shortcut → note mapping

`keyboard_shortcuts.js` maps key letters to MIDI note offsets relative to `noteAnchor`. The label layer inverts this: for each `KeyComponent.noteNumber`, look up which shortcut letter produces that note and render it as the badge label.

A reverse map is built once at render time:
```javascript
// noteNumber → shortcut string
var noteToKey = {};
_.each(Config.get('keyboardShortcuts.keyMap'), function(val, key) {
  if (val.msg === 'toggleNote') {
    noteToKey[val.data + noteAnchor] = key;
  }
});
```

### Files changed

| File | Change |
|------|--------|
| `lab/static/js/src/components/piano/keyboard.js` | Add `renderQwertyLabels()`, `showQwertyLabels()`, `hideQwertyLabels()`. Call `renderQwertyLabels()` at end of `render()`. Subscribe to `EVENTS.BROADCAST.INPUT_MODE` in `initListeners()`. |
| `lab/static/js/src/components/piano/key.js` | No changes |
| `lab/static/css/harmony.css` | Add `.keyboard { position: relative; }`, `.qwerty-labels`, `.qwerty-key-badge`, `.qwerty-key-badge.black` |

### Lifecycle

1. `KeyboardComponent.render()` → calls `renderQwertyLabels()` after keys render
2. `renderQwertyLabels()` builds reverse note→key map, creates `.qwerty-labels` div with one badge per mapped key, appends to `this.keyboardEl`
3. `initListeners()` subscribes to `INPUT_MODE`; handler calls `showQwertyLabels()` or `hideQwertyLabels()`
4. `destroy()` — `.qwerty-labels` is removed automatically when `keyboardEl.remove()` is called (no extra cleanup needed)
5. On keyboard resize/octave change: `piano.js` already destroys and recreates `KeyboardComponent` → labels rebuild fresh with new layout dimensions

## CSS additions

```css
.keyboard {
  position: relative;  /* anchor for label overlay */
}

.qwerty-labels {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  display: none;        /* hidden until QWERTY mode active */
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

## Out of scope

- Showing note names on badges
- Animating badges on keypress
- Any change to the separate QWERTY help panel (collapsible guide below the keyboard)
