from __future__ import annotations

from dataclasses import dataclass
import random

from apps.exercises.models import IdentificationAttempt, PerformanceData, Playlist

UNIT4_SERVED_EXERCISE_COUNT = 6


@dataclass(frozen=True)
class PlayerProgressState:
    exercise_num: int
    mode: str  # "progression" | "review"
    should_redirect: bool = False


def is_completed_identification_attempt(attempt: IdentificationAttempt) -> bool:
    if not attempt.is_page_submit:
        return False
    score = attempt.score or {}
    return score.get("incorrect", 1) == 0 and score.get("unanswered", 1) == 0


def get_completed_exercise_ids(user, playlist: Playlist) -> set[str]:
    pd_rows = PerformanceData.objects.filter(user=user, playlist=playlist)
    ident_attempts = IdentificationAttempt.objects.filter(user=user, playlist=playlist)
    completed = {
        entry["id"]
        for pd in pd_rows
        for entry in (pd.data or [])
        if "id" in entry
    }
    completed.update(
        attempt.exercise.id
        for attempt in ident_attempts
        if attempt.exercise and is_completed_identification_attempt(attempt)
    )
    return completed


def _ordered_exercise_ids(playlist: Playlist) -> list[str]:
    return list(playlist.untransposed_exercises_ids or [])


def _is_unit4_personalized_playlist(playlist: Playlist) -> bool:
    tags = set((playlist.tags or []) + (playlist.skill_tags or []))
    return "unit:4" in tags and bool(tags.intersection({"Interval_Generic", "Interval_Specific"}))


def get_ordered_exercise_ids_for_serving(user, playlist: Playlist) -> list[str]:
    ordered_ids = _ordered_exercise_ids(playlist)
    if not user or not getattr(user, "id", None) or not _is_unit4_personalized_playlist(playlist):
        return ordered_ids

    shuffled_ids = list(ordered_ids)
    rng = random.Random(f"{user.id}:{playlist.id}:unit4")
    rng.shuffle(shuffled_ids)
    return shuffled_ids[:UNIT4_SERVED_EXERCISE_COUNT]


def get_served_exercise_id(user, playlist: Playlist, exercise_num: int, course=None) -> str | None:
    if getattr(playlist, 'is_adaptive', False) or getattr(playlist, 'is_dynamic', False):
        perf = PerformanceData.objects.filter(
            user=user, playlist=playlist, course=course
        ).first()
        if perf and len(perf.data) >= exercise_num:
            slot = perf.data[exercise_num - 1]
            slot_id = slot.get('id')
            if slot_id:
                return slot_id[:6]
        return None

    ordered_ids = get_ordered_exercise_ids_for_serving(user, playlist)
    if exercise_num < 1 or exercise_num > len(ordered_ids):
        return None
    return ordered_ids[exercise_num - 1]


def _next_pending_num(ordered_ids: list[str], completed_ids: set[str]) -> int | None:
    for index, exercise_id in enumerate(ordered_ids, 1):
        if exercise_id not in completed_ids:
            return index
    return None


def _adaptive_pending_slot_num(perf) -> int | None:
    """First 1-based slot index that is missing or not yet submitted.

    A slot counts as submitted when it carries a ``performed_at`` timestamp
    (set by ``PerformanceData.submit`` for every real submission, across both
    the old and new slot schemas). JIT placeholders lack ``performed_at``.
    Returns None when every existing slot is submitted.
    """
    if not perf:
        return None
    for idx, slot in enumerate(perf.data or [], start=1):
        if not slot or slot.get("is_placeholder") or not slot.get("performed_at"):
            return idx
    return None


def resolve_adaptive_step(
    user, playlist: Playlist, requested_num: int, course=None
) -> PlayerProgressState:
    """Decouple ``exercise_num`` from the URL for adaptive/dynamic playlists.

    The backend decides the slot strictly from DB history — never from the
    client-supplied ``requested_num``:

      * If a pending (unsubmitted/placeholder/missing) slot exists, serve it
        (mode ``progression``).
      * If every reserved slot is submitted, advance to the next fresh slot
        (``len(data) + 1``), still ``progression`` — adaptive playlists have no
        fixed length and no review-via-URL.
      * A brand-new user (no PerformanceData) starts at slot 1.

    ``should_redirect`` is set when the derived slot differs from the URL
    ``requested_num`` so the caller can redirect the URL to match reality.
    """
    perf = PerformanceData.objects.filter(
        user=user, playlist=playlist, course=course
    ).first()
    pending = _adaptive_pending_slot_num(perf)
    if pending is not None:
        resolved_num = pending
    elif perf:
        resolved_num = len(perf.data) + 1
    else:
        resolved_num = 1
    should_redirect = requested_num is not None and requested_num != resolved_num
    return PlayerProgressState(
        exercise_num=resolved_num, mode="progression", should_redirect=should_redirect
    )


def resolve_lane_launch(user, playlist: Playlist) -> PlayerProgressState:
    ordered_ids = get_ordered_exercise_ids_for_serving(user, playlist)
    completed_ids = get_completed_exercise_ids(user, playlist)
    next_pending = _next_pending_num(ordered_ids, completed_ids)
    if next_pending is not None:
        return PlayerProgressState(exercise_num=next_pending, mode="progression")
    return PlayerProgressState(exercise_num=len(ordered_ids) or 1, mode="review")


def resolve_requested_step(user, playlist: Playlist, requested_num: int) -> PlayerProgressState:
    ordered_ids = get_ordered_exercise_ids_for_serving(user, playlist)
    completed_ids = get_completed_exercise_ids(user, playlist)
    next_pending = _next_pending_num(ordered_ids, completed_ids)

    if requested_num < 1 or requested_num > len(ordered_ids):
        launch = resolve_lane_launch(user, playlist)
        return PlayerProgressState(
            exercise_num=launch.exercise_num,
            mode=launch.mode,
            should_redirect=True,
        )

    requested_exercise_id = ordered_ids[requested_num - 1]
    if requested_exercise_id in completed_ids:
        return PlayerProgressState(exercise_num=requested_num, mode="review")
    if next_pending == requested_num:
        return PlayerProgressState(exercise_num=requested_num, mode="progression")

    launch = resolve_lane_launch(user, playlist)
    return PlayerProgressState(
        exercise_num=launch.exercise_num,
        mode=launch.mode,
        should_redirect=True,
    )
