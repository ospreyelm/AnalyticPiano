# HarmonyLab Adaptive Engine — Design Specification

**Status:** Draft  
**Date:** 2026-04-17  
**Branch:** feature/music21_builder (foundation complete)

---

## Objective

Transform HarmonyLab from a static playlist system into an adaptive learning engine modeled on Khan Academy's mastery system, with an LMS layer for formal courses. Students progress through tonal harmony skills dynamically. Teachers retain curriculum control.

---

## Two Operating Modes

### Mode A: Formal Course (LMS)
- Teacher creates a course via a setup wizard
- Defines: required skills, skill order, pacing, homework due dates
- Students see assigned homework + adaptive practice pool
- Teacher gets per-student, per-skill gradebook
- Completion tracked against due dates (Artusi-style accountability)

### Mode B: Self-Guided (Khan-style)
- Student sees visual skill map
- Picks any unlocked skill node to practice
- System warns when student jumps over prerequisites
- No due dates, pure mastery progression
- Skills unlock downstream nodes on mastery

---

## Skill Graph (Knowledge Graph)

### Design Principle

The skill graph is the foundation of the entire adaptive system. Every skill node must be:
1. **Teachable** — maps to a distinct concept students can learn
2. **Assessable** — HarmonyLab can currently (or feasibly could) exercise and auto-grade it
3. **Prerequisite-linked** — has a clear "must know X before Y" relationship

Skills are organized into tiers. Within a tier, order is flexible (teacher chooses). Across tiers, the DAG enforces prerequisites.

---

### Comprehensive Skill Taxonomy

Status key:
- ✅ **Built** — exercisable and auto-graded today
- 🔧 **Infra exists** — analysis/display exists, no graded exercise type yet
- 📋 **Planned** — on roadmap, would require new exercise type
- 🚫 **Out of scope** — requires audio input, hardware, or major new system

---

#### TIER 0 — Music Literacy (Pre-Theory)

**Staff Reading**
| Skill Tag | Status | Notes |
|---|---|---|
| `Read_Treble_Clef` | ✅ | pitch identification exercise (`note_name` analysisType) |
| `Read_Bass_Clef` | ✅ | pitch identification exercise |
| `Ledger_Lines` | ✅ | pitch identification with ledger line notes |
| `Alto_Clef` | 📋 | would need new clef in vexflow + exercise type |
| `Tenor_Clef` | 📋 | same |

**Pitch Naming**
| Skill Tag | Status | Notes |
|---|---|---|
| `Note_Names` | ✅ | `note_name` analysisType |
| `Solfege_Movable` | ✅ | `solfege` / `do_based_solfege` analysisType |
| `Solfege_Fixed` | ✅ | `fixed_do` analysisType |
| `Scale_Degrees` | ✅ | `scale_degree` analysisType |
| `Pitch_Class` | ✅ | `pitch_class` analysisType |

**Intervals**
| Skill Tag | Status | Notes |
|---|---|---|
| `Interval_Generic` | ✅ | `interval_generic` analysisType |
| `Interval_Specific` | ✅ | `interval_specific` analysisType |
| `Interval_Compound` | ✅ | `compoundIntervals: true` flag |
| `Interval_Inversion` | 📋 | identify inversion of a given interval |

**Rhythm and Meter** *(all 📋 — no graded rhythm exercise type yet)*
| Skill Tag | Status | Notes |
|---|---|---|
| `Rhythm_Simple_Meter` | 📋 | note values, rests, dots/ties in 2/4, 3/4, 4/4 |
| `Rhythm_Compound_Meter` | 📋 | 6/8, 9/8, 12/8 |
| `Rhythm_Syncopation` | 📋 | off-beat patterns |
| `Rhythm_Tuplets` | 📋 | triplets, quintuplets |
| `Rhythm_Odd_Meter` | 📋 | 5/4, 7/8, etc. |

**Key Signatures and Scales** *(all 📋)*
| Skill Tag | Status | Notes |
|---|---|---|
| `Key_Signatures` | 📋 | identify major/minor key from signature |
| `Major_Scale` | 📋 | spell or identify major scale |
| `Natural_Minor_Scale` | 📋 | natural minor |
| `Harmonic_Minor_Scale` | 📋 | harmonic minor |
| `Melodic_Minor_Scale` | 📋 | melodic minor |
| `Circle_Of_Fifths` | 📋 | navigate key relationships |

