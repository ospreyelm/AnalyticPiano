# Play Mode Playlist Wiring — Design Spec

**Date:** 2026-05-11  
**Status:** Ready for implementation

---

## Problem

Two bugs prevent Play-mode playlists from working:

1. **Empty playlist** — `create_unit_playlist --mode play` creates the playlist record but links zero exercises. Root cause: play-mode exercises have never been imported (only `roman` and `figures` modes have been run). The code path is correct; the import just hasn't been run.

2. **MusicXML exercises excluded from playlist** — For units 9/10, curated MusicXML uploads are used instead of automated phrase-carving (because unit 9 allows only I/V/V7, making automated segments too sparse). But `create_unit_playlist` filters candidates by Riemenschneider description pattern `R(\d+)\s*-\s*Phrase\s*(\d+)`. MusicXML-imported exercises have free-form descriptions that don't match → `riem_num = 0`, which is never in `riem_set` → excluded. These exercises can never reach a playlist via the existing command.

---

## Scope

- Units 9/10: manually curated MusicXML uploads (teacher provides). Need tagging + playlist wiring.
- Units 11+: automated phrase import works end-to-end. Just needs play-mode import run via admin UI.
- No segment-carving logic needed (teacher curates units 9/10 directly; units 11+ use whole phrases).

---

## Design

### Fix 1 — `create_unit_playlist`: allow non-Riem exercises for play mode

In `create_unit_playlist.py`, the riem-filter on line 209 gates all candidates through `_extract_riem_phrase`. For `mode=play`, exercises may have arbitrary descriptions (MusicXML imports, custom segments). 

**Change:** when `mode == "play"`, skip the `riem_num not in riem_set` filter. Include all exercises tagged `unit:N` + `mode:play` authored by the given user, regardless of description shape.

For modes `roman`/`figures`/`matching`, keep existing Riem filter unchanged.

```python
# create_unit_playlist.py — in the candidate loop
for ex in candidates:
    if mode != "play":
        riem_num, _ = Command._extract_riem_phrase(ex.description or "")
        if riem_num not in riem_set:
            continue
    if require_new_chords and not Command._has_new_chord(ex, unit_num, family):
        ...
        continue
    selected.append(ex)
```

### Fix 2 — MusicXML import: stamp UMTO tags

The existing admin MusicXML importer (`import_musicxml_view` in `admin.py`) creates a legacy `chorale` exercise with no `skill_tags`. For units 9/10 play exercises, the teacher needs to:

1. Upload MusicXML via admin → exercise created (legacy chorale format)
2. Set `skill_tags = ["unit:9", "mode:play"]` and `complexity` on the exercise

**Option A (minimal):** Teacher manually edits skill_tags in the Django admin exercise form after upload. No code change.

**Option B (better UX):** Add `unit` and `mode` fields to the MusicXML import admin form. Pre-populate `skill_tags` automatically on creation.

**Decision:** Option B. The MusicXML import form already collects `title`, `is_public`, `start_measure`, `end_measure`. Adding `unit` (number, optional) and `mode` (select: play/roman/figures, default=play) is a small addition. When provided, stamp `unit:N` and `mode:play` on the exercise at creation time.

Also: MusicXML-imported exercises are legacy `chorale` type. For playlist wiring they need `skill_tags`. The existing `ExercisePlaylistOrdered` link works for any exercise type — no UMTO requirement for play mode exercises in playlists.

### Fix 3 — Admin UI: expose play-mode import for units 11+

The "Generate Content" admin page already has the `play` option in the mode dropdown and correctly calls `create_unit_playlist --mode play`. No template change needed.

**Operational note:** To populate unit 11 play playlist:
1. Admin → Generate Content
2. Unit: 11, Riemenschneider range: (appropriate range), Mode: Play
3. Click "Import exercises & create playlist"

This runs `create_unit_playlist` → calls `import_bach_phrases --mode play` → creates UMTO exercises with `skill_tags=['unit:11', 'mode:play', ...]` → builds playlist. Already works once Fix 1 is in place (Fix 1 is only needed for MusicXML/non-Riem exercises; the Riem path is already gated correctly for roman/figures).

Wait — actually Fix 1 is needed for play mode even for Riem-based exercises if `riem_set` is built from the `--riemenschneider` argument range. If the admin ran the import for riemenschneider `1-30` and now runs playlist-only for `1-30`, exercises imported in that range ARE in `riem_set`. So for Riem-based play exercises, the existing filter works. Fix 1 only matters for non-Riem play exercises (units 9/10 MusicXML uploads).

**Revised Fix 1:** Conditioned on both `mode == "play"` AND `riem_num == 0` (i.e., non-Riem description). If `riem_num > 0`, the Riem filter still applies even in play mode (to respect the `--riemenschneider` range scoping).

```python
for ex in candidates:
    riem_num, _ = Command._extract_riem_phrase(ex.description or "")
    is_non_riem = (riem_num == 0)
    if not is_non_riem and riem_num not in riem_set:
        continue
    # non-Riem play exercises (MusicXML) pass through unconditionally
    # (already filtered by unit:N + mode:play tags in candidates query)
    ...
```

---

### Fix 4 — `--riemenschneider` optional for play+playlist-only

`--riemenschneider` is currently required even with `--playlist-only`. For units 9/10 (MusicXML-only), there is no Riem range. Make `--riemenschneider` optional; when absent and mode is play, `riem_set` is treated as "match all" (the `riem_num == 0` pass-through in Fix 1 already handles this). The admin UI passes `riemenschneider` from the form field — add a note that it can be left blank for units 9/10 play playlists.

In the command: `required=False, default=None`. When `options["riemenschneider"]` is None, set `riem_set = None` and skip the riem filter entirely in the candidate loop.

---

## Files Changed

| File | Change |
|---|---|
| `apps/exercises/management/commands/create_unit_playlist.py` | (1) Allow non-Riem exercises when `riem_num == 0`; (2) make `--riemenschneider` optional |
| `apps/exercises/admin.py` → `import_musicxml_view` | Add `unit` + `mode` fields to form; stamp `skill_tags` on created exercise |
| `apps/exercises/templates/admin/exercises/exercise/import_musicxml.html` | Add unit/mode fields to import form |

---

## What Is NOT Changed

- `import_bach_phrases.py` — no changes
- `generate_content.html` — no changes  
- JS exercise definition / grader — no changes
- No segment-carving logic (units 9/10 handled via curated MusicXML)

---

## Testing

1. Upload a MusicXML file with `unit=9`, `mode=play` → verify exercise has `skill_tags=['unit:9', 'mode:play']`
2. Run `create_unit_playlist --unit 9 --riemenschneider 1 --mode play --playlist-only` → verify the MusicXML exercise appears in the playlist
3. Run `create_unit_playlist --unit 11 --riemenschneider 1-5 --mode play` → verify exercises imported, linked to playlist, playlist non-empty
4. Verify existing roman/figures playlists unaffected (Riem filter still applies for those modes)
