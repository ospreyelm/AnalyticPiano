# Curriculum Generation System — Design

_Date: 2026-04-09_

## Problem

Creating a music theory curriculum by hand is not feasible at scale. Almost every exercise is a systematic variation of a base pattern — all 12 dominant 7ths, diatonic triads in every key, Rule of the Octave, ii–V–I in all keys. A full semester curriculum requires ~400 exercises across ~25 playlists. The generation system automates this by reading a YAML spec and producing Exercise/Playlist/Course records in bulk.

Full background and YAML format reference: `docs/curriculum_generation_spec.md`.

---

## Scope

**In scope:** Path A (template-based generation), tonal theory (theory1.yaml), full semester ~400 exercises.

**Out of scope:**
- Path B (MusicXML web import) — separate task
- Path C (word questions) — separate task
- `analytical_pcs`, `figured_bass_pcs` types — post-tonal spec
- Special UI rendering for pc-sets or stacked figured bass notation
- Secondary dominants, modulation, post-tonal content (theory2+)

---

## Architecture

Four modules in `apps/exercises/generation/` plus one management command. Dependencies are one-way: only the management command touches the database.

```
spec_loader.py          (independent — parses YAML, expands key shorthands)
analysis_presets.py     (independent — expands shorthand analysis dicts)
voicing.py              (independent — MIDI arithmetic for register/doubling)
templates.py            → voicing.py, analysis_presets.py
generate_curriculum.py  → spec_loader.py, templates.py, Django ORM
```

**`analysis_presets.py`** — pure functions; expands `{roman_numerals: true}` shorthand to the full analysis mode object the Exercise model expects.

**`voicing.py`** — named strategy functions (`close`, `open`, `close_4voice`, `keyboard_4voice`) that take root + quality + inversion and return MIDI note lists in the correct register.

**`templates.py`** — one function per template (`triad`, `seventh_chord`, `interval`, etc.); returns chord dicts `{"visible": [...], "hidden": [...]}` for matching/analytical/figured_bass types, or `{"visible": [...], "hidden": [], "answer": "...", "choices": [...]}` for identification. Contains the label map (see below).

**`spec_loader.py`** — reads and validates the YAML spec; expands key shorthands (`all_major` → list of 12 keys); returns a structured Python dict.

**`generate_curriculum.py`** — management command; drives spec_loader + templates, creates `Exercise` / `Playlist` / `Course` records; supports `--dry-run` and `--overwrite`.

---

## Build Order

Option B: phased delivery so the pipeline can be validated early with partial content.

### Phase 1 — Infrastructure
- `analysis_presets.py`
- `spec_loader.py` with key shorthand expansion
- `generate_curriculum.py` shell — reads spec, loops over playlists, creates records; `--dry-run` prints what would be created without writing to DB

### Phase 2 — Simple templates
- `voicing.py`: `close`, `open`, `close_4voice`, `keyboard_4voice`
- `templates.py`: `triad`, `seventh_chord`, `interval`, `diatonic_intervals`
- Label map for identification variants (see below)

### Phase 3 — Validate with partial theory1.yaml
- Write `data/curriculum/theory1.yaml` covering intervals + triads + dominant 7ths only
- Run `--dry-run`, inspect output, spot-check voicing and analysis
- Fix any issues before adding complex templates

### Phase 4 — Complex templates + complete curriculum
- `templates.py`: `scale`, `diatonic_triads`, `diatonic_sevenths`, `roto`, `progression`
- Complete `theory1.yaml` with all planned playlists
- Run final generation, tag all content `is_public`

---

## Exercise Types in Scope

Four types are used in theory1. Type is specified explicitly per playlist entry in the YAML — no auto-pairing.

| Type | Visible | Hidden | Input | Use case |
|---|---|---|---|---|
| `matching` | all notes | nothing | keyboard | Play what you see |
| `analytical` | nothing | all notes | keyboard | Realize from roman numeral overlay |
| `figured_bass` | bass note only | upper voices | keyboard | Realize from figured bass numbers |
| `identification` | all notes | nothing | dropdown | Select the correct label |

`analytical_pcs`, `figured_bass_pcs`, and `chorale` are out of scope for theory1.

---

## Identification Label Map

When `type: identification` is specified, the template also requires an `identification_label` field that names the analytical framework. `templates.py` contains a label map that defines `choices` and derives `answer` for each combination.

