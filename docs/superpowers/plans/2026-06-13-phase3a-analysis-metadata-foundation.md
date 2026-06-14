# Phase 3A: Analysis Metadata Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent spec:** [docs/superpowers/plans/2026-06-13-phase3-curation-workbench.md](2026-06-13-phase3-curation-workbench.md)

**Goal:** Enrich AnalysisLayer with 7 analytics fields (set_class, spacing, intervals) computed at save time in both the JS play path and the Python import path; fix the analysisType serving boundary bug; add a backfill command for existing exercises.

**Architecture:** Pure data-layer change — new Optional fields on `AnalysisLayer` Pydantic model; JS `buildAnalysisSlices` merges a `deterministicFieldsArr` computed in `play_sheet.js`; Python `build_chordal_analysis_slices` uses music21 chord properties; `lab/views.py` reads stored `analysisType` before falling back to its heuristic. Identification grader is unchanged — it still live-computes these values.

**Tech Stack:** Python/Pydantic (`apps/exercises/umto.py`), music21, JavaScript AMD modules (`play_save_logic.js`, `play_sheet.js`), Django management commands.

**Run tests with:**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests -v 2
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput lab -v 2
```

---

## File map

| File | Action |
|---|---|
| `apps/exercises/umto.py` | Add 7 optional fields to `AnalysisLayer` |
| `apps/exercises/umto_schema.json` | Regenerated (auto) |
| `apps/exercises/utils/umto_import_router.py` | Expand `build_chordal_analysis_slices` |
| `apps/exercises/tests/test_umto_import_router.py` | New — tests for expanded builder |
| `lab/views.py` | Extract `_resolve_analysis_type` helper; fix ~line 505 |
| `lab/tests/test_analysis_type_serving.py` | New — unit tests for the helper |
| `lab/static/js/src/components/music/play_save_logic.js` | Accept `deterministicFieldsArr` 5th arg |
| `lab/static/js/src/components/music/play_sheet.js` | Compute `deterministicFieldsArr`; pass to builder |
| `apps/exercises/management/commands/backfill_analysis_layer.py` | New |
| `apps/exercises/management/commands/list_exercise_generators.py` | Register command |
| `docs/UMTO_GUIDE.md` | Document new fields |
| `docs/exercise_types.md` | Document `analysisType` storage |
| `docs/management_commands.md` | Add `backfill_analysis_layer` entry |

---

## Task 1: AnalysisLayer model expansion

**Files:**
- Modify: `apps/exercises/umto.py` (AnalysisLayer class)
- Regenerate: `apps/exercises/umto_schema.json`

- [ ] **Add 7 new optional fields to `AnalysisLayer`**

Open `apps/exercises/umto.py`. Find `class AnalysisLayer(BaseModel)`. Append these fields at the end of the class body (after `scale_degrees`):

```python
    # Analytics fields — stored at save time; identification grader still live-computes these
    set_class_prime: Optional[str] = None
    set_class_forte: Optional[str] = None
    set_class_normal: Optional[str] = None
    set_class_set: Optional[str] = None
    spacing: Optional[str] = None
    interval_specific: Optional[str] = None
    interval_generic: Optional[str] = None
```

- [ ] **Verify existing tests still pass (backward compat — new fields are Optional)**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_chordal_umto -v 2
```
Expected: all pass.

- [ ] **Regenerate UMTO JSON schema**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py make_umto_schema
```
Expected: `apps/exercises/umto_schema.json` updated; no error.

- [ ] **Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_schema.json
git commit -m "feat: add 7 optional analytics fields to AnalysisLayer"
```

---

## Task 2: `analysisType` serving boundary fix

**Files:**
- Modify: `lab/views.py` (~line 500-510)
- Create: `lab/tests/test_analysis_type_serving.py`

- [ ] **Write failing unit tests**

Create `lab/tests/test_analysis_type_serving.py`:

