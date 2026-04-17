# Mass Import Performance Implementation Plan

**Date**: 2026-04-16
**Goal**: Build the `mass_import_performance` management command.

## Phase 1: Command Scaffold and Argument Parsing
- **File**: `apps/exercises/management/commands/mass_import_performance.py`
- **Actions**:
  1. Create the class structure extending Django's `BaseCommand`.
  2. Implement `add_arguments` to accept:
     - `<musicxml_file>` (string)
     - `--author` (string, required)
     - `--course` (string, optional)
  3. Validate that the author exists and the file path is valid.

## Phase 2: Music21 Parsing and Auto-Splitting Algorithm
- **File**: `apps/exercises/management/commands/mass_import_performance.py`
- **Actions**:
  1. Load the file using `music21.converter.parse(file_path)`.
  2. Build a method `split_into_chunks(score)`:
     - Iterate through the measures.
     - Define an "empty measure" as one where all parts consist entirely of rests lasting the full duration of the measure.
     - Extract consecutive non-empty measures into discrete `music21.stream.Score` chunks.
  3. Add logic to normalize each chunk so the first measure of the chunk acts as Measure 1 locally.

## Phase 3: Data Translation (Music21 to HarmonyLab JSON)
- **File**: `apps/exercises/management/commands/mass_import_performance.py`
- **Actions**:
  1. For each chunk, determine the primary tonal center using `chunk.analyze('key')`.
  2. Extract all pitches to pass to `music21_builder.spelling_key_for_pitches()` (from `apps.exercises.generation.music21_builder`) to get the correct HarmonyLab key string (e.g., `jC_`).
  3. Traverse the notes/chords in the chunk and map them to the `data.chord` array format:
     - Calculate rhythms based on `note.quarterLength`.
     - Populate `visible` arrays with MIDI pitch numbers.
     - Set default analysis settings based on the key.

## Phase 4: Database Ingestion
- **File**: `apps/exercises/management/commands/mass_import_performance.py`
- **Actions**:
  1. Iterate over the translated chunks and create `Exercise` objects.
     - `description="Imported Segment [Idx], mm. [Start]-[End]"`
     - `type="matching"` (Serves as the raw/base version)
     - `data` containing the translated JSON.
  2. If the `--course` flag is passed, check if a "Recent Imports" `Playlist` exists for today, or create one.
  3. Create `ExercisePlaylistOrdered` entries for the generated exercises.

## Phase 5: Testing [COMPLETED]
- **File**: `apps/exercises/tests/test_mass_import.py`
- **Actions**:
  1. Write a unit test that feeds a simplified MusicXML object (constructed via code) containing a rest gap into the split algorithm to verify correct chunking.
  2. Verify that the correct number of `Exercise` records are created in a dry-run or mock DB environment.

### Status: COMPLETED. 
The mass import performance pipeline, teacher workbench GUI, and projection engine are fully implemented, tested, and actively functioning on the `master` branch.
