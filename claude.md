# HarmonyLab Chorale Exercise System - Implementation Guide

**Status: FIXED** ✓ All issues resolved. See resolution summary below.

## Overview

The Chorale exercise type is a specialized grading system for teaching Bach chorales using MIDI input. Unlike traditional chord-based exercises, chorales use an **onset-based window system** that requires students to play notes in order as they appear in the score.

## Resolution Summary

**Three critical bugs were fixed in chorale_grader.js:**

### 1. Held Notes Algorithm Bug (Lines 201-202)
**Problem:** Voice tracking only marked voices as "seen" when notes were held, not after checking. This caused the algorithm to search backwards through voice history multiple times, incorrectly missing held notes.

**Fix:** Move `voiceSeen[key] = true` outside the held-note conditional to always mark a voice as seen after checking its most recent event.

**Impact:** Bass notes with sustained durations now correctly detected as "held" and turn black when played.

### 2. Passing Tones in Separate Windows (Lines 62-88)
**Problem:** Inner voice passing tones appear at non-beat-aligned onsets (e.g., 2560 ticks instead of 2048). These created separate windows containing only 1-2 notes that couldn't be satisfied by beat-aligned MIDI input from students.

**Example:** Measure 4 has soprano at beat 2 (onset 2048), but alto has a passing tone at offset 2560 (mid-beat). These were in separate windows, blocking window completion.

**Fix:** During initialization, merge all onset groups that are within 1024 ticks (1 beat) of each other into single windows. This groups passing tones with their beat-aligned chords.

**Impact:** All notes (passing tones and main voices) are now in the same window and can be played together. Passing tones turn black when played.

### 3. Enhanced Diagnostics (Lines 89-110)
Added detailed logging:
- Report how many onset groups were merged into windows
- Track which windows contain the last measure
- Show onset + duration for held notes in grading logs

**Impact:** Enables debugging of timing issues and window progression problems.

## Architecture

### Key Files

- **[chorale_grader.js](lab/static/js/src/models/chorale_grader.js)** - Main grading engine (342 lines)
- **[score_timeline.js](lab/static/js/src/components/music/score_timeline.js)** - Timeline construction from CIR data (126 lines)
- **[exercise_sheet.js](lab/static/js/src/components/music/exercise_sheet.js)** - UI initialization for chorales
- **[exercise_context.js](lab/static/js/src/models/exercise_context.js)** - Integration with broader exercise system
- **[exercise_definition.js](lab/static/js/src/models/exercise_definition.js)** - Exercise type definition
- **[vexflow_adapter.js](lab/static/js/src/components/music/vexflow_adapter.js)** - Rendering with analysis overlays
- **[import_chorale.py](apps/exercises/management/commands/import_chorale.py)** - Django management command for importing chorales
- **[chorale_exercises_plan.md](docs/chorale_exercises_plan.md)** - Curriculum and design specification

### Data Flow

```
CIR JSON Score (Bach chorales in canonical internal representation)
    ↓
ScoreTimeline.buildTimeline() → Flat timeline of note events
    ↓
ChoraleGrader.initFromDefinition() → Groups timeline by onset
    ↓
MIDI input (noteOn/noteOff events)
    ↓
ChoraleGrader.grade() → CORRECT/PARTIAL/INCORRECT
    ↓
ExerciseContext → Update UI, advance exercise
```

## How the Chorale Grader Works

### 1. Initialization Phase

When an exercise starts:

```javascript
grader.initFromDefinition(definition)
```

This does:
1. Extracts the CIR score from definition
2. Calls `ScoreTimeline.buildTimeline(score)` to create a flat timeline
3. Groups events by **onset** (timing) using `groupByOnset()`
4. Sets `pointer = 0` (current window index)
5. Initializes `playedNoteIds` Set (tracks which notes have been played)

**Timeline event structure:**
```javascript
{
  id: 0,              // unique identifier for rendering correlation
  onset: 1024,        // cumulative ticks from start
  duration: 2048,     // ticks for this note
  midi: 60,           // MIDI pitch (C4)
  staff: "treble",    // which staff
  voiceIndex: 0,      // which voice on that staff
  measureIndex: 0,    // which measure
  itemIndex: 2,       // position in voice's items array
  headIndex: 0        // which note in a chord
}
```

**Window groups example:**
- Window 0 (onset=0): MIDI notes [60, 52, 43, 33] (SATB chord)
- Window 1 (onset=1024): MIDI notes [57, 52, 43, 33]
- Window 2 (onset=2048): MIDI notes [60, 50, 45, 33]
- etc.

### 2. Play Phase - noteOn Events

When student plays MIDI note at pitch P:

```javascript
grader.noteOn(midi)
```

Process:
1. Add MIDI to `heldMidi` set (notes currently being held)
2. Get current window (pointer) expected notes
3. Calculate **held notes** - notes from previous onsets still sounding (important for tied notes and overlaps)
4. Try to match played note against:
   - Current window's new attacks
   - Held notes from previous windows
5. If match found: add event ID to `playedNoteIds`
6. If no match: set `mistakeMade = true` and `_lastIncorrect = true`
7. Check if window is complete and auto-advance if needed

