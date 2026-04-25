"""
apps/student/unit_progress.py

Service layer for the unit progress page.  Provides a single entry-point,
get_unit_progress_data(), that returns a fully-rendered data structure ready
for the template.

No Django views live here; the function is intentionally importable in tests
without starting the HTTP stack.
"""
from __future__ import annotations

from django.urls import reverse, NoReverseMatch

from apps.exercises.models import PerformanceData, Playlist, StudentSkillMastery
from apps.exercises.taxonomy_reader import TaxonomyReader


def _get_skill_level(user, skill_tag: str) -> str:
    """Return the StudentSkillMastery level for (user, skill_tag), or 'not_started'."""
    try:
        mastery = StudentSkillMastery.objects.get(user=user, skill_tag=skill_tag)
        return mastery.level
    except StudentSkillMastery.DoesNotExist:
        return StudentSkillMastery.LEVEL_NOT_STARTED


def _get_playlists_for_unit(unit_tags: list[str]) -> list[Playlist]:
    """
    Return all Playlist rows whose skill_tags overlap with the unit's tag list.
    Uses a Python-level set intersection after a broad DB query so that we don't
    rely on database-specific array-overlap operators.
    """
    unit_tag_set = set(unit_tags)
    # Fetch all playlists that have at least one skill_tag (non-empty).
    # We then filter in Python to find those whose skill_tags intersect unit_tags.
    candidate_playlists = Playlist.objects.exclude(skill_tags=[])
    matching = [
        pl for pl in candidate_playlists
        if unit_tag_set & set(pl.skill_tags or [])
    ]
    return matching


def _playlist_primary_tag(playlist: Playlist, unit_tags: list[str]) -> str | None:
    """Return the first unit tag that appears in the playlist's skill_tags list."""
    unit_tag_set = set(unit_tags)
    for tag in (playlist.skill_tags or []):
        if tag in unit_tag_set:
            return tag
    return None


def _playlist_stats(user, playlist: Playlist) -> dict:
    """
    Compute per-playlist completion stats for a given user.

    Returns:
        done          - count of unique exercise IDs completed at least once
        last_score_pct - percentage from the most recent entry that has
                         score_numerator, or None if no such entry exists
        url           - URL to resume the playlist at exercise 1
    """
    # Aggregate all PerformanceData rows for (user, playlist) across all courses
    pd_rows = PerformanceData.objects.filter(user=user, playlist=playlist)

    # Unique exercise IDs across all rows and all data entries
    completed_ids: set[str] = {
        entry["id"]
        for pd in pd_rows
        for entry in (pd.data or [])
        if "id" in entry
    }
    done = len(completed_ids)

    # Last score: most recent data entry with score_numerator present.
    # PerformanceData rows are ordered by creation; entries within each row
    # are appended chronologically.  We collect all scored entries and take
    # the last.
    last_score_pct = None
    all_scored_entries = [
        entry
        for pd in pd_rows.order_by("created")
        for entry in (pd.data or [])
        if "score_numerator" in entry
    ]
    if all_scored_entries:
        last_entry = all_scored_entries[-1]
        try:
            numerator = last_entry["score_numerator"]
            denominator = last_entry["score_denominator"]
            if denominator and denominator > 0:
                last_score_pct = round(numerator / denominator * 100)
        except (KeyError, TypeError, ZeroDivisionError):
            pass

    # Build playlist URL targeting the student exercise player
    from apps.exercises.taxonomy_reader import TaxonomyReader
    unit_num = 1  # Default fallback for pilot
    for tag in (playlist.skill_tags or []):
        unit = TaxonomyReader.get_unit_for_tag(tag)
        if unit:
            unit_num = int(unit.get("n", 1))
            break

    url = reverse(
        "student:player",
        kwargs={"unit_num": unit_num},
    ) + f"?playlist={playlist.id}&exercise_num=1"

    return {
        "id": playlist.id,
        "name": playlist.name,
        "done": done,
        "total": playlist.exercise_count,
        "last_score_pct": last_score_pct,
        "url": url,
    }


def get_unit_progress_data(user, unit_n: str) -> dict | None:
    """
    Return all data needed to render the unit progress page for the given unit.

    Parameters
    ----------
    user    : Django User instance (must be authenticated)
    unit_n  : Unit number as a string, e.g. ``"1"`` or ``"9"``

    Returns
    -------
    dict
        Keys: ``unit``, ``tier``, ``bar_segments``, ``skill_cards``
    None
        If *unit_n* does not exist in the taxonomy (caller should raise Http404)
    """
    unit_n = str(unit_n)
    unit = TaxonomyReader.get_unit(unit_n)
    if unit is None:
        return None

    tier = TaxonomyReader.get_tier_for_unit(unit_n) or {}
    unit_tags: list[str] = unit.get("tags", [])

    # --- Bar segments (one per skill tag) ---
    bar_segments = [
        {
            "tag": tag,
            "label": TaxonomyReader.get_skill_label(tag),
            "level": _get_skill_level(user, tag),
        }
        for tag in unit_tags
    ]

    # --- Group playlists by skill tag ---
    matching_playlists = _get_playlists_for_unit(unit_tags)

    # Build a map: skill_tag -> [playlist_stat_dict, ...]
    tag_to_playlists: dict[str, list[dict]] = {tag: [] for tag in unit_tags}
    for playlist in matching_playlists:
        primary_tag = _playlist_primary_tag(playlist, unit_tags)
        if primary_tag is None:
            continue
        stats = _playlist_stats(user, playlist)
        tag_to_playlists[primary_tag].append(stats)

    # Sort playlists within each skill card by name for stable ordering
    for tag in tag_to_playlists:
        tag_to_playlists[tag].sort(key=lambda p: p["name"])

    # --- Skill cards ---
    skill_cards = [
        {
            "tag": tag,
            "label": TaxonomyReader.get_skill_label(tag),
            "level": _get_skill_level(user, tag),
            "playlists": tag_to_playlists.get(tag, []),
        }
        for tag in unit_tags
    ]

    return {
        "unit": unit,
        "tier": tier,
        "bar_segments": bar_segments,
        "skill_cards": skill_cards,
    }
