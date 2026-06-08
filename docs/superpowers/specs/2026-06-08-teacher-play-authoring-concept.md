# Teacher Play View — "Click-First" Authoring Concept (2026-06-08)

> **Status: DESIGN CONCEPT (Thread 1 of the teacher-experience brief).** Captures a voice brainstorm (no transcript survived; reconstructed from memory + a Gemini summary) and a grounded critique against the actual codebase. This is Thread 1 (unify authoring + review in the Play view). Threads 2 (dashboard for any teacher) and 3 (curriculum curation) are still open — see `2026-06-08-teacher-experience-design-brief.md`.

## Core philosophy

**"If you see it on the screen, you can click it to change it."** WYSIWYG, on-canvas, context-sensitive clicks — no buried settings, no floating sidebars. The `/teacher/play/` view is *both* the live classroom blackboard and the structured content creator. A parallel keyboard-shortcut layer serves power users.

## The concept (reconstructed)

```
+------------------------------------------------------------------------+
|  [<- Dashboard]              Exercise Creator        [Import MusicXML] |
+------------------------------------------------------------------------+
|  Analysis Layer (Top):    [ (None) / click to select top analysis ]    |
|  Time Signature:  [ 4/4 ] (click to change)                            |
|                     o            o           #o          o             |
|                     o            o            o          o             |
|  Analysis Layer (Bottom): [ Roman Numeral v ] (click to change)        |
|                             I            IV          V/V         V     |
+------------------------------------------------------------------------+
| [Clear Canvas]                                       [ Save Exercise ] |
+------------------------------------------------------------------------+
```

- **Entry / blackboard preserved.** Canvas loads clean with a time-signature *placeholder*. Unselected → flexible/open meter for free-form teaching. Click the time signature → overlay of standard meters.
- **Input & pedal capture (unchanged).** Teacher plays chords via MIDI/keyboard; notes show as uniform whole notes (or generic values matching the meter); spacebar/sustain pedal locks a chord and triggers background analysis.
- **Click a chord/note → micro-toolbar at cursor:** duration adjust, note respelling (toggle enharmonic), pitch correction (swap a note without replaying).
- **Click the analysis baseline → choose analysis type.** Max two active streams: one above, one below the staff. Some analyses are anchored to a zone; max one per zone.
- **Click an analysis token → correct it.** Click a Roman numeral / figure → inline text field or a prioritized list of options.
- **Power-user shortcuts (parallel):** `T` time sig, `A` analysis zones, `1–4` duration when a chord is selected, `R` cycle key-aware respellings; hover reveals the shortcut as a micro-tooltip for organic learning.
- **Import MusicXML** button top-right → parses onto the same interactive canvas for verify/fix/prep.
- **Save Exercise** commits a cleanly reviewed UMTO row. Post-save (next design): target selector (curriculum library vs. assign to a class section) + auto-transposition toggle.

---

## Critique (grounded in the current codebase)

