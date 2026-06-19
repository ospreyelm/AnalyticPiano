from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import When, Case, Q
from django.urls import reverse
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.generic import View, TemplateView, RedirectView
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie

import logging
logger = logging.getLogger(__name__)

from braces.views import CsrfExemptMixin, LoginRequiredMixin

from django_tables2 import RequestConfig

# from .objects import ExerciseRepository
from .decorators import role_required, course_authorization_required
from .tables import CoursePageTable
from .verification import has_instructor_role, has_course_authorization

from apps.exercises.models import (
    Exercise,
    Playlist,
    Course,
    PerformanceData,
    PlaylistCourseOrdered,
    NonUMTOExerciseError,
)
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.exercises.mastery import get_next_exercise, get_skill_map_elements
from apps.exercises.utils.transpose import transpose as transpose_exercise
from apps.exercises.taxonomy_reader import TaxonomyReader


import json
import copy
import os
import re

# from django.core.mail import send_mail

User = get_user_model()


def _resolve_analysis_type(exercise_data, heuristic):
    """Prefer stored chordal UMTO analysisType over the complexity heuristic."""
    if isinstance(exercise_data, dict) and exercise_data.get("isUMTO") is True:
        stored = exercise_data.get("analysisType")
        if stored:
            return stored
    return heuristic


class RequirejsContext(object):
    def __init__(self, config, debug=True):
        self._debug = debug
        self._config = copy.deepcopy(config)

    def set_module_params(self, module_id, params):
        module_config = {}
        module_config.update(params)
        if "config" not in self._config:
            self._config["config"] = {}
        if module_id not in self._config["config"]:
            self._config["config"][module_id] = {}
        self._config["config"][module_id].update(module_config)
        return self

    def set_app_module(self, app_module_id):
        self.set_module_params("app/main", {"app_module": app_module_id})
        return self

    def add_to_view(self, view_context):
        view_context["requirejs"] = self
        return self

    def debug(self):
        if self._debug:
            return True
        return False

    def config_json(self):
        return json.dumps(self._config)


class RequirejsTemplateView(TemplateView):
    requirejs_app = None

    def __init__(self, *args, **kwargs):
        super(RequirejsTemplateView, self).__init__(*args, **kwargs)
        self.requirejs_context = RequirejsContext(
            settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG
        )

    def get_context_data(self, **kwargs):
        context = super(RequirejsTemplateView, self).get_context_data(**kwargs)
        self.requirejs_context.set_app_module(getattr(self, "requirejs_app"))
        self.requirejs_context.add_to_view(context)
        return context


class RequirejsView(View):
    def __init__(self, *args, **kwargs):
        super(RequirejsView, self).__init__(*args, **kwargs)
        self.requirejs_context = RequirejsContext(
            settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG
        )


class PlayView(RequirejsTemplateView):
    template_name = "play.html"
    requirejs_app = "app/components/app/play"

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    # def get_context_data(self, course_id=None, **kwargs):
    #     context = super(PlayView, self).get_context_data(**kwargs)
    #     er = ExerciseRepository.create(course_id=course_id)

    #     context["group_list"] = er.getGroupList()
    #     # for testing on Windows, use following line
    #     # context['group_list'] = []
    #     context["has_manage_perm"] = has_instructor_role(
    #         self.request
    #     ) and has_course_authorization(self.request, course_id)
    #     if context["has_manage_perm"]:
    #         if course_id is None:
    #             context["manage_url"] = reverse("lab:manage")
    #         else:
    #             context["manage_url"] = reverse(
    #                 "lab:course-manage", kwargs={"course_id": course_id}
    #             )

    #     if course_id is None:
    #         context["home_url"] = reverse("lab:index")
    #     else:
    #         context["home_url"] = reverse(
    #             "lab:course-index", kwargs={"course_id": course_id}
    #         )

    #     return context


# Reusable function to generate exercise_context. Accounts for null inputs.
# Catered to the current desired behavior of the 3 views below. If adding more views or changing desired behavior, changes to this function will be needed
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
        # Determine family based on mode tag
        _family = "roman"
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


