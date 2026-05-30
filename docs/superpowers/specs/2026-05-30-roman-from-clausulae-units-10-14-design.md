# Roman From Clausulae — page_title Titling + Units 10–14 (Design)

Date: 2026-05-30
Status: Approved (brainstorm), pending implementation plan

## Goal

Two related extensions to the `roman_from_clausulae` exercise system:

1. **page_title titling** — Clausulae generators title exercises using the
   musical-type page titles from the Galant Compendium (e.g. "Compound Cadences
   in Three Voices") instead of synthetic/jargon descriptions.
2. **Units 10–14** — Extend `generate_roman_from_clausulae` beyond unit 9
   (simple authentic cadences) to cover units 10, 11, 12, 13, 14, with per-unit
   Roman-numeral answer sets. Units 10–12 and 14 are sourced from the clausulae
   generation engine; unit 13 (Rule of the Octave) is sourced from transposed
   compendium ROO `notes` as a sanctioned exception (§0).

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
| Content source for units 10–12, 14 | **Engine only** — `enumerate_compound_3voice` / `enumerate_compound_4voice` / `enumerate_double_3voice` / `enumerate_double_4voice` (plus `enumerate_simple` for 9). No compendium note-sourcing. |
| Content source for unit 13 (Rule of Octave) | **Compendium ROO `notes`, transposed** to the target keys (sanctioned lessons-spec exception — see §0). Engine has no ROO generator. |
| Titling | **Curated `(family, n_voices) → page_title` map**, applied to **both** generators (`generate_roman_from_clausulae` and `generate_clausulae_b1`). |
| RN derivation | **music21 auto-derivation** via a new VoiceEvent→music21 converter, with a verification gate. |
| Unit assignment | **Generate-and-bin** — analyze derived RNs, assign each exercise to the lowest unit in `{9,10,11,12,13,14}` whose answer set covers them. |
| Per-unit answer-set source of truth | **Extract shared JSON** read by both JS and Python. |

## §0. Unit 13 — Sanctioned Compendium Exception

The lessons spec forbids sourcing student score content from the compendium.
Unit 13 (Rule of the Octave) is a **narrow, explicit exception**, approved by the
author on 2026-05-30, because:

- The engine has no ROO generator, and ROO is a real curriculum unit.
- Unlike the rejected MusicXML→reduced-CIR path, `index.json` already holds
  clean, parsed, validated `notes` (pitch/offset/ql per staff). The 28 ROO
  entries all carry usable `notes`.
- ROO progressions are stepwise diatonic scales harmonized by the rule — a
  well-defined object, not the "musically meaningless" output the spec warned
  about.

**Mechanism:** read the ROO entries from `index.json`
(`page_title` contains "Rule of the Octave"), build UMTO voices from their
`notes`, **transpose** each to the `TARGET_KEYS` (prefer a register that keeps
the voices around middle C), derive RNs via music21 (§3), and bin to unit 13.

The lessons spec
([2026-05-26-roman-from-clausulae-lessons.md](2026-05-26-roman-from-clausulae-lessons.md))
must be amended to record this exception so future agents don't "fix" it back to
engine-only.

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

**Why not derive from `music_theory_taxonomy_with_branches.json`?** The
redundancy roadmap names the taxonomy as the long-term source of truth, but the
taxonomy stores **pedagogical skill tags** (e.g. `Diatonic_Triads`,
`Inversions_First`), not the **Roman-numeral answer strings** (`I6`, `ii°7`)
this table needs. A tag→RN mapping layer does not exist and building one is out
of scope here. This spec therefore makes the extracted JSON the canonical RN
table now, and notes taxonomy reconciliation (taxonomy emits the RN table once a
tag→RN layer exists) as future cleanup aligned with the roadmap.

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

- **Title string format:** `f"{page_title} — {key} major [{fingerprint}]"`. The
  `page_title` + key alone is **not unique** — every variant in the same family
  and key would collide, and `_save_exercise` uses `description + author` as the
  overwrite/idempotency key. The `fingerprint` is the existing compact combo
  label (`_combo_label`, e.g. `D:D-Ti-D T:M-Re-D B:D-Sol-D`) or, when that
  overflows the `varchar(60)` description field, a stable `var{N}` derived from
  the combo's slot fingerprint (not loop index, so it survives reordering). No
  Clausulae terminology, no measure numbers — satisfies the lessons-spec titling
  rule while keeping descriptions unique.
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

**The existing `music21_builder.py` cannot be reused as-is:**

- `build_score_from_data()` builds from legacy **CIR `score.measures`** shape,
  not the generated **UMTO `VoiceEvent`** lists this generator produces.
- `_pitch_to_midi()` (music21_builder.py:163) computes `midi` but **never
  returns it** (returns `None`) — a latent bug; any `note` (non-chord) path in
  `build_score_from_data` would pass `midi=None` to `note.Note`.

Therefore the plan must add a **new, dedicated `VoiceEvent` → music21 `Score`
converter** (e.g. in `music21_builder.py` or the generator). It can read
`VoiceEvent.pitch.midi` / `.step` / `.alter` / `.octave` and `.duration`
directly — the generated events already carry MIDI, so it does not depend on the
broken `_pitch_to_midi`. Fixing or removing `_pitch_to_midi` is a small adjacent
cleanup the plan should include (or split off).

Then:

- Build the `Score` from the realized voices via the new converter.
- Run roman-numeral analysis (same `music21.roman` approach as
  `skills_analyzer.py`) to produce an ordered `(offset → roman_numeral)` list.
- Feed those into `AnalysisSlice`s, all `is_target=True`, so the student sees one
  `?` slot per analyzed onset.

### 4. Generate-and-bin generator

Refactor `generate_roman_from_clausulae.py`:

- **Engine pools (exact functions, tuple shapes to be confirmed in planning):**
  `enumerate_simple`, `enumerate_compound_3voice`, `enumerate_compound_4voice`,
  `enumerate_double_3voice`, `enumerate_double_4voice` — all from
  `clausulae/generate.py`. The `*_late_bass` and `enumerate_compound_3voice_double_tau1`
  variants are optional extras; planning decides whether to include them.
  Run across all `TARGET_KEYS`, retaining the existing `_tonal_valid` filter.
- **ROO pool (unit 13, §0):** ROO `index.json` entries → UMTO voices → transpose
  to `TARGET_KEYS`.
- **Per combo/entry + key:** realize/transpose voices → derive RN set via
  music21 (§3) → build payload.
- **Binning:** assign the exercise to the **lowest** unit in
  `{9, 10, 11, 12, 13, 14}` whose allowed-answer set ⊇ the exercise's RN set.
  ROO material naturally lands in 13 (its inversions/scalar harmonies need unit
  13's set); engine cadences land in 9–12 or 14.
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

- Sequences (units 15+; no engine generator).
- Sourcing score content from the compendium for **non-ROO** units (forbidden by
  the lessons spec). The compendium is used **only** for unit 13 ROO (§0).
- A tag→RN mapping layer over the taxonomy (future cleanup; see §1).
- Any change to `applySkillFilter` logic (already correct).
- Any change to the grading engine or UMTO schema.

### 6. Documentation updates

- **CLAUDE.md and AGENTS.md:** both carry the stale Blocker 1 warning. Mark
  Blocker 1 **resolved** in both; remove the stale "Fix needed" instructions for
  `applySkillFilter`. Blocker 2 status unchanged.
- **`docs/management_commands.md`:** update the `generate_roman_from_clausulae`
  entry for the new pools, ROO source, binning, and per-unit playlists.
- **`2026-05-26-roman-from-clausulae-lessons.md`:** record the §0 ROO compendium
  exception so future agents don't revert it.

### 7. Verification (spec-mandated)

Per the lessons spec, passing tests is **not** sufficient. After generation:

1. Report the **bin histogram** (count of exercises per unit) before any bulk use.
2. Browser smoke-test **one exercise per new unit** (10, 11, 12, 13, 14):
   - Score renders, musically coherent, matches the working clausulae render.
   - One `?` slot per analyzed onset, at the correct offsets.
   - The per-unit answer pool appears in the dropdown.
   - A student can answer and complete the exercise.

## Top Risk

The engine's compound/double cadences may not produce enough harmonic variety to
populate units 10, 11, and 14 (e.g. everything bins into 9 and 12). Unit 13 is
safe (sourced directly from ROO entries), but 10/11/14 depend on the engine's
output landing in those bins. The bin histogram in step 7.1 is the early-warning
signal. If bins are sparse, the "extend to 10–14" goal partially fails for those
units and we revisit — most likely re-opening the compendium-exception
conversation for them too. Surface the histogram **before** committing to bulk
generation.

Secondary: ROO transposition must keep voices in a singable/playable register
(prefer centering around middle C); naive transposition could push voices to
extreme octaves. The new converter should clamp/choose octaves accordingly.

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
- New VoiceEvent→music21 converter produces correct MIDI/durations (does not
  depend on the broken `_pitch_to_midi`).
- ROO transposition: each transposed entry keeps voices in the target register
  (around middle C) and derives a sane RN sequence.

These tests gate correctness but **do not** replace the manual browser
verification in section 7.
