# HarmonyLab Documentation

This directory contains comprehensive documentation for the HarmonyLab system, including implementation guides, roadmaps, and assessments.

## Exercise Type Reference

### **[exercise_types.md](exercise_types.md)** - All Exercise Types
- **Start here** to understand what exercise types exist and how they differ
- **Covers:** All 8 types (`matching`, `analytical`, `figured_bass`, `chorale`, `identification`, `chorale_identification`, and variants), interaction mode (play vs. identify), grader used, paging support, `analysisType` variants for `chorale_identification`, shared `IdentificationGrader` and paging infrastructure
- **Audience:** Anyone building new exercises or extending existing types

---

## Core Documentation

### **[architecture.md](architecture.md)** - How the App Works
- **Start here** for a complete mental model of the system
- **Covers:** Exercise/Playlist/Course data model, how exercises are served, exercise types, key encoding, staff distribution, curriculum generation workflow, grading systems, non-obvious patterns
- **Audience:** Agents and developers making changes to the app

### **[architecture/chorale-system.md](architecture/chorale-system.md)** - Chorale System Guide
- **Focus:** Canonical representation, principal code, grading invariants,
  debugging, and required generation references
- **Audience:** Developers maintaining chorale grading, timeline, or rendering

### **[architecture/engineering-principles.md](architecture/engineering-principles.md)** - Engineering Principles
- **Focus:** Authoritative paths, replacement budgets, model responsibility,
  compatibility retirement, and service boundaries
- **Audience:** Developers and reviewers making architectural changes

---

## Chorale Analysis

