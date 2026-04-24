# applySkillFilter UNIT_ALLOWED_ANSWERS Map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken `applySkillFilter` in `exercise_definition.js` with a declarative `UNIT_ALLOWED_ANSWERS` map covering units 9–20, fixing incorrect filtering for all units beyond Unit 9.

**Architecture:** Add `UNIT_ALLOWED_ANSWERS` object above `applySkillFilter`. Rewrite the function to extract the highest `unit:N` tag, look up the allowlist, and apply exact-match hiding. Pass `analysisType` as a third argument from the call site so non-roman exercises pass through untouched.

**Tech Stack:** JavaScript (AMD/RequireJS module), Lodash (`_`)

> **Note on automated tests:** No JS unit test harness exists in this codebase. The approved spec requests automation for tests 3–6 where feasible. Standing up QUnit or Jest is out of scope for this task. The manual browser steps below cover all spec-required cases. If a test harness is added later, the acceptance criteria table maps 1:1 to unit test cases.

---

## Files

| File | Change |
|---|---|
| `lab/static/js/src/models/exercise_definition.js` | Add `UNIT_ALLOWED_ANSWERS` map; rewrite `applySkillFilter` (lines 37–67); update call site at line 762 |
| `docs/superpowers/specs/2026-04-19-apply-skill-filter-unit-map-design.md` | Update map entries if Task 1 reveals label mismatches (conditional) |

No other files touched.

---

### Task 1: Verify answer string format from real exercises

Before writing any code, confirm what strings `computeWindowLabel` actually emits for secondary chords, diminished sevenths, and augmented sixths. The map is worthless if strings don't match.

**Files:**
- Read: `lab/static/js/src/models/exercise_definition.js:201-330`

- [ ] **Step 1: Open a Unit 16 or Unit 18 exercise in the browser**

Load any `chorale_identification` exercise with secondary dominants or augmented sixths. Open DevTools console and run:

```javascript
// Paste in browser console while on a chorale_identification exercise page
var def = require('app/models/exercise_definition');
// Or find the exercise definition object in the page's JS state.
// Simpler: add a temporary console.log in buildChoraleIdentificationProblems:
```

Add this temporary log at `exercise_definition.js:398` (inside the `_.each(windows, ...)` loop, after `var answer = labels[idx] || ""`):

```javascript
console.log('[ANSWER_CHECK]', answer);
```

- [ ] **Step 2: Load exercises and record actual answer strings**

Play through a phrase containing:
- Secondary dominant (Unit 16): confirm format is `V/V`, `V7/V`, `vii°/V` etc.
- Augmented sixth (Unit 18): confirm format is `It+6`, `Ger+6`, `Fr+6` or different
- Neapolitan (Unit 18): confirm `N6` or `bII6`
- Diminished seventh: confirm `vii°7` or `viio7`

Record any mismatches against the map in the spec.

- [ ] **Step 3: Remove the temporary log**

Revert the `console.log` added in Step 1.

- [ ] **Step 4: Update the map entries in the spec if strings differ**

Edit `docs/superpowers/specs/2026-04-19-apply-skill-filter-unit-map-design.md` to correct any answer strings that don't match real output. This is the source of truth for the map in Task 2.

---

