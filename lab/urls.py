from django.urls import re_path, path
from django.views.generic import RedirectView

from apps.accounts.views import (
    preferences_view,
    set_preferred_mute_value,
    set_preferred_volume,
)
from apps.exercises.views import (
    playlist_performance_view,
    submit_exercise_performance,
    submit_playlist_performance,
)

from .views import (
    AddExerciseView,
    PlayView,
    PlaylistView,
    ExerciseView,
    APIView,
    APIExerciseView,
    RefreshExerciseDefinition,
    CourseView,
    ManageView,
    exercise_performance_history,
)

app_name = "lab"

urlpatterns = [
    path("", RedirectView.as_view(url="/play"), name="index"),
    path("play/", PlayView.as_view(), name="index"),
    # User Preferences
    path("ajax/preferences/", preferences_view, name="user-preferences"),
    path("ajax/set-mute/", set_preferred_mute_value, name="user-preferred-mute"),
    path("ajax/set-volume/", set_preferred_volume, name="user-preferred-volume"),
    # Exercise Performance History
    path(
        "ajax/playlists/<str:playlist_id>/<int:exercise_num>/history/",
        exercise_performance_history,
        name="exercise-performance-history",
    ),
    path(
        "ajax/playlists/<str:playlist_id>/history/",
        exercise_performance_history,
        name="exercise-performance-history",
    ),
    # FIXME should be added to a course: ^courses/(?P<course_id>\d+)/exercises/add/$?
    path("exercises/add/", AddExerciseView.as_view(), name="add-exercise"),
    # Performance
    path(
        "ajax/exercise-performance/",
        submit_exercise_performance,
        name="exercise-performance",
    ),
    path(
        "ajax/playlist-performance/",
        submit_playlist_performance,
        name="playlist-performance",
    ),
    # Exercises, Playlists, Courses
    path("exercises/<str:exercise_id>/", ExerciseView.as_view(), name="exercise-view"),
    path(
        "playlists/<str:playlist_id>/definition/",
        RefreshExerciseDefinition.as_view(),
        name="refresh-definition",
    ),
    path(
        "playlists/<str:course_id>/<str:playlist_id>/definition/",
        RefreshExerciseDefinition.as_view(),
        name="refresh-definition",
    ),
    path(
        "playlists/<str:playlist_id>/<int:exercise_num>/",
        PlaylistView.as_view(),
        name="playlist-view",
    ),
    path(
        "playlists/<str:course_id>/<str:playlist_id>/<int:exercise_num>/",
        PlaylistView.as_view(),
        name="playlist-view",
    ),
    path("playlists/<str:playlist_id>/", PlaylistView.as_view(), name="playlist-view"),
    path(
        "playlists/<str:course_id>/<str:playlist_id>/",
        PlaylistView.as_view(),
        name="playlist-view",
    ),
    path("courses/<str:course_id>/", CourseView.as_view(), name="course-view"),
    path("ajax/exercise-stats/", CourseView.as_view(), name="exercise-stats"),
    # re_path(r"^manage$", ManageView.as_view(), name="manage"),
    # API
    re_path(r"^api$", APIView.as_view(), name="api"),
    re_path(r"^api/v1/exercises$", APIExerciseView.as_view(), name="api-exercises"),
    # LTI -- deprecated -- moved into separate app named "lti"
    # # Mainting these URLs for backwards compatibility. Remove when possible.
    # re_path(r"^lti-launch$", LTILaunchView.as_view(), name="lti-launch"),
    # re_path(r"^lti-config$", LTIToolConfigView.as_view(), name="lti-config"),
    # Admin
    path(
        "admin/exercises/playlist/<str:playlist_id>/performances/",
        playlist_performance_view,
        name="performance-report",
    ),
    # DEPRECATED
    # re_path(r'^courses/(?P<course_id>\d+)/manage$', ManageView.as_view(), name="course-manage"),
    # re_path(r'^courses/(?P<course_id>\d+)/authcheck$', check_course_authorization, name="course-authorization-check"),
    # re_path(r'^courses/(?P<course_id>\d+)/exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)/(?P<exercise_name>\d+)$',
    #         PlaylistView.as_view(), name="course-exercises"),
    # re_path(r'^courses/(?P<course_id>\d+)/exercises/(?P<group_name>[a-zA-Z0-9_\-.]+)$', PlaylistView.as_view(),
    #         name="course-exercise-groups"),
    # re_path(r'^courses/(?P<course_id>\d+)/exercises$', PlaylistView.as_view()),
    # re_path(r'^courses/(?P<course_id>\d+)$', PlayView.as_view(), name="course-index"),
    # re_path(r'^api/v1/groups$', APIGroupView.as_view(), name="api-groups"),
]
