# Skill-Filtered Chord Identification

**Date:** 2026-04-18  
**Status:** Approved for implementation  
**Branch:** feature/music21_builder

---

## Problem

Chorale identification exercises present `?` slots for every chord window in the score. When a student is in a unit focused on I, V, and V7, they also get quizzed on ii6, IV, vii°, and any other harmony present in the slice — noise that undermines the pedagogical goal.

**Goal:** Show the full chorale score for context, but only surface `?` slots for chord functions the current unit is teaching. Everything else displays as score-only.

---

## Design

### Principle

No changes to exercise data, import pipeline, analysis, or grading logic. All analysis is retained in full. Filtering is a pure view concern applied at load time in the front end, using the existing `hidden` flag mechanism already respected by both `ExerciseSheet` and `IdentificationGrader`.

### Data Flow

```
generate_exercise_context()
  → playlistSkillTags: playlist.skill_tags   ← NEW field on Playlist model
  → skillTags: exercise.skill_tags           ← already exists (Gemini added)

ExerciseDefinition.parse()
  → stores playlistSkillTags on exercise object  ← NEW key

ExerciseContext.initIdentificationProblems()
  → problems = definition.buildChoraleIdentificationProblems()
  → problems = applySkillFilter(problems, playlistSkillTags)  ← NEW call
  → stores filtered problems

ExerciseSheet renders
  → skips hidden problems (existing logic, unchanged)

IdentificationGrader grades
  → skips hidden problems (existing logic, unchanged)
```

---

## Components

### 1. Backend: `Playlist.skill_tags` field (NEW)

**File:** `apps/exercises/models.py`

```python
skill_tags = ArrayField(
    base_field=models.CharField(max_length=64),
    default=list,
    blank=True,
    verbose_name="Skill Tags",
    help_text="Harmonic skills this playlist targets (e.g. Dominant_Seventh). "
              "Used to filter identification slots in chorale exercises."
)
```

Same vocabulary as `Exercise.skill_tags` — values from `ALL_SKILL_TAGS` in `skill_graph.py`.

**Migration:** Single `AddField` migration.

**Admin:** Add `skill_tags` to `PlaylistAdmin` fieldsets in `apps/exercises/admin.py`. Use a `MultipleChoiceField` with choices from `ALL_SKILL_TAGS` (same pattern as existing skill tag fields).

---

### 2. Backend: Server sends `playlistSkillTags` (NEW)

**File:** `lab/views.py`, `generate_exercise_context()`, line ~286

```python
"playlistSkillTags": getattr(playlist, "skill_tags", []),
```

Add alongside the existing `"skillTags": getattr(exercise, "skill_tags", [])` line.

---

### 3. JS: `SKILL_CHORD_PATTERNS` map (NEW)

**File:** `lab/static/js/src/models/exercise_definition.js`

Maps each harmonic skill tag to a regex that matches the roman numeral labels our own `analyzer.to_chord()` generates. Labels are controlled output — no variation.

```javascript
var SKILL_CHORD_PATTERNS = {
    // Triads
    "Diatonic_Triads":         /^(I|ii|iii|IV|V|vi|vii°)$/,
    "Inversions_First":        /^(I|ii|iii|IV|V|vi|vii°)(6)$/,
    "Inversions_Second":       /^(I|ii|iii|IV|V|vi|vii°)(64)$/,

    // Seventh chords
    "Dominant_Seventh":        /^V7$/,
    "Diminished_Seventh":      /^vii°7/,
    "Half_Diminished_Seventh": /^viiø7/,

    // Secondary function
    "Secondary_Dominant":      /^V7?\//,
    "Secondary_Leading_Tone":  /^vii°(7)?\//,

    // Chromatic chords
    "Neapolitan_Sixth":        /^N6?$/,
    "Augmented_Sixth":         /^(It|Ger|Fr)\+?6/,

    // Structural tags — no chord-level pattern, filter has no effect
    // (Cadence_*, Picardy_Third, Modulation_*) → omitted intentionally
};
```

**Structural tags** (cadence types, Picardy Third, Modulation) describe passage-level features, not individual chord labels. They are intentionally omitted. If a playlist's `skill_tags` contains only structural tags, `applySkillFilter` returns all problems unfiltered — correct behavior, since there's nothing to filter by.

---

### 4. JS: `applySkillFilter(problems, skillTags)` (NEW)

**File:** `lab/static/js/src/models/exercise_definition.js`

Pure function. No side effects. Returns a new problems array.