### Task 2: Add `UNIT_ALLOWED_ANSWERS` map and rewrite `applySkillFilter`

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js:14-67`

- [ ] **Step 1: Replace lines 14–67 with the new map + function**

The current block to replace starts at line 14 (`var SKILL_CHORD_PATTERNS`) and ends at line 67 (closing `}` of `applySkillFilter`).

Replace the entire block with:

```javascript
  var UNIT_ALLOWED_ANSWERS = {
    // Unit 9: Tonic & dominant — I, V, V7 root position only
    9: ['I', 'i', 'V', 'V7'],

    // Unit 10: First inversions — adds I6, i6, V6, vii°6
    10: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6'],

    // Unit 11: Pre-dominants — adds IV, iv, ii, ii6, vi, VI
    11: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI'],

    // Unit 12: Second inversions — adds I64, V64
    12: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64'],

    // Unit 13: Rule of the octave — adds iii, III, VII
    13: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64',
         'iii', 'III', 'VII'],

    // Unit 14: Diatonic seventh chords — adds ii7, ii°7, IV7, vi7, iii7, vii°7
    14: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64',
         'iii', 'III', 'VII',
         'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7'],

    // Unit 15: Sequences — no new chord types beyond unit 14
    15: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64',
         'iii', 'III', 'VII',
         'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7'],

    // Unit 16: Applied (secondary) chords — adds V/x, V7/x, vii°/x, vii°7/x
    16: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64',
         'iii', 'III', 'VII',
         'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7',
         'V/ii', 'V7/ii', 'V/IV', 'V7/IV', 'V/V', 'V7/V',
         'V/vi', 'V7/vi', 'V/III', 'V7/III',
         'vii°/ii', 'vii°7/ii', 'vii°/V', 'vii°7/V',
         'vii°/vi', 'vii°7/vi', 'vii°/IV', 'vii°7/IV'],

    // Unit 17: Modal mixture — adds bVI, bVII, bIII, ii°, ii°6
    17: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64',
         'iii', 'III', 'VII',
         'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7',
         'V/ii', 'V7/ii', 'V/IV', 'V7/IV', 'V/V', 'V7/V',
         'V/vi', 'V7/vi', 'V/III', 'V7/III',
         'vii°/ii', 'vii°7/ii', 'vii°/V', 'vii°7/V',
         'vii°/vi', 'vii°7/vi', 'vii°/IV', 'vii°7/IV',
         'bVI', 'bVII', 'bIII', 'ii°', 'ii°6'],

    // Unit 18: Neapolitan & augmented sixths — adds N6, It+6, Ger+6, Fr+6
    18: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
         'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
         'I64', 'V64',
         'iii', 'III', 'VII',
         'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7',
         'V/ii', 'V7/ii', 'V/IV', 'V7/IV', 'V/V', 'V7/V',
         'V/vi', 'V7/vi', 'V/III', 'V7/III',
         'vii°/ii', 'vii°7/ii', 'vii°/V', 'vii°7/V',
         'vii°/vi', 'vii°7/vi', 'vii°/IV', 'vii°7/IV',
         'bVI', 'bVII', 'bIII', 'ii°', 'ii°6',
         'N6', 'It+6', 'Ger+6', 'Fr+6'],

    // Units 19–20: Modulation — pass through unmodified.
    // Modulation exercises span tonal centres; filtering to one key's allowlist
    // would hide legitimate chords in the new key.
    19: null,
    20: null,
  };

  function applySkillFilter(problems, skillTags, analysisType) {
    if (!skillTags || skillTags.length === 0) return problems;

    // Only filter roman numeral exercises — all other types pass through
    if ((analysisType || 'roman') !== 'roman') return problems;

    // Extract the highest unit number from any 'unit:N' tag (deterministic, order-independent)
    var unitNum = null;
    _.each(skillTags, function(t) {
      var m = t.match(/^unit:(\d+)/);
      if (m) {
        var parsed = parseInt(m[1], 10);
        unitNum = (unitNum === null) ? parsed : Math.max(unitNum, parsed);
      }
    });

    // No unit tag → pass through
    if (unitNum === null) return problems;

    // Unit not in map → pass through (safe fallback for units 21+)
    if (!UNIT_ALLOWED_ANSWERS.hasOwnProperty(unitNum)) return problems;

    var allowed = UNIT_ALLOWED_ANSWERS[unitNum];

    // null entry (units 19–20) → pass through
    if (allowed === null) return problems;

    return _.map(problems, function(p) {
      if (p.hidden) return p;
      if (allowed.indexOf(p.answer) === -1) {
        p = _.clone(p);
        p.hidden = true;
      }
      return p;
    });
  }
