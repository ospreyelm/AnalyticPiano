# Knowledge Graph Tagging Design Document

## Objective
Convert HarmonyLab's un-categorized exercise curriculum into an Adaptive Knowledge Graph, categorized dynamically via `music21` analysis during the mass import process. This allows the app to serve exercises dynamically based on a student's proficiency in specific skills.

## 1. Core Tonal Harmony "Skill Tags"

A starting list of standard, progressively difficult tags that form our initial knowledge graph:

1. **Diatonic_Triads** (Foundation: I, ii, IV, vi, etc.)
2. **Inversions_First** (6 chords)
3. **Inversions_Second** (6/4 chords)
4. **Dominant_Seventh** (V7)
5. **Cadence_Half** (Ending on V)
6. **Cadence_Perfect_Authentic** (Root position V-I)
7. **Cadence_Deceptive** (V-vi)
8. **Cadence_Plagal** (IV-I)
9. **Secondary_Dominant** (e.g., V/V, V/vi)
10. **Secondary_Leading_Tone** (e.g., vii°/V)
11. **Diminished_Seventh** (Fully diminished, vii°7)
12. **Half_Diminished_Seventh** (viiø7)
13. **Neapolitan_Sixth** (N6)
14. **Augmented_Sixth** (It+6, Fr+6, Ger+6)
15. **Picardy_Third** (Major I ending in a minor tonality)
16. **Modulation_Diatonic_Pivot** (Clear key change using pivot chord)

---

## 2. Python / `music21` Import Logic

During `mass_import_performance.py`, we will evaluate the `chunk` score once it is sliced.

We can analyze a `chunk` using `music21`'s `.chordify()` method and the `roman` module in a dedicated function:

```python
from music21 import roman, key

def analyze_chunk_skills(chunk, chunk_key):
    # Initialize the tonal context
    tonal_key = key.Key(chunk_key)
    skills = set()
    
    # Pedagogical complexity: 1-10 scale based on standard collegiate music theory sequence
    # 1: Diatonic Triads, 2: Inversions/7ths, up to 10: Adv Chromaticism/Enharmonics
    complexity = 1  
    
    # Compress the score into a sequence of chords
    chordified = chunk.chordify()
    chords = list(chordified.recurse().getElementsByClass('Chord'))
    
    roman_numerals = []
    
    # 1. Chord-by-Chord Analysis
    for c in chords:
        rn = roman.romanNumeralFromChord(c, tonal_key)
        roman_numerals.append(rn)
        
        # Check if triad is diatonic or contains altered tones
        key_pcs = {kp.pitchClass for kp in tonal_key.pitches}
        is_diatonic = all(p.pitchClass in key_pcs for p in rn.pitches)
        
        if is_diatonic and rn.isConsonant():
            skills.add("Diatonic_Triads")
            
        if rn.isDominantSeventh():
            skills.add("Dominant_Seventh")
            complexity = max(complexity, 2)
            
        # Detect applied/secondary chords via chromaticism matching dominant/leading-tone qualities
        if not is_diatonic and (rn.isDominantSeventh() or rn.isMajorTriad()):
            skills.add("Secondary_Dominant")
            complexity = max(complexity, 5)
        elif not is_diatonic and (rn.isDiminishedSeventh() or rn.isHalfDiminishedSeventh()):
            skills.add("Secondary_Leading_Tone")
            complexity = max(complexity, 5)
            
        if rn.isAugmentedSixth():
            skills.add("Augmented_Sixth")
            complexity = max(complexity, 8)
            
        # Safely verify Neapolitan API function
        if hasattr(rn, 'isNeapolitan') and rn.isNeapolitan():
            skills.add("Neapolitan_Sixth")
            complexity = max(complexity, 7)
            
        # Inversions checks (music21 returns 0 for root pos, 1 for 1st inv, None if unknown)
        inv = rn.inversion()
        if inv == 1:
            skills.add("Inversions_First")
            complexity = max(complexity, 2)
        elif inv == 2:
            skills.add("Inversions_Second")
            complexity = max(complexity, 3)

    # 2. Sequential / Cadential Analysis
    if len(roman_numerals) >= 2:
        penult = roman_numerals[-2]
        ult = roman_numerals[-1]
        
        # Perfect Authentic Cadence: V -> I
        if penult.scaleDegree == 5 and ult.scaleDegree == 1:
            if penult.inversion() == 0 and ult.inversion() == 0:
                skills.add("Cadence_Perfect_Authentic")
                
        # Plagal Cadence: IV -> I
        if penult.scaleDegree == 4 and ult.scaleDegree == 1:
            skills.add("Cadence_Plagal")
            complexity = max(complexity, 2)
            
        # Deceptive Cadence: V -> vi
        if penult.scaleDegree == 5 and ult.scaleDegree in [6, -6]:
            skills.add("Cadence_Deceptive")
            complexity = max(complexity, 3)
                
        # Half Cadence: phrase finishes on V
        if ult.scaleDegree == 5 and ult.isMajorTriad():
            skills.add("Cadence_Half")
            complexity = max(complexity, 2)
            
        # Picardy Third
        if tonal_key.mode == 'minor' and ult.scaleDegree == 1 and ult.isMajorTriad():
            skills.add("Picardy_Third")
            complexity = max(complexity, 6)
            
    return list(skills), complexity
```

