# Chordal UMTO — Status & Backlog (2026-06-07)

Branch: `worktree-chordal-umto` (off master `bc2c5c4a`), 29 commits.

## Done & verified (this branch)

**Spec A — chordal UMTO score-kind** (`docs/.../2026-06-07-chordal-umto-score-kind-design.md`)
- `ChordEvent` model, `Metadata.score_kind`, `UMTO.chords`, validators, schema regen.
- Frontend chordal case in `umto_chorale` block populates `exercise.problems`.
- Legacy `chord[]` runtime wrapper (`legacy_chord_row_to_chordal_payload`).
- Tests: `apps/exercises/tests/test_chordal_umto.py` (27), `node chordal_problems_logic.test.js` (11).

**Spec B — MusicXML → UMTO router + Workbench** (Codex; `docs/.../2026-06-07-musicxml-umto-router-design.md`)
- `apps/exercises/utils/umto_import_router.py`, `import_musicxml.py` rewrite, Workbench upload/list/project, `import_legacy_chord_csv`.
- Chordal analysis review editor (Codex; `docs/.../2026-06-07-workbench-chordal-analysis-review-design.md`).

**Bug fixes (this session)**
- Key normalization: `analyze_chunk_skills` now converts pseudo-key tokens (`jC_`→C major) before music21. Fixed `Cannot make a step out of 'J'` that blocked all MusicXML imports.
- Edit page crash: `forms.py:_init_chorale_initials` guards `analysis`-as-list (UMTO stores analysis as a list, not dict).
- Render-time staff distribution: `_convertChordalUMTOToProcessedScore` splits `chords[]` across staves per `staffDistribution` at render (layout is a view option, not baked at import). `shouldPreserveChordalMeasures` → false.
- Last-chord split: keep lowest note on bass when register split (≥ MIDI 60 → treble) would empty a staff.

**Manual-verified:** m321 (3-voice rule-of-octave) imports as chordal UMTO — correct key, no bass duplication, 8 onsets, RN analysis (I, vii°6, I6, IV, V, IV6, vii°7, I), grand staff renders correctly incl. final tonic-octave chord.

## Open backlog (each its own session)

### 1. Legacy play view does not navigate (PRE-EXISTING regression)
- Symptom: clicking "New Play View" stays on dashboard; no JS error. `/play` returns 200 server-side; `lab:index` → `/play`.
- **Not caused by chordal work** — user reports it could have broken across hundreds of prior commits; unused for a while.
- Likely an auth/redirect or client-route issue. Needs git bisect against a known-good commit, or browser-network inspection of what happens on the click (does `/play` 302 back to dashboard when authenticated?).
- Files: `lab/views.py` (`PlayView`, `force_redirect` ~line 232/259/524), `lab/templates/_header.html` (`home_url`), `lab/urls.py`.

### 2. Play view "Save as exercise" → save as UMTO
- The original user request: legacy play view lets you pedal-record chords and save as an exercise. That save path must now emit a chordal UMTO exercise (via `build_chordal_umto_payload` / a new `save_chordal_umto_exercise`), not a legacy row.
- Depends on #1 (play view must work first).
- This closes the loop on "make exercises on the fly."

### 3. staffDistribution picker in dashboard (teacher)
- Render already honors `metadata.staffDistribution` (treble/bass/keyboard/grand). Missing: a dropdown on the dashboard edit form that persists `metadata.staffDistribution`.
- Small. The play view already has a live toggle (legacy `chord.js` reads `sessionStorage.staffDistribution`), so per earlier decision the teacher-facing control belongs in the dashboard only.

### 4. Edit-exercise page is too complex — cleanup
- The dashboard edit-exercise form/page has grown unwieldy (chorale + UMTO + chordal + identification all branching in `forms.py` / `dashboard/views/exercises.py` / `edit-exercise.html`).
- Needs a focused simplification pass: separate the score-kind-specific config, reduce the `_configure_chorale_fields` / `_init_chorale_initials` branching, clarify what a teacher actually edits per kind.

## Known follow-ups / tech debt
- `shouldPreserveChordalMeasures` always returns false now — name is misleading; consider renaming or folding into the caller.
- Import-time `_chordal_to_measures` keyboard-split is now only a stored fallback (render re-splits). Could be simplified to single-staff since render owns layout, but kept for identification-window + non-JS consumers.
- Staff split is register-only (≥60 treble) + lowest-to-bass guard. It discards the source MusicXML part assignment (import flattens all parts into one `visible[]`). For voicing-accurate layout, a future option is to preserve per-note source staff in `ChordEvent`.
- Transpose for chordal UMTO still not implemented (Spec B item): `transpose.py` only handles legacy top-level `data["chord"]`.
- Pre-existing full-suite failures: 34 (URL names + music21 9.9.1 analysis drift) — present on base `bc2c5c4a`, unrelated to this branch.
