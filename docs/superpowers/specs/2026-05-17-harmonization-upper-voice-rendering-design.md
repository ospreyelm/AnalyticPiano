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
  measureIndex: 0,                  // absolute index of containing measure
  onset: 0,                         // ticks within measure (matches existing bass note _onset)
  durationTicks: 1024,              // ticks until next target's onset (in same measure) or measure end
  midiNotes: [62, 67, 71],          // student-played MIDI, locked-bass note removed, sorted ascending
  spellings: [                      // canonical step+alter+octave from source UMTO, parallel to midiNotes
    { step: "D", alter: 0, octave: 4 },
    { step: "G", alter: 0, octave: 4 },
    { step: "B", alter: 0, octave: 4 }
  ]
}
```

`spellings[i]` is the source UMTO spelling for `midiNotes[i]`, computed by
`spellMidi` (see below) from a pc-keyed lookup against the source score's
non-rest pitches at the target's offset. Because acceptance requires every
played pc to be in `target.allowedPcs` (which derives from the source slice),
every accepted midi note has a pc match in the source — no key-signature
fallback is needed for this spec.

### Source-spelling lookup (pc-match)

`HarmonizationRealizationLogic.buildPcSpellingMap(score, targetOffsetQb)`
walks **all** voices in the score with absolute (cross-measure) offsets and
collects every non-rest pitch sounding at `targetOffsetQb`. It must consider:

1. Notes whose sounding window contains the target offset, even when the
   note started in a previous measure (tied/held over the barline).
2. Notes that begin exactly at the target offset (the new attacks).

Implementation: reuse `ScoreTimeline.buildTimeline(score)`, which emits a
flat event list with `{ onset, duration, midi, staff, voiceIndex, ... }`
where **both `onset` and `duration` are in ticks at 1024 ticks per quarter**
(see `score_timeline.js`). The target's `offset` field is in quarter-beats,
so the realization builder must convert:

```js
var targetTick = Math.round(targetOffsetQb * 1024);
var sounding = timeline.filter(function (ev) {
  return ev.onset <= targetTick && ev.onset + ev.duration > targetTick;
});
```

Build the pcMap from `sounding` by reading each event's source CIR pitch
(`{step, alter, octave}`). The timeline already carries `staff`,
`voiceIndex`, `measureIndex`, `itemIndex`, `headIndex` — use those to index
back into `score.measures[m].staves[staff].voices[v].items[itemIndex]` (and
`.notes[headIndex]` for chord items) to get the original pitch spelling.
Returns `{ pc: {step, alter} }`. The realization builder uses this map to
spell each student midi:

```js
function spellMidi(midi, pcMap) {
  var pc = ((midi % 12) + 12) % 12;
  var entry = pcMap[pc];
  if (!entry) return null; // should never happen for accepted notes
  // Octave label follows the natural letter, not the sounding pitch.
  // Subtract alter to land on the letter's natural MIDI, then take
  // its standard octave label. Handles B#/Cb (and double accidentals)
  // across octave boundaries.
  var letterBaseMidi = midi - entry.alter;
  var octave = Math.floor(letterBaseMidi / 12) - 1;
  return { step: entry.step, alter: entry.alter, octave: octave };
}
```

Verified for boundary cases:
- MIDI 71, spelled `Cb` (step=C, alter=-1): `letterBase = 72`, octave = 5 → `Cb5` ✓
- MIDI 72, spelled `B#` (step=B, alter=+1): `letterBase = 71`, octave = 4 → `B#4` ✓
- MIDI 70, spelled `Cbb` (alter=-2): octave 5 ✓
- MIDI 73, spelled `B##` (alter=+2): octave 4 ✓

**Tonal.js note:** The codebase already loads `tonal` (used in
`exercise_definition.js` for interval naming). For spelling, tonal exposes
`Note.fromMidi` / `Note.fromMidiSharps`, but both guess the spelling — they
have no API for "spell with this specific step+alter and give me the octave."
Since we already have the canonical step+alter from the source UMTO, the
2-line `letterBaseMidi` formula above is more direct than wrapping tonal.

### Adapter changes (`vexflow_adapter.js`)

**New render option:** `harmonizationRealization` (default `null`).

Inside the per-measure render loop, after `staffVoices('treble', ...)`
returns its (empty-for-harmonization) array, build the overlay voice:

