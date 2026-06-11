"""URL configuration for the teacher app."""
from django.urls import path

from apps.teacher.views import create_course_view, wizard_view

app_name = "teacher"

urlpatterns = [
    path("courses/new/", wizard_view, name="course-wizard"),
    path("courses/create/", create_course_view, name="course-create"),
]