### Why this is the right direction
- It **resolves the fragmentation** the brief flagged: review/override/respell stop living in the bulk-import workbench and move to where authoring happens.
- The Play view **already has the full VexFlow renderer**, so the live notation preview that was impossible on the dashboard (why PR #90 used a text preview) is essentially free here. This is the single strongest reason to re-home authoring/review into Play.

### Already built — this concept mostly *reassembles* existing mechanics (low risk)
- **Key-aware spelling + per-note override** — done (PR #90). Click-to-respell on canvas is the in-Play surface for it; `chordal_spelling.js` already exposes the resolution logic.
- **Roman-numeral token editing + figure-token picker** — built for the workbench panel (`{z5}` etc.); reuse the picker inline. Stacked rendering of braced figures already works.
- **Contextual analysis** — `Analyze.getNoteName`/roman logic already produce the labels Play captures; `dataForSave` already serializes spelling.
- **MusicXML → same canvas** — `umto_import_router.musicxml_score_to_chord_events` already yields chord events *with* spelling. The parser exists; the work is routing its output onto the Play canvas instead of the bulk pipeline.

### Real new complexity — scope levers to decide explicitly
1. **Duration editing is the biggest new engine work.** Today chordal capture is uniform whole notes with onset = index; `_chordal_to_measures` / `_convertChordalUMTOToProcessedScore` split by duration but Play never varies it. Per-chord durations introduce measure splitting, rests, multi-measure layout, and beaming concerns. **Decision: is variable duration in v1, or defer (keep uniform) and ship the rest first?** Strong candidate to defer — it's separable and the rest delivers most of the value.
2. **The two-layer analysis model needs formalizing.** "One above, one below, some anchored, max one per zone" maps to existing `analyzeConfig` modes (`roman_numerals`, `roman_numerals_exp`, `thoroughbass`, `scale_degrees`, `note_names`, `bass_*`) but the placement/mutual-exclusivity rules are currently scattered across `stave_notater.js` / `exercise_sheet.js`. Define a clean **"analysis slot" model** (zone = above|below, each holds ≤1 type, each type declares allowed zones) as the single source of truth.
3. **Keyboard-shortcut collision risk.** The piano already binds letter/number keys for *note entry* (the QWERTY overlay). `1–4`, `R`, `T`, `A` will collide. Authoring shortcuts must be **scoped** (active only when an element is selected, or behind a modifier, or only in an explicit "edit" focus) — don't break live playing.

### Conceptual gaps to close
4. **Save = approval.** If everything is editable inline and the teacher hits Save, **Save itself is the approval** — there's no need for the separate "needs review / generated" gate. This *collapses* the soft gate from PR #90 and removes the round-trip the brief complained about. State this explicitly; it simplifies the model. (Keep `analysis_review_status` for provenance, but in Play it goes straight to `reviewed` on Save.)
5. **Blackboard vs. creator tension.** Don't let authoring affordances clutter live teaching. The zero-friction blackboard (play, see analysis, no decisions) must remain the default; authoring controls should be quiet until invoked. Decide: one surface with progressive reveal, or a subtle mode switch.
6. **Agent-native parity (CLAUDE.md).** Every click-action (set meter, set duration, respell, set RN, choose analysis layer) must have a data-level / tool equivalent so an agent can author too. Design the operations, not just the UI.
7. **Auto-transposition is non-trivial but aligned.** Roman numerals and figured bass are key-relative (transpose cleanly); **note spelling must be recomputed per key** (the very thing PR #90's helpers do). Aligns with the adaptive-engine intent in CLAUDE.md (serve keys via transposition, not DB duplication). Keep it a post-save toggle; design the spelling-per-key recompute carefully.
8. **Scope check vs. the brief.** This concept is almost entirely Thread 1. Threads 2 (any-teacher dashboard) and 3 (curriculum curation/assignment) are only touched by the post-save "target selector." Those need their own design passes — the post-save target selector is the seam where Thread 1 hands off to Threads 2/3.

### Suggested v1 cut (if forced to sequence)
1. Re-home review/override/respell into Play with **live notation preview** (reuse PR #90 mechanics + the existing renderer). Save → `reviewed`.
2. On-canvas click targets: respell, Roman-numeral correction (with figure picker), analysis-layer selection (the slot model).
3. MusicXML import onto the same canvas.
4. **Defer:** variable duration editing, pitch-swap, power-user shortcut layer, auto-transposition, post-save target selector (Threads 2/3).

---

## Handoff prompt for a fresh session

> Design Thread 1 of the Monteverdi teacher experience: a "click-first" WYSIWYG authoring + review flow in the Play view (`/teacher/play/`), where authoring and analysis review happen in one place and Save replaces the separate review step. Read, in order: `docs/superpowers/specs/2026-06-08-teacher-play-authoring-concept.md` (the concept + a grounded critique with scope levers), `docs/superpowers/specs/2026-06-08-teacher-experience-design-brief.md` (the umbrella brief + any-teacher reframe), and the code it references — `play_sheet.js` (`dataForSave`), `exercise_sheet._convertChordalUMTOToProcessedScore`, `vexflow_adapter.itemToTickable`, `chordal_spelling.js`, `umto_factory.save_chordal_umto_exercise`, `umto_import_router` (MusicXML + analysis slices), and the workbench review panel in `workbench.html` (the figure-token picker / respell UI shipped in PR #90). Use the brainstorming skill, then write a design spec. Resolve these decisions first: (a) is variable per-chord duration in v1 or deferred; (b) the formal "analysis slot" model (zones above/below, ≤1 type each, per-type allowed zones); (c) keyboard-shortcut scoping vs. the existing note-entry QWERTY bindings; (d) confirm "Save = approval" collapses the soft gate; (e) agent-native parity for every click-action. Keep the zero-friction live blackboard intact as the default. Output a design spec, not a task list. Threads 2 (any-teacher dashboard) and 3 (curriculum curation) are separate — only design the post-save "target selector" as the seam to them.
