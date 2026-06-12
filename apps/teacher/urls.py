"""URL configuration for the teacher app."""
from django.urls import path

from apps.teacher.views import (
    create_course_view,
    wizard_view,
    course_list_view,
    course_detail_view,
    update_pco_view,
    respread_view,
    add_playlist_view,
    add_group_view,
    suggest_units_view,
)

app_name = "teacher"

urlpatterns = [
    path("courses/new/", wizard_view, name="course-wizard"),
    path("courses/create/", create_course_view, name="course-create"),
    path("courses/", course_list_view, name="course-list"),
    path("courses/<str:course_id>/", course_detail_view, name="course-detail"),
    path("courses/<str:course_id>/update-pco/", update_pco_view, name="course-update-pco"),
    path("courses/<str:course_id>/respread/", respread_view, name="course-respread"),
    path("courses/<str:course_id>/add-playlist/", add_playlist_view, name="course-add-playlist"),
    path("courses/<str:course_id>/groups/", add_group_view, name="course-add-group"),
    path("play/api/suggest-units/", suggest_units_view, name="suggest-units"),
]
