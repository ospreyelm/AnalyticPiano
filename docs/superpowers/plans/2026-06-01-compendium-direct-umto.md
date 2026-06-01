# Compendium Direct UMTO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve polyphony in Galant compendium Roman-numeral exercises so student-player rendering matches the source cadence.

**Architecture:** Keep the existing curated compendium templates and playlist command. Replace the fragile `music21 Score -> m21_to_cir()` conversion in `prepare_compendium_exercise()` with a compendium-specific CIR builder that assigns simultaneous notes to separate staff voices before `save_umto_exercise()` builds UMTO.

**Tech Stack:** Django management commands, music21, UMTO payload factory, pytest/Django tests.

---

### Task 1: Regression Test For Compound Three-Voice Polyphony

**Files:**
- Modify: `apps/exercises/tests/test_compendium_prep.py`

- [ ] Add a test for `m075-076` that asserts the generated CIR has two measures, two upper-staff voices in the final measure, and that the frontend payload built from it also has two measures.

- [ ] Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_compendium_prep.py::test_compound_three_voice_keeps_simultaneous_upper_notes_in_separate_voices -q
```

Expected before implementation: fail because the old converter serializes final simultaneous upper notes into one voice and creates a third rendered measure.

### Task 2: Compendium-Specific CIR Builder

**Files:**
- Modify: `apps/exercises/compendium_prep.py`

- [ ] Add a helper that reads transposed `music21` parts by measure, assigns notes in each part to monophonic lanes using offsets and pitch order, emits rests for gaps, and maps one/two lanes per staff to legacy CIR voices.

- [ ] Keep the existing curated Roman template and unit binning logic unchanged.

### Task 3: Wire And Verify

**Files:**
- Modify: `apps/exercises/compendium_prep.py`
- Modify: `apps/exercises/tests/test_compendium_prep.py`

- [ ] Replace `m21_to_cir(tscore, key_override=hl_key)` with the new compendium CIR builder.

- [ ] Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 -m pytest apps/exercises/tests/test_compendium_prep.py -q
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py check
```

Expected after implementation: tests pass; Django check has only the existing CKEditor warning.
