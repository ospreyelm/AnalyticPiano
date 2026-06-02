# Assessment: Should Humdrum `**kern` replace or supplement our JSON music representation?

**Status:** Written assessment / recommendation. No migration code in this document.
**Scope:** The musical-data representations used across the Python backend and the JS frontend.
**Bottom line:** **Do not replace JSON with `**kern`.** Adopt `**kern` as a low-cost *import/export interchange* layer (music21 is already in the stack), and separately formalize `**kern`'s *dual-indexing idea* as an in-memory sonority table — which is the change that actually delivers the "easy vertical + horizontal access" we want. Concretely: **Option C (in-memory dual-index view) as the internal improvement, plus Option B (kern as interchange) as a complementary, near-free capability. Reject Option A (kern as primary).**

---

## 1. Current state — where music data is defined, parsed, serialized, traversed

The codebase does **not** have one music representation. It has a small stack of them, with a clear "canonical bridge" in the middle. Mapping them is essential to the kern question, because each layer answers the vertical/horizontal question differently.

### 1.1 The representations in use

| Layer | Where | Shape | Axis it favors |
|---|---|---|---|
| **Live MIDI model** | `lab/static/js/src/models/chord.js`, `chord_bank.js` | `Chord._notes = { midi: bool }`; `ChordBank._items = [Chord]` | **Vertical only** — a `Chord` is a sonority; no spelling, no voice membership (MIDI keys), `_rhythmValue` string, `_noteProps[midi]` for arbitrary per-note flags |
| **CIR** (Canonical Internal Representation) | `polyphony_plan.md`; stored in `data/corpus/bach/*.json` and `Exercise.data.score.measures`; built by `apps/exercises/utils/m21_cir_converter.py` | `measures → staves{treble,bass} → voices[] → items[]`; pitch = `{step, alter, octave, is_diatonic}`; duration = `{type, dots}`; `tie` | **Horizontal**, but bucketed inside measures |
| **UMTO** (Universal Music Theory Object) — *the canonical bridge* | `apps/exercises/umto.py` (pydantic) + mirrored as JSON; built by `apps/exercises/umto_factory.py` | `voices{S,A,T,B} = [VoiceEvent]` (horizontal) **plus** `analysis = [AnalysisSlice]` and `grading = [GradingSlice]` keyed by **`offset`** in quarter-lengths (vertical) | **Both**, by carrying two parallel structures |
| **Score timeline** | `lab/static/js/src/components/music/score_timeline.js` | Flat event list; each event `{onset, midi, step, alter, staff, voiceIndex, duration(ticks), …}` | **Both** — `onset` is the vertical key, `staff+"_"+voiceIndex` is the horizontal key |
| **Legacy measures (VexFlow)** | `UMTO._to_legacy_measures()` (`umto.py:239`) | CIR-shaped measures regenerated from UMTO voices for rendering | Horizontal |

JSON Schemas for the persisted shapes live in `docs/schemas/` (e.g. `umto_chorale_playback.schema.json`, which defines the shared `$defs`: `VoiceEvent`, `AnalysisSlice`, `GradingSlice`, `UMTOObject`, `CIRMeasure`). DB volume is large: ~23k each across four `umto_chorale` modes, plus 26,490 barline exercises.

**Key observation:** the system *already* maintains both a horizontal store (`voices`) and vertical stores (`analysis`/`grading` slices keyed by offset), and already derives one view from another (`score_timeline.js`, `_to_legacy_measures`). The "dual access" the kern question is motivated by is **partly already implemented** — it is just done unevenly (richer on the JS side than the Python side).

### 1.2 Vertical (sonority / harmony-at-a-time-point) operations

- **Python — `UMTO.get_chord_at_offset(offset)`** (`umto.py:157`): loops all four voices, re-accumulating `current_time` from zero on every call, to find what sounds at `offset`. Used by `get_allowed_answers()` and `flatten_to_artusi()`.
- **Python — music21 `chordify()`** is the *real* vertical-analysis engine: `roman_derivation.py:61`, `umto_factory.py:352` (Roman numerals per onset), `compendium_prep.py:434,447`, `m21_cir_converter.py:305`. Vertical harmonic labeling is done in music21, not on our JSON.
- **JS — `chorale_grader.js`**: `groupByOnset()` and `buildAnalysisWindows()` (`exercise_definition.js:314`) build a `midiStack` per onset; `Chord.getSortedNotes()` / `getNoteNumbers()` return the sounding sonority.

