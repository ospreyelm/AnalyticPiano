from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.utils.playlist_naming import (
    build_canonical_playlist_name,
    canonical_mode_label,
)


def resolve_canonical_playlist(
    *,
    author,
    unit: str,
    mode: str,
    is_public: bool,
    is_official: bool,
) -> Playlist:
    unit = str(unit)
    canonical_mode_label(mode)  # validates mode; raises ValueError for unsupported values
    name = build_canonical_playlist_name(unit, mode)
    unit_tag = f"unit:{unit}"
    identity = {
        "authored_by": author,
        "playlist_family": Playlist.FAMILY_TEACHER_PLAY,
        "canonical_unit": unit,
        "canonical_mode": mode,
    }

    with transaction.atomic():
        playlist = Playlist.objects.select_for_update().filter(**identity).first()
        if playlist is None:
            legacy_matches = list(
                Playlist.objects.select_for_update().filter(
                    authored_by=author,
                    name=name,
                    playlist_family="",
                )
            )
            if len(legacy_matches) > 1:
                raise ValueError(f"Multiple legacy playlists match {name}.")
            if legacy_matches:
                playlist = legacy_matches[0]
                if playlist.skill_tags != [unit_tag]:
                    raise ValueError(f"Legacy playlist {name} has contradictory unit tags.")
                playlist.playlist_family = Playlist.FAMILY_TEACHER_PLAY
                playlist.canonical_unit = unit
                playlist.canonical_mode = mode
                playlist.is_public = playlist.is_public or is_public
                playlist.is_official = playlist.is_official or is_official
                playlist.save()
            else:
                try:
                    with transaction.atomic():
                        playlist = Playlist.objects.create(
                            name=name,
                            authored_by=author,
                            skill_tags=[unit_tag],
                            is_public=is_public,
                            is_official=is_official,
                            playlist_family=Playlist.FAMILY_TEACHER_PLAY,
                            canonical_unit=unit,
                            canonical_mode=mode,
                        )
                except IntegrityError:
                    playlist = Playlist.objects.select_for_update().get(**identity)

        changed_fields = []
        if is_public and not playlist.is_public:
            playlist.is_public = True
            changed_fields.append("is_public")
        if is_official and not playlist.is_official:
            playlist.is_official = True
            changed_fields.append("is_official")
        if changed_fields:
            playlist.save(update_fields=changed_fields)

        return playlist


def append_exercise_to_canonical_playlist(playlist: Playlist, exercise) -> None:
    """Append an exercise to a canonical teacher-play playlist.

    Appending to the end of a playlist does not invalidate existing student
    performance records (which are tied to specific exercises), so we do not
    block on has_been_performed here.
    """
    with transaction.atomic():
        locked_playlist = Playlist.objects.select_for_update().get(pk=playlist.pk)
        if (
            locked_playlist.playlist_family != Playlist.FAMILY_TEACHER_PLAY
            or locked_playlist.canonical_unit is None
            or not locked_playlist.canonical_mode
        ):
            raise ValueError("append_exercise_to_canonical_playlist requires a canonical teacher playlist.")
        next_order = (
            ExercisePlaylistOrdered.objects.filter(playlist=locked_playlist).aggregate(
                max_order=Max("order")
            )["max_order"]
            or 0
        ) + 1
        ExercisePlaylistOrdered.objects.create(
            playlist=locked_playlist,
            exercise=exercise,
            order=next_order,
        )