class PlaylistView(RequirejsView):
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(
        self, request, playlist_id, course_id=None, exercise_num=None, *args, **kwargs
    ):
        playlist = Playlist.objects.filter(id=playlist_id).first()
        if playlist is None:
            raise Http404("Playlist with this name or ID does not exist.")

        if (
            not playlist.is_public
            and not playlist.authored_by == request.user
            and not request.user.pk in playlist.authored_by.content_permits
        ):
            raise PermissionDenied

        # Prevents "None" in URL by redirecting to view without course_id in URL
        if type(course_id) == str and course_id == "None":
            return redirect(
                "lab:playlist-view", playlist_id=playlist_id, exercise_num=exercise_num
            )

        # Ensures that exercise-num is always in URL
        if exercise_num == None:
            return redirect(
                "lab:playlist-view",
                playlist_id=playlist_id,
                course_id=course_id,
                exercise_num=1,
            )

        # Adaptive or Smart Assignment logic: override exercise selection if playlist targets a dynamic pool
        if playlist.is_adaptive or playlist.is_dynamic:
            exercise = get_adaptive_exercise_for_view(request, playlist, exercise_num, course_id)
            if not exercise:
                raise Http404("Could not find a suitable exercise in this adaptive playlist.")
        else:
            exercise = playlist.get_exercise_obj_by_num(exercise_num)
            if exercise is None:
                if len(playlist.exercise_list) == 0:
                    raise Http404(
                        f"Playlist '{playlist.name}' (ID: {playlist.id}) has no exercises. "
                        "Please edit the playlist to add exercises, or delete it."
                    )
                raise Http404(
                    f"Exercise #{exercise_num} in playlist '{playlist.name}' could not be found. "
                    "It may have been deleted. Please edit the playlist to remove missing exercises."
                )

        context = {"group_list": []}
        course_performed = None
        if course_id:
            course_performed = Course.objects.filter(id=course_id).first()

        exercise_context = generate_exercise_context(
            exercise_num,
            exercise,
            request.user,
            playlist,
            course_performed,
        )

        playlist_previously_passed = False
        if course_performed:
            context["course_name"] = course_performed.title
            course_link = reverse("lab:course-view", kwargs={"course_id": course_id})
            context["course_link"] = course_link
            if (
                course_performed.performance_dict.get(str(request.user), {}).get(
                    playlist_id, "X"
                )
            ) != "X":
                playlist_previously_passed = True

        context["playlist_previously_passed"] = playlist_previously_passed

        next_playlist = None
        # Finding the next playlist in the case that this playlist was accessed from within a course
        if course_performed != None:
            playlist_pco = PlaylistCourseOrdered.objects.filter(
                playlist_id=playlist._id, course_id=course_performed._id
            ).first()
            if playlist_pco != None:
                next_playlist_pco = PlaylistCourseOrdered.objects.filter(
                    course_id=course_performed._id, order=playlist_pco.order + 1
                ).first()
                # If there is a following playlist, get it and add a link to it to the context
                if next_playlist_pco != None:
                    next_playlist = Playlist.objects.filter(
                        _id=next_playlist_pco.playlist_id
                    ).first()
                    next_playlist_link = reverse(
                        "lab:playlist-view",
                        kwargs={
                            "playlist_id": next_playlist.id,
                            "course_id": course_id,
                        },
                    )
                    context["next_playlist_link"] = next_playlist_link

        if playlist.name:
            context["playlist_name"] = playlist.name
        else:
            context["playlist_name"] = playlist.id
            # ^ misleading name for the url variable

        if exercise_context.get("type") in {"umto_symbolic_meter", "umto_barline_placement"}:
            context["exercise_config_json"] = json.dumps(exercise_context)
            return render(request, "qa_player.html", context)

        self.requirejs_context.set_app_module("app/components/app/exercise")
        self.requirejs_context.set_module_params(
            "app/components/app/exercise", exercise_context
        )
        self.requirejs_context.add_to_view(context)
        return render(request, "exercise.html", context)


