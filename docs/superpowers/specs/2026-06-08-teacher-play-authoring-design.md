# Teacher Play View — Click-First Authoring + Review (Thread 1 Design Spec)

Date: 2026-06-08
Status: Design — pending author review.

Follows the concept `2026-06-08-teacher-play-authoring-concept.md` (PR #92) and the
umbrella brief `2026-06-08-teacher-experience-design-brief.md`. This spec resolves the
five decisions the concept left open and defines the post-save seam to Threads 2/3.
It is a design spec, not a task list. Implementation planning is a separate pass.

## Goal

Make `/teacher/play/` a single surface where a teacher authors a chord progression,
reviews/corrects its analysis in place against live notation, and approves it with one
Save. Collapse PR #90's separate "needs review" round-trip: in Play, **Save is the
approval**. Keep the zero-friction live blackboard intact as the default.

Scope is Thread 1 only. The any-teacher dashboard (Thread 2) and curriculum curation
(Thread 3) are out of scope except for the post-save **target selector**, which this
spec defines as the seam where Thread 1 hands off.

## Core philosophy

"If you see it on the screen, you can click it to change it." WYSIWYG, on-canvas,
context-sensitive clicks. The Play view is simultaneously the live classroom blackboard
and the structured content creator. Authoring affordances stay quiet until invoked, so
live teaching is unaffected. A selection-scoped keyboard layer accelerates power users
without colliding with note entry.

---

## Decision (a) — Variable duration: duration-aware slots, equal-duration default

### Reframe

Durations and barlines are **not new**. The canonical model already carries them:
`ChordEvent` has `offset` + `duration` + `duration_type` + `dots`; `metadata.meter` is
required; `umto._to_legacy_measures()` already splits events into measures by meter,
emits barlines, and honors `duration_type`/dots across multiple measures. The only thing
Play does wrong is `dataForSave()` discarding rhythm (`rhythmValue: "w"`), after which
`save_chordal_umto_exercise` re-stamps `duration: 1.0`.

So the v1 question is narrow: make the authoring slot model duration-aware and let the
teacher set note values, while keeping the blackboard frictionless.

### What ships

- Each banked chord is a slot carrying `duration` / `duration_type` / `dots`. The score
  carries `meter` (default `4/4`, set once at the top of the canvas).
- `dataForSave()` stops flattening: it serializes each chord's chosen duration.
- `save_chordal_umto_exercise` accepts per-chord durations and a meter instead of
  hardcoding `1.0`.
- Barlines and multi-measure layout render for free via the existing measure derivation.

### The hard part is reflow, not rendering

Rendering a quarter note is trivial. The danger is that offsets are a cumulative sum of
durations, so shortening one chord slides every later chord earlier; a later chord then
lands mid-bar and spills across a barline, requiring a tied split
(dotted-half + quarter in the next bar) — exactly what `_to_legacy_measures` explicitly
refuses to do (`"We don't handle ties/splitting across measures here yet"`).

### Duration constraint model

**Invariant (non-negotiable in v1): no event crosses a barline.** This single rule
eliminates all ties.

Three coupled constraints uphold it:

1. **Fixed meter + fixed palette.** Meter is set once. Durations are restricted to a
   standard palette — whole, dotted-half, half, dotted-quarter, quarter, eighth,
   dotted-eighth, sixteenth. No tuplets.
2. **Position-aware picker.** A chord at bar-local position `p` (= `offset mod barLen`)
   may only take durations `d` where `p + d ≤ barLen`. The duration palette greys out
   any value that would overflow the current bar, so the edited chord can never straddle.
3. **Non-reflow local edits.** Changing chord N's duration adjusts only the local gap
   between N and N+1 — it never moves N+1's onset. Shortening N leaves freed beats in
   place (see remainder policy); lengthening N is capped at the available local gap, and
   growing further requires deleting/merging the following chord. Because the tail never
   slides, no downstream straddle can be created.

During initial banking none of this triggers: uniform defaults that divide the bar
(quarter in 4/4) tile bars perfectly (onset = cumulative sum; when a bar fills, the next
chord starts a fresh bar). Straddle risk exists **only** on post-hoc duration edits,
which constraints 2 and 3 fence off.

### Remainder policy: auto-pad with a rest

When a shortening edit leaves unfilled time in a bar, the freed span auto-fills with a
rest:

- The model already supports `kind: "rest"`; `_to_legacy_measures` already renders rest
  items. No new rendering engine.
- Onsets stay stable (non-reflow), so no downstream straddle.
- The freed span is always within a single bar (guaranteed by the invariant), so it is
  decomposed greedily into standard rest values (e.g. 3 free beats in 4/4 → dotted-half
  rest; otherwise a short greedy sequence of standard rests).
- Result: a teacher shortens a note and the bar simply shows a rest. The blackboard
  stays frictionless; no "you must fill the bar" gate.

### Defaults and deferrals

- **Default note value on bank: quarter.** Quarters tile a 4/4 bar in four banks, giving
  natural barlines. (Whole-note default would put one chord per bar and produce barlines
  very fast.)
- **Deferred (genuine engine work):** cross-barline ties/splitting, tuplets,
  rests-from-arbitrary-gaps beyond simple bar padding, beaming polish, pickup measures.

---

## Decision (b) — Analysis-slot model: two zones, ≤1 type each, type declares allowed zones

Today the placement and mutual-exclusivity rules for analysis overlays are scattered
across `stave_notater.js` and `exercise_sheet.js`. This spec formalizes a single source
of truth.

### Model

- Two zones: **above** the staff and **below** the staff.
- Each zone holds **at most one** active analysis type.
- Each analysis type declares which zones it is allowed in and its anchor granularity.

```
analysisSlots = { above: <typeId|null>, below: <typeId|null> }

type descriptor: { id, label, allowedZones: [above|below...], anchor: slice|note|measure }
```

Mutual exclusion is structural (one field per zone), not enforced by scattered
conditionals. The "max two streams, max one per zone" rule falls out of the two fields.

### Type → zone mapping (from existing `analyzeConfig` modes)

| Type                              | Allowed zone(s) | Anchor |
|-----------------------------------|-----------------|--------|
| `roman_numerals`, `roman_numerals_exp` | below      | slice  |
| `thoroughbass` (figured bass)     | below           | slice  |
| `scale_degrees`, solfege variants | above           | note   |
| `note_names`                      | above           | note   |
| `bass_*`                          | below           | note   |

### Persistence

The slot selection persists in `analyzeConfig` as `{ above, below }`. A new config module
(`analysis_slots.js`) owns the type descriptors and the zone rules; `stave_notater.js`
and `exercise_sheet.js` consume it instead of re-deriving placement. Clicking an analysis
baseline opens the picker for that zone, listing only types whose `allowedZones` include
it.

---

## Decision (c) — Keyboard-shortcut scoping: selection-scoped, never global

The piano binds nearly every letter and number key for **note entry** (the QWERTY
overlay in `keyboard_shortcuts.js`; SPACE/ENTER bank a chord). Any global authoring
shortcut would collide.

Resolution:

- **No new global authoring shortcuts.** Collision is impossible by construction.
- Authoring accelerators (`1–4` set duration, `R` cycle key-aware respelling, arrows
  nudge) fire **only when a chord or token is selected** (edit focus). `Esc` deselects
  and returns every key to note entry.
- When a text field (Roman-numeral / figure input) is focused, the global note-entry
  handler suspends. `shortcuts.js` must bail when `document.activeElement` is a text
  input/textarea.
- Selection state is the gate. Click-first remains primary; shortcuts only accelerate
  the already-selected element.

This dissolves the concept's `T`/`A`/`1–4`/`R` collision worry — none are global.

---

## Decision (d) — Save = approval, collapsing the soft gate (confirmed)

- A Play Save sets `umto.metadata.analysis_review_status = "reviewed"` directly. Because
  everything was editable in place, Save *is* the approval.
- **Remove the bounce.** Today `music_controls.js` (`onClickSaveJSON`) reads
  `reviewStatus === "generated"` + `reviewUrl` from the add response, fires a
  `window.alert`, and opens the workbench review panel in a new tab. That branch is
  deleted. Save returns `{ id }`; the teacher stays in Play (then proceeds to the
  post-save target selector).
- `analysis_review_status` is retained for provenance. The `generated → workbench` review
  path survives **only** for bulk MusicXML imports that never pass through Play.
- Teacher-facing Save feedback routes through `feedbackService.emit`, not `window.alert`.

---

## Decision (e) — Agent-native parity: UI is a thin layer over a data-op set

Authoring is defined as a set of operations; the UI and an agent drive the same ops. Each
maps to an existing or minimally extended endpoint. The workbench review API is already
keyed by chord `offset`, so the agent payload shape already exists.

```
setMeter(meter)
addChord(visible[], hidden[], offset?)
setChordDuration(offset, duration_type, dots)
respellNote(offset, midi, spellingName)
setAnalysisSlot(zone, typeId|null)
setToken(offset, zone, value)          // Roman numeral or figure text
saveExercise() -> reviewed UMTO { id }
```

Parity rule: every click in the UI corresponds to exactly one operation above; there is
no UI-only affordance. An agent authors by:

- creating the row via the add endpoint (chordal UMTO), and
- editing analysis/spelling by POSTing the same `rows[]`-by-`offset` payload the workbench
  review API (`POST /dashboard/api/workbench/chordal-analysis/<id>/`) already accepts.

The operation set — not the widget set — is the contract. Duration, meter, and analysis-
slot operations are added to the review payload schema so an agent has full parity with
the new authoring controls.

---

## Zero-friction blackboard: quiet until invoked

One surface, progressive reveal — not a mode switch.

- Default state is today's blackboard: play chords, see analysis, make no decisions, no
  authoring chrome.
- Authoring affordances appear only on interaction: clicking a chord opens a micro-
  toolbar at the cursor (duration, respell, pitch correction); clicking an analysis
  baseline opens the zone's type picker; clicking a token opens correction (inline field
  or prioritized option list, reusing the figure-token picker).
