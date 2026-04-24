# UMTO Consistency & Legacy-Prevention Design

**Date:** 2026-04-23
**Status:** Draft, pending implementation plan
**Author:** avnerdorman + Claude (brainstorming)

## Purpose

Make UMTO (Universal Music Theory Object) the single canonical representation for every Exercise in HarmonyLab. Eliminate schema drift, silent legacy fallbacks, and duplicated builder functions that currently cause agent debugging loops. Prevent regression via runtime guardrails, contract tests, and golden fixtures.

## Non-Goals

- Removing existing legacy Exercise rows from the database (grandfathered).
- Replacing VexFlow adapter's CIR-style input with native UMTO consumption (deferred to a future phase).
- Changing the grading engine, MIDI pipeline, or chorale_grader algorithm.
- Adding new pedagogical features, analysis types, or interaction modes.

## Current State (as of 2026-04-23)

### Parallel pipelines
Exercise payloads exist in two shapes:
- **UMTO** (`isUMTO: true`, `metadata+voices+analysis+grading`) — emitted by `generate_unit1.py`, `migrate_unit1_to_umto.py`.
- **Legacy CIR** (`type: "chorale"`, `"chorale_identification"`, raw `score.measures[…].staves.<clef>.voices`) — emitted by `import_chorale.py`, `import_bach_phrases.py`, `import_musicxml.py`, `duplicate_chorale_as_identification.py`, `mass_import_performance.py`, dashboard duplicate-as-pitch endpoint, `scratch/*.py`.

