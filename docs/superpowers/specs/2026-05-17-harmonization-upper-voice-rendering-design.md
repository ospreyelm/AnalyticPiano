# Harmonization Upper-Voice Rendering Design

**Status:** Draft
**Date:** 2026-05-17
**Branch:** `feature/harmonization-exercise`
**Related:** [2026-05-15-harmonization-exercise-design.md](./2026-05-15-harmonization-exercise-design.md)

## Problem

In the harmonization exercise type, the rendered score contains only the locked
bass voice. Upper voices (S, A, T) are filtered out at render time via
`selectVoices: { treble: [], bass: [1] }`. As a result, when a student plays a
correct chord above the bass, their upper-voice notes are accepted by the
grader (entries appended to `acceptedHarmonizationSonorities`) but **nothing
appears on the treble staff**. The student has no visual confirmation that
their realization was registered.

## Goals

1. Display accepted upper-voice student pitches on the treble staff, one
   chord per accepted target.
2. Use real VexFlow `StaveNote` objects so ledger lines, accidentals, and
   stems render automatically.
3. Spell each notehead using the source UMTO score's canonical spelling
   (Bach's spelling, not key-signature guesswork).
4. Update on each accepted target (existing `"graded"` event re-renders the
   sheet — no new wiring needed).
5. Strictly visual. Grader behavior unchanged. No new persistence.

## Non-Goals

- Recording or visualizing mistakes (notes that did not advance the pointer).
- Recording passing tones or ornamentation between accepted chords.
- Color-coding upper-voice errors.
- Locked-soprano variant of the exercise. (Spec assumes locked = `["B"]`.)
- Enharmonic spelling for pitch classes that are not in the source chord
  (key-sig fallback). Not needed because acceptance implies pc is in source.
- Persistent performance log. Captured in a separate future spec.

## Architecture

### Data flow

```
acceptedHarmonizationSonorities (ExerciseContext)
            ↓
HarmonizationRealizationLogic.buildRealization(accepted, targets, score, meter)
            ↓
harmonizationRealization payload (array of measure-scoped entries)
            ↓
VexFlowAdapter.render({ harmonizationRealization })
            ↓
Per measure: build a treble Voice of student StaveNotes + rests
            ↓
trebleVoices.push(overlayVoice) before Formatter.joinVoices
```

### Payload contract

`harmonizationRealization` is an array. Each entry is one accepted target's
chord, scoped to its containing measure:

```js
{
  measureIndex: 0,            // absolute index of containing measure
  onset: 0,                   // ticks within measure (matches existing bass note _onset)
  durationTicks: 1024,        // ticks until next target's onset (in same measure) or measure end
  midiNotes: [62, 67, 71],    // student-played MIDI, bass pc removed, sorted ascending
  spellings: ["D", "G", "B"]  // canonical step + alter from source UMTO, parallel to midiNotes
}
```

`spellings[i]` is the source UMTO spelling for `midiNotes[i]`, looked up by
pitch class against the source score's upper voices at that target's offset.
Because acceptance requires every played pc to be in `target.allowedPcs` (which
derives from the source slice), every accepted midi note has a pc match in the
source — no key-signature fallback path is needed for this spec.

### Source-spelling lookup (pc-match)

`HarmonizationRealizationLogic.buildPcSpellingMap(score, measureIndex, onset)`
walks `score.measures[measureIndex].staves.{treble,bass}.voices[*].items` and
collects all non-rest pitches sounding at that beat (including held notes
from earlier in the measure that overlap this onset). Returns
`{ pc: {step, alter} }`. The realization builder uses this map to spell each
student midi:

```js
function spellMidi(midi, pcMap) {
  var pc = ((midi % 12) + 12) % 12;
  var entry = pcMap[pc];
  if (!entry) return null; // should never happen for accepted notes
  var octave = Math.floor(midi / 12) - 1;
  // Adjust octave if alter pushes step across boundary (e.g. cb5 vs b4)
  return { step: entry.step, alter: entry.alter, octave: octave };
}
```

Octave-boundary correction: when `step="C"` and `alter=-1` and student midi is
59, the spelling is `Cb/5` not `Cb/4`. Use a small lookup of (step, alter) →
semitone-from-C and reconcile.

### Adapter changes (`vexflow_adapter.js`)

**New render option:** `harmonizationRealization` (default `null`).

Inside the per-measure render loop, after `staffVoices('treble', ...)`
returns its (empty-for-harmonization) array, build the overlay voice:

1. Filter `harmonizationRealization` to entries whose `measureIndex` matches
   current measure.
2. Sort by `onset`.
3. Walk ticks from 0 to `measureTotalTicks`. For each gap before/between
   entries, emit a rest. At each entry's onset, emit a `StaveNote`:

   ```js
   var keys = entry.midiNotes.map(function (m, i) {
     var sp = entry.spellings[i];
     var acc = sp.alter === 1 ? "#" : sp.alter === -1 ? "b" : "";
     return sp.step.toLowerCase() + acc + "/" + sp.octave;
   });
   var note = new Vex.Flow.StaveNote({
     clef: "treble",
     keys: keys,
     duration: ticksToDuration(entry.durationTicks),
     auto_stem: false,
   });
   note.setStemDirection(1); // stems up
   note.setStyle({ fillStyle: "#000000", strokeStyle: "#000000" });
   // Accidentals: add for any spelling.alter !== keySigAlter[step]
   ```

4. Wrap tickables in a `Vex.Flow.Voice` with the same time signature as the
   measure's bass voice. Voice tick total **must equal** measure tick total —
   validate in dev mode, throw if mismatched.
5. Push the overlay voice onto `trebleVoices` before
   `Formatter.joinVoices`. Formatter aligns columns automatically.

**Rest handling:** Use existing rest construction at line 744 as template; do
not draw rest glyphs (set `fillStyle: "transparent"` so the rest is invisible
but the Voice tick math is satisfied).

**Skip path:** If `harmonizationRealization` is empty or undefined, do
nothing — treble stays as today.

**Duration mapping (`ticksToDuration`):** Existing `durToVF` works from CIR
`{type, dots}`. Need an inverse: `ticksToDuration(ticks)` → `{type, dots}`.
Cover `w/h/q/8/16` plus dotted half / dotted quarter / dotted eighth. Anything
else: pick nearest representable duration and log a warning.

### Realization builder (`harmonization_realization_logic.js`)

Pure, testable module. Signature:

```js
function buildRealization(accepted, targets, score, meter) {
  // accepted: ExerciseContext.acceptedHarmonizationSonorities
  // targets: HarmonizationTargets array (each has offset in quarter-beats, lockedVoices)
  // score: CIR score object
  // meter: { numerator, denominator } from score.meta
  // returns: harmonizationRealization[]
}
```

Steps:

1. **Dedupe `accepted` by `targetIndex`** — keep most recent entry per index.
2. For each kept entry:
   a. Look up `target = targets[targetIndex]`.
   b. Compute (measureIndex, onsetTicks) from `target.offset` (quarter-beats)
      using the meter.
   c. Strip bass pc: `bassPc = target.lockedVoices.B.pc`;
      `upperMidi = entry.midi.filter(m => m % 12 !== bassPc)`.
   d. Skip if `upperMidi.length === 0`.
   e. Build pc-spelling map from source score at (measureIndex, onsetTicks).
   f. Spell each `upperMidi[i]`.
3. Compute `durationTicks` per entry: ticks to next target's onset (same
   measure) or measure end, whichever is first.
