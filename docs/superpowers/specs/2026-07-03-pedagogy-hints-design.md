# Pedagogy-Aligned Hints & Instructions — Design

**Date:** 2026-07-03
**Status:** Spec (pending product-owner review)
**Owner:** avner
**Scope:** Student-facing hint/instruction language for figured-bass and Roman-numeral exercises; removal of "inversion" from student-facing text.

## Problem

The hints and instructions do not consistently match the pedagogy taught in this
project:

1. **Figured-bass hints do not distinguish abbreviated from unabbreviated
   exercises.** `lab/static/js/src/config/exercise_instructions.js` keys hints
   by interaction mode only (`harmonization`, `identification`, etc.). The
   `analysisType` values `figured_bass` (abbreviated) and
   `figured_bass_unabbreviated` (unabbreviated) share one hint set. An
   unabbreviated exercise never tells the student "choose the unabbreviated
   figure" or that "unabbreviated figures are generic intervals from the bass
   (including the octave)."

2. **Abbreviation hints are a static generic table.** The current harmonization
   hint embeds the full Kellner table regardless of which figures the exercise
   uses. It does not surface the realization table (per-voice-count required vs
   omittable tones) and is not driven by the exercise's actual figures or voice
   count.

3. **"inversion" leaks into student-facing text.** Per the canon
   (`docs/music-theory-canon.md` §"Figured bass — intervals above the bass, not
   inversion") and the user's hard standard (memory
   `feedback_music_theory_no_silent_fallback.md`), figured-bass pedagogy names
   *intervals above the bass*, never "inversion." Yet "inversion" appears in:
   - `lab/static/js/src/config/feedback_catalog.js:28` — feedback body shown to
     students.
   - `apps/exercises/generation/music21_builder.py:76-78` — triad/seventh
     identification answer choices students pick.
   - Unit titles/labels in `music_theory_taxonomy.json`, the taxonomy HTML, and
     `apps/exercises/forms.py`.

4. **Roman-numeral identification hints use "find the root, stack thirds"
   framing** adjacent to inversion language rather than the scale-degree /
   solfège mental model the user teaches (I = 1, 3, 5 = do-mi-sol; I6 = third
   in the bass; IV = 4, 6, 1 = fa-la-do).

## Goals

- Figured-bass hints branch on `analysisType`: abbreviated exercises say
  "choose the abbreviated figure" and show expansions; unabbreviated exercises
  say "choose the unabbreviated figure / generic intervals from the bass
  (including the octave)" and show raw stacks.
- Abbreviated-hint expansions are **per-exercise dynamic** — only the figures
  the exercise uses, and (for harmonization) the realization for *this
  exercise's* voice count, with essential/omittable/doubling tones marked.
- No **newly generated or newly rendered** student-facing hint, feedback, or
  answer-choice string contains the word "inversion." Replace with "third in
  the bass" / "fifth in the bass" / "seventh in the bass" / "interval above
  the bass." (Already-generated exercise titles stored in the DB are excluded
  from this goal for v1 — see Non-goals.)
- Roman-numeral identification hints use scale-degree numbers and solfège
  (do-mi-sol, fa-la-do), never "inversion."
