# Curriculum Generation System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a template-based curriculum generation system that reads a YAML spec and produces Exercise/Playlist/Course records in bulk, delivering a full semester Music Theory I curriculum (~400 exercises, ~25 playlists).

**Architecture:** Four pure-Python modules in `apps/exercises/generation/` (analysis_presets, voicing, templates, spec_loader) with one-way dependencies, driven by a Django management command. Only the command touches the database. Built in four phases: infrastructure → simple templates → partial validation → complex templates + complete curriculum.

**Tech Stack:** Python 3.12, Django 5.2, PyYAML, existing `Exercise`/`Playlist`/`Course`/`ExercisePlaylistOrdered`/`PlaylistCourseOrdered` models.

---

## File Map

**New files (generation modules):**
- `apps/exercises/generation/__init__.py` — empty package marker
- `apps/exercises/generation/analysis_presets.py` — expand shorthand analysis dicts to full Exercise JSON format
- `apps/exercises/generation/voicing.py` — MIDI arithmetic: place chord tones in correct registers
- `apps/exercises/generation/templates.py` — one function per template type; uses voicing.py + label map for identification exercises
- `apps/exercises/generation/spec_loader.py` — parse + validate YAML spec; expand key shorthands

**New files (command + data):**
- `apps/exercises/management/commands/generate_curriculum.py` — management command: drives everything, creates DB records
- `data/curriculum/theory1.yaml` — full semester spec (built in two stages: partial in Task 7, complete in Task 10)

**New test file:**
- `apps/exercises/tests/test_generation.py` — all unit tests for generation modules (no DB needed for most)
- `apps/exercises/tests/test_generate_curriculum_command.py` — integration tests for the management command (DB needed)

**No modifications to existing files.**

---

## Reference: Exercise Data JSON Shape

From `exercises_2026-04-03.csv`, every Exercise `.data` field looks like:

```json
{
  "type": "matching",
  "introText": "<p>...</p>",
  "reviewText": "",
  "staffDistribution": "keyboard",
  "key": "jC_",
  "keySignature": "",
  "analysis": {
    "tempo": false,
    "enabled": true,
    "mode": {
      "abbreviate_thoroughbass": false,
      "note_names": false,
      "fixed_do": false,
      "scientific_pitch": false,
      "pitch_class": false,
      "scale_degrees": false,
      "solfege": false,
      "do_based_solfege": false,
      "thoroughbass": false,
      "roman_numerals": false,
      "chord_labels": false,
      "intervals": false,
      "pci": false,
      "set_class_set": false,
      "set_class_normal": false,
      "set_class_prime": false,
      "set_class_forte": false
    }
  },
  "highlight": {
    "enabled": false,
    "mode": {
      "roothighlight": true,
      "tritonehighlight": true,
      "doublinghighlight": false,
      "modalmixturehighlight": false,
      "loweredhighlight": false,
      "solobass": false,
      "octaveshighlight": false
    }
  },
  "chord": [
    {"rhythmValue": "w", "visible": [48, 64, 67, 72], "hidden": []}
  ]
}
```

For `identification` type, each chord dict also has `"answer"` and `"choices"` keys.
For `figured_bass` type, `visible` contains only the bass note; `hidden` contains upper voices.
For `analytical` type, `visible` is empty; `hidden` contains all notes.

---

## Task 1: analysis_presets.py

**Files:**
- Create: `apps/exercises/generation/__init__.py`
- Create: `apps/exercises/generation/analysis_presets.py`
- Test: `apps/exercises/tests/test_generation.py`

- [ ] **Step 1: Create the package and write failing tests**

```python
# apps/exercises/tests/test_generation.py
from django.test import SimpleTestCase
from apps.exercises.generation.analysis_presets import expand_analysis, default_highlight


class ExpandAnalysisTests(SimpleTestCase):
    def test_empty_shorthand_returns_all_false_modes(self):
        result = expand_analysis({})
        self.assertTrue(result["enabled"])
        self.assertFalse(result["tempo"])
        self.assertFalse(result["mode"]["roman_numerals"])
        self.assertFalse(result["mode"]["thoroughbass"])

    def test_roman_numerals_true_sets_mode_key(self):
        result = expand_analysis({"roman_numerals": True})
        self.assertTrue(result["mode"]["roman_numerals"])
        self.assertFalse(result["mode"]["chord_labels"])

    def test_multiple_keys(self):
        result = expand_analysis({"roman_numerals": True, "chord_labels": True})
        self.assertTrue(result["mode"]["roman_numerals"])
        self.assertTrue(result["mode"]["chord_labels"])
        self.assertFalse(result["mode"]["intervals"])

    def test_all_known_mode_keys_present(self):
        result = expand_analysis({})
        expected_keys = {
            "abbreviate_thoroughbass", "note_names", "fixed_do", "scientific_pitch",
            "pitch_class", "scale_degrees", "solfege", "do_based_solfege",
            "thoroughbass", "roman_numerals", "chord_labels", "intervals",
            "pci", "set_class_set", "set_class_normal", "set_class_prime", "set_class_forte",
        }
        self.assertEqual(set(result["mode"].keys()), expected_keys)

    def test_unknown_key_is_ignored(self):
        result = expand_analysis({"nonexistent_key": True})
        self.assertNotIn("nonexistent_key", result["mode"])

    def test_default_highlight_structure(self):
        h = default_highlight()
        self.assertFalse(h["enabled"])
        self.assertIn("roothighlight", h["mode"])
        self.assertIn("tritonehighlight", h["mode"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.ExpandAnalysisTests -v 2
```
Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create package and implement analysis_presets.py**

```python
# apps/exercises/generation/__init__.py
# (empty)
```

```python
# apps/exercises/generation/analysis_presets.py

_FULL_MODE_DEFAULTS = {
    "abbreviate_thoroughbass": False,
    "note_names": False,
    "fixed_do": False,
    "scientific_pitch": False,
    "pitch_class": False,
    "scale_degrees": False,
    "solfege": False,
    "do_based_solfege": False,
    "thoroughbass": False,
    "roman_numerals": False,
    "chord_labels": False,
    "intervals": False,
    "pci": False,
    "set_class_set": False,
    "set_class_normal": False,
    "set_class_prime": False,
    "set_class_forte": False,
}

_DEFAULT_HIGHLIGHT = {
    "enabled": False,
    "mode": {
        "roothighlight": True,
        "tritonehighlight": True,
        "doublinghighlight": False,
        "modalmixturehighlight": False,
        "loweredhighlight": False,
        "solobass": False,
        "octaveshighlight": False,
    },
}


def expand_analysis(shorthand):
    """
    Expand a shorthand analysis dict to the full Exercise analysis object.

    shorthand: {"roman_numerals": True, "chord_labels": True}
    returns: {"enabled": True, "tempo": False, "mode": {all keys, most False}}
    """
    mode = dict(_FULL_MODE_DEFAULTS)
    for key, val in shorthand.items():
        if key in mode:
            mode[key] = val
    return {
        "enabled": True,
        "tempo": False,
        "mode": mode,
    }


def default_highlight():
    """Return the default highlight object (deep copy)."""
    return {
        "enabled": _DEFAULT_HIGHLIGHT["enabled"],
        "mode": dict(_DEFAULT_HIGHLIGHT["mode"]),
    }
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generation.ExpandAnalysisTests -v 2
```
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/__init__.py apps/exercises/generation/analysis_presets.py apps/exercises/tests/test_generation.py
git commit -m "feat: add analysis_presets module with expand_analysis and default_highlight"
```

---

## Task 2: spec_loader.py

**Files:**
- Create: `apps/exercises/generation/spec_loader.py`
- Test: `apps/exercises/tests/test_generation.py` (add to existing file)

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generation.py`:

```python
import os, tempfile, yaml
from apps.exercises.generation.spec_loader import load_spec, expand_keys, KEY_SHORTHANDS


class KeyShorthandTests(SimpleTestCase):
    def test_all_major_expands_to_12_keys(self):
        self.assertEqual(len(KEY_SHORTHANDS["all_major"]), 12)
        self.assertEqual(KEY_SHORTHANDS["all_major"][0], "jC_")
        self.assertEqual(KEY_SHORTHANDS["all_major"][1], "jG_")

    def test_common_major_expands_to_6_keys(self):
        self.assertEqual(KEY_SHORTHANDS["common_major"], ["jC_", "jG_", "jD_", "jF_", "jBb", "jEb"])

    def test_common_minor_expands_to_6_keys(self):
        self.assertEqual(KEY_SHORTHANDS["common_minor"], ["iA_", "iE_", "iD_", "iG_", "iC_", "iF_"])

    def test_expand_keys_string_shorthand(self):
        self.assertEqual(expand_keys("common_major"), ["jC_", "jG_", "jD_", "jF_", "jBb", "jEb"])

    def test_expand_keys_literal_list(self):
        self.assertEqual(expand_keys(["jC_", "jG_"]), ["jC_", "jG_"])

    def test_expand_keys_list_with_shorthand(self):
        result = expand_keys(["jC_", "common_major"])
        self.assertIn("jC_", result)
        self.assertIn("jG_", result)


class LoadSpecTests(SimpleTestCase):
    def _write_spec(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_load_spec_expands_key_shorthands(self):
        path = self._write_spec("""
meta:
  title: Test
  author: test@example.com
  public: false
playlists:
  - id: pl1
    title: Test Playlist
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: common_major
        voicing: close
        type: matching
""")
        spec = load_spec(path)
        os.unlink(path)
        keys = spec["playlists"][0]["exercises"][0]["keys"]
        self.assertEqual(keys, ["jC_", "jG_", "jD_", "jF_", "jBb", "jEb"])

    def test_load_spec_literal_keys_unchanged(self):
        path = self._write_spec("""
meta:
  title: Test
  author: test@example.com
  public: false
playlists:
  - id: pl1
    title: Test Playlist
    tags: []
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: [jC_, jG_]
        voicing: close
        type: matching
""")
        spec = load_spec(path)
        os.unlink(path)
        keys = spec["playlists"][0]["exercises"][0]["keys"]
        self.assertEqual(keys, ["jC_", "jG_"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.KeyShorthandTests apps.exercises.tests.test_generation.LoadSpecTests -v 2
```
Expected: `ImportError`

- [ ] **Step 3: Implement spec_loader.py**

