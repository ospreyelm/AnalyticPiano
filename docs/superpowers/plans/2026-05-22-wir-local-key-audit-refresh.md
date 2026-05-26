# WiR Local Key Audit Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a management command that audits inferred When in Rome local-key transposition shifts for existing Bach chorale exercises, and document that `recompute_chorale_analysis` refreshes stored UMTO analysis using the same normalization logic.

**Architecture:** Keep import-time key normalization centralized in `import_bach_phrases.py`. The new audit command scans existing rows tagged `riem:N`, groups by Riemenschneider number, infers the local-key shift from the music21 score once per chorale, and reports rows that would be affected. Existing `recompute_chorale_analysis` remains the write path for refreshing `score.umto.analysis`.

**Tech Stack:** Django management commands, music21 chorales corpus, existing `Exercise.skill_tags`, existing UMTO JSON payloads, Django test runner.

---

### Task 1: Audit Command

**Files:**
- Create: `apps/exercises/management/commands/audit_wir_local_key_shifts.py`
- Test: `apps/exercises/tests/test_audit_wir_local_key_shifts.py`

- [x] **Step 1: Write failing tests**

Add tests that create two minimal `Exercise` rows tagged `riem:17` and `riem:1`, then run:

```python
call_command("audit_wir_local_key_shifts", stdout=out)
```

Expected output includes one `R17 +2` row and one `R1 0` row.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_audit_wir_local_key_shifts -v 2
```

Expected: fails because the command does not exist.

- [x] **Step 3: Implement command**

Create `audit_wir_local_key_shifts` with options:

```text
--tag TAG       scope to rows whose skill_tags contain TAG
--riem N        scope to one Riemenschneider number
```

The command should:

```python
from music21.corpus import chorales
from apps.exercises.management.commands.import_bach_phrases import (
    _infer_wir_local_key_transposition,
)
```

For each distinct `riem:N` present in scoped exercises, load the score, infer the shift against `score.measures(1, min(last_measure, 12))`, and print:

```text
R17 +2 rows=1
R1 0 rows=1
```

- [x] **Step 4: Run tests to verify pass**

Run the same command as Step 2. Expected: OK.

### Task 2: Refresh Command Documentation

**Files:**
- Modify: `docs/management_commands.md`
- Modify: `apps/exercises/management/commands/list_exercise_generators.py`
- Modify: `apps/exercises/management/commands/recompute_chorale_analysis.py`

- [x] **Step 1: Update docs and command catalog**

Document:

```bash
python manage.py audit_wir_local_key_shifts
python manage.py audit_wir_local_key_shifts --riem 17
python manage.py recompute_chorale_analysis --riem 17
```

State that `recompute_chorale_analysis` refreshes existing rows using the same WiR local-key transposition logic.

- [x] **Step 2: Add command to `list_exercise_generators.CATALOG`**

Add `audit_wir_local_key_shifts` under Refresh / recompute.

- [x] **Step 3: Update recompute command help text**

Mention local-key transposition normalization in the module docstring/help text.

### Task 3: Verification

**Files:**
- Existing tests and docs only.

- [x] **Step 1: Run focused tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_audit_wir_local_key_shifts apps.exercises.tests.test_import_bach_phrases.BuildRomanAnalysisOverridesTestCase.test_roman_mode_transposes_wir_local_keys_to_music21_score_key -v 2
```

- [x] **Step 2: Run command smoke checks**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py audit_wir_local_key_shifts --riem 17
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py recompute_chorale_analysis --riem 17 --dry-run
```

Expected: audit prints `R17 +2`; dry-run reports rows it would update or unchanged.