### 1.3 Horizontal (melodic line / single voice over time) operations

- **Python**: per-voice item iteration with independent running offsets — `voice_offsets = {"S":0,...}` in `umto_factory.py:245`; `music21_builder.py` voice walks; `pitch_voice_utils.strip_to_voice`.
- **JS**: `score_timeline.js` builds events voice-by-voice (preserving melodic continuity); `chorale_grader.js:305` resolves *held* notes by walking **backwards within `staff+voiceIndex`** to find the most recent note still sounding (`onset + duration > currentOnset`).

### 1.4 The known hard case — ragged / non-aligned durations

This is handled today in several explicit places, all of which are essentially "resolve which note is still sounding when voices don't attack together":

- `compendium_source._trim_notes` — trims each note's quarter-length to the next distinct onset.
- `umto_factory._split_voices_at_onsets` — splits a held note at beat-boundary onsets where another voice attacks (a held half-note becomes two quarters) so rendering/grading line up.
- `umto_factory._absorb_trailing_rests_after_final_attack`.
- `score_timeline.js` — per-measure `maxDuration` (not equality); held detection via `onset + duration > onset`.
- `chorale_grader.js` held-note backward walk (above).
- music21 `chordify()` absorbs ragged offsets natively during analysis.

---

## 2. Assessing `**kern` against the three criteria

`**kern` is a 2-D text grid: **columns are spines** (voices/parts — read a column downward = a melodic line) and **rows are records** (read a row across = a time moment). Tokens encode diatonic pitch (`cc#`, `e-`, octave by letter case/repetition), reciprocal durations (`4`=quarter, `8.`=dotted eighth), ties `[`/`]`, slurs, articulations. **Ragged durations are represented with null tokens `.`**: a spine holding a long note shows `.` in the intervening records, and to find the sounding pitch at a row you scan upward to the last non-null token — the exact analogue of our `chorale_grader` backward walk.

### (1) Can kern represent everything our JSON holds?

| Our field | kern equivalent | Verdict |
|---|---|---|
| Pitch + spelling/enharmonics (`step`,`alter`,`octave`) | Native, explicit (`c#`, `e-`, octave by case) | **Clean** — kern preserves spelling exactly, a strength |
| Duration / dots / ties | Native (reciprocal + `.` dots, `[ ]` ties) | **Clean** |
| Voice membership (S/A/T/B) | Spines; spine-split for divisi. Bach chorales are kern's canonical use case | **Clean** |
| MIDI pitch | Not native; deterministically derivable (music21) | **Derivable**, but we store it explicitly today |
| Dynamics / articulation | Articulation tokens inline; dynamics via a separate `**dynam` spine | **Possible**, secondary |
| **Analysis layer** (`roman_numeral`, `raw_roman_numeral`, `figured_bass`, `raw_figured_bass`, `local_key`, `functional_label`, `pop_symbol`, `scale_degrees[]`) | Parallel analytic spines (`**harm`, custom `**fb`, etc.), offset-aligned | **Partial** — Humdrum's "one spine per dimension" is elegant for *some* of these, but our nested dual record (raw **and** filtered RN, `local_key` for tonicization, `scale_degrees` as `{midi,label}` arrays) needs bespoke token grammars per spine |
| **Pedagogical / app metadata** (`unit_tags[]`, `is_target`, `complexity_score`, `locked_voices`, `voice_count_policy`, `harmonization_target_policy`, `chord_settle_ms`, `release_grace_ms`, `max_voice_displacement`, `visual.x_hint/y_hint/anchor/style`) | Reference records `!!key:value` or comments — unstructured | **No clean home** |

**The gap is the annotation layer, which is the product.** Musical content (pitch/duration/voice) maps to kern beautifully. But HarmonyLab is a *teaching* app: its value is the pedagogical metadata bolted onto the notes. Kern has no structured place for `unit_tags`, targeting flags, grading tolerances, voice-count policy, or render hints — exactly the fields UMTO gives us for free with schema validation.

