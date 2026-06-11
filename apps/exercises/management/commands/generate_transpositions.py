"""generate_transpositions — batch-create transposed UMTO chordal Exercise copies.

Usage
-----
python manage.py generate_transpositions \\
    --exercise EA0001 \\
    --keys C,G,Bb,F#m \\
    [--playlist "My Playlist"] \\
    [--author teacher@example.com] \\
    [--overwrite]

Runtime playlist transposition (transpose_requests) does NOT work for UMTO
chordal rows — they lack the legacy top-level data["chord"] + keySignature
fields that transpose() mutates.  This command creates explicit Exercise copies
instead.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.exercises.constants import all_sigs, pseudo_key_to_sig
from apps.exercises.utils.transpose import normalize_key, compute_key_target

User = get_user_model()

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
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Batch-create transposed Exercise copies of a UMTO chordal exercise. "
        "Analysis slices are copied as-is (they are key-relative). "
        "Each copy is tagged transposed_from:<source_id>."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--exercise",
            required=True,
            metavar="EXERCISE_ID",
            help="Source Exercise ID (must be UMTO chordal, e.g. EA0001).",
        )
        parser.add_argument(
            "--keys",
            required=True,
            metavar="C,G,Bb,F#m",
            help=(
                "Comma-separated list of target keys in clean notation "
                "(e.g. C, G, Bb, F#m, Am).  The source key is always included "
                "implicitly; supply it to include a same-key copy in the playlist."
            ),
        )
        parser.add_argument(
            "--playlist",
            default=None,
            metavar="PLAYLIST_NAME",
            help="Get-or-create a playlist by this name and append copies in key order.",
        )
        parser.add_argument(
            "--author",
            default=None,
            metavar="EMAIL",
            help="Author email for created exercises/playlist.  Defaults to source author.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            default=False,
            help=(
                "If an exercise with the same description+author already exists, "
                "update it instead of skipping."
            ),
        )

    def handle(self, *args, **options):
        # ---- resolve source exercise ----
        try:
            source = Exercise.objects.get(id=options["exercise"])
        except Exercise.DoesNotExist as exc:
            raise CommandError(
                f"Exercise not found: {options['exercise']}"
            ) from exc

        # Validate UMTO chordal
        source_umto = source.data.get("score", {}).get("umto", {})
        if not source.data.get("isUMTO") or not source_umto:
            raise CommandError(
                f"Exercise {source.id} is not a UMTO exercise. "
                "generate_transpositions only works with UMTO chordal exercises."
            )
        if source_umto.get("metadata", {}).get("score_kind") != "chordal":
            raise CommandError(
                f"Exercise {source.id} is a UMTO exercise but not chordal "
                f"(score_kind={source_umto.get('metadata', {}).get('score_kind')!r}). "
                "generate_transpositions requires score_kind='chordal'."
            )

        # ---- resolve author ----
        if options["author"]:
            try:
                author = User.objects.get(email=options["author"])
            except User.DoesNotExist as exc:
                raise CommandError(f"Author not found: {options['author']}") from exc
        else:
            author = source.authored_by

        # ---- parse keys ----
        raw_keys = [k.strip() for k in options["keys"].split(",") if k.strip()]
        if not raw_keys:
            raise CommandError("--keys must be a non-empty comma-separated list.")

        # ---- extract source metadata ----
        meta = source_umto.get("metadata", {})
        source_key_hl = meta.get("key", "")  # HarmonyLab token e.g. 'jC_'
        meter = meta.get("meter")
        clef = meta.get("clef", "keyboard")
        barline_offsets = meta.get("barline_offsets") or []
        complexity = source.complexity or 1
        source_chords = source_umto.get("chords", [])
        source_analysis = source_umto.get("analysis", [])
        staff_distribution = (
            source.data.get("staffDistribution")
            or source_umto.get("metadata", {}).get("staffDistribution")
            or clef
        )

        # Determine source sig from source_key_hl
        # normalize_key converts clean keys; source_key_hl is already in HL format.
        # Reverse-lookup: find sig whose pseudo_key matches source key.
        # The key in UMTO metadata is stored as 'jC_' style.
        # Map via all_keys → all_sigs index.
        from apps.exercises.constants import all_keys
        try:
            key_idx = all_keys.index(source_key_hl)
            # all_keys has 30 entries corresponding to all_sigs positions offset by 1
            # The mapping: all_sigs[i] corresponds to all_keys[2*i] and all_keys[2*i+1]
            # (minor/major pairs), so: sig_index = key_idx // 2
            sig_orig = all_sigs[key_idx // 2]
        except (ValueError, IndexError):
            # Fall back: try pseudo_key_to_sig with stripped HL token
            stripped = source_key_hl.lstrip("ij").rstrip("_")
            sig_orig = pseudo_key_to_sig.get(stripped, "")

        # Build flat list of all MIDI notes in source for range reference
        midi_all = []
        for c in source_chords:
            midi_all.extend(c.get("visible", []))
            midi_all.extend(c.get("hidden", []))

        # ---- process each requested key ----
        results = []  # [(clean_key, status_str, exercise_or_None)]

        playlist = None
        if options["playlist"]:
            playlist, pl_created = Playlist.objects.get_or_create(
                name=options["playlist"],
                authored_by=author,
                defaults={"is_public": source.is_public},
            )
            if pl_created:
                self.stdout.write(f"  Created playlist '{playlist.name}' ({playlist.id})")
            else:
                self.stdout.write(f"  Using existing playlist '{playlist.name}' ({playlist.id})")

        for clean_key in raw_keys:
            sig_target = _sig_for_clean_key(clean_key)
            if sig_target is None:
                results.append((clean_key, "SKIP (unknown key)", None))
                continue

            midi_vector, key_target_hl = _compute_vector_and_key(
                sig_orig, sig_target, source_key_hl
            )
            if key_target_hl is None:
                results.append((clean_key, "SKIP (key out of range)", None))
                continue

            transposed_chords = _transpose_chords(source_chords, midi_vector)

            # Description identifies this copy uniquely
            description = f"{source.description} ({clean_key})"

            # skill_tags: source tags + transposed_from tag
            transposed_from_tag = f"transposed_from:{source.id}"
            base_tags = list(source.skill_tags or [])
            # Avoid duplicating the transposed_from tag if already present
            tags = [t for t in base_tags if not t.startswith("transposed_from:")]
            tags.append(transposed_from_tag)

            # Check if already exists (idempotency)
            existing = Exercise.objects.filter(
                description=description, authored_by=author
            ).first()
            if existing and not options["overwrite"]:
                results.append((clean_key, f"SKIPPED (exists: {existing.id})", existing))
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
                    source=meta.get("source", source.description or ""),
                    skill_tags=tags,
                    complexity=complexity,
                    is_public=source.is_public,
                    overwrite=options["overwrite"],
                    auto_playlist=False,
                    barline_offsets=barline_offsets,
                    # Copy analysis slices as-is — they use key-relative labels.
                    analysis=source_analysis,
                )
            except Exception as exc:
                results.append((clean_key, f"ERROR: {exc}", None))
                continue

            if playlist:
                already_in = ExercisePlaylistOrdered.objects.filter(
                    playlist=playlist, exercise=ex
                ).exists()
                if not already_in:
                    order = _next_playlist_order(playlist)
                    ExercisePlaylistOrdered.objects.create(
                        playlist=playlist, exercise=ex, order=order
                    )

            action = "UPDATED" if (existing and options["overwrite"]) else "CREATED"
            results.append((clean_key, f"{action}: {ex.id} (vector={midi_vector:+d})", ex))

        # ---- print result table ----
        self.stdout.write("")
        self.stdout.write(f"Source: {source.id} — {source.description}")
        self.stdout.write(f"{'Key':<12} {'Result'}")
        self.stdout.write("-" * 60)
        for clean_key, status, _ex in results:
            self.stdout.write(f"  {clean_key:<10} {status}")
        self.stdout.write("")

        ok = sum(1 for _, s, _ in results if s.startswith(("CREATED", "UPDATED", "SKIPPED")))
        errors = sum(1 for _, s, _ in results if s.startswith("ERROR"))
        skips = sum(1 for _, s, _ in results if s.startswith("SKIP "))
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {ok} exercise(s) ready, {skips} invalid key(s), {errors} error(s)."
            )
        )
