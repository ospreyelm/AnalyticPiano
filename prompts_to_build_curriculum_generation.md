# Prompts to Build the Curriculum Generation System

_Status: not started_
_Spec: [docs/curriculum_generation_spec.md](docs/curriculum_generation_spec.md)_
_Plan: [docs/plan.md](docs/plan.md) section 2.12_

These prompts implement the curriculum generation system in order. Each prompt is a standalone task for a focused coding session. Run them sequentially — later prompts depend on earlier ones.

---

## Step 1: Analysis presets and spec loader (no exercise creation yet)

Create the two support modules that the main command depends on.

**Target files (new):**
- `apps/exercises/generation/__init__.py`
- `apps/exercises/generation/analysis_presets.py`
- `apps/exercises/generation/spec_loader.py`

**What to implement:**

In `analysis_presets.py`, create a function `expand_analysis(shorthand_dict)` that takes a dict like `{"roman_numerals": True, "chord_labels": True}` and returns the full analysis object that the Exercise JSON `data["analysis"]` expects, matching the shape already used by existing exercises. Look at `apps/exercises/models.py` and the existing exercise JSON data to confirm the expected shape. Return `{"enabled": True, "tempo": False, "mode": {...all keys...}}` with all unspecified keys defaulted to `False`.

Include a dict of named **analysis presets** that can be referenced by name in the YAML spec:
- `"roman_numerals_only"` — `{roman_numerals: true}`
- `"figured_bass_only"` — `{thoroughbass: true}`
- `"roman_and_bass"` — `{roman_numerals: true, thoroughbass: true}`
- `"note_names"` — `{note_names: true}`
- `"chord_labels"` — `{chord_labels: true}`
- `"full"` — all modes enabled
- `"none"` — all modes disabled

In `spec_loader.py`, create a function `load_spec(yaml_path)` that:
1. Reads and parses the YAML file
2. Validates required top-level keys: `meta`, `course` (optional), `playlists`
3. Expands key shorthands in any `keys:` field into explicit key string lists:
   - `all_major` → 12 major keys (cycle of 5ths order): `["jC_", "jG_", "jD_", "jA_", "jE_", "jB_", "jF#", "jDb", "jAb", "jEb", "jBb", "jF_"]`
   - `all_minor` → 12 minor keys: `["iA_", "iE_", "iB_", "iF#", "iC#", "iG#", "iD_", "iG_", "iC_", "iF_", "iBb", "iEb"]`
   - `all_12` → chromatic from C: `["jC_", "jC#", "jD_", "jEb", "jE_", "jF_", "jF#", "jG_", "jAb", "jA_", "jBb", "jB_"]`
   - `common_major` → `["jC_", "jG_", "jD_", "jF_", "jBb", "jEb"]`
   - `common_minor` → `["iA_", "iE_", "iD_", "iG_", "iC_", "iF_"]`
4. Expands any `analysis:` value that is a string (named preset) using `expand_analysis()`
5. Returns a validated Python dict that `generate_curriculum.py` can iterate over

**Tests:** Write a small `tests/test_spec_loader.py` under `apps/exercises/` (or as a standalone script) that loads `data/curriculum/theory1.yaml` once it exists, and verifies key expansion and analysis preset expansion. Keep it as a simple script (`if __name__ == "__main__"`) not a full Django test case, since it has no DB dependency.

---

## Step 2: Voicing strategies and MIDI note building

Create the low-level MIDI number computation functions that all templates will use.

**Target file (new):** `apps/exercises/generation/voicing.py`

**Note the existing key format** used across the codebase:
- `"jC_"` = C major, `"jG_"` = G major, `"jF#"` = F# major
- `"iA_"` = A minor, `"iE_"` = E minor, `"iF#"` = F# minor
- `"h"` = atonal/no key

**What to implement:**

