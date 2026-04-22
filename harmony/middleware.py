"""
Custom middleware for HarmonyLab.
"""


class DisableCSPMiddleware:
    """
    Middleware to add permissive CSP headers for local development.
    Also disables browser caching for JS files so edits take effect immediately.
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

        # Disable browser caching for JS files in development so edits are always picked up
        path = request.path
        if path.startswith('/static/') and path.endswith('.js'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
        
        return response
