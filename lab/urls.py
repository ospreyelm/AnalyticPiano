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
    identification_answers_view,
)

from .views import (
    AddExerciseView,
    AuthoringMetaView,
    PlayView,
    PlaylistView,
    ExerciseView,
    RefreshExerciseDefinition,
    CourseView,
    SkillMapView,
    SkillMapDataView,
    exercise_performance_history,
    dev_corpus_bach_json,
    ChoraleAnalysisDebugView,
)

app_name = "lab"

urlpatterns = [
    path("", RedirectView.as_view(url="/play"), name="index"),
    path("play/", PlayView.as_view(), name="index"),
    path("teacher/play/", PlayView.as_view(), name="play"),
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
    path("exercises/add/", AddExerciseView.as_view(), name="add-exercise"),
    path(
        "exercises/authoring-meta/",
        AuthoringMetaView.as_view(),
        name="authoring-meta",
    ),
    # Performance
    path(
        "ajax/exercise-performance/",
        submit_exercise_performance,
        name="exercise-performance",
    ),
    path(
        "ajax/identification-answers/",
        identification_answers_view,
        name="identification-answers",
    ),
    # Exercises, Playlists, Courses
    path("exercises/<str:exercise_id>/", ExerciseView.as_view(), name="exercise-view"),
    path(
        "playlists/<str:playlist_id>/definition/",
        RefreshExerciseDefinition.as_view(),
        name="refresh-definition",
    ),
    path(
        "playlists/<str:playlist_id>/<int:exercise_num>/definition/",
        RefreshExerciseDefinition.as_view(),
        name="refresh-definition",
    ),
    path(
        "playlists/<str:course_id>/<str:playlist_id>/definition/",
        RefreshExerciseDefinition.as_view(),
        name="refresh-definition",
    ),
    path(
        "playlists/<str:course_id>/<str:playlist_id>/<int:exercise_num>/definition/",
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
    # Admin
    path(
        "admin/exercises/playlist/<str:playlist_id>/performances/",
        playlist_performance_view,
        name="performance-report",
    ),
    # Dev-only: serve exported corpus JSONs for local testing
    path(
        "ajax/dev/corpus/bach/<str:filename>",
        dev_corpus_bach_json,
        name="dev-corpus-bach-json",
    ),
    # Debug page to print corpus analyses (roman + figured bass)
    path(
        "debug/analysis/",
        ChoraleAnalysisDebugView.as_view(),
        name="debug-analysis",
    ),
    # Skill Map
    path("skill-map/", SkillMapView.as_view(), name="skill-map"),
    path("skill-map/<str:course_id>/", SkillMapView.as_view(), name="skill-map"),
    path("ajax/skill-map/", SkillMapDataView.as_view(), name="skill-map-data"),
    path("ajax/skill-map/<str:course_id>/", SkillMapDataView.as_view(), name="skill-map-data"),
]
