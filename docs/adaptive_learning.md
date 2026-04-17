# Adaptive Learning System

This document provides a technical and pedagogical overview of the Adaptive Curriculum Engine in HarmonyLab.

## 1. The Knowledge Graph

The foundation of the adaptive system is a **Directed Acyclic Graph (DAG)** of music theory skills.

### Skill Taxonomy (`apps/exercises/skill_graph.py`)
Skills are grouped into tiers of increasing complexity:
- **Tier 0 (Music Literacy)**: Treble/Bass clef reading, basic note names, generic intervals.
- **Tier 1 (Diatonic Harmony)**: Specific intervals, triads, dominant sevenths, primary cadences.
- **Tier 2 (Chromatic Harmony)**: Secondary dominants, modal mixture, augmented sixths, modulation.

### Prerequisite Logic
A skill only becomes available for practice ("unlocked") once the student has reached the **`familiar`** level in all of its prerequisite skills.

---

## 2. Mastery & Decay

HarmonyLab tracks competency levels for every skill using the following scale:
1. `not_started` (Level 0)
2. `attempted` (Level 1)
3. `familiar` (Level 2) — **Unlock Threshold**
4. `proficient` (Level 3)
5. `mastered` (Level 4)

### The Decay Algorithm
Mastery is not permanent. To simulate forgetting, the engine applies an exponential decay formula based on the time elapsed since the last practice session:

$$Level_{current} = Level_{original} \times e^{-\lambda t}$$

Where:
- $t$ = Days since last practice.
- $\lambda$ = Decay constant (derived from a 30-day halflife).

If a student's level drops due to decay, the skill will be marked as **"Review Due"** in the Skill Map.

---

## 3. Adaptive Serving Algorithm

When a student practices an **Adaptive Playlist**, the engine selects the "best next exercise" using the following ranking hierarchy:

1. **Weakest Unlocked Skill**: Find all skills that are unlocked but below the `mastery_threshold`. Rank the candidate exercises by the *lowest* mastery level they target.
2. **Complexity Tie-Break**: If multiple exercises target the same mastery level, the engine selects the one with the lowest `complexity` score (Tiered pedagogical ordering).
3. **Deterministic Randomness**: A stable seed (based on user + playlist + progress) is used to pick from remaining ties and select a transposition key, ensuring a consistent experience if the student refreshes the page.

### Transposition Variety
In adaptive mode, the engine automatically chooses a transposition for every exercise to ensure students aren't just memorizing fingerings. It prioritizes the `transpose_requests` set on the Playlist.

---

## 4. Visual Skill Map

The **Skill Map** is the student's primary progress dashboard.

- **Nodes**: Represent skills. Color-coded by mastery level.
- **Edges**: Represent prerequisites.
- **Interaction**: Clicking a node shows prerequisites and provides a "Practice" link that triggers an adaptive session targeting that specific part of the graph.

---

## 5. Teacher Configuration

Teachers can control the behavior of the adaptive engine via the **Course Admin**:
- **`mastery_threshold`**: Set this to `familiar` for a fast-paced survey course, or `mastered` for a foundational course requiring high fluency.
- **Entry Points**: Specific exercises in a playlist can be marked as `is_adaptive_entry` to give new students a place to start before any mastery is recorded.