```

> **Note on `SKILL_CHORD_PATTERNS`:** This object (lines 14–35 in the current file) is no longer used by `applySkillFilter`. Search for other usages before deleting:
> ```bash
> grep -n "SKILL_CHORD_PATTERNS" lab/static/js/src/models/exercise_definition.js
> ```
> If no other usages: delete it. If used elsewhere: leave it and add a comment that it's legacy.

- [ ] **Step 2: Update the call site to pass `analysisType`**

Find line 762 (currently):
```javascript
        exercise.problems = applySkillFilter(
            buildChoraleIdentificationProblems(exercise),
            (exercise.playlistSkillTags).concat(exercise.playlistTags)
        );
```

Change to:
```javascript
        exercise.problems = applySkillFilter(
            buildChoraleIdentificationProblems(exercise),
            (exercise.playlistSkillTags).concat(exercise.playlistTags),
            exercise.analysisType
        );
```

- [ ] **Step 3: Check for any other call sites**

```bash
grep -n "applySkillFilter" lab/static/js/src/models/exercise_definition.js
```

Expected output: two lines — the function definition and the one call site at ~762. If there are additional call sites, update them with the same third-argument pattern.

- [ ] **Step 4: Verify the file loads without syntax errors**

```bash
node --input-type=module <<'EOF'
import fs from 'fs';
const src = fs.readFileSync('lab/static/js/src/models/exercise_definition.js', 'utf8');
// Quick parse check — will throw on syntax error
new Function(src);
console.log('No syntax errors detected');
EOF
```

If the project has a build step or linter, run it instead:
```bash
# If eslint is available:
npx eslint lab/static/js/src/models/exercise_definition.js
```

---

### Task 3: Manual browser regression — Unit 9

Confirm Unit 9 still filters correctly after the rewrite.

**Files:**
- Read: existing Unit 9 playlist (PA01TO) in running dev server

- [ ] **Step 1: Start the dev server**

```bash
python manage.py runserver
```

- [ ] **Step 2: Load the Unit 9 playlist**

Navigate to `http://127.0.0.1:8000/playlists/PA01TO/`

- [ ] **Step 3: Open a chorale identification exercise**

Open DevTools → Console. Filter by `[applySkillFilter]` or add a temporary log at the top of `applySkillFilter`:

```javascript
console.log('[applySkillFilter] unitNum:', unitNum, 'allowed:', allowed);
```

- [ ] **Step 4: Verify filtering**

Expected: only `I`, `i`, `V`, `V7` slots are interactive. All other Roman numeral slots are hidden/greyed. Console should show `unitNum: 9`.

- [ ] **Step 5: Remove temporary log if added**

---

### Task 4: Manual browser smoke test — Unit 11

Verify a non-Unit-9 playlist filters correctly with the new map.

**Files:**
- Requires: a playlist tagged `unit:11` with a `chorale_identification` exercise containing `IV` and `V/V` chords.

- [ ] **Step 1: Tag a test playlist `unit:11`**

In Django admin or shell:
```python
from apps.exercises.models import Playlist
p = Playlist.objects.get(id='PA01TO')  # or any chorale_identification playlist
p.skill_tags = ['unit:11']
p.save()
```

Or create a new playlist pointing at an existing exercise:
```python
from apps.exercises.models import Playlist, Exercise, ExercisePlaylistOrdered
from apps.accounts.models import User

author = User.objects.get(email='avner-local2025@localhost')
p = Playlist(name='Unit 11 Test', authored_by=author, is_dynamic=False, skill_tags=['unit:11'])
p.save()
# Link any chorale_identification exercise
ex = Exercise.objects.filter(data__type='chorale_identification').first()
ExercisePlaylistOrdered.objects.create(exercise=ex, playlist=p, order=1)
print(p.id)
```

- [ ] **Step 2: Load the playlist in browser**

Navigate to `http://127.0.0.1:8000/playlists/<playlist_id>/`

- [ ] **Step 3: Verify Unit 11 filtering**

