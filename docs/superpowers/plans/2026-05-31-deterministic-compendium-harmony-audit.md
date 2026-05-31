# Deterministic Compendium Harmony Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the compendium audit CSV derive Roman numerals and figured bass from HarmonyLab's own deterministic scale-degree/table logic, with Music21 kept only as QA.

**Architecture:** Add a small Python adapter around the legacy `analyze.js` chord-code model and `iChords.js`/`jChords.js` tables. The audit/import path will derive per-vertical `z7` stacks from pitch spelling and key, compute a raw legacy RN from the legacy table, normalize that raw font-encoded label for student/review use, compute figured bass with the existing Python engine, and keep Music21 as a QA-only column.

**Tech Stack:** Django management command, Python tests with pytest, music21 for score/chord construction and QA-only Roman output, existing HarmonyLab analysis tables.

---

### Task 1: Legacy Roman Table Adapter

**Files:**
- Create: `apps/exercises/utils/legacy_roman.py`
- Test: `apps/exercises/tests/test_legacy_roman.py`

- [ ] Add tests for chord-code generation and table lookup:
  - A minor `A C E / A` resolves to `i`.
  - A minor `D B D F` resolves to raw `ii°{z}` and normalized `ii°6` through chord code `5/28`.
  - C major `G B D` resolves to `V`.
  - Brace glyph labels normalize from legacy Sebastian-font syntax to plain text (`ii°{z}` → `ii°6`, `ii⌀{z5}` → `iiø65`).

- [ ] Implement table parsing with a narrow regex over `lab/static/js/src/config/analysis/iChords.js` and `jChords.js`.

- [ ] Implement `legacy_chord_code(pitches, tonic)` matching `Analyze.get_chord_code()`:
  - preserve pitch classes in order of lowest appearance,
  - compute pitch classes relative to tonic,
  - encode with `0..9,y,z`,
  - sort upper parts.

- [ ] Implement `legacy_roman_from_pitches(pitches, tonic, mode)` returning chord code, raw table label, and normalized label.

- [ ] Run `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_legacy_roman.py -q`.

### Task 2: Scale-Degree and Figured-Bass Audit Fields

**Files:**
- Modify: `apps/exercises/management/commands/audit_compendium_cadences.py`
- Modify: `apps/exercises/tests/test_audit_compendium_cadences.py`

- [ ] Add tests that audit rows include `z7_stack`, `bass_z7`, `legacy_chord_code`, `legacy_rn_raw`, `our_rn`, `raw_figured_bass`, and `figured_bass`.

- [ ] Add a regression test for `m145-146` in A minor at offset `1.0`:
  - `bass_z7 == "3"`,
  - `legacy_chord_code == "5/28"`,
  - `legacy_rn_raw == "ii°{z}"`,
  - `our_rn == "ii°6"`,
  - `final_rn == "ii°6"`.

- [ ] Add a regression test for `m187-188` in C major at offset `0.0`:
  - `our_rn == "V"`,
  - `final_rn == "V"`.

- [ ] Update the audit command so `final_rn` defaults to our deterministic normalized RN when it is in the unit answer vocabulary; otherwise fall back to the curated template label while preserving `legacy_rn_raw` and `our_rn` for review. `music21_rn` remains a QA column.

- [ ] Compute figured bass using `apps.exercises.utils.figured_bass.compute_figured_bass()`.

- [ ] Run `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_legacy_roman.py apps/exercises/tests/test_audit_compendium_cadences.py -q`.

### Task 3: Import Path Uses Normalized Labels

**Files:**
- Modify: `apps/exercises/compendium_prep.py`
- Modify: `apps/exercises/tests/test_compendium_prep.py`
- Modify: `apps/exercises/data/unit_allowed_answers.additions.json`
- Modify generated: `lab/static/js/src/config/unit_allowed_answers.js`

- [ ] Add a regression test for `m145-146` in A minor: the UMTO `roman_numeral` at offset `1.0` is `ii°6` and `raw_roman_numeral` is `ii°{z}`.

- [ ] Update `prepare_compendium_exercise()` to compute per-target raw/normalized legacy labels from the transposed score. Use `Cad64` for cadential six-four targets and fall back to curated labels when the normalized legacy label is not in the unit answer vocabulary.

- [ ] Add `ii°6` to unit 12 additions and regenerate `lab/static/js/src/config/unit_allowed_answers.js`.

- [ ] Run `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_compendium_prep.py apps/exercises/tests/test_unit_allowed_answers.py::test_additions_propagate_cumulatively -q`.

### Task 4: Gemini Realization Parity Check

**Files:**
- Create: `apps/exercises/compendium_inverse.py`
- Create: `apps/exercises/management/commands/verify_compendium_realization.py`
- Test: `apps/exercises/tests/test_compendium_inverse.py`
- Test: `apps/exercises/tests/test_verify_compendium_realization.py`
- Modify: `apps/exercises/management/commands/list_exercise_generators.py`

- [ ] Copy a self-contained Z7 round-trip realization layer into HarmonyLab. Do not import from or write to `/Users/adorman/Library/CloudStorage/Dropbox/Codebases/clausulae-project`.

- [ ] Add a test that every vendored example in `apps/exercises/data/galant_compendium_cadences.json` round-trips: original notes → Z7 realization → pitch/offset/ql/tie match.

- [ ] Add `verify_compendium_realization`, a no-DB management command that reports mismatches and exits nonzero if any generated notes differ.

- [ ] Register `verify_compendium_realization` in `list_exercise_generators`.

- [ ] Run `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_compendium_inverse.py apps/exercises/tests/test_verify_compendium_realization.py -q`.

### Task 5: Docs and CSV Smoke Test

**Files:**
- Modify: `docs/management_commands.md`

- [ ] Update the `audit_compendium_cadences` documentation to describe deterministic RN/figured-bass columns.

- [ ] Document `verify_compendium_realization`.

- [ ] Generate a focused CSV:
  `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py audit_compendium_cadences --unit 12 --keys A --out scratch/unit12_a_minor_review.csv`

- [ ] Generate a full CSV:
  `DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py audit_compendium_cadences --out scratch/compendium_rn_review.csv`

- [ ] Commit the code, tests, and docs.

## Self-Review

- The plan uses the existing HarmonyLab table logic and figured-bass engine rather than adding a competing analyzer.
- Music21 remains present only for QA comparison.
- The plan does not touch `/Users/adorman/Library/CloudStorage/Dropbox/Codebases/clausulae-project`.