### 3. Held Notes Algorithm

This is critical for correctness with tied notes and overlaps:

```javascript
_getHeldNotesAtOnset(onset)
```

For each voice/staff combo:
1. Walk timeline backwards from the target onset
2. Find the most recent event **before** the onset
3. Check if that note is still sounding: `ev.onset + ev.duration > onset`
4. Collect all held notes

**Why this matters:**
- In Bach chorales, inner voices often have tied notes
- Bass might hold a note under two treble notes
- Student must only play the NEW notes, not re-trigger held ones

### 4. Grading Phase

Called after each MIDI event or completion:

```javascript
grader.grade(definition, inputChords)
```

Returns:
```javascript
{
  result: "correct|partial|incorrect",
  score: 0|1|2,           // 0=correct, 1=partial, 2=incorrect
  problems: [],
  activeIndex: windowIndex
}
```

**Grading logic:**
- If `_lastIncorrect` was set (wrong note just played): return **INCORRECT** (score=2)
- If `finished` is true (all windows complete): return **CORRECT** (score=0)
- Otherwise: return **PARTIAL** (score=1)

Note: `_lastIncorrect` is a **one-shot flag** consumed after grading to allow partial correction.

### 5. Window Advancement

Called automatically in `noteOn` or explicitly:

```javascript
_advanceIfWindowComplete()
```

Loop until window complete:
1. Check if all required notes played
   - All new attacks in current window
   - All held notes still sounding
2. If yes: increment `pointer`
3. If `pointer >= windowGroups.length`: set `finished = true`

**Important:** No auto-satisfaction of repeated chords - player must explicitly play each note.

---

## Common Issues and Troubleshooting

### Issue 1: Notes Not Registering

**Symptom:** Playing correct notes but they don't turn black (not recognized as played)

**Root causes:**

1. **MIDI number mismatch**
   - Check console log: `[1. PLAY] NOTE ON: X`
   - Verify against window log: `Current window onset=..., new attacks: [60, 52, 43, 33]`
   - **Fix:** Ensure keyboard/MIDI controller octave matches expected range

2. **Timeline building error**
   - Check console: `[INIT] Built timeline with N events...`
   - Verify measure counts match score
   - **Fix:** Check CIR JSON score structure - ensure valid measures/staves/voices

