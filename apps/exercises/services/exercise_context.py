"""Shared exercise context construction for legacy and student players."""

import logging

from django.urls import reverse

from apps.exercises.mastery import get_next_exercise
from apps.exercises.models import Course, Exercise, PerformanceData
from apps.exercises.taxonomy_reader import TaxonomyReader
from apps.exercises.utils.transpose import transpose as transpose_exercise

logger = logging.getLogger(__name__)


def _resolve_analysis_type(exercise_data, heuristic):
    """Prefer stored chordal UMTO analysisType over the complexity heuristic."""
    if isinstance(exercise_data, dict) and exercise_data.get("isUMTO") is True:
        stored = exercise_data.get("analysisType")
        if stored:
            return stored
    return heuristic


def get_adaptive_exercise_for_view(request, playlist, exercise_num, course_id=None):
    """Helper to consistently fetch an adaptive exercise for a specific step."""
    seed = f"{request.user.id}-{playlist.id}-{exercise_num}"
    course_obj = None
    if course_id:
        course_obj = Course.objects.filter(id=course_id).first()
    
    exercise_obj, target_key = get_next_exercise(
        request.user.id, playlist=playlist, course=course_obj, seed=seed
    )

    # get_next_exercise may return a raw ID string (from the pinning path)
    if isinstance(exercise_obj, str):
        base_id = exercise_obj[:6]
        exercise_obj = Exercise.objects.filter(id=base_id).first()

    if exercise_obj:
        # Only invoke transposition if a target_key is explicitly requested (not None)
        # and the exercise has a keySignature (barline/rhythm exercises do not)
        if target_key and isinstance(exercise_obj.data, dict) and exercise_obj.data.get("keySignature") is not None:
            from apps.exercises.constants import pseudo_key_to_sig
            staff_sig = pseudo_key_to_sig.get(target_key)
            if staff_sig:
                return transpose_exercise(exercise_obj, staff_sig)
        return exercise_obj
    return None


