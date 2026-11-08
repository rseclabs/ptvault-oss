"""L-2, L-3, L-10: errors do not leak internals, and debugging is opt-in.

- API errors carry no exception text or traceback unless PTVAULT_DEBUG is set
  (ENVIRONMENT defaults to development, so it cannot be the switch).
- No route returns str(e) in a 5xx response.
- /db-status needs an admin and returns no raw exception.
- The Werkzeug debugger runs only when asked for (--debug or PTVAULT_DEBUG),
  on a loopback interface, outside production and frozen builds.
"""

import pathlib
import re

import pytest
from flask import Flask

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECRET = 'no such table: secret_internal_table at /srv/ptvault/data/ptvault.db'


def _app():
    from utils.error_handler import handle_errors, internal_error
    app = Flask(__name__)

    @app.route('/decorated')
    @handle_errors
    def decorated():
        raise RuntimeError(SECRET)

    @app.route('/helper')
    def helper():
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as e:
            return internal_error(e)

    return app.test_client()


@pytest.mark.parametrize('path', ['/decorated', '/helper'])
def test_errors_are_generic_by_default(monkeypatch, path):
    from config import Config
    monkeypatch.setattr(Config, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(Config, 'DEBUG', False)
    resp = _app().get(path)
    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert 'secret_internal_table' not in body and 'Traceback' not in body and 'traceback' not in body


@pytest.mark.parametrize('path', ['/decorated', '/helper'])
def test_details_only_with_ptvault_debug(monkeypatch, path):
    from config import Config
    monkeypatch.setattr(Config, 'DEBUG', True)
    assert 'secret_internal_table' in _app().get(path).get_data(as_text=True)


@pytest.mark.parametrize('value, expected', [
    (None, False), ('', False), ('0', False), ('false', False), ('1', True), ('true', True), ('YES', True),
])
def test_debug_is_off_unless_set(monkeypatch, value, expected):
    # Never reload config here: a fresh Config class would carry the real data paths.
    from config import env_flag
    if value is None:
        monkeypatch.delenv('PTVAULT_DEBUG', raising=False)
    else:
        monkeypatch.setenv('PTVAULT_DEBUG', value)
    assert env_flag('PTVAULT_DEBUG') is expected


def test_no_route_returns_exception_text_in_a_server_error():
    pattern = re.compile(r'jsonify\([^\n]*str\(e\)[^\n]*\),\s*5\d\d|yield[^\n]*str\(e\)|DatabaseError\(f"[^"]*\{str\(e\)\}')
    hits = [f'{p.relative_to(ROOT)}:{s.count(chr(10), 0, m.start()) + 1}'
            for p in list((ROOT / 'routes').glob('*.py')) + [ROOT / 'middleware/auth.py', ROOT / 'app.py']
            for s in [p.read_text()] for m in pattern.finditer(s)]
    assert not hits, hits


def test_a_real_route_failure_is_generic(live_app, monkeypatch):
    """A route that used to return {"error": str(e)} on a database failure."""
    import routes.testplans as testplans
    from config import Config
    monkeypatch.setattr(Config, 'DEBUG', False)

    def boom(*args, **kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(testplans, '_get_accessible_plan', boom)
    resp = live_app.client_for('admin').get('/api/testplans/plans/1')
    assert resp.status_code == 500
    assert 'secret_internal_table' not in resp.get_data(as_text=True)


# ------------------------------------------------------------------ /db-status (app.py)

def test_db_status_needs_an_admin_and_hides_exceptions():
    source = (ROOT / 'app.py').read_text()
    block = source[source.index("@app.route('/db-status'"):source.index("if __name__ == '__main__':")]
    assert '@require_auth' in block and "@require_role('admin')" in block
    assert 'str(e)' not in block


# ------------------------------------------------------------------ debugger (L-10)

@pytest.mark.parametrize('requested, interface, environment, frozen, expected', [
    (False, 'localhost', 'development', False, False),   # no longer on by default
    (True, 'localhost', 'development', False, True),
    (True, '127.0.0.1', 'development', False, True),
    (True, '0.0.0.0', 'development', False, False),
    (True, 'localhost', 'production', False, False),
    (True, 'localhost', 'development', True, False),
])
def test_debugger_needs_an_explicit_request(requested, interface, environment, frozen, expected):
    from config import debugger_allowed
    assert debugger_allowed(requested, interface, environment, frozen) is expected


def test_app_uses_debugger_allowed():
    source = (ROOT / 'app.py').read_text()
    assert 'debugger_allowed(' in source and "'--debug'" in source
