"""M-10: account management.

Changing your own password needs the current one, and any password change
signs the user out everywhere else. The last admin cannot be demoted. Login
gives one generic error whether the account is unknown, deactivated or the
password is wrong. Email addresses are stored and compared in lower case.
"""

import pytest

from models.auth import hash_password

GOOD = 'CorrectHorse12'
NEW = 'BatteryStaple34'


@pytest.fixture
def accounts(live_app):
    conn = live_app.db()
    conn.execute('UPDATE users SET password_hash = ?', (hash_password(GOOD),))
    conn.commit()
    conn.close()
    return live_app


def _active_sessions(live, user):
    conn = live.db()
    count = conn.execute('SELECT COUNT(*) FROM user_sessions WHERE user_id = ? AND is_active = 1',
                         (live.user_ids[user],)).fetchone()[0]
    conn.close()
    return count


def _login(live, email, password):
    return live.app.test_client().post('/api/auth/login', json={'email': email, 'password': password})


# ------------------------------------------------------------- password change

def test_own_password_change_needs_current_password(accounts):
    client = accounts.client_for('owner')
    me = accounts.user_ids['owner']
    assert client.put(f'/api/users/{me}', json={'password': NEW}).status_code == 400
    assert client.put(f'/api/users/{me}', json={'password': NEW, 'current_password': 'Wrong12345678'}).status_code == 403
    assert _login(accounts, 'owner@example.com', NEW).status_code == 401


def test_own_password_change_signs_out_other_sessions(accounts):
    other_device = accounts.client_for('owner')
    client = accounts.client_for('owner')
    me = accounts.user_ids['owner']
    resp = client.put(f'/api/users/{me}', json={'password': NEW, 'current_password': GOOD})
    assert resp.status_code == 200
    assert client.get('/api/engagements').status_code == 200        # this session stays
    assert other_device.get('/api/engagements').status_code == 401  # others are revoked
    assert _login(accounts, 'owner@example.com', NEW).status_code == 200


def test_admin_reset_of_another_user_needs_no_current_password_and_revokes(accounts):
    victim_session = accounts.client_for('editor')
    admin = accounts.client_for('admin')
    resp = admin.put(f"/api/users/{accounts.user_ids['editor']}", json={'password': NEW})
    assert resp.status_code == 200
    assert victim_session.get('/api/engagements').status_code == 401
    assert _active_sessions(accounts, 'editor') == 0


# ------------------------------------------------------------- last admin

def test_last_admin_cannot_be_demoted(accounts):
    admin = accounts.client_for('admin')
    resp = admin.put(f"/api/users/{accounts.user_ids['admin']}", json={'role': 'tester'})
    assert resp.status_code == 400
    conn = accounts.db()
    assert conn.execute("SELECT role FROM users WHERE username = 'admin'").fetchone()[0] == 'admin'
    conn.close()


def test_admin_can_be_demoted_when_another_admin_exists(accounts):
    admin = accounts.client_for('admin')
    assert admin.put(f"/api/users/{accounts.user_ids['owner']}", json={'role': 'admin'}).status_code == 200
    assert admin.put(f"/api/users/{accounts.user_ids['admin']}", json={'role': 'tester'}).status_code == 200


# ------------------------------------------------------------- login errors

@pytest.mark.parametrize('email,password', [
    ('nobody@example.com', GOOD),        # unknown account
    ('owner@example.com', 'Wrong12345678'),  # wrong password
    ('viewer@example.com', GOOD),        # deactivated, right password
    ('viewer@example.com', 'Wrong12345678'),  # deactivated, wrong password
])
def test_login_failures_share_one_error(accounts, email, password):
    conn = accounts.db()
    conn.execute("UPDATE users SET is_active = 0 WHERE username = 'viewer'")
    conn.commit()
    conn.close()
    resp = _login(accounts, email, password)
    assert resp.status_code == 401
    assert resp.get_json()['error'] == 'Invalid credentials'


# ------------------------------------------------------------- email case

def test_created_email_is_normalised_and_unique_ignoring_case(accounts):
    admin = accounts.client_for('admin')
    resp = admin.post('/api/users', json={'username': 'mixed', 'email': '  Mixed.Case@Example.COM ',
                                          'password': GOOD, 'role': 'tester'})
    assert resp.status_code == 201
    assert resp.get_json()['email'] == 'mixed.case@example.com'
    assert _login(accounts, 'MIXED.case@example.com', GOOD).status_code == 200

    dup = admin.post('/api/users', json={'username': 'mixed2', 'email': 'mixed.case@EXAMPLE.com',
                                         'password': GOOD, 'role': 'tester'})
    assert dup.status_code == 409


def test_updated_email_is_normalised_and_unique_ignoring_case(accounts):
    admin = accounts.client_for('admin')
    owner = accounts.user_ids['owner']
    assert admin.put(f'/api/users/{owner}', json={'email': 'EDITOR@example.com'}).status_code == 409
    assert admin.put(f'/api/users/{owner}', json={'email': ' New.Owner@Example.com'}).status_code == 200
    conn = accounts.db()
    assert conn.execute('SELECT email FROM users WHERE id = ?', (owner,)).fetchone()[0] == 'new.owner@example.com'
    conn.close()
