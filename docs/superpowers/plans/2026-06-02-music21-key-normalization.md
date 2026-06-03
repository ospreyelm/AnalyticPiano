# Music21 Key Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop maintenance/backfill commands from failing with `Cannot make a step out of 'J'` when stored UMTO/CIR data uses HarmonyLab key tokens such as `jC_` and `iA_`.

**Architecture:** Add one backend utility that converts HarmonyLab key tokens to music21-compatible key names and use it at every backend music21 boundary. Keep HarmonyLab storage unchanged (`jC_`, `iA_`, etc. remain canonical in UMTO/CIR), but ensure music21 only receives conventional strings like `C`, `A minor`, `Bb`, or `F# minor`. Add focused tests that reproduce the failure mode and verify maintenance commands skip fewer rows without widening unrelated behavior.

**Tech Stack:** Django management commands, `music21`, existing `apps.exercises.utils.music21_builder`, existing HarmonyLab key constants, Django test runner / pytest.

---

## File Structure

- Create: `apps/exercises/utils/key_normalization.py`
  - Single backend source of truth for converting between HarmonyLab key tokens and music21 key names.
- Modify: `apps/exercises/utils/music21_builder.py`
  - Use the new converter when reconstructing music21 scores from stored CIR/UMTO data.
- Modify: `apps/exercises/management/commands/backfill_raw_roman_numeral.py`
  - Ensure metadata keys passed into UMTO rebuilds stay HarmonyLab-compatible while any music21 analysis path gets normalized keys.
- Modify: `apps/exercises/management/commands/recompute_chorale_analysis.py`
  - Guard refresh logic against stored HarmonyLab key tokens in existing rows where the corpus/global key fallback is not enough.
- Modify: `apps/exercises/management/commands/backfill_skill_tags.py`
  - Verify this command uses `music21_builder.build_score_from_data()` and does not perform its own raw `music21.key.Key()` call on `j...` / `i...` tokens.
- Test: `apps/exercises/tests/test_key_normalization.py`
  - Unit tests for all common HarmonyLab key shapes.
- Test: `apps/exercises/tests/test_music21_builder.py` or existing nearby test file
  - Regression test that `build_score_from_data()` accepts `meta.key = "jC_"` and `meta.key = "iA_"`.
- Test: targeted command tests if command logic changes directly.

---

## Task 1: Add A Backend Key Normalization Utility

**Files:**
- Create: `apps/exercises/utils/key_normalization.py`
- Test: `apps/exercises/tests/test_key_normalization.py`

- [ ] **Step 1: Write failing tests**

Create `apps/exercises/tests/test_key_normalization.py`:

```python
from django.test import SimpleTestCase


class KeyNormalizationTest(SimpleTestCase):
    def test_harmony_key_to_music21_major_natural(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("jC_"), "C")
        self.assertEqual(harmony_key_to_music21("jG_"), "G")

    def test_harmony_key_to_music21_major_accidentals(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("jBb"), "Bb")
        self.assertEqual(harmony_key_to_music21("jF#"), "F#")

    def test_harmony_key_to_music21_minor(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("iA_"), "A minor")
        self.assertEqual(harmony_key_to_music21("iF#"), "F# minor")
        self.assertEqual(harmony_key_to_music21("iBb"), "Bb minor")

    def test_harmony_key_to_music21_accepts_clean_existing_names(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("C"), "C")
        self.assertEqual(harmony_key_to_music21("F#m"), "F# minor")
        self.assertEqual(harmony_key_to_music21("A minor"), "A minor")
        self.assertEqual(harmony_key_to_music21(None), "C")
        self.assertEqual(harmony_key_to_music21(""), "C")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_key_normalization -v 2
```

Expected: fails with `ModuleNotFoundError: No module named 'apps.exercises.utils.key_normalization'`.

- [ ] **Step 3: Implement the utility**

Create `apps/exercises/utils/key_normalization.py`:

