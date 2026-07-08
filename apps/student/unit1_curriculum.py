from __future__ import annotations

from collections import defaultdict
from typing import TypedDict

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.exercises.models import Playlist


class Unit1Lane(TypedDict):
    activity_key: str
    activity_title: str
    lane_key: str
    label: str
    playlist_name: str
    playlist_name_candidates: tuple[str, ...]


UNIT1_CANONICAL_LANES: dict[str, Unit1Lane] = {
    "identify_treble": {
        "activity_key": "identify",
        "activity_title": "Identify",
        "lane_key": "identify_treble",
        "label": "Treble",
        "playlist_name": "Unit 1 - Identify the Notes (Treble)",
        "playlist_name_candidates": ("Unit 1 - Identify the Notes (Treble)", "Unit 1 - Note Names (Treble)"),
    },
    "identify_bass": {
        "activity_key": "identify",
        "activity_title": "Identify",
        "lane_key": "identify_bass",
        "label": "Bass",
        "playlist_name": "Unit 1 - Identify the Notes (Bass)",
        "playlist_name_candidates": ("Unit 1 - Identify the Notes (Bass)", "Unit 1 - Note Names (Bass)"),
    },
    "play_from_name_treble": {
        "activity_key": "play_from_name",
        "activity_title": "Play from Name",
        "lane_key": "play_from_name_treble",
        "label": "Treble",
        "playlist_name": "Unit 1 - Play from Name (Treble)",
        "playlist_name_candidates": ("Unit 1 - Play from Name (Treble)", "Unit 1 - Note Names (Treble Name)"),
    },
    "play_from_name_bass": {
        "activity_key": "play_from_name",
        "activity_title": "Play from Name",
        "lane_key": "play_from_name_bass",
        "label": "Bass",
        "playlist_name": "Unit 1 - Play from Name (Bass)",
        "playlist_name_candidates": ("Unit 1 - Play from Name (Bass)", "Unit 1 - Note Names (Bass Name)"),
    },
    "play_the_notes_treble": {
        "activity_key": "play_the_notes",
        "activity_title": "Play the Notes",
        "lane_key": "play_the_notes_treble",
        "label": "Treble",
        "playlist_name": "Unit 1 - Play the Notes (Treble)",
        "playlist_name_candidates": ("Unit 1 - Play the Notes (Treble)", "Unit 1 - Note Names (Treble Play)"),
    },
    "play_the_notes_bass": {
        "activity_key": "play_the_notes",
        "activity_title": "Play the Notes",
        "lane_key": "play_the_notes_bass",
        "label": "Bass",
        "playlist_name": "Unit 1 - Play the Notes (Bass)",
        "playlist_name_candidates": ("Unit 1 - Play the Notes (Bass)", "Unit 1 - Note Names (Bass Play)"),
    },
}


def _is_unit1_tagged(playlist: Playlist) -> bool:
    return "unit:1" in (playlist.skill_tags or []) or "unit:1" in (playlist.tags or [])


def _pick_lane_playlist(
    lane_key: str,
    lane: Unit1Lane,
    by_name: dict[str, list[Playlist]],
    canonical_author_email: str | None,
) -> Playlist:
    """Resolve one lane against a pre-fetched name→playlists map.

    Replicates the old per-lane resolver's candidate iteration order, author
    scoping, ambiguity (ImproperlyConfigured), and miss (DoesNotExist) semantics
    on data fetched in a single query by ``resolve_unit1_lane_playlists``.
    """
    for candidate_name in lane["playlist_name_candidates"]:
        candidates = by_name.get(candidate_name, [])
        if not candidates:
            continue

        if canonical_author_email:
            author_scoped = [
                playlist
                for playlist in candidates
                if playlist.authored_by and playlist.authored_by.email == canonical_author_email
            ]
            if len(author_scoped) == 1:
                return author_scoped[0]
            if len(author_scoped) > 1:
                raise ImproperlyConfigured(
                    f"Ambiguous Unit 1 playlist mapping for {lane_key}: {candidate_name} "
                    f"under author {canonical_author_email}"
                )
            continue

        if len(candidates) > 1:
            raise ImproperlyConfigured(
                f"Ambiguous Unit 1 playlist mapping for {lane_key}: {candidate_name}. "
                "Set UNIT1_CURRICULUM_AUTHOR_EMAIL to scope the curated Unit 1 source."
            )

        return candidates[0]

    raise Playlist.DoesNotExist(
        f"No Unit 1 playlist found for canonical lane {lane_key}. Tried: {lane['playlist_name_candidates']}"
    )


