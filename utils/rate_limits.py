"""Rate limits and client addresses (L-8).

- Login, setup and password changes have their own, tighter limits.
- Limits live in memory by default, which is per process: with several
  workers, set PTVAULT_RATELIMIT_STORAGE to a shared store (for example
  redis://host:6379/0, which needs the redis package).
- Behind a reverse proxy every request comes from the proxy's address, so all
  users would share one limit. Set PTVAULT_TRUSTED_PROXIES to the number of
  proxies in front of PTVault to use X-Forwarded-For; it is ignored otherwise,
  because a client could send that header itself.
"""

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

DEFAULT_LIMIT = '100 per minute'
LOGIN_LIMIT = '5 per minute'
SETUP_LIMIT = '3 per minute'
PASSWORD_CHANGE_LIMIT = '10 per minute'     # PUT /api/users/<id> (password, email, role)
UNLOCK_LIMIT = '5 per minute'               # POST /api/unlock (database passphrase)


def storage_uri():
    return os.environ.get('PTVAULT_RATELIMIT_STORAGE', '').strip() or 'memory://'


def trusted_proxies():
    value = os.environ.get('PTVAULT_TRUSTED_PROXIES', '').strip()
    return int(value) if value.isdigit() else 0


def configure_rate_limits(app, auth_limits=True):
    """Install the limiter (and ProxyFix when configured). Call after registering blueprints."""
    proxies = trusted_proxies()
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)

    limiter = Limiter(get_remote_address, app=app, default_limits=[DEFAULT_LIMIT], storage_uri=storage_uri())
    if auth_limits:
        for endpoint, limit in (('auth.login', LOGIN_LIMIT), ('auth.setup', SETUP_LIMIT),
                                ('users.update_user', PASSWORD_CHANGE_LIMIT),
                                ('unlock.unlock_database', UNLOCK_LIMIT)):
            view = app.view_functions.get(endpoint)
            if view is not None:
                # The limit is enforced by the wrapper limit() returns, so the wrapper
                # must replace the registered view. (app.py used to discard it, and
                # the login and setup limits were never applied.)
                app.view_functions[endpoint] = limiter.limit(limit)(view)
    return limiter