```python
# Parse a key string to (tonic_pc, is_major)
def parse_key(key_str):
    ...

# Return the diatonic scale as a list of pitch classes (0–11)
# scale_type: "major", "natural_minor", "harmonic_minor", "melodic_minor"
def scale_pcs(tonic_pc, scale_type="major"):
    ...

# Return MIDI number for a given pitch class and desired octave
# octave: 4 = middle C octave
def midi(pitch_class, octave):
    ...

# Build a chord as a list of MIDI numbers
# root_midi: bass note
# intervals: list of semitones above root, e.g., [4, 7] for major triad
def build_chord_from_intervals(root_midi, intervals):
    ...

# Inversion: rotate intervals so the nth interval is bass
def invert(intervals, inversion):
    ...

# TRIAD QUALITIES — returns interval stack above root (not inverted)
TRIAD_INTERVALS = {
    "major":      [4, 7],
    "minor":      [3, 7],
    "diminished": [3, 6],
    "augmented":  [4, 8],
}

# SEVENTH CHORD QUALITIES
SEVENTH_INTERVALS = {
    "dominant":   [4, 7, 10],    # dominant 7th
    "major_major":[4, 7, 11],    # major 7th
    "minor_minor":[3, 7, 10],    # minor 7th
    "half_dim":   [3, 6, 10],    # ø7
    "full_dim":   [3, 6, 9],     # °7
}

# Build a 3-voice triad in close position
# Returns [bass_midi, third_midi, fifth_midi] — SATB with root doubled is a 4-voice close position
def close_triad(root_pc, quality, inversion=0, bass_octave=3):
    ...

# 4-voice close triad: root doubled at octave
def close_4voice_triad(root_pc, quality, inversion=0, bass_octave=3):
    ...

# 4-voice seventh chord close position
def close_4voice_seventh(root_pc, quality, inversion=0, bass_octave=3):
    ...

# Keyboard voicing: bass in bass clef, upper 3 voices in treble clef
def keyboard_4voice(root_pc, intervals_above_root, inversion=0, bass_octave=2):
    ...
```

**Register conventions to match existing CSV exercises:**
- Bass note for chord exercises: around MIDI 48 (C3) — adjust per key so root lands near C3
- Treble chord tones: C4–C5 range (MIDI 60–72)
- For keyboard voicing, bass in bass clef (MIDI 36–52), upper 3 voices in treble clef (MIDI 60–76)

Write a standalone validation script `apps/exercises/generation/validate_voicing.py` that prints out chord MIDI numbers for dominant 7th in all 12 keys (close position, 4 voice) so you can visually verify register against the existing EA00GF exercise family.

---

## Step 3: Template functions

Create the library of parameterizable exercise templates.

**Target file (new):** `apps/exercises/generation/templates.py`

Each template function takes parameters and returns a list of **chord dicts** matching the Exercise JSON `data["chord"]` array shape:
```python
[
    {"rhythmValue": "w", "visible": [60, 64, 67], "hidden": []},
    ...
]
```

The function does NOT create Exercise records — it just returns the chord list. `generate_curriculum.py` wraps this with the full Exercise JSON.

**Templates to implement:**

```python
def single_note(pitches, rhythm="w"):
    """Note reading: one note per chord. pitches = list of MIDI numbers."""

def harmonic_interval(root_midi, interval_semitones, rhythm="w", upper_staff_only=False):
    """One harmonic interval as a 2-note chord."""

def diatonic_intervals(key_str, sizes=(2,3,4,5,6,7), rhythm="h"):
    """All diatonic intervals from scale degree 1 in the given key.
    Returns one chord per interval size (upper note varies diatonically).
    Match the convention in CSV exercises EA00HW (intervals from a root)."""

def triad(root_pc, quality, inversion=0, voicing="close", rhythm="w"):
    """Single triad chord. Returns a 1-element chord list."""

def all_triads_in_key(key_str, qualities=None, inversions=(0,), rhythm="w"):
    """All diatonic triads in a key. Returns 7 (or 7 × inversions) chords."""

def seventh_chord(root_pc, quality, inversion=0, voicing="close_4voice", rhythm="w"):
    """Single 7th chord. Returns a 1-element chord list."""

def all_sevenths_in_key(key_str, rhythm="w"):
    """All diatonic seventh chords in a key. Returns 7 chords."""

def scale_exercise(key_str, scale_type="major", direction="asc", as_melody=True, rhythm="q"):
    """Scale as a sequence of single-note (melody) chords, ascending or descending."""

def roto(key_str, direction="ascending", rhythm="h"):
    """Rule of the Octave — full 4-voice SATB.
    Bass walks the scale step-by-step; upper voices follow standard ROTO voice leading.
    Match the convention in EA00YH (ROTO ascending major).
    This requires hard-coded soprano/alto/tenor lines for each scale degree in major and minor.
    Start with major ascending and major descending; minor can follow."""

def progression(key_str, chords, rhythm="w"):
    """A chord progression as a sequence of chords.
    chords: list of dicts like [{"degree": 1, "quality": "major"}, {"degree": 5, "quality": "dominant"}, ...]
    Returns one chord dict per item."""
```

**Key decisions:**
- `roto` is the most complex — it requires voice-leading tables, not just formulas. Look at the CSV exercises to reverse-engineer the soprano, alto, tenor lines at each scale degree. Or hard-code them from standard ROTO sources (Gjerdingen, Aldwell-Schachter).
- All other templates are purely formula-driven.
- Templates produce `hidden: []` by default (all notes visible as in `matching` type). The caller in `generate_curriculum.py` applies type-specific visibility logic.

---

## Step 4: Management command `generate_curriculum`