```python
"""Key normalization helpers for backend music21 boundaries.

HarmonyLab stores tonal keys as pseudo keys like `jC_`, `jBb`, `iA_`, and
`iF#`. music21 expects conventional key names such as `C`, `Bb`, `A minor`,
and `F# minor`.
"""


def harmony_key_to_music21(value: str | None, *, default: str = "C") -> str:
    if not value:
        return default

    key_text = str(value).strip()
    if not key_text:
        return default

    if key_text.startswith(("j", "i")) and len(key_text) >= 2:
        mode_prefix = key_text[0]
        tonic = key_text[1:].replace("_", "")
        tonic = tonic.replace("-", "b")
        if not tonic:
            return default
        if mode_prefix == "i":
            return f"{tonic} minor"
        return tonic

    normalized = key_text.replace("-", "b")
    if normalized.endswith("m") and not normalized.endswith(" minor"):
        return f"{normalized[:-1]} minor"
    return normalized
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_key_normalization -v 2
```

Expected: all tests pass.

---

## Task 2: Use Normalized Keys In `music21_builder`

**Files:**
- Modify: `apps/exercises/utils/music21_builder.py`
- Test: `apps/exercises/tests/test_music21_builder.py`

- [ ] **Step 1: Write regression tests**

Create or extend `apps/exercises/tests/test_music21_builder.py`:

```python
from django.test import SimpleTestCase


def _minimal_score_data(key_value):
    return {
        "score": {
            "meta": {"key": key_value, "time_signature": "4/4"},
            "measures": [
                {
                    "number": 1,
                    "staves": {
                        "treble": {
                            "voices": [
                                {
                                    "items": [
                                        {
                                            "kind": "note",
                                            "pitch": {"step": "C", "alter": 0, "octave": 4},
                                            "duration": {"type": "q", "dots": 0},
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                }
            ],
        }
    }


class Music21BuilderKeyTest(SimpleTestCase):
    def test_build_score_accepts_harmonylab_major_key(self):
        from apps.exercises.utils.music21_builder import build_score_from_data

        score = build_score_from_data(_minimal_score_data("jC_"))

        self.assertEqual(len(score.parts), 1)

    def test_build_score_accepts_harmonylab_minor_key(self):
        from apps.exercises.utils.music21_builder import build_score_from_data

        score = build_score_from_data(_minimal_score_data("iA_"))

        self.assertEqual(len(score.parts), 1)
```

- [ ] **Step 2: Run tests and verify current behavior**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_music21_builder -v 2
```

Expected: tests may pass today if `build_score_from_data()` does not instantiate a music21 key object yet. Keep them as regression coverage and continue to Step 3.

- [ ] **Step 3: Apply converter at builder boundary**

In `apps/exercises/utils/music21_builder.py`, import the converter:

```python
from apps.exercises.utils.key_normalization import harmony_key_to_music21
```

Then change:

```python
key_sig = meta.get('key', 'C')
```

to:

```python
key_sig = harmony_key_to_music21(meta.get('key', 'C'))
```

If `key_sig` remains unused, add a comment explaining why it is normalized here for future key-signature insertion:

```python
# Normalize now so future music21 key insertion cannot receive HarmonyLab's
# `j...` / `i...` pseudo-key tokens.
key_sig = harmony_key_to_music21(meta.get('key', 'C'))
```

- [ ] **Step 4: Run builder tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_music21_builder apps.exercises.tests.test_key_normalization -v 2
```

Expected: tests pass.

---

## Task 3: Audit And Fix Direct `music21.key.Key()` Callers

**Files:**
- Modify callers found by search.
- Test: targeted command or utility tests.

- [ ] **Step 1: Search direct key construction**

Run:

```bash
rg -n "key\\.Key\\(|m21key\\.Key\\(|Key\\(" apps/exercises -S
```

Expected: list includes generation commands and utilities that may pass clean keys or HarmonyLab pseudo keys.

- [ ] **Step 2: Classify each result**

For each result, classify in a short note in the PR description:

```text
safe: import_bach_phrases uses music21 corpus key objects directly
needs normalization: backfill path reads metadata["key"] from stored UMTO
safe: generate_unit1 receives clean corpus key names before converting to HarmonyLab format
```

- [ ] **Step 3: Patch unsafe callers**

For any caller that uses a stored exercise/UMTO/CIR key, wrap it:

```python
from apps.exercises.utils.key_normalization import harmony_key_to_music21

global_key = m21key.Key(harmony_key_to_music21(stored_key))
```

Do not wrap variables that are already `music21.key.Key` objects.

- [ ] **Step 4: Add direct regression test for one unsafe caller**

If `backfill_raw_roman_numeral` or another command has direct key construction, add a test that creates a minimal UMTO row with `metadata.key = "jC_"` and runs the command in `--dry-run` or mocked-analysis mode without `Cannot make a step out of 'J'`.

- [ ] **Step 5: Run targeted tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_key_normalization apps.exercises.tests.test_music21_builder -v 2
```

Add any command-specific test module created in Step 4 to this command.

---

## Task 4: Improve Refresh Command Reporting

**Files:**
- Modify: `apps/exercises/management/commands/recompute_chorale_analysis.py`
- Modify: `apps/exercises/management/commands/backfill_skill_tags.py`
- Test: command tests if existing, otherwise small utility tests.

- [ ] **Step 1: Add failure category counters**

In broad maintenance commands that currently print many per-row failures, add counters for:

```python
failure_counts = {
    "no_source_score": 0,
    "no_measures": 0,
    "invalid_key": 0,
    "music21_error": 0,
}
```

- [ ] **Step 2: Classify HarmonyLab key failures**

When catching exceptions, classify:

```python
if "Cannot make a step out of 'J'" in str(e):
    failure_counts["invalid_key"] += 1
```

After Task 3, this should trend to zero for commands that are meant to analyze stored HarmonyLab-keyed rows.

- [ ] **Step 3: Print summary**

At command end, print:

```python
self.stdout.write(f"Failure categories: {failure_counts}")
```

- [ ] **Step 4: Run dry-run refresh smoke test**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py refresh_all_exercises --dry-run
```

Expected: no `Cannot make a step out of 'J'` for rows whose stored key is merely `j...` / `i...`; remaining skips are summarized.

---

## Task 5: Document The Key Boundary

**Files:**
- Modify: `docs/redundancy_analysis_report.md`
- Modify: `docs/management_commands.md` if maintenance command behavior changes.

- [ ] **Step 1: Update redundancy report**

In the key normalization section of `docs/redundancy_analysis_report.md`, add:

```markdown
Backend music21 boundaries must call `apps.exercises.utils.key_normalization.harmony_key_to_music21()` before constructing `music21.key.Key` from stored Exercise/UMTO/CIR key strings. HarmonyLab storage remains `j...` / `i...`; music21 receives conventional key names only.
```

- [ ] **Step 2: Update maintenance command docs**

If refresh/backfill output changes, add one sentence to `docs/management_commands.md` under the refresh command section:

```markdown
Stored HarmonyLab key tokens are normalized before music21 analysis; `Cannot make a step out of 'J'` should be treated as a regression.
```

- [ ] **Step 3: Run docs grep**

Run:

```bash
rg -n "Cannot make a step out of 'J'|harmony_key_to_music21|jC_" docs apps/exercises -S
```

Expected: new docs mention the rule, tests cover `jC_`, and no unsafe production caller is knowingly passing `j...` keys to music21.

---

## Self-Review

- Spec coverage: The plan covers the observed `Cannot make a step out of 'J'` failure, centralizes backend key conversion, patches likely music21 boundaries, improves maintenance output, and documents the rule.
- Placeholder scan: No TBD/TODO placeholders remain; every task has concrete files, code snippets, and verification commands.
- Type consistency: The converter is consistently named `harmony_key_to_music21`; tests and command snippets use the same function name.
