---
date: 2026-05-29
topic: student-feedback-system
status: design
scope: UX/content design for student-facing feedback, hints, and instructions
---

# Design: Student Feedback, Hints & Instruction System

## Problem

Student-facing feedback in the exercise player is inconsistent in both **placement**
and **voice**:

- Some constraints fire a **global notification** (the alert-icon panel) for what is
  really a local, momentary event. The clearest example: in harmonization **Click
  mode**, clicking past the chord's note cap broadcasts
  `EVENTS.BROADCAST.NOTIFICATION` ([click_note.js:198](../../../lab/static/js/src/components/input/click_note.js#L198)),
  routing a tiny "you can't add a 5th note" signal through the same channel as a
  browser-level MIDI warning. That panel is global, persistent, and dismiss-on-click —
  far too heavy for a transient editing constraint.
- Some exercises lack enough **on-screen guidance** — the student stares at a staff
  with no instruction on what to do, what mode they're in, or how to commit an answer.
- There is **no shared vocabulary** for "what kind of message is this" or "where should
  it appear," so each feature improvises. The notification panel
  ([notifications.js](../../../lab/static/js/src/components/notifications.js)) was even
  dormant for a stretch (see
  [2026-05-28-midi-fallback-message-design.md](2026-05-28-midi-fallback-message-design.md)),
  meaning some messages were broadcast into the void.
- **Tone** drifts between "system alert" ("MIDI setup was unsuccessful") and pedagogy.
  We want a single warm, encouraging, scholarly voice — a patient teacher, not an error
  dialog.

This spec defines a **feedback taxonomy**, **placement rules**, **copy guidelines**,
a **string-catalog + documentation system**, and a **lightweight component/API** so
every current and future exercise type produces consistent, well-placed, well-written
feedback — and so we can later measure where students get stuck.

This is a design spec. No implementation here; it is detailed enough to seed an
implementation plan next.

## Audience & voice (the north star)

Users are **mixed music students** — some absolute beginners, some conservatory-trained.
Every message is written as if spoken by **a patient, encouraging teacher sitting beside
the student**. Three adjectives govern all copy:

- **Warm** — assumes good faith, never scolds, never blames.
- **Encouraging** — frames mistakes as part of learning; celebrates progress honestly.
- **Scholarly** — uses correct musical terminology, but introduces it gently.

Anti-goal: the "system alert" register — terse, technical, capitalized severities,
exclamation points, error codes, anything that reads like the software is complaining.

---

## 1. Feedback taxonomy

Six categories. Every student-facing message MUST be classifiable as exactly one.
The category determines default placement (§2) and copy register (§3).

| # | Category | What it means | Persistence | Default placement | Example trigger |
|---|----------|---------------|-------------|-------------------|-----------------|
| 1 | **Blocking error** | Something genuinely prevents work and **no usable input path remains**. Very rare. | Sticky until resolved/dismissed | Global notification | Exercise failed to load; no graded surface available |
| 2 | **Recoverable mistake** | A graded attempt was wrong, but the student can immediately try again. The core teaching moment. | Until next attempt | Local anchored (on the score) + control microfeedback | Wrong chord submitted; wrong note named |
| 3 | **Soft constraint** | An action the interface declined because it's outside the current rules — not a "mistake," just "not allowed here." | Transient (auto-fade) | Local anchored bubble or control microfeedback | Clicking past the note cap; clicking outside the active column |
| 4 | **Hint / help** | Optional guidance the student can pull or that we gently push when they appear stuck. | Dismissible / auto-fade | Local anchored bubble; inline help text | "Stuck? The soprano usually moves by step here." |
| 5 | **Success / encouragement** | Confirmation that an attempt was correct, or a phrase/exercise completed. | Brief, auto-fade (+ persistent state color) | Local anchored + control microfeedback | Chord correct; exercise complete |
| 6 | **Mode / state change** | The interface changed state and the student should notice. Not good/bad — orienting. | Brief, auto-fade (+ persistent affordance) | Inline text near the affordance + control microfeedback | Switched Live↔Click; **no WebMIDI / no device → guidance on the available input paths** |

### Category notes

- **Blocking errors are rare by design.** A message is cat. 1 only when **no usable
  input path remains**. Reserve the global panel for things that are genuinely global and
  genuinely persistent.
- **No-MIDI is cat. 6, not cat. 1.** When WebMIDI is unsupported (Safari/Firefox/iOS) or
  no device is connected, work is *not* blocked — the student still has computer-keyboard
  input, Click input, and the on-screen keyboard. So this is a **mode/state** message that
  *orients the student to the input paths they do have*, not a blocking error. (It only
  becomes cat. 1 in the impossible case where every input path is unavailable.) See §4 for
  the exact copy, which must name the available paths.
- **The note-cap is cat. 3, not global.** It is a soft constraint and is currently
  miscategorized as a global notification ([click_note.js:198](../../../lab/static/js/src/components/input/click_note.js#L198)).
- **Recoverable mistakes (cat. 2) are the pedagogical heart.** They must never feel
  punitive and must never be global. They belong on the score, where the music is.
- **Soft constraints (cat. 3) should feel like a gentle nudge, often non-verbal.** The
  best soft-constraint feedback is sometimes *no text at all* (§2.5) — a control that
  visibly refuses (greys, shakes) teaches the rule without a sentence.
- **Mode/state (cat. 6) is orienting, not evaluative.** It answers "what just changed?"
  and "what can I do now?"

---

## 2. Placement rules

Five surfaces, ordered from heaviest to lightest. **Default to the lightest surface
that does the job.** Heaviness is a cost paid in attention and screen noise.

### 2.1 Global notification — `NotificationsComponent`

The existing alert-icon panel ([notifications.js](../../../lab/static/js/src/components/notifications.js)),
rendered into `#notifications` in both
[exercise.html](../../../lab/templates/exercise.html) and
[student/player.html](../../../apps/student/templates/student/player.html).

**Use ONLY for:** category 1 (blocking errors) and truly session-global, persistent
information. Things that are true regardless of where the student's attention is on the
page, and that should remain available until acknowledged.

**Never use for:** transient editing feedback, per-attempt grading results, hints, soft
constraints, or mode changes. (This is the bug we are fixing: the note-cap notification
must leave this channel.)

**Rule of thumb:** if dismissing it makes sense, or if the student would want to re-open
it later, it's global. If it's about *what just happened where I clicked*, it's not.

### 2.2 Local anchored bubble — **NEW surface (the centerpiece)**

A small, positioned message anchored to a **specific score location or control** — a
column/onset, a notehead, a slot, or a button. Auto-fades for soft/transient categories;
dismissible for hints. This is the surface HarmonyLab is **missing** and is the main new
build (see §6).

**Use for:**
- Recoverable mistakes (cat. 2): anchored to the wrong column/note ("That third doesn't
  fit this chord — try again.").
- Soft constraints (cat. 3): anchored to the active column ("This chord takes up to 4
  notes.").
- Hints (cat. 4): anchored to the relevant spot, dismissible.
- Success (cat. 5): brief, anchored to the just-completed column.

**Why anchored:** the student's eyes are on the staff, not the top-right alert icon.
Feedback about the music belongs *on the music*.

**Anchoring is per type via an "anchor provider" — not one shared geometry.** Different
exercise types expose different layout data, so the bubble renderer does **not** assume
click-note geometry is sufficient. Each surface/type supplies a small **anchor provider**
that resolves an anchor descriptor → a pixel rect:

| Anchor kind | Provider source | Used by |
|-------------|-----------------|---------|
| `column`/`onset` | click-note `_staffLayout` (`columns[].centerX`, system `yTop`) — [click-note spec §1](2026-05-28-click-note-input-design.md) | Harmonization Click mode |
| `ident_slot` | identification `?`-slot layout (`_identWindowLayout` / rendered slot DOM) | Pitch/interval/chord identification |
| `chorale_window` | chorale window/onset mapping in the grader + timeline | Chorale play |
| `notehead` | rendered-notehead geometry (canvas hit geometry) | Play/identification on rendered notes |
| `control` | DOM `getBoundingClientRect()` of a named control | Done button, mode toggle |

The renderer (§6.2) takes a resolved rect and is geometry-agnostic. Harmonization Click
mode reuses existing `_staffLayout` (no new export); other types each need their own
provider, defined when that type adopts anchored feedback. Where a type has no provider
yet, its feedback falls back to a non-anchored surface (inline/control) until one is added.

### 2.3 Inline text

Static or semi-static text that lives **in the page layout** (not floating): the
instruction line above an exercise, a one-line help string near the input toolbar, a
mode label.

**Use for:**
- Per-exercise **instructions** (cat. 6 baseline orientation): "Play all four voices of
  Riemenschneider 1, mm. 1–4." This is the persistent on-screen guidance whose absence
  is part of the current problem.
- Persistent mode indication: a small "Click input" / "Live input" label near `#piano`.
- Always-available help affordance ("Need a hint?").

**Rule:** inline text is for guidance that is true for the *whole* exercise or the
*current mode*, not for momentary events.

### 2.4 Button / control microfeedback

The control itself communicates through its own visual state — color, disabled styling,
a brief shake, a checkmark, a count badge. No separate message element.

**Use for:**
- Soft constraints where the *control* is the subject: the **Done** button disabled (with
  tooltip) when no notes are selected; the cap reached → the staff/cursor briefly refuses
  a new notehead.
- Reinforcing success: the **Done** button flashes a check on a correct commit.
- Mode state: the active source-mode toggle button shows its active styling
  (`input-mode-btn-active`, already the pattern in `note_name.js`).

**Rule:** if the feedback is *about a control*, express it *on that control* before adding
any words.

### 2.5 No text at all

The strongest option for many soft constraints and successes. The existing score-coloring
already does this: notes turn **black when correct**, gray when unplayed, red when wrong
(per CLAUDE.md, VexFlow adapter). That *is* feedback — pre-verbal, immediate, and noise-free.

**Use for:**
- Soft constraints where a control visibly refusing is self-explanatory (a click that
  produces no notehead at the cap, optionally with a one-time tiny hint the first time).
- Per-note correctness during play (color only — do not narrate every correct note).
- Cursor/ghost-note affordances that show what a click *would* do.

**Rule:** prefer color/motion/affordance over words whenever the meaning is unambiguous.
Reserve words for when the student would otherwise ask "why?".

### Placement decision flow

```
Is it genuinely global AND persistent (session-level)?      → Global notification (2.1)
Is it about a specific spot on the score?                    → Local anchored bubble (2.2)
Is it true for the whole exercise / current mode?            → Inline text (2.3)
Is it about a specific control?                              → Control microfeedback (2.4)
Is the meaning obvious from a visual refusal / color?        → No text (2.5)
```

Walk top to bottom; stop at the first "yes" — but bias toward the bottom. Most feedback
should resolve to 2.2, 2.4, or 2.5.

---

## 3. Copy guidelines

### 3.1 Tone

- **Teacher beside the student**, never a system reporting status.
- **Second person, present tense, active voice.** "Try the chord again," not "An error
  was detected."
- **No blame, no severity-shouting.** No "ERROR", no all-caps, no "Invalid", no "Failed."
  Avoid the exclamation point except in genuine, earned celebration (sparingly).
- **Curiosity over correction.** Where natural, frame a mistake as a question or
  observation that invites another attempt: "That's close — listen to the third."
- **Confidence without flattery.** Praise the work, not the person, and only when earned.
  "Nicely voiced." beats "You're amazing!"

### 3.2 Length

| Surface | Target length |
|---------|---------------|
| Local anchored bubble | 1 short sentence (≤ ~10 words). One idea. |
| Control microfeedback / tooltip | A fragment or 2–4 words ("Up to 4 notes", "Pick some notes first"). |
| Inline instruction | 1–2 sentences; may include a short bulleted list for multi-step setup. |
| Global notification | Title (≤ ~5 words) + 1–2 sentence body. Optional expandable detail for the technical "why." |
| Hint | 1 sentence; may chain to a second, more specific hint on a second request. |

If a message needs more than its budget, it's probably the wrong surface (too heavy) or
two messages.

### 3.3 Good vs. bad examples

| Situation | ❌ Bad (system-alert / blaming / vague) | ✅ Good (warm, scholarly, right-sized) |
|-----------|----------------------------------------|----------------------------------------|
| No WebMIDI / no device | "MIDI setup was unsuccessful. Check that your browser supports the WebMIDI API…" | "No MIDI keyboard? No problem — click notes onto the staff, use your computer keyboard, or play the on-screen keyboard." |
| Note cap reached | (global panel) "Maximum notes. This chord allows up to 4 note(s)." | (anchored, auto-fade) "This chord takes up to four notes." |
| Wrong chord | "INCORRECT" | "Not quite — check the chord quality and try again." |
| Click outside column | "Invalid click location." | *(no text; the click simply produces no note — the active column stays highlighted)* |
| Done with nothing selected | "Error: empty submission." | (tooltip on disabled Done) "Add a note or two first." |
| Correct chord | "Correct!!!" | "Yes — that's the dominant." *(or color-only)* |
| Exercise complete | "Exercise passed." | "Beautifully done — you've harmonized all of Riemenschneider 1." |
| Mode switch | "INPUT_SOURCE_MODE = click" | "Click input — tap the staff to place each note." |

### 3.4 Music-theory terminology rules

- **Use correct terms** — this is a music-theory tool; "third," "dominant," "inversion,"
  "leading tone" are the vocabulary students are *here to learn*. Do not dumb them down.
- **But scaffold the first encounter.** When a message names a concept a beginner may not
  know, pair it with a concrete pointer: "Check the chord quality — is it major or minor?"
  rather than only "Wrong quality."
- **Prefer the musical "why" over the mechanical "what."** "The bass should be the root
  here" teaches; "Wrong note in voice 4" does not.
- **Consistent vocabulary.** One canonical term per concept across all messages (e.g.
  always "soprano," never sometimes "top voice"). The string catalog (§4) is the registry
  that enforces this.
- **Symbols vs. words.** Use Roman numerals and figured-bass symbols where the student is
  already reading them on screen; spell out in prose where the term is being introduced.

### 3.5 Beginner vs. advanced assumptions

We serve both without two separate copy sets. Strategy:

- **Write the baseline message for the beginner** — concrete, self-contained, no
  unexplained jargon in the *primary* clause.
- **Carry the advanced precision in a secondary clause or an optional detail.** "Not quite
  — that's a ♭VII; this spot wants the dominant." The beginner gets "not quite, aim for the
  dominant"; the advanced student gets the exact diagnosis.
- **Let exercise metadata tune depth where cheap.** Exercises already carry `complexity`
  and `skill_tags` (CLAUDE.md). A later iteration MAY use these to select a terser,
  higher-register variant for advanced units — but v1 ships one well-scaffolded string per
  event. Do **not** build a full difficulty-branching copy engine in v1 (YAGNI).
- **Never gate correctness feedback on assumed knowledge.** A beginner must always be able
  to act on a message without already knowing the term it uses.

---

## 4. Harmonization Click mode — worked examples

These are the canonical reference cases. Each names: category, surface(s), copy, and
persistence. (Grading contract is unchanged — see
[2026-05-28-click-note-input-design.md](2026-05-28-click-note-input-design.md).)

| Event | Category | Surface | Copy | Persistence |
|-------|----------|---------|------|-------------|
| **Too many notes** (click past cap) | 3 Soft constraint | Local anchored bubble at active column + control microfeedback (cursor refuses) | "This chord takes up to {n} notes." | Auto-fade ~2.5s; **never** the global panel |
| **Click outside active column** | 3 Soft constraint | No text (2.5) — click is a no-op; active column stays highlighted. *Optional:* one-time first-occurrence bubble | *(none)* / first-time: "Fill this chord first, then the next opens." | First-time bubble auto-fades; thereafter silent |
| **Done pressed, no notes** | 3 Soft constraint | Control microfeedback — Done disabled with tooltip (preferred), or brief anchored bubble if Done stays enabled | "Add a note or two first." | While empty (disabled state) / auto-fade if bubble |
| **Wrong chord** (committed, graded incorrect) | 2 Recoverable mistake | Local anchored bubble at the column + score coloring (red) + Done microfeedback | "Not quite — check the chord against the figure and try again." | Until next attempt; bubble auto-fades ~4s, color persists |
| **Correct chord** | 5 Success | Score coloring (black) + brief anchored bubble (optional) + Done check flash | "Yes — that's it." *(or color-only)* | Color persists; bubble/flash auto-fade ~1.5s |
| **MIDI ↔ Click mode change** | 6 Mode/state | Inline mode label near `#piano` (persistent) + brief anchored/toast confirmation | Live: "Live input — play your keyboard or MIDI." · Click: "Click input — tap the staff to place each note." | Label persistent; confirmation auto-fades ~2s |
| **No WebMIDI support OR no device connected** | 6 Mode/state (work is **not** blocked — fallback input exists) | Inline guidance near `#piano` (persistent) **+** one brief non-global transient toast/anchored hint on first detection. **No global panel** (cat. 6 never uses it). | "No MIDI keyboard? No problem — name your input: **click notes onto the staff**, use your **computer keyboard**, or play the **on-screen keyboard**." | Inline guidance persists; transient hint auto-fades ~3s |

### Migration note (the cited bug)

[click_note.js:196–204](../../../lab/static/js/src/components/input/click_note.js#L196)
currently does:

```js
this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
  type: "info",
  title: "Maximum notes",
  description: "This chord allows up to " + cap + " note(s).",
});
```

This becomes a **local anchored, auto-fading hint** at the active column (cat. 3, surface
2.2 + 2.4), via the new feedback API (§6) — *not* `EVENTS.BROADCAST.NOTIFICATION`. The
global channel is reserved for cat. 1.

---

## 5. Documentation & string system

### 5.1 Where message strings live

**Single source of truth: a string catalog**, extending the existing
[error_text.js](../../../lab/static/js/src/config/error_text.js) pattern (already a flat
`define({...})` dict surfaced through `Config.get("errorText....")`).

Proposed: a `feedback_text.js` catalog (or rename/extend `error_text.js` →
`feedback_text.js`, keeping the `errorText.*` keys as a back-compat alias). Reusable
UI-feedback and system copy live here keyed by a **feedback ID** (§5.3): grading results,
soft constraints, mode/state messages, hints, system errors. No literal *feedback* strings
inline in components — components reference IDs only. This is what makes copy reviewable,
consistent, and (later) translatable.

**Scope boundary — what the catalog does NOT own.** Exercise-specific *pedagogical
content* stays in exercise data, not the catalog:
- **Per-exercise instructions / prompts** are authored server-side or in UMTO content
  (e.g. `import_chorale.py`'s instructional text, UMTO `description`/`source`). These are
  data, vary per exercise, and are already authored where the exercise is defined — the
  catalog must not duplicate or override them.
- **Roman numerals, figured-bass symbols, answer choices** are exercise/score data.

The dividing line: **catalog = reusable UI/system feedback that is the same across many
exercises; exercise data = content specific to one exercise.** The inline-instruction
*surface* (§2.3) renders exercise-authored strings; the *catalog* supplies only the
generic UI chrome around them (e.g. a generic "Need a hint?" affordance label).

Catalog entry shape:

```js
"harmonization.click.note_cap": {
  category: "soft_constraint",          // taxonomy §1
  surface: "anchored",                  // default placement §2
  title: null,                          // optional (global only)
  // template params in {braces}; resolved at call site
  body: "This chord takes up to {n} notes.",
  detail: null,                         // optional expandable "why" (global)
  defaultTimeoutMs: 2500,               // null = sticky
}
```

Templating: simple `{name}` interpolation against a params object at emit time — no
heavy i18n library in v1, but the shape is i18n-ready (string table keyed by ID).

### 5.2 How to document each feedback event

A **feedback registry doc**: `docs/feedback_catalog.md`, one row per feedback ID, kept in
sync with the catalog. Columns:

| Column | Meaning |
|--------|---------|
| Feedback ID | Canonical key (§5.3) |
| Category | Taxonomy 1–6 |
| Surface | Default placement |
| Trigger | What user/system action fires it |
| Copy | Current string (the canonical wording) |
| Persistence | Sticky / auto-fade(ms) / until-next-attempt |
| Owner exercise type(s) | Which exercise types emit it |

This doc is the **content-design review artifact** — a copywriter/instructor can review
all student-facing language in one place without reading code. Updating copy = editing the
catalog + this row.

### 5.3 Naming convention for feedback IDs

Dotted, lowercase, hierarchical, stable:

```
<domain>.<context>.<event>
```

- `<domain>` — exercise/system area: `harmonization`, `chorale`, `identification`,
  `pitch_id`, `interval`, `system`, `input`.
- `<context>` — sub-area or mode: `click`, `midi`, `grade`, `mode`, `device`.
- `<event>` — the specific event: `note_cap`, `wrong_chord`, `correct`, `empty_commit`,
  `outside_column`, `mode_changed`, `no_device`.

Examples:

```
harmonization.click.note_cap
harmonization.click.outside_column
harmonization.grade.wrong_chord
harmonization.grade.correct
input.mode.changed
input.device.none
system.exercise.load_failed
exercise.complete
```

Rules: IDs are **stable** (rename = migration, since registry + analytics key on them),
**unique**, and **describe the event, not the wording** (copy can change; the ID can't).

### 5.4 How future exercise types add feedback

A short, repeatable checklist (lives in `docs/feedback_catalog.md` header and is referenced
from CLAUDE.md's Documentation Requirements):

1. **Classify** each new student-facing message into one taxonomy category (§1).
2. **Choose the lightest surface** that fits (§2 decision flow).
3. **Add a catalog entry** in `feedback_text.js` with a new feedback ID (§5.3),
   category, surface, copy, persistence.
4. **Register a row** in `docs/feedback_catalog.md`.
5. **Emit via the feedback API** (§6) by ID — never `broadcast(NOTIFICATION, …)` with an
   inline string, never a bare `alert()`.
6. **Run copy past the voice check** (§3): warm, encouraging, scholarly; right length;
   beginner-actionable.
7. If the message has an analytics interest (friction point), it's already covered —
   emitting by ID auto-instruments it (§6).

Add this as a bullet to CLAUDE.md's "Documentation Requirements" so PRs that add a new
exercise type or feedback event are held to it.

---

## 6. Implementation direction (lightweight feedback API)

> Direction only — concrete file plan belongs in the implementation plan. The goal is a
> **single funnel** so feedback stops being ad hoc and becomes consistent, placeable, and
> measurable.

### 6.1 Core idea: one emit funnel, ID-keyed

A `FeedbackService` (single instance, wired in `exercise.js` like other components) with
one primary method:

```js
feedback.emit("harmonization.click.note_cap", {
  params: { n: 4 },
  anchor: { type: "column", onset: 1024, systemIndex: 0 }, // optional
  // category/surface/copy/timeout resolved from the catalog by ID
});
```

The service:
1. Looks up the catalog entry by ID → category, surface, copy template, timeout.
2. Interpolates `params` into the copy.
3. **Routes to the surface** the entry declares (overridable per call):
   - `global` → existing `NotificationsComponent` (`EVENTS.BROADCAST.NOTIFICATION`).
   - `anchored` → the **new anchored-bubble renderer** (below).
   - `inline` → updates a designated inline region (instruction line / mode label).
   - `control` → toggles control state/tooltip (caller supplies the control ref or a
     well-known control ID like `done_button`).
   - `none` → no DOM; emits the analytics event only (§6.4).
4. Applies persistence (sticky vs. auto-fade timeout vs. until-next-attempt).
5. Logs the analytics event (§6.4).

This kills scattered notifications: components call `feedback.emit(id, …)`; the *service*
decides placement from the catalog, so placement policy is centralized and reviewable, not
re-decided in each component.

### 6.2 Anchored-bubble renderer (the new surface)

A small floating-element renderer that takes a **resolved pixel rect** from an **anchor
provider** (§2.2 table) and positions a bubble against it. The renderer is
geometry-agnostic; providers map an anchor descriptor (`{kind, …}`) → rect:
- `column`/`onset` → click-note `_staffLayout` ([click-note spec §1](2026-05-28-click-note-input-design.md)):
  `column.centerX`, system `yTop`. Reuse it; no parallel export for this kind.
- `control` → DOM `getBoundingClientRect()` (Done button, toggle).
- `ident_slot` / `chorale_window` / `notehead` → that type's own provider, added when the
  type adopts anchored feedback (do **not** assume click-note geometry covers them).

Behavior:
- One bubble per anchor at a time (new emit on same anchor replaces).
- **Auto-fade** with the catalog timeout; **dismissible** (small ×) for hints.
- Pointer-events light: never blocks the staff click handlers underneath.
- Distinct styling per category (constraint = neutral/info, mistake = warm-red, success =
  warm-green, hint = soft/quiet) — but all in the warm palette, not alert-red.
- Renders in **both** templates (`exercise.html` and `student/player.html`) — the
  midi-fallback spec's two-template lesson applies (see that spec's "Two Templates" note).

### 6.3 Dismissible / auto-fading semantics

Three persistence modes, declared in the catalog, enforced by the service:
- `sticky` — stays until dismissed or condition resolves (cat. 1; disabled-control states).
- `timeout(ms)` — auto-fades (cat. 3, 5, 6; most hints).
- `until_next_attempt` — cleared when the student commits another graded answer (cat. 2).
  **Concrete binding:** the service subscribes to the existing local event
  `exerciseContext.bind("graded", …)` ([exercise_context.js:356](../../../lab/static/js/src/models/exercise_context.js#L356)
  et al.; already used by `exercise_sheet.js:176`). This is the canonical "an attempt was
  graded" signal — do **not** infer it from `BANK_NOTES` / `NEXT_CHORD` (those are
  input/advance events, not grade events). If a future surface needs a global grade signal,
  add a real broadcast event rather than overloading those.

### 6.4 Analytics on friction points (built in, not bolted on)

Because every message flows through `feedback.emit(id, …)`, instrumentation is free and
uniform. The service logs a lightweight event per emit:

```js
{ feedbackId, category, exerciseId, unit, complexity, skillTags, ts }
```

(These are available from the definition/exercise payload —
`exerciseContext.definition.exercise` carries `exerciseId`, `complexity_score`, and
`skill_tags`; `unit` is derived from tags (e.g. `unit:N`) when not a direct field.)

v1: log to a client buffer / console hook with a clean shape (no backend required to start
— mirrors how `student-progress-tracking` began). A later iteration can POST aggregates.
The payoff: "which feedback IDs fire most" = a direct map of where students struggle
(e.g. `harmonization.grade.wrong_chord` clustering on a unit signals a hard concept;
`harmonization.click.note_cap` firing a lot signals a UI affordance problem). This is why
IDs must be stable (§5.3) — they're the analytics primary key.

### 6.5 What this explicitly avoids

- **No more inline reusable feedback strings** in components (all via catalog IDs).
  Exercise-authored content — per-exercise prompts/instructions, RNs, figured bass, answer
  choices — is **not** migrated into the catalog; it stays in exercise data (§5.1 boundary).
- **No more direct `EVENTS.BROADCAST.NOTIFICATION` from feature code** for non-global
  events — the note-cap migration (§4) is the first cleanup; audit for others.
- **No `window.alert` / ad hoc DOM toasts.**
- The **grading contract is untouched** — feedback is a presentation/observability layer
  reading grade results, never influencing them (consistent with the input-agnostic
  grading invariant in the click-note spec).

### 6.6 Migration sequence (for the later plan)

1. Build `feedback_text.js` catalog + `FeedbackService` + anchored-bubble renderer (both
   templates).
2. Migrate the **note-cap** event off the global panel → `feedback.emit("harmonization.click.note_cap", …)` (cat. 3, anchored). This is the cited bug and the proof case.
3. Wire the other §4 harmonization Click-mode events.
4. Author per-exercise **inline instruction** strings for types currently missing them —
   **in exercise data** (server-side / UMTO content), rendered by the inline surface
   (§2.3); not in the feedback catalog (§5.1 scope boundary).
5. Backfill remaining ad hoc notifications across exercise types onto the funnel.
6. Add the analytics buffer.
7. Add the §5.4 checklist bullet to CLAUDE.md Documentation Requirements.

---

## Out of scope (YAGNI)

- Full i18n / localization (catalog shape is i18n-ready; no translation pipeline in v1).
- A difficulty-branching copy engine that auto-rewrites every string by `complexity`
  (v1 = one well-scaffolded string per event; metadata-tuned variants are a later option).
- Backend analytics storage/dashboards (v1 logs a clean client-side event shape only).
- A hint *content* system (which hints, adaptive hint selection) — this spec defines the
  hint *surface and plumbing*; the pedagogy of hint content is a separate design.
- Audio/spoken feedback.
- Reworking the score-coloring system itself (it stays as the primary "no text" channel).

## Documentation impact

- New `docs/feedback_catalog.md` (registry, §5.2) — created with the catalog.
- CLAUDE.md "Documentation Requirements" gains the §5.4 feedback checklist bullet.
- Any future exercise-type spec must list its feedback IDs (per §5.4).
- No `exercise_types.md` / `management_commands.md` change (no new exercise type or command).

## Open questions for the plan

1. Extend `error_text.js` in place vs. new `feedback_text.js` with a back-compat alias?
   (Recommend: new file, alias old keys, migrate `midi*` entries over time.)
2. Anchored-bubble rendering tech: lightweight absolutely-positioned DOM over the canvas
   (simplest, reuses `_staffLayout` pixel coords) vs. canvas draw. (Recommend: DOM overlay
   — easier to style, animate, make accessible, and dismiss.)
3. Accessibility: anchored bubbles should also surface to assistive tech (e.g. an
   `aria-live` region mirroring cat. 2/5 messages). Confirm scope for v1.