---

#### TIER 1 — Diatonic Harmony Foundation

**Chords and Roman Numerals**
| Skill Tag | Status | Notes |
|---|---|---|
| `Diatonic_Triads` | ✅ | existing skill; all 7 diatonic triads in major/minor |
| `Inversions_First` | ✅ | existing skill; 6-chords |
| `Inversions_Second` | ✅ | existing skill; 6/4 chords |
| `Dominant_Seventh` | ✅ | existing skill; V7 detection |
| `Diatonic_Sevenths` | 🔧 | ii7, iii7, IV7 etc.; music21_builder can generate them |
| `Figured_Bass_Reading` | ✅ | `figured_bass` exercise type exists |

**Cadences**
| Skill Tag | Status | Notes |
|---|---|---|
| `Cadence_Perfect_Authentic` | ✅ | existing skill |
| `Cadence_Half` | ✅ | existing skill |
| `Cadence_Deceptive` | ✅ | existing skill |
| `Cadence_Plagal` | ✅ | existing skill |
| `Cadence_Imperfect_Authentic` | 📋 | IAC — V to I with soprano not on 1̂ |

**Harmonic Function**
| Skill Tag | Status | Notes |
|---|---|---|
| `Harmonic_Function` | 📋 | label T/PD/D function of chords in a progression |
| `Non_Chord_Tones` | 📋 | identify PT, NT, SUS, ANT in a score |

---

#### TIER 2 — Intermediate Harmony

**Chromatic Harmony**
| Skill Tag | Status | Notes |
|---|---|---|
| `Secondary_Dominant` | ✅ | existing skill |
| `Secondary_Leading_Tone` | ✅ | existing skill |
| `Diminished_Seventh` | ✅ | (currently detected as part of secondary analysis) |
| `Half_Diminished_Seventh` | ✅ | (same) |
| `Picardy_Third` | ✅ | existing skill |
| `Modal_Mixture` | 📋 | borrowed chords (bVI, bIII, iv in major) |

**Advanced Chromatic**
| Skill Tag | Status | Notes |
|---|---|---|
| `Neapolitan_Sixth` | ✅ | existing skill |
| `Augmented_Sixth` | ✅ | existing skill (It+6, Fr+6, Ger+6 — not differentiated yet) |
| `Augmented_Sixth_Italian` | 📋 | sub-type of Augmented_Sixth |
| `Augmented_Sixth_French` | 📋 | sub-type |
| `Augmented_Sixth_German` | 📋 | sub-type |
| `Modulation_Diatonic_Pivot` | ✅ | existing skill |
| `Modulation_Chromatic` | 📋 | enharmonic / chromatic pivot modulation |
| `Common_Tone_Dim7` | 📋 | CT°7 as embellishing chord |

---

#### TIER 3 — Voice Leading and Counterpoint

**SATB Voice Leading** *(all 📋 — music21 voiceLeading module available but not hooked up)*
| Skill Tag | Status | Notes |
|---|---|---|
| `Voice_Leading_Basic` | 📋 | no parallel 5ths/8ths, voice range, spacing |
| `Voice_Leading_Triads` | 📋 | 4-part triads with proper doubling |
| `Voice_Leading_Sevenths` | 📋 | resolve 7ths correctly in 4-part |
| `Voice_Leading_Chromatic` | 📋 | chromatic chords in 4-part texture |
| `Figured_Bass_Realization` | 📋 | realize a figured bass in 4 parts |

**Species Counterpoint** *(all 📋 — significant new system needed)*
| Skill Tag | Status | Notes |
|---|---|---|
| `Counterpoint_First_Species` | 📋 | 1:1 note-against-note |
| `Counterpoint_Second_Species` | 📋 | 2:1 |
| `Counterpoint_Third_Species` | 📋 | 4:1 |
| `Counterpoint_Fourth_Species` | 📋 | suspensions |
| `Counterpoint_Fifth_Species` | 📋 | florid |

