# Factory Library Packaging — Manifest, Wrapper, Curated Export, Transpositions

**Goal:** One idempotent command produces the entire official exercise library
under the factory account (`settings.FACTORY_USER_EMAIL`, see
`ensure_factory_account`), locally and on prod. Hand-authored (click-first
editor / `import_musicxml`) content is a first-class "curated" manifest kind
with a git-committed export as backup + prod-sync path.

**Roadmap context:** Phase 1 of the production roadmap. Prereqs landed:
key normalization fix (2026-06-02 plan), `ensure_factory_account`,
play-save metadata dialog (2026-06-10 plan).

## Components

### 1. `apps/exercises/factory_manifest.py`
Python declarative list `MANIFEST: list[FactoryUnitEntry]`. Two kinds:
- `generated`: `{unit, kind="generated", commands=[(command_name, kwargs), ...]}`
  — regenerable from code. Source the unit→generator mapping from the CATALOG
  in `list_exercise_generators.py` (units 1–5 synthetic generators,
  `generate_bach_unit_matrix` for 9–20, compendium/clausulae commands) and the
  intent in `docs/superpowers/plans/2026-06-02-efficient-bach-generation.md`.
- `curated`: `{unit, kind="curated", playlist_name, tag_query | exercise_ids}`
  — playlist built from hand-authored factory exercises. Seeding only
  (re)builds playlist membership; NEVER deletes/overwrites curated Exercise rows.

### 2. `generate_factory_library` management command
- `--units 1,2,9-20` filter; `--author` default `settings.FACTORY_USER_EMAIL`;
  `--report` (coverage map: every taxonomy unit → factory playlist count, flag
  zero-coverage); `--verify` (assert each manifest unit has ≥1 non-empty
  factory playlist tagged `unit:N`; curated units checked as exists+non-empty);
  `--skip-refresh` passthrough; `--dry-run` (print what would run).
- Calls `ensure_factory_account` first, then sub-commands via `call_command`.
- Summary table at end (unit, playlists, exercises, status).

### 3. `export_factory_curated` / `import_factory_curated`
- Export: factory-authored exercises NOT regenerable by generators (selection:
  manifest curated entries + any factory exercise whose skill_tags carry a
  `curated:` tag or that the manifest's tag_query matches) + their playlist
  memberships → JSON files under `data/factory_curated/` (one file per unit,
  stable ordering, exercise `id` preserved; `authored_by` stored as email).
- Import: `--update` upserts by exercise `id`; creates missing playlists +
  EPO rows; never deletes. This is the prod-sync + disaster-recovery path.
- Round-trip test required: export → wipe curated rows in test DB → import →
  identical playlists/exercises.

### 4. `generate_transpositions` management command
- `--exercise EXXXX --keys C,G,Bb,F#m [--playlist NAME] [--author ...]`.
- Verified constraint: runtime playlist transposition (`transpose_requests`)
  does NOT work for UMTO chordal rows (expects legacy top-level `data["chord"]`
  + `keySignature`). So: batch-create transposed Exercise copies — shift
  visible/hidden MIDI in `score.umto.chords`, set new key, rebuild through
  `build_chordal_umto_payload`/`save_chordal_umto_exercise`; analysis slices
  are key-relative → copy as-is; drop `spelling` (or recompute) on transposed
  copies. Reuse pitch-class vector + keyboard-range logic from
  `apps/exercises/utils/transpose.py` (extract shared helper, don't duplicate).
- Tag copies `transposed_from:EXXXX`; idempotent re-run (skip existing copies
  by description or tag).

### 5. `.github/workflows/generate-factory-library.yml`
Copy-adapt `generate-neon-content.yml`: workflow_dispatch inputs (units,
skip-refresh, dry-run), Neon `DATABASE_URL` secret, steps:
`ensure_factory_account` → `import_factory_curated --update` →
`generate_factory_library`. Keep old workflow until parity confirmed.

## Decisions
- "Official" = `authored_by == factory user`. No schema flag.
- Playlist identity is name-keyed (matches `create_unit_playlist`); never
  rename taxonomy unit titles without a migration pass.
- Local factory content population (re-running generators as factory author)
  happens via this command once merged — not ad hoc scripts.

## Tasks
- [x] Task 1 (Sonnet): manifest + `generate_factory_library` (+ 26 tests).
      Orchestrator fix: dropped invented `--public` kwarg from `generate_unit1`
      entry (command has no such flag; its output is public by construction).
- [x] Task 2 (Sonnet): `export_factory_curated` / `import_factory_curated`
      (+ round-trip tests). Orchestrator follow-up: `Exercise.save()` now only
      derives `id` when blank so preserved cross-environment ids survive later
      re-saves (regression test added).
- [x] Task 3 (Sonnet): `generate_transpositions` + shared helpers
      `compute_midi_vector` / `compute_key_target` in utils/transpose.py
      (17 new tests; existing 9 transpose tests green).
- [x] Task 4 (Gemini): workflow yml. Orchestrator fixes: pipenv install (repo
      has no requirements.txt — the original generate-neon-content.yml shares
      this latent bug) + shell quoting in the units conditional.
- [x] Task 5 (orchestrator): review, docs/CATALOG entries, 78/78 tests across
      all P1 modules, dry-run + report smoke against local DB. Actual factory
      seed run deferred to a deliberate session (hours of music21); run order:
      ensure_factory_account → generate_factory_library --units ... .