```python
# apps/exercises/generation/spec_loader.py
import yaml

KEY_SHORTHANDS = {
    "all_major": [
        "jC_", "jG_", "jD_", "jA_", "jE_", "jB_",
        "jF#", "jDb", "jAb", "jEb", "jBb", "jF_",
    ],
    "all_minor": [
        "iA_", "iE_", "iB_", "iF#", "iC#", "iG#",
        "iD_", "iG_", "iC_", "iF_", "iBb", "iEb",
    ],
    "all_12": [
        "jC_", "jC#", "jD_", "jEb", "jE_", "jF_",
        "jF#", "jG_", "jAb", "jA_", "jBb", "jB_",
    ],
    "common_major": ["jC_", "jG_", "jD_", "jF_", "jBb", "jEb"],
    "common_minor": ["iA_", "iE_", "iD_", "iG_", "iC_", "iF_"],
}


def expand_keys(keys):
    """
    Expand a keys value (string shorthand or list) to a concrete list of key strings.

    expand_keys("common_major")     -> ["jC_", "jG_", ...]
    expand_keys(["jC_", "jG_"])     -> ["jC_", "jG_"]
    expand_keys(["jC_", "common_major"]) -> ["jC_", "jC_", "jG_", ...]
    """
    if isinstance(keys, str):
        return list(KEY_SHORTHANDS.get(keys, [keys]))
    result = []
    for k in keys:
        if k in KEY_SHORTHANDS:
            result.extend(KEY_SHORTHANDS[k])
        else:
            result.append(k)
    return result


def load_spec(path):
    """
    Load and validate a curriculum YAML spec file.
    Expands all key shorthands in exercise entries.
    Returns the parsed spec dict.
    """
    with open(path) as f:
        spec = yaml.safe_load(f)
    _expand_spec_keys(spec)
    return spec


def _expand_spec_keys(spec):
    for playlist in spec.get("playlists", []):
        for entry in playlist.get("exercises", []):
            if "keys" in entry:
                entry["keys"] = expand_keys(entry["keys"])
```

- [ ] **Step 4: Install PyYAML if needed, then run tests**

```bash
pip show pyyaml || pip install pyyaml
python manage.py test apps.exercises.tests.test_generation.KeyShorthandTests apps.exercises.tests.test_generation.LoadSpecTests -v 2
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/spec_loader.py apps/exercises/tests/test_generation.py
git commit -m "feat: add spec_loader with key shorthand expansion"
```

---

## Task 3: voicing.py

**Files:**
- Create: `apps/exercises/generation/voicing.py`
- Test: `apps/exercises/tests/test_generation.py` (add)

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generation.py`:

```python
from apps.exercises.generation.voicing import close, keyboard_4voice, close_4voice, open_voicing


class ClosingVoicingTests(SimpleTestCase):
    def test_c_major_root_position(self):
        # C=0, intervals=[0,4,7], root near MIDI 60
        self.assertEqual(close(0, [0, 4, 7]), [60, 64, 67])

    def test_g_major_root_position(self):
        # G=7
        self.assertEqual(close(7, [0, 4, 7]), [67, 71, 74])

    def test_c_major_first_inversion(self):
        # Bass note is E4=64, then G4, C5
        self.assertEqual(close(0, [0, 4, 7], inversion=1), [64, 67, 72])

    def test_c_major_second_inversion(self):
        # Bass note is G4=67, then C5, E5
        self.assertEqual(close(0, [0, 4, 7], inversion=2), [67, 72, 76])

    def test_dominant_seventh_c(self):
        # C dominant 7: C4, E4, G4, Bb4
        self.assertEqual(close(0, [0, 4, 7, 10]), [60, 64, 67, 70])

    def test_notes_are_sorted_ascending(self):
        notes = close(0, [0, 4, 7])
        self.assertEqual(notes, sorted(notes))


class KeyboardFourVoiceTests(SimpleTestCase):
    def test_c_major_matches_csv_convention(self):
        # CSV shows C major as [48, 64, 67, 72] = C3, E4, G4, C5
        self.assertEqual(keyboard_4voice(0, [0, 4, 7]), [48, 64, 67, 72])

    def test_c_dominant_seventh(self):
        # C dominant 7: bass C3=48, E4=64, G4=67, Bb4=70
        self.assertEqual(keyboard_4voice(0, [0, 4, 7, 10]), [48, 64, 67, 70])

    def test_g_major(self):
        # G bass near 45-57: G3=55, treble B4=71, D5=74, G5=79
        result = keyboard_4voice(7, [0, 4, 7])
        self.assertEqual(result[0], 55)   # G3 in bass
        self.assertEqual(len(result), 4)

    def test_four_notes_returned_for_triad(self):
        self.assertEqual(len(keyboard_4voice(0, [0, 4, 7])), 4)

    def test_four_notes_returned_for_seventh_chord(self):
        self.assertEqual(len(keyboard_4voice(0, [0, 4, 7, 10])), 4)

    def test_notes_are_sorted_ascending(self):
        notes = keyboard_4voice(0, [0, 4, 7])
        self.assertEqual(notes, sorted(notes))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.ClosingVoicingTests apps.exercises.tests.test_generation.KeyboardFourVoiceTests -v 2
```
Expected: `ImportError`

- [ ] **Step 3: Implement voicing.py**

```python
# apps/exercises/generation/voicing.py


def _pitch_in_range(pitch_class, midi_low, midi_high):
    """
    Return the lowest MIDI note >= midi_low whose pitch class equals pitch_class (0–11).
    Raises ValueError if none exists within [midi_low, midi_high].

    pitch_class: 0=C, 1=C#/Db, 2=D, ..., 11=B
    """
    offset = (pitch_class - midi_low % 12) % 12
    candidate = midi_low + offset
    if candidate > midi_high:
        raise ValueError(
            f"Pitch class {pitch_class} cannot be placed in [{midi_low}, {midi_high}]"
        )
    return candidate


def close(root_pc, intervals, inversion=0):
    """
    Stack all notes close together, lowest note near MIDI 60 (C4).
    Used for matching exercises where all notes are visible.

    root_pc: pitch class of the root (0=C, 7=G, etc.)
    intervals: list of semitone intervals from root, e.g. [0, 4, 7] for major triad
    inversion: 0=root pos, 1=first inv, 2=second inv

    Returns sorted list of MIDI notes.

    Examples:
        close(0, [0, 4, 7])             -> [60, 64, 67]   # C major
        close(7, [0, 4, 7])             -> [67, 71, 74]   # G major
        close(0, [0, 4, 7], inversion=1)-> [64, 67, 72]   # C/E
        close(0, [0, 4, 7, 10])         -> [60, 64, 67, 70] # C7
    """
    rotated = intervals[inversion:] + intervals[:inversion]
    bass_pc = (root_pc + rotated[0]) % 12
    bass = _pitch_in_range(bass_pc, 60, 71)
    notes = [bass]
    for i in range(1, len(rotated)):
        prev = notes[-1]
        pc = (root_pc + rotated[i]) % 12
        note = _pitch_in_range(pc, prev + 1, prev + 12)
        notes.append(note)
    return notes


def keyboard_4voice(root_pc, intervals):
    """
    Keyboard 4-voice layout: root in bass clef (~MIDI 45–57), upper voices in treble.

    For triads (3-interval list): places 3rd, 5th, doubled-root in treble (~MIDI 60–76).
    For seventh chords (4-interval list): places 3rd, 5th, 7th in treble (no doubling).

    Examples:
        keyboard_4voice(0, [0, 4, 7])       -> [48, 64, 67, 72]  # C major (matches CSV)
        keyboard_4voice(0, [0, 4, 7, 10])   -> [48, 64, 67, 70]  # C dominant 7
    """
    bass = _pitch_in_range(root_pc, 45, 57)
    upper = []
    prev = 59
    for interval in intervals[1:]:
        pc = (root_pc + interval) % 12
        note = _pitch_in_range(pc, prev + 1, prev + 12)
        upper.append(note)
        prev = note
    if len(intervals) == 3:
        # Double the root in soprano
        root_soprano = _pitch_in_range(root_pc, prev + 1, prev + 12)
        upper.append(root_soprano)
    return [bass] + upper


def close_4voice(root_pc, intervals):
    """
    All four voices in treble range (~MIDI 60–84), close position.
    Used when all voices should appear on treble staff without a separate bass.

    Examples:
        close_4voice(0, [0, 4, 7]) -> [60, 64, 67, 72]  # C major with doubled root
    """
    bass = _pitch_in_range(root_pc, 60, 71)
    upper = []
    prev = bass
    for interval in intervals[1:]:
        pc = (root_pc + interval) % 12
        note = _pitch_in_range(pc, prev + 1, prev + 12)
        upper.append(note)
        prev = note
    if len(intervals) == 3:
        root_top = _pitch_in_range(root_pc, prev + 1, prev + 12)
        upper.append(root_top)
    return [bass] + upper


def open_voicing(root_pc, intervals):
    """
    Open voicing: root in bass (~MIDI 45–57), 5th above, 3rd above that.
    Notes spread across roughly two octaves.

    Example:
        open_voicing(0, [0, 4, 7]) -> [48, 67, 76]  # C3, G4, E5
    """
    bass = _pitch_in_range(root_pc, 45, 57)
    if len(intervals) < 3:
        return close(root_pc, intervals)
    fifth_pc = (root_pc + intervals[2]) % 12
    third_pc = (root_pc + intervals[1]) % 12
    fifth = _pitch_in_range(fifth_pc, bass + 12, bass + 24)
    third = _pitch_in_range(third_pc, fifth + 1, fifth + 12)
    return [bass, fifth, third]


# Named strategy lookup so YAML can reference strategies by string
STRATEGIES = {
    "close": close,
    "open": open_voicing,
    "close_4voice": close_4voice,
    "keyboard_4voice": keyboard_4voice,
}
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generation.ClosingVoicingTests apps.exercises.tests.test_generation.KeyboardFourVoiceTests -v 2
```
Expected: all tests PASS. If `keyboard_4voice(0, [0,4,7])` does not return `[48, 64, 67, 72]`, trace `_pitch_in_range` for each note and adjust the bass range constant (`45, 57`) until the CSV value is matched.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/voicing.py apps/exercises/tests/test_generation.py
git commit -m "feat: add voicing module with close, keyboard_4voice, close_4voice, open_voicing strategies"
```

---

## Task 4: templates.py — triad and seventh_chord

**Files:**
- Create: `apps/exercises/generation/templates.py`
- Test: `apps/exercises/tests/test_generation.py` (add)

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generation.py`:

```python
from apps.exercises.generation.templates import triad, seventh_chord, build_chord_dict


