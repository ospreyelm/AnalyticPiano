from django.urls import reverse

from apps.accounts.models import ROLE_TEACHER


def home_url_for_user(user):
    if not user.is_authenticated:
        return reverse("student:login")
    if user.is_superuser or user.role == ROLE_TEACHER:
        return reverse("teacher:course-list")
    return reverse("student:home")
