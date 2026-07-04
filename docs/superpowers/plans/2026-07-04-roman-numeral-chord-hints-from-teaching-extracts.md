# Plan — RN / chord student hints from theory-teaching-extracts

Status: **PROPOSAL — awaiting product-owner sign-off.** Do not implement
the gated items (§4) until approved. The single un-gated demonstrative
spike (§5) may land on this branch, clearly labeled.

Source material: sibling repo `theory-teaching-extracts` (Dr. Amanda Heim,
MUS 141), two extracted lesson packages:
- `RN and Seventh Chord Presentation/` (20 slides) — Roman numerals + sevenths
- `Triad Intro Presentation/` (18 slides) — triads + figured-bass intro

Each package's `lesson-content.json` is the verbatim, course-authored source
of truth; `notation` objects are renderer-agnostic, VexFlow-ready
(`keys:"c/4"`); `circle-of-thirds.js` is a zero-dep ESM SVG component.
Read but not modified.

Existing hint surface in HarmonyLab:
- `lab/static/js/src/config/exercise_instructions.js` — static per-mode
  `help`/`hints` arrays (playback, harmonization, identification,
  chorale_identification, …).
- `lab/static/js/src/config/figured_bass_hints.js` — dynamic per-exercise
  builders: `buildHarmonizationHints`, `buildIdentificationHints`
  (figured-bass), `buildRomanIdentificationHints` (RN). Reads
  `definition.getProblems()` / `getHarmonizationTargets()`.
- Rendered by `exercise_sheet_status.js::_renderHintControls` as a "? Hint"
  button revealing text steps in a panel. Steps are plain text
  (`.text(s.text)`); only the "More info" link is HTML (html flag).
- `lab/static/js/src/config/feedback_catalog.js` — grade feedback IDs
  (`*.grade.*`), emitted via `feedbackService.emit`. Distinct from the
  hint/instruction system but governed by the same doc-requirement rule.

---

## 1. Hint improvements (RN + chords)

Scope: the **hint/instruction** system (`exercise_instructions.js` +
`figured_bass_hints.js`), NOT grade feedback. Grade-feedback IDs are
listed in §6 only where a deck-derived wording could sharpen an existing
diagnostic copy; those are separate, lower-priority, and still gated.

Pedagogical principle: every proposed wording is **quoted/paraphrased from
the deck** so on-screen hints match the language students hear in MUS 141.
Theory-checks cite `docs/music-theory-canon.md` and the
`figure_realization.py` `TABLE`. Apparent contradictions are **flagged for
the product owner** (§3), not resolved silently.

Notation inline rendering: the current hint panel renders plain text only
(see `exercise_sheet_status.js:377-399`). Rendering a `notation` object
inside a hint step is **gated** (needs an HTML step + a notation container +
the rendering approach decision in §2.4). For each item below I mark
whether the illustration is *text-only* (safe) or *inline-notation* (gated).

### Priority (i) — triad quality (major / minor / diminished / augmented)

#### Item T1 — sharpen the quality-diagnostic copy with the deck's two-step rule
- **Existing:** `feedback_catalog.js` `harmonization.grade.incorrect.wrong_quality`
  body: `"Close — check the chord quality (major, minor, diminished?)."`.
  Also echoed in RN hint `buildRomanIdentificationHints` tail:
  `"Uppercase = major, lowercase = minor, ° = diminished, + = augmented."`.
- **Proposed wording (paraphrased from Triad slide 11 `how-to-determine-quality`):**
  > "Find the quality in two steps: first the bounding fifth (root→fifth),
  > then the lower third (root→third). A perfect fifth + major third = major;
  > perfect fifth + minor third = minor; diminished fifth = diminished;
  > augmented fifth = augmented. Case tells you the same thing in the label:
  > uppercase = major, lowercase = minor, ° = diminished, + = augmented."
- **Source:** Triad `lesson-content.json` slide 11 bullets (verbatim):
  *"ID the bounding fifth / ID the lower third / If the bounding fifth is
  perfect, the triad will be either major or minor, depending on the quality
  of the lower third / If the bounding fifth is diminished … / If augmented …"*;
  and slide 10 table (Diminished = m3/m3, Minor = m3/M3, Major = M3/m3,
  Augmented = M3/M3). RN deck slide 10 gives the case conventions.
