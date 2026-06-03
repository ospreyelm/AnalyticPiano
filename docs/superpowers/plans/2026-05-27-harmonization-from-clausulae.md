# Harmonization From Clausulae Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a management command that generates figured-bass harmonization exercises from the working Clausulae cadence generator.

**Architecture:** Keep this deliberately small. Reuse the Clausulae voice generation path that already works for `generate_roman_from_clausulae`, but emit a harmonization UMTO payload that matches the existing chorale harmonization contract: bass locked, figured-bass analysis slices, and `harmonizationTargets` built by `apps.exercises.harmonization.targets.build_targets_from_umto()`. Do not add Roman-driven target derivation or frontend grader changes.

**Tech Stack:** Django management commands, UMTO Pydantic models, existing Clausulae Python package, existing harmonization target builder, Django tests.

---

## Files

| File | Action |
|---|---|
| `apps/exercises/management/commands/generate_harmonization_from_clausulae.py` | Create command and payload builder |
| `apps/exercises/tests/test_harmonization_from_clausulae.py` | Create payload and command tests |
| `apps/exercises/management/commands/list_exercise_generators.py` | Register command |
| `docs/management_commands.md` | Document command |
| `docs/exercise_types.md` | Document exercise type |

## Requirements

- Generate from Clausulae, not from the abandoned XML-derived corpus path.
- Use figured bass for harmonization target derivation.
- Lock only bass: `locked_voices == ["B"]`.
- Support `--unit`, `--author`, `--voices`, `--public`, `--overwrite`.
- Start with 3-voice Unit 9 material by default.
- Save UMTO rows only.
- Build/update a deterministic playlist.
- Keep the smoke-test warning from the Roman-from-Clausulae command.

## Tasks

### Task 1: Payload Contract

**Files:**
- Create: `apps/exercises/tests/test_harmonization_from_clausulae.py`
- Create: `apps/exercises/management/commands/generate_harmonization_from_clausulae.py`

- [x] Write a failing test that calls `_build_harmonization_payload()` with synthetic C-major S/A/B Clausulae voice events.
- [x] Assert payload fields:
  - `mode == "harmonization"`
  - `analysisType == "figured_bass"`
  - `score.umto.metadata.locked_voices == ["B"]`
  - `score.umto.metadata.harmonization_target_policy.source == "figured_bass"`
  - three analysis slices at offsets `0.0`, `2.0`, `4.0`
  - all slices have `figured_bass` and `raw_figured_bass`
  - `harmonizationTargets` has three entries
  - each target has `lockedVoices.B`
- [x] Run the test and confirm it fails because the command module does not exist.
- [x] Implement `_build_harmonization_payload()` minimally.
- [x] Run the test and confirm it passes.

### Task 2: Command Generation

**Files:**
- Modify: `apps/exercises/tests/test_harmonization_from_clausulae.py`
- Modify: `apps/exercises/management/commands/generate_harmonization_from_clausulae.py`

- [x] Write failing command tests for idempotent generation with `--overwrite`.
- [x] Implement the command using the same combo selection shape as `generate_roman_from_clausulae`: `enumerate_simple`, require bass, require Discant, tonal filter, slot-fingerprint dedup.
- [x] Save exercises with tags:
  - `exercise_type:harmonization_from_clausulae`
  - `corpus:standard_exercises_from_clausulae`
  - `unit:N`
  - `mode:harmonization`
  - `voices:N`
  - `Cadence_Perfect_Authentic`
  - `Diatonic_Triads`
- [x] Create/update student-facing playlist named `Unit N - Authentic Cadences (Harmonization)`; keep voice count only as an internal skill tag.
- [x] Run the command tests and confirm they pass.

### Task 3: Docs And Catalog

**Files:**
- Modify: `apps/exercises/management/commands/list_exercise_generators.py`
- Modify: `docs/management_commands.md`
- Modify: `docs/exercise_types.md`

- [x] Register the command in `list_exercise_generators.py`.
- [x] Add a short management command doc entry with the canonical invocation.
- [x] Add/update the harmonization exercise type documentation.
- [x] Run targeted tests.

### Task 4: Verification

- [x] Run harmonization-specific tests:
  ```bash
  DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest \
    apps.exercises.tests.test_harmonization_from_clausulae \
    apps.exercises.tests.test_harmonization_targets \
    apps.exercises.tests.test_generate_harmonization
  ```
- [x] Run Roman-from-Clausulae regression tests:
  ```bash
  DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest \
    apps/exercises/tests/test_roman_from_clausulae.py -q
  ```
- [x] Generate one local batch:
  ```bash
  DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py \
    generate_harmonization_from_clausulae \
    --unit 9 --author avner-local2025@localhost --voices 3 --public --overwrite
  ```
- [x] Confirm generated row payload has `mode="harmonization"`, `analysisType="figured_bass"`, `locked_voices=["B"]`, three figured-bass slices, and three `harmonizationTargets`.
- [x] Confirm generated playlist page responds locally.
- [ ] Browser-play one generated exercise and verify MIDI grading/completion/performance-data save.
