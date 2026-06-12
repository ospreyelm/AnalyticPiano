"""Transposition service for creating UMTO chordal Exercise copies in different keys.

This module provides a reusable function for generating transposed copies of a source
UMTO chordal exercise across multiple keys. It handles key validation, chord transposition,
and playlist management.
"""
import logging
from typing import Optional

from django.contrib.auth import get_user_model

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.exercises.constants import all_sigs, pseudo_key_to_sig, all_keys
from apps.exercises.utils.transpose import compute_key_target

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sig_for_clean_key(clean_key: str) -> str | None:
    """Convert a clean key name (e.g. 'G', 'Bb', 'F#m') to a sig string.

    Returns None when the key cannot be resolved.
    """
    # Minor keys: e.g. 'F#m' → pseudo-key 'f#', 'Am' → 'a'
    if clean_key.endswith("m"):
        root = clean_key[:-1]
        pseudo = root[0].lower() + root[1:]
    else:
        pseudo = clean_key

    sig = pseudo_key_to_sig.get(pseudo)
    return sig  # may be None for unknown keys


def _compute_vector_and_key(sig_orig: str, sig_target: str, key_orig_hl: str) -> tuple[int, str | None]:
    """Return (midi_vector, key_target_hl).

    midi_vector: signed semitone shift using the shortest-interval rule (<=6).
    key_target_hl: HarmonyLab key token, or None on failure.
    """
    from apps.exercises.constants import sig_to_pc

    pc_vector = (12 + sig_to_pc[sig_target] - sig_to_pc[sig_orig]) % 12
    if pc_vector >= 6:
        midi_vector = pc_vector - 12
    else:
        midi_vector = pc_vector

    key_target = compute_key_target(key_orig_hl, sig_orig, sig_target)
    return midi_vector, key_target


def _transpose_chords(chords: list[dict], midi_vector: int) -> list[dict]:
    """Return new chord list with shifted MIDI, dropping spelling."""
    result = []
    for c in chords:
        new_chord = {
            "offset": c["offset"],
            "duration": c["duration"],
            "visible": [p + midi_vector for p in c.get("visible", [])],
            "hidden": [p + midi_vector for p in c.get("hidden", [])],
        }
        # Drop spelling — it is pitch-specific and not re-spelled here.
        # (caller can pass spelling=None; save_chordal_umto_exercise accepts it)
        result.append(new_chord)
    return result


def _hl_key_to_display(hl_key: str) -> str:
    """Convert HarmonyLab token to a human-readable display string."""
    # e.g. 'jG_' -> 'G major', 'iF#' -> 'F# minor'
    if not hl_key or hl_key == "h":
        return hl_key or "?"
    mode = "minor" if hl_key.startswith("i") else "major"
    note = hl_key[1:].rstrip("_")
    return f"{note} {mode}"


