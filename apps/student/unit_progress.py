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
from apps.student.player_progression import is_completed_identification_attempt
from apps.exercises.taxonomy_reader import TaxonomyReader
from apps.student.access import accessible_playlist_queryset
from apps.student.progress import TAG_ALIASES
from apps.student.unit1_curriculum import get_unit1_lane_groups


def _get_skill_level(user, skill_tag: str) -> str:
    """
    Return the best StudentSkillMastery level for a display skill tag.

    Some student-facing Unit 1 tags are aggregate display buckets, such as
    ``clefs``, which should reflect mastery from underlying canonical tags like
    ``Read_Treble_Clef`` and ``Read_Bass_Clef``. For non-aliased tags this
    still behaves like a direct lookup.
    """
    canonical_tags = TAG_ALIASES.get(skill_tag, [skill_tag])
    mastery_rows = StudentSkillMastery.objects.filter(
        user=user,
        skill_tag__in=canonical_tags,
    )
    mastery_map = {mastery.skill_tag: mastery.level for mastery in mastery_rows}
    levels = [
        mastery_map.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED)
        for tag in canonical_tags
    ]
    level_order = [
        StudentSkillMastery.LEVEL_MASTERED,
        StudentSkillMastery.LEVEL_PROFICIENT,
        StudentSkillMastery.LEVEL_FAMILIAR,
        StudentSkillMastery.LEVEL_ATTEMPTED,
        StudentSkillMastery.LEVEL_NOT_STARTED,
    ]
    for level in level_order:
        if level in levels:
            return level
    return StudentSkillMastery.LEVEL_NOT_STARTED


def _get_playlists_for_unit(user, unit_tags: list[str], unit_n: str | None = None) -> list[Playlist]:
    """
    Return all Playlist rows tied to a unit by either:
    - overlap with taxonomy unit tags, or
    - explicit unit tag (e.g. unit:11) in playlist tags/skill_tags.

    Uses a Python-level set intersection after a broad DB query so that we don't
    rely on database-specific array-overlap operators.
    """
    unit_tag_set = set(unit_tags)
    explicit_unit_tag = f"unit:{unit_n}" if unit_n is not None else None
    # Fetch all playlists that have at least one skill_tag (non-empty).
    # We then filter in Python to find those whose skill_tags intersect unit_tags.
    candidate_playlists = accessible_playlist_queryset(user).exclude(skill_tags=[])
    matching = [
        pl for pl in candidate_playlists
        if (
            unit_tag_set & set(pl.skill_tags or [])
            or (
                explicit_unit_tag is not None
                and (
                    explicit_unit_tag in (pl.skill_tags or [])
                    or explicit_unit_tag in (pl.tags or [])
                )
            )
        )
    ]
    return matching