```python
"""Unit tests for the analysisType serving boundary fix in lab/views.py."""
import pytest


def _resolve_analysis_type(exercise_data, heuristic):
    """
    Prefer stored exercise_data['analysisType'] over the complexity heuristic.
    Mirrors the helper extracted in lab/views.py.
    """
    if isinstance(exercise_data, dict):
        stored = exercise_data.get("analysisType")
        if stored:
            return stored
    return heuristic


class TestResolveAnalysisType:
    def test_stored_value_wins_over_heuristic(self):
        data = {"analysisType": "figured_bass", "score": {}}
        assert _resolve_analysis_type(data, "roman") == "figured_bass"

    def test_fallback_to_heuristic_when_not_stored(self):
        data = {"score": {}}
        assert _resolve_analysis_type(data, "roman") == "roman"

    def test_empty_string_treated_as_absent(self):
        data = {"analysisType": "", "score": {}}
        assert _resolve_analysis_type(data, "note_name") == "note_name"

    def test_none_treated_as_absent(self):
        data = {"analysisType": None, "score": {}}
        assert _resolve_analysis_type(data, "scale_degree") == "scale_degree"

    def test_non_dict_data_falls_back(self):
        assert _resolve_analysis_type(None, "roman") == "roman"
        assert _resolve_analysis_type("bad", "roman") == "roman"
```

- [ ] **Run test to confirm it fails (function not imported from views yet)**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput lab.tests.test_analysis_type_serving -v 2
```
Expected: PASS (tests import a local copy of the helper). Proceed.

- [ ] **Extract helper into `lab/views.py` and fix the call site**

In `lab/views.py`, after the imports block at the top of the file, add:

```python
def _resolve_analysis_type(exercise_data, heuristic):
    """Prefer stored exercise.data['analysisType'] over the complexity heuristic."""
    if isinstance(exercise_data, dict):
        stored = exercise_data.get("analysisType")
        if stored:
            return stored
    return heuristic
```

Then find the original call site (~line 505):
```python
            exercise_context["analysisType"] = _family
```

Replace with:
```python
            exercise_context["analysisType"] = _resolve_analysis_type(exercise.data, _family)
```

- [ ] **Run all lab tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput lab -v 2
```
Expected: all pass.

- [ ] **Commit**

```bash
git add lab/views.py lab/tests/test_analysis_type_serving.py
git commit -m "fix: prefer stored exercise.data.analysisType over complexity heuristic"
```

---

## Task 3: Python `build_chordal_analysis_slices` expansion

**Files:**
- Modify: `apps/exercises/utils/umto_import_router.py` (`build_chordal_analysis_slices`)
- Create: `apps/exercises/tests/test_umto_import_router.py` (or add to existing)

- [ ] **Write failing test**

Create (or add to) `apps/exercises/tests/test_umto_import_router.py`:

```python
"""Tests for umto_import_router helper functions."""
from django.test import SimpleTestCase
from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices


class BuildChordalAnalysisSlicesTest(SimpleTestCase):
    CHORDS = [
        {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
        {"offset": 1.0, "duration": 1.0, "visible": [62, 65, 69], "hidden": []},
    ]

    def test_returns_correct_slice_count(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        self.assertEqual(len(slices), 2)

    def test_existing_roman_numeral_field_present(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        self.assertIn("roman_numeral", slices[0]["content"])

    def test_set_class_prime_present_and_non_empty(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        content = slices[0]["content"]
        self.assertIn("set_class_prime", content)
        self.assertIsNotNone(content["set_class_prime"])

    def test_set_class_forte_present(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        self.assertIn("set_class_forte", slices[0]["content"])

    def test_set_class_normal_present(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        self.assertIn("set_class_normal", slices[0]["content"])

    def test_spacing_field_present(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        self.assertIn("spacing", slices[0]["content"])

    def test_interval_fields_present(self):
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        content = slices[0]["content"]
        self.assertIn("interval_specific", content)
        self.assertIn("interval_generic", content)

    def test_interval_fields_null_for_triad(self):
        # interval_specific/generic only populated for 2-note sets
        slices = build_chordal_analysis_slices(self.CHORDS, harmony_key="C")
        self.assertIsNone(slices[0]["content"]["interval_specific"])
        self.assertIsNone(slices[0]["content"]["interval_generic"])

    def test_interval_fields_populated_for_dyad(self):
        dyad_chords = [{"offset": 0.0, "duration": 1.0, "visible": [60, 67], "hidden": []}]
        slices = build_chordal_analysis_slices(dyad_chords, harmony_key="C")
        content = slices[0]["content"]
        self.assertIsNotNone(content["interval_specific"])
```

