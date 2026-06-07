# Spike 5a: Chordal Window/Slot Source — Decision

Date: 2026-06-07
Investigated by reading the live frontend window path (not prototyped in browser).

## Evidence

`lab/static/js/src/components/music/score_timeline.js` — `buildTimeline(score)`:
- Walks `score.measures[].staves.{treble,bass}.voices[].items[]`.
- **Already handles `item.kind === "chord"`**: iterates `item.notes[h].pitch` and emits one
  timeline event per chord head, all sharing the same `onset`. Note shape is
  `{kind:"chord", notes:[{pitch:{step,alter,octave}}, ...], duration:{type,dots}}`.
- Single-note shape: `{kind:"note", pitch:{step,alter,octave}, duration:{type,dots}}`.
- Rests: `{kind:"rest", duration:{...}}` advance onset, emit nothing.
- MIDI is recomputed from `pitch.step/alter/octave` via `pitchToMidi` (C4=60 = `(octave+1)*12 + semitone + alter`). **So chord items must carry correct spelled pitch, not raw MIDI.**
- Ticks: `w=4096, h=2048, q=1024, 8=512, 16=256, 32=128`.

`lab/static/js/src/models/exercise_definition.js`:
- `buildAnalysisWindows(timeline)` (line 314): groups timeline events by `onset` → one
  window per distinct onset (a verticality). Exactly the chordal model.
- `buildUMTOIdentificationProblems` (line 439): for each `umto.analysis` slice, matches
  `slice.offset` to a window via `findAnalysisWindowByOffset(windows, sliceOffset)`;
  `hasSlot:true` when matched, else the slot is hidden (line 487/572).

## W1 — generate `score.measures` from `chords[]` (backend)
- **Feasible: YES, strongly favored.**
- Code touched: backend only (`umto_factory.build_chordal_umto_payload` +
  `_chordal_to_measures` helper). **Zero frontend timeline changes** — buildTimeline already
  reads `kind:"chord"`.
- Risk: (a) emit the exact chord-item shape `notes:[{pitch:{step,alter,octave}}]` (NOT a
  `pitches:[...]` key — the plan draft was wrong); (b) MIDI→spelling must produce correct
  octave so `pitchToMidi` round-trips the intended MIDI; (c) `analysis[].offset`
  (quarter-lengths) must line up with the window onsets `findAnalysisWindowByOffset`
  expects — this is the SAME mechanism voices-kind UMTO already uses, so it inherits a
  working path.

## W2 — teach `buildTimeline` to read `umto.chords` (frontend)
- Feasible: yes, but redundant. Would duplicate the chord-handling that buildTimeline
  already has, and touch the working timeline path (the file carries an explicit warning
  about not reordering/altering timeline because event.id must match renderer noteheads).
- Code touched: `score_timeline.js` + possibly `buildAnalysisWindows`. Higher regression risk.

## DECISION: **W1**

## Rationale
`buildTimeline` already converts `kind:"chord"` measures into per-onset verticalities and
windows. Generating CIR measures from `chords[]` on the backend reuses the entire existing
timeline → window → slot → render → grade pipeline with no frontend changes and no risk to
the id-ordering invariant. W2 would re-implement existing logic against the working path.

## Consequences for later tasks
- **Task 9 (chords→measures):** emit chord items as
  `{kind:"chord", notes:[{pitch:{step,alter,octave}}...], duration:{type,dots}}` for
  cardinality ≥2, and `{kind:"note", pitch:{...}, duration:{...}}` for a single pitch.
  Use the `w/h/q/8/16/32` duration-type map. **Correct the plan's `pitches` key to the
  real `notes:[{pitch}]` shape.** `_midi_to_cir_pitch` must yield octave by `midi//12 - 1`.
- **Task 7 (frontend chordal case):** unchanged — still populates `exercise.problems` from
  `chords[]` for playback; identification slots now come for free from the W1 measures via
  the existing `buildUMTOIdentificationProblems` path. No new frontend window code.
- **Offset-unit alignment** (analysis offset ↔ window onset) is the one thing Task 9's
  identification-slot test (spec test 5) must prove end to end.
