"""L-8 and L-9: CSRF, rate limits and audit coverage.

L-8: login and setup are no longer CSRF-exempt (login CSRF); once a user is
logged in, the CSRF token is bound to their session (an HMAC of the auth
token), so a token planted in the cookie jar is useless; password changes have
their own rate limit; the limiter's storage is configurable and proxy headers
are trusted only when PTVAULT_TRUSTED_PROXIES says so.

L-9: every successful mutating API call is written to the audit log once.
"""

import pathlib

import pytest

from tests.conftest import ENGAGEMENT_A

ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSWORD = 'Correct-Horse-Battery-9'


@pytest.fixture
def csrf_app(live_app):
    from utils.csrf import csrf_protect
    live_app.app.before_request(csrf_protect)
    conn = live_app.db()
    from models.auth import hash_password
    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', (hash_password(PASSWORD), 'editor'))
    conn.commit()
    conn.close()
    return live_app


def _login(client, token='t' * 64):
    client.set_cookie('csrf_token', token)
    return client.post('/api/auth/login', json={'username': 'editor', 'password': PASSWORD},
                       headers={'X-CSRF-Token': token})


# ------------------------------------------------------------------ L-8: login CSRF

@pytest.mark.parametrize('path, body', [
    ('/api/auth/login', {'username': 'editor', 'password': PASSWORD}),
    ('/api/auth/setup', {'email': 'x@example.com', 'password': PASSWORD}),
])
def test_login_and_setup_need_a_csrf_token(csrf_app, path, body):
    client = csrf_app.app.test_client()
    assert client.post(path, json=body).status_code == 403
    client.set_cookie('csrf_token', 'a' * 64)
    assert client.post(path, json=body, headers={'X-CSRF-Token': 'b' * 64}).status_code == 403


def test_login_with_a_matching_token_works_and_binds_the_csrf_token(csrf_app):
    from utils.csrf import session_csrf_token
    client = csrf_app.app.test_client()
    resp = _login(client)
    assert resp.status_code == 200, resp.get_json()
    auth = client.get_cookie('auth_token').value
    assert client.get_cookie('csrf_token').value == session_csrf_token(auth)


# ------------------------------------------------------------------ L-8: session-bound token

def test_authenticated_writes_need_the_session_bound_token(csrf_app):
    client = csrf_app.app.test_client()
    assert _login(client).status_code == 200
    with client.session_transaction() as sess:
        sess['active_engagement_id'] = ENGAGEMENT_A

    # A planted double-submit pair (cookie == header) is not enough once logged in.
    client.set_cookie('csrf_token', 'p' * 64)
    resp = client.post('/api/hosts', json={'ip': '10.0.0.9'}, headers={'X-CSRF-Token': 'p' * 64})
    assert resp.status_code == 403

    token = client.get('/api/auth/csrf-token').get_json()['csrf_token']
    resp = client.post('/api/hosts', json={'ip': '10.0.0.9'}, headers={'X-CSRF-Token': token})
    assert resp.status_code in (200, 201), resp.get_json()


def test_a_token_from_another_session_is_refused(csrf_app):
    from utils.csrf import session_csrf_token
    client = csrf_app.app.test_client()
    assert _login(client).status_code == 200
    other = session_csrf_token(csrf_app.token_for('viewer'))
    resp = client.post('/api/hosts', json={'ip': '10.0.0.8'}, headers={'X-CSRF-Token': other})
    assert resp.status_code == 403


def test_app_uses_the_shared_csrf_check():
    source = (ROOT / 'app.py').read_text()
    assert 'csrf_protect' in source and "'/api/auth/login'" not in source


# ------------------------------------------------------------------ L-8: rate limits and proxies

def test_password_changes_are_rate_limited(live_app):
    from utils.rate_limits import PASSWORD_CHANGE_LIMIT, configure_rate_limits
    configure_rate_limits(live_app.app)
    client = live_app.client_for('admin')
    user_id = live_app.user_ids['viewer']
    allowed = int(PASSWORD_CHANGE_LIMIT.split()[0])
    codes = [client.put(f'/api/users/{user_id}', json={'full_name': 'V'}).status_code for _ in range(allowed + 1)]
    assert codes[-1] == 429 and 429 not in codes[:-1]


def test_login_is_rate_limited(live_app):
    # Before this change the 5/min login limit was registered but never enforced.
    from utils.rate_limits import LOGIN_LIMIT, configure_rate_limits
    configure_rate_limits(live_app.app)
    client = live_app.app.test_client()
    allowed = int(LOGIN_LIMIT.split()[0])
    codes = [client.post('/api/auth/login', json={'username': 'editor', 'password': 'wrong-guess'}).status_code
             for _ in range(allowed + 1)]
    assert codes[:-1] == [401] * allowed and codes[-1] == 429