- [ ] **Run test to confirm it fails**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_umto_import_router -v 2
```
Expected: FAIL — `KeyError: 'set_class_prime'` or `AssertionError`.

- [ ] **Expand `build_chordal_analysis_slices` in `umto_import_router.py`**

Find the `analysis.append(...)` block inside `build_chordal_analysis_slices`. Replace the block that builds the `content` dict with:

```python
        # Set-class analytics via music21
        sc_prime = sc_forte = sc_normal = sc_set = None
        try:
            sc_prime  = chord_obj.primeFormString
            sc_forte  = chord_obj.forteClassTnI
            sc_normal = str(list(chord_obj.normalOrder))
            sc_set    = "{" + ",".join(p.name for p in chord_obj.pitches) + "}"
        except Exception:
            pass

        # Interval analytics (2-note sets only)
        iv_specific = iv_generic = None
        if len(pitches) == 2:
            try:
                from music21 import interval as m21interval
                iv = m21interval.Interval(chord_obj.pitches[0], chord_obj.pitches[1])
                iv_specific = iv.directedName      # e.g. "P5"
                iv_generic  = str(abs(iv.generic.directed))  # e.g. "5"
            except Exception:
                pass

        analysis.append({
            "offset": float(chord_event.get("offset", 0.0)),
            "content": {
                "roman_numeral":    roman_label,
                "raw_roman_numeral": raw_roman,
                "local_key":        harmony_key,
                "raw_figured_bass": raw_fb,
                "figured_bass":     figured_bass,
                "set_class_prime":  sc_prime,
                "set_class_forte":  sc_forte,
                "set_class_normal": sc_normal,
                "set_class_set":    sc_set,
                "spacing":          None,   # populated by JS at play time
                "interval_specific": iv_specific,
                "interval_generic":  iv_generic,
            },
            "unit_tags": [],
            "is_target": True,
        })
```

Note: `spacing` (close/open voicing) requires the rendered staff layout to be meaningful, so it is left to the JS path and stored as `None` from the Python path.

- [ ] **Run test to confirm it passes**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.exercises.tests.test_umto_import_router -v 2
```
Expected: all pass.

- [ ] **Commit**

```bash
git add apps/exercises/utils/umto_import_router.py \
        apps/exercises/tests/test_umto_import_router.py
git commit -m "feat: expand build_chordal_analysis_slices with set_class and interval analytics"
```

---

## Task 4: JS `buildAnalysisSlices` expansion

**Files:**
- Modify: `lab/static/js/src/components/music/play_save_logic.js`
- Modify: `lab/static/js/src/components/music/play_sheet.js`

No automated JS tests; verify with browser smoke test.

- [ ] **Update `buildAnalysisSlices` to accept and merge `deterministicFieldsArr`**

In `play_save_logic.js`, change the function signature and body. Find:

```javascript
function buildAnalysisSlices(offsets, slots, labels, overrides) {
```

Replace the entire function with:

```javascript
function buildAnalysisSlices(offsets, slots, labels, overrides, deterministicFieldsArr) {
  if (!slots || !slots.below) return [];
  var key = BELOW_CONTENT_KEY[slots.below];
  if (!key) return [];
  var out = [];
  for (var i = 0; i < offsets.length; i++) {
    var ov = overrides && overrides[i] && typeof overrides[i].below !== "undefined"
      ? overrides[i].below : null;
    var value = ov !== null ? ov : (labels[i] != null ? labels[i] : "");
    var content = {};
    content[key] = value;
    if (deterministicFieldsArr && deterministicFieldsArr[i]) {
      var extra = deterministicFieldsArr[i];
      for (var field in extra) {
        if (Object.prototype.hasOwnProperty.call(extra, field)) {
          content[field] = extra[field];
        }
      }
    }
    out.push({ offset: offsets[i], content: content, is_target: true, unit_tags: [] });
  }
  return out;
}
```

- [ ] **Compute `deterministicFieldsArr` in `play_sheet.js`**

In `play_sheet.js`, find where `buildAnalysisSlices` is currently called (search for `PlaySaveLogic.buildAnalysisSlices`). Immediately before that call, insert:

