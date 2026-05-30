# Roman From Clausulae — page_title Titling + Units 10–14 (Design)

Date: 2026-05-30
Status: Approved (brainstorm), pending implementation plan

## Goal

Two related extensions to the `roman_from_clausulae` exercise system:

1. **page_title titling** — Clausulae generators title exercises using the
   musical-type page titles from the Galant Compendium (e.g. "Compound Cadences
   in Three Voices") instead of synthetic/jargon descriptions.
2. **Units 10–14** — Extend `generate_roman_from_clausulae` beyond unit 9
   (simple authentic cadences) to cover units **10, 11, 12, 14**, with per-unit
   Roman-numeral answer sets, all sourced from the clausulae generation engine.
   **Unit 13 (Rule of the Octave) is deferred to a separate design spike** (§0) —
   its engine-generation premise is unproven. No compendium score-content
   sourcing, so the lessons spec stays intact.

This honors the preservation notes in
[2026-05-26-roman-from-clausulae-lessons.md](2026-05-26-roman-from-clausulae-lessons.md):
score content comes from the engine, not from compendium XML/notes; titles use
musical type, not measure numbers or Clausulae jargon.

## Key Finding: Blocker 1 Already Resolved

CLAUDE.md's and AGENTS.md's "HIGH PRIORITY: Multi-Unit Playlist System — Blocker 1" warn that
`applySkillFilter`'s generic path is broken and needs a `UNIT_ALLOWED_ANSWERS`
map. **That map already exists** at
[exercise_definition.js:15–90](../../../lab/static/js/src/models/exercise_definition.js),
filled for units 9–20, with the broken `startsWith` path removed. The frontend
skill-filtering work is done. This design treats Blocker 1 as resolved and
removes the stale warning from both CLAUDE.md and AGENTS.md.

The remaining gap is **generator content**: the generator only produces simple
authentic cadences (hardcoded `I → V → I`), so units 10–14 have no source
material yet.

## Decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Content source for units 9–12, 14 | **Engine only** — this round uses `enumerate_simple` / `enumerate_compound_3voice` / `enumerate_compound_4voice`. No compendium note-sourcing. Double cadences are deferred because their 5-position realization is not yet implemented in HarmonyLab. |
| Unit 13 (Rule of Octave) | **Deferred to a separate design spike** (§0). The engine-ROO premise is unproven (per-degree harmonization is underdetermined); it needs its own rule-table design + validation. Not blocked by, and does not block, this spec. |
| Titling | **Curated `(family, n_voices) → page_title` map**, applied to **both** generators (`generate_roman_from_clausulae` and `generate_clausulae_b1`). |
| RN derivation | **music21 auto-derivation** via a new VoiceEvent→music21 converter, but only at structural harmonic target offsets. Do not turn every chordified suspension/held vertical into a student target. |
| Unit assignment | **Generate-and-bin** — analyze derived RNs, assign each exercise to the lowest unit in `{9,10,11,12,14}` whose answer set covers them (14 ⊇ 13, so any RN needing unit-13-only chords lands in 14). |
| Per-unit answer-set source of truth | **Derive from `music_theory_taxonomy_with_branches.json`** (`analysis.roman.cumulative`); both JS and Python read the generated artifact. |

## §0. Unit 13 (Rule of the Octave) — Deferred to a Separate Spike

Unit 13 is **out of scope for this spec** and gets its own brainstorm + design
spec. Reason: the engine-ROO premise does not yet hold up. The existing
`clausulae-project` tests only prove that ROO triples *extracted from the
compendium* are members of the compound-valid sets — they do **not** prove the
engine can *generate* a full Rule-of-the-Octave progression. "Pick the valid
compound triple whose bass matches each scale degree" is **underdetermined**:
many valid triples exist per degree, and ROO is a *specific* deterministic
harmonization, not any valid chain.

What the spike must produce before any unit-13 generation:

- A concrete **ROO degree → harmonization rule table** (ascending and descending;
  the 1-beat / 2-beat structural variants) — the selection algorithm that pins
  down one triple per degree. The compendium figured-bass annotations and the
  structural patterns in `extract_rule_of_octave_voices`
  (`compendium/validate_examples.py`, the `ex_num`→offset map) are the source
  material for that table.
- A decision on whether ROO is engine-generated (new `enumerate_rule_of_octave`)
  or sourced another way, validated by reproducing the 28 compendium ROO entries.
- **If** the spike goes engine-route: promote `_COMPOUND_3V_VALID` /
  `_COMPOUND_4V_VALID` out of `compendium/validate_examples.py` (where they're
  pure `enumerate_compound_*` output, sys.path-hacked into tests) into the
  `clausulae` package, so generation and validation share one source.
  `validate_simple` / `validate_double` already live in
  `clausulae/constraints.py`.

This spec proceeds with units **9, 10, 11, 12, 14** only. The generate-and-bin
machinery here is unit-13-agnostic: when the spike delivers ROO exercises, they
slot into the same binning/playlist pipeline without changes.

## Components

### 1. Shared per-unit answer table (derived from the taxonomy)

`music_theory_taxonomy_with_branches.json` already holds the canonical
per-unit Roman-numeral answer strings at `analysis.roman.cumulative[].value`
(verified for units 9–14; they match the current JS `UNIT_ALLOWED_ANSWERS`
literal). The taxonomy is the source of truth per the redundancy roadmap, so we
**derive** the shared artifact from it rather than freezing the JS literal.

- **Generated artifact:** a build step / management command emits
  `lab/static/js/src/config/unit_allowed_answers.json` from the taxonomy's
  `analysis.roman.cumulative` per unit. Generated, not hand-edited; regenerate
  when the taxonomy changes.
  - If the AMD loader cannot `require` raw JSON, emit a thin
    `unit_allowed_answers.js` AMD module instead, or use the `json`/`text`
    requirejs plugin. **Resolve the exact load mechanism during planning** —
    do not block the design on it.
- **JS:** `exercise_definition.js` imports the generated artifact and the inline
  `UNIT_ALLOWED_ANSWERS` literal is **deleted**. No behavior change to
  `applySkillFilter`.
- **Python:** the generator reads the same artifact (or the taxonomy directly)
  to set `payload.allowed_answers` per unit.
- **Parity test:** assert the generated artifact equals the taxonomy's
  `analysis.roman.cumulative` per unit, and that JS and Python see identical
  sets — so nothing can drift from the taxonomy.

Units beyond 14 (15–20) are carried through by the same derivation where the
taxonomy provides `analysis.roman.cumulative`. Units that must stay
**pass-through `null`** (19–20 in the current JS literal) or whose taxonomy entry
lacks RN data are defined in a **checked-in override file** read by the generator
(e.g. `unit_allowed_answers.overrides.json`: `{ "19": null, "20": null, … }`).
The merge order is taxonomy-derived values first, then overrides applied on top —
so once the JS literal is deleted there is still one explicit, version-controlled
source for the non-derivable entries. The plan flags any unit that ends up in
neither source.

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
  `skills_analyzer.py`) only at the cadence's **structural target offsets**:
  simple cadences use target offsets `[0.0, 2.0, 4.0]`. Compound cadences also
  display targets at `[0.0, 2.0, 4.0]` because `2.0` is the dominant onset with
  a suspension: pedagogically `V(5)4` resolving at `3.0` to `V(5)3`, i.e. a
  `V4-3` suspension. For student answer/binnning, normalize that target to the
  underlying Roman answer `V`. Figured-bass/suspension display, if needed, must
  come from HarmonyLab's existing figured-bass engine (`raw_figured_bass` /
  `figured_bass` fields), not from Music21 Roman analysis. Do not let music21's
  literal vertical spelling expose noisy answer-table figures such as `i54`.