Wire everything together into a callable Django management command.

**Target file (new):** `apps/exercises/management/commands/generate_curriculum.py`

**Depends on:** Steps 1–3.

**Command interface:**

```
python manage.py generate_curriculum data/curriculum/theory1.yaml
  --author=<email>     (required)
  --dry-run            (print what would be created, write nothing)
  --overwrite          (delete+recreate exercises with matching description+author)
  --public             (force all generated content to is_public=True)
```

**What it does:**

1. Load and validate the spec with `spec_loader.load_spec(path)`
2. Resolve the author: `User.objects.get(email=author_email)`
3. For each playlist in the spec:
   a. For each exercise entry in the playlist:
      - Call the appropriate template function to get a chord list
      - Apply visibility logic for the specified `type` (matching → all visible, analytical → all hidden, figured_bass → bass visible + rest hidden)
      - Build the full Exercise JSON dict: `{"type": ..., "key": ..., "keySignature": ..., "staffDistribution": ..., "analysis": expand_analysis(...), "chord": [...], ...}`
      - In non-dry-run mode: create or update an `Exercise` record
   b. Create or update a `Playlist` record; add all generated exercises to it
4. If a `course:` key exists in spec, create a `Course` and ordered playlists

**Auto-ID generation:** Exercise and Playlist IDs are generated by the model's `BaseContentModel` auto-ID logic — don't specify them explicitly; let the model assign them.

**Dry run output:** Print a table showing what would be created:
```
[DRY RUN] Would create Exercise: "Major Triad in C major" (type=matching)
[DRY RUN] Would create Exercise: "Major Triad in G major" (type=matching)
...
[DRY RUN] Would create Playlist: "Major Triads — Root Position" (12 exercises)
```

**Error handling:**
- If author email not found: `CommandError`
- If template name not found: `CommandError` with list of valid template names
- If YAML is invalid: catch `ValidationError` and print readable errors

---

## Step 5: Write `data/curriculum/theory1.yaml` and validate output

Create the first real curriculum spec and validate that the output matches the conventions established in the live CSV exercises.

**Target file (new):** `data/curriculum/theory1.yaml`

**What to include (based on CSV patterns):**

```yaml
meta:
  title: "Music Theory I — Core Curriculum"
  author: "<your-email>"
  public: true

playlists:
  # --- Intervals ---
  - id: intervals_from_root_major
    title: "Diatonic Intervals — Major Keys"
    exercises:
      - template: diatonic_intervals
        keys: common_major
        type: matching
        analysis: roman_numerals_only
        rhythm: h

  # --- Triads ---
  - id: triads_major_rp
    title: "Major Triads — Root Position (all keys)"
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: all_major
        type: matching
        analysis: {chord_labels: true, roman_numerals: true}
        rhythm: w

  - id: triads_minor_rp
    title: "Minor Triads — Root Position (all keys)"
    exercises:
      - template: triad
        quality: minor
        inversion: 0
        keys: all_major
        type: matching
        analysis: {chord_labels: true, roman_numerals: true}
        rhythm: w

  - id: triads_diminished_rp
    title: "Diminished Triads — Root Position (all keys)"
    exercises:
      - template: triad
        quality: diminished
        inversion: 0
        keys: all_12
        type: matching
        analysis: chord_labels
        rhythm: w

  # --- Seventh Chords ---
  - id: seventh_dominant_all_keys
    title: "Dominant 7th Chords (all keys)"
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        type: matching
        analysis: {chord_labels: true, roman_numerals: true}

  - id: seventh_minor_all_keys
    title: "Minor 7th Chords (all keys)"
    exercises:
      - template: seventh_chord
        quality: minor_minor
        inversion: 0
        keys: all_major
        type: matching
        analysis: {chord_labels: true}

  - id: seventh_fulldim_all_keys
    title: "Fully Diminished 7th Chords (all keys)"
    exercises:
      - template: seventh_chord
        quality: full_dim
        inversion: 0
        keys: all_12
        type: matching
        analysis: {chord_labels: true}

  # --- Rule of the Octave ---
  - id: roto_major_ascending
    title: "Rule of the Octave — Major Ascending (C)"
    exercises:
      - template: roto
        direction: ascending
        scale: major
        keys: [jC_]
        type: matching
        analysis: {roman_numerals: true, thoroughbass: true}
        rhythm: h
```

**Validation steps:**
1. `python manage.py generate_curriculum data/curriculum/theory1.yaml --author=<email> --dry-run` — should print all exercises without DB writes
2. `python manage.py generate_curriculum data/curriculum/theory1.yaml --author=<email>` — creates records
3. Open the Django admin or dashboard and spot-check 3–4 exercises: MIDI note numbers should match expected register, voicing should look correct
4. Load the exercise in the app (`/play?exercise=<id>`) and verify it renders + plays correctly
5. Compare dominant 7th output against existing EA00GF exercise family — MIDI numbers and voicing should be equivalent

