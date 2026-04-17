# Mass Import Performance System Design

**Date:** 2026-04-16
**Topic:** Automating Curriculum Generation via Performance Import

## Overview
Currently, HarmonyLab relies on manually creating exercises or importing them piece-by-piece. To scale curriculum creation, we are building a "Mass Import" pipeline. This will allow the teacher to perform dozens of short progressions into Dorico, leaving a bar of rest between each one. 

We will build a standalone, autonomous management command (`mass_import_performance`) that parses the exported MusicXML, automatically detects the rest gaps using `music21`, slices the notation into completely independent data structures, and commits them all to the database. 

Crucially, the importer will save the "raw material" in a way that allows us to project multiple exercise types (Matching, Analytical, Figured Bass, Identification) from the same base performance in the future UI workbench.

## Core Components

### 1. The Importer CLI (`apps/exercises/management/commands/mass_import_performance.py`)
This will be a new Django management command. 

**Inputs:**
- Path to a MusicXML file (`.xml` or `.mxl`) 
- `--author` (Required: email of the instructor who owns the imported data)
- `--course` (Optional: course ID or title to automatically dump the generated exercises into a placeholder playlist for that course)

### 2. Auto-Split Logic (music21)
The script will use `music21` to perform the autonomous splitting:
1. Parse the MusicXML into a `music21.stream.Score`.
2. Iterate through the top-level parts/measures.
3. Determine "gap" measures. A gap measure is defined as a measure where all parts contain a whole rest (or rest total duration == measure length).
4. Extract the contiguous measure chunk between the gap measures.
5. Create an isolated sub-score for each chunk, normalizing the start measure to Measure 1.

### 3. Raw Data Abstraction 
We need to ensure that the material can be converted to *any* exercise type.

Instead of just forcing them into a `matching` exercise JSON immediately, the script will generate a "Base Scaffold". 
1. Use `music21.analyze('key')` to establish the tonal center.
2. Extract the timeline, translating notes into the CIR JSON representation (like chorales) OR the standard `data.chord` arrays, mapping the absolute MIDI values properly.
3. Automatically generate the `key` string (`jC_`, `iA_`) using our completed `spelling_key_for_pitches` logic.
4. Save the resulting structure to an `Exercise` model. 
   - Note: We will default to a `type: 'raw_performance'` or `type: 'matching'` so it can be previewed immediately, but flag it internally as an auto-imported root template.

### 4. Database Ingestion
For each segment generated:
1. `title` is generated: "Imported Segment [1], mm. x-y".
2. Create the `Exercise` record.
3. If a `--course` flag was used, append the `Exercise` ID to a new `Playlist` mapped to that course called "Recent Imports [Date]".

## UI Integration & Workbench (Completed)
The UI mockup created during brainstorming established the direction, and the frontend integration is now **complete**.

**The "Teacher Workbench" Features:**
1. **Workbench View:** A global ingestion zone (`/dashboard/workbench`) where teachers can trigger imports natively via file upload and manage them.
2. **Import Trigger:** The UI passes uploads directly to the `mass_import_performance` management command.
3. **The "Projection Engine" (Mass Actions):** Teachers can multi-select raw imported segments and use "Projection" actions (e.g. Roman Numeral, Figured Bass, Pitch Identification).
4. **Dynamic modes:** Supports global and per-item `identMode` selection (Submit/Practice/Test) at batch creation time.

By creating the split logic autonomously in the CLI and separating ingestion from projection in the data models, the system seamlessly enables this standalone Workbench.

## Execution Plan
1. Create `mass_import_performance.py`.
2. Write unit tests utilizing our mock/test `music21` data to verify the auto-split algorithm accurately slices out empty measures.
3. Build the translation layer that converts the isolated `music21.stream.Measure` segments directly into the JSON `chord` array needed for the app.
4. Handle the Django model instantiation and playlist wrapping.
