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

### Practice vs. Mastery

Student-facing unit pages should distinguish between:

- **mastery state** — high-meaning skill status shown in top summary bars
- **practice progress** — long-lane fluency work shown in lane rows and mini-bars

This distinction is especially important in music-literacy and performance
units, where playlists are intentionally scaffolded from easy to harder and
where completing a few easy exercises is not enough evidence of terminal skill
ownership.

Global rule:

- top progress segments represent `attempted / proficient / mastered`
- lane rows represent recommended-practice progress and fluency-building
- `mastered` is reserved for mixed confirmation on the hardest material in the
  unit, not just early lane success

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

### Smart Assignments (Tag-Based Pooling)
To support massive repertoires like the Bach Chorale corpus, Playlists can be configured as **Smart Assignments** (`is_dynamic = True`):
- **Dynamic Pool**: The system ignores the manual exercise list and instead builds a pool from all exercises in the database matching the Playlist's `tags`.
- **Complexity Gating**: Instructors can set a `min_complexity` and `max_complexity` range, ensuring that even within a huge library like Bach, students only see phrases appropriate for their level (e.g. Theory I vs. Graduate Theory).
- **Infinite Homework**: This allows for "evergreen" assignments that automatically incorporate new imports.

### Challenge-Based Mastery Confirmation

Where units define a mastery challenge, the challenge should draw from the
hardest tier of related lanes rather than from the easiest entry material. A
student may continue to see recommended practice after reaching `proficient`;
the lane inventory is not itself the mastery bar.

Challenge eligibility should be stored in the curricular sequencing layer
(playlist / lane placement metadata), not in UMTO itself. Whether an exercise is
challenge-worthy depends on how the curriculum is using it, not on the
canonical exercise representation alone.

### Navigation & slot progress (decoupled from the URL)

For **adaptive** and **dynamic** playlists, `exercise_num` is a server-derived
slot index, **not** a value trusted from the URL. `resolve_adaptive_step`
(`apps/student/player_progression.py`) picks the slot strictly from
`PerformanceData` history: the first pending (unsubmitted / placeholder /
missing) slot, else `len(data) + 1` (next fresh slot), else `1` for a new
student. When the URL's `exercise_num` differs from the derived slot, the view
redirects the URL to match. Both the page view (`PlayerView.get`) and the SPA
`definition` endpoint (`PlayerDefinitionView`) route adaptive/dynamic requests
through this derivation plus the adaptive engine, so the page view and the
in-place "Next" re-render stay consistent.

Navigation Pinning in `get_next_exercise` (`apps/exercises/mastery.py`) returns
a previously-served exercise for a slot **only** when that slot is genuinely
submitted (`is_submitted is True`). Placeholder and legacy slots fall through
to fresh generation, where the full-history `seen_exercise_ids` dedup prevents
re-serving an exercise the student has already seen this session. This is what
breaks the former re-serve loop (PR #190).

### Deferred: dedicated review mode and exercise redo for adaptive playlists

Building a **dedicated review mode** and the **ability to redo a previously
completed exercise** for adaptive/dynamic playlists is explicitly **deferred**.

- **Current behavior:** adaptive/dynamic serving is always `mode="progression"`
  — the student is advanced to the next pending slot and cannot navigate back
  to a completed slot by editing the URL (the URL `exercise_num` is redirected
  to the derived next slot). There is no review affordance for adaptive
  playlists, and no in-flow "redo this exercise" action distinct from the
  per-exercise "Try Again" reset.
- **Why deferred:** the decoupling in PR #190 prioritized correctness of the
  forward progression (eliminating the re-serve / stuck-slot loop) and a single
  authoritative slot source. Reintroducing review/redo for adaptive requires a
  deliberate design: a server-validated "review a completed slot" path that does
  *not* re-trigger the adaptive engine's pinning/fresh-selection logic, plus a
  redo semantics that distinguishes "re-attempt the same exercise" from
  "advance to a new one" without re-opening the pinning-bypass failure mode.
  That is product+design work, not a bug fix, and is out of scope for the
  simplification effort until explicitly prioritized.
- **Do not** "fix" this by re-trusting the URL `exercise_num` for adaptive or
  by relaxing the `is_submitted` pinning condition — both reintroduce the
  re-serve loop. See Claude memory `adaptive-re-serve-loop` for the traced
  failure mode.

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

---

## 6. Bach Curriculum Factory

The **Bach Curriculum Factory** (`import_bach_phrases.py`) is an automated pipeline that transforms the Bach chorale corpus into a comprehensive library of pedagogical exercises.

### Automated Slicing Logic
The engine uses a sophisticated harmonic-rhythmic heuristic to find logical phrase boundaries (slices):
1.  **Metric Slicing**: Phrases have a controllable "grain size" (minimum of 3 bars by default).
2.  **Harmonic Arrivals**: Slicing occurs at clear cadential targets (I, V, or V/V → V).
3.  **Rhythmic Breathing**: Arrivals on long rhythmic durations (half notes or longer) are prioritized.

### Multi-Mode Generation
From a single chorale, the factory can generate multiple distinct curriculum tracks:
- **Performance (`play`)**: Traditional chorale performance tasks. WiR Roman labels and figured-bass analysis are stored in UMTO analysis for overlays/debugging.
- **Performance with figures (`play_figures`)**: Playback tasks with figured-bass display defaults.
- **Roman Numeral (`roman`)**: Identification of harmonic functions using When in Rome labels as canonical answers.
- **Figured Bass (`figures`)**: Identification of inversions and chord types.
- **Figured Bass, unabbreviated (`figures_unabbreviated`)**: Identification using raw figured-bass stacks.
- **Matching (`matching`)**: Specialized challenges linking notation to harmonic symbols, backed by the same WiR analysis as Roman mode.

### Refreshing Imported Content

`create_unit_playlist` is idempotent by default: if matching exercises already exist for the same author and description, they are skipped. Use `--overwrite`, or the "Overwrite existing exercises" checkbox in the admin/local content-generation UI, to refresh existing rows after importer changes.

### Skill Integration
Every slice is automatically processed by the `analyze_chunk_skills` engine. This ensures that every Bach phrase is immediately "plugged in" to the student's Adaptive Skill Map, allowing the software to recommend specific Bach slices that target a student's personal areas of weakness.
