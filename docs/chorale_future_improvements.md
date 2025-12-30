# Chorale Exercise System - Future Improvements

**Status:** Features 1 & 3 completed. Features 2, 4, & 5 pending.

This document outlines improvements to bring chorale exercises to feature parity with legacy exercises and add new pedagogical capabilities.

---

## Completed Features ✅

### Feature 1: Instructional Text (Commit d52a75e)
- ✅ Updated `import_chorale.py` to generate richer introText and reviewText
- ✅ Clear instructions on how to use keyboard/MIDI controller
- ✅ Explanation of note color feedback

**File:** `apps/exercises/management/commands/import_chorale.py` (lines 89-90)

### Feature 3: Detailed Grading Feedback (Commit d52a75e)
- ✅ Added windowStats tracking to chorale_grader.js
- ✅ Track per-window: status, correct notes, incorrect notes, completion time
- ✅ Build problems array in grade() method with per-window statistics
- ✅ Enable analytics and detailed error tracking

**File:** `lab/static/js/src/models/chorale_grader.js`
- reset() (lines 50-52)
- initFromDefinition() (lines 97-106)
- noteOn() (lines 246-252)
- _advanceIfWindowComplete() (lines 330-350)
- grade() (lines 378-402)

---

## Pending Features (High Priority)

### Feature 2: Visual Feedback for Incorrect Notes

**Objective:** Color incorrect notes red in the VexFlow renderer for immediate visual feedback.

**Current State:**
- Notes are colored gray (unplayed) or black (played correctly)
- No visual distinction for incorrect notes
- Students don't know which wrong notes they played

**Implementation:**

**File:** `lab/static/js/src/components/music/rendering/vexflow_adapter.js` (lines 371-411)

**Step 1: Create incorrectNoteIds Set in chorale_grader.js**

In `reset()`:
```javascript
this.incorrectNoteIds = new Set();  // Track IDs of notes that were played incorrectly
```

In `noteOn()` when a wrong note is detected (line 254):
```javascript
// NEW: Track the incorrect note ID for visual feedback
// (We need to add ID tracking when wrong notes are played)
```

**Step 2: Expose incorrectNoteIds to the renderer**

In `exercise_context.js`, pass incorrectNoteIds to VexFlow adapter:
```javascript
var idState = {
  playedNoteIds: this.grader.playedNoteIds,
  incorrectNoteIds: this.grader.incorrectNoteIds,  // NEW
  nextId: nextId
};
```

**Step 3: Update VexFlow coloring logic**

In `vexflow_adapter.js`:
```javascript
var noteId = idState.nextId || 0;
var played = idState.playedNoteIds && idState.playedNoteIds.has(noteId);
var incorrect = idState.incorrectNoteIds && idState.incorrectNoteIds.has(noteId);

if (incorrect) {
  note.setStyle({ fillStyle: '#FF0000', strokeStyle: '#FF0000' });  // Red
} else if (played) {
  note.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });  // Black
} else {
  note.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });  // Gray
}
```

**Challenge:** We need to track which timeline event IDs correspond to incorrect notes. Currently, when a wrong note is played, we don't have the timeline event ID - we only have the MIDI pitch. We need to either:
1. Store event IDs when wrong notes are detected, OR
2. Find the wrong note in the timeline after the fact

**Testing:**
1. Load a chorale exercise
2. Play a wrong note
3. Verify the note appears in red in the score
4. Play a correct note - verify it turns black
5. Verify unplayed notes remain gray

---

## Pending Features (Medium Priority)

### Feature 4: Mode Variations

**Objective:** Support different playing modes (play outer voices only, soprano only, with figured bass, etc.)

**Current State:**
- All exercises use "play-all-voices" mode
- No mode variations in exercise definition
- No voice filtering in grader

**Available Modes:**
1. `play-all-voices` - All four SATB voices (current)
2. `play-outer` - Soprano + Bass only (for bass line practice)
3. `play-soprano` - Soprano only (melody only)
4. `play-bass-figures` - Bass with figured bass symbols
5. `play-inner` - Alto + Tenor only (inner voice practice)

**Implementation:**

**File:** `lab/static/js/src/models/chorale_grader.js`

**Step 1: Filter timeline by mode in initFromDefinition()**

After building timeline (line 55):
```javascript
// Filter timeline based on mode
var mode = definition.data.mode || 'play-all-voices';
if (mode !== 'play-all-voices') {
  this.timeline = this._filterTimelineByMode(this.timeline, mode);
}
```

**Step 2: Implement _filterTimelineByMode()**

```javascript
_filterTimelineByMode: function (timeline, mode) {
  var voiceFilter = {
    'play-soprano': ['treble-0'],     // Voice 0 = soprano
    'play-bass': ['bass-0'],          // Bass staff, voice 0
    'play-outer': ['treble-0', 'bass-0'],
    'play-inner': ['treble-1', 'bass-1'],  // Voice 1 = alto/tenor
  };

  if (!voiceFilter[mode]) return timeline;

  var allowedVoices = voiceFilter[mode];
  return timeline.filter(function(ev) {
    var voiceKey = ev.staff + '-' + ev.voiceIndex;
    return allowedVoices.indexOf(voiceKey) !== -1;
  });
},
```

**Step 3: Update exercise definition**

In `import_chorale.py` (line 68):
```python
"mode": "play-all-voices",  # Can be: play-all-voices, play-outer, play-soprano, etc.
```

**Testing:**
1. Import exercise with mode="play-soprano"
2. Verify only soprano notes are expected
3. Verify bass/alto notes are grayed out or hidden
4. Verify playing bass notes is marked INCORRECT

---

### Feature 5: Grading Configuration

**Objective:** Make grading configuration actually functional (currently ignored).