- **Pedagogical justification:** the app currently only tells students
  *which symbol* maps to *which quality*; the deck's two-step procedure
  tells them *how to find* the quality from the chord tones — the missing
  step for a student who can't yet hear/see quality.
- **Illustration:** `notation` id `s10-triads-built-from-a` (Triad deck,
  four qualities stacked on A) or RN `s3-built-up-from-a`. Inline rendering
  **gated**; text-only fallback names the four "built up from A" spellings
  (A-C-E♭, A-C-E, A-C♯-E, A-C♯-E♯) — safe now.
- **Theory-check:** agrees with canon §"Interval quality" (generic interval
  + chromatic size determine quality) and the deck's quality table. The
  bounding-fifth rule is first-principles tertian construction. **No
  contradiction.**
- **Surfaces:** (a) RN identification hint tail (text, safe now); (b) the
  `wrong_quality` grade copy (text, safe now but is a grade-feedback
  change — see §6). Recommend shipping (a) first.

#### Item T2 — add a "name the root and the quality" worked example to RN hints
- **Existing:** `buildRomanIdentificationHints` lists the exercise's
  distinct numerals and a `Do-Mi-So`-style solfège mapping, but gives no
  named example of the *form* "g minor / a diminished / F Augmented / F#
  Major" a student should produce.
- **Proposed wording (paraphrased from Triad slide 12 `naming-root-and-quality`):**
  > "Name the chord as **root + quality** — e.g. 'g minor', 'a diminished',
  > 'F augmented', 'F♯ major' — then place that chord on its scale degree
  > to get the Roman numeral."
- **Source:** Triad slide 12 bullets (verbatim): *"When describing the
  quality of a triad, we do so by naming the root and the quality / g minor
  / a diminished / F Augmented / F# Major."*
- **Pedagogical justification:** separates the two sub-skills (identify the
  chord, then identify its scale-degree slot) the app's single-step "name
  the RN by where it sits" glosses over.
- **Illustration:** `notation` ids `s12-examples-bass-clef`,
  `s12-examples-treble-clef`. **Gated** inline; text-only safe now.
- **Theory-check:** naming is neutral w.r.t. canon. **No contradiction.**

### Priority (ii) — seventh-chord qualities + Roman numerals

#### Item S1 — add seventh-chord RN coverage (currently absent)
- **Existing:** `buildRomanIdentificationHints` `_MAJOR_DIATONIC_TRIADS`
  table covers triads **only** (I, ii, iii, IV, V, vi, vii°). Seventh-chord
  RNs (I⁷, ii⁷, V⁷, vii°⁷, …) get no per-numeral worked example. The
  static `identification`/`chorale_identification` help also stops at triads.
- **Proposed wording (paraphrased from RN slide 16 `seventh-chord-quality-1`
  + slide 17 `seventh-chord-quality-2`):**
  > "For a seventh chord, name quality in two parts: the triad quality
  > (root-third-fifth, ignore the seventh), then the seventh (root→seventh).
  > In D major the diatonic sevenths are: I = Major-Major (maj⁷), ii/iii =
  > minor-minor (m⁷), IV = Major-Major (maj⁷), V = Major-minor (dominant
  > ⁷), vi = minor-minor (m⁷), vii° = diminished-minor (m⁷♭₅). Roman-numeral
  > case follows the triad quality, same as for triads."
- **Source:** RN slide 16 bullets (verbatim): *"first identify the quality
  of the triad, ignoring the seventh / Then describe the quality of the
  seventh (root up to seventh)"*; slide 16 `notation`
  `s16-scale-degree-seventh-qualities` carries the `qualityPair` values
  (Major-Major, minor-minor, Major-minor, diminished-minor) per degree;
  slide 17 table gives lead-sheet symbols (Cmaj7, C7, Cm7, Cø7, C°7).
- **Pedagogical justification:** fills a real gap — students get no
  seventh-chord RN help today — and matches the deck's own two-part
  description, which is the course's chosen vocabulary.
