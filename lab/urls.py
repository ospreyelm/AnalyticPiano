from django.contrib.auth.decorators import permission_required
from django.urls import re_path, path
from django.views.generic import TemplateView

from apps.exercises.views import playlist_performance_view, submit_exercise_performance, submit_playlist_performance
from lti_tool.views import LTIToolConfigView, LTILaunchView
from .views import (
    check_course_authorization,
    CourseExerciseView,
    PlayView,
    ExerciseView,
    ManageView,
    APIView,
    APIExerciseView,
    APIGroupView
)

app_name = 'lab'

urlpatterns = [
    re_path(r'^$', PlayView.as_view(), name='index'),

    # Course Exercises
    re_path(r'^courses/(?P<course_id>\d+)/manage$', ManageView.as_view(), name="course-manage"),
    re_path(r'^courses/(?P<course_id>\d+)/authcheck$', check_course_authorization, name="course-authorization-check"),
    re_path(r'^courses/(?P<course_id>\d+)/exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)/(?P<exercise_name>\d+)$',
            ExerciseView.as_view(), name="course-exercises"),
    re_path(r'^courses/(?P<course_id>\d+)/exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)$', ExerciseView.as_view(),
            name="course-exercise-groups"),
    re_path(r'^courses/(?P<course_id>\d+)/exercises$', ExerciseView.as_view()),
    re_path(r'^courses/(?P<course_id>\d+)$', PlayView.as_view(), name="course-index"),

    # FIXME should be added to a course: ^courses/(?P<course_id>\d+)/exercises/add/$?
    re_path(r'^exercises/add$', CourseExerciseView.as_view(), name='add-exercise'),

    re_path(r'exercise-performance$', submit_exercise_performance, name='exercise-performance'),
    re_path(r'playlist-performance$', submit_playlist_performance, name='playlist-performance'),

    # Non-Course Exercises
    re_path(r'^manage$', ManageView.as_view(), name="manage"),
    path('exercises/<str:group_name>/<int:exercise_num>', ExerciseView.as_view(), name="exercises"),
    re_path(r'^exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)$', ExerciseView.as_view(), name="exercise-groups"),

    re_path(r'^exercises$', ExerciseView.as_view()),

    # API
    re_path(r'^api$', APIView.as_view(), name="api"),
    re_path(r'^api/v1/exercises$', APIExerciseView.as_view(), name="api-exercises"),
    re_path(r'^api/v1/groups$', APIGroupView.as_view(), name="api-groups"),

    # LTI -- deprecated -- moved into separate app named "lti"
    # Mainting these URLs for backwards compatibility. Remove when possible.
    re_path(r'^lti-launch$', LTILaunchView.as_view(), name='lti-launch'),
    re_path(r'^lti-config$', LTIToolConfigView.as_view(), name='lti-config'),

    # Admin
    path('admin/exercises/playlist/<str:playlist_id>/performances/',
         playlist_performance_view,
         name='playlist_performance'),

]
