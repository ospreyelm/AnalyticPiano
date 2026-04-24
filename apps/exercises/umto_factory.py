"""Canonical factory for creating UMTO-backed Exercise rows.

This module owns the CIR→UMTO conversion. Every Exercise creation path in the
codebase flows through `save_umto_exercise`. Direct `Exercise(data={...}).save()`
for new rows is blocked by `Exercise.clean()` and `Exercise.save()` guards.

Emergency bypass: set HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 for one-shot migration
scripts only. Never set in CI, tests, or production.
"""

from __future__ import annotations


class NonUMTOExerciseError(ValueError):
    """Raised when save_umto_exercise is handed legacy-shaped data, or when
    Exercise.save() / Exercise.clean() sees a new row whose data fails UMTO
    validation."""
