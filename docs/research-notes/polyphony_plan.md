# Polyphony Migration Plan

This document captures how we evolve HarmonyLab from homophonic whole‑note sequences to full polyphonic exercises with independent rhythms per hand, while preserving real‑time feedback and grading.

## Objectives
- Support multiple voices per staff (independent rhythms, ties, dots).
- Keep immediate feedback: match what students play to what’s on screen and grade it.
- Maintain backward compatibility with existing exercises and UI flows.
- Enable MusicXML import to author music outside the app and reuse it inside HarmonyLab.

## Non‑Goals (for v1)
- Complex engravings (tuplets, repeats/voltas expansion, ornaments beyond ties/dots).
- In‑browser WYSIWYG notation editor (future option).

---

## Canonical Internal Representation (CIR)
Renderer‑agnostic JSON used by both the renderer adapter(s) and the grader’s timeline builder.

- Score
  - meta: { key, time, tempo?, divisions? }
  - measures: Measure[]
- Measure
  - number
  - staves: { [staffId]: Staff }  // e.g., treble, bass
- Staff
  - clef: "treble"|"bass"
  - voices: Voice[]
- Voice
  - direction: "up"|"down"|"auto"
  - items: (Note|Rest|Chord)[]
- Note
  - kind: "note"
  - pitch: { step: "A".."G", alter: -2..2, octave: integer }
  - duration: { type: "w"|"h"|"q"|"8"|"16"|..., dots: 0|1|2 }
  - tie?: { start?: true, stop?: true }
- Rest
  - kind: "rest"
  - duration: { ... }
- Chord
  - kind: "chord"
  - notes: Note[] (no durations per member; duration sits on the chord)
  - duration: { ... }

Example (excerpt):
```json
{
  "meta": { "key": "C", "time": "4/4" },
  "measures": [
    {
      "number": 1,
      "staves": {
        "treble": { "clef": "treble", "voices": [
          { "direction": "up", "items": [
            { "kind": "note", "pitch": {"step":"C","alter":0,"octave":5}, "duration": {"type":"q","dots":0} },
            { "kind": "note", "pitch": {"step":"D","alter":0,"octave":5}, "duration": {"type":"q","dots":0} },
            { "kind": "note", "pitch": {"step":"E","alter":0,"octave":5}, "duration": {"type":"h","dots":0} }
          ]}
        ]},
        "bass": { "clef": "bass", "voices": [
          { "direction": "down", "items": [
            { "kind": "note", "pitch": {"step":"C","alter":0,"octave":3}, "duration": {"type":"h","dots":1}, "tie": {"start": true} },
            { "kind": "note", "pitch": {"step":"G","alter":0,"octave":2}, "duration": {"type":"q","dots":0} }
          ]}
        ]}
      }
    }
  ]
}
```

---

## Grading Timeline (Events)
Derived from CIR; drives real‑time grading with onsets/holds semantics.

Event schema (per absolute time):
```json
{
  "start": 1920,           // ticks from score start (PPQ e.g., 480)
  "duration": 480,         // nominal duration for windowing/scoring (optional)
  "meter": {"bar": 1, "beat": 3},
  "perStaff": {
    "treble": { "newOnsets": [76], "holdsFromPrevious": [] },
    "bass":   { "newOnsets": [43], "holdsFromPrevious": [48] }
  }
}
```
Rules:
- Only first note of a tie appears in `newOnsets`; subsequent tied segments appear as `holdsFromPrevious`.
- If a staff has no new onset for an event, `newOnsets` is empty; the event still occurs for other staves.
- Pedal sustain counts as continuing hold (handled in grader logic).

Grader contract:
- At `event.start`, expect each staff’s `newOnsets` within a timing window (e.g., ±120ms).
- Don’t require re‑attack of `holdsFromPrevious` if the note is currently held or pedal is down.
- Combine staff correctness for overall event score; expose per‑hand feedback.

---

## MusicXML → CIR + Events Pipeline
Backend (Python) using `music21`:
1. Parse MusicXML; extract parts/staves/voices, notes, rests, ties; compute absolute offsets and durations (divisions → ticks).
2. Build CIR JSON (measures/staves/voices/items); convert pitches to step/alter/octave.
3. Build Events by grouping simultaneous onsets and deriving holds from durations/ties.
4. Store in `Exercise.data`:
   - `source`: { type: "musicxml", filename, meta }
   - `score`: CIR JSON
   - `events`: array of event objects

Backward‑compat: if `score/events` missing, legacy chord+rhythm path continues to work.

---