def test_rate_limit_storage_is_configurable(monkeypatch):
    from utils.rate_limits import storage_uri
    monkeypatch.delenv('PTVAULT_RATELIMIT_STORAGE', raising=False)
    assert storage_uri() == 'memory://'
    monkeypatch.setenv('PTVAULT_RATELIMIT_STORAGE', 'redis://localhost:6379/0')
    assert storage_uri() == 'redis://localhost:6379/0'


@pytest.mark.parametrize('value, proxied', [(None, False), ('0', False), ('1', True), ('2', True), ('x', False)])
def test_forwarded_headers_are_trusted_only_when_configured(monkeypatch, value, proxied):
    from flask import Flask
    from werkzeug.middleware.proxy_fix import ProxyFix
    from utils.rate_limits import configure_rate_limits
    if value is None:
        monkeypatch.delenv('PTVAULT_TRUSTED_PROXIES', raising=False)
    else:
        monkeypatch.setenv('PTVAULT_TRUSTED_PROXIES', value)
    app = Flask(__name__)
    configure_rate_limits(app, auth_limits=False)
    assert isinstance(app.wsgi_app, ProxyFix) is proxied


def test_app_uses_the_shared_rate_limits():
    assert 'configure_rate_limits(app)' in (ROOT / 'app.py').read_text()


# ------------------------------------------------------------------ L-9: audit coverage

def _audit_rows(live, **where):
    conn = live.db()
    clause = ' AND '.join(f'{k} = ?' for k in where) or '1'
    rows = conn.execute(f'SELECT action, resource_type, resource_id, engagement_id, user_id, details '
                        f'FROM audit_log WHERE {clause} ORDER BY id', tuple(where.values())).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_host_and_credential_changes_are_audited(live_app):
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    host = client.post('/api/hosts', json={'ip': '10.0.0.5'}).get_json()
    host_id = host.get('id') or host.get('host', {}).get('id')
    client.put(f'/api/hosts/{host_id}', json={'hostname': 'h'})
    cred = client.post(f'/api/hosts/{host_id}/credentials',
                       json={'username': 'u', 'password': 'p', 'password_type': 'clear_text'})
    assert cred.status_code == 201
    client.delete(f'/api/hosts/{host_id}')

    rows = _audit_rows(live_app, user_id=live_app.user_ids['editor'])
    seen = {(r['action'], r['resource_type']) for r in rows}
    assert {('create', 'hosts'), ('update', 'hosts'), ('delete', 'hosts')} <= seen, rows
    assert any(r['action'] == 'create' and 'credentials' in (r['details'] or '') for r in rows)
    assert all(r['engagement_id'] == ENGAGEMENT_A for r in rows)


def test_engagement_update_and_bulk_delete_are_audited(live_app):
    client = live_app.client_for('owner', active_engagement=ENGAGEMENT_A)
    assert client.put(f'/api/engagements/{ENGAGEMENT_A}', json={'description': 'd'}).status_code == 200
    conn = live_app.db()
    ev = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (?, 'note', 't')",
                      (ENGAGEMENT_A,)).lastrowid
    conn.commit()
    conn.close()
    assert client.post('/api/evidence/bulk', json={'operation': 'delete', 'evidence_ids': [ev]}).status_code == 200
    rows = _audit_rows(live_app, user_id=live_app.user_ids['owner'])
    assert any(r['action'] == 'update' and r['resource_type'] == 'engagements' and r['resource_id'] == ENGAGEMENT_A
               for r in rows), rows
    assert any(r['resource_type'] == 'evidence' and 'bulk' in (r['details'] or '') for r in rows), rows


def test_failed_and_read_only_requests_are_not_audited(live_app):
    viewer = live_app.client_for('viewer', active_engagement=ENGAGEMENT_A)
    assert viewer.post('/api/hosts', json={'ip': '10.0.0.6'}).status_code == 403
    viewer.get('/api/hosts')
    assert _audit_rows(live_app, user_id=live_app.user_ids['viewer']) == []


def test_explicitly_audited_actions_are_not_logged_twice(live_app):
    client = live_app.client_for('admin', active_engagement=ENGAGEMENT_A)
    assert client.delete(f'/api/engagements/{ENGAGEMENT_A}').status_code in (200, 204)
    rows = _audit_rows(live_app, user_id=live_app.user_ids['admin'])
    deletes = [r for r in rows if r['action'] == 'delete' and r['resource_id'] == ENGAGEMENT_A]
    assert len(deletes) == 1, rows