Each exercise entry in the YAML generates one exercise type. To get both matching and identification exercises from the same template, use two entries in the playlist's `exercises` list. `identification_label` is only read when `type: identification`; it is ignored otherwise.

```yaml
# YAML example — two entries produce both variants
exercises:
  - template: triad
    quality: major
    inversion: 0
    keys: all_major
    voicing: close
    type: matching

  - template: triad
    quality: major
    inversion: 0
    keys: all_major
    voicing: close
    type: identification
    identification_label: quality
```

| Template | `identification_label` | Choices | Answer source |
|---|---|---|---|
| `triad` | `quality` | `["major", "minor", "diminished", "augmented"]` | `quality` param |
| `triad` | `roman_numeral` | Diatonic to key (e.g. `["I","ii","iii","IV","V","vi","vii°"]`) | Scale degree |
| `triad` | `inversion` | `["root position", "first inversion", "second inversion"]` | `inversion` param |
| `seventh_chord` | `quality` | `["dominant 7","major 7","minor 7","half-dim 7","diminished 7"]` | `quality` param |
| `seventh_chord` | `inversion` | `["root position","6/5","4/3","4/2"]` | `inversion` param |
| `interval` | `name` | `["m2","M2","m3","M3","P4","TT","P5","m6","M6","m7","M7","P8"]` | Computed from interval size + quality |
| `diatonic_triads` | `roman_numeral` | Diatonic to key | Scale degree |
| `diatonic_sevenths` | `roman_numeral` | Diatonic 7ths to key | Scale degree |
| `figured_bass` | `symbol` | `["5/3","6","6/4","7","6/5","4/3","4/2"]` | Inversion symbol |

---

## theory1.yaml Content

~25 playlists, ~400 exercises across six topic areas. Content must be musically correct and pedagogically sound; exact match to existing hand-crafted exercises is not required.

Where a playlist entry below lists multiple types (e.g. `matching + identification`), each type is a separate entry in that playlist's `exercises` list in the YAML — not auto-generated.

### Intervals
- Diatonic intervals in major (common_major keys) — `matching` + `identification` (label: `name`)

### Triads
- Major triads, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Minor triads, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Diminished triads, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Major triads, 1st inversion, all 12 keys — `matching` + `identification` (label: `inversion`)
- Major triads, 2nd inversion, all 12 keys — `matching` + `identification` (label: `inversion`)
- Diatonic triads in major (common_major) — `matching` + `analytical` + `identification` (label: `roman_numeral`)

### Seventh chords
- Dominant 7th, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Major 7th, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Minor 7th, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Half-dim 7th, root position, all 12 keys — `matching` + `identification` (label: `quality`)
- Dominant 7th inversions, all 12 keys — `figured_bass` + `identification` (label: `inversion`)
- Diatonic 7th chords in major (common_major) — `matching` + `analytical` + `identification` (label: `roman_numeral`)

### Figured bass
- Triad inversions, figured bass realization (common_major) — `figured_bass`
- 7th chord inversions, figured bass realization (common_major) — `figured_bass`

### Scales
- Major scales (common_major) — `matching`
- Natural minor scales (common_minor) — `matching`
- Harmonic minor scales (common_minor) — `matching`

### ROTO + Progressions
- Rule of the Octave, major ascending (common_major) — `matching` + `analytical`
- Rule of the Octave, major descending (common_major) — `matching` + `analytical`
- ii–V–I in major keys (common_major) — `matching` + `analytical`

---

## Voicing Conventions

Implemented in `voicing.py`, informed by `exercises_2026-04-03.csv`:

- Bass note: C3 (MIDI 48) or nearby; chord tones in treble C4–C5 range
- `close`: notes stacked as close as possible, root in middle register
- `close_4voice`: root doubled at octave, 5th and 3rd fill in (SATB-style)
- `keyboard_4voice`: bass in left hand below bass clef, upper 3 voices in treble
- Key sequencing follows cycle of 5ths order

---

## Management Command Interface

```bash
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=admin@example.com
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=admin@example.com --dry-run
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=admin@example.com --overwrite
```

See `docs/curriculum_generation_spec.md` for full options reference.

---

## Related

- `docs/curriculum_generation_spec.md` — YAML format, template/voicing reference, full implementation order
- `exercises_2026-04-03.csv` — live exercise data showing voicing conventions to match
- `apps/exercises/management/commands/import_musicxml.py` — existing importer pattern to follow
