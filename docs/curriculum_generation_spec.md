# Curriculum Generation Spec

_Written: 2026-04-03_

## Problem

Creating a complete music theory curriculum by hand is not feasible. The existing live exercises reveal the pattern: almost every exercise is a systematic variation of a base template — all 12 dominant 7ths, diatonic triads in every key, Rule of the Octave ascending/descending, ii–V–I in all keys, etc. Each one was built by hand by computing MIDI numbers individually. A single semester curriculum requires ~400 exercises across ~23 playlists. At manual speed that's weeks of work per teacher.

The solution is a **generation system** with two input paths that both produce standard Exercise/Playlist/Course records in the database.

---

## Two Generation Paths

### Path A: Template-based generation (systematic/theoretical material)

A Python management command reads a **curriculum spec YAML file** and generates Exercise + Playlist + Course records in bulk. The spec file describes parameterizable patterns — chord formulae, key lists, transposition strategies.

Good for: all-12-keys exercises, diatonic sets, interval drills, chord quality surveys, scales, ROTO.

### Path B: MusicXML import (teacher-provided notation)

A teacher uploads a MusicXML file (from Sibelius, Finale, MuseScore, etc.). The system slices it into individual exercises by measure range, wraps each slice with key signature and analysis settings, and stores them as Exercise records. The teacher provides MusicXML for things that are hard to express as a formula: specific chorale examples, sight-reading excerpts, voice-leading demonstrations.

An `import_musicxml` management command already exists (`apps/exercises/management/commands/import_musicxml.py`). Path B is about surfacing this in a web UI with batch options and connecting it to the curriculum spec system.

Both paths produce the same output: `Exercise` records (with `data` JSON), optionally grouped into `Playlist` records, optionally grouped into a `Course`.

---

## Path A: Curriculum Spec YAML

### File location

`data/curriculum/<spec_name>.yaml` — version-controlled alongside the corpus data.

### Top-level structure

```yaml
# data/curriculum/theory1.yaml
meta:
  title: "Music Theory I"
  author: "admin@example.com"   # email of the Django User to assign as authored_by
  public: true                  # set is_public on all generated content

course:
  title: "Music Theory I — Full Course"
  playlists:
    - ref: triads_major_rp      # references a playlist defined below
    - ref: triads_major_inv
    - ref: seventh_chords_dominant
    - ref: roto_major
    # ... etc.

playlists:
  - id: triads_major_rp
    title: "Major Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: all_major           # shorthand for all 12 major keys
        voicing: close            # close | open | keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: seventh_chords_dominant
    title: "Dominant 7th Chords — All Keys"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        voicing: close_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}

  - id: roto_major
    title: "Rule of the Octave — Major (C)"
    tags: [voice-leading, roman-numerals]
    exercises:
      - template: roto
        mode: ascending
        scale: major
        keys: [jC_]
        staffDistribution: keyboardPlusLHBias
        type: matching
        analysis: {thoroughbass: true, roman_numerals: true}
        rhythm: h

  - id: diatonic_intervals_major
    title: "Diatonic Intervals in Major Keys"
    tags: [intervals]
    exercises:
      - template: diatonic_intervals
        scale: major
        keys: [jC_, jG_, jD_, jA_, jE_, jF_, jBb, jEb]
        upper_from_tonic: true
        staffDistribution: RH
        type: matching
        analysis: {intervals: true}
        rhythm: h
        time_signature: "2/2"
```

### Key shorthands

| Shorthand | Expands to |
|---|---|
| `all_major` | All 12 major keys in cycle of 5ths order: `jC_`, `jG_`, `jD_`, `jA_`, `jE_`, `jB_`, `jF#`, `jDb`, `jAb`, `jEb`, `jBb`, `jF_` |
| `all_minor` | All 12 minor keys: `iA_`, `iE_`, `iB_`, `iF#`, `iC#`, `iG#`, `iD_`, `iG_`, `iC_`, `iF_`, `iBb`, `iEb` |
| `all_12` | Chromatic: C through B |
| `common_major` | C, G, D, F, Bb, Eb (most common classroom keys) |
| `common_minor` | a, e, d, g, c, f |

### Built-in templates

Each template is a Python function in `apps/exercises/generation/templates.py` that takes parameters and returns a list of chord dicts `[{"visible": [...], "hidden": [...]}]`.

