# Plan: Finish exercise_context service extraction

Date: 2026-06-29
Branch: `refactor/finish-exercise-context-service-extraction`
Parent: P2 (#6 service extraction) of the architecture simplification assessment.

## Problem

`apps/exercises/services/exercise_context.py` already exists and is the
authoritative implementation of `generate_exercise_context`,
`get_adaptive_exercise_for_view`, and `_resolve_analysis_type`. But
`lab/views.py:52-89` keeps a **compatibility shim** that re-exports those
names and injects model globals (`Course`, `Exercise`, `PerformanceData`,
`TaxonomyReader`) into the service module via
`_sync_exercise_context_service_globals()`.

This is the dual-source-of-truth anti-pattern forbidden by
`docs/architecture/engineering-principles.md`. The shim's own docstring
states its removal condition:

> Compatibility condition: remove this wrapper after callers and tests
> import context helpers from apps.exercises.services.exercise_context
> directly.

Production already migrated: `apps/student/views.py` imports the helpers
from the service. The shim's only remaining callers are **4 test files**
plus `lab/views.py` internal call sites.

## Goal

Make `apps.exercises.services.exercise_context` the sole authority. Delete
the shim. No behavior change.

## Changes

### 1. `apps/exercises/tests/test_generate_exercise_context.py`
- `from lab.views import generate_exercise_context` (3 sites: lines ~68,
  ~290, ~353) → `from apps.exercises.services.exercise_context import generate_exercise_context`
- `@patch("lab.views.PerformanceData")` → `@patch("apps.exercises.services.exercise_context.PerformanceData")`
- `@patch("lab.views.TaxonomyReader")` → `@patch("apps.exercises.services.exercise_context.TaxonomyReader")`

### 2. `apps/exercises/tests/test_harmonization_from_clausulae.py`
- Line ~402: `from lab.views import generate_exercise_context` → service import.

### 3. `lab/tests/test_analysis_type_serving.py`
- Line 5: `from lab.views import _resolve_analysis_type` → service import.
- Line 36: `from lab.views import generate_exercise_context` → service import.

### 4. `lab/views.py`
- Migrate internal call sites (lines ~220, ~241, ~327, ~340, ~410) to call
  `exercise_context_service.generate_exercise_context(...)` /
  `exercise_context_service.get_adaptive_exercise_for_view(...)` directly.
- Delete the shim block (lines 52-89): `_sync_exercise_context_service_globals`,
  `_resolve_analysis_type`, `get_adaptive_exercise_for_view`,
  `generate_exercise_context` wrappers.
- Keep the `exercise_context_service` import (line 39) — now used directly.
- Keep `RequirejsContext`, `PlayView`, and other real lab views untouched.

## Verification

- `python -m py_compile` on all touched files.
- `python manage.py check` (system checks, no DB).
- Run the no-DB SimpleTestCase suites:
  `python manage.py test apps.exercises.tests.test_generate_exercise_context lab.tests.test_analysis_type_serving.ResolveAnalysisTypeTest`
- Grep: no remaining `from lab.views import generate_exercise_context`,
  `from lab.views import _resolve_analysis_type`,
  `from lab.views import get_adaptive_exercise_for_view`, or
  `@patch("lab.views.PerformanceData")` / `@patch("lab.views.TaxonomyReader")`.
- DB-dependent tests (`test_analysis_type_serving.GenerateExerciseContextAnalysisPolicyTest`,
  `test_harmonization_from_clausulae.py`, `test_harmonization_pipeline.py`)
  run if the dev DB is available; otherwise flagged as pending.

## Replacement budget

- Responsibilities added: none.
- Responsibilities removed: the `lab.views` compat shim + global-injection hack.
- Retired code: `lab/views.py` lines 52-89.
- Removal condition: met by this change (all callers migrated to the service).
- Phase: deletion in this same change.