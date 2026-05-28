# MIDI Fallback Message Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dead-end MIDI error notification with a keyboard-guidance message, and re-enable the dormant NotificationsComponent so the message actually renders.

**Architecture:** Five files change. CSS and JS notification infrastructure is uncommented (it was fully written but disabled). The MIDI error text config gets a new key; `midi.js` switches from `"error"` type to `"warning"` and references that key. No backend changes, no new files.

**Tech Stack:** Vanilla JS (AMD/RequireJS modules), CSS, Django templates (already correct — no changes needed).

**Spec:** `docs/superpowers/specs/2026-05-28-midi-fallback-message-design.md`

---

## File Map

| File | Action |
|------|--------|
| `lab/static/js/src/config/error_text.js` | Add `midiUnavailable` key |
| `lab/static/js/src/components/midi.js` | Change `onWebMIDIError` notification type + text |
| `lab/static/js/src/components/app/exercise.js` | Uncomment `NotificationsComponent` import + registration |
| `lab/static/js/src/components/app/play.js` | Uncomment `NotificationsComponent` import + registration |
| `lab/static/css/harmony.css` | Uncomment `.notification` CSS block; add `.warning` rule |

---

## Task 1: Add `midiUnavailable` text key and update `midi.js`

**Files:**
- Modify: `lab/static/js/src/config/error_text.js`
- Modify: `lab/static/js/src/components/midi.js`

- [ ] **Step 1: Add new text key to `error_text.js`**

The file currently contains only `midiPluginError`. Add `midiUnavailable` alongside it. The full file after the change:

```js
define({
  midiPluginError: {
    title: "MIDI Error",
    description:
      "MIDI setup was unsuccessful. Check that your browser supports the WebMIDI API: use Google Chrome (v54+), Microsoft Edge (v79+), or Opera (v42+). For more details, see https://caniuse.com/midi/."
  },
  midiUnavailable: {
    title: "No MIDI Controller",
    description: "Your browser doesn't support MIDI input — use your computer keyboard to play notes instead."
  }
});
```

- [ ] **Step 2: Update `onWebMIDIError` in `midi.js`**

Find `onWebMIDIError` at line 188. Replace the broadcast call. Before:

```js
onWebMIDIError: function () {
  this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
    type: "error",
    title: MIDI_ERROR_TITLE,
    description: MIDI_ERROR_CONTENT,
  });
  this.initListeners();
},
```

After (leave `initListeners()` call untouched):

```js
onWebMIDIError: function () {
  this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
    type: "warning",
    title: Config.get("errorText.midiUnavailable.title"),
    description: Config.get("errorText.midiUnavailable.description"),
  });
  this.initListeners();
},
```

Note: `Config` is already imported at the top of `midi.js` (line 63 uses `Config.get`). No new import needed.

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/config/error_text.js lab/static/js/src/components/midi.js
git commit -m "feat: replace dead-end MIDI error with keyboard-guidance warning"
```

---

## Task 2: Re-enable `NotificationsComponent` in `exercise.js`

**Files:**
- Modify: `lab/static/js/src/components/app/exercise.js`

- [ ] **Step 1: Uncomment the import string (line 13)**

Before:
```js
  // 'app/components/notifications',
  "app/components/input/shortcuts",
```

After:
```js
  "app/components/notifications",
  "app/components/input/shortcuts",
```

- [ ] **Step 2: Uncomment the callback argument (line 40)**

Before:
```js
  MidiComponent,
  // NotificationsComponent,
  KeyboardShortcutsComponent,
```

After:
```js
  MidiComponent,
  NotificationsComponent,
  KeyboardShortcutsComponent,
```

- [ ] **Step 3: Uncomment the component registration (lines 198–203)**

Before:
```js
      // function () {
      //  var c = new NotificationsComponent();
      //  c.init(this);
      //  c.renderTo("#notifications", "#notificationAlerts");
      //  this.addComponent(c);
      // },
```

After:
```js
      function () {
        var c = new NotificationsComponent();
        c.init(this);
        c.renderTo("#notifications", "#notificationAlerts");
        this.addComponent(c);
      },
