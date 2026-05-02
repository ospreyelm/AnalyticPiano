# Taxonomy as Source of Truth - Visual Plan

This document visualizes the architectural shift from hardcoded, fragmented curriculum logic to a centralized, taxonomy-driven system for HarmonyLab.

## 1. Architectural Shift: Before vs. After

### Current State (Fragmented)
Logic is duplicated across multiple files. Changes in one place often lead to desynchronization.

```mermaid
graph TD
    subgraph "Python (Server)"
        P_IMP["import_bach_phrases.py"] -- "Hardcoded Dict" --> P_DICT["UNIT_ALLOWED_ANSWERS"]
        P_PLAY["create_unit_playlist.py"] -- "Import" --> P_DICT
    end

    subgraph "JS (Browser)"
        JS_DEF["exercise_definition.js"] -- "Hardcoded Dict (Manual Copy)" --> JS_DICT["UNIT_ALLOWED_ANSWERS"]
    end

    TAX_JSON["taxonomy.json"] -- "Tags Only" --> P_IMP
    TAX_JSON -- "Tags Only" --> JS_DEF

    style P_DICT fill:#f96,stroke:#333,stroke-width:2px
    style JS_DICT fill:#f96,stroke:#333,stroke-width:2px
```

### Proposed State (Unified)
A single JSON file drives behavior for both the server and the browser.

```mermaid
graph TD
    TAX_JSON["taxonomy.json (analysis: {...})"] 
    
    subgraph "Python (Server)"
        TAX_READER["TaxonomyReader.py"]
        RESOLVER["Targeting Logic (Request Time)"]
    end

    subgraph "JS (Browser)"
        UI["Dynamic UI (Dropdowns/Slots)"]
    end

    TAX_JSON --> TAX_READER
    TAX_READER --> RESOLVER
    TAX_READER --> PLAYLIST["create_unit_playlist.py"]
    
    RESOLVER -- "analysisPolicy Payload" --> UI
    
    style TAX_JSON fill:#4CAF50,stroke:#333,stroke-width:4px,color:#fff
```

---

## 2. The Analysis Pipeline: Three Distinct Steps

This is the core logic that converts music into a student-facing exercise.

```mermaid
sequenceDiagram
    participant M21 as Music21 (Score)
    participant RAW as Step 1: Raw Label
    participant NORM as Step 2: Normalization
    participant TARG as Step 3: Targeting
    participant UI as Browser UI

    Note over M21, RAW: music21.roman.RomanNumeral
    M21->>RAW: get_raw(chord, key)
    RAW-->>NORM: "V/V" (Raw String)
    
    Note over NORM: Pure function: spelling fixes only
    NORM-->>TARG: "V/V" (Canonical Token)
    
    Note over TARG: Context-aware + Unit-specific
    TARG->>TARG: Check if "V/V" is in Unit 11 cumulative
    TARG->>TARG: If not, try Diatonic fallback (V)
    TARG-->>UI: Targeted: "V" | raw: "V/V" | is_target: true
```

---

## 3. Data Flow: Database to Browser

The database no longer stores the *curriculum-specific* answer, only the *musical* record.

```mermaid
flowchart LR
    subgraph DB["Database (UMTO Slice)"]
        direction TB
        RAW["raw_roman_numeral: 'V/V'"]
        TARG_DB["roman_numeral: null"]
    end

    subgraph SERVER["Server (Request Time)"]
        direction TB
        POLICY["analysisPolicy: {allowed: [...], display: {...}}"]
        RESOLVE["Derive roman_numeral + is_target"]
    end

    subgraph JS["Browser (Frontend)"]
        direction TB
        DROPDOWN["Populate choices from allowedValues"]
        SLOTS["Render '?' slots where is_target=true"]
    end

    DB --> RESOLVE
    POLICY --> RESOLVE
    RESOLVE -- "JSON Payload" --> JS
```

---

## 4. Exercise Mode Landscape

This table clarifies how different exercise modes interact with the system and which are covered by the current **Taxonomy as Source of Truth** spec.

| Mode | Interaction | Analysis Engine / Logic | Spec Status |
| :--- | :--- | :--- | :--- |
| **`play`** | Student plays MIDI | `chorale_grader.js` (Window Matching) | **Out of Scope** (Separate Pipeline) |
| **`roman`** | Student clicks labels | **Server-stored `roman_numeral`** | **IN SCOPE (Primary Focus)** |
| **`figures`**| Student clicks labels | Server-stored `figured_bass` | **Deferred** (Same Pattern) |
| **`matching`**| Plays notes to match label | `ANALYSIS_MATCH` mode | **Out of Scope** |

