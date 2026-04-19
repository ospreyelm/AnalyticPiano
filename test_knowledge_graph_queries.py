#!/usr/bin/env python
"""
Test script to verify skill_tags queries work on Exercise model.
Run from project root: python test_knowledge_graph_queries.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'harmony.settings.local')
django.setup()

from apps.exercises.models import Exercise
from collections import Counter

print("\n" + "="*70)
print("KNOWLEDGE GRAPH QUERY TESTS")
print("="*70 + "\n")

# Test 1: Count exercises with tags
print("TEST 1: Exercises with skill tags")
with_tags = Exercise.objects.exclude(skill_tags=[])
print(f"  Total with tags: {with_tags.count()}")
print(f"  Total without tags: {Exercise.objects.filter(skill_tags=[]).count()}")
print(f"  Total exercises: {Exercise.objects.count()}\n")

# Test 2: Single skill filter
print("TEST 2: Filter by single skill (Diatonic_Triads)")
diatonic = Exercise.objects.filter(skill_tags__contains=['Diatonic_Triads'])
print(f"  Count: {diatonic.count()}")
if diatonic.exists():
    ex = diatonic.first()
    print(f"  Example: {ex.id} - {ex.description}")
    print(f"    Skills: {ex.skill_tags}")
    print(f"    Complexity: {ex.complexity}\n")

# Test 3: Multiple skills filter
print("TEST 3: Filter by multiple skills (Diatonic_Triads AND Cadence_Perfect_Authentic)")
multi = Exercise.objects.filter(
    skill_tags__contains=['Diatonic_Triads', 'Cadence_Perfect_Authentic']
)
print(f"  Count: {multi.count()}")
if multi.exists():
    for ex in multi[:2]:
        print(f"  - {ex.id}: {ex.skill_tags}")
print()

# Test 4: Complexity filter
print("TEST 4: Filter by complexity range (complexity <= 3)")
low_complexity = Exercise.objects.filter(complexity__lte=3)
print(f"  Count: {low_complexity.count()}")
complexity_dist = Counter(low_complexity.values_list('complexity', flat=True))
for c in sorted(complexity_dist.keys()):
    print(f"    Complexity {c}: {complexity_dist[c]} exercises")
print()

# Test 5: Specific secondary dominant
print("TEST 5: Filter by skill with complexity (Secondary_Dominant, complexity >= 5)")
secondary = Exercise.objects.filter(
    skill_tags__contains=['Secondary_Dominant'],
    complexity__gte=5
)
print(f"  Count: {secondary.count()}")
if secondary.exists():
    for ex in secondary[:2]:
        print(f"  - {ex.id}: skills={ex.skill_tags}, complexity={ex.complexity}")
print()

# Test 6: All unique skills
print("TEST 6: Distribution of all skill tags")
all_tags = []
for ex in with_tags:
    all_tags.extend(ex.skill_tags)

tag_counts = Counter(all_tags)
print(f"  Unique skills found: {len(tag_counts)}")
for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
    print(f"    {tag}: {count}")
print()

# Test 7: Complexity distribution
print("TEST 7: Complexity distribution")
complexity_counts = Counter(with_tags.values_list('complexity', flat=True))
for c in sorted(complexity_counts.keys()):
    print(f"  Complexity {c}: {complexity_counts[c]} exercises")
print()

# Test 8: Empty skills
print("TEST 8: Exercises with empty skill tags (backfill failures)")
empty = Exercise.objects.filter(skill_tags=[])
print(f"  Count: {empty.count()}")
if empty.exists():
    for ex in empty[:3]:
        print(f"  - {ex.id}: {ex.description}")
print()

print("="*70)
print("TESTS COMPLETE")
print("="*70 + "\n")
