---
title: "feat: SATB per-voice harmonization completion (milestone 1)"
type: feat
status: active
date: 2026-07-06
---

# feat: SATB per-voice harmonization completion (milestone 1)

## Summary

Add a per-voice-completion variant of the existing harmonization exercise, where three of four SATB voices are given (bass always among them) and the student enters the one missing upper voice. Grading reuses the existing chord-onset analysis-match logic unchanged; the variant is discriminated by an explicit `input_style` flag rather than a new exercise mode.

---

## Problem Frame

Current harmonization exercises are built from UMTO `score_kind="chordal"` sources: the student sees a bass line (plus figures/Roman numerals) and fills in the full upper-voice chord at each onset. There is no exercise shape where the student instead completes a single missing voice within a fully-voiced SATB texture — a distinct pedagogical exercise (voice-part dictation within a real four-voice context) that current tooling cannot produce.

Research during planning found the underlying machinery is far closer to "already built" than expected: `score_kind="voices"` (full SATB) is already the default UMTO shape, `metadata.locked_voices` already accepts an arbitrary subset of voices, and `build_targets_from_umto`'s existing "voices" branch already produces correct chord-onset targets for any N-1 locked-voice configuration with no code change. The click-based input path (`click_note.js` / `click_note_logic.js`) already generalizes to arbitrary locked-voice sets via `capRemaining`. The work is therefore narrower than a new exercise type: closing a small number of real gaps (source-eligibility validation, an explicit discriminator flag, and verification that the existing generalized mechanisms behave correctly for this specific configuration) rather than building new grading or rendering infrastructure.

A broader refactor of `exercise_definition.js`, `exercise_context.js`, and `exercise_grader.js` (extending the factory-dispatch pattern already used by the grader to these two files) was considered and explicitly deprioritized — this plan touches those three files only with small additive branches.

---

## Requirements

**Source eligibility and generation**

- R1. A UMTO source used for per-voice harmonization completion has bass in `locked_voices` — bass is never the missing voice in this milestone.
- R2. Generation enforces full four-voice texture at every bass-onset target (no rests in any locked voice at a target onset) and fails loudly with a clear error if violated — never silently skips or tolerates a gap.
- R3. Generation enforces that the missing voice has exactly one attack per bass onset, with no ties or rests at target onsets and no additional attacks between bass onsets (rhythmically 1:1 with the bass-onset grid).
- R4. Generated exercises carry an explicit `input_style` value (`"per_voice"`) rather than having the per-voice UI inferred from `locked_voices` count.

**Grading and runtime behavior**

- R5. Grading reuses the existing chord-onset analysis-match path (`ExerciseContext.gradeHarmonizationMidiSet` → `harmonization_runtime_grader.js` → `harmonizationMatch`) unmodified.
- R6. Student input uses click-based note placement, verified correct for exactly one missing voice among S, A, or T (bass excluded per R1).
- R7. No melodic/voice-leading or voice-crossing constraint is enforced in this milestone — grading remains harmonic (chord-tone) only, matching existing harmonization grading semantics.

**Content and verification**

- R8. At least one pilot exercise exists for each single-missing-voice configuration (missing S, missing A, missing T).
- R9. Each pilot exercise is verified end-to-end in a real browser (not headless — the `Tone.start()` audio gate blocks headless Chromium) for correct rendering of given vs. editable voices and correct grading.

**Documentation and discoverability**

- R10. `docs/exercise_types.md` and `docs/architecture/pipeline-registry.md` reflect the new `input_style` flag and its scope.
- R11. The teacher-facing content listing exposes `input_style` (alongside the existing `score_kind` field) so teachers can distinguish per-voice-completion exercises from full-harmonization ones when browsing or assigning content.

---

## Key Technical Decisions

