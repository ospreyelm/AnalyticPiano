"""URL configuration for the LTI app."""
from django.urls import path

from apps.lti.views import jwks_view, launch_view, oidc_login_view

app_name = "lti"

urlpatterns = [
    path("login/", oidc_login_view, name="login"),
    path("launch/", launch_view, name="launch"),
    path("jwks/", jwks_view, name="jwks"),
]
