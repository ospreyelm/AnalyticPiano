# 2026-04-22-chorale-analysis-note-names-design.md

## Title
Show Explicit Note Names from CIR JSON in Chorale “Analysis” Mode

## Date
2026-04-22

## Status
Approved

## Goal
When `display.showNotation` is false and `display.showNoteNames` is true (analysis mode), render the note names (e.g., “B♭”, “F♯”) directly below each note/chord, using the explicit spelling from the CIR JSON (`step` and `alter`), ignoring octave.

## Data Extraction
- For each note, extract:
  - `step` (A–G)
  - `alter` (0 = natural, 1 = sharp, -1 = flat, etc.)
- Map `alter` to Unicode accidentals:
  - 1 → “♯”, -1 → “♭”, 0 → “”, 2 → “𝄪”, -2 → “𝄫”

## Rendering
- In the VexFlow adapter, when `showNotation` is false but `showNoteNames` is true:
  - For each onset window, render the note name label below the (hidden) staff at the correct x-position.
  - Use the extracted spelling for each note in the chord (if multiple notes, show all, e.g., “B♭ D F”).
- Do not use analyzer/Tonal.js for spelling.

## Audio
- Audio playback remains unchanged (as in normal chorale mode).

## Edge Cases
- If `alter` is missing, treat as 0 (natural).
- If a rest, skip label.

## Testing
- Confirm that “analysis” exercises with notation hidden show correct note names for all accidentals and naturals.
- Confirm that enharmonic spellings (e.g., “A♯” vs “B♭”) match the CIR JSON.
