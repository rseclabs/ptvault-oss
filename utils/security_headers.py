"""Security headers for every response (used by app.py's after_request hook).

Kept outside app.py so tests can import the real code: app.py opens the
configured database when it is imported.
"""

import re
import unicodedata
from urllib.parse import quote

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
# from a third-party host (L-1). No 'unsafe-eval': only CyberChef needs it,
# and it has its own policy above. No 'unsafe-inline' for scripts (L-21): event
# handlers are declared in data-on-* attributes (static/js/utils.js on()) and
# every script is a file, so an injected <img onerror> or <script> does not run
# even if some output is not escaped. Styles still allow inline style= attributes.
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def untrusted_response_headers(response):
    """Mark a response that carries untrusted content (sandbox CSP, no sniffing)."""
    response.headers['Content-Security-Policy'] = SANDBOX_CSP
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Evidence files are decrypted for this response only: keep them out of the
    # browser's disk cache (send_file's default no-cache still stores them; L-29)
    response.headers['Cache-Control'] = 'no-store'
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


def attachment_disposition(filename, fallback='download'):
    """Content-Disposition for a download whose name comes from user data (L-12).

    filename= gets an ASCII-only name (letters, digits, . _ - and spaces), so a
    quote, line break or path in a report name cannot change the header;
    filename*= carries the full UTF-8 name, percent-encoded (RFC 6266/5987).
    """
    name = str(filename or '').replace('\\', '/').split('/')[-1]
    name = ''.join(ch for ch in name if unicodedata.category(ch)[0] != 'C').strip() or fallback
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    ascii_name = re.sub(r'[^A-Za-z0-9._ -]+', '_', ascii_name).strip(' ._') or fallback
    return f"attachment; filename=\"{ascii_name[:150]}\"; filename*=UTF-8''{quote(name[:150], safe='')}"