---

## Step 6: MusicXML batch import enhancements

Extend the existing `import_musicxml` command and add the web UI form.

**Target files (modify):**
- `apps/exercises/management/commands/import_musicxml.py`
- `apps/exercises/utils/musicxml.py` (new — extract core logic here)
- `apps/exercises/views.py` (add web import view)
- `apps/exercises/urls.py` (add URL)
- `apps/exercises/templates/exercises/import_musicxml.html` (new)

**What to do:**

First, **extract** the core MusicXML → Exercise dict logic from `import_musicxml.py` into `apps/exercises/utils/musicxml.py` as a function `parse_musicxml_to_chords(file_path, start_measure=None, end_measure=None)`. The management command should then just call this function. This makes it callable from the web view without subprocess.

**Add batch slicing:** Extend `parse_musicxml_to_chords` to accept a list of measure ranges:
```python
parse_musicxml_to_exercise_list(file_path, slices=[(1,4), (5,8), (9,12)], exercise_type="matching", analysis_preset="roman_numerals_only")
```
Returns a list of Exercise data dicts, one per slice.

**Web form (teacher-facing):**
- File upload (MusicXML only — validate MIME type and extension)
- Measure range mode: "single range" (start/end inputs) or "auto-slice every N measures" 
- Exercise type selector: matching / analytical / figured_bass / chorale
- Analysis preset selector: roman numerals / figured bass / none / custom
- Playlist: create new (with name field) or add to existing (dropdown)
- Public checkbox

**In the view:** Call `parse_musicxml_to_exercise_list`, create Exercise records, create/update Playlist. Redirect to the playlist detail page on success.

**Security note:** Validate that the uploaded file is genuinely XML (parse it, catch exceptions) before any processing. Reject files over 5MB. Never pass the filename to a shell.

---

## Step 7: Word/question exercise type

Add a pure-text exercise type with no staff rendering.

**Target files (modify):**
- `lab/static/js/src/models/exercise_definition.js`
- `lab/static/js/src/components/music/exercise_sheet.js`
- `lab/static/js/src/models/exercise_context.js`
- `lab/templates/exercise.html`

**What to add:**

In `exercise_definition.js`:
- Add `"question"` to the types list
- Add `isQuestion()` method
- Parse `question`, `choices`, `answer` fields from the exercise JSON at the top level (not per-chord, since a `question` exercise has exactly one answer)

In `exercise_sheet.js`:
- Add branch: `if (definition.isQuestion()) { this._initQuestionMode(); }`
- `_initQuestionMode()` skips all VexFlow rendering; mounts `LabelInputComponent` with the question text and choices; hides the `<canvas>` element

Since `LabelInputComponent` is already being built for the `identification` type (see `prompts_to_build_identification.md`), reuse it here. The only difference is no canvas is shown and no staff context.

In `exercise_context.js`:
- Branch on `isQuestion()` to use `IdentificationGrader` (same as identification type — one problem, no notes)

**Exercise JSON shape:**
```json
{
  "type": "question",
  "question": "How many sharps does A major have?",
  "choices": ["2", "3", "4", "5"],
  "answer": "3",
  "introText": ""
}
```

**Template for generation:**

In `apps/exercises/generation/templates.py`, add:
```python
def word_question(question_text, choices, answer):
    """Returns a single-item chord list with question metadata.
    The Exercise JSON wraps this at the top level, not in chord[].
    Returns the extra top-level fields as a metadata dict."""
```

Note: `question` exercises don't use the `chord` array — the data format is different. The Exercise model just stores it as JSON in `data`, so any shape is valid.

---

## Smoke tests

After all steps: verify the full generation pipeline end-to-end.

```bash
# 1. Dry run the full theory1 spec
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=<email> --dry-run

# 2. Generate for real
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=<email> --public

# 3. Verify expected counts (adjust to match spec)
# Expected: ~96 exercises (12 triads × 3 qualities + 12 × 3 7th types + 8 ROTO + interval exercises)

# 4. Spot-check in app
# Load /play?exercise=<first-triad-id> → should render correctly
# Load /play?exercise=<first-7th-chord-id> → should render correctly

# 5. Test overwrite
python manage.py generate_curriculum data/curriculum/theory1.yaml --author=<email> --overwrite
# Re-running should not create duplicates

# 6. Test MusicXML upload (once web UI is built)
# Upload a test MusicXML file → verify exercises created + playlist created

# 7. Test word question type
# Create a question exercise manually via admin, load it in the app — should show text + buttons, no canvas
```
