# Plan: Harmonization Exercises from Clausulae (Unit 9)

Date: 2026-05-27

## Goal

Generate UMTO harmonization exercises sourced from clausulae cadences.
Student sees soprano + bass (locked), supplies inner voices (A, T) by MIDI.
Graded by `InteractionMode.HARMONIZATION` path — same as Bach-phrase harmonization.

## Pre-Implementation Checks (Done)

- `targets.py` has no `source="roman"` branch; uses `content.get("roman_numeral")` as label
  fallback — safe because AnalysisLayer already populates `roman_numeral` (confirmed in RN command).
- No fixed target-count assumptions in JS — safe for 3-target clausulae cadences.
- `maxMeasures` defaults to 4 in JS; must set `display.maxMeasures: 2` explicitly (already a
  pattern in the RN command).
- No other blockers found.

## Architecture Decisions

**Locked voices (Unit 9):** `["S", "B"]` — soprano and bass given, student supplies A + T.
`soprano_given` mode (locked=["S"] only) is harder and belongs in Unit 10+; not in scope here.

**`HarmonizationTargetPolicy.source`:** `"roman"` — AnalysisSlices carry `roman_numeral="I"/"V"`.
`analysisType` in frontend payload stays `"roman"` (consistent with RN command).

**Combo filter:** same `_tonal_valid()` constraint from shared module (2∈ANT, NOT 4∈ULT without 2).

**Keys:** same `TARGET_KEYS = ["C", "F", "G", "D", "Bb"]` as RN command.

**Voice variants:** 3-voice only for Unit 9 (Soprano + Alto + Bass, student supplies Alto).
4-voice (student supplies Alto + Tenor) is a stretch goal for later.

## Tasks

### Step 1: Extract shared module

- [ ] Create `apps/exercises/management/commands/clausulae_exercise_utils.py`
- [ ] Move from `generate_roman_from_clausulae.py`:
  - `_OCTAVE`, `TARGET_KEYS`, `_DUR_SIMPLE`, `_CADENCE_RN`, `_SOL_ABBR`
  - `_m21_note_to_pitch()`
  - `_realize_events()`
  - `_solfege_label()`, `_combo_label()`
  - `_assign_slots()`
  - `_tonal_valid()` (delegates to `clausulae.constraints.tonal_sonority_ok`)
  - `_slot_fingerprint()`
  - `_build_grading_slices()`
  - `_save_exercise()`
  - `_build_playlist()`
- [ ] Also move `_save_exercise` and `_build_playlist` from `generate_clausulae_b1.py`
  (they are identical — three-command convergence confirms worth of shared module)
- [ ] Update `generate_roman_from_clausulae.py` to import from shared module
- [ ] Update `generate_clausulae_b1.py` to import from shared module
- [ ] Run full test suite — no behavior change expected
  ```bash
  DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
    apps.exercises.tests.test_roman_from_clausulae \
    apps.exercises.tests.test_umto_contract
  ```

### Step 2: Write `_build_harmonization_payload()`

Differences from `_build_identification_payload()`:

| Field | Identification | Harmonization |
|---|---|---|
| `mode` | `IDENTIFICATION` | `HARMONIZATION` |
| `locked_voices` | absent | `["S", "B"]` |
| `harmonization_target_policy.source` | absent | `"roman"` |
| `analysis` slices | `is_target=True` × 3 | `is_target=False` × 3, `roman_numeral` set |
| `grading` | RN answer slots | `GradingSlice` per onset, all voice MIDI pitches |
| `analysisType` | `"roman"` | `"roman"` |
| `display.maxMeasures` | `2` | `2` |
| `inputModeFixed` | `"dropdown"` | absent (not applicable) |
| `harmonizationTargets` | absent | built by `build_targets_from_umto()` |

AnalysisSlices for harmonization: `is_target=False` (they are context for the grader,
not student-answer targets). Labels: ANT=`"I"`, PEN=`"V"`, ULT=`"I"` — same as RN command.

GradingSlices: one per onset (ANT/PEN/ULT), `target_midi_pitches` = sorted MIDI of all
voices active at that onset. Reuse `_build_grading_slices()` from shared module unchanged.

After building UMTO, call `build_targets_from_umto(umto_dict)` from
`apps/exercises/harmonization/targets.py` to derive `harmonizationTargets` array, then
embed in payload as `payload["harmonizationTargets"] = targets`.

- [ ] Write `_build_harmonization_payload()` in new command file
- [ ] Write unit tests in `apps/exercises/tests/test_harmonization_from_clausulae.py`:
  - Test: payload has `mode="harmonization"`
  - Test: `locked_voices == ["S", "B"]`
  - Test: `harmonizationTargets` has 3 entries (ANT/PEN/ULT)
  - Test: each target has `lockedVoices` with both S and B populated
  - Test: `grading` slices have correct MIDI pitches for a known combo in C

### Step 3: Write management command

- [ ] Create `apps/exercises/management/commands/generate_harmonization_from_clausulae.py`
- [ ] Args: `--unit`, `--author`, `--voices` (default 3), `--public`, `--overwrite`
- [ ] Same combo selection as RN command: `enumerate_simple` + Discant filter + `_tonal_valid` + dedup
- [ ] Playlist name: `"Unit {N} — Authentic Cadences (Harmonization) {N}-voice"`
- [ ] Description format: `"{N}-part Harmonization Cadence in {KEY} [{label}]"`
  (verify ≤60 chars for 3-voice; use `var{N}` suffix for 4-voice if needed)
- [ ] stdout warning: same smoke-test reminder as RN command

### Step 4: Documentation

- [ ] Add entry to `docs/management_commands.md`
- [ ] Add entry to `docs/exercise_types.md`
- [ ] Register in `apps/exercises/management/commands/list_exercise_generators.py`
- [ ] Mark all tasks above `[x]` when done

### Step 5: Smoke test

- [ ] Generate Unit 9 3-voice batch:
  ```bash
  DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py \
    generate_harmonization_from_clausulae \
    --unit 9 --author avner-local2025@localhost --voices 3 --public --overwrite
  ```
- [ ] Open one exercise in student app
- [ ] Verify: soprano + bass shown in score, inner voice slots active
- [ ] Verify: student can play A (+ T for 4-voice) and exercise grades correctly
- [ ] Verify: completion registers and performance data saves

## Files Created / Modified

| File | Action |
|---|---|
| `apps/exercises/management/commands/clausulae_exercise_utils.py` | Create |
| `apps/exercises/management/commands/generate_roman_from_clausulae.py` | Update imports |
| `apps/exercises/management/commands/generate_clausulae_b1.py` | Update imports |
| `apps/exercises/management/commands/generate_harmonization_from_clausulae.py` | Create |
| `apps/exercises/management/commands/list_exercise_generators.py` | Update |
| `apps/exercises/tests/test_harmonization_from_clausulae.py` | Create |
| `docs/management_commands.md` | Update |
| `docs/exercise_types.md` | Update |

## Out of Scope

- 4-voice variant (student supplies A + T) — Unit 10+
- `soprano_given` locked mode (harder) — Unit 10+
- Visual display of locked voices in score (assumed already handled by harmonization JS path)
