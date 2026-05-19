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

### Lane 2 — Major Scale Play

Student sees a one-measure grand-staff major scale and plays through it on MIDI.

**Command:**
```
python manage.py generate_unit3_scale_exercises --author <email> --public
```

**Source:** `docs/scales-key-signatures/piano-major-scales-fingerings.mxl` — a MusicXML file containing all 15 major scales on a grand staff with standard piano fingerings. This file must be present; it is not auto-generated.

**15 scales covered** (all major keys including theoretical C#, Cb, Gb):

| Level | Max accidentals | Scales |
|---|---|---|
| 1 | ≤3 | C, F, G, Bb, D, Eb, A |
| 2 | ≤5 | adds Ab, E, Db, B |
| 3 | ≤7 | adds Gb, F#, Cb, C# |

For keys where the treble right-hand part would exceed a 5-octave keyboard (F, G, A, Bb, B, Ab, F#), the treble part is automatically shifted down one octave.

**Playlist names:** `Unit 3 — Major Scales, Level {1|2|3}`
**Tags:** `unit:3`, `major_scale`, `unit:3_major_scale`, `unit:3_L{level}`

**Key files:**
- `apps/exercises/management/commands/generate_unit3_scale_exercises.py` — parses MusicXML via music21, builds CIR, creates `chorale`-type exercises

---

## Rebuild sequence

```bash
# Key signatures (major and minor, all 3 levels)
python manage.py generate_unit3_key_sig_exercises --author <email> --public --overwrite

# Major scales (requires MusicXML at docs/scales-key-signatures/piano-major-scales-fingerings.mxl)
python manage.py generate_unit3_scale_exercises --author <email> --public --overwrite
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
```

---

## What is NOT yet built

| Concept | Gap | Notes |
|---|---|---|
| Minor scale play exercises | No command yet | Needs a MusicXML source for natural/harmonic/melodic minor scales, or hand-authored CIR JSON; then a new `generate_unit3_minor_scale_exercises.py` modeled on the major scale command |
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
