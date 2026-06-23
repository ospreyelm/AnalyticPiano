# Split vexflow_adapter.js and exercise_sheet.js by responsibility

## Context

`vexflow_adapter.js` (1771 lines) and `exercise_sheet.js` (2907 lines) are both
far over AGENTS.md's 400-line file guardrail. A prior commit (`38dfc469`)
already proved the extraction pattern works: it pulled ~800 lines of pure
helpers into `vexflow_adapter_logic.js`, `barline_spacing_utils.js`, and
`umto_score_converter.js` — clean, focused, and (in the logic file's case)
covered by a plain-Node `assert` test (`vexflow_adapter_logic.test.js`).

Two recurring bugs (`chordal notehead coloring blackens whole chord on
partial play`, `barline_offsets for MusicXML chordal imports`) trace back to
logic buried inside oversized, multi-concern functions/objects — hard for a
human or an agent to safely scope an edit within without reading thousands
of unrelated lines first.

Important finding from `docs/UMTO_GUIDE.md`: `vexflow_adapter.js` does not
render chordal/voices UMTO directly — `umto_score_converter.js` already
normalizes both into one legacy "CIR" shape before `render()` ever sees it.
Native UMTO rendering (retiring that bridge) is an explicitly separate,
not-yet-authorized future phase. **This plan is scope-limited to the
mechanical split — zero behavior change** — which is the safe prerequisite
for that future migration, not the migration itself.

## Findings

**`vexflow_adapter.js`**: almost entirely one function, `render()`
(lines 691–1771, ~1080 lines). Everything above it (lines 22–654:
`drawInlineRoman`/`drawInlineRomanExp`/`drawInlineRomanExpRun`,
`drawScaleDegreeAbove`, `drawBassScaleDegreeBelow`,
`attachInlineRomanAnnotation`, `attachNoteNameAnnotation`, `itemToTickable`,
`buildVoice`, `buildHarmonizationOverlayVoice`) is already individually
named and mostly self-contained — these are the natural extraction
candidates. `render()` itself has no internal chordal/voices branching (the
converter already normalized that away); it's one long procedural pipeline
mixing tickable assembly, annotation attachment, and stave/measure layout.

**`exercise_sheet.js`**: a single `_.extend(ExerciseSheetComponent.prototype,
{...})` block with 84 methods. Four natural, non-overlapping boundaries:
- **Identification/quiz input** (`_isIdentificationLikeExercise` through
  `onToggleMode`, lines ~201–1388, ~1187 lines)
- **Stave construction/update** (`renderStaves`, `updateStaves`,
  `createDisplayStave`, `createNoteStave`, `createStaveNotater`,
  `addStaves`, `resetStaves`, lines ~1824–2573, ~750 lines)
- **Playback / MIDI grading + ghost note** (`onChordsUpdate`,
  `_calculatePlaybackOffsets`, `onMidiNote`, `autoScroll`, `onGoToExercise`,
  `onClickPristine`, `_drawPlaybackHighlight`, `_clearPlaybackHighlight`,
  `_ghostCanvas`, `drawGhostNote`, `clearGhostNote`, `_drawGhostGlyph`)
- **Status/info/history rendering** (`renderExerciseStatus`,
  `renderExerciseInfo`, `renderExerciseText`, `renderExerciseHistory`,
  `_buildHarmonizationPending`, `_buildHarmonizationRejected`)

Init/lifecycle (constructor, `initComponent`, `initRenderer`, `initStaves`,
`initListeners`, `initChoraleMode`, `clear`, `render`) stays in
`exercise_sheet.js` as the orchestrator.

Chordal-specific logic is **already** cleanly separated (`chordal_spelling.js`,
`chordal_umto_staff_distribution.js`, `chordal_barlines_logic.js`,
`chordal_problems_logic.js` — 45–190 lines each, dispatched from
`umto_score_converter.js` by `score_kind`). This existing pattern is the
model to replicate, not something to redo.

## Approach

Split by responsibility, continuing the existing pure-function-module +
thin-orchestrator pattern. No new architecture, no new abstractions — just
finish what `38dfc469` started.

**1. `vexflow_adapter.js` first** (smaller, more isolated — `exercise_sheet.js`
only calls it as a black box via `render(score, renderer, opts)`, so this
order avoids touching exercise_sheet.js's much larger surface twice):

- New `vexflow_annotation_renderer.js`: `drawInlineRoman`,
  `drawInlineRomanExp`, `drawInlineRomanExpRun`, `_drawScaleDegreeList`,
  `drawScaleDegreeAbove`, `drawBassScaleDegreeBelow`,
  `attachInlineRomanAnnotation`, `attachNoteNameAnnotation`.
- Move `itemToTickable`, `buildVoice`, `buildHarmonizationOverlayVoice` into
  `vexflow_adapter_logic.js` (same module, same pattern — these are pure
  enough to fit alongside `resolveChordNoteStyles` and friends already
  there).
- Break `render()`'s body into named stages (e.g. stave/clef setup, tickable
  assembly per measure, annotation pass, beam/format pass) inside a new
  `vexflow_render_pipeline.js`, called in sequence by a thin `render()` left
  in `vexflow_adapter.js`. Exact stage boundaries to be drawn by reading the
  full function during implementation — the line-range scan above is enough
  to know the file needs this, not yet enough to name every cut point.
- Add a `.test.js` next to each newly-pure module, following
  `vexflow_adapter_logic.test.js`'s pattern exactly (plain Node `assert`,
  runnable via `node <path>.test.js`, no framework/package.json needed).

**2. `exercise_sheet.js` second**, split into four new files matching the
boundaries above:
- `exercise_sheet_identification.js`
- `exercise_sheet_staves.js`
- `exercise_sheet_playback.js`
- `exercise_sheet_status.js`

Each exports an object of methods; `exercise_sheet.js` keeps using
`_.extend(ExerciseSheetComponent.prototype, {...})` but spreads in the four
new objects alongside the lifecycle methods that stay local — this is
additive to the existing prototype/mixin pattern, not a rewrite of the
inheritance model.

## Verification

- Run every existing `.test.js` (27 found, plain Node, no test runner
  config) plus the new ones added in step 1 — each is independently
  runnable: `node path/to/file.test.js`.
- No automated visual-regression coverage exists for these two files, so the
  real regression surface is manual: load one chordal exercise (figured
  bass) and one voices exercise (polyphonic) in the browser via the `run`
  skill, confirm rendering, partial-play notehead coloring, and the
  identification UI are pixel-for-pixel/behaviorally identical to before the
  split. Any difference is a bug introduced by the refactor, not an
  intentional change — this plan is explicitly zero-behavior-change.
- Use an isolated worktree per CLAUDE.md/AGENTS.md repository-hygiene
  convention, since this is multi-file feature-shaped work.