1. Filter `harmonizationRealization` to entries whose `measureIndex` matches
   current measure.
2. Sort by `onset`.
3. Walk ticks from 0 to `measureTotalTicks`. For each gap before/between
   entries, emit one or more transparent rests via `ticksToDurationChunks(gap)`.
   At each entry's onset, split the entry's `durationTicks` into chunks via
   `ticksToDurationChunks(entry.durationTicks)`. The **first chunk** becomes
   the chord StaveNote; every subsequent chunk becomes a transparent rest at
   the same chunk duration so the Voice tick math stays exact.

   ```js
   var keys = entry.midiNotes.map(function (m, i) {
     var sp = entry.spellings[i];
     var acc = sp.alter === 1 ? "#"
             : sp.alter === -1 ? "b"
             : sp.alter === 2 ? "##"
             : sp.alter === -2 ? "bb"
             : "";
     return sp.step.toLowerCase() + acc + "/" + sp.octave;
   });
   var chunks = ticksToDurationChunks(entry.durationTicks);
   if (!chunks || !chunks.length) return; // unsplittable — skip this measure
   var headChunk = chunks[0];
   var note = new Vex.Flow.StaveNote({
     clef: "treble",
     keys: keys,
     duration: durToVF(headChunk),     // {type, dots} → VF duration string
     dots: headChunk.dots,
     auto_stem: false,
   });
   note.setStemDirection(1); // stems up
   note.setStyle({ fillStyle: "#000000", strokeStyle: "#000000" });
   // Accidentals: add for any spelling.alter !== keySigAlter[step]
   tickables.push(note);
   // Remaining chunks as transparent rests to fill durationTicks exactly
   for (var ci = 1; ci < chunks.length; ci++) {
     tickables.push(makeTransparentRest(chunks[ci]));
   }
   ```

4. Wrap tickables in a `Vex.Flow.Voice` with the same time signature as the
   measure's bass voice. Voice tick total **must equal** measure tick total —
   validate in dev mode, log warn and skip overlay for that measure if not.
5. Push the overlay voice onto `trebleVoices` before
   `Formatter.joinVoices`. Formatter aligns columns automatically.

**Rest handling:** Use existing rest construction at line 744 as template; do
not draw rest glyphs (set `fillStyle: "transparent"` so the rest is invisible
but the Voice tick math is satisfied).

**Skip path:** If `harmonizationRealization` is empty or undefined, do
nothing — treble stays as today.

**Duration mapping (`ticksToDuration`):** Existing `durToVF` works from CIR
`{type, dots}`. Need an inverse: `ticksToDurationChunks(ticks)` → ordered list
of `{type, dots, ticks}` chunks summing to `ticks` exactly. Use a greedy
descent through the supported duration set:

- Supported atoms: `w (4096), h. (3072), h (2048), q. (1536), q (1024), 8. (768), 8 (512), 16. (384), 16 (256), 32 (128)`.
- Greedy: subtract the largest atom ≤ remaining ticks; repeat until 0.

For a notehead with `durationTicks = D`:
- Emit the first chunk as a `StaveNote` with that duration.
- Emit remaining chunks **as transparent rests** (not tied notes) — visually
  the chord shows only as the first head; the rests carry the rest of the
  tick total so the Voice still sums to `measureTotalTicks`.

This avoids the original "nearest duration + drift" problem: the head is
drawn at the correct duration that the greedy step picks; any leftover ticks
become invisible rests rather than warping subsequent column alignment.

If the greedy descent cannot zero out `ticks` (only possible for non-power-of-2
remainders smaller than 128), log `console.warn` and skip this measure's
overlay rather than emitting a mismatched Voice.

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
   c. Remove the **locked-bass note instance** (not all pc matches): take
      `bassMidi = target.lockedVoices.B.midi` and drop one occurrence of
      exactly that MIDI from `entry.midi`. If the student doubles the bass pc
      in an upper octave (e.g. bass C2 + soprano C4), the C4 is kept and
      drawn. Drop-one logic:
      ```js
      var bassMidi = target.lockedVoices.B.midi;
      var dropped = false;
      var upperMidi = entry.midi.filter(function (m) {
        if (!dropped && m === bassMidi) { dropped = true; return false; }
        return true;
      });
      ```
      If `target.lockedVoices.B.midi` is absent, fall back to dropping one
      occurrence of any MIDI whose pc matches `target.lockedVoices.B.pc`
      (preserves prior behavior; should not happen with current target
      builder).
   d. Skip if `upperMidi.length === 0`.
   e. Build pc-spelling map from source score at the target's **absolute**
      quarter-beat offset (`target.offset`), via
      `buildPcSpellingMap(score, target.offset)`. The lookup must include
      notes held over from prior measures (ties / suspensions extending
      across barlines).
   f. Spell each `upperMidi[i]` via `spellMidi(midi, pcMap)`.