```

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/app/exercise.js
git commit -m "feat: re-enable NotificationsComponent in exercise app"
```

---

## Task 3: Re-enable `NotificationsComponent` in `play.js`

**Files:**
- Modify: `lab/static/js/src/components/app/play.js`

- [ ] **Step 1: Uncomment the import string (line 10)**

Before:
```js
  // 'app/components/notifications',
  "app/components/input/shortcuts",
```

After:
```js
  "app/components/notifications",
  "app/components/input/shortcuts",
```

- [ ] **Step 2: Uncomment the callback argument (line 27)**

Before:
```js
  MidiComponent,
  // NotificationsComponent,
  KeyboardShortcutsComponent,
```

After:
```js
  MidiComponent,
  NotificationsComponent,
  KeyboardShortcutsComponent,
```

- [ ] **Step 3: Uncomment the component registration (lines 70–75)**

Before:
```js
      // function () {
      // 	var c = new NotificationsComponent();
      // 	c.init(this);
      // 	c.renderTo("#notifications");
      // 	this.addComponent(c);
      // },
```

After:
```js
      function () {
        var c = new NotificationsComponent();
        c.init(this);
        c.renderTo("#notifications");
        this.addComponent(c);
      },
```

Note: `play.js` passes only `"#notifications"` (no second arg) — match that, don't add `"#notificationAlerts"`.

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/app/play.js
git commit -m "feat: re-enable NotificationsComponent in play app"
```

---

## Task 4: Uncomment notification CSS and add `.warning` rule

**Files:**
- Modify: `lab/static/css/harmony.css`

- [ ] **Step 1: Uncomment the `.notification` CSS block**

In `harmony.css`, the block from line 585 to 636 is wrapped in `/* ... */`. The opening `/*.notificationAlerts {` is at line 585 and the closing `}*/` is at line 636.

Remove the `/*` from line 585 (it appears as `/*.notificationAlerts {`) and the `*/` from line 636 (it appears as `}*/`), leaving all inner rules intact.

After uncommenting, the block starts with:
```css
.notificationAlerts {
    color: white;
    background-color: black;
    ...
```
and ends with:
```css
    display: block;
    margin-top: 0.5rem;
}
```

- [ ] **Step 2: Add `.warning` color rule**

Immediately after the `.notification.info .title` rule (which sets `color: blue`), add:

```css
.notification.warning .title {
    color: #d97706;
}
```

So the color rules read:
```css
.notification.error .title {
    color: red;
}
.notification.success .title {
    color: green;
}
.notification.info .title {
    color: blue;
}
.notification.warning .title {
    color: #d97706;
}
```

- [ ] **Step 3: Commit**

```bash
git add lab/static/css/harmony.css
git commit -m "feat: uncomment notification CSS and add warning color rule"
```

---

## Task 5: Manual verification

No automated tests exist for this UI flow. Verify manually.

- [ ] **Step 1: Start the dev server**

```bash
python manage.py runserver
```

- [ ] **Step 2: Open an exercise in a browser without MIDI support**

Option A — use Firefox or Safari (no Web MIDI API).
Option B — in Chrome DevTools console, temporarily override before page load:
```js
// Paste in console before exercise loads, then navigate
Object.defineProperty(navigator, 'requestMIDIAccess', { value: undefined });
```

Navigate to any exercise page (e.g. `/lab/exercise/<id>/`).

- [ ] **Step 3: Verify the warning notification appears**

Expected: amber-colored "No MIDI Controller" title with "Your browser doesn't support MIDI input — use your computer keyboard to play notes instead." body. Should NOT say "MIDI Error" or mention Chrome/Edge/Opera.

- [ ] **Step 4: Verify keyboard input still works**

Press keys on the computer keyboard (default mapping: home row = white keys around middle C). Notes should register in the exercise.

- [ ] **Step 5: Verify MIDI still works in Chrome**

Open Chrome with a MIDI controller attached. Navigate to exercise. Notification should NOT appear. MIDI input should work normally.