### **[chorale_analysis.md](chorale_analysis.md)** - Harmonic Analysis Pipeline
- **Focus:** How Roman numeral and figured-bass annotations are generated
- **Key finding:** Analysis is computed on the fly from pitch content + key signature — no pre-computed labels are stored in CIR JSON files
- **Content:**
  - What the CIR source files do (and don't) contain
  - `buildAnalysisWindows` in `vexflow_adapter.js` — constructing harmonic stacks
  - `Analyze` class in `utils/analyze.js` — chord identification via lookup tables and interval arithmetic
  - How `display.showRomans` / `display.showFigures` work as render toggles only
  - Full pipeline diagram and key source file index
- **Audience:** Developers working on notation rendering or analysis overlays

---

## Feature Development Documentation

### **[chorale_future_improvements.md](chorale_future_improvements.md)** - Chorale System Roadmap
- **Status:** Completed features (1, 3) + 5 pending features documented
- **Content:**
  - **Completed:** Instructional text, detailed grading feedback
  - **Phase 1 (High Priority):** Visual feedback (red notes), mode variations
  - **Phase 2 (Medium Priority):** Grading configuration, mode-specific rendering
  - **Phase 3 (Lower Priority):** Hint system, performance analytics
- **Format:** Implementation steps, code examples, testing strategy for each feature
- **Audience:** Developers planning chorale improvements

---

## Curriculum Strategy

### **[unit_1_note_reading_strategy.md](unit_1_note_reading_strategy.md)** - Unit 1 Implementation
- **Focus:** How we generated 1,200+ diatonic note-reading exercises from Bach chorales
- **Key finding:** Uses strict diatonicality checks and stage-based categorization (Stages 1-4) to avoid accidentals for early learners
- **Content:**
  - Stage definitions (Step/Octave sets)
  - Exclude-chromatic policy
  - Complexity-based sorting (Stage + Key Simplicity)
- **Audience:** Instructors and agents rebuilding or extending the Note Names unit

### **[unit_9_bach_import_strategy.md](unit_9_bach_import_strategy.md)** - Unit 9 Implementation
- **Focus:** How we implemented Tonic/Dominant targeting for Bach chorales
- **Key finding:** Uses `create_unit_playlist`, When in Rome labels, and request-time taxonomy targeting to keep full chorales while asking only in-scope labels
- **Content:**
  - Rationale for request-time targeting instead of destructive imports
  - How to create curriculum-aligned playlists using the standard Bach importer
- **Audience:** Instructors and agents building new curriculum units

### **[WHEN_IN_ROME_IMPORT.md](WHEN_IN_ROME_IMPORT.md)** - WiR Bach Import Reference
- **Focus:** Current `import_bach_phrases`/`create_unit_playlist` behavior for WiR Roman labels, figured bass, play imports, and overwrite refreshes
- **Audience:** Agents and instructors importing or regenerating Bach chorale content

---

## Student Experience & LMS Assessment

### **[lms_student_ux_assessment.md](lms_student_ux_assessment.md)** - Comprehensive LMS Evaluation
- **Status:** Complete assessment of student-facing features
- **Scope:** Navigation, assignments, grading, notifications, mobile support
- **Grade:** C+ (Functional but incomplete) - ~40% feature parity with Canvas/Blackboard
- **Content:**
  - 12 detailed assessment sections with ratings
  - Comparison to industry standards (Canvas, Blackboard, Google Classroom)
  - Issues identified in each area with severity levels
  - Specific recommendations with effort estimates
  - Prioritized 3-phase roadmap (50 hours total)
  - Code locations for implementing each feature

**Key Findings:**
- ✅ Real-time exercise feedback works well
- ✅ Performance tracking captures on-time/tardy/late status
- ❌ No deadline notifications or dashboard alerts
- ❌ No detailed grade reporting beyond pass/fail
- ❌ Mobile support unknown/likely needs work
- ❌ Detailed error feedback not surfaced to students

**Phase 1 Recommendations (15 hours):**
1. Dashboard "Due This Week" widget
2. Email reminders (48h, 24h before due)
3. Display exercise error details (from Feature 3 data)
4. Progress bars during exercise (X of Y notes)

**Audience:** Instructors, product managers, developers improving student experience

---

## Current implementation priority

Current priorities are maintained only in the repository root
[AGENTS.md](../AGENTS.md). Do not infer priority from historical roadmaps or
completed feature summaries in individual documents.

---

## File Organization

```
docs/
├── README.md                              (this file)
├── architecture/
│   ├── engineering-principles.md          (replacement and retirement policy)
│   └── chorale-system.md                  (chorale maintenance guide)
├── chorale_analysis.md                    (harmonic analysis pipeline — computed on the fly)
├── chorale_future_improvements.md         (chorale feature roadmap)
├── WHEN_IN_ROME_IMPORT.md                 (WiR-backed Bach import reference)
├── unit_1_note_reading_strategy.md        (Curriculum strategy: diatonic Note Names for Unit 1)
├── unit_9_bach_import_strategy.md         (Curriculum strategy: WiR + Unit 9 targeting)
└── lms_student_ux_assessment.md          (LMS/student experience evaluation)
```

---

## Quick Links by Role

### For Developers Working on Chorales
1. Read [architecture/chorale-system.md](architecture/chorale-system.md)
2. Check [chorale_analysis.md](chorale_analysis.md) - How harmonic analysis is computed
3. Check [chorale_future_improvements.md](chorale_future_improvements.md) - Planned features with implementation steps
4. See `docs/chorale_exercises_plan.md` - Curriculum specification

### For Product Managers / Instructors
1. Read [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Student experience evaluation
2. Review Phase 1-3 roadmaps for prioritization
3. Check "Code Locations" section for development estimates

### For New Developers
1. Start with [AGENTS.md](../AGENTS.md) for current policy and priority
2. Read [architecture.md](architecture.md) for the application model
3. Read [architecture/engineering-principles.md](architecture/engineering-principles.md)
   before architectural changes
4. Use the read-before-modifying table in `AGENTS.md` for feature-specific docs

---

## Recent Changes

### What's New (April 2026)

**Interval Identification (`chorale_identification`):**
- ✅ `analysisType: "interval_specific"` — labels intervals by quality + size (m3, M6, P5…)
- ✅ `analysisType: "interval_generic"` — labels intervals by size only (3, 6, 8…)
- ✅ `compoundIntervals` flag — reduce to within octave (default) or keep compound
- ✅ Tonal.js as authoritative interval source with `analyze.js` cross-check
- ✅ Identification paging (4 problems/page) with slide animation, page indicator, color feedback across pages
- ✅ Navigate back to answered pages with colors preserved

**Chorale Exercise System (earlier):**
- ✅ Enhanced student instructions (Feature 1)
- ✅ Detailed per-window grading feedback (Feature 3)
- ✅ `roman_numeral` and `figured_bass` analysisType identification

**Documentation:**
- ✅ New `exercise_types.md` — complete map of all 8 exercise types

---

## How to Use These Documents

### Reading Order

**For Understanding the Current System:**
1. [architecture.md](architecture.md) - Application architecture
2. [architecture/chorale-system.md](architecture/chorale-system.md) - Chorale system
3. [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Student experience assessment

**For Planning Future Work:**
1. [chorale_future_improvements.md](chorale_future_improvements.md) - Phase 1-3 roadmap
2. [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Sections 9-11: Implementation priorities

**For Specific Issues:**
- Chorale grading problems: [architecture/chorale-system.md](architecture/chorale-system.md)
- Student experience problems: [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Sections 1-8

---

## Contributing

When updating these documents:

1. Keep current repository policy in [AGENTS.md](../AGENTS.md).
2. Put durable architecture guidance in `docs/architecture/`.
3. Mark superseded specifications and plans clearly.
4. Add code locations and verification guidance for new features.
5. Link related documentation instead of duplicating it.

---

## Questions?

- **Chorale system questions:** See [architecture/chorale-system.md](architecture/chorale-system.md)
- **Student UX questions:** See [lms_student_ux_assessment.md](lms_student_ux_assessment.md) relevant section
- **Feature planning:** See corresponding roadmap document

Last updated: 2026-06-19
