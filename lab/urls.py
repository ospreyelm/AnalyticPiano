from apps.accounts.views import send_keyboard_size
from django.urls import re_path, path

from apps.exercises.views import playlist_performance_view, submit_exercise_performance, submit_playlist_performance
from lti_tool.views import LTIToolConfigView, LTILaunchView
from .views import (
    check_course_authorization,
    AddExerciseView,
    PlayView,
    PlaylistView,
    ExerciseView,
    APIGroupView,
    ManageView,
    APIView,
    APIExerciseView,
    RefreshExerciseDefinition,
    CourseView,
)

app_name = 'lab'

urlpatterns = [
    re_path(r'^$', PlayView.as_view(), name='index'),

    # User Preferences
    path('keyboard-size/', send_keyboard_size, name='keyboard-size'),
    path('exercises/keyboard-size/', send_keyboard_size, name='keyboard-size'),

    # Exercises, Playlists and Courses
    # FIXME should be added to a course: ^courses/(?P<course_id>\d+)/exercises/add/$?
    re_path(r'^exercises/add$', AddExerciseView.as_view(), name='add-exercise'),
    re_path(r'^manage$', ManageView.as_view(), name="manage"),
    path('exercises/<str:exercise_id>/', ExerciseView.as_view(), name="exercise-view"),
    path('exercises/<str:group_name>/', PlaylistView.as_view(), name="exercise-groups"),
    path('exercises/<str:group_name>/<int:exercise_num>', PlaylistView.as_view(), name="exercises"),
    path('courses/<str:course_slug>/', CourseView.as_view(), name="course-view"),
    re_path(r'definition$', RefreshExerciseDefinition.as_view(),
            name="refresh-definition"),
    re_path(r'^exercises$', PlaylistView.as_view()),

    # Performance
    re_path(r'exercise-performance$', submit_exercise_performance, name='exercise-performance'),
    re_path(r'playlist-performance$', submit_playlist_performance, name='playlist-performance'),

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
         name='performance-report'),

    # Deprecated
    # re_path(r'^courses/(?P<course_id>\d+)/exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)/(?P<exercise_name>\d+)$',
    #         PlaylistView.as_view(), name="course-exercises"),
    # re_path(r'^courses/(?P<course_id>\d+)/exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)$', PlaylistView.as_view(),
    #         name="course-exercise-groups"),
    # re_path(r'^courses/(?P<course_id>\d+)/manage$', ManageView.as_view(), name="course-manage"),
    # re_path(r'^courses/(?P<course_id>\d+)/authcheck$', check_course_authorization, name="course-authorization-check"),
    # re_path(r'^courses/(?P<course_id>\d+)/exercises$', PlaylistView.as_view()),
    # re_path(r'^courses/(?P<course_id>\d+)$', PlayView.as_view(), name="course-index"),
]
