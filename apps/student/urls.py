from django.urls import path
from . import views

app_name = "student"

urlpatterns = [
    path("login/", views.StudentLoginView.as_view(), name="login"),
    path("logout/", views.StudentLogoutView.as_view(), name="logout"),
    path("signup/", views.StudentSignupView.as_view(), name="signup"),
    path("", views.HomeView.as_view(), name="home"),
    path("units/<str:unit_n>/", views.UnitProgressView.as_view(), name="unit-progress"),
    path("units/<int:unit_num>/", views.UnitView.as_view(), name="unit"),
    path("units/<int:unit_num>/play/", views.PlayerView.as_view(), name="player"),
    path("unit1-challenge/<str:group_key>/", views.ChallengeView.as_view(), name="unit1-challenge"),
]