class RefreshExerciseDefinition(RequirejsView):
    def get(
        self,
        request,
        playlist_id=None,
        course_id=None,
        exercise_id=None,
        exercise_num=None,
        *args,
        **kwargs,
    ):
        # If playlist_id is None, we are navigating between users' created exercises in Preview mode
        playlist = get_object_or_404(Playlist, id=playlist_id) if playlist_id else None
        if not playlist_id:
            print("Preview")
        exercise_num = request.GET.get("exercise_num", exercise_num)
        exercise_num = int(exercise_num) if exercise_num not in ("", None) else None

        exercise = (
            Exercise.objects.filter(id=exercise_id).first()
            if exercise_id
            else (
                get_adaptive_exercise_for_view(request, playlist, exercise_num, course_id)
                if playlist and playlist.is_adaptive
                else playlist.get_exercise_obj_by_num(exercise_num)
            )
        )
        if exercise is None:
            raise Http404("Exercise not found.")

        course_performed = None

        if course_id:
            course_performed = Course.objects.get(id=course_id)

        exercise_context = generate_exercise_context(
            exercise_num,
            exercise,
            request.user,
            playlist,
            course_performed,
        )

        self.requirejs_context.set_app_module("app/components/app/exercise")
        self.requirejs_context.set_module_params(
            "app/components/app/exercise", exercise_context
        )
        # self.requirejs_context.add_to_view(context)
        return JsonResponse(data=exercise_context)


def dev_corpus_bach_json(request, filename):
    """Serve exported corpus JSON files from data/corpus/bach during development.

    Security: only available when DEBUG=True. Limits filename to a safe subset and
    serves files only from the expected directory.
    """
    if not settings.DEBUG:
        raise Http404()

    # basic filename sanity: allow alnum, dash, underscore, dot
    import re

    if not re.match(r"^[\w\-\.]+$", filename or ""):
        raise Http404()

    # enforce .json extension
    if not filename.endswith(".json"):
        # allow caller to omit extension
        filename = filename + ".json"

    base_dir = getattr(settings, "BASE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    corpus_dir = os.path.join(base_dir, "data", "corpus", "bach")
    file_path = os.path.normpath(os.path.join(corpus_dir, filename))

    # ensure path is under corpus_dir
    if not file_path.startswith(os.path.abspath(corpus_dir) + os.sep):
        raise Http404()

    if not os.path.exists(file_path):
        raise Http404()

    with open(file_path, "r") as f:
        payload = json.load(f)
    return JsonResponse(payload, safe=False)


class ExerciseView(RequirejsView):
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, exercise_id, *args, **kwargs):
        exercise = get_object_or_404(Exercise, id=exercise_id)

        if (
            not exercise.is_public
            and not exercise.authored_by == request.user
            and not request.user.pk in exercise.authored_by.content_permits
        ):
            raise PermissionDenied

        context = {"group_list": []}
        exercise_context = {}

        exercise_context = generate_exercise_context(
            None,
            exercise,
            request.user,
        )

        self.requirejs_context.set_app_module("app/components/app/exercise")
        self.requirejs_context.set_module_params(
            "app/components/app/exercise", exercise_context
        )
        self.requirejs_context.add_to_view(context)
        return render(request, "exercise.html", context)


class CourseView(RequirejsView):
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, course_id, *args, **kwargs):
        course = get_object_or_404(Course, id=course_id)

        if (
            not course.is_public
            and not course.authored_by == request.user
            and not request.user.pk in course.authored_by.content_permits
        ):
            raise PermissionDenied

        whens = []
        for sort_index, value in enumerate(course.playlist_id_list):
            whens.append(When(id=value, then=sort_index))

        qs = (
            course.playlists
            if course.authored_by == request.user
            else course.published_playlists
        )
        playlists = qs.annotate(
            _sort_index=Case(*whens, output_field=models.CharField())
        ).order_by("_sort_index")
        augmented_playlists = map(
            lambda playlist: {
                **PlaylistCourseOrdered.objects.get(
                    Q(playlist_id=playlist._id), Q(course_id=course._id)
                ).__dict__,
                **playlist.__dict__,
                "course_id": course.id,
            },
            playlists,
        )

        user_instance = User.objects.get(pk=request.user.id)
        user_completion = course.performance_dict.get(str(user_instance), None)

        if user_completion:
            augmented_playlists = map(
                lambda aug_playlist: {
                    **aug_playlist,
                    "completion": user_completion.get(str(aug_playlist["order"]), None),
                },
                augmented_playlists,
            )

        playlists_table = CoursePageTable(augmented_playlists, course=course)
        course_author = course.authored_by
        context = {
            "course_title": course.title,
            "playlists_table": playlists_table,
            "course_author": course_author,
        }

        exclude_fields = list(playlists_table.exclude)
        if request.user != course_author:
            # publish date only visible to author, due date to everyone
            exclude_fields.append("publish_date")
        playlists_table.exclude = exclude_fields

        RequestConfig(request).configure(playlists_table)

        return render(request, "course.html", context)


