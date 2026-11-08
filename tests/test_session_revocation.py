"""H-6: a JWT is accepted only while its user_sessions row is active.

Revocation, logout and idle expiry must hold even when no other session is
active, and an error while checking the session must refuse the request.
"""

import sqlite3

from models import auth as auth_model

PROBE = '/api/engagements'


def _session_rows(live, user='owner'):
    conn = live.db()
    rows = conn.execute('SELECT * FROM user_sessions WHERE user_id = ?', (live.user_ids[user],)).fetchall()
    conn.close()
    return rows


def test_session_record_is_stored(live_app):
    live_app.token_for('owner')
    rows = _session_rows(live_app)
    assert len(rows) == 1
    assert rows[0]['is_active'] == 1
    assert rows[0]['expires_at'] is not None


def test_active_session_is_accepted(live_app):
    assert live_app.client_for('owner').get(PROBE).status_code == 200


def test_token_without_session_row_is_refused(live_app):
    token = auth_model.create_session_token(live_app.user_ids['owner'], role='tester', username='owner')
    client = live_app.app.test_client()
    client.set_cookie('auth_token', token)
    assert client.get(PROBE).status_code == 401


def test_logout_of_the_only_session_revokes_the_token(live_app):
    client = live_app.client_for('owner')
    token = client.get_cookie('auth_token').value
    assert client.post('/api/auth/logout').status_code == 200

    replay = live_app.app.test_client()
    replay.set_cookie('auth_token', token)
    assert replay.get(PROBE).status_code == 401


def test_revoke_all_sessions_revokes_every_token(live_app):
    owner = live_app.client_for('owner')
    admin = live_app.client_for('admin')
    assert admin.post('/api/admin/revoke-sessions').status_code == 200

    assert owner.get(PROBE).status_code == 401
    assert admin.get(PROBE).status_code == 401


def test_idle_session_expires_and_stays_expired(live_app):
    client = live_app.client_for('owner')
    conn = live_app.db()
    conn.execute("UPDATE user_sessions SET last_active = datetime('now', '-1 day')")
    conn.commit()
    conn.close()

    first = client.get(PROBE)
    assert first.status_code == 401
    assert first.get_json()['error'] == 'session_idle_timeout'
    assert client.get(PROBE).status_code == 401


def test_session_past_expiry_is_refused(live_app):
    client = live_app.client_for('owner')
    conn = live_app.db()
    conn.execute("UPDATE user_sessions SET expires_at = datetime('now', '-1 minute')")
    conn.commit()
    conn.close()
    assert client.get(PROBE).status_code == 401


def test_session_check_error_fails_closed(live_app, monkeypatch):
    client = live_app.client_for('owner')

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError('no such table: user_sessions')

    monkeypatch.setattr('middleware.auth.check_session', broken, raising=False)
    assert client.get(PROBE).status_code != 200


def test_login_fails_when_session_cannot_be_recorded(live_app, monkeypatch):
    conn = live_app.db()
    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?',
                 (auth_model.hash_password('CorrectHorse12!'), 'owner'))
    conn.commit()
    conn.close()

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError('disk I/O error')

    monkeypatch.setattr('routes.auth.create_session_record', broken)
    resp = live_app.app.test_client().post(
        '/api/auth/login', json={'email': 'owner@example.com', 'password': 'CorrectHorse12!'})
    assert resp.status_code >= 500
    assert 'auth_token' not in resp.headers.get('Set-Cookie', '')