Expected:
- `I`, `i`, `V`, `V7`, `I6`, `i6`, `V6`, `vii°6`, `IV`, `iv`, `ii`, `ii6`, `vi`, `VI` slots → **visible and interactive**
- `V/V`, `V7/V`, `N6`, `It+6` slots → **hidden**

- [ ] **Step 4: Clean up test playlist**

If you **created a new playlist** in Step 1, delete it:
```python
from apps.exercises.models import Playlist
Playlist.objects.filter(name='Unit 11 Test').delete()
```

If you **modified PA01TO directly** in Step 1 (not recommended), restore its original tags:
```python
from apps.exercises.models import Playlist
p = Playlist.objects.get(id='PA01TO')
# Restore to original — check git history for original value before overwriting:
# git show HEAD:apps/exercises/fixtures/... or check admin
p.skill_tags = ['unit:9']
p.save()
```

> **Prefer creating a new test playlist** over modifying PA01TO to avoid risk of overwriting legitimate production tags.

---

### Task 5: Exact-match regression — `V` must not match `VI` or `vii`

Verify the old `startsWith` false-positive is gone.

- [ ] **Step 1: Tag a playlist `unit:9`, load exercise containing `VI` chord**

In browser console after loading a Unit 9 exercise, find a window where `answer === 'VI'` and confirm the slot is hidden.

If no `VI` chord is visible in the current exercise, find one via the browser console. Problems are generated client-side from the score timeline, not stored in `Exercise.data` — the Django shell cannot inspect them. Instead, add a temporary log in `buildChoraleIdentificationProblems` at `exercise_definition.js:398` to dump all answer strings for the loaded exercise:

```javascript
console.log('[ALL_ANSWERS]', _.map(problems, function(p) { return p.answer; }));
```

Load exercises until you see one with a `VI` answer in the console output. Then remove the log.

- [ ] **Step 2: Confirm in console**

Open the exercise with a `VI` chord. In DevTools, add breakpoint or log inside `applySkillFilter` loop:

```javascript
// Temporarily add inside the _.map callback:
console.log('[FILTER]', p.answer, '→', allowed.indexOf(p.answer) === -1 ? 'HIDDEN' : 'VISIBLE');
```

Expected: `VI → HIDDEN` when `unitNum = 9`.

- [ ] **Step 3: Remove temporary log**

---

### Task 6: Commit

- [ ] **Step 1: Stage and commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat(exercise-filter): replace applySkillFilter with UNIT_ALLOWED_ANSWERS map

- Add UNIT_ALLOWED_ANSWERS covering units 9-20 (cumulative per unit)
- Units 19-20 pass through (modulation spans tonal centres)
- Units 21+ pass through (safe fallback)
- analysisType third arg guards non-roman exercises
- Highest unit:N tag wins when multiple unit tags present
- Exact indexOf match fixes V matching VI/vii false positive
- Removes SKILL_CHORD_PATTERNS if unused"
```

---

## Acceptance Criteria Checklist

Before marking complete, verify all of these:

- [ ] Unit 9 playlist: only `I/i/V/V7` slots interactive — all others hidden
- [ ] Unit 11 playlist: `IV`, `ii`, `vi` slots visible; `V/V`, `N6` slots hidden
- [ ] `VI` answer with `unit:9` tag → **hidden** (`VI` not in unit:9 allowlist; old `startsWith('V')` bug falsely showed it)
- [ ] `V` answer with `unit:9` tag → **visible** (`V` is in unit:9 allowlist — confirm it's NOT hidden)
- [ ] `vii°6` answer with `unit:9` tag → **hidden** (not in unit:9 allowlist)
- [ ] Multiple `unit:9` + `unit:11` tags → uses unit 11 allowlist (highest wins)
- [ ] `figured_bass` exercise with `unit:9` tag → all slots visible (analysisType guard)
- [ ] Unit 22 playlist (no map entry) → all slots visible (pass-through)
- [ ] No JS console errors on page load
- [ ] Call site passes `exercise.analysisType` as third arg