### (2) Does the 2-D spine/record model make our analyses simpler?

**Horizontal:** reading a kern spine downward == reading our `voices["S"]` array. No simplification — we already have this.

**Vertical:** reading a kern record across gives only the *new attacks* at that moment; held notes still require the upward null-token scan. So kern does **not** eliminate the ragged-held problem — it just encodes it with `.` tokens instead of offset arithmetic. **The win is the dual *index*, not the kern *serialization*.** And we can get that index without kern.

**Concrete before/after — vertical access (`get_chord_at_offset`).**

*Before* (`umto.py:157`, runs today):
```python
def get_chord_at_offset(self, offset: float) -> List[Pitch]:
    pitches = []
    for voice_id in ["S", "A", "T", "B"]:
        events = getattr(self.voices, voice_id)
        current_time = 0.0
        for event in events:
            if current_time <= offset < (current_time + event.duration - 0.001):
                if event.kind == "note" and event.pitch:
                    pitches.append(event.pitch)
            break  # (subtle: the loop structure re-walks every voice from t=0)
            current_time += event.duration
    return pitches
```
Cost: re-walks all voices from zero on *every* call → O(voices·events) per offset, O(voices·events·slices) to label a whole piece. Fragile float epsilon. Loses which voice each pitch came from. Cannot distinguish a new attack from a held note.

*After* (Option C — a precomputed sonority table; rows = sorted onsets, columns = voices):
```python
table = SonorityTable.from_umto(umto)     # built once
chord    = table.sounding_at(offset)      # O(log n): {"S": Pitch, "A": Pitch, ...}
attacks  = table.attacks_at(offset)       # new onsets only  == kern record's non-null tokens
soprano  = table.voice("S")               # horizontal melodic line
```
The "held vs. attack" distinction (the ragged case) is encoded once, in one tested place, instead of being re-derived in each grader.

**Concrete before/after — voice-leading.** `voice_leading_logic.js:scoreVoiceLeading(sonorities)` already *consumes* a sequence of sonorities; on JS those come from `buildAnalysisWindows().midiStack` (a dual index that already exists). On the **Python** side there is no equivalent, so any port hand-rolls `get_chord_at_offset` per onset. With the table:
```python
sonorities = [table.sounding_at(o).midis() for o in table.onsets]
```
That single line replaces the offset-walking and gives the sonority sequence directly. **This is the missing Python-side mirror of what `score_timeline.js` already does on the JS side.**

### (3) Debuggability — kern table vs. our JSON

- **kern wins on at-a-glance musical legibility.** A plain-text grid shows voices as columns and time as rows; a wrong alto note at beat 3 is visually locatable, and Verovio/Humdrum tools render it. Our UMTO stores the four voices as *separate arrays*, so verticality is invisible and you must mentally accumulate durations to see what aligns — and the offset alignment across `voices`/`analysis`/`grading` is exactly where float bugs hide.
- **JSON wins on tooling and validation.** We have draft-2020-12 JSON Schemas, `jq`, a human-readable `exercise-types-reference.html`, and the `flatten_to_artusi()` debug helper. Kern has no schema validation for our annotation layer and no JS parser in the repo (music21 is Python-only), so a kern-primary frontend would be *harder* to debug, not easier.

Net: kern is better for eyeballing *musical* correctness; JSON is better for validating *structural/pedagogical* correctness. A small in-memory table view (Option C) plus an optional kern *export* gives us the eyeballing benefit without giving up schema validation.

---

## 3. The three architectures, migration cost, and ragged-duration handling

### Option A — `**kern` (or kern-derived model) as the *primary* internal format
- **What changes:** replace UMTO/CIR as the canonical store; re-serialize ~50k+ stored exercises; rewrite `umto.py`, `umto_factory.py`, `m21_cir_converter.py`, all graders (`chorale_grader.js`, `identification_grader.js`, harmonization logic), `score_timeline.js`, the VexFlow adapter; discard/rewrite the JSON Schemas; **write a kern parser in JS** (none exists; music21 is backend-only); invent custom spines + token grammars for the analysis layer and an out-of-band store for pedagogical metadata.
- **Migration cost: VERY HIGH.** And it re-introduces complexity (parallel-spine grammar for annotations) to solve a problem UMTO already solves.
- **Ragged durations:** null-token padding; held-note resolution still required — no net win over today.
- **Verdict: Reject.** Kern's real strengths (interchange, musician legibility) don't touch the app's actual hard parts (pedagogical metadata, real-time MIDI grading, in-browser rendering).

