from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.exercises.models import Playlist


def accessible_playlist_queryset(user) -> QuerySet[Playlist]:
    return Playlist.objects.filter(
        Q(is_public=True)
        | Q(authored_by=user)
        | Q(authored_by__content_permits__contains=user.id)
    ).distinct()


def user_can_access_playlist(user, playlist: Playlist) -> bool:
    if playlist.is_public:
        return True
    if getattr(playlist, "authored_by_id", None) == getattr(user, "id", None):
        return True
    author = getattr(playlist, "authored_by", None)
    permits = getattr(author, "content_permits", []) or []
    return getattr(user, "id", None) in permits
