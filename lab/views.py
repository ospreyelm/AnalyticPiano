from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.generic import View, TemplateView, RedirectView
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from braces.views import CsrfExemptMixin, LoginRequiredMixin
from django_auth_lti import const

from .objects import ExerciseRepository
from .decorators import role_required, course_authorization_required
from .verification import has_instructor_role, has_course_authorization
from lti_tool.models import LTIConsumer, LTICourse
from apps.exercises.models import Exercise, Playlist

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
        if 'config' not in self._config:
            self._config['config'] = {}
        if module_id not in self._config['config']:
            self._config['config'][module_id] = {}
        self._config['config'][module_id].update(module_config)
        return self

    def set_app_module(self, app_module_id):
        self.set_module_params('app/main', {'app_module': app_module_id})
        return self

    def add_to_view(self, view_context):
        view_context['requirejs'] = self
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
        self.requirejs_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)

    def get_context_data(self, **kwargs):
        context = super(RequirejsTemplateView, self).get_context_data(**kwargs)
        self.requirejs_context.set_app_module(getattr(self, 'requirejs_app'))
        self.requirejs_context.add_to_view(context)
        return context


class RequirejsView(View):
    def __init__(self, *args, **kwargs):
        super(RequirejsView, self).__init__(*args, **kwargs)
        self.requirejs_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)


class PlayView(RequirejsTemplateView):
    template_name = "play.html"
    requirejs_app = 'app/components/app/play'

    def get_context_data(self, course_id=None, **kwargs):
        context = super(PlayView, self).get_context_data(**kwargs)
        er = ExerciseRepository.create(course_id=course_id)

        context['group_list'] = er.getGroupList()
        # for testing on Windows, use following line
        # context['group_list'] = []
        context['has_manage_perm'] = has_instructor_role(self.request) and has_course_authorization(self.request,
                                                                                                    course_id)
        if context['has_manage_perm']:
            if course_id is None:
                context['manage_url'] = reverse('lab:manage')
            else:
                context['manage_url'] = reverse('lab:course-manage', kwargs={"course_id": course_id})

        if course_id is None:
            context['home_url'] = reverse('lab:index')
        else:
            context['home_url'] = reverse("lab:course-index", kwargs={"course_id": course_id})

        return context


class ExerciseView(RequirejsView):
    def get(self, request, group_name, exercise_num=1, *args, **kwargs):
        playlist = get_object_or_404(Playlist, name=group_name)
        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if exercise is None:
            raise Http404("This playlist has no exercises.")

        next_exercise = playlist.get_exercise_url_by_num(
            num=playlist.next_num(exercise_num)
        )
        prev_exercise = playlist.get_exercise_url_by_num(
            num=playlist.prev_num(exercise_num)
        )

        context = {'group_list': []}
        exercise_context = {}

        exercise_list = []
        for num, _ in enumerate(playlist.exercise_list, 1):
            print(exercise_num, num)
            exercise_list.append(
                dict(id=f'{group_name}/{num}',
                     name=f'{num}',
                     url=playlist.get_exercise_url_by_num(num),
                     selected=exercise_num == num)
            )

        exercise_context.update(exercise.data)
        exercise_context.update({
            "nextExercise": next_exercise,
            "previousExercise": prev_exercise,
            "exerciseList": exercise_list
        })

        self.requirejs_context.set_app_module('app/components/app/exercise')
        self.requirejs_context.set_module_params('app/components/app/exercise', exercise_context)
        self.requirejs_context.add_to_view(context)

        return render(request, "exercise.html", context)


class ManageView(RequirejsView, LoginRequiredMixin):
    @method_decorator(course_authorization_required(source="arguments"))
    @method_decorator(
        role_required([const.ADMINISTRATOR, const.INSTRUCTOR], redirect_url='lab:not_authorized', raise_exception=True))
    def get(self, request, course_id=None):
        er = ExerciseRepository.create(course_id=course_id)
        context = {"course_label": "", "has_manage_perm": True}
        manage_params = {"group_list": er.getGroupList()}

        if course_id is None:
            context['manage_url'] = reverse('lab:manage')
            context['home_url'] = reverse('lab:index')
            manage_params['exercise_api_url'] = reverse('lab:api-exercises')
        else:
            course_names = LTICourse.getCourseNames(course_id)
            context['course_label'] = "%s (ID: %s)" % (course_names.get('name'), course_id)
            context['manage_url'] = reverse('lab:course-manage', kwargs={"course_id": course_id})
            context['home_url'] = reverse("lab:course-index", kwargs={"course_id": course_id})
            manage_params['exercise_api_url'] = "%s?%s" % (
                reverse('lab:api-exercises'), urlencode({"course_id": course_id}))

        self.requirejs_context.set_app_module('app/components/app/manage')
        self.requirejs_context.set_module_params('app/components/app/manage', manage_params)
        self.requirejs_context.add_to_view(context)

        return render(request, "manage.html", context)


