"""
Custom middleware for HarmonyLab.
"""


class DisableCSPMiddleware:
    """
    Middleware to add permissive CSP headers for local development.
    WARNING: This should ONLY be used in local/dev environments, never in production!
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Set permissive CSP that allows unsafe-eval and unsafe-inline
        # This is needed for RequireJS config injection and Tone.js
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: cdnjs.cloudflare.com unpkg.com cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' cdnjs.cloudflare.com unpkg.com cdn.jsdelivr.net; "
            "media-src 'self' blob:; "
            "worker-src 'self' blob:;"
        )
        
        response['Content-Security-Policy'] = csp_policy
        # Also set the report-only version for debugging
        # response['Content-Security-Policy-Report-Only'] = csp_policy
        
        print(f"[DisableCSPMiddleware] Set CSP header: {csp_policy[:100]}...")
        
        return response