---

## 3. Django `Exercise` Model Updates

We need to be able to instantly query against the database to fetch exercises for a student depending on their current mastery level in the knowledge graph. 

Because of Django and PostgreSQL's powerful support for array fields, we can bypass complex Many-To-Many relationships in favor of extreme performance. The existing `Exercise` model has a purely visual `tags` ArrayField, but we will create dedicated fields explicitly for the knowledge graph.

**Updates to `apps/exercises/models.py`:**

```python
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.fields import ArrayField

class Exercise(ClonableModelMixin, BaseContentModel):
    # ... existing fields ...
    
    # New Field 1: Array of skill strings generated by import script
    skill_tags = ArrayField(
        base_field=models.CharField(max_length=64),
        default=list,
        blank=True,
        verbose_name="Skill Tags",
        help_text="Knowledge Graph skills detected in the chunk (e.g. Secondary_Dominant)"
    )
    
    # New Field 2: Calculated pedagogical complexity
    complexity = models.PositiveSmallIntegerField(
        default=1,
        help_text="Calculated integer 1-10 representing harmony complexity"
    )

    class Meta:
        verbose_name = "Exercise"
        verbose_name_plural = "Exercises"
        # Require a GIN Index on the skill_tags array and B-Tree on complexity for lightning-fast lookups
        indexes = [
            GinIndex(fields=['skill_tags']),
            models.Index(fields=['complexity']),
        ]
```

**Fast Querying Examples:**
*   `Exercise.objects.filter(skill_tags__contains=['Secondary_Dominant'])`
*   `Exercise.objects.filter(skill_tags__contains=['Cadence_Perfect_Authentic'], complexity__lte=3)`

### Database Migration & Backfilling

To backfill existing historically imported exercises in `HarmonyLab` without timing out the server or requiring manual work:

```python
# Provide a Django management command to process existing DB rows in batches:
from apps.exercises.models import Exercise
from django.core.paginator import Paginator

def backfill_exercises():
    exercises = Exercise.objects.filter(skill_tags=[])
    paginator = Paginator(exercises, 1000)
    
    for page_num in paginator.page_range:
        for ex in paginator.page(page_num).object_list:
            # Convert JSON data back into a music21 stream/score to analyze
            # (Requires existing dict -> music21 builder utility)
            try:
                from apps.exercises.utils.music21_builder import build_score_from_data
                chunk_score = build_score_from_data(ex.data)
                detected_skills, detected_complexity = analyze_chunk_skills(
                    chunk_score, 
                    ex.data.get('key', 'C')
                )
            except Exception as e:
                # Log parsing errors and skip
                continue
            
            ex.skill_tags = detected_skills
            ex.complexity = detected_complexity
            ex.save(update_fields=['skill_tags', 'complexity'])
```

---

## 4. "On-The-Fly" Transposition Layer

When the Knowledge Graph system dictates it's time for a student to practice "Secondary_Dominants", we shouldn't have to pre-generate DB objects in every key. 

Instead, the workflow leverages the existing `transpose` utility natively built into the app:

1. **Student State Check:** The student requests another exercise. The Adaptive Engine checks its mastery graph and determines the student is ready to see `Secondary_Dominant` but needs practice in unfamiliar keys like `G Major` and `D Major`.
2. **Query Base Exercise:** System fetches a random exercise matching the skill:
   `ex = Exercise.objects.filter(skill_tags__contains=['Secondary_Dominant'], complexity__lte=5).order_by('?').first()`
3. **Execute Transposition on Selection:** The base exercise happens to be stored natively in `F Major`. The Adaptive Engine invokes the transposition utility:
   ```python
   from apps.exercises.utils.transpose import transpose
   
   # Let's dynamically shift the requested key (e.g. G Major = 1 sharp)
   # staff_sig_request = 1 
   transposed_ex = transpose(ex, staff_sig_request=1)
   ```
4. **Deliver to Student:** The `transpose` function logically calculates the interval difference between the base key (`F Major`) and target key (`G Major`). The utility inherently handles edge cases (like key signature wrapping bounds, enharmonic spelling shifts, and resolving correct accidentals logically within that mode's constraints). It then shifts all core components (`keySignature` and the raw `chord` pitches) within the `data` JSON property, serving the dynamically-generated version directly to the client without ever saving a redundant, duplicated exercise row permanently to the database.