def not_authorized(request):
    return HttpResponse("Unauthorized", status=401)


class SkillMapView(RequirejsView):
    """Page view to render the visual Knowledge Graph / Skill Map."""
    @method_decorator(login_required)
    def get(self, request, course_id=None, *args, **kwargs):
        course = None
        if course_id:
            course = get_object_or_404(Course, id=course_id)
        
        context = {
            "course": course,
            "course_id": course_id,
        }
        self.requirejs_context.add_to_view(context)
        return render(request, "skill_map.html", context)


class SkillMapDataView(View):
    """JSON API to serve graph data for the Skill Map."""
    @method_decorator(login_required)
    def get(self, request, course_id=None, *args, **kwargs):
        course = None
        if course_id:
            course = Course.objects.filter(id=course_id).first()
        
        elements = get_skill_map_elements(request.user.id, course=course)
        return JsonResponse({"elements": elements})


def check_course_authorization(request, course_id, raise_exception=False):
    authorized = has_course_authorization(request, course_id, raise_exception)
    result = {
        "user_id": request.user.id,
        "course_id": course_id,
        "is_authorized": authorized,
    }
    status = 200
    if not authorized:
        status = 403  # forbidden
    return HttpResponse(
        json.dumps(result), content_type="application/json", status=status
    )


class ChoraleAnalysisDebugView(RequirejsTemplateView):
    """Simple page that boots a small app to dump roman + figured-bass analyses
    for a few corpus chorales. Dev-only tool.
    """
    template_name = "debug_analysis.html"
    requirejs_app = "app/components/app/debug_analysis"


