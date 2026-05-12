# Unit 2: Add Barlines Exercise — Exploration

**Date:** 2026-05-11
**Status:** Exploration / pre-design — not yet committed to implementation
**Author:** avnerdorman

---

## What This Is

A new interactive exercise type for Unit 2 (Rhythm & Meter) where students are shown a notated rhythmic passage with no barlines and no time signature, and must click between beat groups to place barlines correctly.

This is "Phase 3 / Repair Family" in the existing Unit 2 meter spec (`2026-05-04-unit2-meter-questions-design.md`), which explicitly deferred it. This document explores whether and how to build it.

---

## Pedagogical Value

**High.** This is the strongest test of meter internalization available in Unit 2:

- MC symbolic questions (Phase 1) test whether students can decode a time signature — useful, but gameable by pattern-matching.
- Add-barlines tests whether students can *feel* the meter in actual notation — they must group beats correctly from note durations alone.
- Students who can do this correctly understand meter; students who cannot are revealed clearly.
- Natural "aha moment" when barlines snap into place — more satisfying than clicking a radio button.
- High replayability: same passage in a different notated meter = a different exercise.

---

## Student Experience

**Potentially fun, with risk of tedium.**

- Sweet spot passage length: 4–8 beats. Long enough to require thought, short enough to not be a slog.
- Risk: exercises that are too long, or whose notation is hard to parse, become frustrating rather than illuminating.
- Kern folk/dance corpus passages are naturally short and idiomatic — good fit.

---

## Scope

**Phase 1 scope:** Simple meters (2/4, 3/4, 4/4) plus compound (6/8, 9/8, 12/8). Full Unit 2 curriculum in one exercise type.

**Out of scope for Phase 1:**
- Irregular meters (5/8, 7/8)
- Common time C / cut time
- Beaming repair (separate interaction)
- Full UMTO integration + mastery tracking (deferred to Phase 2 migration)

---

## Interaction Model

### Beat-cursor approach (revised 2026-05-12)

Rather than calculating pixel-precise hit zones over the VexFlow canvas, the interaction uses a **snapping cursor** that moves between discrete beat positions. This eliminates the need for a canvas hit-zone calculation engine and naturally trains beat-level counting.

**Student sees:**
- A single-voice passage rendered in VexFlow on a staff
- No time signature shown
- No barlines shown initially
- A cursor: rectangular highlight over the current beat + dashed vertical line at its left edge (barline preview)
- Any already-placed barlines shown as solid vertical lines

**Student action:**
- ← / → arrow keys (or on-screen arrow buttons, or swipe on mobile) to move cursor left/right between beats
- Enter / Space / on-screen "Place" button → toggle barline at current cursor position
- All placed barlines visible as the student works
- Submit button when satisfied

**Implementation note:** Beat x-positions come from VexFlow's formatter after rendering — `note.getAbsoluteX()` for each beat-onset note. Cursor rendering is a DOM/SVG overlay positioned using those x-values; no pixel math needed beyond reading note positions post-render.

**Grader:**
- State: `Set<int>` of beat indices where student placed barlines
- Pure set-equality: student set vs correct set
- Score: 0 errors = correct; any wrong or missing position = incorrect
- Partial credit optional in Phase 2

**Pedagogical bonus:** Moving the cursor forces students to count beats explicitly — that's the core skill, built into the navigation itself. Division-level cursor (between division pulses rather than beats) is a natural Phase 2 extension for compound meter practice.

---

## Architecture Approach: C (Hybrid)

Build as a QA player module first. Migrate to a first-class exercise type later if pedagogically validated.

**Rationale:** This is still exploratory. Validating the interaction with real students before wiring it into core infrastructure is the right call. The data format will be UMTO-compatible from day one so migration has zero throwaway cost.

### Phase 1: QA player module

- New exercise family `unit2_add_barlines` served by the existing `qa_player.js`
- VexFlow renders the unbarred passage inside the QA player UI
- Click targets are SVG/DOM overlay zones between beat groups
- Grader is pure JS

### Phase 2 (if validated): Promote to core

- Add `barline_placement` mode to UMTO schema
- Wire into ExerciseContext, ExerciseSheet, VexFlow adapter
- Full mastery/progress tracking

---

## Data Format (UMTO-compatible sketch)