---

#### TIER 3 — Set Theory and Post-Tonal

| Skill Tag | Status | Notes |
|---|---|---|
| `Pitch_Class_Sets` | 🔧 | set_class_set/normal/prime display exists; no graded exercise yet |
| `Normal_Order` | 🔧 | analysis engine exists (`to_set_class_normal`) |
| `Prime_Form` | 🔧 | analysis engine exists (`to_set_class_prime`) |
| `Forte_Numbers` | 🔧 | full 224-set Forte table embedded |
| `Interval_Class_Vector` | 📋 | would need new analysis function |
| `Tn_TnI_Operations` | 📋 | transposition and inversion of sets |
| `Twelve_Tone_Row` | 📋 | P/I/R/RI matrix; significant new system |

---

#### TIER 3 — Jazz and Popular Music

| Skill Tag | Status | Notes |
|---|---|---|
| `Lead_Sheet_Symbols` | 🔧 | `chord_labels` display exists in overlay; no graded ID exercise yet |
| `Jazz_Seventh_Chords` | 🔧 | `hChords-pop.js` covers maj7, m7, 7, ø7, °7 etc. |
| `Extended_Chords` | 🔧 | 9ths, 11ths, 13ths in hChords.js |
| `Altered_Dominants` | 📋 | b9, #9, b13, #11 — need analysis engine |
| `ii_V_I` | 📋 | identify or realize ii–V–I progression |
| `Tritone_Substitution` | 📋 | advanced jazz theory |
| `Blues_Harmony` | 📋 | 12-bar blues, blues scale |
| `Pop_Schemas` | 📋 | I–V–vi–IV, lament bass, etc. |
| `Modal_Schemas` | 📋 | Dorian vamp, Mixolydian patterns |

---

#### TIER 4 — Diatonic Modes

| Skill Tag | Status | Notes |
|---|---|---|
| `Mode_Dorian` | 📋 | identify / spell Dorian mode |
| `Mode_Phrygian` | 📋 | |
| `Mode_Lydian` | 📋 | |
| `Mode_Mixolydian` | 📋 | |
| `Mode_Aeolian` | 📋 | natural minor = Aeolian |
| `Mode_Locrian` | 📋 | |

---

#### TIER 4 — Form Analysis *(all 📋 — no interactive form analysis yet)*

| Skill Tag | Status | Notes |
|---|---|---|
| `Phrase_Period` | 📋 | identify antecedent/consequent |
| `Phrase_Sentence` | 📋 | presentation + continuation |
| `Binary_Form` | 📋 | simple and rounded binary |
| `Ternary_Form` | 📋 | ABA |
| `Sonata_Form` | 📋 | exposition/development/recapitulation |
| `Pop_Form` | 📋 | verse/chorus/bridge analysis |
| `Galant_Schemas` | 📋 | Romanesca, Monte, Fonte etc. |

---

#### Ear Training *(all 🚫 — requires audio input/microphone)*

| Skill Tag | Status | Notes |
|---|---|---|
| `Melodic_Dictation` | 🚫 | audio input not implemented |
| `Harmonic_Dictation` | 🚫 | same |
| `Rhythmic_Dictation` | 🚫 | same |
| `Sight_Singing` | 🚫 | requires pitch detection |
| `Interval_Ear_Training` | 🚫 | audio playback-then-ID not implemented |

---

### Default Prerequisite DAG