def resolve_unit1_lane_playlists() -> dict[str, Playlist]:
    """Resolve every canonical Unit-1 lane to its curated Playlist in ONE query.

    Returns ``{lane_key: Playlist}`` in ``UNIT1_CANONICAL_LANES`` order. The
    playlists' ``authored_by`` is prefetched so author scoping needs no extra
    query. Raises ``Playlist.DoesNotExist`` if any lane is unresolved and
    ``ImproperlyConfigured`` on ambiguous mappings — same contract as the old
    per-lane resolver, batched.
    """
    canonical_author_email = getattr(settings, "UNIT1_CURRICULUM_AUTHOR_EMAIL", None)

    candidate_names = sorted(
        {name for lane in UNIT1_CANONICAL_LANES.values() for name in lane["playlist_name_candidates"]}
    )
    rows = (
        Playlist.objects.filter(name__in=candidate_names)
        .select_related("authored_by")
        .order_by("_id")
    )
    by_name: dict[str, list[Playlist]] = defaultdict(list)
    for playlist in rows:
        if _is_unit1_tagged(playlist):
            by_name[playlist.name].append(playlist)

    resolved: dict[str, Playlist] = {}
    for lane_key, lane in UNIT1_CANONICAL_LANES.items():
        resolved[lane_key] = _pick_lane_playlist(lane_key, lane, by_name, canonical_author_email)
    return resolved


def get_unit1_lane_groups() -> list[dict[str, object]]:
    playlist_ids = get_unit1_playlist_ids()
    groups: list[dict[str, object]] = []
    current_group: dict[str, object] | None = None

    for lane_key, lane in UNIT1_CANONICAL_LANES.items():
        if current_group is None or current_group["key"] != lane["activity_key"]:
            current_group = {
                "key": lane["activity_key"],
                "title": lane["activity_title"],
                "lanes": [],
            }
            groups.append(current_group)

        lane_with_id = dict(lane)
        lane_with_id["playlist_id"] = playlist_ids[lane_key]
        current_group["lanes"].append(lane_with_id)

    return groups


def get_unit1_playlist_ids() -> dict[str, str]:
    return {
        lane_key: playlist.id
        for lane_key, playlist in resolve_unit1_lane_playlists().items()
    }


CHALLENGE_GROUPS = {
    "treble": {
        "name": "Treble Mastery Challenge",
        "lane_keys": ["identify_treble", "play_from_name_treble", "play_the_notes_treble"],
    },
    "bass": {
        "name": "Bass Mastery Challenge",
        "lane_keys": ["identify_bass", "play_from_name_bass", "play_the_notes_bass"],
    },
}

def get_unit1_challenge_groups() -> dict:
    return CHALLENGE_GROUPS

def get_unit1_challenge_source_exercises(group_key: str) -> dict[str, list]:
    from apps.exercises.models import ExercisePlaylistOrdered
    group = CHALLENGE_GROUPS.get(group_key)
    if not group:
        return {}
        
    playlist_ids = get_unit1_playlist_ids()
    result = {}
    for lane_key in group["lane_keys"]:
        p_id = playlist_ids.get(lane_key)
        if not p_id:
            result[lane_key] = []
            continue
            
        epos = ExercisePlaylistOrdered.objects.filter(
            playlist__id=p_id,
            is_mastery_challenge_source=True
        ).select_related("exercise").order_by("order")
        
        result[lane_key] = [epo.exercise for epo in epos]
    return result