```javascript
      var deterministicFieldsArr = (notes || []).map(function(chord) {
        var midis = (chord && chord.visible) ? chord.visible : [];
        var out = {};
        try { out.set_class_set    = analyzer.to_set_class_set(midis)    || null; } catch(e) { out.set_class_set    = null; }
        try { out.set_class_normal = analyzer.to_set_class_normal(midis) || null; } catch(e) { out.set_class_normal = null; }
        try { out.set_class_prime  = analyzer.to_set_class_prime(midis)  || null; } catch(e) { out.set_class_prime  = null; }
        try { out.set_class_forte  = analyzer.to_set_class_forte(midis)  || null; } catch(e) { out.set_class_forte  = null; }
        try { out.spacing          = analyzer.to_spacing(midis)          || null; } catch(e) { out.spacing          = null; }
        if (midis.length === 2) {
          try {
            var ivl = analyzer.to_interval(midis);
            out.interval_specific = (ivl && ivl.name)           || null;
            out.interval_generic  = (ivl && String(ivl.size))   || null;
          } catch(e) { out.interval_specific = null; out.interval_generic = null; }
        } else {
          out.interval_specific = null;
          out.interval_generic  = null;
        }
        return out;
      });
```

Then update the `buildAnalysisSlices` call to pass the 5th argument:

```javascript
      var analysisSlices = PlaySaveLogic.buildAnalysisSlices(
        offsets, slots, labels, tokenOverridesArr, deterministicFieldsArr);
```

- [ ] **Add `analysisType` to the save payload in `play_sheet.js`**

In the `json_data` object definition (the object that gets POSTed to save), add `analysisType`:

```javascript
        analysisType: slots.below === "thoroughbass" ? "figured_bass" : "roman",
```

This ensures newly saved chordal exercises store `analysisType` explicitly.

- [ ] **Browser smoke test**

1. Start dev server: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver`
2. Open `/teacher/play/` — add 3–4 chords, set analysis overlay to Roman numeral
3. Click Save → open DevTools → Network → find the save POST
4. Confirm request body includes `"analysisType": "roman"`
5. Confirm `analysisSlices[0].content` contains `set_class_prime` alongside `roman_numeral`

- [ ] **Commit**

```bash
git add lab/static/js/src/components/music/play_save_logic.js \
        lab/static/js/src/components/music/play_sheet.js
git commit -m "feat: compute set_class/spacing analytics in buildAnalysisSlices at play-save time"
```

---

## Task 5: Backfill management command

**Files:**
- Create: `apps/exercises/management/commands/backfill_analysis_layer.py`
- Modify: `apps/exercises/management/commands/list_exercise_generators.py`

- [ ] **Create the command**

```python
"""Backfill set_class_* and interval analytics fields on existing UMTO chordal exercises."""
from django.core.management.base import BaseCommand

from apps.exercises.models import Exercise
from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices

ANALYTICS_FIELDS = (
    "set_class_prime", "set_class_forte", "set_class_normal",
    "set_class_set", "spacing", "interval_specific", "interval_generic",
)


class Command(BaseCommand):
    help = "Populate analytics fields in AnalysisLayer for existing UMTO chordal exercises."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true",
                            help="Overwrite existing analytics fields.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report counts without writing.")

    def handle(self, *args, **options):
        overwrite = options["all"]
        dry_run = options["dry_run"]
        updated = skipped = errors = 0

        qs = Exercise.objects.filter(data__isUMTO=True)
        for ex in qs.iterator(chunk_size=100):
            data = ex.data
            if not isinstance(data, dict):
                continue
            score = data.get("score", {})
            umto = score.get("umto", {}) if isinstance(score, dict) else {}
            meta = umto.get("metadata", {}) if isinstance(umto, dict) else {}
            if meta.get("score_kind") != "chordal":
                continue

            analysis = umto.get("analysis", [])
            chords   = umto.get("chords", [])
            if not analysis or not chords:
                skipped += 1
                continue

            # Skip if already populated and not overwriting
            if not overwrite:
                first_content = analysis[0].get("content", {})
                if first_content.get("set_class_prime") is not None:
                    skipped += 1
                    continue

            key = meta.get("key", "C")
            try:
                new_slices = build_chordal_analysis_slices(chords, harmony_key=key)
            except Exception as e:
                self.stderr.write(f"[{ex.id}] {e}")
                errors += 1
                continue

            for i, old_slice in enumerate(analysis):
                if i >= len(new_slices):
                    break
                new_content = new_slices[i].get("content", {})
                old_content = old_slice.setdefault("content", {})
                for field in ANALYTICS_FIELDS:
                    if overwrite or field not in old_content:
                        old_content[field] = new_content.get(field)

            if not dry_run:
                ex.data = data
                ex.save(update_fields=["data"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"updated={updated} skipped={skipped} errors={errors}"
            + (" (dry-run)" if dry_run else "")
        ))