```
TIER 0
  Read_Treble_Clef ─────────────┐
  Read_Bass_Clef  ─────────────┤
                                ↓
  Note_Names ──────────────────→ Interval_Generic → Interval_Specific
                                                          ↓
  Solfege_Movable ← Note_Names                    Interval_Compound
  Scale_Degrees   ← Note_Names

TIER 1
  Diatonic_Triads ←── Interval_Specific
     ├──→ Inversions_First → Inversions_Second
     ├──→ Dominant_Seventh → Diatonic_Sevenths
     ├──→ Cadence_Plagal
     └──→ Figured_Bass_Reading

  Cadence_Half ←── Dominant_Seventh
  Cadence_Perfect_Authentic ←── Cadence_Half
  Cadence_Deceptive ←── Cadence_Perfect_Authentic
  Cadence_Imperfect_Authentic ←── Cadence_Perfect_Authentic

TIER 2
  Secondary_Dominant ←── Cadence_Perfect_Authentic
  Secondary_Leading_Tone ←── Secondary_Dominant, Diminished_Seventh
  Diminished_Seventh ←── Dominant_Seventh
  Half_Diminished_Seventh ←── Diminished_Seventh
  Picardy_Third ←── Cadence_Perfect_Authentic
  Modal_Mixture ←── Secondary_Dominant
  Neapolitan_Sixth ←── Secondary_Dominant
  Augmented_Sixth ←── Neapolitan_Sixth
  Modulation_Diatonic_Pivot ←── Secondary_Dominant
  Modulation_Chromatic ←── Augmented_Sixth, Modulation_Diatonic_Pivot
  Common_Tone_Dim7 ←── Diminished_Seventh

TIER 3
  Voice_Leading_Basic ←── Diatonic_Triads
  Voice_Leading_Triads ←── Voice_Leading_Basic
  Voice_Leading_Sevenths ←── Voice_Leading_Triads, Diatonic_Sevenths
  Voice_Leading_Chromatic ←── Voice_Leading_Sevenths, Modal_Mixture

  Counterpoint_First_Species ←── Interval_Specific
  Counterpoint_Second_Species ←── Counterpoint_First_Species
  Counterpoint_Third_Species ←── Counterpoint_Second_Species
  Counterpoint_Fourth_Species ←── Counterpoint_Third_Species
  Counterpoint_Fifth_Species ←── Counterpoint_Fourth_Species

  Pitch_Class_Sets ←── Pitch_Class
  Normal_Order ←── Pitch_Class_Sets
  Prime_Form ←── Normal_Order
  Forte_Numbers ←── Prime_Form

  Lead_Sheet_Symbols ←── Diatonic_Triads
  Jazz_Seventh_Chords ←── Lead_Sheet_Symbols, Diatonic_Sevenths
  Extended_Chords ←── Jazz_Seventh_Chords
  ii_V_I ←── Jazz_Seventh_Chords, Secondary_Dominant

TIER 4
  Mode_Dorian ←── Natural_Minor_Scale
  Mode_Mixolydian ←── Major_Scale
  (other modes ←── respective scale types)

  Galant_Schemas ←── Cadence_Perfect_Authentic, Modulation_Diatonic_Pivot
  Pop_Form ←── Phrase_Period
  Sonata_Form ←── Binary_Form, Phrase_Sentence
```

### Teacher Override
In a formal course, teacher can reorder skill nodes or add/remove prerequisites via the course wizard. The default DAG is the starting point.

### What to Build First (MVP Skill Set)

For Phase 2 implementation, focus on skills that are:
1. Already ✅ Built (16 existing tonal harmony tags)
2. Already ✅ Built (5 pitch naming tags: Note_Names, Solfege_Movable, Solfege_Fixed, Scale_Degrees, Pitch_Class)
3. Already ✅ Built (3 interval tags: Interval_Generic, Interval_Specific, Interval_Compound)
4. Already ✅ Built (2 clef tags: Read_Treble_Clef, Read_Bass_Clef)

**MVP = 26 fully-exercisable skill nodes.** All others are roadmap.

The mastery engine, DAG, and StudentSkillMastery model should be designed to accommodate the full taxonomy — just populate only the MVP nodes at launch.

---

## Mastery System (Khan-style)

### Five Levels

| Level | Display | Trigger |
|---|---|---|
| `not_started` | ○ Not Started | 0 attempts |
| `attempted` | ◔ Attempted | Any attempt on a skill exercise |
| `familiar` | ◑ Familiar | 3 correct out of last 5 attempts |
| `proficient` | ◕ Proficient | 7 correct out of last 10 attempts |
| `mastered` | ● Mastered | 10 correct out of last 10 + on 2+ separate calendar days |

### Skill Unlock
A skill node unlocks for practice when ALL prerequisite skills are at `familiar` or above.

A skill node is considered **complete** for course purposes when `mastered`.

