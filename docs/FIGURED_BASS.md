# Figured Bass in HarmonyLab

## What is figured bass?

Figured bass is a Baroque notation system where numbers (figures) written below a bass note specify the intervals above it. A keyboard player reads the bass line and improvises the upper voices according to the figures.

```
  ┌──────────────────────────────┐
  │  soprano  G4                 │
  │  alto     E4                 │
  │  tenor    C4                 │
  │  bass     C3  ← written out  │
  │           5/3 ← figured      │
  └──────────────────────────────┘
```

The figures describe intervals above the bass — so `5/3` over C means E (a third) and G (a fifth), forming a C major triad.

---

## Abbreviation conventions (Kellner 1732)

Most common chords have conventional abbreviations. HarmonyLab uses these throughout:

| Raw stack | Abbreviated | Chord type |
|-----------|-------------|------------|
| `8/5/3` or `5/3` | `5/3` | Root-position triad |
| `8/6/3` or `6/3` | `6` | First-inversion triad |
| `8/6/4` or `6/4` | `6/4` | Second-inversion triad |
| `8/7/5/3` or `7/5/3` | `7` | Root-position seventh |
| `6/5/3` | `6/5` | First-inversion seventh |
| `6/4/3` | `4/3` | Second-inversion seventh |
| `6/4/2` | `4/2` | Third-inversion seventh |
| `5/4` | `5/4` | 4–3 suspension |

**Chromatic alterations** are prefixed to the affected interval number:
- `#6` — sixth raised a semitone above diatonic
- `b7` — seventh lowered
- `+` suffix — tritone (augmented fourth/diminished fifth), e.g. `4+`

Root-position triads with a chromatic third or fifth show only the accidental: `#` (raised third), `b5` (lowered fifth).

---

## Curriculum sequence (units 9–13)

Figures introduced progressively. Students only see figures from their current and prior units.

| Unit | Title | New figures | Cumulative |
|------|-------|-------------|------------|
| 9 | Tonic & dominant | `5/3`, `7` | `5/3`, `7` |
| 10 | First inversions | `6`, `6/5` | `5/3`, `7`, `6`, `6/5` |
| 11 | Pre-dominants | _(none new)_ | same as unit 10 |
| 12 | Second inversions | `6/4`, `5/4`, `4/3`, `4/2` | all of above |
| 13 | Rule of the octave | _(none new)_ | same as unit 12 |

Units 14+ (`figured_bass` entries in taxonomy) are TBD.

---

## How exercises work

### Student view

Each beat of a Bach chorale phrase has a `?` button below the score. Students click it and choose the correct figure from a dropdown of 4–5 options.

```
  [score: treble + bass staves]

  A major  [?] [?] [?]   [?] [?] [?]   [?]   [?]   [?]
```

The key is shown at the left. Figures are always relative to the bass note at that beat.

### Answer choices

Choices are drawn from the unit's **cumulative** figure set. The correct answer is always present; distractors are other figures the student has already encountered. If the pool is too small, fallback choices are `["5/3", "6", "6/4", "7", "6/5", "4/3", "4/2"]`.

### Targeted beats

Not every beat gets a `?`. Only beats where the sounding chord uses a figure from the unit's **cumulative** set are targeted (`is_target = true`). This prevents students from seeing figures they haven't learned yet.

---

## Pipeline (import → storage → rendering)

```
Bach MIDI/MusicXML
        ↓
    music21 parse
        ↓
  chordify() per beat → roman.romanNumeralFromChord()
        ↓
  compute_figured_bass(chord, key)
    → raw_figured_bass: "7/5/3"
    → figured_bass:     "7"      (Kellner abbreviation)
        ↓
  AnalysisSlice stored in Exercise.data['score']['umto']['analysis']
    slice.content.raw_figured_bass = "7/5/3"
    slice.content.figured_bass     = "7"
    slice.is_target                = True/False
        ↓
  to_frontend_payload(analysis_type="figured_bass")
    → problems[i].answer = slice.content.figured_bass
    → problems[i].choices = [buildChoices from cumulative set]
        ↓
  JS: buildUMTOIdentificationProblems()
    → applySkillFilter() hides non-targeted beats
        ↓
  Student sees score + ? buttons
```

### Key files

| File | Role |
|------|------|
| `apps/exercises/utils/figured_bass.py` | `compute_figured_bass()` + `abbreviate_figured_bass()` |
| `apps/exercises/umto.py` | `AnalysisLayer` model, `to_frontend_payload()` |
| `apps/exercises/umto_factory.py` | CIR→UMTO conversion, note splitting at beat boundaries |
| `apps/exercises/management/commands/import_bach_phrases.py` | Sets `analysis_type="figured_bass"`, calls `build_umto_payload()` |
| `apps/exercises/management/commands/create_unit_playlist.py` | End-to-end import + playlist creation for a unit |
| `music_theory_taxonomy.json` | Cumulative/new figure sets per unit (source of truth) |
| `lab/static/js/src/models/exercise_definition.js` | `buildUMTOIdentificationProblems()`, `applySkillFilter()`, `buildChoices()` |

---

## Creating a figured bass playlist

```bash
python manage.py create_unit_playlist \
  --unit 10 \
  --riemenschneider 1-40 \
  --author admin@example.com \
  --mode figures \
  --public
```

To regenerate existing exercises (e.g. after a bug fix):

```bash
python manage.py create_unit_playlist \
  --unit 10 --riemenschneider 1-40 \
  --author admin@example.com \
  --mode figures \
  --overwrite
```

---

## Known limitations and deferred work

**Suspension detection** — `5/4` (4–3 suspension) requires looking ahead to the resolution note. Currently `compute_figured_bass()` only sees one chord at a time. Implemented stub in `_build_figured_bass_overrides()` in `import_bach_phrases.py` but not yet wired up for all suspension types.

**Chromatic figures** — `#6` (Italian/French/German augmented sixths), `b7`, etc. are computed correctly by `compute_figured_bass()` but the taxonomy `new`/`cumulative` entries for units 14+ are not yet defined.

**Unison noteheads** — when two voices share the same pitch but different durations at the same beat (e.g. alto holds a quarter while soprano plays an eighth), the filled/open notehead distinction requires per-voice VexFlow formatting. Currently both voices share the slot's duration. Beat-boundary splitting (in `umto_factory.py`) mitigates the worst cases.

**Stacked notation** — figures and Roman numerals are currently rendered as flat strings. HTML-stacked rendering (e.g. `6` over `4`) is deferred.

**Units 14+** — `figured_bass` entries in `music_theory_taxonomy.json` are empty for units 14–51. Need to define `new`/`cumulative` values before building playlists for those units.
