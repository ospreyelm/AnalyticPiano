"""Decorators for teacher-only views."""
from functools import wraps

from django.shortcuts import redirect

from apps.accounts.models import ROLE_TEACHER


def teacher_required(view_func):
    """Allow only authenticated users with role=teacher OR superuser.

    Unauthenticated or unauthorised users are redirected to the login page.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            from django.conf import settings

            login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
            return redirect(f"{login_url}?next={request.path}")
        if user.is_superuser or user.role == ROLE_TEACHER:
            return view_func(request, *args, **kwargs)
        # Authenticated but wrong role — redirect to login
        from django.conf import settings

        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        return redirect(f"{login_url}?next={request.path}")

    return _wrapped