class BuildChordDictTests(SimpleTestCase):
    def test_matching_all_visible(self):
        chord = build_chord_dict([60, 64, 67], "matching")
        self.assertEqual(chord["visible"], [60, 64, 67])
        self.assertEqual(chord["hidden"], [])

    def test_analytical_all_hidden(self):
        chord = build_chord_dict([60, 64, 67], "analytical")
        self.assertEqual(chord["visible"], [])
        self.assertEqual(chord["hidden"], [60, 64, 67])

    def test_figured_bass_bass_visible(self):
        chord = build_chord_dict([48, 64, 67, 72], "figured_bass")
        self.assertEqual(chord["visible"], [48])
        self.assertEqual(chord["hidden"], [64, 67, 72])

    def test_identification_all_visible_no_hidden(self):
        chord = build_chord_dict([60, 64, 67], "identification")
        self.assertEqual(chord["visible"], [60, 64, 67])
        self.assertEqual(chord["hidden"], [])
        # answer and choices added separately by template


class TriadTemplateTests(SimpleTestCase):
    def test_c_major_matching_close_returns_one_chord(self):
        chords = triad("jC_", "major", 0, "close", "matching")
        self.assertEqual(len(chords), 1)
        self.assertEqual(chords[0]["visible"], [60, 64, 67])
        self.assertEqual(chords[0]["hidden"], [])

    def test_c_major_keyboard_4voice_matches_csv(self):
        chords = triad("jC_", "major", 0, "keyboard_4voice", "matching")
        self.assertEqual(chords[0]["visible"], [48, 64, 67, 72])

    def test_identification_quality_has_answer_and_choices(self):
        chords = triad("jC_", "major", 0, "close", "identification",
                       identification_label="quality")
        self.assertEqual(chords[0]["answer"], "major")
        self.assertIn("major", chords[0]["choices"])
        self.assertIn("minor", chords[0]["choices"])
        self.assertIn("diminished", chords[0]["choices"])
        self.assertIn("augmented", chords[0]["choices"])

    def test_identification_inversion_has_answer_and_choices(self):
        chords = triad("jC_", "major", 1, "close", "identification",
                       identification_label="inversion")
        self.assertEqual(chords[0]["answer"], "first inversion")
        self.assertIn("root position", chords[0]["choices"])
        self.assertIn("first inversion", chords[0]["choices"])
        self.assertIn("second inversion", chords[0]["choices"])

    def test_minor_triad(self):
        chords = triad("jA_", "minor", 0, "close", "matching")
        # A minor: A4=69, C5=72, E5=76
        self.assertEqual(chords[0]["visible"], [69, 72, 76])

    def test_diminished_triad(self):
        chords = triad("jB_", "diminished", 0, "close", "matching")
        # B dim: B4=71, D5=74, F5=77
        self.assertEqual(chords[0]["visible"], [71, 74, 77])


class SeventhChordTemplateTests(SimpleTestCase):
    def test_c_dominant_seventh_keyboard_4voice(self):
        chords = seventh_chord("jC_", "dominant", 0, "keyboard_4voice", "matching")
        self.assertEqual(chords[0]["visible"], [48, 64, 67, 70])

    def test_identification_quality_dominant(self):
        chords = seventh_chord("jC_", "dominant", 0, "close", "identification",
                               identification_label="quality")
        self.assertEqual(chords[0]["answer"], "dominant 7")
        self.assertIn("major 7", chords[0]["choices"])
        self.assertIn("half-dim 7", chords[0]["choices"])

    def test_identification_inversion_root_position(self):
        chords = seventh_chord("jC_", "dominant", 0, "close", "identification",
                               identification_label="inversion")
        self.assertEqual(chords[0]["answer"], "root position")

    def test_identification_inversion_65(self):
        chords = seventh_chord("jC_", "dominant", 1, "close", "identification",
                               identification_label="inversion")
        self.assertEqual(chords[0]["answer"], "6/5")

    def test_figured_bass_bass_only_visible(self):
        chords = seventh_chord("jC_", "dominant", 0, "keyboard_4voice", "figured_bass")
        self.assertEqual(chords[0]["visible"], [48])
        self.assertEqual(len(chords[0]["hidden"]), 3)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.BuildChordDictTests apps.exercises.tests.test_generation.TriadTemplateTests apps.exercises.tests.test_generation.SeventhChordTemplateTests -v 2
```
Expected: `ImportError`

- [ ] **Step 3: Implement templates.py with triad, seventh_chord, build_chord_dict, and label map**

```python
# apps/exercises/generation/templates.py
from apps.exercises.generation.voicing import STRATEGIES

# ---------------------------------------------------------------------------
# Pitch class lookup: HarmonyLab key string -> pitch class (0=C … 11=B)
# ---------------------------------------------------------------------------
KEY_TO_PC = {
    "jC_": 0,  "jG_": 7,  "jD_": 2,  "jA_": 9,  "jE_": 4,  "jB_": 11,
    "jF#": 6,  "jDb": 1,  "jAb": 8,  "jEb": 3,  "jBb": 10, "jF_": 5,
    "iA_": 9,  "iE_": 4,  "iB_": 11, "iF#": 6,  "iC#": 1,  "iG#": 8,
    "iD_": 2,  "iG_": 7,  "iC_": 0,  "iF_": 5,  "iBb": 10, "iEb": 3,
}

# ---------------------------------------------------------------------------
# Semitone intervals from root for each quality
# ---------------------------------------------------------------------------
QUALITY_INTERVALS = {
    # Triads
    "major":      [0, 4, 7],
    "minor":      [0, 3, 7],
    "diminished": [0, 3, 6],
    "augmented":  [0, 4, 8],
    # Seventh chords
    "dominant":   [0, 4, 7, 10],
    "major7":     [0, 4, 7, 11],
    "minor7":     [0, 3, 7, 10],
    "half_dim":   [0, 3, 6, 10],
    "dim7":       [0, 3, 6, 9],
}

# ---------------------------------------------------------------------------
# Label map: defines choices and answer derivation for identification exercises
# ---------------------------------------------------------------------------
_TRIAD_INVERSION_LABELS = ["root position", "first inversion", "second inversion"]
_SEVENTH_INVERSION_LABELS = ["root position", "6/5", "4/3", "4/2"]

_QUALITY_TO_DISPLAY = {
    "dominant": "dominant 7",
    "major7":   "major 7",
    "minor7":   "minor 7",
    "half_dim": "half-dim 7",
    "dim7":     "diminished 7",
}

