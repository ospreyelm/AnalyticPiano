# Changelog

All notable changes to the HarmonyLab codebase will be documented in this file.

## [Unreleased] - 2026-04-16

### Added
- **Dashboard / UI:** Added a "Delete Selected" bulk-action function to the Exercises list dashboard, including CSRF projection, transaction safety, and validation that blocks deletion of exercises containing student performance data.
- **Workbench:** Added a "Select All" checkbox to the Recent Mass Imports tab to facilitate bulk operations.
- **Roman Numerals:** Added pedagogical mappings for Augmented chords (0/4/8) in `Analyze.js` / `jChords.js`, specifically allowing formatting for `V+/V` and `V+/IV`.

### Fixed
- **Chorale Identification Paging:** Resolved an exact misalignment bug between the physical identification layout positions and the logical Roman Numeral inputs. Extensively refactored the pagination engine in `exercise_context.js`, `exercise_sheet.js`, and `exercise_definition.js` to correctly tie the subset of mapped problems to literal measure slices rather than chronologically sliced arrays. Question mark placeholders are now firmly attached to their corresponding chords on all viewport sizes across multiple pages.
- **Bulk Delete Bug:** Fixed an API flaw in the bulk delete endpoint which queried models by string `id` instead of the integer `pk`.