### Decay (Skill Fade)
Music skills fade faster than math facts. If a student does not practice a skill:
- `mastered` → `proficient` after **60 days** of no practice
- `proficient` → `familiar` after **30 days** of no practice
- `familiar` → `attempted` after **14 days** of no practice

Decay is computed on page load (no background jobs needed — just compare `last_practiced + decay_threshold < now()`).

### What Counts as a "Correct Attempt"
For each exercise attempt, map to correct/incorrect:
- **Chorale play:** `error_tally == 0` → correct
- **Chorale identification:** `score >= passing_threshold` → correct (threshold TBD, suggest 80%)
- An exercise attempt affects **ALL** skill nodes in its `skill_tags` list

### Exercise Type Weighting
Teacher-configurable per course. Default weight = 1.0 for all exercise types.
Teacher can set identification weight (e.g. 0.7) vs play weight (1.0) in course settings.
Weight affects how quickly the attempt window fills: a weight-0.7 attempt counts as 0.7 toward the rolling history window (rounded to nearest integer for threshold checks).
Simple v1 implementation: just store a `exercise_type_weight` float on the Course model and multiply before threshold comparison.

### Key Tracking
Global per skill (not per key). Transposition layer handles key variety in exercise serving. One `StudentSkillMastery` row per student per skill.

### Recent History Window
Store last 10 attempts per skill per user as a rolling boolean list `[True, False, True, ...]`.
Level is recomputed after each attempt.

---

## Data Model

### New: `StudentSkillMastery`

```python
class StudentSkillMastery(models.Model):
    user            = models.ForeignKey(User, on_delete=models.CASCADE)
    skill_tag       = models.CharField(max_length=64)  # e.g. "Secondary_Dominant"

    # Mastery state
    level           = models.CharField(max_length=16, default='not_started')
    recent_history  = models.JSONField(default=list)   # last 10 booleans
    total_correct   = models.IntegerField(default=0)
    total_attempts  = models.IntegerField(default=0)
    practice_days   = models.JSONField(default=list)   # list of date strings (for "2+ days" check)

    # Timestamps
    last_practiced  = models.DateTimeField(null=True, blank=True)
    mastered_at     = models.DateTimeField(null=True, blank=True)
    first_attempted = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'skill_tag')
        indexes = [
            models.Index(fields=['user', 'level']),
            models.Index(fields=['user', 'last_practiced']),
        ]
```

### New: `SkillPrerequisite`
Stores the DAG edges (default + teacher overrides):

```python
class SkillPrerequisite(models.Model):
    course          = models.ForeignKey('Course', null=True, blank=True, on_delete=models.CASCADE)
    skill_tag       = models.CharField(max_length=64)
    requires_tag    = models.CharField(max_length=64)
    # course=None means "default global DAG"

    class Meta:
        unique_together = ('course', 'skill_tag', 'requires_tag')
```

### Modified: `Playlist`
Add `is_adaptive` BooleanField (already planned):
```python
is_adaptive = models.BooleanField(default=False)
```

### Modified: `ExercisePlaylistOrdered`
Add `is_adaptive_entry` BooleanField (already planned):
```python
is_adaptive_entry = models.BooleanField(default=False)
```

### Modified: `Course`
Add course-level adaptive settings:
```python
adaptive_mode       = models.BooleanField(default=False)
required_skills     = ArrayField(CharField(max_length=64), default=list)
mastery_threshold   = models.CharField(max_length=16, default='mastered')
```

---

## Mastery Computation

