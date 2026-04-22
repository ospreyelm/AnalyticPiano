# Unit 9 Bach Chorale Import Strategy

This document describes how the Unit 9 Bach Chorale playlist (**PA01TO**) was created and the technical rationale behind its implementation.

## Objective

Create a playlist of Bach chorale phrases for **Unit 9** of the HarmonyLab curriculum. Unit 9 focuses exclusively on **Tonic (I/i)** and **Dominant (V/V7)** functions. The exercises display a full Bach chorale score but hide all Roman numeral identification slots that are outside the unit's scope.

---

## What Is Currently Implemented

> **Note:** This section describes working, deployed code. The "Future / Planned" section below describes features that are modelled but not yet wired.

### 1. Playlist Creation

Playlist **PA01TO** was created via `scratch/batch_import_unit9.py`. That script:

1. Deletes any stale playlist named `"Unit 9 Bach Phrases (R11-20)"`.
2. Creates a new `Playlist` with `skill_tags=['unit:9']` and `is_dynamic=False`.
3. Calls `import_bach_phrases --riemenschneider N --author ... --mode roman` for Riemenschneider numbers 11–20.
4. Sorts newly created exercises by R-number and phrase number, then links them to the playlist via `ExercisePlaylistOrdered`.

To recreate the playlist from scratch:
```bash
python scratch/batch_import_unit9.py
```

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

### 3. Data Flow: Playlist Tag → Frontend Filter

```
Playlist.skill_tags = ['unit:9']
    ↓
lab/views.py:288  generate_exercise_context()
    "playlistSkillTags": getattr(playlist, "skill_tags", [])
    ↓
JSON context sent to browser
    ↓
exercise_definition.js:759  ExerciseDefinition.parse()
    exercise.playlistSkillTags = definition.playlistSkillTags || []
    ↓
exercise_definition.js:762  buildChoraleIdentificationProblems()
    exercise.problems = applySkillFilter(problems, playlistSkillTags.concat(playlistTags))
    ↓
exercise_definition.js:37  applySkillFilter()
    Detects 'unit:9' → hides all problems where answer ∉ {I, i, V, V7}
```

### 4. `applySkillFilter()` Behavior

**Location:** [lab/static/js/src/models/exercise_definition.js:37–67](lab/static/js/src/models/exercise_definition.js#L37-L67)

The function receives the full `problems` array (one entry per Roman numeral slot in the score) and the combined `playlistSkillTags + playlistTags` array.

**Unit 9 path (lines 43–54):** Triggered when any tag matches `unit:9`, `unit:9_diatonic_triads`, or `unit:9_Dominant_Seventh`. Sets `p.hidden = true` on every problem whose `answer` is not exactly `I`, `i`, `V`, or `V7`. Root-position only — no inversions.

**Generic path (lines 56–59):** For other units, strips the `unit:N_` prefix from each tag and hides problems whose `answer` does not start with the cleaned tag string.

**Effect:** Hidden problems render as greyed-out slots the student cannot interact with. The underlying exercise data is unchanged.

### 5. Why Frontend Filtering (Not Backend Import)

1. **Data preservation** — the full chorale stays in the DB; no information is discarded.
2. **Reusability** — the same exercises appear in later units (e.g., Unit 11 for Pre-Dominants) simply by changing playlist tags.
3. **Consistency** — students see a real Bach score but are only challenged on learned functions.

---

## Future / Planned (Not Yet Wired)

These features are modelled in the DB but not yet active:

| Feature | What exists | What's missing |
|---|---|---|
| **Mastery gating** | `StudentSkillMastery` model, `SkillPrerequisite` DAG model, `Course.mastery_threshold` | `IdentificationAttempt.save()` → mastery update hook; `SkillPrerequisite` rows seeded; `PlaylistView` prereq check |
| **Adaptive serving** | `Playlist.is_dynamic`, `get_adaptive_exercise_for_view` in `lab/views.py:134` | Fully works for dynamic playlists; Unit 9 playlist is currently `is_dynamic=False` (curated) |
| **Bulk curriculum generator** | `import_bach_phrases` command | `generate_curriculum.py` management command (sliding window × mode matrix) |

See [docs/superpowers/specs/2026-04-18-curriculum-architecture.md](superpowers/specs/2026-04-18-curriculum-architecture.md) for the full roadmap.

---

## Reference Links

- **Playlist ID:** `PA01TO`
- **Batch import script:** [scratch/batch_import_unit9.py](../scratch/batch_import_unit9.py)
- **Frontend filter:** [exercise_definition.js:37](../lab/static/js/src/models/exercise_definition.js#L37)
- **Backend tag injection:** [lab/views.py:288](../lab/views.py#L288)
- **Tag vocabulary:** [apps/exercises/skill_graph.py:39](../apps/exercises/skill_graph.py#L39)
- **Mastery tag set:** [apps/exercises/skill_graph.py:156](../apps/exercises/skill_graph.py#L156)