def _next_playlist_order(playlist: Playlist) -> int:
    """Return the next available order index for a playlist."""
    existing = ExercisePlaylistOrdered.objects.filter(playlist=playlist)
    if not existing.exists():
        return 1
    return existing.order_by("-order").values_list("order", flat=True).first() + 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_transposed_copies(
    source_exercise: Exercise,
    key_set: list[str],
    playlist: Optional[Playlist] = None,
    author: Optional[User] = None,
    is_official: bool = False,
    overwrite: bool = False,
) -> list[Exercise]:
    """Generate transposed copies of a UMTO chordal exercise in different keys.

    Args:
        source_exercise: Source Exercise instance (must be UMTO chordal).
        key_set: List of clean key strings (e.g., ["G", "Bb", "F#m"]).
        playlist: Optional Playlist instance to add exercises to.
        author: Optional User instance; defaults to source_exercise.authored_by.
        is_official: If True, set is_official=True on created exercises.
        overwrite: If True, update existing exercises instead of skipping.

    Returns:
        List of Exercise instances (created or updated; errors are skipped but logged).

    Raises:
        ValueError: If source_exercise is not UMTO chordal.
    """
    # ---- Validate source is UMTO chordal ----
    source_umto = source_exercise.data.get("score", {}).get("umto", {})
    if not source_exercise.data.get("isUMTO") or not source_umto:
        raise ValueError(
            f"Exercise {source_exercise.id} is not a UMTO exercise. "
            "generate_transposed_copies only works with UMTO chordal exercises."
        )
    if source_umto.get("metadata", {}).get("score_kind") != "chordal":
        raise ValueError(
            f"Exercise {source_exercise.id} is a UMTO exercise but not chordal "
            f"(score_kind={source_umto.get('metadata', {}).get('score_kind')!r}). "
            "generate_transposed_copies requires score_kind='chordal'."
        )

    # ---- Resolve author ----
    if author is None:
        author = source_exercise.authored_by

    # ---- Extract source metadata ----
    meta = source_umto.get("metadata", {})
    source_key_hl = meta.get("key", "")  # HarmonyLab token e.g. 'jC_'
    meter = meta.get("meter")
    clef = meta.get("clef", "keyboard")
    barline_offsets = meta.get("barline_offsets") or []
    complexity = source_exercise.complexity or 1
    source_chords = source_umto.get("chords", [])
    source_analysis = source_umto.get("analysis", [])
    staff_distribution = (
        source_exercise.data.get("staffDistribution")
        or source_umto.get("metadata", {}).get("staffDistribution")
        or clef
    )

    # Determine source sig from source_key_hl
    # The key in UMTO metadata is stored as 'jC_' style (HarmonyLab format).
    # Map via all_keys → all_sigs index.
    try:
        key_idx = all_keys.index(source_key_hl)
        # all_sigs[i] corresponds to all_keys[2*i] and all_keys[2*i+1]
        sig_orig = all_sigs[key_idx // 2]
    except (ValueError, IndexError):
        # Fall back: try pseudo_key_to_sig with stripped HL token
        stripped = source_key_hl.lstrip("ij").rstrip("_")
        sig_orig = pseudo_key_to_sig.get(stripped, "")

    # ---- Process each requested key ----
    created_exercises = []

    for clean_key in key_set:
        sig_target = _sig_for_clean_key(clean_key)
        if sig_target is None:
            logger.warning(f"Unknown key: {clean_key}, skipping")
            continue

        midi_vector, key_target_hl = _compute_vector_and_key(
            sig_orig, sig_target, source_key_hl
        )
        if key_target_hl is None:
            logger.warning(f"Key out of range: {clean_key}, skipping")
            continue

        transposed_chords = _transpose_chords(source_chords, midi_vector)

        # Description identifies this copy uniquely
        description = f"{source_exercise.description} ({clean_key})"

        # skill_tags: source tags + transposed_from tag
        transposed_from_tag = f"transposed_from:{source_exercise.id}"
        base_tags = list(source_exercise.skill_tags or [])
        # Avoid duplicating the transposed_from tag if already present
        tags = [t for t in base_tags if not t.startswith("transposed_from:")]
        tags.append(transposed_from_tag)

        # Check if already exists (idempotency)
        existing = Exercise.objects.filter(
            description=description, authored_by=author
        ).first()
        if existing and not overwrite:
            logger.info(f"Exercise already exists: {existing.id}, skipping")
            # Still add to playlist if requested
            if playlist:
                already_in = ExercisePlaylistOrdered.objects.filter(
                    playlist=playlist, exercise=existing
                ).exists()
                if not already_in:
                    order = _next_playlist_order(playlist)
                    ExercisePlaylistOrdered.objects.create(
                        playlist=playlist, exercise=existing, order=order
                    )
            created_exercises.append(existing)
            continue

        # Build + save the transposed exercise
        try:
            ex = save_chordal_umto_exercise(
                description=description,
                author=author,
                chords=transposed_chords,
                key=key_target_hl,
                meter=meter,
                clef=clef,
                staff_distribution=staff_distribution,
                source=meta.get("source", source_exercise.description or ""),
                skill_tags=tags,
                complexity=complexity,
                is_public=source_exercise.is_public,
                overwrite=overwrite,
                auto_playlist=False,
                barline_offsets=barline_offsets,
                # Copy analysis slices as-is — they use key-relative labels.
                analysis=source_analysis,
            )
            # Set is_official after creation if requested
            if is_official:
                ex.is_official = is_official
                ex.save(update_fields=["is_official"])
            created_exercises.append(ex)
            logger.info(f"Created transposed exercise: {ex.id} in key {clean_key} (vector={midi_vector:+d})")
        except Exception as exc:
            logger.error(f"Failed to create transposed exercise in key {clean_key}: {exc}")
            continue

        # Add to playlist if requested
        if playlist:
            already_in = ExercisePlaylistOrdered.objects.filter(
                playlist=playlist, exercise=ex
            ).exists()
            if not already_in:
                order = _next_playlist_order(playlist)
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist, exercise=ex, order=order
                )

    return created_exercises
