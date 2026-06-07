# Chordal UMTO Score-Kind (Legacy-in-UMTO) — Design Spec

Date: 2026-06-07

Status: Design spec. No implementation yet.

This is **Spec A** of a two-spec effort. Spec B (MusicXML→chordal converter + Teacher
Workbench authoring UX) depends on this spec and is written separately. Build A first.

---

## 1. Problem

Teachers cannot efficiently bring music into the app, fix its analysis, and fan it out to
all keys. Diagnosis (against `clausulae-project/compendium/examples/m321-322.xml` and
siblings) traced the wall to a **representation mismatch**, not missing import tooling:

- Canonical UMTO `Voices` (`apps/exercises/umto_schema.json`, `$defs.Voices`) is rigid
  **S / A / T / B**, and each `VoiceEvent` carries a **single nullable `pitch`** — no
  chord / multi-head event.
- `build_umto_payload` (`apps/exercises/umto_factory.py:253-396`) walks incoming CIR
  `staves.{treble,bass}.voices[0..1]` and force-fits it into those four named voices.
- Real input is not rectangular SATB:
  - `m321-322.xml`: two upper voices encoded as **chords on one staff** + a bass line.
    Converter output had `key: null`, the bass **duplicated** into a phantom treble
    voice, and polyphony collapsed.
  - `m345-346.xml`: upper staff cardinality varies mid-phrase (`CH3 … CH2 … CH3`) — a
    voice **rests** inside chord notation. Which voice dropped is not recoverable from a
    music21 chord.
  - `m361-361.xml`: a **single monophonic** line, no harmony at all.

Forcing ragged / chord-encoded / monophonic music into a fixed SATB grid is the root
cause of the "musically meaningless" results that `CLAUDE.md` (roman-from-clausulae
lessons) warns about. The fix is not a smarter voice-splitting heuristic (it breaks on
voice crossing and ragged cardinality); it is to **stop forcing voice separation when the
source does not contain it.**

## 2. Key insight

The app **already has** chordal grading/rendering — it is the legacy chord-bank path —
but that path is **not currently reachable from UMTO**, and integrating it requires real
work. The honest picture (verified against the live code):

- Legacy exercises store `data.chord` = an array of chords, each a set of pitches
  (`visible` / `hidden`). Legacy `type` values: `matching`, `analytical`,
  `analytical_pcs`, `figured_bass`, `figured_bass_pcs`, `identification`
  (`exercise_definition.js:96` `ExerciseDefinition.TYPES`).
- The frontend builds a gradeable exercise from `definition.chord` at
  `exercise_definition.js:1237`, normalizing each chord to `{visible, hidden, notes}`. The
  3D piano renderer and the default grader consume that normalized `chord[]`.
- **BUT** `ExerciseDefinition.parse()` returns inside the `if (definition.isUMTO)` block
  (`exercise_definition.js:1028`) **before** the legacy chord branch at line 1237. So a
  UMTO payload never reaches the chord branch. A chordal UMTO needs a **new chordal case
  inside the UMTO branch**, calling a shared chord-normalization helper extracted from the
  legacy branch — not relying on the old branch.
- UMTO identification windows/slots are built from
  `ScoreTimeline.buildTimeline(exercise.score)` → `buildAnalysisWindows(timeline)`
  (`exercise_definition.js:448`), and a slot is hidden when no matching notation window
  exists (`winMeta.hasSlot`, `exercise_definition.js:572`). A chordal UMTO with no
  `score.measures` will produce hidden / missing slots unless we supply the windows. See
  §5a.
- `apps/exercises/utils/transpose.py:75` scans **`exercise.data["chord"]`** (top-level
  legacy array) only. It does **not** see `score.umto.chords`. Transpose support for
  chordal UMTO is therefore real work, **deferred to Spec B** (see §5b).

So a chord is the right *representation* for ragged / monophonic / chord-on-staff input
("these pitches sound at this onset"), and the grading/rendering primitives exist — but
the UMTO↔chordal wiring (frontend branch, window source, transpose, legacy load gate)
must be built. This spec scopes that wiring.

## 3. Goal of Spec A