```python
def compute_mastery_level(history: list[bool], practice_days: list[str]) -> str:
    """history = last 10 booleans, practice_days = unique calendar dates practiced."""
    attempts = len(history)
    if attempts == 0:
        return 'not_started'
    
    correct_last_5  = sum(history[-5:])
    correct_last_10 = sum(history[-10:])
    
    if correct_last_10 >= 10 and len(set(practice_days[-10:])) >= 2:
        return 'mastered'
    if correct_last_10 >= 7:
        return 'proficient'
    if correct_last_5 >= 3:
        return 'familiar'
    return 'attempted'

def compute_decay(mastery: StudentSkillMastery) -> str:
    """Apply time-based decay. Call on page load."""
    if mastery.last_practiced is None or mastery.level == 'not_started':
        return mastery.level
    days_idle = (now() - mastery.last_practiced).days
    level = mastery.level
    if level == 'mastered'  and days_idle > 60: level = 'proficient'
    if level == 'proficient' and days_idle > 30: level = 'familiar'
    if level == 'familiar'  and days_idle > 14: level = 'attempted'
    return level

def record_attempt(user_id, skill_tag, correct: bool):
    """Called after every exercise submission. Updates StudentSkillMastery."""
    mastery, _ = StudentSkillMastery.objects.get_or_create(
        user_id=user_id, skill_tag=skill_tag
    )
    today = date.today().isoformat()
    history = mastery.recent_history[-9:] + [correct]  # rolling window of 10
    days = mastery.practice_days if today in mastery.practice_days else mastery.practice_days + [today]
    
    mastery.recent_history  = history
    mastery.practice_days   = days[-30:]  # keep last 30 days max
    mastery.total_attempts  += 1
    mastery.total_correct   += int(correct)
    mastery.last_practiced  = now()
    if mastery.first_attempted is None:
        mastery.first_attempted = now()
    
    new_level = compute_mastery_level(history, days)
    if new_level == 'mastered' and mastery.level != 'mastered':
        mastery.mastered_at = now()
    mastery.level = new_level
    mastery.save()
```

---

## Exercise Selection (Adaptive Serving)

When serving next exercise to a student in adaptive mode:

```python
def get_next_exercise(user_id, playlist_or_course):
    acquired_skills = StudentSkillMastery.objects.filter(
        user_id=user_id,
        level__in=['familiar', 'proficient', 'mastered']
    ).values_list('skill_tag', flat=True)

    # Exercises where ALL skill_tags are in student's acquired set
    eligible = Exercise.objects.filter(
        skill_tags__contained_by=list(acquired_skills),
        skill_tags__len__gt=0
    )

    # Filter to playlist/course pool
    pool_ids = playlist_or_course.exercise_ids()
    eligible = eligible.filter(id__in=pool_ids)

    # Exclude already mastered skills (prioritize weakest skill)
    # TODO: prioritize exercises that target skills closest to next level up
    return eligible.order_by('?').first()
```

---

## Integration Points

### Performance Submission Hook
In `apps/exercises/views.py` → `submit_exercise_performance()`, after saving `PerformanceData`:

```python
# Update StudentSkillMastery for each skill in the exercise
exercise = Exercise.objects.get(id=exercise_id)
correct = (performance_data.get('error_tally') in (0, -1, 'n/a'))
for skill_tag in exercise.skill_tags:
    record_attempt(request.user.id, skill_tag, correct)
```

Same hook for `IdentificationAttempt` submission.

### Skill Unlock Check
```python
def get_unlocked_skills(user_id, course=None) -> list[str]:
    """Return skill tags the student is eligible to practice."""
    prereqs = SkillPrerequisite.objects.filter(
        models.Q(course=course) | models.Q(course=None)
    ).values('skill_tag', 'requires_tag')
    
    acquired = set(StudentSkillMastery.objects.filter(
        user_id=user_id,
        level__in=['familiar', 'proficient', 'mastered']
    ).values_list('skill_tag', flat=True))
    
    unlocked = []
    for skill in ALL_SKILL_TAGS:
        required = {p['requires_tag'] for p in prereqs if p['skill_tag'] == skill}
        if required.issubset(acquired):
            unlocked.append(skill)
    return unlocked
```

---

## Teacher Course Wizard (LMS Mode)

Multi-step form flow:

**Step 1 — Course basics**
- Course title, description
- Toggle: Formal course (LMS) vs Open practice

**Step 2 — Skill selection**
- Checkbox list of 16 skills (ordered by default DAG)
- Teacher checks which skills are required for course completion
- Optionally drag-and-drop to reorder (overrides DAG for this course)

**Step 3 — Pacing**
- Weeks/semester length
- Homework days per week (e.g. Mon/Wed/Fri)
- Auto-generate due dates per skill based on pace
- Or: manual due date per skill