def get_next_unit_playlist(user, unit_n: str | int, current_playlist: Playlist) -> Playlist | None:
    """Return the next playlist in the unit after current_playlist (same ordering as the unit page)."""
    unit_n_str = str(unit_n)
    unit = TaxonomyReader.get_unit(unit_n_str)
    if not unit:
        return None
    unit_tags = unit.get("tags", [])
    if not unit_tags:
        return None

    all_playlists = _get_playlists_for_unit(user, unit_tags, unit_n=unit_n_str)

    explicit_unit_tag = f"unit:{unit_n_str}"
    tag_to_playlists: dict[str, list[Playlist]] = {tag: [] for tag in unit_tags}
    for pl in all_playlists:
        primary = _playlist_primary_tag(pl, unit_tags)
        if primary is None:
            if explicit_unit_tag in (pl.skill_tags or []) or explicit_unit_tag in (pl.tags or []):
                primary = unit_tags[0]
        if primary:
            tag_to_playlists[primary].append(pl)

    ordered: list[Playlist] = []
    for tag in unit_tags:
        ordered.extend(sorted(tag_to_playlists[tag], key=lambda p: p.name or ""))

    for i, pl in enumerate(ordered):
        if pl.id == current_playlist.id:
            return ordered[i + 1] if i + 1 < len(ordered) else None
    return None


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
    from apps.exercises.models import IdentificationAttempt
    
    # Aggregate all PerformanceData rows for (user, playlist) across all courses
    pd_rows = PerformanceData.objects.filter(user=user, playlist=playlist)
    ident_attempts = IdentificationAttempt.objects.filter(user=user, playlist=playlist)

    # Unique exercise IDs across all rows and all data entries
    completed_ids: set[str] = {
        entry["id"]
        for pd in pd_rows
        for entry in (pd.data or [])
        if "id" in entry
    }
    
    ident_completed_ids = {
        attempt.exercise.id
        for attempt in ident_attempts
        if attempt.exercise and is_completed_identification_attempt(attempt)
    }
    completed_ids.update(ident_completed_ids)
    done = len(completed_ids)

    # Last score: most recent data entry with score_numerator present.
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

    # Check Identification attempts for scores
    ident_scores = []
    submitted_ident_attempts = [
        attempt
        for attempt in ident_attempts.order_by("submitted_at")
        if attempt.is_page_submit
    ]
    for attempt in submitted_ident_attempts:
        score_data = attempt.score or {}
        correct = score_data.get("correct", 0)
        incorrect = score_data.get("incorrect", 0)
        unanswered = score_data.get("unanswered", 0)
        tot = correct + incorrect + unanswered
        if tot > 0:
            ident_scores.append(round(correct / tot * 100))
            
    if ident_scores:
        last_pd_date = pd_rows.order_by("created").last().created if pd_rows.exists() else None
        last_id_date = submitted_ident_attempts[-1].submitted_at if submitted_ident_attempts else None
        
        if last_id_date and (not last_pd_date or last_id_date > last_pd_date):
            last_score_pct = ident_scores[-1]
        elif last_score_pct is None:
            last_score_pct = ident_scores[-1]

    # Build playlist URL targeting the student exercise player
    from apps.exercises.taxonomy_reader import TaxonomyReader
    unit_num = 1  # Default fallback
    playlist_tags = list(playlist.tags or []) + list(playlist.skill_tags or [])

    # First prefer explicit unit tags (e.g., unit:11), which are common on
    # generated dynamic playlists.
    for tag in playlist_tags:
        if isinstance(tag, str) and tag.startswith("unit:"):
            try:
                unit_num = int(tag.split(":", 1)[1])
                break
            except (TypeError, ValueError):
                continue
    else:
        # Fallback to taxonomy lookup for non-unit tags.
        for tag in playlist_tags:
            unit = TaxonomyReader.get_unit_for_tag(tag)
            if unit:
                unit_num = int(unit.get("n", 1))
                break

    # Determine the next uncompleted exercise number
    next_exercise_num = 1
    ex_ids = playlist.untransposed_exercises_ids
    for idx, ex_id in enumerate(ex_ids, 1):
        if ex_id not in completed_ids:
            next_exercise_num = idx
            break

    url = reverse(
        "student:player",
        kwargs={"unit_num": unit_num},
    ) + f"?playlist={playlist.id}&exercise_num={next_exercise_num}"

    return {
        "id": playlist.id,
        "name": playlist.name,
        "done": done,
        "total": playlist.exercise_count,
        "is_adaptive": bool(playlist.is_adaptive),
        "last_score_pct": last_score_pct,
        "url": url,
    }


def _playlist_stats_by_id(user, playlist_id: str) -> dict:
    playlist = Playlist.objects.get(id=playlist_id)
    return _playlist_stats(user, playlist)


def _dedupe_playlists_by_name(playlists: list[Playlist], user) -> list[Playlist]:
    """
    Reduce same-name playlist duplicates (often from different authors/test data)
    to one visible row per display name.

    Preference order:
    1. playlists authored by the current user
    2. newest playlist by created timestamp/_id
    """
    best_by_name: dict[str, Playlist] = {}

    for pl in playlists:
        key = (pl.name or pl.id).strip().lower()
        current = best_by_name.get(key)
        if current is None:
            best_by_name[key] = pl
            continue

        pl_is_user = bool(getattr(pl, "authored_by_id", None) == getattr(user, "id", None))
        cur_is_user = bool(getattr(current, "authored_by_id", None) == getattr(user, "id", None))

        if pl_is_user and not cur_is_user:
            best_by_name[key] = pl
            continue
        if cur_is_user and not pl_is_user:
            continue

        # Tie-breaker: most recently created / highest _id.
        pl_created = getattr(pl, "created", None)
        cur_created = getattr(current, "created", None)
        if (pl_created and cur_created and pl_created > cur_created) or (
            pl_created == cur_created and getattr(pl, "_id", 0) > getattr(current, "_id", 0)
        ):
            best_by_name[key] = pl

    return sorted(best_by_name.values(), key=lambda p: (p.name or p.id).lower())


