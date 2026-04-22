HarmonyLab Curriculum — Grounded Recommendations
Key findings from code
Infra already in place:

StudentSkillMastery model exists — per-user, per-skill, with 5 levels, rolling history, practice days. Mastery gates = query this table.
SkillPrerequisite DAG model exists (global + per-course overrides). Unlock logic = walk this DAG.
Course.mastery_threshold + Course.required_skills exist. Khan-style gating already modeled.
is_dynamic playlist + skill_tags + min/max_complexity = pool assembly at serve time via get_adaptive_exercise_for_view in lab/views.py:134.
IdentificationAttempt logs per-slot correctness — mastery updater feeds from this.
Gap: StudentSkillMastery updates not wired. SkillPrerequisite DAG likely empty. No bulk curriculum generator.

Skill tag inconsistency: skills_analyzer.py emits unit:9_Dominant_Seventh, unit:16_secondary_dominant — mixed case, unit-prefixed. CLAUDE.md lists clean tags (Dominant_Seventh). Reconcile before scaling or adaptive queries break.

1. Unit structure
One unit → one Course, multiple Playlists (by mode).

Per unit, generate 3-4 playlists:

Unit 9 — Chord Identification (is_dynamic, skill_tags=[unit:9], mode=identify/roman)
Unit 9 — Pitch Reading (soprano) (is_dynamic, per analysis type)
Unit 9 — Play Chorale (curated, chorale mode)
Unit 9 — Mixed Review (is_dynamic, grabs from unit+prerequisites)
Course-level: set required_skills=[unit:9 tags] + mastery_threshold=proficient. Khan-style gate free via existing model.

Reason: playlists already have mode-specific behavior (skill-filtered ? slots tied to playlist tags). Modes ≠ interchangeable. Don't cram into one.

2. Exercise generation
Slice chorales by measure windows, not by skill density.

Why: skill density slicing produces exercises where student already knows answer (only one skill present = trivial). Mix is pedagogical reality. Tags already detected per chunk at import.

Generation rule:

For each chorale: sliding 4-measure windows, step=2 (overlap for spaced repetition)
Per window × 3 modes (play, chord-id, pitch-id-soprano) × 1 primary analysis type = ~3 exercises per window
45 chorales × ~8 windows × 3 = ~1080 exercises. Manageable.
Transposition layer (already exists) multiplies effective count without DB bloat.

Build: generate_curriculum.py management command iterating import_chorale with window/mode matrix. Idempotent (skip if description matches).

3. Serving / mastery gates
Use StudentSkillMastery + SkillPrerequisite — already modeled.

Needed:

Hook: on IdentificationAttempt.save() + PerformanceData.submit() → update StudentSkillMastery rows for exercise's skill_tags. Simple rule: last-10 rolling, ≥8 correct = proficient, ≥10 + 3 practice days = mastered.
Seed SkillPrerequisite rows from music_theory_taxonomy_with_branches.json prereqs. One-time command.
Unlock check in PlaylistView.get: if course.adaptive_mode, verify required_skills for previous unit met before rendering.
State already lives in right place. Wire it.

4. Scalability
Pre-generate base exercises. On-demand = transposition only.

~1080 base × 12 keys transposition (virtual) = 13K effective exercises. Pre-generating all 13K = wasteful, transpose layer exists.

Generation strategy:

Offline batch (generate_curriculum.py) for base exercises
Runtime: is_dynamic pool query + transpose on fetch (already works via transposition_matrix)
Index skill_tags GIN already there (models.py:183). Query perf fine.

5. MusicXML
Same pipeline, add converter layer.

music21_builder.py already converts CIR → music21. Add reverse: MusicXML → CIR via music21's converter.parse(). New command import_musicxml.py wraps this, feeds existing skill analyzer.

Challenges:

MusicXML has rests/pickups/repeats that CIR may not model. Normalize at ingest.
Voice assignment ambiguous (MusicXML voices ≠ SATB). Require teacher to tag voice roles on upload.
Key detection: music21 analyze('key') works but unreliable on short excerpts. Let teacher specify or validate.
No 4-voice guarantee → chorale play mode may not apply. Restrict teacher uploads to identification modes initially.



Priority sequence
[] Reconcile skill tag vocabulary (skills_analyzer.py vs CLAUDE.md list). Blocking everything adaptive.
[] Wire mastery updates on IdentificationAttempt + chorale pass. Enables gates.
[] Seed SkillPrerequisite DAG from taxonomy JSON.
[] Build generate_curriculum.py for bulk chorale slicing.
[] Enable course-level gating in PlaylistView (check prereqs met).
[] MusicXML importer last — infrastructure works, format adapter only.
[] Biggest risk: tag vocab drift. Fix first or dynamic pools return wrong exercises.