class AddExerciseView(View):
    http_method_names = ["post"]
    _TAG_RE = re.compile(r"^[A-Za-z0-9:_#/-]{1,40}$")

    def _json_error(self, message, status=400):
        return JsonResponse({"error": message}, status=status)

    def _bool_field(self, payload, field_name, default=False):
        value = payload.get(field_name, default)
        if not isinstance(value, bool):
            raise ValueError(f"{field_name} must be a boolean.")
        return value

    def _description(self, payload):
        description = payload.get("description", "Play view chordal exercise")
        if not isinstance(description, str) or len(description) > 60:
            raise ValueError("description must be a string of 60 characters or fewer.")
        return description

    def _skill_tags(self, payload):
        tags = payload.get("skillTags", [])
        if not isinstance(tags, list) or len(tags) > 20:
            raise ValueError("skillTags must be a list of at most 20 strings.")

        cleaned = []
        unit_tag_count = 0
        for tag in tags:
            if not isinstance(tag, str) or not self._TAG_RE.match(tag):
                raise ValueError("skillTags contains an invalid tag.")
            if tag.startswith("unit:"):
                unit_n = tag.split(":", 1)[1]
                if TaxonomyReader.get_unit(unit_n) is None:
                    raise ValueError(f"unit tag {tag} does not reference a known unit.")
                unit_tag_count += 1
            cleaned.append(tag)
        if unit_tag_count != 1:
            raise ValueError("Exactly one unit tag is required.")
        return cleaned

    def _single_mode(self, payload):
        """Extract and validate exactly one interaction mode."""
        from apps.exercises.utils.playlist_naming import SUPPORTED_TEACHER_PLAY_MODES
        modes = payload.get("modes")
        if modes is not None:
            if not isinstance(modes, list) or len(modes) != 1:
                raise ValueError(
                    "Exactly one mode is required. Send 'mode' (string) not 'modes' (list)."
                )
            mode = modes[0]
        else:
            mode = payload.get("mode", "play")
        if mode not in SUPPORTED_TEACHER_PLAY_MODES:
            raise ValueError(f"Unsupported interaction mode: {mode}")
        return mode

    def _single_unit(self, skill_tags):
        """Return the integer unit number from the validated skill_tags list."""
        for tag in skill_tags:
            if tag.startswith("unit:"):
                return int(tag.split(":", 1)[1])
        raise ValueError("Exactly one unit tag is required.")

    def _factory_user(self):
        return User.objects.filter(email=settings.FACTORY_USER_EMAIL).first()

    def _resolve_author(self, request, save_as_official):
        if not save_as_official:
            return request.user
        if not request.user.is_superuser:
            return None
        return self._factory_user()

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponse(status=400)

        data = request.POST.get("data")
        if not data or data == "null":
            return HttpResponse(status=400)

        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return HttpResponse(status=400)

        if not isinstance(payload, dict):
            return HttpResponse(status=400)

        chords = payload.get("chord")
        if not chords or not isinstance(chords, list):
            return HttpResponse(status=400)

        # Reject explicit playlist destination — routing is automatic.
        if payload.get("playlistId") or payload.get("playlistName"):
            return self._json_error(
                "Playlist destination is automatic for teacher-play saves. "
                "Do not send playlistId or playlistName."
            )

        from apps.exercises.utils.transpose import normalize_key
        key = normalize_key(payload.get("key", "C"))
        meter = payload.get("meter")  # None = free/open mode (no metric validation)
        clef = payload.get("clef", "keyboard")
        staff_distribution = payload.get("staffDistribution", "keyboard")
        barline_offsets = payload.get("barline_offsets") or []
        analysis_slices = payload.get("analysisSlices", [])  # [] => status "none"; non-empty => "reviewed"
        analyze_config = payload.get("analyzeConfig")
        display = payload.get("display")  # teacher's analysis display flags (showRomans, ...)

        try:
            description = self._description(payload)
            skill_tags = self._skill_tags(payload)
            mode = self._single_mode(payload)
            unit = self._single_unit(skill_tags)
            is_public = self._bool_field(payload, "isPublic", False)
            save_as_official = self._bool_field(payload, "saveAsOfficial", False)
            create_transpositions = self._bool_field(payload, "createTranspositions", False)
            key_set_raw = payload.get("keySet") or []
            if isinstance(key_set_raw, str):
                key_set = [k.strip() for k in key_set_raw.split(",") if k.strip()]
            else:
                key_set = [str(k).strip() for k in key_set_raw if str(k).strip()]

            author = self._resolve_author(request, save_as_official)
            if save_as_official and author is None:
                if request.user.is_superuser:
                    return self._json_error(
                        f"Factory user {settings.FACTORY_USER_EMAIL} does not exist.",
                        status=400,
                    )
                return self._json_error("Only superusers can save official exercises.", status=403)

            _mode_map = {
                "identify": InteractionMode.IDENTIFICATION,
                "harmonization": InteractionMode.HARMONIZATION,
            }

            import copy
            mode_display = copy.deepcopy(display or {})
            for flag in ["showRomans", "showFigures", "showChordLabels", "showScaleDegrees", "showNoteNames"]:
                if flag not in mode_display:
                    mode_display[flag] = False
            if mode == "roman":
                mode_display["showRomans"] = True
                mode_display["showFigures"] = False
            elif mode == "figures":
                mode_display["showFigures"] = True
                mode_display["showRomans"] = False
            elif mode in ("identify", "harmonization"):
                mode_display["showRomans"] = False
                mode_display["showFigures"] = False

            from apps.exercises.services.canonical_playlist import (
                append_exercise_to_canonical_playlist,
                resolve_canonical_playlist,
            )

            with transaction.atomic():
                exercise = save_chordal_umto_exercise(
                    description=description,
                    author=author,
                    chords=chords,
                    key=key,
                    meter=meter,
                    clef=clef,
                    staff_distribution=staff_distribution,
                    skill_tags=skill_tags,
                    is_public=is_public,
                    auto_playlist=False,
                    barline_offsets=barline_offsets,
                    analysis=analysis_slices,
                    analyze_config=analyze_config,
                    display=mode_display,
                    mode=_mode_map.get(mode, InteractionMode.PLAYBACK),
                )
                if save_as_official:
                    exercise.is_official = True
                    exercise.save(update_fields=["is_official"])

                playlist = resolve_canonical_playlist(
                    author=author,
                    unit=unit,
                    mode=mode,
                    is_public=is_public,
                    is_official=save_as_official,
                )
                append_exercise_to_canonical_playlist(playlist, exercise)

                if create_transpositions and key_set:
                    from apps.exercises.services.transposition_service import generate_transposed_copies
                    generate_transposed_copies(
                        source_exercise=exercise,
                        key_set=key_set,
                        playlist=playlist,
                        author=author,
                        is_official=save_as_official,
                        overwrite=False,
                    )

        except (NonUMTOExerciseError, ValueError, KeyError) as exc:
            return self._json_error(str(exc) or "Invalid exercise payload.", status=400)

        review_status = (
            (exercise.data or {})
            .get("score", {})
            .get("umto", {})
            .get("metadata", {})
            .get("analysis_review_status", "none")
        )
        response_data = {
            "id": exercise.id,
            "ids": [exercise.id],
            "reviewStatus": review_status,
            "playlistId": playlist.id,
            "playlistName": playlist.name,
            "playlists": [{"id": playlist.id, "name": playlist.name, "mode": mode}],
        }
        return JsonResponse(status=201, data=response_data)