def _playlist_progress_level(stats: dict) -> str:
    done = stats.get("done", 0) or 0
    total = stats.get("total", 0) or 0
    last_score_pct = stats.get("last_score_pct")

    if done <= 0:
        return StudentSkillMastery.LEVEL_NOT_STARTED
    if total > 0 and done < total:
        return StudentSkillMastery.LEVEL_ATTEMPTED
    if last_score_pct == 100:
        return StudentSkillMastery.LEVEL_MASTERED
    if last_score_pct is not None and last_score_pct >= 85:
        return StudentSkillMastery.LEVEL_PROFICIENT
    if last_score_pct is not None and last_score_pct >= 70:
        return StudentSkillMastery.LEVEL_FAMILIAR
    return StudentSkillMastery.LEVEL_ATTEMPTED


def _check_challenge_mastery(user, group_key: str) -> bool:
    from apps.exercises.models import (
        ExercisePlaylistOrdered,
        IdentificationAttempt,
        PerformanceData,
        Playlist,
    )
    
    prefix = f"_challenge_{user.id}_{group_key}"
    challenge_playlists = Playlist.objects.filter(authored_by=user, name__startswith=prefix)
    
    for pl in challenge_playlists:
        expected_exercise_ids = list(
            ExercisePlaylistOrdered.objects.filter(playlist=pl)
            .order_by("order")
            .values_list("exercise__id", flat=True)
        )
        if len(expected_exercise_ids) != 6:
            continue

        expected_exercise_set = set(expected_exercise_ids)
        attempts = []
        
        pd_rows = PerformanceData.objects.filter(user=user, playlist=pl)
        for pd in pd_rows:
            for entry in (pd.data or []):
                exercise_id = entry.get("id", "")[:6]
                if exercise_id not in expected_exercise_set:
                    continue
                numerator = entry.get("score_numerator")
                denominator = entry.get("score_denominator")
                is_success = False
                if denominator not in (None, 0):
                    is_success = (numerator == denominator)
                else:
                    is_success = (entry.get("error_tally") in (0, -1, "n/a"))
                    
                attempts.append({
                    "exercise_id": exercise_id,
                    "is_success": is_success
                })
                
        ident_attempts = IdentificationAttempt.objects.filter(
            user=user, 
            playlist=pl,
            is_page_submit=True
        )
        for attempt in ident_attempts:
            exercise_id = attempt.exercise.id[:6] if attempt.exercise else ""
            if exercise_id not in expected_exercise_set:
                continue
            score_data = attempt.score or {}
            is_success = (score_data.get("incorrect", 0) == 0 and score_data.get("unanswered", 0) == 0)
            attempts.append({
                "exercise_id": exercise_id,
                "is_success": is_success
            })
            
        success_ex_ids = {a["exercise_id"] for a in attempts if a["is_success"] and a["exercise_id"]}
        failed_count = sum(1 for a in attempts if not a["is_success"])
        
        if failed_count == 0 and success_ex_ids == expected_exercise_set:
            return True
            
    return False