```json
{
  "family": "unit2_add_barlines",
  "time_signature": "3/4",
  "show_time_signature": false,
  "clef": "treble",
  "notes": [
    { "duration": "q", "dots": 0 },
    { "duration": "q", "dots": 0 },
    { "duration": "q", "dots": 0 },
    { "duration": "h", "dots": 0 },
    { "duration": "q", "dots": 0 },
    { "duration": "q", "dots": 1 },
    { "duration": "8", "dots": 0 },
    { "duration": "q", "dots": 0 }
  ],
  "correct_barline_positions": [3, 5, 8],
  "tags": ["unit:2", "unit:2_meter_simple", "unit:2_meter_triple"],
  "source": "Essen Folk Song Collection, no. 42"
}
```

`correct_barline_positions` = 0-indexed note positions *after* which a barline falls.

Pitches are omitted or dummy values — this is rhythm-only in Phase 1. If VexFlow requires pitch to render, use a fixed pitch (e.g. B4 / middle line of treble staff) throughout.

---

## Corpus / Repertoire

### Primary recommendation: Essen Folk Song Collection (via Kern Scores)

- Thousands of short monophonic folk melodies
- Public domain
- Available in Kern format at kern.humdrum.org
- Simple and compound meters naturally represented
- Short phrases (4–8 beats) easily extractable

### Secondary: Chopin mazurkas (kern.humdrum.org/search?s=t&keyword=mazurka)

- Good for 3/4 specifically
- More rhythmically interesting than folk songs
- But limited to triple meter — use as supplement, not primary corpus

### Parsing strategy

Kern → Python (music21 or hand-rolled Kern parser) → beat-grouped note list → exercise JSON.

`music21` can parse Kern directly:
```python
from music21 import converter
score = converter.parse("path/to/file.krn")
```

Extract flat note list with durations, compute beat positions, determine correct barline positions from time signature.

---

## Effort Estimate

| Work item | Effort |
|---|---|
| VexFlow unbarred rendering (suppress time sig + barlines) | Medium |
| Beat-cursor overlay (DOM/SVG positioned from note x-coords) | Low-medium |
| Keyboard + on-screen arrow navigation | Low |
| Mobile swipe support | Low |
| Grader (Set&lt;int&gt; set-equality) | Low |
| Kern → exercise JSON import pipeline | Medium |
| QA player extension (VexFlow inside QA player) | Medium |
| UMTO-compatible data schema | Low |
| Django management command to import passages | Low |
| Tests | Low-medium |

**Total: ~2–3 weeks solo** (down from 3–4 weeks). Biggest risk reduced: beat-cursor overlay is much simpler than arbitrary hit-zone calculation. VexFlow unbarred rendering remains the main unknown.

### Recommended spike before committing

1-day spike: render one unbarred passage in VexFlow (no time sig, no barlines), read beat x-positions from the formatter, render a cursor overlay at beat 0, move it left/right with arrow keys. If that feels clean, the hardest unknowns are solved. If VexFlow x-position access is unreliable or the overlay flickers on resize, reassess.

---

## ROI Verdict

| Condition | Verdict |
|---|---|
| Unit 2 is a primary focus right now | **Do it** — strong pedagogical payoff, no similar exercise exists in the stack |
| Unit 2 is one of several units in parallel | **Defer** — high effort for a single unit; symbolic MC questions already cover conceptual knowledge |
| Student engagement / "fun factor" is a priority | **Do it** — most interactive exercise type outside MIDI play |

---

## Prior Art: Placement Exam Repo

A standalone HTML/JS barline-placement tool exists at `github.com/avnerdorman/Placement-Exam`.

**Worth extracting:**
- Beat-grid model (dividing a passage into legal barline insertion points)
- Grading function (set-equality of inserted vs correct positions)

**Not worth reusing:**
- Rendering (not VexFlow)
- Exercise format (not UMTO)

---

## Blockers / Open Questions Before Committing

1. **VexFlow spike** — can we suppress barlines and time signature cleanly, and place reliable click zones? Needs a day of hands-on testing.
2. **Rhythm-only notation** — does rendering with a fixed pitch (B4) look acceptable, or does pitch variation matter for readability?
3. **Kern parsing** — is music21's Kern import reliable enough for the Essen corpus, or will we need a custom parser for edge cases?
4. **QA player extension** — how much surgery does qa_player.js need to host VexFlow rendering? Is it still recognizably the same module after?

---

## Next Steps (if proceeding)

1. Do the VexFlow spike (1 day).
2. If spike passes, write a full design spec (replacing this exploration doc).
3. Write implementation plan via `superpowers:writing-plans`.
4. Build Phase 1 (QA player module).
5. Gather student feedback.
6. Decide on Phase 2 (UMTO promotion) based on results.