- Live teaching is never interrupted; the creator is a latent layer over the blackboard.

---

## Post-save target selector — the seam to Threads 2/3

Thread 1 defines the handoff interface only. Threads 2/3 implement the targets.

- **Trigger:** after Save returns a reviewed UMTO `{ id }`.
- **Contract across the seam:**

  ```
  { exerciseId, targetIntent: "library" | "assign", sectionId?, autoTranspose: bool }
  ```

- **v1 stub:** the selector ships with `library` as the default and only wired target.
  `assign` (to a class section) and a browsable curriculum library are Thread 2/3 work.
- **Auto-transposition** rides this seam as a post-save toggle (default off). Roman
  numerals and figured bass are key-relative and transpose cleanly; note spelling must be
  recomputed per key using the PR #90 `chordal_spelling` helpers. v1 designs the contract
  and toggle; the per-key recompute implementation is deferred with the rest of the
  target work.

---

## MusicXML import onto the same canvas

The "Import MusicXML" affordance routes `umto_import_router.musicxml_score_to_chord_events`
output (chord events already carry spelling) onto the Play canvas for verify/fix/approve,
instead of into the bulk workbench pipeline. The teacher then reviews and Saves through
the same in-Play flow. This reuses the existing parser; the work is routing its output to
the canvas. (Full import-onto-canvas wiring may phase after the core authoring loop.)

