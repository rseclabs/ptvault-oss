"""CSRF protection for the JSON API (L-8).

Mutating /api/ requests must send the CSRF token in an X-CSRF-Token header.

- Logged in (an auth_token cookie is present): the token must be
  session_csrf_token(auth_token), an HMAC of the session's auth token. A
  token planted in the cookie jar (another subdomain, an injected
  Set-Cookie) or taken from another session does not match.
- Before login (login and setup): double-submit, the header must equal the
  csrf_token cookie. Login is not exempt, so another site cannot log the
  browser in to an account of its choosing (login CSRF).

The token is kept in the readable csrf_token cookie so the front end can
copy it into the header; login and setup set it to the bound value.
"""

import hashlib
import hmac
import secrets
from urllib.parse import urlsplit

from flask import jsonify, request

from config import Config

CSRF_COOKIE = 'csrf_token'
CSRF_HEADER = 'X-CSRF-Token'
# Before login there is no session to bind to; these use double-submit.
PRE_AUTH_PATHS = frozenset(['/api/auth/login', '/api/auth/setup', '/api/unlock'])


def session_csrf_token(auth_token):
    """The CSRF token bound to one session."""
    key = str(Config.SECRET_KEY).encode('utf-8')
    return hmac.new(key, b'ptvault-csrf\0' + auth_token.encode('utf-8'), hashlib.sha256).hexdigest()


def issue_csrf_token():
    """Token for the current request: bound to the session if logged in, random otherwise."""
    auth_token = request.cookies.get('auth_token')
    return session_csrf_token(auth_token) if auth_token else secrets.token_hex(32)


def set_csrf_cookie(response, token):
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,            # the front end copies it into the header
        secure=(Config.ENVIRONMENT == 'production'),
        samesite='Lax',
        max_age=86400,
    )
    return response


# Browsers send Secure cookies to these over plain http (a secure context)
LOOPBACK_HOSTS = frozenset(['localhost', '127.0.0.1', '::1'])

INSECURE_COOKIE_HINT = (
    "CSRF token missing: your browser did not send PTVault's cookies. "
    "This instance runs with ENVIRONMENT=production, so its cookies are marked Secure "
    "and browsers only send them over HTTPS, which PTVault does not serve itself. "
    "Put PTVault behind a TLS reverse proxy such as nginx and open it with https://, "
    "or use http://localhost on the machine running it. "
    "See \"Running behind HTTPS\" in the README."
)


def secure_cookies_dropped():
    """True if this request came over plain http to a host the browser withholds Secure cookies from.

    In production every PTVault cookie is Secure, and PTVault serves only http,
    so a browser that opened http://<server-ip>:5000 never sends the cookies
    back: login and setup then fail the CSRF check with no hint why. Loopback
    is exempt (browsers treat it as secure), and so is https, including https
    ended at a proxy when PTVAULT_TRUSTED_PROXIES makes request.is_secure true.
    """
    if Config.ENVIRONMENT != 'production' or request.is_secure:
        return False
    if request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip().lower() == 'https':
        return False                       # TLS at a proxy PTVault was not told to trust
    host = (urlsplit('//' + (request.host or '')).hostname or '').lower()
    return not (host in LOOPBACK_HOSTS or host.endswith('.localhost'))


def csrf_protect():
    """before_request hook: refuse mutating API requests without a valid token."""
    if request.method in ('GET', 'HEAD', 'OPTIONS') or not request.path.startswith('/api/'):
        return None

    header = request.headers.get(CSRF_HEADER) or ''
    auth_token = request.cookies.get('auth_token')
    if auth_token and request.path not in PRE_AUTH_PATHS:
        expected = session_csrf_token(auth_token)
    else:
        expected = request.cookies.get(CSRF_COOKIE) or ''

    if not expected and secure_cookies_dropped():
        # The message is only a hint: the request is refused all the same
        return jsonify({"error": INSECURE_COOKIE_HINT}), 403
    if not header or not expected:
        return jsonify({"error": "CSRF token missing"}), 403
    if not hmac.compare_digest(header, expected):
        return jsonify({"error": "CSRF token mismatch"}), 403
    return None