3. **Event ID mismatch** (rendering doesn't match grader)
   - IDs should correlate between grader and renderer
   - Check in [score_timeline.js:114-120](lab/static/js/src/components/music/score_timeline.js#L114-L120)
   - **Fix:** Don't sort timeline after building - insertion order must match renderer

### Issue 2: Window Not Advancing

**Symptom:** Played all notes in window but stuck on same window

**Root cause:** Held notes not being recognized

**Debug steps:**
1. Check console logs in `_advanceIfWindowComplete`
2. Look for: `Window check: played X/Y notes (Z new + W held)`
3. If W=0 but should be > 0: held notes algorithm failed

**Common causes:**
- Voice structure incorrect in CIR JSON
- Staff/voiceIndex tracking broken
- Note duration calculation wrong

**Fix:**
- Verify CIR score structure
- Check `durToTicks()` calculation in [score_timeline.js:6-12](lab/static/js/src/components/music/score_timeline.js#L6-L12)
- Trace backwards in timeline for held notes

### Issue 3: False Negatives (Wrong Note Detection)

**Symptom:** Playing correct note but marked INCORRECT

**Causes:**

1. **Off-by-one in MIDI calculation**
   - Check [score_timeline.js:28-33](lab/static/js/src/components/music/score_timeline.js#L28-L33)
   - MIDI formula: `(octave + 1) * 12 + semitone`
   - C4 should be 60

2. **Octave wrapping**
   - High treble notes might wrap to wrong octave
   - **Check:** Log expected vs actual: `[2. GRADE] Matched note X in current window`

3. **Chord ordering**
   - If playing chord notes in different order than rendered
   - Grader matches by MIDI pitch, not order, so should work
   - **Check:** Look for duplicate MIDI notes in window

### Issue 4: Instant Pass (Too Easy Grading)

**Symptom:** Exercise completes immediately without playing

**Cause:** Empty timeline or window groups

**Check:**
- Console: `[INIT] Built timeline with 0 events...` → No notes generated
- Reasons:
  - CIR score structure malformed
  - `startMeasure` >= `endMeasure` in options
  - All voices filtered out

**Fix:**
- Verify CIR JSON score format
- Check exercise definition measure range
- Check `selectVoices` option in timeline builder

### Issue 5: Wrong Window Content

**Symptom:** Expected notes don't match actual score

**Check:**
1. Console log first windows: `First 5 windows: ...`
2. Manually verify against rendered score
3. Check measure-by-measure event counts

**Common causes:**
- CIR JSON corrupted or truncated
- Incorrect measure range in import
- Voice selection filtering wrong notes

---

## Debug Logging

The chorale grader has comprehensive console logging with prefixes:

```javascript
[INIT]        // Initialization and timeline building
[1. PLAY]     // MIDI input events (noteOn/noteOff)
[2. GRADE]    // Grading logic and window checks
[3. VISUAL]   // UI state changes
```

**Enable debugging:**
1. Open DevTools (F12)
2. Go to Console tab
3. Start/play exercise
4. Filter by `[INIT]` or `[2. GRADE]` etc.

**Key log lines to watch:**
```
[INIT] Built timeline with X events across Y onset windows
[INIT] First 5 windows: Window 0 (onset=0): 60, 52, 43, 33
[1. PLAY] NOTE ON: 60
[2. GRADE] Current window onset=0, new attacks: [60, 52, 43, 33], held notes: [], all expected: [60, 52, 43, 33]
[2. GRADE] ✓ Matched note 60 in current window (id=0)
[2. GRADE] Window check: played 1/4 notes (4 new + 0 held), complete=false
[2. GRADE] Window complete! Advancing from 0 to 1
[2. GRADE] Exercise complete!
```

---

## Testing Scenarios

### Test 1: Simple Chorale (4 measures)

```bash
python manage.py import_chorale data/corpus/bach/bwv1.6.json \
  --author=admin@example.com \
  --start=0 --end=4 --public
```

Expected behavior:
- 4 windows (one per beat/chord change)
- Clear timeline in console
- Notes advance automatically

### Test 2: Single Voice Play

For "play-soprano" mode:
- Exercise should only expect treble staff notes
- Bass voice held notes should NOT block advancement
- Check `selectVoices` filtering in timeline builder

### Test 3: With Held Notes

Look for measure 2+ with tied notes:
- Console should show: `held notes: [57]` etc.
- Window completion should include held notes in count

---

## Key Design Decisions

### Why Onset-Based Windows?

Instead of note-by-note:
- Groups simultaneous notes together
- Matches real musical performance (chords played together)
- Simplifies tie/overlap handling

### Why One-Shot `_lastIncorrect`?

Instead of persistent error state:
- Allows partial correction mid-phrase
- Prevents one mistake from failing entire exercise
- Only reports the most recent error

### Why No Auto-Satisfaction?

Instead of auto-completing repeated notes:
- Ensures deliberate practice
- Prevents "ghost playing" after completion
- Matches pedagogical intent

---

## Integration Points

### ExerciseContext ([exercise_context.js](lab/static/js/src/models/exercise_context.js))

Special handling for chorales:
```javascript
if (definition.isChorale()) {
  // Doesn't use chord bank advancement
  // Special completion check: flawless = CORRECT
}
```

### ExerciseSheet ([exercise_sheet.js](lab/static/js/src/components/music/exercise_sheet.js))

Initialization:
```javascript
if (definition.isChorale()) {
  grader.initFromDefinition(definition);
}
```

### VexFlow Adapter ([vexflow_adapter.js](lab/static/js/src/components/music/vexflow_adapter.js))

Rendering:
- Displays Roman numerals and figured bass
- Colors notes based on `playedNoteIds` Set
- Gray = unplayed, Black = correct, Red = incorrect

---

## Data Structure: CIR Score

Bach chorales are stored as "Canonical Internal Representation" JSON:

```json
{
  "meta": {
    "key": "G major",
    "time_signature": "4/4"
  },
  "measures": [
    {
      "staves": {
        "treble": {
          "voices": [
            {
              "items": [
                {
                  "kind": "note" | "chord" | "rest",
                  "pitch": { "step": "C", "alter": 0, "octave": 4 },
                  "duration": { "type": "q", "dots": 0 }
                }
              ]
            }
          ]
        },
        "bass": { "voices": [...] }
      }
    }
  ]
}
```

### Duration Types

- `w` = whole (4096 ticks)
- `h` = half (2048)
- `q` = quarter (1024)
- `8` = eighth (512)
- `16` = sixteenth (256)
- `32` = thirty-second (128)

Dots multiply: `base + base/2 + base/4 + ...`

---

## Recent Changes (Last 5 Commits)

1. **ef762a4** - Visual improvements chorales
2. **f0fae8c** - Figured bass applied
3. **71289c2** - RNs fixed
4. **0497cf2** - Improvements to chorale analysis
5. **b7a3a24** - Improvements to analysis and dashboard

---

## Next Steps for Troubleshooting

1. **Reproduce issue** with specific chorale and measure range
2. **Capture console logs** - screenshot or copy-paste full debug output
3. **Verify CIR JSON** structure using `validate_cir_structure()` helper (if exists)
4. **Check timeline** - does `buildTimeline()` produce expected events?
5. **Trace MIDI events** - do noteOn/noteOff arrive correctly?
6. **Verify rendering** - do event IDs match between grader and renderer?

---

## Resources

- Bach Chorale Data: `data/corpus/bach/` (JSON files like `bwv1.6.json`)
- Django Model: `apps/exercises/models.py` (Exercise model with JSON data field)
- Planning Doc: [docs/chorale_exercises_plan.md](docs/chorale_exercises_plan.md)
- Import Script: [apps/exercises/management/commands/import_chorale.py](apps/exercises/management/commands/import_chorale.py)