| Template | Parameters | Description |
|---|---|---|
| `single_note` | `pitches` list, key | Note-reading drill, one note per chord |
| `interval` | `quality`, `size`, `root`, `upper_staff_only` | Harmonic interval on treble or bass staff |
| `diatonic_intervals` | `scale`, `key`, `degrees` | All diatonic intervals from scale degree 1 |
| `triad` | `quality`, `inversion`, `voicing` | Major/minor/dim/aug triad in specified inversion |
| `diatonic_triads` | `scale`, `key`, `degree_range` | All diatonic triads in a key |
| `seventh_chord` | `quality`, `inversion`, `voicing` | Dom7/maj7/min7/ø7/°7 |
| `diatonic_sevenths` | `scale`, `key` | All diatonic seventh chords |
| `scale` | `type`, `key`, `direction` | Scale as sequence of single-note chords |
| `roto` | `mode` (asc/desc), `scale`, `key` | Rule of the Octave with full 4-voice SATB |
| `progression` | `chords` list with figured bass | Chord progression (e.g., `[I, IV, V, I]`) |
| `chorale_excerpt` | `bwv`, `start`, `end` | Delegates to existing `import_chorale` logic |

### Voicing strategies

The generator needs to place notes in specific registers to match pedagogical expectations. Templates use named voicing strategies:

| Strategy | Description |
|---|---|
| `close` | Notes stacked as close as possible, root in middle register (~C3–C5) |
| `open` | Notes spread across two octaves |
| `close_4voice` | SATB-style close voicing (root doubled, 4 voices) |
| `keyboard_4voice` | Bass in left hand (below bass clef), upper 3 voices in treble |
| `rh_only` | Right hand (treble staff) only |
| `lh_only` | Left hand (bass staff) only |

This is the part requiring the most careful implementation — voicing determines register and doubling. The existing CSV shows specific voicing conventions (e.g., dominant 7ths in the CSV use bass note ~C3, chord tones in treble). The generator should match these.

### Analysis settings shorthand

In the spec YAML, `analysis` is a dict of booleans. Any key not listed defaults to `false`. The generator expands this to the full analysis mode object the Exercise model expects.

```yaml
analysis: {roman_numerals: true, chord_labels: true}
# expands to:
# {"enabled": true, "tempo": false, "mode": {"roman_numerals": true, "chord_labels": true, "note_names": false, ...all others false}}
```

---

## Path B: MusicXML Web Import

The existing `import_musicxml` management command handles the parsing logic. What's needed is:

1. A web form at `POST /dashboard/exercises/import-musicxml/` (already in plan.md 2.10)
2. **Batch slicing**: given a MusicXML file, let the teacher specify a list of measure ranges to generate multiple exercises at once, e.g.:
   ```
   Measures 1–4   → Exercise "Chorale excerpt mm. 1–4"
   Measures 5–8   → Exercise "Chorale excerpt mm. 5–8"
   ```
   Or: auto-slice every N measures.
3. **Playlist creation**: optionally group all generated exercises into a new playlist.
4. **Analysis preset**: select which overlays to show (roman numerals, figured bass, note names, none).

The MusicXML → Exercise conversion already works (parses notes into MIDI arrays). The web UI just needs to drive it.

For **teacher-provided MusicXML** (sight-reading excerpts, voice-leading examples, specific chorale demonstrations): teacher exports from Sibelius/Finale/MuseScore as MusicXML, uploads to the form, slices, adds to a playlist. Done in minutes rather than hours.

---

## Path C: Word/theory questions (no staff)

A simple addition — a new exercise type `"question"` with no staff, just a text question and multiple choice answers. This is distinct from the `identification` type (which shows a staff). Useful for:
- Terminology definitions ("What is a deceptive cadence?")
- Key signature identification ("How many sharps does A major have?")
- Conceptual questions ("Which scale degree is the leading tone?")

### Exercise JSON shape

```json
{
  "type": "question",
  "question": "How many sharps does A major have?",
  "choices": ["2", "3", "4", "5"],
  "answer": "3",
  "introText": ""
}
```

No staff is rendered. The UI shows only the question text and button choices (same `LabelInputComponent` from the `identification` type). The grader is identical to `IdentificationGrader` — just one problem with no notes.

