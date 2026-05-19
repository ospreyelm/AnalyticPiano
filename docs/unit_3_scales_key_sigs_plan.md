# Unit 3: Scales & Key Signatures — Curriculum Plan

_Branch: Core Sequence, Tier 1 — Fundamentals_

**Taxonomy entry:** Major, minor forms, circle of fifths
**Tags:** `key_signature`, `major_scale`, `minor_scale`, `Scale_Degrees`, `Pitch_Class`

---

## Status: Partially implemented

Key signature identification (major + minor) and major scale play exercises are live. Minor scale play exercises are not yet generated.

---

## What exists

### Lane 1 — Key Signature Identification

Student sees a staff with a key signature and identifies the key by clicking the correct answer.

**Command:**
```
python manage.py generate_unit3_key_sig_exercises --author <email> --public
```

Generates **6 exercises**: 3 levels × {major, minor}.

**Level accidental limits:**

| Level | Max accidentals | Keys covered |
|---|---|---|
| 1 | ≤3 | C, G, D, A / Am, Em, Bm, Dm, Gm, Cm |
| 2 | ≤5 | adds E, B, Db, F / adds F#m, C#m, Fm, Bbm |
| 3 | ≤7 | all keys including theoretical (C#, Cb, Gb, F#) |

Enharmonic duplicates are excluded at level ≤2 to avoid presenting the same key signature twice (e.g. F# and Gb share 6 sharps/flats; only F# is shown at level 1–2). Both appear at level 3.

**Playlist names:** `Unit 3 — Key Signatures {Major|Minor}, Level {1|2|3}`
**Tags:** `unit:3`, `key_signature`, `unit:3_key_signature_{major|minor}`, `unit:3_L{level}`

**Key files:**
- `apps/exercises/key_signature_problems.py` — `KEY_TABLE`, `MINOR_KEY_TABLE`, `build_key_sig_problem_set()`

---

### Lane 2 — Scale Play (Major and Minor)

Student sees a one-measure grand-staff scale and plays through it on MIDI.

**Command:**
```
# Major only (default)
python manage.py generate_unit3_scale_exercises --author <email> --public

# Minor only (all three forms)
python manage.py generate_unit3_scale_exercises --author <email> --mode minor --public

# Everything at once
python manage.py generate_unit3_scale_exercises --author <email> --mode both --public

# Specific minor forms only
python manage.py generate_unit3_scale_exercises --author <email> --mode minor --minor-forms natural harmonic --public
```

**15 keys per form** (all keys including theoretical enharmonics), grouped into 3 level playlists:

| Level | Max accidentals | Keys |
|---|---|---|
| 1 | ≤3 | C, F, G, Bb, D, Eb, A (major) / A, E, D, B, G, F#, C (minor) |
| 2 | ≤5 | adds Ab, E, Db, B / adds C#, F, G#, Bb |
| 3 | ≤7 | adds Gb, F#, Cb, C# / adds D#, Eb, A#, Ab |

**Major scales:** read from `docs/scales-key-signatures/piano-major-scales-fingerings.mxl` (must be present). Treble part auto-shifted down one octave for keys where the top note exceeds a 5-octave keyboard (F, G, A, Bb, B, Ab, F#).

**Minor scales:** generated programmatically via music21 — no source file needed. One octave ascending, 8 eighth notes per measure. Treble: root4→root5; Bass: root3→root4.

| Form | music21 class | Notes |
|---|---|---|
| Natural | `MinorScale` | Standard natural minor (Aeolian) |
| Harmonic | `HarmonicMinorScale` | Raised 7th |
| Melodic | `MelodicMinorScale` | Ascending form (raised 6th+7th); music21 returns ascending by default |

**Playlist names:**
- `Unit 3 — Major Scales, Level {1|2|3}`
- `Unit 3 — Minor Scales (Natural), Level {1|2|3}`
- `Unit 3 — Minor Scales (Harmonic), Level {1|2|3}`
- `Unit 3 — Minor Scales (Melodic), Level {1|2|3}`

**Tags:** `unit:3`, `{major_scale|minor_scale}`, `unit:3_{major_scale|minor_scale[_natural|_harmonic|_melodic]}`, `unit:3_L{level}`

**Skill graph prerequisites:** `unit:3_minor_scale_harmonic` and `unit:3_minor_scale_melodic` both require `unit:3_minor_scale_natural`.

**Key files:**
- `apps/exercises/management/commands/generate_unit3_scale_exercises.py`

---

## Rebuild sequence

```bash
# Key signatures (major and minor, all 3 levels)
python manage.py generate_unit3_key_sig_exercises --author <email> --public --overwrite

# All scales: major (from MusicXML) + all three minor forms (programmatic)
python manage.py generate_unit3_scale_exercises --author <email> --mode both --public --overwrite
```

If playlist taxonomy tags are out of sync (e.g. after a tag rename), run the one-shot fixer:
```bash
python manage.py fix_unit3_playlists
```
This command is idempotent and safe to re-run.

---

## Course structure

```
Course: "Unit 3: Scales & Key Signatures"
  Playlist: "Unit 3 — Key Signatures Major, Level 1"
  Playlist: "Unit 3 — Key Signatures Major, Level 2"
  Playlist: "Unit 3 — Key Signatures Major, Level 3"
  Playlist: "Unit 3 — Key Signatures Minor, Level 1"
  Playlist: "Unit 3 — Key Signatures Minor, Level 2"
  Playlist: "Unit 3 — Key Signatures Minor, Level 3"
  Playlist: "Unit 3 — Major Scales, Level 1"
  Playlist: "Unit 3 — Major Scales, Level 2"
  Playlist: "Unit 3 — Major Scales, Level 3"
  Playlist: "Unit 3 — Minor Scales (Natural), Level 1"
  Playlist: "Unit 3 — Minor Scales (Natural), Level 2"
  Playlist: "Unit 3 — Minor Scales (Natural), Level 3"
  Playlist: "Unit 3 — Minor Scales (Harmonic), Level 1"
  Playlist: "Unit 3 — Minor Scales (Harmonic), Level 2"
  Playlist: "Unit 3 — Minor Scales (Harmonic), Level 3"
  Playlist: "Unit 3 — Minor Scales (Melodic), Level 1"
  Playlist: "Unit 3 — Minor Scales (Melodic), Level 2"
  Playlist: "Unit 3 — Minor Scales (Melodic), Level 3"
```

---

## What is NOT yet built

| Concept | Gap | Notes |
|---|---|---|
| Minor scale play exercises | ✅ Done | Natural, harmonic, and melodic minor generated programmatically via music21 (`--mode minor`) |
| Scale degree / solfège identification | Not yet | Could use `identification` type with scale degree labels as choices |
| Circle of fifths drill | Not yet | Could be hand-authored `identification` exercises (e.g. "how many sharps in D major?") |
| Key signature spelling (write it) | Not yet — no construct exercise type | Out of scope |

The taxonomy tags `Scale_Degrees` and `Pitch_Class` are listed for Unit 3 but have no corresponding exercises yet.

---

## Reference

- [Exercise types](exercise_types.md) — exercise type reference
- `apps/exercises/management/commands/generate_unit3_key_sig_exercises.py`
- `apps/exercises/management/commands/generate_unit3_scale_exercises.py`
- `apps/exercises/key_signature_problems.py`
- `docs/scales-key-signatures/piano-major-scales-fingerings.mxl` — required source for scale exercises
