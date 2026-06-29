"""
mastery.py — Core mastery tracking logic for the Adaptive Engine.

No view-layer coupling. Callable from views, management commands, and tests.
"""
from datetime import date
import json
from django.utils.timezone import now

from apps.exercises.skill_graph import (
    ALL_SKILL_TAGS,
    DEFAULT_PREREQUISITES,
    MASTERY_LEVELS,
    MASTERY_TAGS,
    UNLOCK_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Mastery computation
# ---------------------------------------------------------------------------

def compute_mastery_level(history: list, practice_days: list) -> str:
    """
    Compute mastery level from rolling attempt history and practice days.

    Args:
        history:       List of booleans (True = correct). Stores last 10 attempts max.
        practice_days: List of ISO date strings (YYYY-MM-DD) when the skill was practiced.

    Returns:
        One of: 'not_started', 'attempted', 'familiar', 'proficient', 'mastered'

    Notes on < 10 attempts:
        When fewer than 10 attempts exist, thresholds use available data:
        - 'mastered'  requires all of the last 10 to be correct (or all available if < 10)
          AND practice on at least 2 separate calendar days.
        - 'proficient' requires 7+ correct in the last 10 (or all available if < 10).
        - 'familiar'  requires 3+ correct in the last 5 attempts (or all available if < 5).
        This means a student who gets 3/3 correct is already 'familiar', which is intended
        — early exercises are designed to validate understanding, not grind repetition.
    """
    attempts = len(history)
    if attempts == 0:
        return "not_started"

    correct_last_5  = sum(history[-5:])
    correct_last_10 = sum(history[-10:])

    # 'mastered' requires perfect recent performance AND multi-day practice.
    # Use all available history if < 10 — a student with 8/8 over 2 days is mastered.
    available_window = min(10, attempts)
    if sum(history[-available_window:]) == available_window and len(set(practice_days)) >= 2:
        return "mastered"

    if correct_last_10 >= 7:
        return "proficient"

    if correct_last_5 >= 3:
        return "familiar"

    return "attempted"


def compute_decay(level: str, last_practiced_dt) -> str:
    """
    Apply time-based skill fade. Returns the new (possibly lower) level string.
    Does NOT save to DB — caller is responsible for persisting.

    Decay thresholds (from spec):
        mastered   → proficient after 60 days idle
        proficient → familiar   after 30 days idle
        familiar   → attempted  after 14 days idle
    """
    if last_practiced_dt is None or level == "not_started":
        return level

    days_idle = (now() - last_practiced_dt).days

    if level == "mastered" and days_idle > 60:
        level = "proficient"
    elif level == "proficient" and days_idle > 30:
        level = "familiar"
    elif level == "familiar" and days_idle > 14:
        level = "attempted"

    return level


# ---------------------------------------------------------------------------
# Attempt recording
# ---------------------------------------------------------------------------

def _current_level(user_id: int, skill_tag: str) -> str:
    """
    Get the current mastery level for a skill tag.
    Returns 'not_started' if no record exists.
    """
    from apps.exercises.models import StudentSkillMastery
    try:
        return StudentSkillMastery.objects.get(user_id=user_id, skill_tag=skill_tag).level
    except StudentSkillMastery.DoesNotExist:
        return "not_started"


def _exercise_content_fingerprint(exercise) -> str | None:
    data = getattr(exercise, "data", {}) or {}
    score = data.get("score") or {}
    umto = score.get("umto")
    if umto:
        payload = {
            "voices": umto.get("voices"),
            "mode": ((umto.get("metadata") or {}).get("mode")),
            "clef": ((umto.get("metadata") or {}).get("clef")),
            "meter": ((umto.get("metadata") or {}).get("meter")),
            "key": ((umto.get("metadata") or {}).get("key")),
        }
        return json.dumps(payload, sort_keys=True)
    if score:
        return json.dumps(score, sort_keys=True)
    if "chord" in data:
        return json.dumps({"chord": data.get("chord"), "rhythm": data.get("rhythm")}, sort_keys=True)
    return None


def record_attempt(user_id: int, exercise, correct: bool) -> dict:
    """
    Record an exercise attempt for every skill tag on the exercise.
    Also applies decay before computing the new mastery level, and
    sets mastered_at if the student just achieved mastery.

    Called after every exercise submission (both play and identification paths).

    Args:
        user_id:  Integer user PK.
        exercise: Exercise model instance (must have .skill_tags list).
        correct:  True if the attempt was error-free / passed threshold.

    Returns:
        A dict of skill-level changes, e.g.:
        {"Note_Names": {"old": "familiar", "new": "proficient"}}
        Empty dict if no levels changed.
    """
    # Deferred import to keep this module importable without Django setup
    from apps.exercises.models import StudentSkillMastery

    # Snapshot current levels
    old_levels = {}
    for skill_tag in exercise.skill_tags:
        if skill_tag in MASTERY_TAGS:
            old_levels[skill_tag] = _current_level(user_id, skill_tag)

    today = date.today().isoformat()

    for skill_tag in exercise.skill_tags:
        if skill_tag not in MASTERY_TAGS:
            continue
        mastery, _ = StudentSkillMastery.objects.get_or_create(
            user_id=user_id,
            skill_tag=skill_tag,
        )

        # Apply decay before updating — ensures level reflects time elapsed
        # since last practice before adding today's attempt.
        decayed_level = compute_decay(mastery.level, mastery.last_practiced)
        mastery.level = decayed_level

        # Rolling window: keep last 9 entries + new attempt = 10 max
        history = list(mastery.recent_history[-9:]) + [correct]

        # Unique calendar days practiced (keep last 30 to bound list growth)
        days = list(mastery.practice_days)
        if today not in days:
            days.append(today)
        days = days[-30:]

        mastery.recent_history  = history
        mastery.practice_days   = days
        mastery.total_attempts  += 1
        mastery.total_correct   += int(correct)
        mastery.last_practiced  = now()

        if mastery.first_attempted is None:
            mastery.first_attempted = now()

        new_level = compute_mastery_level(history, days)
        if new_level == "mastered" and mastery.level != "mastered":
            mastery.mastered_at = now()

        mastery.level = new_level
        mastery.save()

    # Snapshot new levels and compare
    changes = {}
    for skill_tag, old_level in old_levels.items():
        new_level = _current_level(user_id, skill_tag)
        if new_level != old_level:
            changes[skill_tag] = {"old": old_level, "new": new_level}

    return changes


# ---------------------------------------------------------------------------
# Unlock checking
# ---------------------------------------------------------------------------

def get_unlocked_skills(user_id: int, course=None) -> list:
    """
    Return a sorted list of skill tags the student is eligible to practice.

    A skill is unlocked when ALL of its prerequisite skills are at
    UNLOCK_THRESHOLD ('familiar') or above.

    Args:
        user_id: Integer user PK.
        course:  Optional Course instance. If provided, also loads
                 course-specific SkillPrerequisite overrides (course != None rows).
                 Global defaults (course=None rows) are always included.

    Returns:
        List of skill tag strings the student may practice.
    """
    from apps.exercises.models import StudentSkillMastery, SkillPrerequisite
    from django.db.models import Q

    # Build effective prerequisite map (global defaults + course overrides)
    prereq_qs = SkillPrerequisite.objects.filter(
        Q(course__isnull=True) | Q(course=course)
    ).values("skill_tag", "requires_tag")

    prereq_map: dict[str, set] = {}
    for row in prereq_qs:
        prereq_map.setdefault(row["skill_tag"], set()).add(row["requires_tag"])

    # Acquired = at or above unlock threshold
    threshold_idx = MASTERY_LEVELS.index(UNLOCK_THRESHOLD)
    acquired_levels = MASTERY_LEVELS[threshold_idx:]  # ['familiar', 'proficient', 'mastered']

    acquired = set(
        StudentSkillMastery.objects.filter(
            user_id=user_id,
            level__in=acquired_levels,
        ).values_list("skill_tag", flat=True)
    )

    unlocked = []
    for skill in ALL_SKILL_TAGS:
        required = prereq_map.get(skill, set())
        if required.issubset(acquired):
            unlocked.append(skill)

    return unlocked


# ---------------------------------------------------------------------------
# Adaptive Serving
# ---------------------------------------------------------------------------

def get_next_exercise(user, playlist=None, course=None, exercise_num=1, seed=None):
    """
    Selects the next exercise for a user based on their skill mastery levels.
    Implements 'Navigation Pinning': if the user has already seen/started 
    this slot in a playlist, return the identical exercise.

    Arguments supports both user object and user_id for backward compatibility.
    """
    from apps.exercises.models import Exercise, StudentSkillMastery, ExercisePlaylistOrdered, PerformanceData
    from django.db import models
    from django.contrib.auth import get_user_model
    from django.db.models import Min, Q
    import random

    User = get_user_model()
    # Handle user/user_id duality
    user_obj = user if isinstance(user, User) else User.objects.filter(id=user).first()
    user_id = user_obj.id if user_obj else 0

    # 1. Navigation Pinning Check
    # If this is part of a playlist journey, check history first.
    prior_exercise_id = None
    prior_fingerprint = None
    if playlist and user_obj and user_obj.is_authenticated:
        try:
            perf = PerformanceData.objects.filter(user=user_obj, playlist=playlist, course=course).first()
            if perf is not None:
                # If the user has a record for this slot (exercise_num), use it.
                if len(perf.data) >= exercise_num:
                    exercise_data = perf.data[exercise_num - 1]
                    # Skip placeholder slots — reserved but not yet submitted; fall through to fresh selection.
                    if not exercise_data.get('is_placeholder', False):
                        pinned_id = exercise_data.get('id')
                        if pinned_id:
                            # Validate pinned exercise still exists before returning.
                            # If it was deleted (e.g. playlist rebuilt), fall through to fresh selection.
                            pinned_base = pinned_id[:6]
                            pinned_ex = Exercise.objects.filter(id=pinned_base).first()
                            if pinned_ex and (
                                (playlist.is_adaptive or getattr(playlist, 'is_dynamic', False))
                                or ExercisePlaylistOrdered.objects.filter(playlist=playlist, exercise=pinned_ex).exists()
                            ):
                                pinned_key = pinned_id[6:] if len(pinned_id) > 6 else None
                                return pinned_id, pinned_key
                if exercise_num > 1 and len(perf.data) >= exercise_num - 1:
                    prior_exercise_id = (perf.data[exercise_num - 2] or {}).get("id")
        except Exception:
            pass

    if prior_exercise_id:
        prior_base_id = prior_exercise_id[:6]
        prior_exercise = Exercise.objects.filter(id=prior_base_id).first()
        if prior_exercise:
            prior_fingerprint = _exercise_content_fingerprint(prior_exercise)

    # 2. Setup Deterministic RNG for this slot
    seed_payload = f"{user_id}:{playlist.id if playlist else 'none'}:{exercise_num}:{seed or ''}"
    rng = random.Random(seed_payload)

    # 3. Determine thresholds
    mastery_threshold = "mastered"
    if course:
        mastery_threshold = getattr(course, "mastery_threshold", "mastered")
    
    from apps.exercises.skill_graph import MASTERY_LEVELS
    threshold_idx = MASTERY_LEVELS.index(mastery_threshold)
    target_levels = MASTERY_LEVELS[:threshold_idx] 

    # 4. Get unlocked and targeted skills
    unlocked = get_unlocked_skills(user_id, course=course)
    
    # Map unlocked skills to their current level for this user
    mastery_qs = StudentSkillMastery.objects.filter(
        user_id=user_id,
        skill_tag__in=unlocked
    ).values("skill_tag", "level")
    
    current_levels = {m["skill_tag"]: m["level"] for m in mastery_qs}
    for skill in unlocked:
        current_levels.setdefault(skill, "not_started")
    
    # Target skills = unlocked AND level < threshold
    target_skills = [s for s in unlocked if current_levels[s] in target_levels]

    # 3. Handle new students / entry points
    # If no target skills are found (unlikely if taxonomy Tier 0 is seeded), 
    # or if we want to prioritize designated starters:
    starters = []
    if playlist:
        starters = list(ExercisePlaylistOrdered.objects.filter(
            playlist=playlist, is_adaptive_entry=True
        ).values_list("exercise_id", flat=True))

    # 4. Fetch the exercise pool
    pool = Exercise.objects.all()
    if playlist:
        filter_tags = list(playlist.tags or []) + list(getattr(playlist, "skill_tags", []) or [])
        if getattr(playlist, "is_dynamic", False) and filter_tags:
            # DYNAMIC POOL: match exercises whose skill_tags overlap with
            # playlist.tags (unit:9, bach) or playlist.skill_tags (Dominant_Seventh).
            # Exercise.tags is unused — all tag data lives in skill_tags.
            pool = pool.filter(skill_tags__overlap=filter_tags)

            # If the playlist explicitly scopes a mode (e.g., mode:play), require
            # that mode tag to be present on candidate exercises. This prevents
            # mixed-mode pools where overlap on unit tags alone would include
            # both [play] and [roman] exercises.
            mode_tags = [
                tag for tag in filter_tags
                if isinstance(tag, str) and tag.startswith("mode:")
            ]
            for mode_tag in mode_tags:
                pool = pool.filter(skill_tags__contains=[mode_tag])

            # Apply complexity gating from the playlist settings
            pool = pool.filter(
                complexity__gte=playlist.min_complexity,
                complexity__lte=playlist.max_complexity
            )
        else:
            # STATIC POOL: Only pull from exercises manually linked to the playlist
            pool = pool.filter(playlists=playlist)
    
    # 5. Determine the 'Eligible' Pool
    # We prioritize: 
    #   1. Exercises targeting weaknesses (target_skills)
    #   2. Designated entry points (starters)
    #   3. The general pool fallback
    eligible = None
    if target_skills:
        qs = pool.filter(skill_tags__overlap=target_skills)
        if qs.exists():
            eligible = qs

    if not eligible:
        if starters:
            qs = pool.filter(id__in=starters)
            if qs.exists():
                eligible = qs
    
    if not eligible:
        eligible = pool

    if not eligible.exists():
        return None, None

    # 6. Ranking Logic
    # We want to pick the exercise that targets the "weakest" skill 
    # (lowest mastery index) with the lowest complexity.
    candidates = list(eligible.only("id", "skill_tags", "complexity", "data"))

    if prior_exercise_id:
        non_identical_candidates = [ex for ex in candidates if ex.id != prior_exercise_id[:6]]
        if non_identical_candidates:
            candidates = non_identical_candidates

    if prior_fingerprint:
        non_repeating_candidates = [
            ex for ex in candidates
            if _exercise_content_fingerprint(ex) != prior_fingerprint
        ]
        if non_repeating_candidates:
            candidates = non_repeating_candidates
    
    def score_exercise(ex):
        # find the lowest mastery index among the skills this exercise targets
        relevant_levels = [MASTERY_LEVELS.index(current_levels.get(t, "not_started")) 
                          for t in ex.skill_tags if t in unlocked]
        min_level_idx = min(relevant_levels) if relevant_levels else 99
        return (min_level_idx, ex.complexity, rng.random())

    # Sort by min mastery level (primary), complexity (secondary), random (tertiary)
    candidates.sort(key=score_exercise)
    best_ex = candidates[0]

    # 7. Transposition Variety
    # Spec: randomized among common keys or playlist requests.
    # User Request: Don't transpose Bach chorale pieces at all. Use None to bypass.
    if best_ex.data.get("type") in ["chorale", "umto_chorale"] or "bach" in (best_ex.skill_tags or []):
        target_key = None
    else:
        common_keys = ["C", "G", "F", "D", "Bb", "A", "Eb"]
        if playlist and playlist.transpose_requests:
            keys_to_pick = playlist.transpose_requests
        else:
            keys_to_pick = common_keys
        
        raw_choice = rng.choice(keys_to_pick)

        # Keep raw_choice (pseudo-key name like 'G', 'F') as target_key.
        # exercise_context.py calls pseudo_key_to_sig.get(target_key) expecting pseudo-key names.
        # Storing/returning the sig code ('#') would cause pseudo_key_to_sig.get('#') → None → no transposition.
        target_key = raw_choice

    # JIT slot reservation for adaptive/dynamic playlists
    if user_obj and user_obj.is_authenticated and playlist and (
        playlist.is_adaptive or getattr(playlist, 'is_dynamic', False)
    ):
        perf, _ = PerformanceData.objects.get_or_create(
            user=user_obj, playlist=playlist, course=course
        )
        sentinel = {
            "id": None,
            "is_placeholder": True,
            "error_tally": None,
            "performance_duration_in_seconds": None,
            "is_submitted": False,
        }
        # Pad gaps with inert sentinels
        while len(perf.data) < exercise_num - 1:
            perf.data.append(dict(sentinel))

        # target_id stores the pseudo-key name (raw_choice) not the sig code
        target_id = best_ex.id + (target_key or "")

        slot_sentinel = dict(sentinel, id=target_id)
        if len(perf.data) < exercise_num:
            perf.data.append(slot_sentinel)
        else:
            existing = perf.data[exercise_num - 1]
            if not existing.get("is_submitted"):
                existing["id"] = target_id
        perf.save()

    return best_ex, target_key


# ---------------------------------------------------------------------------
# Skill Map Data Generation
# ---------------------------------------------------------------------------

def get_skill_map_elements(user_id: int, course=None):
    """
    Generate graph elements (nodes and edges) for the Student Skill Map.
    Formatted for Cytoscape.js.
    """
    from apps.exercises.models import StudentSkillMastery, SkillPrerequisite
    from apps.exercises.skill_graph import (
        ALL_SKILL_TAGS, 
        DEFAULT_PREREQUISITES, 
        MASTERY_LEVELS,
        UNLOCK_THRESHOLD
    )
    from django.db.models import Q

    # 1. Fetch user mastery data
    mastery_qs = StudentSkillMastery.objects.filter(user_id=user_id).values(
        "skill_tag", "level", "last_practiced"
    )
    mastery_map = {m["skill_tag"]: m for m in mastery_qs}

    # 2. Build prerequisite map (including course overrides)
    prereq_qs = SkillPrerequisite.objects.filter(
        Q(course__isnull=True) | Q(course=course)
    ).values("skill_tag", "requires_tag")
    
    # Map to help check unlock status
    prereq_graph: dict[str, list[str]] = {}
    for row in prereq_qs:
        prereq_graph.setdefault(row["skill_tag"], []).append(row["requires_tag"])

    # 3. Determine acquired skills for unlock logic
    threshold_idx = MASTERY_LEVELS.index(UNLOCK_THRESHOLD)
    acquired_levels = MASTERY_LEVELS[threshold_idx:]
    acquired_skills = {
        m["skill_tag"] for m in mastery_map.values() 
        if m["level"] in acquired_levels
    }

    elements = []

    # 4. Create Nodes
    for skill in ALL_SKILL_TAGS:
        m_data = mastery_map.get(skill, {})
        level = m_data.get("level", "not_started")
        
        # Check if decayed
        is_decayed = False
        if m_data.get("last_practiced"):
            decayed_level = compute_decay(level, m_data["last_practiced"])
            if decayed_level != level:
                is_decayed = True

        # Unlock logic: all prerequisites must be acquired
        reqs = prereq_graph.get(skill, [])
        unlocked = all(r in acquired_skills for r in reqs)

        # Human friendly label (replace underscores with spaces)
        label = skill.replace("_", " ")

        elements.append({
            "data": {
                "id": skill,
                "label": label,
                "level": level,
                "unlocked": unlocked,
                "is_decayed": is_decayed,
                "tier": get_tier(skill)  # Optional helper for layout
            }
        })

    # 5. Create Edges
    for skill, reqs in prereq_graph.items():
        if skill not in ALL_SKILL_TAGS: continue
        for r in reqs:
            if r not in ALL_SKILL_TAGS: continue
            elements.append({
                "data": {
                    "id": f"edge-{r}-{skill}",
                    "source": r,
                    "target": skill
                }
            })

    return elements

def get_tier(skill_tag: str) -> int:
    """Helper to group skills by tier based on position in ALL_SKILL_TAGS (MVP logic)."""
    from apps.exercises.skill_graph import ALL_SKILL_TAGS
    try:
        idx = ALL_SKILL_TAGS.index(skill_tag)
        if idx < 11: return 0  # pre-theory
        if idx < 26: return 1  # foundation
        return 2 # chromatic
    except ValueError:
        return 0