- **Keep `exercise.mode = "harmonization"`, no new mode/pipeline**: introducing `mode="chorale"` (the originally-considered name) would collide with the existing unrelated "chorale" pipeline in `resolved_mode.js` (playback/identification, graded by a different module). Staying on `"harmonization"` means zero changes to `resolvePipeline`, `grader_factory.js`, or the UMTO `InteractionMode` enum.
- **Explicit `input_style` flag, not inferred from `locked_voices` count**: inferring the per-voice UI from "exactly 3 locked voices" is fragile — that count could change for unrelated reasons (e.g. a future exercise with 3 locked voices that isn't this variant). An explicit flag avoids silent misclassification.
- **`input_style` lives on `score.umto.metadata`, alongside `locked_voices`/`voice_count_policy`**, not as a new top-level `Exercise.data` field — it's generation-configuration metadata of the same kind already stored there, not a structural field like `mode`/`harmonizationTargets`.
- **Reuse `click_note.js` / `click_note_logic.js` unchanged (no new sibling grading module)**: flow-analysis research found this mechanism already builds `activeMidi` generically from `target.lockedVoices` (any voice keys) combined with pending clicked notes via `buildCommitSnapshot`, and already supports `capRemaining=1`. The originally-planned "new small sibling module to combine locked pitches with student input" turned out to already exist and generalize — this plan verifies it rather than duplicating it.
- **Bass is always locked in this milestone; bass-as-missing-voice is deferred**: `harmonizationMatch` only hard-checks pitch correctness for bass and soprano when they are the *locked* voice being verified — there is no hard check enforcing the correct pitch when bass is the *missing* voice. Allowing it now would let a student enter any chord tone in the bass register and have it grade as correct. Fixing that is a real grader change, out of scope for milestone 1.
- **Source eligibility enforced at generation time with a loud error, not a runtime tolerance**: matches the project's no-silent-fallback standard — an ineligible source should fail generation, not produce a broken or silently-degraded exercise. Note this loud-failure guarantee is a property of U1's validation pass, not of `build_targets_from_umto` itself — that function silently omits a locked voice from a target's `lockedVoices` dict when it hits a rest, rather than raising. Any future caller of `build_targets_from_umto` on a source that skipped U1's validation would not get the same guarantee.
- **`input_style` also gets a mirrored `skill_tag`** (`input_style:per_voice`), following the existing `mode:harmonization` tag convention already written by the generator command — the metadata copy nested in `score.umto.metadata` isn't queryable without a full-corpus JSON scan, and this project has already had to build a one-off backfill command for an analogous nested-field need (`recompute_harmonization_targets`). The tag gives cheap queryability now at near-zero cost.
- **No register/voice-crossing constraint added to the grader**: accepted as explicit, documented looseness for milestone 1, consistent with "no melodic grading" framing (R7) rather than a new grading rule.
- **Extend `generate_harmonization.py` rather than add a new sibling command**: `--locked-voices` already accepts an arbitrary comma list; this is a data-shape variant of the same generation flow, not a different pipeline, so one command with an added `--input-style` flag and validation step is simpler to maintain than two near-duplicate commands.

---

## Scope Boundaries

- Exactly one missing voice per exercise (S, A, or T). Multiple simultaneous missing voices are out of scope.
- Bass is never the missing voice in this milestone.
- Sources with passing tones, suspensions, or other rhythmic independence between the missing voice and the bass-onset grid are out of scope — eligible sources are homophonic (missing voice moves 1:1 with bass onsets).
- Click-based input only; physical/on-screen piano entry for this variant is out of scope (see KTDs).
- No voice-leading, register, or voice-crossing grading.
- The given/blank rendering distinction (visible given-voice noteheads vs. an editable slot) is the only task cue in milestone 1 — no additional voice-name label or instructional prompt is added.

### Deferred to Follow-Up Work

- Bass-as-missing-voice support (requires adding a hard pitch check to `harmonizationMatch` for a missing bass).
- Multiple-simultaneous-missing-voices.
- Physical/on-screen piano input for this variant (would need new work on the held-note-tracker path and carries release-timing risk related to the existing sustain-pedal bug).
- Non-homophonic sources (passing tones, suspensions, independent rhythm in the missing voice).
- The `exercise_definition.js` / `exercise_context.js` / `exercise_grader.js` factory-pattern extension and `models/` folder index doc (separately deprioritized technical-debt track).

---

## Implementation Units

### U1. Source eligibility validation

**Goal:** A reusable validation check confirms a `score_kind="voices"` UMTO is eligible for per-voice harmonization completion: bass is in `locked_voices`; every locked voice has a non-rest event at every bass-onset target; the intended missing voice has exactly one attack per bass onset with no ties/rests and no additional attacks between onsets.

**Requirements:** R1, R2, R3

**Dependencies:** none

**Files:**
- `apps/exercises/harmonization/voice_completion_eligibility.py` (new)
- `apps/exercises/tests/test_voice_completion_eligibility.py` (new)

**Approach:** Reuse the existing bass-onset-offset and per-voice-event-lookup logic already in `apps/exercises/harmonization/targets.py` (the helpers backing `build_targets_from_umto`'s "voices" branch) rather than re-deriving onset detection. Raise a clear, descriptive exception (not a boolean or silent warning) naming which onset and which voice failed eligibility, per the project's no-silent-fallback standard.

**Patterns to follow:** `apps/exercises/harmonization/targets.py`'s existing dispatch-and-validate shape; `apps/exercises/harmonization/figure_realization.py` as the precedent for a focused, single-purpose theory-logic module.

**Test scenarios:**
- Happy path: a fully-eligible 4-voice source (bass locked, one upper voice missing, full texture, 1:1 rhythm) passes validation.
- Edge case: bass not in `locked_voices` → validation fails with a clear reason.
- Edge case: a locked voice has a rest at one bass onset → validation fails, naming the onset and voice.
- Edge case: the missing voice has a tied note spanning a bass onset → validation fails.
- Edge case: the missing voice has an attack between two bass onsets (passing tone) → validation fails.
- Edge case: more than one voice is missing from `locked_voices` (beyond bass) → validation fails with a distinct reason (not misreported as a texture gap).

**Verification:** All scenarios above pass as unit tests; validation function is directly callable independent of the generator command.

---

### U2. Extend the harmonization generator command

**Goal:** `generate_harmonization.py` accepts an explicit input-style choice, runs U1's eligibility validation before building targets when the per-voice style is requested, and writes `input_style` onto the generated UMTO metadata.

**Requirements:** R1, R2, R3, R4

**Dependencies:** U1

**Files:**
- `apps/exercises/management/commands/generate_harmonization.py`
- `apps/exercises/tests/test_generate_harmonization.py`

**Approach:** Add an `--input-style` argument (default preserves current chord-entry behavior; new value selects `"per_voice"`). When `"per_voice"` is selected, call U1's validation against the copied UMTO before `build_targets_from_umto` runs, surfacing validation failures as `CommandError` (consistent with the command's existing `CommandError` usage for other precondition failures). On success, set `umto["metadata"]["input_style"] = "per_voice"` alongside the existing `locked_voices`/`voice_count_policy` metadata writes, and append `input_style:per_voice` to the exercise's `skill_tags` (mirroring the existing `mode:harmonization` tag already appended by this command) so the variant is queryable without a JSON scan.

**Patterns to follow:** The command's existing precondition-check-then-`CommandError` shape (see the existing "zero targets" and "source not UMTO" checks).

**Test scenarios:**
- Happy path: running with `--input-style per_voice` and an eligible source produces an `Exercise` with `input_style` set and correct `harmonizationTargets`.
- Happy path: omitting `--input-style` (or default) preserves current behavior exactly — no `input_style` key written, existing chord-entry exercises unaffected.
- Error path: `--input-style per_voice` with an ineligible source (per U1) raises `CommandError` and creates no `Exercise`.
- Edge case: `--input-style per_voice` combined with `--locked-voices` missing bass raises `CommandError` before target-building runs (R1 enforced at the command layer, not just deep inside validation).

**Verification:** New and existing command tests pass; a manually-run generation against a known-eligible fixture produces an exercise that loads correctly in-app.

---

### U3. Expose input style in the teacher-facing content listing

**Goal:** Teachers browsing or assigning content can distinguish per-voice-completion exercises from full-harmonization ones. No student-facing frontend accessor is needed for `input_style` in this milestone — grading (`click_note_logic.js`) and rendering (`vexflow_staff_voice_builder.js`) both already dispatch off `lockedVoices` directly and never need to branch on `input_style` at runtime; the only identified consumer for this flag is teacher-side content discovery.

**Requirements:** R4, R11

**Dependencies:** U2

**Files:**
- `apps/teacher/views_library.py`
- `apps/teacher/tests/test_library_hub.py`

**Approach:** Add `input_style` to the exercise metadata dict already returned alongside `score_kind` (`apps/teacher/views_library.py:395`), reading it the same way (`meta.get("input_style", "")` or equivalent), so it's present in the payload when set and absent/empty for existing chord-entry harmonization exercises.

**Patterns to follow:** The existing `score_kind` exposure at the same call site.

**Test scenarios:**
- Happy path: a per-voice exercise's metadata includes `input_style: "per_voice"` in the listing payload.
- Happy path: an existing chord-entry harmonization exercise (no `input_style` set) → payload omits or blanks the field without error.

**Verification:** Teacher library listing test confirms `input_style` appears in the payload when present, matching how `score_kind` already behaves.

---

### U4. Verify click-based single-missing-voice grading

**Goal:** Confirm `click_note.js` / `click_note_logic.js`'s existing generic locked-voice + `capRemaining` mechanism grades correctly for each of the three eligible missing-voice configurations (missing S, missing A, missing T), fixing any narrow gap found rather than assuming full generality.

**Requirements:** R5, R6, R7

**Dependencies:** U2

**Files:**
- `lab/static/js/src/components/input/click_note_logic.test.js`
- `lab/static/js/src/models/harmonization_grader_logic.test.js`

**Execution note:** Characterization-first — write the three missing-voice-configuration test cases against current behavior before making any code change, since the mechanism is believed to already work and the goal is to prove that, not to build new behavior. Escalation: if a configuration reveals a structural gap (grading logic that assumes a single locked voice, not just a missing test case), stop and confirm scope with the product owner before absorbing it as a small patch — do not silently expand "targeted fix" to cover a rewrite of `harmonizationMatch`'s semantics.

**Approach:** For each of missing-S, missing-A, missing-T: construct a target shape with the corresponding `lockedVoices` set (3 of 4 SATB voices, bass always present), simulate a `capRemaining=1` commit snapshot, and confirm `harmonizationMatch` grades a correct answer as correct and an incorrect one as incorrect/partial per existing semantics. If any configuration reveals a real gap (not just a missing test), fix it as a small, targeted change — do not restructure `click_note_logic.js` beyond what the specific gap requires.

**Patterns to follow:** Existing `harmonization_grader_logic.test.js` cases for the current bass-locked configuration.

**Test scenarios:**
- Happy path: missing soprano, correct note entered → graded correct.
- Happy path: missing alto, correct note entered → graded correct.
- Happy path: missing tenor, correct note entered → graded correct.
- Edge case: incorrect chord-tone entered for the missing voice → graded incorrect/partial per existing state semantics (not a new state).
- Edge case: voice-crossing entry (student's note is registrally above/below an adjacent locked voice but is a valid chord tone) → graded correct, confirming R7's accepted looseness is actually what happens, not just assumed.

**Verification:** All three missing-voice configurations produce correct grading outcomes with no code changes beyond what a genuine gap requires; any fix made is covered by a regression test.

---

### U5. Fix accepted-answer overlay rendering for multi-locked-voice configurations

**Goal:** Correct a known generalization gap (found during planning research, not merely hypothesized): the "accepted answer" overlay-rendering path assumes bass is the *only* locked voice and will render incorrectly for all three milestone-1 configurations.

**Requirements:** R6, R9

**Dependencies:** U2

**Files:**
- `lab/static/js/src/models/harmonization_realization_logic.js`
- `lab/static/js/src/models/harmonization_realization_logic.test.js`
- `lab/static/js/src/components/music/rendering/vexflow_render_pipeline.js`
- `lab/static/js/src/components/music/rendering/vexflow_tickable_builder.js`
- `lab/static/js/src/components/music/harmonization_sheet.js` (audit only; touch if a further hardcoded assumption is found)

**Approach:** `dropOneBassInstance` in `harmonization_realization_logic.js` strips exactly one bass pitch from the accepted commit snapshot and treats everything else as "the answer" — correct only when bass is the sole locked voice. Generalize it to strip *all* locked-voice pitches (not just bass), matching the comment already present in `click_note.js#_commit`'s rejected-state path noting locked-voice notes "must not appear in the overlay." Separately, `vexflow_tickable_builder.js#buildHarmonizationOverlayVoice` hardcodes `clef: "treble"` and `vexflow_render_pipeline.js` unconditionally pushes overlay notes to `trebleVoices` — add staff/clef routing so the overlay note for the missing voice renders on the correct staff regardless of which voice (S/A/T) is missing. Audit `harmonization_sheet.js`'s render-config construction for any further single-locked-voice assumption while in this area.

**Patterns to follow:** `click_note.js#_commit`'s existing locked-voice-stripping logic for the rejected-state path, as the precedent for what the accepted-state path needs to match.

**Test scenarios:**
- Happy path: missing soprano, correct answer accepted → overlay shows only the soprano note, on the correct staff, with no leaked alto/tenor/bass noteheads.
- Happy path: missing alto, correct answer accepted → overlay shows only the alto note; no leaked bass/soprano/tenor noteheads.
- Happy path: missing tenor, correct answer accepted → overlay shows only the tenor note on the bass staff (not treble), with no leaked noteheads.
- Regression: existing bass-only-locked harmonization exercises still render their accepted-answer overlay exactly as before (no behavior change for the current chord-entry configuration).

**Verification:** New `harmonization_realization_logic.test.js` cases (multi-locked-voice fixtures, which the file currently lacks entirely) pass; browser smoke test against each of U6's three pilot exercises confirms no leaked given-voice noteheads and correct staff placement.

---

### U6. Pilot content generation

**Goal:** Produce and verify one pilot exercise for each single-missing-voice configuration.

**Requirements:** R8, R9

**Dependencies:** U2, U4, U5

**Files:** none (content generation, no source changes)

**Approach:** Select three eligible source chorale phrases (or one phrase generated three ways) meeting U1's eligibility bar. Run the extended `generate_harmonization.py` (U2) with `--input-style per_voice` and `--locked-voices` set to exclude each of S, A, T in turn (bass always included).

**Test expectation:** none — this unit is content production; correctness is verified via R9's browser check.

**Verification:** Each of the three pilot exercises loads in a real browser, renders the correct given/editable voices, and grades correctly for both correct and incorrect entries.

---

### U7. Documentation updates

**Goal:** Record the new `input_style` flag and its scope in the exercise-type and pipeline-ownership docs.

**Requirements:** R10

**Dependencies:** U2

**Files:**
- `docs/exercise_types.md`
- `docs/architecture/pipeline-registry.md`

**Approach:** Add the `input_style: "per_voice"` variant to the harmonization row/section in both documents, noting it shares the `"harmonization"` pipeline and grading path entirely — no new pipeline entry.

**Test expectation:** none — documentation only.

**Verification:** Both documents accurately describe the new flag and its constraints (bass always locked, homophonic sources only, click-based input) so a future reader doesn't need to re-derive them from code.

---

## Risks & Dependencies

- **Content availability**: eligible sources (full 4-voice texture, no ties/rests in the candidate missing voice, 1:1 rhythm with bass) may be scarcer among existing chorale material than expected, since real chorale writing often includes passing tones and suspensions. If U6 struggles to find three eligible phrases, that's a signal worth surfacing rather than working around by loosening U1's validation.
- **Grading looseness accepted, not hidden**: with only one degree of freedom (one missing voice, three given), harmonic-only grading (R7) means a chord-tone in the wrong register or voice position still grades as correct. This is an explicit, documented product trade-off (see KTDs), not an oversight — worth confirming it still feels right once the pilot exercises are played through in U6.

---

## Open Questions

- **Is harmonic-only grading (R7) pedagogically strong enough for this exercise shape, or does it risk being mechanically deducible?** With three of four voices given and only pitch-class membership checked, some common voicings reduce to elimination rather than harmonic reasoning — e.g. a root-position triad with bass, alto, and soprano given and only the tenor missing: if the doubled tone is among the three given voices, the two given pitch classes already account for two of the three chord tones, so the missing pitch class is determined by elimination alone, with no chord-quality or doubling judgment required. In the opposite case (all three chord tones already visible among the given voices), the exercise accepts any of the three pitch classes for the missing voice, including doublings a real harmony exercise would flag as questionable (e.g. doubling a leading tone) — the thing the exercise is nominally testing. This doesn't block milestone 1 (R7 was an explicit, deliberate scope choice), but it's worth deciding now whether to: (a) accept it as-is and see how the pilot exercises feel in practice, (b) curate pilot sources in U6 to avoid the fully-degenerate elimination case, or (c) treat it as a signal that a follow-up milestone should add a lightweight doubling/quality check. Not resolved in this plan — flagging for a decision before or during U6.