### Detection logic scattered
[lab/views.py:272](../../lab/views.py#L272) detects UMTO via two disjunctive checks. Silent `print()` fallback at line 291 swallows `UMTO.model_validate` errors. [exercise_definition.js:758](../../lab/static/js/src/models/exercise_definition.js#L758) and neighbors branch on `type === "chorale" || "umto_chorale"`.

### Known bugs the current state masks
- `generate_unit1.py` advertises `--lanes identification` at [generate_unit1.py:609](../../apps/exercises/management/commands/generate_unit1.py#L609) but `choices=["exact","analysis","both"]` at [generate_unit1.py:393](../../apps/exercises/management/commands/generate_unit1.py#L393) makes it unreachable.
- `umto_schema.json` is stale. Missing `mode`, `clef`, `is_umto` on `Metadata`; missing tie/target flags on `VoiceEvent`.
- `_build_exact_payload`, `_build_analysis_payload`, `_build_identification_payload` in `generate_unit1.py` are near-duplicate copies of `_score_to_umto_payload`.

## Architecture

Four layers. Build bottom-up. Flip the model guard (Layer 2) last, after all commands migrated and all test fixtures converted.

### Layer 1 — Canonical factory

**New module:** [apps/exercises/umto_factory.py](../../apps/exercises/umto_factory.py)

**Ownership rule:** the factory *owns* the CIR→UMTO conversion. It is not a thin wrapper over existing builders — the conversion logic (offset walking, MIDI calculation, voice-to-staff routing, analysis-slice synthesis, unit-tag attachment, `exercise_id` backfill) lives inside `umto_factory.py`. Existing helpers (`_build_exact_payload`, `_build_analysis_payload`, `_build_identification_payload`, `_score_to_umto_payload` in `generate_unit1.py`; any equivalents in other commands) are **deleted**, not re-exported or delegated to. Every new Exercise in the codebase, including scratch scripts, flows through this one conversion function.

Public API:

```python
def build_umto_payload(
    *,
    exercise_id: str,
    source: str,
    key: str,
    meter: str,
    clef: str,
    complexity_score: int,
    mode: InteractionMode,
    score_data: dict,              # CIR-style input (measures/staves/voices)
    target_voice: str | None = None,  # "soprano"|"alto"|"tenor"|"bass"|None for all
    unit: int | None = None,
    analysis_overrides: list[dict] | None = None,  # optional pre-built AnalysisSlice dicts
) -> dict:
    """Build a UMTO frontend payload from CIR-shaped score_data.
    Owns all CIR→UMTO conversion logic. Replaces _build_exact_payload,
    _build_analysis_payload, _build_identification_payload, _score_to_umto_payload
    in generate_unit1.py and every equivalent in import_chorale, import_bach_phrases,
    import_musicxml, duplicate_chorale_as_identification, mass_import_performance,
    dashboard duplicate endpoint, and scratch/*.py. Those helpers are deleted."""


def save_umto_exercise(
    *,
    description: str,
    score_data: dict,
    author,                        # User
    skill_tags: list[str],
    complexity: int,
    is_public: bool = True,
    umto_kwargs: dict,             # forwarded to build_umto_payload
) -> Exercise:
    """Builds payload, validates via UMTO.model_validate, saves Exercise, backfills exercise_id.
    Create-only — not intended for converting existing legacy rows. Conversion of existing
    rows goes through dedicated migration commands (migrate_unit1_to_umto, migrate_exercises)
    with HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 bypass."""


class NonUMTOExerciseError(ValueError):
    """Raised when save_umto_exercise is handed legacy-shaped data, or when
    Exercise.save() sees a new row whose data fails UMTO validation."""
```

Factory is the only sanctioned path to create an Exercise. All commands import from it.

### Layer 2 — Model-level guard

[apps/exercises/models.py](../../apps/exercises/models.py) `Exercise.save()` override plus `clean()` for Django-admin UX:

```python
def clean(self):
    """Surfaces UMTO validation as a standard ValidationError so Django Admin
    renders a red inline error instead of a 500 page when a legacy exercise
    is submitted via the admin form."""
    super().clean()
    if not self.pk and not _legacy_bypass_enabled():
        if not isinstance(self.data, dict) or not self.data.get("isUMTO"):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {"data": "New exercises must be UMTO. Use apps.exercises.umto_factory.save_umto_exercise()."}
            )
        try:
            from apps.exercises.umto import UMTO
            UMTO.model_validate(self.data.get("score", {}).get("umto") or self.data)
        except Exception as e:
            from django.core.exceptions import ValidationError
            raise ValidationError({"data": f"UMTO validation failed: {e}"}) from e


def save(self, *args, **kwargs):
    is_new = self.pk is None
    if is_new and not _legacy_bypass_enabled():
        if not isinstance(self.data, dict) or not self.data.get("isUMTO"):
            raise NonUMTOExerciseError(
                f"Exercise creation blocked: data missing isUMTO=True. "
                f"Use apps.exercises.umto_factory.save_umto_exercise()."
            )
        try:
            from apps.exercises.umto import UMTO
            UMTO.model_validate(self.data.get("score", {}).get("umto") or self.data)
        except Exception as e:
            raise NonUMTOExerciseError(f"UMTO validation failed: {e}") from e
    super().save(*args, **kwargs)


def _legacy_bypass_enabled() -> bool:
    return os.environ.get("HARMONYLAB_ALLOW_LEGACY_EXERCISE") == "1"
```

`clean()` is invoked automatically by `ModelForm.is_valid()` in Django admin, producing inline form errors. `save()` is the backstop for code paths that bypass forms (raw ORM writes, management commands). Both run the same UMTO validation.

**Bypass policy:**
- `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` reserved for one-shot migration scripts only.
- Never set in production, CI, or test defaults.
- Documented in CLAUDE.md as "emergency only."

**Grandfathering:** Existing rows (pk is not None on load) pass through `save()` untouched on update. Only new-row creation is gated.

### Layer 3 — Views, warnings, duplicate endpoint

**[lab/views.py](../../lab/views.py) — replace silent fallback:**

```python
# Before (line 291):
print(f"UMTO Alignment Warning: {e}")
exercise_context.update(exercise.data)

# After:
import logging
logger = logging.getLogger(__name__)
logger.warning(
    "[LEGACY EXERCISE] Exercise %s failed UMTO validation: %s. "
    "Falling back to raw data. Migrate via apps.exercises.umto_factory.",
    exercise.id, e,
)
exercise_context.update(exercise.data)
```

**[apps/dashboard/views/exercises.py](../../apps/dashboard/views/exercises.py) — `duplicate-as-pitch-identification`:**
Route through `umto_factory.save_umto_exercise()`. Input is an existing Exercise's CIR score; strip to voice (keep `pitch_voice_utils.strip_to_voice`); hand result to factory with `mode=InteractionMode.IDENTIFICATION`, `complexity_score=1`, analysis-type metadata.

### Layer 4 — Contract tests + golden fixtures

**Golden fixtures** — [apps/exercises/tests/fixtures/umto/](../../apps/exercises/tests/fixtures/umto/):
- `unit1_identification_treble.json` — single-voice soprano window, note-name identification
- `unit1_identification_bass.json` — single-voice bass window
- `unit1_playback_treble.json` — PLAYBACK mode
- `unit1_analysis_treble.json` — ANALYSIS_MATCH mode
- `unit9_chorale_roman.json` — 4-voice SATB, roman-numeral analysis slices
- `unit12_chromatic_analysis.json` — secondary dominants, chromatic mediants
- `minimal.json` — **minimalist edge case**: smallest valid UMTO (one note, no analysis, one grading slice, all optional fields at defaults). Catches "does empty `analysis=[]` crash downstream?"
- `maximal.json` — **maximalist edge case**: every optional field populated (`is_tied_start`, `is_tied_stop`, `is_target=False`, `VisualMetadata` with all hints, `AnalysisLayer` with `roman_numeral` + `figured_bass` + `pop_symbol` + `functional_label` all set, `unit_tags=[1,9,12]`, `rhythmic_flexibility=True`). Catches "does schema regen drop optional fields?" and exercises every serialization branch.

Each fixture is a full UMTO JSON payload (not CIR). Generated once by running `python manage.py make_umto_fixtures`, reviewed by hand, committed. Fixtures are the source of truth for what "valid UMTO" looks like.

**Contract tests** — [apps/exercises/tests/test_umto_contract.py](../../apps/exercises/tests/test_umto_contract.py):

1. **Round-trip invariance:** For each fixture, `UMTO.model_validate_json(f).model_dump_json(indent=2)` equals the file contents (after pydantic-stable key ordering). Fails if Pydantic schema changes silently break serialization.
2. **Schema-file sync:** Regenerate `UMTO.generate_schema()` and assert equal to contents of `apps/exercises/umto_schema.json`. CI fails if `umto.py` changes without corresponding `python manage.py make_umto_schema`.
3. **Frontend payload shape:** For each fixture, `to_frontend_payload(unit=N)` output contains the frozen key set `{type, isUMTO, mode, staffDistribution, complexity_score, exerciseId, key, meter, clef, allowed_answers, score, grading}`. **Explicit value assertion: `payload["isUMTO"] is True`** — this is the flag the frontend `isUMTO()` gate ([exercise_definition.js:618-619](../../lab/static/js/src/models/exercise_definition.js#L618-L619)) reads to route rendering/grading. If the flag drops, the frontend silently reverts to the legacy path. Assert value, not just key presence.
4. **Legacy rejection:** `Exercise(data={"type":"chorale_identification", ...}).save()` raises `NonUMTOExerciseError`.
5. **Factory idempotence:** `build_umto_payload(...)` on a fixture's CIR-style input produces byte-equal output to the fixture.
6. **Round-trip via save:** `save_umto_exercise(...)` with fixture input → reload from DB → `Exercise.data["score"]["umto"]` equals the fixture UMTO.

**Rendering regression harness** — [lab/static/js/test/test_umto_rendering.js](../../lab/static/js/test/test_umto_rendering.js):
- Load each fixture via test-only HTTP endpoint or static import.
- Call `ExerciseSheetComponent.prototype._convertUMTOToProcessedScore(umto)`.
- Assert structural contract:
  - `processed.measures.length >= 1`
  - `processed.measures[0].staves.treble.voices` is an array
  - Per-staff voice counts match UMTO voice presence (S+A → treble, T+B → bass, single-voice modes → target clef only)
  - Every VoiceEvent with `kind=note` produces exactly one item with `item.pitch.step/alter/octave` matching UMTO
- Not pixel-perfect rendering. Just input-shape contract.

## Schema Hygiene

### Regenerate `umto_schema.json`

New command [apps/exercises/management/commands/make_umto_schema.py](../../apps/exercises/management/commands/make_umto_schema.py):

```python
class Command(BaseCommand):
    help = "Regenerate apps/exercises/umto_schema.json from UMTO pydantic model"
    def handle(self, *args, **opts):
        from apps.exercises.umto import UMTO
        schema = UMTO.generate_schema()
        path = Path("apps/exercises/umto_schema.json")
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        self.stdout.write(f"Wrote {path}")
```

Run once in implementation. Contract test #2 enforces it stays in sync.

### Fix `generate_unit1.py` lane argparse

Change [generate_unit1.py:393](../../apps/exercises/management/commands/generate_unit1.py#L393):

```python
parser.add_argument("--lanes", choices=["exact", "analysis", "identification", "both", "all"], default="both")
```

Define `"all"` as shorthand for exact+analysis+identification. Update lane-branch conditions accordingly. Delete the three `_build_*_payload` functions — replaced by one `umto_factory.build_umto_payload(mode=...)` call per lane.

### Verify `_convertUMTOToProcessedScore` bass routing

[exercise_sheet.js:2155-2165](../../lab/static/js/src/components/music/exercise_sheet.js#L2155-L2165) currently hard-codes S+A→treble, T+B→bass. For Unit 1 single-voice bass exercises, the migration writes the voice into `voices.B` and sets `metadata.clef="bass"`. Renders on bass staff correctly. But Unit 1 single-voice soprano writes to `voices.S` — renders on treble. Acceptable.

Edge case: bass clef exercise where voice is stored under `S` because migrator picked `umto_voice_id = "S" if target=="treble" else "B"` and target was `"bass"` → stored in `B`. Confirmed correct. Add a contract-test assertion to lock this invariant.

## Documentation

### CLAUDE.md top section (new)

```markdown
## UMTO is the Canonical Exercise Representation

**All new Exercise rows MUST be UMTO.** Legacy `chorale`, `chorale_identification`,
and raw-CIR Exercise shapes are FROZEN — do not extend, do not emit from new code.

### Creating an Exercise (only sanctioned path)

```python
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode

ex = save_umto_exercise(
    description="BWV1.6 mm.1-2 — Soprano (identification) Stage 1",
    score_data=cir_score_dict,
    author=user,
    skill_tags=["unit:1", "Note_Names", "Read_Treble_Clef"],
    complexity=11,
    umto_kwargs=dict(
        exercise_id="TEMP",
        source="BWV1.6 measures 1-2, Soprano voice.",
        key="G", meter="4/4", clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        target_voice="soprano",
        unit=1,
    ),
)
```

Direct `Exercise(data={...}).save()` on new rows is blocked by model validator.
Bypass env `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` exists for one-shot migration scripts
only — never set in CI, tests, or production.

Schema: [apps/exercises/umto_schema.json](apps/exercises/umto_schema.json)
(auto-regenerated by `python manage.py make_umto_schema`).

Guide: [docs/UMTO_GUIDE.md](docs/UMTO_GUIDE.md)
```

### New file — `docs/UMTO_GUIDE.md`

Sections:
- What UMTO is (one paragraph)
- When to use it (always, for new exercises)
- The three `InteractionMode` values and what each renders/grades
- Voice model (S/A/T/B + `clef` metadata → rendering decisions)
- Analysis slices vs. grading slices (separate concerns)
- How to add a new analysis label type (extends `AnalysisLayer` → bump schema → regen `umto_schema.json` → add fixture)
- Common pitfalls: `exercise_id="TEMP"` placeholder pattern, unit-tag-driven filtering, frontend bridge in `_convertUMTOToProcessedScore`
- FAQ: "Why is there still a bridge to CIR?" / "Why does VexFlow not read UMTO directly?" (answer: deferred phase, tracked separately)

### Header comments on legacy code paths

Add top-of-file docstring banner to:
- `apps/dashboard/views/exercises.py` legacy-duplicate branches (if any remain post-migration)
- `lab/static/js/src/models/exercise_definition.js` near `buildChoraleIdentificationProblems` (if it coexists with UMTO variant)

Banner text:

```
# FROZEN — legacy Exercise shape support. Do NOT extend.
# New Exercise creation must go through apps.exercises.umto_factory.
# See CLAUDE.md "UMTO is the Canonical Exercise Representation".
```

## Command Migration Matrix

| Command / file | Currently emits | Action |
|---|---|---|
| `import_chorale.py` | Legacy CIR `chorale`/`chorale_identification` | Rewrite to call `umto_factory.save_umto_exercise` |
| `generate_unit1.py` | UMTO (three duplicated builders) | **Delete** `_build_exact_payload`, `_build_analysis_payload`, `_build_identification_payload`, `_score_to_umto_payload`. Replace with one `umto_factory.save_umto_exercise(...)` call per lane, passing `mode=InteractionMode.PLAYBACK/ANALYSIS_MATCH/IDENTIFICATION`. Fix `--lanes` argparse choices. |
| `migrate_unit1_to_umto.py` | UMTO | Keep; refactor to use factory for symmetry; set `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` while mutating existing rows (update path, not new-row) |
| `migrate_exercises.py` | Varies | Audit; migrate to factory or delete if obsolete |
| `import_bach_phrases.py` | Legacy CIR | Rewrite via factory |
| `import_musicxml.py` | Legacy CIR | Rewrite via factory |
| `duplicate_chorale_as_identification.py` | Legacy CIR | Rewrite via factory |
| `mass_import_performance.py` | Legacy CIR + skill tags | Rewrite via factory; preserve skill-detection hook |
| `apps/dashboard/views/exercises.py` duplicate-as-pitch | Legacy CIR | Rewrite via factory |
| `apps/exercises/admin.py` Exercise create/edit | Raw JSON textarea | Add model-layer validation; admin errors rendered inline |
| `scratch/batch_import_unit9.py` | Legacy CIR | Migrate via factory or delete |
| `scratch/fix_mismatched_keys.py` | Updates existing rows | Keep; bypass via env var if it hits model guard |

## Test Fixture Migration (gate for Layer 2 flip)

Before flipping the model guard:
- Audit every `Exercise(...)` and `Exercise.objects.create(...)` call in `apps/**/tests/`.
- Convert each to use `save_umto_exercise` or a shared `test_umto_helpers.make_umto_exercise(...)` helper.
- Tests specifically exercising legacy-code-path rendering (if any survive) must be migrated or deleted — not env-bypassed.
- Run `pytest apps/` — all green — then flip the guard in the same commit.

## Rollout Order

Nine steps. Each step commits independently. Intermediate states must keep all tests green.

1. **Layer 1 — factory module only.** Write `umto_factory.py` + `NonUMTOExerciseError`. No call sites changed yet. Unit tests for factory happy path + legacy-input rejection.
2. **Schema regeneration.** Add `make_umto_schema` management command. Run it. Commit regenerated `umto_schema.json`.
3. **Golden fixtures.** Write `make_umto_fixtures` command or author fixtures by hand. Commit 5-10 fixture files.
4. **Contract tests.** Add `test_umto_contract.py` with tests 1-3 + 6. Test 4 (legacy rejection) stubbed pending Layer 2. Test 5 (factory idempotence) live.
5. **Migrate generators first.** `generate_unit1.py` (collapse builders, fix `--lanes`), `migrate_unit1_to_umto.py`, `migrate_exercises.py`. Contract tests still green.
6. **Migrate importers.** `import_chorale.py`, `import_bach_phrases.py`, `import_musicxml.py`, `mass_import_performance.py`, `duplicate_chorale_as_identification.py`, dashboard duplicate endpoint. Each command gets its own commit + test.
7. **Migrate test fixtures.** Convert every test that creates an Exercise to use factory / UMTO helper. All tests green.
8. **Rendering regression harness.** Add JS test file per Layer 4. Wire into CI (jest/karma whatever HarmonyLab uses — verify during implementation).
9. **Flip Layer 2 — model guard ON.** Enable `NonUMTOExerciseError` raise in `Exercise.save()`. Enable contract test 4. Update `lab/views.py` to `logger.warning`. Add CLAUDE.md section + `docs/UMTO_GUIDE.md`. Add header banners on legacy files. Final commit.

## Risk & Mitigation

| Risk | Mitigation |
|---|---|
| Hidden legacy call site missed in audit | CI runs `grep -rE '"type":\s*"chorale(_identification)?"' apps/ lab/` and fails on matches outside fixtures/ and tests/legacy_fixtures/ |
| `scratch/*.py` still used in production workflow | Audit with user before deleting; preserve via bypass env if genuinely needed |
| Model-guard breaks admin UI for bulk imports | Verify admin tests pass; admin edits to existing rows are updates (not new creates), so guard should not fire |
| Fixture format drift between Python write + JS read | Fixtures are plain JSON — no format drift possible. Contract test 1 enforces Pydantic stability. |
| Frontend contract test 1 framework choice | Use whatever JS test runner the repo already has; if none, defer Layer 4 JS harness to a separate phase and note as open work |

## Open Questions (for implementation plan)

- Does the repo currently run JS tests in CI? If not, rendering regression harness becomes a manual script; CLAUDE.md directive suffices meanwhile.
- Should `UMTO.to_frontend_payload` be split into per-mode variants (`to_identification_payload`, `to_playback_payload`) or stay single-dispatch on `mode`? Recommendation: single-dispatch; per-mode behavior lives in the frontend consumer.
- Where should `make_umto_fixtures` pull input CIR data from? Recommend: small curated input CIR files under `apps/exercises/tests/fixtures/cir_inputs/`.

## Success Criteria

- `grep -rE '"type":\s*"chorale(_identification)?"' apps/ lab/` returns only fixture and test files.
- `Exercise.objects.filter(data__isUMTO=True).count() / Exercise.objects.count()` trends toward 1.0 for all Exercise rows created after the flip.
- `pytest apps/exercises/tests/test_umto_contract.py` passes in CI.
- No `print("UMTO Alignment Warning: ...")` calls remain in the codebase.
- CLAUDE.md top section states the UMTO directive.
- New developer (or agent) reading CLAUDE.md can create a correct Exercise using `umto_factory` without touching `umto.py` internals.