4. Sort output by `measureIndex` then `onsetTicks`.

### Sheet wiring (`exercise_sheet.js`)

Around line 1693 (existing harmonization render block):

```js
if (isHarmonization && this.exerciseContext) {
  // ... existing acceptedPtr / acceptedOffsetTicks / playedNoteIdsForRender code ...

  var accepted = this.exerciseContext.acceptedHarmonizationSonorities || [];
  var tsParts = (score.meta && score.meta.time_signature || "4/4").split("/");
  var meter = { numerator: parseInt(tsParts[0], 10), denominator: parseInt(tsParts[1], 10) };
  harmonizationRealizationPayload = HarmonizationRealizationLogic.buildRealization(
    accepted, harmTargets, score, meter
  );
}
```

Then pass `harmonizationRealization: harmonizationRealizationPayload` into the
`VexFlowAdapter.render` call.

`exerciseContext.bind("graded", this.render)` already triggers re-render on
every accepted target. No new event wiring.

## Edge cases

| Case | Handling |
|------|---------|
| Bass pc duplicated in student's chord (octave-bass) | Filtered out by `m % 12 !== bassPc`. Bass note already shown on bass stave. |
| Multi-measure span between accepted targets | Each entry capped at end of its own measure. No cross-measure StaveNote. |
| Last accepted target before end of phrase | `durationTicks` = ticks to end of containing measure. |
| Duplicate accepted entries (same targetIndex) | Builder dedupes by targetIndex, keeping most recent. |
| Empty `acceptedHarmonizationSonorities` | Builder returns `[]`. Adapter skips overlay path. Treble blank. |
| Voice tick mismatch (rests + notes ≠ measure total) | Dev-mode `console.error`. Skip overlay for that measure rather than crash. |
| Target offset that doesn't land on a clean tick boundary | Use `Math.round(offsetQb * 1024)` consistent with existing harmonization code. |
| Source UMTO has no upper-voice note at the target offset | Should not occur for accepted targets (acceptance implies match). If it does, log warning + fall back to key-sig spelling (defensive only). |

