"""
Scopes the SameSite=None;Secure cookie posture and frame-ancestors CSP
header to LTI-launched sessions only -- Phase 5 of
docs/superpowers/plans/2026-07-02-lti-integration.md.

Direct-login sessions are never touched: this only acts when
request.session["lti_issuer"] has been set, which happens in exactly one
place (apps.lti.views.launch_view, on a successful launch). An LTI
launch typically renders inside an iframe on the institution's own LMS
domain -- a genuinely cross-site context, where browsers require
SameSite=None;Secure before they'll even store the session cookie, and
where the default same-origin framing posture would otherwise block the
LMS from framing HarmonyLab at all.
"""
from django.conf import settings


class LtiFramingMiddleware:
    """Must be positioned before SessionMiddleware in MIDDLEWARE: Django
    runs process_response in reverse declaration order, so this needs to
    see the session cookie *after* SessionMiddleware has set it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        session = getattr(request, "session", None)
        issuer = session.get("lti_issuer") if session is not None else None
        if not issuer:
            return response

        response["Content-Security-Policy"] = f"frame-ancestors 'self' {issuer};"

        # Secure cookies are dropped by browsers over plain HTTP -- only
        # force the attribute when the connection actually is HTTPS, same
        # guard pylti1p3's own DjangoCookieService uses for its cookies.
        if request.is_secure():
            for cookie_name in (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
                if cookie_name in response.cookies:
                    response.cookies[cookie_name]["samesite"] = "None"
                    response.cookies[cookie_name]["secure"] = True

        return response
