from django.urls import path
from django.views.generic import TemplateView

app_name = "exercises"

urlpatterns = [
    path(
        "admin/exercises/playlist/<str:id>/performances/",
        TemplateView.as_view(template_name="admin/performances.html"),
        name="playlist_performance",
    ),
]