LABEL_MAP = {
    "triad": {
        "quality": {
            "choices": lambda key: ["major", "minor", "diminished", "augmented"],
            "answer":  lambda quality, inversion, key: quality,
        },
        "inversion": {
            "choices": lambda key: _TRIAD_INVERSION_LABELS,
            "answer":  lambda quality, inversion, key: _TRIAD_INVERSION_LABELS[inversion],
        },
    },
    "seventh_chord": {
        "quality": {
            "choices": lambda key: ["dominant 7", "major 7", "minor 7", "half-dim 7", "diminished 7"],
            "answer":  lambda quality, inversion, key: _QUALITY_TO_DISPLAY[quality],
        },
        "inversion": {
            "choices": lambda key: _SEVENTH_INVERSION_LABELS,
            "answer":  lambda quality, inversion, key: _SEVENTH_INVERSION_LABELS[inversion],
        },
    },
    "interval": {
        "name": {
            "choices": lambda key: ["m2", "M2", "m3", "M3", "P4", "TT", "P5",
                                    "m6", "M6", "m7", "M7", "P8"],
            "answer":  lambda quality, inversion, key: quality,  # quality IS the interval name
        },
    },
    "figured_bass": {
        "symbol": {
            "choices": lambda key: ["5/3", "6", "6/4", "7", "6/5", "4/3", "4/2"],
            "answer":  lambda quality, inversion, key: {
                0: "5/3", 1: "6", 2: "6/4",  # triads
            }.get(inversion, "5/3"),
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_chord_dict(notes, exercise_type):
    """
    Build the chord dict for Exercise.data["chord"] based on exercise type.

    notes: sorted list of MIDI note numbers
    exercise_type: "matching" | "analytical" | "figured_bass" | "identification"
    """
    sorted_notes = sorted(notes)
    if exercise_type in ("matching",):
        return {"visible": sorted_notes, "hidden": []}
    elif exercise_type in ("analytical", "analytical_pcs"):
        return {"visible": [], "hidden": sorted_notes}
    elif exercise_type in ("figured_bass", "figured_bass_pcs"):
        return {"visible": [sorted_notes[0]], "hidden": sorted_notes[1:]}
    elif exercise_type == "identification":
        return {"visible": sorted_notes, "hidden": []}
    return {"visible": sorted_notes, "hidden": []}


def _apply_label(chord, template_name, identification_label, quality, inversion, key):
    """Add answer and choices to an identification chord dict in place."""
    entry = LABEL_MAP.get(template_name, {}).get(identification_label)
    if entry is None:
        raise ValueError(
            f"No label map entry for template={template_name!r}, "
            f"identification_label={identification_label!r}"
        )
    chord["answer"] = entry["answer"](quality, inversion, key)
    chord["choices"] = list(entry["choices"](key))


# ---------------------------------------------------------------------------
# Template functions
# ---------------------------------------------------------------------------

def triad(key, quality, inversion, voicing_name, exercise_type, identification_label=None):
    """
    Generate one chord dict for a triad exercise.

    key: HarmonyLab key string e.g. "jC_"
    quality: "major" | "minor" | "diminished" | "augmented"
    inversion: 0 | 1 | 2
    voicing_name: "close" | "keyboard_4voice" | "close_4voice" | "open"
    exercise_type: "matching" | "analytical" | "figured_bass" | "identification"
    identification_label: required when exercise_type="identification"

    Returns: list with one chord dict (wrapped in list for consistency with multi-chord templates)
    """
    root_pc = KEY_TO_PC[key]
    intervals = QUALITY_INTERVALS[quality]
    strategy = STRATEGIES[voicing_name]
    notes = strategy(root_pc, intervals, inversion=inversion)
    chord = build_chord_dict(notes, exercise_type)
    if exercise_type == "identification":
        _apply_label(chord, "triad", identification_label, quality, inversion, key)
    return [chord]


def seventh_chord(key, quality, inversion, voicing_name, exercise_type,
                  identification_label=None):
    """
    Generate one chord dict for a seventh chord exercise.

    quality: "dominant" | "major7" | "minor7" | "half_dim" | "dim7"
    inversion: 0 | 1 | 2 | 3
    """
    root_pc = KEY_TO_PC[key]
    intervals = QUALITY_INTERVALS[quality]
    strategy = STRATEGIES[voicing_name]
    # keyboard_4voice accepts inversion=0 only; for inversions use close
    if voicing_name == "keyboard_4voice" and inversion > 0:
        from apps.exercises.generation.voicing import close as close_fn
        notes = close_fn(root_pc, intervals, inversion=inversion)
    else:
        notes = strategy(root_pc, intervals, inversion=inversion)
    chord = build_chord_dict(notes, exercise_type)
    if exercise_type == "identification":
        _apply_label(chord, "seventh_chord", identification_label, quality, inversion, key)
    return [chord]
```

Note: `close` and `keyboard_4voice` take an `inversion` parameter but only `close` uses it. Update `voicing.py` to accept (and silently ignore) `inversion` in `keyboard_4voice`:

```python
# In voicing.py, update keyboard_4voice signature:
def keyboard_4voice(root_pc, intervals, inversion=0):
    # inversion ignored for keyboard_4voice — always root position bass
    ...
```

Also update `close_4voice` and `open_voicing` to accept `inversion=0` for API consistency:
```python
def close_4voice(root_pc, intervals, inversion=0):
    ...

def open_voicing(root_pc, intervals, inversion=0):
    ...
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generation.BuildChordDictTests apps.exercises.tests.test_generation.TriadTemplateTests apps.exercises.tests.test_generation.SeventhChordTemplateTests -v 2
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/templates.py apps/exercises/generation/voicing.py apps/exercises/tests/test_generation.py
git commit -m "feat: add templates module with triad, seventh_chord, build_chord_dict, and label map"
```

---

## Task 5: templates.py — interval and diatonic_intervals

**Files:**
- Modify: `apps/exercises/generation/templates.py`
- Test: `apps/exercises/tests/test_generation.py` (add)

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generation.py`:

```python
from apps.exercises.generation.templates import interval, diatonic_intervals

# Semitone counts for interval names
_INTERVAL_SEMITONES = {
    "m2": 1, "M2": 2, "m3": 3, "M3": 4, "P4": 5, "TT": 6,
    "P5": 7, "m6": 8, "M6": 9, "m7": 10, "M7": 11, "P8": 12,
}


class IntervalTemplateTests(SimpleTestCase):
    def test_perfect_fifth_above_c(self):
        # P5 above C4(60) = G4(67)
        chords = interval("jC_", "P5", "matching")
        notes = chords[0]["visible"]
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[1] - notes[0], 7)

    def test_major_third_above_c(self):
        # M3 above C4(60) = E4(64)
        chords = interval("jC_", "M3", "matching")
        notes = chords[0]["visible"]
        self.assertEqual(notes[1] - notes[0], 4)

    def test_identification_has_answer_and_choices(self):
        chords = interval("jC_", "M3", "identification", identification_label="name")
        self.assertEqual(chords[0]["answer"], "M3")
        self.assertIn("m3", chords[0]["choices"])
        self.assertIn("P5", chords[0]["choices"])

    def test_bottom_note_near_c4(self):
        chords = interval("jC_", "P5", "matching")
        bottom = chords[0]["visible"][0]
        self.assertGreaterEqual(bottom, 60)
        self.assertLessEqual(bottom, 72)


class DiatonicIntervalsTests(SimpleTestCase):
    def test_c_major_returns_7_intervals(self):
        # diatonic intervals from scale degree 1 to all others: 7 chords (2nd–8ve)
        chords = diatonic_intervals("jC_", "major", "matching")
        self.assertEqual(len(chords), 7)

    def test_all_chords_have_two_visible_notes(self):
        chords = diatonic_intervals("jC_", "major", "matching")
        for chord in chords:
            self.assertEqual(len(chord["visible"]), 2)

    def test_first_interval_is_m2_or_M2(self):
        chords = diatonic_intervals("jC_", "major", "matching")
        semitones = chords[0]["visible"][1] - chords[0]["visible"][0]
        self.assertIn(semitones, [1, 2])  # minor or major second

    def test_last_interval_is_octave(self):
        chords = diatonic_intervals("jC_", "major", "matching")
        semitones = chords[-1]["visible"][1] - chords[-1]["visible"][0]
        self.assertEqual(semitones, 12)

    def test_identification_has_answer_on_each_chord(self):
        chords = diatonic_intervals("jC_", "major", "identification",
                                    identification_label="name")
        for chord in chords:
            self.assertIn("answer", chord)
            self.assertIn("choices", chord)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.IntervalTemplateTests apps.exercises.tests.test_generation.DiatonicIntervalsTests -v 2
```
Expected: `ImportError`

- [ ] **Step 3: Add interval and diatonic_intervals to templates.py**

Add to the bottom of `apps/exercises/generation/templates.py`:

```python
# ---------------------------------------------------------------------------
# Interval semitone lookup
# ---------------------------------------------------------------------------
INTERVAL_SEMITONES = {
    "m2": 1, "M2": 2, "m3": 3, "M3": 4, "P4": 5, "TT": 6,
    "P5": 7, "m6": 8, "M6": 9, "m7": 10, "M7": 11, "P8": 12,
}

# Diatonic scale step semitones (major scale: W W H W W W H)
_MAJOR_STEPS = [2, 2, 1, 2, 2, 2, 1]
_MINOR_STEPS = [2, 1, 2, 2, 1, 2, 2]  # natural minor


def _interval_name_from_semitones(semitones):
    """Return interval name string for a given number of semitones (1-12)."""
    reverse = {v: k for k, v in INTERVAL_SEMITONES.items()}
    return reverse.get(semitones, str(semitones))


def interval(key, interval_name, exercise_type, identification_label=None):
    """
    Generate one chord dict for a harmonic interval exercise.
    Bottom note is the root of the key near MIDI 60.

    key: HarmonyLab key string
    interval_name: "m2" | "M2" | "m3" | "M3" | "P4" | "TT" | "P5" |
                   "m6" | "M6" | "m7" | "M7" | "P8"
    """
    from apps.exercises.generation.voicing import _pitch_in_range
    root_pc = KEY_TO_PC[key]
    bottom = _pitch_in_range(root_pc, 60, 71)
    semitones = INTERVAL_SEMITONES[interval_name]
    top = bottom + semitones
    chord = build_chord_dict([bottom, top], exercise_type)
    if exercise_type == "identification":
        _apply_label(chord, "interval", identification_label, interval_name, 0, key)
    return [chord]


def diatonic_intervals(key, scale, exercise_type, identification_label=None):
    """
    Generate 7 interval chords: diatonic intervals from tonic to each scale degree 2–8.

    key: HarmonyLab key string
    scale: "major" | "minor"
    Returns: list of 7 chord dicts
    """
    from apps.exercises.generation.voicing import _pitch_in_range
    root_pc = KEY_TO_PC[key]
    bottom = _pitch_in_range(root_pc, 60, 71)
    steps = _MAJOR_STEPS if scale == "major" else _MINOR_STEPS
    chords = []
    cumulative = 0
    for step in steps:
        cumulative += step
        top = bottom + cumulative
        name = _interval_name_from_semitones(cumulative)
        chord = build_chord_dict([bottom, top], exercise_type)
        if exercise_type == "identification":
            _apply_label(chord, "interval", identification_label, name, 0, key)
        chords.append(chord)
    return chords
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generation.IntervalTemplateTests apps.exercises.tests.test_generation.DiatonicIntervalsTests -v 2
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/templates.py apps/exercises/tests/test_generation.py
git commit -m "feat: add interval and diatonic_intervals templates"
```

---

## Task 6: generate_curriculum.py — management command

**Files:**
- Create: `apps/exercises/management/commands/generate_curriculum.py`
- Create: `apps/exercises/tests/test_generate_curriculum_command.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/exercises/tests/test_generate_curriculum_command.py
import os
import tempfile
import yaml
from django.contrib.auth import get_user_model
from django.test import TestCase
from io import StringIO
from django.core.management import call_command

from apps.exercises.models import Exercise, Playlist, Course, ExercisePlaylistOrdered

User = get_user_model()

MINIMAL_SPEC = {
    "meta": {"title": "Test Course", "author": None, "public": False},
    "course": {"title": "Test Course", "playlists": [{"ref": "pl_triads"}]},
    "playlists": [
        {
            "id": "pl_triads",
            "title": "Major Triads",
            "tags": ["triads"],
            "exercises": [
                {
                    "template": "triad",
                    "quality": "major",
                    "inversion": 0,
                    "keys": ["jC_", "jG_"],
                    "voicing": "keyboard_4voice",
                    "type": "matching",
                    "analysis": {"roman_numerals": True},
                    "rhythm": "w",
                    "staffDistribution": "keyboard",
                }
            ],
        }
    ],
}


def _write_spec(spec_dict, author_email):
    spec_dict["meta"]["author"] = author_email
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, dir="/tmp"
    )
    yaml.dump(spec_dict, f)
    f.close()
    return f.name


class GenerateCurriculumCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="pass"
        )

    def test_dry_run_creates_no_records(self):
        path = _write_spec(dict(MINIMAL_SPEC), self.user.email)
        before_ex = Exercise.objects.count()
        before_pl = Playlist.objects.count()
        call_command("generate_curriculum", path, "--dry-run", stdout=StringIO())
        os.unlink(path)
        self.assertEqual(Exercise.objects.count(), before_ex)
        self.assertEqual(Playlist.objects.count(), before_pl)

    def test_creates_expected_number_of_exercises(self):
        # 2 keys × 1 template entry = 2 exercises
        path = _write_spec(dict(MINIMAL_SPEC), self.user.email)
        call_command("generate_curriculum", path, stdout=StringIO())
        os.unlink(path)
        self.assertEqual(
            Exercise.objects.filter(authored_by=self.user).count(), 2
        )

    def test_creates_playlist_with_correct_name(self):
        path = _write_spec(dict(MINIMAL_SPEC), self.user.email)
        call_command("generate_curriculum", path, stdout=StringIO())
        os.unlink(path)
        pl = Playlist.objects.get(name="Major Triads", authored_by=self.user)
        self.assertIsNotNone(pl)

    def test_exercises_added_to_playlist_in_order(self):
        path = _write_spec(dict(MINIMAL_SPEC), self.user.email)
        call_command("generate_curriculum", path, stdout=StringIO())
        os.unlink(path)
        pl = Playlist.objects.get(name="Major Triads", authored_by=self.user)
        epos = ExercisePlaylistOrdered.objects.filter(playlist=pl).order_by("order")
        self.assertEqual(epos.count(), 2)

    def test_creates_course(self):
        path = _write_spec(dict(MINIMAL_SPEC), self.user.email)
        call_command("generate_curriculum", path, stdout=StringIO())
        os.unlink(path)
        course = Course.objects.get(title="Test Course", authored_by=self.user)
        self.assertIsNotNone(course)

    def test_overwrite_replaces_existing_exercises(self):
        path = _write_spec(dict(MINIMAL_SPEC), self.user.email)
        call_command("generate_curriculum", path, stdout=StringIO())
        count_after_first = Exercise.objects.filter(authored_by=self.user).count()
        call_command("generate_curriculum", path, "--overwrite", stdout=StringIO())
        os.unlink(path)
        self.assertEqual(
            Exercise.objects.filter(authored_by=self.user).count(), count_after_first
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generate_curriculum_command -v 2
```
Expected: `CommandError` or `SystemExit` (command not found)

- [ ] **Step 3: Implement generate_curriculum.py**

```python
# apps/exercises/management/commands/generate_curriculum.py
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.exercises.generation.spec_loader import load_spec
from apps.exercises.generation.analysis_presets import expand_analysis, default_highlight
from apps.exercises.generation import templates as tmpl
from apps.exercises.models import (
    Exercise, Playlist, Course,
    ExercisePlaylistOrdered, PlaylistCourseOrdered,
)

User = get_user_model()

# Maps template name strings to functions in templates.py
TEMPLATE_FN = {
    "triad":              tmpl.triad,
    "seventh_chord":      tmpl.seventh_chord,
    "interval":           tmpl.interval,
    "diatonic_intervals": tmpl.diatonic_intervals,
    # scale, diatonic_triads, diatonic_sevenths, roto, progression added in Task 8–9
}


class Command(BaseCommand):
    help = "Generate Exercise/Playlist/Course records from a curriculum YAML spec"

    def add_arguments(self, parser):
        parser.add_argument("spec_file", type=str)
        parser.add_argument("--dry-run", action="store_true",
                            help="Print what would be created without writing to DB")
        parser.add_argument("--overwrite", action="store_true",
                            help="Delete and recreate exercises with same description+author")

    def handle(self, *args, **options):
        spec_file = options["spec_file"]
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]

        if not os.path.exists(spec_file):
            raise CommandError(f"Spec file not found: {spec_file}")

        spec = load_spec(spec_file)
        meta = spec.get("meta", {})
        author_email = meta.get("author")
        if not author_email:
            raise CommandError("spec meta.author is required")

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User "{author_email}" not found')

        is_public = meta.get("public", False)
        playlist_objects = {}   # id -> Playlist instance
        total_exercises = 0

        # ── Build playlists and exercises ──────────────────────────────────
        for pl_spec in spec.get("playlists", []):
            pl_id = pl_spec["id"]
            pl_title = pl_spec["title"]
            tags = pl_spec.get("tags", [])

            if dry_run:
                self.stdout.write(f"[dry-run] Would create playlist: {pl_title!r}")
            else:
                if overwrite:
                    Playlist.objects.filter(name=pl_title, authored_by=author).delete()
                playlist_obj = Playlist(name=pl_title, authored_by=author,
                                        is_public=is_public, tags=tags)
                playlist_obj.save()
                playlist_objects[pl_id] = playlist_obj

            exercise_order = 0
            for entry in pl_spec.get("exercises", []):
                template_name = entry["template"]
                fn = TEMPLATE_FN.get(template_name)
                if fn is None:
                    raise CommandError(f"Unknown template: {template_name!r}")

                keys = entry.get("keys", [])
                exercise_type = entry["type"]
                voicing_name = entry.get("voicing", "close")
                quality = entry.get("quality")
                inversion = entry.get("inversion", 0)
                scale = entry.get("scale", "major")
                identification_label = entry.get("identification_label")
                rhythm = entry.get("rhythm", "w")
                staff_distribution = entry.get("staffDistribution", "keyboard")
                analysis = expand_analysis(entry.get("analysis", {}))
                highlight = default_highlight()

                for key in keys:
                    # Build chord list via template function
                    if template_name in ("triad", "seventh_chord"):
                        chords = fn(key, quality, inversion, voicing_name,
                                    exercise_type,
                                    identification_label=identification_label)
                    elif template_name == "interval":
                        chords = fn(key, quality, exercise_type,
                                    identification_label=identification_label)
                    elif template_name == "diatonic_intervals":
                        chords = fn(key, scale, exercise_type,
                                    identification_label=identification_label)
                    else:
                        chords = fn(key, entry, exercise_type)

                    description = _build_description(template_name, entry, key)
                    data = {
                        "type": exercise_type,
                        "introText": entry.get("introText", ""),
                        "reviewText": entry.get("reviewText", ""),
                        "staffDistribution": staff_distribution,
                        "key": key,
                        "keySignature": "",
                        "analysis": analysis,
                        "highlight": highlight,
                        "chord": chords,
                    }

                    if dry_run:
                        self.stdout.write(
                            f"  [dry-run] Would create exercise: {description!r} "
                            f"({len(chords)} chords)"
                        )
                    else:
                        if overwrite:
                            Exercise.objects.filter(
                                description=description, authored_by=author
                            ).delete()
                        ex = Exercise(
                            description=description,
                            data=data,
                            rhythm=rhythm,
                            authored_by=author,
                            is_public=is_public,
                            tags=tags,
                        )
                        ex.save()
                        ExercisePlaylistOrdered(
                            exercise=ex,
                            playlist=playlist_objects[pl_id],
                            order=exercise_order,
                        ).save()
                        exercise_order += 1
                        total_exercises += 1

            if not dry_run:
                self.stdout.write(
                    f"Created {exercise_order} exercises for {pl_title!r} "
                    f"→ playlist {playlist_objects[pl_id].id}"
                )

        # ── Build course ───────────────────────────────────────────────────
        course_spec = spec.get("course")
        if course_spec and not dry_run:
            if overwrite:
                Course.objects.filter(
                    title=course_spec["title"], authored_by=author
                ).delete()
            course = Course(
                title=course_spec["title"],
                authored_by=author,
                is_public=is_public,
            )
            course.save()
            for order, ref_entry in enumerate(course_spec.get("playlists", [])):
                ref = ref_entry["ref"]
                if ref in playlist_objects:
                    PlaylistCourseOrdered(
                        playlist=playlist_objects[ref],
                        course=course,
                        order=order,
                    ).save()
            self.stdout.write(
                f"Created course {course_spec['title']!r} → {course.id}"
            )
        elif course_spec and dry_run:
            self.stdout.write(
                f"[dry-run] Would create course: {course_spec['title']!r}"
            )

        if not dry_run:
            self.stdout.write(
                f"\nDone. {total_exercises} exercises, "
                f"{len(playlist_objects)} playlists."
            )


def _build_description(template_name, entry, key):
    """Build a short description string for an Exercise record."""
    quality = entry.get("quality", "")
    inversion = entry.get("inversion", 0)
    inv_label = ["rp", "1inv", "2inv", "3inv"][inversion] if inversion else "rp"
    return f"{template_name} {quality} {inv_label} {key}".strip()
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generate_curriculum_command -v 2
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/generate_curriculum.py apps/exercises/tests/test_generate_curriculum_command.py
git commit -m "feat: add generate_curriculum management command (Phase 1+2 complete)"
```

---

## Task 7: data/curriculum/theory1.yaml — partial validation (Phase 3)

**Files:**
- Create: `data/curriculum/theory1.yaml` (partial — intervals + triads + dominant 7ths)

This task validates the pipeline end-to-end before adding complex templates.

- [ ] **Step 1: Create data/curriculum/ directory and write partial theory1.yaml**

```bash
mkdir -p data/curriculum
```

```yaml
# data/curriculum/theory1.yaml
# Phase 3 partial — intervals, triads, dominant 7ths only

meta:
  title: "Music Theory I"
  author: "admin@example.com"   # replace with your local admin email
  public: true

course:
  title: "Music Theory I — Full Course"
  playlists:
    - ref: diatonic_intervals_major
    - ref: major_triads_rp_matching
    - ref: major_triads_rp_identification
    - ref: minor_triads_rp_matching
    - ref: minor_triads_rp_identification
    - ref: diminished_triads_rp_matching
    - ref: dominant_seventh_matching
    - ref: dominant_seventh_identification

playlists:
  - id: diatonic_intervals_major
    title: "Diatonic Intervals — Major Keys"
    tags: [intervals]
    exercises:
      - template: diatonic_intervals
        scale: major
        keys: common_major
        type: matching
        analysis: {intervals: true}
        rhythm: h
        staffDistribution: RH
      - template: diatonic_intervals
        scale: major
        keys: common_major
        type: identification
        identification_label: name
        analysis: {}
        rhythm: h
        staffDistribution: RH

  - id: major_triads_rp_matching
    title: "Major Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: major_triads_rp_identification
    title: "Major Triads — Root Position (Identification)"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: all_major
        voicing: close
        type: identification
        identification_label: quality
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  - id: minor_triads_rp_matching
    title: "Minor Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: minor
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: minor_triads_rp_identification
    title: "Minor Triads — Root Position (Identification)"
    tags: [triads]
    exercises:
      - template: triad
        quality: minor
        inversion: 0
        keys: all_major
        voicing: close
        type: identification
        identification_label: quality
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  - id: diminished_triads_rp_matching
    title: "Diminished Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: diminished
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: dominant_seventh_matching
    title: "Dominant 7th Chords — All Keys"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: dominant_seventh_identification
    title: "Dominant 7th Chords — Identification"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        voicing: close
        type: identification
        identification_label: quality
        analysis: {}
        rhythm: w
        staffDistribution: keyboard
```

- [ ] **Step 2: Run dry-run and inspect output**

```bash
python manage.py generate_curriculum data/curriculum/theory1.yaml --dry-run
```
Expected output: lists of would-be exercises grouped by playlist. Verify:
- Diatonic intervals: 6 keys × 7 intervals × 2 types = 84 exercises for this section
- Major triads: 12 keys matching + 12 keys identification = 24
- Check that interval names (m2, M3, P5 etc.) appear correctly in dry-run output

If any template raises an error, fix before proceeding.

- [ ] **Step 3: Run actual generation against local DB**

```bash
python manage.py generate_curriculum data/curriculum/theory1.yaml
```
Then open the app at `http://localhost:8000`, find the generated exercises in the library, and spot-check:
- A C major triad exercise shows [48, 64, 67, 72] (C3, E4, G4, C5)
- An identification exercise shows a dropdown with "major", "minor", "diminished", "augmented"
- A diatonic intervals exercise for jC_ shows 7 interval chords

- [ ] **Step 4: Commit**

```bash
git add data/curriculum/theory1.yaml
git commit -m "feat: add partial theory1.yaml (intervals, triads, dominant 7ths) — Phase 3 validation"
```

---

## Task 8: templates.py — scale, diatonic_triads, diatonic_sevenths

**Files:**
- Modify: `apps/exercises/generation/templates.py`
- Modify: `apps/exercises/management/commands/generate_curriculum.py` (register new templates)
- Test: `apps/exercises/tests/test_generation.py` (add)

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generation.py`:

```python
from apps.exercises.generation.templates import scale, diatonic_triads, diatonic_sevenths


class ScaleTemplateTests(SimpleTestCase):
    def test_c_major_ascending_has_8_chords(self):
        chords = scale("jC_", "major", "ascending", "matching")
        self.assertEqual(len(chords), 8)

    def test_each_chord_has_one_note(self):
        chords = scale("jC_", "major", "ascending", "matching")
        for chord in chords:
            self.assertEqual(len(chord["visible"]), 1)

    def test_ascending_c_major_starts_at_c4(self):
        chords = scale("jC_", "major", "ascending", "matching")
        self.assertEqual(chords[0]["visible"][0], 60)

    def test_ascending_c_major_ends_at_c5(self):
        chords = scale("jC_", "major", "ascending", "matching")
        self.assertEqual(chords[-1]["visible"][0], 72)

    def test_c_major_notes_are_strictly_ascending(self):
        chords = scale("jC_", "major", "ascending", "matching")
        notes = [c["visible"][0] for c in chords]
        self.assertEqual(notes, sorted(notes))


class DiatonicTriadsTests(SimpleTestCase):
    def test_c_major_returns_7_chords(self):
        chords = diatonic_triads("jC_", "major", "matching")
        self.assertEqual(len(chords), 7)

    def test_first_chord_is_c_major(self):
        chords = diatonic_triads("jC_", "major", "matching")
        # I chord: C E G
        self.assertIn(60, chords[0]["visible"])
        self.assertIn(64, chords[0]["visible"])
        self.assertIn(67, chords[0]["visible"])

    def test_second_chord_is_d_minor(self):
        chords = diatonic_triads("jC_", "major", "matching")
        # ii chord: D F A
        self.assertIn(62, chords[1]["visible"])
        self.assertIn(65, chords[1]["visible"])
        self.assertIn(69, chords[1]["visible"])

    def test_identification_has_roman_numeral_answer(self):
        chords = diatonic_triads("jC_", "major", "identification",
                                 identification_label="roman_numeral")
        self.assertEqual(chords[0]["answer"], "I")
        self.assertEqual(chords[1]["answer"], "ii")
        self.assertIn("I", chords[0]["choices"])


class DiatonicSeventhsTests(SimpleTestCase):
    def test_c_major_returns_7_chords(self):
        chords = diatonic_sevenths("jC_", "major", "matching")
        self.assertEqual(len(chords), 7)

    def test_first_chord_is_cmaj7(self):
        chords = diatonic_sevenths("jC_", "major", "matching")
        # Imaj7: C E G B
        notes = chords[0]["visible"]
        self.assertIn(60, notes)
        self.assertIn(64, notes)
        self.assertIn(67, notes)
        self.assertIn(71, notes)

    def test_fifth_chord_is_g7(self):
        chords = diatonic_sevenths("jC_", "major", "matching")
        # V7: G B D F
        notes = chords[4]["visible"]
        self.assertIn(67, notes)
        self.assertIn(71, notes)

    def test_identification_roman_numeral(self):
        chords = diatonic_sevenths("jC_", "major", "identification",
                                   identification_label="roman_numeral")
        self.assertEqual(chords[0]["answer"], "Imaj7")
        self.assertEqual(chords[4]["answer"], "V7")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.ScaleTemplateTests apps.exercises.tests.test_generation.DiatonicTriadsTests apps.exercises.tests.test_generation.DiatonicSeventhsTests -v 2
```
Expected: `ImportError`

- [ ] **Step 3: Add scale, diatonic_triads, diatonic_sevenths to templates.py**

Add to the bottom of `apps/exercises/generation/templates.py`:

```python
# Diatonic quality lookup for major scale degrees (0-indexed)
_MAJOR_DIATONIC_QUALITIES = ["major", "minor", "minor", "major", "major", "minor", "diminished"]
_MAJOR_DIATONIC_7TH_QUALITIES = ["major7", "minor7", "minor7", "major7", "dominant", "minor7", "half_dim"]

# Roman numeral labels for major scale triads
_MAJOR_RN_TRIADS = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
# Roman numeral labels for major scale seventh chords
_MAJOR_RN_SEVENTHS = ["Imaj7", "ii7", "iii7", "IVmaj7", "V7", "vi7", "vii°7"]

# Update LABEL_MAP for diatonic templates
LABEL_MAP["diatonic_triads"] = {
    "roman_numeral": {
        "choices": lambda key: _MAJOR_RN_TRIADS,
        "answer":  lambda quality, inversion, key: quality,  # quality IS the roman numeral here
    },
}
LABEL_MAP["diatonic_sevenths"] = {
    "roman_numeral": {
        "choices": lambda key: _MAJOR_RN_SEVENTHS,
        "answer":  lambda quality, inversion, key: quality,  # quality IS the roman numeral here
    },
}


def scale(key, scale_type, direction, exercise_type):
    """
    Generate 8 single-note chords for a scale exercise.

    key: HarmonyLab key string
    scale_type: "major" | "minor" (natural)
    direction: "ascending" | "descending"
    """
    from apps.exercises.generation.voicing import _pitch_in_range
    root_pc = KEY_TO_PC[key]
    bottom = _pitch_in_range(root_pc, 60, 71)
    steps = _MAJOR_STEPS if scale_type == "major" else _MINOR_STEPS
    notes = [bottom]
    for step in steps:
        notes.append(notes[-1] + step)
    if direction == "descending":
        notes = list(reversed(notes))
    return [build_chord_dict([n], exercise_type) for n in notes]


def diatonic_triads(key, scale_type, exercise_type, identification_label=None):
    """
    Generate 7 triad chords — one for each diatonic scale degree.

    Returns list of 7 chord dicts. For identification, uses roman numeral labels.
    Only major scale supported in theory1.
    """
    from apps.exercises.generation.voicing import _pitch_in_range
    root_pc = KEY_TO_PC[key]
    bottom = _pitch_in_range(root_pc, 60, 71)
    steps = _MAJOR_STEPS if scale_type == "major" else _MINOR_STEPS
    qualities = _MAJOR_DIATONIC_QUALITIES if scale_type == "major" else _MAJOR_DIATONIC_QUALITIES
    rn_labels = _MAJOR_RN_TRIADS

    chords = []
    degree_bottom = bottom
    for i, step in enumerate(steps):
        quality = qualities[i]
        intervals = QUALITY_INTERVALS[quality]
        notes = [degree_bottom]
        for interval in intervals[1:]:
            pc = (root_pc + _degree_semitones(steps, i) + interval) % 12
            note = _pitch_in_range(pc, notes[-1] + 1, notes[-1] + 12)
            notes.append(note)
        chord = build_chord_dict(notes, exercise_type)
        if exercise_type == "identification":
            rn = rn_labels[i]
            chord["answer"] = rn
            chord["choices"] = list(rn_labels)
        chords.append(chord)
        degree_bottom += step
    return chords


def _degree_semitones(steps, degree_index):
    """Return cumulative semitones from tonic to the given scale degree index."""
    return sum(steps[:degree_index])


def diatonic_sevenths(key, scale_type, exercise_type, identification_label=None):
    """
    Generate 7 seventh chord dicts — one for each diatonic scale degree.
    Only major scale supported in theory1.
    """
    from apps.exercises.generation.voicing import _pitch_in_range
    root_pc = KEY_TO_PC[key]
    bottom = _pitch_in_range(root_pc, 60, 71)
    steps = _MAJOR_STEPS
    qualities = _MAJOR_DIATONIC_7TH_QUALITIES
    rn_labels = _MAJOR_RN_SEVENTHS

    chords = []
    degree_bottom = bottom
    for i, step in enumerate(steps):
        quality = qualities[i]
        intervals = QUALITY_INTERVALS[quality]
        notes = [degree_bottom]
        for interval in intervals[1:]:
            pc = (root_pc + _degree_semitones(steps, i) + interval) % 12
            note = _pitch_in_range(pc, notes[-1] + 1, notes[-1] + 12)
            notes.append(note)
        chord = build_chord_dict(notes, exercise_type)
        if exercise_type == "identification":
            rn = rn_labels[i]
            chord["answer"] = rn
            chord["choices"] = list(rn_labels)
        chords.append(chord)
        degree_bottom += step
    return chords
```

Also register the new templates in `generate_curriculum.py`:

```python
# In TEMPLATE_FN dict, add:
    "scale":              tmpl.scale,
    "diatonic_triads":    tmpl.diatonic_triads,
    "diatonic_sevenths":  tmpl.diatonic_sevenths,
```

And in `handle()`, add dispatch for new templates:

```python
elif template_name == "scale":
    direction = entry.get("direction", "ascending")
    scale_type = entry.get("scale", "major")
    chords = fn(key, scale_type, direction, exercise_type)
elif template_name in ("diatonic_triads", "diatonic_sevenths"):
    chords = fn(key, scale, exercise_type,
                identification_label=identification_label)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generation.ScaleTemplateTests apps.exercises.tests.test_generation.DiatonicTriadsTests apps.exercises.tests.test_generation.DiatonicSeventhsTests -v 2
```
Expected: all tests PASS. If diatonic chord tone calculation is off, trace `_degree_semitones` + `_pitch_in_range` for the failing degree.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/templates.py apps/exercises/management/commands/generate_curriculum.py apps/exercises/tests/test_generation.py
git commit -m "feat: add scale, diatonic_triads, diatonic_sevenths templates"
```

---

## Task 9: templates.py — roto and progression

**Files:**
- Modify: `apps/exercises/generation/templates.py`
- Modify: `apps/exercises/management/commands/generate_curriculum.py`
- Test: `apps/exercises/tests/test_generation.py` (add)

- [ ] **Step 1: Write failing tests**

Add to `apps/exercises/tests/test_generation.py`:

```python
from apps.exercises.generation.templates import roto, progression


class RotoTemplateTests(SimpleTestCase):
    def test_c_major_ascending_returns_8_chords(self):
        chords = roto("jC_", "major", "ascending", "matching")
        self.assertEqual(len(chords), 8)

    def test_each_chord_has_four_notes(self):
        chords = roto("jC_", "major", "ascending", "matching")
        for chord in chords:
            total = len(chord["visible"]) + len(chord["hidden"])
            self.assertEqual(total, 4)

    def test_bass_note_walks_scale_stepwise(self):
        # Bass notes (lowest of each chord) should be a scale: C D E F G A B C
        chords = roto("jC_", "major", "ascending", "matching")
        bass_notes = [min(c["visible"]) for c in chords]
        for i in range(1, len(bass_notes)):
            diff = bass_notes[i] - bass_notes[i - 1]
            self.assertIn(diff, [1, 2], msg=f"Non-stepwise bass motion at chord {i}")

    def test_first_chord_root_is_tonic(self):
        chords = roto("jC_", "major", "ascending", "matching")
        bass = min(chords[0]["visible"])
        # C in range 45-57: C3=48
        self.assertEqual(bass % 12, 0)  # pitch class C


class ProgressionTemplateTests(SimpleTestCase):
    def test_ii_v_i_returns_3_chords(self):
        chords = progression("jC_", ["ii", "V", "I"], "matching")
        self.assertEqual(len(chords), 3)

    def test_each_chord_has_notes(self):
        chords = progression("jC_", ["ii", "V", "I"], "matching")
        for chord in chords:
            self.assertGreater(len(chord["visible"]) + len(chord["hidden"]), 0)

    def test_analytical_type_hides_notes(self):
        chords = progression("jC_", ["I", "IV", "V"], "analytical")
        for chord in chords:
            self.assertEqual(chord["visible"], [])
            self.assertGreater(len(chord["hidden"]), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_generation.RotoTemplateTests apps.exercises.tests.test_generation.ProgressionTemplateTests -v 2
```
Expected: `ImportError`

- [ ] **Step 3: Add roto and progression to templates.py**

Add to the bottom of `apps/exercises/generation/templates.py`:

```python
# ---------------------------------------------------------------------------
# Rule of the Octave voicings for each scale degree (major, ascending)
# Bass walks C–D–E–F–G–A–B–C; upper voices follow SATB voice-leading conventions.
# Format: (intervals_from_degree_root) producing 4 MIDI notes when combined
# with keyboard_4voice strategy.
# ---------------------------------------------------------------------------
# ROTO: standard 4-voice realization (Gjerdingen convention)
# Each entry: (bass_interval_from_tonic, upper_voice_intervals_from_bass)
# Upper voices are 3rd, 5th (or 6th), octave above bass
_ROTO_MAJOR_ASC = [
    # degree: (chord type, inversion)
    ("major",      0),  # I   (tonic)
    ("major",      2),  # I64 (passing 6/4 on scale-degree 2)
    ("minor",      1),  # vi6
    ("major",      2),  # IV64
    ("major",      1),  # V6
    ("major",      1),  # V6
    ("major",      0),  # V (on leading tone — simplified)
    ("major",      0),  # I
]

_ROTO_MAJOR_TONIC_PCS = [0, 2, 4, 5, 7, 9, 11, 0]  # scale degrees C D E F G A B C (pitch offsets)

_ROTO_MAJOR_DESC = list(reversed(_ROTO_MAJOR_ASC))
_ROTO_MAJOR_TONIC_PCS_DESC = list(reversed(_ROTO_MAJOR_TONIC_PCS))


def roto(key, scale_type, direction, exercise_type):
    """
    Generate 8 four-voice chords for the Rule of the Octave.

    Bass walks up (or down) the scale stepwise. Upper voices follow
    standard ROTO voice-leading for each scale degree.

    key: HarmonyLab key string
    scale_type: "major" (only major supported in theory1)
    direction: "ascending" | "descending"
    """
    from apps.exercises.generation.voicing import _pitch_in_range, close
    root_pc = KEY_TO_PC[key]

    if direction == "ascending":
        roto_chords = _ROTO_MAJOR_ASC
        degree_offsets = _ROTO_MAJOR_TONIC_PCS
    else:
        roto_chords = _ROTO_MAJOR_DESC
        degree_offsets = _ROTO_MAJOR_TONIC_PCS_DESC

    result = []
    for i, (quality, inversion) in enumerate(roto_chords):
        # Bass note: scale degree in bass register
        degree_pc = (root_pc + degree_offsets[i]) % 12
        bass = _pitch_in_range(degree_pc, 45, 57)

        # Upper voices: close position in treble
        chord_root_pc = (root_pc + degree_offsets[i] - QUALITY_INTERVALS[quality][inversion]) % 12
        intervals = QUALITY_INTERVALS[quality]
        treble_notes = []
        prev = 59
        rotated = intervals[inversion:] + intervals[:inversion]
        for j, interval in enumerate(rotated):
            if j == 0:
                continue  # skip bass (already placed)
            pc = (chord_root_pc + interval) % 12
            note = _pitch_in_range(pc, prev + 1, prev + 12)
            treble_notes.append(note)
            prev = note
        # Doubled root in soprano if only 3-voice treble
        if len(treble_notes) == 2:
            soprano_pc = (chord_root_pc + rotated[0]) % 12
            soprano = _pitch_in_range(soprano_pc, prev + 1, prev + 12)
            treble_notes.append(soprano)

        all_notes = [bass] + treble_notes
        chord = build_chord_dict(all_notes, exercise_type)
        result.append(chord)
    return result


# Roman numeral to diatonic scale degree offset (semitones from tonic, major scale)
_RN_TO_OFFSET = {
    "I": 0, "ii": 2, "iii": 4, "IV": 5, "V": 7, "vi": 9, "vii°": 11,
    "I6": 0, "ii6": 2, "IV6": 5, "V6": 7,
}
_RN_TO_QUALITY = {
    "I": "major", "ii": "minor", "iii": "minor", "IV": "major",
    "V": "major", "vi": "minor", "vii°": "diminished",
    "I6": "major", "ii6": "minor", "IV6": "major", "V6": "major",
}
_RN_TO_INVERSION = {
    "I": 0, "ii": 0, "iii": 0, "IV": 0, "V": 0, "vi": 0, "vii°": 0,
    "I6": 1, "ii6": 1, "IV6": 1, "V6": 1,
}


def progression(key, roman_numerals, exercise_type):
    """
    Generate one chord dict per Roman numeral in the list.

    key: HarmonyLab key string
    roman_numerals: list of strings e.g. ["ii", "V", "I"]
    """
    root_pc = KEY_TO_PC[key]
    chords = []
    for rn in roman_numerals:
        offset = _RN_TO_OFFSET.get(rn, 0)
        quality = _RN_TO_QUALITY.get(rn, "major")
        inversion = _RN_TO_INVERSION.get(rn, 0)
        chord_root_pc = (root_pc + offset) % 12
        intervals = QUALITY_INTERVALS[quality]
        notes = close(chord_root_pc, intervals, inversion=inversion)
        chord = build_chord_dict(notes, exercise_type)
        chords.append(chord)
    return chords
```

Register in `generate_curriculum.py` TEMPLATE_FN:
```python
    "roto":       tmpl.roto,
    "progression": tmpl.progression,
```

Add dispatch in `handle()`:
```python
elif template_name == "roto":
    direction = entry.get("direction", "ascending")
    chords = fn(key, scale, direction, exercise_type)
elif template_name == "progression":
    rn_list = entry.get("chords", ["I", "IV", "V", "I"])
    chords = fn(key, rn_list, exercise_type)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python manage.py test apps.exercises.tests.test_generation.RotoTemplateTests apps.exercises.tests.test_generation.ProgressionTemplateTests -v 2
```
Expected: all tests PASS. If bass notes are not stepwise, verify `degree_offsets` and `_pitch_in_range` for each degree.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/generation/templates.py apps/exercises/management/commands/generate_curriculum.py apps/exercises/tests/test_generation.py
git commit -m "feat: add roto and progression templates"
```

---

## Task 10: theory1.yaml — complete curriculum (Phase 4)

**Files:**
- Modify: `data/curriculum/theory1.yaml` (expand to full semester)

- [ ] **Step 1: Expand theory1.yaml to full semester scope**

Replace the contents of `data/curriculum/theory1.yaml` with the complete spec:

```yaml
# data/curriculum/theory1.yaml
# Full semester Music Theory I curriculum

meta:
  title: "Music Theory I"
  author: "admin@example.com"   # replace with your admin email
  public: true

course:
  title: "Music Theory I — Full Course"
  playlists:
    - ref: diatonic_intervals_major
    - ref: major_triads_rp_matching
    - ref: major_triads_rp_identification
    - ref: major_triads_1inv_matching
    - ref: major_triads_1inv_identification
    - ref: major_triads_2inv_matching
    - ref: minor_triads_rp_matching
    - ref: minor_triads_rp_identification
    - ref: diminished_triads_rp_matching
    - ref: diatonic_triads_major_matching
    - ref: diatonic_triads_major_analytical
    - ref: diatonic_triads_major_identification
    - ref: dominant_seventh_matching
    - ref: dominant_seventh_identification
    - ref: major_seventh_matching
    - ref: minor_seventh_matching
    - ref: half_dim_seventh_matching
    - ref: dominant_seventh_inversions_fb
    - ref: diatonic_sevenths_major_matching
    - ref: diatonic_sevenths_major_analytical
    - ref: diatonic_sevenths_major_identification
    - ref: scales_major
    - ref: scales_natural_minor
    - ref: roto_major_ascending
    - ref: roto_major_descending
    - ref: ii_v_i_major

playlists:
  # ── Intervals ────────────────────────────────────────────────────────────
  - id: diatonic_intervals_major
    title: "Diatonic Intervals — Major Keys"
    tags: [intervals]
    exercises:
      - template: diatonic_intervals
        scale: major
        keys: common_major
        type: matching
        analysis: {intervals: true}
        rhythm: h
        staffDistribution: RH
      - template: diatonic_intervals
        scale: major
        keys: common_major
        type: identification
        identification_label: name
        analysis: {}
        rhythm: h
        staffDistribution: RH

  # ── Triads ────────────────────────────────────────────────────────────────
  - id: major_triads_rp_matching
    title: "Major Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: major_triads_rp_identification
    title: "Major Triads — Root Position (Identification)"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 0
        keys: all_major
        voicing: close
        type: identification
        identification_label: quality
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  - id: major_triads_1inv_matching
    title: "Major Triads — First Inversion"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 1
        keys: all_major
        voicing: close
        type: matching
        analysis: {thoroughbass: true}
        rhythm: w
        staffDistribution: keyboard

  - id: major_triads_1inv_identification
    title: "Major Triads — First Inversion (Identification)"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 1
        keys: all_major
        voicing: close
        type: identification
        identification_label: inversion
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  - id: major_triads_2inv_matching
    title: "Major Triads — Second Inversion"
    tags: [triads]
    exercises:
      - template: triad
        quality: major
        inversion: 2
        keys: all_major
        voicing: close
        type: matching
        analysis: {thoroughbass: true}
        rhythm: w
        staffDistribution: keyboard

  - id: minor_triads_rp_matching
    title: "Minor Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: minor
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: minor_triads_rp_identification
    title: "Minor Triads — Root Position (Identification)"
    tags: [triads]
    exercises:
      - template: triad
        quality: minor
        inversion: 0
        keys: all_major
        voicing: close
        type: identification
        identification_label: quality
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  - id: diminished_triads_rp_matching
    title: "Diminished Triads — Root Position"
    tags: [triads]
    exercises:
      - template: triad
        quality: diminished
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: diatonic_triads_major_matching
    title: "Diatonic Triads — Major Keys (Play)"
    tags: [triads, roman-numerals]
    exercises:
      - template: diatonic_triads
        scale: major
        keys: common_major
        type: matching
        analysis: {roman_numerals: true}
        rhythm: w
        staffDistribution: keyboard

  - id: diatonic_triads_major_analytical
    title: "Diatonic Triads — Major Keys (Realize from Roman Numeral)"
    tags: [triads, roman-numerals]
    exercises:
      - template: diatonic_triads
        scale: major
        keys: common_major
        type: analytical
        analysis: {roman_numerals: true}
        rhythm: w
        staffDistribution: keyboard

  - id: diatonic_triads_major_identification
    title: "Diatonic Triads — Major Keys (Identify)"
    tags: [triads, roman-numerals]
    exercises:
      - template: diatonic_triads
        scale: major
        keys: common_major
        type: identification
        identification_label: roman_numeral
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  # ── Seventh Chords ────────────────────────────────────────────────────────
  - id: dominant_seventh_matching
    title: "Dominant 7th Chords — All Keys"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: dominant_seventh_identification
    title: "Dominant 7th Chords — Identification"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        voicing: close
        type: identification
        identification_label: quality
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  - id: major_seventh_matching
    title: "Major 7th Chords — All Keys"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: major7
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: minor_seventh_matching
    title: "Minor 7th Chords — All Keys"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: minor7
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: half_dim_seventh_matching
    title: "Half-Diminished 7th Chords — All Keys"
    tags: [seventh-chords]
    exercises:
      - template: seventh_chord
        quality: half_dim
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: matching
        analysis: {roman_numerals: true, chord_labels: true}
        rhythm: w
        staffDistribution: keyboard

  - id: dominant_seventh_inversions_fb
    title: "Dominant 7th Inversions — Figured Bass Realization"
    tags: [seventh-chords, figured-bass]
    exercises:
      - template: seventh_chord
        quality: dominant
        inversion: 0
        keys: all_major
        voicing: keyboard_4voice
        type: figured_bass
        analysis: {thoroughbass: true}
        rhythm: w
        staffDistribution: keyboard
      - template: seventh_chord
        quality: dominant
        inversion: 1
        keys: all_major
        voicing: close
        type: figured_bass
        analysis: {thoroughbass: true}
        rhythm: w
        staffDistribution: keyboard
      - template: seventh_chord
        quality: dominant
        inversion: 2
        keys: all_major
        voicing: close
        type: figured_bass
        analysis: {thoroughbass: true}
        rhythm: w
        staffDistribution: keyboard
      - template: seventh_chord
        quality: dominant
        inversion: 3
        keys: all_major
        voicing: close
        type: figured_bass
        analysis: {thoroughbass: true}
        rhythm: w
        staffDistribution: keyboard

  - id: diatonic_sevenths_major_matching
    title: "Diatonic 7th Chords — Major Keys (Play)"
    tags: [seventh-chords, roman-numerals]
    exercises:
      - template: diatonic_sevenths
        scale: major
        keys: common_major
        type: matching
        analysis: {roman_numerals: true}
        rhythm: w
        staffDistribution: keyboard

  - id: diatonic_sevenths_major_analytical
    title: "Diatonic 7th Chords — Major Keys (Realize)"
    tags: [seventh-chords, roman-numerals]
    exercises:
      - template: diatonic_sevenths
        scale: major
        keys: common_major
        type: analytical
        analysis: {roman_numerals: true}
        rhythm: w
        staffDistribution: keyboard

  - id: diatonic_sevenths_major_identification
    title: "Diatonic 7th Chords — Major Keys (Identify)"
    tags: [seventh-chords, roman-numerals]
    exercises:
      - template: diatonic_sevenths
        scale: major
        keys: common_major
        type: identification
        identification_label: roman_numeral
        analysis: {}
        rhythm: w
        staffDistribution: keyboard

  # ── Scales ────────────────────────────────────────────────────────────────
  - id: scales_major
    title: "Major Scales"
    tags: [scales]
    exercises:
      - template: scale
        scale: major
        direction: ascending
        keys: common_major
        type: matching
        analysis: {note_names: true}
        rhythm: q
        staffDistribution: RH

  - id: scales_natural_minor
    title: "Natural Minor Scales"
    tags: [scales]
    exercises:
      - template: scale
        scale: minor
        direction: ascending
        keys: common_minor
        type: matching
        analysis: {note_names: true}
        rhythm: q
        staffDistribution: RH

  # ── ROTO + Progressions ───────────────────────────────────────────────────
  - id: roto_major_ascending
    title: "Rule of the Octave — Major (Ascending)"
    tags: [voice-leading, roman-numerals, roto]
    exercises:
      - template: roto
        scale: major
        direction: ascending
        keys: common_major
        type: matching
        analysis: {thoroughbass: true, roman_numerals: true}
        rhythm: h
        staffDistribution: keyboard
      - template: roto
        scale: major
        direction: ascending
        keys: common_major
        type: analytical
        analysis: {thoroughbass: true, roman_numerals: true}
        rhythm: h
        staffDistribution: keyboard

  - id: roto_major_descending
    title: "Rule of the Octave — Major (Descending)"
    tags: [voice-leading, roman-numerals, roto]
    exercises:
      - template: roto
        scale: major
        direction: descending
        keys: common_major
        type: matching
        analysis: {thoroughbass: true, roman_numerals: true}
        rhythm: h
        staffDistribution: keyboard

  - id: ii_v_i_major
    title: "ii–V–I Progressions — Major Keys"
    tags: [progressions, roman-numerals]
    exercises:
      - template: progression
        chords: [ii, V, I]
        keys: common_major
        type: matching
        analysis: {roman_numerals: true}
        rhythm: w
        staffDistribution: keyboard
      - template: progression
        chords: [ii, V, I]
        keys: common_major
        type: analytical
        analysis: {roman_numerals: true}
        rhythm: w
        staffDistribution: keyboard
```

- [ ] **Step 2: Run dry-run to verify full spec parses cleanly**

```bash
python manage.py generate_curriculum data/curriculum/theory1.yaml --dry-run 2>&1 | tail -20
```
Expected: no errors, output shows all ~26 playlists listed, total exercise count printed.

- [ ] **Step 3: Delete partial content and generate full curriculum**

```bash
# Delete the partial content created in Task 7
python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.exercises.models import Exercise, Playlist, Course
User = get_user_model()
author = User.objects.get(email='admin@example.com')
Exercise.objects.filter(authored_by=author).delete()
Playlist.objects.filter(authored_by=author).delete()
Course.objects.filter(authored_by=author).delete()
print('Deleted partial content')
"

# Generate full curriculum
python manage.py generate_curriculum data/curriculum/theory1.yaml
```
Expected: ~400 exercises, ~26 playlists, 1 course.

- [ ] **Step 4: Spot-check in the app**

Open `http://localhost:8000/library/` and verify:
- "Music Theory I — Full Course" appears and is clonable
- Clicking into "Major Triads — Root Position" shows 12 exercises (one per key)
- Opening a matching exercise shows notes on staff; playing them advances correctly
- Opening an identification exercise shows a dropdown with the right choices

- [ ] **Step 5: Commit**

```bash
git add data/curriculum/theory1.yaml
git commit -m "feat: complete theory1.yaml full semester curriculum (Phase 4)"
```

---

## Self-Review Checklist

After writing, checked against spec:

- [x] **analysis_presets.py** — Task 1 ✓
- [x] **spec_loader.py with key shorthand expansion** — Task 2 ✓
- [x] **voicing.py: close, open, close_4voice, keyboard_4voice** — Task 3 ✓
- [x] **triad template with matching/analytical/figured_bass/identification** — Task 4 ✓
- [x] **seventh_chord template** — Task 4 ✓
- [x] **interval + diatonic_intervals templates** — Task 5 ✓
- [x] **generate_curriculum management command with --dry-run + --overwrite** — Task 6 ✓
- [x] **Partial theory1.yaml validation** — Task 7 ✓
- [x] **scale, diatonic_triads, diatonic_sevenths templates** — Task 8 ✓
- [x] **roto + progression templates** — Task 9 ✓
- [x] **Complete theory1.yaml** — Task 10 ✓
- [x] **Label map for all identification types** — Tasks 4, 5, 8 ✓
- [x] **Identification label is only read when type=identification** — Task 4 ✓

One known simplification in `diatonic_triads`: the upper-voice MIDI calculation uses a helper `_degree_semitones` to offset the root pitch class by scale-degree semitones. If chord tones come out wrong for any degree, trace: `(root_pc + _degree_semitones(steps, i) + interval) % 12` and verify `_pitch_in_range` finds the right MIDI in the stacking range. The `roto` template uses a simplified chord-type table; a music theory professor may want to adjust the specific inversions used for each degree — that lives in `_ROTO_MAJOR_ASC`.