### Option B — `**kern` as an *intermediary / interchange* layer; JSON stays primary
- **What changes:** add `converter.parse(krn)` → existing music21→CIR→UMTO pipeline for *import* of Humdrum corpora; add a `UMTO → music21 → .krn` *export* writer. No grader, renderer, or schema changes.
- **Migration cost: LOW–MODERATE.** music21 `>=9.0` is already a dependency and is already the ingestion engine. The stub is *literally already wired*: `generate_unit2_barline_exercises.py:101` raises `"Essen/Kern import is not implemented yet"` for `--source kern|essen` — Option B is filling that in.
- **Ragged durations:** music21 absorbs them on import; existing `_trim_notes` / `_split_voices_at_onsets` finish the job. No new burden.
- **Upside:** access to large, high-quality Humdrum Bach/chorale corpora (KernScores) for the curriculum factory; interoperability with music-theory research tooling; human-readable kern fixtures for regression tests.
- **Verdict: Adopt as a supplement.** Cheap, low-risk, real corpus/interoperability gains. This is "supplement," not "replace."

### Option C — Keep JSON; borrow kern's *dual-indexing idea* as an in-memory view
- **What changes:** add a `SonorityTable` / sonority-index helper (Python mirror of `score_timeline.js`): rows = sorted onsets, columns = voices, cells = `{pitch, is_attack}` or held/null. Refactor `get_chord_at_offset`, `get_allowed_answers`, and any Python voice-leading/sonority extraction to use it. Pure addition; no schema or storage change; fully backward compatible.
- **Migration cost: LOW.** Touches a handful of Python functions and adds one tested module. Nothing on disk or in the DB changes.
- **Ragged durations:** the table's cells carry "new attack" vs. "held/null" — kern's null-token concept, encoded **once** in a tested place rather than re-derived in every grader and in the fragile `get_chord_at_offset` float walk.
- **Verdict: Adopt as the core internal improvement.** It delivers ~all the analytical ergonomics that motivated the kern question, at the lowest cost, and it closes the real gap: the Python side lacks the dual index the JS side already half-has.

---

## 4. Recommendation

**Adopt Option C as the internal change and Option B as a complementary interchange capability. Reject Option A.**

Reasoning:
1. **The motivation is an access-pattern problem, not a storage-format problem.** "Make vertical and horizontal analysis easy" is solved by an in-memory dual index (Option C), which the JS layer already demonstrates via `score_timeline.js`. Changing the on-disk/serialized format (Option A) is not required and is actively counterproductive.
2. **Kern cannot cleanly hold the annotation layer that is the product.** `unit_tags`, targeting flags, grading tolerances, voice-count/harmonization policy, and render hints have no structured kern home. UMTO holds them with schema validation today.
3. **Kern's genuine value here is interchange**, and that value is available at near-zero cost (Option B): music21 is already in the stack and the import stub already exists. This buys the Humdrum corpus and external-tooling interoperability without disrupting graders, renderers, schemas, or the 50k+ stored exercises.
4. **Ragged durations are handled best by Option C's single, tested "attack vs. held" cell model**, complemented by music21's native offset handling on the Option B import path. Option A would force us to re-implement held-note resolution against null tokens with no benefit.

### Suggested sequencing (no code in this document)
1. **Option C first:** introduce `SonorityTable` in Python, port `get_chord_at_offset` & friends onto it, add tests using existing `data/corpus/bach/*.json` fixtures. Lowest risk, immediate ergonomics + correctness win (kills the float-epsilon walk).
2. **Option B next:** implement the `--source kern|essen` import path through music21→CIR→UMTO and a `UMTO→.krn` export for fixtures/interoperability. Validate ragged cases (suspensions, asynchronous voices) against the new `SonorityTable`.
3. **Revisit Option A only if** a future requirement makes Humdrum the *system of record* (e.g., deep analytic-spine research features) — at which point the annotation-layer gap and the JS-parser gap must be solved first. Not anticipated.