- **Illustration:** `notation` id `s16-scale-degree-seventh-qualities`
  (D-major sevenths with qualityPair labels) or `s14-scale-degree-sevenths`.
  **Gated** inline; text-only safe now.
- **Theory-check:** diatonic seventh qualities (I maj7, ii7, iii7, IV maj7,
  V7, vi7, viiø7) are first-principles tertian stacking; the deck's
  `derivationNote` asserts the same. **No contradiction with canon.**
- **Surfaces:** RN identification hint (text, safe now).

#### Item S2 — "the seventh is a seventh above the root" framing
- **Existing:** no hint frames *why* it is called a seventh chord.
- **Proposed wording (paraphrased from RN slide 14 `seventh-chords-intro`):**
  > "A seventh chord adds the interval of a seventh above the root to a
  > triad. Like triads, one is built on every scale degree."
- **Source:** RN slide 14 bullets (verbatim): *"Seventh chords are called
  as such because they contain the interval of a seventh above the root of
  a triad / Seventh chords can be generated from each scale degree, just
  like triads."*
- **Theory-check:** trivially first-principles. **No contradiction.**
- **Surface:** RN identification hint (text, safe now).

### Priority (iii) — figured-bass reading

#### Item F1 — "the figure names intervals above the bass" reinforcement
- **Existing:** `figured_bass_hints.js` `buildHarmonizationHints` `help`
  already says *"The figures name intervals above the bass — count up from
  the bass note…"* and the static `harmonization` help agrees. This is
  already correct; **no wording change needed**, only a citation record.
- **Deck anchor:** Triad slide 15 `figured-bass-intro` (verbatim): *"Figured
  bass … designate the intervals to be played above the bass"*; slide 16
  (verbatim): *"the intervals in figured bass are the generic intervals from
  the bass. The note above the bass comes from the key unless indicated
  otherwise."*
- **Theory-check:** agrees with canon §"Figured bass" (labels intervals
  above the bass, not RN/inversion names) and the user's standing standard
  (memory: "say 'interval above bass', not 'inversion'"). **No
  contradiction** — current copy already matches the deck. ✅

#### Item F2 — alterations rule, deck wording
- **Existing:** `figured_bass_hints.js` `_isAlteredToken` handles `#,b,n,°,+`
  but the *student-facing* hint prose never states the alteration rule. The
  static `harmonization` hint mentions accidentals only in passing.
- **Proposed wording (paraphrased from Triad slide 16
  `figured-bass-alterations`):**
  > "An accidental next to a number adds that accidental to that generic
  > interval above the bass. A '+' (or strikethrough) raises the interval;
  > a '-' lowers it. The note otherwise comes from the key signature."
- **Source:** Triad slide 16 bullets (verbatim): *"Any accidental next to a
  number indicates adding that accidental to that generic interval above the
  bass / A number with a + (or strikethrough) should be raised / A number
  with a - should be lowered."*
- **Pedagogical justification:** students see `#3`, `5°`, `4+` figures with
  no on-screen explanation of the alteration symbols.
- **Theory-check:** agrees with canon §"Interval quality" (altered
  intervals like `5°`, `4+` are always required) and `figure_realization.py`
  (`_parse_numbers` treats `#,b,n,°,+` as altered → required). **No
  contradiction.** Note: the deck writes the alteration *rule*; the app's
  `TABLE` encodes the *realization* (altered = required). They are
  complementary, not conflicting.
- **Surface:** figured-bass harmonization + identification hints (text,
  safe now).

#### Item F3 — `8/5/3` full-stack shorthand — **DECISION: keep as is**
- **Existing:** the app's `figure_realization.TABLE` uses `5/3` for root
  position and **drops the 8** ("8 (octave) doubles the bass and is dropped
  at the pitch-class level — it never appears below", `figure_realization.py`
  line 16). Hints therefore say "no symbol = 1-3-5". The deck writes the
  **full stack** `8/5/3` and states (Triad slide 17, verbatim): *"8/5/3
  triads are indicated by NO numbers in shorthand figured bass."*