- Feed those structural results into `AnalysisSlice`s, all `is_target=True`, so
  the student sees one `?` slot per harmonic target, not one slot per transient
  contrapuntal vertical.

### 4. Generate-and-bin generator

Refactor `generate_roman_from_clausulae.py`:

- **Engine pools:** `enumerate_simple`, `enumerate_compound_3voice`, and
  `enumerate_compound_4voice` from `clausulae/generate.py`. Run across all
  `TARGET_KEYS`, retaining the existing tonal-pedagogy sonority filter for both
  simple and compound material. Double cadences are deferred to a fast-follow
  because their 5-position quintuple realization is not implemented yet.
- **Per combo + key:** realize voices → derive RN set via music21 (§3) → build
  payload.
- **Binning:** assign the exercise to the **lowest** unit in
  `{9, 10, 11, 12, 14}` whose allowed-answer set ⊇ the exercise's RN set. Unit 13
  is not a candidate here (deferred, §0); since `14 ⊇ 13`, any cadence whose RNs
  need unit-13-only chords (e.g. `iii`/`III`/`VII`) lands in 14.
  - If **no** unit covers it (an RN beyond unit 14, or music21 noise) →
    **reject the exercise and log it** (verification gate; do not silently emit).
- **Payload:** `allowed_answers` = the bin unit's set; `skill_tags` include
  `unit:N`, the music21-derived harmony tags, and the existing namespace tags
  (`exercise_type:roman_from_clausulae`, `corpus:standard_exercises_from_clausulae`,
  `mode:roman`, `voices:N`).