**Step 4 — Mastery threshold**
- Required level for "complete": Familiar / Proficient / Mastered
- Default: Mastered

**Step 5 — Exercise pool**
- System auto-suggests exercises matching course skills
- Teacher can add/remove exercises from pool
- Teacher marks entry-point exercises (for day-one students)

---

## Student Skill Map UI

Visual display of skill graph for students:

- **Node states:** gray (locked), blue (unlocked/not started), yellow (familiar), orange (proficient), green (mastered), red (due for review / decayed)
- **Click node:** opens practice session for that skill
- **Prerequisites shown:** hover shows "unlock by mastering X, Y"
- **Course mode overlay:** shows due dates per node, HW badge

---

## Gradebook (LMS Mode)

Teacher sees table: rows = students, columns = skills.
Each cell shows mastery level (color-coded) + date achieved.
Filter by: skill, mastery level, due date status.

---

## Transposition Integration

Exercises are stored in one key but served in others via existing `transpose()` utility.
For adaptive serving: after selecting an exercise, randomly select target key from student's "unfamiliar keys" set (tracked separately or derived from practice history).

---

## Implementation Phases

### Phase 1 — Foundation (current)
✅ `skill_tags` + `complexity` on Exercise model  
✅ `skills_analyzer.py` (music21 auto-tagging)  
✅ `backfill_skill_tags` management command  
✅ GIN index on skill_tags  

### Phase 2 — Mastery Engine
- `StudentSkillMastery` model + migration
- `SkillPrerequisite` model + migration (with default DAG seeder)
- `compute_mastery_level()` + `compute_decay()` + `record_attempt()` functions
- Hook `record_attempt()` into performance submission
- Tests: mastery level computation, decay, unlock logic

### Phase 3 — Adaptive Serving
- `Playlist.is_adaptive` + `ExercisePlaylistOrdered.is_adaptive_entry` (migrations)
- Modify `PlaylistView` + `RefreshExerciseDefinition` for adaptive mode
- `get_next_exercise()` function
- Submit by `exercise_id` for adaptive playlists
- Pool-exhausted state handling

### Phase 4 — Student Skill Map UI
- Skill map template (graph visualization)
- Per-node mastery level display
- Unlock state logic
- "Due for review" badges

### Phase 5 — Teacher Course Wizard (LMS)
- Multi-step course creation form
- Skill selection + ordering UI
- Pacing + due date generation
- Exercise pool management
- Gradebook view

### Phase 6 — Self-Guided Mode
- Student dashboard with skill graph
- Jump-ahead warning ("you're missing prerequisites: X, Y")
- Suggested next skill based on current mastery state

---

## Open Questions

1. **Identification exercises vs play exercises** — do both contribute to skill mastery equally? Or should identification be weighted less (easier)?
2. **Passing threshold for identification** — `score >= 80%`? Teacher-configurable?
3. **Multi-skill exercises** — an exercise tagged with 4 skills updates all 4 nodes. Is this correct, or should it only update the "primary" skill?
4. **Key tracking** — should we track mastery per skill per key (e.g. Secondary_Dominant in C vs in F#), or just per skill globally?
5. **Course wizard tech** — multi-step Django form vs single-page JS wizard?

---

## Files to Create/Modify (Phase 2+)

| File | Action |
|---|---|
| `apps/exercises/models.py` | Add `StudentSkillMastery`, `SkillPrerequisite`, modify `Course` |
| `apps/exercises/mastery.py` | New: `compute_mastery_level`, `compute_decay`, `record_attempt`, `get_unlocked_skills` |
| `apps/exercises/skill_graph.py` | New: default DAG definition + `ALL_SKILL_TAGS` constant |
| `apps/exercises/migrations/0058_*.py` | New fields migration |
| `apps/exercises/views.py` | Hook `record_attempt` into submission |
| `lab/views.py` | Adaptive serving in `PlaylistView` + `RefreshExerciseDefinition` |
| `apps/dashboard/views/courses.py` | Course wizard (Phase 5) |
| `lab/templates/lab/skill_map.html` | Student skill map (Phase 4) |
| `apps/exercises/tests/test_mastery.py` | Mastery computation tests |