## Testing strategy

**Unit (`harmonization_realization_logic.test.js`):**

- `buildRealization` with one accepted target → one entry with correct
  measureIndex, onset, durationTicks, midiNotes, spellings.
- Bass pc dedupe: student plays `[36, 60, 64, 67]` with bass pc=0 →
  `midiNotes` = `[64, 67]`.
- Duplicate `targetIndex` entries → keeps most recent.
- Multi-measure: two accepted targets in different measures → two entries
  with correct `measureIndex` values.
- Source-spelling lookup: target landing on a chord with F♯ in source →
  midi 66 spelled `{step: "F", alter: 1}`.

**Adapter integration:**

- Pass synthetic `harmonizationRealization` to `VexFlowAdapter.render` →
  verify treble Voice ticks total equals measure ticks; verify the right
  count of non-rest StaveNotes on the treble stave.

**Manual:**

- Open a Riemenschneider 1 harmonization exercise (locked bass).
- Play bass + correct S/A/T notes for first chord. Verify treble noteheads
  appear at correct staff position with correct accidentals after acceptance.
- Continue through phrase. Each accepted target adds its chord at the
  correct beat.
- Verify regression: bass coloring still works; figures still render.

## Files touched

- `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
  — new opt + overlay voice construction + `ticksToDuration` helper
- `lab/static/js/src/components/music/exercise_sheet.js`
  — build payload from `acceptedHarmonizationSonorities`, pass to adapter
- `lab/static/js/src/models/harmonization_realization_logic.js` *(new)*
  — pure builder with `buildRealization` + `buildPcSpellingMap`
- `lab/static/js/src/models/harmonization_realization_logic.test.js` *(new)*

No backend / Python changes. No model changes. No migrations.

## Open questions deferred to future specs

- **Performance log:** Capture every noteOn/noteOff with timestamps,
  independent of grading. Enables retrospective analysis (attempts per
  target, hesitation, parallels in actual performance order, leading-tone
  resolution). Separate spec.
- **Color-coded overlay:** Distinguish each voice (S/A/T) by color, or
  highlight harmonic role (3rd, 5th, 7th). Future.
- **Locked-soprano variant:** Same overlay pattern, drawing student's
  bass/alto/tenor below. Out of scope until that exercise mode ships.
