from django.urls import path

from apps.dashboard.views.groups import (
    groups_list_view,
    group_add_view,
    group_edit_view,
    group_delete_view,
    remove_member,
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
    course_add_view,
    course_edit_view,
    course_delete_view,
    course_activity_view,
)
from apps.dashboard.views.exercises import (
    exercises_list_view,
    exercise_edit_view,
    exercise_delete_view,
    exercise_add_view,
)
from apps.dashboard.views.performance import performance_list_view, playlist_performance_view
from apps.dashboard.views.playlists import (
    playlists_list_view,
    playlist_add_view,
    playlist_edit_view,
    playlist_delete_view,
)
from apps.dashboard.views.preferences import dashboard_preferences_view
from apps.dashboard.views.supervision import (
    supervisors_view,
    supervisors_courses_view,
    subscribers_view,
    unsubscribe_view,
    remove_subscriber_view,
    accept_subscription_view,
    decline_subscription_view,
    unsubscribe_confirmation,
    remove_subscriber_confirmation,
)

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_index_view, name="index"),
    # Exercises
    path("exercises/", exercises_list_view, name="exercises-list"),
    path("exercises/add/", exercise_add_view, name="add-exercise"),
    path("exercises/<str:exercise_id>/", exercise_edit_view, name="edit-exercise"),
    path("exercises/<str:exercise_id>/delete/", exercise_delete_view, name="delete-exercise"),
    # Playlists
    path("playlists/", playlists_list_view, name="playlists-list"),
    path("playlists/add/", playlist_add_view, name="add-playlist"),
    path("playlists/<str:playlist_slug>/", playlist_edit_view, name="edit-playlist"),
    path("playlists/<str:playlist_slug>/delete/", playlist_delete_view, name="delete-playlist"),
    # Courses
    path("courses/", courses_list_view, name="courses-list"),
    path("courses/add/", course_add_view, name="add-course"),
    path("courses/<str:course_slug>/", course_edit_view, name="edit-course"),
    path("courses/<str:course_slug>/delete/", course_delete_view, name="delete-course"),
    path("courses/<str:course_slug>/activity/", course_activity_view, name="course-activity"),
    # Performances
    path("performances/<int:subscriber_id>/", performance_list_view, name="subscriber-performances"),
    path("performances/", performance_list_view, name="performed-playlists"),
    path(
        "playlist-performance/<int:subscriber_id>/<str:playlist_id>/",
        playlist_performance_view,
        name="subscriber-playlist-performance",
    ),
    path("playlist-performance/<str:playlist_id>/", playlist_performance_view, name="playlist-performance"),
    # Subscriptions / Subscribers
    path("subscriptions/", supervisors_view, name="subscriptions"),
    path("subscriptions-courses/", supervisors_courses_view, name="subscriptions-courses"),
    path("unsubscribe/<int:supervisor_id>/confirm/", unsubscribe_confirmation, name="unsubscribe-confirmation"),
    path("unsubscribe/<int:supervisor_id>/", unsubscribe_view, name="unsubscribe"),
    path("subscribers/", subscribers_view, name="subscribers"),
    path(
        "accept-subscriber/<int:supervisor_id>/<int:subscriber_id>/",
        accept_subscription_view,
        name="accept-subscription",
    ),
    path(
        "decline-subscriber/<int:supervisor_id>/<int:subscriber_id>/",
        decline_subscription_view,
        name="decline-subscription",
    ),
    path(
        "remove-subscriber/<int:subscriber_id>/confirm/",
        remove_subscriber_confirmation,
        name="remove-subscriber-confirmation",
    ),
    path("remove-subscriber/<int:subscriber_id>/", remove_subscriber_view, name="remove-subscriber"),
    # Groups
    path("groups/", groups_list_view, name="groups-list"),
    path("groups/add/", group_add_view, name="add-group"),
    path("groups/<str:group_id>/", group_edit_view, name="edit-group"),
    path("groups/<str:group_id>/delete/", group_delete_view, name="delete-group"),
    path("groups/<str:group_id>/remove-member/<int:member_id>/", remove_member, name="remove-group-member"),
    # Preferences
    path("preferences/", dashboard_preferences_view, name="preferences"),
    # Import/Export
    path("export/exercises/", ExerciseExportView.as_view(), name="export-exercises"),
    path("import/exercises/", ExerciseImportView.as_view(), name="import-exercises"),
    path("export/playlists/", PlaylistExportView.as_view(), name="export-playlists"),
    path("import/playlists/", PlaylistImportView.as_view(), name="import-playlists"),
    path("export/courses/", CourseExportView.as_view(), name="export-courses"),
    path("import/courses/", CourseImportView.as_view(), name="import-courses"),
]
