Each exercise currently hard-codes whatever clef layout it needs inside its JSON (staffDistribution, note data all referenced to a specific stave, any analysis text tied to that). Playlists are basically ordered references to those exercise ids—there’s no layer that can mutate the definition on the fly. That’s why today, to get treble vs alto, you’d make two exercises with different staffDistribution/note data.

Adding a “clef override” knob at the playlist level means inventing a translation layer between playlist metadata and the ExerciseDefinition object the client loads. You’d have to:

store the override on the playlist entry (DB + admin/UI)
teach the API to merge that override into the exercise payload when serving the playlist
ensure the renderer, analysis, grading, and authoring UI all handle a clef switch without conflicting with the original stored data (e.g., noteheads live in absolute MIDI numbers today; mapping them to another clef may demand recalculating staff positions, accidentals, etc.).
That’s a sizable backend/frontend change, and it risks diverging what the author sees in the editor from what students actually get.

A more pragmatic compromise is to keep exercises authoritative but generate variants automatically. For example, extend the authoring workflow (or add a management command) that clones an exercise and rewrites its clef/staff-distribution fields and note coordinates. The playlist then just references the specific variant id. You still get “same content, multiple clefs,” but without introducing runtime overrides throughout the stack.

In short: conceptually yes, playlist-level clef overrides would be convenient, but implementing them means a deep rewrite of how definitions are delivered. Until you have a concrete use case that justifies that complexity, cloning exercises per clef remains the simpler, more predictable path.

ok - what woudl it take to add alto clef as an option?


Adding alto clef is feasible but touches every layer that currently assumes the world is treble/bass only.

Renderer + Client Models

StaveNotater only knows "treble"/"bass"; you’d need a new StaveNotater.ALTO, an AltoStaveNotater subclass that positions annotations halfway between existing staves, and a factory branch in StaveNotater.create() (lab/static/js/src/components/music/stave_notater.js (lines 1140-1466)). It should mirror Treble/Bass behavior (analysis labels, metronome marks, etc.) but reference the alto clef, triangle spacing, and whatever solfege diagramming you expect.
StaveNoteFactory and Chord.noteNumBelongsToClef only split notes between treble/bass. You’ll have to teach them what range belongs to the alto staff and how to serialize “alto-only” distributions (e.g., new STAFF_DISTRIBUTION entries like alto or grandStaffAltoTenor), otherwise notes will still migrate to treble/bass (lab/static/js/src/components/music/stave_note_factory.js (lines 1-120), lab/static/js/src/models/chord.js (lines 589-739)).
MusicComponent and ExerciseSheet pass staffDistribution through without validation, so once you add a valid value in general.validStaffDistributions (lab/static/js/src/config/general.js (lines 7-36)), ensure the renderer knows when to instantiate a single-staff alto layout vs. mixed staves. Expect to update the staff distribution widget and music_controls UI so users can toggle the new option (lab/static/js/src/components/music.js (lines 25-355), lab/static/js/src/components/ui/music_controls.js (lines 229-245)).
Exercise Definitions + Admin

Exercise JSON currently serializes staffDistribution with a fixed set of strings and the admin form exposes only those choices (apps/exercises/forms.py (lines 319-334)). Add a new constant/choice there, update help text, and persist it in ExerciseForm.save() (apps/exercises/forms.py (lines 493-521)). Any seeding scripts (e.g., importers) must also know how to emit the alto option.
Downstream consumers—grading, analysis, playlists—pull the definition verbatim. Once the renderer understands alto, playlists don’t need extra logic, but you’ll want authoring tooling to clone existing treble exercises with a different staffDistribution so instructors can assign both.
Effort/Testing

Implementation complexity is moderate: roughly a couple of front-end files plus config/admin changes, but you must regression-test legacy exercises to ensure the new staff distribution doesn’t accidentally remap treble/bass material.
Testing plan: spin up a sample exercise saved with the new staffDistribution, confirm the sheet renders with alto clef glyphs, noteheads land correctly, and grading/highlights still work; then verify existing treble/bass exercises behave identically.
Next steps if you proceed: (1) decide on the exact staff-distribution semantics (alto-only vs. mixed), (2) implement the Alto notater/clef mapping, (3) expose the option in admin/ui, and (4) seed or clone exercises that use it.






Auto context