**Current State:**
- Grading config exists in exercise definition (lines 80-84 of import_chorale.py)
- Config is never used - all values ignored
- Hard-coded behavior only

```python
"grading": {
    "onsetWindowMs": 150,           # Unused
    "releaseTolerancePct": 40,      # Unused
    "octaveFlexible": False         # Unused
}
```

**Implementation:**

**Step 1: Implement releaseTolerancePct**

Currently: Notes must be held until next window starts
Desired: Release can happen up to N% after window end

In `chorale_grader.js` noteOff():
```javascript
noteOff: function (midi) {
  var config = this._config;  // Store grading config in grader
  var toleranceMs = (config.releaseTolerancePct / 100) * 1024;  // ticks

  // Allow late release if within tolerance
  if (this.heldMidi.has(midi)) {
    this.heldMidi.delete(midi);
  }
},
```

**Step 2: Implement octaveFlexible**

Currently: C4 (MIDI 60) matches only C4
Desired: If true, any octave's C matches

In `noteOn()` matching logic:
```javascript
var config = this._config;
var midi_matches = function(played, expected) {
  if (played === expected) return true;
  if (config.octaveFlexible) {
    return (played % 12) === (expected % 12);  // Same note, any octave
  }
  return false;
};
```

**Step 3: Make onsetWindowMs functional**

Currently: Windows are fixed at exact onsets
Desired: Allow notes within ±onsetWindowMs to match

Currently hardcoded merge: 1024 ticks (1 beat)
Could be configurable: `config.onsetWindowMs * (4096 / 60000 / tempo)`

**Testing:**
1. Create exercise with octaveFlexible: true
2. Play a note in different octave - should match
3. Create exercise with octaveFlexible: false
4. Play same note in different octave - should be INCORRECT
5. Test releaseTolerancePct with held notes

---

## Pending Features (Lower Priority)

### Feature 6: Mode-Specific Visual Enhancements

**Objective:** Adjust rendering based on mode.

- `play-bass-figures`: Show figured bass symbols in larger font, highlight bass staff
- `play-outer`: Gray out inner voices (alto/tenor)
- `play-soprano`: Gray out lower voices, enlarge soprano

**Implementation:** Conditional styling in vexflow_adapter.js based on mode

---

### Feature 7: Hint System

**Objective:** Provide hints to stuck students.

**Possible Hints:**
- "You need to play a note at this pitch: X"
- "Next chord contains: C, G, E, C"
- "Hold this note longer"
- Show next window notes in lighter gray

**Implementation:** Modal dialog with progressive hint levels

---

### Feature 8: Performance Metrics Dashboard

**Objective:** Analyze which parts students struggle with most.

**Metrics to Collect:**
- Per-window error rate (% of students who made mistakes)
- Per-note error rate (which specific notes are hard)
- Per-voice error rate (soprano vs bass vs inner)
- Timing statistics (how long to complete each window)

**Display:** Dashboard showing heat maps of difficult passages

---

## Implementation Priority

### Phase 1 (Next)
1. **Feature 2** - Visual feedback for incorrect notes (high impact, low effort)
2. **Feature 4** - Mode variations (enables new exercise types)

### Phase 2
3. **Feature 5** - Grading configuration (makes system flexible)
4. **Feature 6** - Mode-specific rendering (improves UX)

### Phase 3
5. **Feature 7** - Hint system (pedagogical enhancement)
6. **Feature 8** - Performance analytics (data insights)

---

## Technical Debt & Cleanup

### Issue 1: Configuration Storage in Grader

Currently, the grader receives config in `initFromDefinition()` but doesn't store it.

**Solution:** Store config object:
```javascript
initFromDefinition: function (definition) {
  this._config = definition.data.grading || {};  // Store for later use
  // ...
}
```

### Issue 2: Timeline Event IDs for Incorrect Notes

When tracking incorrect notes, we need timeline event IDs for rendering feedback.

**Current:** incorrectNotes = { windowIndex: [midi1, midi2] }
**Needed:** Ability to map MIDI pitch back to event IDs

**Solution:** When wrong note detected, find matching timeline events:
```javascript
if (!matched) {
  // Find and store event IDs of unplayed notes with this MIDI
  var wrongEventIds = [];
  for (var i = 0; i < currentWindow.length; i++) {
    if (tl[currentWindow[i]].midi === midi && !this.playedNoteIds.has(tl[currentWindow[i]].id)) {
      wrongEventIds.push(tl[currentWindow[i]].id);
    }
  }
  this.incorrectNoteIds.add(...wrongEventIds);
}
```

### Issue 3: Exercise Definition Validation

No validation of mode/grading config values.

**Solution:** Add validation in exercise_definition.js:
```javascript
isValidMode: function() {
  var valid = ['play-all-voices', 'play-outer', 'play-soprano'];
  return valid.indexOf(this.data.mode) !== -1;
}
```

---

## Testing Checklist for Future Work

- [ ] Feature 2: Incorrect notes appear in red
- [ ] Feature 4: Mode filtering works for all modes
- [ ] Feature 5: octaveFlexible allows octave variation
- [ ] Feature 5: releaseTolerancePct allows late release
- [ ] Feature 6: Rendering updates based on mode
- [ ] Feature 7: Hint modal appears on demand
- [ ] Feature 8: Dashboard loads and displays metrics
- [ ] All existing tests still pass
- [ ] No regressions in performance

---

## References

- [chorale_grader.js](lab/static/js/src/models/chorale_grader.js) - Main implementation
- [chorale_exercises_plan.md](docs/chorale_exercises_plan.md) - Curriculum specification
- [exercise_definition.js](lab/static/js/src/models/exercise_definition.js) - Type definitions
- [vexflow_adapter.js](lab/static/js/src/components/music/rendering/vexflow_adapter.js) - Rendering
