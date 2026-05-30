# Roman From Clausulae — page_title Titling + Units 10–14 (Design)

Date: 2026-05-30
Status: Approved (brainstorm), pending implementation plan

## Goal

Two related extensions to the `roman_from_clausulae` exercise system:

1. **page_title titling** — Clausulae generators title exercises using the
   musical-type page titles from the Galant Compendium (e.g. "Compound Cadences
   in Three Voices") instead of synthetic/jargon descriptions.
2. **Units 10–14** — Extend `generate_roman_from_clausulae` beyond unit 9
   (simple authentic cadences) to cover units 10, 11, 12, 14, with per-unit
   Roman-numeral answer sets, sourced entirely from the clausulae generation
   engine (not the compendium score content).

This honors the preservation notes in
[2026-05-26-roman-from-clausulae-lessons.md](2026-05-26-roman-from-clausulae-lessons.md):
score content comes from the engine, not from compendium XML/notes; titles use
musical type, not measure numbers or Clausulae jargon.

## Key Finding: Blocker 1 Already Resolved

CLAUDE.md's "HIGH PRIORITY: Multi-Unit Playlist System — Blocker 1" warns that
`applySkillFilter`'s generic path is broken and needs a `UNIT_ALLOWED_ANSWERS`
map. **That map already exists** at
[exercise_definition.js:15–90](../../../lab/static/js/src/models/exercise_definition.js),
filled for units 9–20, with the broken `startsWith` path removed. The frontend
skill-filtering work is done. This design treats Blocker 1 as resolved and
removes the stale warning from CLAUDE.md.

The remaining gap is **generator content**: the generator only produces simple
authentic cadences (hardcoded `I → V → I`), so units 10–14 have no source
material yet.

## Decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Content source for units 10–14 | **Engine only** — `enumerate_simple` / `enumerate_compound` / `enumerate_double`. No compendium note-sourcing. |
| Titling | **Curated `(family, n_voices) → page_title` map**, applied to **both** generators (`generate_roman_from_clausulae` and `generate_clausulae_b1`). |
| Unit 13 (Rule of Octave) | **Skipped this round** — engine has no ROO generator. Documented as future work. |
| RN derivation | **music21 auto-derivation** (reuse `music21_builder.py` / `skills_analyzer.py`), with a verification gate. |
| Unit assignment | **Generate-and-bin** — analyze derived RNs, assign each exercise to the lowest unit whose answer set covers them. |
| Per-unit answer-set source of truth | **Extract shared JSON** read by both JS and Python. |

## Components

### 1. Shared per-unit answer table

Extract the `UNIT_ALLOWED_ANSWERS` literal (units 9–20) from
`exercise_definition.js` into a canonical data file consumed by both stacks.

- **Canonical file:** `lab/static/js/src/config/unit_allowed_answers.json`.
  - If the AMD loader cannot `require` raw JSON, ship a thin generated
    `unit_allowed_answers.js` AMD module wrapping the same data, or use the
    `json`/`text` requirejs plugin. **Resolve the exact load mechanism during
    planning** — do not block the design on it.
- **JS:** `exercise_definition.js` imports the table instead of inlining it.
  No behavior change to `applySkillFilter`.
- **Python:** the generator reads the same file to set `payload.allowed_answers`
  per unit.
- **Parity test:** assert the JS-visible table and the Python-loaded table are
  byte-for-byte equivalent sets per unit, so they can never drift.

### 2. Shared clausula → page_title map

New Python module `apps/exercises/clausulae_titles.py` exposing a lookup keyed by
`(cadence_family, n_voices)`:

| family | n_voices | page_title |
|---|---|---|
| simple | 2 | Simple Cadences in Two Voices |
| simple | 3 | Simple Cadences in Three Voices |
| simple | 4 | Simple Cadences in Four Voices |
| compound | 2 | Compound Cadences in Two Voices |
| compound | 3 | Compound Cadences in Three Voices |
| double | 3 | Double Cadences in Three Voices |
| double | 4 | Double Cadences in Four Voices |

- **Title string format:** `f"{page_title} — {key} major"`. No Clausulae
  terminology, no measure numbers — satisfies the lessons-spec titling rule.
- **Both generators** call this map for their descriptions. Branch B
  (`generate_clausulae_b1`) keeps its exercise identity, tags, and pedagogy;
  only the human-readable title string changes.
- **Open issue — 4-voice compound:** the compendium splits 4v compound cadences
  into three titles ("…with 5/4", "…with 6/5", "…with 6/4 in Four Voices"), but
  `enumerate_compound_4voice` does not tag which suspension type it produced.
  Planning must add a suspension-type discriminator or choose a documented
  default before emitting 4v-compound titles.

### 3. music21 Roman-numeral derivation

Replace the hardcoded `_CADENCE_RN = [(0.0,"I"),(2.0,"V"),(4.0,"I")]` constant.
Reuse the existing analysis stack:

- Build a music21 `Score` from the realized voices (`music21_builder.py`).
- Run roman-numeral analysis (same approach as `skills_analyzer.py`) to produce
  an ordered `(offset → roman_numeral)` list.
- Feed those into `AnalysisSlice`s, all `is_target=True`, so the student sees one
  `?` slot per analyzed onset.

### 4. Generate-and-bin generator

Refactor `generate_roman_from_clausulae.py`:

- **Pools:** `enumerate_simple` + `enumerate_compound` (3v, 4v) +
  `enumerate_double` (3v, 4v), across all `TARGET_KEYS`, retaining the existing
  `_tonal_valid` sonority filter.
- **Per combo + key:** realize voices → derive RN set via music21 → build payload.
- **Binning:** assign the exercise to the **lowest** unit in `{9, 10, 11, 12, 14}`
  whose allowed-answer set ⊇ the exercise's RN set.
  - If the lowest covering unit is exactly **13** (skipped this round), bump to
    **14** (unit 14's set ⊇ unit 13's set).
  - If **no** unit covers it (an RN beyond unit 14, or music21 noise) →
    **reject the exercise and log it** (verification gate; do not silently emit).
- **Payload:** `allowed_answers` = the bin unit's set; `skill_tags` include
  `unit:N`, the music21-derived harmony tags, and the existing namespace tags
  (`exercise_type:roman_from_clausulae`, `corpus:standard_exercises_from_clausulae`,
  `mode:roman`, `voices:N`).
- **Playlists:** one idempotent playlist per unit that actually received
  exercises (per-unit `Playlist(skill_tags=['unit:N', …])`).
- **`--unit` flag:** becomes an optional filter (default: emit all bins).
- **Idempotency** preserved: re-running with `--overwrite` replaces prior rows /
  playlist orderings for the same descriptions.

### 5. Scope boundaries (YAGNI)

Explicitly **out of scope**:

- Unit 13 / Rule of the Octave (no engine generator).
- Sequences (no engine generator).
- Sourcing score content from the compendium `notes`/MusicXML (forbidden by the
  lessons spec).
- Any change to `applySkillFilter` logic (already correct).
- Any change to the grading engine or UMTO schema.

### 6. Documentation updates

- **CLAUDE.md:** mark Blocker 1 **resolved**; remove the stale "Fix needed"
  instructions for `applySkillFilter`. Note Blocker 2 status is unchanged.
- **`docs/management_commands.md`:** update the `generate_roman_from_clausulae`
  entry for the new pools, binning, and per-unit playlists.
- **Unit 13 deferral** recorded here and referenced from CLAUDE.md: revisiting it
  needs either an engine ROO generator or an explicit lessons-spec exception.

### 7. Verification (spec-mandated)

Per the lessons spec, passing tests is **not** sufficient. After generation:

1. Report the **bin histogram** (count of exercises per unit) before any bulk use.
2. Browser smoke-test **one exercise per new unit** (10, 11, 12, 14):
   - Score renders, musically coherent, matches the working clausulae render.
   - One `?` slot per analyzed onset, at the correct offsets.
   - The per-unit answer pool appears in the dropdown.
   - A student can answer and complete the exercise.

## Top Risk

The engine's compound/double cadences may not produce enough harmonic variety to
populate units 10, 11, and 14 (e.g. everything bins into 9 and 12). The bin
histogram in step 7.1 is the early-warning signal. If bins are sparse, the
"extend to 10–14" goal partially fails and we revisit — most likely re-opening
the compendium-exception conversation for those units. Surface the histogram
**before** committing to bulk generation.

## Tests

- Generated exercises carry the expected namespace + `unit:N` tags.
- Each exercise's derived RN set ⊆ its assigned unit's allowed-answer set
  (binning correctness).
- `payload.allowed_answers` equals the assigned unit's set.
- JS ↔ Python parity for the shared answer table.
- Title-map coverage: every emitted `(family, n_voices)` resolves to a page_title.
- Command idempotency; deterministic playlist ordering.
- Analysis slices have `is_target: true`; payloads advertise Roman-numeral
  analysis, not Clausulae analysis.

These tests gate correctness but **do not** replace the manual browser
verification in section 7.