### Key Distinction: Bach vs. Legacy
*   **UMTO Chorale/Identification:** The "New World" (Play, Roman, Figures). Driven by CIR scores and the unified taxonomy.
*   **Legacy Exercises:** (`analyze.js`, `exercise_grader.js`, chord labels, set-class). A completely separate world for old harmonization/analysis exercises; **not used for Bach chorale playlists.**

---

## 5. Repository Architecture Map

This map visualizes how the core modules of HarmonyLab interact, highlighting the path from the **Taxonomy** to the **Browser**.

```mermaid
graph LR
    subgraph "Data & Corpus"
        TAX["music_theory_taxonomy.json"]
        CORPUS["data/corpus/bach/*.json"]
    end

    subgraph "Backend (Django Apps)"
        EX_APP["apps/exercises/"]
        EX_READER["taxonomy_reader.py"]
        EX_MODELS["models.py (Exercise, UMTO)"]
        EX_CMDS["management/commands/ (import, backfill)"]
        
        LAB_APP["lab/"]
        LAB_VIEWS["views.py (generate_context)"]
    end

    subgraph "Frontend (JS Components)"
        JS_MODELS["lab/static/js/src/models/"]
        JS_DEF["exercise_definition.js"]
        JS_GRADER["chorale_grader.js"]
        
        JS_UI["lab/static/js/src/components/"]
        JS_SHEET["exercise_sheet.js"]
        JS_VEX["vexflow_adapter.js"]
    end

    %% Data Flow
    TAX --> EX_READER
    CORPUS --> EX_CMDS
    EX_CMDS --> EX_MODELS
    
    EX_READER --> LAB_VIEWS
    EX_MODELS --> LAB_VIEWS
    
    LAB_VIEWS -- "analysisPolicy + Score" --> JS_DEF
    JS_DEF --> JS_GRADER
    JS_GRADER --> JS_SHEET
    JS_SHEET --> JS_VEX

    %% Styling
    style TAX fill:#f9f,stroke:#333,stroke-width:4px
    style JS_VEX fill:#bbf,stroke:#333,stroke-width:2px
```

---

## 6. Harmonic Analysis State Machine

Emulating an **XState**-style statechart, this diagram shows the lifecycle of a harmonic label as it moves through the pipeline.

```mermaid
stateDiagram-v2
    [*] --> Raw_M21: Chord Input
    
    state Raw_M21 {
        [*] --> music21_Analyze
        music21_Analyze --> Raw_String: "V/V", "Ger+6", etc.
    }

    Raw_String --> Canonical: Normalization Layer
    
    state Canonical {
        [*] --> Handle_Spelling
        Handle_Spelling --> Canonical_Token: "V/V", "Ger⁺⁶", etc.
    }

    Canonical_Token --> Targeted: Targeting Layer (Unit Context)

    state Targeted {
        [*] --> Check_Cumulative
        Check_Cumulative --> Final_Label: If in scope
        Check_Cumulative --> Fallback_Diatonic: If out of scope & Secondary
        Fallback_Diatonic --> Final_Label: "V"
        Check_Cumulative --> Null_Slot: If out of scope & No Fallback
    }

    Final_Label --> [*]: Deliver to Browser
    Null_Slot --> [*]: Hidden in UI
```

---

## 7. Key File Transformations

| Layer | File | Role Change |
| :--- | :--- | :--- |
| **Data** | `music_theory_taxonomy_with_branches.json` | **Becomes Authority.** Adds `analysis.roman` (cumulative/new lists). |
| **Logic** | `apps/exercises/taxonomy_reader.py` | **Gatekeeper.** New methods: `get_unit_analysis()`, `get_cumulative_values()`. |
| **Pipeline**| `import_bach_phrases.py` | **Recorder.** Stores `raw_roman_numeral`. Hardcoded dict deleted. |
| **Delivery**| `lab/views.py` | **Translator.** Builds `analysisPolicy` and resolves targeting at request time. |
| **Frontend**| `exercise_definition.js` | **Consumer.** Deletes hardcoded dict. UI driven by `analysisPolicy`. |

---

## 8. Implementation Checklist

- [ ] **Step 1: Data Authoring** - Populate `analysis` objects in taxonomy JSON files.
- [ ] **Step 2: API Extension** - Update `TaxonomyReader` with new getter methods.
- [ ] **Step 3: Storage Backfill** - Run `backfill_raw_roman_numeral` to populate raw data in existing UMTO exercises.
- [ ] **Step 4: Request-Time Resolution** - Implement targeting logic in `lab/views.py`.
- [ ] **Step 5: Frontend Decoupling** - Remove hardcoded tables in `exercise_definition.js` and sync with new payload.
- [ ] **Step 6: Playlist Integration** - Update `create_unit_playlist.py` to use the unified targeting logic.
