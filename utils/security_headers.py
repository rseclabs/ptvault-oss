"""Security headers for every response (used by app.py's after_request hook).

Kept outside app.py so tests can import the real code: app.py opens the
configured database when it is imported.
"""

from flask import request

from config import Config

# Applied by routes that return content a user or a scanned target controls:
# uploaded evidence files and exported report HTML (M-4). If a browser renders
# such a response directly, it runs in a unique origin with no script, so it
# cannot reach the API with the user's session.
SANDBOX_CSP = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"

# CyberChef requires a relaxed CSP (blob: workers, data: URIs, eval for recipes).
CYBERCHEF_CSP = (
    "default-src 'self' blob: data:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data:; "
    "style-src 'self' 'unsafe-inline' blob: data:; "
    "worker-src 'self' blob:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' blob: data:; "
    "font-src 'self' data: blob:; "
    "frame-src 'none'"
)

# Every library and font is vendored under static/vendor, so nothing loads
# from a third-party host.
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-src 'self' https://gchq.github.io"
)


def untrusted_response_headers(response):
    """Mark a response that carries untrusted content (sandbox CSP, no sniffing)."""
    response.headers['Content-Security-Policy'] = SANDBOX_CSP
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def apply_security_headers(response):
    """after_request hook: add the security headers to a response."""
    # Disable caching for JS/CSS in dev so changes take effect on normal reload
    if Config.ENVIRONMENT != 'production' and request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store'

    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # A route that set its own policy (the sandbox for untrusted content) keeps it.
    if 'Content-Security-Policy' not in response.headers:
        if request.path.startswith('/api/admin/cyberchef'):
            response.headers['Content-Security-Policy'] = CYBERCHEF_CSP
        else:
            response.headers['Content-Security-Policy'] = DEFAULT_CSP

    # HSTS only in production
    if Config.ENVIRONMENT == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response
