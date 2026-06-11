# Management Commands Reference

Quick reference for all exercise-generation, refresh, and curriculum-wiring commands.

Run `python manage.py list_exercise_generators` for a live version of this list.

---

## Admin UI

The Django admin at `/admin/` includes an **Operations** panel at `/admin/exercises/operations/`.

It provides:
- **Exercise catalog** — live counts of exercises grouped by mode/type (matching, harmonization, identification, etc.) and by analysis type
- **Generation forms** — web UI equivalents for the most common management commands; useful for one-off operations without SSH access
- **Refresh dispatcher** — button to run `refresh_all_exercises` against a scoped tag

The admin site uses a custom `GenerateContentAdminSite` (see `apps/exercises/admin.py`).

---

## Command catalog

### Bach chorale phrases (Riemenschneider)

**`import_musicxml`** — Import MusicXML through the UMTO representation router. Stable 2-, 3-, or 4-part scores stay voices-kind UMTO; explicit chord, monophonic, or ragged sources become chordal UMTO.
```
python manage.py import_musicxml path/to/score.musicxml --author admin@example.com --public
```

**`import_legacy_chord_csv`** — Import legacy CSV `data.chord` rows as chordal UMTO exercises. Dry-run first; this does not silently rewrite existing rows.
```
python manage.py import_legacy_chord_csv exercises_2026-04-03.csv \
  --author admin@example.com \
  --dry-run --limit 10

python manage.py import_legacy_chord_csv exercises_2026-04-03.csv \
  --author admin@example.com \
  --public
```

**`import_bach_phrases`** — Import a single Riemenschneider phrase as identification / playback / match / figures / harmonization-source exercises.
```
python manage.py import_bach_phrases --riemenschneider 3 --author admin@example.com \
  --mode roman --extra-tags unit:9
```

**`generate_harmonization`** — Derive a harmonization exercise from an existing UMTO source (locks bass, builds figured-bass targets).
```
python manage.py generate_harmonization --source EB16DF --author admin@example.com \
  --locked-voices B --prompt figured_bass --min-voices 3 --max-voices 4 --public
```

**`render_harmonization_review`** — Render a static HTML review page for a harmonization exercise (debug/QA).
```
python manage.py render_harmonization_review --source EB57LQ
```

**`generate_bach_unit_matrix`** — Efficient Bach generation path: imports each Riemenschneider/mode combination once, stamps requested unit tags, and builds each unit playlist from the shared pool.
```
python manage.py generate_bach_unit_matrix \
  --riemenschneider 1-30 \
  --units 9,10,11,12,14,16,17,18,19,20 \
  --modes roman,figures,play,play_figures \
  --author admin@example.com \
  --public
```

**`deduplicate_bach_phrases`** — Audit duplicate Bach phrase rows for one author. Dry-run by default; pass `--execute` only after verifying playlist links are safe.
```
python manage.py deduplicate_bach_phrases --author admin@example.com
python manage.py deduplicate_bach_phrases --author admin@example.com --execute
```

---

### Pitch identification (Unit 1)

**`generate_unit1`** — Generate the Unit 1 pitch-identification curriculum from the local Bach CIR corpus.
```
python manage.py generate_unit1 --author admin@example.com
```

**`duplicate_chorale_as_identification`** — Spin a chorale exercise into single-voice pitch-identification variants.
```
python manage.py duplicate_chorale_as_identification --source EB16DF --voices soprano alto
```

---

### Rhythm and meter (Unit 2)

**`generate_unit2_barline_exercises`** — Generate Unit 2 barline-placement exercises from the Bach corpus.
```
# Corpus-level playlists (internal, levels 1–8)
python manage.py generate_unit2_barline_exercises --author admin@example.com --source corpus --public

# Student-facing adaptive grouped playlists (run after corpus step)
python manage.py generate_unit2_barline_exercises --author admin@example.com --grouped --public
```

**`generate_unit2_meter_exercises`** — Generate Unit 2 symbolic meter identification exercises from manifest.
```
python manage.py generate_unit2_meter_exercises --author admin@example.com --public
```

**`generate_unit2_meter_reference`** — Pre-generate the `unit2_meter_reference.json` data file (run once; commit result).
```
python manage.py generate_unit2_meter_reference
```

---

### Scales and key signatures (Unit 3)

**`generate_unit3_key_sig_exercises`** — Generate key signature identification exercises (3 levels × major + minor).
```
python manage.py generate_unit3_key_sig_exercises --author admin@example.com --public
```

**`generate_unit3_scale_exercises`** — Generate scale play exercises (major from MusicXML; minor programmatically via music21).
```
# Major only (default)
python manage.py generate_unit3_scale_exercises --author admin@example.com --public

# All minor forms
python manage.py generate_unit3_scale_exercises --author admin@example.com --mode minor --public

# Everything at once
python manage.py generate_unit3_scale_exercises --author admin@example.com --mode both --public
```

**`fix_unit3_playlists`** — One-shot idempotent fixer for Unit 3 playlist taxonomy tags. Safe to re-run.
```
python manage.py fix_unit3_playlists
```

