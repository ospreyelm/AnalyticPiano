from __future__ import annotations

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


def _resolve_unit1_playlist_id(lane_key: str, lane: Unit1Lane) -> str:
    canonical_author_email = getattr(settings, "UNIT1_CURRICULUM_AUTHOR_EMAIL", None)

    for candidate_name in lane["playlist_name_candidates"]:
        candidates = [
            playlist
            for playlist in Playlist.objects.filter(name=candidate_name).order_by("_id")
            if _is_unit1_tagged(playlist)
        ]
        if not candidates:
            continue

        if canonical_author_email:
            author_scoped = [
                playlist
                for playlist in candidates
                if playlist.authored_by and playlist.authored_by.email == canonical_author_email
            ]
            if len(author_scoped) == 1:
                return author_scoped[0].id
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

        return candidates[0].id

    raise Playlist.DoesNotExist(
        f"No Unit 1 playlist found for canonical lane {lane_key}. Tried: {lane['playlist_name_candidates']}"
    )


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
    playlist_ids: dict[str, str] = {}
    for lane_key, lane in UNIT1_CANONICAL_LANES.items():
        playlist_ids[lane_key] = _resolve_unit1_playlist_id(lane_key, lane)

    return playlist_ids


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