## Rendering Strategy
- Adapter pattern. Current legacy VexFlow adapter works for proof‑of‑concept; spacing quirks are known in VF 0.x.
- Target options:
  - VexFlow 4: modern API, better formatter; requires refactor of legacy code.
  - OpenSheetMusicDisplay (OSMD): MusicXML‑native, excellent polyphonic layout, fastest path from MusicXML to screen.
- Regardless of renderer, we render from CIR to keep the pipeline stable.

---

## Milestones (v1)
1. MusicXML upload (dashboard) → server stores file.
2. Converter (music21): MusicXML → CIR + Events → save to `Exercise.data.score/events`.
3. Frontend render: if `score` present, render via adapter (`?newvf` or `?osmd` flag for testing).
4. Grader: if `events` present, drive ExerciseContext from the event timeline (onsets/holds), else legacy path.
5. QA: ties across bars, asynchronous hands, rests, pedal behavior, multi‑measure sequences.

Stretch (v2): tuplets, repeats expansion, more than 2 voices/staff, articulations/dynamics for analysis overlays.

---

## Curated corpora (e.g., Bach Chorales) and Course Integration

Goal: ship high‑quality polyphonic repertoire that students can immediately access inside courses and playlists.

### Sources
- music21 corpus (e.g., `bach/bwv*.xml`) and other permissibly licensed MusicXML datasets.
- Our own curated MusicXML exports (MuseScore/Dorico/etc.) with pedagogical edits.

### Import pipeline (batch)
1. Admin upload or scripted fetch of a corpus folder (MusicXML files).
2. For each file:
   - Parse with music21 → build CIR + Events as described above.
   - Normalize metadata: title, BWV/catalog, key/mode, time signature, number of voices, range, texture tags (e.g., chorale, keyboard style).
   - Store as an Exercise with `data.source = {type: "musicxml-corpus", corpusId, workId}` and `is_public=true`.
   - Tagging in JSON: `data.tags = ["corpus:bach-chorales", "chorale", "polyphonic", "4-part"]`.
3. Optional: generate multiple transposition variants if desired (leveraging existing transpose utilities) and index them as separate, linked exercises.

### Course structure adjustments
- Add a "Repertoire" or "Library" section in the course sidebar/dashboard that exposes corpus filters (composer, key, difficulty, meter, tags).
- Allow “Add to Playlist/Course” from any library item (reuses existing playlist mechanism).
- Provide quick‑start entry points:
  - Practice soprano/alto/tenor/bass separately (mute other voices) using the Events timeline per staff/voice.
  - Keyboard reduction mode (two‑staff rendering) for chorales vs. four staves (stretch goal).
- Progress tracking: treat each library item like an exercise instance; store grading outcomes as usual so course analytics remain intact.

### UI/UX touches
- Search + filters (composer, key, time, voices, difficulty).
- Preview measure images (first system) before opening.
- “Open in Practice” → launches the same play/grade screen using Events timeline.

### Data governance
- Ensure licensing/attribution is preserved in `data.source.meta` and displayed in the UI.
- Keep the original MusicXML alongside CIR for traceability and re‑conversion.

### Milestones (corpora)
1. Batch importer command (management command) that ingests a folder of MusicXML and creates public Exercises with `score` and `events`.
2. Library view in dashboard (basic list + filters + open/add‑to‑playlist actions).
3. Course routing to library items (link an exercise ID from the corpus into a course module/lesson).
4. QA on a subset of Bach chorales: rendering, grading (onsets/holds/ ties), and metadata search.

Acceptance: a student can browse Bach chorales, open one, see proper polyphonic notation, play along, receive instant grading, and add it to a playlist/course.

---

## Open Questions
- Renderer choice: move to OSMD now or stage VF4 migration?
- Storage: keep MusicXML alongside CIR for traceability and re‑conversion?
- Authoring: do we also add a lightweight rhythm editor to tweak imported material?

---

## Acceptance Criteria
- Given a two‑staff MusicXML with independent rhythms per hand, the app:
  - Imports and stores `score` and `events` under `Exercise.data`.
  - Renders two or more measures with correct clefs, barlines, durations.
  - Grades correctly: onsets per hand are required at the right times; tied notes need no re‑attack; pedal holds are honored.
  - Legacy exercises without `score/events` still behave exactly as before.

---

## Flags & Dev Notes
- Rendering prototype: `?newvf` path already wired; consider `?osmd` for OSMD spike.
- Legacy VF spacing is known to mis‑align some cross‑staff rhythms; acceptable for prototype, addressed by OSMD/VF4 in migration.
