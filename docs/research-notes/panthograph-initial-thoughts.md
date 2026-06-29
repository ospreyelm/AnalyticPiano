Perfect. Below is a **clean, implementation-ready planning document** you can treat as the *initial internal reference file* for both **Manuel Pratique** and the **Canon Pantograph**, explicitly framed as an **extension of Analytic Piano** (with VexFlow rendering).

This is written to be:

* stable (won’t need rewriting when details change)
* concrete enough to guide implementation
* abstract enough to avoid premature constraints

You can drop this straight into a Markdown file (e.g.
`/docs/pantograph-manuel-pratique.md`).

---

# Analytic Piano

## Manuel Pratique & Canon Pantograph

**Initial Planning & Architecture Reference (v0.1)**

---

## 1. Purpose

This document defines the **conceptual goals, pedagogical intent, and internal representation** for two closely related extensions to Analytic Piano:

1. **Manuel Pratique Mode**
   (clef fluency, shape preservation, reinterpretation)

2. **Canon Pantograph Mode**
   (transformational counterpoint, canon, ICF visualization)

These are not separate apps.
They are **modes of thinking** implemented inside Analytic Piano.

---

## 2. Guiding Principles

### Pedagogical

* Shape precedes pitch
* Relations precede labels
* Transformation precedes arithmetic
* Understanding precedes realization

### Design

* Clefs are **semantic operators**, not decorations
* Notehead geometry is invariant unless explicitly realized
* Rendering ≠ model
* Playback derives from interpretation, not notation

---

## 3. Manuel Pratique Mode

### 3.1 Definition

**Manuel Pratique Mode** restores historical clef fluency by allowing:

> the *same written music* to be re-interpreted under different clefs
> **without moving noteheads**.

This enables:

* diatonic transposition without arithmetic
* clef-based thinking
* immediate perception of invariance

---

### 3.2 Core Operation (Critical)

> **Change the clef, keep the noteheads fixed.**

This is the foundational gesture.

---

### 3.3 Scope (Initial)

* Grand staff (default)
* Single melodic line or two-hand texture
* Arbitrary clef reassignment per staff
* Immediate playback update based on clef interpretation

### Deferred

* Species rules
* Error checking
* Export

---

## 4. Canon Pantograph Mode

### 4.1 Definition

The **Canon Pantograph** is a transformational system that:

* preserves visual shape
* applies lawful pitch and time transformations
* reveals contrapuntal invariants
* supports CF-based and CF-less canons

Canon is treated as **self-compatibility under transformation**, not copying.

---

### 4.2 CF-Neutral Architecture

The system does **not** privilege a Cantus Firmus.

* All voices are equal objects
* A CF is simply a non-derived voice
* The Imaginary CF (ICF) is a *virtual inverse transform*, not a melody

This supports:

* canons without CF
* double canons
* infinite canons
* “basic version” thinking (Taneev)

---

## 5. Dual Visualization Modes

### 5.1 Structural Mode (Pantograph View)

**Purpose:** understanding

Characteristics:

* Noteheads fixed
* Clefs encode transformations
* Canon and proposta look identical
* CF and ICF look identical
* ICF uses inverse clef + inverse time shift
* Ghosted / reduced opacity for imaginary voices
* Registers ignored

Answers:

> *Why does this work?*

---

### 5.2 Realization Mode (Treble/Bass View)

**Purpose:** usability / hearing

Characteristics:

* Pitches fixed
* Clefs chosen for readability
* Noteheads repositioned
* Octave displacement allowed
* Imaginary scaffolding hidden

Answers:

> *How do I play / hear this?*

---

## 6. Internal Representation (Core Model)

### 6.1 Fundamental Note Object

Each note stores:

```text
- staff_position (integer: line/space index)
- time (relative grid units)
- duration
```

**No pitch is stored directly.**

---

### 6.2 Clef Object

A clef defines a mapping:

```text
staff_position → diatonic pitch
```

Clefs are **functions**, not labels.

---

### 6.3 Voice Object

A voice consists of:

```text
- ordered list of notes
- clef
- time offset
- optional derivation metadata
```

---

### 6.4 Transform Object (Pantograph Arm)

A transform specifies:

```text
- clef reinterpretation (Δp)
- horizontal shift (Δt)
- optional time scaling (augmentation/diminution)
- optional inversion (future)
```

---

## 7. Imaginary Cantus Firmus (ICF)

### Definition

If a canon transform is:

```text
(+Δp, +Δt)
```

then the ICF is:

```text
(−Δp, −Δt)
```

### Representation

* Same notehead geometry
* Inverse clef
* Shifted earlier in time
* Optional ghost opacity

The ICF is **not composed** — it is *derived*.

---

## 8. Interval Logic (Engine, Not Interface)

* Interval legality is computed internally
* Consonance rules are configurable
* Diatonic is default, not mandatory
* Numeric representations (Taneev-style) are hidden unless explicitly shown

The user interacts with **shape and sound**, not numbers.

---

## 9. Rendering (VexFlow)

VexFlow is treated as:

* a renderer
* not a source of truth

Two rendering passes:

1. Structural (pantograph)
2. Realization (treble/bass)

Same data, different interpretation.

---

## 10. Relationship to Solfège Viewer

* Solfège viewer remains melodic-only
* Uses ABC
* Pitch-first abstraction
* No vertical simultaneity

Pantograph logic does **not** belong there.

The two tools share:

* conceptual vocabulary
* pedagogical sequencing
* no rendering infrastructure

---

## 11. Implementation Phases (Suggested)

### Phase 1 – Manuel Pratique

* Clef reinterpretation toggle
* Fixed notehead geometry
* Playback updates

### Phase 2 – Minimal Pantograph

* Derived voice overlay
* Horizontal delay
* Inverse clef visualization
* No rule checking

### Phase 3 – Refinement

* ICF ghosting
* Dual-mode toggle
* Simple legality hints (optional)

---

## 12. Success Criteria

This project succeeds if:

* A student says:
  *“It’s the same thing — just read differently.”*

* A composer can:

  * sketch a canon structurally
  * delay registral decisions
  * understand invariance without arithmetic

* Taneev’s ideas feel **obvious**, not intimidating.

---

## 13. One-Sentence Mission Statement

> **This module restores clef-based transformational thinking so counterpoint and canon can be seen, heard, and understood as invariant shape rather than calculated result.**

---

If you want, next we can:

* extract a **technical task list** from this
* design a **minimal UI wireframe**
* or write a **student-facing intro text** explaining why clefs matter again

This is an excellent moment to pause and build — you now have a solid conceptual spine.