Make a **chordal score-kind a first-class UMTO citizen**, and let existing legacy
`chord[]` rows flow through the UMTO code path at runtime.

Two concrete wins:

1. The MusicXML converter (Spec B) gets a faithful, sanctioned target to write
   chord-on-staff / ragged / monophonic input into.
2. Every existing legacy chord-bank exercise becomes **loadable through UMTO** without a
   database rewrite.

### Explicitly in scope

- A chordal UMTO score representation that carries a chord sequence inside the UMTO
  envelope (key, meter, `unit_tags`, analysis slices, `is_target`).
- `save_umto_exercise` / factory support for creating chordal UMTO rows **without forcing
  SATB**.
- Schema validation for the chordal kind.
- A **runtime read-path** so existing legacy `chord[]` rows render and grade through the
  UMTO path (no stored-data migration).
- Tests proving a legacy `chord[]` exercise grades identically before and after going
  through the UMTO path (round-trip equivalence).

### Explicitly NOT in scope (deferred)

- The MusicXML→chordal converter and any music21 work (**Spec B**).
- Teacher Workbench analysis-fix UI and transpose-all-keys button (**Spec B**).
- One-shot migration that rewrites stored legacy rows into chordal-UMTO rows (a later
  spec; would need the data-integrity / migration-safety guards). This spec **loads**
  legacy rows through UMTO at runtime; it does not rewrite them.
- Independent voice-line / voice-leading grading. **Accepted limitation:** chordal mode
  has no separable voice lines, so per-voice voice-leading grading is impossible for
  chordal exercises. This is fine for identification, Roman-numeral, figured-bass, and
  play-the-chord exercises, which read verticalities. SATB voice-split remains a separate,
  opt-in, best-effort path (not built here) used only when a source genuinely encodes
  separate `Voice` objects.
- SonorityTable / dual-index view (`dual-index-contract.md`) — separate later effort.
- kern as an intermediate format — **rejected**. Evidence: music21 cannot write kern
  (`registerOutputExtensions` is empty); `xml2hum` is unmaintained since 2010 with no
  Apple-Silicon build and the same ≤2-voices-per-staff limit; and every kern route still
  requires the same voice-assignment + key-extraction work while losing UMTO pedagogical
  metadata. `dual-index-contract.md` already concluded the win is an indexing view, not a
  format swap. kern may remain a **read-only import source** (music21 reads `.krn`) in a
  future spec, never an intermediate format.

## 4. Data shape

The chordal kind must conform to the **actual** canonical UMTO contract, not a new
wrapper. Verified facts that constrain the shape:

- `UMTO` (`apps/exercises/umto.py:152`) has top-level fields `metadata`, `voices`,
  `analysis: List[AnalysisSlice]`, `grading: List[GradingSlice]`. `analysis`/`grading`
  default empty; `voices` is currently required.
- The stored Exercise payload puts the canonical object at **`data.score.umto`**
  (`UMTO.to_frontend_payload`, `umto.py:226`), alongside `data.score.meta` and
  `data.score.measures`.
- The frontend reads analysis from `score.umto.analysis[]` / `score.umto.grading[]`
  (`exercise_definition.js:491`). Per-chord analysis would duplicate that and invite
  drift.

Therefore the chordal kind is an **additive change to the canonical UMTO object**, not a
re-wrapper:

- **`Metadata.score_kind`** discriminator: `Literal["voices", "chordal"]`, default
  `"voices"` (existing exercises unchanged).
- **`UMTO.chords: List[ChordEvent]`**, default `[]`. `UMTO.voices` becomes
  `Field(default_factory=Voices)` so a chordal exercise can omit it.
- **`analysis[]` and `grading[]` stay canonical and authoritative** — exactly as the
  voices kind uses them. `chords[]` is the verticality / rendering / legacy-adapter /
  transpose source; it does **not** carry analysis labels.
- **Validator (`model_validator`)**, with these exact rules so current behavior is not
  loosened:
  - `score_kind == "chordal"`: `chords` non-empty; `voices` may be omitted.
  - `score_kind == "voices"`: **`voices` must be explicitly present** (use Pydantic
    `model_fields_set` to detect omission). The `default_factory` exists only so chordal
    payloads can omit `voices`; it must NOT silently make voices-kind payloads valid
    without `voices`. This preserves today's "voices required" behavior.

