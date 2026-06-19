from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from apps.accounts.models import ROLE_TEACHER

class TeacherAccessMiddleware:
    """Enforces central teacher role check on all URLs starting with /teacher/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/teacher/"):
            # Anonymous users are allowed to pass through so standard login decorators (like @teacher_required)
            # can handle the redirect with next=...
            if request.user.is_authenticated:
                # If they are not a teacher and not a superuser, they are restricted
                if not (request.user.is_superuser or request.user.role == ROLE_TEACHER):
                    if request.method == "GET":
                        return redirect(reverse("student:home"))
                    else:
                        return JsonResponse({
                            "error": "Permission denied.",
                            "redirectUrl": reverse("student:home")
                        }, status=403)
        return self.get_response(request)
