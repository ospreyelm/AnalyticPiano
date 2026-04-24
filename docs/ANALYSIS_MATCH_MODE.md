# Analysis Match Mode

Analysis Match mode is a specialized exercise type in HarmonyLab designed for pitch identification and harmonic analysis. In this mode, the visual notation is hidden, and students are prompted to play notes based on analytical labels (like Note Names, Roman Numerals, or Figured Bass).

## Features

### 1. Invisible Notation (Ghost Score)
- The score maintains its full spatial layout and coordinate system to ensure accurate playhead synchronization.
- Notes, stems, and beams are rendered with `globalAlpha = 0` (transparent) by default.
- Labels (Note Names, etc.) remain fully visible.

### 2. Discovery Feedback
- As a student plays a correct note, that specific notehead and its stem "discoverably" appear on the staff in black.
- This provides immediate visual reinforcement of correct identification.

### 3. Rhythmic Completion (Beam Feedback)
- Beams connecting rhythmic groups only appear once **all** notes in that group have been played correctly.
- This encourages students to think in complete rhythmic and harmonic units.

### 4. Octave-Agnostic Grading
- Exercises can be configured to be octave-agnostic, meaning a student can play the correct pitch class in any octave to satisfy the requirement.
- This is particularly useful for beginning students focusing on note names.

## Configuration

### Exercise Editor
- **Show Notation**: Uncheck this box to enable Analysis Match mode (hides the "ghost" notes).
- **Allow octave displacement**: Check this box to enable octave-agnostic grading.
- **Analysis labels**: Select "Note names" (or another analysis type) to provide the prompt for the student.

### Teacher Workbench
The Teacher Workbench supports a one-click "Analysis Match" projection. When creating exercises from a corpus:
1. Click the **Analysis Match** button.
2. The system will automatically:
   - Disable notation visibility.
   - Enable Note Name labels.
   - Set the grader to `ChoraleGrader`.
   - Enable octave-agnostic matching.
   - Tag the exercise with `unit:1`.

## Implementation Details

- **Rendering Engine**: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
- **Grading Engine**: `lab/static/js/src/models/chorale_grader.js` (see `_matchPitch` helper).
- **App Logic**: `lab/static/js/src/components/app/exercise.js` (handles passing grading settings to the engine).
- **Backend Projection**: `apps/dashboard/views/api_workbench.py`
