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

## Decision (a) — Duration & barlines: free entry, teacher-placed barlines, meter-gated Save

### The model (ABC-style)

Authoring **accepts anything**; **barlines are the teacher's responsibility**; the **time
signature is the mode switch and the only save gate**. This replaces an earlier
grid-constrained approach (position-aware duration picker + interior auto-rest), which
created a "hole" in the middle of a bar whenever a note was shortened. Dropping the
auto-derived grid removes the hole problem at the root.

- **Free entry.** The teacher plays chords and sets each chord's note value freely. No
  greyed-out picker, no reflow, no auto-inserted rests. Durations are whatever the teacher
  chooses.
- **Teacher-placed barlines.** Barlines are explicit — placed by the teacher (click the
  gap between two chords to drop/remove a barline; ABC's `|`). A barline sits *between*
  chords, so **a note can never straddle one — straddle is structurally impossible** and
  no runtime invariant machinery is needed. When a meter is set, barlines are
  **auto-suggested** at the cumulative-sum boundaries (reusing the legacy `getsBarline`
  math) as a starting point the teacher then moves/adds/removes.
- **Two modes, switched by the time signature:**
  - **No meter → free/open mode.** Anything goes; no barlines required; **Save always
    allowed.** This *is* the zero-friction live blackboard (and matches the concept doc's
    "unselected meter = flexible/open teaching"). The blackboard-vs-creator tension
    collapses into one control the teacher already understands: the meter.
  - **Meter set → metered mode.** Barlines auto-suggested and editable; **Save is gated on
    validity** (below).
- **Metered Save validity.** Every bar — the chords between consecutive barlines, plus the
  implicit first bar from offset 0 and the final bar to the end — must sum to **exactly
  `barLen`**. Over/under blocks Save with specific feedback ("Bar 3 has 5 beats, expected
  4"). No stretch, no pad: the teacher fixes a duration or moves a barline.

### Canonical rhythm + barline payload

- **Rhythm:** `ChordEvent.duration` as a **quarter-length float**. The chordal model has
  no `duration_type`/`dots` (those live on the voices-kind `VoiceEvent`); they are derived
  at render. `dataForSave()` stops flattening (`rhythmValue: "w"`);
  `save_chordal_umto_exercise` stops hardcoding `1.0` and **drops the final-chord
  auto-stretch** (umto_factory.py:752-758) — it distorted the teacher's rhythm and is
  superseded by the metered Save gate.
- **Barlines:** **explicit, persisted** as barline positions (quarter-length offsets,
  snapped to chord onsets) in chordal metadata. This is a real **schema addition** — today
  the model *derives* measures from meter+durations; the ABC model stores the teacher's
  barlines instead. Barline offsets must coincide with chord onsets (never interior to a
  chord), which is what keeps straddle structurally impossible.
- **Free mode needs an optional meter.** `Metadata.meter` is currently a required string;
  free/open mode requires it to be optional or a sentinel ("none"). Small schema
  consideration to confirm in planning.

### Server-side validity (metered mode only)

Because of agent-native parity (Decision e), validity is enforced **on the server**, not
just in the UI. One shared validator runs on the create/save path
(`save_chordal_umto_exercise` / `/exercises/add/`) **and** the review/update path (the
workbench chordal-analysis endpoint):

- **Free mode (no meter):** no rhythmic validation; any chord stream saves.
- **Metered mode:** reject unless every inter-barline bar sums to exactly `barLen`, and
  every barline offset coincides with a chord onset. This replaces `_build_score_data`'s
  silent absorption of overfull measures (umto_factory.py:516,526).
- **Monotonic/non-overlap** stays enforced (umto_factory.py:508-509).

UI and agent paths obey the same rule because both pass through this validator.

### Legacy precedent: trust, not enforcement

The legacy dashboard let an author type a per-chord duration string (`q h q.` …)
*after* creating the exercise. Its barline logic (`exercise_sheet.js` render loop +
helpers `getsBarline`, `countElapsedBars`, `getWholeNoteCount`,
`getWholeNoteRemainder`, `timeSignatureParsed`) was purely additive:

1. Each chord stored a `_rhythmValue`; `getWholeNoteCount` converts it to a whole-note
   fraction (w=1, h=.5, q=.25, q.=.375).
2. Those fractions are summed into a running `elapsedWholeNotes`.
3. `getsBarline(ts, elapsed)` computes `barCount = elapsed × denom / num` and draws a
   barline at a chord boundary **iff `barCount` is an exact integer** — i.e. only when
   the cumulative sum lands precisely on a bar multiple. The barline is the boundary
   between two `Stave` objects, recorded as an index in `this.barlines`.

There was **no splitting, no ties, and no validation.** If a chord's duration overran a
bar boundary, the note straddled silently and a barline only reappeared wherever a later
cumulative sum happened to re-align on an integer; bars could hold more or less than a
full measure. The author was implicitly trusted to type durations that summed to whole
bars. This is the same cross-barline gap the modern `_to_legacy_measures` still admits
(`"We don't handle ties/splitting across measures here yet"`).

### Why this design reuses the legacy math (narrowly)

The additive barline core (`getsBarline` / `countElapsedBars` / `getWholeNoteCount` /
`timeSignatureParsed`) is reused for two narrow jobs, **not** for deriving the final
barlines:

1. **Auto-suggest** barline positions when a meter is set — a starting point the teacher
   then edits.
2. **Validity check** at Save — confirm each inter-barline bar sums to `barLen`.

The barlines themselves are now **explicit teacher data**, not a render-time derivation.
The contract flips from legacy "trust the author, render whatever" to "free entry, but a
*metered* exercise can only be **saved** when its bars are valid." Free mode keeps the
legacy looseness on purpose; metering is what turns on discipline.

### Defaults and deferrals

- **Default note value on bank: quarter.**
- **Default meter: none (free/open).** The surface starts as the zero-friction blackboard;
  the teacher opts into metering by setting a time signature.
- **Deferred:** ties (a note sounding across a barline), tuplets, explicit rest entry (so
  in metered v1 bars are filled by chords summing exactly), beaming polish, pickup
  measures.

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
- Save has a **validity precondition** (Decision a, metered mode): in free mode it always
  proceeds; with a meter set it proceeds only when every inter-barline bar sums to
  `barLen`. An invalid metered progression blocks Save with specific feedback rather than
  producing a `reviewed` exercise.
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
setMeter(meter|none)                   // none = free/open mode
addChord(visible[], hidden[], offset?)
setChordDuration(offset, quarterLength) // quarter-lengths; no duration_type/dots stored
placeBarline(offset)                   // offset must coincide with a chord onset
removeBarline(offset)
respellNote(offset, midi, spellingName)
setAnalysisSlot(zone, typeId|null)
setToken(offset, zone, value)          // Roman numeral or figure text
saveExercise() -> reviewed UMTO { id } // metered: rejects invalid bars
```

Parity rule: every click in the UI corresponds to exactly one operation above; there is
no UI-only affordance. An agent authors by:

- creating the row via the add endpoint (chordal UMTO), and
- editing analysis/spelling by POSTing the same `rows[]`-by-`offset` payload the workbench
  review API (`POST /dashboard/api/workbench/chordal-analysis/<id>/`) already accepts.

The operation set — not the widget set — is the contract. Duration, meter, barline, and
analysis-slot operations are added to the review payload schema so an agent has full
parity with the new authoring controls.

**Endpoint gap (must close before parity is real).** The current workbench
chordal-analysis POST handler (`api_workbench.py`) updates only analysis `content` and
spelling — it cannot set `duration`, `meter`, barlines, or analysis-slot zones. The
implementation plan must include a schema-extension step for this endpoint covering the
new ops, plus tests for: invalid offset (no matching chord), barline offset not on a chord
onset, and (metered) a bar that does not sum to `barLen`. The shared metered-validity
validator from Decision (a) backs these tests.

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

Two orthogonal things, do not conflate them: **chrome visibility** is progressive-reveal
(quiet until a click), while the **time signature** is a content mode (free vs metered,
per Decision a) that governs only Save-time rhythmic validity — not whether authoring
chrome appears. Free mode + no interaction = today's blackboard exactly.

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

The core loop ships first; import and the post-save seam phase behind it (no hard product
reason to ship them together — splitting reduces v1 risk).

**Phase A — core authoring/review/duration loop:**

1. Re-home review/override/respell into Play with **live notation preview** (free — Play
   already has the VexFlow renderer). Save → `reviewed`.
2. On-canvas click targets: respell, Roman-numeral correction (with figure picker),
   analysis-zone selection (the slot model), per-chord duration (free palette), barline
   place/remove.
3. Duration + explicit barlines in `dataForSave` / `save_chordal_umto_exercise` (remove
   final-chord auto-stretch; persist barline offsets; optional/none meter for free mode);
   ABC-style render path (running stream, barlines where placed, no complete-measure
   requirement mid-edit); meter auto-suggest of barlines.
4. Shared server-side metered-validity validator on create/save **and** review/update
   paths; review-endpoint schema extension for duration/meter/barline/analysis-slot ops
   + tests.

**Phase B — seam + import (after Phase A lands):**

5. MusicXML import onto the same canvas.
6. Post-save target-selector stub (library default) + auto-transpose toggle (contract
   only).

Defer:

- Cross-barline ties, tuplets, beaming polish, pickup measures.
- Pitch-swap-without-replay (beyond respell).
- Full power-user shortcut layer beyond the selection-scoped accelerators.
- Real curriculum library + assign-to-section (Threads 2/3).
- Auto-transposition per-key recompute implementation.

---

## File map (where this lives)

- `lab/static/js/src/components/music/play_sheet.js` — `dataForSave` serializes per-chord
  durations + explicit barline offsets; selection state; micro-toolbar; click-to-edit and
  click-to-place-barline wiring.
- `lab/static/js/src/config/analysis_slots.js` (new) — analysis-slot type descriptors +
  zone rules (single source of truth).
- `lab/static/js/src/components/music/stave_notater.js`, `exercise_sheet.js` — consume
  `analysis_slots.js` instead of scattered placement logic. ABC-style render: draw a
  running chord stream with barlines only where the teacher placed them (no
  complete-measure requirement mid-edit). Reuse the legacy barline math (`getsBarline`,
  `countElapsedBars`, `getWholeNoteCount`, `timeSignatureParsed`) only for barline
  auto-suggest and the metered-validity check — not to derive final barlines.
- `apps/exercises/umto.py` — chordal `Metadata`: add explicit barline offsets; make
  `meter` optional (free/open mode).
- `lab/static/js/src/components/ui/music_controls.js` — Save → `reviewed`; delete the
  generated/reviewUrl bounce; route feedback through `feedbackService`.
- `lab/static/js/src/components/input/shortcuts.js` — selection-scoped accelerators;
  suspend note-entry when a text input is focused.
- `lab/static/js/src/components/music/chordal_spelling.js` — respell on canvas; per-key
  recompute for auto-transpose (deferred impl).
- `apps/exercises/umto_factory.py` (`save_chordal_umto_exercise`, `_build_score_data`) —
  accept per-chord durations + explicit barlines + optional meter; **remove the
  final-chord auto-stretch**; replace overfull-measure absorption with the shared
  metered-validity check.
- `apps/dashboard/views/api_workbench.py` — extend the review payload schema with meter /
  duration / barline / analysis-slot fields for agent parity.
- Reuse the workbench respell editor + figure-token picker JS from `workbench.html`
  inline in Play.

---

## Acceptance criteria

1. Banking N chords and Save produces a chordal UMTO row whose `analysis_review_status` is
   `reviewed` with no review-panel redirect and no `window.alert`.
2. `dataForSave` round-trips each chord's chosen note value as `ChordEvent.duration`
   (quarter-lengths) plus explicit barline offsets; the saved UMTO renders barlines where
   the teacher placed them. (`duration_type`/`dots` are derived at render.)
3. Free mode (no meter) saves any chord stream with no rhythmic validation. Barlines snap
   to chord onsets; no barline can fall interior to a chord, so no event straddles one.
4. In metered mode, Save (UI and server) is allowed only when every inter-barline bar
   sums to exactly `barLen`; an over/under bar **blocks Save** with specific feedback
   ("Bar 3 has 5 beats, expected 4"). No auto-stretch, no auto-rest — the final-chord
   auto-stretch is gone and the teacher's durations stand.
4a. Setting a meter auto-suggests barlines at cumulative-sum boundaries; the teacher can
    move/add/remove them, and validity re-checks against the edited barlines.
5. Each analysis zone holds at most one type; a type only appears in zones its descriptor
   allows; selection persists in `analyzeConfig` as `{ above, below }`.
6. Authoring keyboard accelerators fire only with a selection; with no selection, all keys
   drive note entry; focusing a text field suspends note entry.
7. An agent can author an equivalent exercise end to end using only the documented
   operation set (add endpoint + review API payload), with no UI-only step.
8. The live blackboard with no interaction shows no authoring chrome and behaves as today.
9. Save surfaces the post-save target selector; choosing `library` files the reviewed
   exercise; the seam contract `{ exerciseId, targetIntent, sectionId?, autoTranspose }`
   is emitted. (Phase B.)
10. The review/update endpoint accepts duration, meter, barline, and analysis-slot ops; it
    rejects invalid offsets (no matching chord), barline offsets not on a chord onset, and
    (metered) bars that do not sum to `barLen`, with tests covering each rejection.

## Non-goals

- No any-teacher dashboard redesign (Thread 2).
- No curriculum library / assignment implementation (Thread 3) beyond the seam stub.
- No cross-barline tie engine, tuplets, or new student runtime.
- No new legacy exercise shapes; review state stays at `umto.metadata.analysis_review_status`.