- **Playlists:** one idempotent playlist per unit that actually received
  exercises (per-unit `Playlist(skill_tags=['unit:N', …])`).
- **`--unit` flag:** becomes an optional filter (default: emit all bins).
- **Preview before persistence:** before writing DB rows, support a raw preview
  mode that prints/exports a few generated examples per populated unit. Each
  preview must expose the realized notes, target offsets, analysis-source
  offsets, normalized RN answers, HarmonyLab figured-bass fields (if populated),
  family/key/voice metadata, and reject reason for uncovered/noisy examples.
  This is the first verification gate before API/browser wiring.
- **Idempotency** preserved: re-running with `--overwrite` replaces prior rows /
  playlist orderings for the same descriptions.

### 5. Scope boundaries (YAGNI)

Explicitly **out of scope**:

- Sequences (units 15+; no engine generator).
- Sourcing score content from the compendium for **any** unit (forbidden by the
  lessons spec). The compendium is used only as a validation fixture.
- A tag→RN mapping layer over the taxonomy (future cleanup; see §1).
- Any change to `applySkillFilter` logic (already correct).
- Any change to the grading engine or UMTO schema.

### 6. Documentation updates

- **CLAUDE.md and AGENTS.md:** both carry the stale Blocker 1 warning. Mark
  Blocker 1 **resolved** in both; remove the stale "Fix needed" instructions for
  `applySkillFilter`. Blocker 2 status unchanged.
- **`docs/management_commands.md`:** update the `generate_roman_from_clausulae`
  entry for the new pools, binning, and per-unit playlists.
- **Unit-13 spike spec:** a follow-up `docs/superpowers/specs/` entry capturing
  the §0 ROO design questions (rule table, engine-vs-other, validation-code
  promotion). Created when that spike starts — not part of this spec's work.

### 7. Verification (spec-mandated)

Per the lessons spec, passing tests is **not** sufficient. After generation:

1. Report the **bin histogram** (count of exercises per unit) before any bulk use.
2. Inspect the raw preview table for at least one example per populated unit
   before saving/bulk use:
   - realized notes match the intended clausula voices;
   - compound targets show the `2.0` dominant-suspension target normalized to
     `V`, while figures come from HarmonyLab figured-bass fields;
   - rejected examples have clear reasons.
3. Browser smoke-test **one exercise per new unit** (10, 11, 12, 14):
   - Score renders, musically coherent, matches the working clausulae render.
   - One `?` slot per analyzed onset, at the correct offsets.
   - The per-unit answer pool appears in the dropdown.
   - A student can answer and complete the exercise.

## Top Risk

The engine's simple+compound cadences may not produce enough harmonic variety to
populate units 10, 11, and 14 (e.g. everything bins into 9 and 12). Those units
depend entirely on the engine's in-scope cadence output landing in those bins.
The bin histogram in step 7.1 is the early-warning signal. If bins are sparse,
the "extend to 10–14" goal partially fails for the empty units and we revisit,
most likely by implementing double-cadence realization as the next fast-follow.
Surface the histogram **before** committing to bulk generation.

## Tests

- Generated exercises carry the expected namespace + `unit:N` tags.
- Each exercise's derived RN set ⊆ its assigned unit's allowed-answer set
  (binning correctness).
- `payload.allowed_answers` equals the assigned unit's set.
- Answer-table parity: the generated artifact equals the taxonomy's
  `analysis.roman.cumulative` per unit, and JS and Python see identical sets.
- Title-map coverage: every emitted `(family, n_voices)` resolves to a page_title.
- Command idempotency; deterministic playlist ordering.
- Analysis slices have `is_target: true`; payloads advertise Roman-numeral
  analysis, not Clausulae analysis.
- New VoiceEvent→music21 converter produces correct MIDI/durations (does not
  depend on the broken `_pitch_to_midi`).
- Compound cadence derivation uses only structural target offsets and rejects
  tonal-pedagogy-invalid sonorities; suspension/held offsets are not emitted as
  student RN targets.

These tests gate correctness but **do not** replace the manual browser
verification in section 7.