def _compute_unit1_lane_mastery_level(user, lane_key, playlist_id) -> str:
    from apps.exercises.models import PerformanceData, IdentificationAttempt, ExercisePlaylistOrdered
    
    group_key = "treble" if "treble" in lane_key else "bass"
    if _check_challenge_mastery(user, group_key):
        return StudentSkillMastery.LEVEL_MASTERED
        
    epos = ExercisePlaylistOrdered.objects.filter(playlist__id=playlist_id).select_related("exercise")
    if not epos.exists():
        return StudentSkillMastery.LEVEL_NOT_STARTED
        
    epo_map = {epo.exercise.id[:6]: epo for epo in epos}
    
    advanced_successes = 0
    has_any_attempt = False
    
    pd_rows = PerformanceData.objects.filter(user=user, playlist__id=playlist_id)
    for pd in pd_rows:
        if pd.data:
            has_any_attempt = True
        for entry in (pd.data or []):
            ex_id = entry.get("id", "")[:6]
            epo = epo_map.get(ex_id)
            if not epo:
                continue
                
            numerator = entry.get("score_numerator")
            denominator = entry.get("score_denominator")
            is_success = False
            if denominator not in (None, 0):
                is_success = (numerator == denominator)
            else:
                is_success = (entry.get("error_tally") in (0, -1, "n/a"))
                
            if is_success and epo.difficulty_tier >= 3:
                advanced_successes += 1
                
    ident_attempts = IdentificationAttempt.objects.filter(
        user=user, playlist__id=playlist_id, is_page_submit=True
    )
    if ident_attempts.exists():
        has_any_attempt = True
        
    for attempt in ident_attempts:
        ex_id = attempt.exercise.id[:6] if attempt.exercise else ""
        epo = epo_map.get(ex_id)
        if not epo:
            continue
            
        score_data = attempt.score or {}
        is_success = (score_data.get("incorrect", 0) == 0 and score_data.get("unanswered", 0) == 0)
        
        if is_success and epo.difficulty_tier >= 3:
            advanced_successes += 1
            
    if advanced_successes >= 1:
        return StudentSkillMastery.LEVEL_PROFICIENT
        
    if has_any_attempt:
        return StudentSkillMastery.LEVEL_ATTEMPTED
        
    return StudentSkillMastery.LEVEL_NOT_STARTED


def _get_practice_band(done, total):
    if not total:
        return "not_started"
    pct = (done / total) * 100
    if pct == 0:
        return "not_started"
    if pct <= 20:
        return "getting_started"
    if pct <= 40:
        return "learning"
    if pct <= 60:
        return "practicing"
    if pct <= 80:
        return "fluency_building"
    return "polishing" if pct < 100 else "completed"


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

    # --- Bar segments (generic path: one per skill tag) ---
    bar_segments = [
        {
            "tag": tag,
            "label": TaxonomyReader.get_skill_label(tag),
            "level": _get_skill_level(user, tag),
        }
        for tag in unit_tags
    ]

    activity_cards: list[dict] = []
    skill_cards: list[dict] = []

    if unit_n == "1":
        bar_segments = []
        try:
            lane_groups = get_unit1_lane_groups()
        except Playlist.DoesNotExist:
            lane_groups = []

        for group in lane_groups:
            rows = []
            for lane in group.get("lanes", []):
                stats = _playlist_stats_by_id(user, lane["playlist_id"])
                lane_mastery = _compute_unit1_lane_mastery_level(user, lane["lane_key"], lane["playlist_id"])
                is_proficient = (lane_mastery in ["proficient", "mastered"])
                practice_band = _get_practice_band(stats["done"], stats["total"])
                
                rows.append(
                    {
                        "slug": lane["lane_key"],
                        "label": lane["label"],
                        "playlist_id": lane["playlist_id"],
                        "playlist_name": stats["name"],
                        "done": stats["done"],
                        "total": stats["total"],
                        "last_score_pct": stats["last_score_pct"],
                        "url": stats["url"],
                        "mastery_state": lane_mastery,
                        "progress_band": practice_band,
                        "is_proficient": is_proficient,
                        "recommended_practice": is_proficient and stats["done"] < stats["total"],
                    }
                )
                bar_segments.append(
                    {
                        "tag": lane["lane_key"],
                        "label": f"{group['title']} {lane['label']}",
                        "level": lane_mastery,
                    }
                )
            activity_cards.append(
                {
                    "slug": group["key"],
                    "title": group["title"],
                    "rows": rows,
                }
            )
    else:
        # --- Group playlists by skill tag ---
        matching_playlists = _dedupe_playlists_by_name(
            _get_playlists_for_unit(user, unit_tags, unit_n=unit_n),
            user,
        )
        explicit_unit_tag = f"unit:{unit_n}"

        # Build a map: skill_tag -> [playlist_stat_dict, ...]
        tag_to_playlists: dict[str, list[dict]] = {tag: [] for tag in unit_tags}
        for playlist in matching_playlists:
            primary_tag = _playlist_primary_tag(playlist, unit_tags)
            if primary_tag is None and unit_tags:
                # Backward-compatibility fallback: older/generated unit playlists
                # may only carry unit:N and no taxonomy skill tags.
                if (
                    explicit_unit_tag in (playlist.skill_tags or [])
                    or explicit_unit_tag in (playlist.tags or [])
                ):
                    primary_tag = unit_tags[0]
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
        "activity_cards": activity_cards,
        "skill_cards": skill_cards,
    }
