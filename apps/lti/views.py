"""
OIDC login, launch, and JWKS views.

Grade passback (Phase 6) of
docs/superpowers/plans/2026-07-02-lti-integration.md is not implemented
yet.
"""
from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoOIDCLogin
from pylti1p3.exception import LtiException, OIDCException
from pylti1p3.registration import Registration

from apps.accounts.models import ROLE_TEACHER
from apps.lti.services import (
    ToolConfig,
    check_launch_allowed,
    get_platform_for_launch,
    get_tool_keypair,
    resolve_user,
)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def oidc_login_view(request):
    """OIDC third-party login init -- the platform's launch link hits this
    first; we redirect back to the platform's own auth endpoint."""
    tool_conf = ToolConfig()
    oidc_login = DjangoOIDCLogin(request, tool_conf)
    target_link_uri = request.POST.get("target_link_uri") or request.GET.get("target_link_uri")
    try:
        return oidc_login.redirect(target_link_uri)
    except OIDCException as exc:
        return render(request, "lti/launch_error.html", {"message": str(exc)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def launch_view(request):
    """The signed launch. Validates the JWT, then applies the FERPA
    readiness gate before anything resembling course data is touched."""
    tool_conf = ToolConfig()
    message_launch = DjangoMessageLaunch(request, tool_conf)
    try:
        message_launch.validate()
    except LtiException as exc:
        return render(request, "lti/launch_error.html", {"message": str(exc)}, status=400)

    platform = get_platform_for_launch(message_launch)
    if not check_launch_allowed(platform):
        return render(request, "lti/launch_not_ready.html", {"platform": platform})

    user = resolve_user(message_launch, platform)
    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)

    # Flags this session as LTI-originated for apps.lti.middleware
    # .LtiFramingMiddleware, which scopes the SameSite=None;Secure cookie
    # posture and frame-ancestors CSP to exactly this session -- direct-
    # login sessions are never touched.
    request.session["lti_issuer"] = platform.issuer

    if user.role == ROLE_TEACHER:
        return redirect("teacher:course-list")
    return redirect("student:home")


def jwks_view(request):
    """HarmonyLab's own public JWKS -- one tool-wide keypair, not per
    platform (see services.get_tool_keypair)."""
    _, public_key = get_tool_keypair()
    return JsonResponse({"keys": [Registration.get_jwk(public_key)]})