**`ChordEvent` field rules** (settle exact names in planning, but these constraints hold):

- `offset: float` (quarter-length onset, ≥ 0), `duration: float` (> 0).
- `visible: List[int]`, `hidden: List[int]` — integer MIDI pitches. `visible + hidden`
  may be empty only if a future rest representation needs it (not in Spec A; Spec A chords
  have ≥1 pitch).
- **Input order is preserved** (not sorted) — bass-visible figured bass and voice ordering
  depend on it. The frontend's existing `sortNotes` runs at render where needed; the
  stored array keeps source order.
- `spelling: Optional[List[str]]` — if present, **must equal `len(visible) + len(hidden)`
  and map positionally to `visible` then `hidden`** (validator-enforced). If absent,
  spelling is derived from MIDI at render. This is the contract that lets enharmonics
  survive import + Spec B transpose.

```jsonc
// stored at data.score.umto
{
  "metadata": {
    "key": "C", "meter": "4/4", "clef": "keyboard",
    "complexity_score": 1, "mode": "...",        // existing fields
    "score_kind": "chordal"                       // NEW, default "voices"
  },
  "voices": { "S": [], "A": [], "T": [], "B": [] }, // empty for chordal kind
  "chords": [                                       // NEW; ordered by offset
    {
      "offset": 0.0,                  // quarter-length onset
      "duration": 1.0,                // quarter-lengths
      "visible": [60, 64, 72],        // MIDI sounding (legacy grading semantics)
      "hidden":  [],
      "spelling": ["C4", "E4", "C5"]  // OPTIONAL spelled pitches (preserve enharmonics)
    }
    // ... cardinality may vary freely per chord (ragged OK)
  ],
  "analysis": [                       // canonical, unchanged — NOT per-chord
    { "offset": 0.0, "content": { "roman_numeral": "I", "raw_roman_numeral": "I",
      "figured_bass": "5" }, "unit_tags": [9], "is_target": true }
  ],
  "grading": [ /* canonical GradingSlice[] */ ]
}
```

Design rules:

- **Cardinality is free per chord.** Monophonic = sequence of 1-pitch chords; a resting
  voice = fewer pitches in that chord. No grid, no zip, no invented voices.
- **Spelling preserved when available** (`spelling[]`); MIDI (`visible`) stays the grading
  key.
- **Analysis is canonical top-level** (`analysis[]`), correlated to chords by `offset`.
- The frontend derives a `definition.chord`-equivalent normalized array from `chords[]`
  via a **shared helper**, called from a **new chordal case inside the UMTO branch**
  (§5) — the legacy branch at `exercise_definition.js:1237` is not reachable from UMTO.

## 5. Components and boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `umto.py` models | Add `Metadata.score_kind`, `UMTO.chords: List[ChordEvent]`, make `voices` default; add the chordal validator. Canonical `Voices` model untouched. | — |
| Schema (`umto_schema.json` via `make_umto_schema`) | Regenerate so the new fields validate | `umto.py` |
| `umto_factory` (new chordal builder) + `save_umto_exercise` | Create a chordal UMTO row (chords + canonical analysis/grading) without forcing SATB; validate; persist at `data.score.umto` | schema, models |
| Backend frontend-payload (`to_frontend_payload` / `generate_exercise_context`) | Emit `score.measures` for chordal kind (see §5a) and the chordal score so the frontend has one UMTO-shaped contract | models |
| Frontend: shared chord-normalization helper | Extract the `{visible,hidden,notes}` normalization currently inside the legacy branch (`exercise_definition.js:1237`) into a reusable function | — |
| Frontend: chordal case **inside** the UMTO branch | At `exercise_definition.js:1028+`, when `score.umto.metadata.score_kind === "chordal"`, build the gradeable chord array via the shared helper | shared helper |
| Legacy load-path | At runtime, wrap a legacy `data.chord` row into the UMTO-shaped contract so it renders/grades via the UMTO path (no DB rewrite). Intercept point decided in §9. | backend payload |

