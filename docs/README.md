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

### **[claude.md](../claude.md)** - Main Implementation Guide
- **Status:** ENHANCED ✓ Core issues fixed + features 1 & 3 implemented
- **Focus:** Chorale exercise system architecture and troubleshooting
- **Latest Updates:**
  - Three critical bugs fixed (held notes, passing tones, diagnostics)
  - Feature 1: Enhanced instructional text for chorales
  - Feature 3: Detailed grading feedback with per-window statistics
  - Future roadmap with 5 planned features (Phases 1-3)
- **Audience:** Developers maintaining the chorale grader system

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
- **Focus:** How we implemented Tonic/Dominant filtering for Bach chorales
- **Key finding:** Uses `skill_tags: ["unit:9"]` on a Playlist to trigger frontend filtering in `exercise_definition.js`
- **Content:**
  - Rationale for using frontend filtering instead of data destructive imports
  - How to create curriculum-aligned playlists using the standard Bach importer
- **Audience:** Instructors and agents building new curriculum units

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

## Implementation Priorities Summary

### Chorale System (Music Education Focus)

**Completed:**
- ✅ Fix held notes algorithm
- ✅ Fix passing tones in separate windows
- ✅ Enhanced instructional text (Feature 1)
- ✅ Detailed grading feedback (Feature 3)

**Next (High Priority):**
1. Visual feedback for incorrect notes (Feature 2) - 4-6 hrs
2. Mode variations: play-outer, play-soprano, play-inner (Feature 4) - 6-8 hrs

### LMS Student Experience (Platform Focus)

**Quick Wins (1-2 days):**
1. Dashboard "Due Soon" widget - 4 hrs
2. Email reminders - 6 hrs
3. Error detail display - 3 hrs
4. Progress bars - 2 hrs

**Medium Effort (3-4 days):**
5. Course grade summary - 2 hrs
6. Attempt history - 4 hrs
7. Per-exercise feedback - 3 hrs
8. Mobile fixes - 4 hrs

---

## File Organization

```
docs/
├── README.md                              (this file)
├── claude.md                              (main implementation guide)
├── chorale_analysis.md                    (harmonic analysis pipeline — computed on the fly)
├── chorale_future_improvements.md         (chorale feature roadmap)
├── unit_1_note_reading_strategy.md        (Curriculum strategy: diatonic Note Names for Unit 1)
├── unit_9_bach_import_strategy.md        (Curriculum strategy: frontend filtering for Unit 9)
└── lms_student_ux_assessment.md          (LMS/student experience evaluation)
```

---

## Quick Links by Role

### For Developers Working on Chorales
1. Read [claude.md](../claude.md) - Architecture and grading system
2. Check [chorale_analysis.md](chorale_analysis.md) - How harmonic analysis is computed
3. Check [chorale_future_improvements.md](chorale_future_improvements.md) - Planned features with implementation steps
4. See `docs/chorale_exercises_plan.md` - Curriculum specification

### For Product Managers / Instructors
1. Read [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Student experience evaluation
2. Review Phase 1-3 roadmaps for prioritization
3. Check "Code Locations" section for development estimates

### For New Developers
1. Start with [claude.md](../claude.md) - Overview and architecture
2. Read the "How the Chorale Grader Works" section
3. Check "Common Issues and Troubleshooting" for typical problems
4. Review debug logging section for console-based investigation

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
1. [claude.md](../claude.md) - Sections 1-4: Overview, fixes, architecture
2. [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Sections 1-6: Current state

**For Planning Future Work:**
1. [chorale_future_improvements.md](chorale_future_improvements.md) - Phase 1-3 roadmap
2. [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Sections 9-11: Implementation priorities

**For Specific Issues:**
- Chorale grading problems: [claude.md](../claude.md) - "Common Issues and Troubleshooting"
- Student experience problems: [lms_student_ux_assessment.md](lms_student_ux_assessment.md) - Sections 1-8

---

## Key Metrics

### Chorale System
- **Lines of Code:** ~450 (chorale_grader.js)
- **Features Implemented:** 3 (fixes + Features 1, 3)
- **Features Planned:** 5 (Features 2, 4-8)
- **Estimated Dev Time:** ~90 hours for all features

### LMS System
- **Current Grade:** C+ (Functional but incomplete)
- **Feature Parity:** ~40% vs. Canvas/Blackboard
- **Estimated Improvement Time:** 50 hours (Phase 1-3)
- **Top Priority:** Deadline notifications & grade visibility

---

## Contributing

When updating these documents:

1. Keep [claude.md](../claude.md) synchronized with actual code
2. Update "Recent Changes" section when committing new features
3. Add code locations for new features
4. Use consistent formatting (## sections, code blocks, tables)
5. Include effort estimates for features
6. Link to related documentation

---

## Questions?

- **Chorale system questions:** See [claude.md](../claude.md) debugging section
- **Student UX questions:** See [lms_student_ux_assessment.md](lms_student_ux_assessment.md) relevant section
- **Feature planning:** See corresponding roadmap document

Last updated: 2026-04-21
