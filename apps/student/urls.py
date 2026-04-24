from django.urls import path
from . import views

app_name = "student"

urlpatterns = [
    path("login/", views.StudentLoginView.as_view(), name="login"),
    path("", views.HomeView.as_view(), name="home"),
    path("units/<int:unit_num>/", views.UnitView.as_view(), name="unit"),
    path("units/<int:unit_num>/play/", views.PlayerView.as_view(), name="player"),
]