Each unit is independently testable: models/schema (validate chordal payloads), factory
(create + reload), backend payload (chordal `data.score.umto` → measures + contract),
frontend helper + chordal case (chordal score → gradeable chord array), legacy load-path
(legacy row → equivalent contract).

### 5a. Window / slot source (the non-trivial integration)

UMTO identification slots come from `ScoreTimeline.buildTimeline(exercise.score)` →
`buildAnalysisWindows(timeline)` (`exercise_definition.js:448`), and a slot is hidden when
no notation window matches (`winMeta.hasSlot`, line 572). A chordal exercise with no
`score.measures` will produce hidden / missing slots. Two candidate approaches — **decide
in the plan** (note both; spike how cleanly `chords[] → measures` maps before choosing):

- **Option W1 — generate `score.measures` from `chords[]`** (backend), analogous to
  `UMTO._to_legacy_measures()` for voices. Reuses ALL existing timeline / slot / render
  code unchanged; `chords[]` remains the grading/transpose/legacy-adapter source. Risk:
  faithfully mapping ragged chords + durations into CIR measures.
- **Option W2 — teach the builder to read `umto.chords`** directly (frontend chordal path
  in `ScoreTimeline` / `buildAnalysisWindows`). No synthetic measures, but new frontend
  window code that touches the working timeline path.

This is the single biggest risk in Spec A and the gating decision for the plan.

### 5b. Transpose — deferred to Spec B

`apps/exercises/utils/transpose.py:75` scans only top-level `exercise.data["chord"]`; it
does not see `score.umto.chords`. Transpose-all-keys is a **Spec B** (Workbench UX)
deliverable. Spec A's only obligation: the chordal shape must *support* transposition
(spelling + MIDI present, offsets/durations explicit) so Spec B can either project
`score.umto.chords → data["chord"]` at transpose time or teach `transpose.py` the chordal
walk. No transpose code or transpose test ships in Spec A.

### 5c. Type/mode contract + `problems` population (required)

- **Frontend type stays `type: "umto_chorale"`**; the chordal kind is selected by
  `score.umto.metadata.score_kind === "chordal"`. No new frontend `type`. This reuses the
  existing `isUMTO` + `umto_chorale` dispatch (`exercise_definition.js:1072`).
- The chordal case must run **at the top of the `umto_chorale` block, before** the existing
  `isHarm / isIdent / isPlayback` logic, because that logic sets
  `exercise.problems = isPlayback ? [] : …` (`exercise_definition.js:1095`). Chord-bank
  grading **requires `exercise.problems`** to be populated. So for chordal exercises:
  - **playback / analysis_match / play-all-voices:** build `exercise.problems` from
    `chords[]` via the shared normalization helper (the chord-bank gradeable array) — do
    NOT leave it `[]`. This is the path that makes "play the chords" gradeable, the legacy
    parity behavior.
  - **identification / figured_bass / roman:** build `exercise.problems` correlating
    `chords[]` (verticalities) with canonical `analysis[]` targets by `offset`, plus the
    §5a window/slot source so `?` slots are not hidden.
  - **harmonization:** out of scope for chordal Spec A unless trivially free; the voices
    kind keeps its existing `harmonizationTargets` path.
- Net: the chordal branch owns `exercise.problems`, `exercise.analysis`, and the
  gradeable chord array for chordal exercises, then returns/short-circuits the rest of the
  `umto_chorale` mode logic.

## 6. Correctness bar (tests)

1. **Round-trip equivalence (gating):** an existing legacy `chord[]` exercise, loaded
   through the UMTO path, yields a normalized gradeable chord array **equivalent** to the
   legacy path (same `visible` / `hidden` / `notes` per chord after normalization) and
   grades identically. (Equivalence after normalization, not byte-for-byte JSON.)
2. **Ragged cardinality:** a chordal payload with varying chord sizes (3,3,2,3,1)
   validates, persists, reloads, and grades without padding or dropping pitches.
