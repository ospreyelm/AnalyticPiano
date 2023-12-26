from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import When, Case, Q
from django.urls import reverse
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.generic import View, TemplateView, RedirectView
from django.views.decorators.csrf import csrf_exempt, csrf_protect

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
)

import json
import copy

# from django.core.mail import send_mail

User = get_user_model()


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


# TODO lots of repeated code between PlaylistView and RefreshExerciseDefinition.
#   Could be fixed thru some sort of inheritance or thru making the refresh request after rendering PlaylistView
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

        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if exercise is None:
            raise Http404("This playlist has no exercises.")

        prev_num = playlist.prev_num(exercise_num)
        next_num = playlist.next_num(exercise_num)

        next_exercise_url = playlist.get_exercise_url_by_num(
            num=next_num, course_id=course_id
        )
        prev_exercise_url = playlist.get_exercise_url_by_num(
            num=prev_num, course_id=course_id
        )
        next_exercise_obj = playlist.get_exercise_obj_by_num(next_num)
        next_exercise_id = next_exercise_obj.id if next_exercise_obj != None else ""
        prev_exercise_obj = playlist.get_exercise_obj_by_num(prev_num)
        prev_exercise_id = prev_exercise_obj.id if prev_exercise_obj != None else ""
        first_exercise_obj = playlist.get_exercise_obj_by_num(1)
        first_exercise_id = (
            first_exercise_obj.id if first_exercise_obj.id != exercise.id else ""
        )
        context = {"group_list": []}
        exercise_context = {}

        exercise_list = []
        for num, _ in enumerate(playlist.exercise_list, 1):
            exercise_list.append(
                dict(
                    id=f"{playlist_id}/{num}",
                    name=f"{num}",
                    url=playlist.get_exercise_url_by_num(num),
                    selected=exercise_num == num,
                )
            )

        course_performed = None
        playlist_previously_passed = False
        if course_id:
            course_performed = Course.objects.filter(id=course_id).first()
            if course_performed:
                context["course_name"] = course_performed.title
                course_link = reverse(
                    "lab:course-view", kwargs={"course_id": course_id}
                )
                context["course_link"] = course_link
                if (
                    course_performed.performance_dict.get(str(request.user), {}).get(
                        playlist_id, "X"
                    )
                ) != "X":
                    playlist_previously_passed = True

        context["playlist_previously_passed"] = playlist_previously_passed

        exercise_is_performed = False
        exercise_error_count = 0
        playlist_performance = PerformanceData.objects.filter(
            playlist=playlist, user=request.user, course=course_performed
        ).last()
        if playlist_performance:
            exercise_is_performed = playlist_performance.exercise_is_performed(
                exercise.id
            )
            exercise_error_count = playlist_performance.exercise_error_count(
                exercise.id
            )

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

        exercise_context.update(exercise.data)
        exercise_context.update(
            {
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
                "exerciseIsPerformed": exercise_is_performed,
                "exerciseErrorCount": exercise_error_count,
                "playlistName": playlist.id,
                "courseId": course_performed.id if course_performed else None,
            }
        )
        self.requirejs_context.set_app_module("app/components/app/exercise")
        self.requirejs_context.set_module_params(
            "app/components/app/exercise", exercise_context
        )
        self.requirejs_context.add_to_view(context)

        return render(request, "exercise.html", context)


class RefreshExerciseDefinition(RequirejsView):
    def get(self, request, playlist_id, course_id=None, *args, **kwargs):
        playlist = get_object_or_404(Playlist, id=playlist_id)
        exercise_num = request.GET.get("exercise_num")
        exercise_num = int(exercise_num)

        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if exercise is None:
            raise Http404("Exercise not found.")

        prev_num = playlist.prev_num(exercise_num)
        next_num = playlist.next_num(exercise_num)

        next_exercise_url = playlist.get_exercise_url_by_num(
            num=next_num, course_id=course_id
        )
        prev_exercise_url = playlist.get_exercise_url_by_num(
            num=prev_num, course_id=course_id
        )
        next_exercise_obj = playlist.get_exercise_obj_by_num(next_num)
        next_exercise_id = next_exercise_obj.id if next_exercise_obj != None else ""

        prev_exercise_obj = playlist.get_exercise_obj_by_num(prev_num)
        prev_exercise_id = prev_exercise_obj.id if prev_exercise_obj != None else ""

        first_exercise_obj = playlist.get_exercise_obj_by_num(1)
        first_exercise_id = (
            first_exercise_obj.id if first_exercise_obj.id != exercise.id else ""
        )
        exercise_context = {}

        exercise_list = []
        for num, _ in enumerate(playlist.exercise_list, 1):
            exercise_list.append(
                dict(
                    id=f"{playlist.id}/{num}",
                    name=f"{num}",
                    url=playlist.get_exercise_url_by_num(num),
                    selected=exercise_num == num,
                )
            )

        course_performed = None

        if course_id:
            course_performed = Course.objects.get(id=course_id)

        # TODO: what is the current functionality of this?
        exercise_is_performed = False
        exercise_error_count = 0
        playlist_performance = PerformanceData.objects.filter(
            playlist=playlist, user=request.user, course=course_performed
        ).last()
        if playlist_performance:
            exercise_is_performed = playlist_performance.exercise_is_performed(
                exercise.id
            )
            exercise_error_count = playlist_performance.exercise_error_count(
                exercise.id
            )

        exercise_context.update(exercise.data)
        exercise_context.update(
            {
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
                "exerciseIsPerformed": exercise_is_performed,
                "exerciseErrorCount": exercise_error_count,
                "playlistName": playlist.id,
                "courseId": course_performed.id if course_performed else None,
            }
        )

        self.requirejs_context.set_app_module("app/components/app/exercise")
        self.requirejs_context.set_module_params(
            "app/components/app/exercise", exercise_context
        )
        # self.requirejs_context.add_to_view(context)
        return JsonResponse(data=exercise_context)


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

        url = reverse("lab:exercise-view", kwargs={"exercise_id": exercise_id})
        exercise_info = [
            dict(id=exercise_id, name=f"{exercise._id}", url=url, selected=True)
        ]

        context = {"group_list": []}
        exercise_context = {}

        exercise_context.update(exercise.data)
        exercise_context.update({"exerciseList": [exercise_info]})
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


@method_decorator(csrf_exempt, name="dispatch")
class AddExerciseView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        data = request.POST.get("data")
        if data == "null":
            # TO DO message for user: 'You tried to create an empty exercise. Add some content!'
            return HttpResponse(status=400)

        exercise = Exercise()
        exercise.data = json.loads(data)

        if request.user.is_authenticated:
            exercise.authored_by = request.user
        else:
            # TO DO message for user: 'You are not logged in. You must be logged in to create exercises.'
            return HttpResponse(status=400)

        exercise.save()

        return JsonResponse(status=201, data={"id": exercise.id})


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
        raise Http404("This playlist has no exercises.")

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