---

## v1 cut (sequencing)

Ship:

1. Re-home review/override/respell into Play with **live notation preview** (free — Play
   already has the VexFlow renderer). Save → `reviewed`.
2. On-canvas click targets: respell, Roman-numeral correction (with figure picker),
   analysis-zone selection (the slot model), per-chord duration with the constraint model.
3. Duration-aware `dataForSave` / `save_chordal_umto_exercise`; meter; barlines; auto-rest
   padding.
4. MusicXML import onto the same canvas.
5. Post-save target-selector stub (library default) + auto-transpose toggle (contract
   only).

Defer:

- Cross-barline ties, tuplets, beaming polish, pickup measures.
- Pitch-swap-without-replay (beyond respell).
- Full power-user shortcut layer beyond the selection-scoped accelerators.
- Real curriculum library + assign-to-section (Threads 2/3).
- Auto-transposition per-key recompute implementation.

---

## File map (where this lives)

- `lab/static/js/src/components/music/play_sheet.js` — `dataForSave` serializes durations;
  selection state; micro-toolbar; click-to-edit wiring.
- `lab/static/js/src/config/analysis_slots.js` (new) — analysis-slot type descriptors +
  zone rules (single source of truth).
- `lab/static/js/src/components/music/stave_notater.js`, `exercise_sheet.js` — consume
  `analysis_slots.js` instead of scattered placement logic.
- `lab/static/js/src/components/ui/music_controls.js` — Save → `reviewed`; delete the
  generated/reviewUrl bounce; route feedback through `feedbackService`.
- `lab/static/js/src/components/input/shortcuts.js` — selection-scoped accelerators;
  suspend note-entry when a text input is focused.
- `lab/static/js/src/components/music/chordal_spelling.js` — respell on canvas; per-key
  recompute for auto-transpose (deferred impl).
- `apps/exercises/umto_factory.py` (`save_chordal_umto_exercise`) — accept per-chord
  durations + meter.
- `apps/dashboard/views/api_workbench.py` — extend the review payload schema with meter /
  duration / analysis-slot fields for agent parity.
- Reuse the workbench respell editor + figure-token picker JS from `workbench.html`
  inline in Play.

---

## Acceptance criteria

1. Banking N chords and Save produces a chordal UMTO row whose `analysis_review_status` is
   `reviewed` with no review-panel redirect and no `window.alert`.
2. `dataForSave` round-trips each chord's chosen `duration_type`/`dots` and the score
   `meter`; the saved UMTO renders correct barlines.
3. The duration picker greys out any value that would overflow the current bar; no saved
   event ever crosses a barline.
4. Shortening a chord auto-pads the freed span with standard rest(s) within the same bar;
   later chords' onsets do not move.
5. Each analysis zone holds at most one type; a type only appears in zones its descriptor
   allows; selection persists in `analyzeConfig` as `{ above, below }`.
6. Authoring keyboard accelerators fire only with a selection; with no selection, all keys
   drive note entry; focusing a text field suspends note entry.
7. An agent can author an equivalent exercise end to end using only the documented
   operation set (add endpoint + review API payload), with no UI-only step.
8. The live blackboard with no interaction shows no authoring chrome and behaves as today.
9. Save surfaces the post-save target selector; choosing `library` files the reviewed
   exercise; the seam contract `{ exerciseId, targetIntent, sectionId?, autoTranspose }`
   is emitted.

## Non-goals

- No any-teacher dashboard redesign (Thread 2).
- No curriculum library / assignment implementation (Thread 3) beyond the seam stub.
- No cross-barline tie engine, tuplets, or new student runtime.
- No new legacy exercise shapes; review state stays at `umto.metadata.analysis_review_status`.