class APIView(View):
    api_version = 1

    def get(self, request):
        return HttpResponse(json.dumps({
            'url': reverse('lab:api'),
            'version': self.api_version
        }))


class APIGroupView(CsrfExemptMixin, View):
    def get(self, request):
        '''Public list of groups and exercises.'''
        course_id = request.GET.get('course_id', None)
        er = ExerciseRepository.create(course_id=course_id)
        data = er.getGroupList()
        json_data = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
        return HttpResponse(json_data, content_type='application/json')


class APIExerciseView(CsrfExemptMixin, View):
    def get(self, request):
        course_id = request.GET.get('course_id', None)
        group_name = request.GET.get('group_name', None)
        exercise_name = request.GET.get('exercise_name', None)

        er = ExerciseRepository.create(course_id=course_id)
        if exercise_name is not None and group_name is not None:
            exercise = er.findExerciseByGroup(group_name, exercise_name)
            if exercise is None:
                raise Http404("Exercise does not exist.")
            exercise.load()
            data = exercise.asDict()
        elif exercise_name is None and group_name is not None:
            group = er.findGroup(group_name)
            if group is None:
                raise Http404("Exercise group does not exist.")
            data = group.asDict()
        else:
            data = er.asDict()

        return HttpResponse(json.dumps(data, sort_keys=True, indent=4, separators=(',', ': ')),
                            content_type='application/json')

    @method_decorator(course_authorization_required(source='query'))
    @method_decorator(
        role_required([const.ADMINISTRATOR, const.INSTRUCTOR], redirect_url='lab:not_authorized', raise_exception=True))
    def post(self, request):
        course_id = request.GET.get("course_id", None)
        exercise_data = json.loads(request.POST.get('exercise', None))
        result = ExerciseRepository.create(course_id=course_id).createExercise(exercise_data)

        return HttpResponse(json.dumps(result), content_type='application/json')

    @method_decorator(course_authorization_required(source='query'))
    @method_decorator(
        role_required([const.ADMINISTRATOR, const.INSTRUCTOR], redirect_url='lab:not_authorized', raise_exception=True))
    def delete(self, request):
        course_id = request.GET.get("course_id", None)
        group_name = request.GET.get('group_name', None)
        exercise_name = request.GET.get('exercise_name', None)

        er = ExerciseRepository.create(course_id=course_id)
        deleted, description = (False, "No action taken")
        if group_name is not None and exercise_name is not None:
            deleted, description = er.deleteExercise(group_name, exercise_name)
        elif group_name is not None:
            deleted, description = er.deleteGroup(group_name)

        result = {}
        if deleted:
            result['status'] = "success"
            result['description'] = description
        else:
            result['status'] = "failure"
            result['description'] = "Error: %s" % description

        return HttpResponse(json.dumps(result), content_type='application/json')


def not_authorized(request):
    return HttpResponse('Unauthorized', status=401)


def check_course_authorization(request, course_id, raise_exception=False):
    authorized = has_course_authorization(request, course_id, raise_exception)
    result = {
        "user_id": request.user.id,
        "course_id": course_id,
        "is_authorized": authorized
    }
    status = 200
    if not authorized:
        status = 403  # forbidden
    return HttpResponse(json.dumps(result), content_type='application/json', status=status)


@method_decorator(csrf_exempt, name='dispatch')
class CourseExerciseView(View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        data = request.POST.get('data')
        if data == 'null':
            return HttpResponse(status=400)

        exercise = Exercise()
        exercise.data = json.loads(data)

        # FIXME
        exercise.authored_by = User.get_guest_user()
        exercise.is_public = True

        exercise.save()
        return HttpResponse(status=201)