---

### Intervals (Unit 4)

**`generate_unit4`** — Generate staged synthetic interval worksheet exercises.
```
python manage.py generate_unit4 --author admin@example.com --public
python manage.py generate_unit4 --author admin@example.com --lane specific --max-per-stage 24 --intervals-per-exercise 8 --public
```
Default output is twenty-four one-page worksheets per lane/stage, with eight interval prompts per worksheet. Student playback still serves existing Exercise rows, but Unit 4 interval playlists now use a deterministic per-student seeded order so different students see the same bank in different stable sequences. Only six worksheets are exposed to any one student at a time; the larger bank remains in reserve for variety.

---

### Triads and seventh chords (Unit 5)

**`generate_unit5`** — Generate chord quality identification exercises (root position, staged choices).
```
python manage.py generate_unit5 --type both --author admin@example.com --public
```

---

### Galant Compendium

**`audit_compendium_cadences`** — Export a no-DB CSV for reviewing Galant-compendium Roman numeral labels before import. Each row is one target vertical and includes the source id, unit, target key, offset, sounding notes, bass, Z7 stack, legacy chord code, raw legacy RN (`ii°{z}`), normalized HarmonyLab RN (`ii°6`), figured bass, Music21 RN as QA, editable final RN, status, and exception reason.
```
python manage.py audit_compendium_cadences --out scratch/compendium_rn_review.csv
python manage.py audit_compendium_cadences --unit 17 --keys A --out scratch/unit17_a_minor_review.csv
```

**`verify_compendium_realization`** — Verify that the copied Z7 realization layer reproduces the checked-in Galant compendium note JSON exactly. This is a no-DB parity check for the Gemini/Clausulae round-trip approach; it compares generated pitch/offset/ql/tie data against `apps/exercises/data/galant_compendium_cadences.json`.
```
python manage.py verify_compendium_realization
python manage.py verify_compendium_realization --source-id m145-146
```

**`import_compendium_cadences`** — Import Roman-numeral identification exercises from the checked-in Galant compendium cadence subset. Transposes each templated cadence (Simple/Compound/Evaded, major and minor) to multiple keys and groups results into per-unit playlists. Use `--preview` to inspect the exercise count and bin histogram without any DB writes. By default it reads `apps/exercises/data/galant_compendium_cadences.json`; set `COMPENDIUM_INDEX=/path/to/index.json` only for local regeneration/debugging.

Recommended workflow:
1. Run `verify_compendium_realization` after changing the copied Z7 realization layer or source JSON.
2. Run `audit_compendium_cadences` and review any `status=review` rows before import.
3. Run `import_compendium_cadences --preview` and confirm the bin histogram.
4. Run the real import with `--author`, `--public`, and normally `--overwrite`.

Current expected full-import histogram from the checked-in source is:
- unit 9: 50 exercises
- unit 10: 90 exercises
- unit 12: 60 exercises
- unit 14: 30 exercises
- unit 17: 110 exercises
- total: 340 exercises

The real import creates or refreshes one public playlist per populated unit named `Unit N — Roman Numerals from the Galant Compendium`. `--overwrite` is recommended for regeneration because descriptions are the idempotency key (`Cmp m145-146 Am`, etc.); without it, existing exercises are reused and only playlist ordering is refreshed.
```
# Dry run — no DB writes
python manage.py import_compendium_cadences --preview

# Full import for all currently templated units (9, 10, 12, 14, 17)
python manage.py import_compendium_cadences --author admin@example.com --public --overwrite

# Only units that bin to unit 14
python manage.py import_compendium_cadences --author admin@example.com --unit 14

# Optional local debugging only: restrict target transposition keys
python manage.py import_compendium_cadences --preview --unit 17 --keys C G
```

---

### Branch B (Clausulae)

**`generate_clausulae_b1`** — Generate Branch B Units B1–B4 and B11–B12: formal clausulae and cadence exercises (playback mode).
```
python manage.py generate_clausulae_b1 --author admin@example.com --public
```

**`generate_roman_from_clausulae`** — Generate `roman_from_clausulae` exercises: Roman numeral identification over standard Clausulae material. Unit 9 emits authentic cadences (`I–V–I`); Unit 10 emits first-inversion cadences (`I6–vii°6–I6`). Student-friendly descriptions, no Branch B tags. Analysis slices have `is_target:true` and `roman_numeral` populated.
```
python manage.py generate_roman_from_clausulae \
  --unit 10 \
  --author admin@example.com \
  --voices 3 \
  --public --overwrite
```

**`generate_harmonization_from_clausulae`** — Generate figured-bass harmonization exercises from standard Clausulae material. Unit 9 emits authentic cadences (`5/3–5/3–5/3`); Unit 10 emits first-inversion cadences (`6–6–6`). Uses the existing harmonization path: bass is locked, figured-bass analysis slices drive `harmonizationTargets`, and students play the upper voices.
```
python manage.py generate_harmonization_from_clausulae \
  --unit 10 \
  --author admin@example.com \
  --voices 3 \
  --public --overwrite
```