This is explicitly simpler than `identification` — no VexFlow, no notes, no staff at all.

---

## Management Command Interface

```bash
# Generate from a spec file
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=admin@example.com

# Options
python manage.py generate_curriculum <spec_file>
  --author=<email>          # required: Django user email
  --dry-run                 # print what would be created, don't write to DB
  --overwrite               # replace existing exercises with same description+author
  --public                  # override spec's public setting
  --course-only             # only create Course + Playlist structure, skip exercises
  --playlist <playlist_id>  # add all generated exercises to an existing playlist
```

### Output

On success:
```
Created 12 exercises for "Major Triads — Root Position" → playlist PL00AB
Created 12 exercises for "Dominant 7th Chords" → playlist PL00AC
Created 8 exercises for "Rule of the Octave — Major (C)" → playlist PL00AD
Created course "Music Theory I — Full Course" → CO00AA
Done. 32 exercises, 3 playlists, 1 course.
```

---

## File structure

```
apps/exercises/
  generation/
    __init__.py
    templates.py       # built-in template functions (triad, seventh_chord, roto, etc.)
    voicing.py         # voicing strategy implementations
    spec_loader.py     # YAML spec parser and validator
    analysis_presets.py  # expand shorthand analysis dicts to full mode objects

  management/commands/
    generate_curriculum.py   # new management command
    import_musicxml.py       # existing — extract core logic to utils/musicxml.py
    import_chorale.py        # existing

data/curriculum/
  theory1.yaml          # Semester 1 spec (intervals, triads, 7th chords, ROTO, voice leading)
  theory2.yaml          # Semester 2 spec (secondary dominants, modulation, etc.)
  post_tonal.yaml       # Semester 3+ spec (set classes, interval cycles, hexatonics, etc.)
```

---

## What the existing CSV tells us about conventions

The live exercises establish implicit conventions the generator must match:

- **Register**: Bass note typically C3 (MIDI 48) or nearby; chord tones in treble C4–C5 range
- **Triad voicing (4-voice)**: Root doubled at octave, 5th and 3rd fill in between
- **7th chord voicing (4-voice close)**: root–3rd–5th–7th stacked close in treble, bass in bass clef
- **7th chord voicing (3-voice)**: root/5th–3rd–7th (omit fifth), used for jazz shell voicings
- **Diatonic intervals**: Bottom note is the lower pitch; upper note uses diatonic intervals above
- **ROTO**: 8 chords, bass walks scale step by step, upper voices move in 4-part voice-leading
- **Cycle of 5ths order**: Exercises progress C → G → D → A → E → B → F# → Db → Ab → Eb → Bb → F

These conventions need to be encoded in the voicing strategy functions so generated exercises look and feel like the existing hand-crafted ones.

---

## What MusicXML covers that templates can't

- Specific voice-leading demonstrations from a piece
- Sight-reading excerpts
- Passages from specific pedagogical literature
- Anything with irregular rhythm, ornaments, ties across measures
- The teacher's own compositional examples

For these, the teacher authors the passage in Sibelius/Finale/MuseScore, exports as MusicXML, and imports via the web UI. Template generation handles everything systematic.

---

## Implementation order

1. `apps/exercises/generation/analysis_presets.py` — simplest, no dependencies
2. `apps/exercises/generation/voicing.py` — core interval/register logic
3. `apps/exercises/generation/templates.py` — template functions using voicing.py
4. `apps/exercises/generation/spec_loader.py` — YAML parser and validator
5. `apps/exercises/management/commands/generate_curriculum.py` — management command
6. `data/curriculum/theory1.yaml` — first real spec, validate against CSV conventions
7. MusicXML web UI (after management command is working)
8. `question` exercise type (simple addition after `identification` is done)

---

## Related

- [plan.md](plan.md) — section 2.12 (curriculum generation) and 2.10 (MusicXML web UI)
- [spec.md](spec.md) — section 2.9 (content library build plan)
- `exercises_2026-04-03.csv` — live exercise data showing conventions to match
- `apps/exercises/management/commands/import_musicxml.py` — existing MusicXML parser
- `apps/exercises/management/commands/import_chorale.py` — existing chorale importer pattern