3. **Monophonic:** a sequence of 1-pitch chords validates and grades.
4. **Spelling preserved:** enharmonic spellings survive create→reload.
5. **Identification slots:** a chordal exercise with canonical `analysis[]` targets
   (`roman_numeral` / `figured_bass`, `is_target`, correlated by `offset`) produces the
   expected `?` slots via the chosen window source (§5a) — i.e. slots are **not** hidden by
   `winMeta.hasSlot`. This test validates the §5a decision end to end.
6. **SATB untouched:** existing canonical `Voices` exercises (chorale, chorale_id) still
   validate and behave exactly as before — `score_kind` defaults to `"voices"`; the
   chordal kind is purely additive.
7. **Chordal playback gradeable (§5c):** a chordal exercise in `playback` mode populates
   `exercise.problems` from `chords[]` (NOT `[]`) and grades the played chords correctly —
   the legacy "play the chords" parity behavior.
8. **Voices-kind still requires `voices` (§4 validator):** a `score_kind: "voices"` payload
   that omits `voices` is **rejected** (the `default_factory` must not loosen this); a
   `score_kind: "chordal"` payload that omits `voices` is accepted.
9. **`spelling` length contract:** a `ChordEvent` with `spelling` whose length ≠
   `len(visible)+len(hidden)` is rejected.

## 7. CLAUDE.md compliance

- **"All new Exercise rows MUST be UMTO; legacy shapes FROZEN."** Satisfied: the chordal
  kind is a sanctioned UMTO score-kind created through `save_umto_exercise`, **not** a
  revival of the frozen legacy Exercise row. New rows are UMTO. Legacy rows are only
  *read* through the UMTO path, never extended or re-emitted.
- **Documentation requirements:** Spec B (which introduces the student-facing converter
  output) will update `docs/exercise_types.md` and any new feedback-catalog entries. This
  spec is data-model only; it adds this design doc and, on implementation, updates
  `docs/UMTO_GUIDE.md` to document the chordal score-kind.
- **`make_umto_schema`** must be re-run so `umto_schema.json` reflects the new kind.

## 8. Build sequence

1. `umto.py`: add `Metadata.score_kind`, `UMTO.chords` + `ChordEvent`, default `voices`,
   and the §4 validator (chordal requires `chords`; voices-kind requires explicit
   `voices` via `model_fields_set`; `spelling` length rule). Canonical `Voices` untouched.
2. Regenerate schema (`make_umto_schema`); validation tests: chordal payloads, voices-kind
   regression (test 8), spelling rule (test 9), SATB untouched (test 6).
3. Chordal builder + `save_umto_exercise` support; create/reload tests (tests 2,3,4).
4. **Resolve §5a** (spike W1 vs W2), then implement the chosen window source + backend
   payload (`score.measures` for chordal, or chordal builder path).
5. Frontend: extract shared chord-normalization helper; add chordal case **at the top of
   the `umto_chorale` block** (§5c), populating `exercise.problems` for playback and
   identification; identification-slot test (test 5), playback-gradeable test (test 7).
6. Legacy runtime load-path (backend wrapper per §9); round-trip equivalence test
   (test 1, the gating test).
7. Update `docs/UMTO_GUIDE.md`.

Spec B begins only after step 6 passes.

## 9. Open questions for planning

- **§5a window source (W1 vs W2)** — the gating technical decision. Spike first.
- **Legacy load-path intercept.** Codex-confirmed: `lab/views.py:285` enters the UMTO
  payload path only when `data.isUMTO` or (`metadata` and `voices`) are present; legacy
  `data.chord` rows do not qualify. Preferred resolution: wrap legacy rows **on the
  backend** (in `generate_exercise_context` / `lab.views`) into the UMTO-shaped contract,
  so the frontend has a single UMTO path. Confirm in the plan vs a frontend-side accept of
  raw `chord[]`.
- **`spelling` / `duration` necessity in Spec A.** `spelling` is cheap and future-proofs
  transpose (Spec B) — keep. `duration`/`offset` are needed for §5a window generation —
  keep. Confirm no field is speculative.
- **Field names** under `ChordEvent` — reconcile `visible`/`hidden` (legacy) vs any UMTO
  pitch convention during planning.