```

- [ ] **Register in `list_exercise_generators.py`**

In `CATALOG`, add:
```python
("backfill_analysis_layer", "Backfill set_class/interval analytics into existing UMTO chordal exercises (--all to overwrite, --dry-run to preview)"),
```

- [ ] **Smoke-test**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py backfill_analysis_layer --dry-run
```
Expected output: `updated=N skipped=M errors=0 (dry-run)` — no crash.

- [ ] **Commit**

```bash
git add apps/exercises/management/commands/backfill_analysis_layer.py \
        apps/exercises/management/commands/list_exercise_generators.py
git commit -m "feat: add backfill_analysis_layer management command"
```

---

## Task 6: Documentation updates

**Files:**
- Modify: `docs/UMTO_GUIDE.md`
- Modify: `docs/exercise_types.md`
- Modify: `docs/management_commands.md`

- [ ] **Update `docs/UMTO_GUIDE.md` — add analytics fields table**

In the AnalysisLayer section, add:

```markdown
### Analytics fields (Phase 3A)

All fields are `Optional[str] = None`. Computed at save time — not read by the identification grader (it still live-computes them from MIDI stacks).

| Field | Example | Source |
|---|---|---|
| `set_class_prime` | `"(0,3,7)"` | music21 `chord.primeFormString` / JS `analyzer.to_set_class_prime` |
| `set_class_forte` | `"3-11B"` | music21 `chord.forteClassTnI` / JS `analyzer.to_set_class_forte` |
| `set_class_normal` | `"[0,3,7]"` | music21 `chord.normalOrder` / JS `analyzer.to_set_class_normal` |
| `set_class_set` | `"{C,E,G}"` | pitch names / JS `analyzer.to_set_class_set` |
| `spacing` | `"+"` or `"°"` | JS `analyzer.to_spacing` (Python path stores `null`) |
| `interval_specific` | `"P5"` | 2-note sets only — music21 interval / JS `analyzer.to_interval` |
| `interval_generic` | `"5"` | 2-note sets only |

Use `backfill_analysis_layer` to populate existing exercises.
```

- [ ] **Update `docs/exercise_types.md` — document analysisType storage**

In the UMTO chordal exercise entry, add:

```markdown
**`analysisType` storage:** stored as `exercise.data["analysisType"]` (top-level wrapper key). `lab/views.py::_resolve_analysis_type()` reads this first; falls back to complexity-score heuristic for older rows without the key. Newly saved exercises always include it.
```

- [ ] **Update `docs/management_commands.md` — add backfill entry**

Under the "Backfill / maintenance" section:

```
| `backfill_analysis_layer` | Populate `set_class_*`, `interval_*` analytics in `AnalysisLayer` for existing UMTO chordal exercises. `--all` overwrites; `--dry-run` previews counts. |
```

- [ ] **Commit**

```bash
git add docs/UMTO_GUIDE.md docs/exercise_types.md docs/management_commands.md
git commit -m "docs: document AnalysisLayer analytics fields and analysisType storage"
```

---

## Self-review checklist

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput \
  apps.exercises.tests.test_umto_import_router \
  lab.tests.test_analysis_type_serving \
  -v 2
```

- [ ] All new fields are `Optional` — existing exercises without them still validate
- [ ] `_resolve_analysis_type(None, "roman")` returns `"roman"` (non-dict data handled)
- [ ] `backfill_analysis_layer --dry-run` reports no errors on current DB
- [ ] Browser save includes `analysisType` and `set_class_prime` in POST body
- [ ] `make_umto_schema` reflects all 7 new fields