- **Product-owner decision (C1):** **keep the app wording as is.** Do not
  introduce `8/5/3` into hints. The app's `5/3` convention is correct and the
  `TABLE` is unchanged. No F3 action item.

### Priority (iv) — "circle of thirds" root-finding mental model

#### Item W1 — circle-of-thirds root-finding framing — **DECISION: ADD to grading hint**
- **Existing:** the app does **not** teach the circle-of-thirds wheel for
  RN identification. Per recent commit `9ed9442e` ("RN hints taught
  third-stacking, not this app's actual method"), `buildRomanIdentificationHints`
  was rewritten to use a **solfège / scale-degree pattern** (`Do-Mi-So = I`,
  `Mi-So-Do = I6`, …) and **deliberately dropped** third-stacking. The
  result is the current cumbersome per-syllable wording.
- **Product-owner decision (C2):** **include the circle-of-thirds.** The
  wheel is always the same order (C-E-G-B-D-F-A), which is easy for
  students to remember — and is distinct from "stacked thirds" (the
  construction-only framing `9ed9442e` removed). Re-introducing the
  **wheel** (not the stacked-thirds construction) is wanted.
- **Proposed wording (paraphrased from RN slide 15
  `seventh-chords-root-finding` + Triad slide 8):**
  > "Find the root with the **circle of thirds** — the letters always run
  > in the same order (C-E-G-B-D-F-A) no matter the chord. The chordal
  > root is the pitch furthest counter-clockwise before the large gap of a
  > fourth; from the root, the next two clockwise stops are the third and
  > the fifth (a seventh chord adds one more stop). That root's scale
  > degree is your Roman numeral; the chord's quality is the case/mark."
- **Source:** RN slide 15 bullets (verbatim): *"Finding the root of a
  seventh chord works the same way as with a triad / Use the circle of
  thirds / The pitch furthest counter-clockwise is the chordal root"*;
  Triad slide 8 (verbatim): *"The root … will be the furthest pitch
  counter-clockwise before the large gap of a fourth."*
- **Pedagogical justification:** the wheel is a single, memorable, reusable
  mental model (same order every key) — lighter than the current
  per-syllable solfège list. Note: this does **not** restore the
  "stacked-thirds" construction `9ed9442e` removed; the wheel and
  stacked-thirds are different framings, and only the wheel is added.
- **Illustration:** the `circle-of-thirds` diagram component
  (`mode:"thirds"`, `root`+`chordSize`) renders the wheel inline.
  Inline rendering is **gated** (needs the HTML-step + notation/container
  work from §2.4). Text-only wheel reference ("C-E-G-B-D-F-A, root = furthest
  counter-clockwise before the gap of a fourth") is **safe now**.
- **Theory-check:** the wheel is consistent with canon §"Interval quality"
  (generic-interval counting) and with tertian construction. The grader
  reads a syllable pattern (`analyze.js`); the wheel is a *student-facing
  hint* and does **not** change grader logic, so there is no risk of teaching
  a model the grader doesn't reward — the wheel yields the same root the
  solfège method yields. **No contradiction.**
- **Surface:** RN identification `buildRomanIdentificationHints` (text,
  safe now); inline wheel **gated**. Keep the existing solfège line as a
  secondary hint step (it still matches the grader's mental model); lead
  with the wheel.
- **Lesson page:** the static lesson page (§5) still carries the live
  interactive wheel SVG from `circle-of-thirds.js`; the grading hint carries
  the text wheel reference.

### Item R1 — "Roman numerals have no significance without a key" (new)
- **Existing:** no hint tells students to identify the key first.
- **Proposed wording (paraphrased from RN slide 9 `roman-numerals-2`):**
  > "First, identify the key — Roman numerals have no meaning without one.
  > Then find the chord's scale degree (that's the numeral) and its quality
  > (that's the case/mark)."
- **Source:** RN slide 9 bullets (verbatim): *"First: indicate the key! /
  Roman numerals have no significance without a key!"*
- **Theory-check:** agrees with canon §"Figured bass" framing (identify the
  sounding bass/key context first). **No contradiction.**
- **Surface:** RN identification hint (text, safe now).

---

## 2. Lesson / explanation pages (from the sibling packages)

Two candidate pages, one per package. Both are **net-new** in this repo
(MAP.md confirms: no `lessons/` dir, no lesson view/URL). Per MAP.md the
two analogues are (a) `RequirejsTemplateView` app page (routed via
`lab/urls.py`) or (b) static HTML under `lab/static/reference/` (no
Vite/Django templating, loads own libs). The package `index.html` is
closest to (b).

### Recommended lowest-risk first page (demonstrative step — §5)

**Page: "Triad qualities & the circle of thirds" — static reference HTML.**

- **Drawn from:** Triad Intro package, slides 2–13 (major scale → diatonic
  circle → choose three non-adjacent → root finding via the large gap → four
  qualities → naming).
- **Integration analogue:** **(b) static `lab/static/reference/` HTML**,
  mirroring the package's own `index.html`. **Why:** touches **no** route,
  **no** view, **no** UMTO, **no** `vite.config.js` entry, **no** adapter.
  Lowest risk; reversible by `rm`. Same pattern as existing
  `lab/static/reference/unit2/meter-signatures.html`.
- **JSON load:** **`window.__LESSON_DATA__` injection is NOT available** in a
  static file outside Django templating. For the static spike, **fetch the
  JSON via a relative path** (`./lesson-content.json`) — the same way the
  package's `index.html` does it. This stays inside `lab/static/reference/`
  and uses no Django route. (MAP.md pattern (a) `$.getJSON` is dev-only and
  routed; we avoid it.)
- **Notation rendering:** for the spike, **drive `Vex.Flow` directly** from
  the lesson JSON's VexFlow-native `{keys:"c/4", duration:"q"}` notation
  objects (the package's own `drawIllustrativeVexflow` does a minimal
  version; the RN package `render-lesson.js`'s `renderNotationPlaceholder`
  is the swap point). **Why not the adapter:** the adapter takes the HL
  "processed score" model (`{step,alter,octave}`, `measures[].staves…`),
  NOT VexFlow-native keys; using it requires a lesson-JSON → processed-score
  transform (mirror `umto_score_converter.js`). That transform is the
  gated, higher-risk path (§2.4). The spike bypasses it.
- **VexFlow source:** the spike loads VexFlow the same way the package
  demo does — a local copy under `lab/static/reference/assets/` or the
  repo's vendored `lab/static/js/lib/vexflow.js` copied/symlinked into the
  reference dir (static pages can't use the `vexflow` Vite alias). **Gated
  choice** (see §5): for a throwaway spike, a CDN `<script>` is acceptable
  to prove the rendering path; for anything permanent, use the vendored
  copy. The spike is throwaway.
- **circle-of-thirds.js:** **used.** Import the **Triad (extended) copy**
  as the canonical one (§3 reuse decision). In the static spike, load it as
  a relative-path ESM module (`<script type="module" src="./circle-of-thirds.js">`).
- **URL/placement:** `lab/static/reference/triads-circle-of-thirds/index.html`
  (+ sibling `lesson-content.json`, `circle-of-thirds.js`, `render-lesson.js`,
  `lesson.css` flat in the same dir). Served by Django's static handler at
  `/static/reference/triads-circle-of-thirds/index.html`. No `lab/urls.py`
  change.
- **CSS:** `<link rel="stylesheet" href="./lesson.css">`; override
  `--lesson-*` custom properties in an inline `<style>` to match
  `apps/student/static/student/tokens.css` values (`--teal`, `--surface`,
  `--text`, `--radius`, `--font-ui`). Not processed by Vite (consistent with
  MAP.md "CSS via `<link>`, not JS imports").
- **UMTO-neutrality:** this is **not an exercise** — no `Exercise` row, no
  `save_umto_exercise`, no grading. UMTO rules do not apply. The "don't bloat
  `views.py`" rule is irrelevant: no view is added.

### Candidate page 2 (gated — after sign-off)

**Page: "Roman numerals & seventh chords" — routed app page.**

- **Drawn from:** RN + Seventh Chord package, slides 6–20 (RN intro →
  quality conventions → analyzing triads → seventh chords → qualities →
  using figures + RN + lead sheet). May also pull the worked analysis
  passage (`s11-13-analyzing-triads-passage`, G major: I I V6 I IV6 I6 V I)
  and the C-major progression (`s18-20-c-major-progression`).
- **Integration analogue:** **(a) `RequirejsTemplateView` app page**, routed
  via `lab/urls.py`, template extends `lab/templates/__base.html`, Vite
  entry in `vite.config.js rollupOptions.input`. **Why:** reuses vendored
  VexFlow (via the `vexflow` alias), the `app/` alias, and tokens.css —
  things the static analogue can't reach cleanly. This is the right
  end-state for a permanent, app-integrated lesson.
- **JSON load:** **`window.__LESSON_DATA__ = {{ data|safe }}`** injected
  from a template context (MAP.md pattern (b)). The view side **must be a
  focused service**, not logic in `lab/views.py` (AGENTS.md): e.g. a thin
  `apps/lessons/services.py` that loads + validates the JSON, called by a
  minimal `RequirejsTemplateView` subclass that only sets `extra_context`.
  **Gated — needs the service-extraction design spec.**
- **Notation rendering:** **lesson-JSON → processed-score transform** feeding
  `VexFlowAdapter.render(score, renderer, opts)`, mirroring
  `umto_score_converter.js`'s `convertChordalUMTOToProcessedScore`. This
  keeps a single rendering code path (the adapter) for both exercises and
  lessons. **Gated — needs adapter/transform design spec** (§2.4).
- **circle-of-thirds.js:** imports the same canonical Triad copy (§3).
- **URL/route:** `/lessons/roman-numerals-sevenths/` (new). **Gated — new
  route, must be designed.**
- **CSS:** `{% block css_extra %}<link … tokens.css>{% endblock %}` in the
  template; `lesson.css` via `{% static %}`; `--lesson-*` overrides mapped
  to tokens.css.

### 2.4 Notation-rendering approach decision (gated)

Two paths, decide per page:

- **(A) Direct Vex.Flow** from the lesson JSON's native `keys`/`duration`.
  Pro: no adapter changes, no transform, fastest. Con: second rendering
  code path (lessons vs exercises); bypasses the adapter's `voiceColors`,
  `playedNoteIds`, `analyzeConfig` features (fine for static lessons, which
  are non-interactive).
- **(B) Lesson-JSON → processed-score transform → `VexFlowAdapter.render`.**
  Pro: one rendering path. Con: new converter module (mirror
  `umto_score_converter.js`), possible new adapter entry point for
  non-exercise scores, more surface area.

**Recommendation:** **(A) for the static spike** (§5) and for any
*non-interactive* lesson page; **(B) only if/when** a lesson page needs the
adapter's interactive features (highlighting, played-note colors). (B) is
gated behind a design spec and product-owner sign-off. **State this in the
plan, do not implement (B) now.**

---

## 3. Reuse vs divergence — `circle-of-thirds.js`

Two copies exist:
- RN package: plain (`mode:"seconds"` + `mode:"thirds"`).
- Triad package: **extended** — adds `customCycle` (solfège labels) and
  `hideNonChordTones`. Strict superset, backward-compatible.

**Recommendation:** adopt the **Triad copy as canonical**. Place it once at
`lab/static/js/src/lessons/circle-of-thirds.js` (under the `app/` alias →
`app/lessons/circle-of-thirds`). Both lesson pages import that one file;
the RN page gets the solfège/custom-wheel features for free. Do **not** keep
two copies in the app. (The sibling repo is read-only; the canonicalization
happens *inside* HarmonyLab. The MAP.md recommendation to copy it back into
the RN package in the sibling repo is out of scope for this task — sibling
is not modified.)

For the static spike (§5), the file is copied into the spike's directory
(relative-path ESM import) since static reference pages can't use the `app/`
alias. If/when the routed app page (candidate 2) ships, it imports
`app/lessons/circle-of-thirds` and the spike's local copy is removed.

---

## 4. Scope gating

### Safe to implement after this plan is approved
- **Hint text-only changes** (T1, T2, S1, S2, F2, R1) in
  `figured_bass_hints.js` / `exercise_instructions.js` + the corresponding
  `docs/feedback_catalog.md` note (these are the **hint/instruction** system,
  not the grade-feedback catalog; the doc-requirement rule still applies —
  update the catalog doc to record the deck provenance).
- **`feedback_catalog.js`/`feedback_catalog.md`** changes for the
  `wrong_quality` grade copy (T1b) — text-only, no new emit path, routed
  via the existing `resolveGradeFeedbackId` diagnostic. Still: per
  `docs/feedback_catalog.md`, add the row and keep the emit via
  `feedbackService.emit`. (Gated only insofar as grade copy is user-facing;
  recommend shipping after the hint changes land first.)
- **Canonical `circle-of-thirds.js` import** (§3) at
  `lab/static/js/src/lessons/circle-of-thirds.js` — pure file copy, no
  wiring, no behavior change until a page imports it.

### Needs a separate design spec (do NOT implement before sign-off)
- Any **new adapter entry point** or the **lesson-JSON → processed-score
  transform** (§2.4 path B). Spec at
  `docs/superpowers/specs/YYYY-MM-DD-lesson-notation-rendering-design.md`.
- Any **new route / `RequirejsTemplateView`** (candidate page 2) + the
  **focused lesson-loading service** (not in `lab/views.py`). Spec at
  `docs/superpowers/specs/YYYY-MM-DD-lesson-page-routing-design.md`.
- Any **inline notation rendering inside a hint step** — needs an HTML
  hint step + a notation container + the rendering-approach decision. Spec
  at `docs/superpowers/specs/YYYY-MM-DD-inline-notation-hints-design.md`.
- Any **figured-bass `TABLE` change** (none proposed; F3 explicitly does
  NOT change the table). Per AGENTS.md, a `theory_golden/figure_realization.json`
  case + `docs/FIGURED_BASS.md` sync would be required — **not triggered
  here**.

### Theory contradictions surfaced for the product owner — RESOLVED
- **C1 — `8/5/3` notation convention. — DECISION: keep app wording as is.**
  The deck writes the full stack `8/5/3` (Triad slide 15/17); the app's
  `figure_realization.TABLE` drops the 8 at the pitch-class level (`5/3`).
  Compatible (the 8 is an optional doubling per canon). Product owner
  chose to keep the app's `5/3` wording. **No `TABLE` change, no F3 action.**
- **C2 — circle-of-thirds vs solfège root-finding. — DECISION: ADD the
  circle-of-thirds wheel to the grading hint.** The deck teaches
  root-finding via the **circle of thirds** ("furthest counter-clockwise
  before the large gap of a fourth"); `9ed9442e` had removed third-stacking
  in favor of a solfège/scale-degree pattern. Product owner: the solfège
  result is cumbersome; the **wheel** (always the same order,
  C-E-G-B-D-F-A) is easy to remember and is **not** the "stacked-thirds"
  construction `9ed9442e` removed — so re-introduce the wheel, keep
  solfège as a secondary step. Action = Item W1 (§1). Grader logic is
  untouched (it still reads a syllable pattern); the wheel yields the same
  root, so no grader-hint mismatch.
- **C3 — seventh-chord diminished symbols (`viiø7` vs `vii°7`). — RESOLVED,
  not a contradiction.** These are **different structures**, not a pair to
  reconcile: `viiø7` = **half-diminished** (diminished triad + minor
  seventh), `vii°7` = **fully-diminished** (diminished triad + diminished
  seventh). They appeared together only because deck slide 17 lists both
  lead-sheet symbol rows side-by-side (`Cø7`/`Cm7(♭5)` and `C°7`/`Cdim7`).
  The grader already distinguishes them: `config/analysis/hChords.js`
  defines `36y` → label `Rø7` ("half-dim. 7") and `369` → label `R°7`
  ("dim. 7") as distinct tetrads. **No blocker for S1** — the deck's
  symbol set matches the grader's. S1 may ship once the text changes land.

---

## 5. Demonstrative spike (the one un-gated step)

The single low-risk, self-contained step that needs no route/UMTO/adapter
change: **drop the Triad package as a static reference page** into
`lab/static/reference/triads-circle-of-thirds/`, loading the package's own
`lesson-content.json` + `circle-of-thirds.js` + `render-lesson.js` +
`lesson.css` via relative paths, swapping `renderNotationPlaceholder` for a
minimal direct-`Vex.Flow` renderer (path A, §2.4), VexFlow from a local
copy or (spike-only) CDN. Mirrors the package's `index.html` 1:1.

**Purpose:** prove the rendering path (JSON → VexFlow + circle-of-thirds
SVG → themed CSS) end-to-end inside the repo, on a branch labeled `spike:`,
without touching any routed/view/UMTO/adapter surface. **If it works**, it
becomes the skeleton for candidate page 1; **if not**, it cost only a
reversible static directory.

**Branch/worktree:** this worktree (`rn-chord-hints-from-extracts`), commit
message prefix `spike(triage):` so it is clearly a throwaway demonstrative
step, not an approved feature.

**This spike is OPTIONAL.** If the product owner prefers to see the plan
land first and decide on the lesson-page approach before any HTML ships,
**stop at the plan** and do not run §5. (The plan doc is the required
deliverable; the spike is permitted, not required.)

---

## 6. Hint/feedback IDs proposed to change or add

### Hint/instruction system (`exercise_instructions.js` + `figured_bass_hints.js`)
| Item | Where it fires | Change | Gated? |
|---|---|---|---|
| R1 | RN identification `help` | add "identify the key first" leading clause | no |
| T1a | RN identification `buildRomanIdentificationHints` tail | replace bare case-list with deck two-step (bounding 5th → lower 3rd) + case legend | no (text) |
| T2 | RN identification hints | add "name root + quality, then place on scale degree" step | no (text) |
| S1 | RN identification `buildRomanIdentificationHints` | add seventh-chord numeral→qualityPair examples (new `_MAJOR_DIATONIC_SEVENTHS` table) | no (text); C3 grader-check first |
| S2 | RN identification `help` | add "seventh chord = triad + a seventh above the root" framing | no |
| F2 | figured-bass harmonization + identification hints | add alteration rule (`#`/`+`/`-`) deck wording | no (text) |
| F3 | figured-bass unabbreviated/abbreviated hints | **no action — keep app `5/3` wording** (C1 decision) | n/a |
| W1 | RN identification `buildRomanIdentificationHints` | **ADD** circle-of-thirds wheel framing as lead step (text safe now; inline wheel gated); keep solfège as secondary step | no (text); inline gated |

### Grade feedback (`feedback_catalog.js` + `docs/feedback_catalog.md`)
| Item | ID | Change | Gated? |
|---|---|---|---|
| T1b | `harmonization.grade.incorrect.wrong_quality` | sharpen body with deck two-step (after hint changes land) | no (text), recommend after §1 |
| (new, optional) | `identification.grade.incorrect.wrong_quality` | if the identification grader reports a `wrong_quality` diagnostic, add a deck-worded copy; else skip | **grader diagnostic must exist** — verify first |

**No** `EVENTS.BROADCAST.NOTIFICATION`, **no** `window.alert`. All hint text
stays in the hint panel; all grade copy stays routed through
`feedbackService.emit` / `resolveGradeFeedbackId`.

---

## 7. First implementation step (recommended)

1. **Sign-off received** on C1/C2/C3 (this revision). C1 = keep `5/3`;
   C2 = add the circle-of-thirds wheel (Item W1); C3 = no blocker (grader
   distinguishes `ø7`/`°7`).
2. Land the **text-only RN identification hint changes** (R1, T1a, T2, W1,
   S1, S2) in `figured_bass_hints.js` + `exercise_instructions.js`, with
   `docs/feedback_catalog.md` updated to record deck provenance. One PR,
   `--base master`, `--repo avnerdorman/HarmonyLab`.
3. Separately, land the **text-only figured-bass alteration rule** (F2) —
   separate PR (different surface, smaller blast radius).
4. **Then** decide on the lesson page: run the §5 spike (recommended) or go
   straight to the gated design specs for candidate page 2.

The spike (§5), the inline-wheel hint (W1 inline), and any other gated
item come **after** the hint text changes land and **after** explicit
product-owner approval of the corresponding design spec.