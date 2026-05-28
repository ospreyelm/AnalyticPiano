---
date: 2026-05-28
topic: midi-fallback-message
status: approved
---

# Design: MIDI Fallback — Replace Dead-End Error with Keyboard Guidance

## Problem

When `navigator.requestMIDIAccess` is undefined (Safari, Firefox, iOS) or returns a rejection,
`midi.js:onWebMIDIError` broadcasts a notification with `type: "error"` and the message:

> "MIDI setup was unsuccessful. Check that your browser supports the WebMIDI API: use Google
> Chrome (v54+), Microsoft Edge (v79+), or Opera (v42+)."

This message implies the exercise is broken. It isn't — all exercise types (chorale, harmonization,
identification) already accept input via `KeyboardShortcutsComponent` and `NoteNameInputComponent`,
which fire the same `EVENTS.BROADCAST.NOTE` / `EVENTS.BROADCAST.BANK_NOTES` event bus as MIDI.
The computer keyboard path initializes unconditionally in `exercise.js:getComponentMethods()`
regardless of MIDI state.

## Key Finding: Notification System is Dormant

`NotificationsComponent` is commented out in both `exercise.js` (line 199) and `play.js` (line 71),
and its import is removed. The `#notifications` DOM element exists in `exercise.html` and `play.html`
via `_notifications.html`, but nothing renders into it. `EVENTS.BROADCAST.NOTIFICATION` is broadcast
by `midi.js` but silently dropped — the scary MIDI error message was never visible to students.

All CSS for `.notification` and variants is also commented out in `harmony.css` (lines 585–636).

This means the message fix only lands if `NotificationsComponent` is re-enabled simultaneously.

## What Changes

### 1. `lab/static/js/src/config/error_text.js`

Add a `midiUnavailable` key for the no-MIDI case. Keep `midiPluginError` for any future true
MIDI runtime errors.

```js
midiUnavailable: {
  title: "No MIDI Controller",
  description: "Your browser doesn't support MIDI input — use your computer keyboard to play notes instead."
}
```

### 2. `lab/static/js/src/components/midi.js`

In `onWebMIDIError`, change the notification from `"error"` to `"warning"` and use the new text key.

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

### 3. `lab/static/js/src/components/app/exercise.js` and `play.js`

Uncomment `NotificationsComponent` registration in both files:
- Uncomment import line (`'app/components/notifications'`)
- Uncomment `NotificationsComponent` in define callback arguments
- Uncomment the component factory function that calls `c.init(this)` and `c.renderTo(...)`

### 4. `lab/static/css/harmony.css`

Uncomment the full `.notification` CSS block (lines 585–636). Add `.notification.warning` rule:

```css
.notification.warning .title {
    color: #d97706;
}
```

## What Stays the Same

- All input components initialize regardless of MIDI state — no change to `exercise.js`.
- `initListeners()` call in `onWebMIDIError` remains — keyboard event listeners still attach.
- No template, CSS, or backend changes.

## Out of Scope

- Mouse/click chord entry (would require a new chord assembly UI — significant feature).
- Separate handling for "API not available" vs. "permission denied" (marginal value, adds branching).
- Detecting whether the user actually has a keyboard layout loaded (assumed).

## Files Changed

| File | Change |
|------|--------|
| `lab/static/js/src/config/error_text.js` | Add `midiUnavailable` key |
| `lab/static/js/src/components/midi.js` | Change notification type and text key in `onWebMIDIError` |
| `lab/static/js/src/components/app/exercise.js` | Uncomment `NotificationsComponent` registration |
| `lab/static/js/src/components/app/play.js` | Uncomment `NotificationsComponent` registration |
| `lab/static/css/harmony.css` | Uncomment `.notification` CSS block; add `.notification.warning` rule |