```javascript
function applySkillFilter(problems, skillTags) {
    // No tags → show everything (no-op)
    if (!skillTags || skillTags.length === 0) {
        return problems;
    }

    // Collect patterns for tags that have chord-level meaning
    var patterns = [];
    _.each(skillTags, function (tag) {
        if (SKILL_CHORD_PATTERNS[tag]) {
            patterns.push(SKILL_CHORD_PATTERNS[tag]);
        }
    });

    // No chord patterns found (e.g. only structural tags) → show everything
    if (patterns.length === 0) {
        return problems;
    }

    return _.map(problems, function (p) {
        var matches = _.some(patterns, function (rx) {
            return rx.test(p.answer);
        });
        if (matches) {
            return p;
        }
        return _.extend({}, p, { hidden: true });
    });
}
```

---

### 5. JS: `ExerciseDefinition.parse()` stores `playlistSkillTags` (MODIFIED)

**File:** `lab/static/js/src/models/exercise_definition.js`, near line 889

Replace Gemini's line:
```javascript
exercise.playlistTags = definition.playlistTags || [];
```
With:
```javascript
exercise.playlistSkillTags = definition.playlistSkillTags || [];
```

Keep Gemini's existing line:
```javascript
exercise.skillTags = definition.skillTags || [];
```

---

### 6. JS: Call `applySkillFilter` immediately after `buildChoraleIdentificationProblems` (MODIFIED)

**File:** `lab/static/js/src/models/exercise_definition.js`, line 704

Problems are assigned at parse time. Filter is applied on the same line, in place:

```javascript
// line 704 — existing:
exercise.problems = buildChoraleIdentificationProblems(exercise);

// replace with:
exercise.problems = applySkillFilter(
    buildChoraleIdentificationProblems(exercise),
    exercise.playlistSkillTags || []
);
```

`ExerciseContext` is not touched. It calls `definition.getProblems()` which returns `exercise.problems` — already filtered.

---

### 7. JS: Clean up Gemini's broken `getVisibleSkills()` (MODIFIED)

**File:** `lab/static/js/src/models/exercise_definition.js`

Remove `getVisibleSkills()` (lines ~590-602). It intersects `exercise.skill_tags` with `playlist.tags` — two different namespaces that never overlap. Currently dead code with incorrect logic.

**File:** `lab/static/js/src/components/music/exercise_sheet.js`

Remove line ~801:
```javascript
tpl_data.visible_skills = definition.getVisibleSkills();
```
And any template usage of `visible_skills` in the info panel. The skill badge display feature is out of scope and broken.

---

## What Is NOT Changed

| Component | Reason |
|-----------|--------|
| `chorale_grader.js` | Chorale play mode unaffected |
| `identification_grader.js` | Already skips `hidden: true` problems |
| `exercise_sheet.js` identification slots | Already skips `hidden: true` problems |
| Exercise data / import pipeline | No changes to stored data |
| `skills_analyzer.py` | No changes to detection logic |
| `buildChoraleIdentificationProblems()` | Returns full unfiltered problems; filter applied after |

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `playlist.skill_tags` is empty | All slots shown (no-op filter) |
| All playlist skill tags are structural (cadence types) | All slots shown (no chord patterns to match) |
| No chorale identification exercise | `applySkillFilter` never called |
| `analysisType` is pitch (note_name, solfege, etc.) | Filter still applies if desired, but pitch tags have no entries in `SKILL_CHORD_PATTERNS` → all shown |
| Exercise has chords not in any pattern | Those windows get `hidden: true` |

---

## Files Changed

| File | Change type |
|------|-------------|
| `apps/exercises/models.py` | Add `Playlist.skill_tags` field |
| `apps/exercises/admin.py` | Expose `skill_tags` in PlaylistAdmin |
| `apps/exercises/migrations/XXXX_playlist_skill_tags.py` | New migration |
| `lab/views.py` | Add `playlistSkillTags` to generate_exercise_context |
| `lab/static/js/src/models/exercise_definition.js` | Add `SKILL_CHORD_PATTERNS`, `applySkillFilter()`, store `playlistSkillTags`, remove broken `getVisibleSkills()` |
| `lab/static/js/src/components/music/exercise_sheet.js` | Remove broken `visible_skills` call |

---

## What Gemini Built (Keep vs. Remove)

| Gemini change | Action |
|---------------|--------|
| `views.py` line 287: `"skillTags": exercise.skill_tags` | **Keep** — useful data, costs nothing |
| `exercise_definition.js` line 889: store `skillTags` | **Keep** |
| `exercise_definition.js` line 890: store `playlistTags` | **Replace** with `playlistSkillTags` |
| `exercise_definition.js` `getVisibleSkills()` | **Remove** — broken namespace logic |
| `exercise_sheet.js` line 801: `visible_skills` pill display | **Remove** — wrong feature, broken |