- A "More info" link in figured-bass hints points to the authoritative
  Gettysburg reading-figured-bass page
  (https://musictheory.sites.gettysburg.edu/unit-4-1/reading-figured-bass/),
  which already matches the canon pedagogy and contains no "inversion."

## Non-goals / follow-ups

- Building an in-app reference page. The Gettysburg link suffices for v1; an
  in-app page that mirrors the realization table is a tracked follow-up.
- Renaming the internal feedback key `wrong_inversion` or the grader reason
  `wrong_bass` (internal, not student-facing).
- Re-titling already-generated exercises stored in the DB. Only newly
  generated exercises adopt the new titles. **Owner: avner. Trigger:**
  schedule a one-time re-titling + regeneration pass (and remove the
  `music21_builder.py` grader-side synonym map once it lands) within one
  grading period of this spec merging, tracked as a follow-up issue — not an
  open-ended "someday."
- The deferred `recompute_harmonization_targets` run for pre-existing
  exercises. New exercises get the `requiredIntervalNumbers` field (see
  Architecture) going forward without it.

## Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Scope | Full pedagogy pass: figured-bass hints + "inversion" removal + RN reframe |
| Chord-tone language | Context-dependent: scale-degree numbers for figured-bass hints; solfège (movable do) for RN identification hints |
| Hint content source | Per-exercise dynamic (computed from the exercise's actual figures) |
| Architecture | Approach A — client-side compute at render time, new JS module |
| Required-tones source | Server-provided — `targets.py` already computes `required_numbers()`; extend its payload with the required interval numbers and have the hint module read that field directly. (Supersedes the originally-locked B1 client-side-port decision — see "Why not a client-side JS port of the required-tones algorithm" below.) |
| Reference link | Existing Gettysburg page |
| Notation | Essential intervals plain; omittable named tones in parens; optional octave doubling marked `[+8]` (distinct from parens — doubling adds a tone, it doesn't permit omitting one). Data-driven from the exercise's voice count. |

## Sequencing

This spec bundles two materially different efforts: (1) the "inversion"
terminology removal (feedback text, answer choices, taxonomy/forms labels,
generated titles) — independently justified by the user's existing hard
standard, low technical risk, no dependency on the hint architecture below —
and (2) the analysisType-branched per-exercise dynamic hint rework, which
depends on the `targets.py` payload extension. Ship as two increments rather
than one PR:

- **Increment 1 — terminology removal.** `feedback_catalog.js`,
  `music21_builder.py` triad answer choices + synonym map, taxonomy/forms
  labels, generator titles. No dependency on Increment 2; can land and ship
  first.
- **Increment 2 — dynamic hint architecture.** `figured_bass_hints.js`,
  `targets.py` payload extension, render-layer wiring, Roman-numeral reframe.

## Architecture

### New module: `lab/static/js/src/config/figured_bass_hints.js`

Pure functions, no DOM access. Mirrors one Python source of truth (scope
narrowed from the original three — see "Why not a client-side JS port of the
required-tones algorithm" below):

- `_SHORTHANDS` — mirror of `apps/exercises/harmonization/figures.py:_SHORTHANDS`
  (abbreviated figure → interval token list). Still needed client-side because
  identification hints (surfaces C/D) show students the abbreviation-to-stack
  expansion for labeling purposes, independent of required-tones realization.

Functions:

- `expandFigure(abbrev: string): string[]` — abbreviated figure → interval
  token list, via `_SHORTHANDS`. Mirrors `figures.py:expand_figure_string`.
- `buildHarmonizationHints(definition, analysisType): string[]` — reads
  `definition.harmonizationTargets` (each has `figures`, `displayFigure`,
  `requiredIntervalNumbers` (see server-payload note below), `voiceCountPolicy`,
  `bassSpelling`). Branches on `analysisType`:
  - `figured_bass` (abbreviated) — returns the per-figure essential/omittable/
    doubling notation, reading essential/omittable status directly from each
    target's `requiredIntervalNumbers` (no client-side recomputation).
  - `figured_bass_unabbreviated` (unabbreviated) — returns the per-target raw
    stack using `target.figures` (already the fully expanded interval list —
    `expand_figure_string` is idempotent on already-unabbreviated figures, so
    this field is correct for both abbreviated and unabbreviated exercises
    with no separate raw-figure field needed).
  Returns `[]` if no targets.
- `buildIdentificationHints(definition, analysisType): string[]` — reads the
  slices' `figured_bass` (abbreviated) or `raw_figured_bass` (unabbreviated)
  and returns progressive hint array with plain expansions (no
  essential/optional — the student labels, does not realize). Returns `[]` if
  no FB slices.
- `MORE_INFO_URL` — the Gettysburg page URL, appended as a final hint line.
  `_renderHintControls` currently renders each hint step via
  `$panel.text(allSteps[step])`, which would show this URL as inert text, not
  a clickable link. For this one final step only, switch to
  `$panel.html(...)` with a pre-built (not user-input) anchor tag —
  `<a href="{MORE_INFO_URL}" target="_blank" rel="noopener">More info: reading
  figured bass</a>` — so the student can actually reach the reference page
  without losing exercise state.

JSDoc header states the rule: "Figured bass names intervals above the bass.
Never use 'inversion' in hint prose. See `docs/music-theory-canon.md` and
`AGENTS.md` (theory-sensitive changes require a distinguishing example)."

### Server payload: `targets.py` required-interval-numbers field

`apps/exercises/harmonization/targets.py` already computes
`derive_required_notes()` → `requiredUpperPcs`/`requiredNoteNames` for every
harmonization target, and `harmonization_grader_logic.js` already treats
`target.requiredUpperPcs` as ground truth for grading. Extend the same
`targets.py` payload with `requiredIntervalNumbers` — the generic interval
numbers (not pitch classes) that `required_numbers()` marks essential for this
target's `voiceCountPolicy` — and have `buildHarmonizationHints` read that
field directly instead of re-deriving essential/omittable status from a
client-side port of `TABLE`/`required_numbers`. This removes the risk of the
hint telling a student a tone is "essential" while the grader, reading
`requiredUpperPcs` for the same target, enforces a different set.

### Sync test

`apps/exercises/tests/test_js_figured_bass_hints_sync.py` asserts the JS
`_SHORTHANDS` equals its Python counterpart
(`apps/exercises/harmonization/figures.py:_SHORTHANDS`). Python remains the
source of truth; JS drift fails CI. Follow the `unit_allowed_answers.js`
precedent already in this codebase (`build_unit_allowed_answers` management
command generates the JS file from Python, and
`test_unit_allowed_answers.py:test_generated_js_matches_loader` regenerates
and diffs) rather than hand-authoring two independent literal tables — no
existing test in this suite hand-mirrors a Python structure and asserts
equality against a separately-authored JS literal, so codegen-and-diff is the
safer, already-proven mechanism here.

### Render-layer wiring: `exercise_sheet_status.js:_renderHintControls`

Before building `allSteps = [instructions.help, ...instructions.hints]`, branch
on `definition.analysisType`:

- `figured_bass` → `allSteps = buildHarmonizationHints(definition, "figured_bass")`
  in harmonization mode, or `buildIdentificationHints(definition, "figured_bass")`
  in identification / chorale_identification modes. Fall back to the existing
  static `ExerciseInstructions[mode].hints` if the helper returns `[]` — when
  this fallback fires, emit a dev-only `console.warn` (matching the existing
  `exercise_context.js:404,408` pattern) naming the exercise id and analysisType,
  so a large silent shift to the legacy generic-table hint experience is
  visible in the console during QA rather than only discoverable by chance.
  Expected population hitting this fallback: exercises whose
  `harmonizationTargets` are empty or absent (pre-UMTO/legacy exercises) —
  should shrink over time and not apply to newly generated exercises.
- `figured_bass_unabbreviated` → `allSteps = buildHarmonizationHints(definition, "figured_bass_unabbreviated")`
  in harmonization mode, or `buildIdentificationHints(definition, "figured_bass_unabbreviated")`
  in identification / chorale_identification modes. Same fallback/logging rule.
- All other modes → unchanged static path.

No change to mode detection in `exercise_definition.js`. No UMTO/data-model
change beyond the additive `requiredIntervalNumbers` field above. No
`recompute_harmonization_targets` run for existing exercises — new exercises
get the field going forward; existing exercises without it fall back to the
static hints per the rule above until reprocessed.

### Why not a client-side JS port of the required-tones algorithm

The brainstorm originally locked a client-side port (JS mirrors of `TABLE` +
`required_numbers`, sync-tested vs Python) on the reasoning that server-side
compute would require a data-model change, a recompute run, and would
hardcode one hint language. On review, this compares unfavorably against a
narrower option that wasn't weighed: **extending the existing `targets.py`
payload** (which already computes the identical Python algorithm, and already
ships `requiredUpperPcs`/`requiredNoteNames` to the client for every target)
with one more derived field. That option gets the "no data migration, no
recompute run" properties of the client-side approach — it's an additive,
backward-compatible field on the same target-building path — while avoiding a
second independent implementation of `required_numbers()`'s TABLE lookup,
collision-resolution (`normalize`/`_build_index`), and no-realizable-voice-count
fallback logic in JS, all of which the grader-trusted Python already handles
correctly. Client-side compute is kept for `_SHORTHANDS`/`expandFigure` (a
simple, low-risk lookup with no voice-count branching) and for hint-template
assembly generally; only the required-tones essential/omittable determination
moves to reading a server-provided field.

## Hint content per surface

Notation: **essential intervals plain; omittable named tones in parens;
optional octave doubling marked `[+8]`.** These are deliberately distinct
markers — a parenthesized tone is one of the figure's own named intervals that
the student may drop at this voice count; `[+8]` is an *added* tone (doubling
the bass an octave up) that was never a named requirement of the figure in the
first place. Collapsing both under one parenthesis convention would leave a
student unable to tell, from the notation alone, whether a given digit means
"you may omit this" or "you may additionally double this." Essential/omittable
status is read directly from the target's server-provided
`requiredIntervalNumbers` (see Architecture, above) — not recomputed
client-side. The rule taught to the student: "the plain numbers are the ones
you must keep; the parenthesized ones you may drop in sparse texture; `[+8]`
means you may double the bass an octave up in four parts."

Figures are displayed **below the staff**; they name intervals **above the
bass**.

Worked examples (data-driven; values verified directly against
`apps/exercises/harmonization/figure_realization.py:required_numbers()`,
2026-07-03 review):

| Figure | 3–4 part exercise | 2–4 part exercise | Notes |
|---|---|---|---|
| `6` | `6-3-[+8]` | `6-(3)-[+8]` | 6 essential; 3 omittable only at 2 voices |
| `6/4` | `6-4-[+8]` | `6-4-[+8]` | no 2-voice row; both essential |
| `7` | `7-3-(5)-[+8]` | `7-(5)-(3)-[+8]` | 7 essential always; 3 also essential at 3-4 voices, omittable only at 2 voices; 5 omittable below 4 voices |
| `6/5` | `6-5-(3)-[+8]` | `6-5-(3)-[+8]` | 6,5 essential; 3 omittable |
| `4/3` | `6-(4)-(3)-[+8]` | `6-(4)-(3)-[+8]` | 6 essential; 4,3 each droppable in some 3-voice alt |
| `4/2` | `4-2-(6)` | `2-(6)-(4)` | 2 essential always; 4 also essential at 3-4 voices, omittable only at 2 voices; no `[+8]` under a 2nd/9th (table invariant) |

### A. Harmonization, abbreviated (`analysisType = figured_bass`)

1. **Help:** "Each measure shows a figured-bass symbol **below the staff**. The
   figures name **intervals above the bass** — count up from the bass note to
   find those pitches, then press Lock Chord. Parentheses mark named tones you
   may drop in sparse texture; `[+8]` means you may double the bass an octave
   up in four parts."
2. **Hint 1 (per-figure, data-driven):** for each distinct figure in the
   exercise, the essential/omittable/doubling line from the table above
   (essential/omittable read from the target's `requiredIntervalNumbers`),
   prefixed by the abbreviated figure and `→`.
3. **Hint 2:** "Count from the bass: 3 = two staff steps up, 5 = four steps,
   6 = five steps, 7 = six steps. The plain numbers are the ones you must
   keep; the parenthesized ones you may drop; `[+8]` you may add."
4. **More info:** the Gettysburg URL, rendered as a link (see Architecture,
   above) — opens in a new tab so the student doesn't lose exercise state.

### B. Harmonization, unabbreviated (`analysisType = figured_bass_unabbreviated`)

1. **Help:** "This exercise uses **unabbreviated figures** — every interval
   above the bass is written, including the octave (8). The figures appear
   **below the staff**. Read each number as a generic interval from the bass
   and play those pitches."
2. **Hint 1 (per-target):** reads `harmonizationTargets[i].figures` directly
   (already the fully-expanded interval list — `expand_figure_string` is
   idempotent on already-unabbreviated figures, so no separate raw-figure
   field is needed; e.g. a target with figures `["8","6","3"]` → `8/6/3`
   displayed as `[+8]-6-3`). Mark the doubling 8 with `[+8]`, distinct from a
   dropped/omittable tone.
3. **Hint 2:** "The 8 is the bass doubled at the octave — optional. The other
   numbers are the intervals above the bass you must sound."
4. **More info:** the Gettysburg URL, rendered as a link (see Architecture,
   above) — opens in a new tab so the student doesn't lose exercise state.

### C. Identification / chorale_identification, abbreviated

1. **Help:** "Choose the **abbreviated** figure. Abbreviations drop redundant
   intervals — `6` stands for `6-3`, `7` for `7-5-3`, `6/4` for `6-4`, `4/2`
   (or `2`) for `6-4-2`. The figure names intervals above the bass, not a
   chord name."
2. **Hint 1:** expansion table for the distinct figures actually present in
   the exercise (from slices), via `expandFigure`. Plain expansion; no
   essential/optional (the student labels, does not realize).
3. **More info:** the Gettysburg URL.

### D. Identification / chorale_identification, unabbreviated

1. **Help:** "Choose the **unabbreviated** figure — list every generic
   interval above the bass, including the octave (8). A triad with the third
   in the bass is `8/6/3`, not `6`."
2. **Hint 1:** per-slice raw stacks from `raw_figured_bass`.
3. **More info:** the Gettysburg URL.

### E. Roman-numeral identification reframed (solfège)

1. **Help:** "Name the Roman numeral by where the chord sits in the key. A
   **I** chord = 1, 3, 5 of the key = **do-mi-sol**. A **I6** = the third of
   the chord in the bass = 3, 5, 1 = **mi-sol-do**. A **IV** = 4, 6, 1 =
   **fa-la-do**. Uppercase = major, lowercase = minor, ° = diminished,
   + = augmented."
2. **Hint 1:** "Find the bass, count scale degrees from the tonic to name the
   Roman numeral. If the bass isn't the root, the figure tells you which chord
   tone is in the bass: `6` = third in the bass, `6/4` = fifth in the bass."
3. **Hint 2:** "Decide quality from the stacked thirds, then match
   major/minor/diminished/augmented to the case and symbol."
4. No "inversion" anywhere — "third in the bass" / "fifth in the bass" /
   "seventh in the bass."

## Removing "inversion" from student-facing text

### `feedback_catalog.js:28` + `docs/feedback_catalog.md:44`

Rephrase the body from "Right chord — but the bass doesn't match the figure's
inversion." to:

> "Right chord — but the bass doesn't match the figure. The figure names
> intervals above the bass; check which chord tone is in the bass."

Keep the internal feedback *key* `wrong_inversion` and the grader reason
`wrong_bass` (internal, not student-facing). Renaming the key is churn with no
student benefit; noted as an optional follow-up.

### `music21_builder.py:76-78` — triad identification answer choices

Scope: this change applies to the **triad** `inversion.choices`/`answer`
lambdas at lines 76-78 only. Change the triad identification answer choices
from `["root position", "first inversion", "second inversion"]` to
`["root position", "third in the bass", "fifth in the bass"]`.

The seventh-chord entry (lines 89-91) already reads
`["root position", "6/5", "4/3", "4/2"]` — it never said "inversion" and needs
no change here, and the grader-side synonym map below applies only to the
triad labels since the seventh labels never had an "inversion" form to be
synonymous with.

**Data impact:** existing triad-identification exercises store the old labels
as answer keys. Two options:

- (a) A one-time migration script rewriting stored answer keys to the new
  labels.
- (b) A grader-side synonym map accepting both old and new labels.

**Recommendation: (b).** Backward-compatible, no recompute, old exercises keep
working. The synonym map lives alongside the identification grader and is
removed once all legacy exercises are regenerated (tracked follow-up).

### Unit titles / labels

Adopt the branch-track phrasing already in
`music_theory_taxonomy_with_branches.json:209,473`:

- "First inversions" → **"Chords with the Third in the Bass"**
- "Second inversions" → **"Chords with the Fifth in the Bass"**

Files affected:

- `music_theory_taxonomy.json:209,212,213`
- `music_theory_taxonomy.html:116,118`
- `apps/exercises/forms.py:47,49,93-94`

The A2/A3 form dropdown labels already use "6/3 chords"/"6/4 chords" — keep
those. Internal skill-tag ids (`unit:10_inversions_first`,
`unit:12_inversions_second`) are internal and unchanged.

### Generated exercise titles / tags

In `generate_roman_from_clausulae.py` and
`generate_harmonization_from_clausulae.py`:

- `"First-Inversion Cadence in {key}"` → `"Third-in-the-Bass Cadence in {key}"`
- `"Second-Inversion Cadence in {key}"` → `"Fifth-in-the-Bass Cadence in {key}"`
- Tag `Inversions_First` → `Third_in_Bass`; `Inversions_Second` → `Fifth_in_Bass`
- Unit-title strings `"Unit {unit} — First Inversions (Roman Numerals)"` →
  `"Unit {unit} — Third in the Bass (Roman Numerals)"` (and the harmonization
  analogue).

Regeneration affects only newly generated exercises; existing exercise titles
stored in the DB are not auto-rewritten (follow-up).

### Keep untouched

- Interval inversion (`unit:4_interval_inversion`, `interval_inversion`) — a
  distinct music-theory concept.
- Pitch-class inversional symmetry (unit 31, "Symmetry & inversional axes").
- music21 `rn.inversion()` API calls.
- Internal Python comments (e.g. `figures.py` `# First-inversion triad`).
- Dev-only `console.warn` strings in `exercise_context.js:404,408`.
- Internal skill-tag ids.

## Testing

- **Sync test** (`test_js_figured_bass_hints_sync.py`): JS `_SHORTHANDS` equals
  its Python counterpart. Run in CI (see Architecture / Sync test above for the
  codegen-and-diff mechanism).
- **Unit** (`targets.py`): a new test asserting a built target's
  `requiredIntervalNumbers` matches `required_numbers()` called directly for
  that target's prototype key and `voiceCountPolicy` — this is what actually
  guards the hint against diverging from the grader, since both now read the
  same server-computed field.
- **Golden** (`theory_golden/figured_bass_hints.json`): sample exercises, one
  per `analysisType` × mode, → expected hint arrays. Locks the hint prose.
- **Grader synonym test:** identification grader accepts both old and new
  inversion labels (triad only — see "music21_builder.py — triad
  identification answer choices" above).
- **Feedback-catalog test:** the rephrased body contains no "inversion".
- **Distinguishing example (per AGENTS.md canon rule):** `6/4` at 2 voices =
  not realizable → both 6 and 4 essential in `requiredIntervalNumbers`, vs `6`
  at 2 voices = 6 essential, 3 omittable. This separates the correct rule (the
  TABLE's per-voice-count cells) from the plausible shortcut "all named
  intervals are required," and is now exercised against the `targets.py`
  payload rather than a client-side port.

## Risks

- **JS/Python table drift.** Mitigated by the sync test; Python remains source
  of truth and the AGENTS.md expert-review rule still applies to TABLE changes.
- **Answer-choice synonym map** accepting old + new inversion labels could
  mask a future regression that re-introduces the old labels. Mitigated by a
  test asserting new labels are the canonical form and old labels are accepted
  only as synonyms.
- **Existing generated exercise titles** in the DB still say "First Inversion."
  Acceptable for v1 (titles are not hint prose); re-titling has an owner and a
  trigger date — see Non-goals.
- **Figured-bass hint prose is English-only.** No i18n surface exists today;
  not in scope.