# Unit 9 Bach Chorale Import Strategy

This document describes the current Unit 9 Bach chorale import strategy and the technical rationale behind it. Earlier Unit 9 playlists were created with one-off scripts; new imports should use `create_unit_playlist`.

## Objective

Create a playlist of Bach chorale phrases for **Unit 9** of the HarmonyLab curriculum. Unit 9 focuses exclusively on **Tonic (I/i)** and **Dominant (V/V7)** functions. The exercises display a full Bach chorale score but hide all Roman numeral identification slots that are outside the unit's scope.

---

## What Is Currently Implemented

> **Note:** This section describes working, deployed code. The "Future / Planned" section below describes features that are modelled but not yet wired.

### 1. Playlist Creation

Current playlist generation uses `create_unit_playlist`, which imports a Riemenschneider range, tags each exercise, filters/ordering by the unit taxonomy, and links the result into a static adaptive playlist.

```bash
python manage.py create_unit_playlist \
  --unit 9 \
  --riemenschneider 1-30 \
  --author admin@example.com \
  --mode roman \
  --public
```

To refresh existing exercises after importer fixes, pass `--overwrite` or use the "Overwrite existing exercises" checkbox in the Django admin/local content-generation UI.

```bash
python manage.py create_unit_playlist \
  --unit 9 \
  --riemenschneider 1-30 \
  --author admin@example.com \
  --mode roman \
  --overwrite
```

Supported Bach playlist modes include `roman`, `matching`, `figures`, `figures_unabbreviated`, `play`, and `play_figures`.

### 2. Tag Vocabulary

Two parallel tag namespaces exist. Understanding which is used where prevents confusion.

| Namespace | Form | Example | Used for |
|---|---|---|---|
| **Unit tags** | `unit:N` | `unit:9` | Playlist `skill_tags`; mastery rows; frontend filter trigger |
| **Unit long-form** | `unit:N_SkillName` | `unit:9_Dominant_Seventh` | Emitted by `skills_analyzer.py` on exercises; accepted by `applySkillFilter` |
| **Canonical KG tags** | `SkillName` | `Dominant_Seventh` | `MASTERY_TAGS` set in `skill_graph.py`; `StudentSkillMastery` rows |

**Rule:** `unit:9_Dominant_Seventh` on an exercise is the long-form duplicate of `Dominant_Seventh`. `skill_graph.py:MASTERY_TAGS` explicitly excludes long-forms so mastery rows stay clean.

All valid tags for Unit 9 are declared in `apps/exercises/skill_graph.py:39`:
```python
"unit:9", "unit:9_diatonic_triads", "unit:9_tonic_dominant_exclusively",
"unit:9_Diatonic_Triads", "unit:9_Dominant_Seventh",
```

### 3. Data Flow: Playlist Tag → Request-Time Filter

```
Playlist.skill_tags = ['unit:9']
    ↓
lab/views.py  generate_exercise_context()
    TaxonomyReader gets Unit 9 cumulative answers
    ↓
analysisPolicy + allowed_answers sent to browser
    ↓
exercise_definition.js  buildUMTOIdentificationProblems()
    hides out-of-scope/null-content slots
```

### 4. WiR Analysis Behavior

`import_bach_phrases` uses When in Rome labels for WiR-backed modes:

- `roman`
- `matching`
- `play`
- `play_figures`

For each music21 chordify beat, the importer emits one UMTO analysis slice. Structural WiR beats get `roman_numeral`, `local_key`, `raw_roman_numeral`, `raw_figured_bass`, and `figured_bass`. Beats absent from WiR are retained as null-content slices so frontend slots stay aligned with score windows, but the student does not see a target.

WiR Roman labels are authoritative. music21 labels are preserved only in `raw_roman_numeral` for audit/debugging.

### 5. Figured-Bass Reconciliation

WiR-backed imports also compute figured bass. For R1 mm.8-12, the suspension at offset `14.0` is stored as:

```text
roman_numeral: V7
raw_roman_numeral: iv74
raw_figured_bass: 8/7/4
figured_bass: 7/4-3
```

For Unit 9 targeting, out-of-scope suspension figures such as `7/4-3` are not asked as Unit 9 answers. The request-time targeting layer can move a target to a nearby resolution slice when the resolution is in scope.

### 6. Why Request-Time Filtering (Not Destructive Import)

1. **Data preservation** — the full chorale stays in the DB; no information is discarded.
2. **Reusability** — the same exercises appear in later units (e.g., Unit 11 for Pre-Dominants) simply by changing playlist tags.
3. **Consistency** — students see a real Bach score but are only challenged on learned functions.
4. **Alignment** — null-content WiR/NCT slices keep the analysis array aligned with rendered score windows.

---

## Future / Planned

These features are modelled in the DB but not yet active:

| Feature | What exists | What's missing |
|---|---|---|
| **Mastery gating** | `StudentSkillMastery` model, `SkillPrerequisite` DAG model, `Course.mastery_threshold` | `IdentificationAttempt.save()` → mastery update hook; `SkillPrerequisite` rows seeded; `PlaylistView` prereq check |
| **Adaptive serving** | `Playlist.is_dynamic`, `get_adaptive_exercise_for_view` in `lab/views.py` | Works for dynamic playlists; Bach playlists are usually generated as ordered/static playlists |
| **Bulk curriculum generator** | `create_unit_playlist` command | Higher-level matrix command for many units/modes at once |

See [docs/superpowers/specs/2026-04-18-curriculum-architecture.md](superpowers/specs/2026-04-18-curriculum-architecture.md) for the full roadmap.

---

## Reference Links

- **WiR import reference:** [WHEN_IN_ROME_IMPORT.md](WHEN_IN_ROME_IMPORT.md)
- **Playlist command:** [create_unit_playlist.py](../apps/exercises/management/commands/create_unit_playlist.py)
- **Import command:** [import_bach_phrases.py](../apps/exercises/management/commands/import_bach_phrases.py)
- **Frontend filter:** [exercise_definition.js:37](../lab/static/js/src/models/exercise_definition.js#L37)
- **Request-time targeting:** [lab/views.py](../lab/views.py)
- **Tag vocabulary:** [apps/exercises/skill_graph.py:39](../apps/exercises/skill_graph.py#L39)
- **Mastery tag set:** [apps/exercises/skill_graph.py:156](../apps/exercises/skill_graph.py#L156)