class AuthoringMetaView(View):
    http_method_names = ["get"]

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        units = []
        for unit in TaxonomyReader.get_all_units():
            unit_n = unit.get("n")
            try:
                unit_n = int(unit_n)
            except (TypeError, ValueError):
                pass
            units.append({"n": unit_n, "title": unit.get("title", "")})

        playlist_filter = Q(authored_by=request.user)
        if request.user.is_superuser:
            factory_user = User.objects.filter(email=settings.FACTORY_USER_EMAIL).first()
            if factory_user is not None:
                playlist_filter |= Q(authored_by=factory_user)

        playlists = [
            {
                "id": playlist.id,
                "name": playlist.name,
                "locked": bool(playlist.has_been_performed),
                "skillTags": playlist.skill_tags or [],
            }
            for playlist in Playlist.objects.filter(playlist_filter).order_by("name", "id")
        ]

        return JsonResponse(
            {
                "units": units,
                "playlists": playlists,
                "isSuperuser": bool(request.user.is_superuser),
            }
        )


@login_required()
@method_decorator(csrf_exempt)
def exercise_performance_history(
    request, playlist_name, exercise_num=1, *args, **kwargs
):
    # TODO: change this
    # yes, why is course id not also passed to this function?
    playlist = Playlist.objects.filter(
        Q(name=playlist_name) | Q(id=playlist_name)
    ).first()
    if playlist is None:
        raise Http404("Playlist with this name or ID does not exist.")

    if (
        not playlist.is_public
        and not playlist.authored_by == request.user
        and not request.user.pk in playlist.authored_by.content_permits
    ):
        raise PermissionDenied

    exercise = playlist.get_exercise_obj_by_num(exercise_num)
    if exercise is None:
        if len(playlist.exercise_list) == 0:
            raise Http404("This playlist has no exercises.")
        raise Http404(
            f"Exercise #{exercise_num} in playlist '{playlist.name}' could not be found. "
            "It may have been deleted. Please edit the playlist to remove missing exercises."
        )

    playlist_performance = PerformanceData.objects.filter(
        playlist=playlist, user=request.user
    ).last()

    exercise_data = json.dumps(
        {
            "exerciseIsPerformed": playlist_performance.exercise_is_performed(
                exercise.id
            )
            if playlist_performance
            else False,
            "exerciseErrorCount": playlist_performance.exercise_error_count(exercise.id)
            if playlist_performance
            else 0,
        }
    )
    return HttpResponse(exercise_data, status=200)
