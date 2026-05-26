"""Batch-create harmonization exercises for QA tagging.

Imports Riemenschneider phrases (range below) as `roman`-mode source
exercises, then derives a locked-bass harmonization variant from each.
Groups every harmonization exercise into a single Playlist so they can be
opened back-to-back in the dashboard for manual review of figured-bass
emission on ornamental bass notes.

Usage:
    python scratch/batch_harmonization_qa.py

Re-running is safe: the tag-based source query and Playlist name are
idempotent — existing entries are reused, missing ones are created.
"""
import os
import sys

import django
from django.core.management import call_command

# Allow running from the repo root: `python scratch/batch_harmonization_qa.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.local")
django.setup()

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist  # noqa: E402
from apps.accounts.models import User  # noqa: E402


# ---------------------------------------------------------------------------
# Config — edit these to retarget the batch.
# ---------------------------------------------------------------------------
AUTHOR_EMAIL = "avner-local2025@localhost"
R_RANGE = range(1, 21)                       # R1 .. R20 inclusive
SOURCE_TAG = "qa:harm_fb_audit_2026_05_17"  # unique → safe to query later
HARM_TAG = "qa:harm_fb_audit_2026_05_17"    # also stamped on harm derivative
PLAYLIST_NAME = "QA: Harmonization figured-bass audit (R1-R20)"
LOCKED_VOICES = "B"
MIN_VOICES = 3
MAX_VOICES = 4


def get_or_fail_author() -> User:
    try:
        return User.objects.get(email=AUTHOR_EMAIL)
    except User.DoesNotExist as exc:
        raise SystemExit(
            f"Author {AUTHOR_EMAIL!r} not found. Create the user or change AUTHOR_EMAIL."
        ) from exc


def import_sources():
    """Create roman-mode source exercises for each R-number, tagged with SOURCE_TAG."""
    for riem in R_RANGE:
        print(f"\n=== Riemenschneider {riem}: importing roman-mode sources ===")
        try:
            call_command(
                "import_bach_phrases",
                riemenschneider=riem,
                author=AUTHOR_EMAIL,
                mode="roman",
                extra_tags=[SOURCE_TAG, f"riem:{riem}"],
            )
        except Exception as e:
            print(f"  ! import_bach_phrases R{riem} failed: {e}")


def derive_harmonizations(author: User) -> list[Exercise]:
    """For every source tagged SOURCE_TAG, run generate_harmonization.

    Returns the list of harmonization Exercise rows (existing or newly created).
    """
    sources = list(
        Exercise.objects.filter(
            skill_tags__contains=[SOURCE_TAG],
            authored_by=author,
        ).order_by("_id")
    )
    print(f"\n=== {len(sources)} source exercises tagged {SOURCE_TAG!r} ===")

    harms: list[Exercise] = []
    for source in sources:
        # Skip sources that are already harmonization rows (re-runs).
        mode = (source.data or {}).get("mode")
        if mode == "harmonization":
            continue

        print(f"  → generate_harmonization --source {source.id}")
        try:
            call_command(
                "generate_harmonization",
                source=str(source.id),
                author=AUTHOR_EMAIL,
                locked_voices=LOCKED_VOICES,
                prompt="figured_bass",
                min_voices=MIN_VOICES,
                max_voices=MAX_VOICES,
                public=False,
            )
        except Exception as e:
            print(f"    ! failed: {e}")
            continue

        # Locate the derived harmonization. generate_harmonization names it
        # f"Harm/{source.id}/L=B/v{min}-{max}" (truncated to 60 chars).
        desc_prefix = f"Harm/{source.id}/L={LOCKED_VOICES}/"
        derived = (
            Exercise.objects.filter(
                description__startswith=desc_prefix,
                authored_by=author,
            )
            .order_by("-_id")
            .first()
        )
        if derived is None:
            print(f"    ! could not locate derived harmonization for source {source.id}")
            continue

        # Tag the derivative so the playlist query can find it.
        if HARM_TAG not in (derived.skill_tags or []):
            derived.skill_tags = list(derived.skill_tags or []) + [HARM_TAG]
            derived.save(update_fields=["skill_tags"])

        harms.append(derived)

    return harms


def build_playlist(author: User, harms: list[Exercise]):
    print(f"\n=== Building/refreshing Playlist {PLAYLIST_NAME!r} ===")
    playlist, created = Playlist.objects.get_or_create(
        name=PLAYLIST_NAME,
        authored_by=author,
        defaults=dict(
            is_dynamic=False,
            is_adaptive=False,
            skill_tags=[HARM_TAG],
        ),
    )
    if created:
        print(f"  created new playlist id={playlist.id}")
    else:
        print(f"  reusing existing playlist id={playlist.id}")

    # Wipe + rebuild membership so order matches insertion order in `harms`.
    ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
    for idx, ex in enumerate(harms):
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist,
            exercise=ex,
            order=idx,
        )
    print(f"  linked {len(harms)} harmonization exercise(s)")


def main():
    author = get_or_fail_author()
    import_sources()
    harms = derive_harmonizations(author)
    if not harms:
        print("\nNo harmonization exercises produced — nothing to playlist. Done.")
        return
    build_playlist(author, harms)
    print("\nDone.")


if __name__ == "__main__":
    main()