---

### Playlists and curriculum wiring

**`create_unit_playlist`** — Create a per-unit Playlist that bundles existing exercises by skill tag.
```
python manage.py create_unit_playlist --unit 9
```

**`create_smart_playlist`** — Create an adaptive playlist seeded from skill-tag filters.
```
python manage.py create_smart_playlist --name 'My adaptive set' --tags I V V7
```

**`rebuild_unit1_playlists`** — Rebuild Unit 1 playlists from current taxonomy.
```
python manage.py rebuild_unit1_playlists
```

---

## Refresh / recompute commands

These update existing exercise rows in-place. They do **not** create new rows. Safe to re-run (all idempotent).

> **When to use:** After fixing a bug in the analysis pipeline (e.g. figured bass derivation, key detection), run `refresh_all_exercises` to propagate the fix to all affected rows without re-importing from source files.

> **Key normalization:** Stored HarmonyLab key tokens (`jC_`, `iA_`, …) are normalized via `apps.exercises.utils.key_normalization.harmony_key_to_music21()` before music21 analysis; `Cannot make a step out of 'J'` should be treated as a regression. Broad refresh/backfill commands print a `Failure categories: {...}` summary at the end.

**`refresh_all_exercises`** — Dispatcher: runs `recompute_chorale_analysis` then `recompute_harmonization_targets --resync-from-source` in sequence. The safest way to refresh everything after a pipeline change.
```
python manage.py refresh_all_exercises
python manage.py refresh_all_exercises --tag qa:some_tag   # scope to a tag
python manage.py refresh_all_exercises --dry-run           # preview only
```

**`audit_wir_local_key_shifts`** — Scans WiR-backed Bach rows (tagged `riem:N`) and reports the inferred semitone shift needed to align WiR local keys to the rendered music21 score.
```
python manage.py audit_wir_local_key_shifts
python manage.py audit_wir_local_key_shifts --riem 17
python manage.py audit_wir_local_key_shifts --tag unit:11
# Example output: R17 +2 rows=4
```

**`recompute_chorale_analysis`** — Rebuilds `score.umto.analysis` on chorale-derived rows (tagged `riem:N`) by re-running the analysis pipeline against the stored score. Applies the same WiR local-key transposition logic reported by `audit_wir_local_key_shifts`. Does not re-import from music21 corpus files.
```
python manage.py recompute_chorale_analysis
python manage.py recompute_chorale_analysis --riem 17
python manage.py recompute_chorale_analysis --tag qa:some_tag
python manage.py recompute_chorale_analysis --dry-run
```

**`recompute_harmonization_targets`** — Rebuilds `harmonizationTargets` on harmonization rows from their stored `score.umto.analysis`. Pass `--resync-from-source` (required after running `recompute_chorale_analysis`) to first copy refreshed analysis from the source exercise into the harmonization row.
```
python manage.py recompute_harmonization_targets
python manage.py recompute_harmonization_targets --resync-from-source
python manage.py recompute_harmonization_targets --tag qa:some_tag --dry-run
```

**`backfill_skill_tags`** — Re-run `skills_analyzer` over all UMTO rows and write `skill_tags` + `complexity`.
```
python manage.py backfill_skill_tags --all
```

**`backfill_raw_roman_numeral`** — Backfill `raw_roman_numeral` on existing UMTO analysis slices.
```
python manage.py backfill_raw_roman_numeral
```

**`reanalyze_knowledge_graph`** — Recompute knowledge-graph edges from current exercise tags.
```
python manage.py reanalyze_knowledge_graph
```

---

## Factory library / infrastructure

**`ensure_factory_account`** — Idempotently create the factory system account (`settings.FACTORY_USER_EMAIL`, default `factory@monteverdi.app`) that owns official curated content. Teacher role, unusable password. Safe to re-run; run before any factory-library seeding.
```
python manage.py ensure_factory_account
python manage.py ensure_factory_account --email other@example.com
```

---

## Inspection / debugging

**`dump_exercise`** — Print an exercise's decision fields (type, mode, inputMode, inputModeFixed, analysisType, identMode, allowed_answers) by E-ID, plus the resolved canonical `input_method` (`note_entry` / `dropdown` / `text`). Read the real shape of an exercise instead of guessing field names through the browser. Use the local settings that point at the dev DB.
```
python manage.py dump_exercise EB61KJ --settings=harmony.settings.local
python manage.py dump_exercise EB61KJ --full --settings=harmony.settings.local   # full data JSON
```

## Skipped by refresh_all_exercises

The following exercise types are **not** refreshed automatically — re-run their generators if the pipeline changed:

| Unit | Command |
|------|---------|
| Unit 1 pitch identification | `generate_unit1` |
| Unit 2 meter / barline | `generate_unit2_*` |
| Unit 3 key sig / scales | `generate_unit3_*` |
| Unit 4 intervals | `generate_unit4` |
| Unit 5 chord quality | `generate_unit5` |
