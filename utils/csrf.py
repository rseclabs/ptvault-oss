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

from flask import jsonify, request

from config import Config

CSRF_COOKIE = 'csrf_token'
CSRF_HEADER = 'X-CSRF-Token'
# Before login there is no session to bind to; these use double-submit.
PRE_AUTH_PATHS = frozenset(['/api/auth/login', '/api/auth/setup'])


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

    if not header or not expected:
        return jsonify({"error": "CSRF token missing"}), 403
    if not hmac.compare_digest(header, expected):
        return jsonify({"error": "CSRF token mismatch"}), 403
    return None