3. Compute `durationTicks` per entry: ticks to next target's onset (same
   measure) or measure end, whichever is first.
4. Sort output by `measureIndex` then `onsetTicks`.

### Sheet wiring (`exercise_sheet.js`)

Around line 1693 (existing harmonization render block):

```js
if (isHarmonization && this.exerciseContext) {
  // ... existing acceptedPtr / acceptedOffsetTicks / playedNoteIdsForRender code ...

  var accepted = this.exerciseContext.acceptedHarmonizationSonorities || [];
  // CIR stores meter as score.meta.time ("4/4"); legacy paths may have
  // score.meta.meter or score.meta.time_signature. Read all three.
  var tsRaw = (score.meta && (score.meta.time || score.meta.meter || score.meta.time_signature)) || "4/4";
  var tsParts = String(tsRaw).split("/");
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
| Locked-bass MIDI present in student's chord | Drop **one** occurrence of exactly that MIDI; keep upper-octave doublings of the same pc (e.g. bass C2 + soprano C4 → C4 still drawn). |
| Multi-measure span between accepted targets | Each entry capped at end of its own measure. No cross-measure StaveNote. |
| Last accepted target before end of phrase | `durationTicks` = ticks to end of containing measure. |
| Duplicate accepted entries (same targetIndex) | Builder dedupes by targetIndex, keeping most recent. |
| Empty `acceptedHarmonizationSonorities` | Builder returns `[]`. Adapter skips overlay path. Treble blank. |
| `durationTicks` not representable as a single VexFlow duration | Split into a head + transparent-rest chunks via `ticksToDurationChunks` (greedy). Sum of chunk ticks equals `durationTicks` exactly. |
| Voice tick total still ≠ measure total after chunking | Greedy descent failed (remainder <128 not a power of 2 atom). `console.warn` and skip overlay for that measure. |
| Target offset that doesn't land on a clean tick boundary | Use `Math.round(offsetQb * 1024)` consistent with existing harmonization code. |
| Source UMTO has no upper-voice note at the target offset | Should not occur for accepted targets (acceptance implies match). If it does, log warning + fall back to key-sig spelling (defensive only). |

## Testing strategy

**Unit (`harmonization_realization_logic.test.js`):**

- `buildRealization` with one accepted target → one entry with correct
  measureIndex, onset, durationTicks, midiNotes, spellings.
- Locked-bass instance dedupe: student plays `[36, 60, 64, 67]` with
  `target.lockedVoices.B.midi = 36` → `midiNotes` = `[60, 64, 67]` (C4
  doubling of bass pc is preserved; only the bass MIDI 36 is dropped).
- Locked-bass octave double: student plays `[36, 48, 60, 64]` with bass
  MIDI 36 → `midiNotes` = `[48, 60, 64]` (both 48 and 60 are pc=0 but
  neither equals 36; only the bass instance is dropped).
- Bass MIDI absent fallback: `target.lockedVoices.B.midi` undefined,
  `target.lockedVoices.B.pc = 0`, student plays `[60, 64, 67]` → drop one
  pc=0 instance → `midiNotes` = `[64, 67]`.
- Duplicate `targetIndex` entries → keeps most recent.
- Multi-measure: two accepted targets in different measures → two entries
  with correct `measureIndex` values.
- Source-spelling lookup: target landing on a chord with F♯ in source →
  midi 66 spelled `{step: "F", alter: 1}`.
- Tied-over barline: source soprano holds D5 (alter=0) from m1 beat 4 into
  m2 beat 1. Target at m2 beat 1 with student MIDI 74 → spelled
  `{step: "D", alter: 0, octave: 5}` (lookup must see the held D, not just
  notes that attack at m2 beat 1).

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
