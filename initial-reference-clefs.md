Excellent — here is a **clean rewrite of the planning document** with the **Dandelot vs. Pantograph distinction made explicit and structurally enforced**.
This version is something you can safely treat as a *foundational reference* without worrying that later abstraction will distort the historical pedagogy.

You can replace the earlier document with this one.

---

# Analytic Piano

## Manuel Pratique & Canon Pantograph

### **Revised Planning & Architecture Reference (v0.2)**

---

## 1. Purpose

This document defines two **related but conceptually distinct modes** inside Analytic Piano:

1. **Manuel Pratique Mode**
   *Pitch-centered clef fluency training, following Dandelot*

2. **Canon Pantograph Mode**
   *Transformational counterpoint and canon visualization*

These modes **share infrastructure** (renderer, timeline, playback)
but **do not share semantics**.

This distinction is deliberate, historically grounded, and pedagogically essential.

---

## 2. Core Pedagogical Distinction (Non-Negotiable)

### Manuel Pratique (Dandelot)

* **Pitch-centered**
* Anchored to **specific notes (C and G)**
* Goal: *immediate clef fluency without transposition*
* Clefs are **fixed mappings**
* Geometry is a *means*, not the goal
* No abstraction, no transformation language

### Canon Pantograph

* **Relation-centered**
* CF-neutral
* Goal: *understanding invariance under transformation*
* Clefs act as **operators**
* Geometry is **fundamental**
* Explicit abstraction

> **Manuel pratique trains fluency.
> Pantograph trains understanding.**

They must not be conflated.

---

## 3. Manuel Pratique Mode

### 3.1 Definition

Manuel Pratique Mode implements the pedagogical method of
**Georges Dandelot, *Manuel pratique pour l’étude des clefs* (1928)**.

Its purpose is to train the student to:

* recognize pitches instantly in all clefs
* especially **C and G**
* without mental transposition
* through progressive, tightly constrained exercises

---

### 3.2 Pedagogical Invariants (Dandelot-faithful)

1. **C and G are privileged pitches**

   * they are concrete reference points
   * not abstract anchors

2. **Adjacency precedes scale**

   * notes are learned as neighbors of known pitches
   * not via scale patterns

3. **Clefs are absolute**

   * “this is C in this clef”
   * not “this looks like C elsewhere”

4. **Rhythm is layered after pitch recognition**

   * early rhythmic hierarchy is temporary and instructional
   * later exercises use uniform rhythmic grids

---

### 3.3 Exercise Phases (Formal Grammar)

#### Phase A — Reference Notes

* C and G only
* uniform duration (e.g., quarters)
* purpose: absolute clef orientation

#### Phase B — Neighbor Definition (Special Case)

* mixed durations **only here**

  * reference: longer
  * neighbor: shorter
* patterns like:

  * C–D–C
  * C–B–C
  * G–A–G
  * G–F–G

This phase exists **only to define adjacency**.

#### Phase C — Normalized Reading

* all notes share same rhythmic value
* pitch set expands:

  * C ± 1
  * G ± 1
* orderings vary freely
* no semantic distinction between notes

#### Phase D — Rhythmic Subdivision

* quarter notes
* eighth notes
* triplets
* sixteenths
* etc.

Pitch grammar remains fixed.

#### Phase E — Clef Change

* same exercise regenerated
* new clef
* pitches are still **C and G**
* no abstraction introduced

---

### 3.4 Internal Representation (Manuel Pratique)

* Notes store **actual pitch**
* Clef determines **how pitch is rendered**
* Staff position is derived
* No notion of “same geometry, different pitch”

This is intentional.

---

## 4. Canon Pantograph Mode

### 4.1 Definition

Canon Pantograph Mode is a **transformational analytical tool** for:

* canon
* invertible counterpoint
* imaginary cantus firmus (ICF)
* “basic version” extraction (Taneev)

Canon is treated as **self-compatibility under transformation**, not imitation.

---

### 4.2 Conceptual Model

* **Geometry is primary**
* **Pitch is derived**
* Clefs act as **transformations**
* Voices may be *real* or *imaginary*
* A CF is optional, not fundamental

---

### 4.3 Core Objects

#### Note

```text
- staff_position
- time
- duration
```

#### Clef

```text
mapping(staff_position → pitch)
```

#### Voice

```text
- notes
- clef
- time offset
- derivation metadata (optional)
```

#### Transform (Pantograph Arm)

```text
- vertical reinterpretation (clef / inversion)
- horizontal shift (delay)
- optional scaling (augmentation/diminution)
```

---

### 4.4 Imaginary Cantus Firmus (ICF)

* Not a melody
* A **virtual inverse transform**
* Same geometry
* Inverse clef
* Inverse time shift
* Often ghosted

---

### 4.5 Visualization Modes

#### Structural Mode

* geometry invariant
* noteheads fixed
* clefs encode relations
* answers: *“Why does this work?”*

#### Realization Mode

* pitches fixed
* clefs optimized for reading
* noteheads repositioned
* answers: *“How do I play this?”*

---

## 5. Relationship Between the Modes

### What They Share

* Renderer (VexFlow)
* Timeline
* Playback engine
* UI infrastructure

### What They Do NOT Share

* Semantic meaning of clefs
* Pitch storage model
* Pedagogical language

> **Manuel pratique prepares the mind.
> Pantograph reveals the structure.**

---

## 6. Relationship to Solfège Viewer

* Solfège viewer:

  * melodic only
  * ABC-based
  * pitch-first
  * no simultaneity

* Pantograph:

  * multi-voice
  * relation-first
  * staff-position-first

They share vocabulary, not implementation.

---

## 7. Implementation Order (Recommended)

1. Manuel Pratique Mode

   * clef fluency
   * pitch recognition
   * zero abstraction

2. Early counterpoint (optional)

   * multi-clef reading

3. Canon Pantograph Mode

   * transformation
   * invariance
   * abstraction

This order matches historical practice *and* cognitive load.

---

## 8. Success Criteria

The project succeeds if:

* A student says (Manuel pratique):
  *“I just know where C and G are.”*

* A student says (Pantograph):
  *“It’s the same thing, just transformed.”*

* The two statements are **never confused**.

---

## 9. One-Sentence Summary

> **Manuel pratique trains absolute clef fluency through fixed pitches; the canon pantograph builds on that fluency to reveal invariant relationships under transformation.**

---

If you want, the next logical steps would be:

* updating the **earlier pantograph planning doc** to reference this explicitly
* designing **UI copy** that keeps the modes conceptually separated
* or mapping a **course sequence** that moves students from one mode to the other naturally

This rewrite locks in the most important conceptual boundary — and that will save you a lot of confusion later.