def generate_exercise_context(
    exercise_num=None,
    exercise=None,
    user=None,
    playlist=None,
    course=None,
):
    course_id = course.id if course else None
    playlist_id = playlist.id if playlist else None
    exercise_context = {}
    # Adaptive handling for sequence navigation
    if playlist and playlist.is_adaptive:
        # In adaptive mode, the next number just goes to the next step.
        # The view for that step will call get_next_exercise() for a fresh task.
        next_num = exercise_num + 1
        prev_num = exercise_num - 1 if exercise_num > 1 else None
        
        next_exercise_url = playlist.get_exercise_url_by_num(num=next_num, course_id=course_id)
        prev_exercise_url = playlist.get_exercise_url_by_num(num=prev_num, course_id=course_id) if prev_num else None
        
        # We don't know the ID of the next exercise yet without calling the engine, 
        # but the URL pointing to num+1 is sufficient for the frontend.
        next_exercise_id = f"adaptive-{next_num}" 
        prev_exercise_id = f"adaptive-{prev_num}" if prev_num else None
    else:
        prev_num = playlist.prev_num(exercise_num) if playlist else None
        next_num = playlist.next_num(exercise_num) if playlist else None

        next_exercise_obj = (
            playlist.get_exercise_obj_by_num(next_num)
            if playlist
            else Exercise.objects.filter(authored_by=user, id__gt=exercise.id)
            .order_by("id")
            .first()
        )
        next_exercise_id = next_exercise_obj.id if next_exercise_obj != None else None
        next_exercise_url = (
            playlist.get_exercise_url_by_num(num=next_num, course_id=course_id)
            if playlist
            else reverse("lab:exercise-view", kwargs={"exercise_id": next_exercise_id})
            if next_exercise_id
            else None
        )

        prev_exercise_obj = (
            playlist.get_exercise_obj_by_num(prev_num)
            if playlist
            else Exercise.objects.filter(authored_by=user, id__lt=exercise.id)
            .order_by("-id")
            .first()
        )
        prev_exercise_id = prev_exercise_obj.id if prev_exercise_obj != None else None
        prev_exercise_url = (
            playlist.get_exercise_url_by_num(num=prev_num, course_id=course_id)
            if playlist
            else reverse("lab:exercise-view", kwargs={"exercise_id": prev_exercise_id})
            if prev_exercise_id
            else None
        )

    first_exercise_obj = playlist.get_exercise_obj_by_num(1) if playlist else None
    first_exercise_id = (
        first_exercise_obj.id
        if first_exercise_obj and first_exercise_obj.id != exercise.id
        else None
    )
    force_redirect = False
    exercise_list = []
    if playlist:
        if playlist.is_adaptive:
            # Show a few steps in the 'dots' list for adaptive playlists
            # We don't want to show the full pool (could be 1000s).
            # Show current, and maybe a few around it.
            for num in range(max(1, exercise_num - 2), exercise_num + 3):
                exercise_list.append(
                    dict(
                        id=f"{playlist_id}/{num}",
                        name=f"{num}",
                        url=playlist.get_exercise_url_by_num(num),
                        selected=exercise_num == num,
                    )
                )
        else:
            for num, _ in enumerate(playlist.exercise_list, 1):
                exercise_list.append(
                    dict(
                        id=f"{playlist_id}/{num}",
                        name=f"{num}",
                        url=playlist.get_exercise_url_by_num(num),
                        selected=exercise_num == num,
                    )
                )
    else:
        force_redirect = True
        url = reverse("lab:exercise-view", kwargs={"exercise_id": exercise.id})
        exercise_list.append(
            dict(
                id=f"{exercise.id}",
                name=f"{exercise.id}",
                url=url,
                selected=True,
            )
        )

    # TODO: what is the current functionality of this?
    exercise_is_performed = False
    exercise_error_count = 0
    playlist_performance = PerformanceData.objects.filter(
        playlist=playlist, user=user, course=course
    ).last()
    if playlist_performance:
        # In adaptive mode, the exercise ID in performance data doesn't map 1:1 to exercise_num
        exercise_is_performed = playlist_performance.exercise_is_performed(exercise.id)
        exercise_error_count = playlist_performance.exercise_error_count(exercise.id)
    
    used_raw_umto_fallback = False
    if exercise.data.get("type") == "umto_barline_placement":
        exercise_context.update(exercise.data)
    else:
        # UMTO Alignment: If the data follows the UMTO schema, use its frontend payload generator
        is_umto = exercise.data.get("isUMTO", False) or ("metadata" in exercise.data and "voices" in exercise.data)
        if is_umto:
            try:
                from apps.exercises.umto import UMTO
                umto_obj = UMTO.model_validate(exercise.data)

                # Determine unit focus from playlist tags first; the request-time
                # targeting layer owns curriculum scoping.
                unit_focus = None
                playlist_tags = playlist.skill_tags if playlist else []
                fallback_tags = exercise.skill_tags or []
                for tag in list(playlist_tags) + list(fallback_tags):
                    if isinstance(tag, str) and tag.startswith("unit:"):
                        try:
                            unit_focus = int(tag.split(":")[1])
                        except (ValueError, IndexError):
                            continue

                exercise_context.update(umto_obj.to_frontend_payload(unit=unit_focus))
            except Exception as e:
                # Fallback to raw data if UMTO validation fails
                logger.warning(
                    "[LEGACY EXERCISE] Exercise %s failed UMTO validation: %s. "
                    "Falling back to raw data. Migrate via apps.exercises.umto_factory.",
                    exercise.id, e,
                )
                used_raw_umto_fallback = True
                exercise_context.update(exercise.data)
        elif exercise.data.get("chord"):
            # Legacy chord[] row: wrap into chordal UMTO payload at serve time (read-only).
            # Raw exercise.data is NEVER passed to UMTO.model_validate here.
            try:
                from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload
                _wrapped = legacy_chord_row_to_chordal_payload(exercise.data)
                exercise_context.update(_wrapped)
            except Exception as e:
                logger.warning(
                    "[LEGACY EXERCISE] Exercise %s failed legacy chord wrap: %s. "
                    "Falling back to raw data.",
                    exercise.id, e,
                )
                exercise_context.update(exercise.data)
        else:
            exercise_context.update(exercise.data)
    unit_n = None
    playlist_skill_tags = list(playlist.skill_tags or []) if playlist else []
    fallback_skill_tags = list(exercise.skill_tags or [])
    for tag in playlist_skill_tags + fallback_skill_tags:
        if isinstance(tag, str) and tag.startswith("unit:"):
            unit_n = tag.split(":")[1]
            break
    
    if not unit_n:
        for tag in playlist_skill_tags + fallback_skill_tags:
            u = TaxonomyReader.get_unit_for_tag(tag)
            if u:
                unit_n = str(u.get("n"))
                break
    
    # Build analysisPolicy and apply targeting to raw analysis slices
    analysis_policy = None
    _unit_n_for_policy = unit_n  # may be None if no unit tag found

    if _unit_n_for_policy and exercise_context.get("mode") != "harmonization":
        # Determine family based on mode tag or stored analysisType
        _family = None
        _mode_tag = None
        for _tag in playlist_skill_tags + fallback_skill_tags:
            if _tag == "mode:figures":
                _family = "figured_bass"
                _mode_tag = _tag
                break
            elif _tag == "mode:figures_unabbreviated":
                _family = "figured_bass_unabbreviated"
                _mode_tag = _tag
                break
            elif _tag == "mode:roman":
                _family = "roman"
                _mode_tag = _tag
                break

        if not _family:
            # Fall back to exercise stored analysisType, then default to roman
            if isinstance(exercise.data, dict) and exercise.data.get("isUMTO") is True:
                _family = exercise.data.get("analysisType")
            if not _family or _family not in ("figured_bass", "figured_bass_unabbreviated", "roman"):
                _family = "roman"

        _unit_analysis = TaxonomyReader.get_unit_analysis(_unit_n_for_policy, _family)
        if _unit_analysis:
            _cumulative = TaxonomyReader.get_cumulative_values(_unit_n_for_policy, _family)
            _new_vals = TaxonomyReader.get_new_values(_unit_n_for_policy, _family)

            # Build displayMap: only entries where display != value
            _display_map = {
                entry["value"]: entry["display"]
                for entry in _unit_analysis["cumulative"]
                if entry["display"] != entry["value"]
            }

            analysis_policy = {
                "family": _family,
                "unit": int(_unit_n_for_policy),
                "mode": "targeted_slots",
                "allowedValues": sorted(_cumulative),
                "newValues": sorted(_new_vals),
                "displayMap": _display_map,
            }

            # Apply targeting: set is_target on each analysis slice in the payload
            _score = exercise_context.get("score", {})
            _umto_data = _score.get("umto", {}) if isinstance(_score, dict) else {}
            _slices = _umto_data.get("analysis", [])
            
            # Map family to content fields
            # _raw_field: what we read from the stored slice
            # _target_field: what we write the targeted value to
            if _family == "roman":
                _raw_field = "raw_roman_numeral"
                _target_field = "roman_numeral"
            elif _family == "figured_bass":
                _raw_field = "raw_figured_bass"
                _target_field = "figured_bass"
            elif _family == "figured_bass_unabbreviated":
                _raw_field = "raw_figured_bass"
                _target_field = "raw_figured_bass"
            else:
                _raw_field = "raw_roman_numeral"
                _target_field = "roman_numeral"

            _figure_cumulative = set()
            if _family == "roman":
                try:
                    _figure_cumulative = set(
                        TaxonomyReader.get_cumulative_values(_unit_n_for_policy, "figured_bass")
                        or []
                    )
                except Exception:
                    _figure_cumulative = set()
            _pending_resolution_label = None

            # A teacher-reviewed exercise (analysis_review_status="reviewed", set by
            # save_chordal_umto_exercise/save_umto_exercise when the teacher hits Save
            # with an explicit analysis) is the teacher's confirmed source of truth —
            # the same way WiR labels are trusted for Bach chorales. The curriculum-
            # cumulative targeting below exists to scope auto-generated, unreviewed
            # content to what's been taught so far; it must not redact a reviewed
            # exercise's analysis just because a chord falls outside that unit's
            # cumulative vocabulary list (e.g. a secondary leading-tone chord or a
            # seventh-chord inversion the teacher deliberately included).
            _is_reviewed = _umto_data.get("metadata", {}).get("analysis_review_status") == "reviewed"

            if _is_reviewed:
                for _sl in _slices:
                    _sl["is_target"] = True
            else:
                for _sl in _slices:
                    _content = _sl.get("content", {})
                    if _family == "roman":
                        if (
                            used_raw_umto_fallback
                            and exercise_context.get("type") == "umto_chorale"
                            and _content.get(_target_field) is None
                        ):
                            _val = _content.get(_raw_field)
                        elif _target_field in _content:
                            _val = _content.get(_target_field)
                        else:
                            _val = _content.get(_raw_field)
                    else:
                        _val = _content.get(_raw_field)

                    # For abbreviated figured bass, abbreviate the raw stack
                    # before comparing against cumulative values.
                    # e.g. raw "8/5/3" → abbreviated "" → check "" in cumulative
                    if _family == "figured_bass" and _val is not None:
                        from apps.exercises.utils.figured_bass import abbreviate_figured_bass
                        _compare = abbreviate_figured_bass(_val)
                    else:
                        _compare = _val

                    if (
                        _family == "roman"
                        and _compare is None
                        and _pending_resolution_label is not None
                        and _content.get(_raw_field) == _pending_resolution_label
                    ):
                        _compare = _pending_resolution_label
                        _pending_resolution_label = None

                    _figure_allowed = True
                    if (
                        _family == "roman"
                        and _compare is not None
                        and _figure_cumulative
                        and _content.get("figured_bass") not in (None, "")
                        and _content.get("figured_bass") not in _figure_cumulative
                    ):
                        _figure_allowed = False

                    # Note: use `is not None`, not truthiness — "5/3" is a valid cumulative value.
                    if _compare is not None and _compare in _cumulative and _figure_allowed:
                        _content[_target_field] = _compare
                        _sl["is_target"] = True
                    else:
                        if (
                            _family == "roman"
                            and _compare is not None
                            and _compare in _cumulative
                            and not _figure_allowed
                        ):
                            _pending_resolution_label = _compare
                        _content[_target_field] = None
                        _sl["is_target"] = False

                # ── Cadential 6/4 contextual rewrite (ROMAN ONLY) ──
                if _family == "roman":
                    _CAD64_SOURCES = {"I64", "i64"}
                    _CAD64_TARGETS = {"V", "V7", "V65", "V43"}
                    for _i in range(len(_slices) - 1):
                        _cur = _slices[_i]
                        _nxt = _slices[_i + 1]
                        _cur_rn = _cur.get("content", {}).get("roman_numeral")
                        _nxt_rn = _nxt.get("content", {}).get("roman_numeral")
                        if _cur_rn in _CAD64_SOURCES and _nxt_rn in _CAD64_TARGETS:
                            if "V64" in _cumulative:
                                _cur["content"]["roman_numeral"] = "V64"
                                _cur["is_target"] = True
                            else:
                                _cur["content"]["roman_numeral"] = None
                                _cur["is_target"] = False
            
            # Inject analysisType into the top-level payload for the frontend
            exercise_context["analysisType"] = _resolve_analysis_type(exercise.data, _family)

    exercise_context.update(
        {
            "analysisPolicy": analysis_policy,
            "unit_n": unit_n,
            "nextExercise": next_exercise_url,
            "nextExerciseId": next_exercise_id,
            "nextExerciseNum": next_num,
            "previousExercise": prev_exercise_url,
            "previousExerciseId": prev_exercise_id,
            "previousExerciseNum": prev_num,
            "firstExerciseId": first_exercise_id,
            "exerciseList": exercise_list,
            "exerciseId": exercise.id,
            "exerciseNum": exercise_num,
            "isAdaptive": getattr(playlist, "is_adaptive", False),
            "isDynamic": getattr(playlist, "is_dynamic", False),
            "playlistTags": getattr(playlist, "tags", []),
            "skillTags": getattr(exercise, "skill_tags", []),
            "playlistSkillTags": getattr(playlist, "skill_tags", []),
            "minComplexity": getattr(playlist, "min_complexity", 1),
            "maxComplexity": getattr(playlist, "max_complexity", 10),
            "exerciseIsPerformed": exercise_is_performed,
            "exerciseErrorCount": exercise_error_count,
            "playlistName": playlist_id,
            "courseId": course_id,
            "forceRedirect": force_redirect,
            "identMode": getattr(playlist, "feedback_mode", "") or exercise.data.get("identMode", "submit"),
            "modeLocked": bool(getattr(playlist, "feedback_mode", "")),
            "complexity_score": int(exercise_context.get("complexity_score") or exercise.complexity or 1),
        }
    )
    # print(f"DEBUG: Exercise {exercise.id} complexity_score={exercise_context['complexity_score']}")
    return exercise_context
