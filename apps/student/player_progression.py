from __future__ import annotations

from dataclasses import dataclass

from apps.exercises.models import IdentificationAttempt, PerformanceData, Playlist


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


def _next_pending_num(ordered_ids: list[str], completed_ids: set[str]) -> int | None:
    for index, exercise_id in enumerate(ordered_ids, 1):
        if exercise_id not in completed_ids:
            return index
    return None


def resolve_lane_launch(user, playlist: Playlist) -> PlayerProgressState:
    ordered_ids = _ordered_exercise_ids(playlist)
    completed_ids = get_completed_exercise_ids(user, playlist)
    next_pending = _next_pending_num(ordered_ids, completed_ids)
    if next_pending is not None:
        return PlayerProgressState(exercise_num=next_pending, mode="progression")
    return PlayerProgressState(exercise_num=len(ordered_ids) or 1, mode="review")


def resolve_requested_step(user, playlist: Playlist, requested_num: int) -> PlayerProgressState:
    ordered_ids = _ordered_exercise_ids(playlist)
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
