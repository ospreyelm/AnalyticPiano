from django.urls import path

from apps.dashboard.views.groups import (
    groups_list_view,
    group_add_view,
    group_edit_view,
    group_delete_view,
    remove_member,
    join_group_view,
    regenerate_join_code_view,
)
from apps.dashboard.views.import_export import (
    ExerciseExportView,
    ExerciseImportView,
    PlaylistExportView,
    PlaylistImportView,
    CourseExportView,
    CourseImportView,
)
from apps.dashboard.views.index import dashboard_index_view
from apps.dashboard.views.courses import (
    courses_list_view,
    courses_by_user_view,
    course_add_view,
    course_edit_view,
    course_delete_view,
    course_activity_view,
    identification_answers_view,
)
from apps.dashboard.views.exercises import (
    exercises_list_view,
    exercise_edit_view,
    exercise_delete_view,
    exercise_add_view,
    api_bulk_delete_exercises,
)
from apps.dashboard.views.performance import (
    performances_list_view,
    playlist_performance_view,
)
from apps.dashboard.views.playlists import (
    playlists_list_view,
    playlist_add_view,
    playlist_edit_view,
    playlist_delete_view,
)
from apps.dashboard.views.preferences import dashboard_preferences_view
from apps.dashboard.views.connections import (
    courses_by_others_view,
    connections_view,
    toggle_connection_pin_view,
    toggle_connection_pin_with_confirmation,
    toggle_content_permit_view,
    toggle_performance_permit_view,
)
from apps.dashboard.views.my_work import my_work_view

from apps.dashboard.views.api_workbench import (
    api_recent_imports,
    api_multiply_projection,
    api_chordal_analysis_review,
    workbench_view,
    workbench_upload_view,
)
from apps.dashboard.views.taxonomy import taxonomy_debug_view

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_index_view, name="index"),
    # Teacher Workbench
    path("workbench/", workbench_view, name="workbench"),
    path("workbench/upload/", workbench_upload_view, name="workbench-upload"),
    # Exercises
    path("exercises/", exercises_list_view, name="exercises-list"),
    path("exercises/add/", exercise_add_view, name="add-exercise"),
    path("exercises/<str:exercise_id>/", exercise_edit_view, name="edit-exercise"),
    path("exercises/<str:exercise_id>/delete/", exercise_delete_view, name="delete-exercise"),
    # Playlists
    path("playlists/", playlists_list_view, name="playlists-list"),
    path("playlists/add/", playlist_add_view, name="add-playlist"),
    path("playlists/<str:playlist_id>/", playlist_edit_view, name="edit-playlist"),
    path("playlists/<str:playlist_id>/delete/", playlist_delete_view, name="delete-playlist"),
    # Courses
    path("courses/", courses_list_view, name="courses-list"),
    path("courses/add/", course_add_view, name="add-course"),
    path("courses/<str:course_id>/", course_edit_view, name="edit-course"),
    path("courses/<str:course_id>/delete/", course_delete_view, name="delete-course"),
    path("courses/<str:course_id>/activity/", course_activity_view, name="course-activity"),
    path(
        "courses/<str:course_id>/identification-answers/<int:student_id>/",
        identification_answers_view,
        name="course-identification-answers",
    ),
    path("courses/<int:courses_author_id>/", courses_by_user_view, name="courses-by-user"),
    # Performances
    path("performances/", performances_list_view, name="performed-playlists"),
    path("performances/<int:other_id>/", performances_list_view, name="performances-by-user"),
    path("playlist-performance/<int:performance_id>", playlist_performance_view, name="playlist-performance"),
        # performance by user of a playlist in the context of a course
    # My Work (student view)
    path("my-work/", my_work_view, name="my-work"),
    # Connections
    path("connections/", connections_view, name="connections"),
    path("courses-by-other-users/", courses_by_others_view, name="courses-by-others"),
    path("connections/toggle-content-permit/<int:other_id>/", toggle_content_permit_view, name="toggle-content-permit"),
    path("connections/toggle-performance-permit/<int:other_id>/", toggle_performance_permit_view, name="toggle-performance-permit"),
    path("connections/toggle-connection-pin/<int:other_id>/", toggle_connection_pin_view, name="toggle-connection-pin"),
    path("connections/toggle-connection-pin/<int:other_id>/confirm/", toggle_connection_pin_with_confirmation, name="toggle-connection-pin-with-confirmation"),
    # Groups
    path("groups/", groups_list_view, name="groups-list"),
    path("groups/join/", join_group_view, name="join-group"),
    path("groups/add/", group_add_view, name="add-group"),
    path("groups/<str:group_id>/", group_edit_view, name="edit-group"),
    path("groups/<str:group_id>/delete/", group_delete_view, name="delete-group"),
    path("groups/<str:group_id>/remove-member/<int:member_id>/", remove_member, name="remove-group-member"),
    path("groups/<str:group_id>/regenerate-code/", regenerate_join_code_view, name="regenerate-join-code"),
    # Preferences
    path("preferences/", dashboard_preferences_view, name="preferences"),
    # Import/Export
    path("export/exercises/", ExerciseExportView.as_view(), name="export-exercises"),
    path("import/exercises/", ExerciseImportView.as_view(), name="import-exercises"),
    path("export/playlists/", PlaylistExportView.as_view(), name="export-playlists"),
    path("import/playlists/", PlaylistImportView.as_view(), name="import-playlists"),
    path("export/courses/", CourseExportView.as_view(), name="export-courses"),
    path("import/courses/", CourseImportView.as_view(), name="import-courses"),
    
    # Teacher Dashboard Workbench APIs
    path("api/recent-imports/", api_recent_imports, name="api-recent-imports"),
    path("api/multiply-projection/", api_multiply_projection, name="api-multiply-projection"),
    path(
        "api/workbench/chordal-analysis/<str:exercise_id>/",
        api_chordal_analysis_review,
        name="api-chordal-analysis-review",
    ),
    path("api/exercises/bulk-delete/", api_bulk_delete_exercises, name="api-bulk-delete-exercises"),
    path("debug/taxonomy/", taxonomy_debug_view, name="taxonomy-debug"),
]
